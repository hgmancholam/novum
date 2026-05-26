"""LLM role definitions and model assignments.

Roles are resolved per ``docs/technical-phase/ai-services.md`` §1.2. The
configuration is read once at import time from :mod:`app.config.settings`
so a deployment can override any model via environment variables.
"""

from __future__ import annotations

from enum import StrEnum
from typing import NamedTuple

from app.config import settings


class LLMRole(StrEnum):
    """The four LLM roles in the Novum research agent (RF-06, RF-12, RF-15)."""

    CLASSIFIER = "classifier"
    PLANNER = "planner"
    SYNTHESIZER = "synthesizer"
    JUDGE = "judge"


class RoleConfig(NamedTuple):
    """Resolved configuration for an :class:`LLMRole`."""

    model: str
    temperature: float
    max_tokens: int
    description: str


ROLE_CONFIGS: dict[LLMRole, RoleConfig] = {
    LLMRole.CLASSIFIER: RoleConfig(
        model=settings.llm_model_classifier,
        temperature=0.0,
        max_tokens=512,
        description="Question type classifier (RF-06)",
    ),
    LLMRole.PLANNER: RoleConfig(
        model=settings.llm_model_planner,
        temperature=0.2,
        max_tokens=2048,
        description="Sub-claim decomposition planner",
    ),
    LLMRole.SYNTHESIZER: RoleConfig(
        model=settings.llm_model_synthesizer,
        temperature=0.3,
        max_tokens=4096,
        description="Final answer synthesizer",
    ),
    LLMRole.JUDGE: RoleConfig(
        model=settings.llm_model_judge,
        temperature=0.0,
        max_tokens=2048,
        description="Cross-family judge for answer evaluation (RF-15)",
    ),
}
