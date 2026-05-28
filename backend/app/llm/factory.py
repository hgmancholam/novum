"""Resolves the active LLM provider from ``settings.llm_provider``.

GitHub Models keeps its dedicated path inside :mod:`app.llm.client`
(token + model pool rotation, judge fallback). For every other vendor
we return a litellm-backed :class:`LLMProvider` instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.llm.providers.base import LLMProvider


SUPPORTED_PROVIDERS: tuple[str, ...] = ("github", "openai", "anthropic", "google")


# Provider instances are cached by name so concurrent runs using different
# vendors can each reuse a singleton without thrashing.
_cache: dict[str, LLMProvider] = {}


def get_provider(name: str | None = None) -> LLMProvider:
    """Return a singleton instance of the requested non-github provider.

    When ``name`` is ``None`` the value of ``settings.llm_provider`` is
    used. Raises ``RuntimeError`` for the github provider — that path is
    served directly by :class:`app.llm.client.LLMClient`.
    """
    raw = name if name is not None else settings.llm_provider
    resolved = raw.lower().strip()
    if resolved not in SUPPORTED_PROVIDERS:
        raise RuntimeError(
            f"Unsupported LLM provider='{raw}'. "
            f"Expected one of {SUPPORTED_PROVIDERS}."
        )
    if resolved == "github":
        raise RuntimeError(
            "get_provider() is only valid for non-github providers; "
            "the github path lives inside LLMClient.call."
        )

    cached = _cache.get(resolved)
    if cached is not None:
        return cached

    if resolved == "openai":
        from app.llm.providers.openai import OpenAIProvider

        instance: LLMProvider = OpenAIProvider()
    elif resolved == "anthropic":
        from app.llm.providers.anthropic import AnthropicProvider

        instance = AnthropicProvider()
    elif resolved == "google":
        from app.llm.providers.google import GoogleProvider

        instance = GoogleProvider()
    else:  # pragma: no cover — guarded above
        raise RuntimeError(f"Unhandled provider: {resolved}")

    _cache[resolved] = instance
    return instance


def reset_provider_cache() -> None:
    """Drop cached providers — used by tests that flip ``llm_provider``."""
    _cache.clear()


def available_providers() -> list[dict[str, object]]:
    """Return descriptors of every supported provider for the public API.

    ``available=True`` means the API key is configured (or, for github,
    ``GITHUB_TOKEN`` is set — already required by ``Settings``).
    """
    out: list[dict[str, object]] = []
    for name in SUPPORTED_PROVIDERS:
        if name == "github":
            available = bool(settings.github_token)
            default_model = settings.llm_model_synthesizer
        elif name == "openai":
            available = settings.openai_api_key is not None
            default_model = settings.openai_model
        elif name == "anthropic":
            available = settings.anthropic_api_key is not None
            default_model = settings.anthropic_model
        else:  # google
            available = settings.google_api_key is not None
            default_model = settings.google_model
        out.append(
            {"name": name, "available": available, "default_model": default_model}
        )
    return out
