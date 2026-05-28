"""Tests for SourceRegistry."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from app.domain.enums import SourceType
from app.sources import registry as registry_module
from app.sources.registry import (
    SourceRegistry,
    get_registry,
    get_source,
    reset_registry,
)
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource


@pytest.fixture(autouse=True)
def _reset_source_registry() -> Generator[None, None, None]:
    reset_registry()
    yield
    reset_registry()


def test_get_registry_returns_singleton() -> None:
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_get_returns_singleton_per_source_type() -> None:
    registry = get_registry()
    a = registry.get(SourceType.WIKIPEDIA)
    b = registry.get(SourceType.WIKIPEDIA)
    assert a is b


def test_all_returns_all_registered() -> None:
    registry = get_registry()
    all_sources = registry.all()
    types = {s.source_type for s in all_sources}
    assert SourceType.WIKIPEDIA in types
    assert SourceType.TAVILY in types
    assert any(isinstance(s, TavilySource) for s in all_sources)
    assert any(isinstance(s, WikipediaSource) for s in all_sources)


def test_tavily_omitted_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_module.settings, "tavily_api_key", "")
    registry = get_registry()
    assert set(registry.types()) == {
        SourceType.WIKIPEDIA,
        SourceType.SEMANTIC_SCHOLAR,
        SourceType.OPENALEX,
    }
    with pytest.raises(ValueError):
        registry.get(SourceType.TAVILY)


def test_types_returns_source_type_list() -> None:
    registry = get_registry()
    types = registry.types()
    assert isinstance(types, list)
    assert set(types) == {
        SourceType.WIKIPEDIA,
        SourceType.TAVILY,
        SourceType.SEMANTIC_SCHOLAR,
        SourceType.OPENALEX,
    }


def test_get_source_convenience_function() -> None:
    registry = get_registry()
    assert get_source(SourceType.WIKIPEDIA) is registry.get(SourceType.WIKIPEDIA)


def test_reset_registry_creates_new_instance() -> None:
    r1 = get_registry()
    reset_registry()
    r2 = get_registry()
    assert r1 is not r2


def test_get_unknown_type_raises_value_error() -> None:
    registry = SourceRegistry(sources={})
    with pytest.raises(ValueError):
        registry.get(SourceType.WIKIPEDIA)


def test_build_logs_warning_when_tavily_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(registry_module.settings, "tavily_api_key", "")
    registry = SourceRegistry.build()
    assert SourceType.TAVILY not in registry.types()
    assert SourceType.WIKIPEDIA in registry.types()
