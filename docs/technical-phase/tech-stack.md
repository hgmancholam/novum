# Tech Stack — Novum

> Library and framework decisions, with rationale. Companion to [infrastructure.md](infrastructure.md) and [architecture.md](architecture.md). RF references point to [requirement-understanding.md](../understanding-phase/requirement-understanding.md).
>
> **Status legend:** ✅ locked · 🤔 proposed (pending confirmation) · ⏳ deferred to V2.

---

## 1. Frontend

All frontend decisions are inherited from [ui-prototype.md](../understanding-phase/ui-prototype.md). Listed here for traceability; do not re-decide.

### 1.1 Runtime and core

| Pick | Choice | Rationale | Reference |
|---|---|---|---|
| Framework | **React 19** ✅ | Modern hooks API, concurrent rendering, mature ecosystem. | ui-prototype §1.1 |
| Build tool | **Vite** ✅ | Sub-second HMR, native ESM, Tailwind v4 plugin integration. | ui-prototype §1.1 |
| Language | **TypeScript strict** ✅ | Required by trust-contract posture: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. | ui-prototype §9.10 |
| Router | **React Router v7** ✅ | Data routers fit the simple route table in ui-prototype §4. TanStack Router was the alternative — discarded for familiarity and lower setup overhead. | new decision |

### 1.2 Styling and components

| Pick | Choice | Rationale | Reference |
|---|---|---|---|
| CSS | **Tailwind v4** ✅ | Utility-first, plugin via `@tailwindcss/vite`, no `tailwind.config.js`, no PostCSS. | ui-prototype §1.1 |
| Component primitives | **shadcn/ui (Radix UI)** ✅ | Unstyled accessible primitives we own and customize. Includes `Sheet` for responsive drawers. | ui-prototype §1.1, §2 |
| Animation | **Motion v12** (`motion/react`) ✅ | Modern Framer Motion successor, smaller bundle, declarative. | ui-prototype §1.1, §1.6 |
| Icons | **Lucide React** ✅ | Consistent icon set, one icon per event type. | ui-prototype §1.1, §3.3 |
| Class utils | **clsx + tailwind-merge** ✅ | Standard combo for conditional Tailwind classes. | ui-prototype §1.1 |
| Markdown | **react-markdown + react-syntax-highlighter** ✅ | Renders agent answers and code blocks. | ui-prototype §1.1 |

### 1.3 State and data

| Pick | Choice | Rationale | Reference |
|---|---|---|---|
| Client state | **Zustand** ✅ | Lightweight, no Redux ceremony. Used only for `userStore`, `selectionStore`. | ui-prototype §1.1, §8.3 |
| Server state | **TanStack Query** ✅ | Cache + invalidation model fits SSE-driven world. Devtools accelerate pair-session debugging. | ui-prototype §9.1 |
| HTTP | **`fetch` native** + `lib/api.ts` wrapper ✅ | No axios — fetch is sufficient and bundle-cheap. | ui-prototype §1.1 |
| SSE | **`EventSource` native** + `lib/sse.ts` wrapper ✅ | W3C standard, supports `Last-Event-ID` resume natively (RF-08). | ui-prototype §1.1, §9.3 |

### 1.4 Frontend dev tooling

| Pick | Choice | Rationale | Reference |
|---|---|---|---|
| Linter | **ESLint** + `eslint-plugin-import` with `import/no-restricted-paths` ✅ | Enforces atomic-design layering as a build error (architecture §). | ui-prototype §8.4, §9.10 |
| Formatter | **Prettier** ✅ | Standard. | ui-prototype §9.10 |
| Pre-commit | **Husky** (lint + typecheck) ✅ | Tests excluded — too slow for pre-commit. | ui-prototype §9.10 |
| Path aliases | **vite-tsconfig-paths** ✅ | `@/atoms/...`, `@/organisms/...` read cleanly. | ui-prototype §9.10 |

### 1.5 Frontend testing

| Pick | Choice | Rationale | Reference |
|---|---|---|---|
| Unit + integration | **Vitest + Testing Library + jest-axe** ✅ | Native Vite integration, Jest-compatible API, accessibility checks on atoms. | ui-prototype §9.6 |
| API mocking | **MSW** ✅ | Mocks at the network layer — same code paths as production. | ui-prototype §9.6 |
| E2E | ⏳ **V2** — Playwright deferred | V1 MVP relies on Vitest + manual smoke. Playwright happy-path added post-MVP. | ui-prototype §9.6 |
| Storybook | ⏳ V2 | Cost-benefit doesn't justify it for a 4–6 h build. | ui-prototype §8.4 |

---

## 2. Backend

### 2.1 Runtime and core

