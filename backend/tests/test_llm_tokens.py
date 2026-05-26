"""Tests for ``app.llm.client.count_tokens``."""

from __future__ import annotations

import pytest
import tiktoken

from app.llm.client import count_tokens


def test_count_tokens_returns_zero_for_empty_string() -> None:
    assert count_tokens("") == 0


def test_count_tokens_returns_positive_for_non_empty_string() -> None:
    assert count_tokens("Hello, world!") > 0


def test_count_tokens_uses_known_openai_encoding() -> None:
    # gpt-4 is recognised by tiktoken — should not hit the fallback.
    assert count_tokens("Hello", model="gpt-4") > 0


def test_count_tokens_falls_back_to_cl100k_base_on_unknown_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``encoding_for_model`` raises ``KeyError`` we should fall back."""
    real_get_encoding = tiktoken.get_encoding
    used: dict[str, str] = {}

    def fake_encoding_for_model(model: str) -> object:
        raise KeyError(model)

    def fake_get_encoding(name: str) -> object:
        used["name"] = name
        return real_get_encoding(name)

    monkeypatch.setattr(tiktoken, "encoding_for_model", fake_encoding_for_model)
    monkeypatch.setattr(tiktoken, "get_encoding", fake_get_encoding)

    result = count_tokens("Hello", model="deepseek/DeepSeek-V3-0324")
    assert result > 0
    assert used["name"] == "cl100k_base"
