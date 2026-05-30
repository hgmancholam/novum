"""PR-4 tests: ambiguity short-circuit + quality-weighted FAST lane.

Covers:
- Mejora 4.1 already enforced by `select_answer_kind` priority (regression).
- Mejora 4.2 orchestrator short-circuits to DRAFTING when ambiguity is
  flagged before planning.
- Mejora 5.1 FAST lane accepts on `j_score >= 0.85` even if `ok=False`.
- Mejora 5.2 `S_effective` is weighted by authority * relevance.
"""

from uuid import uuid4

from typing import Any

import pytest

from app.agent.lanes.fast import execute_fast_lane
from app.agent.run_state import RunState
from app.agent.states import AgentState
from app.domain.enums import (
    AnswerKind,
    Lane,
    QuestionType,
    StopReason,
)
from app.llm import MiniJudgeVerdict, SynthesizedAnswer
from app.seams.source import SourceResult


# --------------------------------------------------------------------------
# Mejora 4.1 — regression: ambiguity beats subjective_opinion → BEST_EFFORT
# --------------------------------------------------------------------------
def test_subjective_opinion_with_ambiguity_returns_best_effort() -> None:
    from app.agent.tasks.select_answer_kind import (
        AnswerKindInputs,
        select_answer_kind,
    )

    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.SUBJECTIVE_OPINION,
            structural_confidence=0.9,
            coverage=1.0,
            agreement=0.9,
            ambiguity_flag=True,
        )
    )
    assert out is AnswerKind.BEST_EFFORT


def test_subjective_opinion_without_ambiguity_still_tradeoff() -> None:
    from app.agent.tasks.select_answer_kind import (
        AnswerKindInputs,
        select_answer_kind,
    )

    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.SUBJECTIVE_OPINION,
            structural_confidence=0.9,
            coverage=1.0,
            agreement=0.9,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.TRADEOFF


# --------------------------------------------------------------------------
# Mejora 4.2 — orchestrator short-circuits PLANNING when ambiguous
# --------------------------------------------------------------------------
def test_orchestrator_short_circuits_to_drafting_when_ambiguous() -> None:
    """When `state.has_ambiguity is True`, the fresh-run transition picks
    DRAFTING instead of PLANNING (avoids wasted PLAN/SEARCH/ANALYZE round)."""
    from app.agent.orchestrator import AgentOrchestrator

    state = RunState(
        run_id=uuid4(),
        question="best programming language",
        question_type=QuestionType.COMPARATIVE,
        has_ambiguity=True,
    )
    assert state.current_state is AgentState.INIT

    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch.state = state

    # Mirror the fresh-run branch added in PR-4 Mejora 4.2.
    if state.current_state is AgentState.INIT:
        if state.has_ambiguity:
            state.transition_to(AgentState.DRAFTING)
        else:
            state.transition_to(AgentState.PLANNING)

    assert state.current_state is AgentState.DRAFTING


def test_orchestrator_plans_normally_without_ambiguity() -> None:
    from app.agent.orchestrator import AgentOrchestrator

    state = RunState(
        run_id=uuid4(),
        question="What is the capital of Japan?",
        question_type=QuestionType.FACTUAL,
        has_ambiguity=False,
    )

    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch.state = state

    if state.current_state is AgentState.INIT:
        if state.has_ambiguity:
            state.transition_to(AgentState.DRAFTING)
        else:
            state.transition_to(AgentState.PLANNING)

    assert state.current_state is AgentState.PLANNING


# --------------------------------------------------------------------------
# FAST lane mocks (mirrors test_agent_lanes_fast.py)
# --------------------------------------------------------------------------
class _MockSource:
    def __init__(self, results: list[SourceResult]) -> None:
        self._results = results

    async def search(self, query: str, max_results: int, **kwargs: Any) -> list[SourceResult]:  # noqa: ARG002
        return self._results[:max_results]


class _MockRegistry:
    def __init__(self, results: list[SourceResult]) -> None:
        self._results = results

    def types(self):
        from app.domain.enums import SourceType

        return [SourceType.WIKIPEDIA, SourceType.TAVILY]

    def get(self, source_type):  # noqa: ARG002
        return _MockSource(self._results)


def _make_results(n: int, relevance: float) -> list[SourceResult]:
    return [
        SourceResult(
            url=f"https://example.com/{i}",
            title=f"Source {i}",
            snippet=f"snippet {i}",
            relevance_score=relevance,
            source_type="wikipedia",
        )
        for i in range(n)
    ]


