# BRD-19: Agent Runner & Wiring

**Document ID:** BRD-19
**Version:** 1.2
**Status:** Approved (v1.1) + §4.6 amendment (v1.2, F2 iter 2 reconciliation)
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 20 of 20

---

## 1. Executive Summary

The repository already contains a complete FSM (BRD-07 `AgentOrchestrator`), an event service (BRD-03), an SSE stream (BRD-10), and fork/resume bookkeeping (BRD-15). What is missing is the **runtime bridge**: today `RunService.create_run` only inserts a row in `runs` and returns 201, so the orchestrator is never launched, no `events` rows are appended beyond the row creation itself, no LLM/Tavily/Wikipedia calls are ever made, and the SSE stream emits nothing.

BRD-19 closes this gap with a single new module — `app/agent/runner.py` — plus three two-line wiring changes in `RunService` and one in `app/main.py` `lifespan`. The runner owns the lifecycle of orchestrator `asyncio.Task`s, enforces single-writer-per-run (RF-05), bridges `AgentOrchestrator.emit(...)` to `EventService.append_event(...)` + `connection_manager.publish(...)`, rehydrates `RunState` from the event log on resume, persists terminal `stop_reason` on the `runs` row, and cancels every in-flight task on app shutdown.

This BRD is **not** a refactor of any existing module. The FSM (BRD-07 §10 "Out of Scope" explicitly defers SSE + persistence), the SSE stream (BRD-10), the stopping signals (BRD-09), the confidence calculation (BRD-08), and the fork/resume DB logic (BRD-15) are all left untouched.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-01 | Autonomous stopping — the orchestrator must actually run for the stop reason to be decided. | Complete |
| RF-02 | The 7 `stop_reason` enum values are written to `runs.stop_reason` primarily by the runner's terminal-event handler. **Exception:** `cancel_run` synchronously sets `stop_reason = USER_CANCELLED` on the row as a belt-and-braces idempotent write so the UI reflects cancellation immediately (§4.6). Both writes converge on the same value. | Complete |
| RF-03 | Events are appended (never mutated) via `EventService.append_event`; resume appends on top of the existing log. | Complete |
| RF-04 | ~17 event types with `extra="allow"` schema evolution. The rehydration dispatch (§4.5 step 4) ignores unknown event types, honouring the forward-compatibility rule. | Complete |
| RF-05 | Single-server, single-worker. Task registry is in-process; single-writer-per-run is enforced by `RunAlreadyRunningError`. | Complete |
| RF-08 | SSE shows live activity because the runner publishes every emitted event through `connection_manager`. | Complete |
| RF-11 | Resume of `errored` / `user_cancelled` runs replays prior events into `RunState`, then re-launches the orchestrator. | Complete |
| RF-14 | The orchestrator owns plan critique; runner only relays its events — coverage is inherited. | Complete (by inheritance) |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-03 (RunService / EventService call sites) | End-to-end run lifecycle |
| BRD-05 (LLM client) | Runner must never bypass `llm.call` — orchestrator already conforms |
| BRD-06 (Source plugins) | Sources are constructed inside the orchestrator; runner just provides the registry |
| BRD-07 (Agent FSM) | Provides `AgentOrchestrator`, `EventCallback`, `cancel()`, `run()` |
| BRD-09 (Stopping signals) | Wired inside the orchestrator already — runner is transport-only |
| BRD-10 (SSE streaming) | Requires a `connection_manager.publish(run_id, event)` entry point (see §4.8 — minor extension to BRD-10) |
| BRD-15 (Fork & Resume) | `resume_run` already appends `ResumedAfterError` / `ResumedAfterCancel` — runner extends it by also re-launching the orchestrator |

---

## 4. Technical Specification

### 4.1 File Structure (new + modified only)

```
backend/
  app/
    agent/
      runner.py               # NEW — AgentRunner + module-level singleton
    exceptions.py             # MODIFIED — adds RunAlreadyRunningError
    services/
      run_service.py          # MODIFIED — 3 call sites (create/cancel/resume)
    sse/
      manager.py              # MODIFIED — adds async publish() + per-run queue (see §4.8)
    main.py                   # MODIFIED — lifespan shutdown hook
  tests/
    test_agent_runner.py      # NEW
    test_run_service.py       # EXTENDED — fake runner assertions
    test_routes_runs.py       # EXTENDED — end-to-end via FastAPI TestClient
```

### 4.2 Public API of `AgentRunner`

The runner exposes the surface below. Bodies are intentionally omitted — this is a spec.

```python
class AgentRunner:
    """Owns the lifecycle of every in-flight AgentOrchestrator task (RF-05).

    Single-writer-per-run: at most one asyncio.Task per run_id may exist.
    Registry is in-process (RF-05 forbids multi-worker / distributed locks).
    """

    async def start(self, run_id: UUID) -> None:
        """Spawn the orchestrator task for ``run_id``.

        Loads the run row, rehydrates RunState by replaying the event log
        (§4.5), constructs the emit callback (§4.3), and registers the task.

        Raises:
            RunNotFoundError: if the run row does not exist.
            RunAlreadyRunningError: if a task for this run_id is already registered.
        """

    def cancel(self, run_id: UUID) -> bool:
        """Request cancellation: calls ``orchestrator.cancel()`` and ``task.cancel()``.

        Returns True iff a task was registered. Idempotent for already-cancelled runs.
        Does NOT await termination — that is the orchestrator's job via the cancel flag.
        """

    async def shutdown(self) -> None:
        """Cancel every active task and wait up to 5 s per task.

        Called from FastAPI ``lifespan`` shutdown BEFORE ``engine.dispose()`` (§4.7).
        """

    def is_running(self, run_id: UUID) -> bool:
        """Return True iff a non-finished task is registered for ``run_id``."""


# Module-level singleton — mirrors ``connection_manager`` (BRD-10).
agent_runner: AgentRunner = AgentRunner()
```

