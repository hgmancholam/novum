"""Pytest configuration and shared fixtures.

Test strategy (per IP-03 §5 / L-004): services and routes run against
an in-memory SQLite database. The production ORM uses PostgreSQL-only
types (``postgresql.UUID``, ``JSONB``, ``ENUM``); we keep them untouched
and instead:

  1. Register dialect-specific DDL compilation hooks that translate
     those types to portable SQLite equivalents.
  2. Swap the PG-specific ``server_default`` expressions for portable
     equivalents inside the fixture, and restore them on teardown to
     avoid global side effects.
  3. Provide python-side defaults for ``id`` and timestamp columns via
     mapper ``before_insert`` events, scoped to fixture lifetime.

Run with: ``pytest -q -p no:postgresql`` (L-004).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

# Load env vars BEFORE importing app modules so Settings validation passes.
_env_test = Path(__file__).parent.parent / ".env.test"
if _env_test.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_test, override=True)
else:
    os.environ.setdefault("GITHUB_TOKEN", "test_token")
    os.environ.setdefault("TAVILY_API_KEY", "test_key")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test"
    )

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.dependencies import get_db
from app.main import app
from app.models import Base, Event, Run, User

# ---------------------------------------------------------------------------
# Dialect compilation hooks: PG-only types -> portable SQLite types.
# ---------------------------------------------------------------------------


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "JSON"


@compiles(ENUM, "sqlite")
def _compile_enum_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "VARCHAR(50)"


# ---------------------------------------------------------------------------
# Server-default rewrites: PG functions (gen_random_uuid, now,
# '{}'::jsonb) are unparseable on SQLite. Strip them in-place at fixture
# start; restore on teardown.
# ---------------------------------------------------------------------------


_DEFAULT_BACKUPS: dict[tuple[str, str], object] = {}


def _swap_pg_defaults_to_sqlite() -> None:
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if col.server_default is None:
                continue
            _DEFAULT_BACKUPS[(table.name, col.name)] = col.server_default
            col.server_default = None


def _restore_pg_defaults() -> None:
    for table in Base.metadata.tables.values():
        for col in table.columns:
            key = (table.name, col.name)
            if key in _DEFAULT_BACKUPS:
                col.server_default = _DEFAULT_BACKUPS[key]  # type: ignore[assignment]
    _DEFAULT_BACKUPS.clear()


# ---------------------------------------------------------------------------
# before_insert listeners: fill values PG would have generated via
# ``gen_random_uuid()`` / ``now()``. Scoped to fixture session lifetime.
# ---------------------------------------------------------------------------


def _user_defaults(_mapper: object, _conn: object, target: User) -> None:
    if target.id is None:
        target.id = uuid.uuid4()
    if target.created_at is None:
        target.created_at = datetime.now(UTC)


def _run_defaults(_mapper: object, _conn: object, target: Run) -> None:
    if target.id is None:
        target.id = uuid.uuid4()
    if target.started_at is None:
        target.started_at = datetime.now(UTC)
    if target.output_format is None:
        target.output_format = "prose"
    if target.confidence_threshold is None:
        target.confidence_threshold = 0.7


def _event_defaults(_mapper: object, _conn: object, target: Event) -> None:
    if target.id is None:
        target.id = uuid.uuid4()
    if target.created_at is None:
        target.created_at = datetime.now(UTC)
    if target.payload is None:
        target.payload = {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio backend for anyio."""
    return "asyncio"


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine. Function-scoped to align with the
    function-scoped event loop used by ``pytest-asyncio``."""
    _swap_pg_defaults_to_sqlite()
    event.listen(User, "before_insert", _user_defaults)
    event.listen(Run, "before_insert", _run_defaults)
    event.listen(Event, "before_insert", _event_defaults)

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()
        event.remove(User, "before_insert", _user_defaults)
        event.remove(Run, "before_insert", _run_defaults)
        event.remove(Event, "before_insert", _event_defaults)
        _restore_pg_defaults()


@pytest.fixture
async def sqlite_session(
    sqlite_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Per-test session with table cleanup between tests."""
    maker = async_sessionmaker(
        sqlite_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with maker() as session:
        yield session

    async with sqlite_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM events"))
        await conn.execute(sa.text("DELETE FROM runs"))
        await conn.execute(sa.text("DELETE FROM users"))


@pytest.fixture
async def client(
    sqlite_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with the DB dependency overridden to the SQLite session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield sqlite_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def seeded_user(sqlite_session: AsyncSession) -> str:
    """Insert a test user and return the username (FK target for runs)."""
    user = User(username="testuser", token_hash="x" * 64)
    sqlite_session.add(user)
    await sqlite_session.commit()
    return user.username
