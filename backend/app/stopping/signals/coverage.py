"""Coverage signal — defers when claim coverage meets the gate.

Returns ``DEFER`` when ``coverage >= 0.8`` (the "enough breadth"
threshold from BRD-09 §4.4). Otherwise ``CONTINUE`` — keep searching.
Never emits ``STOP``; terminal decisions are owned by the Judge,
Budget, or Honest signals.
"""

from __future__ import annotations

from app.seams.stopping import SignalResult, StopContext, StopSignalOutput

_COVERAGE_GATE: float = 0.8


class CoverageSignal:
    """Layer A — coverage gate."""

    name: str = "Coverage"
    priority: int = 30

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        if context.coverage >= _COVERAGE_GATE:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation=f"Coverage gate met: {context.coverage:.0%} >= 80%",
                confidence=context.structural_confidence,
            )
        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.CONTINUE,
            explanation=f"Coverage gate not met: {context.coverage:.0%} < 80%",
            confidence=context.structural_confidence,
        )
