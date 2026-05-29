# BRD-29: Per-Run Cost & Token Tracking with Trace Panel

**Document ID:** BRD-29
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-29
**Implementation Order:** 29 of N
**Assumes shipped:** BRD-10 (SSE), BRD-14 (trace panel), BRD-19 (agent runner), BRD-25 (three-lane research flow), ai-services.md §1 (LLM client), the `events` append-only table.

---

## 1. Executive Summary

Novum today emits ~44 event types into an append-only `events` table that is replayed deterministically on every read (`read_determinism` per copilot-instructions §3.4). The agent loop calls external billable services in exactly two places: **(a)** every LLM round-trip goes through `backend/app/llm/client.py::call` (mandated by ai-services.md §1.3 — no direct litellm calls anywhere else), and **(b)** every external knowledge fetch goes through a `Source` plugin under `backend/app/sources/*` (Tavily, Wikipedia, Semantic Scholar, OpenAlex). Despite this discipline, **the platform currently has zero visibility into how much each question costs in USD, how many tokens it burned, which model contributed which fraction, and which Source ate which fraction of Tavily credits.** The only nearby signal is `RunState.tokens_used_estimate` — a coarse, model-agnostic counter that does not map to money, does not distinguish prompt vs completion tokens, and is not persisted as an event so it cannot be reconstructed after a fork or resume.

BRD-29 introduces an **append-only, per-call cost ledger** materialised as a new `CostIncurred` event type. Each external billable call (one per LLM round, one per Source `search`/`fetch`) emits exactly one `CostIncurred` event with: `provider`, `kind` (`llm`/`search`/`fetch`), `model` (LLM only), `task_name` (the FSM state that triggered the call, e.g. `PLANNING`, `JUDGING`), `prompt_tokens`, `completion_tokens`, `units` (search credits for non-LLM providers), `unit_cost_usd`, `cost_usd`, `latency_ms`, and `pricing_source` (`litellm` | `fallback` | `static`). Pricing is **hybrid**: for LLMs we call `litellm.completion_cost(completion_response=raw)` (canonical, kept up to date by upstream) and fall back to a hard-coded table in `backend/app/llm/pricing.py` when litellm returns `None` (e.g. brand-new model variants). For Sources we use a static table keyed on the provider's billable unit (Tavily: 1 credit for `basic` search, 2 for `advanced`, multiplied by `settings.tavily_usd_per_credit`; Wikipedia/Semantic Scholar/OpenAlex: free → `cost_usd=0.0`).

The **read path is two layers**: a Postgres **regular view** `run_costs` (not materialised — we have ≤ ~50 cost events per run, so the aggregation is cheap on every query) plus a partial index `ix_events_cost_provider` on `events ((payload->>'provider')) WHERE type = 'CostIncurred'`. A new REST endpoint `GET /api/runs/{run_id}/costs` returns a structured breakdown (total USD + per-provider × per-kind × per-model rows), and the existing SSE stream continues to emit every event including `CostIncurred` so the frontend can update incrementally without polling.

**Frontend:** a new **trace-panel tab** — `T1d` *Trace · cost breakdown* — surfaces the data live during and after the run. It displays a header chip with the running **total USD** (animated counter, ticks on every `CostIncurred` event over SSE), a stacked **per-provider bar** (Anthropic vs Tavily vs free Sources), and a sortable table grouped by provider → kind → model showing `calls`, `prompt_tokens`, `completion_tokens`, `units`, `cost_usd`, `% of total`. The panel respects the existing trace-panel scaffolding (BRD-14): same `GlassSurface`, same `--accent` tokens, same Motion v12 animations, no new design tokens introduced. A small **TotalCostChip** atom mirrors the running total in the run-header so it is visible without opening the trace panel — consistent with RF-13 (trust surfaces must be permanently visible, not hidden behind tabs).

This BRD is fully **additive**: the events table schema is unchanged (the new event ships inside the existing `payload JSONB` with `extra="allow"`), no event type is removed or renamed, no existing endpoint changes, no migration of historical data is required (old runs simply show `total_usd = 0.0` because they have no `CostIncurred` events), and no impact on the agent FSM, the three plugin seams, the `stop_reason` enum, the confidence formula, or read determinism (the events are persisted and replayed like any other). The hybrid pricing strategy keeps cost current without forcing a PR every time Anthropic re-prices.

