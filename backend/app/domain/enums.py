"""Domain enums matching database enums (BRD-01 migration 001)."""

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

    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    DEFINITIONAL = "definitional"
    STATE_OF_ART = "state_of_art"
    CAUSAL = "causal"


class OutputFormat(StrEnum):
    """Answer format options (RF-10)."""

    PROSE = "prose"
    STRUCTURED = "structured"


class EventType(StrEnum):
    """All event types (20) for the event log."""

    # Question & Planning
    QUESTION_ASKED = "QuestionAsked"
    QUESTION_NORMALIZED = "QuestionNormalized"
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
