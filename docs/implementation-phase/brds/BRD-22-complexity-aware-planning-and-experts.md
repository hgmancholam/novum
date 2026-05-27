# BRD-22: Complexity-Aware Planning + Expected Experts

**Document ID:** BRD-22
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-27
**Implementation Order:** 22 of N

---

## 1. Executive Summary

Q1 of the IP-21 §0.8 smoke matrix — *"What is the capital of Japan?"* — completed end-to-end against `novum-prod.duckdns.org` in **606 seconds** (~10 min), produced the correct `judge_confirmed` + `answer_kind=direct` outcome, and stayed inside a **single round**. The IP-21 WP-3 G8 early-stop fired, but only **after** that round's full classify → plan → critique → Tavily → Wikipedia → analyze → draft → judge sequence had already burned.

BRD-22 adds four additive capabilities so that **trivial-fact questions skip work they cannot benefit from**, and so that **non-trivial questions weight evidence by source expertise** instead of treating every domain as equal:

- **Capability A — Complexity hint at classification time.** A new optional field `complexity_hint ∈ {trivial, standard, deep}` on `QuestionClassifiedEvent` derived from a deterministic heuristic over question length, `QuestionType`, classifier confidence, and single-named-entity presence.
- **Capability B — Per-complexity planner budgets.** `create_plan` scales claim count, source count, and critique passes by `complexity_hint`. `trivial` → 1 claim, 1 source (Wikipedia preferred), **skip the critique pass**. `standard` → unchanged. `deep` → current behaviour **+ one extra critique pass**.
- **Capability C — Expected expert profiles.** `create_plan` emits `expected_experts: list[str]` on `PlanCreatedEvent`. `analyze_evidence` applies a **1.1× credibility multiplier** to evidence whose source domain matches a static `expert_taxonomy` lookup. The multiplier raises **agreement** signal — never `S_raw`, never `kind_ceiling`. The `final_confidence = min(S_effective, J)` invariant is preserved.
- **Capability D — Same-question instant-answer cache.** When `QuestionIndex` (IP-21 WP-6) finds a prior run with normalised-equal question AND `final_confidence ≥ 0.85`, the orchestrator replays the prior `Stopped` payload as a new run within ~1 s and emits a new `PriorRunHintReplayed` event for trust surfacing.

The binding metric is Q1 end-to-end latency: **606 s → ≤ 90 s** on prod, with `complexity_hint=trivial` AND `expected_experts` present in the event stream.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-01 (A — claim coverage / planner budget) | Autonomous stopping policy + planner shape | **Extends** — planner budget now also keyed on `complexity_hint`. No change to A/D/B/E/F gate definitions. |
| RF-04 (source agreement) | Agreement multiplier for expert-matched sources | **Extends** — adds the 1.1× multiplier inside `calculate_agreement`; D-gate definition unchanged. |
| RF-06-quater (trust contract / UI as trust surface) | Surface `complexity_hint`, `expected_experts`, `PriorRunHintReplayed` to the user | **Extends** — three new visible trust elements. |
| RF-12 (`final_confidence = min(S_effective, J)`) | Confidence formula | **Preserved unchanged.** The 1.1× multiplier lives in agreement (an input to `S_raw` via the existing structural calculator), bounded by clamping; it does NOT modify `S_effective` or `kind_ceiling` directly. |
| RF-17 (always answer / AnswerKind) | Six-template synthesis | **Preserved** — capabilities A/B/C/D do not change any AnswerKind or template. |
| RF-18 (saturation) | Embedding novelty signal | **Untouched.** |
| RF-19 (judge on different provider) | Anthropic Haiku judge path | **Untouched.** |

RFs flagged for **text amendment** in `requirement-understanding.md` (BSA flags, does NOT amend):

