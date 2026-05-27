# Audit Report — BRD-19 (Agent Runner & Wiring)

**Artifact:** [BRD-19-agent-runner.md](../brds/BRD-19-agent-runner.md)
**Phase:** F1 — ANALYZE (BRD + US audit sub-loop)
**Auditor:** Auditor Agent
**Iteration:** 1
**Date:** 2026-05-26
**Verdict:** ⚠️ NEEDS REVISION — **RETURN_TO_BSA**
**Score:** **8.10 / 10** (threshold ≥ 9.00)

---

## 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage (BRD audit) | 9 / 10 | 30 % | 2.70 |
| Acceptance Criteria Completeness (US audit) | 8 / 10 | 20 % | 1.60 |
| Blind-Path Absence | 7 / 10 | 25 % | 1.75 |
| Traceability | 9 / 10 | 15 % | 1.35 |
| Consistency with authoritative docs | 7 / 10 | 10 % | 0.70 |
| **TOTAL** |  |  | **8.10 / 10** |

Sub-scores requested by user:
- **BRD audit:** 8.3 / 10 (template complete; one factual inconsistency vs existing code).
- **US audit:** 8.0 / 10 (INVEST clean; two missing edge-case stories).
- **Blind-path detection:** 7.0 / 10 (cancel↔resume race + double-emission window).

---

## 2. Verdict

⚠️ **NEEDS REVISION (RETURN_TO_BSA).** The BRD is well-structured, English-only, RF-traceable, and respects all not-seam constraints (storage, LLM, planner). It correctly identifies the integration gap and proposes a minimal, single-module solution that does not duplicate BRD-07 / BRD-10 / BRD-15. However, three findings prevent approval at the 9/10 bar:

1. A factual mismatch between BRD-19 §4.3 / §4.5 / §11 and the actual `AgentOrchestrator.__init__` signature in `backend/app/agent/orchestrator.py`.
2. An unspecified race window between `cancel_run` and `resume_run`.
3. A double-emission risk in the supervisor's outer error handler (§4.8 #2) given the orchestrator's existing top-level `except Exception` (`orchestrator.py:108`).

None of these are deep design defects — all are tighten-the-spec edits. Two of the four "Open Questions" already have viable defaults in the BRD body and are **deferrable**; two are **blockers in disguise** (see §6 below).

---

## 3. Requirements Coverage Matrix

| RF | Covered? | Where (BRD-19 section) | Notes |
|---|---|---|---|
| RF-01 (autonomous stop) | ✅ | §2 row 1, §4.3 step 3 | Correct: stop only happens once the orchestrator actually runs. |
| RF-02 (7 stop_reason enum) | ✅ | §2 row 2, §4.3 step 3 | Runner is sole writer of `runs.stop_reason` via the terminal branch. Mostly true — §4.6 `cancel_run` writes it *twice* (belt-and-braces); flagged in §4 finding F-05 below. |
| RF-03 (append-only events) | ✅ | §2 row 3, §4.5 step 4 | Resume folds events; never mutates. `extra="allow"` honoured. |
| RF-04 (~17 event types, schema evolution) | ⚠️ | implicit only | RF-04 not listed in §2 traceability table. Minor — coverage is inherited from BRD-07 / BRD-03, but RF-04 schema-evolution invariant *is* exercised by the rehydration dispatch table at §4.5 step 4 ("Unknown event types → ignored"). Add an explicit row. |
| RF-05 (single-server, single-writer-per-run) | ✅ | §2 row 4, §4.2 (`_lock`, `_tasks` registry), US-19.5 | In-process registry; `anyio.Lock`; no Redis. Worker-count guard proposed at §9. |
| RF-08 (cancel + SSE live activity) | ✅ | §2 row 5, §4.3 step 2, §4.9, US-19.2 | Live publish + DB-poll fallback. SSE non-fatality is correct (RF-08 says viewer disconnect must not kill the run). |
| RF-11 (resume) | ✅ | §2 row 6, §4.5, US-19.3 | Re-launch is the missing piece BRD-19 closes. |
| RF-14 (plan critique) | ✅ (inherited) | §2 row 7 | Runner is transport-only — correct. |
| RF-15 (judge disconfirmation) | ✅ (inherited) | not listed | Implicitly inherited via emit relay; explicit mention would help. |

