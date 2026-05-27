"""Tests for domain enums (BRD-02 §4.2).

Cross-checks enum values and counts against the BRD-01 migration
(``backend/alembic/versions/001_initial_schema.py``).
"""

from app.domain.enums import (
    EventType,
    EvidencePolarity,
    OutputFormat,
    QuestionType,
    SourceType,
    StopReason,
)


def test_stop_reason_has_exactly_7_values() -> None:
    assert len(StopReason) == 7


def test_stop_reason_values() -> None:
    expected = {
        "judge_confirmed",
        "honest_unanswerable",
        "honest_contradiction",
        "honest_ambiguous",
        "stopped_by_budget",
        "user_cancelled",
        "errored",
    }
    assert {v.value for v in StopReason} == expected


def test_question_type_has_exactly_5_values() -> None:
    assert len(QuestionType) == 5


def test_question_type_values() -> None:
    expected = {"factual", "comparative", "definitional", "state_of_art", "causal"}
    assert {v.value for v in QuestionType} == expected


def test_output_format_has_exactly_2_values() -> None:
    assert len(OutputFormat) == 2


def test_output_format_values() -> None:
    assert {v.value for v in OutputFormat} == {"prose", "structured"}


def test_event_type_has_exactly_20_values() -> None:
    assert len(EventType) == 20


def test_event_type_values() -> None:
    expected = {
        "QuestionAsked",
        "QuestionNormalized",
        "PlanCreated",
        "PlanCritiqued",
        "PlanRevised",
        "ToolCalled",
        "EvidenceAdded",
        "ClaimCovered",
        "ClaimUncoverable",
        "SourceFailed",
        "AmbiguityDetected",
        "ContradictionDetected",
        "ContradictionResolved",
        "UserContextChallenged",
        "JudgeRuled",
        "ConfidenceMismatch",
        "AgentErrored",
        "ResumedAfterError",
        "ResumedAfterCancel",
        "Stopped",
    }
    assert {v.value for v in EventType} == expected


def test_evidence_polarity_values() -> None:
    assert {v.value for v in EvidencePolarity} == {"supports", "contradicts", "neutral"}


def test_source_type_values() -> None:
    assert {v.value for v in SourceType} == {"tavily", "wikipedia"}


def test_enums_are_string_subclass() -> None:
    """StrEnum members must be usable directly as ``str``."""
    assert StopReason.JUDGE_CONFIRMED == "judge_confirmed"
    assert EventType.STOPPED == "Stopped"
    assert QuestionType.FACTUAL == "factual"
