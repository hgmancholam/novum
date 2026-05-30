"""Tests for ``app.agent.source_hints.build_source_hints`` (IP-30)."""

from __future__ import annotations

from uuid import uuid4

from app.agent.run_state import RunState
from app.agent.source_hints import build_source_hints
from app.domain.enums import (
    ComplexityHint,
    QuestionDomain,
    QuestionType,
    TemporalSensitivity,
)


def _state() -> RunState:
    return RunState(run_id=uuid4(), question="Q?")


def test_build_source_hints_emits_domain() -> None:
    state = _state()
    state.domain = QuestionDomain.MEDICAL
    state.question_type = QuestionType.FACTUAL
    state.complexity_hint = ComplexityHint.STANDARD
    state.temporal_sensitivity = TemporalSensitivity.STATIC

    hints = build_source_hints(state)

    assert hints["domain"] == "medical"
    assert hints["question_type"] == "factual"
    assert hints["complexity_hint"] == "standard"
    assert hints["temporal_sensitivity"] == "static"


def test_build_source_hints_domain_none_when_unset() -> None:
    state = _state()
    hints = build_source_hints(state)

    assert hints["domain"] is None
