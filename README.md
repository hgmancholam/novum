# Novum

> *A self-directing research agent that gathers evidence, resolves contradictions, and decides when it knows enough.*

---

## What is Novum?

**Novum** is a research agent that earns its conclusions — and tells you, on the record, when it cannot.

Unlike general-purpose AI tools that often fabricate sources or silently stop when *they* feel done, Novum treats "I cannot answer this" as a **first-class successful outcome**, not a failure. It surfaces what it found, what it didn't find, what contradicts what, and why it considers itself finished — making its uncertainty legible and its reasoning defensible.

### The Name

The name comes from Francis Bacon's *Novum Organum* (1620) — a treatise that rejected the idea of reaching conclusions through abstract reasoning alone, and argued instead that knowledge must be earned through systematic observation, careful evidence collection, and inductive reasoning built from the ground up.

Bacon believed scientists should gather data without preconceived notions, analyze it methodically, and draw conclusions only after sufficient evidence had been accumulated. Not before.

**That is exactly what this system does.**

Novum is not a nod to novelty. It is a nod to method — to the idea that a well-reasoned answer is worth more than a fast one, and that knowing when you have enough evidence is as important as knowing how to find it.

---

## Core Features

### 1. Autonomous Stopping Criterion
The agent reasons about sufficiency of evidence using a **layered policy** inspired by:
- **Analysis of Competing Hypotheses** (ACH) for the process
- **GRADE methodology** for certainty grading
- **Popperian falsificationism** for disconfirmation rules

**Seven terminal states:**
- `judge_confirmed` — sufficient evidence, high confidence
- `honest_unanswerable` — question is out of scope or lacks sources
- `honest_contradiction` — unresolvable conflict between sources
- `honest_ambiguous` — question has multiple valid interpretations
- `stopped_by_budget` — safety net triggered (clearly labeled)
- `user_cancelled` — user intervention
- `errored` — technical failure

### 2. Full Inspectability (Level 3)
Every run produces:
- **Timeline of all steps** — what the agent did, what it found, why it stopped
- **Citation traceability** — every claim links to evidence chunks, which link to original sources
- **Contradiction surfaces** — conflicts between sources are documented, not hidden
- **Read-determinism** — opening the same run twice shows identical output (no live LLM regeneration)

### 3. Re-Examinable Runs
- **Event-sourced architecture** — append-only `events` table in PostgreSQL
- **Fork from any decision point** — branch a new attempt when an earlier decision was wrong
- **Public commons model** — all runs are world-readable; anyone can fork any run
- **Idempotent replay** — event payloads contain outputs, so replay reconstructs state without re-calling APIs

### 4. Graceful Handling of Messy Reality
- **Ambiguous questions** → early honest stop with clarification prompts
- **Contradictory sources** → bounded resolution attempt, then documented conflict
- **Source failures** → cascading fallback (retry → reformulate → switch source)
- **Minimum source set** — web search + Wikipedia (heterogeneous, ≥2 independent providers)

### 5. Trust Contract with Users
- **Supported question types declared upfront** (factual, comparative, definitional, state-of-the-art, causal)
- **Out-of-scope rejection is documented** (predictive, pure opinion, personal/private)
- **Every guarantee in the design has a UI surface** — hide nothing
- **Honest epistemics** over raw capability — the wedge is "the tool you can hand to your boss"

---

## Current Status

**Phase:** Design & Planning (no code yet)  
All decisions live as Markdown documentation under `docs/`.

### Architecture Principles

1. **Event log is the source of truth** — append-only, never edited
2. **Stop reasons are an enum** — never free text
3. **Three plugin seams** — Source, StoppingSignal, OutputRenderer (extensible)
4. **Three not-seams** — Planner, storage, and LLM provider are deliberately not pluggable in V1
5. **Single-server scope** — no distributed locks, no Redis, no eventual consistency
6. **Honest stops as first-class outcomes** — "cannot answer" is success, not error

---

## Tech Stack

