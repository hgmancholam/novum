# Audit Report — PLAN-US-20

<!-- STATUS HEADER — overwritten on every iteration -->
**Artifact:** PLAN-US-20 (delete-run-and-pagination)
**Phase:** F2
**Auditor:** Auditor Agent
**Latest Iteration:** 2
**Latest Date:** 2026-05-27
**Latest Score:** 9.5/10
**Latest Verdict:** ✅ APPROVED
**Iteration Log:**
| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-27 | 8.6 | ⚠️ NEEDS REVISION |
| 2 | 2026-05-27 | 9.5 | ✅ APPROVED |

---

## Iter 1 — 2026-05-27

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 9.5/10 | 30% | 2.85 |
| Acceptance Criteria Completeness | 8.0/10 | 20% | 1.60 |
| Blind-Path Absence | 7.5/10 | 25% | 1.875 |
| Traceability | 9.0/10 | 15% | 1.35 |
| Consistency w/ docs | 9.5/10 | 10% | 0.95 |
| **TOTAL** | | | **8.625 → 8.6/10** |

### 2. Verdict

⚠️ **NEEDS REVISION (7-8)** — Return to Orchestrator with the Required Changes in §5. `audit_iter_F2` → 2 (max 3 before F6 escalation).

### 3. Requirements Coverage Matrix

| RF | In scope? | Covered? | Where in plan | Notes |
|---|---|---|---|---|
| RF-05 | yes (US-20-A SC-5/6, US-20-B SC-9) | ✅ | §1, Task 1.5 (owner predicate), Task 1.6 (ownership check before terminal check) | Symmetric with BRD-20 §4.5 leak guard. |
| RF-09 | yes (US-20-B) | ✅ | Tasks 1.5, 1.7, 2.3, 2.6 | Keyset envelope `{items, has_more, next_cursor}`. |
| RF-13 | yes (US-20-A SC-3, SC-8) | ✅ | Task 2.5 (Motion exit, opacity-0/group-hover), Task 2.6 (More button visibility) | Microcopy from BRD-20 §14.3 referenced verbatim in tasks. |
| RF-03 | yes (US-20-A SC-7) | ✅ | §1 ("ON DELETE SET NULL"), Task 3.1 (`test_delete_run_orphans_forks_sets_parent_null`), §5 manual smoke | Schema already in place — no migration. |
| RF-08 | partially in scope (delete-while-streaming race) | ✅ | Task 1.6 (`connection_manager.close(run_id)` post-commit), §10 risk row | OK. |

No RF outside scope is missing. No RF coverage gap.

### 4. Blind-Path Findings

#### F-1 — `await_terminal` 409 leak path is undefined
- **Location:** [PLAN-US-20-delete-run-and-pagination.md §3 Task 1.6](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md)
- **Type:** unhandled_error
- **Affected RF / AC:** US-20-A SC-5, BRD-20 AC-04 (microcopy)
- **Severity:** major
- **Evidence:** Task 1.6 says "Best-effort `agent_runner.await_terminal(run_id, timeout=2.0)` to avoid racing the FSM (swallow timeout → still finished by stop_reason check above so impossible, but defensive)". But `await_terminal` already raises `RunStillTerminatingError` (HTTP 409 with body `{"code": "run_still_terminating", ...}`, see `backend/app/exceptions.py:88`). If the swallow is not made explicit, the route will return a 409 whose body **does not match** AC-04's mandated detail string `"Cannot delete a run that is still in progress. Cancel it first."`. Two terminal 409s with different bodies for the same user-facing condition violates the AC-04 contract.
- **Fix recommendation:** In `PLAN-US-20-...md` §3 Task 1.6, replace "swallow timeout → ... but defensive" with an explicit `try/except RunStillTerminatingError: pass` block, AND state that the terminal-state check (`if run.stop_reason is None: raise RunNotFinishedError`) is the **only** producer of the AC-04 409 body. Add a corresponding test case in Task 3.1 (`test_delete_run_swallows_await_terminal_timeout`).

