"""Initial database schema with users, runs, and events tables.

Revision ID: 001
Revises:
Create Date: 2026-05-26

Implements:
- RF-03: Append-only events table
- RF-05: Lightweight identity (users)
- RF-01: stop_reason enum (7 values)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ---------------------------------------------------------------------
    # Enum types
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # users
    # ---------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_users_username", "users", ["username"])

    # ---------------------------------------------------------------------
    # runs (without forked_at_event_id FK initially)
    # ---------------------------------------------------------------------
    op.create_table(
        "runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "owner_username",
            sa.String(50),
            sa.ForeignKey("users.username", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("user_context", sa.Text(), nullable=True),
        sa.Column(
            "question_type",
            postgresql.ENUM(name="question_type", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "output_format",
            postgresql.ENUM(name="output_format", create_type=False),
            nullable=False,
            server_default=sa.text("'prose'"),
        ),
        sa.Column(
            "confidence_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.7"),
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("stopped_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "stop_reason",
            postgresql.ENUM(name="stop_reason", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "forked_at_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),  # FK added after events table exists
    )
    op.create_index(
        "idx_runs_owner_started",
        "runs",
        ["owner_username", sa.text("started_at DESC")],
    )
    op.create_index(
        "idx_runs_active",
        "runs",
        ["id"],
        postgresql_where=sa.text("stop_reason IS NULL"),
    )

    # ---------------------------------------------------------------------
    # events (append-only event log, RF-03)
    # ---------------------------------------------------------------------
    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column(
            "parent_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("run_id", "step_index", name="uq_run_step"),
    )
    op.create_index("idx_events_run_step", "events", ["run_id", "step_index"])
    op.create_index("idx_events_run_created", "events", ["run_id", "created_at"])

    # ---------------------------------------------------------------------
    # FK from runs.forked_at_event_id to events.id
    # ---------------------------------------------------------------------
    op.create_foreign_key(
        "fk_runs_forked_event",
        "runs",
        "events",
        ["forked_at_event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FK first so the events table can be removed
    op.drop_constraint("fk_runs_forked_event", "runs", type_="foreignkey")

    # Drop tables in reverse dependency order
    op.drop_index("idx_events_run_created", table_name="events")
    op.drop_index("idx_events_run_step", table_name="events")
    op.drop_table("events")

    op.drop_index("idx_runs_active", table_name="runs")
    op.drop_index("idx_runs_owner_started", table_name="runs")
    op.drop_table("runs")

    op.drop_index("idx_users_username", table_name="users")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS output_format")
    op.execute("DROP TYPE IF EXISTS question_type")
    op.execute("DROP TYPE IF EXISTS stop_reason")