### Backend
- **Python 3.12** + **FastAPI** + **Pydantic v2** + **uvicorn** (workers=1)
- **PostgreSQL 16** + **SQLAlchemy 2.0 async** + **asyncpg** + **Alembic**
- **LLM:** `litellm` + `instructor` + **GitHub Models** (gpt-5, DeepSeek-V3, Llama-4-Scout)
- **Search:** `tavily-python` (web) + `wikipedia-api`
- **SSE:** `sse-starlette` with 15s heartbeat and `Last-Event-ID` resume
- **Logging:** `structlog` (JSON)
- **Tooling:** `uv`, `ruff`, `pyright strict`, `pytest`

### Frontend
- **React 19** + **Vite** + **TypeScript strict**
- **React Router v7**, **Tailwind v4** (via `@tailwindcss/vite`)
- **shadcn/ui** (Radix), **Motion v12**, **Lucide React**
- **State:** Zustand (client), TanStack Query (server cache)
- **Native `fetch`** + **native `EventSource`** — no axios
- **Testing:** Vitest + Testing Library + jest-axe + MSW

### Infrastructure
- **Frontend:** Vercel Edge CDN (Hobby free tier)
- **Backend:** Oracle Cloud Ampere ARM (free tier, 2 OCPU / 12 GB)
- **Reverse proxy:** Caddy v2 (auto-TLS)
- **Domain:** DuckDNS
- **Cost:** $0/month (within free tiers)

### Explicitly NOT in V1
Docker, Redis, vector DB, LangGraph/LangChain/LlamaIndex, Celery/RQ, WebSockets, Sentry/Datadog, Nginx, cookies, Storybook, i18n, multiple LLM providers.

---

## Documentation Structure

All design documents live under `docs/`:

### Understanding Phase (Requirements & Analysis)
- **[requirement-understanding.md](docs/understanding-phase/requirement-understanding.md)** — Master RF document (RF-01 through RF-16)
- **[stopping-signal-analysis.md](docs/understanding-phase/stopping-signal-analysis.md)** — Layered stopping policy (A/D/B/E/F)
- **[confidence-calculation.md](docs/understanding-phase/confidence-calculation.md)** — `min(S, J)` confidence formula
- **[research-method-selection.md](docs/understanding-phase/research-method-selection.md)** — Methodological lineage (ACH, GRADE, Popper)
- **[ui-prototype.md](docs/understanding-phase/ui-prototype.md)** — L2 product-intent UI spec
- **[data-flows-and-diagrams.md](docs/understanding-phase/data-flows-and-diagrams.md)** — 8 Graphviz diagrams (run sequence, FSM, data flow, ER model)
- **[project-name.md](docs/understanding-phase/project-name.md)** — Why "Novum"?

### Technical Phase (Architecture & Stack)
- **[architecture.md](docs/technical-phase/architecture.md)** — Software design, module boundaries, plugin seams
- **[tech-stack.md](docs/technical-phase/tech-stack.md)** — Library and framework decisions with rationale
- **[infrastructure.md](docs/technical-phase/infrastructure.md)** — Deploy topology, hosting, cost analysis
- **[ai-services.md](docs/technical-phase/ai-services.md)** — LLM provider mapping, model assignment, cost/quotas

### Implementation Phase (In Progress)
- `brds/` — Brief Requirements Documents
- `implementation-plans/` — Module-level implementation guides
- `reviews/` — Code review checklists
- `unit-tests/` — Test strategy and fixtures
- `user-stories/` — Acceptance criteria

---

## Philosophy

> *"Give me a sourced, calibrated answer to this question — and tell me when you cannot."*

Novum is designed for knowledge workers — researchers, PMs, technical leads, consultants — who need **defensible, sourced answers** to research questions: vendor comparisons, technology evaluations, market sizing, policy lookups, due-diligence checks.

The cost of existing AI tools is not just wasted time — it is **uncalibrated trust**. Decisions get made on shaky evidence because the tool never made its uncertainty legible.

**Where Novum is different:**

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

This project is licensed under the [MIT License](LICENSE).
