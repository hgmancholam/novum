"""Plan creation, critique and revision tasks (RF-14).

All three steps share the planner role (O-01). The critic step uses
``CritiqueOutput`` (O-02); the revision step reuses ``PlanOutput``.
"""

from __future__ import annotations

import structlog

from app.domain.enums import ComplexityHint, QuestionType, TemporalSensitivity
from app.domain.events import (
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanRevisedEvent,
    SubClaim,
)
from app.llm import CritiqueOutput, LLMRole, PlanOutput, llm

logger = structlog.get_logger(__name__)

# Sub-claim budget per (QuestionType, ComplexityHint). Tuple shape:
# (claims_min, claims_max, sources_per_claim, critique_passes).
# Trivial questions collapse to 1 claim, 1 source, 0 critique passes.
# Deep questions get extra critique pass (2 total).
CLAIM_BUDGETS: dict[tuple[QuestionType, ComplexityHint], tuple[int, int, int, int]] = {
    # Trivial budgets (BRD-22 §4.6)
    (QuestionType.FACTUAL, ComplexityHint.TRIVIAL): (1, 1, 1, 0),
    (QuestionType.DEFINITIONAL, ComplexityHint.TRIVIAL): (1, 1, 1, 0),
    # Standard budgets (IP-36: tightened — old caps of 4-6 sub-claims kept
    # runs busy past budget; converging on ≤3 claims raises judge_confirmed
    # ratio without losing coverage signal).
    (QuestionType.FACTUAL, ComplexityHint.STANDARD): (1, 2, 2, 1),
    (QuestionType.DEFINITIONAL, ComplexityHint.STANDARD): (1, 2, 2, 1),
    (QuestionType.COMPARATIVE, ComplexityHint.STANDARD): (2, 3, 2, 1),
    (QuestionType.CAUSAL, ComplexityHint.STANDARD): (2, 3, 2, 1),
    (QuestionType.STATE_OF_ART, ComplexityHint.STANDARD): (2, 4, 2, 1),
    (QuestionType.PREDICTIVE_FUTURE, ComplexityHint.STANDARD): (2, 3, 2, 1),
    (QuestionType.SUBJECTIVE_OPINION, ComplexityHint.STANDARD): (2, 3, 2, 1),
    (QuestionType.PERSONAL_PRIVATE, ComplexityHint.STANDARD): (2, 3, 2, 1),
    # Deep budgets (extra critique pass; IP-36 trimmed upper bounds too).
    (QuestionType.FACTUAL, ComplexityHint.DEEP): (2, 3, 3, 2),
    (QuestionType.DEFINITIONAL, ComplexityHint.DEEP): (2, 3, 3, 2),
    (QuestionType.COMPARATIVE, ComplexityHint.DEEP): (3, 5, 3, 2),
    (QuestionType.CAUSAL, ComplexityHint.DEEP): (3, 5, 3, 2),
    (QuestionType.STATE_OF_ART, ComplexityHint.DEEP): (3, 6, 3, 2),
    (QuestionType.PREDICTIVE_FUTURE, ComplexityHint.DEEP): (3, 5, 3, 2),
    (QuestionType.SUBJECTIVE_OPINION, ComplexityHint.DEEP): (3, 5, 3, 2),
    (QuestionType.PERSONAL_PRIVATE, ComplexityHint.DEEP): (3, 5, 3, 2),
}
_DEFAULT_BUDGET: tuple[int, int, int, int] = (2, 3, 2, 1)


def _coerce_complexity(
    question_type: QuestionType | None, hint: ComplexityHint | None
) -> ComplexityHint:
    """Coerce TRIVIAL to STANDARD for incompatible question types.

    TRIVIAL is designed for single-fact lookups (FACTUAL, DEFINITIONAL).
    Non-factual types (COMPARATIVE, CAUSAL, STATE_OF_ART, PREDICTIVE_FUTURE,
    SUBJECTIVE_OPINION, PERSONAL_PRIVATE) require richer evidence and
    multiple sources, so they ignore TRIVIAL and default to STANDARD.

    Args:
        question_type: The classified question type.
        hint: The complexity hint from the classifier.

    Returns:
        The coerced complexity hint (STANDARD if coerced, else original).
    """
    if hint != ComplexityHint.TRIVIAL:
        return hint or ComplexityHint.STANDARD

    incompatible = {
        QuestionType.COMPARATIVE,
        QuestionType.CAUSAL,
        QuestionType.STATE_OF_ART,
        QuestionType.PREDICTIVE_FUTURE,
        QuestionType.SUBJECTIVE_OPINION,
        QuestionType.PERSONAL_PRIVATE,
    }
    if question_type in incompatible:
        logger.info(
            "complexity_coerced",
            reason="incompatible_type",
            question_type=question_type.value if question_type else None,
            original_hint=hint.value if hint else None,
        )
        return ComplexityHint.STANDARD
    return hint or ComplexityHint.STANDARD