Binding success metrics in §10. Expected outcome: every run gets an accurate USD/token breakdown, the trace panel surfaces it live, total instrumentation overhead < 5 ms per LLM call and < 1 ms per Source call.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| **RF-20 (NEW)** | **Per-call cost & token transparency.** Every external billable call MUST emit one append-only `CostIncurred` event recording provider, kind, model, task name, tokens, units, USD cost, latency, and the source of the price. Per-run totals MUST be derivable purely from the event log (no out-of-band sidecar). The UI MUST surface the running total in real time. | **Complete.** New event type + view + endpoint + trace-panel tab + header chip. |
| RF-03 | Event log is append-only and the sole source of truth | **Preserved.** `CostIncurred` is appended like any other event; the view is a read-only projection. No mutation, no deletion. |
| RF-04 | Source heterogeneity (multiple Source plugins) | **Preserved.** Each Source emits its own `CostIncurred` per call; the breakdown surfaces heterogeneity directly. |
| RF-05 | Single-server | **Preserved.** No distributed coordination; the view runs in the same Postgres. |
| RF-08 | SSE with `Last-Event-ID` resume | **Preserved & leveraged.** `CostIncurred` events stream like any other event; the trace panel reconnects via `Last-Event-ID` and replays the cost stream without gaps. |
| RF-11 | Read determinism — reopening a run shows identical output | **Preserved.** Pricing is captured **at emit time** and stored in the event payload. Subsequent reads never recompute, even if litellm's pricing DB shifts. |
| RF-13 | UI surfaces every trust guarantee | **Strengthened.** Cost is itself a trust signal (cheap honest stops are visibly preferable to expensive runaway loops). The header chip + trace tab make the cost permanently visible. |
| RF-15 | Schema evolution via `extra="allow"` + optional keys | **Preserved.** The new event uses `extra="allow"` on its Pydantic model; older event logs (no `CostIncurred`) parse without error and yield `total_usd = 0.0`. |
| RF-16 | Graceful degradation | **Preserved.** If litellm fails to price a model, fallback table is used; if the fallback is also missing, `cost_usd = 0.0` is recorded with `pricing_source = "static"` and a `prompt_tokens/completion_tokens` count is still preserved so the user sees token volume even when USD is unknown. The endpoint returns the partial breakdown without failing. |

No existing RF is amended. No event type is removed. The `stop_reason` enum is untouched. The confidence formula `min(S, J)` (RF-12) is untouched.

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-10 (SSE) | `CostIncurred` events stream over the existing SSE channel; trace panel reuses the connection. |
| BRD-14 (trace panel) | The new `T1d` tab plugs into the existing trace-panel tab strip; no new panel scaffolding. |
| BRD-19 (agent runner) | `runner._supervised_run` is where we set the `current_run_id` / `current_emitter` contextvars. |
| ai-services.md §1.3 | The single `app/llm/client.py::call` chokepoint is the LLM instrumentation seam. |

No downstream BRD blocks on this one. It can ship independently of BRD-26 (meta-judge) and BRD-27 (service health).

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  alembic/
    versions/
      004_run_costs_view.py                    # NEW (revision after current head)
  app/
    config.py                                  # MODIFY: add tavily_usd_per_credit
    domain/
      enums.py                                 # MODIFY: add EventType.COST_INCURRED
      events.py                                # MODIFY: add CostIncurredEvent + register
    llm/
      client.py                                # MODIFY: use create_with_completion, emit event
      context.py                               # NEW: contextvars (run_id, task_name, emitter)
      pricing.py                               # NEW: compute_cost(model, raw_completion)
    sources/
      _cost.py                                 # NEW: _emit_source_cost(...) helper
      pricing.py                               # NEW: tavily_cost(), wikipedia_cost(), stubs
      tavily.py                                # MODIFY: wrap search() + extract()
      wikipedia.py                             # MODIFY: emit zero-cost event
      semantic_scholar.py                      # MODIFY: emit zero-cost event
      openalex.py                              # MODIFY: emit zero-cost event
    agent/
      runner.py                                # MODIFY: set current_run_id + current_emitter
      orchestrator.py                          # MODIFY: set current_task_name per FSM transition
    routes/
      costs.py                                 # NEW: GET /api/runs/{run_id}/costs
    main.py                                    # MODIFY: register costs router
  tests/
    test_llm_client_cost.py                    # NEW
    test_sources_tavily_cost.py                # NEW
    test_sources_wikipedia_cost.py             # NEW
    test_routes_run_costs.py                   # NEW
    test_view_run_costs.py                     # NEW (pytest-postgresql)

