"""Meta-judge LLM helpers (BRD-26 §4.2, IP Área 6).

Two pure-function helpers that wrap the structured LLM calls:

- ``evaluate_value_of_continuation`` — Value-of-Continuation pass.
- ``generate_adversarial_objections`` — Adversarial Completeness pass.

Both helpers build the user-turn payload locally so callers only have to
hand in the small ``MetaJudgeContext`` view. The structured ``ROLE_PROMPTS``
system message is auto-injected by ``LLMClient.call`` for VoC; the
adversarial helper supplies its own system message explicitly so it does
not depend on which prompt is the META_JUDGE default.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.meta_stop import (
    AdversarialCompletenessVerdict,
    ValueOfContinuationVerdict,
)
from app.llm.client import LLMClient
from app.llm.prompts import META_JUDGE_ADVERSARIAL_PROMPT, META_JUDGE_VOC_PROMPT
from app.llm.roles import LLMRole


@dataclass(frozen=True, slots=True)
class MetaJudgeContext:
    """Minimal projection of run state the meta-judge needs."""

    question: str
    answer_kind: str | None
    lane: str
    subclaim_count: int
    evidence_count: int
    authority_mix: dict[str, int]
    structural_confidence: float
    judge_confidence: float | None
    threshold: float
    rounds_used: int
    rounds_remaining: int
    last_judge_rationale: str | None
    draft_prose: str | None = None


def _voc_user_message(ctx: MetaJudgeContext) -> str:
    return (
        f"Question: {ctx.question}\n"
        f"AnswerKind: {ctx.answer_kind or 'unknown'}\n"
        f"Lane: {ctx.lane}\n"
        f"Sub-claims: {ctx.subclaim_count}\n"
        f"Evidence count: {ctx.evidence_count}\n"
        f"Authority mix: {ctx.authority_mix}\n"
        f"S_effective: {ctx.structural_confidence:.3f}\n"
        f"J: {ctx.judge_confidence if ctx.judge_confidence is None else round(ctx.judge_confidence, 3)}\n"
        f"Threshold: {ctx.threshold:.2f}\n"
        f"Rounds used / remaining: {ctx.rounds_used} / {ctx.rounds_remaining}\n"
        f"Last judge rationale: {ctx.last_judge_rationale or '(none)'}\n"
    )


def _adversarial_user_message(ctx: MetaJudgeContext) -> str:
    return (
        f"Question: {ctx.question}\n"
        f"AnswerKind: {ctx.answer_kind or 'unknown'}\n"
        f"Draft:\n{ctx.draft_prose or '(no draft available)'}\n"
        f"Evidence count: {ctx.evidence_count}\n"
        f"Authority mix: {ctx.authority_mix}\n"
    )


async def evaluate_value_of_continuation(
    client: LLMClient, ctx: MetaJudgeContext
) -> ValueOfContinuationVerdict:
    """Run the Value-of-Continuation pass.

    Uses the META_JUDGE role; the default ROLE_PROMPTS entry is the VoC
    prompt, so no explicit system message is needed.
    """
    return await client.call(
        role=LLMRole.META_JUDGE,
        messages=[
            {"role": "system", "content": META_JUDGE_VOC_PROMPT},
            {"role": "user", "content": _voc_user_message(ctx)},
        ],
        response_model=ValueOfContinuationVerdict,
    )


async def generate_adversarial_objections(
    client: LLMClient, ctx: MetaJudgeContext
) -> AdversarialCompletenessVerdict:
    """Run the Adversarial Completeness pass (exactly 3 objections)."""
    return await client.call(
        role=LLMRole.META_JUDGE,
        messages=[
            {"role": "system", "content": META_JUDGE_ADVERSARIAL_PROMPT},
            {"role": "user", "content": _adversarial_user_message(ctx)},
        ],
        response_model=AdversarialCompletenessVerdict,
    )
