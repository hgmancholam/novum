# BRD-02: Pydantic Domain Models & Event System

**Document ID:** BRD-02
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 3 of 19

---

## 1. Executive Summary

Define all Pydantic v2 domain models including the ~17 event types as discriminated unions. These models enforce the event schema, enable type-safe event handling, and serve as the contract for the TypeScript frontend via `scripts/export_types.py`.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-01 | stop_reason enum (7 values) | Complete |
| RF-03 | Event types for fork points | Complete |
| RF-04 | Ambiguity/Contradiction events | Complete |
| RF-11 | Agent error/recovery events | Complete |
| RF-14 | Plan critic events | Complete |
| RF-15 | Disconfirmation events | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-01 | BRD-03, BRD-07, BRD-08, BRD-10 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    domain/
      __init__.py
      enums.py             # All enum definitions
      events.py            # Event discriminated union
      run.py               # Run state models
      confidence.py        # Confidence calculation models
      source.py            # Source/evidence models
scripts/
  export_types.py          # Pydantic → TypeScript
```

### 4.2 Enum Definitions

#### backend/app/domain/enums.py

```python
"""Domain enums matching database enums."""

from enum import StrEnum


class StopReason(StrEnum):
    """Terminal states for a run (RF-01).
    
    These are guarantees, not errors:
    - 4 honest stops (judge_confirmed, honest_*)
    - 1 budget safety net
    - 1 user action
    - 1 error state
    """

    JUDGE_CONFIRMED = "judge_confirmed"
    HONEST_UNANSWERABLE = "honest_unanswerable"
    HONEST_CONTRADICTION = "honest_contradiction"
    HONEST_AMBIGUOUS = "honest_ambiguous"
    STOPPED_BY_BUDGET = "stopped_by_budget"
    USER_CANCELLED = "user_cancelled"
    ERRORED = "errored"


class QuestionType(StrEnum):
    """Supported question types (RF-06)."""

    FACTUAL = "factual"              # Type 1: Factual/objective
    COMPARATIVE = "comparative"       # Type 2: Comparative
    DEFINITIONAL = "definitional"     # Type 3: Definitional/explanatory
    STATE_OF_ART = "state_of_art"    # Type 4: State-of-the-art
    CAUSAL = "causal"                # Type 5: Causal/"why"


class OutputFormat(StrEnum):
    """Answer format options (RF-10)."""

    PROSE = "prose"
    STRUCTURED = "structured"


class EventType(StrEnum):
    """All event types (~17) for the event log."""

    # Question & Planning
    QUESTION_ASKED = "QuestionAsked"
    PLAN_CREATED = "PlanCreated"
    PLAN_CRITIQUED = "PlanCritiqued"
    PLAN_REVISED = "PlanRevised"

    # Search & Evidence
    TOOL_CALLED = "ToolCalled"
    EVIDENCE_ADDED = "EvidenceAdded"
    CLAIM_COVERED = "ClaimCovered"
    CLAIM_UNCOVERABLE = "ClaimUncoverable"
    SOURCE_FAILED = "SourceFailed"

    # Detection Events
    AMBIGUITY_DETECTED = "AmbiguityDetected"
    CONTRADICTION_DETECTED = "ContradictionDetected"
    CONTRADICTION_RESOLVED = "ContradictionResolved"
    USER_CONTEXT_CHALLENGED = "UserContextChallenged"

    # Judge & Confidence
    JUDGE_RULED = "JudgeRuled"
    CONFIDENCE_MISMATCH = "ConfidenceMismatch"

    # Error & Recovery
    AGENT_ERRORED = "AgentErrored"
    RESUMED_AFTER_ERROR = "ResumedAfterError"
    RESUMED_AFTER_CANCEL = "ResumedAfterCancel"

    # Terminal
    STOPPED = "Stopped"


class EvidencePolarity(StrEnum):
    """Polarity of evidence toward a claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class SourceType(StrEnum):
    """Source plugin identifiers."""

    TAVILY = "tavily"
    WIKIPEDIA = "wikipedia"
```

### 4.3 Event Models

#### backend/app/domain/events.py

```python
"""Event type definitions as Pydantic discriminated union.

