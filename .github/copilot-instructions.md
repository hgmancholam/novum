# Copilot Instructions — Novum

> Self-directing research agent that gathers evidence, resolves contradictions, and decides when it knows enough.
> Current repo state: **design / planning phase** (no code yet). All decisions live as Markdown under `docs/understanding-phase/` and `docs/technical-phase/`.

---

## 1. Project context

- **Mission:** answer user questions only after accumulating sufficient evidence; "cannot answer" is a first-class successful outcome (not an error).
- **Single-server scope** — no distributed locks, no Redis, no eventual consistency (RF-05).
- **Event log is the source of truth** — append-only `events` table in PostgreSQL (`payload JSONB`). Every state derives from it.
- **Read determinism** — opening any terminal run twice must show identical output. No live LLM regeneration on read.
- **Honest stops are successes** — the 7 `stop_reason` enum values are guarantees, not failures.

Authoritative sources (read these before proposing changes):

| Topic | File |
|---|---|
| Requirements (RF-01…RF-13) | [docs/understanding-phase/requirement-understanding.md](../docs/understanding-phase/requirement-understanding.md) |
| Stopping policy | [docs/understanding-phase/stopping-signal-analysis.md](../docs/understanding-phase/stopping-signal-analysis.md) |
| Data flow diagrams | [docs/understanding-phase/data-flows-and-diagrams.md](../docs/understanding-phase/data-flows-and-diagrams.md) |
| UI prototype | [docs/understanding-phase/ui-prototype.md](../docs/understanding-phase/ui-prototype.md) |
| Architecture | [docs/technical-phase/architecture.md](../docs/technical-phase/architecture.md) |
| Tech stack | [docs/technical-phase/tech-stack.md](../docs/technical-phase/tech-stack.md) |
| Infrastructure | [docs/technical-phase/infrastructure.md](../docs/technical-phase/infrastructure.md) |

When the user asks you to change a decision, update the originating doc — do not silently diverge from it in code.

---

## 2. Stack at a glance

### Backend (`backend/`)
- **Python 3.12** + **FastAPI** + **Pydantic v2** + **uvicorn --workers 1** (single worker preserves in-process advisory lock).
- **asyncio** + **anyio** for primitives. **httpx[http2]** for HTTP. **orjson** for serialization.
- LLM: **litellm** + **instructor** (structured outputs) + **tiktoken** + **tenacity**. Single provider in V1: **GitHub Models** (`GITHUB_TOKEN`).
- Orchestration: **custom FSM** over a `RunState` Pydantic model — **no LangGraph / LangChain / LlamaIndex** in V1.
- Search: **tavily-python** (web), **wikipedia-api**.
- Storage: **PostgreSQL 16** + **SQLAlchemy 2.0 async** + **asyncpg** + **Alembic** migrations. Schema: `users`, `runs`, `events(payload JSONB)`. Single-writer-per-run task registry replaces filelock. **No Redis / vector DB.**
- SSE: **sse-starlette** with heartbeat 15 s and `Last-Event-ID` resume (RF-08).
- Logging: **structlog** (JSON). Tooling: **uv**, **ruff**, **pyright strict**, **pytest** + **pytest-asyncio** + **pytest-httpx**.

