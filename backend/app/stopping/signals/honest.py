"""Honest stop signal — RF-04 (contradiction / ambiguity / unanswerable).

Priority 10 (highest). Fires before Budget so an honest stop trumps a
budget-exhausted partial answer (contradictions / ambiguity invalidate
prior coverage). The unanswerable branch uses the **all-claims-failed**
condition (IP-09 O-06): all sub-claims must be resolved AND zero of
them must be covered. Half-uncoverable runs still draft a partial
answer.
"""

from __future__ import annotations

from app.domain.enums import StopReason
from app.seams.stopping import SignalResult, StopContext, StopSignalOutput

# When evidence is broadly clean of contradictions, a single contradiction
# does not justify an honest stop yet — keep searching for resolution.
_NO_CONFLICT_OVERRIDE: float = 0.3


class HonestStopSignal:
    """Layer E — honest-stop detector."""

    name: str = "HonestStop"
    priority: int = 10

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        if context.has_contradictions and context.no_conflict < _NO_CONFLICT_OVERRIDE:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.HONEST_CONTRADICTION,
                explanation=(
                    f"Unresolved contradictions detected "
                    f"(no_conflict={context.no_conflict:.2f} < {_NO_CONFLICT_OVERRIDE})"
                ),
                confidence=context.structural_confidence,
            )

        if context.has_ambiguity:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.HONEST_AMBIGUOUS,
                explanation="Question marked as ambiguous; no single answer is defensible",
                confidence=context.structural_confidence,
            )

        all_resolved = (
            context.total_claims > 0
            and (context.covered_claims + context.uncoverable_claims)
            == context.total_claims
        )
        if all_resolved and context.covered_claims == 0:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.HONEST_UNANSWERABLE,
                explanation=(
                    f"All {context.total_claims} claims uncoverable; "
                    "no evidence supports an answer"
                ),
                confidence=context.structural_confidence,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation="No honest-stop condition triggered",
            confidence=context.structural_confidence,
        )
