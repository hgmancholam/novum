"""Tests for ``app.llm.client.LLMClient``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.llm import client as client_module
from app.llm.models import (
    JudgeVerdict,
    PlanOutput,
    QuestionClassification,
    SubClaimOutput,
    SynthesizedAnswer,
)
from app.llm.prompts import ROLE_PROMPTS
from app.llm.roles import ROLE_CONFIGS, LLMRole


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace ``client.chat.completions.create`` with an AsyncMock."""
    mock = AsyncMock()
    monkeypatch.setattr(
        client_module.client.chat.completions, "create", mock
    )
    return mock


@pytest.mark.asyncio
async def test_call_classifier_returns_question_classification(
    mock_create: AsyncMock,
) -> None:
    expected = QuestionClassification(
        question_type="factual", rationale="factual", answerable=True
    )
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.CLASSIFIER,
        [{"role": "user", "content": "What is the capital of France?"}],
        QuestionClassification,
    )

    assert result is expected
    kwargs = mock_create.call_args.kwargs
    assert kwargs["model"] == ROLE_CONFIGS[LLMRole.CLASSIFIER].model
    assert kwargs["temperature"] == ROLE_CONFIGS[LLMRole.CLASSIFIER].temperature
    assert kwargs["max_tokens"] == ROLE_CONFIGS[LLMRole.CLASSIFIER].max_tokens
    assert kwargs["response_model"] is QuestionClassification


@pytest.mark.asyncio
async def test_call_planner_returns_plan_output(mock_create: AsyncMock) -> None:
    expected = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="t", rationale="r")],
        overall_rationale="ok",
    )
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.PLANNER,
        [{"role": "user", "content": "Plan this."}],
        PlanOutput,
    )

    assert result is expected
    assert mock_create.call_args.kwargs["model"] == ROLE_CONFIGS[LLMRole.PLANNER].model


@pytest.mark.asyncio
async def test_call_synthesizer_returns_synthesized_answer(
    mock_create: AsyncMock,
) -> None:
    expected = SynthesizedAnswer(prose="answer", key_points=["a"])
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.SYNTHESIZER,
        [{"role": "user", "content": "Synthesize"}],
        SynthesizedAnswer,
    )

    assert result is expected
    assert (
        mock_create.call_args.kwargs["model"]
        == ROLE_CONFIGS[LLMRole.SYNTHESIZER].model
    )


@pytest.mark.asyncio
async def test_call_judge_returns_verdict(mock_create: AsyncMock) -> None:
    expected = JudgeVerdict(confidence=0.8, verdict="approve", rationale="ok")
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.JUDGE,
        [{"role": "user", "content": "Judge this"}],
        JudgeVerdict,
    )

    assert result is expected
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_call_prepends_role_system_prompt_when_absent(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = SynthesizedAnswer(prose="x", key_points=[])

    await client_module.llm.call(
        LLMRole.SYNTHESIZER,
        [{"role": "user", "content": "Hi"}],
        SynthesizedAnswer,
    )

    messages: list[dict[str, str]] = mock_create.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == ROLE_PROMPTS[LLMRole.SYNTHESIZER]
    assert messages[1] == {"role": "user", "content": "Hi"}


@pytest.mark.asyncio
async def test_call_does_not_prepend_system_when_present(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = SynthesizedAnswer(prose="x", key_points=[])
    custom: list[dict[str, str]] = [
        {"role": "system", "content": "Custom system prompt"},
        {"role": "user", "content": "Hi"},
    ]

    await client_module.llm.call(LLMRole.SYNTHESIZER, custom, SynthesizedAnswer)

    messages: list[dict[str, str]] = mock_create.call_args.kwargs["messages"]
    system_messages = [m for m in messages if m["role"] == "system"]
    assert len(system_messages) == 1
    assert system_messages[0]["content"] == "Custom system prompt"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "response_model", "instance"),
    [
        (
            LLMRole.CLASSIFIER,
            QuestionClassification,
            QuestionClassification(question_type="factual", rationale="r", answerable=True),
        ),
        (
            LLMRole.PLANNER,
            PlanOutput,
            PlanOutput(
                sub_claims=[SubClaimOutput(id="c1", text="t", rationale="r")],
                overall_rationale="r",
            ),
        ),
        (
            LLMRole.SYNTHESIZER,
            SynthesizedAnswer,
            SynthesizedAnswer(prose="p", key_points=["k"]),
        ),
        (
            LLMRole.JUDGE,
            JudgeVerdict,
            JudgeVerdict(confidence=0.5, verdict="approve", rationale="r"),
        ),
    ],
)
async def test_call_success_path_for_each_role(
    mock_create: AsyncMock,
    role: LLMRole,
    response_model: type[Any],
    instance: Any,
) -> None:
    mock_create.return_value = instance

    result = await client_module.llm.call(
        role, [{"role": "user", "content": "go"}], response_model
    )

    assert result is instance
    assert mock_create.call_args.kwargs["model"] == ROLE_CONFIGS[role].model
    assert mock_create.call_args.kwargs["response_model"] is response_model


