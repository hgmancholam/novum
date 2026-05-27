# Audit Report — BRD-19 (Agent Runner & Wiring) — Iter 2

**Artifact:** [BRD-19-agent-runner.md](../brds/BRD-19-agent-runner.md) (v1.1)
**Phase:** F1 — ANALYZE (BRD + US audit sub-loop)
**Auditor:** Auditor Agent
**Iteration:** 2 of 3
**Date:** 2026-05-26
**Verdict:** ✅ **APPROVED — proceed to F2 (Implementation Plan)**
**Score:** **9.20 / 10** (threshold ≥ 9.00)

Prior audit: [BRD-19-audit-v1.md](BRD-19-audit-v1.md) — 8.10 / 10.

---

## 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage (BRD audit) | 9.5 / 10 | 30 % | 2.85 |
| Acceptance Criteria Completeness (US audit) | 9.5 / 10 | 20 % | 1.90 |
| Blind-Path Absence | 8.5 / 10 | 25 % | 2.125 |
| Traceability | 9.5 / 10 | 15 % | 1.425 |
| Consistency with authoritative docs | 9.0 / 10 | 10 % | 0.90 |
| **TOTAL** | | | **9.20 / 10** |

Sub-scores per user request:
- **BRD audit:** 9.4 / 10
- **US audit:** 9.5 / 10 (US-19.6 + US-19.7 added; full INVEST + Gherkin coverage)
- **Blind-path detection:** 8.5 / 10 (the two v1 blockers resolved; three new minor/nit gaps below — none block approval)

---

## 2. Closure status of v1 findings (F-01 … F-10)

| ID | v1 severity | v1.1 status | Evidence |
|---|---|---|---|
| F-01 | BLOCKER | ✅ **CLOSED** | §4.3 "AgentOrchestrator(state=<RunState>, emit=<callback>, stopping_policy=None) — verified against `backend/app/agent/orchestrator.py:49`. No constructor change is required." §4.5 step 5 "using the **existing** constructor signature … No change to `orchestrator.py` is required." §10 lists verbatim "Modifying `backend/app/agent/orchestrator.py` in any way." §11 DoD bullet "`backend/app/agent/orchestrator.py` is NOT modified." Confirmed by inspection of `orchestrator.py:49-55` — signature is `(state, emit, stopping_policy=None)`. |
| F-02 | MAJOR | ✅ **CLOSED** | New §4.6.1 specifies `await_terminal(run_id, timeout=5.0)`: returns immediately if no task is registered; otherwise `asyncio.wait_for(self._tasks[run_id], timeout)`; swallows `CancelledError` (expected); re-raises `TimeoutError` as `RunStillRunningError` → HTTP 409 with `{"code": "run_still_terminating", "retry_after_seconds": 5}`. US-19.6 has Gherkin for both paths (success after wait, 5 s timeout → 409). Justification for option (a) vs (b)/(c) is substantive (latency hiding in (b); UX cost + lack of `ui-prototype.md` retry affordance for (c)). §11 DoD bullet for `await_terminal` present. NFR row added. E9 added in §8. |
| F-03 | MAJOR | ⚠️ **PARTIAL** | §4.8 correctly reframes the supervisor as a last-resort safety net, explicitly deferring to `orchestrator._handle_error` as primary (verified against `orchestrator.py:108-111` and `_handle_error` at line 259 which emits `AgentErroredEvent` + `StoppedEvent(ERRORED)`). The "skip if terminal event already exists" guard is specified. Two paired test cases (with vs without prior `StoppedEvent`) are listed in §6.1 under "supervisor last-resort (F-03)". **However:** the guard cites `event_service.get_latest_event(run_id)`, which **does not exist** in `backend/app/services/event_service.py` (the real API is `get_events(run_id, after_step=0, limit=100)` ordered ASC by `step_index`, and `get_event(event_id)`). See new finding **N-01** below. The semantic intent is unambiguous and easy to translate, so this does not block approval. |
| F-04 | MINOR | ✅ **CLOSED** | §4.3 step 3 sets `stopped_at` only if currently `NULL` ("preserves the cancel-request timestamp set synchronously by `cancel_run`"). New US-19.7. New E10. Test "cancel preserves stopped_at (US-19.7 / F-04)" added in §6.1. |
| F-05 | MINOR | ✅ **CLOSED** | §2 RF-02 row rewritten verbatim: "**Exception:** `cancel_run` synchronously sets `stop_reason = USER_CANCELLED` on the row as a belt-and-braces idempotent write … Both writes converge on the same value." |
| F-06 | MINOR | ✅ **CLOSED** | §7 NFR table distinguishes create (N=0 events, < 200 ms) from resume (< 200 ms for N ≤ 50, < 800 ms for N ≤ 500). Beyond N=500 documented as best-effort. |
| F-07 | MINOR | ✅ **CLOSED** | RF-04 row added to §2 traceability with rehydration-dispatch evidence. |
| F-08 | MINOR | ✅ **CLOSED** | §10 contains verbatim: "On shutdown, in-flight runs are cancelled cooperatively; their `stop_reason` remains `NULL`; they are resumable; no automatic startup sweep is performed." Plus a dedicated "Automatic crash-recovery sweep at process startup" out-of-scope bullet with rationale. |
| F-09 | NIT | ✅ **CLOSED** | §6.1 includes "start for deleted row (E1)" test case. |
| F-10 | NIT | ✅ **CLOSED** | §4.8 #3 verbatim: "`is_running()` returns False **immediately** when the task completes (Python invariant — no internal poll, no grace period)." (Caveat: see N-02 below for a microscopic ordering nuance — not a blocker.) |

