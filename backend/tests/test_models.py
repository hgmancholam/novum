"""Unit tests for ORM models — metadata-only, no live database required."""

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Base, Event, Run, User


def test_tables_registered() -> None:
    """Base.metadata must contain exactly the three core tables."""
    assert set(Base.metadata.tables.keys()) == {"users", "runs", "events"}


def test_user_model_export() -> None:
    """User model maps to the 'users' table."""
    assert User.__tablename__ == "users"


def test_run_model_export() -> None:
    """Run model maps to the 'runs' table."""
    assert Run.__tablename__ == "runs"


def test_event_model_export() -> None:
    """Event model maps to the 'events' table."""
    assert Event.__tablename__ == "events"


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def test_users_columns() -> None:
    """Users table has the expected columns with correct nullability and unique."""
    table = Base.metadata.tables["users"]
    expected = {"id", "username", "token_hash", "created_at"}
    assert set(table.columns.keys()) == expected

    assert table.columns["id"].primary_key is True
    assert table.columns["username"].nullable is False
    assert table.columns["username"].unique is True
    assert table.columns["token_hash"].nullable is False
    assert table.columns["created_at"].nullable is False


def test_runs_columns() -> None:
    """Runs table exposes every documented column."""
    table = Base.metadata.tables["runs"]
    required = {
        "id",
        "owner_username",
        "question",
        "user_context",
        "question_type",
        "output_format",
        "confidence_threshold",
        "started_at",
        "stopped_at",
        "stop_reason",
        "parent_run_id",
        "forked_at_event_id",
    }
    assert required.issubset(set(table.columns.keys()))

    assert table.columns["owner_username"].nullable is False
    assert table.columns["question"].nullable is False
    assert table.columns["user_context"].nullable is True
    assert table.columns["question_type"].nullable is True
    assert table.columns["output_format"].nullable is False
    assert table.columns["confidence_threshold"].nullable is False
    assert table.columns["stop_reason"].nullable is True


def test_events_columns() -> None:
    """Events table exposes every documented column."""
    table = Base.metadata.tables["events"]
    required = {
        "id",
        "run_id",
        "step_index",
        "parent_event_id",
        "type",
        "payload",
        "created_at",
    }
    assert required.issubset(set(table.columns.keys()))

    assert table.columns["run_id"].nullable is False
    assert table.columns["step_index"].nullable is False
    assert table.columns["parent_event_id"].nullable is True
    assert table.columns["type"].nullable is False
    assert table.columns["payload"].nullable is False


# ---------------------------------------------------------------------------
# Foreign keys
# ---------------------------------------------------------------------------


def _fk_for(table_name: str, column_name: str) -> tuple[str, str]:
    """Return (target table, ondelete rule) for the single FK of a column."""
    table = Base.metadata.tables[table_name]
    fks = list(table.columns[column_name].foreign_keys)
    assert len(fks) == 1, (
        f"Expected exactly 1 FK on {table_name}.{column_name}, got {len(fks)}"
    )
    fk = fks[0]
    return fk.column.table.name, (fk.ondelete or "").upper()


def test_foreign_keys() -> None:
    """Foreign key targets and ON DELETE rules match the schema spec."""
    # runs.owner_username -> users.username (CASCADE)
    target, ondelete = _fk_for("runs", "owner_username")
    assert target == "users"
    assert ondelete == "CASCADE"

    # events.run_id -> runs.id (CASCADE)
    target, ondelete = _fk_for("events", "run_id")
    assert target == "runs"
    assert ondelete == "CASCADE"

    # events.parent_event_id -> events.id (SET NULL)
    target, ondelete = _fk_for("events", "parent_event_id")
    assert target == "events"
    assert ondelete == "SET NULL"

    # runs.parent_run_id -> runs.id (SET NULL)
    target, ondelete = _fk_for("runs", "parent_run_id")
    assert target == "runs"
    assert ondelete == "SET NULL"


# ---------------------------------------------------------------------------
# Constraints & column types
# ---------------------------------------------------------------------------


def test_unique_constraint_run_step() -> None:
    """events table must have a unique constraint named uq_run_step on (run_id, step_index)."""
    table = Base.metadata.tables["events"]
    unique_constraints = [
        c for c in table.constraints if isinstance(c, UniqueConstraint)
    ]
    matching = [c for c in unique_constraints if c.name == "uq_run_step"]
    assert len(matching) == 1, (
        f"Expected uq_run_step unique constraint, found: "
        f"{[c.name for c in unique_constraints]}"
    )
    columns = [col.name for col in matching[0].columns]
    assert columns == ["run_id", "step_index"]


def test_event_payload_is_jsonb() -> None:
    """events.payload must be a JSONB column."""
    table = Base.metadata.tables["events"]
    assert isinstance(table.columns["payload"].type, JSONB)
