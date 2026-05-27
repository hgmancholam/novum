"""Stopping-policy coordinator (BRD-09).

Builds a ``StopContext`` once per evaluation, then walks the registered
signals in priority order (lowest number = highest priority). The
first signal returning ``STOP`` wins; the first signal returning
``CONTINUE`` (when no later signal stops) wins; ``DEFER`` lets
lower-priority signals decide.

No module-level singleton (IP-09 O-08). Each ``AgentOrchestrator``
constructs its own policy; tests inject custom signal sets via the
``signals`` kwarg.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.confidence import calculate_structural_confidence
from app.seams.stopping import (
    SignalResult,
    StopContext,
    StoppingSignal,
    StopSignalOutput,
)
from app.stopping.signals import (
    AgreementSignal,
    BudgetSignal,
    CoverageSignal,
    HonestStopSignal,
    JudgeSignal,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.agent.run_state import RunState

logger = structlog.get_logger(__name__)


def _default_signals() -> tuple[StoppingSignal, ...]:
    return (
        HonestStopSignal(),
        BudgetSignal(),
        CoverageSignal(),
        AgreementSignal(),
        JudgeSignal(),
    )


class StoppingPolicy:
    """Coordinates layered stopping signals (E + F + A + D + B)."""

    def __init__(self, signals: Sequence[StoppingSignal] | None = None) -> None:
        registered = tuple(signals) if signals is not None else _default_signals()
        self._signals: tuple[StoppingSignal, ...] = tuple(
            sorted(registered, key=lambda s: s.priority)
        )

    @property
    def signals(self) -> tuple[StoppingSignal, ...]:
        """Registered signals, sorted by priority (read-only view)."""
        return self._signals

    async def evaluate(
        self,
        state: RunState,
        *,
        judge_confidence: float | None = None,
    ) -> StopSignalOutput:
        """Walk all signals in priority order, return the first decisive result.

        Decision rule:
          - The first signal returning ``STOP`` wins immediately.
          - Otherwise, the first ``CONTINUE`` wins (fall-through).
          - If every signal returns ``DEFER``, the overall result is
            ``CONTINUE`` (keep iterating; the orchestrator's own caps
            still apply).
        """
        structural = calculate_structural_confidence(state)
        context = StopContext(
            coverage=structural.coverage,
            agreement=structural.agreement,
            diversity=structural.diversity,
            no_conflict=structural.no_conflict,
            structural_confidence=structural.score,
            judge_confidence=judge_confidence,
            threshold=state.confidence_threshold,
            search_count=state.search_count,
            max_searches=state.max_searches,
            has_contradictions=len(state.contradictions) > 0,
            has_ambiguity=bool(getattr(state, "has_ambiguity", False)),
            uncoverable_claims=len(state.uncoverable_claims),
            covered_claims=len(state.covered_claims),
            total_claims=len(state.sub_claims),
        )

        first_continue: StopSignalOutput | None = None
        for signal in self._signals:
            result = await signal.evaluate(context)
            logger.debug(
                "stopping_signal_evaluated",
                signal=signal.name,
                result=result.result.value,
                stop_reason=result.stop_reason.value if result.stop_reason else None,
            )
            if result.result is SignalResult.STOP:
                return result
            if result.result is SignalResult.CONTINUE and first_continue is None:
                first_continue = result

        if first_continue is not None:
            return first_continue

        # Every signal deferred — overall behaviour is CONTINUE.
        return StopSignalOutput(
            signal_name="StoppingPolicy",
            result=SignalResult.CONTINUE,
            explanation="All signals deferred; continuing research",
            confidence=context.structural_confidence,
        )

    @staticmethod
    def should_stop(result: StopSignalOutput) -> bool:
        """Convenience: ``True`` iff the policy decided to terminate."""
        return result.result is SignalResult.STOP
