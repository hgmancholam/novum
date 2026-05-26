# Implementation Plan: BRD-01 Database Schema & Alembic Migrations

**Plan ID:** IP-01
**BRD Reference:** [BRD-01-database-schema.md](../brds/BRD-01-database-schema.md)
**Created:** 2026-05-26
**Status:** In Progress
**Implementation Order:** 2 of 19

---

## 1. Overview

Implement the PostgreSQL 16 database schema with three core tables (`users`, `runs`, `events`), three enum types (`stop_reason`, `question_type`, `output_format`), and the corresponding SQLAlchemy 2.0 async ORM models. Deliver the first Alembic migration `001_initial_schema.py` that creates the full schema and is verified to upgrade and downgrade cleanly. The `events` table is the append-only source of truth (RF-03); enums encode the 7 terminal `stop_reason` values verbatim (RF-01); `users` provides the lightweight username identity (RF-05).

**Non-goals (out of scope for this BRD):** Pydantic event models (BRD-02), API endpoints (BRD-03), authentication logic (BRD-04), event-type discriminator catalog (BRD-02).

## 2. Implementation Sequence

### Phase 1: ORM Models (Steps 1–5)

| Step | Task | Files to Create/Modify | Priority |
|------|------|------------------------|----------|
| 1 | Declarative `Base` | [backend/app/models/base.py](../../../backend/app/models/base.py) | P0 |
| 2 | `User` model (RF-05) | [backend/app/models/user.py](../../../backend/app/models/user.py) | P0 |
| 3 | `Run` model (FKs, enums, fork columns) | [backend/app/models/run.py](../../../backend/app/models/run.py) | P0 |
| 4 | `Event` model (JSONB payload, lineage) | [backend/app/models/event.py](../../../backend/app/models/event.py) | P0 |
| 5 | Package exports | [backend/app/models/__init__.py](../../../backend/app/models/__init__.py) | P0 |

### Phase 2: Alembic Migration (Steps 6–8)

| Step | Task | Files | Priority |
|------|------|-------|----------|
| 6 | Wire `target_metadata = Base.metadata` in env.py | [backend/alembic/env.py](../../../backend/alembic/env.py) | P0 |
| 7 | Initial migration `001_initial_schema.py` (upgrade + downgrade) | `backend/alembic/versions/001_initial_schema.py` | P0 |
| 8 | Verify `alembic upgrade head` against local Postgres | (runtime) | P1 |

### Phase 3: Unit Tests (Steps 9–11) — mandatory per F3.S3 / L-002

| Step | Task | Files | Priority |
|------|------|-------|----------|
| 9 | ORM metadata smoke tests (table names, columns, indexes, constraints) — no live DB needed | `backend/tests/test_models.py` | P0 |
| 10 | Migration script importability + revision identifiers | `backend/tests/test_migrations.py` | P0 |
| 11 | Run full backend suite (`pytest`) and confirm green | (runtime) | P0 |

## 3. File Inventory

```
backend/
  alembic/
    env.py                                  # MODIFY (target_metadata)
    versions/
      001_initial_schema.py                 # NEW
  app/
    models/
      __init__.py                           # NEW
      base.py                               # NEW
      user.py                               # NEW
      run.py                                # NEW
      event.py                              # NEW
  tests/
    test_models.py                          # NEW
    test_migrations.py                      # NEW
```

## 4. Technical Decisions

| Decision | Rationale | Source |
|----------|-----------|--------|
| `create_type=False` on ORM `ENUM` columns | Enum lifecycle owned by Alembic migration, not ORM autocreate | BRD-01 §4.4 |
| Postgres `gen_random_uuid()` via `pgcrypto` | Native server-side UUIDs, no app-side generation | BRD-01 §4.2 |
| FK `runs.forked_at_event_id → events.id` added **after** `events` table | Resolves circular dependency cleanly | BRD-01 §4.3 |
| `payload JSONB DEFAULT '{}'` | Schema enforced at Pydantic boundary, DB stays flexible | RF-03, Arch rule §5 |
| `extra="allow"` will live on Pydantic event models (BRD-02), **not** on DB columns | Schema evolution at the type layer, not the table layer | Arch rule §5 |
| `idx_runs_active` partial index `WHERE stop_reason IS NULL` | Optimizes active-run lookups (RF-09) | BRD-01 §4.2 |
| ORM metadata tests do **not** require a live Postgres | Keep CI fast; full integration tests deferred to BRD-02 | BRD-01 §7 |

## 5. Verification Criteria

### Static
- [ ] `ruff check backend` clean
- [ ] `pyright` strict clean on `backend/app/models/**` and `backend/alembic/**`
- [ ] `pytest backend/tests/test_models.py backend/tests/test_migrations.py` green

### Runtime (manual, P1)
- [ ] `alembic upgrade head` succeeds on a local `novum` database
- [ ] `psql novum -c "\dT+ stop_reason"` lists the 7 RF-01 values in order
- [ ] `psql novum -c "\dt"` lists `users`, `runs`, `events`
- [ ] `alembic downgrade base` drops tables and enums; re-upgrade succeeds

### Acceptance Criteria Coverage

| AC | Verified By |
|----|-------------|
| AC-01 Migration runs | Runtime verification + `test_migrations.py` (importability) |
| AC-02 Enum values match RF-01 | `test_migrations.py::test_stop_reason_enum_values` (parses migration constants) |
| AC-03 Events append-only at app layer | Documented; enforced in BRD-07 |
| AC-04 FKs work | `test_models.py::test_foreign_keys` (metadata inspection) |
| AC-05 Downgrade works | Runtime verification |

## 6. Dependencies

- **Upstream:** BRD-00 complete (folder structure, `pyproject.toml`, `alembic.ini`, `app/database.py`, `app/config.py`).
- **Runtime:** PostgreSQL 16 reachable via `DATABASE_URL` (for manual verification only — unit tests do not require it).
- **Downstream blockers:** BRD-02 (Pydantic event models), BRD-03 (FastAPI endpoints), BRD-04 (User auth).

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Circular FK (`runs ↔ events`) breaks single-transaction migration | Medium | High | Create `events` after `runs`, then `ALTER TABLE runs ADD CONSTRAINT` for `forked_at_event_id` — already in BRD-01 §4.3 |
| `pyright strict` fails on `Mapped[Optional[UUID]]` with `ENUM(create_type=False)` | Low | Medium | Use `sqlalchemy.dialects.postgresql.ENUM` typed as `Mapped[str]` per BRD-01 §4.4 |
| `pgcrypto` extension missing on target DB | Low | High | Add `CREATE EXTENSION IF NOT EXISTS pgcrypto` at top of `upgrade()` |
| Hidden coupling between ORM and migration enums | Low | Medium | Single source of truth for enum **values**: defined in migration; ORM references by `name=` only |

## 8. Memory Bank Updates (post-implementation)

- `.github/memory-bank/logs/decisions-history.md` → log the 7 technical decisions in §4.
- `.github/memory-bank/indices/knowledge-base-index.md` → mark BRD-01 status In Progress → Done, add IP-01 row, add migration file under "Database Entities".
- `.github/memory-bank/logs/lessons-learned.md` → only if something new surfaces during F3/F4.

---

*Created by Orchestrator Agent — F2 phase of [workflow.yaml](../../../.github/workflow.yaml).*
