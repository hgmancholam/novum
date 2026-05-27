# Audit Report — PLAN-US-15

<!-- STATUS HEADER — overwritten on every iteration -->
**Artifact:** PLAN-US-15 (`docs/implementation-phase/implementation-plans/IP-15-fork-resume.md`)
**Phase:** F2 (PLAN)
**Auditor:** Auditor Agent
**Latest Iteration:** 2
**Latest Date:** 2026-05-26
**Latest Score:** 9.75/10
**Latest Verdict:** ✅ APPROVED

**Iteration Log:**

| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-26 | 8.20 | ⚠️ NEEDS REVISION |
| 2 | 2026-05-26 | 9.75 | ✅ APPROVED |

---

## Iter 1 — 2026-05-26

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 8/10 | 30% | 2.40 |
| Acceptance Criteria Completeness | 9/10 | 20% | 1.80 |
| Blind-Path Absence | 6/10 | 25% | 1.50 |
| Traceability | 10/10 | 15% | 1.50 |
| Consistency w/ docs | 10/10 | 10% | 1.00 |
| **TOTAL** | | | **8.20/10** |

### 2. Verdict

⚠️ **NEEDS REVISION (7-8).** Return to Orchestrator with the actionable items in §5. `audit_iter_F2` advances to 2 (max 3).

The plan is unusually well-engineered on the reconciliation/traceability axis — §1's three binding decisions (lineage-by-reference, `event_id: UUID`, mandatory `ResumedAfter*` events) are correctly identified, internally consistent, and faithful to the shipped architecture (verified against [backend/app/services/run_service.py](../../../backend/app/services/run_service.py), [backend/app/domain/events.py](../../../backend/app/domain/events.py), [backend/app/domain/run.py](../../../backend/app/domain/run.py), [backend/app/routes/runs.py](../../../backend/app/routes/runs.py)). These divergences from BRD-15 §4 are **not penalized** per the user-supplied audit context and per [architecture.md](../../technical-phase/architecture.md) §events + RF-11.

What pulls the score below the 9.0 approval threshold are three concrete blind paths in the task breakdown (§3) and the test inventory (§6) that, if implemented as written today, would either fail at runtime or leave the user without functional resume. Details in §4–§5.

### 3. Requirements Coverage Matrix

| RF | Covered? | Where | Notes |
|---|---|---|---|
| RF-03 (fork from decision points) | ✅ | §3 B2 (cross-run guard), §3 F1-F6, §3 T1-T2, §7 | Fully covered; `FORKABLE_EVENTS` canonical set correctly aligned with [domain/events.py L349-355](../../../backend/app/domain/events.py). |
| RF-04 (events never deleted) | ✅ | §1 R-01 (no event copy on fork), §3 B1 (append-only resume event) | Append-only preserved. |
| RF-11 (resume after error / user cancel) | ⚠️ partial | §3 B1, §3 B5-B6 | Event emission is specified, but **the post-resume agent restart is silent** — see §4 finding F-3. Without it, the user sees `ResumedAfter*` appended and then nothing happens. |

### 4. Blind-Path Findings

#### F-1 — `resume_point: str` is a required field, never populated by B1

- **Location:** §3 B1 / §3 B4 (also propagates to §6 tests `test_resume_errored_emits_event`, `test_resume_cancelled_emits_event`).
- **Type:** `unhandled_error` (Pydantic validation will raise) + `missing_transition`.
- **Affected RF:** RF-11.
- **Severity:** **critical**.
- **Evidence:** [domain/events.py L254-267](../../../backend/app/domain/events.py) shows both `ResumedAfterErrorEvent` and `ResumedAfterCancelEvent` carry a **required** field `resume_point: str` (no default). §3 B4 of the plan states *"no change required; service code reuses these"* but never specifies how `resume_point` is computed by `RunService.resume_run`. As written, B1 cannot construct a valid event instance and `EventService.append_event` will fail Pydantic validation at runtime.
- **Fix recommendation:** Either (a) add an explicit B-task specifying the derivation of `resume_point` (e.g., the FSM state name to resume from, or `"agent_loop"` as a v1 sentinel), and add a test asserting the value, **or** (b) make `resume_point` optional in `domain/events.py` (add a new B-task for the model change, justified under the `extra="allow"` / optional-only schema-evolution rule from copilot-instructions §3.5) and document the rationale.

#### F-2 — Atomicity test cannot pass without an `append_event(commit=False)` refactor that §3 does not list