### Frontend (`frontend/`)
- **React 19** + **Vite** + **TypeScript strict** (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`).
- **React Router v7**, **Tailwind v4** (plugin via `@tailwindcss/vite` — no `tailwind.config.js`, no PostCSS, no `@tailwind base/components/utilities`; use `@import "tailwindcss";` as the first line of the main CSS).
- **shadcn/ui** (Radix), **Motion v12** (`motion/react`), **Lucide React**, **clsx + tailwind-merge**, **react-markdown + react-syntax-highlighter**.
- State: **Zustand** (`userStore`, `selectionStore` only). Server cache: **TanStack Query**.
- Native **`fetch`** via `lib/api.ts` and native **`EventSource`** via `lib/sse.ts` — no axios.
- Atomic-design layering enforced by **ESLint** `import/no-restricted-paths`. Path aliases via **vite-tsconfig-paths**.

### Explicitly NOT in V1
Docker, Redis, Postgres, vector DB, LangGraph/LangChain/LlamaIndex, Celery/RQ, WebSockets, Sentry/Datadog/Prometheus, Nginx (Caddy instead), cookies (use `localStorage`), Storybook, i18n, multiple LLM providers. Do not suggest them unless explicitly asked.

---

## 3. Architectural rules (do not violate without asking)

1. **Three plugin seams:** `Source`, `StoppingSignal`, `OutputRenderer`. New extensions go behind these protocols (see `backend/app/seams/`).
2. **Three not-seams (V1):** the planner, the storage layer, and the LLM provider are **deliberately not pluggable**. Do not introduce abstractions for them.
3. **`stop_reason` is an enum, never free text.** All 8 terminal states map to enum values (RF-02).
4. **Events are append-only.** Resume and fork append; they never mutate or delete. No event editing.
5. **Schema evolution = `extra="allow"` + optional keys only.** Adding keys never breaks. Renaming or removing requires an explicit migration.
6. **UI surfaces every trust guarantee.** Hide nothing from RF §6-quater (RF-13).
7. **Type contract FE↔BE:** Pydantic → JSON Schema → `frontend/src/types/events.ts` via `scripts/export_types.py`. Never hand-edit the generated types.

---

## 4. Code conventions

### Language policy (mandatory)
All code artifacts in **English**: identifiers, comments, docstrings, log messages, exception messages, hardcoded fallback strings, LLM system prompts, migration descriptions. Runtime chat replies follow the user's language (Spanish by default) via an explicit prompt instruction.

### Python
- `ruff` + `pyright strict` clean. Use `match` statements for FSM transitions.
- Pydantic v2 models with discriminated unions for event types. Prefer `model_config = ConfigDict(extra="allow")` on event models.
- Async-first: every IO path is `async def`. Use `anyio.Lock` / `anyio.Event`, not bare `asyncio.Lock`.
- LLM calls go through `app/llm/client.py` (`llm.call`) — never call `litellm` or `httpx` directly from agent code.
- Retries via `tenacity` decorators with exponential backoff.

### TypeScript / React
- Strict TS. No `any`. Respect `noUncheckedIndexedAccess` — guard array/dict access.
- Atomic design: `atoms → molecules → organisms → templates → pages`. Only `pages/` fetches data.
- Co-locate component tests with **Vitest + Testing Library + jest-axe**. Mock APIs at the network with **MSW**.
- Use `cn()` (clsx + tailwind-merge) for conditional classes.

### Tests
- Backend: `pytest` + `pytest-asyncio` + `pytest-postgresql` for a disposable test DB (Alembic upgrade per session). Golden JSONL traces in `tests/fixtures/runs/` are loaded into the test DB and snapshot-diffed against current code.
- Frontend: **Vitest** for everything (Jest-compatible API). Playwright E2E deferred to V2.
- Pre-commit runs lint + typecheck (tests excluded — too slow).

---

## 5. Environment

Required:
```env
GITHUB_TOKEN=<github_pat>
TAVILY_API_KEY=<tvly-...>
```

Build-time (frontend):
```env
VITE_API_URL=https://<oracle-vm>.duckdns.org
VITE_DEMO_SLOWDOWN=1
```

Never commit secrets. `api_key_copilot.txt` and any `.env*` files must stay gitignored.

---

## 6. Working style for this repo

- **Trace every change to an RF.** If you cannot cite an RF or a doc section, ask before implementing.
- **Prefer editing existing docs over creating new ones.** This repo is design-first; scattered Markdown is a smell.
- **Pending decisions** (tech-stack §4) are open: ask the user before locking them in code.
- **Reply to the user in Spanish by default** (the project owner writes Spanish). Code stays English.
- **No over-engineering.** Target a 4–6 h pair-session build. If a feature costs > ~100 LOC and is not in an RF, push back.
