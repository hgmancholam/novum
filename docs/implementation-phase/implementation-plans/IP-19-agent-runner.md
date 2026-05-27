# Implementation Plan — IP-19: Agent Runner & Wiring

**Plan ID:** IP-19
**BRD:** [BRD-19-agent-runner.md](../brds/BRD-19-agent-runner.md) v1.2 (approved at 9.20/10 in v1.1, §4.6 amended in v1.2 to resolve audit B-03)
**Author:** Orchestrator
**Date:** 2026-05-26
**Status:** Draft — awaiting Auditor F2 review (iter 2/3)
**Target reviewer score (F4):** ≥ 9.0/10

### Iter 2 changelog (addresses [AUDIT-PLAN-IP-19](../audits/AUDIT-PLAN-IP-19.md) iter 1)

- **B-01** fixed in §T5: terminal `runs.stop_reason` / `stopped_at` write now happens through a **fresh** `AsyncSession` opened on demand inside the emit callback, so the runner's long-lived identity-map cannot mask a concurrent `cancel_run` write. The `WHERE stopped_at IS NULL` guard is enforced via SQL `UPDATE` (not ORM predicate). T8 #5 mandates two real sessions.
- **B-02** fixed in §3 + §T4 step 6: rehydration uses **direct assignment** to `state.current_state` via a new private helper `_apply_state(state, target)`; a **two-pass** scan pre-computes the set of `step_index` values immediately followed by a `RESUMED_AFTER_*` so that a preceding `STOPPED` is folded as a no-op. `transition_to` is **never** used during rehydration.
- **B-03** fixed by amending BRD-19 to v1.2 (§4.6 code block now places `await_terminal` **before** the resume event append, matching the existing §4.6.1 narrative). §T6 below mirrors the amended BRD verbatim and cites it.
- **B-04** fixed in new §T9.0: an **autouse** `pytest` fixture in `tests/conftest.py` monkeypatches `app.services.run_service.agent_runner` to a no-op stub for every existing test that does not explicitly opt-in via the `real_agent_runner` marker.
- **M-05** fixed in §T4: session lifecycle is now BRD-canonical — `async with async_session_maker() as session:` inside `_supervised_run`. The `_on_task_done` callback only mutates the in-memory registry (sync, no `aclose` scheduling).
- **M-06** fixed in §3: dispatch table rewritten to read SSE-shaped dicts via the real payload keys (`payload["sub_claims"]`, `payload["target_claim_id"]`, `payload["source_type"]`, etc.) verified against [`app/domain/events.py`](../../../backend/app/domain/events.py).
- **m-07** fixed in §T4: `cancel` is sync; spec now states registry reads are safe without the lock (single event-loop thread); only mutations occur under the lock.
- **m-09** fixed in §T3: `ConnectionManager.__init__` adds `self._subscribers: dict[UUID, list[asyncio.Queue[dict[str, Any]]]] = {}`.
- **m-10 / N-03** fixed in §4 E11: prose rewritten to match the real `RunService.cancel_run` behaviour (raises `RunAlreadyStoppedError` HTTP 400). T8 #17 asserts the 400.
- **m-11** fixed in §T4: `await_terminal` docstring spells out caller-cancel semantics for `asyncio.shield`.
- **n-12** fixed in §T8 #15: `FakeOrchestrator.__init__` stores `state` on `self.state` (mirrors the real class); test reads `fake.state`.
- **n-13** fixed in §T11: smoke-test delivery path documented as BRD-10's DB poll loop; queue publish is opportunistic and not validated end-to-end here.
- **#4/#5/#7/#8** time-sensitive tests now wrap waits in `async with asyncio.timeout(2.0):`; no wallclock waits > 0.2 s.

---

## 1. Scope recap

Bridge between BRD-03 (endpoints), BRD-07 (FSM), BRD-10 (SSE) and BRD-15 (resume): launch `AgentOrchestrator` as an `asyncio.Task` whenever a run is created or resumed, cancel it on user request, and clean up on shutdown.

The plan covers **only** files listed in BRD-19 §4.1. `backend/app/agent/orchestrator.py` is NOT modified (BRD-19 §10, §11 DoD).

### Audit v2 carry-overs to resolve in this plan

- **N-01** — `event_service.get_latest_event(run_id)` does NOT exist. Real API on [`event_service.py`](../../../backend/app/services/event_service.py): `get_events(run_id, after_step, limit)` (ASC) and `get_event(event_id)`. **Decision:** add a new `get_latest_event(run_id) -> Event | None` method on `EventService` (DESC, limit 1, ORM object — NOT the SSE-shaped dict). It is the minimum surface needed by the supervisor guard (BRD-19 §4.8 step 2) and is a non-breaking addition.
- **N-02** — `is_running()` docstring must spell out the invariant `run_id in self._tasks and not self._tasks[run_id].done()`.
- **N-03** — cancel-during-resume-wait: the second `POST /cancel` reaches `RunService.cancel_run`, which reads `run.stop_reason = USER_CANCELLED` (still set by the first cancel) and raises `RunAlreadyStoppedError` (HTTP 400) **before** ever touching `agent_runner.cancel`. The resume request is unaffected; once `await_terminal` returns it issues its own `start(R)`. UX: the user sees a clear *"run already cancelled"* message. Captured as edge case E11 and test T8 #17.

---