- **Location:** §3 B1 (claim: *"Wrap append + run mutation in a single `db.commit()` so the pair is atomic"*) vs. §6 test `test_resume_atomic_with_status_clear` vs. §8 risk row 1 (mitigation is contingent).
- **Type:** `unhandled_error` + plan inconsistency (test promises an invariant that the task list does not implement).
- **Affected RF:** RF-11, RF-04.
- **Severity:** **major**.
- **Evidence:** [event_service.py L60](../../../backend/app/services/event_service.py) — `EventService.append_event` calls `await self.db.commit()` **internally**. With the current contract, B1 cannot make append + status-clear atomic; if the status-clear half failed after append, the run would already have a `ResumedAfter*` event but still be in `stop_reason=errored`. The test `test_resume_atomic_with_status_clear` asserts the opposite invariant. §8 mentions a `commit=False` flag as a *possible* refactor but it is not promoted to a B-task in §3.
- **Fix recommendation:** Promote the `commit=False` refactor from §8 mitigation into a concrete task (e.g., **B0** — `EventService.append_event` gains `commit: bool = True` parameter; existing callers unchanged; `RunService.resume_run` passes `commit=False` and commits once after also mutating the run). Update §6 test description to reference this contract.

#### F-3 — Post-resume agent restart is unspecified and not deferred

- **Location:** §3 B1, §5 AC-03, §9 (out of scope).
- **Type:** `no_user_feedback` / `unreachable_terminal` — the user clicks Resume, an event is appended, and then the run is silent forever.
- **Affected RF:** RF-11 ("resume *and continue* execution after an interruption").
- **Severity:** **major**.
- **Evidence:** Today's [run_service.py L140-158](../../../backend/app/services/run_service.py) only clears `stop_reason` and `stopped_at`; no agent task is scheduled. Grep across `backend/` confirms there is no orchestrator handoff from `resume_run`. The plan adds an event but does not add a task to re-enqueue the agent (the single-server task registry per copilot-instructions §2). BRD-15 §4.4 explicitly carried a `# TODO: Trigger agent restart via task queue`. The IP neither implements this nor lists it under §9.
- **Fix recommendation:** Choose one of:
  - **(a)** Add a B-task that re-spawns the agent task after `resume_run` succeeds (single-server task registry handoff). Add a test asserting that after `POST /resume` the orchestrator picks the run up (FSM state transition observable via SSE).
  - **(b)** Explicitly list "agent execution does not resume in v1; resume is event-only" under §9 with a rationale, and add a UI note to `ForkModal`/Resume button microcopy so the user understands the run will not actually continue. (This is a regression on RF-11 and would normally require BSA acknowledgement.)

#### F-4 — `original_error_event_id` vs. `cancel_event_id` semantics ambiguous

- **Location:** §3 B1 (*"`resumed_from_event_id` pointing at the last event of the prior segment (typically the `Stopped` event)"*).
- **Type:** `missing_transition` (semantic).
- **Affected RF:** RF-11.
- **Severity:** **minor**.
- **Evidence:** [domain/events.py L258, L266](../../../backend/app/domain/events.py): `original_error_event_id: UUID` and `cancel_event_id: UUID`. The semantically correct event to reference is the `AgentErrored` event (for the error case) and the `Stopped(user_cancelled)` envelope (for the cancel case) — **not** uniformly "the last event". B1's "typically the `Stopped` event" is ambiguous for the error path: should the field point at the `Stopped(errored)` envelope or at the prior `AgentErrored` event?
- **Fix recommendation:** Pin the contract explicitly: for `ResumedAfterError` → `original_error_event_id = id of the most recent AgentErrored event` (lookup by type, not by recency); for `ResumedAfterCancel` → `cancel_event_id = id of the most recent Stopped event with stop_reason=user_cancelled`. Add the corresponding assertions to §6 tests.

#### F-5 — `useRunStream` historical-replay assumption for terminal runs unverified

- **Location:** §3 F6 (*"useRunStream replays the historical log on connect, so works for terminal runs too"*).
- **Type:** `no_user_feedback` if the assumption is wrong (`ForkModal` would render empty on terminal runs).
- **Affected RF:** RF-03.
- **Severity:** **minor**.
- **Evidence:** [frontend/src/hooks/useRunStream.ts](../../../frontend/src/hooks/useRunStream.ts) connects to `/api/runs/{id}/events` and accumulates from the live stream; the plan does not cite a test or backend contract guaranteeing replay-on-connect for terminal runs. The IP should add either (a) a citation to the SSE replay contract in BRD-10 / [routes/runs.py](../../../backend/app/routes/runs.py), or (b) a fallback: have `CenterPanelContainer` also call `GET /api/runs/{id}/events` (REST) when `run.stop_reason !== null` and the local event buffer is empty.
- **Fix recommendation:** Add a one-line citation to the SSE replay-on-connect guarantee, OR add the REST fallback as a sub-task on F6 with a Vitest test.

