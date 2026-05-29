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


# PR-1 (post-2026-05-29 eval): progress markers used by the event-level plateau
# predicate. If the last ``window`` events contain ZERO of these, the run is
# stuck in SEARCHING↔ANALYZING without producing any structural progress, and
# the orchestrator should stop with ``stopped_by_budget`` (kind=no_progress_events).
_PROGRESS_MARKERS: frozenset[str] = frozenset(
    {
        "ClaimCovered",
        "DraftSynthesized",
        "JudgeRuled",
        "PlanGapsDetected",
        "HypothesisEvaluated",
    }
)


def check_event_level_plateau(state: RunState, window: int | None = None) -> bool:
    """Fire when the last ``window`` emitted events contain no progress markers.

    Independent of ``confidence_history`` (which never populates pre-JUDGING),
    so it is the only no-progress detector that works while the FSM is stuck
    cycling SEARCHING → ANALYZING → SEARCHING.

    Args:
        state: Live ``RunState`` whose ``events`` list is populated by the
            orchestrator's ``emit`` wrapper.
        window: How many trailing events to inspect. Defaults to
            ``state.no_progress_event_window``.

    Returns:
        True if the trailing window has at least ``window`` events AND none of
        them is a progress marker. False otherwise (including warm-up where
        fewer than ``window`` events have been emitted).
    """
    win = window if window is not None else state.no_progress_event_window
    if win <= 0 or len(state.events) < win:
        return False
    tail = state.events[-win:]
    return not any(ev.type.value in _PROGRESS_MARKERS for ev in tail)


# PR-5 Mejora 5.2 (post-2026-05-29 eval): claim-coverage plateau.
# Snapshots of ``len(state.covered_claims)`` are appended to
# ``state.coverage_history`` exactly once per ``_handle_analyzing`` round.
# If the last ``rounds`` snapshots show zero growth (the most recent value
# equals the value ``rounds`` snapshots back), the run is searching without
# converting evidence into claim coverage and should stop best-effort.
_DEFAULT_COVERAGE_PLATEAU_ROUNDS: int = 3


def check_claim_coverage_plateau(state: RunState, rounds: int | None = None) -> bool:
    """Fire when the last ``rounds`` analyze cycles added 0 new covered claims.

    Independent of ``confidence_history`` and of judge runs, so it catches
    the SEARCHING ↔ ANALYZING ping-pong that adds evidence without ever
    promoting a sub-claim to ``covered``.

    Args:
        state: Live ``RunState`` whose ``coverage_history`` is populated by
            the orchestrator at the top of ``_handle_analyzing``.
        rounds: How many trailing snapshots must show zero growth. Defaults
            to 3.

    Returns:
        True if at least ``rounds + 1`` snapshots have been recorded AND
        ``coverage_history[-1] == coverage_history[-(rounds + 1)]``. False
        otherwise (including warm-up where fewer snapshots exist).
    """
    n = rounds if rounds is not None else _DEFAULT_COVERAGE_PLATEAU_ROUNDS
    if n <= 0 or len(state.coverage_history) < n + 1:
        return False
    return state.coverage_history[-1] == state.coverage_history[-(n + 1)]