**Score:** 9 / 10 findings fully closed; F-03 closed in intent, with one downstream method-name fix tracked as N-01.

---

## 3. Open Questions — closure check

| # | Question | Status | Verification |
|---|---|---|---|
| Q1 | `ConnectionManager.publish/subscribe` ownership | ✅ CLOSED | §4.9 heading is verbatim "**4.9 Delta from BRD-10 v1.0 — `connection_manager.publish` / `subscribe` / `unsubscribe`**". Audit verification phrase included ("Verified: `backend/app/sse/manager.py` … exposes only `connect`, `disconnect`, `cancel`, `is_cancelled`, `clear_cancelled`, `active_connections`, `reset`"). Confirmed against the real module — only those 7 method names exist. |
| Q2 | Resume target FSM state | ✅ CLOSED | §4.5 step 5 cites `data-flows-and-diagrams.md` lines 279–280 and locks `AgentState.SEARCHING`. **Verified:** lines 279–280 of that file contain exactly `ResumingAfterCancel -> Searching [label="ResumedAfterCancel\\n(replay event log)"]` and `ResumingAfterError -> Searching [label="ResumedAfterError\\n(replay event log)"]`. Citation is real and supports the claim. |
| Q3 | `WEB_CONCURRENCY` guard mechanism | ✅ CLOSED | §10 out-of-scope bullet states the authoritative mechanism is the systemd unit pin `--workers 1` in `infrastructure.md` §Supervisor. **Verified:** `docs/technical-phase/infrastructure.md:108` reads "Runs `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`." Citation is accurate. |
| Q4 | Quiet-shutdown event vs `stop_reason = NULL` | ✅ CLOSED | §10 contains verbatim the committed default and "no automatic startup sweep." Decision recorded both in body and changelog. |

All four open questions are answered in the BRD body, not only in the changelog.

---

## 4. New Findings (Iter 2)

### N-01 [MINOR] — `event_service.get_latest_event(run_id)` is not a real method

**Section:** §4.8 #2 (supervisor double-emission guard); §6.1 "supervisor last-resort" test case.

**Evidence:** `backend/app/services/event_service.py` exposes only `append_event`, `get_events(run_id, after_step=0, limit=100)`, and `get_event(event_id: UUID)`. There is no `get_latest_event`. `get_events` returns events ordered **ascending** by `step_index` with a default `limit=100`, so it is not a drop-in replacement either.

**Impact:** A coder following §4.8 literally will either (a) invent the missing method on `EventService` — a BRD-03 scope creep — or (b) work around it with `get_events(run_id, after_step=last_known_step_minus_one, limit=1)` plus an ORDER BY DESC, which the current API does not support without modification.

