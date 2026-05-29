"""Unit tests for ``app.llm.pricing.compute_cost``."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.llm import pricing as pricing_module


@pytest.fixture(autouse=True)
def _reset_warn_dedup() -> None:
    pricing_module._warned_models.clear()


def _raw(prompt: int, completion: int) -> Any:
    return SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion
    ))


def test_compute_cost_none_returns_zero_static() -> None:
    cost, source = pricing_module.compute_cost(
        model="anthropic/claude-haiku-4-5", raw_completion=None
    )
    assert cost == 0.0
    assert source == "static"


def test_compute_cost_litellm_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: 0.0042,
    )
    cost, source = pricing_module.compute_cost(
        model="anthropic/claude-sonnet-4-6", raw_completion=_raw(1000, 200)
    )
    assert cost == pytest.approx(0.0042)
    assert source == "litellm"


def test_compute_cost_fallback_table(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force litellm to return None so we fall through to the table.
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: None,
    )
    cost, source = pricing_module.compute_cost(
        model="anthropic/claude-haiku-4-5", raw_completion=_raw(1_000_000, 1_000_000)
    )
    # haiku-4-5 = (1.0 in, 5.0 out) per 1M tokens → 1.0 + 5.0 = 6.0
    assert cost == pytest.approx(6.0)
    assert source == "fallback"


def test_compute_cost_normalized_model_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: None,
    )
    # vendor-prefixed lookup misses → strip prefix and try normalized.
    cost, source = pricing_module.compute_cost(
        model="something-weird/claude-sonnet-4-6",
        raw_completion=_raw(2_000_000, 0),
    )
    # sonnet-4-6 input = 3.0 USD per 1M × 2M = 6.0
    assert cost == pytest.approx(6.0)
    assert source == "fallback"


def test_compute_cost_unknown_model_emits_static_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: None,
    )
    cost, source = pricing_module.compute_cost(
        model="acme/who-knows", raw_completion=_raw(500, 100)
    )
    assert cost == 0.0
    assert source == "static"


def test_compute_cost_pricing_miss_is_deduped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: None,
    )
    warned: list[str] = []

    def _capture(event: str, **kw: Any) -> None:
        if event == "pricing_miss":
            warned.append(kw.get("model", ""))

    monkeypatch.setattr(pricing_module.logger, "warning", _capture)

    for _ in range(3):
        pricing_module.compute_cost(
            model="unknown/x", raw_completion=_raw(100, 50)
        )

    assert warned == ["unknown/x"]


def test_compute_cost_zero_usage_falls_back_to_static(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: None,
    )
    cost, source = pricing_module.compute_cost(
        model="anthropic/claude-sonnet-4-6", raw_completion=_raw(0, 0)
    )
    assert cost == 0.0
    assert source == "static"
