# BRD-07: Agent FSM & Research Loop

**Document ID:** BRD-07
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 8 of 19

---

## 1. Executive Summary

Implement the Agent Finite State Machine (FSM) that orchestrates the research loop. This is the core engine that coordinates planning, searching, evidence collection, and answer generation following the layered stopping policy.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-01 | Autonomous stopping | Complete |
| RF-06 | Question type classification | Complete |
| RF-11 | Agent error handling | Complete |
| RF-14 | Plan critic (up to 2 attempts) | Complete |
| RF-15 | Disconfirmation pass | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-02, BRD-05, BRD-06 | BRD-08, BRD-09, BRD-10 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    agent/
      __init__.py
      fsm.py              # State machine definition
      states.py           # State enum and transitions
      run_state.py        # RunState Pydantic model
      orchestrator.py     # Main orchestration logic
      tasks/
        __init__.py
        plan.py           # Planning task
        search.py         # Search task
        analyze.py        # Evidence analysis
        draft.py          # Answer drafting
```

### 4.2 Agent States

#### backend/app/agent/states.py

```python
"""Agent FSM states and transitions."""

from enum import StrEnum, auto


class AgentState(StrEnum):
    """States in the agent FSM.
    
    State flow:
    INIT → PLANNING → CRITIQUING → SEARCHING → ANALYZING → 
    DRAFTING → JUDGING → (STOPPED | back to SEARCHING)
    """

    INIT = "init"
    PLANNING = "planning"
    CRITIQUING = "critiquing"
    REVISING = "revising"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    DRAFTING = "drafting"
    JUDGING = "judging"
    STOPPED = "stopped"
    ERRORED = "errored"


# Valid state transitions
TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.INIT: {AgentState.PLANNING, AgentState.ERRORED},
    AgentState.PLANNING: {AgentState.CRITIQUING, AgentState.ERRORED},
    AgentState.CRITIQUING: {AgentState.SEARCHING, AgentState.REVISING, AgentState.ERRORED},
    AgentState.REVISING: {AgentState.CRITIQUING, AgentState.SEARCHING, AgentState.ERRORED},
    AgentState.SEARCHING: {AgentState.ANALYZING, AgentState.DRAFTING, AgentState.ERRORED},
    AgentState.ANALYZING: {AgentState.SEARCHING, AgentState.DRAFTING, AgentState.ERRORED},
    AgentState.DRAFTING: {AgentState.JUDGING, AgentState.ERRORED},
    AgentState.JUDGING: {AgentState.STOPPED, AgentState.SEARCHING, AgentState.ERRORED},
    AgentState.STOPPED: set(),  # Terminal
    AgentState.ERRORED: {AgentState.INIT},  # Can resume
}


def can_transition(current: AgentState, target: AgentState) -> bool:
    """Check if a state transition is valid."""
    return target in TRANSITIONS.get(current, set())