| Pick | Choice | Rationale |
|---|---|---|
| Language | **Python 3.12** ✅ | Pattern matching, async improvements, supported on Ubuntu 22.04 ARM. The LLM/agents ecosystem is canonically Python — every reference implementation, paper code, and SDK lands here first. |
| Web framework | **FastAPI** ✅ | Native async, Pydantic-aware route signatures, OpenAPI schema gratis, SSE-friendly via `sse-starlette`. |
| Validation | **Pydantic v2** ✅ | Discriminated unions cleanly model the ~14 event types. JSON schema export feeds the frontend type generator (see §2.7). |
| ASGI server | **uvicorn** with `--workers 1` ✅ | Single worker preserves in-process advisory lock (RF-05 single-server scope). Multiple workers would require Redis or distributed locks — out of scope. |
| Async primitives | **asyncio** + **anyio** ✅ | `anyio` for `Lock`, `Event`, `TaskGroup` — works on top of asyncio without binding us to one runtime. |
| HTTP client | **httpx[http2]** ✅ | Async, HTTP/2 to LLM providers, mockable with `pytest-httpx`. |
| Config | **pydantic-settings** ✅ | Typed `.env` loading, validation at boot. Misconfigured envs fail fast. |
| Serialization | **orjson** ✅ | 3–5× faster than stdlib `json`. Matters for SSE under load. |

### 2.2 LLM and agents

| Pick | Choice | Rationale |
|---|---|---|
| LLM gateway | **litellm** ✅ | One API for all providers behind the thin `llm.call` wrapper (RF §6-ter not-seam). Native support for GitHub Models. Token tracking gratis. Switch providers in one line (R5 mitigation). |
| Structured outputs | **instructor** ✅ | Forces LLM responses into Pydantic models. Eliminates ~50 LOC of JSON parsing + retry boilerplate per call. |
| Orchestration | **Custom FSM** ✅ (no LangGraph) | `match` over `RunState` Pydantic ~150 LOC. Defensible line-by-line in pair session. LangGraph deferred to V2 (still seam-compatible). |
| Token counting | **tiktoken** ✅ | Budget cap (RF-01·F). OpenAI tokenizer used as approximation for Llama/DeepSeek (precision sufficient for budget purposes). |
| Retries | **tenacity** ✅ | Exponential backoff for LLM (RF-11) and source tools (RF-04). Clean decorator API. |

### 2.3 LLM provider and model assignment

**One provider** in V1: **GitHub Models** (`https://models.github.ai/inference`) — OpenAI-SDK-compatible endpoint, authenticated with a GitHub PAT.

| Role | Model | Family | Rationale |
|---|---|---|---|
| Classifier (RF-06) | `meta/Llama-4-Scout-17B-16E-Instruct` | Meta | Fastest tier, sufficient for 8-class classification. |
| Planner | `deepseek/DeepSeek-V3-0324` | DeepSeek | Strong reasoning, good at structured JSON output. |
| Synthesizer | `openai/gpt-5` | OpenAI | Highest-quality final answer, best citation handling. |
| Judge (RF-01·B) | `deepseek/DeepSeek-V3-0324` | DeepSeek | **Cross-family** vs synthesizer (OpenAI ↔ DeepSeek) → mitigates R6 (judge sycophancy). Strong adversarial reasoning. |

**Single API key:** `GITHUB_TOKEN` (PAT). No Groq, Gemini, OpenAI-direct or Anthropic keys required in V1.

**Cost:** $0 within GitHub Models free-tier limits.

### 2.4 Search and retrieval

| Pick | Choice | Rationale |
|---|---|---|
| Web search | **`tavily-python`** ✅ | 1000 searches/month free, sin tarjeta. Returns clean content (not just URLs) — saves a scraping step. |
| Wikipedia | **`wikipedia-api`** ✅ | Official API, no key, no rate limits relevant for our scale. Gives heterogeneity (RF-04 minimum source set) for D-score. |
| Content extraction | ⏳ V2 (`trafilatura`) | Only needed when V2 sources return raw HTML. Not in V1. |

### 2.5 Persistence

| Pick | Choice | Rationale |
|---|---|---|
| Database engine | **PostgreSQL 16** ✅ | Real ACID, indexed queries for run listing, JSONB for flexible event payloads, mature ARM64 support. Self-hosted on the Oracle VM → $0/mo. |
| Async driver | **`asyncpg`** ✅ | Fastest pure-async Postgres driver for Python. Used via SQLAlchemy's `postgresql+asyncpg://` URL. |
| ORM / query builder | **SQLAlchemy 2.0** (async, typed declarative) ✅ | Industry standard. Native async sessions. Typed `Mapped[]` columns play well with pyright strict. |
| Migrations | **Alembic** ✅ | Canonical companion to SQLAlchemy. Async `env.py` template. Auto-generation from model diffs accelerates the build; reviewed migrations land in `backend/alembic/versions/`. |
| Schema strategy | **Three tables:** `users`, `runs`, `events` (events with `payload JSONB`) ✅ | Postgres handles structural columns; JSONB preserves `extra="allow"` Pydantic flexibility for event payloads. Structural changes go through Alembic; payload-key additions need no migration. |
| Token hashing | **`hashlib.sha256`** of `secrets.token_urlsafe(32)` ✅ | Token already has 256 bits of entropy; SHA-256 is sufficient (no password-stretching needed). Stored in `users.token_hash`. |
| Snapshots | ⏳ V2 (deferred) | Postgres replay of ~30 events is sub-millisecond. Skipping snapshots cuts ~100 LOC + a second schema. |

