# BRD-27: Service Health Observability Bar

**Document ID:** BRD-27
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-28
**Implementation Order:** 27 of N
**Assumes shipped:** BRD-05 (LLM client), BRD-06 (Source plugins with `health_check()`), BRD-11 (frontend layout), BRD-18 (infrastructure), Postgres single-server (RF-05).

---

## 1. Executive Summary

Novum already depends on a heterogeneous set of external services — Anthropic (active LLM), Tavily (web search), Wikipedia / Semantic Scholar / OpenAlex (knowledge sources), PostgreSQL (event log, RF-03), plus several **wired-but-disabled** LLM fallbacks (OpenAI, Google Gemini, GitHub Models). Today the user has **no in-app visibility** of whether any of these is degraded or down; failures only surface as run errors *after* a research run has been started, which both wastes budget and undermines the trust surface mandated by RF-13.

BRD-27 introduces a **Service Health Bar**: a thin, persistent footer strip rendered on every page that lists each integrated service as a tiny pill (colored dot + name + tooltip). The bar polls a new aggregator endpoint `GET /api/health/services` once per minute via TanStack Query and updates **silently** (no spinners, no layout shifts, no focus stealing) using `keepPreviousData`.

Backend-side, a new in-memory `HealthRegistry` runs `health_check()` probes against each registered service in parallel with a per-probe timeout, caches the result for 30 s (so the public endpoint is cheap and rate-friendly even if many tabs are open), and maps each probe to a small set of statuses: `ok | degraded | down | disabled | no_key`. The probe layer reuses the existing `Source.health_check()` seam (BRD-06) for search/knowledge sources, adds a lightweight LLM probe through `llm.call` (BRD-05), and a `SELECT 1` round-trip for Postgres.

The result is a **passive, always-on trust surface**: users see at a glance which capabilities are operational before they ever click "Start research", and when a run later stops with `errored` or `stopped_by_budget`, the bar provides the post-hoc explanation in a tooltip rather than a buried log line.

This BRD is **additive only**: one new route, one new in-memory registry, one organism + two molecules + one atom on the frontend, no DB migrations, no new env vars, no changes to the agent FSM, no changes to the three plugin seams, no changes to event semantics.

Binding success metrics in §10. Expected outcome: zero new agent-side dependencies, < 50 ms median response time on `/api/health/services` (cache hit), < 5 % bar-induced backend load.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-05 (single-server) | `uvicorn --workers 1`, no distributed state | **Preserved.** `HealthRegistry` is an in-process singleton; cache is a plain `dict` guarded by `anyio.Lock`. No Redis. |
| RF-08 (read determinism) | No live LLM regeneration on read | **Preserved.** Health probes are out-of-band telemetry; they never feed run state or persisted events. |
| RF-13 (UI as trust surface) | Surface every trust-relevant signal | **Extends.** The bar surfaces the per-service operational state that today is hidden in server logs. |
| RF-16 (graceful degradation) | App stays usable when a non-critical service fails | **Extends.** The bar makes degradation *visible* before the user issues a request that would fail. |

No RF amendments. No changes to `stop_reason` enum. No changes to `final_confidence`.

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-05 (LLM client) | LLM probe goes through `llm.call` with a minimal request; never bypasses the abstraction. |
| BRD-06 (Source plugins) | Reuses `Source.health_check()` already implemented on Tavily, Wikipedia, Semantic Scholar, OpenAlex. |
| BRD-11 (frontend layout) | Adds `ServiceStatusBar` organism to the global layout footer slot. |
| BRD-18 (infrastructure) | The endpoint is exposed under the same FastAPI app; no new process. |

No dependents block on this BRD; it is independently shippable.

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    health/
      __init__.py
      models.py              # NEW: Pydantic response models, ServiceStatus enum
      registry.py            # NEW: HealthRegistry (singleton, 30 s cache, parallel probes)
      probes.py              # NEW: probe coroutines per service category
    routes/
      health.py              # MODIFY: add GET /health/services next to existing /health
  tests/
    test_health_registry.py  # NEW
    test_health_probes.py    # NEW
    test_health_route.py     # NEW

