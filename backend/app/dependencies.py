"""FastAPI dependencies for dependency injection.

This module is the single source of truth for `get_db` and
`get_current_username` (per IP-03 §5). Do not duplicate these
definitions elsewhere.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session for the request lifecycle."""
    async with async_session_maker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_username(
    x_username: Annotated[str | None, Header(alias="X-Username")] = None,
) -> str:
    """Extract the caller's username from the `X-Username` header.

    For V1 (BRD-03) this is a simple header-based identity. Real token
    validation arrives with BRD-04.
    """
    if not x_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Username header required",
        )
    return x_username


CurrentUsername = Annotated[str, Depends(get_current_username)]
