"""Lane routing logic for IP-25 three-lane research flow.

Pure deterministic function that maps (question_type, complexity_hint,
temporal_sensitivity, ambiguity_detected) → (Lane, reason).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings
from app.domain.enums import ComplexityHint, Lane, QuestionType, TemporalSensitivity

if TYPE_CHECKING:
    from app.agent.run_state import RunState


def select_lane(
    question_type: QuestionType,
    complexity_hint: ComplexityHint,
    temporal_sensitivity: TemporalSensitivity | None,
    ambiguity_detected: bool = False,
) -> tuple[Lane, str]:
    """Deterministic lane routing for IP-25.

    Args:
        question_type: Classified question type from the classifier
        complexity_hint: Complexity assessment (TRIVIAL / STANDARD / DEEP)
        temporal_sensitivity: Temporal bucket (STATIC / SLOW_CHANGING / VOLATILE / REALTIME)
        ambiguity_detected: Whether ambiguity was detected in the question

    Returns:
        Tuple of (Lane, reason) where reason is a short English explanation

    Rules (in priority order):
        1. Predictive future questions cannot be TRIVIAL — coerce to STANDARD minimum
           (T-25-A-04: no predictions are truly trivial)
        2. DEEP lane if:
           - complexity_hint == DEEP, OR
           - question_type in {CAUSAL, STATE_OF_ART} AND complexity_hint != TRIVIAL
        3. FAST lane if:
           - complexity_hint == TRIVIAL AND
           - question_type in {FACTUAL, DEFINITIONAL} AND
           - temporal_sensitivity in {STATIC, None} AND
           - NOT ambiguity_detected
        4. Otherwise STANDARD (default fallback)

    Examples:
        >>> select_lane(QuestionType.DEFINITIONAL, ComplexityHint.TRIVIAL,
        ...             TemporalSensitivity.STATIC, False)
        (Lane.FAST, "trivial+factual+static → FAST")

        >>> select_lane(QuestionType.CAUSAL, ComplexityHint.DEEP, None, False)
        (Lane.DEEP, "complexity_hint=DEEP → DEEP")

        >>> select_lane(QuestionType.PREDICTIVE_FUTURE, ComplexityHint.TRIVIAL,
        ...             TemporalSensitivity.STATIC, False)
        (Lane.STANDARD, "predictive_future coerced to ≥STANDARD")
    """
    # Rule 1: Predictive future coercion (T-25-A-04)
    if question_type == QuestionType.PREDICTIVE_FUTURE and complexity_hint == ComplexityHint.TRIVIAL:
        # Coerce to STANDARD — no predictions are trivial
        return (Lane.STANDARD, "predictive_future coerced to ≥STANDARD")

    # Rule 2: DEEP lane conditions
    if complexity_hint == ComplexityHint.DEEP:
        return (Lane.DEEP, "complexity_hint=DEEP → DEEP")

    if (
        question_type in {QuestionType.CAUSAL, QuestionType.STATE_OF_ART}
        and complexity_hint != ComplexityHint.TRIVIAL
    ):
        return (Lane.DEEP, f"{question_type.value}+{complexity_hint.value} → DEEP")

    # Rule 3: FAST lane conditions (all must be true)
    if (
        complexity_hint == ComplexityHint.TRIVIAL
        and question_type in {QuestionType.FACTUAL, QuestionType.DEFINITIONAL}
        and temporal_sensitivity in {TemporalSensitivity.STATIC, None}
        and not ambiguity_detected
    ):
        return (Lane.FAST, f"trivial+{question_type.value}+static → FAST")

    # Rule 4: Default fallback
    # Build a concise reason from the blocking factors
    reasons: list[str] = []
    if complexity_hint != ComplexityHint.TRIVIAL:
        reasons.append(f"complexity={complexity_hint.value}")
    if temporal_sensitivity not in {TemporalSensitivity.STATIC, None}:
        reasons.append(f"temporal={temporal_sensitivity.value if temporal_sensitivity else 'none'}")
    if ambiguity_detected:
        reasons.append("ambiguity")
    if question_type not in {QuestionType.FACTUAL, QuestionType.DEFINITIONAL}:
        reasons.append(f"type={question_type.value}")

    reason_str = ", ".join(reasons) if reasons else "default"
    return (Lane.STANDARD, f"{reason_str} → STANDARD")


def apply_lane_budgets(state: RunState, lane: Lane) -> None:
    """Populate per-run global hard caps on ``state`` from settings.

    PR-1 (post-2026-05-29 eval): every lane gets a wall-clock ceiling and
    counter ceilings for tool calls, evidence items and query reformulations.
    These are FSM-independent — ``AgentOrchestrator._check_global_budget``
    enforces them at the head of every loop iteration so a stuck run can
    never escape with a finite stop.

    Idempotent: callers may invoke once per run (typically right after
    ``select_lane``). Subsequent calls just overwrite with the same values.
    """
    if lane == Lane.FAST:
        state.wall_clock_max_seconds = settings.wall_clock_max_s_fast
        state.max_tool_calls_per_run = settings.max_tool_calls_fast
        state.max_evidence_per_run = settings.max_evidence_fast
        state.max_query_reformulations_per_run = settings.max_query_reformulations_fast
    elif lane == Lane.DEEP:
        state.wall_clock_max_seconds = settings.wall_clock_max_s_deep
        state.max_tool_calls_per_run = settings.max_tool_calls_deep
        state.max_evidence_per_run = settings.max_evidence_deep
        state.max_query_reformulations_per_run = settings.max_query_reformulations_deep
    else:
        state.wall_clock_max_seconds = settings.wall_clock_max_s_standard
        state.max_tool_calls_per_run = settings.max_tool_calls_standard
        state.max_evidence_per_run = settings.max_evidence_standard
        state.max_query_reformulations_per_run = settings.max_query_reformulations_standard
    state.no_progress_event_window = settings.no_progress_event_window
