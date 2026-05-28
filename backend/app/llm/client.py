"""Single entry point for all LLM calls (``llm.call``).

Wraps ``litellm`` + ``instructor`` to give every agent role a uniform,
structured-output interface backed by GitHub Models. Per
``copilot-instructions.md`` §1, the LLM provider is a *not-seam*: agent
code imports :data:`llm` from this module and never touches ``litellm``
or ``httpx`` directly.

WP-5: Judge role now supports provider routing (Anthropic primary, GitHub
fallback) with JudgeProviderDegradedEvent emission on degradation.
"""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from itertools import cycle
from typing import Any, TypeVar, cast

import instructor
import litellm
import structlog
import tiktoken
from instructor.core import InstructorRetryException
from litellm.exceptions import APIConnectionError, AuthenticationError, RateLimitError
from pydantic import BaseModel

from app.config import settings
from app.llm.prompts import ROLE_PROMPTS
from app.llm.retry import retry_llm
from app.llm.roles import ROLE_CONFIGS, LLMRole

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

# Per-run provider override. The agent runner sets this contextvar at the
# start of ``_supervised_run`` so every ``llm.call`` made inside the
# run's task tree picks the user-chosen vendor without changing any
# call signature. ``None`` means "use settings.llm_provider".
current_provider: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_llm_provider", default=None
)


def resolve_active_provider() -> str:
    """Return the provider name in effect for the current async context."""
    override = current_provider.get()
    if override is not None:
        return override
    return settings.llm_provider

# Module-level litellm configuration (ai-services.md §1.1).
# NOTE: do NOT set ``litellm.api_base`` globally. Each call site passes its
# own ``api_base`` explicitly (GitHub Models uses ``settings.llm_api_base``;
# Google/OpenAI/Anthropic use litellm's defaults for their custom_llm_provider).
# A global override sent every non-GitHub provider's request to the GitHub
# endpoint and yielded misleading ``Unauthorized`` errors.
litellm.api_key = settings.github_token
# Drop provider-unsupported params silently (e.g. gpt-5 rejects any
# ``temperature`` other than 1, gpt-5.1 rejects ``temperature`` unless
# ``reasoning_effort='none'``). Without this every synthesizer call
# would hard-fail. Tested explicitly per role in test_llm_client.py.
litellm.drop_params = True

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


# Per-role round-robin iterators over each role's model pool. Advancing
# the iterator on every call (and on every retry) spreads load across
# the configured GitHub Models entries, mitigating per-model per-minute
# rate limits.
_MODEL_ROTATION: dict[LLMRole, Any] = {
    role: cycle(config.models) for role, config in ROLE_CONFIGS.items()
}


# Round-robin pool of GitHub PATs. Each PAT has an independent rate-limit
# bucket on GitHub Models, so rotating per call gives N x effective RPM.
# Parsed from ``settings.github_tokens`` (CSV); falls back to the single
# ``settings.github_token`` when unset.
_TOKEN_POOL: tuple[str, ...] = tuple(
    t.strip() for t in settings.github_tokens.split(",") if t.strip()
) or (settings.github_token,)
_TOKEN_ROTATION = cycle(_TOKEN_POOL)


def _next_token() -> str:
    """Return the next GitHub PAT from the rotation pool."""
    return cast("str", next(_TOKEN_ROTATION))


class LLMPoolExhausted(RateLimitError):
    """All GitHub PATs in the rotation pool returned 429 in a single
    fallback sweep. Subclasses ``RateLimitError`` so the tenacity layer
    still retries it, but the concrete type lets ``_handle_error`` tag
    the resulting ``AgentErroredEvent`` with ``error_code='llm_pool_rate_limited'``
    so the frontend can surface a "rate limit" modal instead of a
    generic failure UI.
    """

    def __init__(self, pool_size: int) -> None:
        super().__init__(
            f"All {pool_size} GitHub Models PATs are rate-limited.",
            llm_provider="github",
            model="",
        )
        self.pool_size = pool_size


class LLMProviderQuotaExhausted(Exception):
    """User-selected non-github provider returned a permanent quota error.

    Distinct from a transient per-minute rate-limit: covers daily/free-tier
    exhaustion (``insufficient_quota``, ``RESOURCE_EXHAUSTED``, etc.) where
    retrying within the request window cannot succeed. Deliberately NOT a
    subclass of ``RateLimitError`` so tenacity does not retry it — the run
    fails fast and the orchestrator surfaces a clear error to the user.
    """

    def __init__(self, provider: str, original: BaseException) -> None:
        super().__init__(f"Provider '{provider}' quota exhausted: {original}")
        self.provider = provider
        self.original = original


