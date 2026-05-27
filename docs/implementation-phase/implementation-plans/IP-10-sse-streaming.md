# Implementation Plan: BRD-10 SSE Streaming & Resume

**Plan ID:** IP-10
**BRD Reference:** [BRD-10-sse-streaming.md](../brds/BRD-10-sse-streaming.md)
**Created:** 2026-05-26
**Status:** Ready for Auditor (F2.S3)
**Implementation Order:** 11 of 19

---

## 1. Overview

Replace the HTTP-501 stub at `GET /api/runs/{run_id}/events` with a production SSE
stream that delivers append-only `events` rows to the frontend in real time, supports
`Last-Event-ID` resume, emits a 15-second heartbeat, and observes live cancellation
issued via `POST /api/runs/{run_id}/cancel` — fully covering **RF-08**.

The deliverable is:

- a new `backend/app/sse/` package (`stream.py` + `manager.py` + `__init__.py`),
- a rewritten `backend/app/routes/events.py` that returns an `EventSourceResponse`,
- one surgical edit in `backend/app/services/run_service.py::cancel_run` to notify
  the in-process `ConnectionManager`,
- a new React hook `frontend/src/hooks/useRunStream.ts` built on top of the
  **already existing** `frontend/src/lib/sse.ts` (no rewrite of that module),
- a focused regression suite (backend `pytest`, frontend `vitest`).

```
client EventSource  ──GET /api/runs/{id}/events──▶  events.py  (route)
       ▲                                                │
       │  Last-Event-ID                                 ▼
       │                                          event_stream()  ── reads ──▶ EventService.get_events
       │  data:/event:/id:                              │                       (append-only — RF-03)
       │                                                ▼
       └──   <heartbeat / data / Stopped>   ◀── ConnectionManager.is_cancelled?
                                                        ▲
                                  RunService.cancel_run ┘  (sets cancelled flag)
```

**In scope (BRD-10 §2 RF coverage):**
- **RF-08** — SSE streaming + heartbeat + `Last-Event-ID` resume + live cancellation.

**Non-goals (deferred):**
- WebSockets, server-push reconnection backoff strategies beyond the
  EventSource native one (no exponential delay table on the server side).
- Multiplexing several runs on a single connection (one EventSource = one run).
- Bearer-token auth on the SSE channel (route stays open like `GET /api/runs/{id}`,
  consistent with RF-05 "public-by-URL").
- Per-connection `step_index` cursor in the DB (the cursor stays in memory inside
  the generator; on reconnect the client provides `Last-Event-ID`).

---

## 2. Architectural Alignment

| Rule (`copilot-instructions.md §3`) | Compliance |
|---|---|
| #1 Three plugin seams | No new seam. SSE is **transport**, not a seam. The `Source` / `StoppingSignal` / `OutputRenderer` Protocols are untouched. |
| #2 Three not-seams | `ConnectionManager` is a single concrete in-process class — **not** abstracted behind a Protocol. The single-worker constraint (RF-05) is the precondition. No interface is exported. |
| #3 `stop_reason` is an enum | The stream terminates when a `Stopped` event arrives. `stop_reason` is **read** from the event payload (already an enum string per BRD-03); no new mapping. |
| #4 Events are append-only | The stream is a **read-only** projection of the `events` table. No new event types, no mutation. The cancellation path is signalled in-memory; the `Stopped{user_cancelled}` event is emitted by the FSM (BRD-07) — outside IP-10. |
| #5 Schema evolution (`extra="allow"`) | No schema change. No new event type. No model migration. Alembic is **not** run. |
| #6 UI surfaces trust guarantees | The hook exposes `isConnected`, `isComplete`, `lastEventId`, `error` so existing center-panel renderers (BRD-13) can show "connection lost / reconnecting". No new UI in IP-10. |
| #7 FE↔BE contract | No new Pydantic event models, so `scripts/export_types.py` does **not** run. The wire shape is the same `dict` returned today by `EventService.get_events`. |
| #8 `final_confidence = min(S, J)` | N/A (transport concern). |
| English-only artifacts (L-001) | All identifiers, docstrings, log keys, error messages in English. |
| `pyright --strict` + `ruff` clean | `from __future__ import annotations` on every new module; PEP 604 unions; no `Any` leak; no `Optional` from `typing`. |
| Async-first | `event_stream` is `async def` + `yield`; the route is `async def`; the manager exposes sync methods only because all state is in-memory dicts (no IO). |
| Mandatory unit tests (L-002) | Coder ships **≥ 20 unit tests** total (≥ 12 backend, ≥ 8 frontend), target ≥ 90 % coverage on `app/sse/` and `frontend/src/hooks/useRunStream.ts`. |
| API_URL prefix (L-008) | Frontend hook delegates to `createSSEConnection(path, …)` in `lib/sse.ts`, which already prefixes `API_URL`. No new `EventSource` call outside `lib/sse.ts`. |

