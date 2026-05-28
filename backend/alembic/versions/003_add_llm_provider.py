"""Add runs.llm_provider column.

Revision ID: 003
Revises: 002
Create Date: 2026-05-27

Adds a per-run record of which LLM vendor served the request so the
choice is read-deterministic and visible at replay time.
"""

import sqlalchemy as sa

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "llm_provider",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'github'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("runs", "llm_provider")
