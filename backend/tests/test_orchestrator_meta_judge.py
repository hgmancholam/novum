"""Unit tests for the meta-judge integration in ``AgentOrchestrator``.

These exercise ``_maybe_run_meta_judge`` directly with a stubbed judge
event and a patched LLM ``call`` so we do not need the full FSM, DB
fixtures, or live providers (BRD-26, IP-26 slice 2).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.domain.enums import Lane
from app.domain.events import (
    AdversarialObjectionsGeneratedEvent,
    BaseEvent,
    DirectedSubclaimsFromObjectionsEvent,
    MetaStopVerdictEvent,
)
from app.domain.meta_stop import (
    AdversarialCompletenessVerdict,
    Objection,
    ValueOfContinuationVerdict,
)


def _state(**overrides: Any) -> RunState:
    defaults: dict[str, Any] = {
        "run_id": uuid4(),
        "question": "What is the inflation-adjusted GDP growth rate of France 2015-2025?",
        "confidence_threshold": 0.7,
        "max_searches": 5,
        "max_judge_attempts": 3,
        "selected_lane": Lane.STANDARD,
        "draft_answer": "Draft body.",
    }
    defaults.update(overrides)
    return RunState(**defaults)


def _judge_event(*, passed: bool = False) -> Any:
    class _StubJudge:
        def __init__(self) -> None:
            self.passed = passed
            self.judge_confidence = 0.58
            self.structural_confidence = 0.62
            self.final_confidence = 0.58
            self.rationale = "needs primary source"
            self.suggested_improvements: list[str] = ["fetch source X"]

    return _StubJudge()


def _orch(state: RunState) -> tuple[AgentOrchestrator, list[BaseEvent]]:
    collected: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)

    return AgentOrchestrator(state, emit), collected


@pytest.mark.asyncio
async def test_meta_judge_skipped_when_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", False)
    orch, events = _orch(_state())
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "skipped"
    assert events == []


@pytest.mark.asyncio
async def test_meta_judge_skipped_on_fast_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    orch, events = _orch(_state(selected_lane=Lane.FAST))
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "skipped"
    assert events == []


@pytest.mark.asyncio
async def test_meta_judge_skipped_when_judge_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    orch, events = _orch(_state())
    outcome = await orch._maybe_run_meta_judge(_judge_event(passed=True))
    assert outcome == "skipped"
    assert events == []


@pytest.mark.asyncio
async def test_meta_judge_skipped_at_attempt_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    state = _state()
    state.judge_attempts = state.max_judge_attempts
    orch, events = _orch(state)
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "skipped"
    assert events == []


@pytest.mark.asyncio
async def test_meta_judge_stop_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    voc = ValueOfContinuationVerdict(
        decision="stop_best_effort",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="no concrete next action",
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", AsyncMock(return_value=voc)
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections",
        AsyncMock(side_effect=AssertionError("AC must NOT run on stop_best_effort")),
    )
    orch, events = _orch(_state())
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "stop_best_effort"
    assert len(events) == 1
    assert isinstance(events[0], MetaStopVerdictEvent)
    assert events[0].verdict.decision == "stop_best_effort"


@pytest.mark.asyncio
async def test_meta_judge_continue_below_min_delta_skips_ac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.01,  # below the configured min
        next_action_hypothesis="search X",
        reason="marginal",
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", AsyncMock(return_value=voc)
    )
    ac_mock = AsyncMock(side_effect=AssertionError("AC must NOT run when ΔS < threshold"))
    monkeypatch.setattr("app.agent.meta_judge_hook.generate_adversarial_objections", ac_mock)
    orch, events = _orch(_state())
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "continue"
    assert len(events) == 1
    assert isinstance(events[0], MetaStopVerdictEvent)


@pytest.mark.asyncio
async def test_meta_judge_confirm_when_ac_all_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.10,
        next_action_hypothesis="check primary source",
        reason="gap remains",
    )
    objections = [
        Objection(text="o1", status="answered_by_evidence", evidence_ids_answering=[]),
        Objection(text="o2", status="answered_by_evidence", evidence_ids_answering=[]),
        Objection(text="o3", status="answered_by_evidence", evidence_ids_answering=[]),
    ]
    ac = AdversarialCompletenessVerdict(objections=objections)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", AsyncMock(return_value=voc)
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections", AsyncMock(return_value=ac)
    )
    orch, events = _orch(_state())
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "confirm"
    assert any(isinstance(e, MetaStopVerdictEvent) for e in events)
    assert any(isinstance(e, AdversarialObjectionsGeneratedEvent) for e in events)
    ac_event = next(e for e in events if isinstance(e, AdversarialObjectionsGeneratedEvent))
    assert ac_event.verdict.all_answered is True


@pytest.mark.asyncio
async def test_meta_judge_continue_when_ac_has_unanswered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.08,
        next_action_hypothesis="x",
        reason="gap",
    )
    objections = [
        Objection(text="o1", status="answered_by_evidence", evidence_ids_answering=[]),
        Objection(
            text="o2",
            status="unanswered_needs_search",
            evidence_ids_answering=[],
            suggested_query="france gdp deflator 2024",
        ),
        Objection(text="o3", status="answered_by_evidence", evidence_ids_answering=[]),
    ]
    ac = AdversarialCompletenessVerdict(objections=objections)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", AsyncMock(return_value=voc)
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections", AsyncMock(return_value=ac)
    )
    state = _state()
    initial_subclaim_count = len(state.sub_claims)
    orch, events = _orch(state)
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "continue"
    assert any(isinstance(e, AdversarialObjectionsGeneratedEvent) for e in events)
    # BRD-26 §4.10: a fresh sub-claim must be minted from the unanswered objection
    # and a DirectedSubclaimsFromObjectionsEvent emitted with matching ids.
    directed = [e for e in events if isinstance(e, DirectedSubclaimsFromObjectionsEvent)]
    assert len(directed) == 1
    assert directed[0].objection_texts == ["o2"]
    assert len(directed[0].new_subclaim_ids) == 1
    assert len(state.sub_claims) == initial_subclaim_count + 1
    minted = state.sub_claims[-1]
    assert minted.text == "france gdp deflator 2024"
    assert minted.status == "pending"
    assert minted.id == str(directed[0].new_subclaim_ids[0])


@pytest.mark.asyncio
async def test_meta_judge_no_directed_event_when_all_objections_answered(
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
        Objection(text="o1", status="answered_by_evidence", evidence_ids_answering=[]),
        Objection(text="o2", status="answered_by_evidence", evidence_ids_answering=[]),
        Objection(text="o3", status="answered_by_evidence", evidence_ids_answering=[]),
    ]
    ac = AdversarialCompletenessVerdict(objections=objections)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", AsyncMock(return_value=voc)
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections", AsyncMock(return_value=ac)
    )
    state = _state()
    initial_count = len(state.sub_claims)
    orch, events = _orch(state)
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "confirm"
    assert not any(isinstance(e, DirectedSubclaimsFromObjectionsEvent) for e in events)
    assert len(state.sub_claims) == initial_count


@pytest.mark.asyncio
async def test_meta_judge_uses_objection_text_when_no_suggested_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.08,
        next_action_hypothesis="x",
        reason="gap",
    )
    objections = [
        Objection(text="missing primary source", status="unanswered_needs_search"),
        Objection(text="o2", status="answered_by_evidence"),
        Objection(text="o3", status="answered_by_evidence"),
    ]
    ac = AdversarialCompletenessVerdict(objections=objections)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", AsyncMock(return_value=voc)
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections", AsyncMock(return_value=ac)
    )
    state = _state()
    orch, _events = _orch(state)
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "continue"
    assert state.sub_claims[-1].text == "missing primary source"


@pytest.mark.asyncio
async def test_meta_judge_swallows_voc_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation",
        AsyncMock(side_effect=RuntimeError("LLM unavailable")),
    )
    orch, events = _orch(_state())
    outcome = await orch._maybe_run_meta_judge(_judge_event())
    assert outcome == "skipped"
    assert events == []