@pytest.mark.asyncio
async def test_call_rotates_github_tokens(
    mock_create: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each call advances `_next_token()` so successive requests use
    different GitHub PATs (independent rate-limit buckets)."""
    from itertools import cycle

    monkeypatch.setattr(client_module, "_TOKEN_POOL", ("tok-a", "tok-b", "tok-c"))
    monkeypatch.setattr(client_module, "_TOKEN_ROTATION", cycle(("tok-a", "tok-b", "tok-c")))

    mock_create.return_value = QuestionClassification(
        question_type="factual", rationale="r", answerable=True
    )

    # Each iteration uses a unique prompt so the CLASSIFIER cache cannot
    # short-circuit subsequent calls — we are exercising token rotation,
    # not memoization.
    for i in range(4):
        await client_module.llm.call(
            LLMRole.CLASSIFIER,
            [{"role": "user", "content": f"q{i}"}],
            QuestionClassification,
        )

    tokens = [c.kwargs["api_key"] for c in mock_create.call_args_list]
    assert tokens == ["tok-a", "tok-b", "tok-c", "tok-a"]


@pytest.mark.asyncio
async def test_pool_exhausted_raises_llmpool_exhausted(
    mock_create: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When every PAT in the rotation pool returns 429 within a single
    fallback sweep, ``_call_with_token_fallback`` raises
    ``LLMPoolExhausted`` (not the raw ``RateLimitError``). This lets the
    error handler tag ``AgentErroredEvent.error_code`` so the frontend
    distinguishes rate-limit from generic failure.
    """
    from itertools import cycle

    from litellm.exceptions import RateLimitError

    monkeypatch.setattr(client_module, "_TOKEN_POOL", ("tok-a", "tok-b"))
    monkeypatch.setattr(client_module, "_TOKEN_ROTATION", cycle(("tok-a", "tok-b")))

    mock_create.side_effect = RateLimitError(
        "Too many requests", llm_provider="github", model="gpt-4o-mini"
    )

    # Disable tenacity retries for this test: we want a single sweep
    # over the token pool, not 5 retries × 2 tokens = 10 attempts.
    async def _call_once(
        role: LLMRole,
        messages: list[dict[str, str]],
        response_model: type[Any],
        max_tokens: int | None = None,
    ) -> Any:
        token = client_module._next_token()  # type: ignore[attr-defined]
        return await client_module._call_with_token_fallback(  # type: ignore[attr-defined]
            lambda _tok: mock_create(model="x", api_key=_tok)
        )

    with pytest.raises(client_module.LLMPoolExhausted) as exc_info:
        await _call_once(
            LLMRole.CLASSIFIER,
            [{"role": "user", "content": "q"}],
            QuestionClassification,
        )

    assert exc_info.value.pool_size == 2
    assert isinstance(exc_info.value.__cause__, RateLimitError)


# ---------------------------------------------------------------------------
# Non-github provider quota exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "marker",
    [
        "insufficient_quota",
        "RESOURCE_EXHAUSTED",
        "You exceeded your current quota",
        "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
    ],
)
def test_is_quota_exhausted_detects_known_markers(marker: str) -> None:
    """``_is_quota_exhausted`` matches the daily-quota signals emitted by
    OpenAI / Google / Anthropic so the orchestrator can fail fast instead
    of letting tenacity burn a multi-minute retry budget."""
    exc = Exception(f"... 429 {marker} ...")
    assert client_module._is_quota_exhausted(exc) is True  # type: ignore[attr-defined]