Internal state:

- `self._tasks: dict[UUID, asyncio.Task[None]]` — task registry.
- `self._orchestrators: dict[UUID, AgentOrchestrator]` — to call `.cancel()` (cooperative flag, distinct from `Task.cancel()`).
- `self._lock: anyio.Lock` — guards registry mutations (`start`/`cancel`/cleanup).

### 4.3 The `emit` Callback Contract

Constructed per run inside `start()` and passed to the existing `AgentOrchestrator` constructor — signature is `AgentOrchestrator(state=<RunState>, emit=<callback>, stopping_policy=None)` (verified against `backend/app/agent/orchestrator.py:49`). **No constructor change is required.** The callback has three responsibilities, **in this order**:

1. **Persist.** `await event_service.append_event(run_id, event)`. The append already computes `step_index = max + 1` atomically (see `EventService.append_event`). The committed `Event` row is captured for step 2.
2. **Publish.** `await connection_manager.publish(run_id, persisted_event_dict)`. This is the live fan-out to any active SSE generator (§4.8). Failures here are **non-fatal**: they are logged with `structlog.exception("sse_publish_failed", ...)` and swallowed — RF-08 mandates the run does not die because a viewer disconnected.
3. **Mark terminal.** If `event.type == "Stopped"` (i.e. `StoppedEvent`), update the `Run` row:
   - `run.stop_reason = event.stop_reason.value` (idempotent: `cancel_run` may have already written the same value).
   - `run.stopped_at = datetime.now(UTC)` **only if `run.stopped_at IS NULL`** — preserves the cancel-request timestamp set synchronously by `cancel_run` (see F-04 / §4.6). For non-cancel terminal reasons, `stopped_at` is NULL on entry and is set here.
   - `await session.commit()`
   This is the primary point where `runs.stop_reason` is written (RF-02); the only other writer is the synchronous idempotent set in `cancel_run` (§4.6). The runner intentionally does **not** mirror `AgentErroredEvent` directly; the orchestrator's exception handler emits both `AgentErroredEvent` AND `StoppedEvent(stop_reason=ERRORED)` (BRD-07 §4.4) so this single branch handles all 7 terminal cases.

The callback runs inside the orchestrator task and shares its `AsyncSession` (§4.4) — it must never open a nested session.

### 4.4 Session Lifecycle

- The HTTP request's `AsyncSession` from `app.dependencies.get_db` is **closed** by the time the runner picks up the task (FastAPI cleans it up when the request returns 201).
- The runner therefore opens its **own** session from `async_session_maker` inside the task coroutine:

  ```python
  async def _run_task(self, run_id: UUID) -> None:
      async with async_session_maker() as session:
          ...
  ```

- One session per run, **not** per event — `EventService.append_event` already commits per call. This keeps the connection pool bounded by `max_active_runs` rather than `max_events`.
- On task exit (success, terminal stop, or exception) the `async with` block closes the session.

### 4.5 State Rehydration from DB on `start()`

`start()` must work identically for fresh runs (zero prior events) and resumed runs (N prior events including `ResumedAfterError` / `ResumedAfterCancel`). Algorithm:

1. `run = await session.get(Run, run_id)` — raise `RunNotFoundError` on miss.
2. Construct an initial `RunState` from the `runs` row (`run_id`, `question`, `user_context`, `confidence_threshold`, `output_format`).
3. `events = await event_service.get_events(run_id, after_step=0, limit=None)` — replay in `step_index` order.
4. For each event, fold it into `RunState` using a **dispatch table keyed by `EventType`**:
   - `PlanCreated` → set `sub_claims`, transition to `CRITIQUING`.
   - `EvidenceCollected` → append to `evidence`, mark claim covered.
   - `ContradictionDetected` → append to `contradictions`.
   - `AnswerDrafted` → set `draft_answer`.
   - `JudgeVerdict` → set `last_judge_confidence`, increment `judge_attempts`.
   - `SearchExecuted` → increment `search_count`.
   - `ResumedAfterError` / `ResumedAfterCancel` → reset `current_state` to the state implied by the anchor event (`AGENT_ERRORED` → `INIT`; `Stopped(user_cancelled)` → state at time of cancel, fallback `SEARCHING`).
   - Unknown / forward-compatible event types → ignored (`extra="allow"` model, RF-03 schema evolution rule).
5. Construct `AgentOrchestrator(state=run_state, emit=emit, stopping_policy=None)` using the **existing** constructor signature in `backend/app/agent/orchestrator.py:49`. No change to `orchestrator.py` is required — it already accepts a pre-built `RunState` as its first positional argument. (See §10 "Out of Scope": the runner MUST NOT modify `orchestrator.py`.)
6. Register the task: `self._tasks[run_id] = asyncio.create_task(self._supervised_run(orchestrator))`. Use `task.add_done_callback(self._on_task_done)` to remove the entry from `_tasks` / `_orchestrators` regardless of outcome (§4.7).