## 2. Task breakdown

Tasks are ordered by dependency. Each task lists files touched, RF coverage, effort estimate, and validation step.

### T1 — Add `RunAlreadyRunningError` exception

- **File:** [`backend/app/exceptions.py`](../../../backend/app/exceptions.py) (MODIFY)
- **Change:** add class mirroring the existing pattern.
  ```python
  class RunAlreadyRunningError(HTTPException):
      """A task for this run is already registered (RF-05 single-writer)."""

      def __init__(self, run_id: str) -> None:
          super().__init__(
              status_code=status.HTTP_409_CONFLICT,
              detail=f"Run {run_id} is already running",
          )


  class RunStillTerminatingError(HTTPException):
      """Prior task did not settle within the resume grace window (BRD-19 §4.6.1)."""

      def __init__(self, run_id: str, retry_after_seconds: int = 5) -> None:
          super().__init__(
              status_code=status.HTTP_409_CONFLICT,
              detail={
                  "code": "run_still_terminating",
                  "run_id": run_id,
                  "retry_after_seconds": retry_after_seconds,
              },
          )
  ```
- **RF coverage:** RF-05, RF-08.
- **Effort:** 10 LOC.
- **Validation:** `pyright --strict` + import in `test_exceptions.py` smoke test (new, 5 LOC).

### T2 — Add `EventService.get_latest_event`

- **File:** [`backend/app/services/event_service.py`](../../../backend/app/services/event_service.py) (MODIFY)
- **Change:** append a new method (closes N-01):
  ```python
  async def get_latest_event(self, run_id: UUID) -> Event | None:
      """Return the highest-step_index Event row for run_id (DESC limit 1).

      Used by the runner supervisor (BRD-19 §4.8) to decide whether
      the orchestrator already emitted a terminal event before raising.
      Returns the ORM object, not the SSE-shaped dict, so callers can
      compare `event.type == EventType.STOPPED.value` directly.
      """
      query = (
          select(Event)
          .where(Event.run_id == run_id)
          .order_by(Event.step_index.desc())
          .limit(1)
      )
      result = await self.db.execute(query)
      return result.scalar_one_or_none()
  ```
- **RF coverage:** RF-03 (read-only over append-only log).
- **Effort:** 12 LOC + 2 tests.
- **Validation:** new tests in `test_event_service.py` (empty run → None; multi-event run → highest step).

### T3 — Add `ConnectionManager.publish` / `subscribe` / `unsubscribe`

- **File:** [`backend/app/sse/manager.py`](../../../backend/app/sse/manager.py) (MODIFY — delta from BRD-10 v1.0, BRD-19 §4.9)
- **Change:** add a per-`run_id` list of bounded queues. The SSE stream (BRD-10) keeps its DB poll loop; queues are an opportunistic live-fanout.
  - **`__init__` addition (required for pyright-strict, closes m-09):**
    ```python
    self._subscribers: dict[UUID, list[asyncio.Queue[dict[str, Any]]]] = {}
    ```
  ```python
  _QUEUE_MAXSIZE = 1000  # per BRD-19 §9 risk-mitigation

  def subscribe(self, run_id: UUID) -> asyncio.Queue[dict[str, Any]]:
      q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
      self._subscribers.setdefault(run_id, []).append(q)
      return q

  def unsubscribe(self, run_id: UUID, queue: asyncio.Queue[dict[str, Any]]) -> None:
      subs = self._subscribers.get(run_id)
      if not subs:
          return
      try:
          subs.remove(queue)
      except ValueError:
          pass
      if not subs:
          del self._subscribers[run_id]

  async def publish(self, run_id: UUID, event: dict[str, Any]) -> None:
      """Best-effort fan-out. Full queues drop the oldest item + log."""
      for q in list(self._subscribers.get(run_id, [])):
          if q.full():
              try:
                  q.get_nowait()
              except asyncio.QueueEmpty:
                  pass
              logger.warning("sse_queue_overflow", run_id=str(run_id))
          q.put_nowait(event)
  ```
- **Reset hook:** extend existing `reset()` to also clear `_subscribers`.
- **RF coverage:** RF-08.
- **Effort:** ~35 LOC + 4 tests (subscribe/unsubscribe/publish-fanout/overflow).
- **Validation:** `test_sse_manager.py` extensions; the SSE stream (BRD-10 §4.2) does not need code changes for this plan — using the queues to short-circuit the poll loop is deferred to a future BRD-10 v1.1 task (BRD-19 §4.9 notes the DB poll fallback preserves correctness).

### T4 — Create `app/agent/runner.py` — `AgentRunner` class

- **File:** `backend/app/agent/runner.py` (NEW, ~180 LOC)
- **Public API** (BRD-19 §4.2 — signatures fixed):
  ```python
  class AgentRunner:
      def __init__(self) -> None: ...
      async def start(self, run_id: UUID) -> None: ...
      def cancel(self, run_id: UUID) -> bool: ...
      async def await_terminal(self, run_id: UUID, timeout: float = 5.0) -> None: ...
      async def shutdown(self) -> None: ...
      def is_running(self, run_id: UUID) -> bool: ...

  agent_runner = AgentRunner()
  ```
- **Internal state** (BRD-19 §4.2):
  - `_tasks: dict[UUID, asyncio.Task[None]]`
  - `_orchestrators: dict[UUID, AgentOrchestrator]`
  - `_lock: anyio.Lock`
