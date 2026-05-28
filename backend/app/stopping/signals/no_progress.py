"""No-progress signal — confidence plateau detector (IP-25 Phase B).

Fires when confidence has not improved meaningfully over the last 3
judge rounds, forcing transition to SYNTHESIZING to avoid wasted cycles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.seams.stopping import SignalResult, StopContext, StopSignalOutput

if TYPE_CHECKING:
    from app.agent.run_state import RunState

logger = structlog.get_logger(__name__)


class NoProgressSignal:
    """Layer C — confidence plateau checkpoint."""

    name: str = "NoProgress"
    priority: int = 30  # After Budget (20), before Judge (40)

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Fire if confidence delta over last 3 rounds < 0.05.

        Does NOT terminate the run directly — instead forces transition
        to SYNTHESIZING so the judge makes the final call with current
        evidence.
        """
        # Signal needs access to confidence_history, which is not in StopContext
        # We'll need to pass RunState through a different path
        # For now, return DEFER since we can't access history here
        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation="No-progress detection requires RunState access",
            confidence=context.structural_confidence,
        )


async def check_no_progress(state: RunState) -> tuple[bool, float]:
    """Check if confidence has plateaued over the last 3 rounds.

    Args:
        state: Current run state with confidence_history populated.

    Returns:
        Tuple of (fires: bool, delta: float). fires=True if plateau detected.
    """
    if len(state.confidence_history) < 3:
        return False, 0.0

    # Calculate delta between most recent and 3 rounds ago
    delta = state.confidence_history[-1] - state.confidence_history[-3]

    # Plateau threshold: less than 0.05 improvement
    if delta < 0.05:
        logger.warning(
            "no_progress_detected",
            delta=delta,
            current=state.confidence_history[-1],
            history_length=len(state.confidence_history),
        )
        return True, delta

    return False, delta