**Resume target FSM state.** The fallback target after replay is **locked to `AgentState.SEARCHING`** for both `ResumedAfterError` and `ResumedAfterCancel`. This is grounded in `docs/understanding-phase/data-flows-and-diagrams.md` §FSM diagram (lines 279–280): `ResumingAfterCancel -> Searching [label="ResumedAfterCancel (replay event log)"]` and `ResumingAfterError -> Searching [label="ResumedAfterError (replay event log)"]`. The evidence / coverage / sub_claims accumulated in `RunState` carry over via the dispatch table; only the FSM cursor resets to `SEARCHING`. Snapshotting the exact pre-cancel state is explicitly out of scope (§10).

### 4.6 Wiring Diff in `RunService`

Three call sites — all **after** the existing `await self.db.commit()` so the row is durable before launch.

**`create_run`** (after `await self.db.refresh(run)`):

```python
await agent_runner.start(run.id)
return RunResponse.model_validate(run)
```

**`cancel_run`** (after `connection_manager.cancel(run_id)`):

```python
agent_runner.cancel(run_id)
return RunResponse.model_validate(run)
```

Note: `cancel_run` keeps its existing behaviour of setting `run.stop_reason = USER_CANCELLED` directly on the row — this is intentional **belt-and-braces**, because the user expects the cancel to be visible immediately even before the orchestrator coroutine notices the cancellation flag. The orchestrator's own `StoppedEvent(stop_reason=USER_CANCELLED)` will then arrive a few hundred ms later and be a no-op against the already-set field (idempotent: same value).

**`resume_run`** — the call sequence is split: `await_terminal` runs **before** the existing body (so the prior task drains its terminal write before we clear `stop_reason`); `start` runs at the end after the final commit + refresh:

```python
# Inserted as the FIRST statement of resume_run, before `await self.db.get(Run, run_id)`.
# Cancel↔Resume race contract (§4.6.1): await prior task termination
# before clearing stop_reason. Bounded by AGENT_RUNNER_RESUME_GRACE_S = 5s.
await agent_runner.await_terminal(run_id, timeout=5.0)

# ... existing body unchanged: row lookup, _RESUMABLE validation, anchor
# lookup, atomic append + stop_reason=None commit, refresh ...

# Inserted as the LAST statement, after `await self.db.refresh(run)`.
await agent_runner.start(run_id)
return RunResponse.model_validate(run)
```

#### 4.6.1 Cancel ↔ Resume Race Contract

**Problem.** `cancel_run(R)` only flips the orchestrator's cooperative `_cancelled` flag; the task may still be alive when `resume_run(R)` is invoked moments later. Without an explicit contract, `agent_runner.start(R)` would raise `RunAlreadyRunningError` and the user sees an HTTP 409 on a perfectly legal Cancel→Resume click sequence (RF-08 violation).

**Chosen contract: (a) `resume_run` awaits the prior task with a bounded timeout before calling `start`.** Concretely:

1. `RunService.resume_run` calls `await agent_runner.await_terminal(run_id, timeout=5.0)` **before** appending the resume event.
2. `AgentRunner.await_terminal(run_id, timeout)` returns immediately if no task is registered; otherwise it awaits `self._tasks[run_id]` with `asyncio.wait_for(..., timeout)`, swallowing `asyncio.CancelledError` (expected) and re-raising `asyncio.TimeoutError` as `RunStillRunningError` mapped to HTTP 409 with a typed `{"code": "run_still_terminating", "retry_after_seconds": 5}` body.
3. The orchestrator's cancel-flag check at every iteration boundary (BRD-07) bounds the typical wait at sub-second; the 5 s ceiling matches the shutdown grace in §4.7 for consistency.

**Why (a) over the alternatives:**
- **(b) replace-on-cancelled inside `start()`** would silently wait inside `start`, hiding latency from the HTTP caller and complicating the single-writer invariant (two coroutines could observe `is_running == False` between cancel-flag-set and task-exit).
- **(c) HTTP 409 with a retry hint** is honest but pushes complexity to the UI, and `ui-prototype.md` does not specify a retry-on-409 affordance for resume. Worse UX than (a).

**Acceptance criterion** is encoded in US-19.6 (Gherkin).

### 4.7 Wiring Diff in `lifespan`

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("starting_novum", host=settings.host, port=settings.port)
    yield
    await agent_runner.shutdown()   # NEW — must run before engine.dispose()
    await engine.dispose()
    logger.info("shutdown_complete")
