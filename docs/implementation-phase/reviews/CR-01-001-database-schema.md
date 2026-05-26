# Code Review Report: BRD-01 Database Schema & Alembic Migrations

**Review ID:** CR-01-001
**BRD Reference:** [BRD-01-database-schema.md](../brds/BRD-01-database-schema.md)
**Implementation Plan:** [IP-01-database-schema.md](../implementation-plans/IP-01-database-schema.md)
**Reviewer:** Reviewer Agent
**Date:** 2026-05-26
**Iteration:** 1

---

## Executive Summary

The implementation delivers all artifacts required by BRD-01: three ORM models (`User`, `Run`, `Event`) over a single `DeclarativeBase`, an Alembic migration `001_initial_schema.py` that creates the three tables plus the three enum types, and 16 static unit tests covering metadata, foreign keys, constraints, column types, and migration source. The Coder's 7 declared deviations from the BRD §4.4 code blocks are all typing/SQLAlchemy 2.0 idiomatic improvements (`text()` wrappers on `server_default`, explicit `postgresql.UUID(as_uuid=True)`, `TYPE_CHECKING` for circular references, `foreign_keys=...` disambiguation on relationships, PEP-604 `str | None`) — none change runtime behavior beyond what is required for pyright-strict and SQLAlchemy 2.0 correctness.

The migration adds `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` (omitted from BRD §4.3 Python but present in BRD §4.2 SQL) — a substantive correctness fix. The downgrade reverses operations in the correct order and drops indexes explicitly before tables. Architectural rules (§3, §4, §5, §7) are respected.

### Overall Score: **9.0 / 10**

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Code quality | 9 / 10 | 25 % | 2.25 |
| Test coverage | 8 / 10 | 20 % | 1.60 |
| Architecture compliance | 10 / 10 | 20 % | 2.00 |
| Documentation | 9 / 10 | 15 % | 1.35 |
| Security | 9 / 10 | 10 % | 0.90 |
| Performance | 9 / 10 | 10 % | 0.90 |
| **TOTAL** | | | **9.00** |

### Verdict: ✅ **APPROVED**

Score meets the 9.0 pass threshold. Zero Blockers, zero Majors. Minors and Nits are advisory and can be deferred to BRD-02 or addressed opportunistically.

---

## Per-Criterion Breakdown

### Code Quality — 9 / 10
The ORM modules are clean, consistent, and idiomatic SQLAlchemy 2.0. The Coder correctly wraps every `server_default` in `text()` (the BRD code passed raw strings, which SQLAlchemy accepts but is less explicit), uses `postgresql.UUID(as_uuid=True)` so column types map to Python `UUID` automatically, and resolves the `Run ↔ Event` circular relationship via `TYPE_CHECKING` + `foreign_keys="Event.run_id"` / `foreign_keys=[run_id]`. Minor deduction: `stop_reason` / `question_type` / `output_format` are typed as `str | None` rather than `Literal[...]` or a Python `Enum`, leaving the 7/5/2 vocabulary unenforced at the app layer — acceptable for the storage layer but worth tightening when domain models land in BRD-02.

### Test Coverage — 8 / 10
16 unit tests, all passing in 0.15 s, cover: table registration, column nullability/uniqueness, foreign key targets + `ON DELETE` rules, the `uq_run_step` unique constraint, JSONB column type, migration revision identifiers, presence of `upgrade`/`downgrade` callables, all 7 `stop_reason` values, 5 `question_type` values, 2 `output_format` values, and the `pgcrypto` extension statement. Deduction: tests are metadata-only — they do not execute the migration against a live (or `pytest-postgresql`) database, so AC-01 (migration runs) and AC-05 (downgrade reverses cleanly) are only verified structurally. The BRD §7 explicitly defers runtime DB integration to BRD-02 / manual `alembic upgrade head`, so this is acceptable for iteration 1, but a static test asserting that `downgrade()` mentions `drop_table` for each table in reverse dependency order would close the AC-05 gap cheaply.

