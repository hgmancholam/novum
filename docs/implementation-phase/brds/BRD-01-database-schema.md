# BRD-01: Database Schema & Alembic Migrations

**Document ID:** BRD-01
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 2 of 19

---

## 1. Executive Summary

Define the PostgreSQL 16 database schema for Novum's three core tables: `users`, `runs`, and `events`. The `events` table is the append-only event log that serves as the single source of truth for all run state (RF-03). This BRD also includes the Alembic migration setup.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-03 | Fork from decision points (append-only events) | Complete |
| RF-05 | Lightweight identity (username only) | Complete |
| RF-01 | stop_reason enum (7 values) | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-00 | BRD-02, BRD-03, BRD-04 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  alembic/
    versions/
      001_initial_schema.py
    env.py
    script.py.mako
  alembic.ini
  app/
    models/
      __init__.py
      base.py              # SQLAlchemy Base
      user.py              # User ORM model
      run.py               # Run ORM model  
      event.py             # Event ORM model
```

### 4.2 Database Schema

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

-- RF-01: 7 terminal states (never free text)
CREATE TYPE stop_reason AS ENUM (
    'judge_confirmed',        -- Answer approved by judge
    'honest_unanswerable',    -- Insufficient evidence
    'honest_contradiction',   -- Irreconcilable source conflict
    'honest_ambiguous',       -- Question ambiguity detected
    'stopped_by_budget',      -- Safety net: max iterations
    'user_cancelled',         -- User manually stopped
    'errored'                 -- Unrecoverable error
);

-- RF-06: Supported question types
CREATE TYPE question_type AS ENUM (
    'factual',                -- Type 1: Factual/objective
    'comparative',            -- Type 2: Comparative
    'definitional',           -- Type 3: Definitional/explanatory
    'state_of_art',           -- Type 4: State-of-the-art
    'causal'                  -- Type 5: Causal/"why"
);

-- RF-10: Output format options
CREATE TYPE output_format AS ENUM (
    'prose',                  -- Natural language paragraph
    'structured'              -- Structured with sections/bullets
);

-- =============================================================================
-- USERS TABLE (RF-05)
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for username lookups (authentication)
CREATE INDEX idx_users_username ON users (username);

-- =============================================================================
-- RUNS TABLE
-- =============================================================================

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Owner reference
    owner_username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    
    -- Question details
    question TEXT NOT NULL,
    user_context TEXT,                              -- RF-07: ≤1000 chars, optional
    question_type question_type,                    -- RF-06: Detected or null
    
    -- Configuration
    output_format output_format NOT NULL DEFAULT 'prose',  -- RF-10
    confidence_threshold FLOAT NOT NULL DEFAULT 0.7,       -- RF-12: User-set [0,1]
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stopped_at TIMESTAMPTZ,
    
    -- Terminal state
    stop_reason stop_reason,                        -- RF-01: NULL while running
    
    -- Forking (RF-03)
    parent_run_id UUID REFERENCES runs(id) ON DELETE SET NULL,
    forked_at_event_id UUID                         -- References events(id)
);

-- Index for recent runs listing (RF-09)
CREATE INDEX idx_runs_owner_started ON runs (owner_username, started_at DESC);

-- Index for active runs (stop_reason IS NULL)
CREATE INDEX idx_runs_active ON runs (id) WHERE stop_reason IS NULL;

-- =============================================================================
-- EVENTS TABLE (RF-03 — Append-only event log)
-- =============================================================================

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Run reference
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    
    -- Event ordering within run
    step_index INTEGER NOT NULL,
    
    -- Event lineage (for fork/resume visualization)
    parent_event_id UUID REFERENCES events(id) ON DELETE SET NULL,
    
    -- Discriminator for event type (~17 types)
    type VARCHAR(50) NOT NULL,
    
    -- Payload: full event data as JSONB
    -- Schema enforced by Pydantic, not DB constraints
    payload JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Ensure unique ordering within a run
    CONSTRAINT uq_run_step UNIQUE (run_id, step_index)
);

-- Index for streaming events by run (RF-08)
CREATE INDEX idx_events_run_step ON events (run_id, step_index);

-- Index for resuming from Last-Event-ID
CREATE INDEX idx_events_run_created ON events (run_id, created_at);

-- Add foreign key for forked_at_event_id after events table exists
ALTER TABLE runs
    ADD CONSTRAINT fk_runs_forked_event
    FOREIGN KEY (forked_at_event_id) REFERENCES events(id) ON DELETE SET NULL;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE users IS 'Lightweight identity: username + token hash (RF-05)';
COMMENT ON TABLE runs IS 'Research run tracking with fork support (RF-03)';
COMMENT ON TABLE events IS 'Append-only event log — single source of truth (RF-03)';

COMMENT ON COLUMN runs.user_context IS 'Optional context ≤1000 chars, never cited (RF-07)';
COMMENT ON COLUMN runs.confidence_threshold IS 'User-set threshold [0,1] for judge gating (RF-12)';
COMMENT ON COLUMN runs.stop_reason IS 'Terminal state enum, NULL while running (RF-01)';

COMMENT ON COLUMN events.payload IS 'JSONB event data, schema enforced by Pydantic';
COMMENT ON COLUMN events.step_index IS 'Monotonic within run for ordering';
```

