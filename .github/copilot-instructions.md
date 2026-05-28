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
| Requirements (RF-01…RF-16) | [docs/understanding-phase/requirement-understanding.md](../docs/understanding-phase/requirement-understanding.md) |
| Stopping policy | [docs/understanding-phase/stopping-signal-analysis.md](../docs/understanding-phase/stopping-signal-analysis.md) |
| Confidence calculation | [docs/understanding-phase/confidence-calculation.md](../docs/understanding-phase/confidence-calculation.md) |
| Data flow diagrams | [docs/understanding-phase/data-flows-and-diagrams.md](../docs/understanding-phase/data-flows-and-diagrams.md) |
| **UI prototype (MANDATORY for frontend)** | [docs/understanding-phase/ui-prototype.md](../docs/understanding-phase/ui-prototype.md) |
| Architecture | [docs/technical-phase/architecture.md](../docs/technical-phase/architecture.md) |
| Tech stack | [docs/technical-phase/tech-stack.md](../docs/technical-phase/tech-stack.md) |
| **AI services (MANDATORY for backend LLM/search)** | [docs/technical-phase/ai-services.md](../docs/technical-phase/ai-services.md) |
| Infrastructure | [docs/technical-phase/infrastructure.md](../docs/technical-phase/infrastructure.md) |

**UI Prototype is binding for all frontend work.** It defines:
- **§1** — Design tokens (colors, typography, animations) — never hardcode hex
- **§3** — Panel states (L1-L7, C1-C13, T1-T5) — exact state machines
- **§7** — Microcopy — use exact strings
- **§8** — Atomic Design (atoms → molecules → organisms → templates → pages) — enforced by ESLint
- **§9** — Technical decisions (TanStack Query, localStorage keys, SSE protocol)

**AI Services is binding for all backend LLM/search work.** It defines:
- **§1** — Provider-agnostic LLM interface (`app/llm/client.py::call` via litellm) supporting Anthropic, Google Gemini, OpenAI direct, GitHub Models. **V1 active: Anthropic Claude only.** 5 LLM roles (classifier, planner, synthesizer, judge, meta-judge) + model assignments.
- **§1.3** — All LLM calls through `app/llm/client.py::call` — never call litellm directly
- **§2** — Tavily: web search Source plugin with `search_depth="advanced"`
- **§3** — Wikipedia: second Source plugin for source heterogeneity (RF-04)
- **§5** — Environment variables: `ANTHROPIC_API_KEY` (required), `TAVILY_API_KEY` (required), `GITHUB_TOKEN` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` (optional fallbacks, wired-but-disabled in V1)

When the user asks you to change a decision, update the originating doc — do not silently diverge from it in code.

---

## 2. Stack at a glance

### Backend (`backend/`)
- **Python 3.12** + **FastAPI** + **Pydantic v2** + **uvicorn --workers 1** (single worker preserves in-process advisory lock).
- **asyncio** + **anyio** for primitives. **httpx[http2]** for HTTP. **orjson** for serialization.
- LLM: **litellm** + **instructor** (structured outputs) + **tiktoken** + **tenacity**. **Provider-agnostic interface** (Anthropic / Gemini / OpenAI / GitHub Models). V1 active: **Anthropic Claude** (`ANTHROPIC_API_KEY`).
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
3. **`stop_reason` is an enum, never free text.** All 7 terminal states map to enum values (RF-02): `judge_confirmed`, `honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`, `stopped_by_budget`, `user_cancelled`, `errored`.
4. **Events are append-only.** Resume and fork append; they never mutate or delete. No event editing. ~17 event types (RF-03, RF-04, RF-11, RF-14, RF-15).
5. **Schema evolution = `extra="allow"` + optional keys only.** Adding keys never breaks. Renaming or removing requires an explicit migration.
6. **UI surfaces every trust guarantee.** Hide nothing from RF §6-quater (RF-13).
7. **Type contract FE↔BE:** Pydantic → JSON Schema → `frontend/src/types/events.ts` via `scripts/export_types.py`. Never hand-edit the generated types.
8. **Confidence formula:** `final_confidence = min(S, J)` where S = structural score, J = judge score (RF-12).

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
ANTHROPIC_API_KEY=<sk-ant-...>
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

---

## 7. Agentic Development Architecture

This project uses an orchestrated agentic workflow for development. All agents must follow the defined protocols.

### 7.1 Agents

| Agent | Role | File |
|-------|------|------|
| **Orchestrator** | Workflow controller, task delegation, quality gates | [orchestrator.agent.md](agents/orchestrator.agent.md) |
| **BSA** | Requirements analysis, BRDs, User Stories | [bsa.agent.md](agents/bsa.agent.md) |
| **Auditor** | Document quality audit (BRDs, US, Plans) inside F1/F2 sub-loops | [auditor.agent.md](agents/auditor.agent.md) |
| **Coder** | Implementation, unit tests, best practices | [coder.agent.md](agents/coder.agent.md) |
| **Reviewer** | Code review, scoring (min 9/10), feedback | [reviewer.agent.md](agents/reviewer.agent.md) |

### 7.2 Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| GitHub MCP | GitHub integration (issues, PRs) | `prompts/skills/github-mcp/` |
| UX Frontend | UI/UX best practices, accessibility | `prompts/skills/ux-frontend/` |
| Database | PostgreSQL operations, queries | `prompts/skills/database/` |
| Implementation Plan | Task breakdown, planning | `prompts/skills/implementation-plan/` |
| Audit BRD | Checklist audit of BRDs (F1 sub-loop) | `prompts/skills/audit-brd/` |
| Audit User Story | INVEST + Gherkin audit (F1 sub-loop) | `prompts/skills/audit-user-story/` |
| Audit Implementation Plan | Blind-path detection (F2 sub-loop) | `prompts/skills/audit-implementation-plan/` |
| Unit Test Backend | Python/pytest testing | `prompts/skills/unit-test-backend/` |
| Unit Test Frontend | React/Vitest testing | `prompts/skills/unit-test-frontend/` |
| Memory Protocol | Knowledge management | `prompts/skills/memory-protocol/` |

### 7.3 Workflow

Formal definition: [workflow.yaml](workflow.yaml)
Visual diagram: [workflow.md](workflow.md)

```
Requirement → BSA (BRD + Stories) → Auditor (F1 sub-loop, max 3) → Orchestrator (Plan) → Auditor (F2 sub-loop, max 3) → Coder (Implement + Test)
                                                                                                                          ↓
                                                                                                                     Reviewer (Score)
                                                                                                                          ↓
                                                                                                Score ≥ 9? → Complete
                                                                                                Score < 9? → Back to Coder (max 5 iterations)
