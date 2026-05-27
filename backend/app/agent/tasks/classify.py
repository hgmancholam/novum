"""RF-06 question classifier wrapper.

Calls ``LLMRole.CLASSIFIER`` and returns the ``QuestionType`` enum value.
All 8 types are now answerable (WP-2.0 amendment) — no more
``honest_unanswerable`` emission from the classifier.

G9 (WP-2): after classification, detect empty comparatives ("best X",
"should I", etc.) without stated criteria and call the LLM to enumerate
plausible evaluation dimensions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import QuestionType
from app.domain.events import AmbiguityDetectedEvent
from app.llm import LLMRole, QuestionClassification, llm

_EMPTY_COMPARATIVE_MARKERS = (
    "best",
    "mejor",
    "better",
    "should i",
    "vale la pena",
    "worth it",
)


class AmbiguityDimensions(BaseModel):
    """LLM structured output for ambiguous comparative questions (G9)."""

    dimensions: list[str] = Field(min_length=2, max_length=6)


async def classify_question(
    question: str,
) -> tuple[QuestionType, QuestionClassification]:
    """Classify ``question`` and return ``(mapped_type, raw_verdict)``.

    WP-2.0: all 8 types are answerable. The LLM returns one of the 8
    lowercase snake_case strings; we convert it to the ``QuestionType``
    enum. If the string doesn't match, raise ``ValueError``.
    """
    verdict = await llm.call(
        role=LLMRole.CLASSIFIER,
        messages=[{"role": "user", "content": question}],
        response_model=QuestionClassification,
    )
    try:
        question_type = QuestionType(verdict.question_type)
    except ValueError as exc:
        raise ValueError(
            f"Classifier returned unrecognized question_type: {verdict.question_type!r}"
        ) from exc
    return question_type, verdict


async def detect_empty_comparative(
    question: str, classified_type: QuestionType
) -> AmbiguityDetectedEvent | None:
    """Detect underspecified comparative questions and emit AmbiguityDetectedEvent.

    G9 (WP-2): questions like "best programming language" or "should I use X"
    without explicit criteria ("for embedded systems", "to build a web app")
    trigger an LLM call to enumerate 2-6 plausible evaluation dimensions.

    Returns:
        AmbiguityDetectedEvent with dimensions if detected, else None.
    """
    if classified_type not in {QuestionType.COMPARATIVE, QuestionType.SUBJECTIVE_OPINION}:
        return None

    lowered = question.lower()
    if not any(m in lowered for m in _EMPTY_COMPARATIVE_MARKERS):
        return None

    # Heuristic: skip if question has explicit "for X" / "to Y" / "in Z" clause
    if any(c in lowered for c in (" for ", " to ", " in ", " para ", " en ")):
        return None

    # Ask the LLM for plausible dimensions
    dimensions = await classify_dimensions(question)
    if not dimensions:
        return None

    return AmbiguityDetectedEvent(
        ambiguous_phrase=question,
        possible_interpretations=dimensions,
        clarification_needed="The question lacks explicit evaluation criteria",
        dimensions=dimensions,
    )


async def classify_dimensions(question: str) -> list[str]:
    """Call the classifier LLM to enumerate evaluation dimensions for ambiguous questions.

    G9 contract:
    - Role: CLASSIFIER (reuse existing)
    - Structured output: AmbiguityDimensions with 2-6 dimensions
    - Returns: list of dimensions, or [] if LLM fails to meet min_length

    System prompt instructs the LLM to output 2-6 orthogonal evaluation
    dimensions that would meaningfully change the answer.
    """
    system_prompt = """You receive an underspecified comparative or opinion question (e.g. 'best programming language').
Output 2-6 short evaluation dimensions that, if the user picked one, would meaningfully change the answer
(e.g. 'performance', 'ecosystem maturity', 'learning curve', 'job market').

One to three words each, English only, no duplicates, no dimensions that are restatements of the question.
Return strict JSON matching the AmbiguityDimensions schema."""

    try:
        result = await llm.call(
            role=LLMRole.CLASSIFIER,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            response_model=AmbiguityDimensions,
        )
        return result.dimensions
    except Exception:
        # If LLM fails (rate limit, validation error, etc.), return []
        # This means "not ambiguous after all" and caller won't emit event
        return []