- **`is_running` docstring** (closes N-02):
  ```python
  def is_running(self, run_id: UUID) -> bool:
      """True iff run_id is in self._tasks AND not self._tasks[run_id].done().

      Python invariant: `task.done()` flips True synchronously the moment
      the task body finishes, before `_on_task_done` fires. We therefore
      check `done()` rather than rely on the callback to have removed the
      entry — there is no internal poll or grace window.
      """
      task = self._tasks.get(run_id)
      return task is not None and not task.done()
  ```
- **`start(run_id)` algorithm** (BRD-19 §4.5):
  1. `async with self._lock:` — if `run_id in self._tasks and not self._tasks[run_id].done()`, raise `RunAlreadyRunningError`. Hand off to `_supervised_run` via `asyncio.create_task` and register both the task and a placeholder orchestrator (`None`) until the supervisor instantiates it. Reasoning: the session, replay and orchestrator construction all happen **inside** `_supervised_run` so the `async with async_session_maker()` block owns the session lifecycle end-to-end (closes M-05).
  2. `task.add_done_callback(self._on_task_done_factory(run_id))` — sync callback; only mutates `_tasks` and `_orchestrators` (no `aclose` scheduling). Lock-protected mutations happen inside a `loop.create_task(self._unregister(run_id))` coroutine.
- **`cancel(run_id)` (sync, closes m-07):**
  ```python
  def cancel(self, run_id: UUID) -> bool:
      """Cooperative cancel. Sync because the public API in BRD-19 §4.2 is sync.

      Registry reads (`self._tasks.get`, `self._orchestrators.get`) are safe
      without the lock: this runner is single-event-loop (RF-05 / uvicorn
      --workers 1) and all mutations of those dicts happen on the same loop.
      We never `task.cancel()` — the orchestrator must observe the
      cooperative flag and emit `Stopped(USER_CANCELLED)` cleanly.
      Idempotent: a second cancel is a no-op on the flag (already True).
      """
      orch = self._orchestrators.get(run_id)
      task = self._tasks.get(run_id)
      if orch is None or task is None or task.done():
          return False
      orch.cancel()  # flips `orchestrator._cancelled` (orchestrator.py:62)
      return True
  ```
- **`await_terminal(run_id, timeout=5.0)`** (BRD-19 §4.6.1, closes m-11):
  ```python
  async def await_terminal(self, run_id: UUID, timeout: float = 5.0) -> None:
      """Block until the prior task settles, with a bounded grace.

      Caller-cancel semantics: `asyncio.shield` ensures that if the HTTP
      request handler is cancelled (client disconnect), the inner task is
      NOT cancelled and continues to drain to a terminal event. The outer
      `CancelledError` propagates up to FastAPI as usual.
      """
      task = self._tasks.get(run_id)
      if task is None or task.done():
          return
      try:
          await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
      except asyncio.TimeoutError as exc:
          raise RunStillTerminatingError(str(run_id)) from exc
      except asyncio.CancelledError:
          pass  # expected — task was cooperatively cancelled
  ```
- **`shutdown()`** (BRD-19 §4.7): snapshot registry under lock; for each `run_id` call `cancel()`; then `await asyncio.wait_for(task, timeout=5.0)` swallowing `CancelledError` and `TimeoutError` with a `structlog.warning`. No `StoppedEvent` is written (BRD-19 §10).
- **`_supervised_run(run_id)`** (BRD-19 §4.4 + §4.8) — owns the session:
  ```python
  async def _supervised_run(self, run_id: UUID) -> None:
      async with async_session_maker() as session:
          event_service = EventService(session)
          run = await session.get(Run, run_id)
          if run is None:
              raise RunNotFoundError(str(run_id))
          state = RunState(
              run_id=run_id,
              question=run.question,
              user_context=run.user_context,
              confidence_threshold=run.confidence_threshold,
              output_format=run.output_format,
          )
          events = await event_service.get_events(run_id, after_step=0, limit=10_000)
          _fold_events(state, events)            # §3 dispatch table
          emit = self._make_emit(run_id, event_service)
          orchestrator = AgentOrchestrator(state, emit, stopping_policy=None)
          async with self._lock:
              self._orchestrators[run_id] = orchestrator
          try:
              await orchestrator.run()
          except asyncio.CancelledError:
              raise
          except Exception as exc:                # last-resort net — BRD-19 §4.8
              await self._supervisor_last_resort(run_id, exc)
  ```
  The `try/except` envelope handles the cases listed in BRD-19 §4.8. `_supervisor_last_resort` opens its **own** fresh session (the in-flight one may be poisoned), calls `EventService.get_latest_event(run_id)` (T2), and appends `AgentErroredEvent + StoppedEvent(ERRORED)` only when the latest event is not already a `Stopped`.
- **RF coverage:** RF-01, RF-05, RF-08, RF-11, RF-14.
- **Effort:** ~200 LOC + ~250 LOC tests.
- **Validation:** `test_agent_runner.py` (T8).

### T5 — Wire the `emit` callback (closes B-01)

