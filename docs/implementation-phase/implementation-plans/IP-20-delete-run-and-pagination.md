# Implementation Plan — IP-20: Delete Finished Run & History Pagination

**Plan ID:** IP-20
**Parent BRD:** [BRD-20 v1.1](../brds/BRD-20-delete-run-and-pagination.md)
**Parent User Stories:** [US-20-A](../user-stories/US-20-A-delete-finished-run.md), [US-20-B](../user-stories/US-20-B-history-pagination.md)
**Date:** 2026-05-27
**Author:** Orchestrator Agent
**Estimated Effort:** M (≈3–4 h pair-session)
**Iteration:** 2 (post F2 audit iter 1 feedback)

---

## 1. Summary

Add a `DELETE /api/runs/{id}` endpoint (owner-scoped, finished-only) that cascades through `events` via existing FK rules, replace the offset-paginated `GET /api/runs` with a **keyset** envelope (`{items, has_more, next_cursor}`) restricted to the authenticated owner, and wire the History panel with a hover-revealed trash icon (Motion exit) plus a "More" button driven by `useInfiniteQuery`. No DB migration. No new env vars.

RF traceability: **RF-05** (owner-scoped ownership symmetry), **RF-09** (paginated discovery), **RF-13** (visible affordance + animated removal), **RF-03** (fork orphaning preserved via `ON DELETE SET NULL`).

---

## 2. Prerequisites

- [x] BRD-20 v1.1 approved by F1 Auditor (9.83/10) — owner-scoping locked, microcopy pinned
- [x] FK cascades already in schema: `events.run_id ON DELETE CASCADE`, `runs.parent_run_id ON DELETE SET NULL` (verified `backend/app/models/event.py:32`, `backend/app/models/run.py:100`)
- [x] BRD-19 `agent_runner.await_terminal` available — used to refuse delete of a still-running run after a soft race
- [x] `connection_manager.close(run_id)` exists in `app/sse/manager.py` — used post-commit to drop any open SSE listener
- [x] Frontend `selectionStore` already exposes `selectedRunId` + `setSelectedRunId` — used by `useDeleteRun` to clear selection on self-delete
- [x] `Trash2` icon from `lucide-react` (already in deps)
- [x] `motion/react` available (used by other organisms)

---

## 3. Task Breakdown

