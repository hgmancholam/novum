"""Unit tests for the DEEP-lane ``after_cove`` meta-judge hook.

Exercises only the meta-judge gate that sits between CoVe and the
mini-judge — we patch the hook helpers directly so no real LLM calls
fire (BRD-26 §4.6, IP-26 slice 3b).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.meta_judge_hook import maybe_run_meta_judge
from app.agent.run_state import RunState
from app.domain.enums import Lane
from app.domain.events import (
    AdversarialObjectionsGeneratedEvent,
    BaseEvent,
    MetaStopVerdictEvent,
)
from app.domain.meta_stop import (
    AdversarialCompletenessVerdict,
    Objection,
    ValueOfContinuationVerdict,
)


class _CoveSignal:
    __slots__ = (
        "passed",
        "judge_confidence",
        "structural_confidence",
        "final_confidence",
        "rationale",
        "suggested_improvements",
    )

    def __init__(self) -> None:
        self.passed = False
        self.judge_confidence = 0.5
        self.structural_confidence = 0.6
        self.final_confidence = 0.5
        self.rationale = "after_cove pre-judge"
        self.suggested_improvements: list[str] = []


def _state(**overrides: Any) -> RunState:
    defaults: dict[str, Any] = {
        "run_id": uuid4(),
        "question": "What caused the 2023 banking turmoil?",
        "confidence_threshold": 0.7,
        "max_searches": 5,
        "max_judge_attempts": 3,
        "selected_lane": Lane.DEEP,
        "draft_answer": "Draft prose body.",
    }
    defaults.update(overrides)
    return RunState(**defaults)


def _collector() -> tuple[list[BaseEvent], Any]:
    collected: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)

    return collected, emit


@pytest.mark.asyncio
async def test_after_cove_emits_event_with_correct_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    voc = ValueOfContinuationVerdict(
        decision="stop",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="enough evidence already",
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation",
        AsyncMock(return_value=voc),
    )
    events, emit = _collector()
    outcome = await maybe_run_meta_judge(_state(), emit, _CoveSignal(), hook="after_cove")
    assert outcome == "continue"
    msv = next(e for e in events if isinstance(e, MetaStopVerdictEvent))
    assert msv.hook == "after_cove"
    assert msv.lane == Lane.DEEP


@pytest.mark.asyncio
async def test_after_cove_stop_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    voc = ValueOfContinuationVerdict(
        decision="stop_best_effort",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="no plausible next step",
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation",
        AsyncMock(return_value=voc),
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections",
        AsyncMock(side_effect=AssertionError("AC must NOT run on stop_best_effort")),
    )
    events, emit = _collector()
    outcome = await maybe_run_meta_judge(_state(), emit, _CoveSignal(), hook="after_cove")
    assert outcome == "stop_best_effort"
    assert any(isinstance(e, MetaStopVerdictEvent) for e in events)


@pytest.mark.asyncio
async def test_after_cove_confirm_skips_mini_judge_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.10,
        next_action_hypothesis="x",
        reason="gap",
    )
    objections = [
        Objection(text="o1", status="answered_by_evidence"),
        Objection(text="o2", status="answered_by_evidence"),
        Objection(text="o3", status="answered_by_evidence"),
    ]
    ac = AdversarialCompletenessVerdict(objections=objections)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation",
        AsyncMock(return_value=voc),
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections",
        AsyncMock(return_value=ac),
    )
    events, emit = _collector()
    outcome = await maybe_run_meta_judge(_state(), emit, _CoveSignal(), hook="after_cove")
    assert outcome == "confirm"
    assert any(isinstance(e, AdversarialObjectionsGeneratedEvent) for e in events)
