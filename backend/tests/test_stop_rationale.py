"""PR-1 Mejoras 2.1 + 2.2 — StopRationale honest rendering.

Tests that ``AgentOrchestrator._stop`` emits a ``StopRationale`` whose
``summary`` matches the *actual* budget that fired (search rounds vs
ReAct steps vs judge attempts) and whose ``confidence`` falls back to
the structural score with ``confidence_kind="structural"`` when no
judge confirmation occurred.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.agent.states import AgentState
from app.domain.enums import Lane, StopReason
from app.domain.events import BaseEvent, StoppedEvent


def _state(**overrides: object) -> RunState:
    base: dict[str, object] = {
        "run_id": uuid4(),
        "question": "anything",
        "current_state": AgentState.JUDGING,
    }
    base.update(overrides)
    return RunState(**base)


def _orchestrator(state: RunState) -> tuple[AgentOrchestrator, list[BaseEvent]]:
    collected: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)

    return AgentOrchestrator(state, emit), collected


def _stopped(events: list[BaseEvent]) -> StoppedEvent:
    for ev in events:
        if isinstance(ev, StoppedEvent):
            return ev
    raise AssertionError("No StoppedEvent emitted")


@pytest.mark.asyncio
async def test_react_budget_rationale_uses_react_step_count() -> None:
    state = _state(
        selected_lane=Lane.DEEP,
        react_step_count=6,
        max_react_steps=8,
        budget_exhausted_kind="react_steps",
        draft_answer="best effort answer",
        last_structural_confidence=0.58,
    )
    orch, events = _orchestrator(state)

    await orch._stop(StopReason.STOPPED_BY_BUDGET)

    stopped = _stopped(events)
    assert stopped.stop_rationale is not None
    assert "ReAct step limit" in stopped.stop_rationale.summary
    assert "6/8" in stopped.stop_rationale.summary
    # The bug we are fixing was reporting "search limit (0 rounds)".
    assert "search limit" not in stopped.stop_rationale.summary.lower()


@pytest.mark.asyncio
async def test_search_budget_rationale_uses_search_count() -> None:
    state = _state(
        search_count=20,
        max_searches=20,
        budget_exhausted_kind="search_rounds",
        draft_answer="best effort answer",
    )
    orch, events = _orchestrator(state)

    await orch._stop(StopReason.STOPPED_BY_BUDGET)

    stopped = _stopped(events)
    assert stopped.stop_rationale is not None
    assert "search limit" in stopped.stop_rationale.summary.lower()
    assert "20/20" in stopped.stop_rationale.summary


@pytest.mark.asyncio
async def test_judge_cap_rationale_mentions_judge_attempts() -> None:
    state = _state(
        judge_attempts=3,
        max_judge_attempts=3,
        budget_exhausted_kind="judge_attempts",
        draft_answer="best effort answer",
    )
    orch, events = _orchestrator(state)

    await orch._stop(StopReason.STOPPED_BY_BUDGET)

    stopped = _stopped(events)
    assert stopped.stop_rationale is not None
    assert "Judge rejected" in stopped.stop_rationale.summary
    assert stopped.stop_rationale.triggering_signal == "judge_cap"


@pytest.mark.asyncio
async def test_confidence_falls_back_to_structural_with_discriminator() -> None:
    state = _state(
        selected_lane=Lane.DEEP,
        react_step_count=8,
        max_react_steps=8,
        budget_exhausted_kind="react_steps",
        draft_answer="best effort answer",
        last_judge_confidence=None,
        last_structural_confidence=0.61,
    )
    orch, events = _orchestrator(state)

    await orch._stop(StopReason.STOPPED_BY_BUDGET)

    stopped = _stopped(events)
    assert stopped.stop_rationale is not None
    assert stopped.stop_rationale.confidence == pytest.approx(0.61)
    assert stopped.stop_rationale.confidence_kind == "structural"


@pytest.mark.asyncio
async def test_judge_confidence_preferred_when_present() -> None:
    state = _state(
        selected_lane=Lane.DEEP,
        budget_exhausted_kind="react_steps",
        draft_answer="best effort answer",
        last_judge_confidence=0.72,
        last_structural_confidence=0.50,
    )
    orch, events = _orchestrator(state)

    await orch._stop(StopReason.STOPPED_BY_BUDGET)

    stopped = _stopped(events)
    assert stopped.stop_rationale is not None
    assert stopped.stop_rationale.confidence == pytest.approx(0.72)
    assert stopped.stop_rationale.confidence_kind == "judge"


@pytest.mark.asyncio
async def test_legacy_inference_when_budget_kind_unset_deep_lane() -> None:
    """Backwards-compat: paths not yet wired still get the right rationale."""
    state = _state(
        selected_lane=Lane.DEEP,
        react_step_count=8,
        max_react_steps=8,
        budget_exhausted_kind=None,
        draft_answer="best effort answer",
    )
    orch, events = _orchestrator(state)

    await orch._stop(StopReason.STOPPED_BY_BUDGET)

    stopped = _stopped(events)
    assert stopped.stop_rationale is not None
    assert "ReAct step limit" in stopped.stop_rationale.summary
