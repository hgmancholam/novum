# BRD-25: Three-Lane Research Flow (FAST / STANDARD / DEEP)

**Document ID:** BRD-25
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-28
**Implementation Order:** 25 of N
**Assumes shipped:** BRD-21 (always-answer refactor), BRD-22 (complexity-aware planning), BRD-23 (research quality improvements).

---

## 1. Executive Summary

Today every Novum run executes the same linear pipeline (`CLASSIFY → PLAN → SEARCH(loop) → ANALYZE → SYNTHESIZE → JUDGE → STOP`) regardless of question type. The empirical effect: a trivial factual question burns the same budget as a multi-causal essay, a volatile/state-of-art query gets the same plan-then-search-once shape as a definitional one, and the search round itself is **serial across sub-claims** (the dominant cause of the observed ~8 minute STANDARD wall-clock). The system also has no mechanism to course-correct a stale plan mid-run, to recognize echo-chamber evidence, or to admit that a single search round was structurally insufficient before burning four more.

BRD-25 reorganizes the runtime into **three architecturally distinct lanes** selected deterministically from the output of `CLASSIFY`:

- **FAST** — single search round, short synthesis, mini-judge gate. Target latency ≤ 15 s for trivial/direct/static questions. Escapes to STANDARD on rejection (`LaneEscalated`).
- **STANDARD** — the current pipeline plus (a) **parallel search** across sub-claims, (b) **query reformulation** when relevance is uniformly low, (c) **echo-chamber penalty** on `C_diversity`, (d) **dynamic re-decomposition** that adds at most one extra round of directed search when the planner detects gap angles, and (e) a `NoProgressSignal` that forces early synthesis when three consecutive judge rounds fail to move `final_confidence` by ≥ 0.05.
- **DEEP** — abductive hypothesis generation in the planner, a custom **ReAct loop** (≤ 8 steps, enum-closed actions `search | deep_fetch | evaluate_hypothesis | finish`) with hypothesis-confirmed early-exit, history compaction when the loop's context exceeds 15 k tokens, and an **explicit CoVe pass** after synthesis that generates 3 verification questions and re-drafts at most once on contradiction.

The change adds **9 new event types**, **1 new enum (`Lane`)**, **2 new orchestrator branches**, **3 new stopping signals**, **1 new sub-FSM (the ReAct loop)**, and **0 new plugin seams**. The three existing seams (`Source`, `StoppingSignal`, `OutputRenderer`) are preserved unchanged; the ReAct loop is composed entirely on top of `Source`, and the new stopping checkpoints are plain `StoppingSignal` implementations. `StopReason` stays at 4 values (`judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`); honest stops continue to map to `stopped_by_budget` + `AnswerKind.best_effort` + descriptive `stop_rationale` (per Amendment 2026-05-27).

Expected outcomes:

