"""Google provider (Gemini family) — routed through litellm."""

from __future__ import annotations

from app.config import settings
from app.llm.providers._litellm_base import _LiteLLMProvider
from app.llm.roles import LLMRole


class GoogleProvider(_LiteLLMProvider):
    name = "google"

    def __init__(self) -> None:
        per_role: dict[LLMRole, str] = {
            r: m
            for r, m in (
                (LLMRole.CLASSIFIER, settings.google_model_classifier),
                (LLMRole.PLANNER, settings.google_model_planner),
                (LLMRole.SYNTHESIZER, settings.google_model_synthesizer),
                (LLMRole.JUDGE, settings.google_model_judge),
            )
            if m
        }
        api_key = (
            settings.google_api_key.get_secret_value()
            if settings.google_api_key is not None
            else None
        )
        super().__init__(
            default_model=settings.google_model,
            # litellm uses ``gemini`` as the provider tag (not ``google``).
            per_role_models=per_role,
            custom_llm_provider="gemini",
            api_key=api_key,
            api_key_env_name="GOOGLE_API_KEY",
        )
