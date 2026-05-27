"""Defensive unwrap for the "model echoes JSON Schema" failure mode.

Some GitHub Models endpoints (Llama-4-Maverick, gpt-4o-mini under
Instructor ``Mode.JSON``) occasionally return the schema definition
wrapped around the actual data. ``_unwrap_schema_envelope`` peels that
wrapper off before Pydantic validation. See ``app/llm/models.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.models import (
    CritiqueOutput,
    JudgeVerdict,
    PlanOutput,
    QuestionClassification,
    QuestionNormalization,
    SynthesizedAnswer,
)


def test_synthesizer_unwraps_schema_envelope() -> None:
    """The exact wire payload that crashed prod (gpt-4o-mini, 2026-05-27)."""
    payload = {
        "description": "Definición de la paloma.",
        "type": "object",
        "title": "SynthesizedAnswer",
        "required": ["prose", "key_points"],
        "properties": {
            "prose": "Una paloma es un ave de la familia Columbidae.",
            "key_points": ["Pertenecen a Columbidae.", "Son gran\u00edvoras."],
            "citations": ["https://es.wikipedia.org/wiki/Columba_livia"],
            "gaps": [],
        },
    }
    answer = SynthesizedAnswer.model_validate(payload)
    assert answer.prose.startswith("Una paloma")
    assert len(answer.key_points) == 2
    assert answer.citations == ["https://es.wikipedia.org/wiki/Columba_livia"]
    assert answer.gaps == []


def test_synthesizer_accepts_correct_payload() -> None:
    payload = {
        "prose": "p",
        "key_points": ["a"],
        "citations": [],
        "gaps": [],
    }
    answer = SynthesizedAnswer.model_validate(payload)
    assert answer.prose == "p"


def test_unwrap_does_not_trigger_when_properties_is_unrelated() -> None:
    """A genuine field called ``properties`` (not a schema envelope) must pass through."""
    payload = {
        "prose": "p",
        "key_points": ["k"],
        "citations": [],
        "gaps": [],
        "properties": "this is not a schema envelope",
    }
    answer = SynthesizedAnswer.model_validate(payload)
    assert answer.prose == "p"


def test_unwrap_does_not_apply_when_inner_lacks_expected_fields() -> None:
    """If ``properties`` looks like a schema definition (no data keys), keep the raw value
    so Pydantic emits its normal ``Field required`` error rather than silently passing."""
    payload = {
        "type": "object",
        "properties": {
            "prose": {"type": "string"},
            "key_points": {"type": "array"},
        },
    }
    with pytest.raises(ValidationError):
        SynthesizedAnswer.model_validate(payload)


@pytest.mark.parametrize(
    "model_cls,inner",
    [
        (
            QuestionClassification,
            {"question_type": "factual", "rationale": "r", "answerable": True},
        ),
        (
            QuestionNormalization,
            {"normalized_question": "q", "was_corrected": False, "language": "en"},
        ),
        (
            PlanOutput,
            {
                "sub_claims": [{"id": "c1", "text": "t", "rationale": "r"}],
                "overall_rationale": "r",
            },
        ),
        (
            JudgeVerdict,
            {
                "confidence": 0.9,
                "verdict": "approve",
                "rationale": "r",
                "improvements": [],
                "factual_errors": [],
            },
        ),
        (
            CritiqueOutput,
            {
                "acceptable": True,
                "summary": "s",
                "issues": [],
                "suggested_changes": [],
            },
        ),
    ],
)
def test_unwrap_applies_to_every_response_model(
    model_cls: type, inner: dict[str, object]
) -> None:
    """All six structured-output models share the defensive validator."""
    envelope = {
        "type": "object",
        "title": model_cls.__name__,
        "properties": inner,
    }
    model_cls.model_validate(envelope)
