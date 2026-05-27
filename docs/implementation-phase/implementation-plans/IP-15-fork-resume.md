# IP-15: Fork & Resume from Events

**Source BRD:** [BRD-15-fork-resume.md](../brds/BRD-15-fork-resume.md)
**Status:** In progress (audit iter 2)
**Date:** 2026-05-26
**Author:** Orchestrator (F2 — PLAN)
**RF coverage:** RF-03 (fork from decision points), RF-04 (events never deleted), RF-11 (resume after error / user cancel)

**Revision log:**
- Iter 1 → score 8.20/10. Returned with 5 actionable items (see [AUDIT-PLAN-US-15](../audits/AUDIT-PLAN-US-15.md) Iter 1).
- Iter 2 → addresses all 5 items in place: required `resume_point` populated (§3 B1), `append_event(commit=False)` promoted to task B0 (§3), event-type-targeted lookup pinned (§3 B1), agent-restart gap explicitly deferred with UI microcopy (§9), SSE replay-on-connect contract cited + REST fallback decision pinned (§3 F6).

---

## 1. Reconciliation with the in-flight architecture

BRD-15 §4 was authored before BRD-01 / BRD-02 / BRD-03 / BRD-10 landed and **contradicts the implemented architecture in three places**. This plan binds the implementation to the architecture that is already in production code, not to the BRD's prose.

| # | BRD-15 spec | Reality (already shipped) | This plan binds to |
|---|---|---|---|
| R-01 | Fork copies events `1..fork_at_step` into a new run and appends a synthetic `ForkCreated` event (§4.3) | `runs.parent_run_id` + `runs.forked_at_event_id` (UUID FK) store lineage **by reference**. No events are copied. `EventType` does **not** include `ForkCreated` (see `backend/app/domain/enums.py`, `backend/app/domain/events.py`, `architecture.md` §events table). | **Lineage by reference.** Forked run starts with an empty event log and references the parent run + the event it was forked from. Trace UI joins on `parent_run_id`. Matches `RunService.fork_run` (already implemented in [run_service.py](../../../backend/app/services/run_service.py)). |
| R-02 | Fork endpoint accepts `{ step_index: int }` (§4.4 `ForkRequest`) | Endpoint accepts `RunForkRequest{ event_id: UUID }` ([backend/app/domain/run.py](../../../backend/app/domain/run.py)). The route at [routes/runs.py](../../../backend/app/routes/runs.py) is live. Frontend [`api.ts::forkRun`](../../../frontend/src/lib/api.ts) already calls it with `event_id`. | **Keep `event_id: UUID`.** Step indices are unstable across the (future) trace UI filters and break referential integrity (no FK). |
| R-03 | Resume only updates `runs.stop_reason`; no event is emitted (current `RunService.resume_run` matches this) | [architecture.md](../../technical-phase/architecture.md) §events explicitly lists `ResumedAfterError` and `ResumedAfterCancel` as required events, and RF-11 § "Resume after cancel" mandates the `Stopped(...)` → `ResumedAfter*` append-only pair. Domain models `ResumedAfterErrorEvent` and `ResumedAfterCancelEvent` are already defined. | **Add event emission to `RunService.resume_run`.** Emit `ResumedAfterError` when prior `stop_reason == errored`, `ResumedAfterCancel` when prior `stop_reason == user_cancelled`. Both carry `resumed_from_event_id` pointing at the last event of the prior segment (typically the `Stopped` event). |

Two BRD-15 details that are also wrong:

- **BRD-15 §4.2 `FORKABLE_EVENTS`** lists `{PlanCreated, EvidenceCollected, ContradictionDetected, AnswerDrafted, JudgeVerdict}`. `EvidenceCollected`, `AnswerDrafted`, `JudgeVerdict` are **not real event types**. The canonical set fixed by BRD-02 / CR-02-001 is `{PLAN_CREATED, AMBIGUITY_DETECTED, CONTRADICTION_DETECTED, JUDGE_RULED, STOPPED}` — locked by `test_forkable_events_exact_membership`. **This plan uses the canonical set** and exposes it to the frontend via the type exporter.
- **BRD-15 §4.6 `ForkModal`** filters events client-side. We do the same, but we read the canonical set from a generated TS constant rather than hard-coding strings.

