"""Confidence calculation engine (BRD-08, RF-12, RF-15)."""

from __future__ import annotations

from app.confidence.calculator import ConfidenceCalculator
from app.confidence.mismatch import MismatchResult, detect_mismatch
from app.confidence.structural import (
    calculate_agreement,
    calculate_coverage,
    calculate_diversity,
    calculate_no_conflict,
    calculate_structural_confidence,
)

__all__ = [
    "ConfidenceCalculator",
    "MismatchResult",
    "calculate_agreement",
    "calculate_coverage",
    "calculate_diversity",
    "calculate_no_conflict",
    "calculate_structural_confidence",
    "detect_mismatch",
]
