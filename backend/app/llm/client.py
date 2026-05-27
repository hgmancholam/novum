"""Single entry point for all LLM calls (``llm.call``).

Wraps ``litellm`` + ``instructor`` to give every agent role a uniform,
structured-output interface backed by GitHub Models. Per
``copilot-instructions.md`` §1, the LLM provider is a *not-seam*: agent
code imports :data:`llm` from this module and never touches ``litellm``
or ``httpx`` directly.
"""

from __future__ import annotations

from typing import Any, TypeVar, cast

import instructor
import litellm
import structlog
import tiktoken
from pydantic import BaseModel

from app.config import settings
from app.llm.prompts import ROLE_PROMPTS
from app.llm.retry import retry_llm
from app.llm.roles import ROLE_CONFIGS, LLMRole

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

# Module-level litellm configuration (ai-services.md §1.1).
litellm.api_base = settings.llm_api_base
litellm.api_key = settings.github_token

# Instructor-patched async client. Tests monkeypatch
# ``app.llm.client.client.chat.completions.create`` directly.
#
# ``instructor.from_litellm`` and ``litellm.acompletion`` are not fully
# typed; we accept that opacity at the boundary and re-establish strict
# typing at the :meth:`LLMClient.call` signature.
#
# ``Mode.JSON`` forces prompt-based JSON output instead of OpenAI tool
# calls, which the meta/Llama-* and deepseek/* models served by GitHub
# Models do not support (they return ``OpenAIException - invalid input
# error`` when ``tools=[...]`` is present).
client: Any = instructor.from_litellm(  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    litellm.acompletion,
    mode=instructor.Mode.JSON,
)


def _has_system_message(messages: list[dict[str, str]]) -> bool:
    return any(m.get("role") == "system" for m in messages)


class LLMClient:
    """Thin client exposing the single :meth:`call` entry point."""

    @retry_llm
    async def call(
        self,
        role: LLMRole,
        messages: list[dict[str, str]],
        response_model: type[T],
    ) -> T:
        """Make a structured LLM call.

        If ``messages`` does not already contain a ``system`` message,
        the role's default system prompt is prepended. The caller stays
        in control whenever they pass their own ``system`` message.
        """
        config = ROLE_CONFIGS[role]

        if not _has_system_message(messages):
            messages = [
                {"role": "system", "content": ROLE_PROMPTS[role]},
                *messages,
            ]

        logger.info(
            "llm_call_start",
            role=role.value,
            model=config.model,
            response_model=response_model.__name__,
        )

        result = await client.chat.completions.create(
            model=config.model,
            # GitHub Models is OpenAI-SDK-compatible (ai-services.md §1.1),
            # so we route through litellm's ``openai`` provider with an
            # explicit ``api_base`` and ``api_key``. The dedicated
            # ``github`` provider in litellm targets a legacy Azure
            # endpoint with a different catalog — do not use it.
            custom_llm_provider="openai",
            api_base=settings.llm_api_base,
            api_key=settings.github_token,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            response_model=response_model,
        )

        logger.info(
            "llm_call_complete",
            role=role.value,
            model=config.model,
            response_model=response_model.__name__,
        )

        return cast("T", result)


llm = LLMClient()


def count_tokens(text: str, model: str = "openai/gpt-5") -> int:
    """Count tokens in ``text`` for the given model.

    Falls back to ``cl100k_base`` when ``encoding_for_model`` does not
    recognise the model id (true for every non-OpenAI GitHub Models
    entry). The result is a hint for budgeting, not an exact accounting
    across families.
    """
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
