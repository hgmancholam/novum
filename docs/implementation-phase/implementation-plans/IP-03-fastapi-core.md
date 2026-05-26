# Implementation Plan: BRD-03 FastAPI Core & API Skeleton

**Plan ID:** IP-03
**BRD Reference:** [BRD-03-fastapi-core.md](../brds/BRD-03-fastapi-core.md)
**Created:** 2026-05-26
**Status:** Ready for Coder
**Implementation Order:** 4 of 19

---

## 1. Overview

Wire up the HTTP surface of Novum: FastAPI routers, run/event services, dependency injection, custom exceptions, and OpenAPI-friendly request/response models. This is the API contract the frontend consumes and the substrate that BRD-04 (auth), BRD-10 (SSE), and BRD-15 (fork/resume) will layer on.

**Source of truth:** BRD-03 §4 contains copy-paste-ready code blocks. The Coder must follow them verbatim unless explicitly tightened in §5 of this plan.

**Non-goals (deferred):**
- Real SSE streaming — BRD-10. `events.py` ships as a NotImplementedError placeholder (BRD-03 §4.7).
- Real token auth — BRD-04. V1 keeps the simple `X-Username` header dependency.
- Agent execution / event generation — BRD-07.
- Authorization checks beyond username extraction (cross-user run access, fork ownership rules) — BRD-04.
- Live SSE on Last-Event-ID resume — BRD-10.

---

## 2. Architectural Alignment

| Architecture rule | Compliance in this BRD |
|---|---|
| Events append-only, JSONB payload | `EventService.append_event` only INSERTs; no UPDATE/DELETE paths |
| `stop_reason` is enum, never free text | `cancel_run`/`resume_run` write `StopReason.USER_CANCELLED.value`; resume clears to `None` |
| Storage layer is a not-seam (no abstraction) | Services depend directly on `AsyncSession`; no repository pattern introduced |
| English-only code artifacts | All identifiers, docstrings, log/exception messages in English |
| Pyright strict / Ruff clean | `from __future__ import annotations`, explicit return types, no `Any` |
| Type contract FE↔BE | Reuses BRD-02 DTOs (`RunCreate`, `RunResponse`, `RunListItem`, `RunForkRequest`); no new wire types |
| FastAPI dependency injection | Single `DbSession` and `CurrentUsername` annotated dependencies, no per-route duplication |

**Cross-check with existing code (must already be true before starting):**
- `backend/app/database.py::async_session_maker` exists (BRD-01). ✓
- `backend/app/domain/run.py` exports `RunCreate`, `RunResponse`, `RunListItem`, `RunForkRequest`. ✓
- `backend/app/domain/events.py` exports `FORKABLE_EVENTS` and `BaseEvent`. ✓
- `backend/app/models/__init__.py` exports `Run` and `Event` ORM. ✓
- `backend/app/main.py` already wires CORS + structlog + lifespan (BRD-00). The BRD-03 update only adds `app.include_router(api_router)` and removes the inline `/health`.

---

## 3. Implementation Sequence

### Phase 1 — Plumbing (Steps 1–3)

| Step | Task | File | Priority |
|------|------|------|----------|
| 1 | Create `dependencies.py` with `get_db`, `DbSession`, `get_current_username`, `CurrentUsername` | [backend/app/dependencies.py](../../../backend/app/dependencies.py) | P0 |
| 2 | Create `exceptions.py` with 6 HTTPException subclasses (RunNotFound, EventNotFound, RunNotForkable, RunAlreadyStopped, RunStillRunning, Unauthorized) | [backend/app/exceptions.py](../../../backend/app/exceptions.py) | P0 |
| 3 | Create `services/__init__.py` re-exporting `RunService` and `EventService` | [backend/app/services/__init__.py](../../../backend/app/services/__init__.py) | P0 |

### Phase 2 — Services (Steps 4–5)

| Step | Task | File | Priority |
|------|------|------|----------|
| 4 | Implement `RunService`: `create_run`, `get_run`, `list_runs`, `fork_run`, `cancel_run`, `resume_run` per BRD-03 §4.5 | [backend/app/services/run_service.py](../../../backend/app/services/run_service.py) | P0 |
| 5 | Implement `EventService`: `append_event`, `get_events`, `get_event` per BRD-03 §4.6 | [backend/app/services/event_service.py](../../../backend/app/services/event_service.py) | P0 |

### Phase 3 — Routes (Steps 6–9)

