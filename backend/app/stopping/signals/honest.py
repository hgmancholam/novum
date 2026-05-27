"""Honest stop signal — DEPRECATED in WP-3.

WP-3 amendment (2026-05-27): honest stops are removed. The conditions
that previously fired HONEST_* now route through draft→resolver→judge
with AnswerKind selection (best_effort, weighted, scenario). This
signal always returns DEFER to preserve backward compat with the
stopping policy architecture.
"""

from __future__ import annotations

from app.seams.stopping import SignalResult, StopContext, StopSignalOutput


class HonestStopSignal:
    """Layer E — DEPRECATED (WP-3, always returns DEFER)."""

    name: str = "HonestStop"
    priority: int = 10

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Always defer — honest stops removed in WP-3."""
        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation="WP-3: honest stops removed, all questions now answered",
            confidence=context.structural_confidence,
        )