frontend/
  src/
    types/
      events.ts                                # REGEN via scripts/export_types.py
    lib/
      formatCost.ts                            # NEW: USD + token formatters
      formatCost.test.ts                       # NEW
    hooks/
      useRunCosts.ts                           # NEW: TanStack Query + live SSE patch
      useRunCosts.test.ts                      # NEW
    components/
      atoms/
        TotalCostChip.tsx                      # NEW: header chip ($0.0421 · 4.3K tok)
        TotalCostChip.test.tsx                 # NEW
        CostBarSegment.tsx                     # NEW: stacked-bar segment
        CostBarSegment.test.tsx                # NEW
      molecules/
        CostBreakdownBar.tsx                   # NEW: stacked bar (per provider)
        CostBreakdownBar.test.tsx              # NEW
        CostBreakdownTable.tsx                 # NEW: sortable table
        CostBreakdownTable.test.tsx            # NEW
      organisms/
        TraceCostPanel.tsx                     # NEW: T1d tab body
        TraceCostPanel.test.tsx                # NEW
        TracePanel.tsx                         # MODIFY: register T1d tab
        RunHeader.tsx                          # MODIFY: mount <TotalCostChip />

docs/
  understanding-phase/
    requirement-understanding.md               # MODIFY: add RF-20
    ui-prototype.md                            # MODIFY: add T1d state + TotalCostChip in §3
  technical-phase/
    ai-services.md                             # MODIFY: append §6 "Cost & token tracking"

.github/
  memory-bank/
    logs/
      decisions-history.md                     # MODIFY: log D1–D5 for BRD-29
```

### 4.2 Database Schema

No table change. One new **regular view** and one **partial index**:

```sql
-- Partial index — only the cost events
CREATE INDEX ix_events_cost_provider
  ON events ((payload->>'provider'))
  WHERE type = 'CostIncurred';

-- Read-only projection
CREATE VIEW run_costs AS
SELECT
  run_id,
  (payload->>'provider')                                   AS provider,
  (payload->>'kind')                                       AS kind,
  (payload->>'model')                                      AS model,
  (payload->>'task_name')                                  AS task_name,
  COUNT(*)                                                 AS calls,
  COALESCE(SUM((payload->>'prompt_tokens')::int), 0)       AS prompt_tokens,
  COALESCE(SUM((payload->>'completion_tokens')::int), 0)   AS completion_tokens,
  COALESCE(SUM((payload->>'units')::int), 0)               AS units,
  COALESCE(SUM((payload->>'cost_usd')::numeric), 0)        AS cost_usd
FROM events
WHERE type = 'CostIncurred'
GROUP BY run_id, provider, kind, model, task_name;
```

### 4.3 Alembic Migration

```python
"""run_costs view + partial index

Revision ID: 004_run_costs
Revises: 003_add_llm_provider
Create Date: 2026-05-29
"""
from alembic import op

revision = "004_run_costs"
down_revision = "003_add_llm_provider"

def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_events_cost_provider "
        "ON events ((payload->>'provider')) "
        "WHERE type = 'CostIncurred'"
    )
    op.execute("""
        CREATE VIEW run_costs AS
        SELECT
          run_id,
          (payload->>'provider') AS provider,
          (payload->>'kind') AS kind,
          (payload->>'model') AS model,
          (payload->>'task_name') AS task_name,
          COUNT(*) AS calls,
          COALESCE(SUM((payload->>'prompt_tokens')::int), 0)     AS prompt_tokens,
          COALESCE(SUM((payload->>'completion_tokens')::int), 0) AS completion_tokens,
          COALESCE(SUM((payload->>'units')::int), 0)             AS units,
          COALESCE(SUM((payload->>'cost_usd')::numeric), 0)      AS cost_usd
        FROM events
        WHERE type = 'CostIncurred'
        GROUP BY run_id, provider, kind, model, task_name
    """)

def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS run_costs")
    op.execute("DROP INDEX IF EXISTS ix_events_cost_provider")