| Step | Task | File | Priority |
|------|------|------|----------|
| 6 | Create `routes/health.py` with `GET /health` | [backend/app/routes/health.py](../../../backend/app/routes/health.py) | P0 |
| 7 | Create `routes/runs.py` with 6 endpoints (create, list, get, fork, cancel, resume) | [backend/app/routes/runs.py](../../../backend/app/routes/runs.py) | P0 |
| 8 | Create `routes/events.py` placeholder (returns 501 / NotImplementedError, BRD-10 will fill it) | [backend/app/routes/events.py](../../../backend/app/routes/events.py) | P0 |
| 9 | Create `routes/__init__.py` exporting an aggregated `api_router` | [backend/app/routes/__init__.py](../../../backend/app/routes/__init__.py) | P0 |

### Phase 4 — Main wiring (Step 10)

| Step | Task | File | Priority |
|------|------|------|----------|
| 10 | Update `main.py`: remove the inline `/health` route and add `app.include_router(api_router)`. Keep existing CORS, structlog, lifespan from BRD-00. | [backend/app/main.py](../../../backend/app/main.py) | P0 |

### Phase 5 — Tests (Steps 11–14) — mandatory per L-002

| Step | Task | File | Priority |
|------|------|------|----------|
| 11 | Unit tests for `RunService` (AC-01 create, AC-04 cancel, AC-05 resume, NotFound paths, fork rejects non-forkable event) — use in-memory SQLite + `Base.metadata.create_all` to avoid PostgreSQL dependency (L-004) | `backend/tests/test_run_service.py` | P0 |
| 12 | Unit tests for `EventService` (append assigns sequential `step_index`, payload excludes envelope keys, `get_events` filters by `after_step`) | `backend/tests/test_event_service.py` | P0 |
| 13 | Integration tests for routes via `httpx.AsyncClient(transport=ASGITransport(app=app))`: AC-01, AC-02, AC-03 + 401 on missing `X-Username` + 404 on unknown run + 501 on `/events` placeholder | `backend/tests/test_routes_runs.py` | P0 |
| 14 | Update existing `test_health.py` to also hit `/health` through the new router (sanity check that `api_router` is mounted) | `backend/tests/test_health.py` (modify) | P0 |

### Phase 6 — Verification (Step 15)

| Step | Task | Priority |
|------|------|----------|
| 15 | `ruff check backend && pyright backend/app/routes backend/app/services backend/app/dependencies.py backend/app/exceptions.py && pytest backend/tests -q -p no:postgresql` all green | P0 |

---

## 4. File Inventory

```
backend/
  app/
    dependencies.py            # NEW
    exceptions.py              # NEW
    services/
      __init__.py              # MODIFY (currently empty package init)
      run_service.py           # NEW
      event_service.py         # NEW
    routes/
      __init__.py              # MODIFY (currently empty package init)
      health.py                # NEW
      runs.py                  # NEW
      events.py                # NEW (placeholder)
    main.py                    # MODIFY (remove inline /health, include api_router)
  tests/
    test_run_service.py        # NEW
    test_event_service.py      # NEW
    test_routes_runs.py        # NEW
    test_health.py             # MODIFY (still passes against new router-based /health)
```

---

## 5. Technical Decisions & Tightenings

| Decision | Rationale | Source |
|----------|-----------|--------|
| **`datetime.now(timezone.utc)` instead of `datetime.utcnow()`** in `cancel_run` | `datetime.utcnow()` is deprecated in Python 3.12. The DB column is `TIMESTAMPTZ` (BRD-01), so a tz-aware UTC value is correct. | Python 3.12 deprecation |
| Reuse the existing `database.async_session_maker` for `get_db` | Avoids drift from BRD-01. Drop the duplicate `get_db` that lives in `database.py` (or have it call into the dependencies version) — pick **one** definition and re-export from `dependencies.py` only. Coder: move the canonical `get_db` to `dependencies.py` and delete it from `database.py`. | BRD-01 §4.2, BRD-03 §4.3 |
| `GET /api/runs/{id}` is **not** guarded by `X-Username` (per BRD-03 endpoint table) | RF-05 makes runs public-by-URL. List endpoint stays per-user; single-run read is shareable. | BRD-03 §4.2, RF-05 |
| `events.py` returns HTTP 501 explicitly (`HTTPException(status_code=501)`) | A raw `raise NotImplementedError` would surface as a 500. 501 is the correct semantic for "not implemented yet" and is testable. | BRD-03 §10 (out of scope) |
| `last_event_id` is read from the **header** `Last-Event-ID`, not a query parameter | The SSE spec sends it as a header on reconnect. The BRD's `Query(..., alias="Last-Event-ID")` is a typo; switch to `Header(default=None, alias="Last-Event-ID")`. Documented now to avoid a rework in BRD-10. | EventSource spec |
| Tests use SQLite in-memory with `StaticPool` for routes/services | Keeps `pytest -p no:postgresql` runs DB-free (L-004) and avoids a live Postgres requirement. The PG-specific `JSONB`, `UUID`, and ENUM types must be type-decorated so SQLAlchemy can downgrade to JSON / CHAR(36) / VARCHAR on SQLite. Coder: if the existing ORM types don't allow this cleanly, the test fixture uses `JSON().with_variant(JSONB(), "postgresql")` at fixture-creation time only, **without** modifying the production models. If type variance is non-trivial, fall back to skipping integration tests under SQLite and run them only via `pytest-postgresql` (gated behind a marker). Prefer the SQLite path. | L-004, BRD-17 |
| No `model_validate_json` / no `json.dumps` in services | All serialization stays inside Pydantic; services return DTOs not dicts (except `EventService.get_events` which is SSE-shaped and intentionally dict). | BRD-03 §4.5–4.6 |
| `RunService.list_runs` truncation (`question[:100] + "..."`) is preserved verbatim | UI expects this exact truncation behavior for the history panel (BRD-12). | BRD-03 §4.5 |

