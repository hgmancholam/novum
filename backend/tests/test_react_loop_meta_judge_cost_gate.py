"""Unit tests for the BRD-26 §4.13 cost gate on `after_react_observation`.

Covers IP-26b acceptance criteria AC-26b-01..09: gate predicates, shared
cap across hooks, outcome dispatch, and the `max_react_steps` invariant.
The meta-judge LLM helpers are patched at the `app.agent.meta_judge_hook`
module level so no real LLM calls fire.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.meta_judge_hook import maybe_run_meta_judge
from app.agent.react.actions import SearchAction
from app.agent.react.loop import (
    ThoughtOutput,
    _cost_gate_after_react_ok,
    _synthetic_signal_from_react,
    run_react_loop,
)
from app.agent.run_state import RunState
from app.domain.enums import Lane, StopReason
from app.domain.events import BaseEvent, MetaStopVerdictEvent
from app.domain.hypothesis import Hypothesis
from app.domain.meta_stop import (
    AdversarialCompletenessVerdict,
    Objection,
    ValueOfContinuationVerdict,
)


class _MockSource:
    async def search(self, query: str, max_results: int = 3, days: Any = None) -> list[Any]:
        return []


class _MockRegistry:
    def types(self) -> list[Any]:
        from app.domain.enums import SourceType

        return [SourceType.WIKIPEDIA, SourceType.TAVILY]

    def get(self, source_type: Any) -> _MockSource:
        return _MockSource()


def _state(**overrides: Any) -> RunState:
    defaults: dict[str, Any] = {
        "run_id": uuid4(),
        "question": "Why did X happen?",
        "owner_username": "test_user",
        "selected_lane": Lane.DEEP,
        "confidence_threshold": 0.7,
        "max_judge_attempts": 3,
        "hypotheses": [Hypothesis(text="H1", priority=0.8)],
        "last_structural_confidence": 0.5,
        "last_judge_confidence": 0.5,
        "draft_answer": "draft",
    }
    defaults.update(overrides)
    return RunState(**defaults)


def _patch_react_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock thought + always-search action so the loop is driven by the gate, not the agent."""

    async def mock_llm_call(role: Any, messages: Any, response_model: Any, **kwargs: Any) -> Any:
        if response_model is ThoughtOutput:
            return ThoughtOutput(thought="keep going")
        return SearchAction(query="generic")

    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.get_registry", lambda: _MockRegistry())


def _collector() -> tuple[list[BaseEvent], Any]:
    collected: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)

    return collected, emit


# ---------------------------------------------------------------------------
# Pure-helper tests
# ---------------------------------------------------------------------------


def test_cost_gate_blocked_when_global_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", False)
    monkeypatch.setattr("app.config.settings.meta_judge_after_react_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_react_warmup_steps", 0)
    monkeypatch.setattr("app.config.settings.max_meta_judge_calls_per_run", 10)
    state = _state()
    state.react_step_count = 5
    assert _cost_gate_after_react_ok(state) is False


def test_cost_gate_blocked_when_slice_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_after_react_enabled", False)
    monkeypatch.setattr("app.config.settings.meta_judge_react_warmup_steps", 0)
    monkeypatch.setattr("app.config.settings.max_meta_judge_calls_per_run", 10)
    state = _state()
    state.react_step_count = 5
    assert _cost_gate_after_react_ok(state) is False


def test_cost_gate_blocked_during_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_after_react_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_react_warmup_steps", 2)
    monkeypatch.setattr("app.config.settings.max_meta_judge_calls_per_run", 10)
    state = _state()
    state.react_step_count = 1
    assert _cost_gate_after_react_ok(state) is False
    state.react_step_count = 2
    assert _cost_gate_after_react_ok(state) is True


def test_cost_gate_blocked_when_cap_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_after_react_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_react_warmup_steps", 0)
    monkeypatch.setattr("app.config.settings.max_meta_judge_calls_per_run", 4)
    state = _state()
    state.react_step_count = 5
    state.meta_judge_calls = 4
    assert _cost_gate_after_react_ok(state) is False
    state.meta_judge_calls = 3
    assert _cost_gate_after_react_ok(state) is True


def test_synthetic_signal_uses_last_observation_as_rationale() -> None:
    from app.agent.react.history import ReactStep

    state = _state(last_structural_confidence=0.6, last_judge_confidence=0.4)
    state.react_history.append(
        ReactStep(
            step=0,
            thought="t",
            action=SearchAction(query="q"),
            observation="this is the latest observation text",
        )
    )
    signal = _synthetic_signal_from_react(state)
    assert signal.passed is False
    assert signal.structural_confidence == 0.6
    assert signal.judge_confidence == 0.4
    assert signal.final_confidence == 0.4  # min(0.6, 0.4)
    assert "latest observation" in signal.rationale