frontend/
  src/
    components/
      atoms/
        StatusDot.tsx              # NEW
        StatusDot.test.tsx         # NEW
      molecules/
        StatusPill.tsx             # NEW (uses shadcn Tooltip)
        StatusPill.test.tsx        # NEW
      organisms/
        ServiceStatusBar.tsx       # NEW
        ServiceStatusBar.test.tsx  # NEW
    hooks/
      useServiceHealth.ts          # NEW (TanStack Query, 60 s refetchInterval)
      useServiceHealth.test.ts     # NEW
    lib/
      api.ts                       # MODIFY: thin helper if not already covered
    types/
      health.ts                    # NEW: mirrors backend Pydantic types
    pages/
      *Layout                      # MODIFY: mount ServiceStatusBar in global footer
```

### 4.2 Database Schema

**No schema changes.** Health state is in-process and ephemeral by design.

### 4.3 Alembic Migration

**None.**

### 4.4 Pydantic Models (`backend/app/health/models.py`)

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    DISABLED = "disabled"
    NO_KEY = "no_key"


class ServiceCategory(StrEnum):
    LLM = "llm"
    SEARCH = "search"
    KNOWLEDGE = "knowledge"
    STORAGE = "storage"


class ServiceHealth(BaseModel):
    """Single service entry in the health bar."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Stable machine id, e.g. 'anthropic'.")
    name: str = Field(..., description="Display name, e.g. 'Anthropic'.")
    category: ServiceCategory
    status: ServiceStatus
    latency_ms: int | None = Field(default=None, ge=0)
    message: str | None = Field(default=None, description="Tooltip text when status != ok.")
    checked_at: datetime


class HealthSnapshot(BaseModel):
    """Response payload for GET /api/health/services."""

    model_config = ConfigDict(extra="allow")

    checked_at: datetime
    cached: bool
    services: list[ServiceHealth]
```

### 4.5 API Endpoints

| Method | Path | Request Body | Response | Description |
|--------|------|--------------|----------|-------------|
| GET | `/api/health` | — | `{"status": "ok"}` | Existing liveness probe. **Unchanged.** |
| GET | `/api/health/services` | — | `HealthSnapshot` | **NEW.** Aggregated per-service health. Cached 30 s server-side. Always returns `200`; per-service problems are encoded in `status` + `message`. |

The endpoint is **public** (no auth) and intentionally cheap. Rate limiting is not required for V1 (cache absorbs traffic).

### 4.6 React Components

| Component | Path | Props | State | Description |
|-----------|------|-------|-------|-------------|
| `StatusDot` | `atoms/StatusDot.tsx` | `{ status: ServiceStatus; size?: number }` | — | 6 px colored circle. Honors `prefers-reduced-motion` (no pulse). |
| `StatusPill` | `molecules/StatusPill.tsx` | `{ service: ServiceHealth }` | local hover | Dot + name + shadcn `Tooltip` with `message`, `latency_ms`, `checked_at` relative. `<button>` for keyboard / a11y. |
| `ServiceStatusBar` | `organisms/ServiceStatusBar.tsx` | — | from `useServiceHealth` | Horizontal flex row grouped by `category` with subtle `·` separators. Scrolls horizontally on narrow viewports. Renders skeleton dots on first load only. |
| `useServiceHealth` | `hooks/useServiceHealth.ts` | — | TanStack Query state | `useQuery({ queryKey: ['health','services'], queryFn, refetchInterval: 60_000, refetchOnWindowFocus: false, placeholderData: keepPreviousData, staleTime: 30_000 })`. |

**Atomic layering** (enforced by ESLint `import/no-restricted-paths`):
- `atoms/StatusDot` → no imports below `atoms/`.
- `molecules/StatusPill` → may import `atoms/`, `lib/`, `types/`, shadcn primitives.
- `organisms/ServiceStatusBar` → may import `molecules/`, `hooks/`, `lib/`, `types/`. **No `fetch` here** — data flows from the hook.
- Only `pages/*` mount the organism.

