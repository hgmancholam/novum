"""BRD-23 WP-1: kind-ceiling stale-citation penalty tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.agent.run_state import EvidenceItem
from app.confidence.kind_ceiling import apply_ceiling, is_stale_majority
from app.config import settings
from app.domain.enums import AnswerKind, TemporalSensitivity


def _evidence(published: datetime | None) -> EvidenceItem:
    return EvidenceItem(
        event_id=uuid4(),
        claim_id="c1",
        source_url="https://example.com",
        source_title="t",
        text="snippet",
        polarity="neutral",
        confidence=0.5,
        source_published_date=published,
    )


def test_no_penalty_when_temporal_is_none() -> None:
    fresh = datetime.now(UTC)
    assert apply_ceiling(0.8, AnswerKind.DIRECT) == 0.8 * 1.00
    assert (
        apply_ceiling(0.8, AnswerKind.DIRECT, temporal_sensitivity=None, stale_majority=True)
        == 0.8 * 1.00
    )
    assert fresh  # silence unused


def test_penalty_applies_only_on_direct_volatile_with_stale_majority() -> None:
    s_raw = 0.8
    base = s_raw * 1.00
    penalty = base * settings.temporal_stale_penalty

    # DIRECT + VOLATILE + stale → penalty
    assert (
        apply_ceiling(
            s_raw,
            AnswerKind.DIRECT,
            temporal_sensitivity=TemporalSensitivity.VOLATILE,
            stale_majority=True,
        )
        == penalty
    )
    # DIRECT + STATIC + stale → no penalty
    assert (
        apply_ceiling(
            s_raw,
            AnswerKind.DIRECT,
            temporal_sensitivity=TemporalSensitivity.STATIC,
            stale_majority=True,
        )
        == base
    )
    # WEIGHTED ceiling untouched even on volatile + stale
    weighted_base = s_raw * 0.85
    assert (
        apply_ceiling(
            s_raw,
            AnswerKind.WEIGHTED,
            temporal_sensitivity=TemporalSensitivity.VOLATILE,
            stale_majority=True,
        )
        == weighted_base
    )


def test_is_stale_majority_counts_missing_dates_as_stale() -> None:
    fresh = datetime.now(UTC) - timedelta(days=3)
    stale = datetime.now(UTC) - timedelta(days=400)

    # 50%+ stale → True
    assert is_stale_majority([_evidence(fresh), _evidence(stale)], days_filter=180) is True
    # Missing dates count as stale when days_filter is provided
    assert is_stale_majority([_evidence(None), _evidence(fresh)], days_filter=180) is True
    # All fresh → False
    assert is_stale_majority([_evidence(fresh), _evidence(fresh)], days_filter=180) is False
    # days_filter=None → False regardless
    assert is_stale_majority([_evidence(stale)], days_filter=None) is False
    # Empty evidence → False
    assert is_stale_majority([], days_filter=180) is False
