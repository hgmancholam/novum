"""Tests for ``app.confidence.structural`` (BRD-08 RF-12 / RF-15)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.confidence.structural import (
    calculate_agreement,
    calculate_coverage,
    calculate_diversity,
    calculate_no_conflict,
    calculate_structural_confidence,
)
from app.domain.enums import AuthorityTier
from app.domain.events import (
    ContradictionDetectedEvent,
    ContradictionSource,
    SubClaim,
)


def _state(
    sub_claims: list[SubClaim] | None = None,
    covered: list[str] | None = None,
    evidence: list[EvidenceItem] | None = None,
    contradictions: list[ContradictionDetectedEvent] | None = None,
) -> RunState:
    return RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=sub_claims or [],
        covered_claims=covered or [],
        evidence=evidence or [],
        contradictions=contradictions or [],
    )


def _ev(url: str, polarity: str = "supports", confidence: float = 0.8) -> EvidenceItem:
    return EvidenceItem(
        claim_id="c1",
        source_url=url,
        source_title="t",
        text="x",
        polarity=polarity,
        confidence=confidence,
        authority_tier=AuthorityTier.REPUTABLE_SECONDARY,
    )


def _contradiction() -> ContradictionDetectedEvent:
    src = ContradictionSource(url="https://a.com", title="A", claim="c1")
    return ContradictionDetectedEvent(
        claim_id="c1",
        source_a=src,
        source_b=ContradictionSource(url="https://b.com", title="B", claim="c1"),
        nature_of_conflict="conflict",
    )


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_coverage_with_no_claims() -> None:
    assert calculate_coverage(_state()) == 0.0


def test_coverage_all_covered() -> None:
    claims = [SubClaim(id=f"c{i}", text="t", status="covered") for i in range(3)]
    state = _state(sub_claims=claims, covered=["c0", "c1", "c2"])
    assert calculate_coverage(state) == 1.0


def test_coverage_partial() -> None:
    claims = [SubClaim(id=f"c{i}", text="t") for i in range(3)]
    state = _state(sub_claims=claims, covered=["c0", "c1"])
    assert calculate_coverage(state) == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------


def test_agreement_empty_evidence() -> None:
    assert calculate_agreement([]) == 0.0


def test_agreement_all_supports() -> None:
    evidence = [_ev(f"https://a{i}.com", "supports", 0.8) for i in range(3)]
    assert calculate_agreement(evidence) == pytest.approx(1.0)


def test_agreement_mixed() -> None:
    evidence = [
        _ev("https://a.com", "supports", 0.9),
        _ev("https://b.com", "supports", 0.9),
        _ev("https://c.com", "contradicts", 0.5),
    ]
    assert calculate_agreement(evidence) == pytest.approx(1.8 / 2.3)


def test_agreement_zero_total_weight() -> None:
    evidence = [_ev("https://a.com", "supports", 0.0) for _ in range(2)]
    assert calculate_agreement(evidence) == 0.0


# ---------------------------------------------------------------------------
# Diversity
# ---------------------------------------------------------------------------


def test_diversity_no_evidence() -> None:
    assert calculate_diversity([]) == 0.0


def test_diversity_one_domain() -> None:
    evidence = [_ev("https://a.com/x"), _ev("https://a.com/y")]
    assert calculate_diversity(evidence) == pytest.approx(0.3)


def test_diversity_two_domains() -> None:
    evidence = [_ev("https://a.com"), _ev("https://b.com")]
    assert calculate_diversity(evidence) == pytest.approx(0.5)


def test_diversity_three_domains() -> None:
    evidence = [_ev(f"https://{c}.com") for c in "abc"]
    assert calculate_diversity(evidence) == pytest.approx(0.7)


def test_diversity_four_domains() -> None:
    evidence = [_ev(f"https://{c}.com") for c in "abcd"]
    assert calculate_diversity(evidence) == pytest.approx(0.9)


def test_diversity_five_or_more() -> None:
    evidence = [_ev(f"https://{c}.com") for c in "abcde"]
    assert calculate_diversity(evidence) == pytest.approx(1.0)
    evidence_more = [_ev(f"https://{c}.com") for c in "abcdefg"]
    assert calculate_diversity(evidence_more) == pytest.approx(1.0)


def test_diversity_normalizes_www_and_scheme() -> None:
    evidence = [
        _ev("https://www.x.com/a"),
        _ev("x.com/b"),
    ]
    assert calculate_diversity(evidence) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# No-conflict
# ---------------------------------------------------------------------------


def test_no_conflict_no_evidence() -> None:
    assert calculate_no_conflict(_state()) == 1.0


def test_no_conflict_no_contradictions() -> None:
    evidence = [_ev("https://a.com") for _ in range(3)]
    state = _state(evidence=evidence)
    assert calculate_no_conflict(state) == 1.0


def test_no_conflict_partial() -> None:
    evidence = [_ev("https://a.com") for _ in range(4)]
    contradictions = [_contradiction()]
    state = _state(evidence=evidence, contradictions=contradictions)
    assert calculate_no_conflict(state) == pytest.approx(0.75)


def test_no_conflict_more_contradictions_than_evidence() -> None:
    evidence = [_ev("https://a.com")]
    contradictions = [_contradiction() for _ in range(3)]
    state = _state(evidence=evidence, contradictions=contradictions)
    assert calculate_no_conflict(state) == 0.0


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def test_structural_full_state() -> None:
    claims = [SubClaim(id=f"c{i}", text="t") for i in range(2)]
    evidence = [
        _ev("https://a.com", "supports", 0.8),
        _ev("https://b.com", "supports", 0.8),
        _ev("https://c.com", "contradicts", 0.4),
    ]
    state = _state(sub_claims=claims, covered=["c0"], evidence=evidence)
    result = calculate_structural_confidence(state)

    assert result.coverage == pytest.approx(0.5)
    assert result.agreement == pytest.approx(1.6 / 2.0)
    assert result.diversity == pytest.approx(0.7)
    assert result.no_conflict == pytest.approx(1.0)
    expected = (
        0.35 * 0.5
        + 0.30 * (1.6 / 2.0)
        + 0.20 * 0.7
        + 0.15 * 1.0
    )
    assert result.score == pytest.approx(expected)
