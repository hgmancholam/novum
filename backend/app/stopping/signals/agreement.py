"""Agreement signal — defers when evidence agreement meets the gate.

Returns ``DEFER`` when ``agreement >= 0.7`` (BRD-09 §4.4). Otherwise
``CONTINUE``. Never emits ``STOP``.
"""

from __future__ import annotations

from app.seams.stopping import SignalResult, StopContext, StopSignalOutput

_AGREEMENT_GATE: float = 0.7


class AgreementSignal:
    """Layer D — agreement gate."""

    name: str = "Agreement"
    priority: int = 35

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        if context.agreement >= _AGREEMENT_GATE:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation=f"Agreement gate met: {context.agreement:.0%} >= 70%",
                confidence=context.structural_confidence,
            )
        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.CONTINUE,
            explanation=f"Agreement gate not met: {context.agreement:.0%} < 70%",
            confidence=context.structural_confidence,
        )
