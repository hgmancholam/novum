# Novum Architecture Summary

> Condensed architecture reference for agents. For full details, see `docs/technical-phase/architecture.md`.

**Last Updated:** 2026-05-26

---

## 1. Architectural Principles (RF-01 to RF-16)

1. **Event log is the source of truth** — All state from append-only `events` table (RF-03)
2. **Stop reasons are enums, never free text** — 7 terminal states map to enum values (RF-02)
3. **Three plugin seams** — Source, StoppingSignal, OutputRenderer (RF §6-ter)
4. **Three not-seams** — Planner, Storage, LLM Provider (deliberately not pluggable in V1)
5. **Read determinism** — Same run replays identically, no live LLM regeneration
6. **Single-server scope** — No Redis, no distributed locks (RF-05)
7. **Honest stops are first-class outcomes** — "Cannot answer" is success, not error (RF-01·E)
8. **UI surfaces the trust contract** — Every guarantee in RF §6-quater has a UI surface (RF-13)

---

## 2. System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT TIER                              │
│  Browser → Vercel CDN (React 19 SPA)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────────┐
│                     APPLICATION TIER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   FastAPI    │  │   Agent FSM  │  │   LLM Layer  │       │
│  │   (Routes)   │  │   (Planner)  │  │  (litellm)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  uvicorn --workers 1 (single process)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     DATA TIER                                │
│  PostgreSQL 16                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐       │
│  │  users   │  │   runs   │  │ events (JSONB payload)│      │
│  └──────────┘  └──────────┘  └──────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Core Data Models

### Run States (FSM — includes RF-14 states)
```
PENDING → CLASSIFYING → PLANNING ←→ PLANCRITIQUING
                           ↓
              ┌──→ SEARCHING ←→ REPLANNING
              │         ↓
              │   SYNTHESIZING
              │         ↓
              └─── JUDGING ──→ STOPPED
```

**Active States:** PENDING, CLASSIFYING, PLANNING, PLANCRITIQUING (RF-14), SEARCHING, REPLANNING (RF-14), SYNTHESIZING, JUDGING
**Terminal States:** STOPPED (with one of 7 stop_reason values)

### Stop Reasons (7 enum values — RF-02)
| Value | Description |
|-------|-------------|
| `judge_confirmed` | Question successfully answered with judge approval |
| `honest_unanswerable` | Insufficient evidence or confidence below threshold |
| `honest_contradiction` | Irreconcilable contradiction between sources |
| `honest_ambiguous` | Question ambiguity detected, cannot proceed |
| `stopped_by_budget` | Token/cost budget exhausted (safety net only) |
| `user_cancelled` | User stopped the run manually |
| `errored` | Unrecoverable error (LLM provider failure, etc.) |

### Event Types (~17 types — RF-03, RF-04, RF-11, RF-14, RF-15)
| Type | Purpose |
|------|---------||
| `QuestionAsked` | Initial question submission |
| `PlanCreated` | Sub-claim decomposition plan |
| `PlanCritiqued` | Plan quality evaluation (RF-14) |
| `PlanRevised` | Iterative plan update (RF-14) |
| `ToolCalled` | Search/retrieval invocation |
| `EvidenceAdded` | Evidence chunk with polarity |
| `ClaimCovered` | Sub-claim satisfied |
| `ClaimUncoverable` | Sub-claim cannot be satisfied |
| `SourceFailed` | Tool/source failure (RF-04) |
| `AmbiguityDetected` | Question ambiguity found |
| `ContradictionDetected` | Source disagreement found |
| `JudgeRuled` | Judge evaluation result |
| `ConfidenceMismatch` | S/J confidence divergence (RF-15) |
| `AgentErrored` | LLM/provider failure (RF-11) |
| `ResumedAfterError` | Recovery from error |
| `ResumedAfterCancel` | Recovery from cancellation |
| `Stopped` | Terminal event with stop_reason |

---

## 4. Plugin Seams

### Source (extensible)
```python
class Source(Protocol):
    async def search(self, query: str) -> list[SearchResult]: ...
    def name(self) -> str: ...
```

### StoppingSignal (extensible)
```python
class StoppingSignal(Protocol):
    def should_stop(self, state: RunState) -> tuple[bool, StopReason | None]: ...
```

### OutputRenderer (extensible)
```python
class OutputRenderer(Protocol):
    def render(self, run: Run) -> str: ...
```

---

## 5. API Contract (Planned)

### REST Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/runs` | Create run |
| GET | `/api/runs/{id}` | Get run |
| GET | `/api/runs/{id}/events` | SSE stream |
| POST | `/api/runs/{id}/resume` | Resume |
| POST | `/api/runs/{id}/fork` | Fork |
| POST | `/api/runs/{id}/cancel` | Cancel |

### SSE Protocol
- Heartbeat: 15s
- Resume: `Last-Event-ID` header
- Close: Server closes after `stop` event

---

## 6. LLM Integration

### Provider
- **GitHub Models** via `GITHUB_TOKEN`
- Single provider in V1

### Model Assignment
| Role | Model |
|------|-------|
| Classifier | `meta/Llama-4-Scout-17B-16E-Instruct` |
| Planner | `deepseek/DeepSeek-V3-0324` |
| Synthesizer | `openai/gpt-5` |
| Judge | `deepseek/DeepSeek-V3-0324` |

### Patterns
```python
# All LLM calls through wrapper
from app.llm import llm

response = await llm.call(
    model="planner",
    messages=[...],
    response_model=PlanResponse  # instructor structured output
)
```

---

## 7. Testing Requirements

### Backend
- pytest + pytest-asyncio
- Real PostgreSQL in tests
- Coverage ≥ 80%
- Golden trace fixtures

### Frontend
- Vitest + Testing Library
- jest-axe for a11y
- MSW for API mocking
- Coverage ≥ 80%

---

## 8. Key Files Reference

| Purpose | Location |
|---------|----------|
| Full architecture | `docs/technical-phase/architecture.md` |
| Tech stack | `docs/technical-phase/tech-stack.md` |
| Requirements | `docs/understanding-phase/requirement-understanding.md` |
| Data flows | `docs/understanding-phase/data-flows-and-diagrams.md` |
| Stopping logic | `docs/understanding-phase/stopping-signal-analysis.md` |