### Architecture Compliance — 10 / 10
All applicable rules from `docs/technical-phase/architecture.md` are honored: storage layer is concrete (not abstracted — correct per "three not-seams"), `stop_reason` enum contains the exact 7 RF-01 values, the `events` table has no `UPDATE`/`DELETE` triggers or check constraints (append-only is application-level per AC-03), `payload JSONB` has no schema-restrictive check constraints (matches Rule §5 `extra="allow"` philosophy at the Pydantic layer), and ORM enum columns all set `create_type=False` so the migration owns enum creation (Rule §7 expectation).

### Documentation — 9 / 10
Every module has a module-level docstring citing the relevant RF (RF-01, RF-03, RF-05). Inline comments explain the deferred FK on `runs.forked_at_event_id`, the rationale for `create_type=False`, and the application-level append-only semantics on `events.payload`. Migration header lists the implemented RFs. All artifacts in English per the language policy. Minor: no inline note in `Run` explaining why `relationship("Event", foreign_keys="Event.run_id")` needs the explicit `foreign_keys` (the dual FK between `runs` and `events` is non-obvious to a future maintainer).

### Security — 9 / 10
`token_hash` is `VARCHAR(64)` (matches a hex-encoded SHA-256) and the schema does not store raw tokens. Foreign-key cascade behavior is conservative and matches BRD §4.2: `users → runs → events` cascades on delete, fork lineage (`parent_run_id`, `parent_event_id`, `forked_at_event_id`) uses `SET NULL` to avoid orphan deletes. No secrets in code. The `DATABASE_URL` fallback in `alembic/env.py` (`postgres:postgres@localhost`) is a development convenience and should not ship to prod, but that is BRD-18 territory.

### Performance — 9 / 10
All four indexes from BRD §4.2 are present: `idx_users_username`, `idx_runs_owner_started` (composite with `started_at DESC` for RF-09 history listing), the partial `idx_runs_active` filtered on `stop_reason IS NULL` (cheap recovery of in-flight runs), `idx_events_run_step` (streaming), and `idx_events_run_created` (resume by `Last-Event-ID`). The `uq_run_step` unique constraint also doubles as an index. No obvious overindexing.

---

## Strengths

- **Schema correctness:** `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` was added to `upgrade()` even though BRD §4.3 omitted it — without this the `gen_random_uuid()` defaults would fail on a fresh database.
- **Downgrade hygiene:** `downgrade()` drops indexes explicitly before tables and drops enums after tables, avoiding the common Alembic mistake of leaving orphaned enum types.
- **Type safety:** explicit `postgresql.UUID(as_uuid=True)` on every UUID column means `Mapped[UUID]` resolves correctly at runtime and through pyright-strict.
- **Relationship disambiguation:** `foreign_keys="Event.run_id"` / `foreign_keys=[run_id]` correctly tells SQLAlchemy which of the two FKs between `runs` and `events` defines the `Run.events` collection — without this, mapper configuration would fail at first use because `runs.forked_at_event_id` also points into `events`.
- **Test isolation:** `test_migrations.py` loads the migration module via `importlib.util.spec_from_file_location` without invoking Alembic, so tests run in 150 ms with no DB and no Alembic env bootstrap.
- **Language policy:** all identifiers, docstrings, and comments are in English.

---

## Issues Found

### Blockers
*None.*

### Majors
*None.*

### Minors

