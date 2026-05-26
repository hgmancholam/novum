"""LLM client integration package.

Public entry points re-exported here:

- :data:`llm` — the singleton client; call ``await llm.call(...)``.
- :class:`LLMClient` — class form (for testing).
- :class:`LLMRole`, :data:`ROLE_CONFIGS`, :class:`RoleConfig` — role wiring.
- Response models for the four roles.
- :func:`count_tokens` — tiktoken-based token estimate.
"""

from __future__ import annotations

from app.llm.client import LLMClient, count_tokens, llm
from app.llm.models import (
    JudgeVerdict,
    PlanOutput,
    QuestionClassification,
    SubClaimOutput,
    SynthesizedAnswer,
)
from app.llm.roles import ROLE_CONFIGS, LLMRole, RoleConfig

__all__ = [
    "ROLE_CONFIGS",
    "JudgeVerdict",
    "LLMClient",
    "LLMRole",
    "PlanOutput",
    "QuestionClassification",
    "RoleConfig",
    "SubClaimOutput",
    "SynthesizedAnswer",
    "count_tokens",
    "llm",
]