_QUOTA_EXHAUSTED_MARKERS: tuple[str, ...] = (
    "insufficient_quota",
    "resource_exhausted",
    "exceeded your current quota",
    "freetier",
    "per_day",
    "perday",
)


def _is_quota_exhausted(exc: BaseException) -> bool:
    """Return True when ``exc`` signals a non-recoverable provider quota cap."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _QUOTA_EXHAUSTED_MARKERS)


R = TypeVar("R")


def _is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, InstructorRetryException):
        msg = str(exc)
        return "RateLimitError" in msg or "Too many requests" in msg or "429" in msg
    return False


async def _call_with_token_fallback(
    make_call: Callable[[str], Awaitable[R]],
) -> R:
    """Try each PAT in the rotation pool, advancing on rate-limit.

    Only rate-limit errors trigger the inner fallback; any other
    exception propagates immediately so tenacity (or the caller) can
    decide what to do. Raises the last rate-limit exception only when
    *all* tokens in the pool have been exhausted.
    """
    last_exc: BaseException | None = None
    for _ in range(len(_TOKEN_POOL)):
        token = _next_token()
        try:
            return await make_call(token)
        except Exception as exc:
            if _is_rate_limit(exc):
                logger.warning(
                    "llm_token_rate_limited",
                    token_prefix=token[:15],
                )
                last_exc = exc
                continue
            raise
    assert last_exc is not None
    raise LLMPoolExhausted(pool_size=len(_TOKEN_POOL)) from last_exc


# WP-5: Track if we've already degraded the judge provider in this run
# (process-level flag to avoid spamming events on repeated judge calls)
_judge_degraded = False


def _next_model(role: LLMRole) -> str:
    """Return the next model id from ``role``'s rotation pool."""
    return cast("str", next(_MODEL_ROTATION[role]))


def _has_system_message(messages: list[dict[str, str]]) -> bool:
    return any(m.get("role") == "system" for m in messages)


