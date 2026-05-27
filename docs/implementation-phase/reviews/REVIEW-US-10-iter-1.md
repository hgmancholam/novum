# Code Review Report

**User Story:** US-10 (BRD-10 — SSE Streaming & Resume)
**Iteration:** 1
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent
**Scope:** RF-08 (streaming + heartbeat + Last-Event-ID resume + live cancellation)

---

## Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Code Quality | 9.5/10 | 25% | 2.375 |
| Test Coverage | 9.5/10 | 20% | 1.900 |
| Architecture | 10/10 | 20% | 2.000 |
| Documentation | 9.5/10 | 15% | 1.425 |
| Security | 9/10 | 10% | 0.900 |
| Performance | 9/10 | 10% | 0.900 |
| **TOTAL** | | | **9.50/10** |

## Verdict

✅ **APPROVED**

---

## 1. RF-08 Coverage

| Sub-requirement | Surface | Status |
|---|---|---|
| Streaming via SSE | [backend/app/sse/stream.py](../../../backend/app/sse/stream.py#L73) → [routes/events.py](../../../backend/app/routes/events.py#L31) | ✅ |
| 15 s heartbeat | `HEARTBEAT_TICKS = 60` × 0.25 s = 15 s ([stream.py#L37](../../../backend/app/sse/stream.py#L37)) | ✅ |
| `Last-Event-ID` resume | Query primary + header fallback ([events.py#L34-L42](../../../backend/app/routes/events.py#L34)) | ✅ |
| Live cancellation | `ConnectionManager.cancel` invoked from `RunService.cancel_run` ([run_service.py#L137](../../../backend/app/services/run_service.py#L137)) + synthetic `cancelled` frame ([stream.py#L102-L122](../../../backend/app/sse/stream.py#L102)) | ✅ |

## 2. Acceptance Criteria (IP-10 §6 — 12 ACs)

| AC | Test |
|---|---|
| AC-01 headers | [test_routes_events.py::test_stream_returns_event_stream_content_type](../../../backend/tests/test_routes_events.py#L97) |
| AC-02 real-time delivery | [test_sse_stream.py::test_stream_yields_events_then_terminates_on_stopped](../../../backend/tests/test_sse_stream.py#L98) (poll_interval_s=0) |
| AC-03 heartbeat | [test_sse_stream.py::test_stream_emits_heartbeat_after_idle_ticks](../../../backend/tests/test_sse_stream.py#L146) + `test_stream_heartbeat_resets_on_real_event` |
| AC-04 query resume | [test_routes_events.py::test_resume_via_query_param_skips_seen_events](../../../backend/tests/test_routes_events.py#L120) + `test_stream_resume_skips_events_at_or_below_last_event_id` |
| AC-05 header resume | [test_routes_events.py::test_resume_via_header_fallback](../../../backend/tests/test_routes_events.py#L131) + `test_query_param_wins_over_header` |
| AC-06 termination on Stopped | [test_sse_stream.py::test_stream_yields_events_then_terminates_on_stopped](../../../backend/tests/test_sse_stream.py#L98) |
| AC-07 termination on cancel | [test_sse_stream.py::test_stream_breaks_on_cancellation_with_synthetic_frame](../../../backend/tests/test_sse_stream.py#L201) + `test_cancellation_emits_synthetic_cancelled_frame` |
| AC-08 disconnect cleans up | [test_routes_events.py::test_disconnect_cleans_up_manager_state](../../../backend/tests/test_routes_events.py#L156) |
| AC-09 cancel_run signals manager | [test_run_service.py::test_cancel_run_signals_connection_manager](../../../backend/tests/test_run_service.py#L170) |
| AC-10 hook accumulates + Stopped | [useRunStream.test.tsx](../../../frontend/src/hooks/useRunStream.test.tsx#L117) "accumulates …" + "sets isComplete=true when a 'Stopped' event arrives" |
| AC-11 hook ignores heartbeats | [useRunStream.test.tsx](../../../frontend/src/hooks/useRunStream.test.tsx#L169) "ignores heartbeat frames in events[]" |
| AC-12 API_URL prefix | [useRunStream.test.tsx](../../../frontend/src/hooks/useRunStream.test.tsx#L107) "creates one EventSource targeting the run endpoint via API_URL" |

**All 12 ACs covered by named tests.**

## 3. Deviation Compliance (IP-10 §3)

| ID | Decision | Verified |
|---|---|---|
| O-01 | `lib/sse.ts` not rewritten — only `addNamedListener` appended | ✅ Module retains `createSSEConnection`/`parseSSEEvent`; only an ≤8-LOC helper added ([sse.ts#L76-L92](../../../frontend/src/lib/sse.ts#L76)) |
| O-02 | Query-string `last_event_id` primary; header fallback | ✅ Route reads `last_event_id` as `Query` (primary) and `Last-Event-ID` as `Header` (fallback); query wins via `or` precedence ([events.py#L45](../../../backend/app/routes/events.py#L45)). Test `test_query_param_wins_over_header` enforces ordering. |
| O-03 | Module-level singleton + `reset()` not in `__init__.py` | ✅ `connection_manager` exported; `reset()` only on instance ([manager.py#L80-L88](../../../backend/app/sse/manager.py#L80)) |
| O-04 | 0.25 s poll, heartbeat tick-counted (60), injectable | ✅ Constants at module level, both kwargs on `event_stream` |
| O-05 | Drain pending events then yield synthetic `cancelled` | ✅ Implemented at [stream.py#L102-L122](../../../backend/app/sse/stream.py#L102); covered by `test_stream_breaks_on_cancellation_with_synthetic_frame` |
| O-06 | No `request.is_disconnected()` | ✅ Cleanup happens in `try/finally` |
| O-07 | No auth on SSE route | ✅ No `CurrentUsername` dep |

## 4. Architectural Rules (`copilot-instructions.md §3`)

| Rule | Compliance |
|---|---|
| #1 Three plugin seams | ✅ No new seam (SSE is transport) |
| #2 Three not-seams | ✅ `ConnectionManager` is a concrete class, no Protocol wrapper. The `_CancellationProbe`/`_EventReader` Protocols in `stream.py` are private test seams — acceptable for DI, not user-facing |
| #3 `stop_reason` is an enum | ✅ Read from event payload; the synthetic `cancelled` event is **not** a stop_reason — it is a transport-level frame, **not** persisted |
| #4 Events are append-only | ✅ Stream is read-only projection over `EventService.get_events`. Synthetic `cancelled` frame explicitly **not** persisted to DB (verified in `stream.py` and asserted in tests) |
| #5 Schema evolution | ✅ No new event types, no migration, no env var |
| #6 UI surfaces guarantees | ✅ Hook exposes `isConnected`, `isComplete`, `lastEventId`, `error` |
| #7 FE↔BE contract | ✅ Wire shape is the existing `dict` from `EventService.get_events`; no Pydantic event model changes |
| #8 Confidence formula | N/A |

## 5. Detailed Feedback

### Code Quality (9.5/10)
- Clean separation: `manager.py` (sync state), `stream.py` (async generator), `routes/events.py` (transport adapter).
- `_parse_last_event_id` extracted as a pure helper — easy to test (5 dedicated tests).
- `_CancellationProbe` / `_EventReader` Protocols are minimal and enable seamless DI for tests without leaking abstractions to the public surface. Excellent decision.
- Late import of `connection_manager` inside `event_stream` avoids circular imports — documented inline.
- Minor: `request: Request` is marked `# noqa: ARG001` in [events.py#L33](../../../backend/app/routes/events.py#L33). Either use it or drop the parameter — keeping it "for future" violates YAGNI. Not blocking.

### Test Coverage (9.5/10)
- 45 new/modified tests total (8 + 14 + 9 + 13 + 1).
- Backend stream tests inject `poll_interval_s=0.0` and `heartbeat_ticks` — **no real `asyncio.sleep` reliance**, fully aligned with IP-10 R-06.
- Frontend mocks `EventSource` on `globalThis` and drives it imperatively — no flake risk, no MSW SSE complexity.
- `test_cancellation_emits_synthetic_cancelled_frame` and `test_run_with_no_events_then_cancelled` cover both drain paths.
- Minor: no dedicated timing test for AC-02 ("within POLL_INTERVAL_S"). Covered implicitly by zero-interval tests. Acceptable for V1.

### Architecture (10/10)
- Surgical edit to `run_service.py` (one new line + one import), exactly as scoped.
- No scope creep: no Alembic, no env vars, no `useRun.ts` rewrite, no seam changes.
- Single-worker singleton justified explicitly in module docstring (RF-05).

### Documentation (9.5/10)
- Every new module has a head docstring citing the relevant RF / IP-10 section.
- Inline comments explain non-obvious decisions (late import, heartbeat tick reset on real event, drain-then-cancel ordering).
- Minor: heartbeat behavior under load (R-03) could use one more inline comment at the `idle_ticks = 0` line in [stream.py#L131](../../../backend/app/sse/stream.py#L131). Not blocking.

### Security (9/10)
- Public-by-URL route (RF-05) — matches existing `GET /api/runs/{id}` policy.
- JSON serialization via `json.dumps` is safe — no template injection vector.
- Synthetic `cancelled` data is the literal `"{}"` — no injection surface.
- `int()` parsing of `last_event_id` catches `ValueError` — no DoS via malformed input.
- Minor: no rate limiting on SSE endpoint. Acceptable for V1 single-server scope; flag for future BRD if abuse appears.

### Performance (9/10)
- 0.25 s poll interval is reasonable for a single-worker, single-user-per-run scenario.
- Heartbeat counter pauses naturally under load (idle_ticks reset on real event) — R-03 mitigated.
- `DbSession` is held for the lifetime of the stream (R-02) — documented trade-off, acceptable for V1.
- Late import of `connection_manager` inside the generator has negligible cost (Python caches loaded modules).

## 6. Compliance Checklist

- [x] English-only artifacts (identifiers, docstrings, log keys, comments) — verified
- [x] `from __future__ import annotations` on every new module
- [x] PEP 604 unions (`str | None`), no `Optional` import
- [x] No `Any` in public signatures (`Any` only inside `dict[str, Any]` payloads — necessary for the event-as-dict contract)
- [x] API_URL prefix: hook delegates to `createSSEConnection`; no direct `new EventSource(...)` outside `lib/sse.ts` — confirmed by AC-12 test
- [x] No Pydantic event-model changes → `scripts/export_types.py` not required
- [x] Append-only events table untouched

## 7. Positive Highlights

- The `_CancellationProbe` / `_EventReader` private Protocols are a textbook example of dependency inversion without over-abstraction — exactly the spirit of "three not-seams".
- The drain-on-cancel pattern (yield pending events, **then** the synthetic `cancelled` frame) is subtle and correctly implemented, fulfilling the "no event ever lost" invariant of RF-04.
- Frontend hook decouples `lastEventIdRef` (synchronous resume cursor) from `lastEventId` (rendered state) — avoids stale-closure bugs on rapid reconnect.
- Tests are deterministic and fast — zero `asyncio.sleep`-driven flake.

## 8. Non-Blocking Suggestions (for future iterations)

1. Drop `request: Request` from `stream_events` or wire it (e.g. for `request.client.host` logging). Currently noqa-silenced.
2. Add one explicit "delivery within POLL_INTERVAL_S" timing test (AC-02) with a small monotonic-clock budget, to make the latency invariant assertable.
3. Consider exposing `connection_manager.active_connections(run_id)` via a debug-only endpoint for observability (future BRD).

---

**Final Score: 9.50 / 10 — APPROVED. Proceed to F5: COMPLETE.**
