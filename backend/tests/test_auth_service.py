"""Unit tests for `AuthService` (BRD-04 §4.4)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token import hash_token
from app.services.auth_service import (
    AuthService,
    InvalidTokenError,
    UsernameExistsError,
)

pytestmark = pytest.mark.asyncio


async def test_register_creates_user_and_returns_token(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    username, token = await service.register("alice")

    assert username == "alice"
    assert len(token) == 64
    user = await service.get_user("alice")
    assert user is not None
    assert user.token_hash == hash_token(token)
    assert user.token_hash != token  # never stored in plain


async def test_register_normalizes_username(sqlite_session: AsyncSession) -> None:
    service = AuthService(sqlite_session)
    username, _ = await service.register("  Alice  ")
    assert username == "alice"


async def test_register_rejects_too_short_username(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    with pytest.raises(ValueError):
        await service.register("ab")


async def test_register_rejects_too_long_username(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    with pytest.raises(ValueError):
        await service.register("a" * 51)


async def test_register_rejects_invalid_characters(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    with pytest.raises(ValueError):
        await service.register("bad name!")


async def test_register_accepts_underscores_and_hyphens(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    username, _ = await service.register("user_name-01")
    assert username == "user_name-01"


async def test_register_duplicate_raises_username_exists(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    await service.register("bob")
    with pytest.raises(UsernameExistsError):
        await service.register("bob")


async def test_register_duplicate_is_case_insensitive(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    await service.register("carol")
    with pytest.raises(UsernameExistsError):
        await service.register("CAROL")


async def test_verify_returns_true_for_valid_pair(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    username, token = await service.register("dora")
    assert await service.verify(username, token) is True


async def test_verify_raises_for_wrong_token(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    username, _ = await service.register("eve")
    with pytest.raises(InvalidTokenError):
        await service.verify(username, "0" * 64)


async def test_verify_raises_for_unknown_user(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    with pytest.raises(InvalidTokenError):
        await service.verify("ghost", "0" * 64)


async def test_get_user_returns_none_for_unknown(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    assert await service.get_user("nobody") is None


async def test_get_user_returns_user_for_known(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthService(sqlite_session)
    await service.register("frank")
    user = await service.get_user("frank")
    assert user is not None
    assert user.username == "frank"
