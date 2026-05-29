"""Add run_costs view and partial index for CostIncurred events.

Revision ID: 004_run_costs
Revises: 003
Create Date: 2026-05-30

Materializes the cost ledger as a SQL view aggregated by run_id,
provider, kind, model and task_name (BRD-29 §4.2). A partial index on
(run_id, payload->>'provider') restricted to CostIncurred events keeps
the per-run aggregate cheap even as the events table grows.
"""

from alembic import op

revision = "004_run_costs"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_events_cost_provider
        ON events (run_id, (payload->>'provider'))
        WHERE payload->>'type' = 'CostIncurred'
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW run_costs AS
        SELECT
            run_id,
            payload->>'provider' AS provider,
            payload->>'kind'     AS kind,
            payload->>'model'    AS model,
            payload->>'task_name' AS task_name,
            COUNT(*)                                              AS call_count,
            COALESCE(SUM((payload->>'prompt_tokens')::bigint), 0)     AS prompt_tokens,
            COALESCE(SUM((payload->>'completion_tokens')::bigint), 0) AS completion_tokens,
            COALESCE(SUM((payload->>'units')::bigint), 0)             AS units,
            COALESCE(SUM((payload->>'cost_usd')::double precision), 0.0) AS cost_usd,
            COALESCE(SUM((payload->>'latency_ms')::bigint), 0)        AS latency_ms_total
        FROM events
        WHERE payload->>'type' = 'CostIncurred'
        GROUP BY run_id, payload->>'provider', payload->>'kind',
                 payload->>'model', payload->>'task_name'
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS run_costs")
    op.execute("DROP INDEX IF EXISTS ix_events_cost_provider")
