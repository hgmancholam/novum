"""End-to-end orchestrator tests with mocked LLM and source registry."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.agent.states import AgentState
from app.domain.enums import SourceType, StopReason
from app.domain.events import (
    AgentErroredEvent,
    BaseEvent,
    ClaimCoveredEvent,
    ConfidenceMismatchEvent,
    EvidenceAddedEvent,
    JudgeRuledEvent,
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanRevisedEvent,
    QuestionAskedEvent,
    StoppedEvent,
    ToolCalledEvent,
)
from app.llm import client as client_module
from app.llm.models import (
    CritiqueOutput,
    JudgeVerdict,
    PlanOutput,
    QuestionClassification,
    SubClaimOutput,
    SynthesizedAnswer,
)
from app.seams.source import SourceError, SourceResult
from app.sources import registry as registry_mod
from tests.test_agent_tasks_draft import (  # reuse the inline mapping output
    draft_mod,
)


class _LLMStub:
    """Returns a queued response based on ``response_model`` type."""

    def __init__(self) -> None:
        self._queues: dict[str, list[Any]] = {}

    def queue(self, model_name: str, *values: Any) -> None:
        self._queues.setdefault(model_name, []).extend(values)

    async def __call__(self, *_args: Any, **kwargs: Any) -> Any:
        model = kwargs["response_model"]
        name = model.__name__
        queue = self._queues.get(name, [])
        if not queue:
            raise AssertionError(f"No queued LLM response for {name}")
        return queue.pop(0)


@pytest.fixture
def llm_stub(monkeypatch: pytest.MonkeyPatch) -> _LLMStub:
    stub = _LLMStub()
    monkeypatch.setattr(client_module.client.chat.completions, "create", stub)
    return stub


class _FakeSource:
    def __init__(
        self,
        source_type: SourceType,
        results: list[SourceResult] | None = None,
        error: SourceError | None = None,
    ) -> None:
        self._source_type = source_type
        self._results = results or []
        self._error = error

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def name(self) -> str:
        return self._source_type.value

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        if self._error is not None:
            raise self._error
        return self._results

    async def health_check(self) -> bool:
        return True


class _FakeRegistry:
    def __init__(self, sources: dict[SourceType, _FakeSource]) -> None:
        self._sources = sources

    def get(self, source_type: SourceType) -> _FakeSource:
        return self._sources[source_type]

    def types(self) -> list[SourceType]:
        return list(self._sources.keys())

    def all(self) -> list[_FakeSource]:
        return list(self._sources.values())


def _install_registry(
    monkeypatch: pytest.MonkeyPatch, sources: dict[SourceType, _FakeSource]
) -> None:
    monkeypatch.setattr(registry_mod, "_registry", _FakeRegistry(sources))


def _result(url: str, score: float = 0.8) -> SourceResult:
    return SourceResult(url=url, title=f"t-{url}", snippet=f"snip {url}", relevance_score=score)


def _state(**overrides: Any) -> RunState:
    defaults: dict[str, Any] = {
        "run_id": uuid4(),
        "question": "What is the capital of France?",
        "confidence_threshold": 0.5,
        "max_searches": 5,
        "max_judge_attempts": 3,
        "max_plan_revisions": 2,
    }
    defaults.update(overrides)
    return RunState(**defaults)


def _make_orchestrator(
    state: RunState,
) -> tuple[AgentOrchestrator, list[BaseEvent]]:
    collected: list[BaseEvent] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)

    return AgentOrchestrator(state, emit), collected


def _plan(*ids: str) -> PlanOutput:
    return PlanOutput(
        sub_claims=[SubClaimOutput(id=i, text=f"claim {i}", rationale="r") for i in ids],
        overall_rationale="ok",
    )


def _classify(bucket: int, answerable: bool = True) -> QuestionClassification:
    return QuestionClassification(question_type=bucket, rationale="x", answerable=answerable)


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


async def test_run_happy_path(llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue(
        "CritiqueOutput",
        CritiqueOutput(acceptable=True, summary="ok"),
    )
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="answer", key_points=["k"], citations=["u1"]),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok"),
    )

    tavily = _FakeSource(
        SourceType.TAVILY,
        results=[_result("u1", 0.9), _result("u2", 0.9), _result("u3", 0.9)],
    )
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})

    state = _state()
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.JUDGE_CONFIRMED
    assert state.current_state == AgentState.STOPPED
    types = [type(e).__name__ for e in events]
    assert types[0] == "QuestionAskedEvent"
    assert "PlanCreatedEvent" in types
    assert "PlanCritiquedEvent" in types
    assert "ToolCalledEvent" in types
    assert "EvidenceAddedEvent" in types
    assert "ClaimCoveredEvent" in types
    assert "JudgeRuledEvent" in types
    assert types[-1] == "StoppedEvent"
    stopped = events[-1]
    assert isinstance(stopped, StoppedEvent)
    assert stopped.answer_prose == "answer"


async def test_rf06_unanswerable_stops_before_planning(
    llm_stub: _LLMStub,
) -> None:
    llm_stub.queue("QuestionClassification", _classify(6))

    state = _state()
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.HONEST_UNANSWERABLE
    assert [type(e).__name__ for e in events] == [
        "QuestionAskedEvent",
        "StoppedEvent",
    ]
    stopped = events[-1]
    assert isinstance(stopped, StoppedEvent)
    assert stopped.answer_prose is None


async def test_rf14_max_revisions_then_proceed(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    # First critique rejects, then revise, then critique rejects again,
    # then revise, then critique still rejects (but we've hit cap → proceed).
    llm_stub.queue(
        "CritiqueOutput",
        CritiqueOutput(acceptable=False, summary="bad", issues=["x"]),
        CritiqueOutput(acceptable=False, summary="bad", issues=["x"]),
        CritiqueOutput(acceptable=False, summary="bad", issues=["x"]),
    )
    llm_stub.queue("PlanOutput", _plan("c1"), _plan("c1"))
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="answer", key_points=["k"], citations=[]),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok"),
    )

    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1", 0.9), _result("u2", 0.9)])
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})

    state = _state()
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.JUDGE_CONFIRMED
    assert state.plan_revision_count == 2
    revised_events = [e for e in events if isinstance(e, PlanRevisedEvent)]
    assert len(revised_events) == 2
    critique_events = [e for e in events if isinstance(e, PlanCritiquedEvent)]
    assert len(critique_events) == 3


async def test_budget_exhausted_no_coverage(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1", "c2"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))

    # Source returns nothing → no coverage ever.
    empty = _FakeSource(SourceType.TAVILY, results=[])
    _install_registry(monkeypatch, {SourceType.TAVILY: empty})

    state = _state(max_searches=2)
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.STOPPED_BY_BUDGET
    stopped = events[-1]
    assert isinstance(stopped, StoppedEvent)
    assert stopped.answer_prose is None


async def test_cancel_mid_loop(llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    tavily = _FakeSource(SourceType.TAVILY, results=[])
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})

    state = _state(max_searches=10)
    collected: list[BaseEvent] = []
    orch_holder: list[AgentOrchestrator] = []

    async def emit(ev: BaseEvent) -> None:
        collected.append(ev)
        # Trigger cancel mid-FSM after the plan critique is emitted, then
        # yield so the loop can observe the flag at the next iteration check.
        if isinstance(ev, PlanCritiquedEvent) and orch_holder:
            orch_holder[0].cancel()
        await asyncio.sleep(0)

    orch = AgentOrchestrator(state, emit)
    orch_holder.append(orch)
    reason = await orch.run()
    assert reason == StopReason.USER_CANCELLED
    assert any(isinstance(e, StoppedEvent) for e in collected)


async def test_judge_max_attempts_stops_by_budget_not_silent_confirm(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
    )
    # Judge rejects 3 times with no divergence so no claim re-opening.
    rejection = JudgeVerdict(confidence=0.9, verdict="reject", rationale="no", improvements=[])
    llm_stub.queue("JudgeVerdict", rejection, rejection, rejection)

    tavily = _FakeSource(
        SourceType.TAVILY,
        results=[_result("u1", 0.9), _result("u2", 0.9)],
    )
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})

    state = _state(max_judge_attempts=3, max_searches=10)
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.STOPPED_BY_BUDGET
    judge_events = [e for e in events if isinstance(e, JudgeRuledEvent)]
    assert len(judge_events) == 3
    assert all(not e.passed for e in judge_events)


async def test_rf15_disconfirmation_emits_confidence_mismatch(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
    )
    # Judge rejects with low confidence → S=1.0 (covered), J=0.1 → divergence 0.9 > 0.3
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(
            confidence=0.1,
            verdict="reject",
            rationale="no",
            improvements=["fix c1"],
        ),
        JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok"),
    )
    llm_stub.queue("IssueToClaimMapping", draft_mod.IssueToClaimMapping(claim_ids=["c1"]))

    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1", 0.9), _result("u2", 0.9)])
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})

    state = _state(max_searches=10, max_judge_attempts=3)
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.JUDGE_CONFIRMED
    mismatches = [e for e in events if isinstance(e, ConfidenceMismatchEvent)]
    assert len(mismatches) == 1
    assert mismatches[0].divergence > 0.3


async def test_error_path_emits_agent_errored(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))

    class _ExplodingSource(_FakeSource):
        async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
            raise RuntimeError("boom")

    _install_registry(monkeypatch, {SourceType.TAVILY: _ExplodingSource(SourceType.TAVILY)})

    state = _state()
    orch, events = _make_orchestrator(state)
    reason = await orch.run()

    assert reason == StopReason.ERRORED
    errored = [e for e in events if isinstance(e, AgentErroredEvent)]
    assert len(errored) == 1
    assert errored[0].error_type == "RuntimeError"
    assert state.current_state == AgentState.ERRORED


async def test_illegal_transition_raises() -> None:
    state = _state()
    with pytest.raises(ValueError, match="Invalid transition"):
        state.transition_to(AgentState.DRAFTING)


async def test_evidence_ids_in_claim_covered_match_in_memory(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok"),
    )
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1", 0.9), _result("u2", 0.9)])
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})

    state = _state()
    orch, events = _make_orchestrator(state)
    await orch.run()

    evidence_events = [e for e in events if isinstance(e, EvidenceAddedEvent)]
    covered_events = [e for e in events if isinstance(e, ClaimCoveredEvent)]
    assert len(covered_events) == 1
    in_memory_ids = {ei.event_id for ei in state.evidence}
    emitted_ids = {e.id for e in evidence_events}
    assert emitted_ids == in_memory_ids
    assert set(covered_events[0].evidence_ids) == in_memory_ids


async def test_question_asked_event_emitted_first(
    llm_stub: _LLMStub,
) -> None:
    llm_stub.queue("QuestionClassification", _classify(7))
    state = _state()
    orch, events = _make_orchestrator(state)
    await orch.run()
    assert isinstance(events[0], QuestionAskedEvent)
    assert events[0].question == state.question


async def test_safety_net_honest_unanswerable_after_5_empty_rounds(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    empty = _FakeSource(SourceType.TAVILY, results=[])
    _install_registry(monkeypatch, {SourceType.TAVILY: empty})

    state = _state(max_searches=10)
    orch, _events = _make_orchestrator(state)
    reason = await orch.run()
    assert reason == StopReason.HONEST_UNANSWERABLE


async def test_plan_created_event_emitted(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1", "c2"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1", 0.9), _result("u2", 0.9)])
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok"),
    )

    state = _state()
    orch, events = _make_orchestrator(state)
    await orch.run()

    plan_events = [e for e in events if isinstance(e, PlanCreatedEvent)]
    assert len(plan_events) == 1
    assert {c.id for c in plan_events[0].sub_claims} == {"c1", "c2"}


async def test_tool_called_includes_target_claim(
    llm_stub: _LLMStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_stub.queue("QuestionClassification", _classify(1))
    llm_stub.queue("PlanOutput", _plan("c1"))
    llm_stub.queue("CritiqueOutput", CritiqueOutput(acceptable=True, summary="ok"))
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1", 0.9), _result("u2", 0.9)])
    _install_registry(monkeypatch, {SourceType.TAVILY: tavily})
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(prose="a", key_points=[], citations=[]),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok"),
    )

    state = _state()
    orch, events = _make_orchestrator(state)
    await orch.run()

    tool_events = [e for e in events if isinstance(e, ToolCalledEvent)]
    assert len(tool_events) >= 1
    assert tool_events[0].target_claim_id == "c1"