All events have:
- type: discriminator field
- model_config with extra="allow" for schema evolution
"""

from datetime import datetime
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    EvidencePolarity,
    EventType,
    QuestionType,
    SourceType,
    StopReason,
)


class BaseEvent(BaseModel):
    """Base class for all events."""

    model_config = ConfigDict(extra="allow")

    id: Optional[UUID] = None
    run_id: Optional[UUID] = None
    step_index: Optional[int] = None
    parent_event_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


# =============================================================================
# Question & Planning Events
# =============================================================================


class QuestionAskedEvent(BaseEvent):
    """Initial question submitted by user."""

    type: Literal[EventType.QUESTION_ASKED] = EventType.QUESTION_ASKED
    question: str
    user_context: Optional[str] = None
    detected_question_type: Optional[QuestionType] = None


class SubClaim(BaseModel):
    """A sub-claim in the research plan."""

    model_config = ConfigDict(extra="allow")

    id: str
    text: str
    status: Literal["pending", "covered", "uncoverable"] = "pending"


class PlanCreatedEvent(BaseEvent):
    """Initial plan with sub-claims decomposition."""

    type: Literal[EventType.PLAN_CREATED] = EventType.PLAN_CREATED
    sub_claims: list[SubClaim]
    rationale: str


class PlanCritiquedEvent(BaseEvent):
    """Plan critic evaluation (RF-14)."""

    type: Literal[EventType.PLAN_CRITIQUED] = EventType.PLAN_CRITIQUED
    critique: str
    issues: list[str]
    suggested_changes: list[str]
    acceptable: bool


class PlanRevisedEvent(BaseEvent):
    """Plan updated after critique."""

    type: Literal[EventType.PLAN_REVISED] = EventType.PLAN_REVISED
    previous_sub_claims: list[SubClaim]
    new_sub_claims: list[SubClaim]
    revision_rationale: str
    attempt_number: int  # 1 or 2 (max 2 per RF-14)


# =============================================================================
# Search & Evidence Events
# =============================================================================


class ToolCalledEvent(BaseEvent):
    """Search tool invocation."""

    type: Literal[EventType.TOOL_CALLED] = EventType.TOOL_CALLED
    source_type: SourceType
    query: str
    query_intent: str  # Why this query was chosen
    target_claim_id: Optional[str] = None


class SourceResult(BaseModel):
    """A single result from a source."""

    model_config = ConfigDict(extra="allow")

    url: str
    title: str
    snippet: str
    relevance_score: Optional[float] = None


class EvidenceAddedEvent(BaseEvent):
    """Evidence collected from a source."""

    type: Literal[EventType.EVIDENCE_ADDED] = EventType.EVIDENCE_ADDED
    source_type: SourceType
    source_url: str
    source_title: str
    extracted_text: str
    polarity: EvidencePolarity
    target_claim_id: str
    confidence: float  # How confident the agent is in this evidence


class ClaimCoveredEvent(BaseEvent):
    """Sub-claim has sufficient evidence."""

    type: Literal[EventType.CLAIM_COVERED] = EventType.CLAIM_COVERED
    claim_id: str
    claim_text: str
    evidence_ids: list[UUID]
    coverage_rationale: str


class ClaimUncoverableEvent(BaseEvent):
    """Sub-claim cannot be answered with available sources."""

    type: Literal[EventType.CLAIM_UNCOVERABLE] = EventType.CLAIM_UNCOVERABLE
    claim_id: str
    claim_text: str
    reason: str
    attempted_sources: list[SourceType]


class SourceFailedEvent(BaseEvent):
    """Source plugin returned an error."""

    type: Literal[EventType.SOURCE_FAILED] = EventType.SOURCE_FAILED
    source_type: SourceType
    query: str
    error_message: str
    recoverable: bool


# =============================================================================
# Detection Events (RF-04)
# =============================================================================


class AmbiguityDetectedEvent(BaseEvent):
    """Question ambiguity detected (RF-04)."""

    type: Literal[EventType.AMBIGUITY_DETECTED] = EventType.AMBIGUITY_DETECTED
    ambiguous_phrase: str
    possible_interpretations: list[str]
    clarification_needed: str


class ContradictionSource(BaseModel):
    """A source involved in a contradiction."""

    model_config = ConfigDict(extra="allow")

    url: str
    title: str
    claim: str


class ContradictionDetectedEvent(BaseEvent):
    """Irreconcilable source conflict (RF-04)."""

    type: Literal[EventType.CONTRADICTION_DETECTED] = EventType.CONTRADICTION_DETECTED
    claim_id: str
    source_a: ContradictionSource
    source_b: ContradictionSource
    nature_of_conflict: str


class ContradictionResolvedEvent(BaseEvent):
    """Contradiction resolved through additional evidence."""

    type: Literal[EventType.CONTRADICTION_RESOLVED] = EventType.CONTRADICTION_RESOLVED
    original_contradiction_id: UUID
    resolution: str
    winning_source: Optional[str] = None
    rationale: str


class UserContextChallengedEvent(BaseEvent):
    """User context contradicts evidence (RF-07)."""

    type: Literal[EventType.USER_CONTEXT_CHALLENGED] = EventType.USER_CONTEXT_CHALLENGED
    user_context_claim: str
    contradicting_evidence: str
    source_url: str


# =============================================================================
# Judge & Confidence Events (RF-12, RF-15)
# =============================================================================


class JudgeRuledEvent(BaseEvent):
    """Judge LLM evaluation (RF-12)."""

    type: Literal[EventType.JUDGE_RULED] = EventType.JUDGE_RULED
    judge_model: str
    judge_confidence: float  # J in min(S, J)
    structural_confidence: float  # S
    final_confidence: float  # min(S, J)
    threshold: float  # User-set threshold
    passed: bool  # final_confidence >= threshold
    rationale: str
    suggested_improvements: Optional[list[str]] = None


class ConfidenceMismatchEvent(BaseEvent):
    """S and J diverge significantly (RF-15)."""

    type: Literal[EventType.CONFIDENCE_MISMATCH] = EventType.CONFIDENCE_MISMATCH
    structural_confidence: float
    judge_confidence: float
    divergence: float  # abs(S - J)
    trust_flag: str  # Warning message for UI


# =============================================================================
# Error & Recovery Events (RF-11)
# =============================================================================


class AgentErroredEvent(BaseEvent):
    """Unrecoverable error during execution."""

    type: Literal[EventType.AGENT_ERRORED] = EventType.AGENT_ERRORED
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    recoverable: bool
    recovery_suggestion: Optional[str] = None


class ResumedAfterErrorEvent(BaseEvent):
    """Run resumed after an error."""

    type: Literal[EventType.RESUMED_AFTER_ERROR] = EventType.RESUMED_AFTER_ERROR
    original_error_event_id: UUID
    resume_point: str


class ResumedAfterCancelEvent(BaseEvent):
    """Run resumed after user cancellation."""

    type: Literal[EventType.RESUMED_AFTER_CANCEL] = EventType.RESUMED_AFTER_CANCEL
    cancel_event_id: UUID
    resume_point: str


# =============================================================================
# Terminal Event
# =============================================================================


class AnswerSection(BaseModel):
    """Section of a structured answer."""

    model_config = ConfigDict(extra="allow")

    heading: str
    content: str


class Citation(BaseModel):
    """Citation reference in the answer."""

    model_config = ConfigDict(extra="allow")

    id: int
    url: str
    title: str


class StoppedEvent(BaseEvent):
    """Terminal event with final answer or honest stop."""

    type: Literal[EventType.STOPPED] = EventType.STOPPED
    stop_reason: StopReason
    
    # Answer (if judge_confirmed)
    answer_prose: Optional[str] = None
    answer_sections: Optional[list[AnswerSection]] = None
    citations: Optional[list[Citation]] = None
    
    # Honest stop details (if honest_*)
    honest_explanation: Optional[str] = None
    
    # Metrics
    total_tokens: Optional[int] = None
    total_duration_seconds: Optional[float] = None


# =============================================================================
# Discriminated Union
# =============================================================================


Event = Annotated[
    Union[
        QuestionAskedEvent,
        PlanCreatedEvent,
        PlanCritiquedEvent,
        PlanRevisedEvent,
        ToolCalledEvent,
        EvidenceAddedEvent,
        ClaimCoveredEvent,
        ClaimUncoverableEvent,
        SourceFailedEvent,
        AmbiguityDetectedEvent,
        ContradictionDetectedEvent,
        ContradictionResolvedEvent,
        UserContextChallengedEvent,
        JudgeRuledEvent,
        ConfidenceMismatchEvent,
        AgentErroredEvent,
        ResumedAfterErrorEvent,
        ResumedAfterCancelEvent,
        StoppedEvent,
    ],
    Field(discriminator="type"),
]

# Mapping for deserialization
EVENT_TYPE_MAP: dict[str, type[BaseEvent]] = {
    EventType.QUESTION_ASKED: QuestionAskedEvent,
    EventType.PLAN_CREATED: PlanCreatedEvent,
    EventType.PLAN_CRITIQUED: PlanCritiquedEvent,
    EventType.PLAN_REVISED: PlanRevisedEvent,
    EventType.TOOL_CALLED: ToolCalledEvent,
    EventType.EVIDENCE_ADDED: EvidenceAddedEvent,
    EventType.CLAIM_COVERED: ClaimCoveredEvent,
    EventType.CLAIM_UNCOVERABLE: ClaimUncoverableEvent,
    EventType.SOURCE_FAILED: SourceFailedEvent,
    EventType.AMBIGUITY_DETECTED: AmbiguityDetectedEvent,
    EventType.CONTRADICTION_DETECTED: ContradictionDetectedEvent,
    EventType.CONTRADICTION_RESOLVED: ContradictionResolvedEvent,
    EventType.USER_CONTEXT_CHALLENGED: UserContextChallengedEvent,
    EventType.JUDGE_RULED: JudgeRuledEvent,
    EventType.CONFIDENCE_MISMATCH: ConfidenceMismatchEvent,
    EventType.AGENT_ERRORED: AgentErroredEvent,
    EventType.RESUMED_AFTER_ERROR: ResumedAfterErrorEvent,
    EventType.RESUMED_AFTER_CANCEL: ResumedAfterCancelEvent,
    EventType.STOPPED: StoppedEvent,
}


# Forkable events (RF-03)
FORKABLE_EVENTS: set[EventType] = {
    EventType.PLAN_CREATED,
    EventType.AMBIGUITY_DETECTED,
    EventType.CONTRADICTION_DETECTED,
    EventType.JUDGE_RULED,
    EventType.STOPPED,
}
```

### 4.4 Run State Models

#### backend/app/domain/run.py

```python
"""Run state and request/response models."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import OutputFormat, QuestionType, StopReason


