# BRD-09: Stopping Signal Policy

**Document ID:** BRD-09
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 10 of 19

---

## 1. Executive Summary

Implement the StoppingSignal plugin seam with the layered stopping policy (A+D+B+E+F) from the stopping signal analysis. This BRD defines when the agent stops autonomously and which stop_reason enum value to use.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-01 | Autonomous stopping, 7 stop_reason values | Complete |
| RF-04 | Honest stops (ambiguity, contradiction) | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-02, BRD-07, BRD-08 | BRD-10 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    seams/
      stopping.py          # StoppingSignal protocol
    stopping/
      __init__.py
      policy.py            # Layered policy coordinator
      signals/
        __init__.py
        coverage.py        # Signal A: Coverage
        agreement.py       # Signal D: Agreement
        judge.py           # Signal B: Judge
        honest.py          # Signal E: Honest stops
        budget.py          # Signal F: Budget
```

### 4.2 Stopping Policy Layers

| Layer | Signal | When Fires | stop_reason |
|-------|--------|------------|-------------|
| A | Coverage | All claims covered | (proceed to B) |
| D | Agreement | Evidence agrees | (proceed to B) |
| B | Judge | Confidence ≥ threshold | `judge_confirmed` |
| E | Honest | Detected issue | `honest_*` |
| F | Budget | Max iterations | `stopped_by_budget` |

### 4.3 StoppingSignal Protocol

#### backend/app/seams/stopping.py

```python
"""StoppingSignal plugin seam — one of three extensibility points.

Signals determine when the agent should stop.
V1: Coverage, Agreement, Judge, Honest, Budget
V2: DomainSafety, ConfidencePlateau
"""

from abc import abstractmethod
from enum import StrEnum
from typing import Protocol, runtime_checkable, Optional

from app.domain.enums import StopReason


class SignalResult(StrEnum):
    """Result of evaluating a stopping signal."""

    CONTINUE = "continue"      # Keep going
    STOP = "stop"              # Stop with reason
    DEFER = "defer"            # Let next signal decide


class StopSignalOutput:
    """Output from a stopping signal evaluation."""

    def __init__(
        self,
        signal_name: str,
        result: SignalResult,
        stop_reason: Optional[StopReason] = None,
        explanation: Optional[str] = None,
        confidence: float = 0.0,
    ) -> None:
        self.signal_name = signal_name
        self.result = result
        self.stop_reason = stop_reason
        self.explanation = explanation
        self.confidence = confidence


@runtime_checkable
class StoppingSignal(Protocol):
    """Protocol for stopping signal plugins."""

    @property
    def name(self) -> str:
        """Human-readable signal name."""
        ...

    @property
    def priority(self) -> int:
        """Priority order (lower = earlier). E > F > A > D > B."""
        ...

    async def evaluate(self, context: "StopContext") -> StopSignalOutput:
        """Evaluate whether to stop.
        
        Args:
            context: Current run context
            
        Returns:
            StopSignalOutput with result and optional stop_reason
        """
        ...


class StopContext:
    """Context passed to stopping signals."""

    def __init__(
        self,
        coverage: float,
        agreement: float,
        diversity: float,
        no_conflict: float,
        structural_confidence: float,
        judge_confidence: Optional[float],
        threshold: float,
        iteration_count: int,
        max_iterations: int,
        has_contradictions: bool,
        has_ambiguity: bool,
        uncoverable_claims: int,
        total_claims: int,
    ) -> None:
        self.coverage = coverage
        self.agreement = agreement
        self.diversity = diversity
        self.no_conflict = no_conflict
        self.structural_confidence = structural_confidence
        self.judge_confidence = judge_confidence
        self.threshold = threshold
        self.iteration_count = iteration_count
        self.max_iterations = max_iterations
        self.has_contradictions = has_contradictions
        self.has_ambiguity = has_ambiguity
        self.uncoverable_claims = uncoverable_claims
        self.total_claims = total_claims
```

### 4.4 Signal Implementations

#### backend/app/stopping/signals/coverage.py

```python
"""Signal A: Coverage — all claims covered."""

from app.seams.stopping import (
    StoppingSignal,
    StopContext,
    StopSignalOutput,
    SignalResult,
)