### 4.7 UI Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Center / History / Trace panels                                         │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  ● Anthropic   ◐ OpenAI   ○ Gemini  ·  ● Tavily   ● Wikipedia  ·  ● DB  │  ← ServiceStatusBar (28 px)
└──────────────────────────────────────────────────────────────────────────┘
```

**Visual contract** (binds to `ui-prototype.md` §1 tokens):

| Status | Glyph | Token | Animation |
|--------|-------|-------|-----------|
| `ok` | `●` | `--accent-success` | none |
| `degraded` | `⚠` | `--accent-warning` | soft pulse 1.5 s (disabled under `prefers-reduced-motion`) |
| `down` | `●` | `--accent-danger` | none |
| `disabled` | `○` | `--text-tertiary` | none |
| `no_key` | `◐` | `--text-tertiary` (border `--accent-warning`) | none |

Container: `h-7 border-t border-(--glass-border) bg-(--bg-secondary)/40 backdrop-blur-xl`. Pills use `text-xs text-(--text-tertiary)`, with `hover:text-(--text-secondary)`. Color transitions on the dot use Motion `duration: 0.4, ease: "easeOut"` so silent refreshes never flash.

### 4.8 Probe Registry (`backend/app/health/probes.py`)

Each probe is `async () -> ServiceHealth` and **must** complete within `PROBE_TIMEOUT_S = 2.0`. On timeout, the probe returns `status=down, message="probe timeout"`.

Initial registered probes (V1 scope):

| id | name | category | Probe |
|----|------|----------|-------|
| `anthropic` | Anthropic | `llm` | `llm.call(LLMRole.HEALTH, messages=[…], max_tokens=1)` via the existing client (BRD-05). `no_key` if `ANTHROPIC_API_KEY` unset. |
| `openai` | OpenAI | `llm` | `disabled` in V1 (config flag). If a key is present, probe `models.retrieve("gpt-4o-mini")`. |
| `gemini` | Google Gemini | `llm` | `disabled` in V1. |
| `github_models` | GitHub Models | `llm` | `disabled` in V1. |
| `tavily` | Tavily | `search` | `TavilySource().health_check()` (BRD-06). |
| `wikipedia` | Wikipedia | `knowledge` | `WikipediaSource().health_check()` (BRD-06). |
| `semantic_scholar` | Semantic Scholar | `knowledge` | `SemanticScholarSource().health_check()` (BRD-06). |
| `openalex` | OpenAlex | `knowledge` | `OpenAlexSource().health_check()` (BRD-06). |
| `postgres` | PostgreSQL | `storage` | `await session.execute(text("SELECT 1"))` with 500 ms timeout. |

**Status mapping rules** (applied uniformly):

| Observation | Status | Message |
|-------------|--------|---------|
| Probe returns `True`, latency ≤ p95 threshold | `ok` | `None` |
| Probe returns `True`, latency > p95 threshold (`> 1500 ms`) | `degraded` | `"high latency: {ms}ms"` |
| Probe raises `TimeoutError` | `down` | `"probe timeout"` |
| Probe raises auth-like exception (`401`, `403`) | `down` | `"authentication failed"` |
| Probe raises connect/DNS error | `down` | `"unreachable"` |
| Probe raises HTTP 5xx | `down` | `"upstream error: {code}"` |
| Probe raises rate-limit (`429`) | `degraded` | `"rate limited"` |
| Required env var missing | `no_key` | `"missing {VAR_NAME}"` |
| Service flag `enabled=false` | `disabled` | `"not enabled in V1"` |

### 4.9 HealthRegistry (`backend/app/health/registry.py`)

```python
class HealthRegistry:
    """Singleton, in-process cache of the most recent ServiceHealth snapshot.

    Single-writer: an asyncio task per probe runs under asyncio.gather()
    behind an anyio.Lock so concurrent requests share one refresh.
    """

    CACHE_TTL_S = 30.0
    PROBE_TIMEOUT_S = 2.0

    async def snapshot(self) -> HealthSnapshot: ...
    async def refresh(self) -> HealthSnapshot: ...  # forces re-probe
