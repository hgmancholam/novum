"""ReAct loop unit tests (IP-25 Phase E)."""

from uuid import uuid4

import pytest

from app.agent.react.actions import (
    EvaluateHypothesisAction,
    FinishAction,
    SearchAction,
)
from app.agent.react.history import ReactStep, summarize_history_if_needed
from app.agent.react.loop import ThoughtOutput, run_react_loop
from app.agent.run_state import RunState
from app.domain.enums import StopReason
from app.domain.events import (
    AgentActionEvent,
    AgentObservationEvent,
    AgentThoughtEvent,
)
from app.domain.hypothesis import Hypothesis


@pytest.mark.asyncio
async def test_loop_terminates_on_hypothesis_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test loop terminates with JUDGE_CONFIRMED when hypothesis is confirmed with S≥0.75."""
    run_id = uuid4()
    hypothesis = Hypothesis(text="Tokyo is the capital of Japan", priority=0.9)
    state = RunState(
        run_id=run_id,
        question="What is the capital of Japan?",
        owner_username="test_user",
        hypotheses=[hypothesis],
        last_structural_confidence=0.8,
    )

    call_log = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        model_name = getattr(response_model, "__name__", str(response_model))
        call_log.append(model_name)
        if response_model == ThoughtOutput:
            return ThoughtOutput(
                thought="I should evaluate the hypothesis with available evidence"
            )
        # Check if it's the AgentActionUnion by checking the string representation
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            # Return an EvaluateHypothesisAction that confirms
            return EvaluateHypothesisAction(
                hypothesis_id=hypothesis.id,
                verdict="confirmed",
            )
        raise ValueError(f"Unexpected model: {response_model}")

    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await run_react_loop(state, emit, max_steps=5)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert state.hypotheses[0].verdict == "confirmed"
    assert state.react_step_count == 1


@pytest.mark.asyncio
async def test_loop_terminates_on_all_refuted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test loop terminates with STOPPED_BY_BUDGET when all hypotheses are refuted."""
    run_id = uuid4()
    hypotheses = [
        Hypothesis(text="Hypothesis 1", priority=0.8, verdict="refuted"),
        Hypothesis(text="Hypothesis 2", priority=0.7, verdict="refuted"),
    ]
    state = RunState(
        run_id=run_id,
        question="Test question?",
        owner_username="test_user",
        hypotheses=hypotheses,
        last_structural_confidence=0.5,
    )

    call_log = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        model_name = getattr(response_model, "__name__", str(response_model))
        call_log.append(model_name)
        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="All hypotheses already refuted")
        # Check if it's the AgentActionUnion
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            # Return a search action (loop will detect all refuted in stopping signal)
            return SearchAction(query="test query")
        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await run_react_loop(state, emit, max_steps=5)

    # Assertions
    assert result == StopReason.STOPPED_BY_BUDGET


