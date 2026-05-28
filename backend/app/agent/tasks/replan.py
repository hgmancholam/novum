"""Re-decomposition task — dynamic plan gap detection (IP-25 Phase B).

Identifies uncovered angles after ANALYZING completes by querying the
planner LLM with the current evidence summary and sub-claims.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from app.agent.run_state import RunState
from app.llm import LLMRole, llm

logger = structlog.get_logger(__name__)


class PlanGapsOutput(BaseModel):
    """Structured response from the planner LLM for gap detection."""

    gaps: list[str] = []


async def identify_plan_gaps(state: RunState) -> list[str]:
    """Call planner LLM to identify uncovered angles or sub-questions.

    Analyzes the current question, sub-claims, and evidence summary to
    detect gaps in the research plan. Returns up to 3 short imperative
    phrases describing missing angles.

    Args:
        state: Current run state with question, sub-claims, and evidence.

    Returns:
        List of gap descriptions (max 3), or empty list if none identified.
    """
    # Build evidence summary for context
    evidence_summary = _build_evidence_summary(state)

    # Construct prompt
    user_prompt = f"""Question: {state.question}

Current sub-claims:
{_format_sub_claims(state)}

Evidence summary:
{evidence_summary}

Identify up to 3 angles or sub-questions that are not yet covered by the current plan. Return short imperative phrases describing what's missing.

If the plan already covers all major angles adequately, return an empty list."""

    try:
        result: PlanGapsOutput = await llm.call(
            role=LLMRole.PLANNER,
            user_messages=[{"role": "user", "content": user_prompt}],
            response_model=PlanGapsOutput,
        )

        # Cap at 3 gaps as specified — explicit typing for pyright strict
        all_gaps: list[str] = result.gaps if result.gaps else []
        gaps: list[str] = all_gaps[:3]

        logger.info(
            "plan_gaps_identified",
            question_type=state.question_type.value if state.question_type else None,
            current_claims=len(state.sub_claims),
            gaps_found=len(gaps),
        )

        return gaps

    except Exception as e:
        logger.error(
            "plan_gaps_identification_failed",
            error=str(e),
            question=state.question[:50],
        )
        # Fail gracefully — return empty list so research continues
        return []


def _build_evidence_summary(state: RunState) -> str:
    """Build a concise summary of gathered evidence."""
    if not state.evidence:
        return "No evidence gathered yet."

    # Group evidence by claim
    evidence_by_claim: dict[str, int] = {}
    for item in state.evidence:
        evidence_by_claim[item.claim_id] = evidence_by_claim.get(item.claim_id, 0) + 1

    lines = []
    for claim in state.sub_claims:
        count = evidence_by_claim.get(claim.id, 0)
        status = claim.status
        lines.append(f"  - {claim.text} [{status}, {count} sources]")

    return "\n".join(lines)


def _format_sub_claims(state: RunState) -> str:
    """Format sub-claims list for prompt."""
    if not state.sub_claims:
        return "(none yet)"

    lines = []
    for i, claim in enumerate(state.sub_claims, 1):
        lines.append(f"{i}. {claim.text} (status: {claim.status})")

    return "\n".join(lines)
