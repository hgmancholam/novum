"""Drafting, judging and disconfirmation helpers.

- ``draft_answer`` calls the synthesizer to produce the final prose.
  WP-2: derives ambiguity_flag (G3), calls select_answer_kind, enforces
  contradiction surfacing (G10), and validates kind-specific payloads.
- ``evaluate_with_judge`` calls the judge and builds ``JudgeRuledEvent``
  with ``final_confidence = min(S, J)`` (O-08 in BRD-07; placeholder S
  until BRD-08 ships).
- ``map_issues_to_claims`` is the RF-15 disconfirmation helper that
  finds which claims to re-open from judge issues.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from app.agent.run_state import RunState
from app.agent.tasks.select_answer_kind import AnswerKindInputs, select_answer_kind
from app.confidence import calculate_structural_confidence
from app.domain.enums import EventType
from app.domain.events import (
    AnswerSection,
    JudgeRuledEvent,
    SubClaim,
)
from app.exceptions import LLMContractError
from app.llm import (
    ROLE_CONFIGS,
    JudgeVerdict,
    LLMRole,
    SynthesizedAnswer,
    llm,
)
from app.llm.prompts import build_synthesizer_prompt


class IssueToClaimMapping(BaseModel):
    """Inline structured output for the disconfirmation mapping step."""

    claim_ids: list[str] = Field(default_factory=list)


def _format_evidence_for_claim(state: RunState, claim: SubClaim) -> str:
    items = [e for e in state.evidence if e.claim_id == claim.id]
    if not items:
        return "  (no evidence collected)"
    return "\n".join(f"  - [{e.source_title}]({e.source_url}) — {e.text[:200]}" for e in items)


async def draft_answer(state: RunState) -> SynthesizedAnswer:
    """Synthesize the final answer using all collected evidence.

    WP-2 implementation:
    - G3: derive ambiguity_flag from state.has_event(EventType.AMBIGUITY_DETECTED)
    - Select answer_kind based on question_type, S, coverage, agreement, ambiguity
    - G10: enforce contradictions field when ContradictionDetectedEvent exists
    - Build prompt with answer_kind-specific template
    - Validate and retry on kind mismatch or missing contradictions (once each)
    """
    if state.question_type is None:
        raise ValueError("draft_answer called before question_type was set")

    # G3: derive ambiguity_flag from events
    ambiguity_flag = state.has_event(EventType.AMBIGUITY_DETECTED)

    # G10: check if contradictions are required
    requires_contradictions = state.has_event(EventType.CONTRADICTION_DETECTED)

    # Compute structural confidence inputs
    struct_conf = calculate_structural_confidence(state)
    coverage = state.coverage_ratio()
    # agreement is in struct_conf.score (placeholder — BRD-08 has the real formula)
    # For now, use a heuristic: if no contradictions, agreement = 0.8, else 0.5
    agreement = 0.5 if requires_contradictions else 0.8

    # Select answer kind
    inputs = AnswerKindInputs(
        question_type=state.question_type,
        structural_confidence=struct_conf.score,
        coverage=coverage,
        agreement=agreement,
        ambiguity_flag=ambiguity_flag,
    )
    answer_kind = select_answer_kind(inputs)
    state.selected_answer_kind = answer_kind

    # Format evidence for synthesizer
    evidence_list = [
        {
            "url": e.source_url,
            "title": e.source_title,
            "snippet": e.text,
        }
        for e in state.evidence
    ]

    # Build prompt
    system_prompt, max_tokens = build_synthesizer_prompt(
        question=state.question,
        evidence=evidence_list,
        answer_kind=answer_kind,
        user_language="es",  # TODO: use state.language when added
        requires_contradictions=requires_contradictions,
    )

    # Call synthesizer with retry logic
    retry_count = 0
    max_retries = 1

    while retry_count <= max_retries:
        try:
            raw_payload = await llm.call(
                role=LLMRole.SYNTHESIZER,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": state.question},
                ],
                response_model=dict,  # Get raw dict first
                max_tokens=max_tokens,
            )

            # Validate with context
            result = SynthesizedAnswer.model_validate(
                raw_payload,
                context={"_requires_contradictions": requires_contradictions},
            )

            # Check kind matches
            if result.answer_kind != answer_kind:
                if retry_count == 0:
                    # First mismatch: retry with hardened prefix
                    system_prompt = (
                        f"CRITICAL: You MUST set answer_kind to '{answer_kind.value}'. "
                        f"Any other value will be rejected.\n\n"
                        + system_prompt
                    )
                    retry_count += 1
                    continue
                else:
                    raise LLMContractError(
                        f"Synthesizer returned answer_kind={result.answer_kind.value} "
                        f"after retry; expected {answer_kind.value}"
                    )

            # Success — populate state and return
            state.draft_answer = result.prose
            state.draft_citations = list(result.citations)
            state.draft_sections = [
                AnswerSection(heading=str(idx + 1), content=kp)
                for idx, kp in enumerate(result.key_points)
            ]
            return result

        except ValidationError as exc:
            # Check if it's the contradictions requirement violation
            if requires_contradictions and "contradictions required" in str(exc):
                if retry_count == 0:
                    # First missing contradictions: retry with even harder prefix
                    system_prompt = (
                        "CRITICAL: The run has detected contradictions. You MUST populate "
                        "the 'contradictions' field with at least one entry. Omitting it "
                        "will cause validation failure.\n\n"
                        + system_prompt
                    )
                    retry_count += 1
                    continue
                else:
                    raise LLMContractError(
                        "Synthesizer omitted contradictions field after retry"
                    ) from exc
            # Other validation error — re-raise
            raise

    # Should not reach here
    raise LLMContractError("Draft answer retry loop exhausted without success")


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