```

### 4.4 Pydantic Models

`backend/app/domain/events.py` (new event class, registered in the discriminated union):

```python
class CostIncurredEvent(BaseEvent):
    """Append-only cost record per external billable call (RF-20)."""
    model_config = ConfigDict(extra="allow")

    type: Literal[EventType.COST_INCURRED] = EventType.COST_INCURRED

    provider: str                           # "anthropic" | "tavily" | "wikipedia" | ...
    kind: Literal["llm", "search", "fetch"]
    model: str | None = None                # LLM model id; None for non-LLM
    task_name: str | None = None            # FSM state, e.g. "PLANNING"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    units: int = 0                          # search credits, page-fetches, etc.
    unit_cost_usd: float = 0.0
    cost_usd: float                         # canonical USD
    latency_ms: int
    pricing_source: Literal["litellm", "fallback", "static"]
```

`backend/app/domain/enums.py`:

```python
class EventType(StrEnum):
    # ... existing 44 values ...
    COST_INCURRED = "CostIncurred"
```

Endpoint response models in `backend/app/routes/costs.py`:

```python
class ProviderCostRow(BaseModel):
    provider: str
    kind: Literal["llm", "search", "fetch"]
    model: str | None
    calls: int
    prompt_tokens: int
    completion_tokens: int
    units: int
    cost_usd: float
    pct_of_total: float                     # 0..100, rounded to 2 decimals

class RunCostsResponse(BaseModel):
    run_id: UUID
    total_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    by_provider: list[ProviderCostRow]      # sorted desc by cost_usd
```

### 4.5 API Endpoints

| Method | Path | Request Body | Response | Description |
|--------|------|--------------|----------|-------------|
| GET | `/api/runs/{run_id}/costs` | — | `RunCostsResponse` | Returns per-provider × kind × model breakdown for one run. Auth: bearer JWT (existing `current_user` dependency) + ownership check (the run must belong to the user). |

No new SSE endpoint — the existing `/api/runs/{run_id}/stream` already emits all event types, so `CostIncurred` events flow over the same channel and the frontend can patch its in-memory totals incrementally.

### 4.6 React Components

| Component | Path | Props | State | Description |
|-----------|------|-------|-------|-------------|
| `TotalCostChip` | `atoms/TotalCostChip.tsx` | `{ totalUsd: number; tokens: number; loading?: boolean }` | none | Compact chip rendering `$0.0421 · 4.3K tok` with `--accent-soft` background. Animated counter when value changes (Motion v12 spring). Tooltip "Cost so far — click to open breakdown" links to `T1d`. |
| `CostBarSegment` | `atoms/CostBarSegment.tsx` | `{ provider: string; value: number; total: number; color: string }` | none | One segment of a stacked horizontal bar. Width = `(value / total) * 100%`. ARIA `role="presentation"` (label provided by parent). |
| `CostBreakdownBar` | `molecules/CostBreakdownBar.tsx` | `{ rows: ProviderCostRow[] }` | none | Stacked horizontal bar (per provider). Legend below with color swatches + USD. Empty state: "No cost recorded yet." |
| `CostBreakdownTable` | `molecules/CostBreakdownTable.tsx` | `{ rows: ProviderCostRow[]; sortBy?: "cost" \| "calls" \| "tokens" }` | local sort state | Sortable table: Provider · Kind · Model · Calls · Prompt tok · Completion tok · Units · USD · % of total. Sticky header, scrollable body. |
| `TraceCostPanel` | `organisms/TraceCostPanel.tsx` | `{ runId: UUID }` | uses `useRunCosts(runId)` | The body of the new `T1d` tab. Header shows total + per-token average; body shows `CostBreakdownBar` then `CostBreakdownTable`. Loading skeleton + empty state. |
| `TracePanel` (modify) | `organisms/TracePanel.tsx` | unchanged | tab state | Add `T1d` tab labeled "Cost" with `Coins` icon (Lucide). |
| `RunHeader` (modify) | `organisms/RunHeader.tsx` | unchanged | uses `useRunCosts(runId)` | Mount `<TotalCostChip />` next to the existing status chips. Clicking it activates the `T1d` tab via `selectionStore.setTraceTab("cost")`. |

#### 4.6.1 `useRunCosts` hook contract

```typescript
export interface UseRunCostsReturn {
  total: { usd: number; promptTokens: number; completionTokens: number };
  rows: ProviderCostRow[];
  isLoading: boolean;
  isError: boolean;
  source: "rest" | "sse-patched";        // for debugging only
}

