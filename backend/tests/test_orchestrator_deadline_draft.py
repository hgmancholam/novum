"""Tests for PR-11 deadline-draft escape in ``_check_global_budget``.

When a recoverable global cap (tool_calls / evidence / query_reformulations /
event-plateau / claim-coverage-plateau) is hit AND we already have enough
evidence collected, the orchestrator must attempt one last-chance synthesis
instead of stopping with no draft. Q2/Q6 in the 2026-05-29 eval reached the
reformulation cap with 18-21 evidence items but produced no draft and no
judge verdict; PR-11 fixes that wasted work.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState
from app.domain.enums import EventType, StopReason
from app.domain.events import BaseEvent, QueryReformulatedEvent


def _make_orch(
    *, current_state: AgentState = AgentState.SEARCHING
) -> tuple[AgentOrchestrator, list[BaseEvent]]:
    state = RunState(run_id=uuid4(), question="q")
    state.current_state = current_state
    captured: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        captured.append(ev)

    return AgentOrchestrator(state, emit), captured


def _push_evidence(state: RunState, n: int) -> None:
    for i in range(n):
        state.add_evidence(
            EvidenceItem(
                claim_id=f"c{i}",
                source_url=f"https://x/{i}",
                source_title="t",
                text="snippet",
                polarity="support",
                confidence=0.5,
            )
        )


def _push_reformulations(state: RunState, n: int) -> None:
    for i in range(n):
        state.events.append(
            QueryReformulatedEvent(
                original_query=f"q{i}",
                reformulated_query=f"q{i}-v2",
                target_claim_id=f"c{i}",
                reason="low_relevance",
            )
        )


@pytest.mark.asyncio
async def test_reformulation_cap_with_evidence_forces_drafting() -> None:
    """Cap hit + evidence ≥ floor → transition to DRAFTING, do NOT stop."""
    orch, captured = _make_orch(current_state=AgentState.SEARCHING)
    orch.state.max_query_reformulations_per_run = 3
    _push_reformulations(orch.state, 3)
    _push_evidence(orch.state, 10)

    stopped = await orch._check_global_budget()

    assert stopped is False
    assert orch.state.budget_forced_synthesis is True
    assert orch.state.current_state == AgentState.DRAFTING
    assert orch.state.budget_exhausted_kind == "query_reformulations"
    assert orch.state.stop_reason is None
    assert not any(ev.type == EventType.STOPPED for ev in captured)


@pytest.mark.asyncio
async def test_reformulation_cap_without_evidence_still_stops() -> None:
    """Cap hit + evidence < floor → legacy STOPPED_BY_BUDGET path."""
    orch, captured = _make_orch()
    orch.state.max_query_reformulations_per_run = 3
    _push_reformulations(orch.state, 3)
    _push_evidence(orch.state, 2)  # below the 5-item floor

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.budget_forced_synthesis is False
    assert orch.state.budget_exhausted_kind == "query_reformulations"
    assert orch.state.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert any(ev.type == EventType.STOPPED for ev in captured)


@pytest.mark.asyncio
async def test_deadline_draft_runs_at_most_once() -> None:
    """Once the latch is set, a second cap hit goes straight to stop."""
    orch, captured = _make_orch()
    orch.state.max_query_reformulations_per_run = 3
    _push_reformulations(orch.state, 3)
    _push_evidence(orch.state, 10)
    orch.state.budget_forced_synthesis = True  # simulate first pass done

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert any(ev.type == EventType.STOPPED for ev in captured)


@pytest.mark.asyncio
async def test_evidence_cap_with_evidence_forces_drafting() -> None:
    orch, captured = _make_orch(current_state=AgentState.ANALYZING)
    orch.state.max_evidence_per_run = 5
    _push_evidence(orch.state, 5)

    stopped = await orch._check_global_budget()

    assert stopped is False
    assert orch.state.budget_forced_synthesis is True
    assert orch.state.current_state == AgentState.DRAFTING
    assert orch.state.budget_exhausted_kind == "evidence"
    assert not any(ev.type == EventType.STOPPED for ev in captured)


@pytest.mark.asyncio
async def test_wall_clock_cap_still_hard_stops_even_with_evidence() -> None:
    """Wall-clock is the irrescatable cap — no deadline draft attempted."""
    from datetime import UTC, datetime, timedelta

    orch, captured = _make_orch()
    orch.state.wall_clock_max_seconds = 1
    orch.state.started_at = datetime.now(UTC) - timedelta(seconds=10)
    _push_evidence(orch.state, 10)

    stopped = await orch._check_global_budget()

    assert stopped is True
    assert orch.state.budget_forced_synthesis is False
    assert orch.state.budget_exhausted_kind == "wall_clock"
    assert orch.state.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert any(ev.type == EventType.STOPPED for ev in captured)
