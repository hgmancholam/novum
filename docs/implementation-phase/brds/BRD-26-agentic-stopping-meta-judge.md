# BRD-26: Agentic Stopping — Reflective Meta-Judge + Adversarial Completeness

**Document ID:** BRD-26
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-28
**Implementation Order:** 26 of N
**Assumes shipped:** BRD-22, BRD-23, IP-25 (three-lane research flow, parallel search, route telemetry, dynamic re-decomposition, FAST mini-judge, abductive hypotheses, DEEP ReAct loop, explicit CoVe in DEEP).

---

## 1. Executive Summary

IP-25 introduced three lanes, dynamic re-decomposition (STANDARD), abductive hypotheses (DEEP), an explicit CoVe pass (DEEP), and a `NoProgressSignal` based on a sliding-window delta on `S_effective`. **Termination, however, still relies on hard numeric caps** — `max_judge_attempts`, `max_redecomposition`, `max_react_steps`, `max_cove_rounds`, the 3-round Δ-confidence window. These caps are honest *floors* (the run cannot diverge), but they are not honest *decision criteria*: a run that has structurally converged at S=0.72 keeps spending a full budget before the floor fires, and a run that is genuinely close to a breakthrough gets cut at exactly attempt N.

BRD-26 replaces the numeric cap as the **decision** mechanism with an **agentic stopping decision** — a small LLM-driven reasoning step that asks, after every standard candidate-stop point, **two epistemic questions**:

1. **Value-of-Continuation (VoC).** *"If we ran one more round, what concrete search would we issue, and what is the expected gain on `S_effective`?"* If the model cannot name a concrete next action, or estimates ΔS < ε, stop.
2. **Adversarial Completeness (AC).** *"What are the three strongest objections a skeptical reviewer could raise against the current draft? Which of them are already answered by cited evidence, and which would require a new directed search?"* If all objections are answered, stop with `judge_confirmed`. If unanswered objections exist AND budget allows AND VoC says "worth it", convert each unanswered objection into a **directed sub-claim** and re-enter `SEARCHING` with a *target*, not exploration.

The hard caps (`max_judge_attempts`, `max_react_steps`, etc.) **do not disappear** — they are demoted from *decision criterion* to *safety floor*. They guarantee termination; the new reasoning step decides termination.

The result is twofold:

- **Earlier honest stops** — saturated runs (volatile topic with no new sources to find) exit at the first VoC verdict instead of burning the full budget.
- **More productive continuations** — when the agent keeps going, it goes toward a named gap (an unanswered objection), not toward another generic search round.

This BRD is **additive only**: new optional events, new prompts, two new orchestrator hooks, zero changes to the `StopReason` enum, zero changes to `final_confidence = min(S_effective, J)` (RF-12), zero changes to the three seams (`Source`, `StoppingSignal`, `OutputRenderer`).

Binding success metrics in §10. Expected outcomes: −25 % p50 latency on saturated STANDARD runs (early VoC stop), +15 % `judge_confirmed` rate on borderline runs (objection-driven continuation), no regression on FAST.

---

## 2. RF Traceability

All RFs interpreted under the **Amendment 2026-05-27** (`stop_reason ∈ {judge_confirmed, stopped_by_budget, user_cancelled, errored}`; honest finals via `AnswerKind.BEST_EFFORT` + `stop_rationale`).

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-02 (stopping is success) | Honest stops are first-class outcomes | **Extends** — adds an *epistemic* reason ("saturated, no concrete next action") on top of the budgetary reason. Maps to the same enum values; the *reason* lives in `stop_rationale` + a new `MetaStopVerdict` event. |
| RF-01·A / RF-01·D (layered stopping) | Coverage + agreement + judge gates | **Extends** — VoC + AC are evaluated **after** the judge fires, **before** the hard cap. The judge LLM still owns approve/reject (§7 of advanced-ai-research.md); the meta-judge owns "is another round worth it?". Two distinct LLM responsibilities. |
| RF-12 (`final_confidence = min(S_effective, J)`) | Confidence formula invariant | **Preserved unchanged.** The meta-judge produces an *expected* ΔS estimate used to decide continuation; it never enters the persisted `final_confidence`. |
| RF-13 (UI as trust surface) | Surface every signal | **Extends** — the trace panel renders the meta-judge verdict (VoC, AC), the unanswered objections, and (when applicable) the directed sub-claims generated from them. |
| RF-08 (read determinism) | No live LLM regeneration on read | **Preserved** — every meta-judge output is persisted as an event; replays consume the persisted text, no re-inference. |
| RF-03 (append-only event log) | Additive schema | **Preserved** — 3 new event types, all `extra="allow"`. No existing event mutated. |
| RF-05 (single-server) | `uvicorn --workers 1` | **Preserved** — meta-judge is just one more `llm.call` per checkpoint; no new infra. |

