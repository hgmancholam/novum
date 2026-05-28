"""Intra-loop stopping signals for ReAct (IP-25 Phase E T-25-E-06).

Four signals that evaluate during ReAct loop execution to decide
whether to terminate early based on hypothesis verdicts, coverage,
and contradictions.
"""

from __future__ import annotations

from app.agent.run_state import RunState
from app.domain.enums import StopReason
from app.seams.stopping import SignalResult, StopContext, StopSignalOutput


class HypothesisConfirmedSignal:
    """Fires when ≥1 hypothesis confirmed AND structural confidence ≥ 0.75."""

    name: str = "HypothesisConfirmed"
    priority: int = 5  # High priority — positive terminal

    def __init__(self, state: RunState | None = None):
        """Initialize with optional state reference."""
        self._state = state

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check if any hypothesis is confirmed with sufficient confidence."""
        # Access state via instance variable
        state = self._state
        if state is None:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation="No state available",
            )

        confirmed_count = sum(
            1 for h in state.hypotheses if h.verdict == "confirmed"
        )

        if confirmed_count >= 1 and (state.last_structural_confidence or 0.0) >= 0.75:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.JUDGE_CONFIRMED,
                explanation=(
                    f"{confirmed_count} hypothesis(es) confirmed with S={state.last_structural_confidence or 0.0:.2f}"
                ),
                confidence=state.last_structural_confidence or 0.0,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation=(
                f"Confirmed: {confirmed_count}, S={state.last_structural_confidence or 0.0:.2f}"
            ),
        )


class AllHypothesesRefutedSignal:
    """Fires when all hypotheses are refuted → best effort answer."""

    name: str = "AllHypothesesRefuted"
    priority: int = 15  # Medium-low priority

    def __init__(self, state: RunState | None = None):
        """Initialize with optional state reference."""
        self._state = state

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check if all hypotheses have been refuted."""
        state = self._state
        if state is None:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation="No state available",
            )

        if not state.hypotheses:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation="No hypotheses to evaluate",
            )

        total = len(state.hypotheses)
        refuted_count = sum(1 for h in state.hypotheses if h.verdict == "refuted")

        if refuted_count == total:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.STOPPED_BY_BUDGET,
                explanation=f"All {total} hypotheses refuted — best effort synthesis",
                confidence=context.structural_confidence,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation=f"Refuted: {refuted_count}/{total}",
        )


class ReactStepCapSignal:
    """Fires when react_step_count >= max_react_steps."""

    name: str = "ReactStepCap"
    priority: int = 20  # Low priority — budget safety net

    def __init__(self, state: RunState | None = None):
        """Initialize with optional state reference."""
        self._state = state

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check if ReAct loop has reached max steps."""
        state = self._state
        if state is None:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation="No state available",
            )

        if state.react_step_count >= state.max_react_steps:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.STOPPED_BY_BUDGET,
                explanation=(
                    f"ReAct step budget exhausted: "
                    f"{state.react_step_count}/{state.max_react_steps}"
                ),
                confidence=context.structural_confidence,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation=(
                f"Steps remaining: "
                f"{state.react_step_count}/{state.max_react_steps}"
            ),
        )


class ReactContradictionSignal:
    """Fires when ≥2 confirmed hypotheses with disjoint primary_authoritative evidence."""

    name: str = "ReactContradiction"
    priority: int = 10  # Medium priority

    def __init__(self, state: RunState | None = None):
        """Initialize with optional state reference."""
        self._state = state

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check for contradictory confirmed hypotheses."""
        state = self._state
        if state is None:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation="No state available",
            )

        confirmed_hypotheses = [
            h for h in state.hypotheses if h.verdict == "confirmed"
        ]

        if len(confirmed_hypotheses) < 2:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation=f"Only {len(confirmed_hypotheses)} confirmed hypothesis",
            )

        # Check if evidence sets are disjoint (simplified heuristic)
        # In a full implementation, would check authority_tier and evidence overlap
        evidence_sets = [set(h.evidence_ids) for h in confirmed_hypotheses]

        # If any pair has disjoint evidence, flag contradiction
        for i in range(len(evidence_sets)):
            for j in range(i + 1, len(evidence_sets)):
                if evidence_sets[i].isdisjoint(evidence_sets[j]):
                    return StopSignalOutput(
                        signal_name=self.name,
                        result=SignalResult.STOP,
                        stop_reason=StopReason.STOPPED_BY_BUDGET,
                        explanation=(
                            f"Contradictory hypotheses detected: "
                            f"{len(confirmed_hypotheses)} confirmed with disjoint evidence"
                        ),
                        confidence=context.structural_confidence,
                    )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation=f"{len(confirmed_hypotheses)} confirmed with overlapping evidence",
        )


async def evaluate_react_intra_loop(state: RunState) -> StopSignalOutput | None:
    """Aggregate helper to evaluate all ReAct intra-loop signals.

    Args:
        state: Current run state

    Returns:
        StopSignalOutput if any signal fires STOP, None otherwise

    Priority order:
        1. HypothesisConfirmedSignal (5)
        2. ReactContradictionSignal (10)
        3. AllHypothesesRefutedSignal (15)
        4. ReactStepCapSignal (20)
    """
    # Build minimal StopContext
    context = StopContext(
        search_count=state.search_count,
        max_searches=state.max_searches,
        structural_confidence=state.last_structural_confidence or 0.0,
        judge_confidence=state.last_judge_confidence,
        coverage=state.coverage_ratio(),
        agreement=state.last_agreement or 0.0,
        diversity=0.0,  # Not used in ReAct signals
        no_conflict=1.0 if not state.contradictions else 0.0,
        threshold=state.confidence_threshold,
        has_contradictions=bool(state.contradictions),
        has_ambiguity=state.has_ambiguity,
        uncoverable_claims=0,  # Not used in ReAct signals
        covered_claims=len(state.evidence),  # Approximate
        total_claims=len(state.hypotheses),  # Approximate
        judge_passed=None,
    )

    # Create signals with state reference
    signals = [
        HypothesisConfirmedSignal(state),
        ReactContradictionSignal(state),
        AllHypothesesRefutedSignal(state),
        ReactStepCapSignal(state),
    ]

    # Evaluate in priority order
    for signal in sorted(signals, key=lambda s: s.priority):
        result = await signal.evaluate(context)
        if result.result == SignalResult.STOP:
            return result

    return None
