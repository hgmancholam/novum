# Audit Report — IP-19 (Agent Runner & Wiring)

**Artifact:** [IP-19-agent-runner.md](../implementation-plans/IP-19-agent-runner.md)
**Parent BRD:** [BRD-19 v1.2](../brds/BRD-19-agent-runner.md) (v1.1 approved at 9.20; §4.6 amended in v1.2 to close B-03)
**Phase:** F2 — PLAN (implementation-plan audit sub-loop)
**Auditor:** Auditor Agent
**Latest Iteration:** 2 of 3
**Latest Date:** 2026-05-26
**Latest Score:** **9.40 / 10** (threshold ≥ 9.00) — PASS
**Latest Verdict:** ✅ **APPROVED**

**Iteration Log:**

| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-26 | 7.55 | ⚠️ RETURN TO ORCHESTRATOR |
| 2 | 2026-05-26 | 9.40 | ✅ APPROVED |

---

## Iter 1 — 2026-05-26

---

## 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| BRD traceability (every task ↔ BRD §) | 9.5 / 10 | 15 % | 1.425 |
| Acceptance-criteria coverage (each US-19.x has a test) | 9.0 / 10 | 20 % | 1.800 |
| **Blind-Path Absence** | **5.5 / 10** | 30 % | 1.650 |
| Test rigour (deterministic, isolated, complete) | 8.0 / 10 | 20 % | 1.600 |
| Non-breaking guarantees (existing tests, additive surfaces) | 6.5 / 10 | 15 % | 0.975 |
| **TOTAL** | | | **7.55 / 10** |

Sub-scores per user request:
- **BRD-trace:** 9.5 / 10 — every task references the right §.
- **Blind-path:** 5.5 / 10 — three BLOCKER and three MAJOR gaps below.
- **Test-rigour:** 8.0 / 10 — 17 scenarios, but #15 injection mechanism and time-based scenarios #4/#5/#7/#8 underspecified.
- **Non-breaking:** 6.5 / 10 — existing `test_run_service.py` will break (see B-04).

---

## 2. Closure status of BRD-19 audit-v2 carry-overs

| ID | v2 origin | Closure in plan | Status |
|---|---|---|---|
| **N-01** | `event_service.get_latest_event` does not exist | T2 adds it: SQL is `select(Event).where(Event.run_id == run_id).order_by(Event.step_index.desc()).limit(1)` returning ORM `Event | None`. Matches the supervisor's `event.type == EventType.STOPPED.value` comparison in T4 step §4.8 #2. SQL is correct (DESC + LIMIT 1). Non-breaking addition (new method on existing service). | ✅ **CLOSED** |
| **N-02** | `is_running()` invariant ambiguous | T4 docstring is verbatim: `"True iff run_id is in self._tasks AND not self._tasks[run_id].done()"` and implementation `return task is not None and not task.done()`. Spells out the Python `task.done()` invariant. | ✅ **CLOSED** |
| **N-03** | Cancel-during-resume-wait window | Plan §4 E11 documents it; test T8 #17 covers it. **However:** the described behaviour ("second cancel is forwarded to orchestrator, idempotent") does **not** match `RunService.cancel_run` (lines 134-149) — `cancel_run` reads `run.stop_reason is not None` and raises `RunAlreadyStoppedError` (HTTP 400) **before** ever calling `agent_runner.cancel`. With the plan's chosen ordering (T6: `await_terminal` at the TOP, before the `stop_reason = None` commit), the row still has `stop_reason = USER_CANCELLED` when the second cancel arrives → cancel_run returns 400, not a no-op. The UX is still acceptable ("run already cancelled"), but the plan's prose is inaccurate. | ⚠️ **PARTIAL** (see M-04) |

---

## 3. Verification of cited code (per user prompt §1.4)