> The BRD is not amended by this plan (per the F1 in-place rule, BRD edits belong to BSA). The Orchestrator escalates the BRD-vs-architecture mismatch in the post-implementation hand-off note so BSA can produce a BRD-15 v1.1 reconciliation.

---

## 2. Scope

### In scope

| Area | What we ship |
|---|---|
| Backend — service | `RunService.resume_run` emits `ResumedAfterError` / `ResumedAfterCancel` via `EventService.append_event` (atomic with the `stop_reason` clear). Branch decided by the prior `stop_reason`. |
| Backend — service | `RunService.fork_run` additionally validates that the event belongs to the run being forked (currently it only checks the event exists, not its `run_id`). |
| Backend — domain | Confirm `ResumedAfterErrorEvent.original_error_event_id` and `ResumedAfterCancelEvent.cancel_event_id` fields are populated by the service. Rename intent kept; no schema change. |
| Type export | `scripts/export_types.py` adds a `FORKABLE_EVENTS` TS constant derived from `app.domain.events.FORKABLE_EVENTS`. Regenerate `frontend/src/types/events.ts`. |
| Frontend — atom | `ForkableEventRow` (presentational row inside the modal). |
| Frontend — organism | `ForkModal` — picks a forkable event from the run's event log, calls `useRun().fork(eventId)`, navigates to the new run on success. |
| Frontend — organism | `ActionBar` — un-disable the Fork button when the run has ≥ 1 forkable event in its log; open `ForkModal`. Removes the "(coming soon)" tooltip in that branch. |
| Frontend — molecule | `LineageBadge` — shows `Forked from <short-id>` when `run.parentRunId !== null`. Tooltip surfaces the event UUID. |
| Frontend — page | `CenterPanelContainer` — owns the modal open/close state, supplies forkable events via `useRunStream(runId)` (already used for terminal runs because `useRunStream` replays the historical log on connect). |
| Tests | Backend pytest + Frontend Vitest + jest-axe, ≥ 80 % per L-002. |

### Deferred (NOT this iteration)

- Trace-panel right-click "Fork from here" affordance → BRD-14.
- Visual lineage graph / breadcrumb across multiple fork generations → V2.
- Editing or deleting forks → out of scope per BRD-15 §10.
- A `ForkCreated` event in the event log → architecture decision: lineage is on `runs`, not in events. Documented in §1 R-01.

---

## 3. Task breakdown

### Backend