### 4.3 Alembic Migration

#### alembic/versions/001_initial_schema.py

```python
"""Initial database schema with users, runs, and events tables.

Revision ID: 001
Revises: 
Create Date: 2026-05-26

Implements:
- RF-03: Append-only events table
- RF-05: Lightweight identity (users)
- RF-01: stop_reason enum (7 values)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    stop_reason_enum = postgresql.ENUM(
        "judge_confirmed",
        "honest_unanswerable",
        "honest_contradiction",
        "honest_ambiguous",
        "stopped_by_budget",
        "user_cancelled",
        "errored",
        name="stop_reason",
    )
    stop_reason_enum.create(op.get_bind(), checkfirst=True)

    question_type_enum = postgresql.ENUM(
        "factual",
        "comparative",
        "definitional",
        "state_of_art",
        "causal",
        name="question_type",
    )
    question_type_enum.create(op.get_bind(), checkfirst=True)

    output_format_enum = postgresql.ENUM(
        "prose",
        "structured",
        name="output_format",
    )
    output_format_enum.create(op.get_bind(), checkfirst=True)

    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_username", "users", ["username"])

    # Runs table (without forked_at_event_id FK initially)
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_username", sa.String(50), sa.ForeignKey("users.username", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("user_context", sa.Text(), nullable=True),
        sa.Column("question_type", question_type_enum, nullable=True),
        sa.Column("output_format", output_format_enum, nullable=False, server_default="prose"),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("stopped_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("stop_reason", stop_reason_enum, nullable=True),
        sa.Column("parent_run_id", postgresql.UUID(), sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("forked_at_event_id", postgresql.UUID(), nullable=True),  # FK added after events
    )
    op.create_index("idx_runs_owner_started", "runs", ["owner_username", sa.text("started_at DESC")])
    op.create_index("idx_runs_active", "runs", ["id"], postgresql_where=sa.text("stop_reason IS NULL"))

    # Events table
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("parent_event_id", postgresql.UUID(), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", "step_index", name="uq_run_step"),
    )
    op.create_index("idx_events_run_step", "events", ["run_id", "step_index"])
    op.create_index("idx_events_run_created", "events", ["run_id", "created_at"])

    # Add FK from runs.forked_at_event_id to events.id
    op.create_foreign_key(
        "fk_runs_forked_event",
        "runs",
        "events",
        ["forked_at_event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FK first
    op.drop_constraint("fk_runs_forked_event", "runs", type_="foreignkey")

    # Drop tables in reverse order
    op.drop_table("events")
    op.drop_table("runs")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS output_format")
    op.execute("DROP TYPE IF EXISTS question_type")
    op.execute("DROP TYPE IF EXISTS stop_reason")
```

### 4.4 SQLAlchemy ORM Models

#### backend/app/models/base.py

```python
"""SQLAlchemy declarative base and common utilities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass
```

#### backend/app/models/user.py

```python
"""User ORM model (RF-05: Lightweight identity)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """User model with username-only identity."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
```

#### backend/app/models/run.py

