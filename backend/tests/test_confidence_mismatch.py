"""Tests for ``app.confidence.mismatch`` (BRD-08 RF-15)."""

from __future__ import annotations

import pytest

from app.confidence.mismatch import MismatchResult, detect_mismatch


def test_no_mismatch_below_threshold() -> None:
    result = detect_mismatch(structural=0.8, judge=0.7)
    assert result.has_mismatch is False
    assert result.trust_flag is None
    assert result.divergence == pytest.approx(0.1)


def test_no_mismatch_at_threshold() -> None:
    # Strict greater-than: divergence exactly == threshold must not trigger.
    # Use exact IEEE-754 values (0.5 and 0.25) to avoid FP slack.
    result = detect_mismatch(structural=0.5, judge=0.25, threshold=0.25)
    assert result.has_mismatch is False
    assert result.trust_flag is None
    assert result.divergence == pytest.approx(0.25)


def test_mismatch_structural_higher() -> None:
    result = detect_mismatch(structural=0.85, judge=0.55)
    assert result.has_mismatch is True
    assert result.trust_flag is not None
    assert "Structural metrics" in result.trust_flag
    assert "85%" in result.trust_flag
    assert "55%" in result.trust_flag


def test_mismatch_judge_higher() -> None:
    result = detect_mismatch(structural=0.30, judge=0.80)
    assert result.has_mismatch is True
    assert result.trust_flag is not None
    assert "Judge assessment" in result.trust_flag
    assert "80%" in result.trust_flag
    assert "30%" in result.trust_flag


def test_mismatch_custom_threshold() -> None:
    result = detect_mismatch(structural=0.5, judge=0.65, threshold=0.1)
    assert result.has_mismatch is True
    assert result.trust_flag is not None


def test_mismatch_divergence_value() -> None:
    result = detect_mismatch(structural=0.85, judge=0.55)
    assert result.divergence == pytest.approx(0.30)


def test_mismatch_equal_values_no_flag() -> None:
    result = detect_mismatch(structural=0.7, judge=0.7)
    assert result.has_mismatch is False
    assert result.divergence == 0.0


def test_mismatch_result_is_frozen() -> None:
    result = detect_mismatch(structural=0.85, judge=0.55)
    assert isinstance(result, MismatchResult)
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        result.has_mismatch = False  # type: ignore[misc]
