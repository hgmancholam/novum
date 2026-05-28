"""Tests for WP-2.0 classifier extension to all 8 QuestionType values.

Verifies the classifier can emit all 8 types and the mapping works correctly.
"""

from uuid import uuid4

import pytest

from app.agent.tasks.classify import classify_question
from app.domain.enums import QuestionType
from app.llm import QuestionClassification


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,expected_type,llm_response_string",
    [
        # PREDICTIVE_FUTURE (Type 6)
        (
            "What are the long-term risks of AI-generated code in enterprise systems?",
            QuestionType.PREDICTIVE_FUTURE,
            "predictive_future",
        ),
        (
            "Could AI systems replace mid-level software engineers within the next 10 years?",
            QuestionType.PREDICTIVE_FUTURE,
            "predictive_future",
        ),
        # SUBJECTIVE_OPINION (Type 7)
        (
            "What is the best programming language?",
            QuestionType.SUBJECTIVE_OPINION,
            "subjective_opinion",
        ),
        # PERSONAL_PRIVATE (Type 8)
        (
            "Should I quit my job?",
            QuestionType.PERSONAL_PRIVATE,
            "personal_private",
        ),
        # COMPARATIVE (Q6 cross-check, Fix C)
        (
            "Should a high-scale AI platform use event-driven architecture or synchronous microservices?",
            QuestionType.COMPARATIVE,
            "comparative",
        ),
    ],
)
async def test_classify_emits_new_types(
    question: str,
    expected_type: QuestionType,
    llm_response_string: str,
    mock_llm_call,
) -> None:
    """Classifier returns one of the 3 new types (6/7/8) or COMPARATIVE (Q6)."""
    # Mock the LLM to return the expected type string
    mock_llm_call.return_value = QuestionClassification(
        question_type=llm_response_string,
        rationale=f"This is a {llm_response_string} question",
        answerable=True,
    )

    question_type, verdict, complexity_hint, heuristic_signals = await classify_question(question)

    assert question_type == expected_type
    assert verdict.question_type == llm_response_string
    assert verdict.answerable is True


@pytest.mark.asyncio
async def test_question_classified_event_discriminator_roundtrip(mock_llm_call) -> None:
    """US-22-1 AC-6: QuestionClassifiedEvent round-trips through discriminated union."""
    from pydantic import TypeAdapter

    from app.domain.events import Event, QuestionClassifiedEvent

    mock_llm_call.return_value = QuestionClassification(
        question_type="factual",
        rationale="test",
        answerable=True,
        confidence=0.90,
    )

    # Call classify to get all return values including complexity_hint
    q_type, verdict, hint, signals = await classify_question("Capital of Japan?")

    # Create event
    event = QuestionClassifiedEvent(
        id=uuid4(),
        run_id=uuid4(),
        step_index=1,
        question_type=q_type,
        classifier_confidence=verdict.confidence or 1.0,
        complexity_hint=hint,
        heuristic_signals=signals,
    )

    # Serialize and deserialize through discriminated union
    adapter = TypeAdapter(Event)
    payload = event.model_dump()
    roundtripped = adapter.validate_python(payload)

    assert roundtripped.type == "QuestionClassified"
    assert roundtripped.complexity_hint is not None  # Complexity hint is present (actual value depends on heuristic)
    assert "word_count" in roundtripped.heuristic_signals