| # | Layer | File | Purpose |
|---|---|---|---|
| **B0** | service | [backend/app/services/event_service.py](../../../backend/app/services/event_service.py) | **Atomicity prerequisite for B1.** Currently `append_event` calls `await self.db.commit()` internally ([event_service.py L60](../../../backend/app/services/event_service.py)), which makes it impossible to bundle the event append with the run-row mutation in a single transaction. Add a keyword-only `commit: bool = True` flag: when `commit=False`, use `await self.db.flush()` + `await self.db.refresh(db_event)` and skip `commit`. Default-true preserves all existing callers byte-for-byte. Test: `test_event_service_append_no_commit` asserts that `commit=False` does not call `commit` (use `AsyncMock` spy) and that the event is still flushed (id populated). |
| B1 | service | [backend/app/services/run_service.py](../../../backend/app/services/run_service.py) | `resume_run`: branch on the prior `stop_reason` via `match`. **Source-event lookup is by type, not by recency:** for `errored` → `select(Event).where(Event.run_id == run_id, Event.type == EventType.AGENT_ERRORED).order_by(Event.step_index.desc()).limit(1)`; for `user_cancelled` → same query with `Event.type == EventType.STOPPED` filtering `payload->>'stop_reason' = 'user_cancelled'` (the `Stopped(user_cancelled)` event is the canonical resume anchor per [architecture.md](../../technical-phase/architecture.md) §events). Then append the recovery event via `EventService.append_event(..., commit=False)` (B0) with **all required fields populated**: `ResumedAfterErrorEvent(original_error_event_id=<found.id>, resume_point=f"after_step_{found.step_index}")` or `ResumedAfterCancelEvent(cancel_event_id=<found.id>, resume_point=f"after_step_{found.step_index}")`. `parent_event_id = found.id`. Then clear `stop_reason` + `stopped_at` on the run row. Single `await self.db.commit()` at the end so the append and the status clear are atomic. Defensive: if the lookup returns `None` (corrupt state — a run marked `errored` with no `AgentErrored` event), raise `HTTPException(500, "resume anchor event not found")` — do not silently clear status without an event. |
| B2 | service | (same file) | `fork_run`: add `if event.run_id != run_id: raise EventNotFoundError(...)` defensive check before the `FORKABLE_EVENTS` check. Prevents cross-run fork. |
| B3 | exceptions | [backend/app/exceptions.py](../../../backend/app/exceptions.py) | Reuse existing `EventNotFoundError` for the cross-run case (no new exception). No new exception for the corrupt-state guard in B1 — a bare `HTTPException(500, ...)` is acceptable for an invariant violation that the codebase is not expected to recover from. |
| B4 | domain | [backend/app/domain/events.py](../../../backend/app/domain/events.py) | **No schema change required.** Verified: `ResumedAfterErrorEvent` has `{original_error_event_id: UUID, resume_point: str}` and `ResumedAfterCancelEvent` has `{cancel_event_id: UUID, resume_point: str}` ([events.py L254–267](../../../backend/app/domain/events.py)). Both `resume_point` fields are **required** — B1 must populate them (`f"after_step_{N}"` per the format pinned above). |
| B5 | tests | [backend/tests/test_run_service.py](../../../backend/tests/test_run_service.py) | Extend with cases: `resume_errored_emits_ResumedAfterError_with_parent_pointing_at_AgentErrored`, `resume_cancelled_emits_ResumedAfterCancel_with_parent_pointing_at_Stopped_user_cancelled`, `resume_event_resume_point_matches_anchor_step_index`, `resume_raises_500_when_anchor_event_missing` (corrupt-state guard), `resume_is_atomic_when_append_fails` (force `EventService.append_event` to raise → `run.stop_reason` must still be `errored` after rollback), `fork_rejects_event_from_other_run`. |
| B6 | tests | [backend/tests/test_routes_runs.py](../../../backend/tests/test_routes_runs.py) | E2E: `POST /resume` returns 200 + a follow-up `GET /events` shows the new `ResumedAfter*` frame appended with monotonically next `step_index` and a populated `resume_point` string. `POST /fork` with event from another run returns 404. |

### Type exporter

| # | Layer | File | Purpose |
|---|---|---|---|
| T1 | scripts | [scripts/export_types.py](../../../scripts/export_types.py) | After the `EventType` union, append `export const FORKABLE_EVENTS: readonly EventType[] = [...]` sourced from `app.domain.events.FORKABLE_EVENTS`. Sort by `EventType` order to keep diffs stable. |
| T2 | generated | [frontend/src/types/events.ts](../../../frontend/src/types/events.ts) | Regenerated by `T1`. Hand-edits forbidden per copilot-instructions §3.7. |

### Frontend

