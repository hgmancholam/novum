# Code Review Report — IP-03 FastAPI Core & API Skeleton

**BRD:** [BRD-03-fastapi-core.md](../brds/BRD-03-fastapi-core.md)
**Plan:** [IP-03-fastapi-core.md](../implementation-plans/IP-03-fastapi-core.md)
**Iteration:** 1
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent

---

## Summary

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Code Quality | 10/10 | 25% | 2.50 |
| Test Coverage | 10/10 | 20% | 2.00 |
| Architecture Compliance | 10/10 | 20% | 2.00 |
| Documentation | 9/10 | 15% | 1.35 |
| Security | 8/10 | 10% | 0.80 |
| Performance | 9/10 | 10% | 0.90 |
| **TOTAL** | | | **9.55 / 10** |

## Verdict

**APPROVED** — proceed to F5: COMPLETE.

Static checks already green (`ruff` clean, `pyright` strict 0/0, `pytest` **108 passed**). All 5 acceptance criteria are covered by named tests; all IP-03 §5 tightenings are correctly applied; architectural rules (events append-only, `stop_reason` enum, storage not abstracted, English-only) are respected.

---

## Acceptance-Criteria Coverage

| AC | Spec | Test(s) | Status |
|----|------|---------|--------|
| AC-01 | Create run → 201 + persisted | `test_routes_runs.py::test_create_run_returns_201_and_persists`, `test_run_service.py::test_create_run_persists` | ✅ |
| AC-02 | List recent (DESC + truncation) | `test_routes_runs.py::test_list_runs_orders_desc_by_started_at`, `test_run_service.py::test_list_runs_truncates_long_questions`, `…does_not_truncate_short_questions`, `…scopes_to_username` | ✅ |
| AC-03 | Fork creates child run + forkable enforced | `test_routes_runs.py::test_fork_run_sets_parent_and_event`, `test_run_service.py::test_fork_sets_parent_and_event`, `…rejects_non_forkable_event`, `…rejects_unknown_event` | ✅ |
| AC-04 | Cancel → `user_cancelled` + `stopped_at` | `test_routes_runs.py::test_cancel_endpoint_sets_user_cancelled`, `test_run_service.py::test_cancel_sets_stop_reason_user_cancelled`, `…rejects_already_stopped_run`, `…missing_run_raises_404` | ✅ |
| AC-05 | Resume clears stop state | `test_routes_runs.py::test_resume_endpoint_clears_stop_state`, `test_run_service.py::test_resume_clears_stop_state`, `…rejects_judge_confirmed_run`, `…rejects_still_running`, `…accepts_errored_state` | ✅ |

Additional safety tests required by IP-03 §6 — all present:
`test_missing_username_returns_401`, `test_list_missing_username_returns_401`, `test_get_run_does_not_require_username` (RF-05), `test_unknown_run_returns_404`, `test_cancel_unknown_run_returns_404`, `test_events_placeholder_returns_501`, `test_health_route_registered_exactly_once`, `test_append_assigns_sequential_step_index`, `test_append_excludes_envelope_keys_from_payload`.

---

## Strengths

