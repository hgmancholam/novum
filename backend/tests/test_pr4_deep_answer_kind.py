"""PR-4 unit tests — DEEP lane populates ``answer_kind`` + structural confidence.

Verifies the two invariants the 29/05 Q7 run broke:

* ``state.selected_answer_kind`` is stamped right after hypotheses are
  generated, so the StoppedEvent never carries ``answer_kind=None`` on a
  DEEP run.
* ``state.last_structural_confidence`` is populated on best-effort stops,
  so ``StopRationale.confidence`` (and the UI) shows a real score instead
  of "0 % Research Limit Reached".
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.lanes.deep import execute_deep_lane
from app.agent.react.actions import SearchAction
from app.agent.react.loop import ThoughtOutput
from app.agent.run_state import RunState
from app.agent.tasks.hypotheses import HypothesesList, HypothesisDraft
from app.domain.enums import AnswerKind, Lane, StopReason
from app.llm import MiniJudgeVerdict
from app.llm.models import SynthesizedAnswer
from app.seams.source import SourceResult


class _MockSource:
    def __init__(self, results: list[SourceResult]) -> None:
        self._results = results

    async def search(self, query: str, max_results: int) -> list[SourceResult]:
        return list(self._results[:max_results])


class _MockRegistry:
    def __init__(self, results: list[SourceResult]) -> None:
        self._results = results

    def types(self):
        from app.domain.enums import SourceType

        return [SourceType.WIKIPEDIA, SourceType.TAVILY]

    def get(self, source_type):
        return _MockSource(self._results)


@pytest.mark.asyncio
async def test_deep_lane_stamps_selected_answer_kind_before_react(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After hypotheses are generated, ``state.selected_answer_kind`` is set."""
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", False)

    state = RunState(
        run_id=uuid4(),
        question="Why did the Roman Empire fall?",
        question_type="causal",
        selected_lane=Lane.DEEP,
        max_react_steps=1,
    )

    async def mock_llm_call(role, messages, response_model, **kwargs):
        name = getattr(response_model, "__name__", str(response_model))
        if name == "HypothesesList":
            return HypothesesList(
                items=[
                    HypothesisDraft(text="overextension", priority=0.9),
                    HypothesisDraft(text="economic crisis", priority=0.7),
                ]
            )
        if name == "ThoughtOutput":
            return ThoughtOutput(thought="need more search")
        if "Action" in name or "AgentActionUnion" in str(response_model):
            return SearchAction(query="roman empire fall")
        if name == "SynthesizedAnswer":
            return SynthesizedAnswer(
                prose="Best-effort synthesis.", key_points=[], citations=[], gaps=[]
            )
        if name == "MiniJudgeVerdict":
            return MiniJudgeVerdict(ok=False, j_score=0.4, reason="insufficient")
        if "CoveQuestions" in name:
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(items=["Q"])
        if "CoveVerdict" in name:
            from app.agent.tasks.cove import CoveVerdict

            return CoveVerdict(contradicts=False, evidence="ok")
        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return []

    registry = _MockRegistry(
        [
            SourceResult(
                url="https://example.com/1",
                title="Rome",
                snippet="x",
                relevance_score=0.8,
                source_type="wikipedia",
            )
        ]
    )

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.get_registry", lambda: registry)
    monkeypatch.setattr("app.agent.tasks.cove.get_registry", lambda: registry)

    events: list = []

    async def emit(ev):
        events.append(ev)

    result = await execute_deep_lane(state, emit)

    # selected_answer_kind is populated before any draft event.
    assert state.selected_answer_kind is not None
    assert isinstance(state.selected_answer_kind, AnswerKind)
    # And the run reached a terminal lane outcome.
    assert result in (StopReason.JUDGE_CONFIRMED, StopReason.STOPPED_BY_BUDGET)


@pytest.mark.asyncio
async def test_deep_lane_best_effort_stop_populates_structural_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DEEP best-effort stops, ``last_structural_confidence`` is non-null
    so ``StopRationale.confidence`` shows a real score instead of 0 %.
    """
    monkeypatch.setattr("app.config.settings.meta_judge_enabled", False)

    state = RunState(
        run_id=uuid4(),
        question="What will AI look like in 2040?",
        question_type="predictive_future",
        selected_lane=Lane.DEEP,
        max_react_steps=1,
    )

    async def mock_llm_call(role, messages, response_model, **kwargs):
        name = getattr(response_model, "__name__", str(response_model))
        if name == "HypothesesList":
            return HypothesesList(
                items=[
                    HypothesisDraft(text="LLMs dominate", priority=0.8),
                    HypothesisDraft(text="AGI emerges", priority=0.6),
                ]
            )
        if name == "ThoughtOutput":
            return ThoughtOutput(thought="keep searching")
        if "Action" in name or "AgentActionUnion" in str(response_model):
            return SearchAction(query="ai 2040")
        if name == "SynthesizedAnswer":
            return SynthesizedAnswer(
                prose="Speculative draft.", key_points=[], citations=[], gaps=[]
            )
        if name == "MiniJudgeVerdict":
            return MiniJudgeVerdict(ok=False, j_score=0.3, reason="speculative")
        if "CoveQuestions" in name:
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(items=["Q"])
        if "CoveVerdict" in name:
            from app.agent.tasks.cove import CoveVerdict

            return CoveVerdict(contradicts=False, evidence="ok")
        raise ValueError(f"Unexpected model: {response_model}")

    registry = _MockRegistry(
        [
            SourceResult(
                url="https://example.com/ai",
                title="AI",
                snippet="x",
                relevance_score=0.7,
                source_type="wikipedia",
            )
        ]
    )

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.get_registry", lambda: registry)
    monkeypatch.setattr("app.agent.tasks.cove.get_registry", lambda: registry)

    events: list = []

    async def emit(ev):
        events.append(ev)

    result = await execute_deep_lane(state, emit)

    assert result == StopReason.STOPPED_BY_BUDGET
    assert state.budget_exhausted_kind == "react_steps"
    assert state.selected_answer_kind is not None
    # PR-4 Mejora 4.2: confidence must be populated.
    assert state.last_structural_confidence is not None
    assert 0.0 <= state.last_structural_confidence <= 1.0