export function useRunCosts(runId: string): UseRunCostsReturn;
```

Behaviour:
- On mount: TanStack Query `GET /api/runs/{runId}/costs` (cached by `["runs", runId, "costs"]`).
- Subscribes to the existing run SSE store; every incoming `CostIncurred` event patches the cached query data via `queryClient.setQueryData(...)`. No new fetch on every event.
- On run termination (any `Stopped` event), invalidates the query once to reconcile with the canonical view aggregate (defensive — SSE patching can drift if reconnect dropped a frame).

### 4.7 UI Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  RunHeader  [Q: "..."]  [Status: SEARCHING]  [⏱ 12s]  [💰 $0.0421 · 4.3K] │
├────────────┬───────────────────────────────────┬─────────────────────────┤
│            │                                   │  TracePanel             │
│  History   │       CenterPanel                 │  ┌─────────────────┐    │
│  Panel     │       (live feed)                 │  │ Events │ Plan │  │    │
│            │                                   │  │ Sources│ Cost │  │←T1d│
│            │                                   │  ├─────────────────┤    │
│            │                                   │  │ Total: $0.0421  │    │
│            │                                   │  │ ▓▓▓▓▓▓▓░░░░░░  │    │
│            │                                   │  │  anthropic 78%  │    │
│            │                                   │  │  tavily    20%  │    │
│            │                                   │  │  wikipedia  2%  │    │
│            │                                   │  ├─────────────────┤    │
│            │                                   │  │ ┌─Table─────┐   │    │
│            │                                   │  │ │ ...       │   │    │
│            │                                   │  │ └───────────┘   │    │
│            │                                   │  └─────────────────┘    │
└────────────┴───────────────────────────────────┴─────────────────────────┘
```

The chip in the header is **always visible**, even when the trace panel is collapsed. Clicking it expands the trace panel and selects `T1d`. The chip uses `--accent-soft` background, `--accent` text, `JetBrains Mono` font for the numeric value (consistency with all numeric chips in the design system).

### 4.8 Contextvar plumbing (backend)

New file `backend/app/llm/context.py`:

```python
from contextvars import ContextVar
from typing import Awaitable, Callable
from uuid import UUID
from app.domain.events import BaseEvent

current_run_id: ContextVar[UUID | None] = ContextVar("current_run_id", default=None)
current_task_name: ContextVar[str | None] = ContextVar("current_task_name", default=None)
current_emitter: ContextVar[Callable[[BaseEvent], Awaitable[None]] | None] = (
    ContextVar("current_emitter", default=None)
)
```

`runner._supervised_run` sets `current_run_id` and `current_emitter` right after building the `_emit` callback, before the FSM loop runs. `orchestrator` wraps each FSM transition in a small helper that sets `current_task_name` to the new state's value (one-liner per transition).

### 4.9 LLM client change

`backend/app/llm/client.py::call` is rewritten to use `instructor`'s **`create_with_completion`** (returns the Pydantic model **and** the raw litellm completion):

```python
async def call(self, role, messages, response_model, max_tokens=None, emit_event=None):
    t0 = time.perf_counter()
    model_instance, raw = await self._instructor.chat.completions.create_with_completion(
        model=self._model_for(role),
        messages=messages,
        response_model=response_model,
        max_tokens=max_tokens or _MAX_TOKENS[role],
        temperature=_TEMPERATURE[role],
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Cost & token accounting (RF-20)
    usage = getattr(raw, "usage", None)
    if usage is not None:
        cost, src = compute_cost(model=self._model_for(role), raw_completion=raw)
        emitter = current_emitter.get()
        if emitter is not None:
            await emitter(CostIncurredEvent(
                provider=settings.llm_provider,
                kind="llm",
                model=self._model_for(role),
                task_name=current_task_name.get(),
                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                completion_tokens=getattr(usage, "completion_tokens", 0),
                cost_usd=cost,
                latency_ms=latency_ms,
                pricing_source=src,
            ))
    return model_instance
```

### 4.10 Source instrumentation

Helper `backend/app/sources/_cost.py`:

```python
async def emit_source_cost(*, provider: str, kind: Literal["search","fetch"],
                            units: int, unit_cost_usd: float, latency_ms: int) -> None:
    emitter = current_emitter.get()
    if emitter is None:
        return
    await emitter(CostIncurredEvent(
        provider=provider,
        kind=kind,
        units=units,
        unit_cost_usd=unit_cost_usd,
        cost_usd=units * unit_cost_usd,
        latency_ms=latency_ms,
        pricing_source="static",
    ))
```

Each Source plugin calls this helper at the end of every billable request.

### 4.11 SSE → frontend

No changes to `app/sse/stream.py` — it already streams every event type. The new `CostIncurred` events automatically flow to clients. The `useRunCosts` hook patches the cached query data on every incoming event; `RunHeader` and `TraceCostPanel` re-render reactively.

