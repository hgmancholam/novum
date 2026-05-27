"""Confidence calculator (RF-12, WP-3).

Wraps ``calculate_structural_confidence`` with judge confidence to
produce a ``ConfidenceResult`` containing ``final = min(S_effective, J)``
where S_effective = S_raw · kind_ceiling[answer_kind]. ``check_sufficient``
is implemented for BRD-09 consumption but not yet wired into the FSM (IP-08 O-08).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.confidence.kind_ceiling import apply_ceiling
from app.confidence.structural import calculate_structural_confidence
from app.domain.confidence import ConfidenceResult

if TYPE_CHECKING:
    from app.agent.run_state import RunState
    from app.domain.enums import AnswerKind


class ConfidenceCalculator:
    """Compute structural + final confidence and check sufficiency."""

    def __init__(self, threshold: float = 0.7) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"threshold must be in [0.0, 1.0], got {threshold}"
            )
        self.threshold = threshold

    def calculate(
        self,
        state: RunState,
        judge_confidence: float,
        answer_kind: AnswerKind | None = None,
        kind_appropriateness: float = 1.0,
    ) -> ConfidenceResult:
        """Return a ``ConfidenceResult`` with ``final = min(S_effective, J)``.

        Args:
            state: Current run state
            judge_confidence: J ∈ [0.0, 1.0]
            answer_kind: Selected AnswerKind for ceiling application (None → ceiling=1.0)
            kind_appropriateness: Judge-scored kind fitness (defaults to 1.0)

        Returns:
            ConfidenceResult with ceiling applied to structural score
        """
        structural = calculate_structural_confidence(
            state,
            kind_appropriateness,
            expected_experts=state.expected_experts or None,
        )
        s_raw = structural.score
        s_effective = (
            apply_ceiling(s_raw, answer_kind)
            if answer_kind is not None
            else s_raw
        )
        final = min(s_effective, judge_confidence)
        return ConfidenceResult(
            structural=structural,
            judge=judge_confidence,
            final=final,
            threshold=self.threshold,
            passed=final >= self.threshold,
        )

    def check_sufficient(self, state: RunState) -> bool:
        """Per-component sufficiency check (BRD-09 territory, not wired)."""
        structural = calculate_structural_confidence(
            state,
            expected_experts=state.expected_experts or None,
        )
        return (
            structural.coverage >= 0.6
            and structural.agreement >= 0.5
            and structural.no_conflict >= 0.7
        )