1. **RF-01·A** — add `complexity_hint` as a sanctioned input to the planner budget heuristic.
2. **RF-04 / RF-12** — explicitly state that agreement may be weighted by an `expected_experts` × source-domain match, with a fixed 1.1× ceiling and **no compounding** across multiple expert matches per evidence row.
3. **RF-06-quater** — add `complexity_hint`, `expected_experts`, and `PriorRunHintReplayed` to the enumerated trust-surface elements.

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| IP-21 WP-3 (G8 early-stop, kind-aware structural confidence) | Capability B short-circuit composes with G8 |
| IP-21 WP-6 (`QuestionIndex` in-memory) | Capability D cache lookup |
| BRD-05 (LLM client) | Capability A still routes via `app/llm/client.py::call` |
| BRD-07 (Agent FSM) | Capabilities A/B/C/D add NO new FSM states |
| BRD-08 (Confidence calculation) | Capability C multiplier wires through `calculate_agreement` |

No new env vars. No new Alembic migration. No new external service. No new plugin seam.

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    domain/
      events.py                   # MODIFY: +complexity_hint on QuestionClassifiedEvent,
                                  #          +expected_experts on PlanCreatedEvent,
                                  #          +new event PriorRunHintReplayedEvent
      enums.py                    # MODIFY: +ComplexityHint enum
    agent/
      tasks/
        classify.py               # MODIFY: derive complexity_hint heuristic
        plan.py                   # MODIFY: budget table keyed on (QuestionType, ComplexityHint),
                                  #         emit expected_experts, conditional critique pass
        analyze.py                # MODIFY: pass expected_experts to agreement calc
      experts/
        __init__.py               # NEW
        taxonomy.py               # NEW: expert_taxonomy: dict[str, list[str]] + match() helper
      instant_cache.py            # NEW: thin wrapper over QuestionIndex for D
      orchestrator.py             # MODIFY: pre-classify cache lookup → emit PriorRunHintReplayed
    confidence/
      agreement.py                # MODIFY: optional expert_match_multiplier param
  tests/
    test_classify_complexity.py   # NEW (US-22-1)
    test_plan_complexity_budget.py # NEW (US-22-2)
    test_experts_taxonomy.py      # NEW (US-22-3)
    test_agreement_expert_boost.py # NEW (US-22-3 integration)
    test_instant_answer_cache.py  # NEW (US-22-4)

frontend/
  src/
    types/
      events.ts                   # REGENERATED via scripts/export_types.py (do not hand-edit)
    components/
      molecules/
        ComplexityBadge.tsx       # NEW (RF-06-quater surface)
        ExpectedExpertsList.tsx   # NEW
      organisms/
        TracePanel.tsx            # MODIFY: render PriorRunHintReplayed entry
```

### 4.2 Database Schema

**No migration required.** All state lives in the event log (RF-03 invariant). Capability D uses the in-memory `QuestionIndex` from IP-21 WP-6; no persistence (RF-05).

### 4.3 Alembic Migration

None.

### 4.4 Pydantic Models (additive only)

```python
# app/domain/enums.py (additive)
from enum import Enum

class ComplexityHint(str, Enum):
    TRIVIAL = "trivial"
    STANDARD = "standard"
    DEEP = "deep"

# app/domain/events.py (additive fields, extra="allow" preserved)
class QuestionClassifiedEvent(BaseEvent):
    # ... existing fields ...
    complexity_hint: ComplexityHint | None = None        # NEW (BRD-22 A)

class PlanCreatedEvent(BaseEvent):
    # ... existing fields ...
    expected_experts: list[str] | None = None            # NEW (BRD-22 C)
    complexity_hint: ComplexityHint | None = None        # NEW (mirrored for trace UX)

class PriorRunHintReplayedEvent(BaseEvent):              # NEW (BRD-22 D)
    """Emitted when the instant-answer cache short-circuits a new run."""
    model_config = ConfigDict(extra="allow")
    source_run_id: UUID
    source_final_confidence: float
    normalised_question: str
    replayed_answer_kind: AnswerKind