```

`shutdown()` iterates the registry, calls `cancel()` on each, then `await asyncio.wait_for(task, timeout=5.0)` per task, swallowing `asyncio.CancelledError` and `asyncio.TimeoutError` with a `logger.warning`. After 5 s the task is abandoned — Python will not block process exit on a daemonic task.

### 4.8 Error Flow + AgentErroredEvent Emission

**Primary path — inside the orchestrator.** Already handled by BRD-07 §4.4 and verified against `backend/app/agent/orchestrator.py:107-111` (`except Exception → _handle_error → emit AgentErroredEvent + StoppedEvent(ERRORED) → return StopReason.ERRORED`). The orchestrator **never lets a non-`CancelledError` exception escape `run()`**. The runner's emit callback persists both events and marks the run terminal via §4.3 step 3. This is the normal error path; the supervisor below is NOT involved.

**Last-resort safety net — outside the orchestrator.** `_supervised_run` wraps `orchestrator.run()` in `try/except` strictly to handle pathological cases where the orchestrator's own `_handle_error` itself fails (e.g. DB write fails during emission of `AgentErroredEvent`, or a bug in BRD-07's error path lets an exception escape). It is NOT a routine error path:

1. `asyncio.CancelledError` → re-raise (cooperative cancellation; the row was already marked by `cancel_run` per §4.6).
2. Any other `Exception` (escape from the orchestrator's own top-level `except`):
   1. Open a **fresh** session.
   2. **Guard against double-emission.** Read the latest event for `run_id` (`event_service.get_latest_event(run_id)`). If it is already a `StoppedEvent`, the orchestrator successfully emitted a terminal event before the exception escaped — **skip** all further emission and only ensure `runs.stop_reason` is populated (idempotent set).
   3. Otherwise, append `AgentErroredEvent(error_type=type(e).__name__, error_message=str(e), recoverable=True)` + `StoppedEvent(stop_reason=ERRORED)`, then update the row.
   4. Log with `structlog.exception("supervisor_last_resort", run_id=run_id, exc_info=True)`. The task must never die silently.
3. **Registry cleanup** — `_on_task_done` callback removes the run_id from `_tasks` and `_orchestrators` under the `anyio.Lock`. This means `is_running()` returns False **immediately** when the task completes (Python invariant — no internal poll, no grace period). A subsequent `resume_run` can re-`start()` the same `run_id` without colliding.

### 4.9 Delta from BRD-10 v1.0 — `connection_manager.publish` / `subscribe` / `unsubscribe`

> **Status: documented as a delta inside BRD-19. No separate BRD-10 amendment is filed.** Verified: `backend/app/sse/manager.py` (commit at audit time) exposes only `connect`, `disconnect`, `cancel`, `is_cancelled`, `clear_cancelled`, `active_connections`, `reset` — there is no `publish`/`subscribe` today. The three methods below are added by BRD-19 implementation and tracked here as the canonical specification.

The current `ConnectionManager` (BRD-10 §4.3) only tracks connection ids + cancel flags; the SSE stream (BRD-10 §4.2) discovers new events by polling `EventService.get_events` every 500 ms. To make live publish work end-to-end, this BRD adds a minimal pub/sub layer on the same manager:

```python
async def publish(self, run_id: UUID, event: dict[str, Any]) -> None:
    """Fan out one event to every active subscriber of run_id. Non-blocking."""

def subscribe(self, run_id: UUID) -> asyncio.Queue[dict[str, Any]]:
    """Return a per-connection queue; SSE generator drains it."""