### Phase 1 — Backend

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 1.1 | Add `RunNotFinishedError` (409) and `RunForbiddenError` (403); add `InvalidCursorError` (400) | `backend/app/exceptions.py` | S | — | AC-04, AC-05, AC-11 |
| 1.2 | Register the three new exceptions in the FastAPI exception-handler registry so the literal `detail` bodies from BRD-20 §14.3 reach the client | `backend/app/exceptions.py` (handler block) or `backend/app/main.py` (whichever pattern matches existing handlers) | S | 1.1 | AC-04, AC-05, AC-11 |
| 1.3 | Add `RunListPage` Pydantic model (`items`, `has_more`, `next_cursor`) — `ConfigDict(extra="allow")` per schema-evolution rule | `backend/app/domain/run.py` | S | — | AC-07, AC-09 |
| 1.4 | Implement cursor codec: `_encode_cursor(started_at, id) -> str` and `_decode_cursor(str) -> tuple[datetime, UUID]` using `base64.urlsafe_b64encode` over `f"{iso}|{uuid}"`; raise `InvalidCursorError` on malformed input | `backend/app/services/run_service.py` (module-level private helpers) | S | 1.1 | AC-11; US-20-B Sc.6 |
| 1.5 | Refactor `RunService.list_runs` → `list_runs_keyset(username: str, limit: int, cursor: str \| None) -> RunListPage`. Owner-scoped `WHERE owner_username = :username`. Tuple keyset filter `(started_at, id) < (:cur_ts, :cur_id)` only when cursor provided. Order `started_at DESC, id DESC`. Fetch `limit + 1` rows to compute `has_more` cheaply; trim last item if over. `next_cursor = _encode_cursor(last_item.started_at, last_item.id)` if `has_more` else `None`. Drop the old offset signature entirely. | `backend/app/services/run_service.py` | M | 1.3, 1.4 | AC-07, AC-08, AC-09, AC-12; US-20-B Sc.1-3, Sc.9 |
| 1.6 | Implement `RunService.delete_run(run_id: UUID, username: str) -> None`. Lookup → 404 (`RunNotFoundError`) if missing. Ownership check **before** terminal check (BRD-20 §4.5 leak guard) → `RunForbiddenError`. Terminal check `if run.stop_reason is None: raise RunNotFinishedError(...)` with the AC-04 literal detail. **Best-effort `await_terminal` wrapped in `try/except RunStillTerminatingError: pass`** so the AC-04 409 body is NEVER shadowed by the BRD-19 `run_still_terminating` 409 body. `await self.db.delete(run); await self.db.commit()`. Post-commit: `connection_manager.close(run_id)` (idempotent — uses `pop(..., None)`). | `backend/app/services/run_service.py` | M | 1.1, 1.5 | AC-03, AC-04, AC-05, AC-06; US-20-A Sc.3-7 |
| 1.7 | Refactor route `GET /api/runs`: replace `limit/offset` query params with `limit: int = Query(20, ge=1, le=100), cursor: str \| None = Query(None)`. Change `response_model=RunListPage`. Pass `username` (auth-required dep — change from `_username` to `username`) into `list_runs_keyset`. | `backend/app/routes/runs.py` | S | 1.5 | AC-07, AC-09, AC-11, AC-12 |
| 1.8 | Add route `DELETE /api/runs/{run_id}` returning `status_code=204` and no response body. Auth-required via `CurrentUsername`. Calls `RunService.delete_run`. | `backend/app/routes/runs.py` | S | 1.6 | AC-03, AC-04, AC-05 |
| 1.9 | Regenerate frontend types via `scripts/export_types.py` (RunListPage joins the contract; no event-schema change) | `frontend/src/types/events.ts` (auto-generated) | S | 1.3 | — |