class RunCreate(BaseModel):
    """Request body for creating a new run."""

    question: str = Field(..., min_length=10, max_length=2000)
    user_context: Optional[str] = Field(None, max_length=1000)  # RF-07
    output_format: OutputFormat = OutputFormat.PROSE
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)  # RF-12


class RunResponse(BaseModel):
    """Response model for a run."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_username: str
    question: str
    user_context: Optional[str]
    question_type: Optional[QuestionType]
    output_format: OutputFormat
    confidence_threshold: float
    started_at: datetime
    stopped_at: Optional[datetime]
    stop_reason: Optional[StopReason]
    parent_run_id: Optional[UUID]
    forked_at_event_id: Optional[UUID]


class RunListItem(BaseModel):
    """Lightweight run for list views (RF-09)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question: str  # Truncated in service layer
    started_at: datetime
    stopped_at: Optional[datetime]
    stop_reason: Optional[StopReason]


class RunForkRequest(BaseModel):
    """Request to fork a run from a specific event (RF-03)."""

    event_id: UUID
```

### 4.5 Confidence Models

#### backend/app/domain/confidence.py

```python
"""Confidence calculation models (RF-12)."""

from pydantic import BaseModel, ConfigDict, Field


class StructuralConfidence(BaseModel):
    """Structural confidence components.
    
    S = 0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.15·C_no_conflict
    """

    model_config = ConfigDict(extra="allow")

    coverage: float = Field(..., ge=0.0, le=1.0, description="C_coverage: % of claims covered")
    agreement: float = Field(..., ge=0.0, le=1.0, description="C_agreement: evidence alignment")
    diversity: float = Field(..., ge=0.0, le=1.0, description="C_diversity: source independence")
    no_conflict: float = Field(..., ge=0.0, le=1.0, description="C_no_conflict: absence of contradictions")

    @property
    def score(self) -> float:
        """Calculate weighted structural score S."""
        return (
            0.35 * self.coverage
            + 0.30 * self.agreement
            + 0.20 * self.diversity
            + 0.15 * self.no_conflict
        )