def unsubscribe(self, run_id: UUID, queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Remove a subscriber queue."""
```

The SSE stream then prefers `queue.get()` with timeout = heartbeat interval, falling back to the existing DB poll on miss (preserves Last-Event-ID resume semantics — RF-08). If the queue is dropped because the consumer is slow, the next DB poll catches up. **This is the only change required outside BRD-19's own module** and is listed here so the auditor can flag it as a cross-cutting concern.

---

## 5. User Stories

### US-19.1 — Run starts immediately and emits live events

**As a** user
**I want** the agent to begin researching the moment I submit a question
**So that** I see live progress on the trace panel within a second of clicking "Ask"

```gherkin
Given an authenticated user with an open SSE connection to /api/runs/{run_id}/events
When the user submits POST /api/runs with a valid question
Then POST /api/runs returns 201 within 200 ms
And within 500 ms the SSE stream receives at least one QuestionAsked event
And within 5 s the SSE stream receives at least one PlanCreated event
And the corresponding rows exist in the events table with monotonic step_index
```

### US-19.2 — Cancel stops the agent within seconds

**As a** user
**I want** pressing Cancel to stop the agent quickly
**So that** I don't waste LLM budget on a question I no longer want answered

```gherkin
Given a run in state SEARCHING with an active orchestrator task
When the user calls POST /api/runs/{run_id}/cancel
Then the response is 200 within 200 ms
And runs.stop_reason is set to "user_cancelled" immediately
And within 2 s a StoppedEvent with stop_reason="user_cancelled" is appended to events
And agent_runner.is_running(run_id) returns False within 2 s
And no further LLM calls are issued after the cancel returns
```

### US-19.3 — Resume an errored run continues from the last event

**As a** user
**I want** to retry a run that errored mid-flight
**So that** the work already done (plan, evidence) is not thrown away

```gherkin
Given a run with stop_reason="errored" and N prior events including AgentErrored at step K
When the user calls POST /api/runs/{run_id}/resume
Then a ResumedAfterError event is appended at step N+1 (RF-11)
And runs.stop_reason is cleared
And agent_runner.start is invoked for run_id
And the orchestrator's RunState is rehydrated with the N prior events folded in
And the agent resumes from a state consistent with the last non-error event
And no event prior to step K is mutated or deleted (RF-04)
```

### US-19.4 — No orphan tasks on shutdown

**As an** operator
**I want** the FastAPI process to terminate cleanly
**So that** systemd restarts do not leak coroutines or DB connections

```gherkin
Given 3 runs are mid-flight when SIGTERM is received
When FastAPI's lifespan shutdown executes
Then agent_runner.shutdown() is awaited before engine.dispose()
And each task receives cancellation
And each task either terminates within 5 s or is logged and abandoned
And engine.dispose() runs after all tasks are settled
And the process exits with status 0
```

### US-19.6 — Resume immediately after cancel honours the new request

**As a** user
**I want** clicking Resume right after Cancel to start the run again without errors
**So that** I don't see a confusing 409 on a legal Cancel→Resume click sequence (RF-08)

```gherkin
Given a run R in state SEARCHING with an active orchestrator task
And POST /api/runs/{R}/cancel was issued less than 500 ms ago
And the orchestrator has not yet emitted Stopped(user_cancelled)
When the user calls POST /api/runs/{R}/resume
Then resume_run awaits agent_runner.await_terminal(R, timeout=5.0)
And within 5 s the prior task settles (emits Stopped(user_cancelled) or is cancelled)
And a ResumedAfterCancel event is appended after the Stopped row
And agent_runner.start(R) is awaited exactly once
And the response is 200 (not 409) under normal latency
And if the prior task fails to settle within 5 s the response is 409
   with body {"code": "run_still_terminating", "retry_after_seconds": 5}
```

### US-19.7 — Cancel preserves the requested `stopped_at`

**As a** user
**I want** the run history to show when I clicked Cancel, not when the agent finally noticed
**So that** the audit trail and history-panel ordering (BRD-12) reflect my actual intent

```gherkin
Given a run R in state SEARCHING and the orchestrator is mid LLM call
When POST /api/runs/{R}/cancel sets runs.stopped_at = T0 on the row
And 1.5 s later the orchestrator emits Stopped(user_cancelled)
Then the runner's emit-callback sets stop_reason but leaves stopped_at unchanged
And runs.stopped_at remains T0 (not T0 + 1.5 s)
And the StoppedEvent payload still carries its own timestamp (event time)
```

### US-19.5 — Single-writer-per-run is enforced

**As a** developer
**I want** two concurrent start() calls for the same run_id to fail loudly
**So that** RF-05 (no distributed locks; single-writer-per-run) holds even under racy callers

```gherkin
Given agent_runner.start(run_id=R) has been awaited and the task is still running
When agent_runner.start(run_id=R) is called a second time
Then a RunAlreadyRunningError is raised
And the existing task is not disturbed
And no second AsyncSession is opened
```

---

## 6. Testing Strategy

All tests use `pytest` + `pytest-asyncio`. **No real GitHub Models / Tavily / Wikipedia calls.** The orchestrator is faked at the class boundary (`AgentOrchestrator` subclass that yields a scripted sequence of events).

### 6.1 `tests/test_agent_runner.py` (NEW)

- **happy path** — `start(run_id)` with a `FakeOrchestrator` emitting `[QuestionAsked, PlanCreated, Stopped(JUDGE_CONFIRMED)]` results in 3 rows in `events`, `runs.stop_reason == "judge_confirmed"`, registry empty after completion.
- **single-writer** — second `start(R)` while first task is still running raises `RunAlreadyRunningError`.
- **start for deleted row (E1)** — `start(R)` where `run` row was deleted concurrently raises `RunNotFoundError` and registers nothing.
- **cancel** — `cancel(R)` flips orchestrator flag; `FakeOrchestrator` honours it and emits `Stopped(USER_CANCELLED)`; row updated; registry cleared.
- **cancel preserves stopped_at (US-19.7 / F-04)** — `cancel_run` sets `stopped_at = T0`; orchestrator emits `Stopped(USER_CANCELLED)` 1.5 s later; emit-callback observes `stopped_at IS NOT NULL` and leaves it untouched; final row has `stopped_at == T0`.
- **resume awaits prior task (US-19.6 / F-02)** — start R, request cancel, immediately call `resume_run`; assert `await_terminal` was awaited; assert `start(R)` is invoked exactly once *after* the prior task settled; assert no `RunAlreadyRunningError`.
- **resume timeout maps to 409 (US-19.6)** — fake orchestrator ignores cancel flag for 10 s; `resume_run` returns HTTP 409 with `{"code": "run_still_terminating"}` after the 5 s grace.
- **shutdown** — register 3 fake long-running orchestrators (each `await asyncio.sleep(10)`); `await shutdown()` returns within ~5 s; all tasks cancelled.
- **shutdown leaves stop_reason NULL** — registered tasks are cancelled cooperatively; no `StoppedEvent` is appended by the runner during `shutdown()`; `runs.stop_reason` remains `NULL` on the row and the run is resumable.
- **error propagation (normal path)** — `FakeOrchestrator.run` emits `AgentErrored` + `Stopped(ERRORED)` internally (mirroring `_handle_error`); supervisor sees no escape; runner persists both via emit-callback; no double-emission.
- **supervisor last-resort (F-03)** — `FakeOrchestrator.run` raises bare `RuntimeError("boom")` with no prior `Stopped` event in DB; supervisor opens fresh session, sees `get_latest_event` is NOT a `StoppedEvent`, appends `AgentErrored` + `Stopped(ERRORED)`. THEN repeat: pre-seed a `StoppedEvent(ERRORED)`, raise bare `RuntimeError`; assert supervisor **skips** emission (no duplicate `AgentErrored` or `Stopped` row).
- **publish failure is non-fatal** — monkeypatch `connection_manager.publish` to raise; verify events still persist and the run completes.
- **rehydration** — pre-seed `events` table with `[QuestionAsked, PlanCreated, EvidenceCollected x 2, AgentErrored, ResumedAfterError]`; call `start(R)`; assert the orchestrator receives a `RunState` with 2 evidence items, `sub_claims` populated, and `current_state == SEARCHING` (the locked fallback).
- **task race on terminal** — orchestrator emits `Stopped` and then the supervisor's `done_callback` fires; registry must be empty exactly once.

### 6.2 `tests/test_run_service.py` (EXTENDED)

Use a **fake** `agent_runner` (monkeypatched via `app.services.run_service.agent_runner`) that records calls.

- `create_run` → asserts `agent_runner.start(run.id)` is awaited exactly once.
- `cancel_run` → asserts `agent_runner.cancel(run.id)` is called exactly once.
- `resume_run` → asserts `agent_runner.start(run.id)` is awaited exactly once **after** the resume event is committed.

### 6.3 `tests/test_routes_runs.py` (EXTENDED)

End-to-end via FastAPI `TestClient` with a fake orchestrator wired via a dependency override:

- POST `/api/runs` → 201, then poll `events` table; verify the scripted sequence lands in order with monotonic `step_index`.
- A captured `connection_manager.publish` mock receives the same events in the same order.
- POST `/api/runs/{id}/cancel` → 200, then verify `Stopped(user_cancelled)` is appended within 2 s.

### 6.4 Coverage Target

`pytest --cov=app/agent/runner --cov-fail-under=80`. Targeted ≥ 80 % per `testing-policy` user memory; in practice the runner is small (~150 LOC) so ≥ 90 % is realistic.

---

## 7. Non-Functional Requirements

| Metric | Target | Notes |
|---|---|---|
| Latency `POST /api/runs` → 201 (create, N=0 events) | < 200 ms | Excludes LLM. `agent_runner.start` is fire-and-forget; event replay is N=0. |
| Latency `POST /api/runs/{id}/resume` → 200 (resume, N events) | < 200 ms for N ≤ 50 events; < 800 ms for N ≤ 500 events | Replay cost is O(N) DB reads + pure-Python folding. Beyond N=500 events the resume budget is documented as best-effort; budget exhaustion (RF-01·F) typically caps runs well below that. |
| Latency from `POST /api/runs` → first event published | < 200 ms | `QuestionAsked` is emitted before any LLM call. |
| Cancel latency (`POST /cancel` → `Stopped` row) | < 2 s | Orchestrator must check `self._cancelled` at every iteration boundary (BRD-07 already does). |
| Resume race grace (`await_terminal`) | ≤ 5 s | §4.6.1; exceeds → HTTP 409 with retry hint. |
| Memory | O(active runs) | Registry grows on `start`, shrinks on terminal event or shutdown. |
| Shutdown grace | ≤ 5 s per task | `asyncio.wait_for(timeout=5.0)`. |
| LLM provider | Only via `llm.call` | Runner never imports `litellm` directly (BRD-05 not-seam). |

---

## 8. Edge Cases & Failure Modes

| # | Scenario | Behaviour |
|---|---|---|
| E1 | `start(run_id)` called for a run whose row was deleted concurrently | `await session.get(Run, run_id)` returns None → raise `RunNotFoundError`. No task is registered. |
| E2 | DB unavailable mid-run (asyncpg connection drop) | Orchestrator's next `append_event` raises `OperationalError` → caught by `_supervised_run` → best-effort attempt to append `AgentErroredEvent` on a new session. If THAT also fails, log `structlog.exception` and drop the task. The `runs` row keeps its prior state until DB recovers. |
| E3 | `connection_manager.publish` raises | Logged and swallowed (§4.3 step 2). Run continues. SSE viewers fall back to the existing 500 ms DB poll loop. |
| E4 | `asyncio.CancelledError` arrives between persist and publish | Persist is already committed (atomic at DB level). Publish is skipped — viewer sees the event on next DB poll. Acceptable: the event is **never lost**, only delayed by up to 500 ms. |
| E5 | App shutdown while runs are mid-flight | `shutdown()` cancels each task and awaits up to 5 s. Tasks that exceed the grace period are logged and abandoned. The next process start will see them as silently-running rows; the user can `resume_run` them. |
| E6 | `cancel(run_id)` called for an unknown run_id | Returns False. No exception. Idempotent. |
| E7 | Two `cancel(run_id)` calls in quick succession | Second is a no-op (orchestrator flag is already True). |
| E8 | `start(run_id)` for a row whose `stop_reason` is already non-null (e.g. `JUDGE_CONFIRMED`) | Raise `RunAlreadyStoppedError` — terminal runs cannot be relaunched without `resume_run`, which validates `stop_reason in _RESUMABLE`. |
| E9 | Cancel↔Resume race (cancel issued, resume issued before task observes the cancel flag) | `resume_run` calls `await_terminal(timeout=5.0)` before `start`. Within grace → 200 + ResumedAfterCancel. Beyond grace → HTTP 409 `run_still_terminating` (§4.6.1, US-19.6). |
| E10 | `cancel_run` writes `stopped_at = T0`; orchestrator emits `Stopped(user_cancelled)` later | Emit-callback sets `stopped_at` **only if NULL**, preserving `T0` (§4.3 step 3, US-19.7). `stop_reason` write is idempotent (same value). |

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Task registry leak (terminal event arrives but `done_callback` does not fire) | Memory grows unbounded over weeks | Low | `add_done_callback` is invariant — Python guarantees it. Belt-and-braces: periodic registry sweep on shutdown. |
| Orchestrator never honours `cancel()` flag (infinite loop in a state handler) | Cancel UX broken; shutdown hangs 5 s | Medium | BRD-07 already checks `self._cancelled` at every loop iteration. Test US-19.2 enforces < 2 s cancel latency. Shutdown timeout caps the worst case at 5 s. |
| Pub/sub queue overflow (slow SSE consumer) | Memory pressure per stuck viewer | Low | Bounded queue (`maxsize=1000`); on overflow drop oldest + log. DB poll loop in BRD-10 ensures eventual delivery. |
| Two FastAPI workers (operator misconfigures `uvicorn --workers 2`) | Single-writer-per-run silently broken | Medium | Documented in BRD-18 / infrastructure.md; systemd unit pins `--workers 1`. Runtime check at startup: log error and refuse to start if `os.environ.get("WEB_CONCURRENCY", "1") != "1"`. |
| Resume rehydration mismatch (folded `RunState` disagrees with reality) | Agent re-does work or skips work | Medium | Resume always re-enters at `INIT` or `SEARCHING` (never mid-state); evidence/coverage carry over but FSM state is fresh. Snapshot test on `test_agent_runner.py::rehydration`. |

---

## 10. Out of Scope

Explicitly **not** part of BRD-19:

- LangGraph, LangChain, LlamaIndex or any other orchestration framework (copilot-instructions §2).
- Multi-process or multi-worker coordination (RF-05).
- Distributed locks, Redis, Celery, RQ (copilot-instructions §2 NOT-in-V1).
- Changes to the FSM transitions (BRD-07 §4.2) or task handlers (BRD-07 §4.4).
- Changes to stopping signals (BRD-09) or the confidence formula `min(S, J)` (BRD-08).
- Changes to the SSE wire protocol or the `Last-Event-ID` resume contract (BRD-10).
- Changes to fork/resume DB logic — `fork_run` and `resume_run` keep their current event-append behaviour (BRD-15). BRD-19 only **adds** an `agent_runner.start(run.id)` call after the existing commits.
- Persisting `RunState` snapshots. State is rehydrated from events on every `start()`; there is no separate state cache (RF-03: the event log is the source of truth).
- Authorization on `start()`. The runner trusts the calling service to have already enforced ownership; HTTP-layer auth lives in routes/services (BRD-04).
- **Modifying `backend/app/agent/orchestrator.py`** in any way. The existing constructor signature `AgentOrchestrator(state, emit, stopping_policy)` is sufficient (verified at audit time). Any extension of the orchestrator is a BRD-07 change and out of scope here.
- **Automatic crash-recovery sweep at process startup.** On startup the runner does NOT scan for `stop_reason IS NULL` rows and does NOT re-launch them. The user must explicitly `resume_run` such rows. Rationale: an automatic sweep could re-launch runs the user had abandoned, and there is no safe way (without a separate `ServerShuttingDown` event) to distinguish "crashed mid-flight" from "in-flight at clean shutdown".
- **Shutdown event emission.** On shutdown, in-flight runs are cancelled cooperatively; their `stop_reason` remains `NULL`; they are resumable; no automatic startup sweep is performed. The runner does NOT emit a `StoppedEvent` or a hypothetical `ServerShuttingDown` event for in-flight runs during `shutdown()`. The 5 s per-task grace allows clean cancellation but is not used to write terminal events. Adding an explicit shutdown event is a deliberate follow-up for V2 and is not part of BRD-19.
- **Cross-process worker-count enforcement.** BRD-19 may log and refuse to start when `WEB_CONCURRENCY != "1"` as a defensive in-process check (§9), but the **authoritative** mechanism is the systemd unit pinning `--workers 1` in `docs/technical-phase/infrastructure.md` §Supervisor. Any deeper enforcement (systemd-introspection, advisory locks) is an infrastructure concern, not a runner concern.

---

## 11. Definition of Done

- [ ] `backend/app/agent/runner.py` exists and exports `AgentRunner` + `agent_runner` singleton.
- [ ] `backend/app/exceptions.py` exports `RunAlreadyRunningError` (HTTP 409 Conflict).
- [ ] `backend/app/services/run_service.py` invokes `agent_runner.start` from `create_run` and `resume_run`, and `agent_runner.cancel` from `cancel_run`.
- [ ] `backend/app/main.py` awaits `agent_runner.shutdown()` in `lifespan` shutdown **before** `engine.dispose()`.
- [ ] `backend/app/sse/manager.py` exposes `publish` / `subscribe` / `unsubscribe` (delta from BRD-10 v1.0, documented in §4.9).
- [ ] `backend/app/agent/runner.py` exposes `await_terminal(run_id, timeout)` for the cancel↔resume race contract (§4.6.1).
- [ ] **`backend/app/agent/orchestrator.py` is NOT modified.** The runner uses the existing `AgentOrchestrator(state=..., emit=..., stopping_policy=...)` signature.
- [ ] `tests/test_agent_runner.py` covers all scenarios listed in §6.1 (including the new E9, E10, US-19.6, US-19.7, and supervisor double-emission guard) and passes.
- [ ] `tests/test_run_service.py` extensions pass.
- [ ] `tests/test_routes_runs.py` extensions pass.
- [ ] `pyright --strict` clean on the new module.
- [ ] `ruff check` and `ruff format --check` clean.
- [ ] Coverage on `app/agent/runner.py` ≥ 80 %.
- [ ] Manual smoke test on Hetzner VM: `POST /api/runs` with a real question; `journalctl -u novum -f` shows `llm_call_start` within 1 s; SSE client receives `QuestionAsked` + `PlanCreated`; `runs.stop_reason` is populated within the budget.
- [ ] Decision logged in `.github/memory-bank/logs/decisions-history.md`.
- [ ] Lesson logged in `.github/memory-bank/logs/lessons-learned.md` (integration-gap pattern across BRD-03/07/10/15).

---

## Open Questions — Resolved (v1.1)

All four open questions from v1.0 are resolved in this revision. Decisions are recorded here for traceability; the binding language lives in the BRD body.

1. **`ConnectionManager.publish`/`subscribe` ownership** — **Resolved: documented as a delta inside BRD-19 §4.9.** No BRD-10 amendment filed. Grounded in audit verification of `backend/app/sse/manager.py` which has no pub/sub today.
2. **Resume target FSM state after `user_cancelled`** — **Resolved: locked to `AgentState.SEARCHING`** in §4.5 step 5. Grounded in `docs/understanding-phase/data-flows-and-diagrams.md` FSM diagram lines 279–280: `ResumingAfterCancel -> Searching` and `ResumingAfterError -> Searching`.
3. **`WEB_CONCURRENCY` guard mechanism** — **Resolved: out of scope for BRD-19 runtime.** The authoritative mechanism is the systemd unit pin `--workers 1` documented in `docs/technical-phase/infrastructure.md` §Supervisor (line 108). The in-process env-var check in §9 is a defensive secondary guard only.
4. **Quiet-shutdown event vs `stop_reason = NULL`** — **Resolved: `stop_reason = NULL` + resumable + no startup sweep.** Verbatim from §10: "On shutdown, in-flight runs are cancelled cooperatively; their `stop_reason` remains `NULL`; they are resumable; no automatic startup sweep is performed." `data-flows-and-diagrams.md` does **not** cover process shutdown sequences explicitly (the diagrams focus on a single run's lifecycle, not the FastAPI process lifecycle), so the default is committed in writing here.

---

## Changelog

### v1.2 — 2026-05-26 (§4.6 amendment, F2 iter 2 reconciliation)

Resolves audit B-03 from [AUDIT-PLAN-IP-19](../audits/AUDIT-PLAN-IP-19.md) iter 1: the §4.6 `resume_run` code-block snippet contradicted the §4.6.1 narrative ("before appending the resume event") by showing `await_terminal` at the bottom.

- **§4.6 — `resume_run` snippet rewritten.** `await agent_runner.await_terminal(run_id, timeout=5.0)` is now shown as the **first statement** of `resume_run`, before the row lookup, matching §4.6.1 and protecting the cancel-row write from a race with the resume `UPDATE`. `await agent_runner.start(run_id)` remains the **last statement** after the final commit + refresh. No behavioural change vs the v1.1 narrative — only the snippet was misleading.

No other section is touched. All v1.1 approvals carry forward.

### v1.1 — 2026-05-26 (post-audit revision, F1 iter 2/3)

Addresses every finding in `docs/implementation-phase/audits/BRD-19-audit-v1.md` (score 8.10 → target ≥ 9.0).

- **F-01 [BLOCKER] closed** — §4.3 and §4.5 step 5 now use the real `AgentOrchestrator(state=..., emit=..., stopping_policy=...)` signature (verified against `backend/app/agent/orchestrator.py:49`). All wording implying an `initial_state` parameter or an `on_event` callback name has been removed. §11 DoD now explicitly states `orchestrator.py` is NOT modified. §10 lists "modifying `orchestrator.py`" as out of scope.
- **F-02 [MAJOR] closed** — New §4.6.1 "Cancel ↔ Resume Race Contract" picks option (a): `resume_run` calls `await agent_runner.await_terminal(run_id, timeout=5.0)` before `start`. Justification (vs (b) and (c)) included. New `await_terminal` method specified in §11 DoD. New US-19.6 covers the Gherkin acceptance criteria. New edge case E9 in §8. New NFR row for the 5 s grace.
- **F-03 [MAJOR] closed** — §4.8 reframed: the orchestrator's own top-level `except Exception` is the primary error path; the supervisor is reframed as a last-resort safety net for failures inside `_handle_error` itself. Mandatory `get_latest_event` guard added before any emission to prevent double-`AgentErrored`/`Stopped` rows. Test cases added in §6.1.
- **F-04 [MINOR] closed** — §4.3 step 3 sets `stopped_at` only when currently `NULL`, preserving the cancel-request timestamp. New US-19.7. New edge case E10. Test case added in §6.1.
- **F-05 [MINOR] closed** — §2 RF-02 row rewritten to acknowledge `cancel_run` as a secondary idempotent writer.
- **F-06 [MINOR] closed** — §7 NFR table now distinguishes create (N=0) from resume (bounded budgets for N ≤ 50 and N ≤ 500 events).
- **F-07 [MINOR] closed** — RF-04 row added to §2 traceability table.
- **F-08 [MINOR / light blocker] closed** — §10 now contains verbatim the requested commitment: "On shutdown, in-flight runs are cancelled cooperatively; their `stop_reason` remains `NULL`; they are resumable; no automatic startup sweep is performed." Also explicit "no automatic crash-recovery sweep at process startup" bullet.
- **F-09 [NIT] closed** — §6.1 adds a `start for deleted row (E1)` test case.
- **F-10 [NIT] closed** — §4.8 #3 tightened to clarify `is_running()` returns False **immediately** when the task completes (no internal poll or grace window).
- **Open questions section** rewritten to record the resolution of all four questions; raw open list deleted.
- **`data-flows-and-diagrams.md` coverage of the 4 open questions:**
  - Q1 (publish/subscribe ownership) — doc did not answer (it shows event flow in the abstract, not module ownership); committed default: delta inside BRD-19.
  - Q2 (resume target state) — **doc answered** at lines 279–280 (`ResumingAfterCancel -> Searching` and `ResumingAfterError -> Searching`); locked to `SEARCHING`.
  - Q3 (`WEB_CONCURRENCY`) — doc did not answer (infra concern); committed default: out of scope, see `infrastructure.md` line 108.
  - Q4 (shutdown event vs `stop_reason = NULL`) — doc did not answer (single-run lifecycle scope, not process lifecycle); committed default: `NULL` + resumable + no startup sweep.

### v1.0 — 2026-05-26

- Initial draft. Defined `AgentRunner` (`start` / `cancel` / `shutdown` / `is_running`), the emit callback, session lifecycle, state rehydration, RunService wiring diffs, lifespan hook, error flow, and the BRD-10 `publish`/`subscribe` extension.