| Plan citation | Real code | Verdict |
|---|---|---|
| [`orchestrator.py:49`](../../../backend/app/agent/orchestrator.py) — `__init__(state, emit, stopping_policy=None)` | Confirmed: `class AgentOrchestrator: def __init__(self, state: RunState, emit: EventCallback, stopping_policy: StoppingPolicy \| None = None)` | ✅ |
| `orchestrator.py:107-111` — top-level `except Exception → _handle_error` | Confirmed at lines 105-111 (`except Exception as exc: return await self._handle_error(exc)`). `_handle_error` emits `AgentErroredEvent` then `_stop(StopReason.ERRORED)` which emits `StoppedEvent`. | ✅ |
| `AgentState.SEARCHING` reachable from `CRITIQUING` (for the RESUMED_* fold) | `TRANSITIONS[CRITIQUING] = {SEARCHING, REVISING, STOPPED, ERRORED}` — `CRITIQUING → SEARCHING` valid. **But:** `TRANSITIONS[INIT] = {PLANNING, STOPPED, ERRORED}` — `INIT → CRITIQUING` (PLAN_CREATED row) is **INVALID**. And `TRANSITIONS[STOPPED] = TRANSITIONS[ERRORED] = set()` — any post-terminal fold via `transition_to` will raise `ValueError`. | ⚠️ See B-02 |
| `RunState` fields used by dispatch | All referenced fields exist (`sub_claims`, `plan_revision_count`, `evidence` via `add_evidence`, `covered_claims` via `mark_claim_covered`, `uncoverable_claims`, `contradictions`, `failed_sources`, `search_count`, `last_judge_confidence`, `last_structural_confidence`, `judge_attempts`, `has_ambiguity`, `stop_reason`, `current_state`). | ✅ |
| `RunService.create_run`, `cancel_run`, `resume_run` line up with T6 | Signatures match. `cancel_run` already calls `connection_manager.cancel`; `resume_run` already commits before returning. | ✅ (with order caveat — see B-03) |
| `EventService.append_event` / `get_events` shape | `append_event(run_id, event, parent_event_id=None, *, commit=True) -> Event` ORM row. `get_events(run_id, after_step=0, limit=100) -> list[dict]` (SSE-shaped, ASC). Plan T4 step 5 says `get_events(run_id, after_step=0, limit=10_000)` — call exists with default `commit=True`; **but** `get_events` returns SSE-shaped dicts, not ORM rows; the dispatch table's `event.sub_claims` / `event.claim_id` / `event.tool` access assumes pydantic-event objects. Folding must rehydrate the dicts back into BaseEvent subclasses or read by key. | ⚠️ See B-01 |
| `sse/manager.py` publish/subscribe is purely additive | Current `ConnectionManager.__init__` initializes `_connections` and `_cancelled` only. Plan T3 references `self._subscribers.setdefault(...)` without explicitly adding `self._subscribers: dict[...] = {}` to `__init__`. The `reset()` extension is called out; the field declaration is not. | ⚠️ See m-06 |
| `exceptions.py` pattern | Matches — `class RunAlreadyRunningError(HTTPException)` follows the existing module style; `RunStillTerminatingError` mirrors `RunStillRunningError`. | ✅ |
| `database.py::async_session_maker` | Exists with `expire_on_commit=False`. | ✅ (but see B-01) |
| `main.py::lifespan` shape | Exact match — `yield` then `await engine.dispose()`. Plan insertion is valid. | ✅ |
| `EventType.STOPPED`, `StoppedEvent(stop_reason, ...)` | `StoppedEvent.type: Literal[EventType.STOPPED] = EventType.STOPPED`; `stop_reason: StopReason` field present. Plan T5 reads `stopped.stop_reason.value` — correct (StopReason is StrEnum). | ✅ |

---

## 4. Blind-Path Findings

Severity legend: `[BLOCKER]` = must fix before F3; `[MAJOR]` = must fix or accept with documented test; `[MINOR]` = should fix; `[NIT]` = stylistic.

### B-01 [BLOCKER] — Session-cache staleness breaks `stopped_at` preservation (US-19.7 / E10)

**Sections:** Plan §T5 `_make_emit`, BRD §4.4 (single session per run) + §4.3 step 3.

