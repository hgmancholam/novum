"""RF-06 question classifier wrapper.

Calls ``LLMRole.CLASSIFIER`` and maps the 1-8 taxonomy buckets to the
5-value ``QuestionType`` enum. Buckets 6/7/8 (or ``answerable=False``)
return ``(None, verdict)``; the orchestrator emits ``honest_unanswerable``.
"""

from __future__ import annotations

from app.domain.enums import QuestionType
from app.llm import LLMRole, QuestionClassification, llm

_BUCKET_MAP: dict[int, QuestionType] = {
    1: QuestionType.FACTUAL,
    2: QuestionType.COMPARATIVE,
    3: QuestionType.DEFINITIONAL,
    4: QuestionType.CAUSAL,
    5: QuestionType.STATE_OF_ART,
}


async def classify_question(
    question: str,
) -> tuple[QuestionType | None, QuestionClassification]:
    """Classify ``question`` and return ``(mapped_type, raw_verdict)``.

    ``mapped_type is None`` signals the orchestrator must emit
    ``honest_unanswerable`` (RF-06 buckets 6/7/8 or ``answerable=False``).
    """
    verdict = await llm.call(
        role=LLMRole.CLASSIFIER,
        messages=[{"role": "user", "content": question}],
        response_model=QuestionClassification,
    )
    if not verdict.answerable or verdict.question_type not in _BUCKET_MAP:
        return None, verdict
    return _BUCKET_MAP[verdict.question_type], verdict
