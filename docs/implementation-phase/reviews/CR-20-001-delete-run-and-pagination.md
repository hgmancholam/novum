# Code Review Report — BRD-20

**User Story:** US-20-A (Delete) + US-20-B (Pagination)
**BRD:** [BRD-20 v1.1](../brds/BRD-20-delete-run-and-pagination.md)
**Plan:** [PLAN-US-20 v2](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md)
**Iteration:** 1 (F4)
**Date:** 2026-05-27
**Reviewer:** Reviewer Agent

---

## 1. Summary

| Criterion | Score | Weight | Weighted |
|-----------|------:|-------:|---------:|
| Code Quality        | 9.5 / 10 | 25% | 2.375 |
| Test Coverage       | 9.5 / 10 | 20% | 1.900 |
| Architecture        | 10  / 10 | 20% | 2.000 |
| Documentation       | 9.0 / 10 | 15% | 1.350 |
| Security            | 10  / 10 | 10% | 1.000 |
| Performance         | 9.5 / 10 | 10% | 0.950 |
| **TOTAL**           |          |     | **9.58 / 10** |

## 2. Verdict

**✅ APPROVED** — score ≥ 9 threshold. No required changes. Two cosmetic nits listed in §6.

---

## 3. BRD Acceptance Criteria — Pass / Fail

