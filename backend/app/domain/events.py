"""Event type definitions as Pydantic discriminated union.

All events have:
- ``type``: discriminator field tied to :class:`EventType`
- ``model_config`` with ``extra="allow"`` for schema evolution (RF-03)
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    EventType,
    EvidencePolarity,
    QuestionType,
    SourceType,
    StopReason,
)


class BaseEvent(BaseModel):
    """Base class for all events."""

    model_config = ConfigDict(extra="allow")

    id: UUID | None = None
    run_id: UUID | None = None
    step_index: int | None = None
    parent_event_id: UUID | None = None
    created_at: datetime | None = None


# =============================================================================
# Question & Planning Events
# =============================================================================


class QuestionAskedEvent(BaseEvent):
    """Initial question submitted by user."""

    type: Literal[EventType.QUESTION_ASKED] = EventType.QUESTION_ASKED
    question: str
    user_context: str | None = None
    detected_question_type: QuestionType | None = None


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
    query_intent: str
    target_claim_id: str | None = None


class SourceResult(BaseModel):
    """A single result from a source."""

    model_config = ConfigDict(extra="allow")

    url: str
    title: str
    snippet: str
    relevance_score: float | None = None


class EvidenceAddedEvent(BaseEvent):
    """Evidence collected from a source."""

    type: Literal[EventType.EVIDENCE_ADDED] = EventType.EVIDENCE_ADDED
    source_type: SourceType
    source_url: str
    source_title: str
    extracted_text: str
    polarity: EvidencePolarity
    target_claim_id: str
    confidence: float


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
    winning_source: str | None = None
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
    judge_confidence: float
    structural_confidence: float
    final_confidence: float
    threshold: float
    passed: bool
    rationale: str
    suggested_improvements: list[str] | None = None


class ConfidenceMismatchEvent(BaseEvent):
    """S and J diverge significantly (RF-15)."""

    type: Literal[EventType.CONFIDENCE_MISMATCH] = EventType.CONFIDENCE_MISMATCH
    structural_confidence: float
    judge_confidence: float
    divergence: float
    trust_flag: str


# =============================================================================
# Error & Recovery Events (RF-11)
# =============================================================================


class AgentErroredEvent(BaseEvent):
    """Unrecoverable error during execution."""

    type: Literal[EventType.AGENT_ERRORED] = EventType.AGENT_ERRORED
    error_type: str
    error_message: str
    stack_trace: str | None = None
    recoverable: bool
    recovery_suggestion: str | None = None


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
    answer_prose: str | None = None
    answer_sections: list[AnswerSection] | None = None
    citations: list[Citation] | None = None

    # Honest stop details (if honest_*)
    honest_explanation: str | None = None

    # Metrics
    total_tokens: int | None = None
    total_duration_seconds: float | None = None


# =============================================================================
# Discriminated Union
# =============================================================================


Event = Annotated[
    QuestionAskedEvent | PlanCreatedEvent | PlanCritiquedEvent | PlanRevisedEvent | ToolCalledEvent | EvidenceAddedEvent | ClaimCoveredEvent | ClaimUncoverableEvent | SourceFailedEvent | AmbiguityDetectedEvent | ContradictionDetectedEvent | ContradictionResolvedEvent | UserContextChallengedEvent | JudgeRuledEvent | ConfidenceMismatchEvent | AgentErroredEvent | ResumedAfterErrorEvent | ResumedAfterCancelEvent | StoppedEvent,
    Field(discriminator="type"),
]


# Mapping for deserialization and FSM dispatch.
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


# Forkable events (RF-03): decision points a user can branch from.
FORKABLE_EVENTS: set[EventType] = {
    EventType.PLAN_CREATED,
    EventType.AMBIGUITY_DETECTED,
    EventType.CONTRADICTION_DETECTED,
    EventType.JUDGE_RULED,
    EventType.STOPPED,
}
