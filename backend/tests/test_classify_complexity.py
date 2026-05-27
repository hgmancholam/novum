"""Tests for complexity hint derivation (US-22-1).

Covers TC-01..TC-07:
- TC-01: Trivial fact (short factual single-entity high-conf)
- TC-02: Standard comparative (excludes trivial even if short)
- TC-03: Deep state-of-art (>=16 words)
- TC-04: Multi-entity coercion (2+ entities → standard)
- TC-05: Low-conf no-trivial (< min_trivial_confidence)
- TC-06: Single-entity DEFINITIONAL → trivial
- TC-07: Replay tolerates missing field (None → 1.0 default)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.tasks import classify
from app.domain.enums import ComplexityHint, QuestionType
from app.llm import client as client_module
from app.llm.models import QuestionClassification


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Mock LLM client for classifier responses."""
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


def _classification(
    question_type: str,
    answerable: bool = True,
    confidence: float | None = None,
) -> QuestionClassification:
    return QuestionClassification(
        question_type=question_type,
        rationale="test",
        answerable=answerable,
        confidence=confidence,
    )


async def test_trivial_fact_short_single_entity_high_conf(
    mock_create: AsyncMock,
) -> None:
    """TC-01: Short factual question with single entity → trivial."""
    mock_create.return_value = _classification("factual", confidence=0.90)
    q_type, verdict, hint, signals = await classify.classify_question("Capital of Japan?")
    assert q_type == QuestionType.FACTUAL
    assert hint == ComplexityHint.TRIVIAL
    assert signals["word_count"] <= 8
    assert signals["entity_count"] == 1
    assert signals["single_entity"] is True


async def test_standard_comparative_excludes_trivial(
    mock_create: AsyncMock,
) -> None:
    """TC-02: COMPARATIVE is never trivial even if short."""
    mock_create.return_value = _classification("comparative", confidence=0.95)
    q_type, verdict, hint, signals = await classify.classify_question("X vs Y?")
    assert q_type == QuestionType.COMPARATIVE
    assert hint == ComplexityHint.STANDARD


async def test_deep_state_of_art_long_question(
    mock_create: AsyncMock,
) -> None:
    """TC-03: STATE_OF_ART with >=16 words → deep."""
    mock_create.return_value = _classification("state_of_art", confidence=0.60)
    long_q = "What are the latest advances and emerging trends in distributed consensus algorithms for decentralized blockchain systems and networks?"
    q_type, verdict, hint, signals = await classify.classify_question(long_q)
    assert q_type == QuestionType.STATE_OF_ART
    assert hint == ComplexityHint.DEEP
    assert signals["word_count"] >= 16


async def test_multi_entity_coercion_to_standard(
    mock_create: AsyncMock,
) -> None:
    """TC-04: Two entities → standard (not trivial)."""
    mock_create.return_value = _classification("factual", confidence=0.90)
    q_type, verdict, hint, signals = await classify.classify_question("Tokyo vs Kyoto?")
    assert q_type == QuestionType.FACTUAL
    assert hint == ComplexityHint.STANDARD
    assert signals["entity_count"] >= 2
    assert signals["single_entity"] is False


async def test_low_conf_no_trivial(
    mock_create: AsyncMock,
) -> None:
    """TC-05: Confidence below min_trivial_confidence → standard."""
    mock_create.return_value = _classification("factual", confidence=0.75)
    q_type, verdict, hint, signals = await classify.classify_question("Capital?")
    assert q_type == QuestionType.FACTUAL
    assert hint == ComplexityHint.STANDARD
    assert signals["confidence_floor_met"] is False


async def test_single_entity_definitional_trivial(
    mock_create: AsyncMock,
) -> None:
    """TC-06: DEFINITIONAL with single entity → trivial."""
    mock_create.return_value = _classification("definitional", confidence=0.90)
    q_type, verdict, hint, signals = await classify.classify_question("What is CQRS?")
    assert q_type == QuestionType.DEFINITIONAL
    assert hint == ComplexityHint.TRIVIAL
    assert signals["entity_count"] == 1


async def test_replay_tolerates_missing_confidence(
    mock_create: AsyncMock,
) -> None:
    """TC-07: Classifier omits confidence → defaults to 1.0."""
    mock_create.return_value = _classification("factual", confidence=None)
    q_type, verdict, hint, signals = await classify.classify_question("Tokyo?")
    # With confidence=1.0 default, short factual single-entity → trivial
    assert hint == ComplexityHint.TRIVIAL