```

### 7.4 Memory Protocol (MANDATORY)

All agents MUST:

**Before every task:**
1. Read `.github/memory-bank/shared/project-context.md`
2. Read `.github/memory-bank/indices/knowledge-base-index.md`
3. Read `.github/memory-bank/logs/lessons-learned.md`

**After every task:**
1. Update `.github/memory-bank/logs/decisions-history.md`
2. Update `.github/memory-bank/logs/lessons-learned.md` (if applicable)
3. Update `.github/memory-bank/indices/knowledge-base-index.md` (if new artifacts)

### 7.5 Memory Bank Structure

```
.github/memory-bank/
├── templates/              # Document templates (BRD, User Story, etc.)
├── indices/                # Knowledge base index
├── logs/                   # Decisions history, lessons learned
├── conventions/            # Naming conventions
└── shared/                 # Project context, structure, architecture summary
```

### 7.6 Output Locations

| Artifact Type | Location |
|---------------|----------|
| BRDs | `docs/implementation-phase/brds/` |
| User Stories | `docs/implementation-phase/user-stories/` |
| Implementation Plans | `docs/implementation-phase/implementation-plans/` |
| Audit Reports (F1+F2) | `docs/implementation-phase/audits/` |
| Code Reviews | `docs/implementation-phase/reviews/` |
| Test Documentation | `docs/implementation-phase/unit-tests/` |

### 7.7 Quality Gates

| Gate | Threshold | Action on Failure |
|------|-----------|-------------------|
| Document Audit Score (F1 — BRD/US) | ≥ 9/10 | Return to BSA with feedback (max 3 per phase) |
| Document Audit Score (F2 — Plan) | ≥ 9/10 | Return to Orchestrator with feedback (max 3 per phase) |
| Code Review Score (F4) | ≥ 9/10 | Return to Coder with feedback |
| Max Audit Iterations (per phase) | 3 | Escalate to manual review (F6) |
| Max Review Iterations (F3↔F4) | 5 | Escalate to manual review (F6) |
| Test Coverage | ≥ 80% | Request additional tests |
| Documentation | Required | Request documentation |

### 7.8 Compatibility

This agentic architecture works with:
- **GitHub Copilot** (VS Code)
- **Claude Code** (CLI/Editor)
