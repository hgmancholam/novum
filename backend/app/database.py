"""Database engine and session configuration.

The canonical `get_db` FastAPI dependency lives in `app.dependencies`.
This module deliberately does not re-export it to keep a single source
of truth (IP-03 §5).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