**Coverage gap:** none of substance; RF-04 should be added to the traceability table for completeness.

---

## 4. Findings

Each finding tagged `[BLOCKER]`, `[MAJOR]`, `[MINOR]`, or `[NIT]` with section anchor.

### [BLOCKER] F-01 — Incorrect orchestrator constructor signature

**Section:** §4.3 ("`AgentOrchestrator(..., on_event=emit)`"), §4.5 step 5 ("BRD-07 currently builds `RunState` from constructor args; a small extension is needed to accept a pre-built `initial_state`"), §11 DoD bullet 6.

**Evidence (actual code):**
```python
# backend/app/agent/orchestrator.py:49
class AgentOrchestrator:
    def __init__(
        self,
        state: RunState,
        emit: EventCallback,
        stopping_policy: StoppingPolicy | None = None,
    ) -> None:
```

- The parameter is named **`state`**, not `initial_state`.
- The parameter is named **`emit`**, not `on_event`.
- The orchestrator **already** accepts a pre-built `RunState` — no extension is required.

**Why this is a blocker:** §4.5 step 5 calls for a "non-breaking parameter addition (default `None` → build from args)". That work is unnecessary and, if implemented, would itself be a BRD-07 change forbidden by §10 "Out of Scope" of this BRD. The DoD item (§11 bullet 6) inherits the same mistake. A coder following this BRD literally would modify `orchestrator.py` without justification.

**Required fix in BRD-19 (no code changes — BSA only):**
- §4.3: rename `on_event=emit` → `emit=emit` (or simply `emit=callback`).
- §4.5 step 5: drop "a small extension is needed" and pass the rehydrated `RunState` directly via the existing `state=` argument.
- §11 DoD: delete bullet 6 ("`backend/app/agent/orchestrator.py` accepts an optional `initial_state`…").

---

### [MAJOR] F-02 — Cancel ↔ Resume race is unspecified

**Section:** §4.6 (cancel + resume diffs), US-19.2, US-19.3, §8 Edge Cases.

**Scenario:**
1. `cancel_run(R)` sets `run.stop_reason = USER_CANCELLED`, commits the row, calls `connection_manager.cancel(R)` and `agent_runner.cancel(R)` — the latter only **flips the flag**; the task is still alive.
2. User calls `resume_run(R)` 100 ms later. `resume_run` validates `stop_reason in _RESUMABLE` (true), appends `ResumedAfterCancel`, **clears `stop_reason`**, commits, then calls `agent_runner.start(R)`.
3. The original orchestrator task has not yet noticed the cancel flag → its registry entry is still present → `start(R)` raises `RunAlreadyRunningError`.

**Why this is a major blind path:**
- Neither US-19.3 nor §8 specifies what `resume_run` should do in this window.
- The user-facing failure mode (HTTP 409 a few hundred ms after a cancel+resume click) is exactly the kind of "blind path" the Auditor must flag (RF-08 says the user is in control; UX must not 409 on a legal sequence).
- Race window is bounded by orchestrator iteration latency, which BRD-07 does not pin — could be seconds inside an in-flight LLM call.

**Required fix:** add an explicit contract. Options to surface in BRD-19:
- (a) `resume_run` awaits prior task completion (`await agent_runner.await_terminal(run_id, timeout=…)`) before `start`; on timeout return 409 with a typed code.
- (b) `agent_runner.start` waits-on-and-replaces a still-flag-cancelled task instead of raising.
- (c) Document HTTP 409 + a retry recommendation as the explicit contract, and add a US covering this race.

BSA must pick one and add a US + an edge-case row (E9) to §8.

