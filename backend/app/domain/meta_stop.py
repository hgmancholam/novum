"""Pydantic models for the meta-judge layer (BRD-26 §4.2, IP Área 6).

The meta-judge runs *after* the regular judge has produced its verdict and
answers two epistemic questions:

1. ``ValueOfContinuationVerdict`` — "is one more research round worth it?"
2. ``AdversarialCompletenessVerdict`` — "what are the strongest 3 objections
   a skeptical reviewer could raise, and which of them are answered by the
   evidence we already have?"

All models use ``extra="allow"`` so future fields can be added without
breaking replay (RF-03).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ValueOfContinuationVerdict(BaseModel):
    """LLM-produced answer to: 'Is another research round worth it?'"""

    model_config = ConfigDict(extra="allow")

    decision: Literal["stop", "continue", "stop_best_effort"]
    expected_delta_s: float = Field(ge=0.0, le=1.0)
    next_action_hypothesis: str | None = None
    reason: str = Field(min_length=1, max_length=500)


class Objection(BaseModel):
    """A single skeptical objection produced by the adversarial reviewer."""

    model_config = ConfigDict(extra="allow")

    text: str = Field(min_length=1, max_length=500)
    status: Literal[
        "answered_by_evidence",
        "unanswered_needs_search",
        "unanswered_no_search_possible",
    ]
    evidence_ids_answering: list[UUID] = Field(default_factory=list)
    suggested_query: str | None = None


class AdversarialCompletenessVerdict(BaseModel):
    """Result of the adversarial completeness pass.

    Exactly three objections must be produced. ``all_answered`` is derived
    from the objection status list and persisted for the trace UX.
    """

    model_config = ConfigDict(extra="allow")

    objections: list[Objection]
    all_answered: bool = False

    @field_validator("objections")
    @classmethod
    def _validate_objection_count(cls, value: list[Objection]) -> list[Objection]:
        if len(value) != 3:
            raise ValueError("AdversarialCompletenessVerdict requires exactly 3 objections")
        return value

    @model_validator(mode="after")
    def _derive_all_answered(self) -> "AdversarialCompletenessVerdict":
        derived = all(o.status == "answered_by_evidence" for o in self.objections)
        object.__setattr__(self, "all_answered", derived)
        return self