**Required fix in BRD-19 (next iteration or implementation-plan):** either
1. amend §4.8 #2 to use a query expression compatible with the current `EventService` (e.g. "issue a SELECT ordered by `step_index` DESC LIMIT 1 directly via the session" — acceptable inside the runner since it does not violate the storage not-seam), **or**
2. explicitly note that BRD-19 adds `EventService.get_latest_event(run_id) -> Event | None` as a new method (and lift this into §4.1 + DoD).

Because the guard logic is correct and the translation is mechanical, this finding does **not** block approval at the 9.0 bar. Recommend resolution as the first task in the F2 implementation plan.

### N-02 [NIT] — `is_running()` micro-window after `task.done()` and before `_on_task_done`

**Section:** §4.2 (`is_running` docstring "non-finished task is registered"); §4.8 #3 ("False immediately on task completion — Python invariant — no internal poll").

**Issue:** `add_done_callback` callbacks are scheduled on the event loop **after** the task finishes — there is a microscopic window where `task.done() == True` but `_on_task_done` has not yet removed the registry entry. The BRD's "immediately" wording is precise about intent but ambiguous about mechanism: a coder might implement `is_running` as `run_id in self._tasks` (false-positive during the window) or as `run_id in self._tasks and not self._tasks[run_id].done()` (correct).

**Required fix:** in §4.2 docstring, replace "non-finished task is registered" with "`run_id in self._tasks and not self._tasks[run_id].done()`" so the invariant is unambiguous. Pure documentation fix. Non-blocking; can be addressed at implementation time.

### N-03 [MINOR] — Cancel-during-resume-wait window is unspecified

**Section:** §4.6 (resume_run wiring), §4.6.1 (cancel↔resume race contract), §8 Edge Cases.

**Scenario.** `resume_run(R)` has committed the `ResumedAfterCancel` event and cleared `stop_reason` (see `backend/app/services/run_service.py:151` for the existing semantics — `resume_run` requires `stop_reason is None` to fail and commits the resume row before any post-commit work). It is now awaiting `agent_runner.await_terminal(R, timeout=5.0)`. During this window the user POSTs `/cancel`:
- `cancel_run` reads `run.stop_reason is None` (cleared by resume) → does NOT raise `RunAlreadyStoppedError`.
- `cancel_run` sets `run.stop_reason = USER_CANCELLED`, commits, calls `agent_runner.cancel(R)` which finds the prior (still-cancelling) task and is a no-op.
- The original task completes; `await_terminal` returns; `resume_run` calls `agent_runner.start(R)` on a row whose `stop_reason` is now `USER_CANCELLED`.
- The new orchestrator starts on a row marked as stopped — the row state and the FSM state are inconsistent, and the user's second cancel is silently lost.

**Why this is a blind path:** the user is in control (RF-08); a legal Cancel → Resume → Cancel click sequence within a few seconds produces an unrecoverable inconsistency.

**Required fix:** either
1. document E11: "If a cancel arrives while `resume_run` is awaiting `await_terminal`, `start(run.id)` re-reads `run.stop_reason` and raises `RunAlreadyStoppedError` instead of launching." Add a Gherkin scenario to US-19.6, or
2. document this as an accepted limitation and require the UI to disable Cancel while a Resume is pending (cross-reference `ui-prototype.md`).

Non-blocking — the previous v1 contract was strictly worse — but should land in the F2 plan or a v1.2 follow-up.

---

## 5. Blind-Path Checklist (Iter 2)

