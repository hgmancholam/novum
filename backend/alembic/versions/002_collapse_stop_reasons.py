"""Collapse StopReason enum from 7 to 4 values (WP-3).

Revision ID: 002
Revises: 001
Create Date: 2026-05-27

Implements:
- WP-3: StopReason collapse (honest_unanswerable, honest_contradiction,
  honest_ambiguous → judge_confirmed)
- M2: Preserves legacy values in events.payload.legacy_stop_reason for
  historical runs

Amendment rationale: honest stops are now "answers" with AnswerKind
selection (best_effort, weighted, scenario). The 3 honest_* terminals
collapse into judge_confirmed with kind-specific confidence ceilings.
"""

from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Collapse stop_reason enum to 4 values and preserve legacy values in JSONB."""
    # Step 1: Add legacy_stop_reason to events.payload (JSONB column accepts any key)
    # We'll update the payload with SQL directly since JSONB supports arbitrary keys
    op.execute(
        """
        UPDATE events
        SET payload = payload || jsonb_build_object('legacy_stop_reason', payload->>'stop_reason')
        WHERE type = 'Stopped'
        """
    )

    # Step 2: Map honest_* values in runs.stop_reason to judge_confirmed for display
    # (The source of truth is events; runs.stop_reason is denormalized for queries)
    op.execute(
        """
        UPDATE runs
        SET stop_reason = 'judge_confirmed'
        WHERE stop_reason IN ('honest_unanswerable', 'honest_contradiction', 'honest_ambiguous')
        """
    )

    # Step 3: Drop the old enum constraint from runs table
    op.execute("ALTER TABLE runs ALTER COLUMN stop_reason DROP DEFAULT")
    op.execute("ALTER TABLE runs ALTER COLUMN stop_reason TYPE text USING stop_reason::text")

    # Step 4: Drop and recreate the enum type with only 4 values
    op.execute("DROP TYPE IF EXISTS stop_reason CASCADE")
    new_stop_reason_enum = postgresql.ENUM(
        "judge_confirmed",
        "stopped_by_budget",
        "user_cancelled",
        "errored",
        name="stop_reason",
    )
    new_stop_reason_enum.create(op.get_bind(), checkfirst=False)

    # Step 5: Re-apply the enum type to the runs.stop_reason column
    op.execute(
        """
        ALTER TABLE runs
        ALTER COLUMN stop_reason TYPE stop_reason
        USING stop_reason::stop_reason
        """
    )


def downgrade() -> None:
    """Restore the 7-value enum and legacy_stop_reason from events.payload."""
    # Step 1: Convert runs.stop_reason back to text
    op.execute("ALTER TABLE runs ALTER COLUMN stop_reason DROP DEFAULT")
    op.execute("ALTER TABLE runs ALTER COLUMN stop_reason TYPE text USING stop_reason::text")

    # Step 2: Restore judge_confirmed → honest_unanswerable where legacy value exists
    # (This is lossy: we map all former honest_* back to honest_unanswerable for simplicity)
    op.execute(
        """
        UPDATE runs
        SET stop_reason = COALESCE(
            (SELECT e.payload->>'legacy_stop_reason'
             FROM events e
             WHERE e.run_id = runs.id AND e.type = 'Stopped'
             LIMIT 1),
            stop_reason
        )
        WHERE stop_reason = 'judge_confirmed'
        """
    )

    # Step 3: Drop and recreate the old 7-value enum
    op.execute("DROP TYPE IF EXISTS stop_reason CASCADE")
    old_stop_reason_enum = postgresql.ENUM(
        "judge_confirmed",
        "honest_unanswerable",
        "honest_contradiction",
        "honest_ambiguous",
        "stopped_by_budget",
        "user_cancelled",
        "errored",
        name="stop_reason",
    )
    old_stop_reason_enum.create(op.get_bind(), checkfirst=False)

    # Step 4: Re-apply the enum to the column
    op.execute(
        """
        ALTER TABLE runs
        ALTER COLUMN stop_reason TYPE stop_reason
        USING stop_reason::stop_reason
        """
    )

    # Step 5: Remove legacy_stop_reason from events.payload
    op.execute(
        """
        UPDATE events
        SET payload = payload - 'legacy_stop_reason'
        WHERE type = 'Stopped' AND payload ? 'legacy_stop_reason'
        """
    )