---

## 3. Deviations from BRD-10 §4 (binding overrides)

BRD-10 §4 was authored against an empty `frontend/src/lib/sse.ts`. The repository
already contains a minimal `createSSEConnection(path, options)` function used by
production tests. The plan keeps that surface and **layers** the hook above it
instead of rewriting it.

### O-01. Do **NOT** replace `frontend/src/lib/sse.ts` with a class-based `SSEClient`

Reasons:
- The existing module is already API_URL-compliant (L-008).
- Pre-existing tests (`useRun.test.tsx`, `useRunHistory.test.tsx`) implicitly
  rely on the function-based shape via MSW.
- A class would force a refactor of `useRun.ts` outside IP-10's scope.

**Decision:** keep `createSSEConnection` and `parseSSEEvent` as-is. Add ONE
non-breaking extension: a typed event-listener helper so the new hook can
subscribe to named event types (`message`, `heartbeat`, `Stopped`, etc.) without
re-implementing `addEventListener` lifecycle.

### O-02. Resume uses query-string `last_event_id`, NOT a header

BRD-10 §4.4 shows the server reading `Last-Event-ID` either from the query alias
**or** from the request header. The native `EventSource` API does NOT let the
client set custom headers, so on initial connect the only viable transport is
the query string. The existing `createSSEConnection` already serialises
`options.lastEventId` as `?last_event_id=...` (verified in `lib/sse.ts`).

**Decision:** the server reads `last_event_id` from the **query string** only.
The route signature drops the `Header(alias="Last-Event-ID")` parameter (it was
never callable from a browser) and keeps a single `Query(alias="last_event_id")`
parameter. The route also still inspects the standard `Last-Event-ID` request
header as a fallback for **non-browser** clients (`httpx-sse` test client,
backend-to-backend), but it is no longer the documented contract.

### O-03. `ConnectionManager` is in `app/sse/manager.py` and is a module-level singleton

BRD-10 §4.3 already proposes a module-level singleton. Confirm the choice
explicitly: the single-worker constraint (RF-05, `uvicorn --workers 1`) makes
this safe. **No DI, no factory, no Protocol.** Tests that need a fresh manager
call `connection_manager.reset()` (added for test isolation; not exported in
`__init__.py`).

### O-04. `event_stream` polls with a **0.25 s** interval and tracks heartbeat per-loop, not per-wall-clock

BRD-10 §4.2 uses `datetime.utcnow()` + a 0.5 s `asyncio.sleep` and compares wall
clocks. Wall-clock comparison combined with async-cancellation can drift on a
busy event loop.

**Decision:**
- Poll interval = **0.25 s** (`POLL_INTERVAL_S`).
- Heartbeat counter measured in **loop ticks** (`HEARTBEAT_TICKS = 60` → 15 s at
  0.25 s/tick) so heartbeat cadence is deterministic in tests with
  `anyio.move_on_after`.
- Both constants are module-level and overrideable via `app.config.settings`
  (`sse_heartbeat_seconds` already exists; we add a derived
  `sse_heartbeat_ticks` computed at import time, **not** a new env var).

### O-05. The stream terminates on `Stopped` **or** on `connection_manager.is_cancelled`

BRD-10 §4.2 ends the stream only when the last polled batch ends with a
`Stopped` event. That is correct for normal termination, but on user-initiated
cancellation, the `Stopped{user_cancelled}` event is appended **by the FSM**
asynchronously — there is a window between `RunService.cancel_run` flipping the
manager flag and the FSM emitting the event.

**Decision:** the stream checks `connection_manager.is_cancelled(run_id)` at the
top of every poll loop. If true, it drains any remaining events already in the
DB once, then yields a final `event: cancelled` synthetic SSE frame
(`data: {}`, `id: <last_seen>`) and breaks. The synthetic frame is **not**
persisted as a DB event — it is purely a client-side signal that complements
the eventual `Stopped` event the FSM will write. The client treats either as
"end of stream".

