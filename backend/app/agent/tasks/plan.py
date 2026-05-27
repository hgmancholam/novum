"""Plan creation, critique and revision tasks (RF-14).

All three steps share the planner role (O-01). The critic step uses
``CritiqueOutput`` (O-02); the revision step reuses ``PlanOutput``.
"""

from __future__ import annotations

from app.domain.enums import QuestionType
from app.domain.events import (
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanRevisedEvent,
    SubClaim,
)
from app.llm import CritiqueOutput, LLMRole, PlanOutput, llm

# Sub-claim budget per question complexity. Trivial questions (a single
# fact, a definitional yes/no) collapse to 1-2 claims so the agent
# does not spin through 14 iterations chasing coverage on a question
# that has one answer. Aggregate / state-of-the-art questions keep the
# larger envelope. When the type is unknown we use a conservative
# middle range.
CLAIM_BUDGETS: dict[QuestionType, tuple[int, int]] = {
    QuestionType.FACTUAL: (1, 2),
    QuestionType.DEFINITIONAL: (1, 2),
    QuestionType.COMPARATIVE: (2, 4),
    QuestionType.CAUSAL: (2, 4),
    QuestionType.STATE_OF_ART: (3, 6),
}
_DEFAULT_BUDGET: tuple[int, int] = (3, 5)


def _claim_budget(question_type: QuestionType | None) -> tuple[int, int]:
    if question_type is None:
        return _DEFAULT_BUDGET
    return CLAIM_BUDGETS.get(question_type, _DEFAULT_BUDGET)


def _format_claims(sub_claims: list[SubClaim]) -> str:
    return "\n".join(f"- {c.id}: {c.text}" for c in sub_claims)


async def create_plan(
    question: str,
    question_type: QuestionType | None = None,
) -> PlanCreatedEvent:
    """Create the initial plan for ``question`` (WP-6: with prior-run hints).

    ``question_type`` (when known) is used to scale the number of
    sub-claims requested from the planner so trivial questions stay
    short and complex syntheses still get a richer plan.

    WP-6: Queries the question index for similar past questions and
    injects top-3 prior runs as planning hints (planner-only; synthesizer
    and judge never see these).
    """
    lo, hi = _claim_budget(question_type)

    # WP-6: Query question index for similar prior runs
    from app.agent.question_index import get_index
    from app.llm.embeddings import embed

    prior_hints_block = ""
    try:
        index = get_index()
        if len(index) > 0:
            # Embed the current question
            vecs = await embed([question])
            if vecs:
                hints = index.top_k(vecs[0], k=3)
                if hints:
                    hints_text = "\n".join([
                        f"- Previous similar question: \"{h.question_text}\"\n"
                        f"  Sub-claims used: {', '.join(h.sub_claims[:3])}{'...' if len(h.sub_claims) > 3 else ''}"
                        for h in hints
                    ])
                    prior_hints_block = (
                        f"\n\nPlanning hints from similar prior runs (you MAY borrow "
                        f"relevant sub-claims, but you MUST NOT borrow conclusions):\n{hints_text}\n"
                    )
    except Exception:  # noqa: BLE001 - non-critical enhancement
        # Don't fail the plan if index query fails
        pass

    user_msg = (
        f"Decompose the following question into {lo}-{hi} verifiable sub-claims.\n"
        f"For a trivial single-fact question, prefer the lower bound "
        f"({lo}); do not pad with adjacent or background claims.\n\n"
        f"Question: {question}{prior_hints_block}\n"
    )
    result = await llm.call(
        role=LLMRole.PLANNER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=PlanOutput,
    )
    sub_claims = [SubClaim(id=sc.id, text=sc.text, status="pending") for sc in result.sub_claims]
    return PlanCreatedEvent(
        sub_claims=sub_claims,
        rationale=result.overall_rationale,
    )


async def critique_plan(question: str, sub_claims: list[SubClaim]) -> PlanCritiquedEvent:
    """Self-critique the current plan."""
    user_msg = (
        "You are now evaluating a research plan you previously drafted.\n"
        f"Original question: {question}\n"
        f"Current sub-claims:\n{_format_claims(sub_claims)}\n\n"
        "Identify issues, suggest changes, and decide whether to accept the plan."
    )
    result = await llm.call(
        role=LLMRole.PLANNER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=CritiqueOutput,
    )
    return PlanCritiquedEvent(
        critique=result.summary,
        issues=result.issues,
        suggested_changes=result.suggested_changes,
        acceptable=result.acceptable,
    )


async def revise_plan(
    question: str,
    current_claims: list[SubClaim],
    attempt_number: int,
    critique_issues: list[str] | None = None,
    question_type: QuestionType | None = None,
) -> PlanRevisedEvent:
    """Revise the plan after a rejected critique."""
    lo, hi = _claim_budget(question_type)
    issues_block = "\n".join(f"- {i}" for i in critique_issues) if critique_issues else "(none)"
    user_msg = (
        f"Revise the research plan based on critique feedback.\n\n"
        f"Original question: {question}\n"
        f"Current sub-claims:\n{_format_claims(current_claims)}\n\n"
        f"Critique issues:\n{issues_block}\n\n"
        f"Return an improved plan with {lo}-{hi} verifiable sub-claims."
    )
    result = await llm.call(
        role=LLMRole.PLANNER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=PlanOutput,
    )
    new_claims = [SubClaim(id=sc.id, text=sc.text, status="pending") for sc in result.sub_claims]
    return PlanRevisedEvent(
        previous_sub_claims=current_claims,
        new_sub_claims=new_claims,
        revision_rationale=result.overall_rationale,
        attempt_number=attempt_number,
    )
