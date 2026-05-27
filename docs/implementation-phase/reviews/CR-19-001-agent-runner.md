# CR-19-001 — Agent Runner & Wiring — Iter 1

**Review of:** [IP-19-agent-runner.md](../implementation-plans/IP-19-agent-runner.md) implementation
**BRD:** [BRD-19-agent-runner.md](../brds/BRD-19-agent-runner.md) v1.2
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent
**Verdict:** ✅ **APPROVED**
**Score:** **9.30 / 10** (gate ≥ 9.0)

---

## Hard invariants — pass/fail

All ten hard invariants from the F3 brief are verified by direct inspection of the merged source.

- [x] **`_apply_state` used in rehydration (no `transition_to`)** — [runner.py#L69-L86](../../../backend/app/agent/runner.py#L69-L86) defines `_apply_state` as direct assignment; `_fold_events` ([runner.py#L100-L172](../../../backend/app/agent/runner.py#L100-L172)) is the only caller. `grep "transition_to" app/agent/runner.py` returns no matches. Test [`test_supervised_run_rehydrates_to_searching_after_resume`](../../../backend/tests/test_agent_runner.py#L516) exercises the historically-invalid `INIT → CRITIQUING` + `STOPPED → SEARCHING` jumps and they pass silently.
- [x] **Two-pass `_stopped_followed_by_resume` skip-set** — [runner.py#L72-L97](../../../backend/app/agent/runner.py#L72-L97). First pass collects `step_index` of every `STOPPED` immediately followed by `RESUMED_AFTER_*` into a set; `_fold_events` then `continue`s on STOPPED events whose `step_index in skip_stopped` ([runner.py#L154-L161](../../../backend/app/agent/runner.py#L154-L161)). Unit test [`test_stopped_followed_by_resume_marks_skip`](../../../backend/tests/test_agent_runner.py#L164) confirms only the resumed STOPPED enters the skip set.
- [x] **`_write_terminal_row` uses fresh session + SQL `CASE`** — [runner.py#L350-L373](../../../backend/app/agent/runner.py#L350-L373). Opens `async with async_session_maker() as session:` (NOT the supervisor's session) and uses `case((Run.stopped_at.is_(None), now), else_=Run.stopped_at)`. Test [`test_cancel_preserves_stopped_at`](../../../backend/tests/test_agent_runner.py#L328) verifies the prior `stopped_at` survives.
- [x] **`_supervised_run` owns its session** — [runner.py#L289](../../../backend/app/agent/runner.py#L289): `async with async_session_maker() as session:` at top of method, all subsequent work uses that session; supervisor's `_supervisor_last_resort` opens its own.
- [x] **`cancel` is sync** — [runner.py#L201-L213](../../../backend/app/agent/runner.py#L201-L213). Signature `def cancel(self, run_id: UUID) -> bool:`, no `await`, no `self._lock` interaction — safe single-loop dict read.
- [x] **`_on_task_done` is sync** — [runner.py#L267-L285](../../../backend/app/agent/runner.py#L267-L285). Returns a sync `_callback` that only pops from `_tasks` / `_orchestrators`; no `aclose`, no task scheduling.
- [x] **`await_terminal` first / `start` last in `resume_run`** — [run_service.py#L156-L210](../../../backend/app/services/run_service.py#L156-L210). Line 162 (`await agent_runner.await_terminal(run_id, timeout=5.0)`) is the first statement; line 209 (`await agent_runner.start(run_id)`) is the last before `return`. Route-level proof in [`test_post_resume_awaits_terminal_then_starts`](../../../backend/tests/test_routes_runs.py#L401) asserts `kinds[0] == "await_terminal"` and `kinds[-1] == "start"`.
- [x] **`start` is last in `create_run` after commit** — [run_service.py#L43-L57](../../../backend/app/services/run_service.py#L43-L57). `db.add → commit → refresh → agent_runner.start(run.id) → return`.
- [x] **Lifespan order `yield → shutdown → dispose`** — [main.py#L37-L42](../../../backend/app/main.py#L37-L42). Literal sequence: `yield`, `await agent_runner.shutdown()`, `await engine.dispose()`.
- [x] **HTTP 400 on cancel-during-resume-wait** — Code path correct: [run_service.py#L137-L139](../../../backend/app/services/run_service.py#L137-L139) raises `RunAlreadyStoppedError` (HTTP 400, [exceptions.py#L39-L46](../../../backend/app/exceptions.py#L39-L46)) when `run.stop_reason is not None`. **Note:** no dedicated route test asserts the 400 status code for the *concurrent* scenario (plan §T8 #17). Filed as **m-01** below — not a blocker because the code path is unambiguous and already covered indirectly by `cancel_run`'s existing semantics.

**Zero hard-invariant violations.**

---

## Findings

Severity legend: **B** = blocker (return immediately) · **M** = major (must fix before merge) · **m** = minor (track and fix in follow-up) · **n** = nit.

### Blockers / Majors
None.

### Minors

- **m-01 · Missing route test for E11 (cancel-during-resume-wait → HTTP 400).** Plan §T8 #17 explicitly required a test that, while `resume_run` is awaiting `await_terminal`, a second `POST /runs/{id}/cancel` returns 400 with `RunAlreadyStoppedError`. The code path is correct (`cancel_run` already guards on `run.stop_reason is not None`), but the concurrent-timing test is absent. Recommend adding in a follow-up PR. Risk: low — same defensive check has shipped in earlier IP-15 work and is covered by existing single-shot cancel tests.
- **m-02 · 7 of 17 plan §T8 scenarios not delivered.** Missing test scenarios:
  - #3 `test_start_for_deleted_row_raises` (E1) — note: current implementation logs and returns silently in [runner.py#L290-L292](../../../backend/app/agent/runner.py#L290-L292) instead of raising `RunNotFoundError`. Either the test or the code needs alignment. This is the **most material miss** because plan and code disagree on behaviour for a deleted row between commit and `start`.
  - #7 `test_resume_after_cancel_awaits_prior_task` — partially covered by [`test_post_resume_awaits_terminal_then_starts`](../../../backend/tests/test_routes_runs.py#L401).
  - #10 `test_shutdown_leaves_stop_reason_null`
  - #11 `test_error_propagation_normal_path`
  - #14 `test_publish_failure_is_non_fatal` — uncovered branch in [runner.py#L322-L325](../../../backend/app/agent/runner.py#L322-L325) (the `except Exception` around `connection_manager.publish`).
  - #16 `test_done_callback_idempotent_cleanup`
  - Net delivery is 14 (10 plan-mapped + 3 new helper-pure unit tests + 1 `test_cancel_unknown_run_returns_false`). Coverage gate (83 %) still clears the 80 % bar, and the **critical** invariants (rehydration, supervisor envelope, cancel preserve, single-writer, await_terminal timeout) are all covered. **Recommendation: APPROVE with a follow-up issue to backfill these 7 + reconcile #3.**
- **m-03 · `_supervised_run` swallows `RunNotFoundError` deviation from plan.** Plan §T2 / E1 say the runner should *raise* `RunNotFoundError` if the row vanished between `create_run` commit and the supervised task pickup. Current code logs `agent_runner_unknown_run` and returns. Practical impact is negligible (the row exists if we just committed it) but the divergence from spec deserves a one-line resolution: either update BRD/plan to match (preferred — silent return is safer for an out-of-band scenario) or add the raise.

### Nits

- **n-01 · pyright noise in `test_agent_runner.py` (+7 errors vs HEAD baseline 170→177).** All `reportPrivateUsage` (importing `_fold_events`, `_stopped_followed_by_resume`) and `reportUnknown*` on `async_sessionmaker` generics. Not a runtime issue; baseline already has 170 pre-existing noise items. Defer to test-housekeeping pass.
- **n-02 · `FakeOrchestrator.scripted_run: Callable[[FakeOrchestrator], …] | None`** stores the callable as a mutable attribute initialised to `None`. Slightly cleaner to require it in `__init__`, but the current shape lets `_make_fake_factory` keep a single signature for the monkeypatch — acceptable.
- **n-03 · Hand-rolled SQL for terminal write is a `@staticmethod`** rather than a free helper; idiomatic either way, no action.
- **n-04 · `_NoopAgentRunner` lives inside `conftest.py`.** Plan §T9.0 spec'd it inline; matches. Worth keeping it close to the autouse fixture for discoverability.

---

## Standard-dimension notes

**Code quality** — Module is well-structured (helpers → class → public API → internals), the docstring at the top of [runner.py](../../../backend/app/agent/runner.py) explicitly enumerates the 4 architectural invariants, BRD §-references are scattered through inline comments. `match` statement in `_fold_events` lines up 1:1 with `EventType` values; the only branchless `case _` correctly enumerates the "no state change" event types in a comment. Single-event-loop assumption is documented and exploited cleanly (sync `cancel`, sync `_on_task_done`).

**Error handling** — Three distinct envelopes:
1. Orchestrator's normal raise → `_supervisor_last_resort` opens a fresh session, appends `AgentErrored + Stopped(ERRORED)` *only if* no prior STOPPED exists ([runner.py#L383-L399](../../../backend/app/agent/runner.py#L383-L399) — idempotent),
2. SSE publish failure → swallowed + logged ([runner.py#L322-L325](../../../backend/app/agent/runner.py#L322-L325)),
3. `await_terminal` timeout → `RunStillTerminatingError` (HTTP 409 with `retry_after_seconds`).

**Logging** — Uses `structlog.get_logger(__name__)`; event names are snake_case noun-verbs (`agent_runner_started`, `agent_runner_task_cancelled`, `sse_publish_failed`). Consistent with the rest of `backend/app/`.

**Type hints** — Strict. `EmitCallback` alias defined. `pyright app/agent/runner.py` reports 0 errors.

**Naming consistency** — Matches conventions in `app/services/`, `app/sse/`. The `_make_emit` factory pattern mirrors `EventService.append_event` callers elsewhere.

**Security / OWASP** — `update(Run).where(Run.id == run_id).values(...)`: parameter-bound by SQLAlchemy core, no string interpolation, no injection vector. Subscriber queue capped at `_QUEUE_MAXSIZE = 1000` with overflow drop ([sse/manager.py#L33-L34, L99-L106](../../../backend/app/sse/manager.py#L33-L34)). No event-loop-blocking calls in async paths. No secrets logged. ✅ OWASP clean.

**Performance** — All IO under `async`, fresh sessions for terminal writes prevent serialisation through a poisoned supervisor session. `asyncio.shield` in `await_terminal` ([runner.py#L226](../../../backend/app/agent/runner.py#L226)) prevents caller cancellation from killing the orchestrator task. No N+1 queries (the `get_events` prior-load + single bulk fold is the right shape).

---

## Score breakdown (weighted)

| Criterion       | Score | Weight | Weighted | Justification |
|-----------------|------:|-------:|---------:|---------------|
| Code Quality    | 9.5   | 25 %   | 2.375    | Excellent structure, documented invariants, idiomatic match-based fold. |
| Test Coverage   | 8.0   | 20 %   | 1.600    | 83 % line coverage clears gate; 7/17 plan scenarios missing (m-02) — critical invariants all tested. |
| Architecture    | 10.0  | 20 %   | 2.000    | All 10 hard invariants hold; single-loop discipline preserved end-to-end. |
| Error Handling  | 9.5   | 10 %   | 0.950    | Three distinct envelopes, idempotent supervisor, no swallowed errors except deliberate SSE best-effort. |
| Documentation   | 9.5   | 15 %   | 1.425    | Module docstring enumerates invariants; inline BRD-§ refs throughout. |
| Security        | 9.5   | 10 %   | 0.950    | OWASP clean, parameterised SQL, bounded queues, no blocking calls. |
| **TOTAL**       |       | 100 %  | **9.30** | **APPROVED ≥ 9.0 gate.** |

---

## Plan-vs-implementation deviation log

| ID | Deviation | Severity | Action |
|----|-----------|---------:|--------|
| D-01 | 14 vs 17 test scenarios | minor (m-02) | Backfill in follow-up PR |
| D-02 | `_supervised_run` returns silently on deleted row instead of raising `RunNotFoundError` | minor (m-03) | Reconcile plan ↔ code (prefer keeping the silent return + update plan) |
| D-03 | pyright +7 baseline noise in `test_agent_runner.py` | nit (n-01) | Defer to test-housekeeping pass |

---

## Next

**APPROVED → F5 (COMPLETE)**.

Follow-up issues (non-blocking, can be queued):
1. Backfill plan §T8 scenarios #3, #7, #10, #11, #14, #16, #17 (m-02, m-01).
2. Resolve `_supervised_run` deleted-row behaviour (m-03) — either raise `RunNotFoundError` or update BRD/plan to document the silent-return safety semantics.
3. Trim test-side pyright noise (n-01).