1. **AC-05 only verified structurally.** [test_migrations.py](../../../backend/tests/test_migrations.py) does not assert that `downgrade()` references each `drop_table` / `drop_index` / `DROP TYPE` statement in reverse dependency order. Add a cheap source-substring test (or AST walk) that confirms `drop_constraint("fk_runs_forked_event"...)` appears before `drop_table("events")`, which appears before `drop_table("runs")`, which appears before `drop_table("users")`. Closes the AC-05 gap without a live DB.
2. **Enum columns typed as `str | None`.** In [run.py#L73](../../../backend/app/models/run.py#L73), [run.py#L75](../../../backend/app/models/run.py#L75), [run.py#L96](../../../backend/app/models/run.py#L96), `question_type`, `output_format`, and `stop_reason` are `Mapped[str | None]` / `Mapped[str]`. Application code can therefore assign any string and only fail at INSERT time (PG enum check). When domain Pydantic models land in BRD-02, tighten to `Mapped[StopReason | None]` using a Python `enum.Enum` or `Literal[...]` so misuse is caught by pyright.

### Nits

3. **Redundant UniqueConstraint.** [event.py#L72-L74](../../../backend/app/models/event.py#L72-L74) re-declares `UniqueConstraint("run_id", "step_index", name="uq_run_step")` via `__table_args__`. This duplicates the migration's `sa.UniqueConstraint(...)` and is harmless (and is in fact the canonical SQLAlchemy 2.0 pattern), but a one-line comment noting that the migration is the source of truth would help readers.
4. **Hardcoded DATABASE_URL fallback in env.py.** [alembic/env.py#L34-L38](../../../backend/alembic/env.py#L34-L38) defaults to `postgres:postgres@localhost`. Acceptable for dev; ensure BRD-18 / production deploy injects `DATABASE_URL` explicitly.

---

## Acceptance Criteria

| AC | Status | Evidence |
|---|---|---|
| **AC-01** Migration runs successfully | 🟡 Static-pass | Module imports, `revision = "001"`, `upgrade()`/`downgrade()` callable, all `op.*` calls well-formed. Runtime `alembic upgrade head` deferred to manual P1 (per BRD §7). |
| **AC-02** Enum values match RF-01 | ✅ Pass | All 7 `stop_reason` literals present in [migration source](../../../backend/alembic/versions/001_initial_schema.py#L33-L41); asserted by `test_stop_reason_enum_has_seven_values`. |
| **AC-03** Events append-only | ✅ Pass | No `UPDATE`/`DELETE` triggers or check constraints on `events` in migration; `payload` is unconstrained `JSONB`; append-only is documented as application-level in [event.py](../../../backend/app/models/event.py) module docstring. |
| **AC-04** Foreign keys work | ✅ Pass | All FK targets and `ON DELETE` rules match BRD §4.2; asserted by `test_foreign_keys` (CASCADE on `runs.owner_username`, `events.run_id`; SET NULL on `runs.parent_run_id`, `events.parent_event_id`). |
| **AC-05** Downgrade works | 🟡 Static-pass | `downgrade()` drops FK first, then indexes, then tables in reverse order, then enums. No runtime verification (see Minor #1). |

🟡 = Structurally verified; runtime verification deferred per BRD §7.

---

## Architecture Compliance

| Check | Status | Notes |
|---|---|---|
| Rule §3 — `stop_reason` exact 7 enum values | ✅ | Verified in migration + test. |
| Rule §4 — Events append-only at DB level | ✅ | No restrictive constraints; application-level enforcement documented. |
| Rule §5 — JSONB unrestricted (schema evolution via `extra="allow"`) | ✅ | No JSON check constraints. |
| Rule §7 — ORM enums use `create_type=False` | ✅ | All three enum types in [run.py#L23-L46](../../../backend/app/models/run.py#L23-L46). |
| Language policy — English only | ✅ | All artifacts in English. |
| `target_metadata = Base.metadata` in `env.py` | ✅ | [alembic/env.py#L23](../../../backend/alembic/env.py#L23). |
| Single-writer / single-server (no Redis, no distributed locks) | ✅ | Pure PG + SQLAlchemy async; no infra additions. |

---

## Recommendation

✅ **APPROVED.** Proceed to BRD-02 (Pydantic domain models & event types). The two Minor items are tracked here and should be folded into BRD-02 work:

- Minor #1 → add downgrade-ordering source test alongside BRD-02 schema tests.
- Minor #2 → introduce a `StopReason` / `QuestionType` / `OutputFormat` Python `Enum` (or `Literal`) in BRD-02 domain models and update the ORM `Mapped[...]` annotations to use them.

---

**Reviewer signature:** Reviewer Agent — 2026-05-26
