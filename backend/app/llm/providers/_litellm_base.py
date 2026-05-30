"""Shared litellm-backed provider implementation.

OpenAI, Anthropic and Google all expose OpenAI-compatible structured
output through litellm + instructor. The only per-provider differences
are (a) the model id, (b) the api_key env, and (c) litellm's
``custom_llm_provider`` tag. Subclasses fill in those three details.

The GitHub provider does NOT inherit from this base — its token/model
pool rotation and judge fallback live in :mod:`app.llm.client` for
historical reasons and stay untouched here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

import structlog
from pydantic import BaseModel

if TYPE_CHECKING:
    from app.llm.roles import LLMRole

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class _LiteLLMProvider:
    """Base for vendors reachable through litellm's native routing."""

    name: str = "litellm"

    def __init__(
        self,
        default_model: str,
        per_role_models: dict[LLMRole, str],
        custom_llm_provider: str,
        api_key: str | None,
        api_key_env_name: str,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                f"Provider '{self.name}' selected but {api_key_env_name} is not set. "
                f"Set it in the environment or change LLM_PROVIDER."
            )
        self._default_model = default_model
        self._per_role_models = per_role_models
        self._custom_llm_provider = custom_llm_provider
        self._api_key = api_key

    def model_for(self, role: LLMRole) -> str:
        return self._per_role_models.get(role) or self._default_model

    async def complete(
        self,
        role: LLMRole,
        messages: list[dict[str, str]],
        response_model: type[T],
        temperature: float,
        max_tokens: int,
    ) -> T:
        # Imported lazily so unit tests can monkeypatch
        # ``app.llm.client.client`` before this module is touched.
        from app.llm.client import client

        model = self.model_for(role)
        logger.info(
            "llm_provider_call_start",
            provider=self.name,
            role=role.value,
            model=model,
            response_model=response_model.__name__,
        )
        # Anthropic prompt caching: convert the long stable system message
        # into the structured cache_control form so Claude bills it at 10%
        # input rate on subsequent calls within the 5-min ephemeral TTL.
        # No-op for non-Anthropic providers and when disabled by settings.
        effective_messages = _maybe_apply_anthropic_cache(
            messages, self._custom_llm_provider
        )
        result: Any = await client.chat.completions.create(
            model=model,
            custom_llm_provider=self._custom_llm_provider,
            api_key=self._api_key,
            messages=effective_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=response_model,
            max_retries=1,
        )
        logger.info(
            "llm_provider_call_complete",
            provider=self.name,
            role=role.value,
            model=model,
        )
        return cast("T", result)


def _maybe_apply_anthropic_cache(
    messages: list[dict[str, Any]],
    custom_llm_provider: str,
) -> list[dict[str, Any]]:
    """Rewrite the system message into Anthropic's cache_control form.

    Returns ``messages`` unchanged when the provider is not Anthropic, the
    setting is off, or no system message is present. Otherwise replaces the
    first system message's plain-string ``content`` with the structured
    block list so Claude treats it as a cacheable prefix. Subsequent system
    messages (if any) are left alone — we only cache the largest stable
    prefix per Anthropic's pricing rules.
    """
    if custom_llm_provider != "anthropic":
        return messages
    # Lazy import to avoid a circular dependency at module load.
    from app.config import settings

    if not settings.anthropic_prompt_cache_enabled:
        return messages
    rewritten: list[dict[str, Any]] = []
    cached = False
    for msg in messages:
        if (
            not cached
            and msg.get("role") == "system"
            and isinstance(msg.get("content"), str)
            and msg["content"].strip()
        ):
            rewritten.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": msg["content"],
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            )
            cached = True
        else:
            rewritten.append(msg)
    return rewritten
