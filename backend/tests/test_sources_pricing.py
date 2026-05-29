"""Unit tests for ``app.sources.pricing``."""

from __future__ import annotations

import pytest

from app.config import settings
from app.sources import pricing as src_pricing


def test_tavily_basic_is_one_credit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "tavily_usd_per_credit", 0.008)
    units, unit, total = src_pricing.tavily_cost("basic")
    assert (units, unit, total) == (1, 0.008, 0.008)


def test_tavily_advanced_is_two_credits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "tavily_usd_per_credit", 0.008)
    units, unit, total = src_pricing.tavily_cost("advanced")
    assert units == 2
    assert unit == 0.008
    assert total == pytest.approx(0.016)


def test_tavily_unknown_depth_defaults_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "tavily_usd_per_credit", 0.01)
    units, unit, total = src_pricing.tavily_cost("xyz")
    assert (units, unit, total) == (1, 0.01, 0.01)


def test_wikipedia_is_free() -> None:
    assert src_pricing.wikipedia_cost() == (1, 0.0, 0.0)


def test_free_source_is_free() -> None:
    assert src_pricing.free_source_cost() == (1, 0.0, 0.0)