### O-06. The route does NOT use `request.is_disconnected()`

`EventSourceResponse` already handles client disconnect by raising
`asyncio.CancelledError` inside the generator. The `finally:` clause runs on
disconnect and removes the connection from the manager.

### O-07. The route does NOT depend on `CurrentUsername`

Consistent with `GET /api/runs/{id}` (public-by-URL, RF-05). Adding auth here
would break the existing center-panel SSE flow on shared run URLs.

---

## 4. File-Level Plan

### 4.1 New backend files

| File | Purpose | LOC budget |
|---|---|---|
| `backend/app/sse/__init__.py` | Public surface: `connection_manager`, `event_stream`. | ≤ 10 |
| `backend/app/sse/manager.py` | `ConnectionManager` class + module singleton + `reset()` helper. | ≤ 80 |
| `backend/app/sse/stream.py` | `event_stream(run_id, event_service, last_event_id)` async generator. Constants `POLL_INTERVAL_S`, `HEARTBEAT_TICKS`. | ≤ 110 |

### 4.2 Modified backend files

| File | Change |
|---|---|
| `backend/app/routes/events.py` | Replace HTTP-501 stub with `EventSourceResponse`. Reads `last_event_id` from query (primary) and `Last-Event-ID` header (fallback). Wires `connection_manager.connect/disconnect`. |
| `backend/app/services/run_service.py` | In `cancel_run`, after the DB commit, call `connection_manager.cancel(run_id)`. Import is at the top of the file. |
| `backend/app/main.py` | (Optional — verify only.) Confirm `events` router is already mounted; if not, mount it. |

### 4.3 New frontend files

| File | Purpose | LOC budget |
|---|---|---|
| `frontend/src/hooks/useRunStream.ts` | React hook wrapping `createSSEConnection`, accumulating events, exposing `{events, isConnected, isComplete, lastEventId, error, reconnect, close}`. | ≤ 130 |

### 4.4 Modified frontend files

| File | Change |
|---|---|
| `frontend/src/lib/sse.ts` | Add one helper: `addNamedListener(source, eventName, handler)` (≤ 8 LOC). Do not refactor existing functions. |

### 4.5 New test files

| File | Coverage |
|---|---|
| `backend/tests/test_sse_manager.py` | `ConnectionManager` connect/disconnect/cancel/reset, active counts, idempotence. ≥ 6 tests. |
| `backend/tests/test_sse_stream.py` | `event_stream` happy path, resume from `last_event_id`, heartbeat cadence (tick counter), termination on `Stopped`, termination on `is_cancelled`, empty-events polling. ≥ 8 tests. Uses an in-memory `EventService` fake (no DB). |
| `backend/tests/test_routes_events.py` | Route returns 200 + correct headers; resume via `?last_event_id=`; resume via `Last-Event-ID` header fallback; disconnect cleans up manager state. ≥ 4 tests. Uses `httpx-sse` (already a transitive dep via `httpx`). If unavailable, parse the response body line-by-line. |
| `frontend/src/hooks/useRunStream.test.tsx` | Hook lifecycle: connect → receive events → `Stopped` sets `isComplete` → heartbeat ignored → reconnect → close on unmount. ≥ 8 tests. Uses `EventSource` from MSW (`msw/native` SSE handler) — if too heavy, use a hand-rolled `EventSource` mock attached to `globalThis`. |

---

## 5. Implementation Steps (binding order)

1. **`app/sse/manager.py`** — write `ConnectionManager` + singleton + `reset()`.
2. **`tests/test_sse_manager.py`** — write tests; run them green.
3. **`app/sse/stream.py`** — write `event_stream` with parametric `EventService`.
4. **`tests/test_sse_stream.py`** — write tests using a fake `EventService`.
5. **`app/sse/__init__.py`** — export `connection_manager` and `event_stream`.
6. **`app/routes/events.py`** — replace stub with `EventSourceResponse` wiring.
7. **`tests/test_routes_events.py`** — write integration tests.
8. **`app/services/run_service.py`** — add the one-line `connection_manager.cancel(run_id)` call in `cancel_run`.
9. **`tests/test_run_service.py`** — add **one** test asserting the manager flag is set after `cancel_run` (no new file).
10. **`frontend/src/lib/sse.ts`** — append `addNamedListener` helper.
11. **`frontend/src/hooks/useRunStream.ts`** — write hook.
12. **`frontend/src/hooks/useRunStream.test.tsx`** — write hook tests.
13. **Run** `ruff check backend`, `pyright backend`, `npx vitest run` — all green.