**Problem.** The plan's emit callback does:
```python
if event.type == EventType.STOPPED:
    run = await session.get(Run, run_id)
    if run is not None:
        run.stop_reason = stopped.stop_reason.value
        if run.stopped_at is None:                # ← stale read!
            run.stopped_at = datetime.now(UTC)
        await session.commit()
```
The runner reuses a single `AsyncSession` for the entire run task (BRD §4.4 / plan T4 step 2). `async_session_maker` is configured with `expire_on_commit=False` ([database.py:18](../../../backend/app/database.py)), so the `Run` instance in the runner's identity-map is **never auto-refreshed** after the initial `session.get(Run, run_id)` at start.

`RunService.cancel_run` runs in a **different** HTTP-request session ([run_service.py:134-149](../../../backend/app/services/run_service.py)) — it sets `run.stopped_at = datetime.now(UTC)` and `run.stop_reason = USER_CANCELLED` and commits. The runner's cached `Run` does not see this write. When the orchestrator later emits `Stopped(USER_CANCELLED)` (1.5 s later, per US-19.7 Gherkin), the emit callback's `session.get(Run, run_id)` returns the cached object whose `stopped_at` is still `None` — the guard succeeds and **overwrites** the user's `T0` with `T0 + 1.5 s`.

This is the exact scenario US-19.7 / E10 / F-04 was supposed to prevent. The plan invokes the guard `if run.stopped_at is None` but the guard runs against stale identity-map data, not against the DB.

**Fix options (Orchestrator must pick one):**
1. Force a refresh before the guard: `await session.refresh(run, attribute_names=["stop_reason", "stopped_at"])`.
2. Open a fresh session for the terminal write: `async with async_session_maker() as fresh: run = await fresh.get(Run, run_id); …`.
3. Use a `WHERE stopped_at IS NULL` SQL UPDATE so the database (not the ORM cache) enforces the predicate.

**Tests affected.** T8 #5 (`test_cancel_preserves_stopped_at`) — if the test uses two real sessions (HTTP-side `cancel_run` + runner-side emit) and a real DB row this will FAIL under the plan as-written. If the test reuses a single session it will accidentally pass and the bug ships. Plan must mandate the two-session setup.

**RF impact:** RF-08 (UX), RF-02 (terminal write), audit invariant for `stopped_at` (US-19.7).

### B-02 [BLOCKER] — Rehydration dispatch uses an invalid FSM transition path

**Sections:** Plan §3 (rehydration dispatch table), §T4 step 6.

**Problem.** The plan describes the fold as e.g. *"set `current_state = AgentState.CRITIQUING`"* but it never explicitly forbids using `state.transition_to(...)`, and `transition_to` is the only public API on `RunState` that mutates `current_state` ([run_state.py:91-94](../../../backend/app/agent/run_state.py) raises `ValueError` on illegal transitions).

Walking the table from `INIT` with the canonical resumed-after-error sequence `[QuestionAsked, PlanCreated, EvidenceAdded, AgentErrored, ResumedAfterError]`:

1. `PLAN_CREATED` ⇒ `INIT → CRITIQUING`. But `TRANSITIONS[INIT] = {PLANNING, STOPPED, ERRORED}` ([states.py:24](../../../backend/app/agent/states.py)) — `INIT → CRITIQUING` is **illegal**.
2. If `STOPPED` was folded before `RESUMED_AFTER_*` (per the dispatch-order rule in the table), `current_state` is now `STOPPED`. `TRANSITIONS[STOPPED] = set()` — any subsequent `transition_to(SEARCHING)` raises.
3. `AGENT_ERRORED` folded as `no-op` (per the table), but if any prior fold left `current_state == ERRORED`, the next `transition_to` will also raise.

The plan ALSO contradicts itself in scope: the "STOPPED row says 'folded only if NOT followed by a resume event — guarded by dispatch order'" — dispatch order alone is not a guard, it is an ordering assumption. The events arrive in `step_index` order; if a `Stopped(ERRORED)` precedes a `ResumedAfterError`, the table will set `current_state = ERRORED` (via the implicit terminal transition) BEFORE the resume row clears it.

