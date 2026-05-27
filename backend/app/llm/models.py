"""Pydantic models for structured LLM outputs.

These are the contracts that :func:`app.llm.client.LLMClient.call`
returns. Each model is bound to one of the four LLM roles defined in
:mod:`app.llm.roles`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import AnswerKind


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

    ``question_type`` is one of the 8 ``QuestionType`` enum values (as a
    string in lowercase snake_case: factual, comparative, definitional,
    state_of_art, causal, predictive_future, subjective_opinion,
    personal_private).
    """

    question_type: str
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


class ScenarioBranch(BaseModel):
    """A scenario branch for predictive/future questions."""

    label: str
    probability_band: str = Field(..., pattern="^(low|medium|high)$")
    summary: str
    drivers: list[str]


class WeightedCandidate(BaseModel):
    """A weighted candidate for comparative questions with disagreement."""

    label: str
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: str


class TradeoffCriterion(BaseModel):
    """A tradeoff criterion for subjective opinion questions."""

    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    notes: str


class SynthesizedAnswer(BaseModel):
    """Final answer produced by the synthesizer."""

    prose: str = Field(..., description="Natural-language answer")
    # Optional: synthesizer prompts for non-DIRECT kinds may omit key_points
    # in favour of the kind-specific payload (scenarios/candidates/...).
    key_points: list[str] = Field(default_factory=list, description="Main points covered")
    citations: list[str] = Field(
        default_factory=list, description="URLs of cited evidence"
    )
    gaps: list[str] = Field(
        default_factory=list, description="Known gaps in the evidence"
    )
    # RF-17 (WP-1 additive). Optional in WP-1; required from WP-2 onward when
    # the synthesizer renders one of the six AnswerKind-specific templates.
    answer_kind: AnswerKind | None = Field(default=None)

    # Kind-specific payloads (WP-2) — exactly one populated when answer_kind is set
    scenarios: list[ScenarioBranch] | None = None  # SCENARIO
    candidates: list[WeightedCandidate] | None = None  # WEIGHTED
    criteria: list[TradeoffCriterion] | None = None  # TRADEOFF
    redirect_alternatives: list[str] | None = None  # ETHICAL_REDIRECT
    interpretation: str | None = None  # BEST_EFFORT (top guess)
    alternative_interpretations: list[str] | None = None  # BEST_EFFORT

    # Cross-kind surfacing (G5 / G10) — visible to user
    contradictions: list[str] | None = None
    remaining_uncertainties: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)

    @model_validator(mode="after")
    def _validate_kind_specific_fields(self, info) -> SynthesizedAnswer:
        """Validate that the correct kind-specific field is populated.

        Also enforces G10: when the run has contradictions, the synthesizer
        must populate the contradictions field.
        """
        if self.answer_kind is None:
            # Back-compat with WP-1 callers
            return self

        # Map each kind to its required field
        kind_field_map = {
            AnswerKind.SCENARIO: "scenarios",
            AnswerKind.WEIGHTED: "candidates",
            AnswerKind.TRADEOFF: "criteria",
            AnswerKind.ETHICAL_REDIRECT: "redirect_alternatives",
            AnswerKind.BEST_EFFORT: "interpretation",
            AnswerKind.DIRECT: None,  # Uses prose/key_points/citations
        }

        # Check that the right field is populated
        required_field = kind_field_map.get(self.answer_kind)
        if required_field:
            if getattr(self, required_field) is None:
                raise ValueError(
                    f"answer_kind={self.answer_kind.value} requires field "
                    f"'{required_field}' to be populated"
                )
            # Ensure other kind-specific fields are None
            for field_name in [
                "scenarios",
                "candidates",
                "criteria",
                "redirect_alternatives",
                "interpretation",
            ]:
                if field_name != required_field and getattr(self, field_name) is not None:
                    raise ValueError(
                        f"answer_kind={self.answer_kind.value} must not populate "
                        f"'{field_name}'"
                    )

        # G10: contradiction enforcement
        context = info.context or {}
        requires_contradictions = context.get("_requires_contradictions", False)
        if requires_contradictions and not self.contradictions:
            raise ValueError(
                "contradictions required: run surfaced ContradictionDetectedEvent "
                "but synthesizer omitted them"
            )

        return self


class JudgeVerdict(BaseModel):
    """Verdict from the cross-family judge (RF-12, RF-15, WP-5 extensions)."""

    confidence: float = Field(..., ge=0.0, le=1.0, description="Judge confidence J")
    verdict: str = Field(..., description="approve/reject/needs_revision")
    rationale: str = Field(..., description="Explanation of the verdict")
    improvements: list[str] = Field(default_factory=list)
    factual_errors: list[str] = Field(default_factory=list)

    # WP-5: Judge verifier extensions (all optional with defaults for backward compat)
    coherence: float = Field(1.0, ge=0.0, le=1.0, description="Logical consistency score")
    contradictions_detected: list[str] = Field(
        default_factory=list,
        description="Specific contradictions the judge found",
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence gaps the judge identified",
    )
    kind_appropriateness: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="How well the answer_kind fits the question (WP-3 G5)",
    )

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
