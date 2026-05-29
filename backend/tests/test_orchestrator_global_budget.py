"""Tests for AgentOrchestrator._check_global_budget (PR-1, post-2026-05-29 eval).

Guarantees that no FSM cycle can hang forever: the wall-clock, tool-call,
evidence, query-reformulation and event-plateau caps all force a terminal
``Stopped(STOPPED_BY_BUDGET)`` event independently of the StoppingSignal
plugins (which only fire after a JudgeRuled event).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState
from app.domain.enums import EventType, SourceType, StopReason
from app.domain.events import BaseEvent, ToolCalledEvent
from app.stopping.signals.no_progress import check_event_level_plateau


def _make_orchestrator() -> tuple[AgentOrchestrator, list[BaseEvent]]:
    state = RunState(run_id=uuid4(), question="q")
    state.current_state = AgentState.SEARCHING
    captured: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        captured.append(ev)

    orch = AgentOrchestrator(state, emit)
    return orch, captured


@pytest.mark.asyncio
async def test_wall_clock_cap_fires_and_stops() -> None:
    orch, captured = _make_orchestrator()
    orch.state.wall_clock_max_seconds = 1
    # Pretend the run started well over the cap ago.
    orch.state.started_at = datetime.now(UTC) - timedelta(seconds=10)

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert orch.state.budget_exhausted_kind == "wall_clock"
    assert any(ev.type == EventType.STOPPED for ev in captured)


@pytest.mark.asyncio
async def test_wall_clock_within_budget_does_not_stop() -> None:
    orch, _ = _make_orchestrator()
    orch.state.wall_clock_max_seconds = 600
    stopped = await orch._check_global_budget()
    assert stopped is False
    assert orch.state.stop_reason is None


@pytest.mark.asyncio
async def test_tool_calls_cap_fires() -> None:
    orch, captured = _make_orchestrator()
    orch.state.max_tool_calls_per_run = 3
    for i in range(3):
        await orch.emit(
            ToolCalledEvent(
                source_type=SourceType.TAVILY,
                query=f"q{i}",
                query_intent="explore",
            )
        )

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.budget_exhausted_kind == "tool_calls"
    assert orch.state.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert any(ev.type == EventType.STOPPED for ev in captured)


@pytest.mark.asyncio
async def test_evidence_cap_fires() -> None:
    orch, _ = _make_orchestrator()
    orch.state.max_evidence_per_run = 2
    for i in range(2):
        orch.state.add_evidence(
            EvidenceItem(
                claim_id=f"c{i}",
                source_url=f"https://x/{i}",
                source_title="t",
                text="snippet",
                polarity="support",
                confidence=0.5,
            )
        )

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.budget_exhausted_kind == "evidence"


@pytest.mark.asyncio
async def test_no_caps_exceeded_returns_false() -> None:
    orch, _ = _make_orchestrator()
    # All defaults — nothing exceeded.
    stopped = await orch._check_global_budget()
    assert stopped is False


@pytest.mark.asyncio
async def test_emit_appends_to_state_events() -> None:
    """PR-1: emit() must mirror events into state.events so has_event() works
    on fresh runs (not only after a resume fold)."""
    orch, _ = _make_orchestrator()
    assert orch.state.events == []
    await orch.emit(
        ToolCalledEvent(
            source_type=SourceType.TAVILY,
            query="x",
            query_intent="explore",
        )
    )
    assert len(orch.state.events) == 1
    assert orch.state.has_event(EventType.TOOL_CALLED)


# ---------------------------------------------------------------------------
# Event-level plateau predicate (no_progress.check_event_level_plateau).
# ---------------------------------------------------------------------------


def _push_tool_events(state: RunState, n: int) -> None:
    for i in range(n):
        state.events.append(
            ToolCalledEvent(
                source_type=SourceType.TAVILY,
                query=f"q{i}",
                query_intent="explore",
            )
        )


def test_event_plateau_warmup_returns_false() -> None:
    state = RunState(run_id=uuid4(), question="q")
    state.no_progress_event_window = 30
    _push_tool_events(state, 5)
    assert check_event_level_plateau(state) is False


def test_event_plateau_full_window_no_progress_returns_true() -> None:
    state = RunState(run_id=uuid4(), question="q")
    state.no_progress_event_window = 10
    _push_tool_events(state, 10)
    assert check_event_level_plateau(state) is True


def test_event_plateau_progress_marker_resets() -> None:
    """A ClaimCovered event inside the window keeps the predicate at False."""
    from app.domain.events import ClaimCoveredEvent

    state = RunState(run_id=uuid4(), question="q")
    state.no_progress_event_window = 10
    _push_tool_events(state, 9)
    state.events.append(
        ClaimCoveredEvent(
            claim_id="c1",
            claim_text="some claim",
            evidence_ids=[],
            coverage_rationale="covered",
        )
    )
    assert check_event_level_plateau(state) is False


@pytest.mark.asyncio
async def test_check_global_budget_triggers_no_progress_plateau() -> None:
    orch, _ = _make_orchestrator()
    orch.state.no_progress_event_window = 10
    _push_tool_events(orch.state, 10)

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.budget_exhausted_kind == "no_progress_events"
    assert orch.state.stop_reason == StopReason.STOPPED_BY_BUDGET