- **STANDARD p50 latency: ~100–220 s → 32–48 s** (Phase 0 alone, from parallel search).
- **FAST p50 latency on trivial queries: ≤ 15 s** (vs. ~60 s under today's pipeline).
- **`judge_confirmed` rate on causal/scenario queries: +25 pp** (from DEEP hypothesis routing).
- **`stopped_by_budget` with intermediate `final_confidence` (0.5–0.7) reduced by ≥ 30 %** (from `NoProgressSignal`).

Phase 0 (parallel search + query reformulation + echo-chamber penalty) is the **critical, unblocking** sub-deliverable; it stands alone and ships even if no other phase ships. Phases A–F build the lane architecture on top.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|---|---|---|
| RF-01·A (layered stopping) | Coverage / agreement / judge gates | **Extends** — adds `NoProgressSignal` (sliding ΔS window), `EchoChamberDetectedEvent` (diversity penalty), FAST mini-judge gate, and DEEP intra-loop signals (`HypothesisConfirmedSignal`, `AllHypothesesRefutedSignal`, `ReactStepCapSignal`, `ReactContradictionSignal`). All implemented as `StoppingSignal` plugins of the existing seam (RF-01). |
| RF-02 (4-value `StopReason` enum) | Honest stops are first-class | **Preserved unchanged.** All new lane-specific honest stops route through `stopped_by_budget` + `AnswerKind.best_effort` + a `stop_rationale` that quotes the reason (e.g. "all hypotheses refuted", "no progress over 3 rounds", "contradicting evidence in CoVe"). |
| RF-03 (event log append-only) | Schema additive | **Preserved unchanged.** All 9 new events are additive (`extra="allow"`, optional new fields `X \| None = None`). No existing event is mutated. Pre-BRD-25 traces replay byte-identically. |
| RF-04 (source heterogeneity) | Tavily + Wikipedia + others | **Extends presentation** — echo-chamber detection across same-source clusters now lowers `C_diversity`; FAST runs both sources in parallel and gates on agreement. The Source seam is untouched. |
| RF-05 (single-server, `uvicorn --workers 1`) | No distribution | **Preserved unchanged.** The ReAct loop is in-process; parallel search uses `asyncio.gather` within the same worker. |
| RF-08 (read determinism) | No live LLM on read | **Preserved unchanged.** Every LLM output (Thought, Action, Observation, hypothesis verdict, CoVe verification, mini-judge) is persisted as an event; replay never re-invokes. |
| RF-11 (SSE stream + resume) | `Last-Event-ID` resume | **Preserved unchanged.** All 9 new events ship via the same SSE channel; the FE consumes them through the existing wrapper. |
| RF-12 (`final_confidence = min(S_effective, J)`) | Confidence formula invariant | **Preserved unchanged.** The echo-chamber multiplier (0.85) and the route selection do not alter the formula — they alter inputs (`C_diversity`) and routing, not the aggregation. |
| RF-13 (UI as trust surface) | Surface every guarantee | **Extends** — the trace panel and (via BRD-24) the center feed render the new events: `RouteSelected`, `LaneEscalated`, `PlanGapsDetected`, `NoProgressDetected`, `HypothesesGenerated`, `AgentThought/Action/Observation`, `HypothesisEvaluated`, `HistorySummarized`, `VerificationQuestionsGenerated`, `CoveContradictionDetected`, `EchoChamberDetected`, `QueryReformulated`. |
| RF-19 (LLM provider) | GitHub Models in V1 | **Preserved unchanged.** All new LLM calls go through `app/llm/client.py::call` with existing `LLMRole` values (no new role added; the FAST mini-judge reuses `JUDGE`, the CoVe verifier reuses `JUDGE`, the hypothesis generator reuses `PLANNER`, the ReAct Thought/Action reuses `PLANNER`). |

**No RF amendments required.** All extensions are within the existing wording.

> **Doc updates (separate PR, in scope of US-25-7):**
> - `advanced-ai-research.md` — full rewrite to describe the 3-lane architecture (already drafted).
> - `stopping-signal-analysis.md` — add the new signals to the priority table.
> - `data-flows-and-diagrams.md` — add per-lane sequence diagrams.

---

## 3. Dependencies

| Depends On | Required For |
|---|---|
| BRD-05 (LLM client) | All new LLM calls go through `llm.call`. |
| BRD-06 (Source seam) | `Source.fetch` (parallel), `Source.fetch_full` (DEEP `deep_fetch` action). |
| BRD-07 (Agent FSM) | New orchestrator branches per lane; no new top-level FSM state — the ReAct loop is a sub-FSM internal to DEEP. |
| BRD-08 (confidence calculation) | `C_diversity` receives the echo-chamber multiplier. `final_confidence` formula unchanged. |
| BRD-09 (StoppingSignals seam) | All new signals are plain `StoppingSignal` plugins. |
| BRD-22 (complexity-aware planning) | `complexity_hint` is one of the three inputs to `select_lane`. |
| BRD-23 (research quality) | `temporal_sensitivity`, `authority_tier`, and `deep_fetch` are reused — DEEP's `deep_fetch` action is the BRD-23 escalation path lifted into the ReAct loop. |

No new env vars. No Alembic migration. No new external service.

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    domain/
      enums.py                              # MODIFY: +Lane, +EventType.{ROUTE_SELECTED,
                                            #          LANE_ESCALATED, PLAN_GAPS_DETECTED,
                                            #          NO_PROGRESS_DETECTED, HYPOTHESES_GENERATED,
                                            #          AGENT_THOUGHT, AGENT_ACTION, AGENT_OBSERVATION,
                                            #          HYPOTHESIS_EVALUATED, HISTORY_SUMMARIZED,
                                            #          VERIFICATION_QUESTIONS_GENERATED,
                                            #          COVE_CONTRADICTION_DETECTED,
                                            #          QUERY_REFORMULATED, ECHO_CHAMBER_DETECTED}
      events.py                             # MODIFY: +14 additive event classes (9 lane events
                                            #          + 2 Phase-0 events + 3 CoVe/history events)
      hypothesis.py                         # NEW: Hypothesis Pydantic model
      mini_judge.py                         # NEW: MiniJudgeVerdict Pydantic model
    agent/
      lane_router.py                        # NEW: select_lane() pure function
      run_state.py                          # MODIFY: +selected_lane, +hypotheses,
                                            #          +redecomposition_count, +max_redecomposition,
                                            #          +confidence_history, +react_history,
                                            #          +react_step_count, +max_react_steps,
                                            #          +cove_rounds, +max_cove_rounds
      orchestrator.py                       # MODIFY: emit RouteSelected; branch per lane;
                                            #          re-decomposition hook; track confidence_history
      tasks/
        search.py                           # MODIFY: parallelize execute_search_round +
                                            #          query reformulation (Phase 0)
        replan.py                           # NEW: identify_plan_gaps()
        hypotheses.py                       # NEW: generate_hypotheses()
        cove.py                             # NEW: generate_verification_questions() + verify_question()
      lanes/
        __init__.py                         # NEW
        fast.py                             # NEW: execute_fast_lane()
        deep.py                             # NEW: execute_deep_lane()
      react/
        __init__.py                         # NEW
        loop.py                             # NEW: run_react_loop()
        actions.py                          # NEW: AgentActionType + Pydantic action models
        prompts.py                          # NEW: REACT_THOUGHT_PROMPT, REACT_ACTION_PROMPT
        history.py                          # NEW: summarize_history_if_needed()
    confidence/
      structural.py                         # MODIFY: echo-chamber penalty on C_diversity (Phase 0)
    stopping/
      no_progress.py                        # NEW: NoProgressSignal (Phase B)
      react_intra_loop.py                   # NEW: 4 ReAct signals (Phase E)
      __init__.py                           # MODIFY: register new signals at correct priority
    llm/
      prompts.py                            # MODIFY: +PLAN_GAPS_PROMPT, +FAST_SYNTH_PROMPT,
                                            #          +FAST_MINI_JUDGE_PROMPT, +HYPOTHESES_PROMPT,
                                            #          +COVE_QUESTIONS_PROMPT,
                                            #          +COVE_VERIFICATION_PROMPT
frontend/
  src/
    types/
      events.ts                             # REGEN: via scripts/export_types.py
  tests/                                    # 30+ new test files (see §8)
```

### 4.2 New enum: `Lane`

```python
# app/domain/enums.py
class Lane(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
```

### 4.3 New events (14 total, all additive)

All events use `model_config = ConfigDict(extra="allow")` and follow the existing `BaseEvent` shape. New fields on **existing** events are not introduced — every new piece of information lives on a new event type.

**Phase 0 — performance + quality (2 events):**

```python
class QueryReformulatedEvent(BaseEvent):
    type: Literal[EventType.QUERY_REFORMULATED] = EventType.QUERY_REFORMULATED
    original_query: str
    reformulated_query: str
    target_claim_id: UUID
    reason: Literal["low_relevance"]

class EchoChamberDetectedEvent(BaseEvent):
    type: Literal[EventType.ECHO_CHAMBER_DETECTED] = EventType.ECHO_CHAMBER_DETECTED
    target_claim_id: UUID
    n_sources: int
    date_window_days: int
    diversity_penalty_applied: float       # 0.85 today
```

**Phase A — telemetry (1 event):**

```python
class RouteSelectedEvent(BaseEvent):
    type: Literal[EventType.ROUTE_SELECTED] = EventType.ROUTE_SELECTED
    lane: Lane
    reason: str
    question_type: QuestionType
    complexity_hint: ComplexityHint
    temporal_sensitivity: TemporalSensitivity | None
```

**Phase B — re-decomposition + no-progress (2 events):**

```python
class PlanGapsDetectedEvent(BaseEvent):
    type: Literal[EventType.PLAN_GAPS_DETECTED] = EventType.PLAN_GAPS_DETECTED
    gaps: list[str]
    extra_sub_claim_ids: list[UUID]

class NoProgressDetectedEvent(BaseEvent):
    type: Literal[EventType.NO_PROGRESS_DETECTED] = EventType.NO_PROGRESS_DETECTED
    delta_3rounds: float
    current_confidence: float
```

**Phase C — FAST escalation (1 event):**

```python
class LaneEscalatedEvent(BaseEvent):
    type: Literal[EventType.LANE_ESCALATED] = EventType.LANE_ESCALATED
    from_lane: Lane
    to_lane: Lane
    reason: str
```

**Phase D — hypotheses (1 event):**

```python
class HypothesesGeneratedEvent(BaseEvent):
    type: Literal[EventType.HYPOTHESES_GENERATED] = EventType.HYPOTHESES_GENERATED
    hypotheses: list[Hypothesis]
```

**Phase E — ReAct (5 events):**

```python
class AgentThoughtEvent(BaseEvent):
    type: Literal[EventType.AGENT_THOUGHT] = EventType.AGENT_THOUGHT
    step: int
    thought: str

class AgentActionEvent(BaseEvent):
    type: Literal[EventType.AGENT_ACTION] = EventType.AGENT_ACTION
    step: int
    action_type: AgentActionType
    args: dict[str, Any]

class AgentObservationEvent(BaseEvent):
    type: Literal[EventType.AGENT_OBSERVATION] = EventType.AGENT_OBSERVATION
    step: int
    result_summary: str
    tokens: int

class HypothesisEvaluatedEvent(BaseEvent):
    type: Literal[EventType.HYPOTHESIS_EVALUATED] = EventType.HYPOTHESIS_EVALUATED
    hypothesis_id: UUID
    verdict: Literal["confirmed", "refuted"]
    evidence_ids: list[UUID]

class HistorySummarizedEvent(BaseEvent):
    type: Literal[EventType.HISTORY_SUMMARIZED] = EventType.HISTORY_SUMMARIZED
    steps_summarized: int
    summary_tokens: int
```

**Phase F — explicit CoVe (2 events):**

```python
class VerificationQuestionsGeneratedEvent(BaseEvent):
    type: Literal[EventType.VERIFICATION_QUESTIONS_GENERATED] = EventType.VERIFICATION_QUESTIONS_GENERATED
    questions: list[str]

class CoveContradictionDetectedEvent(BaseEvent):
    type: Literal[EventType.COVE_CONTRADICTION_DETECTED] = EventType.COVE_CONTRADICTION_DETECTED
    question: str
    contradicting_evidence: str
```

### 4.4 Phase 0 — Performance fix (critical, unblocking)

**Parallel search.** `execute_search_round` extracts a private `_search_one_claim(claim, cascade, days_filter, state) -> list[BaseEvent]` that does NOT mutate state. The outer loop becomes:

```python
results = await asyncio.gather(*[_search_one_claim(c, ...) for c in claims])
for events in results:               # apply in deterministic claim order
    for ev in events:
        state.apply(ev)
```

This preserves replay determinism (events apply in the same order they would have under the serial loop) while parallelizing the I/O. Expected: 5 sub-claims × (2.5–11 s) → max ≈ 11 s instead of sum ≈ 25–55 s.

**Query reformulation.** Inside `_search_one_claim`, after the Tavily call: if **all** Tavily results have `relevance_score < 0.3`, a single second call is issued with reformulated query `f"{claim.text} {state.question[:40]}"`. Emits `QueryReformulatedEvent`. **One reformulation per claim**, no loop.

**Echo-chamber penalty.** `calculate_diversity` (or new helper `_apply_echo_chamber_penalty`) inspects per-claim evidence: if `n_sources >= 3` AND all have `source_published_date` AND span < 7 days AND `C_agreement == 1.0`, multiplies `C_diversity *= 0.85` and emits `EchoChamberDetectedEvent`. The multiplier is bounded — never iterated; if the cluster grows, the multiplier is not re-applied.

### 4.5 Phase A — Route selection (telemetry-only at first ship)

```python
# app/agent/lane_router.py
def select_lane(
    question_type: QuestionType,
    complexity_hint: ComplexityHint,
    temporal_sensitivity: TemporalSensitivity | None,
    ambiguity_detected: bool,
) -> tuple[Lane, str]:
    """
    FAST   ⟺ question_type ∈ {DIRECT_FACTUAL, DEFINITIONAL}
            AND complexity_hint == TRIVIAL
            AND temporal_sensitivity in {None, STATIC, SLOW_CHANGING}
            AND not ambiguity_detected

    DEEP   ⟺ complexity_hint == DEEP
            OR question_type ∈ {CAUSAL, SCENARIO, PREDICTIVE_FUTURE} AND complexity_hint != TRIVIAL

    STANDARD ⟺ default

    Guards:
      - PREDICTIVE_FUTURE never routes to FAST (force STANDARD even if TRIVIAL).
      - REALTIME temporal sensitivity never routes to FAST.
    """
```

**Ship sequence.** Phase A first ships as **telemetry-only**: `RouteSelectedEvent` is emitted, but the orchestrator still runs the STANDARD pipeline for every lane. After 1 week of production data on `lane=DEEP` traffic (must be ≥ 10 % to justify Phase E), Phase C and Phase E activate.

### 4.6 Phase B — Dynamic re-decomposition + `NoProgressSignal`

**Re-decomposition** runs once per STANDARD run, gated by `S_raw < threshold + 0.10` AND `redecomposition_count < max_redecomposition` (default 1). When triggered, `identify_plan_gaps` calls the planner with `PLAN_GAPS_PROMPT` — returns ≤ 3 gap descriptions, converted into new `SubClaim` entries, emits `PlanGapsDetectedEvent`, transitions `ANALYZING → SEARCHING`.

**`NoProgressSignal`** fires when `len(state.confidence_history) >= 3` AND `state.confidence_history[-1] - state.confidence_history[-3] < 0.05`. It does **not** terminate the run directly — it forces `SYNTHESIZING` with the evidence on hand and lets the judge + best-effort fallback decide the final stop. Emits `NoProgressDetectedEvent`. Registered at **medium priority**: after `BudgetExhausted` and `UserCancelled`, before any lane-specific signal.

### 4.7 Phase C — FAST lane

`execute_fast_lane(state) -> StopReason | Literal["escalate"]`:

1. **One** parallel search round (Wikipedia top-3 + Tavily top-3) on the original question text — no sub-claims.
2. Synthesis with `FAST_SYNTH_PROMPT` (≤ 2 sentences, inline citations).
3. Mini-judge with `FAST_MINI_JUDGE_PROMPT` returning structured `MiniJudgeVerdict { ok: bool, j_score: float, reason: str }` via `instructor`.
4. If `S_effective >= 0.85 AND mini_judge.ok` → `judge_confirmed`. Else → `"escalate"`.

On escalation, the orchestrator emits `LaneEscalatedEvent(from=FAST, to=STANDARD, reason=mini_judge.reason)` and runs the STANDARD pipeline normally. **No evidence is discarded** — the search results from FAST become the seed evidence for STANDARD's first round.

**LLM-call budget on happy path: 2** (synth + mini-judge). One Source call (parallel Tavily + Wikipedia) on the search side. Target wall-clock ≤ 15 s.

### 4.8 Phase D — Abductive hypotheses

`generate_hypotheses(state)` runs in the planner phase when `question_type ∈ {CAUSAL, SCENARIO, PREDICTIVE_FUTURE}` OR `AnswerKind == BEST_EFFORT` OR `selected_lane == DEEP`. Returns 2–4 `Hypothesis { id, text, priority, verdict: pending, evidence_ids: [] }`. Emits `HypothesesGeneratedEvent`.

In STANDARD (when triggered), hypotheses **enrich the synthesizer prompt** for scenario answers (each confirmed hypothesis becomes a labeled scenario block with its individual `j_score`). They do not change the search loop in STANDARD.

In DEEP, hypotheses are the **driver** of the ReAct loop (§4.9).

### 4.9 Phase E — DEEP lane (ReAct loop)

`execute_deep_lane(state) -> StopReason`:

1. Generate hypotheses (reuse Phase D).
2. Run `run_react_loop(state, max_steps=8)`.
3. Synthesize using the ReAct history as context.
4. Judge.
5. CoVe pass (Phase F).
6. Return `StopReason`.

**ReAct loop contract (`react/loop.py`):**

- Each step: (a) `Thought` LLM call (planner role) emits `AgentThoughtEvent`; (b) `Action` LLM call returns a Pydantic `AgentActionUnion` (discriminated by `type`); (c) `execute_action` dispatches:
  - `SearchAction { query, source_hint }` → `Source.fetch` → emits `EvidenceAddedEvent` + `AgentObservationEvent`.
  - `DeepFetchAction { url }` → `Source.fetch_full` → emits `DeepFetchPerformedEvent` (from BRD-23) + `AgentObservationEvent`.
  - `EvaluateHypothesisAction { hypothesis_id, verdict }` → updates `state.hypotheses[i].verdict` + emits `HypothesisEvaluatedEvent`.
  - `FinishAction { reason }` → exits loop.
- Step counter advances only on a valid action; invalid `AgentActionUnion` parse → reprompt without consuming a step.
- History compaction: when `total_history_tokens > 15_000`, `summarize_history_if_needed` invokes the synthesizer to compress `history[:-4]` (last 4 steps stay verbatim). Emits `HistorySummarizedEvent`.

**Intra-loop stopping signals (`stopping/react_intra_loop.py`):**

| Signal | Fires when | Decision |
|---|---|---|
| `HypothesisConfirmedSignal` | ≥ 1 hypothesis with `verdict=confirmed` AND `S_effective >= threshold` | exit loop → SYNTHESIZE → expect `judge_confirmed` |
| `AllHypothesesRefutedSignal` | All hypotheses `verdict=refuted` | exit loop → SYNTHESIZE in fallback mode → `stopped_by_budget` + `best_effort` (rationale: "all hypotheses refuted") |
| `ReactStepCapSignal` | `step >= max_react_steps` | exit loop → SYNTHESIZE in fallback mode → `stopped_by_budget` + `best_effort` (rationale: "react step cap") |
| `ReactContradictionSignal` | ≥ 2 confirmed hypotheses backed by primary-authoritative evidence that mutually contradict | exit loop → SYNTHESIZE in fallback mode → `stopped_by_budget` + `best_effort` (rationale: "contradictory authoritative evidence") |

All four are `StoppingSignal` plugins of the existing seam; their priority is **below** `BudgetExhausted` and `UserCancelled`, **above** the standard judge-loop cap.

### 4.10 Phase F — Explicit CoVe in DEEP

After `SYNTHESIZING` and **before** the final judge:

1. `generate_verification_questions(draft)` — synthesizer role, returns 3 questions via `instructor`. Emits `VerificationQuestionsGeneratedEvent`.
2. For each question: `verify_question(question, draft)` — judge role, runs a small Source search (Tavily top-2 within Wikipedia + Tavily), returns `CoveVerdict { contradicts: bool, evidence: str }`.
3. If ≥ 1 verdict has `contradicts=True` AND `state.cove_rounds < max_cove_rounds` (default 1): emit `CoveContradictionDetectedEvent`, re-draft synthesizer with contradiction context, increment `cove_rounds`, loop once. Otherwise accept the draft.

**Cap is hard.** Even with contradictions, `cove_rounds=1` terminates the CoVe loop — the judge then sees the second draft and decides; if it still rejects, the standard `stopped_by_budget` + `best_effort` path takes over.

### 4.11 RunState additions

All additive, all backward-compatible:

```python
class RunState(BaseModel):
    # ... existing ...
    selected_lane: Lane | None = None
    hypotheses: list[Hypothesis] = []
    redecomposition_count: int = 0
    max_redecomposition: int = 1
    confidence_history: list[float] = []        # appended after each JudgeRuled
    react_history: list[ReactStep] = []
    react_step_count: int = 0
    max_react_steps: int = 8
    cove_rounds: int = 0
    max_cove_rounds: int = 1
```

### 4.12 What does NOT change

- The 3 plugin seams (`Source`, `StoppingSignal`, `OutputRenderer`).
- The 4-value `StopReason` enum.
- `final_confidence = min(S_effective, J)`.
- The judge LLM provider, the planner/synthesizer/classifier role assignments (no new `LLMRole`).
- The SSE protocol (new events ship via the existing channel).
- The database schema (events are serialized JSONB; new fields land in `payload` without DDL).

---

## 5. Functional Requirements

| FR | Description | Verification |
|---|---|---|
| FR-25-01 | `execute_search_round` issues all sub-claim searches in parallel via `asyncio.gather`; event ordering per claim is preserved on persistence. | AC-01 |
| FR-25-02 | When all Tavily results for a claim have `relevance_score < 0.3`, one reformulated query is issued and `QueryReformulatedEvent` is emitted. | AC-02 |
| FR-25-03 | When ≥ 3 sources for the same claim are dated within < 7 days and `C_agreement == 1.0`, `C_diversity` is multiplied by 0.85 and `EchoChamberDetectedEvent` is emitted. | AC-03 |
| FR-25-04 | After `CLASSIFY`, `RouteSelectedEvent` is emitted with `lane`, `reason`, `question_type`, `complexity_hint`, `temporal_sensitivity`. | AC-04 |
| FR-25-05 | `select_lane` returns FAST only when `complexity_hint=TRIVIAL` AND `question_type ∈ {DIRECT_FACTUAL, DEFINITIONAL}` AND `temporal_sensitivity ∈ {None, STATIC, SLOW_CHANGING}`; PREDICTIVE_FUTURE and REALTIME force STANDARD minimum. | AC-05 |
| FR-25-06 | STANDARD runs trigger re-decomposition at most once per run (`redecomposition_count` bounded by `max_redecomposition=1`) and only when `S_raw < threshold + 0.10` AND budget remains. | AC-06 |
| FR-25-07 | `NoProgressSignal` fires when `len(confidence_history) >= 3` AND `confidence_history[-1] - confidence_history[-3] < 0.05`; the run is steered to `SYNTHESIZING`, not terminated directly. | AC-07 |
| FR-25-08 | FAST lane terminates the run with `judge_confirmed` when `S_effective >= 0.85 AND mini_judge.ok`. Otherwise emits `LaneEscalatedEvent` and the orchestrator runs STANDARD on the same `RunState`. | AC-08 |
| FR-25-09 | Hypotheses are generated when `question_type ∈ {CAUSAL, SCENARIO, PREDICTIVE_FUTURE}` OR `AnswerKind == BEST_EFFORT` OR `selected_lane == DEEP`; `HypothesesGeneratedEvent` carries 2–4 hypotheses with unique IDs. | AC-09 |
| FR-25-10 | DEEP runs the ReAct loop with `max_react_steps=8`; the cap is a hard invariant (test-enforced). | AC-10 |
| FR-25-11 | Every ReAct step persists `AgentThoughtEvent`, `AgentActionEvent`, and `AgentObservationEvent` in that order. Invalid actions do not advance `react_step_count`. | AC-11 |
| FR-25-12 | When ReAct history exceeds 15 k tokens, `summarize_history_if_needed` compacts `history[:-4]` and emits `HistorySummarizedEvent`. | AC-12 |
| FR-25-13 | The 4 ReAct intra-loop signals (`HypothesisConfirmedSignal`, `AllHypothesesRefutedSignal`, `ReactStepCapSignal`, `ReactContradictionSignal`) are registered at correct priority and produce the correct `StopReason`. | AC-13 |
| FR-25-14 | DEEP CoVe generates exactly 3 verification questions; on ≥ 1 contradiction AND `cove_rounds < max_cove_rounds`, the synthesizer re-drafts once. | AC-14 |
| FR-25-15 | `StopReason` enum remains 4-valued. Honest stops via DEEP signals map to `stopped_by_budget` + `AnswerKind.best_effort` + a descriptive `stop_rationale`. | AC-15 |
| FR-25-16 | `final_confidence = min(S_effective, J)` is unchanged by all phases. | AC-16 |
| FR-25-17 | All 14 new events ship via the existing SSE channel; FE types regenerated via `scripts/export_types.py`. | AC-17 |

---

## 6. Non-Functional Requirements

| NFR | Requirement | Verification |
|---|---|---|
| NFR-25-01 | STANDARD p50 wall-clock ≤ **48 s** post Phase 0 (down from 100–220 s baseline). | `time` on `smoke_ip21.py` + golden trace replay. |
| NFR-25-02 | FAST p50 wall-clock ≤ **15 s** on trivial questions. | Smoke fixture. |
| NFR-25-03 | DEEP p95 wall-clock ≤ **300 s** with ReAct cap enforced. | Smoke fixture. |
| NFR-25-04 | Replay determinism: golden traces pre-BRD-25 replay byte-identically; golden traces post-BRD-25 are themselves deterministic across replays. | AC-18 |
| NFR-25-05 | Single-server / single-worker (RF-05). No new infra dependency. | Architecture review. |
| NFR-25-06 | All new prompts, identifiers, log messages and `stop_rationale` strings are English. User-facing replies follow the existing user-language rule. | Manual + grep. |
| NFR-25-07 | All new code passes `pyright strict` and `ruff` with zero warnings. | CI. |
| NFR-25-08 | Coverage ≥ 80 % on every new file (`lane_router.py`, `tasks/replan.py`, `tasks/hypotheses.py`, `tasks/cove.py`, `lanes/fast.py`, `lanes/deep.py`, `react/*.py`, `stopping/no_progress.py`, `stopping/react_intra_loop.py`). | `pytest --cov`. |
| NFR-25-09 | `LaneEscalated` does not discard evidence — the seed evidence from FAST is reused by STANDARD. | AC-19 |

---

## 7. Acceptance Criteria

| AC | Statement |
|---|---|
| AC-01 | `tests/test_agent_tasks_search.py::test_execute_search_round_runs_claims_in_parallel` — mocked per-source `asyncio.sleep` confirms total ≈ max(per-claim), not sum. |
| AC-02 | Unit test: all Tavily relevance < 0.3 → exactly one reformulated query + `QueryReformulatedEvent`; at least one ≥ 0.3 → no reformulation. |
| AC-03 | Unit test: 3 sources for the same claim with dates within 5 days + `C_agreement=1.0` → `C_diversity` multiplied by 0.85 + `EchoChamberDetectedEvent` emitted. |
| AC-04 | Integration test: every run emits `RouteSelectedEvent` between `QuestionClassifiedEvent` and `PlanCreatedEvent` with all 5 fields populated. |
| AC-05 | Table-driven unit tests on `select_lane`: every combination in the matrix produces the documented `Lane` and `reason`; PREDICTIVE_FUTURE + TRIVIAL → STANDARD; REALTIME + DEFINITIONAL + TRIVIAL → STANDARD. |
| AC-06 | Integration test: `S_raw=0.6` with budget remaining → re-decomp triggers exactly once; `S_raw=0.9` → re-decomp skipped; subsequent rounds never re-trigger re-decomp. |
| AC-07 | Unit test on `NoProgressSignal`: `confidence_history=[0.55, 0.56, 0.57]` → fires; `[0.55, 0.60, 0.66]` → does not fire; `[0.55, 0.57]` → does not fire (fewer than 3). |
| AC-08 | Integration test: FAST happy path → 2 LLM calls + `judge_confirmed`; FAST rejection → `LaneEscalatedEvent` + STANDARD run completes successfully reusing the seed evidence. |
| AC-09 | Integration test: CAUSAL question → `HypothesesGeneratedEvent` emitted, 2–4 hypotheses with unique IDs; DIRECT_FACTUAL → no `HypothesesGeneratedEvent`. |
| AC-10 | Invariant test: across 100 fuzzed DEEP runs, `react_step_count` never exceeds `max_react_steps`. |
| AC-11 | Unit test: each ReAct step emits exactly one `AgentThoughtEvent` + one `AgentActionEvent` + one `AgentObservationEvent` in order; an invalid action does not produce events and does not advance the counter. |
| AC-12 | Unit test: forcing history to 16 k tokens triggers `HistorySummarizedEvent` with `steps_summarized == total_steps - 4`. |
| AC-13 | Unit test per signal: each of the 4 ReAct signals fires under its documented condition and produces the documented decision (`judge_confirmed` for `HypothesisConfirmedSignal`, `stopped_by_budget` + `best_effort` for the other three with the documented `stop_rationale`). |
| AC-14 | Unit test on CoVe: 3 questions generated; 1 contradiction + `cove_rounds=0` → re-draft + `cove_rounds=1`; second contradiction at `cove_rounds=1` → no further re-draft. |
| AC-15 | Integration test: every honest-stop path emits a `Stopped` event with `stop_reason="stopped_by_budget"`, `answer_kind="best_effort"`, and a non-empty `stop_rationale`. |
| AC-16 | Property test on `_fold_events`: across all golden traces, `final_confidence == min(S_effective, J)` after replay. |
| AC-17 | CI check: `python scripts/export_types.py` produces empty diff after BRD-25 implementation; `frontend/src/types/events.ts` contains the 14 new event types. |
| AC-18 | Golden-trace replay: pre-BRD-25 traces in `tests/fixtures/runs/` replay byte-identically; post-BRD-25 fixtures are stable across 10 replays. |
| AC-19 | Integration test: on `LaneEscalated`, the `RunState.evidence` carried into STANDARD contains the FAST-collected evidence (no truncation). |

---

## 8. Test Plan (binding)

**New backend test files:**

| File | Phase | Scope |
|---|---|---|
| `tests/test_agent_tasks_search.py` (extended) | 0 | parallel + reformulation |
| `tests/test_confidence_structural.py` (extended) | 0 | echo-chamber penalty |
| `tests/test_domain_events.py` (extended) | all | serialization of 14 new events |
| `tests/test_agent_lane_router.py` | A | `select_lane` truth table |
| `tests/test_agent_orchestrator_route.py` | A | `RouteSelectedEvent` emission |
| `tests/test_agent_tasks_replan.py` | B | `identify_plan_gaps` |
| `tests/test_stopping_no_progress.py` | B | `NoProgressSignal` |
| `tests/test_agent_lanes_fast.py` | C | FAST lane happy path + escalation |
| `tests/test_agent_tasks_hypotheses.py` | D | hypothesis generation |
| `tests/test_agent_orchestrator.py` (extended) | D, E | hypothesis routing per question_type |
| `tests/test_agent_react_loop.py` | E | loop termination, invalid actions, history summarization, event emission |
| `tests/test_agent_lanes_deep.py` | E | DEEP end-to-end |
| `tests/test_stopping_react_intra_loop.py` | E | 4 signals |
| `tests/test_agent_tasks_cove.py` | F | verification questions + contradiction handling |
| `tests/fixtures/runs/2026-05-28-fast-trivial.jsonl` | C | new golden trace |
| `tests/fixtures/runs/2026-05-28-deep-causal.jsonl` | E | new golden trace |
| `tests/fixtures/runs/2026-05-28-standard-redecomp.jsonl` | B | new golden trace |

Coverage gate ≥ 80 % on every new file.

---

## 9. Out of Scope

| Item | Reason |
|---|---|
| Distributed orchestration / multi-worker | RF-05 (single-server) is a V1 invariant; the ReAct loop is in-process. |
| New plugin seam for the ReAct executor | The loop sits on top of the existing `Source` seam; promoting it to a seam would be premature. |
| New `LLMRole` for the ReAct Thought | The planner role suits Thought generation; introducing a new role would proliferate model assignments without benefit. |
| Tree-of-Thoughts / Multi-agent debate | Cost grows ≥ N×; ReAct + abductive hypotheses cover the multi-path case at a fraction of the cost. |
| Live web fetch beyond the existing `Source.fetch_full` | Out of scope — the DEEP `deep_fetch` action reuses the BRD-23 escalation; introducing a third channel is unjustified. |
| Adaptive `max_react_steps` per question | Adds tuning surface area; the fixed cap of 8 is the V1 invariant. |

---

## 10. Success Metrics (binding, measured 2 weeks post-rollout)

| Metric | Baseline (pre BRD-25) | Target |
|---|---|---|
| STANDARD p50 wall-clock | 100–220 s | **≤ 48 s** (Phase 0 alone) |
| STANDARD p95 wall-clock | 350–450 s | **≤ 120 s** |
| FAST p50 wall-clock on trivial questions | n/a (today routed via STANDARD ≈ 60 s) | **≤ 15 s** |
| DEEP p95 wall-clock | n/a (today routed via STANDARD ≈ 350 s) | **≤ 300 s** |
| `judge_confirmed` rate on CAUSAL queries | ~45 % | **≥ 70 %** (+25 pp) |
| `stopped_by_budget` with `final_confidence ∈ [0.5, 0.7]` | baseline | **−30 %** |
| Echo-chamber detections per 100 runs | 0 (no signal) | **detected when present, measured** |
| Query reformulations per 100 search rounds | 0 | **5–15** (signal of low-relevance recovery) |
| LLM call count per FAST happy path | n/a | **2** |
| LLM call count per DEEP run (median) | n/a | **≤ 20** |
| Replay determinism | 100 % | **100 %** |

---

## 11. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Parallel search exhausts Tavily rate limits | Medium | High | Existing rate-limit retry layer (BRD-06) absorbs; if quota breaches, fall back to serial via env flag `SEARCH_PARALLELISM=1`. |
| Phase 0 parallel order subtly drifts replay | Low | High | Apply events post-`gather` in deterministic claim order; golden-trace replay test (AC-18). |
| FAST mini-judge over-confirms low-quality answers | Medium | Medium | Threshold `S_effective >= 0.85` is high; mini-judge is structured (`MiniJudgeVerdict`); escalation is cheap. |
| DEEP ReAct loop never converges and always hits the cap | Medium | Medium | Hard cap of 8 + `AllHypothesesRefutedSignal` + best-effort fallback; observability via `meta_judge_calls_per_run` (BRD-26 when shipped). |
| Re-decomposition loops despite the cap | Low | High | `max_redecomposition=1` is a hard invariant; unit test on `redecomposition_count` post-trigger. |
| `NoProgressSignal` fires too eagerly on slow but real progress | Medium | Medium | Threshold (0.05 over 3 rounds) is conservative; signal routes to SYNTHESIZE, not terminate — judge still has the final say. |
| CoVe re-draft introduces new contradictions | Medium | Low | `max_cove_rounds=1` caps the loop; the final judge has authority over the second draft. |
| ReAct history summarization loses critical detail | Medium | Medium | Last 4 steps always kept verbatim; summary is descriptive, never authoritative for the judge. |
| `RunState` growth (hypotheses + react_history + confidence_history) bloats event payload | Low | Low | Each field bounded (≤ 4 hypotheses, ≤ 8 steps, ≤ ~10 history entries). |
| Phase E ships without Phase A telemetry confirming demand | Medium | Medium | Gating rule in IP-25 §7: Phase E requires 1 week of `lane=DEEP` traffic ≥ 10 % before activation. |

---

## 12. References

- IP-25 implementation plan: [IP-25](../implementation-plans/IP-25-three-lane-research-flow.md)
- Strategy doc: [building-the-plan.md](../../understanding-phase/building-the-plan.md)
- Architecture (3-lane): [advanced-ai-research.md](../../understanding-phase/advanced-ai-research.md)
- Stopping policy: [stopping-signal-analysis.md](../../understanding-phase/stopping-signal-analysis.md)
- Confidence: [confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- AI services: [ai-services.md](../../technical-phase/ai-services.md)
- Dependencies: BRD-05 (LLM client), BRD-06 (Source), BRD-07 (FSM), BRD-08 (confidence), BRD-09 (StoppingSignals), BRD-22 (complexity-aware planning), BRD-23 (research quality).
- Builds toward: BRD-26 (agentic stopping — replaces hard caps as the decision criterion).
- Requirements catalogue: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