| # | Layer | File | Purpose |
|---|---|---|---|
| F1 | atoms | `frontend/src/components/atoms/ForkableEventRow.tsx` (new) | Presentational row: `<button>` with event type label, short event UUID, step index, selected state ring. ARIA `role="radio"` + `aria-checked`. Uses `cn()` + design tokens. |
| F2 | organisms | `frontend/src/components/organisms/ForkModal.tsx` (new) | Controlled modal (`open`, `onClose`, `runId`, `events`). Filters `events` by `FORKABLE_EVENTS`. Empty-state copy from ui-prototype §7 (microcopy fallback: "No forkable points yet — wait for the agent to reach a plan or contradiction."). Submits via `useRun().fork(eventId)` (already wired); on success it closes and navigates to `/runs/<new id>`. Uses `Dialog` primitive if present in `atoms/`, otherwise a tokenized `<div role="dialog" aria-modal="true">` with focus trap (`useFocusTrap` if available; otherwise the standard "first focusable" pattern co-located in the component). |
| F3 | molecules | `frontend/src/components/molecules/LineageBadge.tsx` (new) | Shows `Forked from <username>/<short-id>` if `parentRunId !== null`. Click → navigates to the parent run page. Hidden when `parentRunId === null`. |
| F4 | organisms | [frontend/src/components/organisms/ActionBar.tsx](../../../frontend/src/components/organisms/ActionBar.tsx) | Drop the `disabled` + "(coming soon)" tooltip when `forkableEventCount > 0`. New optional prop `forkableEventCount: number` (default 0 keeps the disabled-with-tooltip branch). `onFork` is now wired. Existing `aria-label`, `data-testid`, `loading` props preserved. |
| F5 | organisms | [frontend/src/components/organisms/RunHeader.tsx](../../../frontend/src/components/organisms/RunHeader.tsx) | Render `LineageBadge` inside the meta row (right of `MetaRow`, before `ElapsedClock` when running). |
| F6 | pages | [frontend/src/pages/CenterPanelContainer.tsx](../../../frontend/src/pages/CenterPanelContainer.tsx) | Owns `isForkModalOpen` state. Sources `events` from `useRunStream({ runId })`. **SSE replay-on-connect contract** ([backend/app/sse/stream.py](../../../backend/app/sse/stream.py) `event_stream`, L73–155): when the client connects without a `last_event_id`, the server starts at `after_step=0` and streams every persisted event chronologically; for terminal runs the stream closes immediately after the trailing `Stopped` frame. `useRunStream` therefore receives the full historical log for both live and terminal runs — no separate REST fetch needed. New Vitest case `CenterPanelContainer renders ForkModal for terminal run` confirms this by mocking `useRunStream` to return a closed stream with a non-empty `events` array. Container computes `forkableEvents` and `forkableEventCount` and passes them to `ActionBar` + `ForkModal`. Listens for `forkedRun` from `useRun()` and calls `navigate(\`/runs/${forkedRun.id}\`)`. |
| F7 | hooks | [frontend/src/hooks/useRun.ts](../../../frontend/src/hooks/useRun.ts) | Already exposes `fork(eventId)`, `forkError`, `forkedRun`. **No change** to the hook — only the container consumes the new fields. |
| F8 | tests | `ForkModal.test.tsx`, `ForkableEventRow.test.tsx`, `LineageBadge.test.tsx`, `ActionBar.test.tsx` (extend), `CenterPanelContainer.test.tsx` (extend) | Vitest + RTL + jest-axe + MSW. ≥ 80 % per L-002. See §6. |

---

## 4. Event lineage diagram

Resume after error (RF-11):

```
events: [QuestionAsked] -> [PlanCreated] -> [...] -> [AgentErrored] -> [Stopped(errored)]
                                                                            |
                                                                            v  parent_event_id
                                                                       [ResumedAfterError]
                                                                            |
                                                                            v
                                                                       (agent resumes)
```

Fork:

```
run A.events: [QuestionAsked] -> [PlanCreated] -> [...] -> [JudgeRuled]
                                                                |
                                                                |  runs.forked_at_event_id (UUID FK)
                                                                v
run B (owner_username, parent_run_id=A.id, forked_at_event_id=JudgeRuled.id, empty event log to start)
```

No event is appended on fork. Lineage is reconstructed from `runs.parent_run_id` + `runs.forked_at_event_id`.

---

## 5. Acceptance-criteria coverage

| BRD-15 AC | Reconciled meaning | Status after IP-15 |
|---|---|---|
| AC-01 Fork creates new run | New run with `parent_run_id` + `forked_at_event_id` referencing the parent. Parent unchanged. **Events are not copied** (§1 R-01). | ✅ Already in `RunService.fork_run`; covered by `test_run_service::test_fork_run_*`. |
| AC-02 Only forkable events shown | Modal filters by the canonical `FORKABLE_EVENTS` set exported from the backend. | ✅ F2 + T1. |
| AC-03 Resume adds event | `ResumedAfterError` or `ResumedAfterCancel` appended atomically with the `stop_reason` clear. | ✅ B1. |
| AC-04 Fork preserves lineage | `LineageBadge` shows "Forked from …" on forked-run page. | ✅ F3 + F5. |

