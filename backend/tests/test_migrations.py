"""Static tests for the 001_initial_schema Alembic migration.

These tests inspect the migration module without executing it against
a live database (runtime DB verification is a manual P1 step).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

MIGRATION_PATH: Path = (
    Path(__file__).parent.parent / "alembic" / "versions" / "001_initial_schema.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_001", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_source() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_module_imports() -> None:
    """Migration module loads and declares the expected revision identifiers."""
    module = _load_migration()
    assert module.revision == "001"
    assert module.down_revision is None


def test_migration_has_upgrade_and_downgrade() -> None:
    """Migration module exposes callable upgrade() and downgrade()."""
    module = _load_migration()
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_stop_reason_enum_has_seven_values() -> None:
    """All 7 RF-01 stop_reason values appear in the migration source."""
    source = _migration_source()
    expected = [
        "judge_confirmed",
        "honest_unanswerable",
        "honest_contradiction",
        "honest_ambiguous",
        "stopped_by_budget",
        "user_cancelled",
        "errored",
    ]
    for value in expected:
        assert f'"{value}"' in source, f"Missing stop_reason value: {value}"


def test_question_type_enum_values() -> None:
    """All 5 question_type values (RF-06) appear in the migration source."""
    source = _migration_source()
    for value in ["factual", "comparative", "definitional", "state_of_art", "causal"]:
        assert f'"{value}"' in source, f"Missing question_type value: {value}"


def test_output_format_enum_values() -> None:
    """Both output_format values (RF-10) appear in the migration source."""
    source = _migration_source()
    for value in ["prose", "structured"]:
        assert f'"{value}"' in source, f"Missing output_format value: {value}"


def test_pgcrypto_extension_created() -> None:
    """pgcrypto extension is created at the top of upgrade()."""
    source = _migration_source()
    assert (
        'CREATE EXTENSION IF NOT EXISTS "pgcrypto"' in source
        or "CREATE EXTENSION IF NOT EXISTS pgcrypto" in source
    )