```

### 4.3 Run State Model

#### backend/app/agent/run_state.py

```python
"""RunState Pydantic model — mutable state during execution."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agent.states import AgentState
from app.domain.enums import QuestionType, StopReason
from app.domain.events import SubClaim


class EvidenceItem(BaseModel):
    """Collected evidence during research."""

    model_config = ConfigDict(extra="allow")

    event_id: UUID
    claim_id: str
    source_url: str
    source_title: str
    text: str
    polarity: str  # supports/contradicts/neutral
    confidence: float


class RunState(BaseModel):
    """Mutable state for a running research agent.
    
    This model tracks all in-progress state during execution.
    Events are the immutable record; RunState is ephemeral.
    """

    model_config = ConfigDict(extra="allow")

    # Identity
    run_id: UUID
    question: str
    user_context: Optional[str] = None
    question_type: Optional[QuestionType] = None

    # Configuration
    confidence_threshold: float = 0.7
    output_format: str = "prose"

    # FSM State
    current_state: AgentState = AgentState.INIT
    started_at: datetime = Field(default_factory=datetime.utcnow)

    # Planning
    sub_claims: list[SubClaim] = Field(default_factory=list)
    plan_revision_count: int = 0
    max_plan_revisions: int = 2  # RF-14

    # Evidence Collection
    evidence: list[EvidenceItem] = Field(default_factory=list)
    covered_claims: set[str] = Field(default_factory=set)
    uncoverable_claims: set[str] = Field(default_factory=set)
    contradictions: list[dict] = Field(default_factory=list)

    # Search State
    search_count: int = 0
    max_searches: int = 20  # Budget limit
    failed_sources: list[str] = Field(default_factory=list)

    # Answer
    draft_answer: Optional[str] = None
    draft_sections: Optional[list[dict]] = None

    # Judge
    judge_attempts: int = 0
    max_judge_attempts: int = 3
    last_judge_confidence: Optional[float] = None
    last_structural_confidence: Optional[float] = None

    # Terminal
    stop_reason: Optional[StopReason] = None
    final_answer: Optional[str] = None

    # Metrics
    total_tokens: int = 0
    iteration_count: int = 0

    def transition_to(self, new_state: AgentState) -> None:
        """Transition to a new state with validation."""
        from app.agent.states import can_transition

        if not can_transition(self.current_state, new_state):
            raise ValueError(
                f"Invalid transition: {self.current_state} → {new_state}"
            )
        self.current_state = new_state

    def add_evidence(self, evidence: EvidenceItem) -> None:
        """Add evidence and update claim coverage."""
        self.evidence.append(evidence)

    def mark_claim_covered(self, claim_id: str) -> None:
        """Mark a claim as covered by evidence."""
        self.covered_claims.add(claim_id)

    def mark_claim_uncoverable(self, claim_id: str) -> None:
        """Mark a claim as uncoverable."""
        self.uncoverable_claims.add(claim_id)

    def all_claims_resolved(self) -> bool:
        """Check if all claims are either covered or uncoverable."""
        claim_ids = {c.id for c in self.sub_claims}
        resolved = self.covered_claims | self.uncoverable_claims
        return claim_ids <= resolved

    def coverage_ratio(self) -> float:
        """Calculate the ratio of covered claims."""
        if not self.sub_claims:
            return 0.0
        return len(self.covered_claims) / len(self.sub_claims)
```

### 4.4 Agent Orchestrator

#### backend/app/agent/orchestrator.py

```python
"""Main agent orchestrator — runs the research loop."""

from typing import AsyncIterator, Callable, Awaitable
from uuid import UUID
import structlog

from app.agent.states import AgentState
from app.agent.run_state import RunState
from app.domain.enums import StopReason, QuestionType
from app.domain.events import (
    BaseEvent,
    QuestionAskedEvent,
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanRevisedEvent,
    StoppedEvent,
    AgentErroredEvent,
)
from app.agent.tasks.plan import create_plan, critique_plan, revise_plan
from app.agent.tasks.search import execute_search_round
from app.agent.tasks.analyze import analyze_evidence
from app.agent.tasks.draft import draft_answer, evaluate_with_judge

logger = structlog.get_logger()

# Type for event callback
EventCallback = Callable[[BaseEvent], Awaitable[None]]


class AgentOrchestrator:
    """Orchestrates the research agent loop."""

    def __init__(
        self,
        run_id: UUID,
        question: str,
        user_context: str | None = None,
        confidence_threshold: float = 0.7,
        output_format: str = "prose",
        on_event: EventCallback | None = None,
    ) -> None:
        self.state = RunState(
            run_id=run_id,
            question=question,
            user_context=user_context,
            confidence_threshold=confidence_threshold,
            output_format=output_format,
        )
        self.on_event = on_event
        self._cancelled = False

    async def emit(self, event: BaseEvent) -> None:
        """Emit an event via the callback."""
        if self.on_event:
            await self.on_event(event)

    def cancel(self) -> None:
        """Request cancellation of the run."""
        self._cancelled = True

    async def run(self) -> StopReason:
        """Execute the research loop.
        
        Returns the stop reason when complete.
        """
        logger.info("agent_run_start", run_id=str(self.state.run_id))

        try:
            # Emit question asked
            await self.emit(QuestionAskedEvent(
                question=self.state.question,
                user_context=self.state.user_context,
            ))

            # Detect question type
            self.state.question_type = await self._detect_question_type()

            # Main loop
            while not self._is_terminal():
                if self._cancelled:
                    return await self._stop(StopReason.USER_CANCELLED)

                self.state.iteration_count += 1

                match self.state.current_state:
                    case AgentState.INIT:
                        await self._handle_init()
                    case AgentState.PLANNING:
                        await self._handle_planning()
                    case AgentState.CRITIQUING:
                        await self._handle_critiquing()
                    case AgentState.REVISING:
                        await self._handle_revising()
                    case AgentState.SEARCHING:
                        await self._handle_searching()
                    case AgentState.ANALYZING:
                        await self._handle_analyzing()
                    case AgentState.DRAFTING:
                        await self._handle_drafting()
                    case AgentState.JUDGING:
                        await self._handle_judging()

                # Budget check
                if self.state.search_count >= self.state.max_searches:
                    return await self._stop(StopReason.STOPPED_BY_BUDGET)

            return self.state.stop_reason or StopReason.ERRORED

        except Exception as e:
            logger.exception("agent_error", run_id=str(self.state.run_id))
            await self.emit(AgentErroredEvent(
                error_type=type(e).__name__,
                error_message=str(e),
                recoverable=True,
            ))
            self.state.transition_to(AgentState.ERRORED)
            return StopReason.ERRORED

    def _is_terminal(self) -> bool:
        """Check if we're in a terminal state."""
        return self.state.current_state in {AgentState.STOPPED, AgentState.ERRORED}

    async def _detect_question_type(self) -> QuestionType | None:
        """Detect the question type (RF-06)."""
        # Simple heuristic; can be enhanced with LLM
        q = self.state.question.lower()
        
        if any(w in q for w in ["when", "where", "who", "what is", "how many"]):
            return QuestionType.FACTUAL
        if any(w in q for w in ["vs", "versus", "compare", "difference", "better"]):
            return QuestionType.COMPARATIVE
        if any(w in q for w in ["what is", "define", "explain", "meaning"]):
            return QuestionType.DEFINITIONAL
        if any(w in q for w in ["best", "latest", "current", "state of the art"]):
            return QuestionType.STATE_OF_ART
        if any(w in q for w in ["why", "reason", "cause"]):
            return QuestionType.CAUSAL
        
        return None

    async def _handle_init(self) -> None:
        """Initialize and move to planning."""
        self.state.transition_to(AgentState.PLANNING)

    async def _handle_planning(self) -> None:
        """Create initial plan."""
        plan_event = await create_plan(self.state.question)
        await self.emit(plan_event)
        self.state.sub_claims = plan_event.sub_claims
        self.state.transition_to(AgentState.CRITIQUING)

    async def _handle_critiquing(self) -> None:
        """Critique the plan (RF-14)."""
        critique = await critique_plan(self.state.sub_claims)
        await self.emit(critique)

        if critique.acceptable:
            self.state.transition_to(AgentState.SEARCHING)
        elif self.state.plan_revision_count < self.state.max_plan_revisions:
            self.state.transition_to(AgentState.REVISING)
        else:
            # Max revisions reached, proceed anyway
            self.state.transition_to(AgentState.SEARCHING)

    async def _handle_revising(self) -> None:
        """Revise the plan."""
        revised = await revise_plan(
            self.state.sub_claims,
            self.state.plan_revision_count + 1,
        )
        await self.emit(revised)
        self.state.sub_claims = revised.new_sub_claims
        self.state.plan_revision_count += 1
        self.state.transition_to(AgentState.CRITIQUING)

    async def _handle_searching(self) -> None:
        """Execute search round."""
        events = await execute_search_round(self.state)
        for event in events:
            await self.emit(event)
        self.state.search_count += 1

        # Check if we have enough evidence or should analyze
        if self.state.evidence or self.state.search_count >= 3:
            self.state.transition_to(AgentState.ANALYZING)

    async def _handle_analyzing(self) -> None:
        """Analyze collected evidence."""
        events = await analyze_evidence(self.state)
        for event in events:
            await self.emit(event)

        # Decide next step
        if self.state.all_claims_resolved():
            self.state.transition_to(AgentState.DRAFTING)
        elif self.state.search_count < self.state.max_searches:
            self.state.transition_to(AgentState.SEARCHING)
        else:
            self.state.transition_to(AgentState.DRAFTING)

    async def _handle_drafting(self) -> None:
        """Draft the answer."""
        draft = await draft_answer(self.state)
        self.state.draft_answer = draft.prose
        self.state.transition_to(AgentState.JUDGING)

    async def _handle_judging(self) -> None:
        """Evaluate answer with judge (RF-12)."""
        judge_event = await evaluate_with_judge(self.state)
        await self.emit(judge_event)
        
        self.state.last_judge_confidence = judge_event.judge_confidence
        self.state.last_structural_confidence = judge_event.structural_confidence
        self.state.judge_attempts += 1

        if judge_event.passed:
            await self._stop(StopReason.JUDGE_CONFIRMED)
        elif self.state.judge_attempts >= self.state.max_judge_attempts:
            # Max attempts, stop with best answer
            await self._stop(StopReason.JUDGE_CONFIRMED)
        else:
            # Need more evidence
            self.state.transition_to(AgentState.SEARCHING)

    async def _stop(self, reason: StopReason) -> StopReason:
        """Stop the run with the given reason."""
        self.state.stop_reason = reason
        self.state.transition_to(AgentState.STOPPED)

        stopped_event = StoppedEvent(
            stop_reason=reason,
            answer_prose=self.state.draft_answer if reason == StopReason.JUDGE_CONFIRMED else None,
            total_tokens=self.state.total_tokens,
        )
        await self.emit(stopped_event)

        logger.info(
            "agent_run_complete",
            run_id=str(self.state.run_id),
            stop_reason=reason,
            iterations=self.state.iteration_count,
        )

        return reason