### 2.6 SSE and observability

| Pick | Choice | Rationale |
|---|---|---|
| SSE server | **sse-starlette** (`EventSourceResponse`) ✅ | Implements ui-prototype §9.3 protocol: heartbeat 15s, `Last-Event-ID` resume, server-closes-after-`Stopped`. |
| Pub-sub internal | `asyncio.Queue` per subscriber + `anyio.Event` for terminal signal ✅ | No Redis needed — single-server scope (RF-05). Each SSE client = one queue fed by the agent loop, with DB-backed catch-up on resume. |
| Logging | **structlog** ✅ | Structured JSON logs, context-binding by `run_id`. Greps cleanly during demo debug. |
| Metrics | **SQL-derived** via `scripts/metrics.py` querying Postgres ✅ | Computes KPIs 1/2/3/5 from RF §6-bis with aggregate SQL queries. No Prometheus in V1. |
| Tracing (LangSmith/Langfuse) | ⏳ V2 | Free tiers exist but introduce another secret + an external dependency at demo time. |

### 2.7 Backend dev tooling

| Pick | Choice | Rationale |
|---|---|---|
| Package manager | **uv** ✅ | 10–100× faster than pip, deterministic lockfile, manages Python versions. De facto standard in 2026. |
| Linter + formatter | **ruff** ✅ | Replaces black + isort + flake8 + pyupgrade + more. Single binary. |
| Type checker | **pyright** strict ✅ | Faster and stricter than mypy. Better at Pydantic edge cases. |
| Tests | **pytest + pytest-asyncio + pytest-httpx** ✅ | Async test support + HTTP mocking without touching network. |
| Test DB | **disposable Postgres** via `pytest-postgresql` (or Docker testcontainer) + Alembic upgrade per session ✅ | Real Postgres in tests catches JSONB / migration bugs that SQLite-in-mem would hide. |
| Golden traces | `tests/fixtures/runs/*.jsonl` loaded into the test DB + outcome snapshot diffs ✅ | Fixtures stay human-readable in git; loader replays them into the events table per test. |
| Pre-commit | **pre-commit** with ruff + pyright + event-schema check + `alembic check` ✅ | Prevents event-contract drift and migration drift between builds. |
| Type sharing FE↔BE | **`datamodel-code-generator`** ✅ | Pydantic → JSON Schema → `frontend/src/types/events.ts`. One command, zero drift. |

---

## 3. Explicitly NOT in V1

For the record (and the pair session):

- ❌ **Docker** — single binary + systemd is simpler. Add Docker only if multi-container ever needed.
- ❌ **Redis / vector DB** — Postgres covers the persistence need; in-process `asyncio.Queue` covers pub-sub at single-server scope.
- ❌ **Managed Postgres (RDS / Neon / Supabase)** — self-hosted on Oracle keeps cost at $0. Reconsider in V2 if HA matters.
- ❌ **LangGraph / LangChain / LlamaIndex** — custom FSM is more defensible.
- ❌ **Celery / RQ** — `asyncio.TaskGroup` is sufficient.
- ❌ **WebSockets** — SSE is the ui-prototype §9.3 spec.
- ❌ **Sentry / Datadog / Prometheus** — structured logs + post-hoc script.
- ❌ **Nginx** — Caddy is simpler (see infrastructure.md).
- ❌ **Cookies** — `localStorage` per ui-prototype §9.2.
- ❌ **Storybook** — V2 per ui-prototype §8.4.
- ❌ **i18n** — V2 per ui-prototype §9.7.
- ❌ **Multiple LLM providers** — GitHub Models alone covers all four roles; reduces secrets to one.

---

## 4. Pending decisions

_None._ All V1 stack decisions are locked. Open infrastructure items (region selection, off-host backup, UptimeRobot) live in [infrastructure.md](infrastructure.md#6-pending-decisions).

---

## 5. Environment variables summary

```env
# Required
GITHUB_TOKEN=<github_pat>
TAVILY_API_KEY=<tvly-...>
DATABASE_URL=postgresql+asyncpg://novum:<password>@localhost:5432/novum

# Optional fallbacks (V2 or for resilience)
OPENROUTER_API_KEY=<...>
GROQ_API_KEY=<...>

# Build-time only (frontend)
VITE_API_URL=https://<oracle-vm>.duckdns.org
VITE_DEMO_SLOWDOWN=1
```