**Required fix.** The plan must state explicitly:
1. Rehydration MUST bypass `transition_to` and use **direct assignment** to `state.current_state` (private setter pattern OR a dedicated `state._rehydrate_state(target)` helper).
2. The fold MUST run a **two-pass** sweep, or look ahead for a trailing `RESUMED_AFTER_*` before applying `STOPPED`. Pure dispatch-order is unsafe (it only works if the implementer happens to skip the `STOPPED` row when a resume follows — that is the look-ahead, but the table buries it in a footnote).
3. Test T8 #15 must seed `AgentErrored` followed by `ResumedAfterError` AND assert `current_state == AgentState.SEARCHING` (already in the plan) PLUS assert no `ValueError` was raised mid-fold.

**RF impact:** RF-11 (resume must not crash), RF-04 (event-log fold determinism).

### B-03 [MAJOR] — `await_terminal` insertion point contradicts BRD §4.6

**Sections:** Plan §T6 ("call `await_terminal` at the **TOP** of `resume_run`, before `_find_resume_anchor` runs"); BRD §4.6 wiring diff places it **after** the final `await self.db.refresh(run)`.

**Problem.** Two divergent specifications:

| Doc | Insertion point | Side effects |
|---|---|---|
| BRD-19 v1.1 §4.6 (approved) | After `await self.db.commit()` + `await self.db.refresh(run)`; i.e. the `runs.stop_reason` clear is already durable. | The prior task may still write `stop_reason = USER_CANCELLED` while `await_terminal` waits — overwrites the just-cleared field. |
| IP-19 §T6 | At the **top** of `resume_run`, before `_find_resume_anchor`. | Safer (no overwrite race), but means `resume_run` blocks for up to 5 s **before** issuing its own validation (`stop_reason in _RESUMABLE`, anchor lookup). |

The plan's choice is the better one technically, but the plan does not declare the BRD diff as an amendment, nor does it cite the BRD's own §4.6 wording. The Coder will read both and get conflicting instructions.

Additionally, with `await_terminal` at the TOP:
- The prior task (still cancelling) may emit `Stopped(USER_CANCELLED)` during the wait, which writes `stop_reason = USER_CANCELLED` on the row (same value already there). When `await_terminal` returns, `resume_run` re-fetches and proceeds. The plan says *"Re-fetch the row after"* — but it doesn't say **how** (`session.refresh(run)`? Re-issue `session.get`?). The same identity-map staleness as B-01 applies on the resume path.

**Required fix.** Either (a) update the plan to mirror the BRD verbatim and accept the overwrite race, OR (b) propose a BRD v1.2 amendment (1-line diff) and have the plan explicitly cite that amendment. Spell out the re-fetch primitive in either case.

### B-04 [MAJOR] — Existing `test_run_service.py` will break (non-breaking guarantee violated)

**Sections:** Plan §T6, §T9.

**Problem.** T6 wires `agent_runner.start(run.id)` into the **production** `RunService.create_run`. The existing test suite at [test_run_service.py](../../../backend/tests/test_run_service.py) (and the route tests) exercises `RunService.create_run` without any fake — once T6 lands, every `create_run` call in tests will try to spawn a real `AgentOrchestrator` task that opens a session and calls real LLM / search adapters.

T9 ADDS new tests with a monkeypatched fake runner. The plan does NOT mandate an **autouse** no-op fake for the rest of the suite. Result: ~all pre-existing run-service tests fail or hang on T6 merge.

**Required fix.** Plan must require, in T6 or T9:
- An autouse `pytest` fixture (e.g. in `tests/conftest.py`) that monkeypatches `app.services.run_service.agent_runner` to a no-op stub for every test that does not explicitly opt-in to the real runner.
- An equivalent fixture for `app.main.lifespan` if any test exercises shutdown.

