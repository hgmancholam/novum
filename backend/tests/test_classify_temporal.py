"""BRD-23 WP-1: tests for ``derive_temporal_sensitivity`` heuristic."""

from __future__ import annotations

import pytest

from app.agent.tasks.classify import derive_temporal_sensitivity
from app.domain.enums import QuestionType, TemporalSensitivity


@pytest.mark.parametrize(
    ("question", "qtype", "expected"),
    [
        # realtime markers
        ("What is the current price of bitcoin?", QuestionType.FACTUAL, TemporalSensitivity.REALTIME),
        ("Who is winning right now?", QuestionType.FACTUAL, TemporalSensitivity.REALTIME),
        # recent-year marker → volatile
        ("Best ML framework in 2025?", QuestionType.COMPARATIVE, TemporalSensitivity.VOLATILE),
        # volatile keyword
        ("Latest LLM benchmarks", QuestionType.STATE_OF_ART, TemporalSensitivity.VOLATILE),
        # COMPARATIVE without other signals → volatile (type-based)
        ("PostgreSQL vs MongoDB", QuestionType.COMPARATIVE, TemporalSensitivity.VOLATILE),
        # FACTUAL with no temporal cue → static
        ("What is the capital of Japan?", QuestionType.FACTUAL, TemporalSensitivity.STATIC),
        # DEFINITIONAL with no cue → static
        ("What is CQRS?", QuestionType.DEFINITIONAL, TemporalSensitivity.STATIC),
        # slow-changing marker (population)
        ("Population of Brazil", QuestionType.FACTUAL, TemporalSensitivity.SLOW_CHANGING),
        # explicit old year → slow-changing
        ("Events of 2008 crisis", QuestionType.CAUSAL, TemporalSensitivity.SLOW_CHANGING),
        # CAUSAL with no signal → slow-changing default
        ("Why did the empire fall?", QuestionType.CAUSAL, TemporalSensitivity.SLOW_CHANGING),
    ],
)
def test_derive_temporal_sensitivity(
    question: str, qtype: QuestionType, expected: TemporalSensitivity
) -> None:
    assert derive_temporal_sensitivity(question, qtype) == expected
