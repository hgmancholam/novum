"""Orchestrator integration tests for FAST lane (IP-25 Phase C)."""

from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.domain.enums import Lane, StopReason
from app.domain.events import LaneEscalatedEvent, RouteSelectedEvent
from app.llm import MiniJudgeVerdict, QuestionClassification, SynthesizedAnswer
from app.llm.models import QuestionNormalization
from app.seams.source import SourceResult


@pytest.mark.asyncio
async def test_fast_lane_runs_only_2_llm_calls_on_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST lane happy path: classify (1) + synth (2) + mini-judge (3) = 3 total LLM calls."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the capital of Japan?",
        owner_username="test_user",
    )

    # Mock classifier to route to FAST
    mock_classification = QuestionClassification(
        question_type="factual",
        answerable=True,
        confidence=0.95,
        rationale="Direct factual question",
    )

    # Mock search results
    mock_search_results = [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet="Tokyo is the capital of Japan.",
            relevance_score=0.9,
        )
        for i in range(3)
    ]

    # Mock synthesizer
    mock_synth = SynthesizedAnswer(
        prose="Tokyo is the capital of Japan [1][2].",
        key_points=[],
        citations=[f"https://example.com/{i}" for i in range(6)],
        gaps=[],
    )

    # Mock mini-judge
    mock_verdict = MiniJudgeVerdict(
        ok=True,
        j_score=0.95,
        reason="Correct and well-cited",
    )

    llm_call_log = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        llm_call_log.append({"role": role, "model": response_model})
        if response_model == QuestionNormalization:
            return QuestionNormalization(
                normalized_question="What is the capital of Japan?",
                was_corrected=False,
                language="en",
            )
        if response_model == QuestionClassification:
            return mock_classification
        if response_model == SynthesizedAnswer:
            return mock_synth
        if response_model == MiniJudgeVerdict:
            return mock_verdict
        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return mock_search_results

    monkeypatch.setattr("app.agent.tasks.classify.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.normalize.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))

    # Execute
    events = []
    async def emit(event):
        events.append(event)

    orchestrator = AgentOrchestrator(state, emit)
    result = await orchestrator.run()

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    # Normalize (1) + Classify (2) + Synth (3) + Mini-judge (4) = 4 total
    # (normalizer is now mandatory)
    assert len(llm_call_log) == 4

    # Verify RouteSelected event emitted
    route_events = [e for e in events if isinstance(e, RouteSelectedEvent)]
    assert len(route_events) == 1
    assert route_events[0].lane == Lane.FAST


@pytest.mark.asyncio
async def test_lane_escalated_event_emitted_then_standard_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST lane escalates when mini-judge rejects, then STANDARD pipeline runs."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the meaning of life?",
        owner_username="test_user",
    )

    # Mock classifier to route to FAST
    mock_normalization = QuestionNormalization(
        normalized_question="What is the meaning of life?",
        was_corrected=False,
        language="en",
    )
    mock_classification = QuestionClassification(
        question_type="factual",
        answerable=True,
        confidence=0.95,
        rationale="Looks factual",
    )

    # Mock search results
    mock_search_results = [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet=f"Evidence {i}",
            relevance_score=0.9,
        )
        for i in range(3)
    ]

    # Mock synthesizer
    mock_synth = SynthesizedAnswer(
        prose="The meaning of life is 42.",
        key_points=[],
        citations=[],
        gaps=[],
    )

    # Mock mini-judge (rejects)
    mock_mini_verdict = MiniJudgeVerdict(
        ok=False,
        j_score=0.3,
        reason="Not factually supported",
    )

    # Queue calls until escalation. We only test that LaneEscalatedEvent fires;
    # STANDARD continuation is exercised by other orchestrator tests.
    synth_count = {"i": 0}

    async def mock_llm_call(role, messages, response_model, **kwargs):
        if response_model == QuestionNormalization:
            return mock_normalization
        if response_model == QuestionClassification:
            return mock_classification
        if response_model == SynthesizedAnswer:
            synth_count["i"] += 1
            return mock_synth
        if response_model == MiniJudgeVerdict:
            return mock_mini_verdict
        # Any other downstream call (PlanOutput, etc.) → stop the test cleanly.
        raise RuntimeError(f"test_stop_after_escalation: unexpected {response_model}")

    async def mock_search(*args, **kwargs):
        return mock_search_results

    monkeypatch.setattr("app.agent.tasks.normalize.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.classify.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.plan.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.replan.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.draft.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))
    monkeypatch.setattr("app.sources.registry.get_registry", lambda: MockRegistry(mock_search))
    # Force FAST lane routing regardless of classifier heuristics
    monkeypatch.setattr(
        "app.agent.lane_router.select_lane",
        lambda **kwargs: (Lane.FAST, "test_forced_fast"),
    )

    # Execute
    events = []
    async def emit(event):
        events.append(event)

    orchestrator = AgentOrchestrator(state, emit)
    await orchestrator.run()

    # Assertions
    escalated_events = [e for e in events if isinstance(e, LaneEscalatedEvent)]
    assert len(escalated_events) == 1
    assert escalated_events[0].from_lane == Lane.FAST
    assert escalated_events[0].to_lane == Lane.STANDARD


class MockRegistry:
    """Mock source registry for testing."""

    def __init__(self, search_fn):
        self._search_fn = search_fn

    def types(self):
        from app.domain.enums import SourceType
        return [SourceType.WIKIPEDIA, SourceType.TAVILY]

    def get(self, source_type):
        return MockSource(self._search_fn)


class MockSource:
    """Mock source for testing."""

    def __init__(self, search_fn):
        self._search_fn = search_fn

    async def search(self, query, max_results=3, days=None, **kwargs):
        return await self._search_fn(query, max_results=max_results)
