"""Tests for WikipediaSource."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.sources.wikipedia as wikipedia_module
from app.domain.enums import SourceType
from app.seams.source import SourceError
from app.sources.base import DEFAULT_MAX_CONTENT_CHARS
from app.sources.wikipedia import WikipediaSource


@dataclass
class FakePage:
    title: str
    fullurl: str
    summary: str = ""
    text: str = ""
    links: dict[str, object] = field(default_factory=dict)
    _exists: bool = True

    def exists(self) -> bool:
        return self._exists


def _missing(title: str) -> FakePage:
    return FakePage(title=title, fullurl=f"https://en.wikipedia.org/wiki/{title}", _exists=False)


def _install_page_lookup(
    source: WikipediaSource, mapping: dict[str, FakePage]
) -> None:
    def _page(query: str) -> FakePage:
        return mapping.get(query, _missing(query))

    source._wiki.page = _page  # type: ignore[method-assign,assignment]


async def test_search_returns_direct_match_when_page_exists() -> None:
    source = WikipediaSource()
    page = FakePage(
        title="Python (programming language)",
        fullurl="https://en.wikipedia.org/wiki/Python_(programming_language)",
        summary="Python is a high-level language.",
        text="Full article text.",
    )
    _install_page_lookup(source, {"Python": page})

    results = await source.search("Python", max_results=1)

    assert len(results) == 1
    assert results[0].title == page.title
    assert results[0].url == page.fullurl
    assert results[0].snippet == page.summary
    assert results[0].content == page.text
    assert results[0].relevance_score == 1.0


async def test_search_returns_linked_pages_up_to_max_results() -> None:
    source = WikipediaSource()
    direct = FakePage(
        title="A",
        fullurl="https://en.wikipedia.org/wiki/A",
        summary="sA",
        text="tA",
        links={"B": object(), "C": object(), "D": object()},
    )
    linked_b = FakePage(title="B", fullurl="https://en.wikipedia.org/wiki/B", text="tB")
    linked_c = FakePage(title="C", fullurl="https://en.wikipedia.org/wiki/C", text="tC")
    linked_d = FakePage(title="D", fullurl="https://en.wikipedia.org/wiki/D", text="tD")
    _install_page_lookup(
        source, {"A": direct, "B": linked_b, "C": linked_c, "D": linked_d}
    )

    results = await source.search("A", max_results=3)

    assert len(results) == 3
    assert results[0].title == "A"
    assert results[0].relevance_score == 1.0
    assert {r.title for r in results[1:]} == {"B", "C"}
    for r in results[1:]:
        assert r.relevance_score == 0.8


async def test_search_skips_missing_linked_pages() -> None:
    source = WikipediaSource()
    direct = FakePage(
        title="A",
        fullurl="https://en.wikipedia.org/wiki/A",
        text="tA",
        links={"Bad": object(), "Good": object()},
    )
    good = FakePage(title="Good", fullurl="https://en.wikipedia.org/wiki/Good")
    _install_page_lookup(source, {"A": direct, "Good": good})

    results = await source.search("A", max_results=3)
    titles = [r.title for r in results]
    assert "Bad" not in titles
    assert "Good" in titles


async def test_search_falls_back_to_variations_when_page_missing() -> None:
    source = WikipediaSource()
    replaced = FakePage(
        title="Machine learning",
        fullurl="https://en.wikipedia.org/wiki/Machine_learning",
        summary="ml",
        text="full",
    )
    _install_page_lookup(source, {"machine learning": replaced})

    results = await source.search("machine_learning", max_results=2)

    assert len(results) == 1
    assert results[0].title == "Machine learning"
    assert results[0].relevance_score == 0.7


async def test_search_returns_empty_when_nothing_found() -> None:
    source = WikipediaSource()
    _install_page_lookup(source, {})
    assert await source.search("nothing here", max_results=3) == []


async def test_search_truncates_content() -> None:
    source = WikipediaSource()
    long_text = "z" * (DEFAULT_MAX_CONTENT_CHARS + 50)
    page = FakePage(
        title="Long",
        fullurl="https://en.wikipedia.org/wiki/Long",
        summary="s",
        text=long_text,
    )
    _install_page_lookup(source, {"Long": page})

    results = await source.search("Long", max_results=1)

    assert results[0].content is not None
    assert results[0].content.endswith("...")
    assert len(results[0].content) == DEFAULT_MAX_CONTENT_CHARS + 3


async def test_search_raises_source_error_on_unexpected_exception() -> None:
    source = WikipediaSource()
    original = RuntimeError("network down")

    def _boom(_query: str) -> FakePage:
        raise original

    source._wiki.page = _boom  # type: ignore[method-assign,assignment]

    with pytest.raises(SourceError) as exc_info:
        await source.search("anything")

    assert exc_info.value.source_type is SourceType.WIKIPEDIA
    assert exc_info.value.recoverable is True
    assert exc_info.value.__cause__ is original


async def test_search_runs_sync_calls_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = WikipediaSource()
    page = FakePage(
        title="X", fullurl="https://en.wikipedia.org/wiki/X", summary="s", text="t"
    )
    _install_page_lookup(source, {"X": page})

    call_count = 0
    real_run_sync = wikipedia_module.anyio.to_thread.run_sync

    async def _counting_run_sync(func: Callable[..., Any], *args: Any) -> Any:
        nonlocal call_count
        call_count += 1
        return await real_run_sync(func, *args)

    monkeypatch.setattr(wikipedia_module.anyio.to_thread, "run_sync", _counting_run_sync)

    await source.search("X", max_results=1)

    assert call_count >= 1


async def test_health_check_returns_true_when_python_article_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = WikipediaSource()
    page = FakePage(
        title="Python (programming language)",
        fullurl="https://en.wikipedia.org/wiki/Python_(programming_language)",
    )
    _install_page_lookup(source, {"Python (programming language)": page})

    assert await source.health_check() is True


async def test_health_check_returns_false_on_exception() -> None:
    source = WikipediaSource()

    def _boom(_query: str) -> FakePage:
        raise RuntimeError("network down")

    source._wiki.page = _boom  # type: ignore[method-assign,assignment]
    assert await source.health_check() is False


async def test_health_check_returns_false_when_page_missing() -> None:
    source = WikipediaSource()
    _install_page_lookup(source, {})
    assert await source.health_check() is False


def test_source_type_and_name_properties() -> None:
    source = WikipediaSource(language="es")
    assert source.source_type is SourceType.WIKIPEDIA
    assert source.name == "Wikipedia (es)"


async def test_search_propagates_source_error_unchanged() -> None:
    """If an inner call already raises SourceError, do not wrap it again."""
    source = WikipediaSource()
    inner = SourceError(source_type=SourceType.WIKIPEDIA, message="inner")

    # Monkeypatch anyio.to_thread.run_sync to raise SourceError directly.
    async def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise inner

    source_run_sync_orig = wikipedia_module.anyio.to_thread.run_sync
    wikipedia_module.anyio.to_thread.run_sync = _raise  # type: ignore[assignment]
    try:
        with pytest.raises(SourceError) as exc_info:
            await source.search("q")
        assert exc_info.value is inner
    finally:
        wikipedia_module.anyio.to_thread.run_sync = source_run_sync_orig  # type: ignore[assignment]
