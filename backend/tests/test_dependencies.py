"""Tests for `get_current_username` dependency (BRD-04 §4.6 / AC-04).

We exercise the dependency end-to-end via a protected route (`POST
/api/runs`) since the dependency reads request headers.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


_VALID_BODY = {
    "question": "What is the capital of France?",
    "user_context": None,
    "output_format": "prose",
    "confidence_threshold": 0.7,
}


async def test_get_current_username_missing_headers_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/runs", json=_VALID_BODY)
    assert response.status_code == 401


async def test_get_current_username_missing_token_returns_401(
    client: AsyncClient, seeded_user: str
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers={"X-Username": seeded_user},
    )
    assert response.status_code == 401


async def test_get_current_username_missing_username_returns_401(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers={"X-Token": auth_headers["X-Token"]},
    )
    assert response.status_code == 401


async def test_get_current_username_wrong_token_returns_401(
    client: AsyncClient, seeded_user: str
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers={"X-Username": seeded_user, "X-Token": "0" * 64},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_get_current_username_unknown_user_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers={"X-Username": "ghost", "X-Token": "0" * 64},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_get_current_username_valid_pair_succeeds(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers=auth_headers,
    )
    assert response.status_code == 201