- **File:** `backend/app/agent/runner.py` (inside T4)
- **Contract** (BRD-19 §4.3 — three responsibilities in order). The terminal-state branch opens a **fresh** session and uses a SQL `UPDATE` with `WHERE stopped_at IS NULL` so the guard is enforced by the database, not by the runner's long-lived identity-map. This is what makes US-19.7 / E10 safe under concurrent `cancel_run` writes happening in a different session (closes audit B-01):
  ```python
  def _make_emit(self, run_id: UUID, event_service: EventService) -> EventCallback:
      async def emit(event: BaseEvent) -> None:
          db_event = await event_service.append_event(run_id, event)
          sse_payload = {
              "id": str(db_event.id),
              "run_id": str(db_event.run_id),
              "step_index": db_event.step_index,
              "parent_event_id": (
                  str(db_event.parent_event_id) if db_event.parent_event_id else None
              ),
              "type": db_event.type,
              "created_at": db_event.created_at.isoformat(),
              **db_event.payload,
          }
          try:
              await connection_manager.publish(run_id, sse_payload)
          except Exception:  # noqa: BLE001 — RF-08 mandates non-fatal publish
              logger.exception("sse_publish_failed", run_id=str(run_id))
          if event.type == EventType.STOPPED:
              stopped = cast(StoppedEvent, event)
              await self._write_terminal_row(run_id, stopped.stop_reason.value)
      return emit

  async def _write_terminal_row(self, run_id: UUID, stop_reason: str) -> None:
      async with async_session_maker() as session:
          now = datetime.now(UTC)
          # SQL-side guard: only set stopped_at when it is NULL — this is
          # what protects the T0 set synchronously by RunService.cancel_run
          # in a different session (closes audit B-01).
          await session.execute(
              update(Run)
              .where(Run.id == run_id)
              .values(
                  stop_reason=stop_reason,
                  stopped_at=case(
                      (Run.stopped_at.is_(None), now),
                      else_=Run.stopped_at,
                  ),
              )
          )
          await session.commit()
  ```
- **Notes:**
  - The long-lived per-task session (T4) is used **only** for `event_service.append_event` and the initial `get_events` replay.
  - `_write_terminal_row` is the single point that mutates `runs.stop_reason` / `stopped_at` from the runner side. It is idempotent vs the synchronous write in `RunService.cancel_run` (same `USER_CANCELLED` value).
  - `case` + `update` imports come from `sqlalchemy`.
- **RF coverage:** RF-02, RF-04, RF-08.
- **Effort:** ~40 LOC.

### T6 — Wire `RunService` (mirrors BRD-19 v1.2 §4.6)

- **File:** [`backend/app/services/run_service.py`](../../../backend/app/services/run_service.py) (MODIFY)
- **Companion change:** BRD-19 is amended to v1.2 — §4.6 `resume_run` code block places `await_terminal` **before** the resume-event append, aligning the code block with the existing §4.6.1 narrative ("before appending the resume event"). The plan below mirrors the amended BRD verbatim (closes audit B-03).
- **Changes** (BRD-19 v1.2 §4.6):
  - `create_run`: after `await self.db.refresh(run)`, add `await agent_runner.start(run.id)`.
  - `cancel_run`: after `connection_manager.cancel(run_id)`, add `agent_runner.cancel(run_id)`.
  - `resume_run`: **insert at the top of the method**, before `await self.db.get(Run, run_id)`:
    ```python
    await agent_runner.await_terminal(run_id, timeout=5.0)
    ```
    The existing body (row lookup, `_RESUMABLE` validation, anchor lookup, atomic resume-event append, `stop_reason = None`, commit, refresh) runs unchanged. After the final `await self.db.refresh(run)`, add:
    ```python
    await agent_runner.start(run_id)
    return RunResponse.model_validate(run)
    ```
  - The pre-flight `await_terminal` is the **only** valid placement: it lets the prior task drain to its terminal write **before** the resume `UPDATE` clears `stop_reason`. Otherwise the prior task's `_write_terminal_row` would race with the resume-event commit and could overwrite the freshly cleared `stop_reason` (the exact failure mode of B-01 from the v1 audit).
- **Import** `agent_runner` at the top of the module.
- **RF coverage:** RF-05, RF-08, RF-11.
- **Effort:** ~10 LOC, 3 call sites.
- **Validation:** extended `test_run_service.py` asserting call order (`await_terminal` → row fetch → anchor lookup → append + commit → `start`).

### T7 — Wire FastAPI `lifespan`