#### F-6 — `EventNotFoundError` reused for cross-run case (B3) — semantically off

- **Location:** §3 B2 / B3.
- **Type:** schema/semantic concern.
- **Affected RF:** RF-03.
- **Severity:** **minor** (acceptable, but the rationale should be explicit).
- **Evidence:** [exceptions.py](../../../backend/app/exceptions.py) `EventNotFoundError` maps to 404 *"event does not exist"*. The cross-run case is *"event exists, but not on this run"* — closer to a 403/422. Reusing the exception leaks the existence of foreign events only by negative inference, which is fine for v1, but the plan should document the choice.
- **Fix recommendation:** Add a one-line rationale in B3 (e.g., *"intentionally collapsed to 404 to avoid disclosing existence of foreign events; revisit if cross-tenant boundaries appear in V2"*).

### 5. Required Changes

Priority order for Iter 2. Threshold ≥ 9.0; F-1, F-2, F-3 must be addressed for approval.

1. **[F-1, critical] Specify `resume_point: str` derivation in §3 B1 (and §6 tests).** Either populate the field with a concrete value or add a B-task to make it optional in `domain/events.py`. Update test names accordingly.
2. **[F-2, major] Promote the `commit=False` refactor of `EventService.append_event` from §8 (risk mitigation) into a first-class task (suggested label **B0**) in §3.** Reword §3 B1 to reference the new contract. Make `test_resume_atomic_with_status_clear` reference the same contract.
3. **[F-3, major] Resolve the post-resume agent restart gap.** Either add a task that re-enqueues the agent in the single-server task registry (preferred — keeps RF-11 honest) or explicitly list "agent continuation deferred to V2" under §9 with a UI microcopy note in F4/F6 so the user is informed. The current plan promises RF-11 in §7 but does not deliver continuation.
4. **[F-4, minor] Pin the semantics of `original_error_event_id` and `cancel_event_id`** in §3 B1 (look up by event *type*, not by "last event"). Add corresponding assertions to the §6 tests.
5. **[F-5, minor] Either cite the SSE replay-on-connect contract** that makes F6 safe for terminal runs, **or** add a REST fallback (`GET /api/runs/{id}/events`) as a sub-task on F6 with a Vitest test.

### 6. Positive Highlights

- §1 is exemplary reconciliation work: each divergence from BRD-15 is paired with a concrete code reference and a binding decision. This is exactly the kind of plan that prevents the implementer from drifting back into the BRD's contradictions.
- The `FORKABLE_EVENTS` canonical-set correction is grounded in `test_forkable_events_exact_membership` and matches [domain/events.py L349-355](../../../backend/app/domain/events.py) verbatim — no scope creep.
- §7 RF coverage matrix is tight and auditable.
- §3 T1/T2 correctly identifies that `frontend/src/types/events.ts` is generated and forbids hand-edits per copilot-instructions §3.7.
- §6 backend tests cover the cross-run fork guard and the resume-event atomicity claim — the right tests for the right invariants, even though the atomicity test exposes the gap flagged in F-2.
- Frontend test inventory covers a11y (jest-axe) and the empty-state path for `ForkModal`, consistent with the UI prototype microcopy guidance.

### 7. Next Step

- ⚠️ **NEEDS REVISION** — return to Orchestrator with the five Required Changes in §5.
- `audit_iter_F2` advances to **2** (max 3).
- If Iter 3 still scores < 9 → escalate to **F6 (manual review)**.

---

## Iter 2 — 2026-05-26

### 0. Resolution of Iter 1 findings