```python
"""Run ORM model for research run tracking."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Enum types matching database
StopReasonType = ENUM(
    "judge_confirmed",
    "honest_unanswerable",
    "honest_contradiction",
    "honest_ambiguous",
    "stopped_by_budget",
    "user_cancelled",
    "errored",
    name="stop_reason",
    create_type=False,
)

QuestionTypeEnum = ENUM(
    "factual",
    "comparative",
    "definitional",
    "state_of_art",
    "causal",
    name="question_type",
    create_type=False,
)

OutputFormatEnum = ENUM(
    "prose",
    "structured",
    name="output_format",
    create_type=False,
)


class Run(Base):
    """Research run with question, config, and terminal state."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    
    # Owner
    owner_username: Mapped[str] = mapped_column(
        String(50), 
        ForeignKey("users.username", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Question
    question: Mapped[str] = mapped_column(Text, nullable=False)
    user_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question_type: Mapped[Optional[str]] = mapped_column(QuestionTypeEnum, nullable=True)
    
    # Configuration
    output_format: Mapped[str] = mapped_column(
        OutputFormatEnum, 
        nullable=False, 
        server_default="prose",
    )
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.7")
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
    stopped_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Terminal state
    stop_reason: Mapped[Optional[str]] = mapped_column(StopReasonType, nullable=True)
    
    # Forking
    parent_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), 
        nullable=True,
    )
    forked_at_event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Relationships
    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="run",
        order_by="Event.step_index",
        cascade="all, delete-orphan",
    )
```

#### backend/app/models/event.py

```python
"""Event ORM model (RF-03: Append-only event log)."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Event(Base):
    """Append-only event in the event log."""

    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    
    # Run reference
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Ordering
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Lineage
    parent_event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Type discriminator
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # JSONB payload
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
    
    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="events")
```

#### backend/app/models/__init__.py

```python
"""ORM models package."""

from app.models.base import Base
from app.models.user import User
from app.models.run import Run
from app.models.event import Event

__all__ = ["Base", "User", "Run", "Event"]
```

### 4.5 Alembic Configuration

#### alembic/env.py (key sections)

```python
"""Alembic environment configuration."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from settings."""
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## 5. Acceptance Criteria

### AC-01: Migration Runs Successfully
```gherkin
Given PostgreSQL 16 is running
  And the database "novum" exists
When I run "alembic upgrade head"
Then the migration completes without errors
  And the users, runs, and events tables exist
  And the stop_reason, question_type, output_format enums exist
```

### AC-02: Enum Values Match RF-01
```gherkin
Given the migration has been applied
When I query "SELECT unnest(enum_range(NULL::stop_reason))"
Then exactly 7 values are returned:
  | judge_confirmed |
  | honest_unanswerable |
  | honest_contradiction |
  | honest_ambiguous |
  | stopped_by_budget |
  | user_cancelled |
  | errored |
```

### AC-03: Events Are Append-Only
```gherkin
Given a run with events exists
When I attempt to UPDATE an event's payload
Then the operation should succeed (no DB constraint prevents it)
  And application-level code MUST enforce append-only semantics
```

### AC-04: Foreign Keys Work Correctly
```gherkin
Given a user "testuser" exists
When I create a run with owner_username = "testuser"
  And I create events for that run
Then all foreign keys are satisfied
  And deleting the user cascades to runs and events
```

### AC-05: Downgrade Works
```gherkin
Given the migration has been applied
When I run "alembic downgrade base"
Then all tables and enums are dropped
  And the database is empty
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/models/base.py`
- [ ] Create `backend/app/models/user.py`
- [ ] Create `backend/app/models/run.py`
- [ ] Create `backend/app/models/event.py`
- [ ] Create `backend/app/models/__init__.py`
- [ ] Update `backend/alembic/env.py` for async
- [ ] Create `backend/alembic/versions/001_initial_schema.py`
- [ ] Create local PostgreSQL database `novum`
- [ ] Run `alembic upgrade head`
- [ ] Verify tables with `\dt` in psql
- [ ] Verify enums with `\dT+` in psql
- [ ] Test downgrade with `alembic downgrade base`
- [ ] Re-apply with `alembic upgrade head`

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Migration | alembic | upgrade/downgrade | 100% |
| Schema | psql | Table structure | Manual |
| Integration | pytest-postgresql | CRUD operations | BRD-02 |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | localhost | PostgreSQL async connection |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Enum modification in future | High | Medium | New enums via migration, old values preserved |
| JSONB schema evolution | Medium | High | Pydantic `extra="allow"`, add optional keys only |
| Cascade delete unintended | High | Low | Test cascade behavior explicitly |

## 10. Out of Scope

- Pydantic domain models (BRD-02)
- API CRUD operations (BRD-03)
- Event type definitions (BRD-02)
- Index tuning (V2)
