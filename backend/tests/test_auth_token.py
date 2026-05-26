"""Unit tests for `app.auth.token` (BRD-04 §4.3)."""

from __future__ import annotations

from app.auth.token import generate_token, hash_token, verify_token


def test_generate_token_returns_64_hex_chars() -> None:
    token = generate_token()
    assert len(token) == 64
    int(token, 16)  # raises if not hex


def test_generate_token_is_unique_across_calls() -> None:
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100


def test_hash_token_is_deterministic() -> None:
    token = "abc123"
    assert hash_token(token) == hash_token(token)


def test_hash_token_returns_64_hex_chars() -> None:
    digest = hash_token("anything")
    assert len(digest) == 64
    int(digest, 16)


def test_hash_token_differs_for_different_inputs() -> None:
    assert hash_token("a") != hash_token("b")


def test_verify_token_accepts_matching_pair() -> None:
    token = generate_token()
    assert verify_token(token, hash_token(token)) is True


def test_verify_token_rejects_mismatch() -> None:
    token = generate_token()
    other = generate_token()
    assert verify_token(token, hash_token(other)) is False


def test_verify_token_rejects_empty_token() -> None:
    assert verify_token("", hash_token("real")) is False


def test_verify_token_rejects_wrong_length_hash() -> None:
    # `compare_digest` returns False (not raises) when lengths differ.
    assert verify_token("token", "short") is False
