"""Tests for FAST lane execution (IP-25 Phase C)."""

from uuid import uuid4

import pytest

from app.agent.lanes.fast import execute_fast_lane
from app.agent.run_state import RunState
from app.domain.enums import Lane, QuestionType, StopReason
from app.llm import MiniJudgeVerdict, SynthesizedAnswer
from app.seams.source import SourceResult


@pytest.mark.asyncio
async def test_fast_lane_stops_when_mini_judge_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST lane returns JUDGE_CONFIRMED when mini-judge approves and S ≥ 0.85."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the capital of Japan?",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )

    # Mock search results (6 items for S_effective=1.0)
    mock_results = [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet=f"Evidence snippet {i}",
            relevance_score=0.9,
            source_type="wikipedia",
        )
        for i in range(3)
    ]

    # Mock synthesizer response
    mock_synth = SynthesizedAnswer(
        prose="Tokyo is the capital of Japan [1][2].",
        key_points=[],
        citations=[f"https://example.com/{i}" for i in range(3)],
        gaps=[],
    )

    # Mock mini-judge verdict (ok=True)
    mock_verdict = MiniJudgeVerdict(
        ok=True,
        j_score=0.92,
        reason="Factually correct and well-cited",
    )


    async def mock_search(*args, **kwargs):
        return mock_results

    async def mock_llm_call(role, messages, response_model, **kwargs):
        if response_model == SynthesizedAnswer:
            return mock_synth
        if response_model == MiniJudgeVerdict:
            return mock_verdict
        raise ValueError(f"Unexpected response_model: {response_model}")

    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))
    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    # Collect emitted events
    events = []
    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_fast_lane(state, emit)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert state.draft_answer == mock_synth.prose
    assert state.final_answer == mock_synth.prose
    assert state.last_judge_confidence == 0.92
    assert len(state.evidence) == 6


@pytest.mark.asyncio
async def test_fast_lane_escalates_when_mini_judge_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST lane escalates when mini-judge rejects (ok=False)."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the meaning of life?",
        question_type=QuestionType.DEFINITIONAL,
        selected_lane=Lane.FAST,
    )

    # Mock search results (6 items for S_effective=1.0)
    mock_results = [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet=f"Evidence snippet {i}",
            relevance_score=0.9,
            source_type="wikipedia",
        )
        for i in range(3)
    ]

    # Mock synthesizer response
    mock_synth = SynthesizedAnswer(
        prose="The meaning of life is 42.",
        key_points=[],
        citations=[f"https://example.com/{i}" for i in range(3)],
        gaps=[],
    )

    # Mock mini-judge verdict (ok=False)
    mock_verdict = MiniJudgeVerdict(
        ok=False,
        j_score=0.45,
        reason="Answer is not factually supported by sources",
    )


    async def mock_search(*args, **kwargs):
        return mock_results

    async def mock_llm_call(role, messages, response_model, **kwargs):
        if response_model == SynthesizedAnswer:
            return mock_synth
        if response_model == MiniJudgeVerdict:
            return mock_verdict
        raise ValueError(f"Unexpected response_model: {response_model}")

    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))
    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    events = []
    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_fast_lane(state, emit)

    # Assertions
    assert result == "escalate"


@pytest.mark.asyncio
async def test_fast_lane_escalates_when_s_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST lane escalates when S_effective < 0.85 (insufficient evidence)."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the capital of Japan?",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )

    # Mock search results (only 2 items for S_effective=0.33)
    mock_results = [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet=f"Evidence snippet {i}",
            relevance_score=0.9,
            source_type="wikipedia",
        )
        for i in range(2)
    ]

    async def mock_search(*args, **kwargs):
        return mock_results

    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))

    events = []
    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_fast_lane(state, emit)

    # Assertions
    assert result == "escalate"


@pytest.mark.asyncio
async def test_fast_lane_calls_only_synth_and_mini_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST lane happy path makes exactly 2 LLM calls (synth + mini-judge)."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the capital of France?",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )

    # Mock search results
    mock_results = [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet=f"Evidence snippet {i}",
            relevance_score=0.9,
            source_type="wikipedia",
        )
        for i in range(3)
    ]

    # Mock synthesizer response
    mock_synth = SynthesizedAnswer(
        prose="Paris is the capital of France [1][2].",
        key_points=[],
        citations=[f"https://example.com/{i}" for i in range(3)],
        gaps=[],
    )

    # Mock mini-judge verdict
    mock_verdict = MiniJudgeVerdict(
        ok=True,
        j_score=0.95,
        reason="Correct answer",
    )

    llm_call_count = {"count": 0}

    async def mock_search(*args, **kwargs):
        return mock_results

    async def mock_llm_call(role, messages, response_model, **kwargs):
        llm_call_count["count"] += 1
        if response_model == SynthesizedAnswer:
            return mock_synth
        if response_model == MiniJudgeVerdict:
            return mock_verdict
        raise ValueError(f"Unexpected response_model: {response_model}")

    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))
    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    events = []
    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_fast_lane(state, emit)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert llm_call_count["count"] == 2  # Exactly 2 LLM calls


@pytest.mark.asyncio
async def test_fast_lane_does_not_escalate_for_trivial_factual_static(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR-3 Mejora 3.1+3.2: trivial+static questions clear the bar with a
    single solid hit (no needless STANDARD escalation, G7/G16 regression).
    """
    from app.domain.enums import ComplexityHint, TemporalSensitivity

    state = RunState(
        run_id=uuid4(),
        question="What is the capital of Japan?",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
    )

    mock_results = [
        SourceResult(
            url=f"https://en.wikipedia.org/wiki/Tokyo_{i}",
            title=f"Tokyo {i}",
            snippet="Tokyo is the capital of Japan.",
            relevance_score=0.5,
            source_type="wikipedia",
        )
        for i in range(3)
    ]
    mock_synth = SynthesizedAnswer(
        prose="Tokyo is the capital of Japan [1].",
        key_points=[],
        citations=["https://en.wikipedia.org/wiki/Tokyo_0"],
        gaps=[],
    )
    mock_verdict = MiniJudgeVerdict(ok=True, j_score=0.9, reason="ok")

    async def mock_search(*args, **kwargs):
        return mock_results

    async def mock_llm_call(role, messages, response_model, **kwargs):
        if response_model == SynthesizedAnswer:
            return mock_synth
        if response_model == MiniJudgeVerdict:
            return mock_verdict
        raise ValueError(f"Unexpected response_model: {response_model}")

    monkeypatch.setattr("app.agent.lanes.fast.get_registry", lambda: MockRegistry(mock_search))
    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    events: list = []

    async def emit(event):
        events.append(event)

    result = await execute_fast_lane(state, emit)

    assert result == StopReason.JUDGE_CONFIRMED
    assert state.final_answer == mock_synth.prose


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

    async def search(self, query, max_results, **kwargs):
        return await self._search_fn(query, max_results=max_results)