---

### [MAJOR] F-03 — Double-emission risk in supervisor's outer error path

**Section:** §4.8 #2.

**Evidence (actual code):**
```python
# backend/app/agent/orchestrator.py:107-111
        except Exception as exc:  # noqa: BLE001 - top-level error envelope
            ...
            return await self._handle_error(exc)
        return self.state.stop_reason or StopReason.ERRORED
```
`_handle_error` already emits `AgentErroredEvent` + `StoppedEvent(ERRORED)`. **The orchestrator never lets a non-`CancelledError` exception escape.**

**Why this matters:** BRD-19 §4.8 #2 proposes that the runner's `_supervised_run` also "opens a fresh session, appends `AgentErroredEvent` + `StoppedEvent(ERRORED)`" on any other `Exception`. Given the orchestrator's contract, that branch is reachable **only** if `_handle_error` itself raises — i.e. a bug in BRD-07's error path or a session failure during emission. The BRD presents this as routine error handling, not as a defensive last resort, which risks a coder duplicating terminal events under normal failure scenarios.

**Required fix:** clarify §4.8 to say:
- The supervisor branch is a **last-resort safety net for failures inside `_handle_error` itself** (e.g. DB write fails during emission of `AgentErroredEvent`).
- Before emitting, the supervisor must check whether a terminal event for this run already exists (e.g. `event_service.get_latest_event(run_id)` returns a `StoppedEvent`) and **skip** emission if so.
- Otherwise, the BRD must explicitly state that the orchestrator's top-level `except Exception` will be removed — which would be a BRD-07 change and therefore re-violate §10 "Out of Scope".

---

### [MAJOR] F-04 — Missing US / edge case for double-emission during cancel

**Section:** §4.6 cancel_run flow + §4.3 step 3.

**Scenario:** `cancel_run` sets `run.stopped_at = now()` directly on the row. Later, the orchestrator emits `StoppedEvent(USER_CANCELLED)`, and the runner's emit-callback §4.3 step 3 runs **`run.stopped_at = datetime.now(UTC)` again** — overwriting the original cancel timestamp with one that lags by however long the orchestrator took to notice the flag.

**Impact:** `stopped_at` no longer reflects the moment the cancel was *requested* — it reflects the moment the FSM noticed it. Audit trail and history-panel ordering (BRD-12) are subtly wrong.

**Required fix:** in §4.3 step 3, specify "set `run.stopped_at` only if currently NULL (or only update `stop_reason`)". Alternatively, hand cancel-driven termination a different code path in the emit callback. Either way, the BRD must pick one and document it. Add edge case E9 in §8.

---

### [MINOR] F-05 — `runs.stop_reason` is written by **two** code paths

**Section:** §4.3 step 3 vs §4.6 `cancel_run` "belt-and-braces" note.

§2 RF-02 row claims "the runner's terminal-event handler" is the *single* writer. §4.6 contradicts this: `cancel_run` writes `stop_reason = USER_CANCELLED` synchronously. The BRD already acknowledges the duplication ("belt-and-braces; idempotent"), but the wording in §2 is wrong. Fix the §2 row to say "single writer **except** for the synchronous-cancel idempotent set in `cancel_run`".

---

### [MINOR] F-06 — `start()` latency budget conflated for create vs resume

**Section:** US-19.1 (`POST /api/runs returns 201 within 200 ms`), §7 NFR row 1, §4.5 (event replay).

