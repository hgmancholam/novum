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


def _classification(bucket: int, answerable: bool = True) -> QuestionClassification:
    return QuestionClassification(question_type=bucket, rationale="x", answerable=answerable)


@pytest.mark.parametrize(
    ("bucket", "expected"),
    [
        (1, QuestionType.FACTUAL),
        (2, QuestionType.COMPARATIVE),
        (3, QuestionType.DEFINITIONAL),
        (4, QuestionType.CAUSAL),
        (5, QuestionType.STATE_OF_ART),
    ],
)
async def test_buckets_1_to_5_map_to_question_type(
    mock_create: AsyncMock, bucket: int, expected: QuestionType
) -> None:
    mock_create.return_value = _classification(bucket)
    mapped, verdict = await classify.classify_question("q?")
    assert mapped == expected
    assert verdict.question_type == bucket


@pytest.mark.parametrize("bucket", [6, 7, 8])
async def test_buckets_6_7_8_return_none(mock_create: AsyncMock, bucket: int) -> None:
    mock_create.return_value = _classification(bucket)
    mapped, verdict = await classify.classify_question("q?")
    assert mapped is None
    assert verdict.question_type == bucket


async def test_answerable_false_returns_none(mock_create: AsyncMock) -> None:
    mock_create.return_value = _classification(1, answerable=False)
    mapped, _ = await classify.classify_question("q?")
    assert mapped is None


async def test_passes_question_as_user_message(mock_create: AsyncMock) -> None:
    mock_create.return_value = _classification(1)
    await classify.classify_question("What is X?")
    kwargs: dict[str, Any] = mock_create.call_args.kwargs
    messages = kwargs["messages"]
    assert any(m["role"] == "user" and m["content"] == "What is X?" for m in messages)