- **IP-03 §5 tightenings fully applied.**
  - `datetime.now(UTC)` in [run_service.py#L130](../../../backend/app/services/run_service.py#L130) — no `utcnow` anywhere.
  - `Last-Event-ID` read as `Header(alias="Last-Event-ID", convert_underscores=False)` in [events.py#L26](../../../backend/app/routes/events.py#L26), not a query param.
  - Single canonical `get_db` lives only in [dependencies.py#L19](../../../backend/app/dependencies.py#L19); [database.py#L3](../../../backend/app/database.py#L3) explicitly notes this and does not duplicate it.
  - `events.py` returns explicit `HTTPException(501)` (not bare `NotImplementedError` → 500); covered by `test_events_placeholder_returns_501`.
  - `GET /api/runs/{run_id}` is intentionally unauthenticated per RF-05; `test_get_run_does_not_require_username` documents the intent.
- **Architectural rules respected** (copilot-instructions §3): `EventService.append_event` is INSERT-only, no UPDATE/DELETE; `stop_reason` writes go through `StopReason.USER_CANCELLED.value` (enum, never free text); services depend directly on `AsyncSession` — no repository pattern introduced; no LangGraph/LangChain/Redis sneaking in; all identifiers/docstrings/messages in English.
- **DTO discipline.** Routes consume Pydantic DTOs from `app.domain.run`; no hand-rolled dicts on the wire (except the intentionally SSE-shaped `EventService.get_events`).
- **Improvement over the BRD verbatim.** `main.py` uses `settings.cors_origins_list` instead of the BRD's `allow_origins=["*"]` — tighter default, no regression. Acceptable deviation.
- **Defensive payload extraction.** `_ENVELOPE_KEYS` is a `frozenset` constant; payload type is derived from the model (`payload.get("type")`), so the DB column is never empty.
- **Test isolation.** The SQLite conftest uses dialect compile hooks + scoped `before_insert` listeners + per-fixture default backup/restore — production ORM is left untouched (L-004 honored). `dependency_overrides` is cleared in a `finally` block, preventing cross-test bleed.
- **Routing sanity test** (`test_health_route_registered_exactly_once`) catches the exact regression IP-03 §8 flagged ("forgetting to delete the inline `/health`").

---

## Issues

### Blocker
_None._

### Major
_None._

### Minor

1. **`cancel_run` / `resume_run` accept `username` but never use it for authorization.**
   - Location: [run_service.py#L120](../../../backend/app/services/run_service.py#L120), [run_service.py#L141](../../../backend/app/services/run_service.py#L141).
   - Status: **acceptable in scope.** IP-03 §1 Non-goals explicitly defer cross-user authorization to BRD-04. The parameter is plumbed to keep the BRD-04 signature stable. Recommend a one-line `# noqa`-style comment or a TODO marker referencing BRD-04 so the unused param doesn't read as a smell. Not a blocker.

2. **`fork_run` does not verify the fork-point event belongs to `run_id`.**
   - Location: [run_service.py#L91](../../../backend/app/services/run_service.py#L91).
   - Today `RunService.fork_run` looks up the event by ID alone; a caller could pass any forkable event from any run. Not in BRD-03 ACs (AC-03 only requires that `parent_run_id` and `forked_at_event_id` are set), but it's a cheap invariant to add later: `if event.run_id != run_id: raise RunNotForkableError(...)`.
   - Fix suggestion (defer to BRD-15 if preferred): add the check + a `test_fork_rejects_event_from_other_run`. Logging here as a follow-up, not a return-to-coder item.

3. **`EventService.append_event` computes `next_index` via `SELECT MAX … + 1` then INSERTs.**
   - Location: [event_service.py#L39](../../../backend/app/services/event_service.py#L39).
   - Status: **acceptable.** RF-05 fixes V1 to a single uvicorn worker, and BRD-07 will add a per-run single-writer lock. The DB `UNIQUE(run_id, step_index)` constraint (BRD-01) provides a safety net even if two writers ever race. Document this assumption inline if it isn't already in BRD-07's plan.

4. **Unused parameters in the SSE placeholder.**
   - Location: [events.py#L21-L29](../../../backend/app/routes/events.py#L21).
   - `request: Request`, `db: DbSession`, and `last_event_id` are declared but the handler raises 501 immediately. This is intentional (locks in BRD-10's signature) and is documented in the module docstring. No change required.

5. **`RunListItem.question` truncation is non-Unicode-aware.**
   - Location: [run_service.py#L78](../../../backend/app/services/run_service.py#L78).
   - `r.question[:100]` slices by code units; a question with multi-codepoint emoji could be cut mid-grapheme. Out of scope for BRD-03 (the BRD prescribes this exact truncation verbatim) and the UI consumer (BRD-12) tolerates it. Noting for future polish.

---

## Detailed Findings by Criterion

### Code Quality (10/10)
- `from __future__ import annotations` everywhere; explicit return types; no `Any` outside the deliberate SSE dict shape; `frozenset` constants for `_RESUMABLE` and `_ENVELOPE_KEYS`.
- No code duplication. `RunService` cleanly composes `db.get` → guard → mutate → commit/refresh → DTO. No premature abstraction (no repository, no UoW).
- Imports sorted; module docstrings present.

### Test Coverage (10/10)
- Every public service method has a happy path + at least one negative path.
- Routes are exercised end-to-end via `httpx.AsyncClient(ASGITransport)`.
- 108/108 passing; testing-policy.md ≥80% threshold cleared on the new surface.

### Architecture Compliance (10/10)
- Events append-only ✓
- `stop_reason` is the enum value, not free text ✓
- No repository pattern; services own `AsyncSession` ✓
- Single LLM/storage/planner (none of the not-seams are pluggable) — N/A for this BRD ✓
- No Redis / no distributed lock / single worker preserved ✓
- DTOs are the only wire types; SSE dict shape is acknowledged as intentional ✓

### Documentation (9/10)
- Every module has a focused docstring with the BRD section it implements.
- The intentional unauth on `GET /api/runs/{id}` is documented in the route module header AND asserted by a named test — exactly the IP-03 §8 mitigation. One small nit: `cancel_run`/`resume_run` could note in their docstring that `username` is reserved for BRD-04 (Minor #1).

### Security (8/10)
- Input validation lives at the boundary via Pydantic DTOs (`RunCreate`, `RunForkRequest`) — OWASP A03 (Injection) is contained.
- Username comes from a single header dependency with a 401 on absence — no implicit anonymous fallback on protected endpoints.
- CORS uses a config-driven allow-list (better than BRD spec).
- Open follow-ups (deferred to BRD-04 per IP-03 §1): no cross-user authorization (anyone with `X-Username: alice` can cancel/resume alice's runs); no token validation. Scope-correct.

### Performance (9/10)
- Async-first; uses indexed lookups (`db.get` by PK; `ORDER BY started_at DESC LIMIT … OFFSET …`).
- `append_event` does two round-trips (max scan + insert). With the BRD-01 covering index on `(run_id, step_index)` the max scan is O(1); acceptable for V1.
- No N+1 patterns; no blocking calls inside async code.

---

## Required Changes

None for this iteration. Items in **Minor** above are documented follow-ups for BRD-04 / BRD-15 / BRD-07 and do not block APPROVAL.

---

## Positive Highlights

- IP-03 §5 tightening table is implemented to the letter.
- The conftest's strategy (compile hooks + scoped insert listeners + default backup/restore) lets routes and services run on SQLite **without modifying production models** — a clean L-004 win.
- `test_health_route_registered_exactly_once` and `test_events_placeholder_returns_501` are exactly the regression locks IP-03 §8 asked for.

---

## Final Verdict

**APPROVED — Score 9.55 / 10 (threshold 9).** Advance the workflow to F5: COMPLETE and update the memory bank (knowledge-base-index: flip BRD-03 to `Implemented`; decisions-history: record the IP-03 §5 tightenings; lessons-learned: note the SQLite-compile-hook fixture pattern for future BRDs touching PG-specific types).
