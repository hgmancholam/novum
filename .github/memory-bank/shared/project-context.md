# Novum Project Context

> Central context document for all agents. Read this FIRST before any task.

**Last Updated:** 2026-05-26
**Updated By:** System Initialization
**Project Phase:** Design / Planning

---

## 1. Project Overview

### Mission
Novum is a **self-directing research agent** that:
- Gathers evidence to answer user questions
- Resolves contradictions between sources
- Decides when it has sufficient evidence
- Can honestly report "cannot answer" as a valid outcome

### Core Principles
1. **Event log is the source of truth** — All state derives from the append-only `events` table
2. **Stop reasons are enums, not free text** — Guarantees, not failures
3. **Single-server scope** — No distributed systems in V1
4. **Read determinism** — Same input always produces same output
5. **Honest stops are successes** — "Cannot answer" is a valid outcome

---

## 2. Current State

### Phase
- **Current:** Design / Planning (no production code yet)
- **Documentation:** Comprehensive in `docs/` folder
- **Infrastructure:** Planned (Hetzner VM, Vercel)

### Active Work
- Setting up agentic development workflow
- Defining agents, skills, and memory protocol
- Preparing for implementation phase

### Recent Changes
| Date | Change | Agent |
|------|--------|-------|
| 2026-05-26 | Initial agentic architecture setup | System |

---

## 3. Tech Stack Summary

### Backend
- **Language:** Python 3.12
- **Framework:** FastAPI + Pydantic v2
- **Database:** PostgreSQL 16 + SQLAlchemy 2.0 async + asyncpg
- **LLM:** litellm + instructor (GitHub Models provider)
- **Search:** Tavily (web), Wikipedia API
- **Stopping policy:** A (claim coverage) + D (agreement) + B (judge) + E (honest) + F (budget)

### Frontend
- **Framework:** React 19 + Vite
- **Language:** TypeScript strict
- **Styling:** Tailwind v4 (plugin, no config)
- **Components:** shadcn/ui (Radix), Motion v12
- **State:** Zustand + TanStack Query
- **SSE:** Native EventSource with Last-Event-ID resume

### Infrastructure (Oracle Cloud Always Free)
- **Compute:** VM.Standard.A1.Flex (2 OCPU, 12 GB RAM, ARM64)
- **Frontend CDN:** Vercel (global edge)
- **Reverse proxy:** Caddy v2 (auto-TLS)
- **Domain:** DuckDNS

### Key Constraints
- **Single worker** uvicorn (no distributed locks)
- **No Redis, Docker, LangGraph in V1**
- **Event-sourced architecture**
- **7 stop_reason enum values, never free text**

---

## 4. Requirements Reference (RF-01 to RF-16)

| RF | Title | Summary |
|----|-------|---------|
| RF-01 | Autonomous stopping criterion | Layered policy: A (claim coverage) + D (source agreement) + B (LLM judge) + E (honest stop) + F (budget) |
| RF-02 | Full inspectability | Level 3: structured log + navigable trace UI + diff viewer |
| RF-03 | Re-examinable runs | Event log as source of truth; fork from decision points |
| RF-04 | Graceful handling of messy reality | Ambiguity → honest stop; contradiction → resolution attempt; source failure → cascading fallback |
| RF-05 | Cross-session persistence | Lightweight identity (username only), public runs, fork semantics |
| RF-06 | Question type classification | 5 supported (factual, comparative, definitional, SotA, causal); 3 rejected |
| RF-07 | User-provided context | Optional guidance, not evidence; never cited |
| RF-08 | Live streaming + cancellation | SSE transport, resume from `Last-Event-ID` |
| RF-09 | Run discovery | Direct URL + recent runs list |
| RF-10 | Answer format selection | Prose with citations OR structured report |
| RF-11 | Agent error handling | Retry + recoverable `errored` state with Resume |
| RF-12 | Confidence threshold | User-set minimum; `final_confidence = min(S, J)` |
| RF-13 | UI as trust contract surface | Every guarantee has a visible UI element |
| RF-14 | Plan-quality gate | Plan critic + iterative re-planning |
| RF-15 | Disconfirmation pass | Adversarial queries + source independence + confidence mismatch flag |
| RF-16 | Calibration eval set | 5-question labeled seed set |

Full details: `docs/understanding-phase/requirement-understanding.md`

---

## 5. Architecture Summary

### Three Plugin Seams (Extensible)
1. **Source** — Add new information sources
2. **StoppingSignal** — Add new stopping conditions
3. **OutputRenderer** — Add new output formats

### Three Not-Seams (Fixed in V1)
1. **Planner** — Custom FSM, not pluggable
2. **Storage** — PostgreSQL, not pluggable
3. **LLM Provider** — GitHub Models, not pluggable

### Data Flow
```
User Query → Classifier → Planner → [Search → Synthesize]* → Judge → Answer
                                          ↓
                                    Event Log (append-only)
```

---

## 6. Folder Structure

```
novum/
├── .github/
│   ├── copilot-instructions.md
│   ├── workflow.yaml
│   ├── workflow.md
│   ├── prompts/              # Agents
│   │   ├── orchestrator.agent.md
│   │   ├── bsa.agent.md
│   │   ├── coder.agent.md
│   │   ├── reviewer.agent.md
│   │   └── skills/           # Skills
│   └── memory-bank/          # Shared memory
│       ├── templates/
│       ├── indices/
│       ├── logs/
│       ├── conventions/
│       └── shared/
├── docs/
│   ├── understanding-phase/  # Requirements, analysis
│   ├── technical-phase/      # Architecture, tech stack
│   └── implementation-phase/ # Generated artifacts
│       ├── brds/
│       ├── user-stories/
│       ├── implementation-plans/
│       ├── reviews/
│       └── unit-tests/
├── backend/                  # Python/FastAPI (to be created)
└── frontend/                 # React/Vite (to be created)
```

---

## 7. Active Decisions

| ID | Decision | Status |
|----|----------|--------|
| - | No active decisions yet | - |

---

## 8. Blockers

_None currently identified._

---

## 9. Quick Links

- [Full Requirements](docs/understanding-phase/requirement-understanding.md)
- [Architecture](docs/technical-phase/architecture.md)
- [Tech Stack](docs/technical-phase/tech-stack.md)
- [Workflow Definition](.github/workflow.yaml)
- [Knowledge Base Index](.github/memory-bank/indices/knowledge-base-index.md)