| Prior change | Status | Evidence |
|---|---|---|
| §5.1 [F-1, critical] Specify `resume_point` derivation | ✅ done | §3 B1 pins `resume_point=f"after_step_{anchor.step_index}"` for both branches. §3 B4 explicitly notes both `resume_point` fields are required and B1 must populate them. §6 adds `test_resume_event_resume_point_matches_anchor_step_index` and the routes-level test asserts "a populated `resume_point` string". Cross-verified against [backend/app/domain/events.py L254–267](../../../backend/app/domain/events.py): both fields are required (no default). |
| §5.2 [F-2, major] Promote `commit=False` refactor to a first-class task | ✅ done | §3 introduces task **B0** in `event_service.py` adding keyword-only `commit: bool = True`; when `False`, uses `flush()` + `refresh()`. Default-true preserves existing callers. §6 adds `test_event_service_append_no_commit` with `AsyncMock` spy. §3 B1 calls `append_event(..., commit=False)` and emits a single commit after the run-row mutation. §8 risk row correctly demoted ("promoted to task B0 … no longer a residual risk"). Cross-verified against [backend/app/services/event_service.py L60](../../../backend/app/services/event_service.py): the internal-commit call site is real and the proposed signature is backwards-compatible. |
| §5.3 [F-3, major] Resolve post-resume agent-restart gap | ✅ done (option **b** chosen) | §9 explicitly defers post-resume agent continuation to a future iteration with three concrete UI deliverables: (i) F4 ActionBar inline notice with pinned microcopy in `frontend/src/lib/microcopy.ts`, (ii) F6 `ResearchingBanner` suppression gated on `events.some(e => e.step_index > resumeStepIndex)`, (iii) the Vitest case `CenterPanelContainer shows post-resume notice and no ResearchingBanner until agent emits`. §10 DoD adds a follow-up task entry to wire the agent worker. RF-11 is now honestly scoped: state transition (ships) vs. agent restart (deferred with continuous user feedback — no silent-stall blind path). |
| §5.4 [F-4, minor] Pin `original_error_event_id` / `cancel_event_id` semantics by type | ✅ done | §3 B1 specifies the lookup as `Event.type == EventType.AGENT_ERRORED` (errored branch) and `Event.type == EventType.STOPPED` + payload filter `payload->>'stop_reason' = 'user_cancelled'` (cancel branch), both ordered by `step_index.desc()`. §6 test names updated: `test_resume_errored_emits_event_with_anchor_at_AgentErrored` and `test_resume_cancelled_emits_event_with_anchor_at_Stopped_user_cancelled` — they assert the field equals the looked-up event id. As a bonus, §3 B1 adds a corrupt-state guard (`HTTPException(500)` if anchor missing) with a dedicated test `test_resume_raises_500_when_anchor_event_missing`. |
| §5.5 [F-5, minor] Cite SSE replay-on-connect contract (or add REST fallback) | ✅ done (citation chosen) | §3 F6 cites [backend/app/sse/stream.py](../../../backend/app/sse/stream.py) `event_stream` L73–155 (connection without `last_event_id` ⇒ `after_step=0` ⇒ chronological replay of every persisted event; for terminal runs the loop exits after the trailing `Stopped` frame). §6 adds `CenterPanelContainer renders ForkModal for terminal run` mocking `useRunStream` with `isComplete=true` + non-empty `events`. Cross-verified against [stream.py L73–155](../../../backend/app/sse/stream.py): `_parse_last_event_id(None)` returns `0`; the polling loop yields every event then returns when an event of type `"Stopped"` is encountered. Contract is sound; REST fallback unnecessary. |

All five Iter-1 Required Changes are resolved in place. No new blind paths introduced by the revisions.

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 10/10 | 30% | 3.00 |
| Acceptance Criteria Completeness | 10/10 | 20% | 2.00 |
| Blind-Path Absence | 9/10 | 25% | 2.25 |
| Traceability | 10/10 | 15% | 1.50 |
| Consistency w/ docs | 10/10 | 10% | 1.00 |
| **TOTAL** | | | **9.75/10** |

Deltas vs. Iter 1: Requirements Coverage 8→10 (RF-11 honestly scoped via §9 deferral + UI continuity), AC Completeness 9→10 (every AC now has a concrete, asserted test path including the new resume_point and post-resume UX cases), Blind-Path Absence 6→9 (F-1/F-2/F-3/F-4/F-5 closed; the residual −1 is F-6, see §4). Traceability and Consistency unchanged at 10/10.

### 2. Verdict

✅ **APPROVED (≥ 9).** Publish the plan; proceed to **F3: IMPLEMENT** (Coder). `audit_iter_F2` final value: 2 of 3. No escalation needed.

### 3. Requirements Coverage Matrix

| RF | Covered? | Where | Notes |
|---|---|---|---|
| RF-03 (fork from decision points) | ✅ | §3 B2, F1–F6, T1–T2, §7 | Unchanged from Iter 1; cross-run guard + canonical `FORKABLE_EVENTS` set + lineage-by-reference all intact. |
| RF-04 (events never deleted) | ✅ | §1 R-01, §3 B0 (atomic append), §3 B1 (append-only resume) | B0 strengthens this: append + status-clear are now provably atomic, removing the risk of an orphan `ResumedAfter*` event without a matching status clear (or vice-versa). |
| RF-11 (resume after error / user cancel) | ✅ | §3 B0–B1, §3 B5–B6, §9 deferral, §3 F4 (inline notice) / F6 (banner suppression) | Honestly scoped: the **state transition** ships (status clear + `ResumedAfter*` event with populated `resume_point`); the **agent restart** is explicitly deferred to a follow-up iteration tracked in §10 DoD, with UI continuity guaranteed so the user is never left silent. This is the correct resolution of F-3. |

