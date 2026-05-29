# Implementation Plan — IP-27: Service Health Observability Bar

**Plan ID:** IP-27
**Parent BRD:** [BRD-27 v1.0](../brds/BRD-27-service-health-observability.md)
**Parent User Stories:** _(to be drafted alongside this plan — `US-27-A` service-health-endpoint, `US-27-B` status-bar-ui)_
**Date:** 2026-05-28
**Author:** Orchestrator Agent
**Estimated Effort:** M (≈4–5 h pair-session)
**Iteration:** 1

---

## 1. Summary

Add a public, cached aggregator endpoint `GET /api/health/services` and a thin always-on footer `ServiceStatusBar` (atom → molecule → organism + hook). The backend introduces a new `app/health/` package containing a `HealthRegistry` singleton that runs per-service probes in parallel under `asyncio.wait_for(2.0)`, maps exceptions and latencies to a 5-value `ServiceStatus` enum (`ok | degraded | down | disabled | no_key`), and caches the snapshot in process for 30 s. Probes reuse the existing `Source.health_check()` seam (Tavily, Wikipedia, Semantic Scholar, OpenAlex), a token-free Anthropic ping through `llm.call`, and a 500 ms `SELECT 1` for Postgres. Disabled providers (OpenAI, Gemini, GitHub Models) emit `disabled` synchronously with no network.

The frontend polls the endpoint every 60 s via TanStack Query with `placeholderData: keepPreviousData` so refreshes are silent, and renders the result as horizontally-grouped pills with shadcn `Tooltip` exposing the failure message and a relative `checked_at`. Mounted **once** at the page-level shell so every route inherits it.

**Additive only:** no DB migration, no new env vars, no changes to `StopReason`, FSM, seams, or event log. The existing `/health` liveness probe is left untouched per BRD §10.

RF traceability: **RF-05** (in-process singleton, single worker), **RF-08** (out-of-band telemetry, never feeds run state), **RF-13** (trust surface visible at all times), **RF-16** (degradation visible *before* the user hits "Start research").

---

## 2. Prerequisites

- [x] BRD-27 v1.0 approved by F1 Auditor — locks status taxonomy, mapping rules, AC microcopy.
- [x] `Source.health_check()` already implemented on the four source plugins (`tavily.py:82`, `wikipedia.py:101`, `semantic_scholar.py:273`, `openalex.py`). Verified.
- [x] `SourceRegistry.build()` (`app/sources/registry.py`) is the canonical singleton; **reuse it** instead of instantiating new `Source` objects — avoids double construction and respects `settings.tavily_api_key` gating.
- [x] `llm.call(LLMRole, ...)` exists at `app/llm/client.py:297`. Probe will use `count_tokens` (free of charge on Anthropic) when available, otherwise a `max_tokens=1` `messages.create` against the cheapest role (`LLMRole.CLASSIFIER`).
- [x] `settings.anthropic_api_key`, `settings.tavily_api_key`, `settings.allow_non_anthropic_providers`, `settings.database_url` already in `app/config.py`. No new env vars.
- [x] Routes are mounted **without** a global `/api` prefix at `app/main.py:72`; each router sets its own (`runs.py:23 → prefix="/api/runs"`). The existing `health_router` uses **no prefix** (route = `/health`). The new endpoint therefore needs an explicit `/api/health/services` path — done by adding a **second router** in `app/routes/health.py` so the legacy `/health` keeps working for deployment health checks (BRD §10).
- [x] Frontend `QueryClientProvider` is already wired (used by `useRunHistory`, see `CenterPanelContainer.test.tsx:4`).
- [x] `AppShell` template at `frontend/src/components/templates/AppShell.tsx` is the root layout; it currently has no footer slot — the bar mounts **outside** `AppShell` (sibling, below it) so the 3-panel geometry stays untouched.
- [x] shadcn `Tooltip` and `lucide-react` are in deps.
- [x] `clsx` + `tailwind-merge` (`cn()`) available.
- [x] Motion v12 (`motion/react`) available for dot color transitions.