| Check | Result | Notes |
|---|---|---|
| Path completeness | ✅ | Cancel↔Resume race (v1 F-02) closed by §4.6.1. Cancel-during-resume-wait noted (N-03) but does not affect the canonical paths. |
| Error handling | ⚠️ → ✅ | Supervisor is now last-resort with explicit double-emission guard (§4.8 #2). N-01 is a translation issue, not a logic gap. |
| User feedback continuity | ✅ | `publish` + DB-poll fallback; 409 carries typed code + retry hint. |
| Terminal reachability | ✅ | All 7 `stop_reason` enum values reachable. |
| Cancellation honored | ✅ | Bounded ≤ 2 s (US-19.2), 5 s ceiling on shutdown (§4.7). |
| Resume coverage | ✅ | §4.5 + §4.6 + §4.6.1; locked to `SEARCHING` (Q2). |
| Budget cap | ✅ (inherited) | Owned by BRD-09. |
| Schema evolution | ✅ | §4.5 step 4 ignores unknown event types. |

---

## 6. User Story Audit (INVEST + Gherkin)

| US | I | N | V | E | S | T | Verdict |
|---|---|---|---|---|---|---|---|
| US-19.1 (start emits live events) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-19.2 (cancel < 2 s) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-19.3 (resume errored) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-19.4 (no orphan tasks on shutdown) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-19.5 (single-writer-per-run) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-19.6 (resume after cancel — NEW) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ — covers both success and 409 timeout paths in Gherkin |
| US-19.7 (cancel preserves `stopped_at` — NEW) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

All 7 stories pass INVEST + Gherkin. Sub-score 9.5 / 10 — full coverage of the v1 gaps.

---

## 7. Cross-doc Consistency Verification

| Reference in BRD-19 | Verified | Result |
|---|---|---|
| `orchestrator.py:49` signature `(state, emit, stopping_policy=None)` | ✅ | Matches lines 49-55 of the real file. |
| `orchestrator.py:107-111` top-level `except Exception → _handle_error` | ✅ | Confirmed; `_handle_error` at line 259 emits `AgentErroredEvent` + `_stop(StopReason.ERRORED)` (line 277). |
| `data-flows-and-diagrams.md` lines 279–280 (`ResumingAfter* -> Searching`) | ✅ | Exact match in source file. |
| `infrastructure.md` line 108 (`--workers 1` pin) | ✅ | Exact match. |
| `sse/manager.py` current API (no `publish`/`subscribe`) | ✅ | Confirmed — only `connect`, `disconnect`, `cancel`, `is_cancelled`, `clear_cancelled`, `active_connections`, `reset`. §4.9 delta is justified. |
| `event_service.get_latest_event` | ❌ | **Method does not exist** — see N-01. |
| `run_service.cancel_run` / `resume_run` call shape | ✅ | Wiring diffs in §4.6 are compatible with the real `cancel_run` (lines 134-149) and `resume_run` (lines 151-…). |

---

## 8. Memory Protocol Verification

`D-033: BRD-19 v1.1 — Audit feedback applied (F1 iter 2/3)` confirmed present at `.github/memory-bank/logs/decisions-history.md:13`. ✅

---

## 9. Verdict

**✅ APPROVED — score 9.20 / 10 ≥ 9.00.**

All 10 v1 findings are closed; F-03 has one downstream method-name issue (N-01) that is mechanical to resolve in the F2 implementation plan and does not invalidate the supervisor's logical contract. Two additional minor/nit findings (N-02, N-03) surfaced but neither blocks approval at the 9.0 bar.

**BRD-19 v1.1 is ready for the Orchestrator to start the F2 implementation-plan phase.**

Recommended F2 plan tasks should include (non-binding):
1. Resolve N-01 (either add `EventService.get_latest_event` or use a direct DESC query inside the runner).
2. Resolve N-02 (tighten `is_running` docstring + implementation to `run_id in _tasks and not _tasks[run_id].done()`).
3. Decide N-03 (E11 + Gherkin or UI-side disable) — can be deferred to v1.2 if scope-tight.

---

## 10. Next Step

- F1 closes. `audit_iter_F1 = 2` (within the 3-iteration cap).
- Hand off to **Orchestrator** for F2 (implementation-plan generation).
- F2 plan must cite N-01, N-02, N-03 as known-resolve items so they do not regress into blind spots.

---

## 11. Positive Highlights (Iter 2)

- Every v1 finding has a traceable, evidence-backed closure in the BRD body (not just the changelog).
- BSA verified BRD claims against real source files (orchestrator.py:49, sse/manager.py, infrastructure.md:108, data-flows lines 279-280) — this is a measurable improvement in rigour vs v1.
- §4.6.1 is a model of how to specify a race contract: states the problem, picks one option, justifies vs alternatives, defines the API surface, ties to a Gherkin US, and lands an NFR.
- §4.8 reframing makes the supervisor's role unambiguous: primary path is the orchestrator's own `_handle_error`; supervisor is defensive only.
- Open questions section is now a **resolution log**, not an open list — a clean closing pattern for an F1 sub-loop.