#### F-2 — AC-10 toast contract has no implementation owner in this plan
- **Location:** [PLAN-US-20-delete-run-and-pagination.md §3 Task 2.4 and §11 Open Decision #1](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md)
- **Type:** no_user_feedback
- **Affected RF / AC:** RF-13, BRD-20 AC-10, US-20-A Scenario 8
- **Severity:** **critical**
- **Evidence:** BRD-20 §5 AC-10 is binding: *"a toast is shown with the literal copy `'Couldn't delete the run. Please try again.'`"*. US-20-A Scenario 8 repeats it verbatim. Task 2.4 instead proposes `console.error` + return rejection "if no toast hook exists". A `console.error` is invisible to the end user and fails AC-10. Punting the call to the Auditor (§11 #1) does not relieve the plan of an in-scope AC.
- **Fix recommendation:** In `PLAN-US-20-...md` §3, add a new Task 2.4b: "Add a minimal `useToast` hook + `<Toaster>` mount under `frontend/src/components/molecules/Toast.tsx` (single Radix `Toast.Root` queue, no animation choreography) — scoped to error toasts only. AC-10 string lives in `lib/constants.ts`." Wire `useDeleteRun.onError` to call it. If the Orchestrator judges that a toast molecule is non-trivial enough to deserve its own BRD, the alternative is to **open BRD-21 and remove AC-10's toast clause from BRD-20 §5 in the same revision** — but the plan cannot leave AC-10 silently unmet.

#### F-3 — Cache-walk API inconsistency: `setQueryData` vs `setQueriesData`
- **Location:** [PLAN-US-20-...md §3 Task 2.4](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md) vs §10 first risk row
- **Type:** missing_transition (silently leaves stale entries in caches whose key tuple includes a different `pageSize` or `username`)
- **Affected RF / AC:** US-20-A Scenario 3 ("R disappears from the cached history pages immediately"), US-20-B Scenario 7 (stable pagination)
- **Severity:** major
- **Evidence:** Task 2.4 prescribes `setQueryData` ("snapshot ... cache, remove the item from every page (`setQueryData` → `{...page, items: page.items.filter(...)}`)"). §10 risk row 1 contradicts this by prescribing `queryClient.setQueriesData({ queryKey: ["runs","history"] }, ...)` (plural). `setQueryData` requires an exact key match — it will skip cache entries that share only the prefix.
- **Fix recommendation:** In `PLAN-US-20-...md` §3 Task 2.4, replace `setQueryData` with `setQueriesData({ queryKey: ["runs","history"] }, ...)` (plural, prefix match) for both the optimistic write and the rollback snapshot loop. Align the task and the risk row.

#### F-4 — Missing explicit AC → task mapping column
- **Location:** [PLAN-US-20-...md §3 (all phases)](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md)
- **Type:** traceability gap (skill checklist §2 last bullet: "Every task lists which acceptance criterion it satisfies")
- **Severity:** minor
- **Evidence:** The task tables list `# / Task / File(s) / Effort / Depends on` but no `Satisfies AC` column. Mapping is inferable but not explicit. The Reviewer (F4) will need it to score Acceptance Criteria Completeness.
- **Fix recommendation:** Add a `Satisfies` column to the three Phase tables in §3 listing the BRD-20 AC IDs (AC-01…AC-12) and/or US-20-A/US-20-B Scenario numbers covered by each task.

#### F-5 — Old offset-based tests not explicitly removed
- **Location:** [PLAN-US-20-...md §3 Task 3.1, Task 3.2](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md)
- **Type:** schema_break (test suite drift)
- **Severity:** minor
- **Evidence:** Task 1.5 says "Drop the old offset signature entirely". Existing `backend/tests/test_run_service.py` and `backend/tests/test_routes_runs.py` exercise `list_runs(limit, offset)` and the legacy `list[RunListItem]` response shape. Tasks 3.1 / 3.2 say "extend" but never say "remove or rewrite the legacy `test_list_runs_*` cases". This will fail the suite the moment Task 1.5 lands.
- **Fix recommendation:** In `PLAN-US-20-...md` §3 Task 3.1 add: "Delete/rewrite the legacy `test_list_runs_*` cases that asserted the offset signature or `list[RunListItem]` envelope." Same in Task 3.2 for the route-level tests.

### 5. Required Changes (apply to `PLAN-US-20-delete-run-and-pagination.md` in place)

1. [ ] **§3 Task 1.6** — Make the `await_terminal` timeout swallow explicit (`try/except RunStillTerminatingError: pass`) and state that the terminal-state check is the sole producer of the AC-04 409 body. *(F-1)*
2. [ ] **§3 add Task 2.4b** — Either (a) ship a minimal `useToast` + `<Toaster>` under `frontend/src/components/molecules/` wired to `useDeleteRun.onError` with the AC-10 literal, or (b) open BRD-21 in the same revision and excise AC-10's toast clause from BRD-20 §5. Drop §11 Open Decision #1 once resolved. *(F-2)*
3. [ ] **§3 Task 2.4** — Change `setQueryData` to `setQueriesData({ queryKey: ["runs","history"] }, ...)` for both the optimistic write and the snapshot/rollback walk. Align with §10 risk row 1. *(F-3)*
4. [ ] **§3 (all phase tables)** — Add a `Satisfies` column listing BRD-20 AC IDs / US-20-* Scenario numbers per task. *(F-4)*
5. [ ] **§3 Task 3.1 and Task 3.2** — Add a sub-bullet "Delete or rewrite the legacy `test_list_runs_*` cases (offset signature / `list[RunListItem]` envelope) so the suite stays green after Task 1.5." *(F-5)*
6. [ ] **§11** — Replace the three open decisions with the resolutions in §0 of this report (toast → resolved per Required Change 2; HistoryList → resolved as "decide before Phase 2 starts via a 1-minute inspection of `RunPage.tsx` / current consumer"; cursor codec → confirmed). Keep §11 only for genuinely open items.

### 6. Positive Highlights

- **Scope discipline excellent.** Plan touches only `runs.py`, `run_service.py`, `exceptions.py`, `domain/run.py`, `useRunHistory.ts`, `lib/api.ts`, `types/history.ts`, and one new `HistoryItem` organism. No drift into BRD-12, BRD-15, BRD-19.
- **No DB migration / no env vars** — correctly leverages existing FK cascades verified at `backend/app/models/event.py:32` and `backend/app/models/run.py:100`.
- **§10 Risks** anticipates the four real failure modes (multi-variant cache, selection-store coupling, idempotent `connection_manager.close`, FSM race).
- **§9 Sequencing** correctly forces `pytest -q` after 1.6 and after 1.8, and `export_types.py` (1.9) before any FE work.
- **L-008 (`API_URL` prefix)** explicitly cited in Task 2.2.
- **Ownership-before-terminal leak guard** (Task 1.6) preserves BRD-20 §4.5 contract.
- **Tests interleaved per phase**, not deferred — matches `testing-policy` L-002.

### 7. Verdict on Plan §11 Open Decisions

| # | Decision | Auditor Verdict | Rationale |
|---|---|---|---|
| 1 | Toast surface (console.error vs toast) | ❌ **REJECTED** as `console.error` fallback | AC-10 is binding and mandates a literal toast string. Plan must add a minimal toast molecule (Required Change #2) or split into BRD-21 and remove the AC. Console-only fails the no-user-feedback blind-path check (§3 of Blind-Path Detection Checklist). |
| 2 | HistoryList extraction (organism vs page) | ✅ **ACCEPTED with constraint** | Flexibility is acceptable per scope discipline, BUT the Coder must commit to one path **before starting Phase 2** via a 1-minute `grep` for the current loop location. Add this as a 1-line note at the head of §3 Phase 2; do NOT leave the decision dangling at impl time. |
| 3 | Cursor codec: unsigned base64 over `f"{iso}\|{uuid}"` | ✅ **ACCEPTED** | BRD-20 §11 #3 already locked this. AC-11 covers tampering (400 on malformed input). A signed (HMAC) cursor would require a new server-secret env var (banned by §8 "no new env vars") and is V2 territory. No security gain inside an owner-scoped endpoint where the worst tamper outcome is "skip your own rows". |

### 8. Next Step

- ⚠️ NEEDS REVISION → return to **Orchestrator** with the six Required Changes above; `audit_iter_F2` increments to 2.
- If audit_iter_F2 reaches 3 without ≥ 9.0 → escalate to **F6** (manual review).

---

## Iter 2 — 2026-05-27

### 0. Resolution of Iter 1 findings

| Prior change | Status | Evidence |
|---|---|---|
| RC-1 — Task 1.6 explicit `try/except RunStillTerminatingError` + sole-producer note (F-1) | ✅ done | [PLAN-US-20 §3 Task 1.6](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md): *"**Best-effort `await_terminal` wrapped in `try/except RunStillTerminatingError: pass`** so the AC-04 409 body is NEVER shadowed by the BRD-19 `run_still_terminating` 409 body."* Coverage test `test_delete_run_409_does_not_leak_run_still_terminating_body` added to Task 3.1. |
| RC-2 — New Task 2.4b: minimal `useToast` + `<Toaster>` molecule wired to `onError` (F-2) | ✅ done | [PLAN-US-20 §3 Task 2.4b](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md) ships `toastStore.ts` + `useToast.ts` + `Toaster.tsx` (≤ 80 LOC). Task 2.4 `onError` calls `useToast().push({ kind: "error", message: "Couldn't delete the run. Please try again." })` — literal AC-10 string. New Task 3.6 covers Toaster unit tests. |
| RC-3 — Task 2.4 uses `setQueriesData` (plural) (F-3) | ✅ done | [PLAN-US-20 §3 Task 2.4](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md): *"**`queryClient.setQueriesData({ queryKey: ["runs", "history"] }, ...)`** (plural — prefix match across all `pageSize`/`username` tuples)"*. Aligned with §10 risk row 1. |
| RC-4 — `Satisfies` column on every phase table (F-4) | ✅ done | Phases 1, 2, 3 tables all carry a `Satisfies` column mapping each task to AC-IDs and/or US-20-A/B scenarios. (Phase 4 is docs-only — no AC mapping required.) |
| RC-5 — Phase 3 explicit legacy-test removal step (F-5) | ✅ done | New [Task 3.0](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md) declared as a pre-3.1/3.2 prerequisite: *"identify every existing `test_list_runs_*` case ... and either delete them or rewrite them against the new envelope"*. |
| RC-6 — §11 collapsed, no open decisions (F-2/Decision #1, Decision #2, Decision #3) | ✅ done | [PLAN-US-20 §11](../implementation-plans/PLAN-US-20-delete-run-and-pagination.md): *"All three open decisions from PLAN v1 were ruled on by the F2 Auditor … No decisions remain open."* Decision #1 → Task 2.4b; Decision #2 → Task 2.0 mandates a `grep` + committed top-of-file comment; Decision #3 → confirmed unsigned base64. |

All 6 Required Changes from Iter 1 closed.

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 9.5/10 | 30% | 2.85 |
| Acceptance Criteria Completeness | 9.5/10 | 20% | 1.90 |
| Blind-Path Absence | 9.5/10 | 25% | 2.375 |
| Traceability | 9.5/10 | 15% | 1.425 |
| Consistency w/ docs | 9.5/10 | 10% | 0.95 |
| **TOTAL** | | | **9.50/10** |

### 2. Verdict

✅ **APPROVED (≥ 9)** — Plan is ready for F3 (Coder). `audit_iter_F2` stops at 2; no further iteration required.

### 3. Requirements Coverage Matrix

| RF | In scope? | Covered? | Where in plan | Notes |
|---|---|---|---|---|
| RF-05 | yes | ✅ | Tasks 1.5 (owner predicate), 1.6 (ownership-before-terminal leak guard) | Unchanged from Iter 1 — still correct. |
| RF-09 | yes | ✅ | Tasks 1.5, 1.7, 2.3, 2.6 | Keyset envelope contract intact. |
| RF-13 | yes | ✅ | Tasks 2.4, 2.4b, 2.5, 2.6 | AC-10 toast now has an implementation owner (Task 2.4b) — previous gap closed. |
| RF-03 | yes | ✅ | §1, Task 3.1 (`test_delete_run_orphans_forks_sets_parent_null`), §5 manual smoke | Unchanged. |
| RF-08 | partial (delete-while-streaming race) | ✅ | Task 1.6 (`connection_manager.close(run_id)` post-commit), §10 risk row | Unchanged. |

No RF gaps. No scope drift.

### 4. Blind-Path Findings

None of severity ≥ minor. The four previously open blind paths (F-1 unhandled `await_terminal` 409, F-2 silent AC-10 failure, F-3 stale cross-variant cache pages, F-5 legacy-test break) are all resolved.

### 5. Required Changes

None. Plan is approved as-is.

### 6. Positive Highlights

- **Iter-1 feedback applied verbatim and in place** — no scope creep, no new BRDs spawned, no decisions deferred.
- **Task 2.4b kept minimal** (~80 LOC budget cited explicitly per copilot-instructions §6 over-engineering rule).
- **Task 2.0 "locate the list-loop"** is a clever pre-flight step that resolves §11 #2 without freezing flexibility prematurely; the result is committed in a top-of-file comment so the Coder cannot drift.
- **Task 3.6** (Toaster unit tests with Vitest fake timers, single `advanceTimersByTime`) honors L-009.
- **Task 3.1 `test_delete_run_409_does_not_leak_run_still_terminating_body`** turns the F-1 fix into a regression net.
- **§13 Document History** explicitly enumerates the iter-1 fixes — easy diff for reviewer/escalation trail.

### 7. Informational Notes (not deductions — out of audit scope)

- Task 4.3 flags a microcopy-sync follow-up between BRD-20 §14.3 and `ui-prototype.md §7.12`. Tracking that elsewhere (lessons-learned TODO) is correct — out of this plan's scope.
- Task 2.0 hard-codes a discovery comment at the top of Task 2.6's file; the Coder should keep that comment if it survives the PR (informational only).

### 8. Next Step

- ✅ APPROVED → publish PLAN-US-20 v2 as the source of truth; proceed to **F3 (CODE — Coder Agent)**.
- `audit_iter_F2` final value: 2. No further audit iteration.