def test_synthetic_signal_handles_empty_history() -> None:
    state = _state(last_structural_confidence=None, last_judge_confidence=None)
    signal = _synthetic_signal_from_react(state)
    assert signal.final_confidence == 0.0
    assert signal.rationale == "no_observations_yet"


# ---------------------------------------------------------------------------
# Counter increment (T-26b-F-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_judge_calls_counter_increments_once_per_emission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    voc = ValueOfContinuationVerdict(
        decision="stop_best_effort",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="done",
    )
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation",
        AsyncMock(return_value=voc),
    )

    class _Sig:
        passed = False
        judge_confidence = 0.5
        structural_confidence = 0.5
        final_confidence = 0.5
        rationale = "r"

    state = _state()
    _, emit = _collector()
    for hook in ("after_judge", "after_cove", "after_react_observation"):
        await maybe_run_meta_judge(state, emit, _Sig(), hook=hook)  # type: ignore[arg-type]
    assert state.meta_judge_calls == 3


# ---------------------------------------------------------------------------
# Integration: run_react_loop wiring
# ---------------------------------------------------------------------------


def _enable_gate(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cap: int = 4,
    warmup: int = 2,
) -> None:
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_after_react_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_react_warmup_steps", warmup)
    monkeypatch.setattr("app.config.settings.max_meta_judge_calls_per_run", cap)
    monkeypatch.setattr("app.config.settings.meta_judge_min_delta_s", 0.03)


def _patch_meta_judge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    voc: ValueOfContinuationVerdict,
    ac: AdversarialCompletenessVerdict | None = None,
) -> None:
    monkeypatch.setattr(
        "app.agent.meta_judge_hook.evaluate_value_of_continuation",
        AsyncMock(return_value=voc),
    )
    if ac is not None:
        monkeypatch.setattr(
            "app.agent.meta_judge_hook.generate_adversarial_objections",
            AsyncMock(return_value=ac),
        )


@pytest.mark.asyncio
async def test_gate_default_off_emits_zero_after_react_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-26b-01 — defaults (flag False) keep behaviour unchanged."""
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", True)
    monkeypatch.setattr("app.config.settings.meta_judge_after_react_enabled", False)
    _patch_react_llm(monkeypatch)
    # Patch VoC so any accidental invocation would be loud:
    _patch_meta_judge(
        monkeypatch,
        voc=ValueOfContinuationVerdict(
            decision="stop_best_effort",
            expected_delta_s=0.0,
            next_action_hypothesis=None,
            reason="should not be called",
        ),
    )
    state = _state()
    events, emit = _collector()
    result = await run_react_loop(state, emit, max_steps=4)
    after_react = [
        e
        for e in events
        if isinstance(e, MetaStopVerdictEvent) and e.hook == "after_react_observation"
    ]
    assert after_react == []
    assert state.meta_judge_calls == 0
    assert result == "forced_synth"


@pytest.mark.asyncio
async def test_voc_stop_best_effort_breaks_loop_with_judge_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-26b-04 + PR-6b — VoC `stop_best_effort` returns JUDGE_CONFIRMED."""
    _enable_gate(monkeypatch, cap=10, warmup=2)
    _patch_react_llm(monkeypatch)
    _patch_meta_judge(
        monkeypatch,
        voc=ValueOfContinuationVerdict(
            decision="stop_best_effort",
            expected_delta_s=0.0,
            next_action_hypothesis=None,
            reason="saturated",
        ),
    )
    state = _state()
    events, emit = _collector()
    result = await run_react_loop(state, emit, max_steps=8)
    assert result == StopReason.JUDGE_CONFIRMED
    # warmup=2 means the gate is first checked when state.react_step_count
    # reaches 2 (i.e. after the 2nd observation, step indices 0 and 1).
    # The first MetaStop verdict fires there and breaks the loop.
    assert state.react_step_count == 2
    msv = [
        e
        for e in events
        if isinstance(e, MetaStopVerdictEvent) and e.hook == "after_react_observation"
    ]
    assert len(msv) == 1
    assert state.meta_judge_calls == 1


