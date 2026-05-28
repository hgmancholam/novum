"""Shared protocol for LLM providers.

A provider encapsulates *how* to reach a specific vendor (model id,
auth, transport, retries). The four agent roles (classifier, planner,
synthesizer, judge) are vendor-agnostic and route through whichever
provider :func:`app.llm.factory.get_provider` resolves from
``settings.llm_provider``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

    from app.llm.roles import LLMRole

T = TypeVar("T", bound="BaseModel")


class LLMProvider(Protocol):
    """Vendor-agnostic structured-output contract for a single LLM call."""

    name: str

    def model_for(self, role: LLMRole) -> str:
        """Return the model id this provider uses for ``role`` (for logging)."""
        ...

    async def complete(
        self,
        role: LLMRole,
        messages: list[dict[str, str]],
        response_model: type[T],
        temperature: float,
        max_tokens: int,
    ) -> T:
        """Run a structured chat completion and return the parsed model."""
        ...