```

All new fields are `X | None = None`. No existing event is mutated destructively. Historical replay continues to work.

### 4.5 Heuristic — Capability A (`complexity_hint`)

Deterministic, no LLM call. Computed inside `classify_question` after the LLM verdict returns.

```text
trivial  ⟺  (len(question.words) ≤ 8)
            AND question_type ∈ {FACTUAL, DEFINITIONAL}
            AND classifier_confidence ≥ 0.80
            AND single_named_entity_detected(question)

deep     ⟺  question_type ∈ {STATE_OF_ART, CAUSAL, COMPARATIVE}
            AND (len(question.words) ≥ 16 OR classifier_confidence < 0.55)

standard ⟺  otherwise
```

Entity detection: simple capitalised-token heuristic (no spaCy dependency). One contiguous capitalised span = single entity. Multi-entity (two unrelated capitalised spans) bumps to `standard`.

### 4.6 Budget Table — Capability B

Augments `CLAIM_BUDGETS` in `plan.py`. Tuple = `(claims_min, claims_max, sources_per_claim, critique_passes)`.

| `QuestionType` × `ComplexityHint` | trivial | standard | deep |
|---|---|---|---|
| FACTUAL | (1, 1, 1, 0) | (1, 2, 2, 1) | (2, 3, 3, 2) |
| DEFINITIONAL | (1, 1, 1, 0) | (1, 2, 2, 1) | (2, 3, 3, 2) |
| COMPARATIVE | n/a — coerced to `standard` | (2, 4, 2, 1) | (3, 5, 3, 2) |
| CAUSAL | n/a — coerced to `standard` | (2, 4, 2, 1) | (3, 5, 3, 2) |
| STATE_OF_ART | n/a — coerced to `standard` | (3, 6, 3, 1) | (4, 8, 3, 2) |
| others (5 new IP-21 types) | inherits per type-family default | inherits | inherits |

`trivial` for COMPARATIVE/CAUSAL/STATE_OF_ART is **invalid** — the planner coerces to `standard` and emits a debug log. This is intentional to prevent the classifier from gaming the budget.

`critique_passes = 0` ⇒ the planner skips the critique step entirely (no `PlanCritiquedEvent` emitted), going from `Planning → Searching` directly.

### 4.7 Expert Taxonomy — Capability C

A static module-level dictionary in `app/agent/experts/taxonomy.py`. Domain patterns match by **exact suffix** (e.g. `"mayoclinic.org"`) and a fixed allowlist of TLD-family rules (e.g. `"*.gov"`, `"*.edu"`). The full initial taxonomy lives in **US-22-3 Appendix A**.

`match(source_domain, expected_experts) → multiplier`:
- Returns `1.1` if **any** expert in `expected_experts` claims `source_domain`.
- Returns `1.0` otherwise.
- **Never compounds.** Two matches → still `1.1`.
- Multiplier applied inside `calculate_agreement` only, clamped to `[0.0, 1.0]` after multiplication.

### 4.8 Instant-Answer Cache — Capability D

Pre-classify step inside `orchestrator.start_run`:

1. Normalise question: lowercase, strip punctuation, collapse whitespace.
2. Lookup in `QuestionIndex` (IP-21 WP-6) by exact normalised match (NOT cosine similarity — exact only).
3. If hit AND `prior_run.final_confidence ≥ 0.85` AND `prior_run.stop_reason == JUDGE_CONFIRMED`:
   - Emit `RunCreated` (so history still records the new run).
   - Emit `PriorRunHintReplayedEvent` with `source_run_id`.
   - Re-emit the prior run's `JudgeRuledEvent` + `StoppedEvent` payloads (new UUIDs, new timestamps).
   - Transition to `STOPPED` without ever entering `CLASSIFYING`.
   - Target wall-clock: **≤ 1 s**.
4. Else: normal pipeline.

**No persistence.** Cache lives entirely in the existing `QuestionIndex`; restart clears it (RF-05).

### 4.9 API Endpoints

No new endpoints. All changes flow through the existing `POST /api/runs` and the SSE stream.

### 4.10 React Components

| Component | Path | Props | State |
|---|---|---|---|
| `ComplexityBadge` | `components/molecules/ComplexityBadge.tsx` | `hint: ComplexityHint` | none |
| `ExpectedExpertsList` | `components/molecules/ExpectedExpertsList.tsx` | `experts: string[]` | none |
| `TracePanel` | `components/organisms/TracePanel.tsx` | (existing) | (existing) — adds a new row type for `PriorRunHintReplayed` |

UI strings (RF-13 trust surface; English source, localised at render):

- ComplexityBadge:
  - trivial → `"Quick lookup"`
  - standard → `"Standard research"`
  - deep → `"Deep investigation"`
- ExpectedExpertsList header: `"Looking for sources from:"`
- PriorRunHintReplayed entry: `"Same question answered ≤ {Δt} ago (confidence {x.xx}). Reused that result."`

### 4.11 UI Layout

No layout changes. The two new molecules render inside the existing **Center Panel** state `C5 (planning)` and `C13 (terminal)` regions defined in `ui-prototype.md §3`.

---

## 5. Acceptance Criteria

### AC-01 — Trivial fact short-circuits the round (Capability A + B)
```gherkin
Given question "What is the capital of Japan?" with no prior cached run
When a new run is started
Then QuestionClassifiedEvent.complexity_hint == "trivial"
And  PlanCreatedEvent.sub_claims has length 1
And  PlanCreatedEvent.expected_experts contains "encyclopedia"
And  No PlanCritiquedEvent is emitted in round 1
And  end-to-end wall-clock from RunCreated to Stopped is ≤ 90 s on prod
And  StoppedEvent.stop_reason == "judge_confirmed"
And  StoppedEvent.answer_kind == "direct"
```

### AC-02 — Standard question unchanged (regression guard)
```gherkin
Given question "PostgreSQL vs MongoDB for a small SaaS team"
When a new run is started
Then QuestionClassifiedEvent.complexity_hint == "standard"
And  PlanCreatedEvent.sub_claims length is in [2, 4]
And  Exactly one PlanCritiquedEvent is emitted in round 1
And  PlanCreatedEvent.expected_experts contains "database_engineer"
```

### AC-03 — Deep question adds critique pass (Capability B)
```gherkin
Given question "What are the long-term societal risks of AI-generated code reaching production?"
When a new run is started
Then QuestionClassifiedEvent.complexity_hint == "deep"
And  PlanCreatedEvent.sub_claims length is in [4, 8]
And  Exactly two PlanCritiquedEvent events are emitted in round 1
```

### AC-04 — Expert multiplier raises agreement (Capability C)
```gherkin
Given a plan with expected_experts == ["nutritionist", "medical_researcher"]
And  evidence row E with source_domain == "mayoclinic.org" and base agreement contribution 0.50
When calculate_agreement is invoked
Then E's weighted contribution is 0.55  (0.50 × 1.1, clamped)
And  final_confidence still satisfies min(S_effective, J), with S unchanged in formula shape
```

### AC-05 — Expert multiplier does NOT compound
```gherkin
Given expected_experts == ["nutritionist", "medical_researcher"]
And  source_domain "mayoclinic.org" matches BOTH experts
When agreement is computed
Then the multiplier applied is exactly 1.1 (NOT 1.21)
```

### AC-06 — Instant-answer cache replays a high-confidence prior run (Capability D)
```gherkin
Given a prior run P exists with normalised_question == "what is the capital of japan"
And  P.final_confidence == 0.92
And  P.stop_reason == "judge_confirmed"
When a new run for the same question is started
Then RunCreatedEvent is emitted
And  PriorRunHintReplayedEvent is emitted with source_run_id == P.id
And  StoppedEvent is emitted within 1 s wall-clock of RunCreated
And  No QuestionClassifiedEvent, PlanCreatedEvent, or SearchStartedEvent is emitted
```

### AC-07 — Cache miss falls through cleanly
```gherkin
Given no prior run matches the normalised question
When a new run is started
Then NO PriorRunHintReplayedEvent is emitted
And  The full pipeline runs (classify → plan → search → analyze → draft → judge)
```

### AC-08 — Cache ignores low-confidence priors
```gherkin
Given a prior run P with final_confidence == 0.70 for the same normalised question
When a new run is started
Then NO PriorRunHintReplayedEvent is emitted
And  The full pipeline runs
```

### AC-09 — Event replay forward-compatibility
```gherkin
Given a historical events.jsonl trace recorded before BRD-22
When the orchestrator replays it
Then no error is raised
And  missing complexity_hint, expected_experts, PriorRunHintReplayedEvent are tolerated as None / absent
```

---

## 6. Implementation Checklist

- [ ] Enum + event model additions — `backend/app/domain/enums.py`, `backend/app/domain/events.py`
- [ ] Classifier heuristic — `backend/app/agent/tasks/classify.py`
- [ ] Planner budget table + critique skip + experts emission — `backend/app/agent/tasks/plan.py`
- [ ] Expert taxonomy module — `backend/app/agent/experts/taxonomy.py`
- [ ] Agreement multiplier hook — `backend/app/confidence/agreement.py` + `backend/app/agent/tasks/analyze.py`
- [ ] Instant-answer cache pre-classify step — `backend/app/agent/orchestrator.py`, `backend/app/agent/instant_cache.py`
- [ ] FE generated types — `scripts/export_types.py` then verify `frontend/src/types/events.ts`
- [ ] FE molecules — `ComplexityBadge.tsx`, `ExpectedExpertsList.tsx`
- [ ] FE trace row — `TracePanel.tsx` extension
- [ ] Unit tests — `test_classify_complexity.py`, `test_plan_complexity_budget.py`, `test_experts_taxonomy.py`, `test_agreement_expert_boost.py`, `test_instant_answer_cache.py`
- [ ] FE tests — `ComplexityBadge.test.tsx`, `ExpectedExpertsList.test.tsx`
- [ ] Smoke matrix re-run for Q1 on prod, asserting ≤ 90 s

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (BE) | pytest | `app/agent/tasks/classify.py`, `app/agent/tasks/plan.py`, `app/agent/experts/`, `app/confidence/agreement.py` | ≥ 80% |
| Integration (BE) | pytest + mocked LLM | classify → plan flow per complexity; agreement boost end-to-end; cache hit/miss | Critical paths |
| Unit (FE) | Vitest + RTL + jest-axe | `ComplexityBadge`, `ExpectedExpertsList` | ≥ 80% |
| Smoke (prod) | `scripts/smoke_ip21.py` (extended) | Q1 latency assertion ≤ 90 s | Q1 row only |

## 8. Environment Variables

No new env vars.

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Classifier confidence under-reports for legitimate trivial-fact questions → `standard` budget → no latency gain | Medium | Medium | Two-prong heuristic: confidence ≥ 0.80 **OR** length ≤ 6 words + single entity. Tunable thresholds in `app/config.py`. |
| Expert taxonomy biases toward English-language sources (e.g. `mayoclinic.org` over `who.int` translated) | Medium | Medium | Include international authorities (`who.int`, `nih.gov`, `ec.europa.eu`); seed taxonomy from IP-21 smoke matrix coverage. Out of scope to auto-learn. |
| Instant-cache replay fools the user into thinking a fresh run happened | High | Low | **MANDATORY** `PriorRunHintReplayed` event + visible trace badge "Reused prior result"; never silent. RF-06-quater. |
| Cache hit on stale data after model upgrade | Low | Medium | RF-05 already restarts the in-memory cache on every deploy. Documented; no extra mechanism. |
| `1.1×` multiplier accidentally compounds via two expert matches → confidence inflation | High | Low | Test AC-05 enforces non-compounding. Multiplier is computed once per (evidence_row, plan), not summed. |
| Trivial coercion skips critique on edge cases that need it (e.g. ambiguous one-word entity "Paris" — city vs. person) | Medium | Low | Empty-comparative detector (IP-21 G9) still runs; ambiguity events still emit and bump effective complexity. |
| Frontend type drift if `scripts/export_types.py` not re-run | Medium | Medium | Pre-commit hook (existing) regenerates; CI compares generated vs. committed. |

## 10. Out of Scope

- Dynamic / learned expert taxonomy. The taxonomy is **static** in V1 — taxonomy edits = code change.
- Cross-tenant cache sharing. Cache is process-local (RF-05).
- Cosine-similarity match for cache. **Exact normalised match only** in V1.
- Persisting the cache across restarts (would require DB; deferred V2).
- New plugin seam ("ExpertProfile"). Static module is sufficient.
- Modifying `S_raw` formula or `kind_ceiling`. Capability C touches **agreement only**.
- Changing the FSM. No new states; no new transitions.

---

## 11. Metrics

### 11.1 Binding success metric

| Metric | Baseline (prod 2026-05-27) | Target | Verification |
|---|---|---|---|
| Q1 end-to-end wall-clock | 606 s | ≤ 90 s | `smoke_ip21.py` Q1 row, both `complexity_hint=trivial` AND `expected_experts != []` present in the event stream |
| `judge_confirmed` outcome preserved on Q1 | yes | yes | Same script |
| Cache-hit latency (warm) | n/a | ≤ 1 s | `test_instant_answer_cache.py` integration test |

### 11.2 Secondary metrics

| Metric | Target |
|---|---|
| % of FACTUAL/DEFINITIONAL classified as `trivial` on a 50-question dev set | ≥ 60 % |
| % of STATE_OF_ART classified as `deep` on dev set | ≥ 70 % |
| Median agreement uplift on rows with expert match | +5 % to +10 % |

---

## 12. User Stories Summary

| Story ID | Title | Priority | Estimated Effort |
|---|---|---|---|
| US-22-1 | Complexity hint at classification time | High | S |
| US-22-2 | Per-complexity planner budget + conditional critique | High | M |
| US-22-3 | Expected expert profiles + agreement multiplier | Medium | M |
| US-22-4 | Same-question instant-answer cache | High | S |

---

## 13. Stakeholders

| Name | Role | Interest | Involvement |
|---|---|---|---|
| Giovanny (PO) | Product owner | Demo latency, trust surface | Approver |
| BSA Agent | Requirements | This BRD + US-22-x | Author |
| Auditor Agent | F1/F2 gate | Validates BRD + US | Approver (F1 sub-loop) |
| Orchestrator Agent | Planner | Drafts IP-22 from this BRD | Consumer |

---

## 14. Appendix

### 14.1 Glossary

| Term | Definition |
|---|---|
| **Complexity hint** | Deterministic 3-valued classification (`trivial`/`standard`/`deep`) of a question's research depth, emitted by the classifier. |
| **Expected expert** | A symbolic role label (e.g. `"nutritionist"`) used to look up authoritative domain patterns. |
| **Expert taxonomy** | Static `dict[str, list[str]]` mapping expert label → domain patterns. |
| **Instant-answer cache** | In-memory replay of a prior high-confidence `Stopped` payload when the normalised question matches exactly. |

### 14.2 References

- `docs/implementation-phase/implementation-plans/IP-21-always-answer-refactor.md` — WP-3 (G8), WP-6 (QuestionIndex)
- `docs/implementation-phase/audits/IP-21-status-audit.md` — current state
- `docs/understanding-phase/requirement-understanding.md` — RF-01·A, RF-04, RF-06-quater, RF-12, RF-17/18/19
- `docs/understanding-phase/confidence-calculation.md` — `min(S_effective, J)` formula
- Smoke run logs: `smoke_ip21_run6.txt` (Q1 = 606 s)

### 14.3 Open questions (to be resolved by Auditor F1 sub-loop)

See section returned to Orchestrator in the BSA reply.

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | BSA Agent | Initial draft (F1) — capabilities A/B/C/D, AC-01..09, risk register, metrics |
