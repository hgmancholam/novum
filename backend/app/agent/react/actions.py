"""Agent action types for ReAct loop (IP-25 Phase E T-25-E-02).

Discriminated union of 4 action types with 'type' as discriminator.
All actions inherit from BaseModel with extra="allow" for schema evolution.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import SourceType


class SearchAction(BaseModel):
    """Search action: query the Source seam."""

    model_config = ConfigDict(extra="allow")

    type: Literal["search"] = "search"
    query: str
    source_hint: SourceType | None = None


class DeepFetchAction(BaseModel):
    """Deep fetch action: retrieve full content from a URL."""

    model_config = ConfigDict(extra="allow")

    type: Literal["deep_fetch"] = "deep_fetch"
    url: str


class EvaluateHypothesisAction(BaseModel):
    """Evaluate hypothesis action: mark hypothesis as confirmed or refuted."""

    model_config = ConfigDict(extra="allow")

    type: Literal["evaluate_hypothesis"] = "evaluate_hypothesis"
    hypothesis_id: UUID
    verdict: Literal["confirmed", "refuted"]


class FinishAction(BaseModel):
    """Finish action: terminate the ReAct loop with a reason."""

    model_config = ConfigDict(extra="allow")

    type: Literal["finish"] = "finish"
    reason: str


# Discriminated union using 'type' field as discriminator
AgentActionUnion = Annotated[
    SearchAction | DeepFetchAction | EvaluateHypothesisAction | FinishAction,
    Field(discriminator="type"),
]