def test_is_quota_exhausted_ignores_transient_rate_limit() -> None:
    """Per-minute 429s without a quota marker stay retryable."""
    exc = Exception("429 Too Many Requests, please slow down")
    assert client_module._is_quota_exhausted(exc) is False  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_non_github_provider_quota_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``provider.complete`` raises a RateLimitError carrying a
    quota-exhausted message, ``LLMClient.call`` converts it into
    ``LLMProviderQuotaExhausted`` so tenacity does NOT retry and the
    orchestrator can tag ``error_code='llm_provider_quota_exhausted'``."""
    from litellm.exceptions import RateLimitError

    token = client_module.current_provider.set("google")
    try:
        quota_exc = RateLimitError(
            "geminiException - 429 RESOURCE_EXHAUSTED: "
            "Quota exceeded for generate_content_free_tier_requests",
            llm_provider="google",
            model="gemini/gemini-2.5-flash",
        )

        class _StubProvider:
            name = "google"

            def model_for(self, _role: LLMRole) -> str:
                return "gemini/gemini-2.5-flash"

            async def complete(self, **_kwargs: Any) -> Any:
                raise quota_exc

        monkeypatch.setattr(
            "app.llm.factory.get_provider", lambda _name=None: _StubProvider()
        )

        with pytest.raises(client_module.LLMProviderQuotaExhausted) as exc_info:
            await client_module.llm.call(
                LLMRole.CLASSIFIER,
                [{"role": "user", "content": "q"}],
                QuestionClassification,
            )

        assert exc_info.value.provider == "google"
        assert exc_info.value.original is quota_exc
        # Critical: NOT a RateLimitError subclass → tenacity will not retry.
        assert not isinstance(exc_info.value, RateLimitError)
    finally:
        client_module.current_provider.reset(token)


@pytest.mark.asyncio
async def test_non_github_provider_transient_rate_limit_still_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient (non-quota) RateLimitError bubbles up unchanged so the
    standard tenacity retry path still gets to handle it."""
    from litellm.exceptions import RateLimitError

    token = client_module.current_provider.set("openai")
    try:
        transient = RateLimitError(
            "429 Too Many Requests — slow down",
            llm_provider="openai",
            model="gpt-5",
        )

        class _StubProvider:
            name = "openai"

            def model_for(self, _role: LLMRole) -> str:
                return "gpt-5"

            async def complete(self, **_kwargs: Any) -> Any:
                raise transient

        monkeypatch.setattr(
            "app.llm.factory.get_provider", lambda _name=None: _StubProvider()
        )

        with pytest.raises(RateLimitError) as exc_info:
            await client_module.llm.call(
                LLMRole.CLASSIFIER,
                [{"role": "user", "content": "q"}],
                QuestionClassification,
            )

        # The raw RateLimitError comes through after tenacity exhausts
        # its 5 retries (each retry hits the same stub which keeps
        # raising). It must NOT be wrapped as LLMProviderQuotaExhausted.
        assert not isinstance(exc_info.value, client_module.LLMProviderQuotaExhausted)
    finally:
        client_module.current_provider.reset(token)