- **File:** [`backend/app/main.py`](../../../backend/app/main.py) (MODIFY)
- **Change** (BRD-19 §4.7):
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
      logger.info("starting_novum", host=settings.host, port=settings.port)
      yield
      await agent_runner.shutdown()  # NEW
      await engine.dispose()
      logger.info("shutdown_complete")
  ```
- **Defensive single-worker check** (BRD-19 §9, §10): on startup, if `os.environ.get("WEB_CONCURRENCY", "1") != "1"`, log `logger.error("multiple_workers_detected", web_concurrency=...)`. Do NOT raise — production uses systemd `--workers 1` (authoritative). Logging only.
- **RF coverage:** RF-05.
- **Effort:** ~6 LOC.
- **Validation:** integration test via `TestClient` lifespan (`test_main.py` extension, optional).

### T8 — Tests — `tests/test_agent_runner.py`

- **File:** `backend/tests/test_agent_runner.py` (NEW)
- **Fixtures:**
  - `FakeOrchestrator` — subclass of `AgentOrchestrator` (or a duck-typed stand-in) with a scripted `run()` method that emits a configurable sequence and respects `self._cancelled`. Lives in `tests/conftest.py` to be reusable. **Capture rule (closes n-12):** `FakeOrchestrator.__init__(state, emit, stopping_policy)` stores `self.state = state` (matching the real class's `self.state` attribute); tests read the rehydrated state via `fake.state` after the run completes.
  - `monkeypatch.setattr(app.agent.runner, "AgentOrchestrator", FakeOrchestrator)` per-test.
  - `pg_session` fixture from `tests/conftest.py` (existing).
- **Time discipline (applies to all scenarios):** every `await` that may block on the orchestrator wraps the await in `async with asyncio.timeout(2.0):` (or 5.0 for shutdown). **No wallclock waits exceed 0.2 s.** `FakeOrchestrator` uses `await asyncio.sleep(...)` for the few cases that need to simulate work, with the sleep durations passed as parameters so tests can keep them tiny.
- **Scenarios** (one test function each — maps 1:1 to BRD-19 §6.1):
  1. `test_start_happy_path` — scripted `[QuestionAsked, PlanCreated, Stopped(JUDGE_CONFIRMED)]`, assert 3 rows in `events`, `runs.stop_reason == "judge_confirmed"`, `runs.stopped_at IS NOT NULL`, registry empty.
  2. `test_start_single_writer_raises` — second `start(R)` raises `RunAlreadyRunningError`.
  3. `test_start_for_deleted_row_raises` — delete row between create and `start` → `RunNotFoundError`, no task registered. (E1)
  4. `test_cancel_emits_user_cancelled` — `cancel(R)`, FakeOrchestrator observes flag and emits `Stopped(USER_CANCELLED)` within < 2 s; row updated; registry cleared.
  5. `test_cancel_preserves_stopped_at` — **two real sessions required** to exercise B-01. Setup: open session `S_http`, call `RunService(S_http).cancel_run(R)` → row has `stop_reason=USER_CANCELLED`, `stopped_at=T0`. `FakeOrchestrator` (running in its own task with its own session) sleeps 0.15 s then emits `Stopped(USER_CANCELLED)`; the runner's `_write_terminal_row` opens its **own** fresh session for the UPDATE. Assert via a third independent session that `runs.stopped_at == T0` (not `T0 + 0.15s`) and `runs.stop_reason == USER_CANCELLED`. (US-19.7 / E10 / closes B-01)
  6. `test_await_terminal_returns_immediately_when_no_task` — `await_terminal(unknown_id)` returns instantly.
  7. `test_resume_after_cancel_awaits_prior_task` — start R, request cancel, immediately call `RunService.resume_run`; assert `await_terminal` returned within 5 s; assert second `start(R)` succeeded; no `RunAlreadyRunningError`. (US-19.6)
  8. `test_resume_timeout_raises_run_still_terminating` — FakeOrchestrator ignores `_cancelled` for 10 s; `await_terminal(timeout=0.5)` raises `RunStillTerminatingError`. (US-19.6 timeout branch)
  9. `test_shutdown_cancels_all_tasks` — register 3 long-running fakes; `await agent_runner.shutdown()` returns within ~5 s; all tasks done.
  10. `test_shutdown_leaves_stop_reason_null` — verify `runs.stop_reason IS NULL` after shutdown; verify run is in the `_RESUMABLE` set.
  11. `test_error_propagation_normal_path` — FakeOrchestrator emits `AgentErrored + Stopped(ERRORED)` internally → supervisor sees no escape → no duplicate rows.
  12. `test_supervisor_emits_when_no_prior_stop` — FakeOrchestrator raises `RuntimeError("boom")` BEFORE emitting `Stopped` → supervisor uses fresh session, `get_latest_event` returns non-Stopped → supervisor appends `AgentErrored + Stopped(ERRORED)`. (F-03)
  13. `test_supervisor_skips_when_prior_stop_exists` — pre-seed `Stopped(ERRORED)` event row → FakeOrchestrator raises bare `RuntimeError` → supervisor `get_latest_event` returns `Stopped` → no new events appended; `runs.stop_reason` idempotent set if NULL. (F-03)
  14. `test_publish_failure_is_non_fatal` — monkeypatch `connection_manager.publish` to `raise RuntimeError`; run completes; all events persisted.
  15. `test_rehydration_folds_prior_events` — pre-seed `[QuestionAsked, PlanCreated, EvidenceAdded, EvidenceAdded, AgentErrored, Stopped(ERRORED), ResumedAfterError]`; capture `fake.state` (see fixture above); assert `len(state.evidence) == 2`, `len(state.sub_claims) > 0`, `state.current_state == AgentState.SEARCHING`, `state.stop_reason is None` (resume cleared it), AND no `ValueError` raised mid-fold (covers B-02 — the illegal `INIT → CRITIQUING` and `STOPPED → SEARCHING` jumps must be silent under `_apply_state`).
  16. `test_done_callback_idempotent_cleanup` — orchestrator emits `Stopped` then task finishes; assert registry entry removed exactly once.
  17. `test_cancel_during_resume_wait_returns_400` (E11, closes N-03) — start R; issue first cancel via `RunService.cancel_run` (sets `stop_reason=USER_CANCELLED`); from a **second** session and concurrent task, start `RunService.resume_run(R)` which awaits `await_terminal`; while it waits, issue a second cancel via a **third** session and assert `RunAlreadyStoppedError` (HTTP 400) is raised. The prior task settles; `resume_run` proceeds; no extra event rows are appended for the rejected cancel.
- **Coverage target:** ≥ 80% on `app/agent/runner.py` (BRD-19 §11). Practical target: ≥ 90% given the small surface.
- **Effort:** ~350 LOC test code.

### T9 — Tests — extend `tests/test_run_service.py`

#### T9.0 — Autouse no-op runner fixture in `tests/conftest.py` (closes B-04)

- **File:** [`backend/tests/conftest.py`](../../../backend/tests/conftest.py) (MODIFY)
- **Change:**
  ```python
  @pytest.fixture(autouse=True)
  def _noop_agent_runner(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
      """Replace the global `agent_runner` with a no-op stub for every test.

      Without this, every existing `RunService.create_run` call would spawn
      a real `AgentOrchestrator` task using the real LLM and search adapters
      — making the entire pre-IP-19 suite flaky or outright failing.

      Tests that need the real runner opt in with the `real_agent_runner`
      marker (`@pytest.mark.real_agent_runner`).
      """
      if "real_agent_runner" in request.keywords:
          return

      class _NoopRunner:
          async def start(self, run_id: UUID) -> None: ...
          def cancel(self, run_id: UUID) -> bool: return False
          async def await_terminal(self, run_id: UUID, timeout: float = 5.0) -> None: ...
          async def shutdown(self) -> None: ...
          def is_running(self, run_id: UUID) -> bool: return False

      stub = _NoopRunner()
      monkeypatch.setattr("app.services.run_service.agent_runner", stub)
      monkeypatch.setattr("app.main.agent_runner", stub)
  ```
- **Marker registration:** add to [`backend/pyproject.toml`](../../../backend/pyproject.toml) `[tool.pytest.ini_options].markers`: `"real_agent_runner: opt in to the real AgentRunner (default is a no-op stub)"`.
- **Effort:** ~25 LOC.
- **Validation:** running the existing test suite before T6/T7 land verifies the fixture is harmless (no behavioural change); after T6/T7 land, the existing tests stay green because they never see a real task.

#### T9.1 — New `RunService` tests

#### T9.1 — New `RunService` tests

- **File:** [`backend/tests/test_run_service.py`](../../../backend/tests/test_run_service.py) (EXTEND)
- **Strategy:** these tests use `@pytest.mark.real_agent_runner` to bypass the autouse stub from T9.0, then monkeypatch `app.services.run_service.agent_runner` with a per-test fake that records call order.
- **New tests:**
  - `test_create_run_invokes_runner_start` — exactly one `start(run.id)` call after the row commit.
  - `test_cancel_run_invokes_runner_cancel` — exactly one `cancel(run.id)` call.
  - `test_resume_run_awaits_terminal_then_starts` — call order is `await_terminal` (called **before** the row lookup) → `_find_resume_anchor` → `start`.
  - `test_resume_run_timeout_propagates_409` — fake `await_terminal` raises `RunStillTerminatingError`; `RunService.resume_run` re-raises (no swallow); no `ResumedAfter*` event is appended (transactional rollback).
- **Effort:** ~80 LOC.

### T10 — Tests — extend `tests/test_routes_runs.py`

- **File:** [`backend/tests/test_routes_runs.py`](../../../backend/tests/test_routes_runs.py) (EXTEND)
- **Strategy:** TestClient + dependency-override the orchestrator to a FakeOrchestrator that emits a known sequence; capture `connection_manager.publish` calls.
- **New tests:**
  - `test_post_runs_kicks_off_runner_and_streams_events` — `POST /api/runs` returns 201; poll the `events` table; verify the FakeOrchestrator's scripted sequence is present in DB and was published via `connection_manager.publish` in order.
  - `test_post_cancel_emits_stopped_within_2s` — `POST /api/runs/{id}/cancel` followed by polling shows a `Stopped(user_cancelled)` event within 2 s.
  - `test_post_resume_after_error_replays_then_continues` — pre-seed an errored run with N events; `POST /resume`; verify N+1 events present after FakeOrchestrator emits `Stopped(JUDGE_CONFIRMED)`.
- **Effort:** ~120 LOC.

### T11 — Manual smoke test (BRD-19 §11 DoD)

- After CI green, deploy to Hetzner VM (`novum-prod`), `sudo systemctl restart novum`, then:
  1. `POST https://novum-prod.duckdns.org/api/runs` with a real question.
  2. `sudo journalctl -u novum -f` must show `llm_call_start` within 1 s.
  3. SSE client must receive `QuestionAsked` + `PlanCreated`.
  4. `runs.stop_reason` populated within the per-run budget.
- **Delivery-path note (closes n-13):** the SSE client receives events via BRD-10's existing 500 ms DB poll loop, not via the new `ConnectionManager.publish` queues. T3's publish path is an opportunistic live-fanout for a future BRD-10 v1.1; this smoke test does not validate it end-to-end. Validating the publish path is covered by unit test T8 #1 (asserts `connection_manager.publish` is called per event).

---

## 3. Rehydration dispatch (folder reference for T4 step 6)

### 3.1 Why direct assignment, not `transition_to`

The public `RunState.transition_to(new_state)` validates against the FSM table at [`states.py:24`](../../../backend/app/agent/states.py) and **raises `ValueError`** on illegal transitions. The rehydration walk hits two illegal transitions on canonical sequences (closes audit B-02):

- `INIT → CRITIQUING` (after the `PLAN_CREATED` row) — not in `TRANSITIONS[INIT]`.
- `STOPPED → SEARCHING` (after a `RESUMED_AFTER_*` row when a prior `STOPPED` was folded) — `TRANSITIONS[STOPPED] = ∅`.

Rehydration therefore **bypasses** `transition_to` and assigns `state.current_state` directly via a module-private helper:

```python
def _apply_state(state: RunState, target: AgentState) -> None:
    """Direct assignment used ONLY during rehydration. Skips FSM validation.

    The fold reconstructs a historical state from the event log; the log
    is the source of truth and may legally encode jumps that the live FSM
    forbids (e.g. INIT → CRITIQUING when the planner ran in one tick).
    """
    state.current_state = target
```

### 3.2 Two-pass fold for STOPPED ↔ RESUMED look-ahead

The fold walks `events: list[dict]` (SSE-shaped, see [`event_service.py`](../../../backend/app/services/event_service.py) `get_events` return). A pre-scan computes the set of `step_index` values that are *immediately followed by* a `RESUMED_AFTER_*` event:

```python
def _stopped_followed_by_resume(events: list[dict[str, Any]]) -> set[int]:
    resumed_types = {EventType.RESUMED_AFTER_ERROR.value, EventType.RESUMED_AFTER_CANCEL.value}
    skip: set[int] = set()
    for i, e in enumerate(events):
        if e["type"] == EventType.STOPPED.value and i + 1 < len(events) \
           and events[i + 1]["type"] in resumed_types:
            skip.add(e["step_index"])
    return skip
```

The main fold consults `skip` before applying a `STOPPED` row. This is the explicit guard required by audit B-02; pure dispatch order is **not** sufficient on its own.

### 3.3 Dispatch table (dict-based, real payload keys)

Event objects are SSE-shaped `dict[str, Any]` — envelope keys merged with the JSONB payload. Field names match [`app/domain/events.py`](../../../backend/app/domain/events.py) verbatim.

| `event["type"]` | Fold action on `RunState` |
|---|---|
| `QUESTION_ASKED` | no-op (state already constructed from `runs` row) |
| `PLAN_CREATED` | `state.sub_claims = [SubClaim(**c) for c in event["sub_claims"]]`; `_apply_state(state, AgentState.CRITIQUING)` |
| `PLAN_CRITIQUED` | no-op (informational) |
| `PLAN_REVISED` | `state.sub_claims = [SubClaim(**c) for c in event["new_sub_claims"]]`; `state.plan_revision_count += 1` |
| `EVIDENCE_ADDED` | `state.add_evidence(EvidenceItem(claim_id=event["target_claim_id"], source_url=event["source_url"], source_title=event["source_title"], text=event["extracted_text"], polarity=event["polarity"], confidence=event["confidence"]))` |
| `CLAIM_COVERED` | `state.mark_claim_covered(event["claim_id"])` |
| `CLAIM_UNCOVERABLE` | `state.mark_claim_uncoverable(event["claim_id"])` |
| `SOURCE_FAILED` | append `event["source_type"]` to `state.failed_sources` |
| `CONTRADICTION_DETECTED` | append `ContradictionDetectedEvent.model_validate(event)` to `state.contradictions` |
| `TOOL_CALLED` | `state.search_count += 1` if `event["source_type"]` indicates a search (any `SourceType` value other than internal LLM calls) |
| `JUDGE_RULED` | `state.last_judge_confidence = event["judge_confidence"]`; `state.last_structural_confidence = event["structural_confidence"]`; `state.judge_attempts += 1` |
| `AMBIGUITY_DETECTED` | `state.has_ambiguity = True` |
| `AGENT_ERRORED` | no-op (a trailing `RESUMED_AFTER_ERROR` overrides; otherwise the run is terminal and we don't relaunch) |
| `STOPPED` | **two-pass guarded.** If `event["step_index"] in skip` → no-op (a resume follows). Else `state.stop_reason = StopReason(event["stop_reason"])` and `_apply_state(state, AgentState.STOPPED)`. |
| `RESUMED_AFTER_ERROR` / `RESUMED_AFTER_CANCEL` | `state.stop_reason = None`; `_apply_state(state, AgentState.SEARCHING)` (BRD-19 §4.5 lock, data-flows-and-diagrams.md lines 279–280) |
| `CONFIDENCE_MISMATCH` / `USER_CONTEXT_CHALLENGED` / `CONTRADICTION_RESOLVED` | no-op (informational; coverage already updated above) |

Unknown `event["type"]` values are skipped (RF-04 forward-compat).

### 3.4 Folder signature

```python
def _fold_events(state: RunState, events: list[dict[str, Any]]) -> None:
    skip = _stopped_followed_by_resume(events)
    for e in events:
        # one `match` per event type; uses the table above.
        ...
```

---

## 4. New edge cases added by this plan

| # | Scenario | Behaviour |
|---|---|---|
| E11 | Cancel issued while `RunService.resume_run` is awaiting `await_terminal` | The second `POST /cancel` enters `RunService.cancel_run`, reads `run.stop_reason = USER_CANCELLED` (still set by the first cancel), and raises `RunAlreadyStoppedError` → **HTTP 400** with the existing "already stopped" detail. The resume request is unaffected and proceeds normally once `await_terminal` returns. The UX message tells the user the run is already cancelled; if they want to abort the resume itself they cancel again **after** the new task starts. Closes audit N-03 / m-10. Test T8 #17 asserts the 400. |

---

## 5. RF coverage matrix

| RF | Tasks |
|---|---|
| RF-01 | T4, T5, T8 |
| RF-02 | T5, T6, T8 |
| RF-03 | T2, T4, T8 |
| RF-04 | T4 (dispatch table), T8 |
| RF-05 | T1, T4 (single-writer), T6, T7, T8 |
| RF-08 | T1, T3, T5, T6, T8, T10 |
| RF-11 | T4 (rehydration), T6, T8, T10 |
| RF-14 | T4 (orchestrator inheritance) |

---

## 6. Dependency order

```
T1 ─┐
T2 ─┼─► T4 ─► T5 (inside T4) ─► T6 ─► T7 ─► T8 ─► T9 ─► T10 ─► T11
T3 ─┘
```

T1, T2, T3 can be done in parallel. T4 needs T1+T2+T3. T6 needs T4. T7 needs T4. T8 needs T4+T5. T9 needs T6. T10 needs T6+T7.

---

## 7. Effort estimate

| Task | LOC (impl) | LOC (test) |
|---|---|---|
| T1 | 25 | 5 |
| T2 | 12 | 30 |
| T3 | 35 | 80 |
| T4+T5 | 230 | — |
| T6 | 10 | — |
| T7 | 6 | 20 |
| T8 | — | 360 |
| T9.0 (autouse fixture) | 25 | — |
| T9.1 | — | 80 |
| T10 | — | 120 |
| **Total** | **~345** | **~695** |

Still well within copilot-instructions §6 budget (target ≤ 600 LOC impl for non-RF work; this IS RF work and adds the missing runtime bridge).

---

## 8. Validation gates

- `cd backend; uv run ruff check` clean.
- `cd backend; uv run pyright` strict clean on `app/agent/runner.py`, `app/exceptions.py`, `app/services/run_service.py`, `app/sse/manager.py`, `app/main.py`.
- `cd backend; uv run pytest -q` all tests pass.
- `cd backend; uv run pytest --cov=app/agent/runner --cov-fail-under=80` ≥ 80%.
- Manual smoke test on Hetzner VM (T11) — observe `llm_call_start` in `journalctl -u novum -f`.
- No changes to `backend/app/agent/orchestrator.py` (DoD).

---

## 9. Risks and mitigations specific to this plan

| Risk | Mitigation |
|---|---|
| Long-lived per-task session may stale-read `runs` row written by another session | **Fix (B-01):** terminal-row write uses a fresh short-lived session + SQL `UPDATE ... WHERE stopped_at IS NULL`. Only `event_service.append_event` and the replay reuse the long-lived session. Test T8 #5 enforces this. |
| `asyncio.shield(task)` semantics — caller-cancel propagates while task continues | Documented in `await_terminal` docstring (m-11). Test T8 #8 covers the timeout branch; behaviour-on-caller-cancel is left implicit because no FastAPI route currently disconnects mid-await. |
| Rehydration mismatch (folded `RunState` disagrees with reality) | `_apply_state` bypasses the FSM validator only during rehydration (§3.1). Two-pass guard (§3.2) protects against `STOPPED → SEARCHING` reaching the live FSM. Test T8 #15 captures the rehydrated state and snapshots key fields. Resume always re-enters at `SEARCHING` (BRD-19 §4.5 lock). |
| Test flakiness on time-based assertions (cancel < 2 s, await_terminal < 5 s) | Use `async with asyncio.timeout(...)` instead of `time.time()` deltas in tests; FakeOrchestrator uses `asyncio.sleep` so we can pass tiny durations (§T8 prelude). No wallclock waits > 0.2 s. |
| Existing test suite breaks when `RunService.create_run` spawns a real task | **Fix (B-04):** autouse `_noop_agent_runner` fixture in `tests/conftest.py` (§T9.0). Tests that need the real runner opt in via `@pytest.mark.real_agent_runner`. |
| Pre-IP-19 BRD-19 §4.6 code block and §4.6.1 narrative disagreed on `await_terminal` placement | **Fix (B-03):** BRD-19 v1.2 amendment moves the code block snippet to mirror §4.6.1 ("before appending the resume event"). Plan §T6 cites the amendment. |

---

## 10. Definition of done (mirrors BRD-19 §11, all items must be ticked before F4 review)

- [ ] T1–T7 implemented; T8–T10 written and green.
- [ ] `pyright --strict` clean.
- [ ] `ruff check` and `ruff format --check` clean.
- [ ] Coverage on `app/agent/runner.py` ≥ 80%.
- [ ] `backend/app/agent/orchestrator.py` unchanged (verify via `git diff`).
- [ ] Manual smoke test on Hetzner VM passes (T11).
- [ ] Memory bank updated: `decisions-history.md` (D-035 or next) + `lessons-learned.md` (one entry for the integration-bridge pattern).
- [ ] Audit findings N-01, N-02, N-03 explicitly closed (T2, T4 docstring, T8 #17).
