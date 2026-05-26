# Database Connection Skill

## Description
Specialized knowledge for PostgreSQL database operations, schema inspection, query execution, and migration management.

## When to Use
- Reviewing database schema
- Writing database queries
- Inspecting JSONB structures
- Managing Alembic migrations
- Debugging data issues

## Tech Stack Reference

- **Database**: PostgreSQL 16
- **Driver**: asyncpg
- **ORM**: SQLAlchemy 2.0 async
- **Migrations**: Alembic

## Schema Overview (Novum — RF-05)

```sql
-- Core tables (as defined in infrastructure.md)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_username VARCHAR(50) NOT NULL REFERENCES users(username),
    question TEXT NOT NULL,
    user_context TEXT,                          -- RF-07: optional guidance (max 1000 chars)
    output_format VARCHAR(20) DEFAULT 'structured', -- RF-10: 'prose' | 'structured'
    confidence_threshold FLOAT DEFAULT 0.6,    -- RF-12: 0.0-1.0
    question_type VARCHAR(20),                 -- RF-06: Type 1-8
    stop_reason VARCHAR(30),                   -- RF-02: 7 enum values
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stopped_at TIMESTAMPTZ,
    parent_run_id UUID REFERENCES runs(id),    -- RF-03: fork parent
    forked_at_event_id UUID                    -- RF-03: fork point
);

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id),
    parent_event_id UUID REFERENCES events(id), -- RF-03: event chain
    step_index INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL,                  -- ~17 event types
    payload JSONB NOT NULL,                     -- extra="allow" for evolution
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(run_id, step_index)
);

-- Indexes
CREATE INDEX idx_events_run_id ON events(run_id);
CREATE INDEX idx_events_run_step ON events(run_id, step_index);
CREATE INDEX idx_runs_owner ON runs(owner_username);
CREATE INDEX idx_runs_started ON runs(started_at DESC);
```

### Stop Reason Enum (RF-02)
```sql
-- Never free text, always one of these 7 values:
-- judge_confirmed, honest_unanswerable, honest_contradiction,
-- honest_ambiguous, stopped_by_budget, user_cancelled, errored
```

## SQLAlchemy Patterns

### Model Definition
```python
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import uuid

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending"
    )
    stop_reason: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="runs")
    events: Mapped[list["Event"]] = relationship(
        back_populates="run",
        order_by="Event.sequence_number"
    )
```

### Async Session Usage
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_run_with_events(
    session: AsyncSession,
    run_id: uuid.UUID
) -> Run | None:
    """Fetch a run with all its events."""
    result = await session.execute(
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.events))
    )
    return result.scalar_one_or_none()

async def create_event(
    session: AsyncSession,
    run_id: uuid.UUID,
    event_type: str,
    payload: dict
) -> Event:
    """Create a new event for a run."""
    # Get next sequence number
    result = await session.execute(
        select(func.coalesce(func.max(Event.sequence_number), 0) + 1)
        .where(Event.run_id == run_id)
    )
    next_seq = result.scalar_one()

    event = Event(
        run_id=run_id,
        sequence_number=next_seq,
        event_type=event_type,
        payload=payload
    )
    session.add(event)
    await session.commit()
    return event
```

## JSONB Operations

### Querying JSONB
```python
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

# Query by JSONB field
result = await session.execute(
    select(Event)
    .where(Event.payload["status"].astext == "completed")
)

# Query nested JSONB
result = await session.execute(
    select(Event)
    .where(Event.payload["metadata"]["source"].astext == "tavily")
)

# Check if key exists
result = await session.execute(
    select(Event)
    .where(Event.payload.has_key("error"))
)
```

### Updating JSONB
```python
from sqlalchemy.dialects.postgresql import insert

# Update specific key
await session.execute(
    update(Event)
    .where(Event.id == event_id)
    .values(payload=Event.payload.op("||")({"status": "updated"}))
)
```

## Alembic Migrations

### Creating Migration
```bash
# Generate migration from model changes
alembic revision --autogenerate -m "Add new column"

# Create empty migration
alembic revision -m "Custom migration"
```

### Migration Template
```python
"""Add stop_reason column to runs

Revision ID: abc123
Revises: def456
Create Date: 2026-05-26 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'runs',
        sa.Column('stop_reason', sa.String(50), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('runs', 'stop_reason')
```

### Running Migrations
```bash
# Upgrade to latest
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Check current revision
alembic current

# View migration history
alembic history
```

## Useful Queries

### Inspect Schema
```sql
-- List all tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';

-- Describe table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'events';

-- List indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'events';
```

### Debug Queries
```sql
-- Recent events by run
SELECT e.event_type, e.sequence_number, e.payload, e.created_at
FROM events e
WHERE e.run_id = 'uuid-here'
ORDER BY e.sequence_number;

-- Runs by status
SELECT status, COUNT(*) as count
FROM runs
GROUP BY status;

-- Events with specific payload
SELECT * FROM events
WHERE payload->>'error' IS NOT NULL;
```

## Testing with Database

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def db_session():
    """Create a test database session."""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost/test_db",
        echo=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```