def _claim_budget(
    question_type: QuestionType | None, hint: ComplexityHint | None
) -> tuple[int, int, int, int]:
    """Return (claims_min, claims_max, sources_per_claim, critique_passes)."""
    if question_type is None or hint is None:
        return _DEFAULT_BUDGET
    coerced_hint = _coerce_complexity(question_type, hint)
    return CLAIM_BUDGETS.get((question_type, coerced_hint), _DEFAULT_BUDGET)


def _fallback_experts(question: str, question_type: QuestionType) -> list[str]:
    """Deterministic fallback when LLM returns empty expected_experts.

    Uses keyword heuristics to match domain patterns. Returns a single-expert
    list biased toward safe defaults ("encyclopedia" for most types).

    Args:
        question: The normalized question text.
        question_type: The classified question type.

    Returns:
        A list of 1-2 expert labels from the taxonomy vocabulary.
    """
    q_lower = question.lower()

    # Medical/health keywords
    if any(
        kw in q_lower
        for kw in [
            "health",
            "disease",
            "symptom",
            "nutrition",
            "diet",
            "vitamin",
            "cancer",
            "diabetes",
            "treatment",
            "medicine",
        ]
    ):
        return ["nutritionist", "medical_researcher"]

    # Database/data keywords
    if any(
        kw in q_lower
        for kw in [
            "database",
            "sql",
            "postgres",
            "mongodb",
            "nosql",
            "query",
            "schema",
            "transaction",
        ]
    ):
        return ["database_engineer"]

    # Programming/SaaS keywords
    if any(
        kw in q_lower
        for kw in [
            "code",
            "programming",
            "software",
            "saas",
            "api",
            "framework",
            "library",
            "deployment",
        ]
    ):
        return ["software_engineer", "saas_architect"]

    # Geography keywords
    if any(
        kw in q_lower
        for kw in ["capital", "country", "city", "river", "mountain", "continent"]
    ):
        return ["geographer", "encyclopedia"]

    # Default: encyclopedia for FACTUAL/DEFINITIONAL, generic for others
    if question_type in (QuestionType.FACTUAL, QuestionType.DEFINITIONAL):
        return ["encyclopedia"]
    return ["encyclopedia"]


def _format_claims(sub_claims: list[SubClaim]) -> str:
    return "\n".join(f"- {c.id}: {c.text}" for c in sub_claims)