class CoverageSignal:
    """Signal A: Check if all claims are covered."""

    @property
    def name(self) -> str:
        return "Coverage"

    @property
    def priority(self) -> int:
        return 30  # After Honest, before Judge

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check coverage threshold."""
        # Require at least 80% coverage to proceed
        if context.coverage >= 0.8:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation=f"Coverage sufficient: {context.coverage:.0%}",
                confidence=context.coverage,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.CONTINUE,
            explanation=f"Coverage insufficient: {context.coverage:.0%}",
            confidence=context.coverage,
        )
```

#### backend/app/stopping/signals/agreement.py

```python
"""Signal D: Agreement — evidence supports claims."""

from app.seams.stopping import (
    StoppingSignal,
    StopContext,
    StopSignalOutput,
    SignalResult,
)


class AgreementSignal:
    """Signal D: Check evidence agreement."""

    @property
    def name(self) -> str:
        return "Agreement"

    @property
    def priority(self) -> int:
        return 35  # After Coverage, before Judge

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check agreement threshold."""
        if context.agreement >= 0.7:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.DEFER,
                explanation=f"Agreement sufficient: {context.agreement:.0%}",
                confidence=context.agreement,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.CONTINUE,
            explanation=f"Agreement insufficient: {context.agreement:.0%}",
            confidence=context.agreement,
        )
```

#### backend/app/stopping/signals/judge.py

```python
"""Signal B: Judge — LLM evaluation passes threshold."""

from app.domain.enums import StopReason
from app.seams.stopping import (
    StoppingSignal,
    StopContext,
    StopSignalOutput,
    SignalResult,
)


class JudgeSignal:
    """Signal B: Judge approval."""

    @property
    def name(self) -> str:
        return "Judge"

    @property
    def priority(self) -> int:
        return 40  # After Coverage and Agreement

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check judge confidence against threshold."""
        if context.judge_confidence is None:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.CONTINUE,
                explanation="Judge not yet evaluated",
            )

        final = min(context.structural_confidence, context.judge_confidence)

        if final >= context.threshold:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.JUDGE_CONFIRMED,
                explanation=f"Final confidence {final:.0%} >= threshold {context.threshold:.0%}",
                confidence=final,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.CONTINUE,
            explanation=f"Final confidence {final:.0%} < threshold {context.threshold:.0%}",
            confidence=final,
        )
```

#### backend/app/stopping/signals/honest.py

```python
"""Signal E: Honest stops — detected issues that require honest admission."""

from app.domain.enums import StopReason
from app.seams.stopping import (
    StoppingSignal,
    StopContext,
    StopSignalOutput,
    SignalResult,
)


class HonestStopSignal:
    """Signal E: Honest stops for detected issues."""

    @property
    def name(self) -> str:
        return "HonestStop"

    @property
    def priority(self) -> int:
        return 10  # Highest priority (fires first)

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check for conditions requiring honest stop."""
        
        # Check for irreconcilable contradictions
        if context.has_contradictions and context.no_conflict < 0.3:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.HONEST_CONTRADICTION,
                explanation="Irreconcilable source conflicts detected",
                confidence=0.0,
            )

        # Check for ambiguity
        if context.has_ambiguity:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.HONEST_AMBIGUOUS,
                explanation="Question ambiguity requires clarification",
                confidence=0.0,
            )

        # Check for unanswerable (all claims uncoverable)
        if (
            context.uncoverable_claims > 0
            and context.uncoverable_claims >= context.total_claims * 0.5
        ):
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.HONEST_UNANSWERABLE,
                explanation="Insufficient evidence available",
                confidence=0.0,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation="No honest stop conditions detected",
        )
```

#### backend/app/stopping/signals/budget.py

```python
"""Signal F: Budget — safety net for max iterations."""

from app.domain.enums import StopReason
from app.seams.stopping import (
    StoppingSignal,
    StopContext,
    StopSignalOutput,
    SignalResult,
)


class BudgetSignal:
    """Signal F: Budget safety net."""

    @property
    def name(self) -> str:
        return "Budget"

    @property
    def priority(self) -> int:
        return 20  # After Honest, before Coverage

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        """Check if budget is exhausted."""
        if context.iteration_count >= context.max_iterations:
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.STOPPED_BY_BUDGET,
                explanation=f"Max iterations ({context.max_iterations}) reached",
                confidence=context.structural_confidence,
            )

        return StopSignalOutput(
            signal_name=self.name,
            result=SignalResult.DEFER,
            explanation=f"Budget: {context.iteration_count}/{context.max_iterations}",
        )
