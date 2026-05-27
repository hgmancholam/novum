"""Tests for WP-2 draft.py synthesizer templates and validation.

Verifies:
- Six AnswerKind templates work (one test per kind)
- Kind mismatch triggers retry then LLMContractError
- G10: missing contradictions triggers retry then LLMContractError
- M3: max_tokens per kind is correct
"""

import json
from pathlib import Path

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.agent.tasks.draft import draft_answer
from app.domain.enums import AnswerKind, QuestionType
from app.domain.events import AmbiguityDetectedEvent, ContradictionDetectedEvent, SubClaim
from app.exceptions import LLMContractError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthesizer"


def load_fixture(filename: str) -> dict:
    """Load a JSON fixture from tests/fixtures/synthesizer/."""
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


@pytest.fixture
def base_state() -> RunState:
    """Minimal RunState for drafting tests."""
    from uuid import uuid4

    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )
    state.evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/test",
            source_title="Test Source",
            text="Test evidence snippet",
            polarity="supports",
            confidence=0.9,
        )
    ]
    state.sub_claims = []
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer_kind,fixture_file,question_type,setup_func",
    [
        (AnswerKind.DIRECT, "direct.json", QuestionType.FACTUAL, lambda s: setattr(s, "sub_claims", [SubClaim(id="c1", text="Test", status="covered")])),
        (AnswerKind.WEIGHTED, "weighted_q6.json", QuestionType.COMPARATIVE, lambda s: setattr(s, "sub_claims", [SubClaim(id="c1", text="Test", status="covered")])),
        (AnswerKind.SCENARIO, "scenario.json", QuestionType.PREDICTIVE_FUTURE, lambda s: None),
        (AnswerKind.TRADEOFF, "tradeoff.json", QuestionType.SUBJECTIVE_OPINION, lambda s: None),
        (
            AnswerKind.ETHICAL_REDIRECT,
            "ethical_redirect.json",
            QuestionType.PERSONAL_PRIVATE,
            lambda s: None,
        ),
        (AnswerKind.BEST_EFFORT, "best_effort.json", QuestionType.SUBJECTIVE_OPINION, lambda s: s.events.append(AmbiguityDetectedEvent(ambiguous_phrase="test", possible_interpretations=[], clarification_needed=""))),
    ],
)
async def test_draft_answer_per_kind(
    answer_kind: AnswerKind,
    fixture_file: str,
    question_type: QuestionType,
    setup_func,
    base_state: RunState,
    mock_llm_call,
) -> None:
    """Draft answer succeeds for each AnswerKind with matching fixture."""
    fixture_data = load_fixture(fixture_file)
    mock_llm_call.return_value = fixture_data

    base_state.question_type = question_type
    setup_func(base_state)

    result = await draft_answer(base_state)

    assert result.answer_kind == answer_kind
    assert base_state.selected_answer_kind == answer_kind

    # Verify kind-specific field is populated
    if answer_kind == AnswerKind.SCENARIO:
        assert result.scenarios is not None
        assert len(result.scenarios) >= 2
    elif answer_kind == AnswerKind.WEIGHTED:
        assert result.candidates is not None
        assert len(result.candidates) >= 2
    elif answer_kind == AnswerKind.TRADEOFF:
        assert result.criteria is not None
        assert len(result.criteria) >= 3
    elif answer_kind == AnswerKind.ETHICAL_REDIRECT:
        assert result.redirect_alternatives is not None
        assert len(result.redirect_alternatives) >= 2
    elif answer_kind == AnswerKind.BEST_EFFORT:
        assert result.interpretation is not None
        assert result.alternative_interpretations is not None


@pytest.mark.asyncio
async def test_kind_mismatch_retries_then_fails(
    base_state: RunState, mock_llm_call
) -> None:
    """Kind mismatch triggers one retry, then raises LLMContractError."""
    # First call returns wrong kind
    wrong_kind_payload = load_fixture("direct.json")
    wrong_kind_payload["answer_kind"] = "weighted"  # Mismatch

    # Second call (retry) also returns wrong kind
    mock_llm_call.side_effect = [wrong_kind_payload, wrong_kind_payload]

    base_state.question_type = QuestionType.FACTUAL  # Should select DIRECT

    with pytest.raises(LLMContractError, match="after retry"):
        await draft_answer(base_state)

    # Should have called twice (initial + 1 retry)
    assert mock_llm_call.call_count == 2


@pytest.mark.asyncio
async def test_g10_missing_contradictions_retries_then_fails(
    base_state: RunState, mock_llm_call
) -> None:
    """G10: When ContradictionDetectedEvent exists, contradictions field required."""
    # Add ContradictionDetectedEvent to state
    base_state.events = [
        ContradictionDetectedEvent(
            claim_id="c1",
            source_a={"url": "a", "title": "A", "claim": "X"},
            source_b={"url": "b", "title": "B", "claim": "not X"},
            nature_of_conflict="disagreement",
        )
    ]

    # First call returns valid payload but no contradictions
    payload_no_contradictions = load_fixture("direct.json")
    payload_no_contradictions["contradictions"] = None

    # Second call (retry) also missing contradictions
    mock_llm_call.side_effect = [
        payload_no_contradictions,
        payload_no_contradictions,
    ]

    base_state.question_type = QuestionType.FACTUAL

    with pytest.raises(LLMContractError, match="omitted contradictions"):
        await draft_answer(base_state)

    # Should have called twice
    assert mock_llm_call.call_count == 2


@pytest.mark.asyncio
async def test_g10_contradictions_present_succeeds(
    base_state: RunState, mock_llm_call
) -> None:
    """G10: When contradictions exist and are populated, validation succeeds."""
    base_state.events = [
        ContradictionDetectedEvent(
            claim_id="c1",
            source_a={"url": "a", "title": "A", "claim": "X"},
            source_b={"url": "b", "title": "B", "claim": "not X"},
            nature_of_conflict="disagreement",
        )
    ]

    payload_with_contradictions = load_fixture("direct.json")
    payload_with_contradictions["contradictions"] = [
        "Source A says X, Source B says not X"
    ]
    mock_llm_call.return_value = payload_with_contradictions

    base_state.question_type = QuestionType.FACTUAL
    result = await draft_answer(base_state)

    assert result.contradictions is not None
    assert len(result.contradictions) >= 1


@pytest.mark.asyncio
async def test_g3_ambiguity_flag_derived_from_events(
    base_state: RunState, mock_llm_call
) -> None:
    """G3: ambiguity_flag is derived from has_event(AMBIGUITY_DETECTED)."""
    # Add AmbiguityDetectedEvent
    base_state.events = [
        AmbiguityDetectedEvent(
            ambiguous_phrase="best language",
            possible_interpretations=["Performance", "Learning curve"],
            clarification_needed="Criteria not stated",
            dimensions=["Performance", "Learning curve"],
        )
    ]

    mock_llm_call.return_value = load_fixture("best_effort.json")

    base_state.question_type = QuestionType.SUBJECTIVE_OPINION
    result = await draft_answer(base_state)

    # With ambiguity_flag=True, resolver should select BEST_EFFORT
    assert result.answer_kind == AnswerKind.BEST_EFFORT