@pytest.mark.asyncio
async def test_voc_continue_with_ac_all_answered_returns_judge_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-26b-05 — VoC `continue` + AC all_answered → JUDGE_CONFIRMED."""
    _enable_gate(monkeypatch, cap=10, warmup=2)
    _patch_react_llm(monkeypatch)
    ac = AdversarialCompletenessVerdict(
        objections=[
            Objection(text="o1", status="answered_by_evidence"),
            Objection(text="o2", status="answered_by_evidence"),
            Objection(text="o3", status="answered_by_evidence"),
        ]
    )
    _patch_meta_judge(
        monkeypatch,
        voc=ValueOfContinuationVerdict(
            decision="continue",
            expected_delta_s=0.10,
            next_action_hypothesis="next query",
            reason="gap",
        ),
        ac=ac,
    )
    state = _state()
    events, emit = _collector()
    result = await run_react_loop(state, emit, max_steps=8)
    assert result == StopReason.JUDGE_CONFIRMED
    assert state.react_step_count == 2


@pytest.mark.asyncio
async def test_continue_without_terminal_falls_through_to_intra_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`continue` + unanswered AC → loop keeps going, cap eventually clips emissions."""
    _enable_gate(monkeypatch, cap=2, warmup=2)
    _patch_react_llm(monkeypatch)
    ac = AdversarialCompletenessVerdict(
        objections=[
            Objection(text="o1", status="unanswered_no_search_possible"),
            Objection(text="o2", status="unanswered_no_search_possible"),
            Objection(text="o3", status="unanswered_no_search_possible"),
        ]
    )
    _patch_meta_judge(
        monkeypatch,
        voc=ValueOfContinuationVerdict(
            decision="continue",
            expected_delta_s=0.10,
            next_action_hypothesis="next query",
            reason="gap",
        ),
        ac=ac,
    )
    state = _state()
    events, emit = _collector()
    result = await run_react_loop(state, emit, max_steps=8)
    after_react = [
        e
        for e in events
        if isinstance(e, MetaStopVerdictEvent) and e.hook == "after_react_observation"
    ]
    # Cap=2 → at most 2 after_react meta-judge invocations across the run.
    assert len(after_react) <= 2
    assert state.meta_judge_calls <= 2
    # Loop completed via the `max_react_steps` floor: either the loop
    # exits with "forced_synth" (no intra-loop signal) or via the
    # ReactStepCap intra-loop signal that maps to STOPPED_BY_BUDGET.
    # Either way the absolute cap holds (AC-26b-06).
    assert result in ("forced_synth", StopReason.STOPPED_BY_BUDGET)
    assert state.react_step_count == 8


@pytest.mark.asyncio
async def test_worst_case_8_step_run_respects_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-26b-02/06 — cap=4 caps emissions even with VoC always continue."""
    _enable_gate(monkeypatch, cap=4, warmup=2)
    _patch_react_llm(monkeypatch)
    ac = AdversarialCompletenessVerdict(
        objections=[
            Objection(text="o1", status="unanswered_no_search_possible"),
            Objection(text="o2", status="unanswered_no_search_possible"),
            Objection(text="o3", status="unanswered_no_search_possible"),
        ]
    )
    _patch_meta_judge(
        monkeypatch,
        voc=ValueOfContinuationVerdict(
            decision="continue",
            expected_delta_s=0.10,
            next_action_hypothesis="next",
            reason="r",
        ),
        ac=ac,
    )
    state = _state()
    events, emit = _collector()
    await run_react_loop(state, emit, max_steps=8)
    total_meta = [e for e in events if isinstance(e, MetaStopVerdictEvent)]
    assert len(total_meta) <= 4
    assert state.meta_judge_calls <= 4
    # max_react_steps invariant
    assert state.react_step_count == 8


@pytest.mark.asyncio
async def test_cap_is_shared_across_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-26b-02 — pre-existing meta-judge calls count against the cap."""
    _enable_gate(monkeypatch, cap=4, warmup=2)
    _patch_react_llm(monkeypatch)
    ac = AdversarialCompletenessVerdict(
        objections=[
            Objection(text="o1", status="unanswered_no_search_possible"),
            Objection(text="o2", status="unanswered_no_search_possible"),
            Objection(text="o3", status="unanswered_no_search_possible"),
        ]
    )
    _patch_meta_judge(
        monkeypatch,
        voc=ValueOfContinuationVerdict(
            decision="continue",
            expected_delta_s=0.10,
            next_action_hypothesis="next",
            reason="r",
        ),
        ac=ac,
    )
    state = _state()
    # Simulate 2 prior meta-judge calls from `after_judge`/`after_cove`.
    state.meta_judge_calls = 2
    events, emit = _collector()
    await run_react_loop(state, emit, max_steps=8)
    after_react = [
        e
        for e in events
        if isinstance(e, MetaStopVerdictEvent) and e.hook == "after_react_observation"
    ]
    # Only 2 slots left (4 - 2 prior).
    assert len(after_react) <= 2
    assert state.meta_judge_calls <= 4
