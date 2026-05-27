"""Confidence calculation engine (BRD-08, RF-12, RF-15, WP-3)."""

from __future__ import annotations

from app.confidence.calculator import ConfidenceCalculator
from app.confidence.kind_ceiling import KIND_CEILING, apply_ceiling
from app.confidence.mismatch import MismatchResult, detect_mismatch
from app.confidence.structural import (
    calculate_agreement,
    calculate_coverage,
    calculate_diversity,
    calculate_no_conflict,
    calculate_structural_confidence,
)

__all__ = [
    "KIND_CEILING",
    "ConfidenceCalculator",
    "MismatchResult",
    "apply_ceiling",
    "calculate_agreement",
    "calculate_coverage",
    "calculate_diversity",
    "calculate_no_conflict",
    "calculate_structural_confidence",
    "detect_mismatch",
]
