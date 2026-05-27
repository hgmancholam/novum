"""Drafting, judging and disconfirmation helpers.

- ``draft_answer`` calls the synthesizer to produce the final prose.
- ``evaluate_with_judge`` calls the judge and builds ``JudgeRuledEvent``
  with ``final_confidence = min(S, J)`` (O-08 in BRD-07; placeholder S
  until BRD-08 ships).
- ``map_issues_to_claims`` is the RF-15 disconfirmation helper that
  finds which claims to re-open from judge issues.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.run_state import RunState
from app.confidence import calculate_structural_confidence
from app.domain.events import (
    AnswerSection,
    JudgeRuledEvent,
    SubClaim,
)
from app.llm import (
    ROLE_CONFIGS,
    JudgeVerdict,
    LLMRole,
    SynthesizedAnswer,
    llm,
)


class IssueToClaimMapping(BaseModel):
    """Inline structured output for the disconfirmation mapping step."""

    claim_ids: list[str] = Field(default_factory=list)


def _format_evidence_for_claim(state: RunState, claim: SubClaim) -> str:
    items = [e for e in state.evidence if e.claim_id == claim.id]
    if not items:
        return "  (no evidence collected)"
    return "\n".join(f"  - [{e.source_title}]({e.source_url}) — {e.text[:200]}" for e in items)


async def draft_answer(state: RunState) -> SynthesizedAnswer:
    """Synthesize the final answer using all collected evidence."""
    claim_blocks: list[str] = []
    for claim in state.sub_claims:
        claim_blocks.append(
            f"{claim.id} ({claim.status}): {claim.text}\n{_format_evidence_for_claim(state, claim)}"
        )
    context_block = f"User context: {state.user_context}\n" if state.user_context else ""
    user_msg = (
        f"Question: {state.question}\n\n"
        f"{context_block}"
        f"Sub-claims and evidence:\n" + "\n\n".join(claim_blocks) + "\n\n"
        "Produce the final answer."
    )
    result = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=SynthesizedAnswer,
    )
    state.draft_answer = result.prose
    state.draft_citations = list(result.citations)
    state.draft_sections = [
        AnswerSection(heading=str(idx + 1), content=kp) for idx, kp in enumerate(result.key_points)
    ]
    return result


async def evaluate_with_judge(state: RunState) -> JudgeRuledEvent:
    """Call the judge and assemble a ``JudgeRuledEvent``."""
    draft = state.draft_answer or ""
    user_msg = (
        f"Question: {state.question}\n\n"
        f"Draft answer:\n{draft}\n\n"
        f"Evaluate factuality, completeness and grounding."
    )
    verdict = await llm.call(
        role=LLMRole.JUDGE,
        messages=[{"role": "user", "content": user_msg}],
        response_model=JudgeVerdict,
    )
    judge_confidence = verdict.confidence
    structural_confidence = calculate_structural_confidence(state).score
    final_confidence = min(judge_confidence, structural_confidence)
    threshold = state.confidence_threshold
    passed = final_confidence >= threshold and verdict.verdict.lower() == "approve"
    return JudgeRuledEvent(
        judge_model=ROLE_CONFIGS[LLMRole.JUDGE].model,
        judge_confidence=judge_confidence,
        structural_confidence=structural_confidence,
        final_confidence=final_confidence,
        threshold=threshold,
        passed=passed,
        rationale=verdict.rationale,
        suggested_improvements=list(verdict.improvements) or None,
    )


async def map_issues_to_claims(issues: list[str], sub_claims: list[SubClaim]) -> list[str]:
    """Map judge issues to the claim IDs that should be re-opened (RF-15)."""
    if not issues or not sub_claims:
        return []
    claims_block = "\n".join(f"- {c.id}: {c.text}" for c in sub_claims)
    issues_block = "\n".join(f"- {i}" for i in issues)
    user_msg = (
        "Given a list of judge issues and the current sub-claims, return the "
        "claim IDs that should be re-investigated. Only return IDs that match "
        "an existing sub-claim.\n\n"
        f"Sub-claims:\n{claims_block}\n\n"
        f"Issues:\n{issues_block}"
    )
    result = await llm.call(
        role=LLMRole.PLANNER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=IssueToClaimMapping,
    )
    valid_ids = {c.id for c in sub_claims}
    return [cid for cid in result.claim_ids if cid in valid_ids]