```

**Concurrency:** if a request arrives while a refresh is in flight, it awaits the same `asyncio.Future` rather than triggering a second batch.

---

## 5. Acceptance Criteria

### AC-01: Aggregated health endpoint returns all registered services

```gherkin
Given the backend is running with ANTHROPIC_API_KEY and TAVILY_API_KEY set
  And no OPENAI_API_KEY, GOOGLE_API_KEY, or GITHUB_TOKEN is set
When I GET /api/health/services
Then the response status is 200
  And the body matches HealthSnapshot
  And services[].id includes "anthropic", "tavily", "wikipedia", "postgres"
  And the service with id "openai" has status "disabled"
  And the service with id "gemini" has status "disabled"
  And the service with id "github_models" has status "disabled"
  And every entry has a checked_at within the last 30 seconds
```

### AC-02: Cache prevents thundering herd

```gherkin
Given the HealthRegistry cache is empty
When 50 concurrent requests hit GET /api/health/services
Then each probe coroutine is invoked at most once
  And all 50 responses contain the same checked_at timestamp
  And cached is true on at least 49 responses
```

### AC-03: A failing service is rendered as "down" with a tooltip message

```gherkin
Given the Tavily probe raises httpx.ConnectError("unreachable")
When I GET /api/health/services
Then the entry with id "tavily" has status "down"
  And message contains "unreachable"
  And the response status is 200
  And no other service is affected
```

### AC-04: Missing API key produces no_key, not down

```gherkin
Given ANTHROPIC_API_KEY is unset at process start
When I GET /api/health/services
Then the entry with id "anthropic" has status "no_key"
  And message contains "ANTHROPIC_API_KEY"
  And no LLM network call is attempted
```

### AC-05: Silent refresh on the frontend

```gherkin
Given the ServiceStatusBar has rendered an initial snapshot
When 60 seconds elapse and the next refetch fires
Then no loading spinner appears
  And no layout shift occurs
  And focus is not stolen from any input
  And the dot colors transition over ~400 ms
```

### AC-06: Tooltip exposes failure details

```gherkin
Given the Anthropic service has status "down" with message "authentication failed"
When the user focuses or hovers the Anthropic pill
Then a tooltip appears within 200 ms
  And the tooltip text contains "authentication failed"
  And the tooltip text contains a relative timestamp ("just now", "30s ago", …)
```

### AC-07: Accessibility — keyboard and screen reader

```gherkin
Given the ServiceStatusBar is rendered
When the user tabs through the page
Then each StatusPill receives focus in DOM order
  And each pill exposes aria-label of the form
       "{name}: {status}, {latency_ms}ms" (or "{name}: {status}" when no latency)
  And axe-core reports zero violations on the bar
```

### AC-08: Endpoint stays cheap

```gherkin
Given the HealthRegistry has a warm cache
When I GET /api/health/services
Then the p95 response time is below 50 ms
  And no outbound network calls are made