```

### 4.5 Policy Coordinator

#### backend/app/stopping/policy.py

```python
"""Layered stopping policy coordinator."""

from typing import Optional
import structlog

from app.agent.run_state import RunState
from app.confidence import calculate_structural_confidence
from app.domain.enums import StopReason
from app.seams.stopping import StopContext, StopSignalOutput, SignalResult
from app.stopping.signals.coverage import CoverageSignal
from app.stopping.signals.agreement import AgreementSignal
from app.stopping.signals.judge import JudgeSignal
from app.stopping.signals.honest import HonestStopSignal
from app.stopping.signals.budget import BudgetSignal

logger = structlog.get_logger()


class StoppingPolicy:
    """Coordinates layered stopping signals (A+D+B+E+F)."""

    def __init__(self) -> None:
        # Signals in priority order
        self.signals = sorted(
            [
                HonestStopSignal(),   # E: Priority 10
                BudgetSignal(),       # F: Priority 20
                CoverageSignal(),     # A: Priority 30
                AgreementSignal(),    # D: Priority 35
                JudgeSignal(),        # B: Priority 40
            ],
            key=lambda s: s.priority,
        )

    async def evaluate(
        self,
        state: RunState,
        judge_confidence: Optional[float] = None,
    ) -> StopSignalOutput:
        """Evaluate all signals in priority order.
        
        Returns first STOP result, or last DEFER/CONTINUE.
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
            iteration_count=state.iteration_count,
            max_iterations=state.max_searches,
            has_contradictions=len(state.contradictions) > 0,
            has_ambiguity=False,  # Set by agent when detected
            uncoverable_claims=len(state.uncoverable_claims),
            total_claims=len(state.sub_claims),
        )

        last_result: Optional[StopSignalOutput] = None

        for signal in self.signals:
            result = await signal.evaluate(context)
            logger.debug(
                "stopping_signal_evaluated",
                signal=signal.name,
                result=result.result,
                stop_reason=result.stop_reason,
            )

            if result.result == SignalResult.STOP:
                return result

            last_result = result

        # No stop signal, continue
        return last_result or StopSignalOutput(
            signal_name="policy",
            result=SignalResult.CONTINUE,
            explanation="All signals deferred",
        )

    def should_stop(self, result: StopSignalOutput) -> bool:
        """Check if result indicates stopping."""
        return result.result == SignalResult.STOP


# Singleton
stopping_policy = StoppingPolicy()
```

---

## 5. Acceptance Criteria

### AC-01: Honest Stops Fire First
```gherkin
Given contradictions detected and no_conflict < 0.3
When I evaluate stopping policy
Then result.stop_reason = HONEST_CONTRADICTION
  And this fires before budget check
```

### AC-02: Budget Safety Net Works
```gherkin
Given iteration_count = 20 and max_iterations = 20
When I evaluate stopping policy
Then result.stop_reason = STOPPED_BY_BUDGET
```

### AC-03: Judge Confirmation Requires Coverage+Agreement
```gherkin
Given coverage >= 0.8 and agreement >= 0.7
  And judge_confidence >= threshold
When I evaluate stopping policy
Then result.stop_reason = JUDGE_CONFIRMED
```

### AC-04: Continue When Insufficient
```gherkin
Given coverage = 0.5 and no honest/budget triggers
When I evaluate stopping policy
Then result.result = CONTINUE
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/seams/stopping.py`
- [ ] Create `backend/app/stopping/__init__.py`
- [ ] Create `backend/app/stopping/signals/__init__.py`
- [ ] Create `backend/app/stopping/signals/coverage.py`
- [ ] Create `backend/app/stopping/signals/agreement.py`
- [ ] Create `backend/app/stopping/signals/judge.py`
- [ ] Create `backend/app/stopping/signals/honest.py`
- [ ] Create `backend/app/stopping/signals/budget.py`
- [ ] Create `backend/app/stopping/policy.py`
- [ ] Write unit tests for each signal
- [ ] Write integration test for policy

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | Each signal | 100% |
| Integration | pytest | Full policy | 100% |
| Priority | pytest | Signal ordering | 100% |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Wrong priority order | High | Low | Unit tests verify order |
| Missing honest case | Med | Med | Exhaustive test cases |

## 10. Out of Scope

- DomainSafety signal (V2)
- Adaptive thresholds
- User-customizable policy