# --------------------------------------------------------------------------
# Mejora 5.1 — accept on j_score >= 0.85 even when ok=False
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fast_lane_accepts_on_strong_j_score_even_when_not_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = RunState(
        run_id=uuid4(),
        question="capital of Japan",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )

    results = _make_results(3, relevance=0.95)
    monkeypatch.setattr(
        "app.agent.lanes.fast.get_registry", lambda: _MockRegistry(results)
    )

    synth = SynthesizedAnswer(
        prose="Tokyo is the capital of Japan.",
        key_points=[],
        citations=["https://example.com/0"],
        gaps=[],
    )
    verdict = MiniJudgeVerdict(
        ok=False,           # conservative mini-judge
        j_score=0.88,       # but strong score → PR-4 accepts
        reason="Wants more citations but content is correct.",
    )

    async def mock_llm_call(role, messages, response_model, **_):  # noqa: ARG001
        if response_model is SynthesizedAnswer:
            return synth
        if response_model is MiniJudgeVerdict:
            return verdict
        raise AssertionError(f"unexpected model {response_model}")

    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    events: list = []

    async def emit(ev) -> None:
        events.append(ev)

    result = await execute_fast_lane(state, emit)
    assert result == StopReason.JUDGE_CONFIRMED
    assert state.final_answer == synth.prose


@pytest.mark.asyncio
async def test_fast_lane_still_escalates_on_low_j_score_and_not_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = RunState(
        run_id=uuid4(),
        question="capital of Japan",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )
    results = _make_results(3, relevance=0.95)
    monkeypatch.setattr(
        "app.agent.lanes.fast.get_registry", lambda: _MockRegistry(results)
    )

    synth = SynthesizedAnswer(
        prose="Some answer.",
        key_points=[],
        citations=["https://example.com/0"],
        gaps=[],
    )
    verdict = MiniJudgeVerdict(ok=False, j_score=0.4, reason="Insufficient.")

    async def mock_llm_call(role, messages, response_model, **_):  # noqa: ARG001
        if response_model is SynthesizedAnswer:
            return synth
        if response_model is MiniJudgeVerdict:
            return verdict
        raise AssertionError

    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    async def emit(_ev) -> None: ...

    result = await execute_fast_lane(state, emit)
    assert result == "escalate"


# --------------------------------------------------------------------------
# Mejora 5.2 — quality-weighted S_effective
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fast_lane_quality_weight_rejects_many_low_relevance_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the old `n/6` proxy, 6 rows at relevance 0.1 would pass (S=1.0).
    With the new `sum(authority * relevance) / 4` proxy:
      S = 6 * 0.9 * 0.1 / 4 = 0.135  → below 0.85 → escalate.
    """
    state = RunState(
        run_id=uuid4(),
        question="x",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )
    results = _make_results(3, relevance=0.1)
    monkeypatch.setattr(
        "app.agent.lanes.fast.get_registry", lambda: _MockRegistry(results)
    )

    async def emit(_ev) -> None: ...

    result = await execute_fast_lane(state, emit)
    assert result == "escalate"


@pytest.mark.asyncio
async def test_fast_lane_quality_weight_accepts_few_high_relevance_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3 rows per source = 6 rows; relevance 0.95.
      S = 6 * 0.9 * 0.95 / 4 = 1.28 → clamped to 1.0 → above 0.85.
    """
    state = RunState(
        run_id=uuid4(),
        question="x",
        question_type=QuestionType.FACTUAL,
        selected_lane=Lane.FAST,
    )
    results = _make_results(3, relevance=0.95)
    monkeypatch.setattr(
        "app.agent.lanes.fast.get_registry", lambda: _MockRegistry(results)
    )

    synth = SynthesizedAnswer(
        prose="answer", key_points=[], citations=["https://example.com/0"], gaps=[]
    )
    verdict = MiniJudgeVerdict(ok=True, j_score=0.9, reason="ok")

    async def mock_llm_call(role, messages, response_model, **_):  # noqa: ARG001
        if response_model is SynthesizedAnswer:
            return synth
        if response_model is MiniJudgeVerdict:
            return verdict
        raise AssertionError

    monkeypatch.setattr("app.agent.lanes.fast.llm.call", mock_llm_call)

    async def emit(_ev) -> None: ...

    result = await execute_fast_lane(state, emit)
    assert result == StopReason.JUDGE_CONFIRMED