---

## 5. Acceptance Criteria

### AC-01: Every LLM call emits exactly one cost event

```gherkin
Given an agent run executes 7 LLM calls (1 classifier, 2 planner, 3 synthesizer, 1 judge)
When the run completes
Then exactly 7 events of type "CostIncurred" with kind="llm" are persisted in the events table
  And each event payload contains non-null provider, model, prompt_tokens, completion_tokens, cost_usd, latency_ms, pricing_source
  And the cost_usd values match litellm.completion_cost() within ±$0.000001 when pricing_source="litellm"
```

### AC-02: Tavily calls emit one cost event each with correct units

```gherkin
Given a Source plugin executes 3 Tavily searches with search_depth="advanced" and 1 deep-fetch via extract()
And settings.tavily_usd_per_credit is 0.008
When the run completes
Then 4 CostIncurred events with provider="tavily" are persisted
  And the 3 search events have units=2 and cost_usd=0.016 each
  And the 1 extract event has kind="fetch"
  And no event is duplicated across retries (idempotent — even if tenacity retries the same call once, only the final successful attempt emits)
```

### AC-03: Wikipedia and other free sources are recorded with zero cost

```gherkin
Given an agent run queries Wikipedia twice
When the run completes
Then 2 CostIncurred events with provider="wikipedia", cost_usd=0.0, units=1, pricing_source="static" exist
  And they appear in the run_costs view under provider="wikipedia"
```

### AC-04: GET /api/runs/{run_id}/costs returns grouped totals

```gherkin
Given a completed run with 7 LLM calls (total $0.0341) and 4 Tavily calls (total $0.064)
When the user (run owner) sends GET /api/runs/{run_id}/costs with a valid JWT
Then the response is 200 OK
  And response.total_usd equals 0.0981 ±0.0001
  And response.by_provider contains a row {provider:"anthropic", kind:"llm", calls:7, cost_usd:0.0341}
  And response.by_provider contains a row {provider:"tavily", kind:"search", calls:3, units:6, cost_usd:0.048}
  And response.by_provider contains a row {provider:"tavily", kind:"fetch", calls:1, units:2, cost_usd:0.016}
  And rows are sorted by cost_usd descending
  And every row's pct_of_total sums to 100 ±0.5
```

### AC-05: Endpoint rejects non-owners

```gherkin
Given a run R belongs to user A
When user B sends GET /api/runs/R/costs with B's valid JWT
Then the response is 404 Not Found
  And no cost data leaks in the response body
```

### AC-06: TotalCostChip updates live during a run

```gherkin
Given the run page is open and an agent run is executing
When a CostIncurred event arrives over SSE with cost_usd=0.012
Then the TotalCostChip displays the new running total within 200 ms
  And the change is animated (the numeric value tweens, no jump)
  And no full re-fetch of /api/runs/{id}/costs occurs (verified via MSW request count)
```

### AC-07: TraceCostPanel shows correct breakdown after run completion

```gherkin
Given a completed run with the breakdown from AC-04
When the user clicks the "Cost" tab in the TracePanel
Then the stacked bar shows three segments: anthropic (~35%), tavily (~65%, split into two visually-distinct sub-segments)
  And the table lists all 3 rows sorted by USD descending
  And the column "% of total" sums to 100 ±0.5
  And keyboard navigation through the table preserves visible focus
```

### AC-08: Read determinism — reopening shows identical numbers

```gherkin
Given a run completed yesterday with total_usd = $0.1234
And Anthropic's pricing has since changed by 50%
When the user reopens the run today
Then GET /api/runs/{id}/costs still returns total_usd = $0.1234
  And the trace panel renders the same per-row numbers it showed yesterday
```

### AC-09: Graceful degradation on pricing miss

```gherkin
Given an LLM call returns usage data for a model not in litellm's pricing DB and not in our fallback table
When the call completes
Then a CostIncurred event is still emitted
  And the event has cost_usd=0.0 and pricing_source="static"
  And prompt_tokens and completion_tokens are non-zero (preserved)
  And the trace panel renders the row with cost as "—" (em-dash) but tokens visible
  And no exception reaches the user
```

### AC-10: Fork preserves the cost ledger of the parent

```gherkin
Given a parent run with 5 CostIncurred events totalling $0.05
When the user forks the run at step_index 8
Then the child run starts with the parent's events copied (including all 5 CostIncurred)
  And GET /api/runs/{child_id}/costs returns the parent's totals, plus any new costs the child incurs
```