This must be called out as an explicit task / sub-bullet, not buried in T9's "monkeypatch strategy".

**RF impact:** non-breaking guarantee (architecture rule §3-7); test-suite stability.

### M-05 [MAJOR] — Session lifecycle is double-specified

**Sections:** BRD §4.4 ("One session per run … On task exit (success, terminal stop, or exception) the `async with` block closes the session.") versus Plan §T4 step 10 + §9 risk row ("`_on_task_done` callback runs in the loop thread and cannot await directly → use `loop.create_task(session.aclose())`").

**Problem.** Two ownership models:
- BRD wants the session bound to the supervised coroutine via `async with async_session_maker() as session:` (cleaned by the context manager).
- Plan wants the session opened in `start()` step 2 and closed in `_on_task_done` (a sync `add_done_callback` that schedules `loop.create_task(session.aclose())`).

The plan's model has real risks:
1. On process shutdown, after `agent_runner.shutdown()` awaits each task, the done-callbacks fire and schedule `session.aclose()` coroutines. If `engine.dispose()` runs immediately after `shutdown()` returns (per lifespan order), those scheduled close-tasks may not get a chance to run before the loop stops — leaked connections / asyncpg warnings on shutdown.
2. The plan's risk-row mitigation references `asyncio.run_coroutine_threadsafe` then dismisses it — that's correct (done-callbacks run on the loop) but leaves the reader confused.

**Required fix.** Pick ONE model. Recommended: BRD model (`async with` inside `_supervised_run`, no done-callback close). The done-callback only mutates the in-memory registry (`_tasks.pop`, `_orchestrators.pop`) — pure sync, no session involvement.

### M-06 [MAJOR] — Rehydration consumes SSE-shaped dicts, not pydantic events

**Sections:** Plan §T4 step 5 calls `event_service.get_events(run_id, after_step=0, limit=10_000)`. Plan §3 dispatch table treats event objects as typed (`event.sub_claims`, `event.claim_id`, `event.tool`, `event.judge_confidence`, …).

**Problem.** `EventService.get_events` returns `list[dict[str, Any]]` shaped as `{"id": …, "step_index": …, "type": …, **payload}` — NOT `BaseEvent` instances. Field access in the dispatch table will be `event["sub_claims"]`, not `event.sub_claims`. Additionally for `TOOL_CALLED` the plan reads `event.tool == "search"` but the real field is `source_type: SourceType` (no `tool` field exists).

**Required fix.** Either:
1. The plan adds a private helper `_load_pydantic_events(run_id)` on the runner (or extends `EventService`) that rehydrates dicts back into the discriminated-union `Event` type using `pydantic.TypeAdapter(Event).validate_python(d)`, or
2. The dispatch table is rewritten to access events via dict keys and uses the real field names: `event["target_claim_id"]` (not `claim_id` for `EvidenceAdded`), `event["source_type"]` (not `event.tool`), etc.

Without this fix the rehydration will crash on the first non-trivial event.

**RF impact:** RF-04 (forward-compat), RF-11 (resume).

### m-07 [MINOR] — `cancel()` is sync but the plan asserts lock-protected access

**Sections:** Plan §T4 "`cancel(run_id)`: **under lock**, look up orchestrator and task; call `orchestrator.cancel()`".

**Problem.** `cancel` has signature `def cancel(self, run_id) -> bool` (sync, per the BRD public API). It cannot `async with self._lock:`. In CPython the dict read is atomic on a single event loop, so there is no functional race, but the plan's wording is internally inconsistent. Either:
- Drop the "under lock" claim and add a note "registry reads are safe without the lock because they occur on the single event-loop thread; mutations always happen under the lock."
- Promote `cancel` to `async def cancel`.

The first option is recommended (preserves the BRD public API).

### m-08 [MINOR] — `STOPPED` dispatch guard relies on dispatch order

**Sections:** Plan §3 STOPPED row.

The note "folded only if NOT followed by a resume event — guarded by dispatch order" is not a guard, it is a hope. Already covered by B-02; lifting the look-ahead into an explicit pre-pass makes this MINOR if B-02 is fixed.

