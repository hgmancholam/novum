"""Tests for lane_router.py (IP-25 Phase A).

Verifies deterministic routing logic from (question_type, complexity_hint,
temporal_sensitivity, ambiguity_detected) → (Lane, reason).
"""

from app.agent.lane_router import select_lane
from app.domain.enums import ComplexityHint, Lane, QuestionType, TemporalSensitivity


def test_fast_for_trivial_definitional_static() -> None:
    """Trivial definitional questions with static temporal → FAST lane."""
    lane, reason = select_lane(
        question_type=QuestionType.DEFINITIONAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
        ambiguity_detected=False,
    )
    assert lane == Lane.FAST
    assert "trivial" in reason.lower()
    assert "FAST" in reason


def test_fast_for_trivial_factual_static() -> None:
    """Trivial factual questions with static temporal → FAST lane."""
    lane, reason = select_lane(
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
        ambiguity_detected=False,
    )
    assert lane == Lane.FAST
    assert "trivial" in reason.lower()
    assert "FAST" in reason


def test_fast_for_trivial_factual_none_temporal() -> None:
    """Trivial factual with None temporal (no explicit bucket) → FAST lane."""
    lane, reason = select_lane(
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=None,
        ambiguity_detected=False,
    )
    assert lane == Lane.FAST
    assert "FAST" in reason


def test_deep_for_deep_complexity() -> None:
    """DEEP complexity hint → DEEP lane regardless of question type."""
    lane, reason = select_lane(
        question_type=QuestionType.COMPARATIVE,
        complexity_hint=ComplexityHint.DEEP,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
        ambiguity_detected=False,
    )
    assert lane == Lane.DEEP
    assert "DEEP" in reason
    assert "complexity_hint=DEEP" in reason


def test_deep_for_causal_standard() -> None:
    """Causal questions with STANDARD complexity → DEEP lane."""
    lane, reason = select_lane(
        question_type=QuestionType.CAUSAL,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=None,
        ambiguity_detected=False,
    )
    assert lane == Lane.DEEP
    assert "DEEP" in reason
    assert "causal" in reason.lower()


def test_deep_for_state_of_art_standard() -> None:
    """State-of-art questions with STANDARD complexity → DEEP lane."""
    lane, reason = select_lane(
        question_type=QuestionType.STATE_OF_ART,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.SLOW_CHANGING,
        ambiguity_detected=False,
    )
    assert lane == Lane.DEEP
    assert "DEEP" in reason
    assert "state_of_art" in reason.lower()


