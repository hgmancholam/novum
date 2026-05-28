"""LLM role definitions and model assignments.

Roles are resolved per ``docs/technical-phase/ai-services.md`` §1.2. The
configuration is read once at import time from :mod:`app.config.settings`
so a deployment can override any model via environment variables.

Each role exposes a ``models`` tuple (1..N) used by the LLM client for
round-robin rotation across the GitHub Models catalog, which mitigates
per-model per-minute rate limits. The first entry is the canonical
default and the only one used when no pool is configured.
"""

from __future__ import annotations

from enum import StrEnum
from typing import NamedTuple

from app.config import settings


class LLMRole(StrEnum):
    """The four LLM roles in the Novum research agent (RF-06, RF-12, RF-15).

    IP Área 6 (BRD-26) adds ``META_JUDGE`` which reuses the JUDGE model
    family by default — it answers a different epistemic question
    ("is one more round worth it?") so reusing the family does not
    re-introduce judge/synthesizer entanglement.
    """

    CLASSIFIER = "classifier"
    PLANNER = "planner"
    SYNTHESIZER = "synthesizer"
    JUDGE = "judge"
    META_JUDGE = "meta_judge"


class RoleConfig(NamedTuple):
    """Resolved configuration for an :class:`LLMRole`."""

    models: tuple[str, ...]
    temperature: float
    max_tokens: int
    description: str

    @property
    def model(self) -> str:
        """Primary model for the role (first in rotation pool)."""
        return self.models[0]


def _resolve_pool(pool_csv: str, single: str) -> tuple[str, ...]:
    """Parse a comma-separated model pool, falling back to ``single``."""
    items = tuple(m.strip() for m in pool_csv.split(",") if m.strip())
    return items if items else (single,)


ROLE_CONFIGS: dict[LLMRole, RoleConfig] = {
    LLMRole.CLASSIFIER: RoleConfig(
        models=_resolve_pool(
            settings.llm_model_classifier_pool, settings.llm_model_classifier
        ),
        temperature=0.0,
        max_tokens=512,
        description="Question type classifier (RF-06)",
    ),
    LLMRole.PLANNER: RoleConfig(
        models=_resolve_pool(
            settings.llm_model_planner_pool, settings.llm_model_planner
        ),
        temperature=0.2,
        max_tokens=2048,
        description="Sub-claim decomposition planner",
    ),
    LLMRole.SYNTHESIZER: RoleConfig(
        models=_resolve_pool(
            settings.llm_model_synthesizer_pool, settings.llm_model_synthesizer
        ),
        # gpt-5 only supports temperature=1; litellm.drop_params=True
        # would silently coerce, but we set it explicitly to keep the
        # config honest. Determinism for synthesis comes from the prompt,
        # not from sampling temperature.
        temperature=1.0,
        max_tokens=4096,
        description="Final answer synthesizer",
    ),
    LLMRole.JUDGE: RoleConfig(
        models=_resolve_pool(
            settings.llm_model_judge_pool, settings.llm_model_judge
        ),
        temperature=0.0,
        max_tokens=2048,
        description="Cross-family judge for answer evaluation (RF-15)",
    ),
}

# IP Área 6 (BRD-26 §4.3): META_JUDGE reuses the JUDGE config by default.
# A per-deployment override can swap the model pool by setting the env
# vars consumed by ``settings.llm_model_judge_pool``.
ROLE_CONFIGS[LLMRole.META_JUDGE] = ROLE_CONFIGS[LLMRole.JUDGE]._replace(
    description="Meta-judge: Value-of-Continuation + Adversarial Completeness (BRD-26)",
)
