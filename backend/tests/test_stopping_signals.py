"""Unit tests for the 5 default stopping signals."""

from __future__ import annotations

import pytest

from app.domain.enums import StopReason
from app.seams.stopping import SignalResult, StopContext
from app.stopping.signals import (
    AgreementSignal,
    BudgetSignal,
    CoverageSignal,
    HonestStopSignal,
    JudgeSignal,
)


def _ctx(**overrides: object) -> StopContext:
    base: dict[str, object] = {
        "coverage": 0.0,
        "agreement": 0.0,
        "diversity": 0.0,
        "no_conflict": 1.0,
        "structural_confidence": 0.0,
        "judge_confidence": None,
        "threshold": 0.7,
        "search_count": 0,
        "max_searches": 20,
        "has_contradictions": False,
        "has_ambiguity": False,
        "uncoverable_claims": 0,
        "covered_claims": 0,
        "total_claims": 0,
    }
    base.update(overrides)
    return StopContext(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CoverageSignal
# ---------------------------------------------------------------------------


async def test_coverage_high_defers() -> None:
    out = await CoverageSignal().evaluate(_ctx(coverage=0.85))
    assert out.result is SignalResult.DEFER


async def test_coverage_at_threshold_defers() -> None:
    out = await CoverageSignal().evaluate(_ctx(coverage=0.80))
    assert out.result is SignalResult.DEFER


async def test_coverage_low_continues() -> None:
    out = await CoverageSignal().evaluate(_ctx(coverage=0.50))
    assert out.result is SignalResult.CONTINUE


def test_coverage_priority_is_30() -> None:
    assert CoverageSignal().priority == 30


def test_coverage_name() -> None:
    assert CoverageSignal().name == "Coverage"


# ---------------------------------------------------------------------------
# AgreementSignal
# ---------------------------------------------------------------------------


async def test_agreement_high_defers() -> None:
    out = await AgreementSignal().evaluate(_ctx(agreement=0.80))
    assert out.result is SignalResult.DEFER


async def test_agreement_at_threshold_defers() -> None:
    out = await AgreementSignal().evaluate(_ctx(agreement=0.70))
    assert out.result is SignalResult.DEFER


async def test_agreement_low_continues() -> None:
    out = await AgreementSignal().evaluate(_ctx(agreement=0.50))
    assert out.result is SignalResult.CONTINUE


def test_agreement_priority_is_35() -> None:
    assert AgreementSignal().priority == 35


def test_agreement_name() -> None:
    assert AgreementSignal().name == "Agreement"


# ---------------------------------------------------------------------------
# BudgetSignal
# ---------------------------------------------------------------------------


async def test_budget_under_limit_defers() -> None:
    out = await BudgetSignal().evaluate(_ctx(search_count=10, max_searches=20))
    assert out.result is SignalResult.DEFER


async def test_budget_at_limit_stops() -> None:
    out = await BudgetSignal().evaluate(_ctx(search_count=20, max_searches=20))
    assert out.result is SignalResult.STOP
    assert out.stop_reason is StopReason.STOPPED_BY_BUDGET


async def test_budget_over_limit_stops() -> None:
    out = await BudgetSignal().evaluate(_ctx(search_count=25, max_searches=20))
    assert out.result is SignalResult.STOP
    assert out.stop_reason is StopReason.STOPPED_BY_BUDGET


def test_budget_does_not_reference_judge_attempts() -> None:
    import inspect

    from app.stopping.signals import budget as budget_mod

    source = inspect.getsource(budget_mod)
    assert "judge_attempts" not in source


def test_budget_priority_is_20() -> None:
    assert BudgetSignal().priority == 20


def test_budget_name() -> None:
    assert BudgetSignal().name == "Budget"


# ---------------------------------------------------------------------------
# HonestStopSignal — DEPRECATED in WP-3 (always returns DEFER)
# ---------------------------------------------------------------------------


async def test_honest_signal_always_defers() -> None:
    """WP-3: signal kept as no-op for backward compatibility; never STOPs."""
    sig = HonestStopSignal()
    out_contradiction = await sig.evaluate(_ctx(has_contradictions=True, no_conflict=0.1))
    out_ambiguity = await sig.evaluate(_ctx(has_ambiguity=True))
    out_unanswerable = await sig.evaluate(
        _ctx(total_claims=4, covered_claims=0, uncoverable_claims=4)
    )
    out_clean = await sig.evaluate(_ctx(total_claims=3, covered_claims=2))
    for out in (out_contradiction, out_ambiguity, out_unanswerable, out_clean):
        assert out.result is SignalResult.DEFER
        assert out.stop_reason is None


def test_honest_priority_is_10() -> None:
    assert HonestStopSignal().priority == 10


# ---------------------------------------------------------------------------
# JudgeSignal
# ---------------------------------------------------------------------------


async def test_judge_no_confidence_continues() -> None:
    out = await JudgeSignal().evaluate(_ctx(judge_confidence=None))
    assert out.result is SignalResult.CONTINUE


async def test_judge_passes_all_gates() -> None:
    out = await JudgeSignal().evaluate(
        _ctx(
            coverage=0.85,
            agreement=0.75,
            structural_confidence=0.8,
            judge_confidence=0.85,
            threshold=0.7,
        )
    )
    assert out.result is SignalResult.STOP
    assert out.stop_reason is StopReason.JUDGE_CONFIRMED


async def test_judge_coverage_gate_blocks() -> None:
    out = await JudgeSignal().evaluate(
        _ctx(
            coverage=0.50,
            agreement=0.80,
            structural_confidence=0.6,
            judge_confidence=0.9,
            threshold=0.7,
        )
    )
    assert out.result is SignalResult.CONTINUE
    assert "Coverage gate" in (out.explanation or "")


async def test_judge_agreement_gate_blocks() -> None:
    out = await JudgeSignal().evaluate(
        _ctx(
            coverage=0.85,
            agreement=0.50,
            structural_confidence=0.7,
            judge_confidence=0.9,
            threshold=0.7,
        )
    )
    assert out.result is SignalResult.CONTINUE
    assert "Agreement gate" in (out.explanation or "")


async def test_judge_stops_when_passed_true_regardless_of_threshold() -> None:
    """C2: threshold is enforced by the judge LLM, not by this signal.

    Once judge_passed=True and coverage/agreement gates pass, the signal
    stops with JUDGE_CONFIRMED even if min(S, J) < threshold. The judge
    LLM is trusted to have applied the threshold itself.
    """
    out = await JudgeSignal().evaluate(
        _ctx(
            coverage=0.85,
            agreement=0.80,
            structural_confidence=0.8,
            judge_confidence=0.5,
            judge_passed=True,
            threshold=0.7,
        )
    )
    assert out.result is SignalResult.STOP
    assert out.stop_reason is StopReason.JUDGE_CONFIRMED
    # final = min(0.8, 0.5) = 0.5 is logged but not gated
    assert out.confidence == pytest.approx(0.5)


async def test_judge_final_min_S_J_surfaced_in_explanation() -> None:
    """C2: min(S, J) is still computed and surfaced (RF-12) even when low."""
    out = await JudgeSignal().evaluate(
        _ctx(
            coverage=0.85,
            agreement=0.80,
            structural_confidence=0.4,
            judge_confidence=0.9,
            judge_passed=True,
            threshold=0.7,
        )
    )
    assert out.result is SignalResult.STOP
    assert out.confidence == pytest.approx(0.4)
    assert "final=" in (out.explanation or "")


def test_judge_priority_is_40() -> None:
    assert JudgeSignal().priority == 40


def test_judge_name() -> None:
    assert JudgeSignal().name == "Judge"
