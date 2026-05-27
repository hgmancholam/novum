"""Budget signal — research-round budget safety net (RF-01).

This signal exclusively guards the **search-round** budget
(``search_count`` / ``max_searches``). It does NOT subsume the
judge-attempts sub-loop counter (IP-09 O-07); that cap is enforced
inline in ``AgentOrchestrator._handle_judging``.
"""

from __future__ import annotations

from app.domain.enums import StopReason
from app.seams.stopping import SignalResult, StopContext, StopSignalOutput


class BudgetSignal:
    """Layer F — search-round budget safety net."""

    name: str = "Budget"
    priority: int = 20

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        if context.search_count >= context.max_searches:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.STOPPED_BY_BUDGET,
                explanation=(
                    f"Search budget exhausted: "
                    f"{context.search_count}/{context.max_searches} rounds"
                ),
                confidence=context.structural_confidence,
            )
        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation=(
                f"Search budget remaining: "
                f"{context.search_count}/{context.max_searches} rounds"
            ),
            confidence=context.structural_confidence,
        )
