"""Domain enums matching database enums (BRD-01 migration 001).

Amendment 2026-05-27 — "always answer" refactor (WP-1, additive):
- ``QuestionType`` extended with Types 6/7/8 (predictive_future, subjective_opinion,
  personal_private). They no longer short-circuit to ``honest_unanswerable``;
  the orchestrator routes them via ``AnswerKind`` instead.
- ``AnswerKind`` introduced. The shape of the final answer when the run
  terminates as ``judge_confirmed``.
- ``StopReason`` is unchanged in this WP. Collapse to 4 values lands at the
  end of WP-3 once the synthesizer templates and per-kind ceilings exist.
"""

from enum import StrEnum


class StopReason(StrEnum):
    """Terminal states for a run (RF-01, WP-3 amendment 2026-05-27).

    Four terminal states:
    - 1 positive terminal (judge_confirmed with AnswerKind)
    - 1 budget safety net
    - 1 user action
    - 1 error state

    The three ``honest_*`` values were removed in WP-3. Ambiguous/sparse/
    contradictory questions now route through ``AnswerKind`` selection
    (best_effort, weighted, scenario) inside ``judge_confirmed``.
    """

    JUDGE_CONFIRMED = "judge_confirmed"
    STOPPED_BY_BUDGET = "stopped_by_budget"
    USER_CANCELLED = "user_cancelled"
    ERRORED = "errored"


class QuestionType(StrEnum):
    """Supported question types (RF-06).

    Types 1–5 are the "answerable" classes. Types 6–8 used to short-circuit
    to ``honest_unanswerable``; per the 2026-05-27 amendment they now route
    to dedicated ``AnswerKind`` templates (predictive_future→SCENARIO,
    subjective_opinion→TRADEOFF, personal_private→ETHICAL_REDIRECT).
    """

    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    DEFINITIONAL = "definitional"
    STATE_OF_ART = "state_of_art"
    CAUSAL = "causal"
    PREDICTIVE_FUTURE = "predictive_future"
    SUBJECTIVE_OPINION = "subjective_opinion"
    PERSONAL_PRIVATE = "personal_private"


class AnswerKind(StrEnum):
    """Shape of the answer produced at terminal ``judge_confirmed`` (RF-17).

    Selected by ``app.agent.tasks.select_answer_kind`` from
    ``(question_type, S, C_coverage, C_agreement, ambiguity_flag)``.
    Each kind carries a soft confidence ceiling (see
    ``app.confidence.kind_ceiling``).
    """

    DIRECT = "direct"
    WEIGHTED = "weighted"
    SCENARIO = "scenario"
    TRADEOFF = "tradeoff"
    ETHICAL_REDIRECT = "ethical_redirect"
    BEST_EFFORT = "best_effort"


class OutputFormat(StrEnum):
    """Answer format options (RF-10)."""

    PROSE = "prose"
    STRUCTURED = "structured"


class ComplexityHint(StrEnum):
    """Question complexity classification for planning budget (BRD-22).

    - ``trivial``: short factual/definitional queries (≤8 words) → 1 claim, 1 source, no critique
    - ``standard``: typical questions → current default budget
    - ``deep``: research-heavy questions (≥16 words or STATE_OF_ART) → extra critique pass
    """

    TRIVIAL = "trivial"
    STANDARD = "standard"
    DEEP = "deep"


class EventType(StrEnum):
    """All event types (22) for the event log."""

    # Question & Planning
    QUESTION_ASKED = "QuestionAsked"
    QUESTION_NORMALIZED = "QuestionNormalized"
    QUESTION_CLASSIFIED = "QuestionClassified"
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
    PRIOR_RUN_HINT_REPLAYED = "PriorRunHintReplayed"

    # Judge & Confidence
    JUDGE_RULED = "JudgeRuled"
    CONFIDENCE_MISMATCH = "ConfidenceMismatch"

    # WP-4: Saturation detection
    SATURATION_DETECTED = "SaturationDetected"

    # WP-5: Judge provider degradation
    JUDGE_PROVIDER_DEGRADED = "JudgeProviderDegraded"

    # BRD-23 WP-2: deep-fetch escalation
    DEEP_FETCH_PERFORMED = "DeepFetchPerformed"

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
    SEMANTIC_SCHOLAR = "semantic_scholar"
    OPENALEX = "openalex"


class TemporalSensitivity(StrEnum):
    """Temporal-sensitivity bucket per BRD-23 §4.4 (WP-1).

    Drives planner source routing, Tavily ``days`` filter, and the
    stale-citation ceiling penalty inside ``kind_ceiling``.
    """

    STATIC = "static"
    SLOW_CHANGING = "slow_changing"
    VOLATILE = "volatile"
    REALTIME = "realtime"


class AuthorityTier(StrEnum):
    """Authority-tier bucket per BRD-23 §4.4 / §4.7 (WP-3).

    Multiplies the evidence row's contribution to ``C_coverage`` and
    ``C_independence`` inside ``confidence/structural.py``. ``C_agreement``
    and ``C_no_conflict`` are untouched.
    """

    PRIMARY_AUTHORITATIVE = "primary_authoritative"
    REPUTABLE_SECONDARY = "reputable_secondary"
    GENERAL = "general"
    LOW_SIGNAL = "low_signal"
