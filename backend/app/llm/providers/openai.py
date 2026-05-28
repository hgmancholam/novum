"""OpenAI provider (GPT family) — routed through litellm."""

from __future__ import annotations

from app.config import settings
from app.llm.providers._litellm_base import _LiteLLMProvider
from app.llm.roles import LLMRole


class OpenAIProvider(_LiteLLMProvider):
    name = "openai"

    def __init__(self) -> None:
        per_role: dict[LLMRole, str] = {
            r: m
            for r, m in (
                (LLMRole.CLASSIFIER, settings.openai_model_classifier),
                (LLMRole.PLANNER, settings.openai_model_planner),
                (LLMRole.SYNTHESIZER, settings.openai_model_synthesizer),
                (LLMRole.JUDGE, settings.openai_model_judge),
            )
            if m
        }
        api_key = (
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key is not None
            else None
        )
        super().__init__(
            default_model=settings.openai_model,
            per_role_models=per_role,
            custom_llm_provider="openai",
            api_key=api_key,
            api_key_env_name="OPENAI_API_KEY",
        )