### Phase 2 — Frontend

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 2.0 | **Locate the list-loop**: before starting Phase 2, run `grep -rn "useRunHistory\|HistoryItem\|hasNextPage" frontend/src` and decide ONCE whether the list rendering currently lives inside a `pages/*` file or already in an organism. Record the chosen target in a comment at the top of Task 2.6's file. (Resolves §11 #2 ahead of time per Auditor instruction.) | n/a (discovery) | XS | 1.9 | sequencing |
| 2.1 | Update `RunHistoryPage` envelope and DTO types: rename to `{ items: RunSummary[]; hasMore: boolean; nextCursor: string \| null }` (camelCase at the TS layer; snake_case stays at the wire). Drop `nextOffset`. | `frontend/src/types/history.ts` | S | 1.9 | AC-07, AC-09 |
| 2.2 | Update `listRuns` in `lib/api.ts`: signature `listRuns({ limit, cursor }: { limit?: number; cursor?: string \| null })` → `Promise<{ items: RunListItemDto[]; has_more: boolean; next_cursor: string \| null }>`. Drop `offset`. Add `deleteRun(id: string): Promise<void>` issuing `DELETE` with auth headers; on non-2xx, throw `ApiError` (existing class). Both MUST prefix `API_URL` (lesson L-008). | `frontend/src/lib/api.ts` | S | 1.7, 1.8 | AC-03, AC-07, AC-08 |
| 2.3 | Refactor `useRunHistory`: switch `pageParam` from `number` to `string \| null` (cursor). `queryFn` calls `listRuns({ limit, cursor: pageParam ?? null })`, maps DTO items via existing `mapRun`, returns `{ items, nextCursor: dto.next_cursor }`. `getNextPageParam: p => p.nextCursor ?? undefined`. Keep `staleTime: 30_000`. | `frontend/src/hooks/useRunHistory.ts` | S | 2.1, 2.2 | AC-07, AC-08, AC-09 |
| 2.4 | Add `useDeleteRun()` to `hooks/useRunHistory.ts` (same file — co-located by domain). `useMutation` calling `deleteRun(id)`. `onMutate`: snapshot via `queryClient.getQueriesData({ queryKey: ["runs", "history"] })`, then **`queryClient.setQueriesData({ queryKey: ["runs", "history"] }, ...)`** (plural — prefix match across all `pageSize`/`username` tuples) to remove the item from every page (`{...page, items: page.items.filter(i => i.id !== id)}`). `onError`: rollback by iterating the snapshot and calling `setQueryData(key, data)` for each. `onSuccess`: if `selectionStore.getState().selectedRunId === id`, call `setSelectedRunId(null)` so the center panel returns to L1 (BRD-12). On error, call the new `useToast().push({ kind: "error", message: "Couldn't delete the run. Please try again." })` (literal AC-10 string). `onSettled`: `queryClient.invalidateQueries({ queryKey: ["runs", "history"] })`. | `frontend/src/hooks/useRunHistory.ts` | M | 2.3, 2.4b | AC-03, AC-06, AC-10; US-20-A Sc.3, Sc.8, Sc.9, Sc.10 |
| 2.4b | **NEW (mandated by F2 audit)**: Create a minimal `useToast` + `<Toaster>` molecule pair so AC-10 is satisfied. `frontend/src/components/molecules/Toaster.tsx` renders a `motion.ul` of toast messages (top-right, slide-in 180ms, auto-dismiss 5 s). `frontend/src/hooks/useToast.ts` exposes `push({ kind: "error" \| "info", message: string })` backed by a Zustand store at `frontend/src/stores/toastStore.ts`. Mount `<Toaster />` once at the page-level shell (next to the existing layout shell). Co-located unit tests assert `push` adds an entry and auto-dismiss removes it. Stays small (≤ ~80 LOC total per copilot-instructions §6 over-engineering rule). | `frontend/src/stores/toastStore.ts` (NEW), `frontend/src/hooks/useToast.ts` (NEW), `frontend/src/components/molecules/Toaster.tsx` (NEW), shell page (MODIFIED — mount once) | M | 2.0 | AC-10; US-20-A Sc.8 |
| 2.5 | Create organism `HistoryItem` at `components/organisms/HistoryItem.tsx`. Props: `run: RunSummary`, `selected: boolean`, `onSelect: (id: string) => void`, `onDelete?: (id: string) => void`. Structure: `motion.li` with `layout`, `exit={{ opacity: 0, height: 0, marginTop: 0, marginBottom: 0 }}`, `transition={{ duration: 0.18 }}`. Outer `button` for select. Absolute-positioned secondary `button` `bottom-2 right-2` with `Trash2` icon (16px), `aria-label="Delete run"`, `title="Delete run"`. Visibility: rendered only when `run.status !== "running" && onDelete !== undefined`. Default `opacity-0`, `group-hover:opacity-100`, `focus-visible:opacity-100`, `transition-opacity duration-120 motion-reduce:transition-none`. `onClick` stops propagation, calls `onDelete(run.id)`. | `frontend/src/components/organisms/HistoryItem.tsx` (NEW) | M | 2.1 | AC-01, AC-02, AC-03; US-20-A Sc.1, Sc.2 |
| 2.6 | At the location chosen in 2.0, replace inline list rendering with: `<AnimatePresence initial={false}>` around the items, mapping pages through `HistoryItem` and passing `deleteMutation.mutate` as `onDelete`. Append a footer `<button>` rendered iff `hasNextPage`, label `"More"` (`"Loading…"` while `isFetchingNextPage`), disabled while loading, `onClick={() => fetchNextPage()}`. Hide when `!hasNextPage`. Show empty state (BRD-12 L1) when `pages.flatMap(p => p.items).length === 0 && !isLoading`. | `frontend/src/components/organisms/HistoryList.tsx` (NEW) OR the page file selected in 2.0 | M | 2.3, 2.4, 2.5 | AC-07, AC-08, AC-09; US-20-B Sc.1-5, Sc.7 |
| 2.7 | Frontend smoke-edit: ensure `HistoryPanel` template in `components/templates/HistoryPanel.tsx` is **untouched** (it's a geometry-only slot container per the file header). All new logic lives in the organism + page. | n/a | — | 2.6 | layering |

### Phase 3 — Tests

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 3.0 | **Legacy test removal/rewrite**: identify every existing `test_list_runs_*` case in `backend/tests/test_run_service.py` and `backend/tests/test_routes_runs.py` that asserts the old `list[RunListItem]` shape or `limit/offset` signature, and either delete them or rewrite them against the new envelope before adding new cases. Pre-Task 3.1/3.2 prerequisite. | `backend/tests/test_run_service.py`, `backend/tests/test_routes_runs.py` | S | 1.5, 1.7 | hygiene |
| 3.1 | Backend: extend `tests/test_run_service.py` with: `test_list_runs_keyset_first_page`, `test_list_runs_keyset_owner_scoped` (AC-12), `test_list_runs_keyset_cursor_advances`, `test_list_runs_keyset_has_more_false_at_tail`, `test_list_runs_keyset_invalid_cursor_raises`, `test_delete_run_success`, `test_delete_run_cascades_events`, `test_delete_run_404_when_missing`, `test_delete_run_403_when_not_owner`, `test_delete_run_409_when_in_progress`, `test_delete_run_409_does_not_leak_run_still_terminating_body` (verifies the try/except in Task 1.6), `test_delete_run_orphans_forks_sets_parent_null` (AC-06). Use existing pytest-postgresql fixtures. | `backend/tests/test_run_service.py` | M | 3.0, 1.5, 1.6 | AC-03..AC-12 |
| 3.2 | Backend: extend `tests/test_routes_runs.py` with: `test_list_runs_returns_envelope`, `test_list_runs_unauthenticated_returns_401`, `test_delete_run_returns_204`, `test_delete_run_returns_401_unauthenticated`, `test_delete_run_returns_403_not_owner`, `test_delete_run_returns_404_missing`, `test_delete_run_returns_409_in_progress` (asserts the AC-04 literal detail body), `test_delete_run_returns_400_invalid_cursor` (against GET). | `backend/tests/test_routes_runs.py` | M | 3.0, 1.7, 1.8 | AC-03..AC-12 |
| 3.3 | Frontend: new `HistoryItem.test.tsx` co-located with the organism. Cases: trash hidden for `status="running"`, trash reachable via focus + aria-label `"Delete run"`, click trash calls `onDelete(run.id)` and does NOT trigger `onSelect`, keyboard `Enter` on trash triggers delete, no-axe-violations. | `frontend/src/components/organisms/HistoryItem.test.tsx` (NEW) | M | 2.5 | AC-01, AC-02; US-20-A Sc.1, Sc.2 |
| 3.4 | Frontend: hook tests in `useRunHistory.test.ts`. Cases: optimistic remove from all cached pages (multiple `pageSize` cache entries — assert `setQueriesData` ran), rollback on error, clears `selectionStore.selectedRunId` when deleting the selected run, leaves it untouched otherwise, `useInfiniteQuery` `getNextPageParam` returns cursor and stops on `null`, error toast `push` invoked with literal AC-10 string. Mock network with MSW. | `frontend/src/hooks/useRunHistory.test.ts` (NEW or extend if exists) | M | 2.3, 2.4, 2.4b | AC-03, AC-08, AC-09, AC-10; US-20-A Sc.3, Sc.8, Sc.9 |
| 3.5 | Frontend: integration test of the list container — renders 20 items + `"More"` button when `hasMore=true`, clicking `"More"` issues the next request and appends results, button shows `"Loading…"` while fetching, button hidden when `hasMore=false`, empty state rendered when 0 items, deleting the last item shows the L1 empty state. Use MSW with two pages. | `frontend/src/components/organisms/HistoryList.test.tsx` (NEW) | M | 2.6 | AC-07, AC-08, AC-09; US-20-A Sc.10; US-20-B Sc.1-5, Sc.7 |
| 3.6 | Frontend: `Toaster.test.tsx` — `push` appends, auto-dismiss after 5 s removes (use Vitest fake timers per L-009 — single `advanceTimersByTime` only), no-axe-violations. | `frontend/src/components/molecules/Toaster.test.tsx` (NEW) | S | 2.4b | AC-10 |

### Phase 4 — Docs & memory bank

| # | Task | File(s) | Effort | Depends on |
|---|------|---------|--------|------------|
| 4.1 | Update knowledge-base index: register `PLAN-US-20` and the new exception/model entries | `.github/memory-bank/indices/knowledge-base-index.md` | S | end |
| 4.2 | Append D-046 to decisions history: keyset codec, 401 path on `GET /api/runs`, `connection_manager.close` post-commit sequencing | `.github/memory-bank/logs/decisions-history.md` | S | end |
| 4.3 | (Out of scope here but tracked) follow-up doc PR syncing §14.3 microcopy into `docs/understanding-phase/ui-prototype.md §7.12` — note as a TODO in lessons-learned if not done in this PR | `.github/memory-bank/logs/lessons-learned.md` (optional) | XS | — |

---

## 4. File Modifications

### New files
```
backend/                                      (none — additive in existing files)
frontend/src/components/organisms/HistoryItem.tsx
frontend/src/components/organisms/HistoryItem.test.tsx
frontend/src/hooks/useRunHistory.test.ts                (if absent)
frontend/src/components/organisms/HistoryList.tsx       (if list currently lives inside a page file)
frontend/src/components/organisms/HistoryList.test.tsx  (or page-level test extension)
docs/implementation-phase/implementation-plans/PLAN-US-20-delete-run-and-pagination.md  (this file)
```

### Modified files
```
backend/app/exceptions.py
backend/app/domain/run.py
backend/app/services/run_service.py
backend/app/routes/runs.py
backend/tests/test_run_service.py
backend/tests/test_routes_runs.py
frontend/src/types/history.ts
frontend/src/lib/api.ts
frontend/src/hooks/useRunHistory.ts
frontend/src/types/events.ts                            (regenerated)
.github/memory-bank/indices/knowledge-base-index.md
.github/memory-bank/logs/decisions-history.md
```

---

## 5. Database Changes

**None.** No migration. Cascade rules are already in place (BRD-20 §4.2).

---

## 6. API Contract

```yaml
GET /api/runs:
  auth: required (X-Username + X-Token; 401 otherwise)
  query:
    limit:  integer, 1..100, default 20
    cursor: string|null, opaque base64
  response 200:
    items: RunListItem[]
    has_more: boolean
    next_cursor: string|null   # null iff has_more=false
  errors:
    400: { detail: "Invalid cursor" }
    401: { detail: "Authentication required." }

DELETE /api/runs/{run_id}:
  auth: required
  response 204: <empty>
  errors:
    401: { detail: "Authentication required." }
    403: { detail: "Run is not owned by the current user." }
    404: { detail: "Run not found: <id>" }
    409: { detail: "Cannot delete a run that is still in progress. Cancel it first." }
```

All literals match BRD-20 §14.3.

---

## 7. State / Cache Strategy (Frontend)

```
┌─ useInfiniteQuery (["runs","history", pageSize, username]) ─┐
│   pages: [{ items: RunSummary[], nextCursor: string|null }, ...]
│   getNextPageParam: p => p.nextCursor ?? undefined
└─────────────────────────────────────────────────────────────┘
            ▲                                       │
            │ optimistic setQueryData               │ "More" click
            │ (filter id out of every page)         ▼
┌─ useDeleteRun ──────────────────────────────────────────────┐
│   onMutate: snapshot + remove
│   onError:  rollback to snapshot
│   onSuccess: if selectedRunId === id → setSelectedRunId(null)
│   onSettled: invalidateQueries(["runs","history"])
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Testing Strategy

- Backend coverage target ≥ 80 % on changed lines (`RunService.delete_run`, `list_runs_keyset`, cursor codec, two new exception classes, two new routes).
- Frontend coverage target ≥ 80 % on `HistoryItem`, `useDeleteRun`, `useRunHistory` pagination, list container.
- A11y: `HistoryItem.test.tsx` runs `jest-axe` on a rendered card, asserts no violations and that the trash button has accessible name "Delete run".
- Float / time pitfalls (L-009/L-011/L-012) **do not apply** here — no timer-driven UI in this BRD.

Manual smoke (post-merge, single command on the dev DB):
```
psql -c "SELECT id, parent_run_id FROM runs WHERE parent_run_id = '<deleted-id>';"
# expected: parent_run_id IS NULL for all surviving forks; deleted row absent.
```

---

## 9. Sequencing for Coder

1. Phase 1 in order (1.1 → 1.9). Run `pytest -q` after 1.6 and again after 1.8 to lock the contract.
2. Run `python scripts/export_types.py` (task 1.9) before touching frontend.
3. Phase 2 in order (2.1 → 2.6). Run `npm test -- --run` after 2.4 to validate optimistic flow before UI work.
4. Phase 3 alongside or immediately after each implementation task — DO NOT defer to the end (per L-002 testing-policy: tests are part of the same change).
5. Phase 4 last (memory bank updates after green tests).

---

## 10. Risks & Mitigations (delta from BRD §9)

| Risk | Mitigation in this plan |
|------|-------------------------|
| Optimistic delete on a query key that has multiple `pageSize/username` variants in cache | `setQueryData` walks every cached page tuple matching `["runs","history"]` prefix via `queryClient.setQueriesData({ queryKey: ["runs","history"] }, ...)` (note: `setQueriesData`, plural) |
| Selection cleared on every delete (even non-self) — UX regression | Explicit `if (selectedRunId === id)` guard inside `onSuccess`; covered by hook test 3.4 |
| `connection_manager.close(run_id)` raising if no listener | API is idempotent in current code (`pop` with default); test 3.1 covers the no-listener path |
| Race: user clicks Delete during the ~50ms window between FSM `Stopped` event and `run.stopped_at` commit | `delete_run` calls `agent_runner.await_terminal(run_id, timeout=2.0)` before deletion; if it times out (shouldn't with terminal stop_reason) the subsequent stop_reason check still guards |
| Cursor exposes internal `started_at` precision via base64 | Documented as opaque; clients MUST NOT decode (BRD §4.4). Server validates on every request. |

---

## 11. Open Decisions — RESOLVED in F2 Iter 1

All three open decisions from PLAN v1 were ruled on by the F2 Auditor:

1. **Toast surface** — RESOLVED: Required Task **2.4b** ships a minimal `useToast` + `<Toaster>` molecule pair (≤ ~80 LOC). `console.error` fallback rejected — AC-10 mandates a visible literal toast string.
2. **HistoryList extraction** — RESOLVED: flexibility retained but Task **2.0** mandates a single `grep` + decision before Phase 2 begins; the answer is committed in a top-of-file comment so the Coder cannot drift.
3. **Cursor codec (unsigned base64)** — RESOLVED: ACCEPTED. BRD-20 §11 #3 already locked it; AC-11 covers tampering; signing would require a new server secret (banned by BRD-20 §8).

No decisions remain open.

---

## 12. Estimated Effort Breakdown

| Phase | Effort |
|-------|--------|
| Phase 1 (Backend) | ~1.5 h |
| Phase 2 (Frontend, incl. 2.4b toast) | ~2 h |
| Phase 3 (Tests) | ~1 h (interleaved) |
| Phase 4 (Docs) | 15 min |
| **Total** | **≈ 4–5 h** |

## 13. Document History

| Iter | Date | Changes |
|------|------|---------|
| 1 | 2026-05-27 | Initial plan |
| 2 | 2026-05-27 | F2 audit iter 1 fixes: Task 1.6 `try/except RunStillTerminatingError`; new Task 2.4b (Toaster/useToast); Task 2.4 switched to `setQueriesData` (plural); `Satisfies` column added to every phase table; Task 3.0 added (legacy test rewrite); §11 collapsed (all decisions resolved); new Task 3.6 for Toaster tests. |
