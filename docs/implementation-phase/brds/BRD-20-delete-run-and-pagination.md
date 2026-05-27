# BRD-20: Delete Finished Run & History Pagination

**Document ID:** BRD-20
**Version:** 1.1
**Status:** Draft (F1 iter 2)
**Author:** BSA Agent
**Date:** 2026-05-27
**Implementation Order:** 20 of 20

---

## 1. Executive Summary

Allow the authenticated owner of a **finished** run to permanently delete it from the History panel via a hover-revealed trash icon, with **no confirmation dialog**, and replace the current `limit/offset` list endpoint with a **keyset-paginated** stream of 20 items plus a "More" affordance to load subsequent pages.

Deletion is destructive and final: every `events` row of the run is removed via the existing `ON DELETE CASCADE`. Forks descending from the deleted run are kept alive but lose their lineage pointer (`parent_run_id` → `NULL`) via the existing `ON DELETE SET NULL`. In-progress runs cannot be deleted — they must be cancelled first.

The trust contract (RF-13) is honored by an animated removal of the card so the user perceives the cascade, and by a visible "More" button so the list size is never opaque.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-05 | Cross-session persistence — owner controls own runs | **Complete** (delete is owner-scoped; list is now also owner-scoped — symmetric contract, see §4.5 and §11 #2) |
| RF-09 | History panel discovery & pagination | Complete (replaces ad-hoc `limit/offset`) |
| RF-13 | UI as trust contract — visible affordance + animated removal | Complete |
| RF-03 | Re-examinable runs — fork lineage handling on delete | Partial (orphan-but-keep policy) |

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-01 (DB schema — `events.run_id ON DELETE CASCADE`, `runs.parent_run_id ON DELETE SET NULL` already in place) | Backend delete |
| BRD-04 (User identity — `X-Username` ownership check) | 403 path |
| BRD-09 (Stop-reason enum — `stop_reason IS NOT NULL` ⇔ terminal) | 409 path |
| BRD-12 (History Panel — `HistoryItem`, `useRunHistory`) | Frontend integration |

No new dependencies on external services; no new env vars; no new migrations.

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    routes/
      runs.py                      # MODIFY: add DELETE, refactor GET list
    services/
      run_service.py               # MODIFY: delete_run(), list_runs_keyset()
    domain/
      run.py                       # MODIFY: add RunListPage (envelope w/ has_more, next_cursor)
    exceptions.py                  # MODIFY: add RunNotFinishedError, RunForbiddenError
  tests/
    test_routes_runs.py            # MODIFY: cover DELETE + paginated GET
    test_run_service.py            # MODIFY: ownership, terminal-state guard, keyset

frontend/
  src/
    types/
      history.ts                   # MODIFY: HistoryResponse → { items, has_more, next_cursor }
    lib/
      api.ts                       # MODIFY: getRunHistory(cursor), deleteRun() — already drafted in BRD-12
    hooks/
      useRunHistory.ts             # MODIFY: useInfiniteQuery wiring, useDeleteRun w/ optimistic update
    components/
      organisms/
        HistoryPanel.tsx           # MODIFY: render "More" button, hide when !has_more
        HistoryItem.tsx            # MODIFY: hover trash icon, exit animation
        HistoryItem.test.tsx       # MODIFY: cover hover + delete + a11y
```

### 4.2 Database Schema

**No migration required.** Both cascade rules are already configured (verified in `backend/app/models/event.py` and `backend/app/models/run.py`):

```sql
-- events.run_id  → runs.id  ON DELETE CASCADE     ✓ in place
-- runs.parent_run_id → runs.id ON DELETE SET NULL ✓ in place
-- events.forked_at_event_id → events.id ON DELETE SET NULL ✓ in place
```

SQLAlchemy relationship `Run.events` already declares `cascade="all, delete-orphan"`, so deleting a `Run` via the ORM removes its events both in-session and at the DB layer.

### 4.3 Alembic Migration

None.

### 4.4 Pydantic Models

```python
# app/domain/run.py (additions)

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID

class RunListPage(BaseModel):
    """Keyset-paginated page of run summaries (RF-09)."""
    model_config = ConfigDict(extra="allow")

    items: list[RunListItem]
    has_more: bool
    next_cursor: str | None = None  # opaque base64("<iso8601>|<uuid>")
```

The cursor encodes the `(started_at, id)` tuple of the **last item of the current page**; the next request returns rows strictly `(started_at, id) < cursor` under `ORDER BY started_at DESC, id DESC`.

> **`next_cursor` semantics (clarification):** when `has_more` is `false`, `next_cursor` is **always** `null`, regardless of whether the page returned items (empty page or last non-empty page). Clients MUST NOT issue further `GET /api/runs` requests once they have observed `has_more=false`.

### 4.5 API Endpoints

| Method | Path | Auth | Request | Response | Status codes |
|--------|------|------|---------|----------|--------------|
| `GET`    | `/api/runs?limit=20&cursor=<opaque>` | `X-Username` + `X-Token` (required, owner-scoped) | — | `RunListPage` | 200, 400, **401** |
| `DELETE` | `/api/runs/{run_id}` | `X-Username` + `X-Token` (required, owner-only) | — | empty body | **204**, 401, 403, 404, 409 |

**`GET /api/runs` — breaking change to response shape.** The previous return `list[RunListItem]` becomes `RunListPage`. BRD-12 already documents the envelope (`items`, `hasMore`) on the frontend side; the rename `hasMore → has_more` aligns with snake_case JSON convention used elsewhere (`stop_reason`, `started_at`). Frontend types regenerate via `scripts/export_types.py`.

**Owner scoping (resolves §11 #2).** `GET /api/runs` is now strictly owner-scoped. The service signature is `list_runs_keyset(username: str, limit: int, cursor: str | None)` (the `username | None` overload from v1.0 is **removed**). The SQL contract gains a mandatory predicate:

```sql
SELECT ...
FROM runs
WHERE owner_username = :username                 -- enforced by the route, not optional
  AND (started_at, id) < (:cursor_started_at, :cursor_id)  -- only when cursor is present
ORDER BY started_at DESC, id DESC
LIMIT :limit;
```

Rationale: a global list is inconsistent with an owner-scoped delete (user A could see runs they cannot delete). The only consumer is `frontend/src/hooks/useRunHistory.ts`, updated atomically in this BRD — no compatibility tax.

- `limit`: `1 ≤ limit ≤ 100`, default `20`.
- `cursor`: omitted on the first page; on subsequent pages it MUST be the `next_cursor` returned by the previous response. Server validates format; malformed cursor → 400.
- `has_more`: `True` iff a row strictly older than the last returned row exists **for the same owner**.

**`GET /api/runs` — error model:**

| Status | Condition | Body |
|--------|-----------|------|
| 200 | Success | `RunListPage` |
| 400 | Malformed/tampered cursor | `{"detail": "Invalid cursor"}` |
| 401 | `X-Username` or `X-Token` missing / unknown / mismatched (per BRD-04 auth middleware) | `{"detail": "Authentication required."}` |

All user-visible strings (button labels, error detail bodies, error toasts) introduced by this BRD are listed verbatim in **§14.3 Microcopy additions** and cross-referenced from `docs/understanding-phase/ui-prototype.md §7.12 (History)`.

**`DELETE /api/runs/{run_id}`** — error model (all detail bodies cross-referenced in §14.3):

| Status | Condition | Body |
|--------|-----------|------|
| 204 | Deleted | empty |
| 401 | `X-Username` / `X-Token` missing or invalid (BRD-04 middleware) | `{"detail": "Authentication required."}` |
| 403 | `run.owner_username != X-Username` | `{"detail": "Run is not owned by the current user."}` |
| 404 | Run does not exist | `{"detail": "Run not found: <id>"}` |
| 409 | `run.stop_reason IS NULL` (still running) | `{"detail": "Cannot delete a run that is still in progress. Cancel it first."}` |

The owner check runs **before** the terminal-state check (avoids leaking the existence of someone else's run via a 409).

### 4.6 React Components

| Component | Path | Props | State | Description |
|-----------|------|-------|-------|-------------|
| `HistoryItem` | `organisms/HistoryItem.tsx` | `run: RunSummary`, `selected: boolean`, `onSelect`, `onDelete?: (id) => void` | `isHovered` (CSS only via `group-hover`), `isExiting` | Renders the card; trash button only when `run.status !== "running"` AND `onDelete` is defined |
| `HistoryPanel` | `organisms/HistoryPanel.tsx` | — | TanStack `useInfiniteQuery` page list | Renders flat list of pages and a "More" button when `hasNextPage`; spinner inside the button while `isFetchingNextPage` |
| `useDeleteRun` | `hooks/useRunHistory.ts` | `runId` | Optimistic mutation | On `onMutate`, removes the item from every cached page via `setQueryData`; **on success, if the deleted id matches `selectionStore.selectedRunId`, clear it so the center panel falls back to L1 (BRD-12 empty state)**; on error, rolls back and surfaces the toast string defined in §14.3 |

### 4.7 UI Layout

```
┌──── History Panel ────┐
│ ▣ Run question…    L3 │  ← selected
│ ▢ Run question…    L4 │  ← hover → 🗑 (bottom-right)
│ ▢ Run question…    L2 │
│ … 20 items max …      │
│ ┌──────────────────┐  │
│ │     More ▾       │  │  ← visible iff has_more
│ └──────────────────┘  │
└───────────────────────┘
```

- Trash icon (`lucide-react` `Trash2`, 16px) is rendered absolute-positioned `bottom-2 right-2` inside the card.
- Default opacity `0`; on `group-hover` AND `focus-visible:within` → `opacity-100` with a 120ms fade (Motion). Reduced-motion users see no transition.
- The icon button has `aria-label="Delete run"` and `title="Delete run"` (see §14.3 for the canonical strings; new entries proposed for `ui-prototype.md §7.12`). It is **not** rendered for runs whose `status === "running"` (L1 in BRD-12 state machine), so screen readers never announce a forbidden action.
- The pagination affordance label is `"More"` (see §14.3; this supersedes the placeholder `"Load more"` currently listed in `ui-prototype.md §7.12 (L7)`).
- On click → optimistic Motion `exit` animation (opacity 0, height 0, 180ms) then the card unmounts. List below slides up.

---

## 5. Acceptance Criteria

### AC-01: Trash icon appears only on hover for finished runs
```gherkin
Given the user is authenticated and has at least one finished run in the panel
When the user hovers a finished run card
Then a trash icon appears at the bottom-right of that card
  And the icon has aria-label "Delete run"
  And the icon is keyboard-focusable
```

### AC-02: Trash icon is hidden for running runs
```gherkin
Given a run with status="running" is shown in the panel
When the user hovers the card
Then no trash icon is rendered
  And the DELETE endpoint is never reachable for that run from the UI
```

### AC-03: Delete succeeds without confirmation
```gherkin
Given the user is authenticated and owns a finished run R
When the user clicks the trash icon on R's card
Then no confirmation dialog is shown
  And the card animates out (opacity 0, height 0, ~180ms)
  And the backend returns 204
  And R is removed from the cached history pages
  And R's events rows are deleted from the database (cascade)
```

### AC-04: Delete forbidden for in-progress runs (server-side defense)
```gherkin
Given a run R with stop_reason IS NULL
When a DELETE /api/runs/{R.id} request is sent
Then the backend returns 409 with detail "Cannot delete a run that is still in progress. Cancel it first."
  And no events are deleted
```

### AC-05: Delete forbidden for non-owners
```gherkin
Given a run R owned by user "alice"
When user "bob" sends DELETE /api/runs/{R.id}
Then the backend returns 403
  And no rows are deleted
```

### AC-06: Fork orphaning preserves descendants
```gherkin
Given a finished run P with two children F1 and F2 (parent_run_id = P.id)
When P is deleted
Then F1 and F2 still exist
  And F1.parent_run_id IS NULL
  And F2.parent_run_id IS NULL
  And F1 and F2 still appear in the history list (no fork badge)
```

### AC-07: Pagination — first page returns 20 items max
```gherkin
Given the user has 35 runs
When the History panel mounts
Then GET /api/runs?limit=20 returns 20 items
  And has_more is true
  And next_cursor is non-null
  And a "More" button is rendered at the end of the list
```

### AC-08: "More" loads the next page and appends
```gherkin
Given the panel has loaded 20 items and "More" is visible
When the user clicks "More"
Then GET /api/runs?limit=20&cursor=<next_cursor> is sent
  And the next page items are appended below the existing 20
  And the cursor advances accordingly
```

### AC-09: No more runs — button disappears
```gherkin
Given the panel has loaded all the user's runs
When the last page response returns has_more=false
Then the "More" button is no longer rendered
  And no further requests are made on scroll
```

### AC-10: Network/server error surfaces and rolls back
```gherkin
Given the user clicks the trash icon
When the DELETE request returns 5xx or fails to reach the server
Then the card reappears in the panel
  And a toast is shown with the literal copy "Couldn't delete the run. Please try again." (see §14.3)
  And the cached query state is restored to the pre-mutation snapshot
```

### AC-11: Cursor is opaque and tamper-resistant
```gherkin
Given the user sends GET /api/runs?cursor=NOT_A_REAL_CURSOR
Then the backend returns 400 with detail "Invalid cursor"
  And no rows are returned
```

### AC-12: Owner-scoped list (resolves §11 #2)
```gherkin
Given user "alice" owns 5 finished runs and user "bob" owns 3 finished runs
When alice sends GET /api/runs with header X-Username: alice
Then the response contains exactly 5 items
  And none of the items reference a run owned by bob
```

---

## 6. Implementation Checklist

- [ ] `backend/app/exceptions.py` — add `RunNotFinishedError` (409), `RunForbiddenError` (403)
- [ ] `backend/app/domain/run.py` — add `RunListPage` model
- [ ] `backend/app/services/run_service.py` — `delete_run(run_id, username)`, `list_runs_keyset(username: str, limit, cursor)` (owner-scoped, no `None` overload), internal `_encode_cursor` / `_decode_cursor`
- [ ] `backend/app/routes/runs.py` — `DELETE /api/runs/{run_id}` route; refactor `GET /api/runs` to return `RunListPage`
- [ ] `scripts/export_types.py` — regenerate `frontend/src/types/events.ts` (no event-schema change, but `RunListPage` is now part of the contract)
- [ ] `frontend/src/types/history.ts` — switch envelope to `{ items, has_more, next_cursor }`
- [ ] `frontend/src/lib/api.ts` — finalize `getRunHistory(cursor?: string)` and `deleteRun(id)`; ensure both prepend `API_URL` (lesson L-008)
- [ ] `frontend/src/hooks/useRunHistory.ts` — `useInfiniteQuery` with `getNextPageParam: p => p.next_cursor ?? undefined`; `useDeleteRun` with optimistic `setQueryData` over all cached pages + rollback on error
- [ ] `frontend/src/components/organisms/HistoryItem.tsx` — hover trash button, `Trash2` icon, `aria-label`, Motion exit
- [ ] `frontend/src/components/organisms/HistoryPanel.tsx` — render "More" button, loading state inside it, hide when `!hasNextPage`
- [ ] Tests: `backend/tests/test_routes_runs.py`, `backend/tests/test_run_service.py`
- [ ] Tests: `frontend/src/components/organisms/HistoryItem.test.tsx`, `HistoryPanel.test.tsx`
- [ ] Manual smoke: delete a run with 2 forks → forks remain, parent_run_id NULL

---

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (BE) | pytest + pytest-asyncio | `RunService.delete_run`, keyset pagination, cursor codec | ≥ 80% |
| Integration (BE) | pytest + pytest-postgresql | `DELETE /api/runs/{id}` cascades events, fork survives with NULL parent | Critical |
| Unit (FE) | Vitest + Testing Library | `HistoryItem` hover, `HistoryPanel` More button, `useDeleteRun` optimistic + rollback | ≥ 80% |
| A11y (FE) | jest-axe | trash button has accessible name; no violations on panel render | All |
| E2E | Playwright | Deferred to V2 |

Backend test fixtures must include: a finished run owned by user A, a running run owned by user A, a finished run owned by user B, a finished run with 2 forked children, and ≥ 25 runs to exercise pagination boundaries.

---

## 8. Environment Variables

None added or modified.

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Optimistic delete leaves stale entries in non-active query caches | Medium | Medium | After mutation success, `queryClient.invalidateQueries({ queryKey: ["runs"] })` to refetch in background |
| User accidentally deletes a run (no confirmation by requirement) | High | Medium | Out of scope per requirement; revisit as "undo toast" in V2 (out of scope) |
| Cursor collision when many runs share the same `started_at` millisecond | Low | Low | Tie-break on `id DESC` inside the cursor; `(started_at, id)` is a strict total order |
| Breaking change to `GET /api/runs` response shape may break other clients | Medium | Low | Only consumer is `frontend/src/hooks/useRunHistory.ts`; updated atomically |
| Race: delete while an SSE stream for the same run is open | Medium | Low | SSE manager already drops connections when the run row vanishes (events FK cascade triggers); add an explicit `connection_manager.close(run_id)` call after delete commits to guarantee no late frames |

---

## 10. Out of Scope

- Bulk delete (multi-select) — defer to V2.
- Soft delete / restore (trash bin / undo toast) — defer to V2.
- Confirmation dialog — explicitly excluded by the user requirement.
- Deletion of in-progress runs — user must cancel first via `POST /api/runs/{id}/cancel` (BRD-15).
- Admin / cross-user deletion — not a V1 concern.
- Infinite scroll — explicit user gesture (click "More") is required by the requirement; no `IntersectionObserver` auto-load.
- Search / filter inside the paginated list — covered by BRD-12 L7 (filtered state), out of scope for BRD-20.

---

## 11. Open Decisions (for Auditor review)

1. **Fork orphaning policy — RESOLVED: option (a) `ON DELETE SET NULL`.**
   The DB schema already encodes this (`runs.parent_run_id ON DELETE SET NULL`, verified in `backend/app/models/run.py:100`). Forks survive; lineage badge disappears. Rationale: the user requirement says "elimina todo el historial **asociado a esa búsqueda**", which we interpret as *that run's events*, not *every descendant*. Restricting deletion when forks exist would frustrate the user's stated goal.
2. **List scope — RESOLVED (F1 iter 2): owner-scoped.** `GET /api/runs` now filters `WHERE owner_username = :username` (see §4.5 SQL contract and AC-12 in §5). The previous `username | None` overload is removed from `list_runs_keyset`. Rationale: symmetric with delete (a user must not see runs they cannot delete); the only consumer is `frontend/src/hooks/useRunHistory.ts`, updated atomically — no compatibility tax. The 401 path is also documented in §4.5.
3. **Cursor codec — RESOLVED: opaque base64 of `f"{started_at.isoformat()}|{id}"`.** Stateless, no DB round-trip to validate, easy to test. Tampered cursors return 400.
4. **Pagination strategy — RESOLVED: keyset over `(started_at DESC, id DESC)`.** Avoids skew when new runs arrive between page loads. Offset-based pagination would have shifted the window every time a run is created or deleted.

---

## 12. User Stories Summary

| Story ID | Title | Priority | Estimated Effort |
|----------|-------|----------|------------------|
| US-20-A | Delete a finished run from the history panel | High | M |
| US-20-B | Paginate the history panel with a "More" button | High | S |

---

## 13. Stakeholders

| Name | Role | Interest | Involvement |
|------|------|----------|-------------|
| Project owner | End user / Product | Primary requester | Approver |
| BSA Agent | Analyst | Authoring | Author |
| Auditor Agent | QA | F1 audit | Consulted |

---

## 14. Appendix

### 14.1 References

- `docs/understanding-phase/requirement-understanding.md` (RF-05, RF-09, RF-13)
- `docs/understanding-phase/stopping-signal-analysis.md` (7 terminal `stop_reason` values)
- `docs/implementation-phase/brds/BRD-01-database-schema.md` (cascade rules)
- `docs/implementation-phase/brds/BRD-12-history-panel.md` (state machine L1–L7)
- `backend/app/models/run.py:100` and `backend/app/models/event.py:32` (cascade verification)

### 14.2 Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-27 | BSA Agent | Initial draft |
| 1.1 | 2026-05-27 | BSA Agent | F1 audit iter 2 fixes: owner-scoped `GET /api/runs` locked (AC-12, §11 #2 RESOLVED, RF-05 Complete); `useDeleteRun` clears `selectionStore.selectedRunId` (§4.6); 401 path documented; AC-10 toast string pinned; `next_cursor` null-on-`has_more=false` clarified (§4.4); new §14.3 microcopy additions. |

### 14.3 Microcopy additions (proposed for `ui-prototype.md §7.12 History`)

These strings are introduced by BRD-20 and MUST be added to the binding microcopy table in `docs/understanding-phase/ui-prototype.md §7.12` in a follow-up sync. Implementation must use these literals verbatim.

| Surface | String | Used in |
|---------|--------|---------|
| Trash icon `aria-label` / `title` (`HistoryItem`) | `"Delete run"` | BRD-20 §4.7; US-20-A Scenario 1 |
| Pagination button label (`HistoryPanel`) | `"More"` | BRD-20 §4.7; AC-07, AC-08; US-20-B Scenarios 1–3 (**supersedes** the earlier `"Load more"` placeholder in `ui-prototype.md §7.12 (L7)`) |
| Pagination button in-flight label | `"Loading…"` | BRD-20 §4.6; US-20-B Scenario 5 |
| Delete error toast (5xx / network) | `"Couldn't delete the run. Please try again."` | BRD-20 AC-10; US-20-A Scenario 8 |
| `DELETE` 401 detail body | `"Authentication required."` | BRD-20 §4.5 (DELETE table) |
| `DELETE` 403 detail body | `"Run is not owned by the current user."` | BRD-20 §4.5; US-20-A Scenario 6 |
| `DELETE` 404 detail body | `"Run not found: <id>"` | BRD-20 §4.5 |
| `DELETE` 409 detail body | `"Cannot delete a run that is still in progress. Cancel it first."` | BRD-20 §4.5; AC-04; US-20-A Scenario 5 |
| `GET /api/runs` 400 detail body | `"Invalid cursor"` | BRD-20 §4.5; AC-11; US-20-B Scenario 6 |
| `GET /api/runs` 401 detail body | `"Authentication required."` | BRD-20 §4.5 (GET error model) |