---

## 6. Test inventory

Coverage target: ≥ 80 % per L-002. Float boundaries are not in play (no thresholds). Fake timers not used.

### Backend

| Test | File | Asserts |
|---|---|---|
| `test_event_service_append_no_commit` | `test_event_service.py` | `append_event(..., commit=False)` flushes (event.id populated) but does **not** call `db.commit()` (verified by `AsyncMock` spy). Existing default-true callers unaffected. |
| `test_resume_errored_emits_event_with_anchor_at_AgentErrored` | `test_run_service.py` | After `resume_run` on a run with `stop_reason=errored`, the new event is `ResumedAfterError` with `original_error_event_id == <last AgentErrored>.id`, `parent_event_id == <last AgentErrored>.id`, and `resume_point == f"after_step_{anchor.step_index}"`. |
| `test_resume_cancelled_emits_event_with_anchor_at_Stopped_user_cancelled` | `test_run_service.py` | Same shape with `ResumedAfterCancel` + `cancel_event_id == <Stopped(user_cancelled)>.id`. |
| `test_resume_is_atomic_when_append_fails` | `test_run_service.py` | Patch `EventService.append_event` to raise after `flush`; assert run.stop_reason is **still** `errored` after the failed call (single-commit atomicity from B1). |
| `test_resume_raises_500_when_anchor_event_missing` | `test_run_service.py` | A run marked `errored` with zero `AgentErrored` events → `HTTPException(500)`; run.stop_reason unchanged. |
| `test_fork_rejects_cross_run_event` | `test_run_service.py` | Forking run A with an event of run B → `EventNotFoundError` (404). |
| `test_routes_resume_appends_event` | `test_routes_runs.py` | `POST /resume` returns 200; subsequent `GET /events` includes the new `ResumedAfter*` frame at the next `step_index` with a populated `resume_point`. |
| `test_routes_fork_cross_run_404` | `test_routes_runs.py` | `POST /runs/A/fork` with event of run B → 404 JSON body. |

### Frontend

| Test | File | Asserts |
|---|---|---|
| `ForkableEventRow renders type + short id` | `ForkableEventRow.test.tsx` | Type label, last 8 chars of UUID, `aria-checked` toggling, jest-axe clean. |
| `ForkModal filters non-forkable types` | `ForkModal.test.tsx` | Given `[PlanCreated, ToolCalled, EvidenceAdded, JudgeRuled]`, modal lists only `PlanCreated` and `JudgeRuled`. Uses MSW for `POST /fork`. |
| `ForkModal disables submit when no selection` | `ForkModal.test.tsx` | Submit button `disabled` until a row is clicked. |
| `ForkModal navigates on success` | `ForkModal.test.tsx` | After successful `fork`, `useNavigate()` is called with `/runs/<new-id>`. Uses a `MemoryRouter`. |
| `ForkModal shows empty-state when no forkable events` | `ForkModal.test.tsx` | Renders the empty-state copy + no submit button. |
| `ActionBar enables Fork when count > 0` | `ActionBar.test.tsx` (extend) | With `forkableEventCount=3`, button is not disabled, no "(coming soon)" tooltip, click calls `onFork`. |
| `ActionBar keeps Fork disabled when count == 0` | `ActionBar.test.tsx` (extend) | Existing tooltip + disabled assertion preserved. |
| `LineageBadge hides when parentRunId is null` | `LineageBadge.test.tsx` | Renders nothing. |
| `LineageBadge links to parent run` | `LineageBadge.test.tsx` | Click navigates to `/runs/<parentRunId>`. |
| `CenterPanelContainer wires fork flow` | `CenterPanelContainer.test.tsx` (extend) | Opening the modal, selecting an event, hitting Fork triggers `useRun().fork(...)` with the right `event_id`. |
| `CenterPanelContainer renders ForkModal for terminal run` | `CenterPanelContainer.test.tsx` (extend) | Mocks `useRunStream` returning `isComplete=true` + non-empty `events`; asserts modal lists forkable rows, confirming the SSE replay-on-connect assumption (§3 F6). |
| `CenterPanelContainer shows post-resume notice and no ResearchingBanner until agent emits` | `CenterPanelContainer.test.tsx` (extend) | After a successful resume, the inline notice (§9) is visible and `ResearchingBanner` is **not** rendered until an event with `step_index > resumeStepIndex` arrives. |