### AC-11: A11y — both header chip and trace tab pass jest-axe

```gherkin
Given the run page is rendered in both dark and light themes (BRD-28)
When jest-axe runs against RunHeader and TraceCostPanel
Then no contrast or ARIA violations are reported
  And the TotalCostChip exposes an accessible name like "Cost so far: $0.04, 4,300 tokens"
```

---

## 6. Implementation Checklist

### Backend
- [ ] `EventType.COST_INCURRED` added — `backend/app/domain/enums.py`
- [ ] `CostIncurredEvent` class + union registration — `backend/app/domain/events.py`
- [ ] Contextvars module — `backend/app/llm/context.py`
- [ ] LLM pricing module (hybrid) — `backend/app/llm/pricing.py`
- [ ] Source pricing module — `backend/app/sources/pricing.py`
- [ ] Source cost emit helper — `backend/app/sources/_cost.py`
- [ ] `llm/client.py::call` switched to `create_with_completion` + emits event
- [ ] `agent/runner.py::_supervised_run` sets `current_run_id` + `current_emitter`
- [ ] `agent/orchestrator.py` sets `current_task_name` per FSM transition
- [ ] Tavily wrapper emits `search` + `fetch` cost events
- [ ] Wikipedia / Semantic Scholar / OpenAlex emit zero-cost events
- [ ] `Settings.tavily_usd_per_credit` added — `backend/app/config.py`
- [ ] Alembic migration for view + partial index — `backend/alembic/versions/004_run_costs_view.py`
- [ ] Endpoint `GET /api/runs/{run_id}/costs` + Pydantic response models — `backend/app/routes/costs.py`
- [ ] Router registered in `backend/app/main.py`
- [ ] Backend tests — `tests/test_llm_client_cost.py`, `tests/test_sources_tavily_cost.py`, `tests/test_sources_wikipedia_cost.py`, `tests/test_routes_run_costs.py`, `tests/test_view_run_costs.py`

### Frontend
- [ ] Regenerate `frontend/src/types/events.ts` via `python scripts/export_types.py`
- [ ] `lib/formatCost.ts` + tests
- [ ] `hooks/useRunCosts.ts` + tests (TanStack Query + SSE patching)
- [ ] Atoms: `TotalCostChip`, `CostBarSegment` + tests
- [ ] Molecules: `CostBreakdownBar`, `CostBreakdownTable` + tests
- [ ] Organism: `TraceCostPanel` + tests (a11y)
- [ ] `TracePanel.tsx` registers new `T1d` tab
- [ ] `RunHeader.tsx` mounts `<TotalCostChip />` + click-to-open-trace wiring
- [ ] MSW handler for `/api/runs/{id}/costs` in tests
- [ ] Vitest a11y check on RunHeader + TraceCostPanel in **both** themes (light/dark)

### Documentation
- [ ] `docs/understanding-phase/requirement-understanding.md` — append RF-20 with the wording from §2
- [ ] `docs/understanding-phase/ui-prototype.md` — add panel state `T1d` (Trace · cost breakdown) + reference to TotalCostChip in the header inventory
- [ ] `docs/technical-phase/ai-services.md` — append §6 "Cost & token tracking" (event shape, pricing strategy, env vars, instrumentation contract)
- [ ] `.github/memory-bank/logs/decisions-history.md` — log D1–D5 for BRD-29

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (BE) | pytest + pytest-asyncio | `llm/pricing.py`, `sources/pricing.py`, `_cost.py` | ≥ 90% (pure functions) |
| Unit (BE) | pytest + pytest-httpx + stubs | `llm/client.py::call` with mocked `create_with_completion` | ≥ 85% |
| Integration (BE) | pytest-postgresql | `run_costs` view + `GET /api/runs/{id}/costs` end-to-end | Critical paths |
| Unit (FE) | Vitest | `formatCost.ts`, `useRunCosts.ts` | ≥ 90% |
| Component (FE) | Vitest + Testing Library | `TotalCostChip`, `CostBreakdownBar`, `CostBreakdownTable`, `TraceCostPanel` | ≥ 80% |
| Accessibility (FE) | jest-axe | RunHeader + TraceCostPanel in dark **and** light theme | Zero violations |
| Type contract | Generated TS + `tsc --noEmit` | `frontend/src/types/events.ts` | Build passes |
| Migration | Alembic upgrade/downgrade/upgrade | `004_run_costs_view.py` | Idempotent |