class LLMClient:
    """Thin client exposing the single :meth:`call` entry point."""

    async def _call_judge_with_fallback(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        max_tokens: int | None = None,
    ) -> tuple[T, str | None]:
        """Call judge with provider routing and fallback (WP-5).

        Returns: (result, degraded_event_info or None)
        """
        global _judge_degraded

        config = ROLE_CONFIGS[LLMRole.JUDGE]
        requested_provider = settings.judge_provider
        max_tok = max_tokens if max_tokens is not None else config.max_tokens

        # Attempt 1: Requested provider (anthropic or github)
        if requested_provider == "anthropic" and settings.anthropic_api_key:
            model = "anthropic/claude-haiku-4-5"
            try:
                logger.info("llm_judge_anthropic_attempt", model=model)
                result = await client.chat.completions.create(
                    model=model,
                    custom_llm_provider="anthropic",
                    api_key=settings.anthropic_api_key.get_secret_value(),
                    messages=messages,
                    temperature=config.temperature,
                    max_tokens=max_tok,
                    response_model=response_model,
                    max_retries=1,
                )
                logger.info("llm_judge_anthropic_success", model=model)
                return cast("T", result), None

            except (AuthenticationError, APIConnectionError, RateLimitError) as exc:
                logger.warning(
                    "llm_judge_anthropic_failed",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
                # Fall through to GitHub fallback
                degraded_event = {
                    "requested_provider": "anthropic",
                    "fallback_provider": "github",
                    "error_class": type(exc).__name__,
                }
            except Exception:
                # Unexpected error — re-raise, don't fall back
                raise
        else:
            degraded_event = None

        # Attempt 2: GitHub Models fallback (or primary if judge_provider=="github")
        model = _next_model(LLMRole.JUDGE)  # Use configured judge model (deepseek)
        logger.info("llm_judge_github_attempt", model=model, fallback=degraded_event is not None)

        async def _judge_github(token: str) -> Any:
            return await client.chat.completions.create(
                model=model,
                custom_llm_provider="openai",
                api_base=settings.llm_api_base,
                api_key=token,
                messages=messages,
                temperature=config.temperature,
                max_tokens=max_tok,
                response_model=response_model,
                max_retries=1,
            )

        result = await _call_with_token_fallback(_judge_github)

        logger.info("llm_judge_github_success", model=model)
        return cast("T", result), degraded_event if not _judge_degraded else None

    @retry_llm
    async def call(
        self,
        role: LLMRole,
        messages: list[dict[str, str]],
        response_model: type[T],
        max_tokens: int | None = None,
        emit_event: Any = None,  # WP-5: optional event emitter for JudgeProviderDegradedEvent
    ) -> T:
        """Make a structured LLM call.

        If ``messages`` does not already contain a ``system`` message,
        the role's default system prompt is prepended. The caller stays
        in control whenever they pass their own ``system`` message.

        The concrete model is picked round-robin from the role's pool
        on every call; tenacity retries on rate-limit errors therefore
        try a different model on each attempt.

        WP-5: Judge role supports provider routing with fallback. Pass
        ``emit_event`` callback to receive JudgeProviderDegradedEvent
        when fallback occurs.

        Args:
            role: The LLM role to use (determines model pool, temperature, etc.)
            messages: The conversation messages
            response_model: Pydantic model class for structured output
            max_tokens: Optional override for role's default max_tokens (WP-2 M3)
            emit_event: Optional async callback for emitting degradation events (WP-5)
        """
        global _judge_degraded

        config = ROLE_CONFIGS[role]

        if not _has_system_message(messages):
            messages = [
                {"role": "system", "content": ROLE_PROMPTS[role]},
                *messages,
            ]

        logger.info(
            "llm_call_start",
            role=role.value,
            response_model=response_model.__name__,
        )

        # Provider seam: when LLM_PROVIDER != "github", route through the
        # factory-resolved provider (OpenAI / Anthropic / Google). The
        # github path below stays untouched to preserve token+model pool
        # rotation and judge fallback (WP-5).
        active_provider = resolve_active_provider()
        if active_provider != "github":
            from app.llm.factory import get_provider

            provider = get_provider(active_provider)
            effective_max = max_tokens if max_tokens is not None else config.max_tokens
            try:
                result = await provider.complete(
                    role=role,
                    messages=messages,
                    response_model=response_model,
                    temperature=config.temperature,
                    max_tokens=effective_max,
                )
            except (RateLimitError, InstructorRetryException) as exc:
                # Per-day / free-tier exhaustion is NOT recoverable inside
                # the run's lifetime. Surface as a typed error so tenacity
                # skips it (LLMProviderQuotaExhausted is not a RateLimitError
                # subclass) and the orchestrator fails the run with a
                # clear provider-level message.
                if _is_quota_exhausted(exc):
                    logger.warning(
                        "llm_provider_quota_exhausted",
                        provider=active_provider,
                        role=role.value,
                        error=str(exc),
                    )
                    raise LLMProviderQuotaExhausted(active_provider, exc) from exc
                raise
            logger.info(
                "llm_call_complete",
                role=role.value,
                provider=provider.name,
                model=provider.model_for(role),
                response_model=response_model.__name__,
            )
            return result

        # WP-5: Special handling for judge role with provider routing
        if role == LLMRole.JUDGE:
            result, degraded_info = await self._call_judge_with_fallback(
                messages, response_model, max_tokens
            )

            if degraded_info and emit_event and not _judge_degraded:
                # Emit JudgeProviderDegradedEvent
                from app.domain.enums import EventType
                from app.domain.events import JudgeProviderDegradedEvent

                event = JudgeProviderDegradedEvent(
                    type=EventType.JUDGE_PROVIDER_DEGRADED,
                    **degraded_info,
                )
                await emit_event(event)
                _judge_degraded = True  # Emit once per process

            logger.info(
                "llm_call_complete",
                role=role.value,
                response_model=response_model.__name__,
            )
            return result

        # Standard path for non-judge roles. On per-token rate-limit
        # we walk the rotation pool inline before letting tenacity wait.
        model = _next_model(role)
        effective_max = max_tokens if max_tokens is not None else config.max_tokens

        async def _make_call(token: str) -> Any:
            return await client.chat.completions.create(
                model=model,
                # GitHub Models is OpenAI-SDK-compatible (ai-services.md §1.1),
                # so we route through litellm's ``openai`` provider with an
                # explicit ``api_base`` and ``api_key``. The dedicated
                # ``github`` provider in litellm targets a legacy Azure
                # endpoint with a different catalog — do not use it.
                custom_llm_provider="openai",
                api_base=settings.llm_api_base,
                api_key=token,
                messages=messages,
                temperature=config.temperature,
                max_tokens=effective_max,
                response_model=response_model,
                # Disable Instructor's internal retry loop. We let tenacity
                # own the retry budget so that every retry attempt re-enters
                # ``LLMClient.call`` and rotates to the next model in the
                # role's pool. Without this Instructor burns 3 attempts on
                # the same model before tenacity ever sees the error.
                max_retries=1,
            )

        result = await _call_with_token_fallback(_make_call)

        logger.info(
            "llm_call_complete",
            role=role.value,
            model=model,
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