### m-09 [MINOR] — `ConnectionManager.__init__` does not initialize `_subscribers`

**Sections:** Plan §T3.

The plan's `subscribe` uses `self._subscribers.setdefault(run_id, [])` but never lists adding `self._subscribers: dict[UUID, list[asyncio.Queue[dict[str, Any]]]] = {}` to `__init__`. Pyright-strict will fail. One-line fix; should be in the spec to avoid the Coder guessing.

### m-10 [MINOR] — E11 description does not match `RunService.cancel_run` behaviour

**Sections:** Plan §4 (E11 table row), §T8 #17.

E11 says: *"Second `cancel(R)` is forwarded to orchestrator (idempotent flag, already True)."* But `RunService.cancel_run` ([run_service.py:142-144](../../../backend/app/services/run_service.py)) reads `run.stop_reason is not None` **before** ever calling `agent_runner.cancel`. With T6's "await_terminal at the TOP" ordering, the row still has `stop_reason = USER_CANCELLED` during the wait. The second cancel returns HTTP 400 `RunAlreadyStoppedError`, NOT a silent no-op. The UX is still acceptable; the prose is wrong.

**Required fix.** Rewrite E11: *"While `resume_run` awaits `await_terminal`, a second `POST /cancel` reads `run.stop_reason = USER_CANCELLED` (still set by the first cancel) and returns HTTP 400 `RunAlreadyStoppedError`. The user sees a clear 'already cancelled' message; the resume request continues unaffected and will issue its own `start(R)` once `await_terminal` returns."* Adjust T8 #17 to assert the 400, not a no-op.

### m-11 [MINOR] — `asyncio.shield(task)` caller-cancel semantics unspecified

**Sections:** Plan §T4 `await_terminal`.

If the HTTP request that triggered `resume_run` is disconnected by the client (FastAPI propagates `CancelledError` into the handler), `await asyncio.wait_for(asyncio.shield(task), timeout)` raises `CancelledError` in the **caller** while the shielded task continues. The plan does not say whether this is desired. It almost certainly is (we want the inner task to settle), but the plan should call it out so the Coder doesn't "fix" it by removing the shield.

### n-12 [NIT] — T8 #15 does not specify how `FakeOrchestrator` captures the `RunState`

**Sections:** Plan §T8 #15.

"capture the `RunState` passed to FakeOrchestrator" — but the constructor passes `state` positionally. The plan should add one line: *"`FakeOrchestrator.__init__` stores `state` on `self.state` (the real orchestrator already does this); the test reads `fake.state` after the run completes."* Avoids inventing a class-level capture list.

### n-13 [NIT] — T11 smoke-test delivery path unspecified

**Sections:** Plan §T11.

T11 says SSE client must receive `QuestionAsked + PlanCreated`. T3 leaves the BRD-10 SSE stream untouched — events arrive via the existing 500 ms DB poll loop, not via the new `publish` queues. The smoke test still passes, but T11 should add one sentence: *"Events reach the SSE client via BRD-10's DB poll loop; the queue path is opportunistic and untested at this layer."*

---

## 5. Blind-Path Checklist

| Check | Result | Notes |
|---|---|---|
| Path completeness | ⚠️ | Rehydration fold path crashes on invalid FSM transitions (B-02). |
| Error handling | ✅ | Supervisor last-resort spec is sound (N-01 closed). |
| User feedback continuity | ⚠️ | E11 description misleads the Coder (m-10); SSE delivery via DB poll consistent with BRD-10. |
| Terminal reachability | ✅ | All 7 `stop_reason` values reachable. |
| Cancellation honored | ⚠️ | T8 #4/#5 time bounds need `asyncio.timeout`; spec is approximate. |
| Resume coverage | ⚠️ | B-01 (stopped_at overwrite) + B-03 (insertion-point contradiction) + M-06 (dict vs pydantic) all hit the resume path. |
| Budget cap | ✅ (inherited from BRD-09). |
| Schema evolution | ✅ | Unknown event types ignored (RF-04). |