class ConfidenceResult(BaseModel):
    """Full confidence calculation result."""

    model_config = ConfigDict(extra="allow")

    structural: StructuralConfidence
    judge: float = Field(..., ge=0.0, le=1.0, description="J: Judge confidence")
    final: float = Field(..., ge=0.0, le=1.0, description="min(S, J)")
    threshold: float = Field(..., ge=0.0, le=1.0, description="User-set threshold")
    passed: bool = Field(..., description="final >= threshold")
```

### 4.6 Type Export Script

#### scripts/export_types.py

```python
#!/usr/bin/env python3
"""Export Pydantic models to TypeScript types.

Usage:
    python scripts/export_types.py > frontend/src/types/events.ts
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from pydantic import TypeAdapter

from app.domain.events import (
    Event,
    QuestionAskedEvent,
    PlanCreatedEvent,
    StoppedEvent,
    # ... all event types
)
from app.domain.enums import StopReason, QuestionType, OutputFormat, EventType


def main() -> None:
    """Generate TypeScript types from Pydantic models."""
    
    # Generate JSON Schema
    adapter = TypeAdapter(Event)
    schema = adapter.json_schema(mode="serialization")
    
    print("// Auto-generated from Pydantic models — DO NOT EDIT")
    print(f"// Generated: {__import__('datetime').datetime.now().isoformat()}")
    print()
    
    # Export enums
    print("// Enums")
    for enum_cls in [StopReason, QuestionType, OutputFormat, EventType]:
        print(f"export type {enum_cls.__name__} = {' | '.join(repr(v.value) for v in enum_cls)};")
    print()
    
    # Export JSON schema for runtime validation
    print("// JSON Schema for runtime validation")
    print(f"export const EventSchema = {json.dumps(schema, indent=2)} as const;")
    print()
    
    print("// Event type union (use for type narrowing)")
    print("export type Event = ")
    for i, event_type in enumerate(EventType):
        prefix = "  | " if i > 0 else "    "
        print(f"{prefix}{event_type.value}Event")
    print(";")


if __name__ == "__main__":
    main()
```

---

## 5. Acceptance Criteria

### AC-01: All Events Serialize Correctly
```gherkin
Given a StoppedEvent with all fields populated
When I call event.model_dump_json()
Then valid JSON is produced
  And the "type" field equals "Stopped"
  And all nested models are serialized
```

### AC-02: Discriminated Union Works
```gherkin
Given JSON with type="PlanCreated"
When I parse with TypeAdapter(Event).validate_json(data)
Then a PlanCreatedEvent instance is returned
  And isinstance(result, PlanCreatedEvent) is True
```

### AC-03: Schema Evolution Works
```gherkin
Given a StoppedEvent with an extra field "future_field"
When I parse the JSON
Then the model parses successfully
  And future_field is accessible via model.model_extra
```

### AC-04: Type Export Generates Valid TypeScript
```gherkin
Given all domain models are defined
When I run python scripts/export_types.py
Then valid TypeScript is generated
  And the EventType enum has 19 values
  And the Event union has 19 members
```

### AC-05: Forkable Events Set Is Correct
```gherkin
Given the FORKABLE_EVENTS set
Then it contains exactly:
  | PlanCreated |
  | AmbiguityDetected |
  | ContradictionDetected |
  | JudgeRuled |
  | Stopped |
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/domain/__init__.py`
- [ ] Create `backend/app/domain/enums.py`
- [ ] Create `backend/app/domain/events.py`
- [ ] Create `backend/app/domain/run.py`
- [ ] Create `backend/app/domain/confidence.py`
- [ ] Create `scripts/export_types.py`
- [ ] Run pyright on domain module
- [ ] Write unit tests for serialization
- [ ] Write unit tests for discriminated union
- [ ] Generate TypeScript types
- [ ] Create `frontend/src/types/events.ts`

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | Serialization/deserialization | 100% |
| Unit | pytest | Discriminated union parsing | 100% |
| Unit | pytest | Schema evolution (extra fields) | 100% |
| Types | pyright | All domain models | 100% |

## 8. Environment Variables

_None required for this BRD._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Event type mismatch FE/BE | High | Medium | Automated type export, CI check |
| Missing event in union | High | Low | Exhaustive match in FSM |
| Schema drift | Medium | Medium | `extra="allow"` + optional keys only |

## 10. Out of Scope

- Event persistence (BRD-03)
- Event streaming via SSE (BRD-10)
- Event-driven FSM logic (BRD-07)
- Confidence calculation logic (BRD-08)
