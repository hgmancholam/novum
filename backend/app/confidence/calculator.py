"""Confidence calculator (RF-12).

Wraps ``calculate_structural_confidence`` with judge confidence to
produce a ``ConfidenceResult`` containing ``final = min(S, J)`` and a
threshold-gating flag. ``check_sufficient`` is implemented for BRD-09
consumption but not yet wired into the FSM (IP-08 O-08).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.confidence.structural import calculate_structural_confidence
from app.domain.confidence import ConfidenceResult

if TYPE_CHECKING:
    from app.agent.run_state import RunState


class ConfidenceCalculator:
    """Compute structural + final confidence and check sufficiency."""

    def __init__(self, threshold: float = 0.7) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"threshold must be in [0.0, 1.0], got {threshold}"
            )
        self.threshold = threshold

    def calculate(self, state: RunState, judge_confidence: float) -> ConfidenceResult:
        """Return a ``ConfidenceResult`` with ``final = min(S, J)``."""
        structural = calculate_structural_confidence(state)
        final = min(structural.score, judge_confidence)
        return ConfidenceResult(
            structural=structural,
            judge=judge_confidence,
            final=final,
            threshold=self.threshold,
            passed=final >= self.threshold,
        )

    def check_sufficient(self, state: RunState) -> bool:
        """Per-component sufficiency check (BRD-09 territory, not wired)."""
        structural = calculate_structural_confidence(state)
        return (
            structural.coverage >= 0.6
            and structural.agreement >= 0.5
            and structural.no_conflict >= 0.7
        )
