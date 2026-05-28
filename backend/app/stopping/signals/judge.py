"""Judge signal — confirms a run when all gates pass (RF-12, RF-15).

Gates (in order, IP-09 O-04; C2 unified-threshold model):
  1. ``judge_confidence`` is available (we are in or after JUDGING).
  2. ``judge_passed`` is True (i.e. judge verdict was approve).
  3. ``coverage >= 0.8`` — enough sub-claims covered.
  4. ``agreement >= 0.7`` — evidence broadly aligns.

The run's ``confidence_threshold`` is no longer re-applied here as a
``min(S, J) >= threshold`` gate. It is passed into the judge prompt so
the judge LLM applies it itself when deciding approve vs reject; this
removes the double-gate that caused stuck runs (commit 9a961fc context).
``final = min(S, J)`` is still computed and surfaced in the explanation
for observability (RF-12 stays the displayed confidence formula).
"""

from __future__ import annotations

from app.domain.enums import StopReason
from app.seams.stopping import SignalResult, StopContext, StopSignalOutput

_COVERAGE_GATE: float = 0.8
_AGREEMENT_GATE: float = 0.7


class JudgeSignal:
    """Layer B — judge confirmation gate (lowest priority)."""

    name: str = "Judge"
    priority: int = 40

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        if context.judge_confidence is None:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.CONTINUE,
                explanation="Judge has not evaluated yet",
                confidence=context.structural_confidence,
            )

        if context.judge_passed is False:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.CONTINUE,
                explanation="Judge verdict was reject; never silently confirm",
                confidence=context.structural_confidence,
            )

        if context.coverage < _COVERAGE_GATE:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.CONTINUE,
                explanation=(
                    f"Coverage gate failed: {context.coverage:.0%} < 80%"
                ),
                confidence=context.structural_confidence,
            )

        if context.agreement < _AGREEMENT_GATE:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.CONTINUE,
                explanation=(
                    f"Agreement gate failed: {context.agreement:.0%} < 70%"
                ),
                confidence=context.structural_confidence,
            )

        # C2: threshold is enforced by the judge LLM itself (see judge
        # prompt). Once judge_passed is True and coverage/agreement gates
        # pass we STOP. final=min(S,J) is logged for RF-12 observability.
        final = min(context.structural_confidence, context.judge_confidence)
        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.STOP,
            stop_reason=StopReason.JUDGE_CONFIRMED,
            explanation=(
                f"All gates passed; final=min(S={context.structural_confidence:.2f}, "
                f"J={context.judge_confidence:.2f})={final:.2f} "
                f"(threshold {context.threshold:.2f} applied by judge LLM)"
            ),
            confidence=final,
        )
