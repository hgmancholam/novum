"""Integration tests for auth routes (BRD-04 §4.5).

Covers AC-01 (register), AC-02 (duplicate), AC-03 (verify), and the
public-profile endpoint at `GET /api/auth/users/{username}`.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json={"username": "alice"})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert isinstance(body["token"], str)
    assert len(body["token"]) == 64


async def test_register_normalizes_username(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register", json={"username": "  Bob  "}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "bob"


async def test_register_duplicate_returns_new_token(client: AsyncClient) -> None:
    first = await client.post("/api/auth/register", json={"username": "carol"})
    assert first.status_code == 200
    dup = await client.post("/api/auth/register", json={"username": "carol"})
    assert dup.status_code == 200
    assert dup.json()["username"] == "carol"
    assert dup.json()["token"] != first.json()["token"]


async def test_register_invalid_chars_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register", json={"username": "bad name!"}
    )
    assert response.status_code == 400


async def test_register_too_short_returns_422(client: AsyncClient) -> None:
    # Pydantic min_length=3 short-circuits before service ValueError.
    response = await client.post("/api/auth/register", json={"username": "ab"})
    assert response.status_code == 422


async def test_verify_returns_true_for_valid_token(client: AsyncClient) -> None:
    reg = await client.post("/api/auth/register", json={"username": "dora"})
    token = reg.json()["token"]

    response = await client.post(
        "/api/auth/verify", json={"username": "dora", "token": token}
    )
    assert response.status_code == 200
    assert response.json() == {"valid": True}


async def test_verify_returns_false_for_wrong_token(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json={"username": "eve"})
    response = await client.post(
        "/api/auth/verify", json={"username": "eve", "token": "0" * 64}
    )
    assert response.status_code == 200
    assert response.json() == {"valid": False}


async def test_verify_returns_false_for_unknown_user(client: AsyncClient) -> None:
    """No 404 — the route never leaks user existence."""
    response = await client.post(
        "/api/auth/verify", json={"username": "ghost", "token": "0" * 64}
    )
    assert response.status_code == 200
    assert response.json() == {"valid": False}


async def test_get_user_profile_returns_200(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json={"username": "frank"})
    response = await client.get("/api/auth/users/frank")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "frank"
    assert "created_at" in body
    # No token / token_hash leaked.
    assert "token" not in body
    assert "token_hash" not in body


async def test_get_user_profile_returns_404_for_unknown(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/auth/users/nobody")
    assert response.status_code == 404