**No RF amendments are required for this BRD.** All RFs are extended within their existing wording.

> **Doc updates (separate PR, not part of this BRD's implementation):**
> - `advanced-ai-research.md` §7 — add §7.6 *"Agentic stopping decision (VoC + AC)"* between §7.4 (hard caps) and §7.5 (the four enum values), describing the two reasoning hooks.
> - `stopping-signal-analysis.md` — add the meta-judge to the priority table.

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-05 (LLM client) | `llm.call(LLMRole.META_JUDGE, …)` — new role added to the existing enum (§4.3). |
| BRD-07 (Agent FSM) | Two new hook points in the orchestrator (`_after_judge`, `_after_react_observation`). No new FSM state. |
| BRD-09 (Stopping signals) | The new logic lives in `app/stopping/meta_judge.py` as **two `StoppingSignal` plugins** (`ValueOfContinuationSignal`, `AdversarialCompletenessSignal`). Existing signals untouched. |
| IP-25 (3-lane flow) | Hooks per lane (FAST: skip; STANDARD: after judge; DEEP: after each `AgentObservation` AND after CoVe). |
| BRD-23 WP-2 (deep-fetch) | Objections that point to a known URL with shallow snippet trigger `deep_fetch` instead of a new search round. |

No new env vars. No Alembic migration. No new external service. No new plugin seam — the two new evaluators are plain `StoppingSignal` implementations of the existing seam (RF-01).

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    domain/
      enums.py                          # MODIFY: +EventType.META_STOP_VERDICT,
                                        #          +EventType.ADVERSARIAL_OBJECTIONS_GENERATED,
                                        #          +EventType.DIRECTED_SUBCLAIMS_FROM_OBJECTIONS
      events.py                         # MODIFY: +MetaStopVerdictEvent,
                                        #          +AdversarialObjectionsGeneratedEvent,
                                        #          +DirectedSubclaimsFromObjectionsEvent
      meta_stop.py                      # NEW: Pydantic models MetaStopVerdict, Objection
    llm/
      roles.py                          # MODIFY: +LLMRole.META_JUDGE (uses judge model family
                                        #          by default; configurable per env)
      prompts/
        meta_judge_voc.py               # NEW: Value-of-Continuation prompt
        meta_judge_adversarial.py       # NEW: Adversarial Completeness prompt
    stopping/
      meta_judge.py                     # NEW: ValueOfContinuationSignal,
                                        #       AdversarialCompletenessSignal
      __init__.py                       # MODIFY: register both new signals
    agent/
      orchestrator.py                   # MODIFY: invoke meta-judge at three hook points,
                                        #          handle "directed re-search" outcome
      tasks/
        objections_to_subclaims.py      # NEW: convert unanswered objections to SubClaim list
  tests/
    test_meta_judge_voc.py              # NEW
    test_meta_judge_adversarial.py      # NEW
    test_stopping_meta_judge_priority.py # NEW
    test_orchestrator_meta_stop_flow.py # NEW
    test_objections_to_subclaims.py     # NEW
    test_meta_judge_replay_determinism.py # NEW
```

### 4.2 New domain types

```python
# app/domain/meta_stop.py
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class ValueOfContinuationVerdict(BaseModel):
    """LLM-produced answer to: 'Is another round worth it?'"""
    model_config = ConfigDict(extra="allow")
    decision: Literal["stop", "continue", "stop_best_effort"]
    expected_delta_s: float = Field(ge=0.0, le=1.0)
    next_action_hypothesis: str | None  # what we would search; None => nothing concrete
    reason: str  # short English rationale, persisted verbatim

class Objection(BaseModel):
    model_config = ConfigDict(extra="allow")
    text: str  # the skeptical objection itself
    status: Literal["answered_by_evidence", "unanswered_needs_search", "unanswered_no_search_possible"]
    evidence_ids_answering: list[UUID] = []  # populated when status=answered_by_evidence
    suggested_query: str | None = None        # only when status=unanswered_needs_search

class AdversarialCompletenessVerdict(BaseModel):
    model_config = ConfigDict(extra="allow")
    objections: list[Objection]  # exactly 3 — validated
    all_answered: bool            # derived; persisted for trace UX
```

### 4.3 New LLM role

```python
# app/llm/roles.py
class LLMRole(StrEnum):
    # ... existing ...
    META_JUDGE = "meta_judge"   # NEW

# Default model: same family as the JUDGE role (DeepSeek-V3 in prod).
# Env override: META_JUDGE_PROVIDER, META_JUDGE_MODEL_<provider> (mirrors §5 of ai-services.md).
```

Rationale for sharing the judge family by default: the meta-judge reasons about evidence sufficiency, which is the judge's competence. The orchestrator pays the cost of independence-from-synthesizer once at the judge step; the meta-judge can stay in the same family without re-introducing bias because it reasons about a different question (worth-continuing) than the judge (is-the-draft-supported).

### 4.4 New events (all additive)

```python
# app/domain/events.py

class MetaStopVerdictEvent(BaseEvent):
    """Persisted output of the Value-of-Continuation evaluator."""
    model_config = ConfigDict(extra="allow")
    type: Literal[EventType.META_STOP_VERDICT] = EventType.META_STOP_VERDICT
    lane: Lane
    hook: Literal["after_judge", "after_react_observation", "after_cove"]
    verdict: ValueOfContinuationVerdict
    confidence_at_check: float  # final_confidence at the moment of evaluation

class AdversarialObjectionsGeneratedEvent(BaseEvent):
    """The three skeptic objections + their answered/unanswered status."""
    model_config = ConfigDict(extra="allow")
    type: Literal[EventType.ADVERSARIAL_OBJECTIONS_GENERATED] = EventType.ADVERSARIAL_OBJECTIONS_GENERATED
    lane: Lane
    verdict: AdversarialCompletenessVerdict

class DirectedSubclaimsFromObjectionsEvent(BaseEvent):
    """Conversion of unanswered objections to new SubClaim entries."""
    model_config = ConfigDict(extra="allow")
    type: Literal[EventType.DIRECTED_SUBCLAIMS_FROM_OBJECTIONS] = EventType.DIRECTED_SUBCLAIMS_FROM_OBJECTIONS
    source_objection_count: int
    created_subclaim_ids: list[UUID]
```

### 4.5 Reasoning hooks per lane

| Lane | Hook point | When |
|---|---|---|
| FAST  | none | FAST already has its mini-judge with a binary decision; meta-judge would be over-engineering at this cost level. |
| STANDARD | `after_judge` | Right after `JudgeRuled`, **before** evaluating `max_judge_attempts`. |
| DEEP  | `after_react_observation` | Inside the ReAct loop, after each `AgentObservation`, instead of evaluating `max_react_steps` directly. |
| DEEP  | `after_cove` | After the explicit CoVe pass, **before** evaluating `max_cove_rounds`. |

### 4.6 Decision algorithm (STANDARD `after_judge`)

```text
1. If judge.verdict == approve AND final_confidence ≥ threshold:
       → judge_confirmed (no meta-judge invoked; happy path is cheap).

2. Else, invoke ValueOfContinuationSignal:
       voc = await llm.call(META_JUDGE, prompt=VOC_PROMPT, ...)
       emit MetaStopVerdictEvent(hook="after_judge", verdict=voc, ...)

   If voc.decision == "stop":
       → judge_confirmed if final_confidence ≥ threshold
       → stopped_by_budget + AnswerKind.BEST_EFFORT otherwise
       → fallback synthesizer prompt cited in §4.8

   If voc.decision == "stop_best_effort":
       → stopped_by_budget + AnswerKind.BEST_EFFORT (skip the threshold check;
         the meta-judge has just declared the question saturated).

   If voc.decision == "continue" AND voc.expected_delta_s ≥ 0.03:
       → invoke AdversarialCompletenessSignal:
             ac = await llm.call(META_JUDGE, prompt=AC_PROMPT, ...)
             emit AdversarialObjectionsGeneratedEvent(verdict=ac, ...)

         If ac.all_answered == True:
             → judge_confirmed
               (the meta-judge says "no concrete next action, no unanswered objections"
                — this is the strongest possible "we are done" signal)

         Else (unanswered objections exist):
             → objections_to_subclaims(ac.objections) appends new SubClaims
             → emit DirectedSubclaimsFromObjectionsEvent
             → state.judge_attempt_count += 1
             → if judge_attempt_count >= max_judge_attempts (HARD CAP):
                    → best_effort_fallback
               else:
                    → transition ANALYZING → SEARCHING (directed)

3. If voc.expected_delta_s < 0.03 even when decision == "continue":
       → treat as voc.decision == "stop_best_effort" (epistemic floor).
```

**Hard caps remain.** `max_judge_attempts` (default 5, raised from IP-25's 2 because the agentic decision usually stops earlier) is the absolute safety floor. The cap **never** decides termination on its own when the meta-judge says `continue`; it only ends the loop when the meta-judge has already said `continue` `max_judge_attempts` times in a row.

### 4.7 Decision algorithm (DEEP)

Two hook points: `after_react_observation` and `after_cove`. Logic mirrors §4.6 with one specialization:

- In DEEP, "objections" map naturally onto **hypotheses**. If `ac.unanswered_objections` overlaps semantically with `state.hypotheses` whose `verdict == "pending"`, the new directed sub-claims are routed to the ReAct loop as `evaluate_hypothesis(hypothesis_id, target=objection.text)` actions rather than as new `SubClaim` entries. (Implementation: §4.10.)

The ReAct `max_react_steps = 8` hard cap stays as the absolute floor. When the meta-judge says `stop` mid-loop, `react_step_count` is **not** advanced — the loop terminates cleanly, history is summarized once, and we transition to `SYNTHESIZING`.

### 4.8 Best-effort fallback wording (additive prompt clause)

When termination is `stopped_by_budget` via the meta-judge (not via cap), the synthesizer is invoked with an extra clause:

> *"FALLBACK MODE: The meta-judge has determined that further research would not meaningfully improve the answer (saturation). Structure your reply in four parts: (1) what evidence we have, (2) what we could not confirm and why we could not confirm it, (3) our best current take given the evidence, (4) what specific new evidence (concrete source, paper, dataset, or person) would close the remaining gap. Reply in the user's language."*

This is the same template as the existing best-effort fallback from BRD-23 §9.2; the only addition is *"and why we could not confirm it"* in part (2), populated from the meta-judge's `reason` field.

### 4.9 Prompts (English, code-level)

**`meta_judge_voc.py`** (system + user template):

```
SYSTEM (meta-judge, role=META_JUDGE):
You decide whether one more research round is worth running.
You do NOT decide if the draft is correct — that is the judge's job, already done.

Your input:
- Original question, AnswerKind, lane
- Sub-claims and their current evidence count + tier mix
- Current S_effective and J_score
- Number of rounds already executed; rounds remaining in the budget
- Last judge verdict (approve/reject + reason)

Output a structured ValueOfContinuationVerdict:
  - decision: stop | continue | stop_best_effort
  - expected_delta_s: realistic estimate of how much S_effective would move
    if one more round ran; must be in [0, 1]
  - next_action_hypothesis: a CONCRETE query you would search next, or null
    if you cannot name one
  - reason: one short English sentence

Decision rules (apply in order):
1. If you cannot name a concrete next_action_hypothesis -> decision=stop_best_effort.
2. If expected_delta_s < 0.03 -> decision=stop_best_effort.
3. If S_effective >= threshold AND judge approved -> decision=stop.
4. Otherwise -> decision=continue.
```

**`meta_judge_adversarial.py`** (system + user template):

```
SYSTEM (meta-judge, role=META_JUDGE):
You are a skeptical reviewer of a research draft. Generate EXACTLY 3 objections
that a serious, fair-minded skeptic could raise against the draft.

For each objection, classify status as one of:
- answered_by_evidence: the existing cited evidence already addresses the objection
  (provide the evidence_ids that answer it)
- unanswered_needs_search: a new search COULD answer the objection; provide a
  suggested_query (<= 6 tokens)
- unanswered_no_search_possible: the objection is real but no available source
  can decide it (e.g. requires non-public data)

The 3 objections must be DIFFERENT in nature (do not generate variations of the same
concern). Prefer objections about: (a) missing entity/perspective, (b) staleness or
temporal scope, (c) source independence / echo chamber, (d) ambiguity of the claim
itself.

Output AdversarialCompletenessVerdict.
```

### 4.10 `objections_to_subclaims` (STANDARD) and hypothesis routing (DEEP)

```python
# app/agent/tasks/objections_to_subclaims.py
def convert(objections: list[Objection], state: RunState) -> list[SubClaim]:
    return [
        SubClaim(
            id=uuid4(),
            text=obj.text,
            search_queries=[obj.suggested_query] if obj.suggested_query else [],
            origin="adversarial_objection",  # NEW SubClaim.origin enum value
        )
        for obj in objections
        if obj.status == "unanswered_needs_search"
    ]
```

In DEEP, before calling `convert`, the orchestrator runs a similarity check
(`state.hypotheses[].text` vs `objection.text`, simple embedding-free heuristic
using token overlap ≥ 0.5). If a hypothesis is matched, the objection is
**routed to that hypothesis** as the next `evaluate_hypothesis` target instead
of creating a new sub-claim. This keeps the DEEP loop hypothesis-centric.

### 4.11 Replay determinism (RF-08)

Every meta-judge output is persisted in the event log. On read, the FE renders
from events; no LLM is invoked. The orchestrator's `_fold_events` consumes
`MetaStopVerdictEvent` and `AdversarialObjectionsGeneratedEvent` to reconstruct
the decision branch on resume. A run that was forked **before** a
`MetaStopVerdictEvent` re-invokes the meta-judge from scratch on the fork — and
that is the intended fork semantics (replay = read, fork = re-run).

### 4.12 Cost accounting

Per round where the meta-judge fires (= every non-happy-path round in STANDARD,
every ReAct step in DEEP), the additional cost is:

- **STANDARD**: +1 VoC call. AC fires only if VoC says continue with positive
  ΔS — so at most +2 LLM calls per non-happy-path round, typically +1.
- **DEEP after_react_observation**: +1 VoC call per step. AC fires only at
  the decision boundary; budget overall ≈ +max_react_steps calls.
- **DEEP after_cove**: +1 VoC call.

The 4 PAT pool absorbs this in V1. Telemetry tracks `meta_judge_calls_per_run`
to detect regressions.

### 4.13 Cost gate for `after_react_observation` (slice 3b' — DESIGN, deferred)

The DEEP `after_react_observation` hook is wired in the type (`MetaJudgeHook`
literal) but **not** called from `run_react_loop`. Naively enabling it would
issue one extra `META_JUDGE` LLM call per ReAct step (worst case
`max_react_steps` ≈ 8 calls/run, on top of the existing `after_cove` call).
This subsection specifies the cost gate that must be satisfied before the
hook is wired in `app/agent/react/loop.py`.

**Activation predicate** — the hook runs at the end of a ReAct step iff **all**
conditions hold:

1. `settings.meta_judge_enabled` is `true` (existing global kill-switch).
2. `settings.meta_judge_after_react_enabled` is `true` (new, default `false`
   — independent slice flip).
3. `state.react_step_count >= settings.meta_judge_react_warmup_steps`
   (default `2`) — skip the first 2 steps so the agent has at least one
   non-trivial observation to weigh against.
4. `state.meta_judge_calls < settings.max_meta_judge_calls_per_run` (new,
   default `4`) — hard cap shared across **all** hooks (STANDARD `after_judge`
   + DEEP `after_cove` + DEEP `after_react_observation`).
5. `(now - state.last_meta_judge_at) >= 0` (no time gate in V1; placeholder
   for future rate-limit).

When the predicate is false, the loop continues exactly as today (no event
emitted, no LLM call).

**Per-call gate (already in `meta_judge_hook.py`)** — once invoked, the
existing VoC sanitization keeps cost down:

- `voc.decision == "stop"` or `"stop_best_effort"` → no AC call.
- `voc.expected_delta_s < settings.meta_judge_min_delta_s` (default `0.03`)
  → no AC call.
- AC only fires when VoC says `continue` with ΔS ≥ threshold.

**New state field** (additive — fits the `extra="allow"` schema rule):

```python
class RunState(BaseModel):
    meta_judge_calls: int = 0          # incremented in meta_judge_hook.maybe_run_meta_judge
    last_meta_judge_at: datetime | None = None
```

`meta_judge_calls` is already incremented implicitly via `MetaStopVerdictEvent`
emission; promote it to an explicit counter so the predicate is O(1).

**New settings** (in `app/config.py`):

| Key | Default | Purpose |
|---|---|---|
| `meta_judge_after_react_enabled` | `false` | Independent flip for slice 3b'. |
| `meta_judge_react_warmup_steps` | `2` | Skip the first N ReAct steps. |
| `max_meta_judge_calls_per_run` | `4` | Hard cap across all hooks. |

**Worst-case cost after gate** — with defaults and `max_react_steps=8`:

- Warmup skips steps 0–1 → up to 6 candidate calls.
- Hard cap clips at 4 (minus calls already spent in `after_judge` /
  `after_cove`).
- AC only on `continue` + ΔS ≥ 0.03 → typically 0–2 extra calls.

Net upper bound: **≤ 4 META_JUDGE invocations per DEEP run**, regardless of
ReAct length. Matches today's effective budget for `after_cove`-only runs.

**Wiring sketch** (no implementation — sequencing only):

In `run_react_loop`, right after `emit(AgentObservationEvent(...))` and
**before** the `evaluate_react_intra_loop` call:

```text
if _cost_gate_ok(state, settings):
    outcome = await maybe_run_meta_judge(
        state, emit, judge_signal=_synthetic_signal_from_react(state),
        hook="after_react_observation",
    )
    match outcome:
        "stop_best_effort" → break, propagate StopReason.STOPPED_BY_BUDGET
        "confirm"          → break, propagate StopReason.JUDGE_CONFIRMED
        "continue"/"skipped" → fall through to intra-loop signals
```

The `_synthetic_signal_from_react` helper builds a duck-typed object exposing
the five attributes `maybe_run_meta_judge` needs (`passed=False`,
`structural_confidence`/`judge_confidence` from the latest evidence-derived
proxy, `final_confidence=min(S,J)`, `rationale=last_observation_summary`).

**Telemetry** — extend the existing `meta_judge_calls_per_run` gauge with a
breakdown label `hook ∈ {after_judge, after_cove, after_react_observation}`
so regressions in slice 3b' are isolable.

**Acceptance for un-deferring** — the slice ships when:

- The gate is implemented and a unit test asserts ≤ `max_meta_judge_calls_per_run`
  calls across a synthetic 8-step DEEP run.
- A regression test asserts the `meta_judge_after_react_enabled=false` path
  emits **zero** `MetaStopVerdictEvent`s with `hook="after_react_observation"`.
- Telemetry baseline shows mean `meta_judge_calls_per_run` ≤ 3 over a 20-run
  shadow window before the flag flips to `true` in prod.

---

## 5. Functional Requirements

| FR | Description | Verification |
|---|---|---|
| FR-26-01 | The meta-judge runs **after** the regular judge in STANDARD, after each `AgentObservation` and the CoVe pass in DEEP, and **never** in FAST. | AC-01 |
| FR-26-02 | Every meta-judge invocation persists exactly one `MetaStopVerdictEvent` with the lane, the hook name, and the full `ValueOfContinuationVerdict` payload. | AC-02 |
| FR-26-03 | When VoC returns `decision == "continue"` AND `expected_delta_s ≥ 0.03`, the orchestrator invokes the Adversarial Completeness pass; otherwise it does not. | AC-03 |
| FR-26-04 | Exactly 3 objections are produced per AC pass; objections are persisted in an `AdversarialObjectionsGeneratedEvent` with their classified status. | AC-04 |
| FR-26-05 | Unanswered objections with `status == "unanswered_needs_search"` become new `SubClaim` entries (STANDARD) or hypothesis targets (DEEP) before re-entering `SEARCHING`. | AC-05 |
| FR-26-06 | When all three objections are `answered_by_evidence`, the run terminates as `judge_confirmed` regardless of the hard-cap counter. | AC-06 |
| FR-26-07 | The hard caps (`max_judge_attempts`, `max_react_steps`, `max_cove_rounds`) remain enforced as **safety floors**: when reached, the run terminates via `draft_best_effort_fallback` even if the meta-judge would say `continue`. | AC-07 |
| FR-26-08 | The `final_confidence = min(S_effective, J)` formula is unchanged. The meta-judge's `expected_delta_s` is **not** persisted as part of `final_confidence`. | AC-08 |
| FR-26-09 | Resuming a stopped run never re-invokes the meta-judge. All meta-judge text is rendered from `MetaStopVerdictEvent.verdict.reason` and the persisted `Objection` list. | AC-09 |
| FR-26-10 | A run terminated by VoC `stop_best_effort` reaches the synthesizer in FALLBACK MODE and the resulting `Stopped` event has `stop_reason == "stopped_by_budget"` AND `answer_kind == "best_effort"` AND a `stop_rationale` that quotes the meta-judge's `reason`. | AC-10 |
| FR-26-11 | The `LLMRole.META_JUDGE` defaults to the same model family as `JUDGE` (DeepSeek-V3 in prod) and is overridable per provider via env (`META_JUDGE_PROVIDER`, `META_JUDGE_MODEL_<provider>`). | AC-11 |
| FR-26-12 | FAST runs do not emit any of the three new events under any circumstance. | AC-12 |

---

## 6. Non-Functional Requirements

| NFR | Requirement | Verification |
|---|---|---|
| NFR-26-01 | The meta-judge adds at most **+2 LLM calls** per non-happy-path round in STANDARD and **+1 call** per ReAct step in DEEP. | Telemetry `meta_judge_calls_per_run`, P95 panel. |
| NFR-26-02 | The meta-judge prompts return structured Pydantic output via `instructor`; malformed outputs trigger one retry, then fall through to `decision="stop_best_effort"`. | AC-13 |
| NFR-26-03 | All new prompts, identifiers, log messages and `Objection.text` are in English. The synthesizer fallback reply follows the user's language. | Manual + grep checks. |
| NFR-26-04 | The meta-judge runs **single-server, single-worker** (RF-05). No new infra. | Architecture review. |
| NFR-26-05 | Each `llm.call(META_JUDGE, …)` is retried via tenacity with the existing backoff config; permanent provider quota errors fail fast (`LLMProviderQuotaExhausted`). | AC-14 |
| NFR-26-06 | The three new event types must be exported to `frontend/src/types/events.ts` via `scripts/export_types.py` in the same PR. | AC-15 |

---

## 7. Acceptance Criteria

| AC | Statement |
|---|---|
| AC-01 | Synthetic STANDARD run with rejected judge → `MetaStopVerdictEvent(hook="after_judge")` emitted exactly once per round; FAST happy-path run → 0 emissions. |
| AC-02 | All `MetaStopVerdictEvent` rows carry a valid `ValueOfContinuationVerdict` (Pydantic-validated on load). |
| AC-03 | Unit test: VoC returning `continue` + `expected_delta_s=0.10` triggers an AC call; VoC returning `continue` + `expected_delta_s=0.01` does **not** trigger AC and instead terminates as `stop_best_effort`. |
| AC-04 | AC events always contain `len(objections) == 3`; Pydantic validator enforces this. |
| AC-05 | Integration test: AC with one `unanswered_needs_search` objection → one new `SubClaim` appears in `state.sub_claims` with `origin == "adversarial_objection"` and is searched in the next round. |
| AC-06 | Integration test: AC where all 3 objections are `answered_by_evidence` → run terminates `judge_confirmed` on the same round, regardless of `judge_attempt_count`. |
| AC-07 | Integration test: `judge_attempt_count == max_judge_attempts` AND VoC says `continue` → run terminates via `draft_best_effort_fallback` (hard cap wins). |
| AC-08 | Unit test on `_fold_events`: `final_confidence` after replay equals `min(S_effective, J)`; `expected_delta_s` does **not** appear in the formula. |
| AC-09 | Integration test: resume a stopped run with meta-judge events present → 0 `llm.call` invocations on the read path. |
| AC-10 | Integration test: VoC `stop_best_effort` → `Stopped.stop_reason == "stopped_by_budget"`, `Stopped.answer_kind == "best_effort"`, `Stopped.stop_rationale` contains `verdict.reason`. |
| AC-11 | Config test: `META_JUDGE_PROVIDER=anthropic`, `META_JUDGE_MODEL_anthropic="claude-sonnet-4-6"` → next meta-judge call routes through the Anthropic client. |
| AC-12 | Unit test: FAST happy-path and FAST escalated-to-STANDARD runs → 0 `MetaStopVerdictEvent` rows from the FAST portion; STANDARD portion emits normally. |
| AC-13 | Unit test: `instructor` returns malformed output → one retry; second malformed output → `decision="stop_best_effort"` synthesized in code with `reason="meta_judge_unparseable"`. |
| AC-14 | Unit test: simulated `LLMProviderQuotaExhausted` on META_JUDGE → no retry burned, fallback to `stop_best_effort` with `reason="meta_judge_quota_exhausted"`. |
| AC-15 | CI check: `python scripts/export_types.py` produces empty diff. |
| AC-16 | Pre-BRD-26 golden traces in `tests/fixtures/runs/` replay byte-identically. The new code paths are inactive when `MetaStopVerdictEvent` is absent from the trace. |

---

## 8. Test Plan (binding)

| Test file | Scope |
|---|---|
| `tests/test_meta_judge_voc.py` | Pure unit on prompt structure, Pydantic validation, decision rules. |
| `tests/test_meta_judge_adversarial.py` | Pure unit on AC: cardinality (3), status enum, suggested_query length cap. |
| `tests/test_stopping_meta_judge_priority.py` | Confirm the two new `StoppingSignal` plugins fire at the correct priority relative to `BudgetExhaustedSignal`, `JudgeSignal`, `NoProgressSignal`. |
| `tests/test_orchestrator_meta_stop_flow.py` | End-to-end orchestrator paths: stop, continue+AC-answered, continue+AC-search, hard-cap-wins. |
| `tests/test_objections_to_subclaims.py` | Conversion logic, origin enum, hypothesis-routing in DEEP. |
| `tests/test_meta_judge_replay_determinism.py` | `_fold_events` consumes the new events without re-invoking the LLM; golden traces unchanged. |
| `tests/test_agent_lanes_fast_no_meta_judge.py` | FAST lane never emits the new events. |
| `tests/fixtures/runs/2026-05-28-meta-judge-saturation.jsonl` | New golden trace: a saturated `volatile` topic that stops early via VoC. |
| `tests/fixtures/runs/2026-05-28-meta-judge-objection-driven.jsonl` | New golden trace: an AC pass that creates a directed sub-claim, finds the missing evidence, and approves. |

Coverage gate ≥ 80 % for `app/stopping/meta_judge.py`, `app/agent/tasks/objections_to_subclaims.py`, `app/llm/prompts/meta_judge_*.py`.

---

## 9. Out of Scope

| Item | Reason |
|---|---|
| Meta-judge over FAST | FAST has 2 LLM calls total; a meta-judge would be a ~50 % overhead. The mini-judge already plays that role at the right cost level. |
| Bayesian belief tracking (`Beta(α, β)` posterior over correctness) | Decision-theoretically clean but requires likelihood estimation infrastructure outside V1 scope. Reconsider in V2 if the meta-judge proves insufficient. |
| Self-consistency (N parallel synth drafts) | Cost grows linearly with N; not justified until we measure that the agentic stop is *still* leaving uncertainty on the table. |
| Tree-of-Thoughts | Quadratic cost; ReAct + abductive hypotheses (IP-25) already covers the multi-path exploration case. |
| Replacing the regular judge with the meta-judge | The judge owns *is-the-draft-supported*; the meta-judge owns *is-another-round-worth-it*. Conflating them re-introduces the bias the BRD is solving. |
| Changing `StopReason` enum | The 4-value enum is the correct contract. Honest stops via meta-judge map to `stopped_by_budget` + `BEST_EFFORT` (RF-02). |

---

## 10. Success Metrics (binding, measured 2 weeks post-rollout)

| Metric | Baseline (post IP-25) | Target |
|---|---|---|
| STANDARD p50 wall-clock on saturated runs (`S_effective` plateau detected) | ~120 s | **≤ 90 s** (−25 %) |
| `judge_confirmed` rate on borderline STANDARD runs (`S_effective ∈ [threshold-0.05, threshold+0.05]` at first judge) | ~55 % | **≥ 70 %** (+15 pp) |
| `stopped_by_budget` runs whose `stop_rationale` cites "no concrete next action" instead of "max_judge_attempts" | 0 % | **≥ 60 %** |
| FAST happy-path latency | ~15 s | unchanged (no regression) |
| DEEP p50 wall-clock | ~200 s | **≤ 200 s** (no regression; quality up via early-stop on confirmed hypotheses) |
| Mean `meta_judge_calls_per_run` (STANDARD) | n/a | **≤ 3** |
| Replay determinism | 100 % | **100 %** (golden traces) |

If the saturated-run latency target is not met after 2 weeks, lower the VoC continuation threshold from `expected_delta_s ≥ 0.03` to `≥ 0.05` (config change, no code).

---

## 11. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Meta-judge over-confidence ("just one more round will fix it") leads to runaway continuation | Medium | Medium | Hard caps remain the absolute floor; telemetry alerts when `meta_judge_calls_per_run > max_judge_attempts × 1.5`. |
| Meta-judge under-confidence stops good runs early | Medium | Medium | The `expected_delta_s ≥ 0.03` threshold is configurable; AC pass is a second chance — if AC finds no unanswered objections the stop is well-founded. |
| AC objections degenerate to variations of the same concern | Medium | Low | Prompt explicitly forbids variations; unit test on a known degenerate fixture ensures the LLM does not regress. |
| Meta-judge cost regresses LLM quota | Low | Medium | Anthropic tier-1 rate limits absorb easily; if not, lower default to 1 meta-judge call per round (skip AC unless VoC `expected_delta_s ≥ 0.10`). |
| Determinism breaks if meta-judge returns slightly different text on replay | High if mishandled | High | All meta-judge outputs persisted verbatim; replay never re-invokes (AC-09). This is the same pattern used for judge and synthesizer outputs. |
| Meta-judge and judge disagree pathologically (judge approves, VoC says `continue`) | Low | Low | When `judge.verdict == approve` AND `final_confidence ≥ threshold`, the meta-judge is **not invoked** (§4.6 step 1). Disagreement is impossible on the happy path. |

---

## 12. References

- IP-25 implementation plan: [IP-25](../implementation-plans/IP-25-three-lane-research-flow.md)
- Research flow narrative: [advanced-ai-research.md](../../understanding-phase/advanced-ai-research.md)
- Strategy rationale: [building-the-plan.md](../../understanding-phase/building-the-plan.md)
- Confidence formula (unchanged by this BRD): [confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- Stopping policy (extended by this BRD): [stopping-signal-analysis.md](../../understanding-phase/stopping-signal-analysis.md)
- LLM client + roles: BRD-05
- Stopping signals seam: BRD-09
- Requirements catalogue: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