Coverage gate per copilot-instructions §7.7: ≥ 80%.

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAVILY_USD_PER_CREDIT` | No | `0.008` | USD price per Tavily credit (1 credit per `basic` search, 2 per `advanced`). Override per actual contract. Surfaced as `Settings.tavily_usd_per_credit`. |

No new required variables. `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are already required by V1.

## 9. Risks & Mitigations

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-01 | `instructor.create_with_completion` API differs across versions and breaks the LLM client | High | Medium | Pin `instructor` version in `pyproject.toml`; integration test covers the actual installed version; fallback path documented in §4.9 (use `chat.completions.create_with_completion` if top-level form is missing). |
| R-02 | `litellm.completion_cost()` returns `None` for new Claude variants → silent zero cost | Medium | High | Hybrid pricing falls back to local table; if both miss, `pricing_source="static"` + `cost_usd=0.0` is emitted with tokens preserved; UI renders cost as "—" and surfaces it (AC-09). Local table is reviewed every release. |
| R-03 | Contextvars are not propagated to a Source call that spawns its own background task | Medium | Low | The repo's single-worker policy (uvicorn `--workers 1`) + asyncio.Task contextvar inheritance covers the common case; any Source that creates a new task must use `asyncio.create_task(..., context=copy_context())`. Documented in `ai-services.md` §6. |
| R-04 | SSE event ordering vs REST endpoint reads — patched totals drift from view aggregate | Low | Low | On every `Stopped` event the frontend invalidates the TanStack Query to reconcile; AC-08 covers determinism. |
| R-05 | `ix_events_cost_provider` partial index inflates write latency on hot insert path | Low | Low | Cost events are ≤ ~50 per run; index is partial (only indexes `CostIncurred` rows). Measured overhead < 0.1 ms per insert in development. |
| R-06 | `payload->>'cost_usd'::numeric` casts fail if a buggy emitter writes a string | Medium | Low | Pydantic v2 type-validates `cost_usd: float` at emit time; the cast is defensive. Test `test_view_run_costs.py` includes a malformed-row case to confirm the view skips bad rows gracefully (returns `0.0` via `COALESCE`). |
| R-07 | Tavily pricing default of `0.008` is wrong for the actual contract → totals off by a constant factor | Low | Medium | Surface in `.env.example` and ai-services.md §6 as "operator-tunable"; document that historical events keep the price captured at emit time (read determinism, RF-11). |
| R-08 | New tab + chip add visual noise that distracts from RF-13 trust signals | Low | Low | The chip uses `--accent-soft` (subdued) and the tab is opt-in; a11y review (AC-11) catches contrast/clutter regressions in both themes. |

## 10. Out of Scope (V1)

- **Cross-run dashboards** (cost per day, cost per user, cost per model across all runs). Promotion to a materialised view + dedicated dashboard page is deferred until usage justifies it.
- **USD-denominated soft budgets** (auto-stop when run exceeds $X). V1 keeps the existing `tokens_used_estimate` budget; a USD budget would be a new BRD that wires `cost_usd` into `_check_global_budget`.
- **Per-user billing or invoices.** No `users.balance` column, no Stripe integration.
- **Live alerting** when a run exceeds N×P50 cost. Out of scope for this BRD.
- **Cost projections** ("at current rate this run will reach $Y"). Could be a derived chip later; not implemented in V1.
- **Embedding-call cost tracking.** `app/llm/embeddings.py` is invoked from the saturation signal; instrumenting it adds noise. Deferred — V1 focuses on `client.py::call` only.
- **Cost capture for retries inside tenacity.** Only the final successful call emits; failed retries are not recorded (avoids over-counting). If a retry exhausts and the call fails terminally, no `CostIncurred` is emitted (AC-02 idempotency clause).
- **Anthropic prompt-caching discount accounting.** litellm exposes `cache_creation_input_tokens` / `cache_read_input_tokens` in `usage`; we record them via `extra="allow"` for future analysis but do not apply a discount formula in V1.
- **Vista materializada.** A regular view is sufficient at V1 scale; promotion path documented in `decisions-history.md` D1.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-29 | BSA Agent | Initial draft. Adds RF-20. Backend (event + view + endpoint) + Frontend (TotalCostChip atom, CostBreakdown molecules, TraceCostPanel organism, T1d tab). Pricing hybrid: litellm + fallback. |
