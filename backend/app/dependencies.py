"""FastAPI dependencies for dependency injection.

This module is the single source of truth for `get_db` and
`get_current_username` (per IP-03 §5 / IP-04 §5). Do not duplicate
these definitions elsewhere.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.services.auth_service import AuthService, InvalidTokenError


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session for the request lifecycle."""
    async with async_session_maker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_username(
    db: DbSession,
    x_username: Annotated[str | None, Header(alias="X-Username")] = None,
    x_token: Annotated[str | None, Header(alias="X-Token")] = None,
) -> str:
    """Verify caller identity from `X-Username` + `X-Token` headers.

    Both headers are required (BRD-04 §4.6). Missing headers, unknown
    user, and wrong token all yield 401 with a symmetric error message
    so the response does not reveal which of the two failed.
    """
    if not x_username or not x_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Username and X-Token headers required",
        )

    service = AuthService(db)
    try:
        await service.verify(x_username, x_token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        ) from exc
    return x_username


CurrentUsername = Annotated[str, Depends(get_current_username)]