### 4. Blind-Path Findings

Only one minor finding remains. F-1 through F-5 from Iter 1 are closed (see §0).

#### F-6 (carry-over, minor) — Cross-run fork case still reuses `EventNotFoundError` without a documented rationale

- **Location:** §3 B2 / B3.
- **Type:** semantic concern (information-disclosure consideration).
- **Affected RF:** RF-03.
- **Severity:** **minor** (non-blocking).
- **Status:** Iter 2 §3 B3 now reads *"Reuse existing `EventNotFoundError` for the cross-run case (no new exception)."* This addresses the *mechanical* choice but does **not** spell out the *rationale* requested in Iter 1 §5.5 ("intentionally collapsed to 404 to avoid disclosing existence of foreign events; revisit if cross-tenant boundaries appear in V2"). The choice is defensible — collapsing to 404 is the right call for V1 single-server, single-tenant — but a one-line rationale in B3 would close the loop for a future reader.
- **Severity rationale for not blocking:** This is a documentation nit on an already-correct decision. It costs 1 point on Blind-Path Absence but does not threaten path completeness, terminal reachability, or user feedback. Listed below as a non-blocking nit for the Coder.

### 5. Required Changes

None (APPROVED). The single non-blocking nit is in §6 below.

### 6. Positive Highlights & Non-Blocking Nits

Highlights:

- **B0 promotion is exemplary.** The plan correctly identified that B0 is a *prerequisite* (not a mitigation) for the B1 atomicity invariant and refactored the task graph accordingly. The `commit: bool = True` keyword-only default preserves every existing caller — a clean, surgical change.
- **Anchor lookup pinned by `EventType`** is the right invariant. Combined with the corrupt-state `HTTPException(500)` guard and the dedicated test, it eliminates the entire "silently clear status without an event" failure mode flagged in Iter 1.
- **§9 deferral pattern is reusable.** Splitting RF-11 into "state transition (ships now)" + "agent restart (deferred, but UI never goes silent)" is a clean pattern that other in-flight BRDs should copy when they hit similar gaps. Recording this for the lessons-learned log.
- **SSE replay citation with file:line precision** ([stream.py L73–155](../../../backend/app/sse/stream.py)) — exactly the kind of citation that prevents the next auditor from re-litigating the question.
- **`resume_point=f"after_step_{anchor.step_index}"`** is a frugal, traceable encoding — the resume cursor can be reconstructed without any side channel, which will help when the agent-worker BRD lands and needs to know where to pick up.

Non-blocking nits the Coder should know:

1. **(F-6 carry-over)** When implementing §3 B2/B3, add a one-line code comment justifying why `EventNotFoundError` (→ 404) is reused instead of a 403/422 for the cross-run case. Suggested phrasing: *"Collapsed to 404 to avoid disclosing existence of foreign events; revisit if cross-tenant boundaries appear in V2."* No new exception class needed.
2. When implementing B0, prefer `pytest`'s `mocker.spy(event_service.db, "commit")` (or the AsyncMock spy named in §6) over patching the whole `AsyncSession` so the existing default-true callers' commit behaviour is also verifiable in the same test module.
3. The §9 microcopy string lives in `frontend/src/lib/microcopy.ts`. If that file does not yet exist in the workspace, prefer creating it (single source of truth for user-facing strings) over inlining the constant in `ActionBar.tsx` — this future-proofs the flip when the agent-worker BRD lands.
4. §10 DoD's follow-up task entry should be filed as an explicit row in `.github/memory-bank/logs/decisions-history.md` (not just a hand-off note) so the agent-worker BRD has a discoverable predecessor.

None of the above blocks approval.

### 7. Next Step

- ✅ **APPROVED** — plan is ready for **F3: IMPLEMENT**.
- Hand off to **Coder** with the four non-blocking nits in §6 as advisory inputs.
- `audit_iter_F2` final: **2 of 3**. No escalation.
- Memory-bank updates: append a `decisions-history.md` row for the APPROVED verdict and a `lessons-learned.md` entry for the "state-transition-now / restart-deferred-with-UI-continuity" pattern (see §6 highlight #3).