def test_standard_for_causal_trivial() -> None:
    """Causal + TRIVIAL → STANDARD (not DEEP, trivial overrides type rule)."""
    lane, reason = select_lane(
        question_type=QuestionType.CAUSAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
        ambiguity_detected=False,
    )
    # Should NOT go to DEEP because complexity is TRIVIAL
    # Should NOT go to FAST because question_type is CAUSAL (not FACTUAL/DEFINITIONAL)
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_standard_default_comparative() -> None:
    """Comparative with STANDARD complexity → STANDARD lane (default)."""
    lane, reason = select_lane(
        question_type=QuestionType.COMPARATIVE,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_predictive_future_never_trivial() -> None:
    """Predictive future coerced to ≥STANDARD (T-25-A-04)."""
    lane, reason = select_lane(
        question_type=QuestionType.PREDICTIVE_FUTURE,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "predictive_future coerced" in reason.lower()
    assert "STANDARD" in reason


def test_predictive_future_standard_stays_standard() -> None:
    """Predictive future with STANDARD complexity → STANDARD (no coercion needed)."""
    lane, reason = select_lane(
        question_type=QuestionType.PREDICTIVE_FUTURE,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_predictive_future_deep_stays_deep() -> None:
    """Predictive future with DEEP complexity → DEEP (coercion doesn't apply)."""
    lane, reason = select_lane(
        question_type=QuestionType.PREDICTIVE_FUTURE,
        complexity_hint=ComplexityHint.DEEP,
        temporal_sensitivity=None,
        ambiguity_detected=False,
    )
    assert lane == Lane.DEEP
    assert "DEEP" in reason


def test_realtime_excludes_fast() -> None:
    """REALTIME temporal sensitivity blocks FAST lane (T-25-A-05 test req)."""
    lane, reason = select_lane(
        question_type=QuestionType.DEFINITIONAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.REALTIME,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason
    # Should mention temporal in reason
    assert "temporal" in reason.lower() or "realtime" in reason.lower()


def test_ambiguity_blocks_fast() -> None:
    """Ambiguity detected blocks FAST lane (T-25-A-06 test req)."""
    lane, reason = select_lane(
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
        ambiguity_detected=True,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason
    # Should mention ambiguity in reason
    assert "ambiguity" in reason.lower()


def test_volatile_temporal_blocks_fast() -> None:
    """VOLATILE temporal sensitivity blocks FAST lane."""
    lane, reason = select_lane(
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_slow_changing_temporal_blocks_fast() -> None:
    """SLOW_CHANGING temporal sensitivity blocks FAST lane."""
    lane, reason = select_lane(
        question_type=QuestionType.DEFINITIONAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.SLOW_CHANGING,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_subjective_opinion_standard() -> None:
    """Subjective opinion questions → STANDARD by default."""
    lane, reason = select_lane(
        question_type=QuestionType.SUBJECTIVE_OPINION,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=None,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_personal_private_standard() -> None:
    """Personal/private questions → STANDARD by default."""
    lane, reason = select_lane(
        question_type=QuestionType.PERSONAL_PRIVATE,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=None,
        ambiguity_detected=False,
    )
    assert lane == Lane.STANDARD
    assert "STANDARD" in reason


def test_reason_format_is_concise() -> None:
    """Reason strings should be concise and descriptive."""
    _, reason = select_lane(
        question_type=QuestionType.COMPARATIVE,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
        ambiguity_detected=False,
    )
    # Should be short and contain the lane name
    assert len(reason) < 120
    assert "STANDARD" in reason or "DEEP" in reason or "FAST" in reason


# ---------------------------------------------------------------------------
# PR-1 (post-2026-05-29 eval): per-lane global budget caps.
# ---------------------------------------------------------------------------

from uuid import uuid4

from app.agent.lane_router import apply_lane_budgets
from app.agent.run_state import RunState
from app.config import settings


def _fresh_state() -> RunState:
    return RunState(run_id=uuid4(), question="q")


def test_apply_lane_budgets_fast() -> None:
    state = _fresh_state()
    apply_lane_budgets(state, Lane.FAST)
    assert state.wall_clock_max_seconds == settings.wall_clock_max_s_fast
    assert state.max_tool_calls_per_run == settings.max_tool_calls_fast
    assert state.max_evidence_per_run == settings.max_evidence_fast
    assert state.max_query_reformulations_per_run == settings.max_query_reformulations_fast


def test_apply_lane_budgets_standard() -> None:
    state = _fresh_state()
    apply_lane_budgets(state, Lane.STANDARD)
    assert state.wall_clock_max_seconds == settings.wall_clock_max_s_standard
    assert state.max_tool_calls_per_run == settings.max_tool_calls_standard
    assert state.max_evidence_per_run == settings.max_evidence_standard
    assert state.max_query_reformulations_per_run == settings.max_query_reformulations_standard


def test_apply_lane_budgets_deep() -> None:
    state = _fresh_state()
    apply_lane_budgets(state, Lane.DEEP)
    assert state.wall_clock_max_seconds == settings.wall_clock_max_s_deep
    assert state.max_tool_calls_per_run == settings.max_tool_calls_deep
    assert state.max_evidence_per_run == settings.max_evidence_deep
    assert state.max_query_reformulations_per_run == settings.max_query_reformulations_deep


def test_apply_lane_budgets_fast_smaller_than_deep() -> None:
    """Sanity: FAST caps are strictly tighter than DEEP."""
    fast = _fresh_state()
    deep = _fresh_state()
    apply_lane_budgets(fast, Lane.FAST)
    apply_lane_budgets(deep, Lane.DEEP)
    assert fast.wall_clock_max_seconds <= deep.wall_clock_max_seconds
    assert fast.max_tool_calls_per_run < deep.max_tool_calls_per_run
    assert fast.max_evidence_per_run < deep.max_evidence_per_run
    assert fast.max_query_reformulations_per_run < deep.max_query_reformulations_per_run
