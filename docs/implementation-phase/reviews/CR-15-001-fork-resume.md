# Code Review Report — IP-15 Fork & Resume

**User Story / Plan:** IP-15 (Fork & Resume from Events) — [IP-15-fork-resume.md](../implementation-plans/IP-15-fork-resume.md)
**Source BRD:** [BRD-15-fork-resume.md](../brds/BRD-15-fork-resume.md) (partially superseded by IP-15 §1 reconciliation)
**Plan audit reference:** [AUDIT-PLAN-US-15.md](../audits/AUDIT-PLAN-US-15.md) (audit_score 9.75/10, APPROVED iter 2)
**Iteration:** 1 (max 5)
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent
**Phase:** F4 (REVIEW)

---

## Summary

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Code Quality | 9.5/10 | 25% | 2.375 |
| Test Coverage | 10/10 | 20% | 2.000 |
| Architecture Compliance | 10/10 | 20% | 2.000 |
| Documentation | 9/10 | 15% | 1.350 |
| Security | 10/10 | 10% | 1.000 |
| Performance | 10/10 | 10% | 1.000 |
| **TOTAL** | | | **9.73 / 10** |

## Verdict

✅ **APPROVED** — proceeds to **F5 COMPLETE**.

The implementation realises every IP-15 task (B0–B6, T1–T2, F1–F8), satisfies RF-03 / RF-04 / RF-11, and the documented deviations (`monkeypatch` instead of `mocker.spy`; pre-existing ruff/eslint/hang issues left out-of-scope) are acceptable per the review brief. The atomicity, anchor-by-type, cross-run guard, and `resume_point` contract are all directly asserted in tests, not just smoke-checked.

---

## RF / Architecture Compliance

