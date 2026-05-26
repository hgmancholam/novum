"""Domain package: Pydantic models for events, runs, confidence (BRD-02).

Exposes the public API consumed by the FSM (BRD-07), persistence layer
(BRD-03), SSE serializer (BRD-10), and the TypeScript exporter
(``scripts/export_types.py``).
"""

from app.domain.confidence import ConfidenceResult, StructuralConfidence
from app.domain.enums import (
    EventType,
    EvidencePolarity,
    OutputFormat,
    QuestionType,
    SourceType,
    StopReason,
)
from app.domain.events import (
    EVENT_TYPE_MAP,
    FORKABLE_EVENTS,
    AgentErroredEvent,
    AmbiguityDetectedEvent,
    AnswerSection,
    BaseEvent,
    Citation,
    ClaimCoveredEvent,
    ClaimUncoverableEvent,
    ConfidenceMismatchEvent,
    ContradictionDetectedEvent,
    ContradictionResolvedEvent,
    ContradictionSource,
    Event,
    EvidenceAddedEvent,
    JudgeRuledEvent,
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanRevisedEvent,
    QuestionAskedEvent,
    ResumedAfterCancelEvent,
    ResumedAfterErrorEvent,
    SourceFailedEvent,
    SourceResult,
    StoppedEvent,
    SubClaim,
    ToolCalledEvent,
    UserContextChallengedEvent,
)
from app.domain.run import RunCreate, RunForkRequest, RunListItem, RunResponse

__all__ = [
    # Enums
    "EventType",
    "EvidencePolarity",
    "OutputFormat",
    "QuestionType",
    "SourceType",
    "StopReason",
    # Event union & registries
    "Event",
    "EVENT_TYPE_MAP",
    "FORKABLE_EVENTS",
    "BaseEvent",
    # Event classes
    "AgentErroredEvent",
    "AmbiguityDetectedEvent",
    "ClaimCoveredEvent",
    "ClaimUncoverableEvent",
    "ConfidenceMismatchEvent",
    "ContradictionDetectedEvent",
    "ContradictionResolvedEvent",
    "EvidenceAddedEvent",
    "JudgeRuledEvent",
    "PlanCreatedEvent",
    "PlanCritiquedEvent",
    "PlanRevisedEvent",
    "QuestionAskedEvent",
    "ResumedAfterCancelEvent",
    "ResumedAfterErrorEvent",
    "SourceFailedEvent",
    "StoppedEvent",
    "ToolCalledEvent",
    "UserContextChallengedEvent",
    # Nested DTOs
    "AnswerSection",
    "Citation",
    "ContradictionSource",
    "SourceResult",
    "SubClaim",
    # Run DTOs
    "RunCreate",
    "RunForkRequest",
    "RunListItem",
    "RunResponse",
    # Confidence DTOs
    "ConfidenceResult",
    "StructuralConfidence",
]
