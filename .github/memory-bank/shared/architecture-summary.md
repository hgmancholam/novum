# Novum Architecture Summary

> Condensed architecture reference for agents. For full details, see `docs/technical-phase/architecture.md`.

**Last Updated:** 2026-06-08

---

## 1. Architectural Principles (RF-01 to RF-16)

1. **Event log is the source of truth** — All state from append-only `events` table (RF-03)
2. **Stop reasons are enums, never free text** — 4 terminal states map to enum values (RF-02, collapsed from 7 in the WP-3 "always answer" refactor)
3. **Three plugin seams** — Source, StoppingSignal, OutputRenderer (RF §6-ter)
4. **Three not-seams** — Planner, Storage, LLM Provider (deliberately not pluggable in V1)
5. **Read determinism** — Same run replays identically, no live LLM regeneration
6. **Single-server scope** — No Redis, no distributed locks (RF-05)
7. **Every question gets an answer** — Ambiguous/sparse/contradictory cases route through `AnswerKind` selection (`best_effort`, `weighted`, `scenario`, …) inside `judge_confirmed`, instead of short-circuiting to a separate "honest stop" terminal (superseded RF-01·E; see WP-3 amendment 2026-05-27)
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

### Research Lanes (3 values — IP-25 Phase A, `Lane` enum)
`select_lane` deterministically routes each run into one of three pipelines based on `ComplexityHint` and question signals:

| Lane | Description |
|------|-------------|
| `fast` | Single-round: Wikipedia + Tavily top-3, mini-judge — for trivial/factual questions |
| `standard` | Default multi-round search → synthesize → judge pipeline (the FSM diagram above) |
| `deep` | Extended pipeline: extra critique passes, ReAct loop, abductive hypotheses, Chain-of-Verification |

### Authority Tiers (4 values — BRD-23 §4.4/§4.7, `AuthorityTier` enum)
Computed per evidence source and used to weight `C_coverage` / `C_independence` in the structural confidence calculation (`confidence/structural.py`):

| Tier | Description |
|------|-------------|
| `primary_authoritative` | Government, standards bodies, primary sources for the domain |
| `reputable_secondary` | Established media, recognized institutions |
| `general` | General web sources without specific authority signal |
| `low_signal` | Low-credibility or unverified sources |

**Active States:** PENDING, CLASSIFYING, PLANNING, PLANCRITIQUING (RF-14), SEARCHING, REPLANNING (RF-14), SYNTHESIZING, JUDGING
**Terminal States:** STOPPED (with one of 4 stop_reason values)

### Stop Reasons (4 enum values — RF-02, WP-3 amendment 2026-05-27)
| Value | Description |
|-------|-------------|
| `judge_confirmed` | Question answered and approved by the judge — carries an `AnswerKind` describing the shape of the answer (`direct`, `weighted`, `scenario`, `tradeoff`, `ethical_redirect`, `best_effort`) |
| `stopped_by_budget` | Token/cost budget exhausted (safety net only) |
| `user_cancelled` | User stopped the run manually |
| `errored` | Unrecoverable error (LLM provider failure, etc.) |

> The three `honest_*` values (`honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`) were **removed** in WP-3 (commit `6ec6f39`, "always answer" refactor). Ambiguous, sparse-evidence and contradictory questions no longer short-circuit to a separate honest-stop terminal — they route through `select_answer_kind` into a `judge_confirmed` outcome with an appropriate `AnswerKind` (typically `best_effort`, `weighted`, or `scenario`). The deprecated `HonestStopSignal` (`backend/app/stopping/signals/honest.py`) is kept as a stub that always returns `DEFER`, for backward compatibility with the layered stopping-policy architecture.

### AnswerKind (6 values — RF-17, selected at `judge_confirmed` time)
Selected by `app.agent.tasks.select_answer_kind` from `(question_type, S, C_coverage, C_agreement, ambiguity_flag)`. Each kind carries a soft confidence ceiling via `app.confidence.kind_ceiling`.

| Value | Description |
|-------|-------------|
| `direct` | Confident, single-answer response |
| `weighted` | Multiple candidates weighted by evidence strength |
| `scenario` | Branch-based answer for predictive/future questions |
| `tradeoff` | Criteria-based comparison for subjective/opinion questions |
| `ethical_redirect` | Redirect for personal/private questions that cannot ethically be answered directly |
| `best_effort` | Lower-confidence answer assembled from partial/sparse evidence |

### Event Types (45 types — RF-03, RF-04, RF-11, RF-14, RF-15, IP-25, IP-26, BRD-26, BRD-29)
The full enumeration lives in `backend/app/domain/enums.py::EventType`. Representative groups:

| Group | Examples |
|-------|----------|
| Question & Planning | `QuestionAsked`, `QuestionNormalized`, `QuestionClassified`, `PlanCreated`, `PlanCritiqued`, `PlanRevised`, `HypothesesGenerated` |
| Search & Evidence | `ToolCalled`, `EvidenceAdded`, `ClaimCovered`, `ClaimUncoverable`, `SourceFailed`, `DeepFetchPerformed`, `QueryReformulated` |
| Detection | `AmbiguityDetected`, `ContradictionDetected`, `ContradictionResolved`, `UserContextChallenged`, `EchoChamberDetected`, `PriorRunHintReplayed` |
| Judge & Confidence | `JudgeRuled`, `ConfidenceMismatch`, `SaturationDetected`, `JudgeProviderDegraded`, `MetaStopVerdict`, `AdversarialObjectionsGenerated`, `DirectedSubclaimsFromObjections` |
| Lane / ReAct / CoVe (IP-25) | `RouteSelected`, `LaneEscalated`, `PlanGapsDetected`, `NoProgressDetected`, `AgentThought`, `AgentAction`, `AgentObservation`, `HypothesisEvaluated`, `HistorySummarized`, `VerificationQuestionsGenerated`, `CoveContradictionDetected` |
| Synthesis | `DraftSynthesized` |
| Error & Recovery | `AgentErrored`, `ResumedAfterError`, `ResumedAfterCancel` |
| Terminal & Cost | `Stopped`, `CostIncurred` |

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
- **Anthropic Claude** via `ANTHROPIC_API_KEY` — single provider in V1, hard-enforced by a `model_validator` in `app/config.py` (raises `ValueError` if `llm_provider != "anthropic"` unless `ALLOW_NON_ANTHROPIC_PROVIDERS=true`)
- Routed by `LLMRole` (classifier, planner, synthesizer, judge — see `app/llm/roles.py`)

### Model Assignment
| Role | Model |
|------|-------|
| Classifier | `anthropic/claude-haiku-4-5` |
| Planner | `anthropic/claude-sonnet-4-6` |
| Synthesizer | `anthropic/claude-sonnet-4-6` |
| Judge | `anthropic/claude-sonnet-4-6` |

### Patterns
```python
# All LLM calls through the client wrapper — never call litellm/httpx directly
from app.llm.client import llm

response = await llm.call(
    role=LLMRole.PLANNER,
    messages=[...],
    response_model=PlanOutput,  # instructor-style structured output
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