---

## 6. Acceptance-Criteria → Test Mapping

| AC | Verified by |
|----|-------------|
| AC-01 Create run | `test_routes_runs.py::test_create_run_returns_201_and_persists` |
| AC-02 List recent | `test_routes_runs.py::test_list_runs_orders_desc_by_started_at` |
| AC-03 Fork from event | `test_routes_runs.py::test_fork_run_sets_parent_and_event` + `test_run_service.py::test_fork_rejects_non_forkable_event` |
| AC-04 Cancel | `test_run_service.py::test_cancel_sets_stop_reason_user_cancelled` |
| AC-05 Resume | `test_run_service.py::test_resume_clears_stop_state` + `test_resume_rejects_judge_confirmed_run` |

Additional safety tests (not in ACs but required by BRD-03 §9 risks):
- `test_routes_runs.py::test_missing_username_returns_401`
- `test_routes_runs.py::test_unknown_run_returns_404`
- `test_routes_runs.py::test_events_placeholder_returns_501`
- `test_event_service.py::test_append_assigns_sequential_step_index`
- `test_event_service.py::test_append_excludes_envelope_keys_from_payload`

---

## 7. Verification Criteria

### Static
- [ ] `ruff check backend` clean (incl. new files)
- [ ] `pyright backend/app/routes backend/app/services backend/app/dependencies.py backend/app/exceptions.py` strict-clean
- [ ] `python -c "from app.main import app; print([r.path for r in app.routes])"` lists `/health`, `/api/runs`, `/api/runs/{run_id}`, `/api/runs/{run_id}/fork`, `/api/runs/{run_id}/cancel`, `/api/runs/{run_id}/resume`, `/api/runs/{run_id}/events`

### Tests
- [ ] `pytest backend/tests -q -p no:postgresql` green
- [ ] All 5 ACs covered by at least one named test
- [ ] Coverage ≥ 80% on `app/services/` and `app/routes/` (per Quality Gates)

### Documentation
- [ ] No deviation from BRD-03 §4 code blocks except the items listed in §5 above
- [ ] `knowledge-base-index.md`: flip BRD-03 status from `Draft` → `Implemented`; add IP-03 row; add 5 new artifact rows (`RunService`, `EventService`, `dependencies.py`, `exceptions.py`, `api_router`); flip `/api/runs/*` planned endpoints to Implemented

---

## 8. Risks & Mitigations (this iteration)

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| SQLite cannot host PG-specific types (JSONB / UUID / ENUM) used by BRD-01 ORM | Medium | If type-variance route is non-trivial, gate route integration tests behind a `@pytest.mark.postgres` marker and ship service-level tests with a hand-built minimal table. Service unit tests stay green either way. |
| `Last-Event-ID` parsing collides with FastAPI header normalization | Low | Use `Header(default=None, alias="Last-Event-ID", convert_underscores=False)`. Test in BRD-10. |
| `datetime.utcnow` slipping through if Coder copies BRD verbatim | High | Explicitly called out in §5; reviewer should flag any remaining occurrence. |
| Forgetting to delete the inline `/health` in `main.py` after including the router | Medium | Test asserts `/health` is registered exactly once in `app.routes`. |
| Auth bypass on `GET /api/runs/{id}` is intentional (RF-05) but easy to misread as a bug | Low | Plan §5 documents it; review must not flag it. |

---

## 9. Effort & Sequencing

Total estimated effort: ~2.5 hours coding + ~1.5 hours tests + ~30 min verification. No external services, no LLM calls. Single Coder pass should reach review.

---

## 10. Definition of Done

1. All files in §4 exist and match BRD-03 §4 (with §5 tightenings).
2. All 5 ACs have green tests under `pytest -p no:postgresql`.
3. `ruff` + `pyright` clean on the new surface.
4. `knowledge-base-index.md` updated.
5. `decisions-history.md` records the §5 tightenings (datetime, Last-Event-ID header, single `get_db`).
6. Reviewer scores ≥ 9/10.