| AC | Subject | Status | Evidence |
|----|---------|:------:|----------|
| AC-01 | Trash icon on hover, `aria-label="Delete run"`, focusable | PASS | [HistoryItem.tsx#L52-L70](../../../frontend/src/components/organisms/HistoryItem.tsx#L52) |
| AC-02 | No trash icon for running runs | PASS | `canDelete = onDelete !== undefined && run.status !== "running"` ([HistoryItem.tsx#L37](../../../frontend/src/components/organisms/HistoryItem.tsx#L37)); covered by `HistoryItem.test.tsx` |
| AC-03 | Delete → 204, optimistic exit, cascade | PASS | [run_service.py#L185-L188](../../../backend/app/services/run_service.py#L185); test `test_delete_run_removes_finished_run` |
| AC-04 | 409 when in-progress, literal detail | PASS | [exceptions.py#L29-L36](../../../backend/app/exceptions.py#L29); test `test_delete_run_in_progress_returns_409_with_literal_detail` |
| AC-05 | 403 when not owner | PASS | [run_service.py#L171](../../../backend/app/services/run_service.py#L171); test `test_delete_run_not_owned_returns_403_with_literal_detail` |
| AC-06 | Forks orphan (parent_run_id → NULL) | PASS | `test_delete_run_orphans_forks` + `test_delete_run_cascades_events` |
| AC-07 | First page = 20 max + has_more + next_cursor | PASS | [run_service.py#L113-L150](../../../backend/app/services/run_service.py#L113); test `test_list_runs_returns_envelope_shape` |
| AC-08 | "More" loads next page, appends, no overlap | PASS | `test_list_runs_paginates_with_cursor`; FE `HistoryList.tsx` More button |
| AC-09 | has_more=false → button hidden | PASS | [HistoryList.tsx#L156-L170](../../../frontend/src/components/organisms/HistoryList.tsx#L156) `{hasNextPage ? … : null}` |
| AC-10 | Error toast literal `"Couldn't delete the run. Please try again."` | PASS | [useRunHistory.ts#L150-L153](../../../frontend/src/hooks/useRunHistory.ts#L150) — verbatim |
| AC-11 | Tampered cursor → 400 `"Invalid cursor"` | PASS | [run_service.py#L57-L66](../../../backend/app/services/run_service.py#L57); test `test_list_runs_invalid_cursor_returns_400` |
| AC-12 | Owner-scoped list | PASS | [run_service.py#L121](../../../backend/app/services/run_service.py#L121) `where(Run.owner_username == username)`; test `test_list_runs_excludes_other_users` |

**12 / 12 ACs pass.**

---

## 4. Plan Spot-Check (10 manual items from request)

| # | Check | Result | Where |
|---|-------|:------:|-------|
| 1 | Ownership BEFORE `stop_reason IS NULL` | PASS | [run_service.py#L168-L173](../../../backend/app/services/run_service.py#L168) (403 before 409) |
| 2 | `try/except RunStillTerminatingError: pass` around `await_terminal` | PASS | [run_service.py#L175-L179](../../../backend/app/services/run_service.py#L175); covered by `test_delete_run_swallows_run_still_terminating` |
| 3 | `useDeleteRun.onMutate` uses `setQueriesData` (plural) | PASS | [useRunHistory.ts#L121-L132](../../../frontend/src/hooks/useRunHistory.ts#L121) |
| 4 | AC-10 toast literal verbatim | PASS | `"Couldn't delete the run. Please try again."` |
| 5 | Trash `aria-label="Delete run"` + `motion-reduce:transition-none` | PASS | [HistoryItem.tsx#L56,L68](../../../frontend/src/components/organisms/HistoryItem.tsx#L56) |
| 6 | `Toaster` ≤ ~80 LOC, under `components/molecules/` | PASS (~80 LOC including `ToastRow`) | [Toaster.tsx](../../../frontend/src/components/molecules/Toaster.tsx) |
| 7 | `templates/HistoryPanel.tsx` UNTOUCHED (geometry-only) | PASS | Slot signature `{header, body, footer}` unchanged |
| 8 | Events cascade after Run delete | PASS | `test_delete_run_cascades_events` asserts `COUNT(events) == 0` |
| 9 | `DELETE /api/runs/{run_id}` registered | PASS | [routes/runs.py#L60-L69](../../../backend/app/routes/runs.py#L60) `@router.delete(...)`, status 204 |
| 10 | `...init` spread BEFORE `headers`/`body` (L-009) | PASS | [api.ts#L171-L177](../../../frontend/src/lib/api.ts#L171) (`deleteRun`); same pattern in `api.get/post/put/delete` |

---

## 5. Dimension Notes

### 5.1 Code Quality — 9.5
- Cursor codec is a clean module-level pair (`_encode_cursor` / `_decode_cursor`), exception surface narrowed to `(binascii.Error, UnicodeDecodeError, ValueError)`.
- `list_runs_keyset` uses the `limit + 1` trick to compute `has_more` without a `COUNT(*)` round-trip — idiomatic and cheap.
- The dialect-portable `or_(started_at < ts, and_(started_at == ts, id < id))` is the right choice (avoids row-value comparison which SQLite lacks).
- `HistoryItem` is a single ~80-line component with clean memoization and prop drilling. `RunRow` reuse keeps the diff small.

### 5.2 Test Coverage — 9.5
- 13 new backend service tests (incl. ordering, has_more boundary, cursor advance, tail-empty, terminating-swallow, SSE-close idempotence).
- 5+ new route-level tests covering 204/401/403/404/409/400 paths with **literal detail body assertions** — matches BRD §14.3.
- Frontend: `HistoryItem.test.tsx`, `HistoryList.test.tsx`, `useRunHistory.test.tsx`, `Toaster.test.tsx` co-located.
- Coder reports 62 BE / 402 FE pass — consistent with the touched-file count.

### 5.3 Architecture — 10
- No new dependencies. No migration. No Redis / Docker.
- Plugin seams untouched (`Source`, `StoppingSignal`, `OutputRenderer`).
- Atomic-design respected: list-loop moved into `organisms/HistoryList.tsx`, page container in `pages/HistoryPanelContainer.tsx`, template (`HistoryPanel`) unchanged.
- `RunListPage` declares `model_config = ConfigDict(extra="allow")` per schema-evolution rule.
- Events append-only invariant preserved (delete cascades via DB FK, not via event mutation).

### 5.4 Documentation — 9
- Service docstrings explicitly enumerate the 6-step ordering of `delete_run` with BRD §4.5 citation — exactly the non-obvious WHY the project conventions ask for.
- Cursor codec, `_to_list_item`, `RunListPage` all link to BRD/RF.
- Minor: `useRunHistory.ts` docstring cites "AC-13, AC-14" — BRD-20 only has AC-01..AC-12. Cosmetic, see §6 Finding 1.

### 5.5 Security — 10
- **Ownership before existence-leak**: 403 strictly precedes 409 (test `test_delete_run_ownership_check_precedes_terminal_check` proves it).
- **Owner-scoped list**: SQL has a mandatory `WHERE owner_username = :username`; service signature has no `None` overload, so the route cannot accidentally call it un-scoped.
- **Cursor tamper guard**: `_decode_cursor` catches all decode-path exceptions and raises `InvalidCursorError` → 400; no internal trace leaks.
- **Parameterized SQLAlchemy** throughout — no string interpolation into queries.
- **Auth headers preserved** in `deleteRun` (explicit `getAuthHeaders()` spread before `init?.headers`).
- No XSS surface: trash button text is `aria-label` only, no user content rendered as HTML.

### 5.6 Performance — 9.5
- `limit + 1` keyset avoids a second `COUNT` query.
- Index hit: `(started_at, id)` natural ordering — assumed present from BRD-12 migrations (BRD-20 §4.2 ⇒ no migration); not regressed.
- Cascade-delete is one round-trip (ORM delete + commit), and `connection_manager.close` is in-memory.
- Optimistic UI: `onMutate` mutates cache synchronously before the network call — no flash on the happy path. AC-10 rollback path is also synchronous.

---

## 6. Findings (cosmetic only — non-blocking)

1. **Stale AC numbers in JSDoc.** `frontend/src/hooks/useRunHistory.ts` lines 5-7 and 86-87 reference "AC-13, AC-14". BRD-20 v1.1 stops at AC-12. Suggest renaming to "AC-03, AC-10" in the file header and to "AC-03, AC-10" / "BRD-20 §4.6" in the `useDeleteRun` docblock. *No behavior impact.*
2. **`Toaster.tsx` imports `cn` from `@/lib/utils`.** The rest of the codebase imports `cn` from `@/lib/cn` (e.g. `HistoryItem.tsx#L7`, `HistoryPanel.tsx`). If both re-export the same function this is harmless; if `lib/utils.ts` is a duplicate seam, fold it into `lib/cn.ts` for consistency. Verify in a follow-up.

Neither finding affects ACs, scores, or merge readiness.

---

## 7. Positive Highlights

- **Leak-guard ordering** is explicit, documented, AND covered by a dedicated test — exactly the surface the BRD §4.5 calls out.
- **Plural `setQueriesData` + snapshot rollback** are textbook TanStack Query optimistic mutation; covers the multi-`pageSize`-cache risk listed in BRD §9 / PLAN §10.
- **Cursor codec is stateless** (`base64url("<iso>|<uuid>")`) and tested for tamper, advance, and tail-empty boundaries.
- **Atomic-design discipline**: the template (`HistoryPanel.tsx`) is unchanged; new behavior lives entirely in the organism + page container.
- **Literal-string fidelity**: every error `detail` and the toast copy match BRD §14.3 verbatim, asserted in tests.

---

## 8. Recommendation

**APPROVE — merge after the two cosmetic nits in §6 are addressed in a follow-up commit (do not block this iteration).**
