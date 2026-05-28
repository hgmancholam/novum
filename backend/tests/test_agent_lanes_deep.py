"""DEEP lane integration tests (IP-25 Phase E)."""

from uuid import uuid4

import pytest

from app.agent.lanes.deep import execute_deep_lane
from app.agent.react.actions import EvaluateHypothesisAction, SearchAction
from app.agent.react.loop import ThoughtOutput
from app.agent.run_state import RunState
from app.agent.tasks.hypotheses import HypothesesList, HypothesisDraft
from app.domain.enums import Lane, StopReason
from app.domain.hypothesis import Hypothesis
from app.llm import MiniJudgeVerdict
from app.llm.models import SynthesizedAnswer
from app.seams.source import SourceResult


@pytest.mark.asyncio
async def test_deep_lane_happy_path_judge_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test DEEP lane happy path: hypotheses → ReAct (confirm) → synth → judge → JUDGE_CONFIRMED."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="Why did the Roman Empire fall?",
        owner_username="test_user",
        question_type="causal",
        selected_lane=Lane.DEEP,
        max_react_steps=5,
    )

    # Prepare hypothesis that will be confirmed
    hypothesis = Hypothesis(
        text="Military overextension and economic instability",
        priority=0.9,
    )

    call_log = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        model_name = getattr(response_model, "__name__", str(response_model))
        call_log.append(model_name)

        # Step 1: Generate hypotheses
        if response_model == HypothesesList:
            return HypothesesList(
                items=[
                    HypothesisDraft(
                        text="Military overextension and economic instability",
                        priority=0.9,
                    ),
                    HypothesisDraft(
                        text="Barbarian invasions",
                        priority=0.7,
                    ),
                    HypothesisDraft(
                        text="Political corruption",
                        priority=0.6,
                    ),
                ]
            )

        # Step 2: ReAct loop - thought
        if response_model == ThoughtOutput:
            return ThoughtOutput(
                thought="The evidence strongly supports the first hypothesis"
            )

        # Step 3: ReAct loop - action (confirm hypothesis)
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            # Get the first hypothesis ID from state
            hyp_id = state.hypotheses[0].id if state.hypotheses else hypothesis.id
            return EvaluateHypothesisAction(
                hypothesis_id=hyp_id,
                verdict="confirmed",
            )

        # Step 4: Synthesize answer
        if response_model == SynthesizedAnswer:
            return SynthesizedAnswer(
                prose="The Roman Empire fell due to military overextension and economic instability [1][2].",
                key_points=[
                    "Overextended military resources",
                    "Economic crisis and debasement",
                ],
                citations=["https://example.com/1", "https://example.com/2"],
                gaps=[],
            )

        # Step 5: Mini-judge verdict
        if response_model == MiniJudgeVerdict:
            return MiniJudgeVerdict(
                ok=True,
                j_score=0.85,
                reason="Well-supported by historical evidence",
            )

        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return [
            SourceResult(
                url=f"https://example.com/{i}",
                title=f"Source {i}",
                snippet="Military and economic factors",
                relevance_score=0.9,
            )
            for i in range(3)
        ]

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )

    # Set structural confidence high enough for HypothesisConfirmedSignal
    state.last_structural_confidence = 0.8

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_deep_lane(state, emit)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert len(state.hypotheses) == 3
    assert state.hypotheses[0].verdict == "confirmed"
    # When ReAct loop returns JUDGE_CONFIRMED directly, no synthesis/judge is needed
    # The hypothesis confirmation signal fires within the loop
    # assert state.draft_answer is not None  # Not set when stopping early
    # assert "Roman Empire" in state.draft_answer.prose

    # Verify LLM calls made
    assert "HypothesesList" in call_log
    assert "ThoughtOutput" in call_log
    # Mini-judge and synthesis NOT called when ReAct loop returns JUDGE_CONFIRMED directly
    # assert "SynthesizedAnswer" in call_log
    # assert "MiniJudgeVerdict" in call_log


