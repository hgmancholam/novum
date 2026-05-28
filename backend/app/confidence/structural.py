"""Structural confidence components (RF-12, RF-15).

Pure synchronous helpers operating on in-memory ``RunState``. Each
function returns a float in ``[0.0, 1.0]`` and is safe against the
empty edge cases documented in IP-08 §4.1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.agent.experts import match as expert_match
from app.config import settings
from app.domain.confidence import StructuralConfidence
from app.domain.enums import AuthorityTier

if TYPE_CHECKING:
    from app.agent.run_state import EvidenceItem, RunState

_DIVERSITY_TABLE: dict[int, float] = {0: 0.0, 1: 0.3, 2: 0.5, 3: 0.7, 4: 0.9}


def _authority_multiplier(tier: AuthorityTier | None) -> float:
    """Return BRD-23 §4.7 multiplier for *tier* (``GENERAL`` when ``None``)."""
    effective = tier if tier is not None else AuthorityTier.GENERAL
    match effective:
        case AuthorityTier.PRIMARY_AUTHORITATIVE:
            return settings.authority_multiplier_primary
        case AuthorityTier.REPUTABLE_SECONDARY:
            return settings.authority_multiplier_reputable
        case AuthorityTier.GENERAL:
            return settings.authority_multiplier_general
        case AuthorityTier.LOW_SIGNAL:
            return settings.authority_multiplier_low


def calculate_coverage(state: RunState) -> float:
    """C_coverage: covered claims / total sub-claims, authority-weighted (BRD-23 §4.7).

    Each covered claim contributes the mean authority multiplier of its
    supporting evidence rows; claims with no evidence contribute 1.0
    (pre-BRD-23 baseline). Result is clamped to ``[0.0, 1.0]``.
    """
    if not state.sub_claims:
        return 0.0
    total = 0.0
    for claim_id in state.covered_claims:
        rows = [e for e in state.evidence if e.claim_id == claim_id]
        if not rows:
            total += 1.0
            continue
        total += sum(_authority_multiplier(r.authority_tier) for r in rows) / len(rows)
    return max(0.0, min(1.0, total / len(state.sub_claims)))


def calculate_agreement(
    evidence: list[EvidenceItem],
    expected_experts: list[str] | None = None,
) -> float:
    """C_agreement: confidence-weighted ratio of non-contradicting evidence.

    V1 polarity is not yet classified per snippet (search.py emits all
    evidence as ``neutral``). Treat ``neutral`` as tacit support when no
    contradicting evidence exists for the same body: retrieval that
    returns N sources without explicit dissent is evidence that the
    claim is uncontroversial, not that the evidence is mute.

    Formula: ``(supports + neutral) / (supports + neutral + contradicts)``
    weighted by per-item confidence. Returns 0.0 only when the body is
    empty or fully contradicting.

    Args:
        evidence: List of evidence items
        expected_experts: Expert labels for credibility boost (US-22-3).
                         Applies 1.1× multiplier to aligning evidence from
                         matching sources, clamped per-row to [0, 1].
                         Contradicting evidence never receives multiplier.

    Returns:
        Agreement score in [0.0, 1.0]
    """
    if not evidence:
        return 0.0
    
    # Apply expert multiplier to aligning evidence only (supports + neutral),
    # clamped per-row to avoid exceeding 1.0
    aligning_weight = sum(
        min(e.confidence * expert_match(e.source_url, expected_experts), 1.0)
        for e in evidence
        if e.polarity in ("supports", "neutral")
    )
    
    # Contradicting evidence never receives multiplier
    contradicting_weight = sum(
        e.confidence for e in evidence if e.polarity == "contradicts"
    )
    
    denom = aligning_weight + contradicting_weight
    if denom == 0.0:
        return 0.0
    return aligning_weight / denom


def _extract_domain(url: str) -> str:
    """Return a lowercased host without scheme or ``www.`` prefix."""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = (parsed.netloc or parsed.path).split("/")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def calculate_diversity(evidence: list[EvidenceItem]) -> float:
    """C_diversity: unique-domain count mapped through a fixed table,
    then scaled by the mean authority multiplier across unique domains
    (BRD-23 §4.7). Clamped to ``[0.0, 1.0]``.
    """
    if not evidence:
        return 0.0
    # Best (highest-multiplier) tier seen per domain.
    best_per_domain: dict[str, float] = {}
    for e in evidence:
        host = _extract_domain(e.source_url)
        mult = _authority_multiplier(e.authority_tier)
        if mult > best_per_domain.get(host, 0.0):
            best_per_domain[host] = mult
    count = len(best_per_domain)
    base = _DIVERSITY_TABLE.get(count, 1.0)
    mean_mult = sum(best_per_domain.values()) / count
    return max(0.0, min(1.0, base * mean_mult))


def calculate_no_conflict(state: RunState) -> float:
    """C_no_conflict: 1 - contradictions / evidence, clamped to [0.0, 1.0]."""
    if not state.evidence:
        return 1.0
    ratio = len(state.contradictions) / len(state.evidence)
    return max(0.0, 1.0 - ratio)


def calculate_structural_confidence(
    state: RunState,
    kind_appropriateness: float = 1.0,
    expected_experts: list[str] | None = None,
) -> StructuralConfidence:
    """Compose the five S components into a ``StructuralConfidence``.

    Args:
        state: Current run state
        kind_appropriateness: Judge-scored 0..1 "does AnswerKind fit the question?"
                              (WP-3 G5). Defaults to 1.0 when not yet judged.
        expected_experts: Expert labels for credibility boost (US-22-3).
                         Passed through to calculate_agreement.

    Returns:
        StructuralConfidence with all components populated
    """
    return StructuralConfidence(
        coverage=calculate_coverage(state),
        agreement=calculate_agreement(state.evidence, expected_experts=expected_experts),
        diversity=calculate_diversity(state.evidence),
        no_conflict=calculate_no_conflict(state),
        kind_appropriateness=kind_appropriateness,
    )
