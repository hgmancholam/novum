"""Pydantic models for structured LLM outputs.

These are the contracts that :func:`app.llm.client.LLMClient.call`
returns. Each model is bound to one of the four LLM roles defined in
:mod:`app.llm.roles`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class JudgeVerdict(BaseModel):
    """Verdict from the cross-family judge (RF-12, RF-15)."""

    confidence: float = Field(..., ge=0.0, le=1.0, description="Judge confidence J")
    verdict: str = Field(..., description="approve/reject/needs_revision")
    rationale: str = Field(..., description="Explanation of the verdict")
    improvements: list[str] = Field(default_factory=list)
    factual_errors: list[str] = Field(default_factory=list)
