"""Tests for G9 empty-comparative detection (WP-2 classify.py).

Verifies that questions like "best X" or "should I" without explicit
criteria trigger AmbiguityDetectedEvent with dimensions from the LLM.
"""

import pytest

from app.agent.tasks.classify import detect_empty_comparative
from app.domain.enums import QuestionType
from app.domain.events import AmbiguityDetectedEvent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,classified_type",
    [
        ("What is the best programming language?", QuestionType.SUBJECTIVE_OPINION),
        ("¿Cuál es el mejor framework?", QuestionType.SUBJECTIVE_OPINION),
        ("Should I use Rust?", QuestionType.COMPARATIVE),
        ("Vale la pena aprender TypeScript?", QuestionType.SUBJECTIVE_OPINION),
    ],
)
async def test_empty_comparative_triggers_ambiguity(
    question: str,
    classified_type: QuestionType,
    mock_llm_call,
) -> None:
    """Empty comparatives without criteria emit AmbiguityDetectedEvent."""
    # Mock classify_dimensions to return 2 dimensions
    from app.agent.tasks.classify import AmbiguityDimensions

    mock_llm_call.return_value = AmbiguityDimensions(
        dimensions=["Performance", "Ecosystem maturity"]
    )

    event = await detect_empty_comparative(question, classified_type)

    assert event is not None
    assert isinstance(event, AmbiguityDetectedEvent)
    assert event.dimensions is not None
    assert len(event.dimensions) >= 2
    assert "Performance" in event.dimensions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,classified_type",
    [
        (
            "What is the best programming language for embedded systems?",
            QuestionType.COMPARATIVE,
        ),
        (
            "Should I use Rust to build a web API?",
            QuestionType.COMPARATIVE,
        ),
        (
            "¿Cuál es el mejor framework para machine learning?",
            QuestionType.SUBJECTIVE_OPINION,
        ),
    ],
)
async def test_criteria_bound_questions_no_ambiguity(
    question: str,
    classified_type: QuestionType,
    mock_llm_call,
) -> None:
    """Questions with explicit criteria ("for X", "to Y") do NOT trigger."""
    event = await detect_empty_comparative(question, classified_type)

    assert event is None
    # LLM should not be called
    mock_llm_call.assert_not_called()


@pytest.mark.asyncio
async def test_non_comparative_types_no_trigger(mock_llm_call) -> None:
    """FACTUAL or CAUSAL questions never trigger ambiguity detection."""
    event = await detect_empty_comparative(
        "What is the capital of Japan?", QuestionType.FACTUAL
    )

    assert event is None
    mock_llm_call.assert_not_called()
