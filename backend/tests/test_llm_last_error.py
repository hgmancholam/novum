"""Unit tests for ``app.llm.last_error`` (passive provider health tracker)."""

from __future__ import annotations

import time

import pytest

from app.llm import last_error


@pytest.fixture(autouse=True)
def _reset() -> None:
    last_error.reset_all()


def test_get_recent_returns_none_when_no_record() -> None:
    assert last_error.get_recent("anthropic") is None


def test_record_then_get_returns_entry() -> None:
    last_error.record("anthropic", "rate_limit", "429 too many requests")
    err = last_error.get_recent("anthropic")
    assert err is not None
    assert err.kind == "rate_limit"
    assert err.provider == "anthropic"
    assert "429" in err.message


def test_clear_drops_entry() -> None:
    last_error.record("anthropic", "auth", "boom")
    last_error.clear("anthropic")
    assert last_error.get_recent("anthropic") is None


def test_record_overwrites_previous_entry() -> None:
    last_error.record("anthropic", "rate_limit", "first")
    last_error.record("anthropic", "auth", "second")
    err = last_error.get_recent("anthropic")
    assert err is not None and err.kind == "auth" and err.message == "second"


def test_entry_decays_past_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_now = [1000.0]
    monkeypatch.setattr(last_error.time, "time", lambda: fake_now[0])

    last_error.record("anthropic", "quota", "exceeded")
    assert last_error.get_recent("anthropic", within_s=60.0) is not None

    fake_now[0] += 120.0
    assert last_error.get_recent("anthropic", within_s=60.0) is None


def test_entries_are_per_provider() -> None:
    last_error.record("anthropic", "auth", "a")
    last_error.record("openai", "rate_limit", "o")
    assert last_error.get_recent("anthropic").kind == "auth"  # type: ignore[union-attr]
    assert last_error.get_recent("openai").kind == "rate_limit"  # type: ignore[union-attr]


def test_message_is_truncated() -> None:
    huge = "x" * 5000
    last_error.record("anthropic", "upstream", huge)
    err = last_error.get_recent("anthropic")
    assert err is not None and len(err.message) <= 500


def test_real_time_clock_records_within_window() -> None:
    last_error.record("anthropic", "rate_limit", "fresh")
    err = last_error.get_recent("anthropic", within_s=5.0)
    assert err is not None
    assert err.recorded_at <= time.time()
