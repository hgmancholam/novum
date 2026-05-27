"""Tests for ``app.agent.tasks.classify``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agent.tasks import classify
from app.domain.enums import QuestionType
from app.llm import client as client_module
from app.llm.models import QuestionClassification


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


def _classification(question_type: str, answerable: bool = True) -> QuestionClassification:
    return QuestionClassification(question_type=question_type, rationale="x", answerable=answerable)


@pytest.mark.parametrize(
    ("question_type_str", "expected"),
    [
        ("factual", QuestionType.FACTUAL),
        ("comparative", QuestionType.COMPARATIVE),
        ("definitional", QuestionType.DEFINITIONAL),
        ("causal", QuestionType.CAUSAL),
        ("state_of_art", QuestionType.STATE_OF_ART),
        ("predictive_future", QuestionType.PREDICTIVE_FUTURE),
        ("subjective_opinion", QuestionType.SUBJECTIVE_OPINION),
        ("personal_private", QuestionType.PERSONAL_PRIVATE),
    ],
)
async def test_all_8_question_types_map_correctly(
    mock_create: AsyncMock, question_type_str: str, expected: QuestionType
) -> None:
    """WP-2.0: All 8 question types are answerable and map string to enum."""
    mock_create.return_value = _classification(question_type_str)
    mapped, verdict = await classify.classify_question("q?")
    assert mapped == expected
    assert verdict.question_type == question_type_str


async def test_unrecognized_question_type_raises_error(mock_create: AsyncMock) -> None:
    """Classifier returning unrecognized question_type raises ValueError."""
    mock_create.return_value = _classification("invalid_type")
    with pytest.raises(ValueError, match="unrecognized question_type"):
        await classify.classify_question("q?")


async def test_passes_question_as_user_message(mock_create: AsyncMock) -> None:
    mock_create.return_value = _classification("factual")
    await classify.classify_question("What is X?")
    kwargs: dict[str, Any] = mock_create.call_args.kwargs
    messages = kwargs["messages"]
    assert any(m["role"] == "user" and m["content"] == "What is X?" for m in messages)