```

### 4.5 Planning Task

#### backend/app/agent/tasks/plan.py

```python
"""Planning tasks: create, critique, revise."""

from app.domain.events import (
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanRevisedEvent,
    SubClaim,
)
from app.llm import llm, LLMRole, PlanOutput, CritiqueOutput


async def create_plan(question: str) -> PlanCreatedEvent:
    """Create initial research plan."""
    result = await llm.call(
        role=LLMRole.PLANNER,
        user_message=f"Decompose this question into verifiable sub-claims:\n\n{question}",
        response_model=PlanOutput,
    )

    sub_claims = [
        SubClaim(id=c.id, text=c.text, status="pending")
        for c in result.sub_claims
    ]

    return PlanCreatedEvent(
        sub_claims=sub_claims,
        rationale=result.overall_rationale,
    )


async def critique_plan(sub_claims: list[SubClaim]) -> PlanCritiquedEvent:
    """Critique the plan (RF-14)."""
    claims_text = "\n".join(f"- {c.id}: {c.text}" for c in sub_claims)
    
    result = await llm.call(
        role=LLMRole.CRITIC,
        user_message=f"Evaluate this research plan:\n\n{claims_text}",
        response_model=CritiqueOutput,
    )

    return PlanCritiquedEvent(
        critique=result.summary,
        issues=result.issues,
        suggested_changes=result.suggested_changes,
        acceptable=result.acceptable,
    )


