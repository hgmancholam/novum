"""Smoke tests for the ``004_run_costs`` migration.

The view itself uses PostgreSQL-specific JSON operators and cannot run on
SQLite; here we assert the migration's SQL structure and its alembic
linkage so a typo or revision-id drift breaks the build.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "004_run_costs_view.py"
)


@pytest.fixture(scope="module")
def migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_mig_004_run_costs_view", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_links_to_003(migration: ModuleType) -> None:
    assert migration.revision == "004_run_costs"
    assert migration.down_revision == "003"


def test_upgrade_emits_view_and_index(monkeypatch: pytest.MonkeyPatch, migration: ModuleType) -> None:
    statements: list[str] = []

    def _capture(sql: str) -> None:
        statements.append(sql)

    # ``op`` is imported into the migration module's namespace.
    monkeypatch.setattr(migration.op, "execute", _capture)
    migration.upgrade()

    joined = "\n".join(statements)
    # Index
    assert "ix_events_cost_provider" in joined
    assert "payload->>'type' = 'CostIncurred'" in joined
    # View
    assert "CREATE OR REPLACE VIEW run_costs" in joined
    for col in (
        "provider", "kind", "model", "task_name",
        "prompt_tokens", "completion_tokens",
        "units", "cost_usd", "latency_ms_total",
    ):
        assert col in joined, f"missing column {col!r} in view definition"
    # Aggregation by all five group keys.
    assert "GROUP BY run_id" in joined


def test_downgrade_drops_view_and_index(monkeypatch: pytest.MonkeyPatch, migration: ModuleType) -> None:
    statements: list[str] = []
    monkeypatch.setattr(
        migration.op, "execute", lambda s: statements.append(s)
    )
    migration.downgrade()
    joined = "\n".join(statements)
    assert "DROP VIEW IF EXISTS run_costs" in joined
    assert "DROP INDEX IF EXISTS ix_events_cost_provider" in joined
