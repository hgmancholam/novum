"""Anthropic provider (Claude family) — routed through litellm."""

from __future__ import annotations

from app.config import settings
from app.llm.providers._litellm_base import _LiteLLMProvider
from app.llm.roles import LLMRole


class AnthropicProvider(_LiteLLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        per_role: dict[LLMRole, str] = {
            r: m
            for r, m in (
                (LLMRole.CLASSIFIER, settings.anthropic_model_classifier),
                (LLMRole.PLANNER, settings.anthropic_model_planner),
                (LLMRole.SYNTHESIZER, settings.anthropic_model_synthesizer),
                (LLMRole.JUDGE, settings.anthropic_model_judge),
            )
            if m
        }
        api_key = (
            settings.anthropic_api_key.get_secret_value()
            if settings.anthropic_api_key is not None
            else None
        )
        super().__init__(
            default_model=settings.anthropic_model,
            per_role_models=per_role,
            custom_llm_provider="anthropic",
            api_key=api_key,
            api_key_env_name="ANTHROPIC_API_KEY",
        )