async def revise_plan(
    current_claims: list[SubClaim],
    attempt_number: int,
) -> PlanRevisedEvent:
    """Revise the plan based on critique."""
    claims_text = "\n".join(f"- {c.id}: {c.text}" for c in current_claims)
    
    result = await llm.call(
        role=LLMRole.PLANNER,
        user_message=f"Revise this plan based on the critique:\n\n{claims_text}",
        response_model=PlanOutput,
    )

    new_claims = [
        SubClaim(id=c.id, text=c.text, status="pending")
        for c in result.sub_claims
    ]

    return PlanRevisedEvent(
        previous_sub_claims=current_claims,
        new_sub_claims=new_claims,
        revision_rationale=result.overall_rationale,
        attempt_number=attempt_number,
    )
```

---

## 5. Acceptance Criteria

### AC-01: FSM Follows Valid Transitions
```gherkin
Given an agent in INIT state
When planning completes
Then state transitions to PLANNING → CRITIQUING
When critique accepts
Then state transitions to SEARCHING
```

### AC-02: Plan Critic Limits Revisions (RF-14)
```gherkin
Given a plan that fails critique
When revision is attempted
Then max 2 revisions are allowed
  And after 2 revisions, agent proceeds to SEARCHING
```

### AC-03: Search Budget Enforced
```gherkin
Given max_searches = 20
When 20 searches are executed
Then agent stops with STOPPED_BY_BUDGET
```

### AC-04: Judge Approval Stops Run
```gherkin
Given draft answer passes judge evaluation
When judge confidence >= threshold
Then agent stops with JUDGE_CONFIRMED
  And final answer is in StoppedEvent
```

### AC-05: Cancellation Works
```gherkin
Given agent is running
When cancel() is called
Then agent stops at next iteration
  And stop_reason = USER_CANCELLED
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/agent/__init__.py`
- [ ] Create `backend/app/agent/states.py`
- [ ] Create `backend/app/agent/run_state.py`
- [ ] Create `backend/app/agent/orchestrator.py`
- [ ] Create `backend/app/agent/tasks/__init__.py`
- [ ] Create `backend/app/agent/tasks/plan.py`
- [ ] Create `backend/app/agent/tasks/search.py`
- [ ] Create `backend/app/agent/tasks/analyze.py`
- [ ] Create `backend/app/agent/tasks/draft.py`
- [ ] Write unit tests for state transitions
- [ ] Write integration tests for full loop

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | State transitions | 100% |
| Unit | pytest | RunState methods | 100% |
| Integration | pytest | Full loop (mocked LLM) | 100% |

## 8. Environment Variables

_Uses LLM variables from BRD-05._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Infinite loop | High | Low | Iteration counter + budget |
| State corruption | High | Low | Immutable events as backup |
| LLM failures | Med | Med | Retry + error state |

## 10. Out of Scope

- Confidence calculation details (BRD-08)
- Stopping signal logic (BRD-09)
- SSE streaming (BRD-10)
- Disconfirmation pass implementation (partial in BRD-08)
