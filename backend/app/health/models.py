"""Pydantic models for the service-health endpoint (BRD-27 §4.4).

``extra="allow"`` on the per-service entry keeps the schema
forward-compatible: future fields like ``budget`` (token usage)
can be added without breaking the contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(StrEnum):
    """The five terminal states for a single service probe."""

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    DISABLED = "disabled"
    NO_KEY = "no_key"


class ServiceCategory(StrEnum):
    """Functional grouping for the bar UI (BRD-27 §4.7)."""

    LLM = "llm"
    SEARCH = "search"
    KNOWLEDGE = "knowledge"
    STORAGE = "storage"


class ServiceHealth(BaseModel):
    """Single service entry in the health bar."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Stable machine id, e.g. 'anthropic'.")
    name: str = Field(..., description="Display name, e.g. 'Anthropic'.")
    category: ServiceCategory
    status: ServiceStatus
    latency_ms: int | None = Field(default=None, ge=0)
    message: str | None = Field(
        default=None,
        description="Tooltip text when status != ok.",
    )
    checked_at: datetime


class HealthSnapshot(BaseModel):
    """Response payload for ``GET /api/health/services``."""

    model_config = ConfigDict(extra="allow")

    checked_at: datetime
    cached: bool
    services: list[ServiceHealth]
