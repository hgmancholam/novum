"""Judge signal — confirms a run when all three gates pass (RF-12, RF-15).

Gates (in order, IP-09 O-04):
  1. ``judge_confidence`` is available (we are in or after JUDGING).
  2. ``coverage >= 0.8`` — enough sub-claims covered.
  3. ``agreement >= 0.7`` — evidence broadly aligns.
  4. ``min(structural, judge) >= threshold`` — final-confidence rule
     (RF-12: ``final_confidence = min(S, J)``).

Only when all four hold does the signal emit ``STOP{JUDGE_CONFIRMED}``.
Otherwise it returns ``CONTINUE`` (the policy will fall through to
``CONTINUE`` and the orchestrator will iterate again, unless an
earlier-priority signal stopped it).
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

        final = min(context.structural_confidence, context.judge_confidence)
        if final >= context.threshold:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.JUDGE_CONFIRMED,
                explanation=(
                    f"All gates passed; final=min(S={context.structural_confidence:.2f}, "
                    f"J={context.judge_confidence:.2f})={final:.2f} >= "
                    f"threshold={context.threshold:.2f}"
                ),
                confidence=final,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.CONTINUE,
            explanation=(
                f"Final confidence {final:.2f} below threshold {context.threshold:.2f}"
            ),
            confidence=final,
        )