`start()` does: row load → replay N events → build `RunState` → construct orchestrator → register task. For `create_run` (N=0) this is sub-100 ms. For `resume_run` of a long run (N=200+ events), replay alone could exceed 200 ms. US-19.1 is fine (it's about `create`), but §7 NFR row 1 doesn't distinguish. Add a separate budget for `resume_run` or note the bound is "N=0 events".

---

### [MINOR] F-07 — RF-04 missing from §2 traceability

See coverage table above. One-line addition.

---

### [MINOR] F-08 — Crash-recovery on process start is not in §10 Out of Scope

**Section:** §8 E5, §10.

§8 E5 says runs that exceed the 5 s shutdown grace are "abandoned" and "the next process start will see them as silently-running rows; the user can `resume_run` them". This implies no automatic startup scan/sweep, but §10 doesn't list "automatic recovery of stop_reason=NULL rows on startup" as out of scope. Add it explicitly so the next BRD (or a future audit) doesn't re-open the question.

---

### [NIT] F-09 — `start()` for a deleted row

**Section:** §4.5 step 1, §8 E1.

E1 covers the race, but US/test for E1 is absent. Add either a one-line test entry in §6.1 or a brief note.

---

### [NIT] F-10 — `is_running` after a finished task

**Section:** §4.2 (`is_running`), US-19.2 (`is_running(run_id) returns False within 2 s`).

The `done_callback` (§4.7 / §4.8 #3) removes the entry, so `is_running` returns False **immediately** after task termination — not "within 2 s". US-19.2 phrasing is fine (it bounds the orchestrator's reaction time), but a developer reading §4.2 may expect an internal poll-with-grace. Tighten the docstring in §4.2.

---

## 5. User Story Audit (INVEST + Gherkin)

| US | I | N | V | E | S | T | Gherkin clarity | Verdict |
|---|---|---|---|---|---|---|---|---|
| US-19.1 (start emits live events) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | clear | ✅ |
| US-19.2 (cancel < 2 s) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | clear | ✅ |
| US-19.3 (resume errored) | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | misses cancel-then-resume race (F-02) | ⚠️ extend |
| US-19.4 (no orphan tasks on shutdown) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | clear | ✅ |
| US-19.5 (single-writer-per-run) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | clear | ✅ |

**Missing stories (raised by F-02 / F-04):**

- **US-19.6 (proposed):** Resume immediately after cancel honours the new resume request (Given a cancel was issued < 500 ms ago, When resume is called, Then …).
- **US-19.7 (proposed, or fold into US-19.2):** Cancel preserves the *requested* `stopped_at` timestamp across the eventual `StoppedEvent` write.

INVEST average: 4.6 / 5 stories fully pass; one extension needed → **8.0 / 10**.

---

## 6. Open Questions — Blocker vs Deferrable

User asked for an explicit classification of the four open questions in BRD-19.

| # | Open question | Verdict | Reason |
|---|---|---|---|
| 1 | `ConnectionManager.publish/subscribe` ownership (BRD-10 amendment vs BRD-19 delta) | **DEFERRABLE** | §4.9 already fully specifies the API surface and the SSE consumer behaviour. The ownership decision is paperwork. Recommended resolution: amend BRD-10 v1.1; record decision in BRD-19 §3 dependencies. |
| 2 | Resume target FSM state after `user_cancelled` | **DEFERRABLE WITH CAVEAT** | §4.5 step 4 already proposes "fallback `SEARCHING`". The risk row in §9 ("Resume rehydration mismatch") covers the consequences. Acceptable as a TODO **iff** the BRD locks the fallback to `SEARCHING` and references it from US-19.3. |
| 3 | `WEB_CONCURRENCY` guard mechanism | **DEFERRABLE** | §9 proposes the env-var refusal check and the systemd unit pin. The choice between env-var vs systemd-introspection is an infrastructure concern — does not block BRD-19's runtime behaviour. Mark as a follow-up for `infrastructure.md`. |
| 4 | Quiet-shutdown event vs `stop_reason = NULL` | **BLOCKER (light)** | §10 currently says "out of scope" for snapshot persistence but does **not** say which behaviour wins for shutdown. §8 E5 implies `NULL + resumable`. F-08 above turns this into a one-line `§10` addition. Fix as part of the F-08 edit. |

**Net:** 3 of 4 open questions are deferrable; #4 collapses into the F-08 minor fix. **None are stand-alone blockers** — but the BRD must commit to a default in writing for each.

---

## 7. Blind-Path Detection Checklist

| Check | Result | Notes |
|---|---|---|
| Path completeness (every non-terminal step has an outgoing edge for every outcome) | ⚠️ | Cancel→Resume race (F-02) has no defined outgoing edge from "task still alive + resume requested". |
| Error handling (every operation has retry / recovery / terminal) | ⚠️ | Supervisor's outer except is ambiguous (F-03). |
| User feedback continuity (UI never left without a state) | ✅ | Live `publish` + DB-poll fallback (§4.9) preserves L-states in `ui-prototype.md` §3. |
| Terminal reachability (all flows reach one of the 7 `stop_reason`) | ✅ | All 7 terminate via `StoppedEvent`. |
| Cancellation honoured (long-running steps observe `_cancelled`) | ✅ | Orchestrator already checks at iteration boundaries; runner relays via `cancel()`. |
| Resume coverage (every error/cancel terminal has a defined resume path) | ✅ | §4.5 + §4.6. |
| Budget cap | ✅ (inherited) | Owned by BRD-09; runner is transport-only. |
| Schema evolution (`extra="allow"` / optional keys) | ✅ | §4.5 step 4 "Unknown event types → ignored". |

→ **Blind-path score: 7 / 10** (2 unresolved scenarios, 6 clean).

---

## 8. Top-3 Must-Fix (Return to BSA)

1. **F-01 [BLOCKER]** — Correct §4.3, §4.5 step 5, and §11 DoD bullet 6 to match the existing `AgentOrchestrator(state=..., emit=...)` signature. Drop the proposed "optional `initial_state` parameter" — it is unnecessary and would violate BRD-19 §10 "Out of Scope".
2. **F-02 [MAJOR]** — Define the cancel↔resume race contract. Pick one of (a) await prior task termination inside `resume_run`, (b) replace-on-cancelled inside `start()`, or (c) document HTTP 409 as the explicit retry contract. Add edge case E9 to §8 and either extend US-19.3 or add US-19.6.
3. **F-03 [MAJOR]** — Re-frame §4.8 #2 as a last-resort safety net for failures inside the orchestrator's own `_handle_error`. Specify the "skip if terminal event already exists" guard so the supervisor cannot append duplicate `AgentErroredEvent` / `StoppedEvent` rows under normal exception paths.

Secondary edits (not gating, but recommended in the same pass): F-04 (`stopped_at` overwrite), F-05 (single-writer wording in §2), F-07 (RF-04 row), F-08 (§10 explicit out-of-scope for startup sweep + quiet-shutdown answer).

---

## 9. Positive Highlights

- Correctly identifies the integration gap; cites BRD-07 §10 as the upstream "not my problem" delegation. Minimal-surface design.
- Respects all three not-seams (storage, LLM, planner) — no abstraction layer introduced.
- Single-writer-per-run is enforced **in-process** (RF-05), no Redis/distributed locks.
- `extra="allow"` rehydration table explicitly handles unknown event types (RF-03 schema evolution rule honoured).
- DoD includes manual smoke test on Hetzner VM with real LLM call — strong end-to-end gate.
- Out-of-scope list is explicit and conservative (no scope creep into BRD-07 / BRD-08 / BRD-09 / BRD-15).
- English-only across body, identifiers, and proposed log messages — language policy clean.

---

## 10. Next Step

- **Action:** Return to BSA with this report. `audit_iter_F1 = 1 → 2` after BSA applies fixes.
- **Approval condition:** score ≥ 9.00. F-01, F-02, F-03 closed; F-04, F-05, F-07, F-08 closed or explicitly waived.
- **Iteration cap:** 3. Current iteration is well within budget.

---

## 11. Memory Update Pointer

A one-line decision entry has been appended to `.github/memory-bank/logs/decisions-history.md` referencing this report. No new lesson is recorded — the patterns surfaced here (orchestrator API drift between BRD and code, cancel↔resume race) are well-covered by existing entries on integration-gap detection.