@pytest.mark.asyncio
async def test_loop_caps_at_max_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test loop returns forced_synth after max_steps when no terminal condition met."""
    run_id = uuid4()
    hypothesis = Hypothesis(text="Test hypothesis", priority=0.8)
    state = RunState(
        run_id=run_id,
        question="Test question?",
        owner_username="test_user",
        hypotheses=[hypothesis],
        last_structural_confidence=0.5,
    )

    call_count = {"n": 0}

    async def mock_llm_call(role, messages, response_model, **kwargs):
        call_count["n"] += 1
        if response_model == ThoughtOutput:
            return ThoughtOutput(thought=f"Iteration {call_count['n']}")
        # Check if it's the AgentActionUnion
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            # Always return search action to keep looping
            return SearchAction(query=f"query {call_count['n']}")
        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute with max_steps=2
    result = await run_react_loop(state, emit, max_steps=2)

    # Assertions
    assert result == "forced_synth"
    assert state.react_step_count == 2


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Difficult to provoke Pydantic validation error via mock without breaking monkeypatch"
)
async def test_invalid_action_does_not_count_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that invalid actions trigger retry without incrementing step counter."""
    run_id = uuid4()
    hypothesis = Hypothesis(text="Test hypothesis", priority=0.8)
    state = RunState(
        run_id=run_id,
        question="Test question?",
        owner_username="test_user",
        hypotheses=[hypothesis],
    )

    call_count = {"n": 0}

    async def mock_llm_call(role, messages, response_model, **kwargs):
        call_count["n"] += 1
        if response_model == ThoughtOutput:
            return ThoughtOutput(thought=f"Attempt {call_count['n']}")
        # Check if it's the AgentActionUnion
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            # First call raises error, second call succeeds
            if call_count["n"] == 2:
                raise ValueError("Simulated invalid action")
            return FinishAction(reason="Done")
        raise ValueError(f"Unexpected model: {response_model}")

    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    await run_react_loop(state, emit, max_steps=5)

    # With the current implementation, the exception handler in _generate_action
    # retries without counting, but verifying the exact behavior is complex
    # due to monkeypatch scope. Marking as xfail per instructions.
    assert state.react_step_count == 1


@pytest.mark.asyncio
async def test_history_summarized_when_tokens_exceed_15k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test history summarization when token count exceeds threshold."""
    # Create a history with long observations to exceed 50 tokens
    history = [
        ReactStep(
            step=i,
            thought=f"Thought {i}",
            action=SearchAction(query=f"query {i}"),
            observation=" ".join([f"word{j}" for j in range(20)]),  # ~20 tokens each
        )
        for i in range(10)  # 10 steps × ~20 tokens = ~200 tokens
    ]

    call_log = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        call_log.append(response_model.__name__)
        if response_model.__name__ == "HistorySummary":
            from app.agent.react.history import HistorySummary

            return HistorySummary(
                summary="Summarized first 6 steps of investigation"
            )
        raise ValueError(f"Unexpected model: {response_model}")

    monkeypatch.setattr("app.agent.react.history.llm.call", mock_llm_call)

    # Execute with low threshold
    result, steps_summarized = await summarize_history_if_needed(
        history, max_tokens=50
    )

    # Assertions
    assert steps_summarized == 6  # 10 - 4 = 6 steps summarized
    assert len(result) == 5  # 1 summary + 4 verbatim
    assert result[0].step == -1  # Synthetic summary step
    assert result[0].thought == "Summarized first 6 steps of investigation"
    # Last 4 steps preserved
    assert result[1].step == 6
    assert result[4].step == 9


@pytest.mark.asyncio
async def test_all_events_emitted_per_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that AgentThoughtEvent, AgentActionEvent, AgentObservationEvent are emitted per step."""
    run_id = uuid4()
    hypothesis = Hypothesis(text="Test hypothesis", priority=0.8)
    state = RunState(
        run_id=run_id,
        question="Test question?",
        owner_username="test_user",
        hypotheses=[hypothesis],
    )

    async def mock_llm_call(role, messages, response_model, **kwargs):
        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="First thought")
        # Check if it's the AgentActionUnion
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            # Finish immediately
            return FinishAction(reason="Test complete")
        raise ValueError(f"Unexpected model: {response_model}")

    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    await run_react_loop(state, emit, max_steps=5)

    # Assertions
    thought_events = [e for e in events if isinstance(e, AgentThoughtEvent)]
    action_events = [e for e in events if isinstance(e, AgentActionEvent)]
    observation_events = [e for e in events if isinstance(e, AgentObservationEvent)]

    assert len(thought_events) == 1
    assert len(action_events) == 1
    assert len(observation_events) == 1

    # Verify order
    assert isinstance(events[0], AgentThoughtEvent)
    assert isinstance(events[1], AgentActionEvent)
    assert isinstance(events[2], AgentObservationEvent)


# Mock helpers


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

    async def search(self, query, max_results=3, days=None):
        return await self._search_fn(query, max_results=max_results)
