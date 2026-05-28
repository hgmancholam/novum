"""BRD-23 §4.7 — Authority-tier multiplier inside C_coverage and C_diversity."""

from __future__ import annotations

from uuid import uuid4

from app.agent.run_state import EvidenceItem, RunState
from app.confidence.structural import (
    calculate_agreement,
    calculate_coverage,
    calculate_diversity,
    calculate_no_conflict,
    calculate_structural_confidence,
)
from app.domain.confidence import StructuralConfidence
from app.domain.enums import AuthorityTier
from app.domain.events import SubClaim


def _ev(
    url: str,
    claim_id: str = "c1",
    tier: AuthorityTier | None = None,
    polarity: str = "supports",
    confidence: float = 0.8,
) -> EvidenceItem:
    return EvidenceItem(
        claim_id=claim_id,
        source_url=url,
        source_title="t",
        text="x",
        polarity=polarity,
        confidence=confidence,
        authority_tier=tier,
    )


def _state_one_claim(*evidence: EvidenceItem) -> RunState:
    return RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=[SubClaim(id="c1", text="t", status="covered")],
        covered_claims=["c1"],
        evidence=list(evidence),
    )


def test_primary_authoritative_row_contributes_1_05x_to_c_coverage() -> None:
    state = _state_one_claim(
        _ev("https://cdc.gov/x", tier=AuthorityTier.PRIMARY_AUTHORITATIVE)
    )
    # Mean multiplier for the one row = 1.05; clamped to 1.0
    assert calculate_coverage(state) == 1.0


def test_general_row_contributes_0_90x_to_c_coverage() -> None:
    state = _state_one_claim(_ev("https://example.com/x", tier=AuthorityTier.GENERAL))
    assert abs(calculate_coverage(state) - 0.90) < 1e-9


def test_low_signal_row_contributes_0_50x_to_c_coverage() -> None:
    state = _state_one_claim(_ev("https://medium.com/x", tier=AuthorityTier.LOW_SIGNAL))
    assert abs(calculate_coverage(state) - 0.50) < 1e-9


def test_c_coverage_clamped_to_1_0_after_multiplier() -> None:
    # Three primary-authoritative rows on one claim → mean = 1.05, clamped 1.0
    state = _state_one_claim(
        _ev("https://a.gov/1", tier=AuthorityTier.PRIMARY_AUTHORITATIVE),
        _ev("https://b.gov/2", tier=AuthorityTier.PRIMARY_AUTHORITATIVE),
        _ev("https://c.gov/3", tier=AuthorityTier.PRIMARY_AUTHORITATIVE),
    )
    assert calculate_coverage(state) == 1.0


def test_low_signal_rows_drag_c_diversity_below_baseline() -> None:
    """C_diversity with 4 LOW_SIGNAL domains: base=0.9 × mean=0.50 = 0.45."""
    ev = [
        _ev("https://medium.com/a", tier=AuthorityTier.LOW_SIGNAL),
        _ev("https://quora.com/b", tier=AuthorityTier.LOW_SIGNAL),
        _ev("https://substack.com/c", tier=AuthorityTier.LOW_SIGNAL),
        _ev("https://w3schools.com/d", tier=AuthorityTier.LOW_SIGNAL),
    ]
    assert abs(calculate_diversity(ev) - (0.9 * 0.5)) < 1e-9


def test_diversity_takes_best_tier_per_domain() -> None:
    """Two rows on same host; the higher tier should win."""
    ev = [
        _ev("https://nyt.com/a", tier=AuthorityTier.REPUTABLE_SECONDARY),
        _ev("https://nyt.com/b", tier=AuthorityTier.LOW_SIGNAL),
    ]
    # 1 unique domain → base=0.3, mean_mult=1.00 → 0.30
    assert abs(calculate_diversity(ev) - 0.30) < 1e-9


def test_c_agreement_untouched_by_authority_multiplier() -> None:
    """BRD-23 §4.7 scope: agreement/no_conflict are NOT touched."""
    ev = [
        _ev("https://medium.com/a", tier=AuthorityTier.LOW_SIGNAL, polarity="supports", confidence=0.8),
        _ev("https://cdc.gov/b", tier=AuthorityTier.PRIMARY_AUTHORITATIVE, polarity="supports", confidence=0.8),
    ]
    # Without expert boost, both align fully; LOW_SIGNAL row receives same agreement weight as PRIMARY.
    # Expected = 1.0 (no contradictions).
    assert calculate_agreement(ev) == 1.0


def test_c_no_conflict_untouched_by_authority_multiplier() -> None:
    state = _state_one_claim(
        _ev("https://medium.com/x", tier=AuthorityTier.LOW_SIGNAL),
    )
    assert calculate_no_conflict(state) == 1.0


def test_authority_tier_missing_defaults_to_general_on_replay() -> None:
    """Pre-BRD-23 traces (tier=None) replay as GENERAL → multiplier 0.90."""
    state = _state_one_claim(_ev("https://unknown.example/x", tier=None))
    assert abs(calculate_coverage(state) - 0.90) < 1e-9


def test_final_confidence_respects_authority_through_s_effective() -> None:
    """Compose full S and verify the authority multiplier flows through."""
    state = _state_one_claim(_ev("https://medium.com/x", tier=AuthorityTier.LOW_SIGNAL))
    s = calculate_structural_confidence(state)
    assert isinstance(s, StructuralConfidence)
    # C_coverage drops to 0.5 vs pre-BRD-23 baseline of 1.0 for the covered claim.
    assert abs(s.coverage - 0.50) < 1e-9