---

## 6. Test-Rigour Assessment

- **17 scenarios** in T8 — strong breadth.
- **Time-based tests** (#4, #5, #7, #8) need `asyncio.timeout`, not `time.time()` deltas. The plan §9 row says "use `asyncio.timeout`" but the test descriptions in §T8 do not enforce it. Add to T8 prelude: *"All time-sensitive assertions wrap waits in `async with asyncio.timeout(2.0):`; no wallclock waits exceed 0.2 s."*
- **#15 rehydration** — see n-12.
- **#5 stopped_at preservation** — must use a real two-session setup (one for `cancel_run`, one for the runner) per B-01. The plan does not specify this.
- **Coverage command** — `pytest --cov=app/agent/runner --cov-fail-under=80` is sound; `pytest-cov` is in `dev` deps ([pyproject.toml:33](../../../backend/pyproject.toml)).

---

## 7. Required Changes (top 3 must-fix)

1. **[B-01] Force a fresh DB read before the `stopped_at IS NULL` guard** in the emit callback (refresh, fresh session, or SQL UPDATE WHERE). Update T8 #5 to use two real sessions.
2. **[B-02] Mandate direct `state.current_state = …` assignment during rehydration**, plus a look-ahead two-pass for the `STOPPED → RESUMED_AFTER_*` pair. Add a `RunState._rehydrate_state(target)` helper or document the private-attr bypass.
3. **[B-03] Resolve the `await_terminal` insertion-point contradiction** with BRD-19 §4.6: either change the plan to match the BRD verbatim, or amend the BRD and cite the amendment.

Secondary (must also fix before APPROVED):

4. **[B-04] Add an autouse no-op `agent_runner` fixture** in `tests/conftest.py` to keep existing tests green.
5. **[M-05] Pick a single session-lifecycle model** (BRD's `async with` is recommended; drop the done-callback session close).
6. **[M-06] Rehydrate `get_events` dicts into pydantic events** OR rewrite the dispatch table for dict access with correct field names (`target_claim_id`, `source_type`, etc.).

---

## 8. Positive Highlights

- **N-01 / N-02 cleanly closed** with verifiable SQL and docstrings.
- **17 test scenarios** covering every US plus the new E10/E11 — strong breadth.
- **Effort estimate is realistic** (~300 LOC impl + ~685 LOC tests), well within the §6 budget.
- **RF coverage matrix** (§5) is tight and traceable.
- **Dependency order** (§6) and **Validation gates** (§8) are unambiguous and enforceable in CI.

---

## 9. Verdict

**⚠️ RETURN TO ORCHESTRATOR — score 7.55 / 10 < 9.00.**

The plan reads as a careful and detailed handoff document, and the BRD-trace is excellent. However, three independent BLOCKERs (session-cache staleness, FSM-transition fold violation, BRD-vs-plan ordering contradiction) and three MAJORs (existing-tests breakage, session-lifecycle ambiguity, dict-vs-event mismatch) together produce a real risk that the Coder ships a runner whose resume path crashes on the first `PLAN_CREATED` event and whose `stopped_at` invariant is silently violated.

These are mechanical fixes — not redesigns — and the Orchestrator can address them in iter 2 with edits to:
- §T5 (emit callback refresh primitive),
- §3 + §T4 step 6 (rehydration assignment model + look-ahead),
- §T6 (insertion-point + re-fetch primitive + BRD reconciliation),
- §T9 (autouse fake fixture),
- §T4 step 2/10 + §9 (session ownership single source of truth),
- §3 dispatch (pydantic rehydration or dict-key access with correct field names).

---

## 10. Next Step

- `audit_iter_F2 = 1` (within the 3-iteration cap).
- Hand back to **Orchestrator** for plan iteration 2/3 with the Required Changes in §7.
- Next audit will verify each B-* and M-* finding under section 0 (Resolution of Iter 1 findings) of the appended `## Iter 2` block in this file.

---