async def create_plan(
    question: str,
    question_type: QuestionType | None = None,
    complexity_hint: ComplexityHint | None = None,
    temporal_sensitivity: TemporalSensitivity | None = None,
) -> PlanCreatedEvent:
    """Create the initial plan for ``question`` (WP-6 + BRD-22).

    ``question_type`` + ``complexity_hint`` scale the number of sub-claims,
    sources-per-claim, and critique passes so trivial questions stay short
    and deep syntheses get richer plans.

    WP-6: Queries the question index for similar past questions and
    injects top-3 prior runs as planning hints (planner-only; synthesizer
    and judge never see these).

    BRD-22: Populates ``expected_experts`` (from LLM OR fallback) and
    ``preferred_sources`` (Wikipedia for trivial-factual).

    Args:
        question: The normalized question text.
        question_type: Classified question type.
        complexity_hint: Complexity hint from classifier (BRD-22).

    Returns:
        PlanCreatedEvent with sub-claims, rationale, complexity_hint,
        expected_experts, and preferred_sources.
    """
    coerced_hint = _coerce_complexity(question_type, complexity_hint)
    claims_min, claims_max, sources_per_claim, critique_passes = _claim_budget(
        question_type, coerced_hint
    )
    lo, hi = claims_min, claims_max

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

    sources_hint = (
        f" Aim for approximately {sources_per_claim} source(s) per sub-claim."
        if sources_per_claim > 1
        else ""
    )
    user_msg = (
        f"Decompose the following question into {lo}-{hi} verifiable sub-claims.\n"
        f"For a trivial single-fact question, prefer the lower bound "
        f"({lo}); do not pad with adjacent or background claims.{sources_hint}\n"
        f"For EACH sub-claim also emit ``search_keywords``: a 3-7 keyword "
        f"phrase (space-separated, no punctuation) optimised for web search. "
        f"Strip filler words; keep proper nouns, technical terms, and the "
        f"core entities. Example: claim "
        f"\"PostgreSQL offers ACID compliance and strong relational modeling\" "
        f"-> keywords \"PostgreSQL ACID relational database\".\n\n"
        f"Question: {question}{prior_hints_block}\n"
    )
    result = await llm.call(
        role=LLMRole.PLANNER,
        messages=[{"role": "user", "content": user_msg}],
        response_model=PlanOutput,
    )
    sub_claims = [
        SubClaim(
            id=sc.id,
            text=sc.text,
            status="pending",
            search_keywords=sc.search_keywords,
        )
        for sc in result.sub_claims
    ]

    # BRD-22: expected_experts from LLM OR fallback
    expected_experts = (
        result.expected_experts
        if result.expected_experts
        else _fallback_experts(question, question_type or QuestionType.FACTUAL)
    )

    # BRD-22: preferred_sources for trivial-factual
    preferred_sources: list[str] | None = None
    if coerced_hint == ComplexityHint.TRIVIAL and question_type in (
        QuestionType.FACTUAL,
        QuestionType.DEFINITIONAL,
    ):
        preferred_sources = ["wikipedia"]

    # BRD-23 WP-1: temporal routing overrides trivial wiki-first when topic is volatile/realtime
    if temporal_sensitivity == TemporalSensitivity.REALTIME:
        preferred_sources = ["tavily"]
    elif temporal_sensitivity == TemporalSensitivity.VOLATILE:
        preferred_sources = ["tavily", "wikipedia"]

    # C5: academic routing — for research-grade question types at
    # standard/deep complexity, add Semantic Scholar + OpenAlex so the
    # planner is guaranteed to pull from peer-reviewed sources, not just
    # web/wiki. Temporal overrides above still win for realtime/volatile
    # topics where freshness beats citation depth.
    _ACADEMIC_QUESTION_TYPES = {
        QuestionType.STATE_OF_ART,
        QuestionType.PREDICTIVE_FUTURE,
        QuestionType.CAUSAL,
        QuestionType.COMPARATIVE,
    }
    _ACADEMIC_COMPLEXITY = {ComplexityHint.STANDARD, ComplexityHint.DEEP}
    if (
        question_type in _ACADEMIC_QUESTION_TYPES
        and coerced_hint in _ACADEMIC_COMPLEXITY
        and temporal_sensitivity != TemporalSensitivity.REALTIME
    ):
        # Post-PR-7: academic sources FIRST (cascade is first-success-wins,
        # so without this Tavily always wins and S2/OpenAlex never run).
        # Web fallbacks still appended so coverage degrades gracefully if
        # the academic backends return nothing for the topic.
        base = ["semantic_scholar", "openalex"]
        prior = list(preferred_sources) if preferred_sources else ["tavily", "wikipedia"]
        for fallback in prior:
            if fallback not in base:
                base.append(fallback)
        for fallback in ("tavily", "wikipedia"):
            if fallback not in base:
                base.append(fallback)
        preferred_sources = base

    return PlanCreatedEvent(
        sub_claims=sub_claims,
        rationale=result.overall_rationale,
        complexity_hint=coerced_hint,
        expected_experts=expected_experts,
        preferred_sources=preferred_sources,
        temporal_sensitivity=temporal_sensitivity,
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
    complexity_hint: ComplexityHint | None = None,
) -> PlanRevisedEvent:
    """Revise the plan after a rejected critique (BRD-22).

    Args:
        question: The normalized question text.
        current_claims: The current sub-claims list.
        attempt_number: Revision attempt counter (1 or 2).
        critique_issues: Issues from the critique.
        question_type: Classified question type.
        complexity_hint: Complexity hint (BRD-22). If None, defaults to STANDARD.

    Returns:
        PlanRevisedEvent with new sub-claims and revision rationale.
    """
    # Fallback strategy for historical replay (BRD-22 Task 4.4)
    if complexity_hint is None:
        logger.info(
            "complexity_hint_defaulted_on_revise",
            reason="missing",
            question_type=question_type.value if question_type else None,
        )
        complexity_hint = ComplexityHint.STANDARD

    coerced_hint = _coerce_complexity(question_type, complexity_hint)
    claims_min, claims_max, _sources, _critiques = _claim_budget(
        question_type, coerced_hint
    )
    lo, hi = claims_min, claims_max
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
        complexity_hint=coerced_hint,
    )