---

## 6. Acceptance Criteria (lifted from BRD-10 §5 + audit clarifications)

- **AC-01 — Stream returns 200 with correct headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`.
- **AC-02 — Real-time delivery:** new events appear in the stream within `POLL_INTERVAL_S` (≤ 0.25 s in tests, measured via `pytest-asyncio` with a fake clock).
- **AC-03 — Heartbeat:** an `event: heartbeat\ndata: \n\n` frame is emitted at most every 15 s when no business events are pending.
- **AC-04 — Resume (query):** when `?last_event_id=5` is supplied, the stream skips events with `step_index <= 5`.
- **AC-05 — Resume (header):** when the `Last-Event-ID: 5` request header is supplied and the query param is absent, behaviour is identical to AC-04.
- **AC-06 — Termination on Stopped:** after a `Stopped` event is sent, the generator returns and the response closes.
- **AC-07 — Termination on cancel:** when `connection_manager.cancel(run_id)` is called from another coroutine, the generator emits a final `event: cancelled` frame and returns within `POLL_INTERVAL_S`.
- **AC-08 — Disconnect cleans up:** when the client closes the connection, `connection_manager.active_connections(run_id)` decrements to zero.
- **AC-09 — `cancel_run` triggers the manager:** `RunService.cancel_run` calls `connection_manager.cancel(run_id)` after a successful DB commit.
- **AC-10 — Hook accumulates events:** `useRunStream` exposes events in arrival order and sets `isComplete=true` only on `type: "Stopped"`.
- **AC-11 — Hook ignores heartbeats:** heartbeat frames do not appear in `events[]`.
- **AC-12 — API_URL prefix:** the hook does NOT instantiate `EventSource` directly; it uses `createSSEConnection`.

Definition of done = all 12 ACs covered by named tests + lint + typecheck clean.

---

## 7. Risk Register

| ID | Risk | Mitigation |
|---|---|---|
| R-01 | `EventSourceResponse` swallowing cancellation errors | Wrap generator in explicit `try/finally`; assert `disconnect` ran in tests. |
| R-02 | DB connection held open for the lifetime of the stream (`DbSession` is request-scoped) | Document the trade-off; for V1 single-worker this is acceptable. Add a TODO referencing a future BRD if connection pressure appears. |
| R-03 | Heartbeat starves under high event volume | Heartbeat counter resets whenever a real event is yielded, so under load the heartbeat naturally pauses. Documented in `stream.py`. |
| R-04 | Frontend hook reconnect storm on backend restart | `EventSource` native retry is sufficient (browser default 3 s). Cap manual `reconnect()` to user-triggered. |
| R-05 | `Last-Event-ID` parsing on `int()` raises `ValueError` from a malformed client | Catch `ValueError` and treat as `after_step = 0`. Already in BRD-10 §4.2 pseudocode. |
| R-06 | Tests rely on real `asyncio.sleep` and flake | Inject `POLL_INTERVAL_S` via test-only kwarg, set to `0.0` in tests. |

---

## 8. RF Coverage Matrix

| RF | Surface | Test |
|---|---|---|
| RF-08 | `GET /api/runs/{id}/events` returns SSE stream | `test_routes_events.py::test_stream_returns_event_stream_content_type` |
| RF-08 | `Last-Event-ID` resume | `test_routes_events.py::test_resume_via_query_param`, `test_resume_via_header_fallback` |
| RF-08 | 15 s heartbeat | `test_sse_stream.py::test_heartbeat_after_15s_of_silence` |
| RF-08 | Live cancellation | `test_sse_stream.py::test_stream_breaks_on_cancellation`, `test_run_service.py::test_cancel_run_signals_connection_manager` |

---

## 9. Out-of-Scope Confirmation

- No new event types (RF-03 contract unchanged).
- No new env vars beyond the already-present `sse_heartbeat_seconds`.
- No Alembic migration.
- No changes to `Source`, `StoppingSignal`, `OutputRenderer` seams.
- No changes to `useRun.ts` / `useRunHistory.ts` (BRD-12).
