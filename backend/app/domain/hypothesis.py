"""Hypothesis model for abductive reasoning (IP-25 Phase D).

Used in causal/scenario/predictive_future questions and DEEP lane
to generate 2-4 competing hypotheses that guide search and synthesis.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Hypothesis(BaseModel):
    """A candidate hypothesis for abductive reasoning."""

    model_config = ConfigDict(extra="allow")

    id: UUID = Field(default_factory=uuid4)
    text: str
    priority: float = Field(ge=0.0, le=1.0)
    verdict: Literal["pending", "confirmed", "refuted"] = "pending"
    evidence_ids: list[UUID] = Field(default_factory=list)