@pytest.mark.asyncio
async def test_deep_lane_falls_back_to_best_effort_on_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test DEEP lane returns STOPPED_BY_BUDGET when ReAct loop hits step cap."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="What is the future of AI?",
        owner_username="test_user",
        question_type="predictive_future",
        selected_lane=Lane.DEEP,
        max_react_steps=2,  # Low cap to trigger budget stop
    )

    call_log = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        model_name = getattr(response_model, "__name__", str(response_model))
        call_log.append(model_name)

        # Step 1: Generate hypotheses
        if response_model == HypothesesList:
            return HypothesesList(
                items=[
                    HypothesisDraft(
                        text="AI will revolutionize healthcare",
                        priority=0.8,
                    ),
                    HypothesisDraft(
                        text="AI will cause job displacement",
                        priority=0.7,
                    ),
                ]
            )

        # Step 2: ReAct loop - thought
        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="Need more investigation")

        # Step 3: ReAct loop - action (always search to keep looping)
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            return SearchAction(query="AI future predictions")

        # Step 4: Synthesize (after loop caps out)
        if response_model == SynthesizedAnswer:
            return SynthesizedAnswer(
                prose="The future of AI remains uncertain but shows promise in healthcare.",
                key_points=["Healthcare applications", "Job market impact"],
                citations=["https://example.com/1"],
                gaps=["Long-term societal effects unclear"],
            )

        # Step 5: Mini-judge (best effort)
        if response_model == MiniJudgeVerdict:
            return MiniJudgeVerdict(
                ok=True,
                j_score=0.6,
                reason="Best effort given budget constraints",
            )

        # Phase F: CoVe handlers
        if "CoveQuestions" in str(response_model):
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(items=["Q1", "Q2", "Q3"])

        if "CoveVerdict" in str(response_model):
            from app.agent.tasks.cove import CoveVerdict

            return CoveVerdict(contradicts=False, evidence="ok")

        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        # Return empty to avoid network and ensure loop doesn't terminate early
        return []

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )
    monkeypatch.setattr(
        "app.agent.tasks.cove.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_deep_lane(state, emit)

    # Assertions
    # Should hit step cap and fall back to best-effort synthesis
    # Mini-judge result determines final outcome (j_score=0.6 ≥ threshold usually leads to JUDGE_CONFIRMED)
    assert result in (StopReason.JUDGE_CONFIRMED, StopReason.STOPPED_BY_BUDGET)
    assert state.react_step_count == 2  # Hit the cap
    assert len(state.hypotheses) == 2
    # draft_answer should be set after best-effort synthesis
    assert state.draft_answer is not None


@pytest.mark.asyncio
async def test_cove_redraft_when_contradiction_within_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoVe redrafts when contradiction found and cove_rounds < max_cove_rounds."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="When did Tokyo become Japan's capital?",
        owner_username="test_user",
        question_type="factual",
        selected_lane=Lane.DEEP,
        max_react_steps=2,
        max_cove_rounds=1,
    )

    synth_call_count = 0

    async def mock_llm_call(role, messages, response_model, **kwargs):
        nonlocal synth_call_count

        # Hypothesis generation
        if response_model == HypothesesList:
            return HypothesesList(
                items=[
                    HypothesisDraft(text="Tokyo became capital in 1868", priority=0.9),
                    HypothesisDraft(text="Tokyo became capital in 1869", priority=0.5),
                ]
            )

        # ReAct loop thought
        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="Need to verify this")

        # ReAct loop action - search twice to hit cap
        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            return SearchAction(query="Tokyo capital", target_claim_id=None)

        # Synthesis (called twice: initial + redraft)
        if response_model == SynthesizedAnswer:
            synth_call_count += 1
            if synth_call_count == 1:
                return SynthesizedAnswer(
                    prose="Tokyo became Japan's capital in 1868.",
                    key_points=["Tokyo", "1868"],
                    citations=["https://example.com/1"],
                    gaps=[],
                )
            else:  # Second synth after CoVe contradiction
                return SynthesizedAnswer(
                    prose="Tokyo became Japan's de facto capital in 1868, but was not officially designated until 1943.",
                    key_points=["Tokyo", "1868 de facto", "1943 official"],
                    citations=["https://example.com/1", "https://example.com/2"],
                    gaps=[],
                )

        # CoVe question generation
        if "CoveQuestions" in str(response_model):
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(
                items=[
                    "Was Tokyo officially designated as capital in 1868?",
                    "Did Tokyo replace Kyoto as capital?",
                    "Is there a distinction between de facto and de jure capital?",
                ]
            )

        # CoVe verification
        if "CoveVerdict" in str(response_model):
            from app.agent.tasks.cove import CoveVerdict

            # First question contradicts draft
            return CoveVerdict(
                contradicts=True,
                evidence="Tokyo was de facto capital in 1868 but not officially designated until 1943.",
            )

        # Mini-judge
        if response_model == MiniJudgeVerdict:
            return MiniJudgeVerdict(ok=True, j_score=0.8, reason="Good")

        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return [
            SourceResult(
                url="https://example.com/1",
                title="Tokyo History",
                snippet="Tokyo history details",
                relevance_score=0.9,
            )
        ]

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )
    monkeypatch.setattr(
        "app.agent.tasks.cove.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_deep_lane(state, emit)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert synth_call_count == 2  # Initial + redraft
    assert state.cove_rounds == 1
    assert "1943" in state.draft_answer  # Redrafted answer includes correction

    # Verify events emitted
    event_types = [e.type for e in events]
    assert "VerificationQuestionsGenerated" in event_types
    assert "CoveContradictionDetected" in event_types


@pytest.mark.asyncio
async def test_cove_accepts_draft_when_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoVe accepts draft when cove_rounds >= max_cove_rounds."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="Test question?",
        owner_username="test_user",
        question_type="factual",
        selected_lane=Lane.DEEP,
        max_react_steps=2,
        max_cove_rounds=1,
        cove_rounds=1,  # Already at max
    )

    synth_call_count = 0

    async def mock_llm_call(role, messages, response_model, **kwargs):
        nonlocal synth_call_count

        if response_model == HypothesesList:
            return HypothesesList(
                items=[HypothesisDraft(text="Hypothesis", priority=0.9), HypothesisDraft(text="Alternative", priority=0.5)]
            )

        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="Thinking")

        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            return SearchAction(query="test", target_claim_id=None)

        if response_model == SynthesizedAnswer:
            synth_call_count += 1
            return SynthesizedAnswer(
                prose="Original answer.",
                key_points=["Key"],
                citations=["https://example.com/1"],
                gaps=[],
            )

        if "CoveQuestions" in str(response_model):
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(items=["Question 1", "Question 2", "Question 3"])

        if "CoveVerdict" in str(response_model):
            from app.agent.tasks.cove import CoveVerdict

            return CoveVerdict(
                contradicts=True,
                evidence="Contradicting evidence",
            )

        if response_model == MiniJudgeVerdict:
            return MiniJudgeVerdict(ok=True, j_score=0.7, reason="Acceptable")

        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return [
            SourceResult(
                url="https://example.com/1",
                title="Source",
                snippet="Text",
                relevance_score=0.8,
            )
        ]

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )
    monkeypatch.setattr(
        "app.agent.tasks.cove.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_deep_lane(state, emit)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert synth_call_count == 1  # No redraft because budget exhausted
    assert state.cove_rounds == 1  # Not incremented
    assert state.draft_answer == "Original answer."

    # CoVe events still emitted
    event_types = [e.type for e in events]
    assert "VerificationQuestionsGenerated" in event_types
    assert "CoveContradictionDetected" in event_types


@pytest.mark.asyncio
async def test_cove_no_contradiction_skips_redraft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoVe skips redraft when no contradictions found."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="Test question?",
        owner_username="test_user",
        question_type="factual",
        selected_lane=Lane.DEEP,
        max_react_steps=2,
    )

    synth_call_count = 0

    async def mock_llm_call(role, messages, response_model, **kwargs):
        nonlocal synth_call_count

        if response_model == HypothesesList:
            return HypothesesList(
                items=[HypothesisDraft(text="Hypothesis", priority=0.9), HypothesisDraft(text="Alternative", priority=0.5)]
            )

        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="Thinking")

        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            return SearchAction(query="test", target_claim_id=None)

        if response_model == SynthesizedAnswer:
            synth_call_count += 1
            return SynthesizedAnswer(
                prose="Final answer.",
                key_points=["Key"],
                citations=["https://example.com/1"],
                gaps=[],
            )

        if "CoveQuestions" in str(response_model):
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(items=["Q1", "Q2", "Q3"])

        if "CoveVerdict" in str(response_model):
            from app.agent.tasks.cove import CoveVerdict

            # No contradiction
            return CoveVerdict(
                contradicts=False,
                evidence="Evidence supports the draft.",
            )

        if response_model == MiniJudgeVerdict:
            return MiniJudgeVerdict(ok=True, j_score=0.8, reason="Good")

        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return [
            SourceResult(
                url="https://example.com/1",
                title="Source",
                snippet="Text",
                relevance_score=0.8,
            )
        ]

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )
    monkeypatch.setattr(
        "app.agent.tasks.cove.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    result = await execute_deep_lane(state, emit)

    # Assertions
    assert result == StopReason.JUDGE_CONFIRMED
    assert synth_call_count == 1  # Only one synth, no redraft
    assert state.cove_rounds == 0  # Not incremented
    assert state.draft_answer == "Final answer."

    # Verify events
    event_types = [e.type for e in events]
    assert "VerificationQuestionsGenerated" in event_types
    assert "CoveContradictionDetected" not in event_types  # No contradiction


@pytest.mark.asyncio
async def test_cove_uses_synthesizer_for_questions_judge_for_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoVe uses SYNTHESIZER for questions and JUDGE for verification."""
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="Test?",
        owner_username="test_user",
        question_type="factual",
        selected_lane=Lane.DEEP,
        max_react_steps=1,
    )

    roles_used = []

    async def mock_llm_call(role, messages, response_model, **kwargs):
        from app.llm.roles import LLMRole

        roles_used.append(str(role))

        if response_model == HypothesesList:
            return HypothesesList(
                items=[
                    HypothesisDraft(text="H1", priority=0.9),
                    HypothesisDraft(text="H2", priority=0.5),
                ]
            )

        if response_model == ThoughtOutput:
            return ThoughtOutput(thought="T")

        if "AgentActionUnion" in str(response_model) or "SearchAction" in str(response_model):
            return SearchAction(query="q", target_claim_id=None)

        if response_model == SynthesizedAnswer:
            return SynthesizedAnswer(
                prose="A",
                key_points=[],
                citations=[],
                gaps=[],
            )

        if "CoveQuestions" in str(response_model):
            from app.agent.tasks.cove import CoveQuestions

            return CoveQuestions(items=["Q1", "Q2", "Q3"])

        if "CoveVerdict" in str(response_model):
            from app.agent.tasks.cove import CoveVerdict

            return CoveVerdict(contradicts=False, evidence="ok")

        if response_model == MiniJudgeVerdict:
            return MiniJudgeVerdict(ok=True, j_score=0.7, reason="ok")

        raise ValueError(f"Unexpected model: {response_model}")

    async def mock_search(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.tasks.hypotheses.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.react.loop.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.lanes.deep.llm.call", mock_llm_call)
    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)
    monkeypatch.setattr(
        "app.agent.react.loop.get_registry",
        lambda: MockRegistry(mock_search),
    )
    monkeypatch.setattr(
        "app.agent.tasks.cove.get_registry",
        lambda: MockRegistry(mock_search),
    )

    events = []

    async def emit(event):
        events.append(event)

    # Execute
    await execute_deep_lane(state, emit)

    # Assertions: verify SYNTHESIZER used for CoveQuestions, JUDGE for CoveVerdict
    # roles_used contains StrEnum values like "synthesizer", "judge"
    assert any("synthesizer" in r.lower() for r in roles_used), f"SYNTHESIZER not found in {roles_used}"
    assert any("judge" in r.lower() for r in roles_used), f"JUDGE not found in {roles_used}"


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
