"""LLM provider seam.

Each provider implements :class:`LLMProvider` and is selected at runtime
by :func:`app.llm.factory.get_provider` from ``settings.llm_provider``.
Agent code never imports providers directly; it goes through
``app.llm.client.llm.call``.
"""

from app.llm.providers.base import LLMProvider

__all__ = ["LLMProvider"]
