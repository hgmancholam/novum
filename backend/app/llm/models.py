"""Pydantic models for structured LLM outputs.

These are the contracts that :func:`app.llm.client.LLMClient.call`
returns. Each model is bound to one of the four LLM roles defined in
:mod:`app.llm.roles`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


def _unwrap_schema_envelope(cls: type[BaseModel], value: Any) -> Any:
    """Defensive unwrap for the "model echoes JSON Schema" failure mode.

    Some GitHub Models endpoints (Llama-4-Maverick, gpt-4o-mini under
    Instructor ``Mode.JSON``) occasionally return the schema definition
    wrapped around the actual data, e.g.::

        {"type": "object", "title": "X",
         "properties": {"prose": "...", "key_points": [...]},
         "required": [...]}

    instead of the expected ``{"prose": "...", "key_points": [...]}``.
    When we detect that envelope (``properties`` is a dict containing at
    least one of the model's declared fields) we unwrap it before
    Pydantic validation runs. Otherwise pass-through.
    """
    if not isinstance(value, dict):
        return value
    inner = value.get("properties")
    if not isinstance(inner, dict):
        return value
    expected = set(cls.model_fields.keys())
    if expected & set(inner.keys()):
        return inner
    return value


class QuestionClassification(BaseModel):
    """Output of the classifier (RF-06 question typing).

    ``question_type`` follows the eight-bucket taxonomy from
    ``docs/understanding-phase/requirement-understanding.md``: types 1-5
    are answerable by research, types 6-8 must terminate with
    ``honest_unanswerable``.
    """

    question_type: int = Field(..., ge=1, le=8)
    rationale: str
    answerable: bool

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)


class QuestionNormalization(BaseModel):
    """Output of the pre-classifier normalizer.

    Cleans typos / informal phrasing without changing the user's intent
    and detects the language so downstream prompts can reply in kind.
    ``was_corrected`` is True iff ``normalized_question`` differs from
    the raw input in a non-trivial way (more than whitespace).
    """

    normalized_question: str = Field(..., min_length=1)
    was_corrected: bool
    language: str = Field(
        ...,
        description="BCP-47-style code, e.g. 'es', 'en', 'pt'",
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)


class SubClaimOutput(BaseModel):
    """A single sub-claim emitted by the planner."""

    id: str = Field(..., description="Unique identifier like 'c1', 'c2'")
    text: str = Field(..., description="The sub-claim statement")
    rationale: str = Field(..., description="Why this claim is needed")


class PlanOutput(BaseModel):
    """Structured plan emitted by the planner."""

    sub_claims: list[SubClaimOutput] = Field(..., min_length=1, max_length=10)
    overall_rationale: str = Field(
        ..., description="How these claims answer the question"
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)


class SynthesizedAnswer(BaseModel):
    """Final answer produced by the synthesizer."""

    prose: str = Field(..., description="Natural-language answer")
    key_points: list[str] = Field(..., description="Main points covered")
    citations: list[str] = Field(
        default_factory=list, description="URLs of cited evidence"
    )
    gaps: list[str] = Field(
        default_factory=list, description="Known gaps in the evidence"
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)


class JudgeVerdict(BaseModel):
    """Verdict from the cross-family judge (RF-12, RF-15)."""

    confidence: float = Field(..., ge=0.0, le=1.0, description="Judge confidence J")
    verdict: str = Field(..., description="approve/reject/needs_revision")
    rationale: str = Field(..., description="Explanation of the verdict")
    improvements: list[str] = Field(default_factory=list)
    factual_errors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)


class CritiqueOutput(BaseModel):
    """Output of the plan critic step (RF-14)."""

    acceptable: bool = Field(..., description="True if the plan is good enough to execute")
    summary: str = Field(..., description="One-paragraph evaluation")
    issues: list[str] = Field(default_factory=list, description="Concrete problems found")
    suggested_changes: list[str] = Field(
        default_factory=list,
        description="Actionable revisions (only used if acceptable=False)",
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)
