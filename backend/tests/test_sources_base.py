"""Tests for BaseSource truncation helper."""

from __future__ import annotations

from app.sources.base import DEFAULT_MAX_CONTENT_CHARS, BaseSource


def test_truncate_short_string_unchanged() -> None:
    base = BaseSource()
    assert base._truncate_content("hello") == "hello"


def test_truncate_long_string_clipped_with_ellipsis() -> None:
    base = BaseSource()
    long_text = "x" * (DEFAULT_MAX_CONTENT_CHARS + 10)
    out = base._truncate_content(long_text)
    assert out.endswith("...")
    assert len(out) == DEFAULT_MAX_CONTENT_CHARS + 3
    assert out[:-3] == "x" * DEFAULT_MAX_CONTENT_CHARS


def test_truncate_respects_max_chars_argument() -> None:
    base = BaseSource()
    out = base._truncate_content("abcdefghij", max_chars=4)
    assert out == "abcd..."


def test_truncate_at_exact_max_returns_unchanged() -> None:
    base = BaseSource()
    text = "a" * 10
    assert base._truncate_content(text, max_chars=10) == text