```

---

## 6. Implementation Checklist

- [ ] Pydantic models — `backend/app/health/models.py`
- [ ] Probe coroutines — `backend/app/health/probes.py`
- [ ] HealthRegistry singleton — `backend/app/health/registry.py`
- [ ] Route handler — extend `backend/app/routes/health.py`
- [ ] Router wiring — confirm `/api/health/services` is exposed
- [ ] Backend unit tests — `backend/tests/test_health_*.py`
- [ ] Type export — regenerate `frontend/src/types/health.ts` via `scripts/export_types.py`
- [ ] Atom — `frontend/src/components/atoms/StatusDot.tsx`
- [ ] Molecule — `frontend/src/components/molecules/StatusPill.tsx`
- [ ] Organism — `frontend/src/components/organisms/ServiceStatusBar.tsx`
- [ ] Hook — `frontend/src/hooks/useServiceHealth.ts`
- [ ] Mount in global layout — every page footer
- [ ] Frontend unit tests — Vitest + Testing Library + jest-axe + MSW
- [ ] ESLint passes (atomic layering, no relative `fetch`)
- [ ] Manual smoke: kill Tavily key locally → bar shows `no_key`/`down` within 60 s

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (BE) | pytest + pytest-asyncio | `backend/app/health/` | ≥ 80 % |
| Unit (FE) | Vitest + Testing Library | `frontend/src/components/{atoms,molecules,organisms}/` and `hooks/useServiceHealth` | ≥ 80 % |
| A11y (FE) | jest-axe | `ServiceStatusBar`, `StatusPill` | zero violations |
| Network mock (FE) | MSW | Simulate `ok`, `degraded`, `down`, `disabled`, `no_key` payloads | 100 % of status branches |
| Integration | pytest | Real `/api/health/services` with monkeypatched probes | Critical path: cache reuse, parallel probes |
| E2E | Playwright | — | Deferred to V2 |

**Critical test cases:**
- Concurrent refresh under lock (AC-02).
- Probe timeout returns `down`, never propagates (AC-03).
- `placeholderData: keepPreviousData` keeps stale data visible during refetch (AC-05).
- `aria-label` shape and axe compliance (AC-07).

## 8. Environment Variables

No new environment variables. Existing variables consulted by probes:

| Variable | Required | Default | Probe behavior if missing |
|----------|----------|---------|---------------------------|
| `ANTHROPIC_API_KEY` | Yes (V1) | — | `anthropic` → `no_key` |
| `TAVILY_API_KEY` | Yes (V1) | — | `tavily` → `no_key` |
| `OPENAI_API_KEY` | No | — | `openai` stays `disabled` even if present in V1 |
| `GOOGLE_API_KEY` | No | — | `gemini` stays `disabled` in V1 |
| `GITHUB_TOKEN` | No | — | `github_models` stays `disabled` in V1 |
| `DATABASE_URL` | Yes | — | `postgres` → `down` with `"unreachable"` |

Probe thresholds (constants in `registry.py`, not env-driven in V1):
- `CACHE_TTL_S = 30.0`
- `PROBE_TIMEOUT_S = 2.0`
- `LATENCY_DEGRADED_MS = 1500`

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Health probes count against provider rate limits | Med | Med | 30 s server-side cache; LLM probe uses `max_tokens=1`; knowledge probes already paginate to 1 result. |
| A misbehaving probe blocks the snapshot | High | Low | Each probe runs under `asyncio.wait_for(coro, PROBE_TIMEOUT_S)`; failures map to `down`, never re-raise. |
| The bar becomes noisy and distracts users | Med | Med | Default text token is `--text-tertiary`; pulses are reserved for `degraded` only; `prefers-reduced-motion` disables motion entirely. |
| Confusion between `disabled` and `down` | Low | Med | Distinct glyphs (`○` vs `●`) and distinct colors; tooltip always carries explicit text. |
| Endpoint becomes a deanonymized API-key oracle | Med | Low | Endpoint never returns the key or full provider error body — only the mapped `status` + a short, sanitized `message`. |
| Bar adds visible network traffic in DevTools | Low | High | Documented behavior; 60 s interval and `staleTime: 30_000` keep it minimal. |

## 10. Out of Scope

- **Budget / token-usage monitoring** — requires aggregating from the `events` table (`tokens_used`, RF-11). Deferred to a follow-up BRD; `ServiceHealth` keeps `extra="allow"` so a `budget` field can be added non-breakingly.
- **Historical health timeline / uptime chart** — V2.
- **Push notifications, sound alerts, browser notifications** — V2.
- **Admin actions from the bar** (re-probe, disable a service) — V2.
- **Per-user health visibility filtering** — V2; V1 shows the same bar to every authenticated user.
- **Sentry / Datadog / Prometheus integration** — explicitly out of scope per `copilot-instructions.md` §2.
- **Migrating the existing `/api/health` liveness probe** — kept unchanged for compatibility with deployment health checks.