| Requirement | Evidence | Status |
|---|---|---|
| RF-03 fork from decision points | `RunService.fork_run` keeps `parent_run_id` + `forked_at_event_id` by reference (lineage by reference per IP-15 §1 R-01); `FORKABLE_EVENTS` exported to TS and consumed by [`CenterPanelContainer`](../../../frontend/src/pages/CenterPanelContainer.tsx#L29) | ✅ |
| RF-04 events never deleted (append-only) | No code path mutates or deletes events; resume appends a new `ResumedAfter*` frame; fork emits no event (lineage on `runs`) | ✅ |
| RF-11 resume after error / user cancel | `resume_run` emits `ResumedAfterError` / `ResumedAfterCancel` with `resume_point=f"after_step_{N}"`, `parent_event_id == anchor.id`, atomically with the `stop_reason` clear | ✅ |
| 7-value `stop_reason` enum invariant | Untouched; `_RESUMABLE` is a `frozenset` of two `StopReason` values only | ✅ |
| Events append-only / `extra="allow"` | Event models unchanged; B0 only adds a `commit: bool` flag to the writer | ✅ |
| Atomic-design import boundaries | `ForkModal` (organism) imports only atoms + `microcopy` + `cn`; only `pages/` imports `useRun*` | ✅ |
| Type-export contract (FE↔BE) | `scripts/export_types.py` exports `FORKABLE_EVENTS`; `frontend/src/types/events.ts` line 63 regenerated from `app.domain.events.FORKABLE_EVENTS` — no hand-edit | ✅ |
| Single uvicorn worker / no distributed locks | No new locks, queues, or workers introduced | ✅ |

---

## Detailed Feedback

### Code Quality (9.5/10)

**Strengths**

- [`RunService.resume_run`](../../../backend/app/services/run_service.py) uses a `match` statement for the branch and bundles the event append + status clear under a single `await self.db.commit()` exactly as IP-15 §3 B1 mandates. The corrupt-state guard (`raise HTTPException(500, "resume anchor event not found")`) refuses to silently clear status, which is the correct invariant.
- [`_find_resume_anchor`](../../../backend/app/services/run_service.py) filters `Stopped` events for `payload['stop_reason'] == 'user_cancelled'` in Python with an explicit comment ("portable across JSONB and SQLite test"). This is the right call given the test DB uses SQLite (no `payload->>` operator), and the comment justifies the deviation from the plan's `payload->>'stop_reason'` SQL filter without weakening the invariant.
- [`EventService.append_event`](../../../backend/app/services/event_service.py) `commit: bool = True` is keyword-only and default-true — existing call-sites (`cancel_run`, `create_run`, etc.) are unchanged byte-for-byte, as the plan required.
- Frontend organisms keep responsibilities thin: `ForkModal` is purely presentational, `CenterPanelContainer` owns mutation state, `useMemo` is used correctly for both `forkableEvents` and `resumeStepIndex`.

**Minor issues (the 0.5 deduction)**

- `FORK_MODAL_DESCRIPTION` in [`microcopy.ts`](../../../frontend/src/lib/microcopy.ts) says "The new run will replay the trace up to (and including) that point, then continue independently." Per IP-15 §1 R-01 the new run starts with **an empty event log** (lineage by reference, no replay). The microcopy contradicts the architecture. **Non-blocking** but should be tightened in a follow-up — e.g. "The new run branches from that point; you'll keep the original untouched." This is cosmetic copy, not a correctness bug.

### Test Coverage (10/10)

- Backend: `event_service.py` 100%, `run_service.py` 97% (Coder report). 43 IP-15 tests passing.
- Real invariants asserted, not smoke tests:
  - `test_resume_errored_emits_ResumedAfterError_with_anchor` — checks `latest.type`, `parent_event_id == anchor.id`, `step_index == anchor.step_index + 1`, **and** `payload["resume_point"] == f"after_step_{anchor.step_index}"`.
  - `test_resume_cancelled_emits_ResumedAfterCancel_with_anchor` — same shape with `cancel_event_id`.
  - `test_resume_raises_500_when_anchor_event_missing` — refreshes the run row post-error and asserts `stop_reason` is **still** `errored`.
  - `test_resume_is_atomic_when_append_fails` — monkeypatches `EventService.append_event` to raise, then asserts `run.stop_reason == errored` after rollback. Genuine atomicity test.
  - `test_fork_rejects_cross_run_event` — service-level, and `test_fork_endpoint_rejects_cross_run_event` — route-level 404.
- The `monkeypatch`-based commit counter in `test_append_event_no_commit_flushes_but_does_not_commit` (and its symmetric `test_append_event_default_still_commits`) asserts both directions of the invariant — strictly better than the plan's `mocker.spy` would have been. The documented deviation is accepted.
- Frontend: 43 tests across 6 suites passing. Highlights:
  - `ForkModal.test.tsx` — covers closed/empty/list/error/Escape/Close/pending-row-disabled paths and `axe()` clean.
  - `LineageBadge.test.tsx` — null-hide + link-to-parent + axe.
  - `CenterPanelContainer.test.tsx` — asserts the SSE-replay-on-connect assumption (`renders the ForkModal for a terminal run with forkable events`) and the post-resume notice/banner gate in **both** directions (notice shown before agent emits; banner returns once a `step_index > resumeStepIndex` event arrives). This is the §9 invariant the plan asked for.

### Architecture Compliance (10/10)

- Lineage by reference (no `ForkCreated` event) matches the in-flight architecture, not BRD-15 §4.3. The BRD divergence is correctly handled in IP-15 §1 and not re-introduced into code.
- `EventNotFoundError` (404) reused for both unknown-event and cross-run cases — collapsing the cross-run case to 404 (not 403) is an explicit security choice and is documented inline in [`run_service.py`](../../../backend/app/services/run_service.py) ("collapse to 404 so callers cannot probe event IDs across runs to enumerate the event log"). Good.
- Atomic-design boundaries verified:
  - `ForkableEventRow` (atom) — imports `Button`, `EventIcon`, `cn`. No molecules.
  - `LineageBadge` (molecule) — imports `Badge` atom + `react-router-dom`.
  - `ForkModal` (organism) — imports atoms + microcopy.
  - `CenterPanelContainer` (page) — sole consumer of `useRun` + `useRunStream`.
- No new plugin seams introduced where IP-15 §3 says "not-seams" (storage, planner, provider untouched).

### Documentation (9/10)

- Module-level docstrings on every new file cite IP-15 task IDs and the relevant RF/BRD section.
- The "why" comments in `RunService.resume_run` (single-commit atomicity rationale) and `_find_resume_anchor` (JSONB-vs-SQLite portability) are exactly the comments that should exist per the project comment policy.
- Microcopy centralised in [`microcopy.ts`](../../../frontend/src/lib/microcopy.ts) so a future BRD can flip it without grepping components.
- The 1-point deduction tracks the same issue as Code Quality: the `FORK_MODAL_DESCRIPTION` string documents a behaviour that does not exist.

### Security (10/10)

- Cross-run probing closed (B2). 404, not 403/400 — does not leak whether the event exists in another run.
- Pydantic `RunForkRequest` validates `event_id: UUID` at the boundary — no string-passthrough.
- All DB access is parameterised through SQLAlchemy 2.0 `select(...)` — no SQL injection surface.
- `API_URL` rule (L-008) holds: no new `fetch("/...")` or `new EventSource("/...")` introduced. The fork call goes through `useRun().fork(...)` which uses the shared `api` client (verified in `CenterPanelContainer.test.tsx` — the recorded URL contains `/api/runs/${RUN_ID}/fork`, and the `init.body` parses as `{ event_id }`, so the L-009 `...init` spread-order bug is not present in this path).
- No `setSystemTime`+`advanceTimersByTime` in the new Vitest cases.
- Auth still flows through the existing `username` dependency on every route.

### Performance (10/10)

- `resume_run` performs at most three queries (run fetch, anchor lookup, then a flush + commit). The errored-anchor lookup uses `ORDER BY step_index DESC LIMIT 1`, hitting the existing index.
- The cancelled-anchor lookup fetches all `Stopped` events for the run — bounded at ≤ 1 per run in practice, justified inline. No performance risk.
- Frontend: `forkableEvents`, `resumeStepIndex`, `agentEmittedAfterResume` are all `useMemo`-gated; `FORKABLE_SET` and `RESUME_EVENT_TYPES` are module-level `ReadonlySet` constants, not re-created per render.

---

## Required Changes (if not approved)

None — the score is above the 9.0 threshold. The microcopy nit below is recorded as a follow-up, not a blocker.

## Follow-up (non-blocking, defer to BRD-15 v1.1 or next iteration)

1. **`FORK_MODAL_DESCRIPTION` accuracy.** [`microcopy.ts`](../../../frontend/src/lib/microcopy.ts) currently says "The new run will replay the trace up to (and including) that point, then continue independently." Per IP-15 §1 R-01, the forked run starts with an empty event log and lineage is by reference. Reword to e.g. "The new run branches from that point; the original stays untouched." Update the corresponding microcopy import if any test asserts the literal.
2. **Plan §3 F2 listed a "Submit button disabled until a row is clicked" test.** The implementation chose per-row "Fork from here" buttons instead of a separate Submit, which is a reasonable UX choice. The equivalent test (`disables only the pending row's button while forking`) is in place. If the BRD/UX wants the modal to gain a primary Submit, raise it as a separate ticket.
3. **`test_events_placeholder_returns_501` is deselected** because `pytest-timeout` is not installed and the test hangs. Out of scope for IP-15 but should be tracked as a backend hygiene item (add `pytest-timeout` or fix the underlying placeholder behaviour).
4. **Pre-existing ruff / eslint debt** (3 ruff, ~56 eslint) is correctly left out of IP-15's scope but should be filed as a tech-debt ticket so it does not keep being inherited by future PR descriptions.
5. **Agent-restart wiring** is explicitly deferred per IP-15 §9. The hand-off note to BSA (BRD-15 v1.1 reconciliation + worker BRD) should be appended to `decisions-history.md` if not already done by the Orchestrator.

## Positive Highlights

- Atomicity is **actually tested** (`test_resume_is_atomic_when_append_fails`) by patching the dependency to raise after flush and verifying state is rolled back — many "atomic" claims in similar codebases stop at smoke-checking and break silently. This one will catch regressions.
- The `monkeypatch` commit-counter pattern reused in both `_no_commit_flushes_but_does_not_commit` and `_default_still_commits` asserts the invariant in both directions, which is strictly more informative than the plan's single `mocker.spy` would have been.
- The defensive cross-run 404 (rather than 400) closes an event-ID enumeration vector and is explained inline.
- The `_find_resume_anchor` JSONB / SQLite portability note shows the implementer understood the test/prod DB gap and chose the safer path with explicit reasoning — exactly the kind of "why" comment the project's comment policy asks for.
- The post-resume notice + banner-suppression invariant is tested in **both** directions, so the §9 deferral is observably honest in the UI.

---

**Decision:** ✅ APPROVED → **F5 COMPLETE**. No return to Coder.
