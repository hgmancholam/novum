"""Chain-of-Verification (CoVe) for DEEP lane (IP-25 Phase F).

After synthesizing a draft answer, generate 3 verification questions and
check each against fresh evidence. If contradictions are found and budget
allows, re-draft with the contradicting evidence as context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, Field

from app.llm import LLMRole, llm
from app.seams.source import SourceResult
from app.sources.registry import SourceRegistry, get_registry

if TYPE_CHECKING:
    from app.agent.run_state import RunState

from app.agent.source_hints import build_source_hints  # noqa: E402

logger = structlog.get_logger(__name__)


class CoveQuestions(BaseModel):
    """Structured output for verification questions generation."""

    items: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="3 sharp verification questions",
    )


class CoveVerdict(BaseModel):
    """Structured output for verification verdict."""

    contradicts: bool = Field(
        ...,
        description="True if evidence contradicts the draft answer",
    )
    evidence: str = Field(
        ...,
        description="Relevant evidence text or reason for no contradiction",
    )


async def generate_verification_questions(draft: str) -> list[str]:
    """Generate 3 verification questions for a draft answer.

    Args:
        draft: The synthesized draft answer to verify

    Returns:
        List of exactly 3 verification questions (padded with empty strings
        if model returns fewer than 3, or clamped if it returns more)

    Raises:
        ValidationError: If model returns zero questions (Pydantic validation)
    """
    from app.llm.prompts import COVE_QUESTIONS_PROMPT

    logger.info("cove_generating_questions", draft_length=len(draft))

    response = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[
            {"role": "system", "content": COVE_QUESTIONS_PROMPT},
            {"role": "user", "content": f"Draft answer:\n{draft}"},
        ],
        response_model=CoveQuestions,
    )

    questions = response.items

    # Clamp to first 3 or pad to 3
    if len(questions) > 3:
        questions = questions[:3]
        logger.info("cove_questions_clamped", original_count=len(response.items))
    elif len(questions) < 3:
        original_count = len(questions)
        questions = questions + [""] * (3 - len(questions))
        logger.info("cove_questions_padded", original_count=original_count)

    logger.info("cove_questions_generated", count=len(questions))
    return questions


async def verify_question(
    question: str,
    draft: str,
    registry: SourceRegistry,
    state: RunState | None = None,
) -> CoveVerdict:
    """Verify a question against fresh evidence.

    Args:
        question: The verification question to check
        draft: The original draft answer
        registry: Source registry for searching evidence
        state: Optional run state — when provided, forwards
            ``language`` / ``question_type`` / ``expected_experts`` to the
            search call so the source can tighten its filters.

    Returns:
        CoveVerdict with contradiction flag and evidence text
    """
    logger.info("cove_verifying_question", question=question[:100])

    # Skip empty questions (from padding)
    if not question.strip():
        return CoveVerdict(
            contradicts=False,
            evidence="(skipped empty question)",
        )

    # Step 1: Search for evidence using first available source
    source_types = registry.types()
    if not source_types:
        logger.warning("cove_no_sources_available")
        return CoveVerdict(
            contradicts=False,
            evidence="no sources available",
        )

    source_type = source_types[0]
    source = registry.get(source_type)
    hints: dict[str, Any] = (
        build_source_hints(state) if state is not None else {}
    )
    try:
        results: list[SourceResult] = await source.search(
            query=question, max_results=3, **hints
        )
    except Exception as exc:
        logger.warning(
            "cove_search_failed",
            error=str(exc),
            source_type=source_type,
        )
        results = []

    if not results:
        logger.info("cove_no_evidence_found", question=question[:100])
        return CoveVerdict(
            contradicts=False,
            evidence="no evidence found",
        )

    # Step 2: Build context from top-3 results
    evidence_context = "\n\n".join(
        f"Source {i+1} ({result.title}):\n{result.content or result.snippet}"
        for i, result in enumerate(results[:3])
    )

    # Step 3: Ask judge to detect contradiction
    from app.llm.prompts import COVE_VERIFICATION_PROMPT

    verdict = await llm.call(
        role=LLMRole.JUDGE,
        messages=[
            {"role": "system", "content": COVE_VERIFICATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Verification question: {question}\n\n"
                    f"Draft answer: {draft}\n\n"
                    f"Fresh evidence:\n{evidence_context}"
                ),
            },
        ],
        response_model=CoveVerdict,
    )

    logger.info(
        "cove_verification_complete",
        contradicts=verdict.contradicts,
        evidence_length=len(verdict.evidence),
    )

    return verdict
