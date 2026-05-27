"""Tests for ``app.confidence.calculator`` (BRD-08 RF-12)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.confidence.calculator import ConfidenceCalculator
from app.domain.events import SubClaim


def _state_full(coverage_ratio: float = 1.0) -> RunState:
    claims = [SubClaim(id=f"c{i}", text="t", status="covered") for i in range(2)]
    covered = ["c0", "c1"] if coverage_ratio >= 1.0 else ["c0"]
    evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url=f"https://{d}.com",
            source_title="t",
            text="x",
            polarity="supports",
            confidence=0.9,
        )
        for d in ("a", "b", "c", "d", "e")
    ]
    return RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=claims,
        covered_claims=covered,
        evidence=evidence,
    )


def test_init_default_threshold() -> None:
    assert ConfidenceCalculator().threshold == pytest.approx(0.7)


def test_init_custom_threshold() -> None:
    assert ConfidenceCalculator(threshold=0.5).threshold == pytest.approx(0.5)


def test_init_invalid_threshold_high_raises() -> None:
    with pytest.raises(ValueError):
        ConfidenceCalculator(threshold=1.5)


def test_init_invalid_threshold_negative_raises() -> None:
    with pytest.raises(ValueError):
        ConfidenceCalculator(threshold=-0.1)


def test_calculate_final_uses_min_judge_lower() -> None:
    calc = ConfidenceCalculator(threshold=0.5)
    result = calc.calculate(_state_full(), judge_confidence=0.4)
    assert result.final == pytest.approx(0.4)
    assert result.judge == pytest.approx(0.4)


def test_calculate_final_uses_min_structural_lower() -> None:
    calc = ConfidenceCalculator(threshold=0.5)
    # Empty state → S = 0
    empty = RunState(run_id=uuid4(), question="Q?")
    result = calc.calculate(empty, judge_confidence=0.9)
    assert result.final == pytest.approx(result.structural.score)


def test_calculate_passed_above_threshold() -> None:
    calc = ConfidenceCalculator(threshold=0.5)
    result = calc.calculate(_state_full(), judge_confidence=0.9)
    assert result.passed is True


def test_calculate_passed_below_threshold() -> None:
    calc = ConfidenceCalculator(threshold=0.8)
    result = calc.calculate(_state_full(), judge_confidence=0.3)
    assert result.passed is False


def test_calculate_returns_structural_components() -> None:
    calc = ConfidenceCalculator()
    result = calc.calculate(_state_full(), judge_confidence=1.0)
    assert result.structural.coverage == pytest.approx(1.0)
    assert result.structural.agreement == pytest.approx(1.0)
    assert result.structural.diversity == pytest.approx(1.0)
    assert result.structural.no_conflict == pytest.approx(1.0)


def test_calculate_threshold_preserved() -> None:
    calc = ConfidenceCalculator(threshold=0.65)
    result = calc.calculate(_state_full(), judge_confidence=0.8)
    assert result.threshold == pytest.approx(0.65)


def test_check_sufficient_true() -> None:
    # coverage 1.0 + agreement 1.0 + no_conflict 1.0 → True
    assert ConfidenceCalculator().check_sufficient(_state_full()) is True


def test_check_sufficient_low_coverage() -> None:
    claims = [SubClaim(id=f"c{i}", text="t") for i in range(10)]
    state = RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=claims,
        covered_claims=["c0", "c1", "c2"],  # 30 % coverage
        evidence=[
            EvidenceItem(
                claim_id="c1",
                source_url="https://a.com",
                source_title="t",
                text="x",
                polarity="supports",
                confidence=0.9,
            )
        ],
    )
    assert ConfidenceCalculator().check_sufficient(state) is False


def test_check_sufficient_low_agreement() -> None:
    claims = [SubClaim(id=f"c{i}", text="t", status="covered") for i in range(2)]
    state = RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=claims,
        covered_claims=["c0", "c1"],
        evidence=[
            EvidenceItem(
                claim_id="c1",
                source_url=f"https://{d}.com",
                source_title="t",
                text="x",
                polarity="refutes",
                confidence=0.9,
            )
            for d in ("a", "b")
        ],
    )
    assert ConfidenceCalculator().check_sufficient(state) is False


def test_check_sufficient_too_many_conflicts() -> None:
    from app.domain.events import ContradictionDetectedEvent, ContradictionSource

    claims = [SubClaim(id=f"c{i}", text="t", status="covered") for i in range(2)]
    evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url=f"https://{d}.com",
            source_title="t",
            text="x",
            polarity="supports",
            confidence=0.9,
        )
        for d in ("a", "b")
    ]
    contradictions = [
        ContradictionDetectedEvent(
            claim_id="c1",
            source_a=ContradictionSource(url="https://a.com", title="A", claim="c1"),
            source_b=ContradictionSource(url="https://b.com", title="B", claim="c1"),
            nature_of_conflict="conflict",
        )
    ]
    state = RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=claims,
        covered_claims=["c0", "c1"],
        evidence=evidence,
        contradictions=contradictions,
    )
    # no_conflict = 1 - 1/2 = 0.5 < 0.7
    assert ConfidenceCalculator().check_sufficient(state) is False
