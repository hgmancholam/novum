"""PR-2 unit tests — pre-synth meta-judge gate.

Drives ``AgentOrchestrator._maybe_run_before_synth_meta_judge`` directly
with stubbed ``evaluate_value_of_continuation`` so we never hit a live
LLM. Verifies the four outcomes wired by the plan:

  * ``force_synth``  → VoC ``decision="stop"``   ⇒ transition to DRAFTING
  * ``continue``     → VoC ``decision="continue"`` ⇒ transition to SEARCHING
  * ``stop_best_effort`` → VoC ``decision="stop_best_effort"`` ⇒ STOP_BY_BUDGET
  * fires-once-per-run ⇒ second invocation is a no-op
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState
from app.domain.enums import Lane, StopReason
from app.domain.events import BaseEvent, MetaStopVerdictEvent, StoppedEvent, SubClaim
from app.domain.meta_stop import ValueOfContinuationVerdict


def _state(**overrides: Any) -> RunState:
    defaults: dict[str, Any] = {
        "run_id": uuid4(),
        "question": "Is PostgreSQL or MongoDB better for a small SaaS application?",
        "confidence_threshold": 0.7,
        "max_searches": 5,
        "max_judge_attempts": 3,
        "selected_lane": Lane.STANDARD,
        "current_state": AgentState.ANALYZING,
    }
    defaults.update(overrides)
    return RunState(**defaults)


def _orch(state: RunState) -> tuple[AgentOrchestrator, list[BaseEvent]]:
    collected: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)

    return AgentOrchestrator(state, emit), collected


def _patch_voc(monkeypatch: pytest.MonkeyPatch, verdict: ValueOfContinuationVerdict) -> AsyncMock:
    mock = AsyncMock(return_value=verdict)
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", mock
    )
    # AC must NEVER run on the pre-synth hook (no draft to attack).
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.generate_adversarial_objections",
        AsyncMock(side_effect=AssertionError("AC must not run pre-synth")),
    )
    return mock


def _with_pending_claims_and_evidence(state: RunState, n_evidence: int) -> None:
    """Configure ``state`` so the threshold-trigger condition fires.

    Adds a pending sub-claim (so ``all_claims_resolved`` is False) plus
    ``n_evidence`` placeholder ``EvidenceItem``-shaped objects appended
    directly to ``state.evidence``. The hook only reads ``len()``.
    """
    state.sub_claims.append(SubClaim(id=str(uuid4()), text="c1", status="pending"))
    for i in range(n_evidence):
        state.evidence.append(
            EvidenceItem(
                claim_id="c1",
                source_url=f"https://example{i}.com/a",
                source_title=f"t{i}",
                text="x",
                polarity="supports",
                confidence=0.7,
            )
        )


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_judge_before_synthesizing_force_synth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_before_synth_min_evidence", 20)
    voc = ValueOfContinuationVerdict(
        decision="stop",  # → "force_synth" semantics for pre-synth hook
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="evidence is sufficient",
    )
    _patch_voc(monkeypatch, voc)

    state = _state()
    _with_pending_claims_and_evidence(state, n_evidence=20)
    orch, events = _orch(state)

    handled = await orch._maybe_run_before_synth_meta_judge()

    assert handled is True
    assert state.before_synth_hook_fired is True
    assert state.current_state == AgentState.DRAFTING
    assert any(isinstance(e, MetaStopVerdictEvent) for e in events)
    assert not any(isinstance(e, StoppedEvent) for e in events)


@pytest.mark.asyncio
async def test_meta_judge_before_synthesizing_continue_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_before_synth_min_evidence", 20)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.20,  # well above min delta
        next_action_hypothesis="fetch primary benchmarks",
        reason="missing primary source",
    )
    _patch_voc(monkeypatch, voc)

    state = _state()
    state.search_count = 1  # < max_searches=5 so SEARCHING transition is allowed
    _with_pending_claims_and_evidence(state, n_evidence=20)
    orch, events = _orch(state)

    handled = await orch._maybe_run_before_synth_meta_judge()

    assert handled is True
    assert state.before_synth_hook_fired is True
    assert state.current_state == AgentState.SEARCHING
    assert any(isinstance(e, MetaStopVerdictEvent) for e in events)


@pytest.mark.asyncio
async def test_meta_judge_before_synthesizing_stop_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_before_synth_min_evidence", 20)
    voc = ValueOfContinuationVerdict(
        decision="stop_best_effort",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="no productive next move",
    )
    _patch_voc(monkeypatch, voc)
    # Best-effort fallback also calls the LLM; stub it to a no-op.
    monkeypatch.setattr(
        "app.agent.tasks.draft.draft_best_effort_fallback", AsyncMock(return_value=None)
    )

    state = _state()
    _with_pending_claims_and_evidence(state, n_evidence=20)
    orch, events = _orch(state)

    handled = await orch._maybe_run_before_synth_meta_judge()

    assert handled is True
    assert state.before_synth_hook_fired is True
    assert state.budget_exhausted_kind == "search_rounds"
    assert state.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert any(isinstance(e, MetaStopVerdictEvent) for e in events)
    assert any(isinstance(e, StoppedEvent) for e in events)


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_judge_before_synth_fires_only_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_before_synth_min_evidence", 20)
    voc = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.20,
        next_action_hypothesis="x",
        reason="x",
    )
    voc_mock = _patch_voc(monkeypatch, voc)

    state = _state()
    state.search_count = 1
    _with_pending_claims_and_evidence(state, n_evidence=20)
    orch, _events = _orch(state)

    await orch._maybe_run_before_synth_meta_judge()
    assert voc_mock.await_count == 1
    assert state.before_synth_hook_fired is True

    # Reset FSM so the second call's trigger condition is still satisfied.
    state.current_state = AgentState.ANALYZING
    handled = await orch._maybe_run_before_synth_meta_judge()
    assert handled is False
    assert voc_mock.await_count == 1  # NOT invoked again


@pytest.mark.asyncio
async def test_meta_judge_before_synth_skipped_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", False)
    voc_mock = AsyncMock(side_effect=AssertionError("VoC must not run when disabled"))
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", voc_mock
    )

    state = _state()
    _with_pending_claims_and_evidence(state, n_evidence=50)
    orch, _events = _orch(state)

    handled = await orch._maybe_run_before_synth_meta_judge()
    assert handled is False
    assert state.before_synth_hook_fired is False


@pytest.mark.asyncio
async def test_meta_judge_before_synth_skipped_on_fast_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    voc_mock = AsyncMock(side_effect=AssertionError("VoC must not run on FAST"))
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", voc_mock
    )

    state = _state(selected_lane=Lane.FAST)
    _with_pending_claims_and_evidence(state, n_evidence=50)
    orch, _events = _orch(state)

    handled = await orch._maybe_run_before_synth_meta_judge()
    assert handled is False
    assert state.before_synth_hook_fired is False


@pytest.mark.asyncio
async def test_meta_judge_before_synth_skipped_below_threshold_and_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No trigger: claims not resolved AND evidence < threshold."""
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_before_synth_min_evidence", 20)
    voc_mock = AsyncMock(side_effect=AssertionError("VoC must not run below threshold"))
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation", voc_mock
    )

    state = _state()
    _with_pending_claims_and_evidence(state, n_evidence=5)
    orch, _events = _orch(state)

    handled = await orch._maybe_run_before_synth_meta_judge()
    assert handled is False
    assert state.before_synth_hook_fired is False


@pytest.mark.asyncio
async def test_meta_judge_before_synth_triggers_when_all_claims_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trigger via the ``all_claims_resolved`` path with low evidence count."""
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_before_synth_min_evidence", 20)
    voc = ValueOfContinuationVerdict(
        decision="stop",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="done",
    )
    _patch_voc(monkeypatch, voc)

    state = _state()  # no sub_claims → all_claims_resolved() is True
    orch, events = _orch(state)
    assert state.all_claims_resolved() is True

    handled = await orch._maybe_run_before_synth_meta_judge()

    assert handled is True
    assert state.current_state == AgentState.DRAFTING
    assert any(isinstance(e, MetaStopVerdictEvent) for e in events)
