# Implementation Plan — IP-29: Per-Run Cost & Token Tracking with Trace Panel

**Plan ID:** IP-29
**Parent BRD:** [BRD-29 v1.0](../brds/BRD-29-cost-and-token-tracking.md)
**Parent User Stories:** _(to be drafted alongside this plan — `US-29-A` backend-ledger, `US-29-B` read-path-api, `US-29-C` frontend-trace-tab)_
**Date:** 2026-05-29
**Author:** Orchestrator Agent
**Estimated Effort:** L (≈ 6–8 h pair-session, full-stack)
**Iteration:** 1

---

## 1. Summary

Add an **append-only per-call cost ledger** to Novum so every external billable invocation (one per LLM round, one per Source `search`/`fetch`) emits exactly one `CostIncurred` event into the existing `events` table (`payload JSONB`, `extra="allow"`). The ledger is the **only** source of truth; a regular Postgres view `run_costs` aggregates it on demand, a REST endpoint `GET /api/runs/{run_id}/costs` returns the grouped breakdown, and a new **trace-panel tab `T1d`** plus a **`TotalCostChip`** in the run header surface the totals live via the existing SSE stream (no new SSE endpoint, no polling).

Backend instrumentation lives in **two chokepoints** mandated by `ai-services.md §1.3`: `backend/app/llm/client.py::call` (rewritten to use `instructor.chat.completions.create_with_completion`, which returns `(model_instance, raw_completion)` so we can read `raw.usage` after Instructor's JSON extraction) and every `Source` plugin under `backend/app/sources/*`. Pricing is **hybrid**: for LLMs `litellm.completion_cost(completion_response=raw)` first, falling back to a hard-coded table in `backend/app/llm/pricing.py` (`pricing_source="fallback"`) and finally to `cost_usd=0.0` with `pricing_source="static"` when both miss (AC-09). For Sources, a static table in `backend/app/sources/pricing.py` keyed on the provider's billable unit — Tavily: 1 credit `basic` / 2 credits `advanced` × `settings.tavily_usd_per_credit` (env `TAVILY_USD_PER_CREDIT`, default `0.008`); Wikipedia / Semantic Scholar / OpenAlex: `cost_usd=0.0`, `units=1`.

Three new `ContextVar`s in `backend/app/llm/context.py` (`current_run_id`, `current_task_name`, `current_emitter`) carry the run-level metadata into the call sites without threading it through every function signature. `runner._supervised_run` ([backend/app/agent/runner.py](../../../backend/app/agent/runner.py) ~line 420, before the FSM loop) sets `current_run_id` and `current_emitter` (the same `_emit` callback that already wraps `EventService.append_event` at line 453). The orchestrator wraps each FSM transition with a one-line `_with_task(name)` helper that sets `current_task_name`.

**Frontend** is full-stack scope per BRD-29 §4.6: a TanStack-Query hook `useRunCosts(runId)` (`hooks/useRunCosts.ts`) loads from the REST endpoint on mount and patches the cached data on every incoming `CostIncurred` SSE frame (no re-fetch per event). Two atoms (`TotalCostChip`, `CostBarSegment`), two molecules (`CostBreakdownBar`, `CostBreakdownTable`), and one organism (`TraceCostPanel`) build the surface. `TracePanel` registers the new `T1d` tab; the run-header organism mounts `<TotalCostChip />` next to the existing status chips. **No new design tokens** are introduced — everything reuses `--accent`, `--accent-soft`, `--glass-bg`, `--text-*` from `index.css`, which means the feature works in both **dark** (default) and **light** (BRD-28) themes for free.

**Strictly additive:** the `events` table schema is unchanged (one new row type via `extra="allow"`), no existing event type is removed or renamed, the `stop_reason` enum and confidence formula `min(S, J)` are untouched, the three plugin seams remain stable, and historical runs (no `CostIncurred` events) simply render `total_usd = 0.0`. Pricing is captured at emit time so **read determinism** (RF-11) holds across re-opens and forks (AC-08, AC-10). Failed tenacity retries do **not** emit (avoid over-counting — only the final successful call records cost — AC-02 idempotency clause).

RF traceability: **RF-20 (NEW)**, **RF-03** (append-only preserved), **RF-08** (SSE preserved & leveraged), **RF-11** (price captured once, never recomputed), **RF-13** (cost is a trust signal — surfaced both in the always-visible chip and the trace tab), **RF-15** (`extra="allow"` schema evolution), **RF-16** (graceful degradation on pricing miss).

---

## 2. Prerequisites

- [x] BRD-29 v1.0 written (`docs/implementation-phase/brds/BRD-29-cost-and-token-tracking.md`) — locks the event shape, pricing strategy (hybrid), view-not-MV decision, and full-stack scope. **F1 Auditor review still pending** — proceed only after audit ≥ 9/10 per copilot-instructions §7.7.
- [x] Existing `EventService.append_event` at [backend/app/services/event_service.py](../../../backend/app/services/event_service.py)::29 already handles envelope splitting, `step_index` assignment, JSONB payload write, and SSE fan-out via the `_emit` callback in [backend/app/agent/runner.py](../../../backend/app/agent/runner.py)::453. The new event reuses this path verbatim — **no changes to `EventService`**.
- [x] `EventType` enum at [backend/app/domain/enums.py](../../../backend/app/domain/enums.py)::92 already has 44 literals + a discriminated union `Event` registered in [backend/app/domain/events.py](../../../backend/app/domain/events.py)::826 + `EVENT_TYPE_MAP`. Adding one more literal + one Pydantic class is a known 3-line pattern.
- [x] `FORKABLE_EVENTS` at [backend/app/domain/events.py](../../../backend/app/domain/events.py)::854 — the new event **must NOT** be added (it's not a meaningful fork point).
- [x] SSE stream at [backend/app/sse/stream.py](../../../backend/app/sse/stream.py)::75 already streams every event type and supports `Last-Event-ID` resume. The new event auto-flows — **no SSE changes**.
- [x] `current_provider: ContextVar` already exists at [backend/app/llm/client.py](../../../backend/app/llm/client.py)::41 — proves the contextvar inheritance pattern works for our single-worker uvicorn (RF-05). New contextvars follow the same pattern in a sibling `context.py` module.
- [x] `count_tokens` at [backend/app/llm/client.py](../../../backend/app/llm/client.py)::465-479 already uses `tiktoken` with a `cl100k_base` fallback — kept as-is (used elsewhere by the budget gate); not the source of cost data.
- [x] `litellm` is already pinned in [backend/pyproject.toml](../../../backend/pyproject.toml); `litellm.completion_cost(completion_response=...)` is part of the public API in the installed version.
- [x] `instructor` is already pinned; confirm at plan time whether `client.chat.completions.create_with_completion(...)` is the correct API surface (mode `TOOLS` / `JSON`). **First task of Phase 2** is a 5-min smoke test (see Task 2.1 note).
- [x] `frontend/src/components/atoms`, `molecules`, `organisms`, `templates` layering is enforced by ESLint `import/no-restricted-paths` — atoms imported by molecules, molecules by organisms; no organism imports another organism.
- [x] `TanStack Query` (`@tanstack/react-query`) is in `frontend/package.json` (used by existing hooks). `useRunCosts` follows the same shape as other run-scoped queries.
- [x] The SSE store on the frontend (the existing `useRunSSE` / equivalent — verify in Phase 4 by reading `frontend/src/hooks/`) already publishes typed events. `useRunCosts` subscribes to it; **no change** to the SSE infrastructure on the FE side.
- [x] `scripts/export_types.py` regenerates `frontend/src/types/events.ts` from Pydantic — the new event literal must flow through this script (Phase 4 Task 4.1).
- [x] User-memory rules respected: **all code in English** (events, comments, log lines, system prompts); **React props never use `[key: string]: unknown`** — use `HTMLAttributes<...>` or explicit literal-union props; **`fetch()` options spread order** — `...init` before explicit `headers`/`body` if used via `api.ts`.

---

## 3. Task Breakdown

### Phase 1 — Domain & foundations (parallelizable across files)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 1.1 | Add `EventType.COST_INCURRED = "CostIncurred"` to the enum at [backend/app/domain/enums.py](../../../backend/app/domain/enums.py)::92. Insert in alphabetical/cluster position — group with the audit/observation cluster (after `AGENT_OBSERVATION` is acceptable) since it has no obvious sibling. Update the docstring/comment that says "All event types (44)" to "(45)". | `backend/app/domain/enums.py` (MODIFY) | XS | — | event registration |
| 1.2 | Add the `CostIncurredEvent` Pydantic class to [backend/app/domain/events.py](../../../backend/app/domain/events.py) (after the last event class, before the `Event = Annotated[...]` discriminated-union declaration at ~line 826). Exact fields per BRD-29 §4.4: `provider: str`, `kind: Literal["llm","search","fetch"]`, `model: str \| None = None`, `task_name: str \| None = None`, `prompt_tokens: int = 0`, `completion_tokens: int = 0`, `units: int = 0`, `unit_cost_usd: float = 0.0`, `cost_usd: float`, `latency_ms: int`, `pricing_source: Literal["litellm","fallback","static"]`. **Use `ConfigDict(extra="allow")`** (RF-15) so future fields like Anthropic `cache_read_input_tokens` can be appended via the payload without a migration. Then add the class to the `Event` `Annotated` union and to `EVENT_TYPE_MAP`. **Do NOT add it to `FORKABLE_EVENTS`** (line ~854). | `backend/app/domain/events.py` (MODIFY) | S | 1.1 | event registration |
| 1.3 | Create `backend/app/llm/context.py` with three contextvars exactly per BRD-29 §4.8: `current_run_id: ContextVar[UUID \| None]`, `current_task_name: ContextVar[str \| None]`, `current_emitter: ContextVar[Callable[[BaseEvent], Awaitable[None]] \| None]`, all `default=None`. Import `BaseEvent` from `app.domain.events`. **No global state, no thread-locals.** Add a module docstring linking back to RF-20 and BRD-29 §4.8. | `backend/app/llm/context.py` (NEW) | XS | — | context plumbing |
| 1.4 | Create `backend/app/llm/pricing.py`. Exports:<br>```python<br>def compute_cost(*, model: str, raw_completion: Any) -> tuple[float, Literal["litellm","fallback","static"]]:<br>```<br>Implementation:<br>1. Try `litellm.completion_cost(completion_response=raw_completion)`. If it returns a positive float, return `(cost, "litellm")`.<br>2. On `None`/`0.0`/exception, look up `model` in a local `_PRICING_TABLE` dict (USD per 1M tokens, input + output). V1 active: `claude-sonnet-4-5` (Anthropic). Compute `cost = (prompt_tokens/1e6) * in_price + (completion_tokens/1e6) * out_price`. Return `(cost, "fallback")`.<br>3. If model not in table, return `(0.0, "static")` and log a `structlog.warn("pricing_miss", model=model)` once per process (dedupe via `functools.lru_cache` or an in-module `set`).<br>Use `getattr(raw_completion, "usage", None)` defensively; if absent, return `(0.0, "static")`. **Pure module — no I/O, no DB**. | `backend/app/llm/pricing.py` (NEW) | S | — | AC-01, AC-09; R-02 |
| 1.5 | Add `tavily_usd_per_credit: float = 0.008` to `Settings` in [backend/app/config.py](../../../backend/app/config.py). Default `0.008`; env var `TAVILY_USD_PER_CREDIT` (Pydantic-settings auto-binds). Add a one-line docstring comment: "USD per Tavily credit; basic=1 credit, advanced=2 credits". | `backend/app/config.py` (MODIFY) | XS | — | AC-02, R-07 |
| 1.6 | Create `backend/app/sources/pricing.py`. Exports three pure helpers:<br>```python<br>def tavily_cost(search_depth: str) -> tuple[int, float, float]:  # (units, unit_cost_usd, cost_usd)<br>def wikipedia_cost() -> tuple[int, float, float]:<br>def free_source_cost() -> tuple[int, float, float]:  # used by SemanticScholar, OpenAlex<br>```<br>`tavily_cost`: `{"basic": 1, "advanced": 2}.get(search_depth, 1)` × `settings.tavily_usd_per_credit`. `wikipedia_cost` → `(1, 0.0, 0.0)`. `free_source_cost` → `(1, 0.0, 0.0)`. Import `settings` from `app.config`. | `backend/app/sources/pricing.py` (NEW) | XS | 1.5 | AC-02, AC-03 |
| 1.7 | Create `backend/app/sources/_cost.py` with the shared emit helper:<br>```python<br>async def emit_source_cost(*, provider: str, kind: Literal["search","fetch"], units: int, unit_cost_usd: float, latency_ms: int) -> None:<br>```<br>Reads `current_emitter` from `app.llm.context`; if `None`, return silently (covers the "called outside a run" case — e.g. health-check probes). Otherwise emits a `CostIncurredEvent(provider=provider, kind=kind, model=None, task_name=current_task_name.get(), units=units, unit_cost_usd=unit_cost_usd, cost_usd=units * unit_cost_usd, latency_ms=latency_ms, pricing_source="static")`. **Do NOT swallow emitter exceptions** — let them surface so a broken event service is loud, not silent. | `backend/app/sources/_cost.py` (NEW) | S | 1.2, 1.3 | AC-02, AC-03 |

### Phase 2 — Backend instrumentation (depends on Phase 1)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 2.1 | **API smoke first.** In a 5-min REPL session, confirm the exact instructor API: open `backend/.venv` Python, call `import instructor; client = instructor.from_litellm(litellm.acompletion); print(hasattr(client.chat.completions, "create_with_completion"))`. **Expected `True`** — if `False`, fall back to wrapping the existing `create` call and parsing usage from the response object (instructor exposes `_raw_response` on the model in newer versions). Record the discovered call form in the docstring of `client.py::call` so future readers know which API surface was wired. **This is a 5-min spike, not a feature task** — it just de-risks R-01 before refactoring `call()`. | n/a (REPL) | XS | 1.4 | R-01 |
| 2.2 | Rewrite [backend/app/llm/client.py](../../../backend/app/llm/client.py)::call (current signature at ~line 300). Changes:<br>1. Replace the `instructor` call with `create_with_completion`. New return shape: `(model_instance, raw_completion)`. The function's public return type is unchanged (`T`).<br>2. Wrap the call in `t0 = time.perf_counter()` / `latency_ms = int((time.perf_counter() - t0) * 1000)`.<br>3. After success: `usage = getattr(raw, "usage", None)`. If non-`None`, call `compute_cost(model=..., raw_completion=raw)`. Read `current_emitter`; if set, `await emitter(CostIncurredEvent(provider=settings.llm_provider, kind="llm", model=self._model_for(role), task_name=current_task_name.get(), prompt_tokens=getattr(usage, "prompt_tokens", 0), completion_tokens=getattr(usage, "completion_tokens", 0), cost_usd=cost, latency_ms=latency_ms, pricing_source=src))`.<br>4. **Failure path:** if the call raises, do NOT emit — only successful calls record cost (AC-02 idempotency).<br>5. Keep the `@retry_llm` tenacity decorator unchanged (line 269). Because cost emission is **inside** the success block of the wrapped call body, tenacity retries do not double-emit.<br>6. The `current_provider` contextvar continues to drive provider selection — no change to that path.<br>Keep all existing behaviour: token-fallback rotation, `_is_quota_exhausted`, `LLMProviderQuotaExhausted` short-circuit, the optional `emit_event` parameter (used by `JudgeProviderDegradedEvent` — leave it). | `backend/app/llm/client.py` (MODIFY) | M | 1.2, 1.3, 1.4, 2.1 | AC-01, AC-02 (LLM half), AC-09 |
| 2.3 | In [backend/app/agent/runner.py](../../../backend/app/agent/runner.py)::`_supervised_run` (~line 420), after the `_emit` async callback is constructed (~line 453) and **before** the FSM loop runs:<br>```python<br>from app.llm.context import current_run_id, current_emitter<br>current_run_id.set(run_id)<br>current_emitter.set(_emit)<br>```<br>The `current_provider.set(...)` line that already exists in this function is the precedent — follow the exact same pattern. **No `copy_context()` needed** — `_supervised_run` is the asyncio.Task root for the run, and contextvar inheritance propagates to all awaits below. | `backend/app/agent/runner.py` (MODIFY) | XS | 1.3 | AC-01, AC-02 |
| 2.4 | In [backend/app/agent/orchestrator.py](../../../backend/app/agent/orchestrator.py), add a tiny helper method:<br>```python<br>@contextmanager<br>def _with_task(self, name: str) -> Iterator[None]:<br>    from app.llm.context import current_task_name<br>    token = current_task_name.set(name)<br>    try:<br>        yield<br>    finally:<br>        current_task_name.reset(token)<br>```<br>Then wrap each FSM state-transition handler (`_run_classify`, `_run_plan`, `_run_search_round`, `_run_draft`, `_run_judge`, etc. — find via `grep` on `async def _run_`) with `with self._with_task(self.state.current_state.value):` at the top of the method body. The `current_state` enum value (e.g. `"CLASSIFYING"`, `"PLANNING"`) becomes the `task_name` on each LLM call inside that step. **Use the enum's `.value` (string)**, not its repr. | `backend/app/agent/orchestrator.py` (MODIFY) | S | 1.3 | AC-01 task_name attribution |
| 2.5 | Instrument [backend/app/sources/tavily.py](../../../backend/app/sources/tavily.py). Two changes:<br>**(a)** `search()` (~line 57): wrap the `await self._client.search(**kwargs)` call with `t0 = time.perf_counter()`; on success compute `latency_ms`, call `units, unit_cost, cost = tavily_cost(self._search_depth)`, then `await emit_source_cost(provider="tavily", kind="search", units=units, unit_cost_usd=unit_cost, latency_ms=latency_ms)`. Do NOT emit on failure (mirrors LLM behaviour, AC-02).<br>**(b)** `fetch_full()` / `extract()` (~line 101): same pattern with `kind="fetch"`. Tavily's `extract` is metered the same way as `search` per their API docs — use `tavily_cost("advanced")` (2 credits) since extract is the deep-fetch path.<br>**Idempotency note:** if tenacity (the underlying `tavily-python` client retries internally) ever surfaces multiple successful calls, only the outer call's success branch executes — single emit guaranteed. | `backend/app/sources/tavily.py` (MODIFY) | S | 1.6, 1.7 | AC-02 |
| 2.6 | Instrument [backend/app/sources/wikipedia.py](../../../backend/app/sources/wikipedia.py)::`search()` (~line 46): same wrapper, `provider="wikipedia"`, `kind="search"`, units/cost from `wikipedia_cost()` → `(1, 0.0, 0.0)`. Wikipedia has no `fetch` path equivalent (Wikipedia's `page()` IS the fetch) — emit once per `search()` call. | `backend/app/sources/wikipedia.py` (MODIFY) | XS | 1.6, 1.7 | AC-03 |
| 2.7 | Instrument [backend/app/sources/semantic_scholar.py](../../../backend/app/sources/semantic_scholar.py) and [backend/app/sources/openalex.py](../../../backend/app/sources/openalex.py). Same pattern, `provider="semantic_scholar"` / `"openalex"`, `free_source_cost()`. One emit per public method call (`search`, optional `fetch_full`). If either source uses pagination internally that issues N HTTP requests for one logical search, **emit once per logical Source method call**, not per HTTP request — the user-visible unit is the search, not the HTTP round-trip. Document this in a one-line comment at each call site. | `backend/app/sources/semantic_scholar.py`, `backend/app/sources/openalex.py` (MODIFY) | S | 1.6, 1.7 | AC-03 |

### Phase 3 — Read path: view, index, endpoint (parallelizable with Phase 4 backend half)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 3.1 | Create the Alembic migration `backend/alembic/versions/004_run_costs_view.py`. `revision = "004_run_costs"`, `down_revision = "003_add_llm_provider"` (matches current head per the migrations list). Body exactly per BRD-29 §4.3:<br>• `upgrade()`: `op.execute("CREATE INDEX ix_events_cost_provider ON events ((payload->>'provider')) WHERE type = 'CostIncurred'")` then `op.execute(CREATE_VIEW_SQL)` with the GROUP BY exactly as specified in BRD §4.2 (group by `run_id, provider, kind, model, task_name`). Wrap the view SQL in a Python `_VIEW_SQL = """..."""` constant for readability.<br>• `downgrade()`: `DROP VIEW IF EXISTS run_costs` then `DROP INDEX IF EXISTS ix_events_cost_provider` (reverse order of `upgrade`).<br>• Add a module docstring noting that the view is **regular, not materialised** (per D1 of BRD-29 §10), and that promotion to MV is a future migration. | `backend/alembic/versions/004_run_costs_view.py` (NEW) | S | 1.2 | AC-04, D1 |
| 3.2 | Create `backend/app/routes/costs.py`. Module structure:<br>1. Pydantic response models exactly per BRD-29 §4.4 — `ProviderCostRow` (with `pct_of_total: float`) and `RunCostsResponse` (with `total_usd`, `total_prompt_tokens`, `total_completion_tokens`, `by_provider: list[ProviderCostRow]`).<br>2. FastAPI router `router = APIRouter(prefix="/api/runs", tags=["costs"])`.<br>3. Endpoint `GET /{run_id}/costs` with dependencies `current_user: User = Depends(get_current_user)` and `db: AsyncSession = Depends(get_db)` (reuse the existing dependencies from `app/dependencies.py`).<br>4. **Ownership check** first: `run = await db.get(Run, run_id); if run is None or run.user_id != current_user.id: raise HTTPException(404)`. Return 404 (not 403) so we don't leak existence of foreign runs (AC-05).<br>5. Query the view with raw SQL via `text()`: `SELECT provider, kind, model, calls, prompt_tokens, completion_tokens, units, cost_usd FROM run_costs WHERE run_id = :run_id ORDER BY cost_usd DESC`. Bind `run_id`. Map rows to `ProviderCostRow`.<br>6. Compute totals in Python: `total_usd = sum(r.cost_usd for r in rows)`, same for tokens. Compute `pct_of_total = round((row.cost_usd / total_usd) * 100, 2) if total_usd > 0 else 0.0` — division-by-zero guard (covers empty runs and all-free runs).<br>7. Return `RunCostsResponse(run_id=run_id, total_usd=total_usd, total_prompt_tokens=..., total_completion_tokens=..., by_provider=rows)`. | `backend/app/routes/costs.py` (NEW) | M | 3.1 | AC-04, AC-05 |
| 3.3 | Register the router in [backend/app/main.py](../../../backend/app/main.py): add `from app.routes import costs` (preserve alphabetical order of imports if the file uses it) and `app.include_router(costs.router)` next to the other run-scoped routers. | `backend/app/main.py` (MODIFY) | XS | 3.2 | AC-04 |

### Phase 4 — Frontend types + data layer (depends on Phases 1, 3)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 4.1 | Regenerate `frontend/src/types/events.ts` by running `python scripts/export_types.py` from the repo root with the backend `.venv` activated. The script reads `app.domain.events.Event` via Pydantic's `TypeAdapter.json_schema()` and writes the union literal `"CostIncurred"` plus the JSON-schema fragment for `CostIncurredEvent`. **Never hand-edit this file** (copilot-instructions §3.7). Diff after regen: only the new literal in `EventType`, a new entry in the `EventSchema` const, and possibly a re-sorted union — review for unrelated drift and **abort the PR** if anything outside `CostIncurred` changed. | `frontend/src/types/events.ts` (REGEN — automated, no manual edits) | XS | 1.2 | type contract |
| 4.2 | Create `frontend/src/types/costs.ts` with the response types mirroring the backend (these are NOT auto-generated since the endpoint response is a Pydantic model, not an event):<br>```typescript<br>export interface ProviderCostRow {<br>  provider: string;<br>  kind: "llm" \| "search" \| "fetch";<br>  model: string \| null;<br>  calls: number;<br>  prompt_tokens: number;<br>  completion_tokens: number;<br>  units: number;<br>  cost_usd: number;<br>  pct_of_total: number;<br>}<br>export interface RunCostsResponse {<br>  run_id: string;<br>  total_usd: number;<br>  total_prompt_tokens: number;<br>  total_completion_tokens: number;<br>  by_provider: ProviderCostRow[];<br>}<br>```<br>Snake-case keys deliberately match the wire format — no transformation layer. | `frontend/src/types/costs.ts` (NEW) | XS | 3.2 | type contract |
| 4.3 | Create `frontend/src/lib/formatCost.ts`. Pure helpers:<br>```typescript<br>export function formatUsd(value: number): string;       // "$0.0421" / "$1.23" / "$0.00" / "—" if NaN<br>export function formatTokens(n: number): string;        // "4.3K", "1.2M", "847"<br>export function formatPct(p: number): string;           // "12.4%"<br>```<br>`formatUsd`: 4 decimals when value < 1, 2 decimals otherwise. `formatTokens`: K/M abbreviation, 1 decimal under 100. `formatPct`: 1 decimal. **All English** — no `Intl.NumberFormat({locale: "es-CO"})` (user-memory language policy: code/UI fallback strings stay English). | `frontend/src/lib/formatCost.ts` (NEW), `frontend/src/lib/formatCost.test.ts` (NEW) | S | — | §4.6 chip & table rendering |
| 4.4 | Extend `frontend/src/lib/api.ts` with the typed endpoint (if the existing pattern is one function per endpoint) OR add a thin wrapper in a new `frontend/src/lib/api/costs.ts` module. Prefer the latter to avoid cluttering `api.ts`. Function:<br>```typescript<br>export async function fetchRunCosts(runId: string, init?: RequestInit): Promise<RunCostsResponse>;<br>```<br>Use the existing `api` client (which prefixes `API_URL` and handles auth — per user-memory `api-url-rule.md`). Do **NOT** use raw `fetch("/api/...")` — that breaks in production. Make sure `...init` is spread BEFORE explicit `headers`/`body` (user-memory `fetch() options spread order`). | `frontend/src/lib/api/costs.ts` (NEW) | S | 4.2 | API_URL rule |
| 4.5 | Create `frontend/src/hooks/useRunCosts.ts`. Public API per BRD-29 §4.6.1:<br>```typescript<br>export interface UseRunCostsReturn {<br>  total: { usd: number; promptTokens: number; completionTokens: number };<br>  rows: ProviderCostRow[];<br>  isLoading: boolean;<br>  isError: boolean;<br>  source: "rest" \| "sse-patched";<br>}<br>export function useRunCosts(runId: string): UseRunCostsReturn;<br>```<br>Implementation:<br>1. `useQuery({ queryKey: ["runs", runId, "costs"], queryFn: () => fetchRunCosts(runId), staleTime: 30_000 })`.<br>2. Subscribe to the existing SSE store. Filter for `event.type === "CostIncurred"`. On each frame, call `queryClient.setQueryData<RunCostsResponse>(["runs", runId, "costs"], (prev) => patchCosts(prev, event))` — see Task 4.6 for `patchCosts`.<br>3. Track `source: "sse-patched"` after the first SSE patch; otherwise `"rest"`.<br>4. On run termination (subscribe to `event.type === "Stopped"`), call `queryClient.invalidateQueries(["runs", runId, "costs"])` once — defensive reconciliation against missed frames (AC-08).<br>5. Compute `total` and `rows` from the cached `RunCostsResponse`. If `data` is undefined (initial load), return zeros + `isLoading: true`. | `frontend/src/hooks/useRunCosts.ts` (NEW), `useRunCosts.test.ts` (NEW) | M | 4.2, 4.3, 4.4 | AC-06, AC-08 |
| 4.6 | In the same `hooks/useRunCosts.ts` module (or a sibling `hooks/_patchCosts.ts` for testability), implement `patchCosts(prev: RunCostsResponse \| undefined, event: CostIncurredEvent): RunCostsResponse`. Logic:<br>1. Start from `prev ?? emptyResponse(runId)`.<br>2. Find or insert the matching `ProviderCostRow` by `(provider, kind, model)` triple. If found: increment `calls`, `prompt_tokens`, `completion_tokens`, `units`, `cost_usd`. If not found: push a new row.<br>3. Recompute `total_usd`, totals, and `pct_of_total` for **all** rows (cheap — ≤ 10 rows).<br>4. Re-sort `by_provider` by `cost_usd` desc.<br>**Pure function** — testable without React. Unit-tested in Phase 6. | `frontend/src/hooks/useRunCosts.ts` (or `_patchCosts.ts`) | S | 4.5 | AC-06 |

### Phase 5 — Frontend UI: atoms, molecules, organism, integration (depends on Phase 4)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 5.1 | Create the atom `TotalCostChip` (`atoms/TotalCostChip.tsx`). Props: `{ totalUsd: number; tokens: number; loading?: boolean }` extending `ButtonHTMLAttributes<HTMLButtonElement>` (per user-memory `typescript-react-props.md` — **never** `[key: string]: unknown`). Render a `<button>` (the chip is clickable per BRD §4.7 — opens trace tab T1d). Visual:<br>• Inline-flex, `h-7 px-2 gap-1.5 rounded-md`, `bg-(--accent-soft) text-(--accent) hover:bg-(--accent-soft)/80 transition-colors`.<br>• Icon: `<Coins className="h-3.5 w-3.5" aria-hidden />` from lucide-react.<br>• Text: `<span className="font-mono text-xs">{formatUsd(totalUsd)} · {formatTokens(tokens)}</span>` — JetBrains Mono via the existing token class `font-mono`.<br>• Loading state: when `loading`, swap the value text for `<span className="inline-block h-3 w-12 bg-(--glass-bg) animate-pulse rounded" />`.<br>• Accessibility: `aria-label={`Cost so far: ${formatUsd(totalUsd)}, ${formatTokens(tokens)} tokens. Click to open breakdown.`}` (AC-11 — exact phrasing).<br>• Motion: `<motion.span key={totalUsd} initial={{ opacity: 0, y: -2 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>{formatUsd(totalUsd)}</motion.span>` wraps **only the numeric value** to tween on change (AC-06 "animated, no jump"). Respect `useReducedMotion()` — disable the y-translate when reduced. | `frontend/src/components/atoms/TotalCostChip.tsx` (NEW), `.test.tsx` (NEW) | S | 4.3 | AC-06, AC-11, §4.6 |
| 5.2 | Create the atom `CostBarSegment` (`atoms/CostBarSegment.tsx`). Props: `{ provider: string; value: number; total: number; color: string }`. Renders a single `<div>` with `style={{ width: `${(value/total)*100}%`, backgroundColor: color }}`, `className="h-2 first:rounded-l-full last:rounded-r-full"`. Width transitions smoothly: `transition-[width] duration-300 ease-out`. `role="presentation"` because the label is owned by the parent legend (AC-07). | `frontend/src/components/atoms/CostBarSegment.tsx` (NEW), `.test.tsx` (NEW) | XS | — | §4.6, AC-07 |
| 5.3 | Create the molecule `CostBreakdownBar` (`molecules/CostBreakdownBar.tsx`). Props: `{ rows: ProviderCostRow[] }`. Aggregate rows by `provider` (sum `cost_usd`); pick colors from a stable palette function `providerColor(provider)` keyed off `--accent`, `--warm`, and `--text-muted` for "other" — keeps the same look across themes (no hardcoded hex per the design-system rule). Render:<br>• A horizontal flex container (`h-2 w-full rounded-full bg-(--glass-bg) flex overflow-hidden`) with one `<CostBarSegment>` per provider.<br>• A legend below (`ul` with `role="list"`) — one `<li>` per provider: color swatch + provider name + `formatUsd(provider.total)` + `formatPct(provider.pct)`.<br>• **Empty state** (`rows.length === 0`): centred text "No cost recorded yet." in `text-(--text-muted)`. | `frontend/src/components/molecules/CostBreakdownBar.tsx` (NEW), `.test.tsx` (NEW) | S | 5.2 | AC-07 |
| 5.4 | Create the molecule `CostBreakdownTable` (`molecules/CostBreakdownTable.tsx`). Props: `{ rows: ProviderCostRow[]; sortBy?: "cost" \| "calls" \| "tokens" }` (default `"cost"`). Local `useState` for the active sort. Render a native `<table>` (better a11y than a flex grid for tabular data). Columns: Provider · Kind · Model · Calls · Prompt tok · Completion tok · Units · USD · %. Sticky header (`<thead className="sticky top-0 bg-(--bg-elevated)">`). Column headers are `<button>`s that toggle sort direction; current sort indicated by a chevron icon (lucide `ChevronUp`/`ChevronDown`). Tokens columns use `formatTokens`; USD uses `formatUsd`; pct uses `formatPct`. Empty model renders as em-dash `"—"`. AC-09 graceful row: when `cost_usd === 0 && pricing_source === "static"`, render USD as `"—"` (need to pass `pricing_source` — augment the `ProviderCostRow` view query to include the most common `pricing_source` per group, OR just render `"—"` whenever `cost_usd === 0` — pick the latter for simplicity since free Sources also render `"—"` then, which is honest). **Decision:** render `"—"` when `cost_usd === 0` (covers both wikipedia and pricing-miss). Document this in §6.2 below. | `frontend/src/components/molecules/CostBreakdownTable.tsx` (NEW), `.test.tsx` (NEW) | M | 4.3 | AC-04, AC-07, AC-09 |
| 5.5 | Create the organism `TraceCostPanel` (`organisms/TraceCostPanel.tsx`). Props: `{ runId: string }`. Layout:<br>```tsx<br>const { total, rows, isLoading, isError } = useRunCosts(runId);<br>if (isLoading) return <CostPanelSkeleton />;<br>if (isError)   return <CostPanelError onRetry={...} />;<br>return (<br>  <div className="flex flex-col gap-4 p-4"><br>    <header className="flex items-baseline justify-between"><br>      <h3 className="text-sm font-medium text-(--text-primary)">Cost breakdown</h3><br>      <span className="font-mono text-base text-(--accent)">{formatUsd(total.usd)}</span><br>    </header><br>    <CostBreakdownBar rows={rows} /><br>    <CostBreakdownTable rows={rows} /><br>  </div><br>);<br>```<br>`CostPanelSkeleton` and `CostPanelError` are local (not exported) sub-components — keep them in the same file. **Reuse the existing `GlassSurface`** from BRD-14's trace panel if the sibling tabs do (verify by reading one existing trace-tab body — adjust to mirror the same wrapper). | `frontend/src/components/organisms/TraceCostPanel.tsx` (NEW), `.test.tsx` (NEW) | M | 4.5, 5.3, 5.4 | AC-07, AC-09 |
| 5.6 | Register the `T1d` tab in `TracePanel.tsx`. Open `frontend/src/components/organisms/TracePanel.tsx`, find the tab strip (likely a `Tabs` component from shadcn or an array of tab descriptors). Add `{ id: "cost", label: "Cost", icon: Coins }` (verify the exact descriptor shape by reading one existing tab — e.g. T1a Events). Wire the tab body to `<TraceCostPanel runId={runId} />`. **The label is exactly "Cost"** (per BRD §4.7 ASCII layout) — single word, English. Add the new tab AFTER the existing tabs (rightmost position). | `frontend/src/components/organisms/TracePanel.tsx` (MODIFY) | S | 5.5 | AC-07, T1d state |
| 5.7 | Mount `<TotalCostChip />` in the run header. **First locate the actual file**: read `grep -r "RunHeader" frontend/src/` — BRD-29 §4.6 names it `organisms/RunHeader.tsx` but the IP-28 plan showed that BRD-28 had a similar miss (the real top-bar lives in `templates/AppShell.tsx`). For a per-run header, the actual owner is most likely `organisms/RunHeader.tsx` OR the run page's top section in `pages/RunPage.tsx`. **Verify before editing**; if the BRD path is wrong, record the corrected path in §6.2.<br>Once located: import `useRunCosts(runId)` and `TotalCostChip`. Mount the chip in the actions row (next to the existing status chips). On click, dispatch the trace-tab change via the existing `selectionStore` (verify the action name — likely `setTraceTab("cost")` or similar). If there's no such store action, add it as a minimal one-liner to `selectionStore.ts`. | `frontend/src/components/organisms/RunHeader.tsx` (or actual run-page header — verify) (MODIFY); possibly `selectionStore.ts` (MODIFY) | S | 5.1, 5.6 | AC-06, AC-11 |
| 5.8 | Re-export new atoms / molecules / organism from their respective barrels (`atoms/index.ts`, `molecules/index.ts`, `organisms/index.ts`) so other files can import via barrel. Follow the existing pattern (one line per export). | `frontend/src/components/atoms/index.ts`, `molecules/index.ts`, `organisms/index.ts` (MODIFY) | XS | 5.1–5.5 | conventions |
| 5.9 | ESLint sanity: `npm run lint` from `frontend/`. Verify `import/no-restricted-paths` is clean — atoms import nothing from molecules/organisms; molecules don't import organisms; the new organism imports only molecules + atoms + hooks + shadcn ui. The `TraceCostPanel` import of `useRunCosts` is fine (hooks are layering-neutral). | n/a | XS | 5.8 | atomic-layering rule |

### Phase 6 — Tests (depends on Phases 2, 3, 5; some sub-tasks parallel)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 6.1 | `backend/tests/test_llm_pricing.py` (NEW — pure unit). Cover `compute_cost`:<br>• Litellm path: stub `litellm.completion_cost` to return `0.0123` → `(0.0123, "litellm")`.<br>• Fallback path: stub to return `None`, pass a `raw_completion` mock with `usage.prompt_tokens=1000, completion_tokens=500`, model `"claude-sonnet-4-5"` → assert `(positive_float, "fallback")` and the math matches the table.<br>• Static path: stub to return `None`, pass unknown model → `(0.0, "static")`.<br>• Missing-usage path: `raw_completion` without `usage` attribute → `(0.0, "static")`.<br>• Exception path: stub to raise → falls back without bubbling.<br>**No async, no DB** — runs in < 50 ms. | `backend/tests/test_llm_pricing.py` (NEW) | S | 1.4 | AC-09; R-02 |
| 6.2 | `backend/tests/test_sources_pricing.py` (NEW — pure unit). Cover all three helpers: `tavily_cost("basic")` → `(1, 0.008, 0.008)`; `tavily_cost("advanced")` → `(2, 0.008, 0.016)`; `tavily_cost("unknown")` → `(1, 0.008, 0.008)`; `wikipedia_cost()` → `(1, 0.0, 0.0)`; `free_source_cost()` → `(1, 0.0, 0.0)`. Override `settings.tavily_usd_per_credit` via `monkeypatch` to verify the multiplication scales (e.g. `0.01` → `(2, 0.01, 0.02)`). | `backend/tests/test_sources_pricing.py` (NEW) | XS | 1.5, 1.6 | AC-02 |
| 6.3 | `backend/tests/test_llm_client_cost.py` (NEW). Patterns from the existing `tests/conftest.py` + user-memory `pytest-hang-diagnosis.md` (monkeypatch the **consumer** binding, not just the source module):<br>• Stub `instructor.from_litellm(...).chat.completions.create_with_completion` to return `(model_instance, fake_raw)` where `fake_raw.usage.prompt_tokens=100, completion_tokens=50`.<br>• Set `current_run_id`, `current_task_name="CLASSIFYING"`, `current_emitter=collector.append`.<br>• Invoke `client.call(role=CLASSIFIER, messages=[...], response_model=DummyModel)`.<br>• Assert exactly one `CostIncurredEvent` emitted with `kind="llm"`, `model=<resolved>`, `task_name="CLASSIFYING"`, `prompt_tokens=100`, `completion_tokens=50`, `pricing_source="litellm"`, `latency_ms >= 0`.<br>• Failure variant: stub raises → assert NO event emitted, exception bubbles (AC-02 idempotency).<br>• Missing-emitter variant: `current_emitter=None` → call succeeds, no event, no exception. | `backend/tests/test_llm_client_cost.py` (NEW) | M | 2.2 | AC-01, AC-02, AC-09 |
| 6.4 | `backend/tests/test_sources_tavily_cost.py` (NEW). Stub `AsyncTavilyClient.search` to return a fixed response; collect events via an in-test emitter set on `current_emitter`. Assert:<br>• 1 `search` call → 1 `CostIncurredEvent` with `provider="tavily"`, `kind="search"`, `units=2` (advanced default), `cost_usd≈0.016`, `pricing_source="static"`.<br>• Same for `extract` → `kind="fetch"`, `units=2`.<br>• Failure variant: stub raises → 0 events emitted. | `backend/tests/test_sources_tavily_cost.py` (NEW) | S | 2.5 | AC-02 |
| 6.5 | `backend/tests/test_sources_wikipedia_cost.py` (NEW). Single test: 2 Wikipedia searches → 2 `CostIncurredEvent`s with `cost_usd=0.0`, `units=1`, `provider="wikipedia"`. | `backend/tests/test_sources_wikipedia_cost.py` (NEW) | XS | 2.6 | AC-03 |
| 6.6 | `backend/tests/test_view_run_costs.py` (NEW — uses `pytest-postgresql`). Migrate to head; seed via `EventService.append_event` three events for one `run_id` (2 LLM with different models, 1 Tavily). Query `SELECT * FROM run_costs WHERE run_id=:id ORDER BY cost_usd DESC` via raw `text()`. Assert: 3 rows (or 2 if the same `(provider, kind, model)` collapses — adjust based on the grouping in BRD §4.2; with 2 different models we expect 3 rows: claude+claude-haiku+tavily). Assert SUM of `cost_usd` equals the sum of the seeded events. **Malformed-row variant:** seed a row with `payload={"type":"CostIncurred", "cost_usd":"not-a-number", ...}` via raw insert; assert the view's `COALESCE(SUM((payload->>'cost_usd')::numeric), 0)` either skips the row or fails predictably — record the actual behaviour in §6.2 and adjust the test to assert it (this confirms R-06). | `backend/tests/test_view_run_costs.py` (NEW) | M | 3.1 | AC-04, AC-08; R-06 |
| 6.7 | `backend/tests/test_routes_run_costs.py` (NEW — integration via `httpx.AsyncClient` against the FastAPI app). Setup: create a user, create a run owned by that user, seed 7 LLM + 4 Tavily events via `EventService`. Tests:<br>• Owner GET → 200, `total_usd ≈ 0.0981`, 3 rows sorted desc by USD, every `pct_of_total` ∈ [0, 100], sum of pcts ≈ 100 ±0.5 (AC-04).<br>• Non-owner GET → 404, response body does NOT contain `total_usd` (AC-05).<br>• Unauthenticated GET → 401.<br>• Empty run (no events) → 200, `total_usd=0.0`, `by_provider=[]`, no division-by-zero error. | `backend/tests/test_routes_run_costs.py` (NEW) | M | 3.2, 3.3 | AC-04, AC-05, AC-08 |
| 6.8 | `frontend/src/lib/formatCost.test.ts` (NEW). Table-driven tests:<br>• `formatUsd(0.0421)` → `"$0.0421"`; `formatUsd(1.234)` → `"$1.23"`; `formatUsd(0)` → `"$0.00"`; `formatUsd(NaN)` → `"—"`.<br>• `formatTokens(847)` → `"847"`; `formatTokens(4300)` → `"4.3K"`; `formatTokens(1_200_000)` → `"1.2M"`; `formatTokens(0)` → `"0"`.<br>• `formatPct(12.4)` → `"12.4%"`; `formatPct(100)` → `"100.0%"`. | `frontend/src/lib/formatCost.test.ts` (NEW) | S | 4.3 | render correctness |
| 6.9 | `frontend/src/hooks/useRunCosts.test.ts` (NEW). `renderHook` with a QueryClientProvider + a mock SSE store. Tests:<br>• Initial: MSW returns the canned `RunCostsResponse` → `total.usd` matches, `source === "rest"`.<br>• Patch: emit a `CostIncurred` event via the SSE store mock → `total.usd` increases by the event's `cost_usd` within one `act`, `source === "sse-patched"`, MSW request count is still 1 (AC-06 — no re-fetch).<br>• Stopped event: emit `Stopped` → assert `queryClient.invalidateQueries` was called once for the cost query.<br>• Unit-test `patchCosts` directly with table-driven inputs (insert new row, increment existing, recompute totals/pct/sort). | `frontend/src/hooks/useRunCosts.test.ts` (NEW) | M | 4.5, 4.6 | AC-06, AC-08 |
| 6.10 | `frontend/src/components/atoms/TotalCostChip.test.tsx` (NEW). Tests:<br>• Renders `formatUsd` + `formatTokens` strings.<br>• `aria-label` matches AC-11 phrasing.<br>• Loading state renders the pulse placeholder.<br>• Click handler fires.<br>• jest-axe → zero violations in dark theme AND light theme (set `document.documentElement.dataset.theme` between assertions — same pattern as IP-28 §4.6). | `frontend/src/components/atoms/TotalCostChip.test.tsx` (NEW) | S | 5.1 | AC-06, AC-11 |
| 6.11 | `frontend/src/components/atoms/CostBarSegment.test.tsx` (NEW). Tests: width is `(value/total)*100`%; `role="presentation"`; renders nothing when `total === 0` (avoid `NaN%`). | `frontend/src/components/atoms/CostBarSegment.test.tsx` (NEW) | XS | 5.2 | render correctness |
| 6.12 | `frontend/src/components/molecules/CostBreakdownBar.test.tsx` (NEW). Tests: 3-provider input → 3 segments + 3 legend items in the same order; segment widths sum to ≤100%; empty state renders the "No cost recorded yet." copy when `rows=[]`. | `frontend/src/components/molecules/CostBreakdownBar.test.tsx` (NEW) | S | 5.3 | empty-state, ordering |
| 6.13 | `frontend/src/components/molecules/CostBreakdownTable.test.tsx` (NEW). Tests:<br>• Renders all columns from BRD §4.6.<br>• Clicking the "USD" header re-sorts (ASC → DESC → ASC).<br>• Renders `"—"` for `cost_usd === 0` rows (AC-09).<br>• Renders `"—"` for null `model`.<br>• Keyboard navigation: Tab traverses sortable headers; Enter activates sort (AC-07).<br>• jest-axe → zero violations. | `frontend/src/components/molecules/CostBreakdownTable.test.tsx` (NEW) | M | 5.4 | AC-07, AC-09, AC-11 |
| 6.14 | `frontend/src/components/organisms/TraceCostPanel.test.tsx` (NEW). Tests via MSW:<br>• Loading state visible while query is pending.<br>• Error state visible on 500 response; retry button re-fetches.<br>• Successful state: header total, breakdown bar, and table all render with correct values.<br>• jest-axe in BOTH themes. | `frontend/src/components/organisms/TraceCostPanel.test.tsx` (NEW) | M | 5.5 | AC-07, AC-09, AC-11 |
| 6.15 | `frontend/src/components/organisms/TracePanel.test.tsx` (MODIFY existing if present; otherwise NEW). Add ONE assertion: the "Cost" tab is present in the tab strip; clicking it renders `TraceCostPanel`. **Do not** duplicate `TraceCostPanel`'s tests — just confirm the wiring. | `frontend/src/components/organisms/TracePanel.test.tsx` (MODIFY or NEW) | S | 5.6 | T1d wiring |
| 6.16 | Run header test addition. Extend the test file of whichever component Task 5.7 modified (`RunHeader.test.tsx` or `RunPage.test.tsx`): assert `TotalCostChip` is present; click it → assert `selectionStore.traceTab` becomes `"cost"`. | `frontend/src/components/organisms/RunHeader.test.tsx` (MODIFY) | S | 5.7 | AC-06, AC-11 |
| 6.17 | Full-stack sanity: run `cd backend && .\.venv\Scripts\python.exe -m pytest -q tests/` → all green (existing 100+ tests must still pass — no regressions). Run `cd frontend && npm test -- --run` → all green. Run `cd frontend && npx tsc --noEmit` → no errors (validates the regenerated `types/events.ts`). Run `cd backend && .\.venv\Scripts\python.exe -m ruff check . && .\.venv\Scripts\python.exe -m pyright` → clean. | n/a | S | all previous | regression gate |

### Phase 7 — Docs & memory bank (depends on Phase 6 green)

| # | Task | File(s) | Effort | Depends on |
|---|------|---------|--------|------------|
| 7.1 | Append **RF-20** to [docs/understanding-phase/requirement-understanding.md](../../understanding-phase/requirement-understanding.md). Use the exact wording from BRD-29 §2 (the RF-20 row). Insert immediately after RF-19. Update any "RF-XX (19 total)" counter to 20. | `docs/understanding-phase/requirement-understanding.md` (MODIFY) | S | 6.17 |
| 7.2 | Append **§6 "Cost & token tracking"** to [docs/technical-phase/ai-services.md](../../technical-phase/ai-services.md). Subsections: §6.1 Event shape (`CostIncurredEvent` field-by-field); §6.2 Pricing strategy (hybrid order: litellm → fallback table → static-zero; how to update the table); §6.3 Environment variables (`TAVILY_USD_PER_CREDIT`); §6.4 Instrumentation contract (which call sites emit, what they must set on `current_*` contextvars). One-paragraph each — link to BRD-29 for the rationale. | `docs/technical-phase/ai-services.md` (MODIFY) | M | 6.17 |
| 7.3 | Add the **T1d "Trace · cost breakdown"** panel state to [docs/understanding-phase/ui-prototype.md](../../understanding-phase/ui-prototype.md) §3 (TracePanel states T1a–T5). Mirror the structure of an existing T-state entry. Also list `TotalCostChip` under the run-header atoms inventory in whichever §1 / §3 section enumerates header chips. | `docs/understanding-phase/ui-prototype.md` (MODIFY) | S | 6.17 |
| 7.4 | Update `.github/memory-bank/indices/knowledge-base-index.md` to register: `CostIncurredEvent`, `current_run_id` / `current_task_name` / `current_emitter`, `app/llm/pricing.py`, `app/sources/pricing.py`, `app/sources/_cost.py`, `run_costs` view, `GET /api/runs/{id}/costs` endpoint, `useRunCosts` hook, `TotalCostChip` atom, `CostBreakdownBar` / `CostBreakdownTable` molecules, `TraceCostPanel` organism, T1d panel state. | `.github/memory-bank/indices/knowledge-base-index.md` (MODIFY) | S | 6.17 |
| 7.5 | Append D1–D5 to `.github/memory-bank/logs/decisions-history.md`: D1 view-not-MV with promotion path; D2 hybrid pricing rationale; D3 Tavily static price table + env override; D4 full-stack scope (revised mid-plan to include FE); D5 contextvar plumbing pattern. Date 2026-05-29, author "Orchestrator Agent for BRD-29". | `.github/memory-bank/logs/decisions-history.md` (MODIFY) | S | 6.17 |
| 7.6 | If any non-obvious gotcha surfaced during implementation (e.g. instructor API form had to fall back from `create_with_completion`, or `pytest-postgresql` had a config issue with the view), record a one-paragraph lesson in `.github/memory-bank/logs/lessons-learned.md`. Otherwise skip. | `.github/memory-bank/logs/lessons-learned.md` (optional) | XS | 6.17 |

---

## 4. File Modifications

### New files
```
backend/app/llm/context.py
backend/app/llm/pricing.py
backend/app/sources/pricing.py
backend/app/sources/_cost.py
backend/app/routes/costs.py
backend/alembic/versions/004_run_costs_view.py
backend/tests/test_llm_pricing.py
backend/tests/test_sources_pricing.py
backend/tests/test_llm_client_cost.py
backend/tests/test_sources_tavily_cost.py
backend/tests/test_sources_wikipedia_cost.py
backend/tests/test_view_run_costs.py
backend/tests/test_routes_run_costs.py
frontend/src/types/costs.ts
frontend/src/lib/formatCost.ts
frontend/src/lib/formatCost.test.ts
frontend/src/lib/api/costs.ts
frontend/src/hooks/useRunCosts.ts
frontend/src/hooks/useRunCosts.test.ts
frontend/src/components/atoms/TotalCostChip.tsx
frontend/src/components/atoms/TotalCostChip.test.tsx
frontend/src/components/atoms/CostBarSegment.tsx
frontend/src/components/atoms/CostBarSegment.test.tsx
frontend/src/components/molecules/CostBreakdownBar.tsx
frontend/src/components/molecules/CostBreakdownBar.test.tsx
frontend/src/components/molecules/CostBreakdownTable.tsx
frontend/src/components/molecules/CostBreakdownTable.test.tsx
frontend/src/components/organisms/TraceCostPanel.tsx
frontend/src/components/organisms/TraceCostPanel.test.tsx
docs/implementation-phase/implementation-plans/IP-29-cost-and-token-tracking.md   (this file)
```

### Modified files
```
backend/app/domain/enums.py                                  (add EventType.COST_INCURRED)
backend/app/domain/events.py                                 (add CostIncurredEvent + union + EVENT_TYPE_MAP)
backend/app/llm/client.py                                    (use create_with_completion + emit cost event)
backend/app/agent/runner.py                                  (set current_run_id + current_emitter)
backend/app/agent/orchestrator.py                            (_with_task helper + per-transition wrap)
backend/app/sources/tavily.py                                (wrap search + extract)
backend/app/sources/wikipedia.py                             (wrap search)
backend/app/sources/semantic_scholar.py                      (wrap search/fetch)
backend/app/sources/openalex.py                              (wrap search/fetch)
backend/app/config.py                                        (tavily_usd_per_credit)
backend/app/main.py                                          (register costs router)
frontend/src/types/events.ts                                 (REGEN — automated, do not hand-edit)
frontend/src/components/organisms/TracePanel.tsx             (register T1d tab)
frontend/src/components/organisms/RunHeader.tsx              (mount TotalCostChip — verify file path in Task 5.7)
frontend/src/components/atoms/index.ts                       (barrel export)
frontend/src/components/molecules/index.ts                   (barrel export)
frontend/src/components/organisms/index.ts                   (barrel export)
frontend/src/store/selectionStore.ts                         (only if Task 5.7 needs a new traceTab action)
docs/understanding-phase/requirement-understanding.md        (RF-20)
docs/understanding-phase/ui-prototype.md                     (T1d + TotalCostChip)
docs/technical-phase/ai-services.md                          (§6)
.github/memory-bank/indices/knowledge-base-index.md
.github/memory-bank/logs/decisions-history.md
```

### Conditionally modified
```
.github/memory-bank/logs/lessons-learned.md                  (only if a non-obvious gotcha surfaces)
backend/app/llm/client.py                                    (fallback to alternate instructor API if Task 2.1 spike fails)
```

### Out of scope (do not touch)
```
backend/app/services/event_service.py                        (no change — reused as-is)
backend/app/sse/stream.py                                    (no change — all events stream automatically)
backend/app/llm/embeddings.py                                (out of scope per BRD §10)
frontend/src/hooks/useRunSSE.ts (or equivalent)              (consumed read-only by useRunCosts)
```

---

## 5. Sequencing & Dependencies

```
Phase 1 (foundations — files independent of each other)
  ├── 1.1 EventType enum ─┐
  ├── 1.2 Pydantic event ─┤
  ├── 1.3 contextvars ────┤
  ├── 1.4 LLM pricing ────┤
  ├── 1.5 settings ───────┤
  ├── 1.6 source pricing ─┤
  └── 1.7 cost emit helper┴──┐
                              ├──> Phase 2 (instrumentation backend)
                              │    ├── 2.1 spike (instructor API)
                              │    ├── 2.2 client.py::call
                              │    ├── 2.3 runner contextvars
                              │    ├── 2.4 orchestrator task_name
                              │    └── 2.5–2.7 source wrappers
                              │
                              └──> Phase 3 (read path — parallel with Phase 2)
                                   ├── 3.1 Alembic view
                                   ├── 3.2 endpoint
                                   └── 3.3 router register

Phase 4 (FE types + data — depends on Phase 1 events + Phase 3 endpoint)
  ├── 4.1 regen types ─────┐
  ├── 4.2 costs.ts ────────┤
  ├── 4.3 formatCost ──────┤
  ├── 4.4 api client ──────┤
  ├── 4.5 useRunCosts ─────┤
  └── 4.6 patchCosts ──────┴──> Phase 5 (UI)
                                ├── 5.1 TotalCostChip atom
                                ├── 5.2 CostBarSegment atom
                                ├── 5.3 CostBreakdownBar molecule
                                ├── 5.4 CostBreakdownTable molecule
                                ├── 5.5 TraceCostPanel organism
                                ├── 5.6 register T1d tab
                                ├── 5.7 mount TotalCostChip in run header
                                ├── 5.8 barrels
                                └── 5.9 lint

Phase 6 (tests — most parallel, fan-out)
  ├── BE pure: 6.1, 6.2 (parallel, no deps beyond Phase 1)
  ├── BE integration: 6.3, 6.4, 6.5 (depend on Phase 2)
  ├── BE DB: 6.6, 6.7 (depend on Phase 3)
  ├── FE pure: 6.8 (depends on Phase 4)
  ├── FE hook: 6.9 (depends on Phase 4)
  ├── FE components: 6.10–6.14 (depend on Phase 5)
  ├── FE wiring: 6.15, 6.16 (depend on Phase 5)
  └── 6.17 full regression gate (depends on all of 6.1–6.16)

Phase 7 (docs — depends on Phase 6 green)
  └── 7.1–7.6 (independent of each other, parallelizable)
```

**Critical path:** Phase 1 → Phase 2.2 (`client.py::call`) → Phase 6.3 → Phase 6.17. The frontend half (Phases 4–5) can start as soon as Phase 1 task 1.2 (the Pydantic event) and Phase 3 task 3.2 (the endpoint) are merged — a second pair can take Phases 4–5 in parallel with backend tests.

---

## 6. Acceptance Criteria Coverage

| BRD AC | Covered by |
|--------|-----------|
| AC-01 every LLM call emits cost event | 1.1, 1.2, 1.4, 2.2, 2.3, 2.4, 6.1, 6.3 |
| AC-02 Tavily emits per-call, idempotent on retry | 1.5, 1.6, 1.7, 2.5, 6.2, 6.4 |
| AC-03 Wikipedia / free Sources record zero cost | 1.6, 1.7, 2.6, 2.7, 6.5 |
| AC-04 endpoint returns grouped totals | 3.1, 3.2, 6.6, 6.7 |
| AC-05 endpoint rejects non-owners | 3.2 (ownership check), 6.7 |
| AC-06 chip updates live | 4.5, 4.6, 5.1, 5.7, 6.9, 6.10 |
| AC-07 trace panel shows correct breakdown | 5.3, 5.4, 5.5, 5.6, 6.12, 6.13, 6.14, 6.15 |
| AC-08 read determinism on re-open | 1.2 (`extra="allow"` + price captured at emit), 6.6 (view aggregate stable), 4.5 (invalidate on Stopped) |
| AC-09 graceful pricing miss | 1.4 (static fallback), 5.4 (`"—"` rendering), 6.1, 6.13 |
| AC-10 fork preserves ledger | Inherits from existing fork semantics (events copied as-is) — no new work, but **add an assertion** to whichever fork test already exists (`tests/test_routes_runs_fork.py` or similar — verify in Phase 6) that copies a parent's `CostIncurred` events. Treat as part of 6.7 if the test infrastructure allows. |
| AC-11 a11y both themes | 6.10, 6.13, 6.14 (jest-axe with `data-theme` set to dark and light) |

Every BRD-29 AC maps to ≥ 1 implementation task **and** ≥ 1 test. AC-10 reuses the existing fork mechanism — verified by extending an existing test rather than adding new code paths.

---

## 7. Risk Re-Assessment (vs BRD-29 §9)

| ID | BRD risk | Plan-time view | Residual action |
|----|----------|----------------|-----------------|
| R-01 instructor `create_with_completion` API drift | Task 2.1 spike de-risks this in 5 min before refactoring; fallback path documented. | Pin `instructor` version in `pyproject.toml`; record actual call form in `client.py` docstring. |
| R-02 litellm pricing miss | Hybrid fallback covers V1 (Anthropic). Static-zero is the floor — tokens still recorded. | 6.1 tests the three-way branch; 5.4 renders `"—"` for zero cost. |
| R-03 contextvars in child tasks | Single-worker uvicorn + asyncio inheritance covers default path. | 6.3 indirectly tests by setting contextvars then invoking `call()`. If a Source ever creates a background task, the helper at `_cost.py` must be called from the SAME task — document this in `ai-services.md §6.4`. |
| R-04 SSE drift vs REST | 4.5 invalidates query on `Stopped` event. | 6.9 explicitly tests the invalidation. |
| R-05 partial-index write overhead | Cost events are ≤ ~50 per run; partial index only indexes `CostIncurred` rows. | No specific test — overhead validated during the manual smoke (Phase 6.17). |
| R-06 cast failures on bad payloads | Pydantic v2 validates at emit time. | 6.6 includes a malformed-row variant to assert `COALESCE` swallows it gracefully. |
| R-07 wrong Tavily price default | Surfaced as env var; price captured per-event so historical totals are stable. | 7.2 documents the env var; 7.5 records the rationale in decisions history. |
| R-08 visual noise in run header | `--accent-soft` subdued styling; opt-in tab. | 6.10/6.14 jest-axe in both themes verifies no contrast/clutter regression. |

**No new risks identified at plan time.** Plan-time additions:
- **R-09 (new) — `RunHeader.tsx` may not exist.** BRD-29 §4.6 names this file, but BRD-28's IP showed that the real top-bar in some contexts lives in `templates/AppShell.tsx`. **Mitigation:** Task 5.7 verifies the actual file path before editing; if the BRD path is wrong, the corrected path is recorded in this plan's §6.2 of the decisions-history log (not in this document — handled via memory bank update 7.5).

---

## 8. Out of Scope (re-confirmed from BRD-29 §10)

- Cross-run dashboards (cost per day / user / model).
- USD-denominated soft budgets (auto-stop on $X exceeded).
- Per-user billing or Stripe.
- Live alerting on cost anomalies.
- Cost projections ("at current rate this run will reach $Y").
- Embedding-call cost tracking (`app/llm/embeddings.py` untouched).
- Cost capture for failed tenacity retries.
- Anthropic prompt-caching discount accounting (capture cache fields via `extra="allow"` only; no discount math).
- Materialised view (`run_costs` is a regular view in V1).

---

## 9. Definition of Done

- [ ] All Phase 1–7 checklist items complete.
- [ ] `cd backend && .\.venv\Scripts\python.exe -m ruff check .` clean.
- [ ] `cd backend && .\.venv\Scripts\python.exe -m pyright` clean (strict mode).
- [ ] `cd backend && .\.venv\Scripts\python.exe -m pytest -q tests/` — every new test green; pre-existing 100+ tests still green.
- [ ] `cd frontend && npm run lint` clean.
- [ ] `cd frontend && npx tsc --noEmit` clean (validates the regenerated `types/events.ts`).
- [ ] `cd frontend && npm test -- --run` — every new test green; pre-existing tests still green.
- [ ] Coverage on new backend modules ≥ 85 % (pure-pricing modules ≥ 90 %). Coverage on new frontend modules ≥ 80 % (per copilot-instructions §7.7). `formatCost.ts` and `patchCosts` target ≥ 90 % (pure logic).
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` is idempotent (view dropped/recreated cleanly).
- [ ] Manual smoke against a real run: `psql -c "SELECT * FROM run_costs WHERE run_id='<id>';"` shows non-zero `cost_usd` for Anthropic and Tavily; `curl -H "Authorization: Bearer <jwt>" .../api/runs/<id>/costs` returns matching totals; the run-page UI shows the live-updating `TotalCostChip` and the `T1d` tab renders the breakdown.
- [ ] BRD-29 ACs 1–11 verified — ten via automated tests, one (AC-06 live animation) via a short screen recording attached to the PR.
- [ ] RF-20 added to [requirement-understanding.md](../../understanding-phase/requirement-understanding.md); §6 added to [ai-services.md](../../technical-phase/ai-services.md); T1d + chip added to [ui-prototype.md](../../understanding-phase/ui-prototype.md); knowledge-base index and decisions-history updated.
- [ ] No regressions to existing event types, FSM transitions, fork/resume semantics, SSE protocol, or auth flow.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-29 | Orchestrator Agent | Initial plan derived from BRD-29 v1.0 (awaiting F2 Auditor) |