---

## 7. RF coverage matrix

| RF | Task(s) |
|---|---|
| RF-03 fork from decision points | B2 (cross-run guard), F1, F2, F3, F4, F5, F6, T1, T2 |
| RF-04 events never deleted (append-only) | B1 (event emission for resume), §1 R-01 (no event copy on fork) |
| RF-11 resume after error / user cancel | B1, B5, B6, F4 (existing Resume button), F6 |

---

## 8. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Modal a11y regressions (focus trap) | Low | jest-axe assertion on every render path of `ForkModal`. |
| Frontend reads events via SSE during a live run and the run terminates while the modal is open | Low | `useRunStream.isComplete` flips to true; the snapshot of `events` at the moment the modal opened is what the user picks from (stale-OK). |
| Existing `RunService.fork_run` is missing the cross-run guard (B2) — silent bug | Med | B2 + `test_fork_rejects_cross_run_event` close it. |
| Users press Resume and see no new events because the agent worker has not landed | High | F4 microcopy + F6 banner suppression (§9). The state transition is correct; only the continuation is deferred. |
| BRD-15 stays out of sync with this plan | Low | Orchestrator hand-off note flags BSA to produce BRD-15 v1.1 reconciling §4 with the architecture. |

> The previously-listed "append_event commits internally" risk is **promoted to task B0** (§3) and is no longer a residual risk.

---

## 9. Out of scope

Same as BRD-15 §10 plus:

- Migration of historical resume actions (none exist — pre-IP-15 resumes did not emit events; the gap is irrecoverable but cosmetic since `Stopped` is still in the log and `stopped_at == null` after resume is the recovered state).
- Per-event right-click "Fork from here" in the Trace panel — BRD-14.
- **Post-resume agent continuation (explicit deferral).** RF-11 mandates that a resumed run "continues from there". V1 has no task queue / worker registry yet ([architecture.md](../../technical-phase/architecture.md) §782 references an "in-process task registry" but the corresponding BRD has not landed; `RunService.resume_run` only clears `stop_reason`). IP-15 ships the **state transition** (status clear + `ResumedAfter*` event), not the **agent restart**. Until the worker BRD lands, the UI must signal this to the user. Frontend tasks add the following:
  - **F4 ActionBar microcopy:** after a successful `resume` mutation, render an inline informational note next to the live dot — copy: *"Resume recorded. Agent restart will land in a future iteration — refresh the page to see new events as they arrive."* This text is pinned in `frontend/src/lib/microcopy.ts` (or co-located constant if no central microcopy file exists yet) so a future BRD can flip it.
  - **F6 CenterPanelContainer:** suppress the misleading `ResearchingBanner` after a resume until at least one new post-resume event arrives (gate on `events.some(e => e.step_index > resumeStepIndex)` where `resumeStepIndex` is the `ResumedAfter*.step_index` from the latest SSE frame).
  - **Vitest case** `CenterPanelContainer shows post-resume notice and no ResearchingBanner until agent emits` covers this.

---

## 10. Definition of Done

- All B0–B6 / T1–T2 / F1–F8 tasks merged with tests passing.
- `pytest backend` green, ≥ 80 % coverage on new code.
- `vitest run` green, ≥ 80 % coverage on new components.
- `pyright --strict` and `ruff` clean on backend changes.
- ESLint + tsc strict clean on frontend changes (atomic-design imports respected).
- `scripts/export_types.py` re-run; `frontend/src/types/events.ts` regenerated and committed.
- jest-axe a11y assertions pass on `ForkModal` + `LineageBadge`.
- Hand-off note in `decisions-history.md` includes (a) the BRD-15 reconciliation request to BSA and (b) a follow-up task entry to wire the agent worker so resumed runs actually continue — unblocks the inline notice flip in F4.
