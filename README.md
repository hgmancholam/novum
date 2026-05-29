# Novum

> *A self-directing research agent that gathers evidence, resolves contradictions, and decides when it knows enough — and tells you, on the record, when it cannot.*

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB.svg)](backend/pyproject.toml)
[![React](https://img.shields.io/badge/react-19-61DAFB.svg)](frontend/package.json)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#current-status)

---

## What is Novum?

**Novum** is a research agent designed for knowledge workers who need **defensible, sourced answers** — vendor comparisons, technology evaluations, market sizing, policy lookups, due-diligence checks.

Unlike general-purpose AI tools that often fabricate sources or silently stop when *they* feel done, Novum treats **"I cannot answer this" as a first-class successful outcome**. It surfaces what it found, what it didn't find, what contradicts what, and why it considers itself finished — making its uncertainty legible and its reasoning defensible.

### The Name

The name comes from Francis Bacon's *Novum Organum* (1620) — a treatise rejecting the idea of reaching conclusions through abstract reasoning alone, and arguing instead that knowledge must be **earned through systematic observation, careful evidence collection, and inductive reasoning**.

Novum is not a nod to novelty. It is a nod to method.

---

## Core Features

### 1. Autonomous Stopping Criterion
The agent reasons about sufficiency of evidence using a **layered policy** inspired by:
- **Analysis of Competing Hypotheses** (ACH) for the process
- **GRADE methodology** for certainty grading
- **Popperian falsificationism** for disconfirmation rules

**Seven terminal states** (`stop_reason` enum, never free text):

| State | Meaning |
|---|---|
| `judge_confirmed` | Sufficient evidence, high confidence |
| `honest_unanswerable` | Out of scope or no sources found |
| `honest_contradiction` | Unresolvable conflict between sources |
| `honest_ambiguous` | Multiple valid interpretations |
| `stopped_by_budget` | Safety net triggered (clearly labeled) |
| `user_cancelled` | User intervention |
| `errored` | Technical failure |

### 2. Full Inspectability (Level 3)
- **Timeline of all steps** — what the agent did, what it found, why it stopped
- **Citation traceability** — every claim links to evidence chunks, which link to original sources
- **Contradiction surfaces** — conflicts between sources are documented, not hidden
- **Read-determinism** — opening the same run twice shows identical output (no live LLM regeneration on read)

### 3. Re-Examinable Runs
- **Event-sourced architecture** — append-only `events` table in PostgreSQL (`payload JSONB`)
- **Fork from any decision point** — branch a new attempt when an earlier decision was wrong
- **Public commons model** — all runs are world-readable; anyone can fork any run
- **Idempotent replay** — event payloads contain outputs, so replay reconstructs state without re-calling APIs
- **SSE resume** — `Last-Event-ID` reconnects pick up where the stream dropped

### 4. Graceful Handling of Messy Reality
- **Ambiguous questions** → early honest stop with clarification prompts
- **Contradictory sources** → bounded resolution attempt, then documented conflict
- **Source failures** → cascading fallback (retry → reformulate → switch source)
- **Heterogeneous sources** — web search (Tavily) + Wikipedia (≥2 independent providers)
- **Meta-judge layer** — second LLM pass guards against premature confirmation

### 5. Trust Contract with Users
- Supported question types declared upfront (factual, comparative, definitional, state-of-the-art, causal)
- Out-of-scope rejection is documented (predictive, pure opinion, personal/private)
- Every guarantee in the design has a UI surface — **hide nothing**

---

## Current Status

**Phase:** Alpha — vertical slice working end-to-end on a single server.

- ✅ Event-sourced backend with FSM agent runner
- ✅ Five-role LLM pipeline (classifier, planner, synthesizer, judge, meta-judge)
- ✅ Tavily + Wikipedia source plugins
- ✅ Streaming UI (SSE) with three-panel layout (History · Center · Trace)
- ✅ Fork & resume from any event
- ✅ Confidence formula `min(S, J)` and 7-value `stop_reason` enum
- 🚧 Hardening, observability, and additional source plugins

See [docs/implementation-phase/implementation-plans/](docs/implementation-phase/implementation-plans/) for the per-module build log (IP-00 through IP-26).

---

## Architecture Principles

1. **Event log is the source of truth** — append-only, never edited. Resume and fork append; they never mutate.
2. **Three plugin seams** — `Source`, `StoppingSignal`, `OutputRenderer` (extensible).
3. **Three not-seams** — planner, storage, and LLM provider are deliberately not pluggable in V1.
4. **Single-server scope** — no distributed locks, no Redis, no eventual consistency.
5. **`stop_reason` is an enum, never free text** — all 7 terminal states are guarantees, not failures.
6. **Schema evolution = `extra="allow"` + optional keys only** — adding keys never breaks.
7. **Confidence = `min(S, J)`** — structural score capped by judge score.

---

## Tech Stack

### Backend (`backend/`)
- **Python 3.12** + **FastAPI** + **Pydantic v2** + **uvicorn** (`--workers 1`)
- **PostgreSQL 16** + **SQLAlchemy 2.0 async** + **asyncpg** + **Alembic**
- **LLM:** `litellm` + `instructor` + `tiktoken` + `tenacity` — provider-agnostic interface, V1 active: **Anthropic Claude**
- **Search:** `tavily-python` (web) + `wikipedia-api`
- **SSE:** `sse-starlette` with 15 s heartbeat and `Last-Event-ID` resume
- **Logging:** `structlog` (JSON)
- **Tooling:** `uv`, `ruff`, `pyright strict`, `pytest` + `pytest-asyncio` + `pytest-postgresql`

### Frontend (`frontend/`)
- **React 19** + **Vite 6** + **TypeScript strict** (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)
- **React Router v7**, **Tailwind v4** (via `@tailwindcss/vite`)
- **shadcn/ui** (Radix), **Motion v12**, **Lucide React**
- **State:** Zustand (client), **TanStack Query** (server cache)
- Native **`fetch`** + native **`EventSource`** — no axios
- **Testing:** **Vitest** + **Testing Library** + **jest-axe** + **MSW**
- Atomic-design layering enforced by ESLint `import/no-restricted-paths`

### Infrastructure
- **Frontend:** Vercel Edge CDN (Hobby free tier)
- **Backend:** Oracle Cloud Ampere ARM (free tier, 2 OCPU / 12 GB)
- **Reverse proxy:** Caddy v2 (auto-TLS)
- **Domain:** DuckDNS
- **Cost:** $0/month (within free tiers)

### Explicitly NOT in V1
Docker, Redis, vector DB, LangGraph/LangChain/LlamaIndex, Celery/RQ, WebSockets, Sentry/Datadog/Prometheus, Nginx, cookies, Storybook, i18n, multiple active LLM providers.

---

## Quick Start

### Prerequisites
- Python 3.12+ and [`uv`](https://github.com/astral-sh/uv)
- Node.js 20+ and `npm`
- PostgreSQL 16 (local or remote)

### Environment

Create `backend/.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/novum
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

Create `frontend/.env`:
```env
VITE_API_URL=http://localhost:8000
```

### Backend
```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --workers 1
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Tests
```bash
# Backend
cd backend && uv run pytest

# Frontend
cd frontend && npm test
```

---

## Repository Layout

```
novum/
├── backend/                     # FastAPI + agent FSM + event log
│   ├── app/
│   │   ├── agent/               # FSM orchestrator, runner, planner
│   │   ├── auth/                # User identity (anonymous + username)
│   │   ├── confidence/          # min(S, J) calculation
│   │   ├── domain/              # Pydantic event models
│   │   ├── llm/                 # Provider-agnostic LLM client (litellm)
│   │   ├── output/              # Output renderers (markdown, json)
│   │   ├── routes/              # FastAPI endpoints
│   │   ├── seams/               # Source / StoppingSignal / OutputRenderer protocols
│   │   ├── sources/             # Tavily + Wikipedia plugins
│   │   ├── sse/                 # SSE streaming with Last-Event-ID resume
│   │   └── stopping/            # Layered stopping policy
│   ├── alembic/                 # Migrations
│   └── tests/                   # pytest suite
├── frontend/                    # React 19 + Vite + Tailwind v4
│   └── src/
│       ├── atoms/ molecules/ organisms/ templates/ pages/   # Atomic design
│       ├── lib/                 # api.ts, sse.ts, constants
│       ├── stores/              # Zustand (userStore, selectionStore)
│       └── types/               # Generated from Pydantic JSON Schema
├── docs/
│   ├── understanding-phase/     # Requirements (RF-01..RF-16), UI prototype
│   ├── technical-phase/         # Architecture, tech stack, AI services
│   └── implementation-phase/    # BRDs, user stories, IP plans, audits, reviews
└── scripts/                     # export_types.py, deploy helpers
```

---

## Documentation

### Understanding Phase
- **[requirement-understanding.md](docs/understanding-phase/requirement-understanding.md)** — Master RF document (RF-01 through RF-16)
- **[stopping-signal-analysis.md](docs/understanding-phase/stopping-signal-analysis.md)** — Layered stopping policy
- **[confidence-calculation.md](docs/understanding-phase/confidence-calculation.md)** — `min(S, J)` confidence formula
- **[research-method-selection.md](docs/understanding-phase/research-method-selection.md)** — Methodological lineage (ACH, GRADE, Popper)
- **[ui-prototype.md](docs/understanding-phase/ui-prototype.md)** — Binding UI spec (design tokens, panel states, microcopy)
- **[data-flows-and-diagrams.md](docs/understanding-phase/data-flows-and-diagrams.md)** — Sequence, FSM, ER diagrams

### Technical Phase
- **[architecture.md](docs/technical-phase/architecture.md)** — Module boundaries and plugin seams
- **[tech-stack.md](docs/technical-phase/tech-stack.md)** — Library decisions with rationale
- **[ai-services.md](docs/technical-phase/ai-services.md)** — LLM roles, model assignments, cost/quotas
- **[infrastructure.md](docs/technical-phase/infrastructure.md)** — Deploy topology and hosting

### Implementation Phase
- **[implementation-plans/](docs/implementation-phase/implementation-plans/)** — Per-module build plans (IP-00..IP-26)
- **[brds/](docs/implementation-phase/brds/)** · **[user-stories/](docs/implementation-phase/user-stories/)** · **[audits/](docs/implementation-phase/audits/)** · **[reviews/](docs/implementation-phase/reviews/)** · **[unit-tests/](docs/implementation-phase/unit-tests/)**

---

## Philosophy

> *"Give me a sourced, calibrated answer to this question — and tell me when you cannot."*

The cost of existing AI tools is not just wasted time — it is **uncalibrated trust**. Decisions get made on shaky evidence because the tool never made its uncertainty legible.

| Capability | ChatGPT | Perplexity | Elicit | **Novum** |
|---|---|---|---|---|
| Cites real sources | partial | yes | yes (academic) | **yes** |
| Says when it cannot answer | rarely | rarely | sometimes | **first-class outcome** |
| Surfaces contradictions in sources | no | weak | weak | **first-class event** |
| Inspectable reasoning trace | no | no | no | **yes (Level 3)** |
| Re-runnable from any decision point | no | no | no | **yes (fork)** |
| Trust contract with the user | implicit | implicit | implicit | **documented** |

**The wedge is honest epistemics, not raw capability.**

---

## License

Released under the [MIT License](LICENSE).