---

## 3. Task Breakdown

### Phase 1 — Backend

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 1.1 | Create `app/health/` package skeleton with `__init__.py` (empty re-exports). | `backend/app/health/__init__.py` (NEW) | XS | — | layering |
| 1.2 | Define Pydantic models exactly per BRD §4.4: `ServiceStatus`, `ServiceCategory` (StrEnum), `ServiceHealth(model_config=ConfigDict(extra="allow"))`, `HealthSnapshot`. Drop the unused `Literal` import; keep `extra="allow"` so a future `budget` field is non-breaking (BRD §10). | `backend/app/health/models.py` (NEW) | S | 1.1 | AC-01; schema-evolution rule |
| 1.3 | Implement `app/health/probes.py`. Module exports an immutable `PROBES: list[ProbeSpec]` and one `async def probe(spec) -> ServiceHealth` per spec. Concretely:<br>• `ProbeSpec = NamedTuple(id, name, category, runner)` where `runner` is `Callable[[], Awaitable[None]]` (raises on failure, returns `None` on success).<br>• **`_anthropic_runner`** — if `not settings.anthropic_api_key`: raise `NoKeyError("ANTHROPIC_API_KEY")`. Else call `llm.call(LLMRole.CLASSIFIER, messages=[{"role":"user","content":"."}], max_tokens=1, temperature=0)` and discard the response. Wrap so `litellm.AuthenticationError`/HTTP 401/403 maps to `AuthError`, 429 to `RateLimitError`, `httpx.ConnectError`/DNS to `UnreachableError`, 5xx to `UpstreamError(code)`. _(Helpers live in `probes.py`; do not leak SDK exceptions upward.)_<br>• **`_openai_runner` / `_gemini_runner` / `_github_models_runner`** — return a sentinel `DisabledError("not enabled in V1")` immediately. **Do not consult env vars; do not call the network.** Promotion to `ok`/`down` is a future BRD.<br>• **`_tavily_runner`** — `await get_registry().get(SourceType.TAVILY).health_check()`; if `False`, raise `UpstreamError("health_check returned False")`. If `TAVILY` not in registry (no key), raise `NoKeyError("TAVILY_API_KEY")`.<br>• **`_wikipedia_runner`, `_semantic_scholar_runner`, `_openalex_runner`** — same shape, against the corresponding `SourceType`. These never require keys.<br>• **`_postgres_runner`** — `async with get_session() as s: await asyncio.wait_for(s.execute(text("SELECT 1")), timeout=0.5)`. Map `asyncio.TimeoutError` → `TimeoutError`, `sqlalchemy.exc.OperationalError` → `UnreachableError`. | `backend/app/health/probes.py` (NEW) | M | 1.2 | AC-01, AC-03, AC-04; §4.8 |
| 1.4 | Define probe-local exception taxonomy in the same module (`NoKeyError`, `AuthError`, `RateLimitError`, `UnreachableError`, `UpstreamError`, `DisabledError`). Each subclass of `Exception` with a `message: str`. Kept **internal to `app/health/`** — never raised by the route. | same as 1.3 | XS | 1.3 | AC-03 mapping table |
| 1.5 | Implement `HealthRegistry` (singleton) at `app/health/registry.py`. Public API exactly as BRD §4.9:<br>• Class attributes `CACHE_TTL_S = 30.0`, `PROBE_TIMEOUT_S = 2.0`, `LATENCY_DEGRADED_MS = 1500`.<br>• Internal state: `_cache: HealthSnapshot \| None`, `_inflight: asyncio.Future[HealthSnapshot] \| None`, `_lock: anyio.Lock`.<br>• `snapshot()` — if `_cache` exists and `now - _cache.checked_at < CACHE_TTL_S`, return it with `cached=True`. Otherwise call `_refresh_locked()`.<br>• `refresh()` — bypasses cache, always returns `cached=False`.<br>• `_refresh_locked()` — under `_lock`, if `_inflight` is set, `await _inflight`. Otherwise create `_inflight`, run `await self._run_all_probes()`, set `_cache`, resolve future, clear `_inflight`. **Single-flight pattern** (AC-02).<br>• `_run_all_probes()` — `await asyncio.gather(*[self._run_one(spec) for spec in PROBES])` (no `return_exceptions=True` — `_run_one` swallows everything per the mapping table).<br>• `_run_one(spec)` — record `t0 = monotonic()`, run `await asyncio.wait_for(spec.runner(), timeout=PROBE_TIMEOUT_S)`, compute `latency_ms`. On success: `status = OK` if `latency_ms <= LATENCY_DEGRADED_MS` else `DEGRADED` with `message=f"high latency: {latency_ms}ms"`. On `DisabledError → DISABLED`; `NoKeyError → NO_KEY` with `message=f"missing {var}"`; `AuthError → DOWN "authentication failed"`; `RateLimitError → DEGRADED "rate limited"`; `TimeoutError → DOWN "probe timeout"`; `UnreachableError → DOWN "unreachable"`; `UpstreamError(code) → DOWN f"upstream error: {code}"`; anything else → `DOWN "internal probe error"` (defense in depth; logged via structlog). | `backend/app/health/registry.py` (NEW) | M | 1.3, 1.4 | AC-01, AC-02, AC-03, AC-04, AC-08; §4.9 |
| 1.6 | Module-level singleton accessor: `def get_registry() -> HealthRegistry` returning a lazy-instantiated module global (mirrors `app/sources/registry.py:_registry` pattern). | same as 1.5 | XS | 1.5 | AC-02 |
| 1.7 | Wire the new route. In `backend/app/routes/health.py`, **keep** `@router.get("/health")` unchanged. **Add a second router**:<br>```python<br>services_router = APIRouter(prefix="/api/health", tags=["Health"])<br>@services_router.get("/services", response_model=HealthSnapshot)<br>async def services() -> HealthSnapshot:<br>    return await get_registry().snapshot()<br>```<br>This avoids breaking deployment liveness checks that still call `/health` (BRD §10) while satisfying BRD §4.5 / AC-01. | `backend/app/routes/health.py` (MODIFY) | S | 1.5 | AC-01, AC-08 |
| 1.8 | Register the new router in `app/routes/__init__.py`: `from app.routes.health import router as health_router, services_router as health_services_router` + `api_router.include_router(health_services_router)`. | `backend/app/routes/__init__.py` (MODIFY) | XS | 1.7 | AC-01 |
| 1.9 | Regenerate frontend types: run `python scripts/export_types.py`. Confirm `frontend/src/types/health.ts` (or the project's existing aggregated types file) gains `ServiceStatus`, `ServiceCategory`, `ServiceHealth`, `HealthSnapshot`. **Never hand-edit.** | `frontend/src/types/health.ts` (auto-generated) | S | 1.2 | type-contract rule |

### Phase 2 — Frontend

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 2.1 | Add `getServiceHealth(): Promise<HealthSnapshot>` to `frontend/src/lib/api.ts`. **MUST** prefix `API_URL` (user-memory `api-url-rule.md`); use the existing `api.get` helper which already does it. No auth header required (endpoint is public per BRD §4.5). | `frontend/src/lib/api.ts` (MODIFY) | XS | 1.9 | AC-01 |
| 2.2 | Create the atom `StatusDot` (`atoms/StatusDot.tsx`). Props: `{ status: ServiceStatus; size?: number }` extending `HTMLAttributes<HTMLSpanElement>` (per user-memory `typescript-react-props.md` — never use `[key: string]: unknown`). Renders a `motion.span` with `width/height = size ?? 6`, `borderRadius: "50%"`. Color via inline `style.background` mapped from the BRD §4.7 table (uses CSS vars: `var(--accent-success)` etc.). For `degraded`: add Motion `animate={{ opacity: [1, 0.45, 1] }}` with `transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}`; gate the animation behind `useReducedMotion()` from `motion/react`. For `no_key`: render an outline (border `--accent-warning`, transparent background). For `disabled`: hollow circle (border `--text-tertiary`). Co-located test asserts: each status maps to the expected `style.background` / border; reduced-motion disables the pulse. | `frontend/src/components/atoms/StatusDot.tsx` (NEW), `StatusDot.test.tsx` (NEW) | S | 1.9 | §4.7 visual contract |
| 2.3 | Create the molecule `StatusPill` (`molecules/StatusPill.tsx`). Props: `{ service: ServiceHealth }`. Structure: shadcn `<Tooltip><TooltipTrigger asChild><button>…</button></TooltipTrigger><TooltipContent>…</TooltipContent></Tooltip>` with `delayDuration={200}`. Button content: `<StatusDot status=… />` + `<span className="text-xs">{service.name}</span>`. `aria-label` exactly `{name}: {status}, {latency_ms}ms` (or `{name}: {status}` when `latency_ms == null`) per AC-07. Tooltip content: `{message ?? "operational"}` on line 1, `latency_ms != null ? `${latency_ms} ms` : "—"` on line 2, relative `checked_at` on line 3 (via a tiny inline `_relativeTime(iso)` helper: returns `"just now"`, `"30s ago"`, `"2m ago"`, … — no extra dep). The button is `type="button"`, no-op `onClick` (visual only). Co-located test asserts: aria-label shape for both with- and without-latency; tooltip text contains `message` when status != ok; zero axe violations. | `frontend/src/components/molecules/StatusPill.tsx` (NEW), `StatusPill.test.tsx` (NEW) | M | 2.2 | AC-06, AC-07 |
| 2.4 | Create the hook `useServiceHealth` (`hooks/useServiceHealth.ts`). Body:<br>```ts<br>return useQuery<HealthSnapshot>({<br>  queryKey: ["health", "services"],<br>  queryFn: getServiceHealth,<br>  refetchInterval: 60_000,<br>  refetchOnWindowFocus: false,<br>  staleTime: 30_000,<br>  placeholderData: keepPreviousData,<br>  retry: 1,<br>});<br>```<br>Re-export the result type unchanged. Co-located test (MSW + Vitest fake timers) asserts: refetch fires after 60 s; previous data remains visible during the refetch (no `isLoading` transition after first success). | `frontend/src/hooks/useServiceHealth.ts` (NEW), `useServiceHealth.test.ts` (NEW) | S | 2.1 | AC-05 |
| 2.5 | Create the organism `ServiceStatusBar` (`organisms/ServiceStatusBar.tsx`). No props. Internals:<br>• `const { data, isLoading, isError } = useServiceHealth()`.<br>• On first load (`isLoading && !data`): render 9 skeleton dots (`<StatusDot status="disabled" />`) so the bar height never collapses.<br>• On error (`isError && !data`): render the same skeletons; no toast (BRD §9: never noisy).<br>• Otherwise: group `data.services` by `category` in the canonical order `["llm", "search", "knowledge", "storage"]`. Render each group as a `<div className="flex items-center gap-3">` of `StatusPill`. Between groups, render `<span aria-hidden="true" className="px-1 text-(--text-tertiary)/40">·</span>`.<br>• Container: `<footer role="status" aria-live="polite" aria-label="Service health" className="h-7 w-full border-t border-(--glass-border) bg-(--bg-secondary)/40 backdrop-blur-xl"> <div className="flex h-full items-center gap-4 overflow-x-auto px-4">…</div> </footer>`.<br>• **No `fetch` here** — data flows from the hook (atomic-layering rule).<br>Co-located test (MSW + jest-axe) asserts: groups appear in order; group separators rendered with `aria-hidden`; axe-clean; renders 9 skeletons on first load. | `frontend/src/components/organisms/ServiceStatusBar.tsx` (NEW), `ServiceStatusBar.test.tsx` (NEW) | M | 2.3, 2.4 | AC-01, AC-05, AC-06, AC-07; §4.7 |
| 2.6 | Mount the bar **once** at the page-level shell. The bar lives **outside** `AppShell` so the 3-panel geometry is untouched (per Task 2.7 in IP-20 spirit). Concretely: in the root layout page (the file that currently renders `<AppShell …/>` as the top-level element — locate via `grep -rn "<AppShell" frontend/src/pages` and pick the file that wraps the active route), wrap its return as:<br>```tsx<br><div className="flex h-screen flex-col"><br>  <div className="flex-1 min-h-0"><AppShell … /></div><br>  <ServiceStatusBar /><br></div><br>```<br>Confirm the page already has access to `QueryClientProvider` (verified — `CenterPanelContainer.test.tsx:4`). Update the wrapper's existing test to assert the bar is present (one extra `findByRole("status", { name: /Service health/ })`). | the chosen shell page (MODIFY) + its existing test | S | 2.5 | AC-05, RF-13 |
| 2.7 | ESLint sanity: confirm `import/no-restricted-paths` still passes. Atoms must not import from `molecules/`/`organisms/`; molecules not from `organisms/`; organisms not from `pages/`. Run `npm run lint`. | n/a | XS | 2.5 | atomic-layering rule |

### Phase 3 — Tests

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 3.1 | Backend `test_health_probes.py`: parametrized cases per probe exception → mapped `ServiceHealth` (no network — `_*_runner` is monkeypatched). Cover: `NoKeyError → NO_KEY`, `AuthError → DOWN "authentication failed"`, `RateLimitError → DEGRADED "rate limited"`, `TimeoutError → DOWN "probe timeout"`, `UnreachableError → DOWN "unreachable"`, `UpstreamError(503) → DOWN "upstream error: 503"`, `DisabledError → DISABLED`, success → `OK`, success with latency > 1500 ms → `DEGRADED`. Also: `_anthropic_runner` returns immediately when `settings.anthropic_api_key == ""` (no LLM call attempted — patch `llm.call` and assert `not called`) — AC-04. | `backend/tests/test_health_probes.py` (NEW) | M | 1.3, 1.5 | AC-03, AC-04; §4.8 mapping |
| 3.2 | Backend `test_health_registry.py`: cache TTL (two calls within 30 s → second has `cached=True`, same `checked_at`); cache expiry (`monkeypatch.setattr(registry, "_cache_age", lambda: 31.0)` style or freezegun on a monotonic shim — pick the lighter option); **single-flight** (AC-02 — 50 concurrent `asyncio.gather(snapshot() for _ in range(50))`; each probe `runner` is a `Mock` with `assert call_count == 1`; all 50 results share the `checked_at`); `refresh()` bypasses cache; a probe `runner` that raises `RuntimeError("boom")` does NOT bubble up — registry catches anything and maps to `status=down`, `message="internal probe error"`. | `backend/tests/test_health_registry.py` (NEW) | M | 1.5 | AC-02, AC-03, AC-08; §4.9 |
| 3.3 | Backend `test_health_route.py`: `GET /api/health/services` returns 200 + `HealthSnapshot`-shaped body (monkeypatch `get_registry().snapshot` to return a fixed snapshot). One case for each AC-01 invariant: `services[].id` includes anthropic/tavily/wikipedia/postgres; openai/gemini/github_models are `disabled`; `checked_at` within 30 s of `now`. Assert the legacy `GET /health` still returns `{"status":"ok"}` and is registered exactly once (no double-register regression from Task 1.8). | `backend/tests/test_health_route.py` (NEW) | S | 1.7, 1.8 | AC-01 |
| 3.4 | Frontend `StatusDot.test.tsx`: covered in Task 2.2 row. | (already listed) | — | 2.2 | §4.7 |
| 3.5 | Frontend `StatusPill.test.tsx`: covered in Task 2.3 row (aria-label both shapes, tooltip text, axe-clean). | (already listed) | — | 2.3 | AC-06, AC-07 |
| 3.6 | Frontend `useServiceHealth.test.ts`: MSW intercepts `GET /api/health/services`; first request resolves with snapshot A; advance Vitest fake timers by 60_000; second request resolves with snapshot B; assert: between the two, `data` stays equal to snapshot A (no flash to `undefined`) and `isLoading` stays `false` — proves `keepPreviousData` (AC-05). Use a **single `advanceTimersByTime`** call (lesson L-009). | `frontend/src/hooks/useServiceHealth.test.ts` (NEW) | M | 2.4 | AC-05 |
| 3.7 | Frontend `ServiceStatusBar.test.tsx`: render with MSW returning a snapshot containing one of each status; assert groups in order LLM → Search → Knowledge → Storage; `·` separators present with `aria-hidden="true"`; bar exposes `role="status"` + `aria-label="Service health"`; on MSW error, bar renders 9 skeleton dots and does NOT throw; jest-axe reports zero violations. | `frontend/src/components/organisms/ServiceStatusBar.test.tsx` (NEW) | M | 2.5 | AC-01, AC-05, AC-07 |
| 3.8 | Performance assertion (lightweight, no benchmark dep): in `test_health_route.py`, after warming the cache, `time.monotonic()`-bracket 50 sequential calls; assert mean per-call wall time `< 0.020 s` on the CI runner — proves AC-08's "no outbound call on cache hit". Skip on CI if `os.getenv("CI") == "true"` and runner is known-slow; gate behind `@pytest.mark.timing`. | `backend/tests/test_health_route.py` (extend) | S | 3.3 | AC-08 |

### Phase 4 — Docs & memory bank

| # | Task | File(s) | Effort | Depends on |
|---|------|---------|--------|------------|
| 4.1 | Register IP-27 + the new `app/health/` package and `ServiceStatusBar` organism in the knowledge-base index. | `.github/memory-bank/indices/knowledge-base-index.md` | S | end |
| 4.2 | Append a decision entry: 30 s cache TTL chosen vs SSE/push (decision recorded for future re-evaluation), single-flight via `asyncio.Future`, disabled providers are *static* in V1 (no network), bar mounted outside `AppShell` to preserve panel geometry. | `.github/memory-bank/logs/decisions-history.md` | S | end |
| 4.3 | If anything novel surfaced (e.g. Anthropic `count_tokens` not available in the installed SDK version → fallback path) record in lessons-learned. Otherwise skip. | `.github/memory-bank/logs/lessons-learned.md` (optional) | XS | — |

---

## 4. File Modifications

### New files
```
backend/app/health/__init__.py
backend/app/health/models.py
backend/app/health/probes.py
backend/app/health/registry.py
backend/tests/test_health_probes.py
backend/tests/test_health_registry.py
backend/tests/test_health_route.py
frontend/src/components/atoms/StatusDot.tsx
frontend/src/components/atoms/StatusDot.test.tsx
frontend/src/components/molecules/StatusPill.tsx
frontend/src/components/molecules/StatusPill.test.tsx
frontend/src/components/organisms/ServiceStatusBar.tsx
frontend/src/components/organisms/ServiceStatusBar.test.tsx
frontend/src/hooks/useServiceHealth.ts
frontend/src/hooks/useServiceHealth.test.ts
docs/implementation-phase/implementation-plans/IP-27-service-health-observability.md   (this file)
```

### Modified files
```
backend/app/routes/health.py
backend/app/routes/__init__.py
frontend/src/lib/api.ts
frontend/src/types/health.ts                 (regenerated by scripts/export_types.py)
frontend/src/pages/<root-shell>.tsx          (resolved in Task 2.6)
.github/memory-bank/indices/knowledge-base-index.md
.github/memory-bank/logs/decisions-history.md
```

### Untouched (intentional)
```
backend/app/seams/source.py          # Source seam contract unchanged
backend/app/sources/*.py              # health_check() already exists
backend/app/llm/client.py             # called as-is via LLMRole.CLASSIFIER
backend/app/agent/**                  # FSM untouched
frontend/src/components/templates/AppShell.tsx   # geometry untouched
docs/understanding-phase/**           # no RF amendments
```

---

## 5. Database Changes

**None.** Health state is in-process and ephemeral by design (BRD §4.2).

---

## 6. Configuration

**No new env vars.** Probes read existing settings:

| Setting | Used by | Behavior when missing |
|---------|---------|----------------------|
| `settings.anthropic_api_key` | `_anthropic_runner` | `no_key` with `"missing ANTHROPIC_API_KEY"` |
| `settings.tavily_api_key` | `_tavily_runner` (via `SourceRegistry`) | `no_key` with `"missing TAVILY_API_KEY"` |
| `settings.database_url` | `_postgres_runner` | `down` with `"unreachable"` |
| (none — static) | `_openai_runner`, `_gemini_runner`, `_github_models_runner` | `disabled` always in V1 |

Constants (hardcoded in `registry.py`, **not** env-driven in V1 per BRD §8):
- `CACHE_TTL_S = 30.0`
- `PROBE_TIMEOUT_S = 2.0`
- `LATENCY_DEGRADED_MS = 1500`

---

## 7. Sequencing & Risk Notes

1. **Phase 1 must land green before Phase 2 starts** — the type export in Task 1.9 is the contract for the hook in Task 2.4. Skipping it forces hand-written types, violating the type-contract rule.
2. **Single-flight test (Task 3.2) is the highest-value backend test.** A naive `_lock`-free implementation passes every other test and fails this one — it is the only guard against thundering-herd rate-limit incidents.
3. **AC-04 has a real bug-bait**: a "probe" that silently returns `True` when the env var is missing leaks `ok` instead of `no_key`. The test must `patch("app.llm.client.call")` and assert it was **never called** when the key is unset.
4. **`prefers-reduced-motion`** must be honored in `StatusDot` for `degraded`; otherwise users with vestibular disorders see a perpetual pulse. Verified via `useReducedMotion()` mock in `StatusDot.test.tsx`.
5. **API-URL rule** (lesson L-008): the new `getServiceHealth` MUST go through `api.get` so it inherits `API_URL`. A relative `fetch("/api/health/services")` breaks production where the Vercel frontend and Hetzner backend live on different origins.
6. **Bar height is `h-7` (28 px)** — it eats vertical space from the 3-panel area. The shell wrap in Task 2.6 must use `flex flex-col` with `min-h-0` on the panel container, otherwise `AppShell`'s internal scroll regions overflow. Verified in IP-11 layouts.
7. **Risk: disabled providers tempt promotion.** The runners explicitly do not consult `OPENAI_API_KEY` even when present — a future BRD will lift the gate (`settings.allow_non_anthropic_providers`). Until then, the bar must show `disabled` even for users who *have* the key, to match V1 routing.

---

## 8. Done When

- `pytest backend/tests/test_health_*.py` is green and covers ≥ 80 % of `app/health/`.
- `vitest run frontend/src/components/{atoms,molecules,organisms}/*StatusDot* *StatusPill* *ServiceStatusBar*` and `vitest run frontend/src/hooks/useServiceHealth.test.ts` are green and ≥ 80 % coverage.
- `npm run lint` (frontend) and `ruff check` + `pyright` (backend) clean.
- Manual smoke (local, single command): unset `TAVILY_API_KEY` → start backend → load the SPA → within 60 s the Tavily pill flips to `no_key` with the expected tooltip; re-export the key → next refresh flips it back to `ok`. No console errors. No layout shift.
- Bar is present on every authenticated and unauthenticated page (mounted at the shell, not per-route).
