"""Hybrid LLM pricing — litellm first, static fallback table second.

Returns ``(cost_usd, pricing_source)``. Pure module: no I/O, no DB.
See BRD-29 §4.4 and IP-29 Task 1.4.
"""

from __future__ import annotations

from typing import Any, Literal

import litellm
import structlog

logger = structlog.get_logger(__name__)

PricingSource = Literal["litellm", "fallback", "static"]


# USD per 1M tokens (input, output). V1 active: Anthropic Claude.
# Anthropic public pricing as of 2026-05.
_PRICING_TABLE: dict[str, tuple[float, float]] = {
    "anthropic/claude-sonnet-4-6": (3.0, 15.0),
    "anthropic/claude-sonnet-4-5": (3.0, 15.0),
    "anthropic/claude-haiku-4-5": (1.0, 5.0),
    "anthropic/claude-haiku-3-5": (0.80, 4.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-3-5": (0.80, 4.0),
}


_warned_models: set[str] = set()


def _normalize_model(model: str) -> str:
    return model.split("/", 1)[-1] if "/" in model else model


def _extract_usage(raw_completion: Any) -> tuple[int, int]:
    usage = getattr(raw_completion, "usage", None)
    if usage is None:
        return 0, 0
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    return prompt, completion


def compute_cost(
    *, model: str, raw_completion: Any
) -> tuple[float, PricingSource]:
    """Return ``(cost_usd, pricing_source)`` for a single completion.

    Order: litellm.completion_cost → static table → zero. Always defensive
    — any exception falls through to the next branch.
    """
    if raw_completion is None:
        return 0.0, "static"

    try:
        litellm_cost = litellm.completion_cost(completion_response=raw_completion)
        if litellm_cost and float(litellm_cost) > 0.0:
            return float(litellm_cost), "litellm"
    except Exception as exc:  # noqa: BLE001 — defensive over upstream API drift
        logger.debug("litellm_cost_failed", model=model, error=str(exc))

    prompt, completion = _extract_usage(raw_completion)
    if prompt == 0 and completion == 0:
        return 0.0, "static"

    prices = _PRICING_TABLE.get(model) or _PRICING_TABLE.get(_normalize_model(model))
    if prices is None:
        if model not in _warned_models:
            _warned_models.add(model)
            logger.warning("pricing_miss", model=model)
        return 0.0, "static"

    in_price, out_price = prices
    cost = (prompt / 1_000_000.0) * in_price + (completion / 1_000_000.0) * out_price
    return cost, "fallback"
