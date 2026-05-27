# Implementation Plan — IP-22: Complexity-Aware Planning + Expected Experts

**Plan ID:** IP-22
**Parent BRD:** [BRD-22 v1.0](../brds/BRD-22-complexity-aware-planning-and-experts.md)
**Parent User Stories:** [US-22-1](../user-stories/US-22-1-complexity-hint-classifier.md), [US-22-2](../user-stories/US-22-2-planner-complexity-budget.md), [US-22-3](../user-stories/US-22-3-expected-experts.md), [US-22-4](../user-stories/US-22-4-instant-answer-cache.md)
**Date:** 2026-05-27
**Author:** Orchestrator Agent
**Estimated Effort:** L (≈5–6 h pair-session)
**Iteration:** 2

---

## 1. Summary

Add four additive capabilities to the agent so that trivial-fact questions skip work and non-trivial questions weight evidence by source expertise:

- **A — Complexity hint.** Deterministic 3-valued classification (`trivial` | `standard` | `deep`) emitted alongside `QuestionType` from the classifier step.
- **B — Per-complexity planner budget.** Claim count, sources-per-claim, and critique-pass count scale with `complexity_hint`. Trivial skips `CRITIQUING` entirely; deep adds a forced second critique cycle.
- **C — Expected expert profiles.** Planner emits `expected_experts: list[str]`. `calculate_agreement` applies a non-compounding `1.1×` per-row multiplier when source domain matches the static `expert_taxonomy`, clamped to `[0, 1]`. `min(S_effective, J)` invariant preserved (multiplier feeds `S_raw` via agreement only).
- **D — Same-question instant-answer cache.** Pre-classify lookup against an in-memory dict keyed by `(username, normalised_question)`. On hit (prior run `JUDGE_CONFIRMED` AND `final_confidence ≥ 0.85`), emit `RunCreated → PriorRunHintReplayed → JudgeRuled → Stopped` within ≤ 1 s, never entering `CLASSIFYING`.

No new env vars, no new Alembic migration, no new plugin seam, no new FSM state.

RF traceability:
- **RF-01·A** — planner budget extended with `ComplexityHint` axis.
- **RF-04** — agreement weighted by expert match (additive, non-compounding).
- **RF-06-quater / RF-13** — three new visible trust elements (`ComplexityBadge`, `ExpectedExpertsList`, `PriorRunHintReplayed` trace row).
- **RF-12** — `final_confidence = min(S_effective, J)` unchanged; multiplier lives strictly inside `calculate_agreement`.
- **RF-03 / RF-05** — events stay append-only; replay tolerates missing optional fields; cache is in-memory only (cleared on restart).
- **RF-17/18/19** — untouched.

---

## 2. Prerequisites

- [x] IP-21 WP-3 (G8 early-stop, kind-aware structural confidence) — verified in [orchestrator.py](../../../backend/app/agent/orchestrator.py#L233-L246).
- [x] IP-21 WP-6 (`QuestionEmbeddingIndex`) — verified in [question_index.py](../../../backend/app/agent/question_index.py#L41-L107).
- [x] BRD-05 LLM client — `app/llm/client.py::call` (all LLM access routes through here).
- [x] BRD-07 Agent FSM — `AgentOrchestrator` + `RunState` available.
- [x] BRD-08 Confidence — `calculate_agreement(state.evidence)` exists in [structural.py](../../../backend/app/confidence/structural.py#L26-L51).
- [x] BRD-04 user identity — `username` available on `Run`, plumbed through `RunService.create_run` → `runner.start_run`.

---

## 3. Autonomous Decisions (resolves BRD ambiguities)

The following autonomous decisions are recorded here per the Orchestrator runbook (rule §6 of the request) and will be appended to `decisions-history.md` as D-IP22-*.

| ID | Decision | Rationale |
|----|----------|-----------|
| **D-IP22-01** | Introduce a NEW event type `QuestionClassifiedEvent` (not present in current `events.py`). BRD-22 §4.4 says "MODIFY" but the type doesn't exist — today the classifier result is folded into `state.question_type` without a dedicated event. | Required by US-22-1 AC + by RF-02 inspectability. The only honest carrier for `complexity_hint`. |
| **D-IP22-02** | `instant_cache.py` uses a **separate** in-memory dict keyed by `(username, normalised_question)`, NOT a wrapper over `QuestionEmbeddingIndex`. | `QuestionEmbeddingIndex.PriorRunHint` is `extra="forbid"` and deliberately redacts `answer_kind`/`prose`/`confidence` (G6 contract). Storing replay payload there would break that contract. Two parallel caches keep each contract clean. |
| **D-IP22-03** | "Extra critique pass" for `deep` is implemented as a target counter `critique_passes_target ∈ {0,1,2}` on `RunState`. The orchestrator overrides the first critique's `acceptable` verdict when the target is 2 to force one mandatory revise + re-critique cycle. | Reuses existing `CRITIQUING ↔ REVISING` loop. No new FSM state required. Emits exactly two `PlanCritiquedEvent`s as US-22-2 AC-3 requires. |
| **D-IP22-04** | FE binding: BRD says "TracePanel.tsx" but actual surfaces are `organisms/TraceTimeline.tsx` + `molecules/EventNode.tsx` + `organisms/PlanPreview` / `CenterPanelView`. We extend those instead. | Matches the real codebase. No regression in layering. |
| **D-IP22-05** | `expected_experts` extraction: the planner LLM prompt is extended to request the field, AND a deterministic fallback map is consulted when the LLM returns an empty list (trivial-factual ⇒ `["encyclopedia"]`; medical/health markers ⇒ `["medical_researcher"]`; DB markers ⇒ `["database_engineer"]`). The fallback guarantees AC-1/AC-2 of US-22-3. | Pure-LLM emission is fragile under mocked tests and trivial path; a small keyword fallback ensures determinism for the canonical Q1 ("capital of Japan") and the AC scenarios. |
| **D-IP22-06** | Trivial-factual budget is `(1, 1, 1, 0)` exactly. Wikipedia is preferred via `PlanCreatedEvent.preferred_sources = ["wikipedia"]`; the search task already calls Wikipedia first in its registry order, so no search-task code change is required — only the event field is populated. | Avoids touching `search.py` and the search cascade. Honors US-22-2 AC-5 strictly. |
| **D-IP22-07** | Cross-user cache scoping enforced at lookup, NOT storage. Key in the dict is `(username, normalised_question)`. Mistyped or missing `username` ⇒ no replay. | AC-08 of US-22-4 with the smallest surface area. |
| **D-IP22-08** | TLD-family expert matching (`*.gov`, `*.edu`) matches when the registered host has the bare TLD as suffix OR a `.<sub>.<tld>` chain ending in it (e.g. `cia.gov`, `nih.gov`, `pubmed.ncbi.nlm.nih.gov`). Single literal patterns (e.g. `mayoclinic.org`) match by exact suffix on the host minus `www.`. | Matches the BRD wording and US-22-3 TC-04. |
| **D-IP22-09** | Replay path emits **synthetic** `JudgeRuledEvent` + `StoppedEvent` carrying the prior run's numerical values (`structural_confidence`, `judge_confidence`, `final_confidence`, `answer_kind`, `answer_prose`, `answer_structured`, `citations`). New `id`, new `created_at`, new `run_id`. `StopRationale.triggering_signal = "instant_cache"`. | US-22-4 calls these "faithful echoes". Adds a distinct `triggering_signal` value so trust surface can label them. |
| **D-IP22-10** | `normalise_question` strips Unicode punctuation via `unicodedata.category().startswith("P")` (no regex), lowercases via `str.lower()`, collapses whitespace via `" ".join(s.split())`. | Deterministic, no third-party deps, matches AC-5 of US-22-4. |

---

## 4. Task Breakdown

### Phase 1 — Backend domain layer (enums + events)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 1.1 | Add `ComplexityHint(str, Enum)` with values `TRIVIAL`, `STANDARD`, `DEEP` (lowercase string values). Export from `app/domain/enums`. | `backend/app/domain/enums.py` | XS | — | US-22-1 DoD |
| 1.2 | Add new `EventType.QUESTION_CLASSIFIED = "QuestionClassified"` and `EventType.PRIOR_RUN_HINT_REPLAYED = "PriorRunHintReplayed"`. | `backend/app/domain/enums.py` | XS | — | US-22-1, US-22-4 |
| 1.3 | Add `QuestionClassifiedEvent(BaseEvent)` Pydantic model with `type: Literal[EventType.QUESTION_CLASSIFIED]`, `question_type: QuestionType`, `classifier_confidence: float`, `complexity_hint: ComplexityHint \| None = None`, `heuristic_signals: dict[str, Any] \| None = None` (records `word_count`, `single_entity`, `entity_count`). `extra="allow"`. | `backend/app/domain/events.py` | S | 1.1, 1.2 | US-22-1 AC-1..AC-6 |
| 1.4 | Extend `PlanCreatedEvent` with three optional fields: `complexity_hint: ComplexityHint \| None = None`, `expected_experts: list[str] \| None = None`, `preferred_sources: list[str] \| None = None`. Order: after existing fields. `extra="allow"` already set. | `backend/app/domain/events.py` | XS | 1.1 | US-22-2 AC-1..AC-7; US-22-3 AC-1, AC-2 |
| 1.5 | Add `PriorRunHintReplayedEvent(BaseEvent)` with `type: Literal[EventType.PRIOR_RUN_HINT_REPLAYED]`, `source_run_id: UUID`, `source_final_confidence: float`, `source_stop_reason: StopReason`, `source_answer_kind: AnswerKind \| None = None`, `normalised_question: str`, `prior_completed_at: datetime`. `extra="allow"`. | `backend/app/domain/events.py` | S | 1.1, 1.2 | US-22-4 AC-1, AC-7 |
| 1.6 | Update `Event = Annotated[Union[…], Field(discriminator="type")]` discriminated union (and any `EVENT_TYPE_MAP` / `FORKABLE_EVENTS` lists in `events.py`) to include the two new event classes. Neither new event is forkable. | `backend/app/domain/events.py` | S | 1.3, 1.5 | RF-03 |
| 1.7 | Add config knobs to `Settings` in `app/config.py`: `complexity_max_trivial_words: int = 8`, `complexity_min_trivial_confidence: float = 0.80`, `complexity_min_deep_words: int = 16`, `complexity_max_deep_confidence: float = 0.55`, `instant_cache_min_confidence: float = 0.85`, `instant_cache_max_size: int = 256`. | `backend/app/config.py` | XS | — | US-22-1 §Technical; US-22-4 DoD |

### Phase 2 — Backend domain layer (LLM models + helpers)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 2.1 | Extend `QuestionClassification` (`app/llm/models.py`) with optional `confidence: float \| None = Field(default=None, ge=0.0, le=1.0)`. The classifier prompt already returns rationale; we add a numeric `confidence` so the heuristic in Phase 3 has the input it needs. Update the system prompt in `app/llm/prompts.py` (or wherever the classifier system prompt lives — grep first) to request `"confidence": <float 0..1>`. **System prompt extensions: all text in English (per `/memories/language-policy.md`).** | `backend/app/llm/models.py`, `backend/app/llm/prompts.py` (or `app/llm/roles.py`) | S | — | US-22-1 heuristic |
| 2.2 | Extend `PlanOutput` (`app/llm/models.py`) with optional `expected_experts: list[str] \| None = Field(default=None, max_length=6)`. Update planner system prompt to request `"expected_experts": [list of expert labels from a fixed vocabulary]` and the vocabulary list. The vocabulary mirrors the taxonomy keys. **System prompt extensions: all text in English (per `/memories/language-policy.md`).** | `backend/app/llm/models.py`, planner prompt source | S | — | US-22-3 AC-1, AC-2 |

### Phase 3 — Classifier: complexity heuristic

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 3.1 | Add module `app/agent/complexity.py` exposing `derive_complexity_hint(question: str, question_type: QuestionType, classifier_confidence: float \| None) -> tuple[ComplexityHint, dict[str, Any]]`. Implements BRD-22 §4.5 deterministic heuristic. Returns hint + signals dict (`word_count`, `entity_count`, `single_entity`, `confidence_floor_met`). Pure, synchronous, no LLM call. | `backend/app/agent/complexity.py` (NEW) | M | 1.1, 1.7 | US-22-1 AC-1..AC-5 |
| 3.2 | Add private `_count_named_entities(question: str) -> int` inside `complexity.py`. Heuristic: split on whitespace, strip leading sentence interrogatives (`What`, `Why`, `Where`, `When`, `Who`, `How`, `Is`, `Are`, `Do`, `Does`, `Did`, `Can`, `Could`, `Would`, `Should` — case-insensitive at position 0 only). Count **contiguous runs** of title-case or ALL-CAPS tokens; a contiguous run = one or more adjacent tokens matching `tok[0].isupper() and (tok[1:].islower() or tok.isupper())`. Hyphenated entities are NOT split (no `.split('-')`) — `"Hewlett-Packard"` counts as 1 token. Strip trailing punctuation (`?!.,;:`) from each token before the case test. Each contiguous run = 1 entity; non-contiguous runs separated by lowercase tokens (e.g. `vs`, `and`) count separately. Over-counting (e.g. `"Event Sourcing"` → 1 run of 2 tokens) is acceptable — biases toward `standard`, the safe default. **Docstring MUST include these examples:** `"Tokyo"` → 1; `"Event Sourcing"` → 1 (contiguous); `"PostgreSQL vs MongoDB"` → 2 (non-contiguous, separated by `vs`); `"What is CQRS?"` → 1; `"Hewlett-Packard"` → 1; `"Event Sourcing and CQRS"` → 2. | `backend/app/agent/complexity.py` | S | 3.1 | US-22-1 Scenario 4 |
| 3.3 | Modify `classify_question` (`app/agent/tasks/classify.py`) to return `tuple[QuestionType, QuestionClassification, ComplexityHint, dict[str, Any]]` — call `derive_complexity_hint` after the LLM call. Use `verdict.confidence or 1.0` when the LLM omits it (back-compat). | `backend/app/agent/tasks/classify.py` | S | 2.1, 3.1 | US-22-1 |
| 3.4 | Modify `AgentOrchestrator._detect_question_type` (`app/agent/orchestrator.py`) to: (a) capture `complexity_hint` + signals; (b) write them to a new `state.complexity_hint: ComplexityHint \| None = None` field (add to `RunState`); (c) emit a new `QuestionClassifiedEvent` before any other downstream event. Order of events after the change: `QuestionAsked → QuestionNormalized → QuestionClassified → (AmbiguityDetected?)`. | `backend/app/agent/orchestrator.py`, `backend/app/agent/run_state.py` | M | 1.3, 3.3 | US-22-1 AC-1..AC-6 |

### Phase 4 — Planner: budget table + critique skip + experts emission

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 4.1 | Replace `CLAIM_BUDGETS: dict[QuestionType, tuple[int,int]]` in `app/agent/tasks/plan.py` with `CLAIM_BUDGETS: dict[tuple[QuestionType, ComplexityHint], tuple[int,int,int,int]]` per BRD-22 §4.6. Tuple shape `(claims_min, claims_max, sources_per_claim, critique_passes)`. Add fallback `_DEFAULT_BUDGET = (3, 5, 2, 1)`. Add `_coerce_complexity(question_type, hint)` that returns `STANDARD` when `hint == TRIVIAL` and `question_type` is in `{COMPARATIVE, CAUSAL, STATE_OF_ART, PREDICTIVE_FUTURE, SUBJECTIVE_OPINION, PERSONAL_PRIVATE}`. Log structured event `complexity_coerced reason=incompatible_type` when coercion happens. | `backend/app/agent/tasks/plan.py` | M | 1.1 | US-22-2 AC-1..AC-6 |
| 4.2 | Update `_claim_budget(question_type, hint)` signature to take both keys and return the full 4-tuple. | `backend/app/agent/tasks/plan.py` | S | 4.1 | — |
| 4.3 | Update `create_plan` signature: add `complexity_hint: ComplexityHint \| None = None`. Use coerced hint. Populate the new `PlanCreatedEvent` fields: `complexity_hint`, `expected_experts` (from `result.expected_experts` OR fallback map per D-IP22-05), `preferred_sources` (`["wikipedia"]` when `complexity == TRIVIAL` AND `question_type ∈ {FACTUAL, DEFINITIONAL}`, else `None`). Pass `sources_per_claim` into the LLM prompt as a hint. | `backend/app/agent/tasks/plan.py` | M | 4.1, 1.4, 2.2 | US-22-2, US-22-3 |
| 4.4 | Update `revise_plan` to accept `complexity_hint: ComplexityHint \| None`. **Fallback strategy when `None` (historical replay or pre-BRD-22 trace):** default to `ComplexityHint.STANDARD` at the top of the function and log `complexity_hint_defaulted_on_revise reason=missing` via `structlog.get_logger(__name__).info`. Emit the defaulted value in `PlanRevisedEvent.complexity_hint` so the trace stays consistent. This mirrors the fallback used in Task 4.1 / `_coerce_complexity` and satisfies US-22-2 AC-6. | `backend/app/agent/tasks/plan.py` | S | 4.1 | US-22-2 AC-3, AC-6 |
| 4.5 | Add helper `_fallback_experts(question: str, question_type: QuestionType) -> list[str]` in `app/agent/tasks/plan.py` using a small keyword map (medical: `["nutritionist", "medical_researcher"]`; database: `["database_engineer"]`; programming/SaaS: `["software_engineer", "saas_architect"]`; fact: `["encyclopedia"]`; geography: `["geographer", "encyclopedia"]`; default: `["encyclopedia"]`). Used when the LLM returns empty `expected_experts`. | `backend/app/agent/tasks/plan.py` | S | 2.2 | US-22-3 AC-1, AC-2; D-IP22-05 |
| 4.6 | Add `complexity_hint: ComplexityHint \| None`, `critique_passes_target: int = 1`, `critique_passes_completed: int = 0`, `expected_experts: list[str] = []`, `preferred_sources: list[str] = []` to `RunState`. Default `extra="allow"` already on the model. **Replay-determinism strategy (RF-03):** neither `critique_passes_target` nor `critique_passes_completed` is persisted in a dedicated event field. Instead, both are **recomputed during `_fold_events`** (see Task 4.9): target is recomputed deterministically from the budget table using `(state.question_type, state.complexity_hint)`; completed = `len([e for e in events if e.type == EventType.PLAN_CRITIQUED])`. This avoids a new event schema and keeps the event log canonical (RF-03). | `backend/app/agent/run_state.py` | S | 1.1 | US-22-2, US-22-3, RF-03 |
| 4.7 | Modify `AgentOrchestrator._handle_planning` to: (a) call `create_plan(..., complexity_hint=self.state.complexity_hint)`; (b) write `expected_experts` + `preferred_sources` to `RunState`; (c) compute and store `critique_passes_target` from the budget table (`0` for trivial, `1` for standard, `2` for deep); (d) if target == 0 → `transition_to(SEARCHING)`; else → `transition_to(CRITIQUING)`. | `backend/app/agent/orchestrator.py` | M | 4.1, 4.3, 4.6 | US-22-2 AC-1, AC-4 |
| 4.8 | Modify `_handle_critiquing`: increment `state.critique_passes_completed` at top. If `critique_passes_completed < critique_passes_target` → force the path: emit critique, transition to `REVISING` regardless of `critique.acceptable`. If `critique_passes_completed >= critique_passes_target` → use the existing acceptable/revise branching. This guarantees deep emits exactly 2 `PlanCritiquedEvent`s. | `backend/app/agent/orchestrator.py` | M | 4.7 | US-22-2 AC-3 |
| 4.9 | Update `runner.py::_fold_events` to fold the new optional fields on `PlanCreatedEvent` (`complexity_hint`, `expected_experts`, `preferred_sources`) into `RunState`. **Additionally:** (a) recompute `state.critique_passes_target` from the budget table after the `PlanCreatedEvent` fold using `_claim_budget(state.question_type, state.complexity_hint or ComplexityHint.STANDARD)[3]`; (b) recompute `state.critique_passes_completed` after each `PlanCritiquedEvent` fold by incrementing a local counter (or equivalently, recompute at end via `sum(1 for e in events if e.type == EventType.PLAN_CRITIQUED)`). Both counters MUST be derived purely from the event log — never persisted directly. Tolerate absence of optional fields (replay of pre-BRD-22 traces): if `complexity_hint` is missing on a folded `PlanCreatedEvent`, default to `STANDARD` and recompute target accordingly. | `backend/app/agent/runner.py` | S | 4.6 | RF-03; US-22-2 AC-6 |

### Phase 5 — Experts taxonomy + agreement multiplier

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 5.1 | Create package `app/agent/experts/` with `__init__.py` exporting `expert_taxonomy` and `match`. | `backend/app/agent/experts/__init__.py` (NEW) | XS | — | US-22-3 DoD |
| 5.2 | Create `app/agent/experts/taxonomy.py` shipping the static `expert_taxonomy: dict[str, list[str]]` per US-22-3 Appendix A verbatim (12 experts × 50 patterns). | `backend/app/agent/experts/taxonomy.py` (NEW) | S | 5.1 | US-22-3 DoD |
| 5.3 | Add `_normalize_host(url_or_host: str) -> str` to `taxonomy.py`: parse via `urllib.parse.urlparse`, take `netloc` (or `path` for bare hosts), lowercase, strip leading `www.`. Returns empty string on parse failure (no raise). | `backend/app/agent/experts/taxonomy.py` | S | 5.2 | US-22-3 TC-03 |
| 5.4 | Add `_pattern_matches(host: str, pattern: str) -> bool`: if pattern starts with `*.`, match when host suffix equals pattern[2:] OR host == pattern[2:]. Else, match when host == pattern OR host endswith `."{pattern}"` (literal). Case-insensitive on both sides. | `backend/app/agent/experts/taxonomy.py` | S | 5.3 | US-22-3 TC-04 |
| 5.5 | Add public `match(source_domain_or_url: str, expected_experts: list[str] \| None) -> float`. Returns `1.0` if `expected_experts` is `None`/empty. Iterates experts; for each, iterates patterns; returns `1.1` on first hit. Unknown expert label → log `expert_label_unknown label=<label>` via `structlog.get_logger(__name__).debug` and skip. Never raises. Never compounds. | `backend/app/agent/experts/taxonomy.py` | S | 5.2, 5.4 | US-22-3 AC-3..AC-9 |
| 5.6 | Modify `calculate_agreement` in `app/confidence/structural.py`: add optional kwarg `expected_experts: list[str] \| None = None`. Replace the bare-sum with a per-evidence-row weighted formula: `aligning = sum(min(e.confidence * match(e.source_url, expected_experts), 1.0) for e in evidence if polarity in ("supports","neutral"))`; `contradicting = sum(e.confidence for e in evidence if polarity == "contradicts")` (multiplier does NOT apply to contradictions — boost is for agreement strength only). Return `aligning / (aligning + contradicting)` or `0.0`. Backward compatible — default kwarg keeps current behaviour. | `backend/app/confidence/structural.py` | M | 5.5 | US-22-3 AC-3..AC-6 |
| 5.7 | Thread `expected_experts` through `calculate_structural_confidence(state, kind_appropriateness=1.0, expected_experts=None)` and call `calculate_agreement(state.evidence, expected_experts=expected_experts)`. | `backend/app/confidence/structural.py` | S | 5.6 | US-22-3 AC-7 |
| 5.8 | Update `ConfidenceCalculator.calculate` and `ConfidenceCalculator.check_sufficient` to read `state.expected_experts` and forward to `calculate_structural_confidence`. | `backend/app/confidence/calculator.py` | S | 5.7 | US-22-3 AC-7 |
| 5.9 | Update `AgentOrchestrator._handle_judging` and `_handle_analyzing` callers of `calculate_agreement(...)` to pass `expected_experts=self.state.expected_experts`. Other callers in stopping signals (grep `calculate_agreement(`) updated identically — they read agreement to decide A-gate. | `backend/app/agent/orchestrator.py`, `backend/app/stopping/**` (any signal that calls `calculate_agreement`) | M | 5.6 | US-22-3 AC-7 |

### Phase 6 — Instant-answer cache (D)

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 6.1 | Create `app/agent/instant_cache.py` with: `normalise_question(s: str) -> str` (lower + strip Unicode punctuation via `unicodedata.category().startswith("P")` + collapse whitespace + `.strip()`); `CachedRun` Pydantic model carrying `run_id`, `final_confidence`, `judge_confidence`, `structural_confidence`, `stop_reason`, `answer_kind`, `answer_prose`, `answer_structured`, `answer_structured_data`, `citations`, `completed_at`; module-level `OrderedDict[tuple[str, str], CachedRun]` capped at `settings.instant_cache_max_size` (LRU eviction); `record_run(username, question, payload)` callable (called by orchestrator at terminal); `try_replay(username, question) -> CachedRun \| None` callable (called by orchestrator pre-classify). | `backend/app/agent/instant_cache.py` (NEW) | M | 1.7 | US-22-4 DoD |
| 6.2 | `try_replay` returns `None` when: dict miss, `final_confidence < settings.instant_cache_min_confidence`, `stop_reason != StopReason.JUDGE_CONFIRMED`, or any arg falsy. Pure synchronous. | `backend/app/agent/instant_cache.py` | S | 6.1 | US-22-4 AC-2, AC-3, AC-8 |
| 6.3 | Add `reset_instant_cache()` helper for tests/shutdown. | `backend/app/agent/instant_cache.py` | XS | 6.1 | US-22-4 AC-6 |
| 6.4 | Modify `AgentOrchestrator.run`: at the very top of the `is_fresh` branch (BEFORE emitting `QuestionAskedEvent`), call `try_replay(self.state.owner_username, self.state.question)`. On hit: (a) emit `QuestionAskedEvent` (still the canonical opener); (b) emit `PriorRunHintReplayedEvent`; (c) build synthetic `JudgeRuledEvent` carrying prior numerical values; (d) call `self._stop_from_cache(cached)` which builds a `StoppedEvent` with `stop_rationale.triggering_signal = "instant_cache"` and prior answer payload; (e) return `StopReason.JUDGE_CONFIRMED`. Skip classify, plan, search, analyze, draft entirely. | `backend/app/agent/orchestrator.py` | M | 1.5, 6.2 | US-22-4 AC-1, AC-7 |
| 6.5 | Add `owner_username: str \| None = None` to `RunState` and ensure `runner.py` sets it when constructing/rehydrating `RunState` (it reads `Run.owner_username` from DB). Cross-user scoping (AC-08) hinges on this. | `backend/app/agent/run_state.py`, `backend/app/agent/runner.py` | S | — | US-22-4 AC-8 |
| 6.6 | Hook `record_run(username, question, payload)` into `AgentOrchestrator._stop` — called only when `reason == StopReason.JUDGE_CONFIRMED` AND `state.last_judge_confidence is not None` AND not coming from cache replay (guard via the same path that built the `StoppedEvent`). Build `payload` from the final state values just written into `StoppedEvent`. | `backend/app/agent/orchestrator.py` | S | 6.1 | US-22-4 AC-1, AC-9 |
| 6.7 | Update `_fold_events` in `runner.py` to fold `PriorRunHintReplayedEvent`: it is **informational only** — extract `source_run_id` and `source_final_confidence` into a transient `state.metadata.replay_source_run_id` field (optional dict on `RunState`, `extra="allow"`) for audit, but do NOT mutate canonical state fields. The subsequent synthetic `JudgeRuledEvent` + `StoppedEvent` (folded by their existing fold branches, both `extra="allow"`) are responsible for populating `state.last_judge_confidence`, `state.structural_confidence`, `state.final_confidence`, `state.answer_kind`, `state.answer_prose`, `state.answer_structured`, `state.citations`, `state.stop_reason`, and `state.stop_rationale` (including `triggering_signal="instant_cache"`). Verify the existing fold branches for `JudgeRuledEvent` and `StoppedEvent` already cover these fields; if any field is missing from those branches, extend them in this task. Add an explicit forking test case (referenced from TC-09 of US-22-4 — see Task 8.5) that forks a replayed run and asserts the forked run inherits the correct `last_judge_confidence`, `final_confidence`, and `answer_kind` from the synthetic events. | `backend/app/agent/runner.py` | S | 1.5 | RF-03; US-22-4 AC-7 |

### Phase 7 — FE type generation + components

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 7.1 | Run `python scripts/export_types.py` and commit the regenerated `frontend/src/types/events.ts`. Verify it includes `ComplexityHint`, `QuestionClassifiedEvent`, `PriorRunHintReplayedEvent`, and the three new optional fields on `PlanCreatedEvent`. | `frontend/src/types/events.ts` (regenerated) | S | 1.6 | US-22-1, US-22-2, US-22-4 DoD |
| 7.2 | Create molecule `ComplexityBadge.tsx` at `frontend/src/components/molecules/ComplexityBadge.tsx`. Props: `hint: ComplexityHint`. Use shadcn `Badge` (variants: `trivial→secondary`, `standard→default`, `deep→outline`). Strings: `"Quick lookup"`, `"Standard research"`, `"Deep investigation"`. `role="status"`, `aria-label` mirrors visible text. Co-locate `ComplexityBadge.test.tsx` (renders each variant, `jest-axe` no violations). | `frontend/src/components/molecules/ComplexityBadge.tsx` (NEW), `.test.tsx` (NEW) | M | 7.1 | US-22-1 TC-08 |
| 7.3 | Create molecule `ExpectedExpertsList.tsx` at `frontend/src/components/molecules/ExpectedExpertsList.tsx`. Props: `experts: string[]`. Header `"Looking for sources from:"`. Render `<ul role="list" aria-label="Expected expert types for this plan">` with chips (existing `Badge` styling). Each expert label rendered via a tiny `formatExpertLabel(s)` helper (`s.split('_').map(titlecase).join(' ')`). Empty array → render nothing (early return). Co-locate test. | `frontend/src/components/molecules/ExpectedExpertsList.tsx` (NEW), `.test.tsx` (NEW) | M | 7.1 | US-22-3 TC-11 |
| 7.4 | Wire `ComplexityBadge` + `ExpectedExpertsList` into `PlanPreview` (`frontend/src/components/molecules/PlanPreview.tsx`). Read fields from the current `PlanCreatedEvent`; render the badge above the sub-claims list and the experts list right under it. Hide both when fields are missing. Update `PlanPreview.test.tsx` with a green-path render test. | `frontend/src/components/molecules/PlanPreview.tsx` (MODIFIED), `PlanPreview.test.tsx` (MODIFIED) | M | 7.2, 7.3 | RF-13 |
| 7.5 | Extend `EventNode.tsx` (or whichever atom/molecule renders trace rows) with a `PriorRunHintReplayed` branch: icon `Recycle` from `lucide-react`, label `"Same question answered {relative}. Reused that result (confidence {x.xx})."` using `Intl.RelativeTimeFormat`. `role="link"`, `aria-label` mirrors visible. `onClick` navigates to `source_run_id` via the existing selection-store callback already used for run links. | `frontend/src/components/molecules/EventNode.tsx` (MODIFIED), `EventNode.test.tsx` (MODIFIED) | M | 7.1 | US-22-4 AC-7, TC-10 |
| 7.6 | Update `TraceTimeline` (organism) to include the new event type in its rendered set (today it filters or maps by `event.type`). Add a stable, scrollable position so the row doesn't shift on stream resume. | `frontend/src/components/organisms/TraceTimeline.tsx` (MODIFIED), `.test.tsx` (MODIFIED) | S | 7.5 | RF-13 |

### Phase 8 — Tests

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 8.1 | New `backend/tests/test_classify_complexity.py` covering TC-01..TC-07 of US-22-1: trivial fact, standard comparative, deep state-of-art, multi-entity coercion, low-conf no-trivial, single-entity DEFINITIONAL → trivial, replay tolerates missing field. Pytest-asyncio. Mock `llm.call` via `app/llm/client.py` injection (existing pattern in `test_agent_tasks_classify.py`). | `backend/tests/test_classify_complexity.py` (NEW) | M | 3.1, 3.3 | US-22-1 |
| 8.2 | New `backend/tests/test_plan_complexity_budget.py` covering TC-01..TC-06, TC-09 of US-22-2: trivial+FACTUAL, trivial+DEFINITIONAL, standard+COMPARATIVE, deep+STATE_OF_ART (asserts 2 critiques), trivial+STATE_OF_ART coercion, `complexity_hint=None` fallback, replay tolerates missing fields. Patch the planner LLM with canned `PlanOutput` per case. | `backend/tests/test_plan_complexity_budget.py` (NEW) | M | 4.1..4.5 | US-22-2 |
| 8.3 | New `backend/tests/test_experts_taxonomy.py` covering TC-01..TC-08 of US-22-3: exact match, mismatch, blog miss, TLD-family `*.gov`, two-expert non-compound, clamp at 1.0, `None` → all 1.0, unknown label logged + no-raise. Pure unit tests, no LLM. | `backend/tests/test_experts_taxonomy.py` (NEW) | M | 5.2..5.5 | US-22-3 |
| 8.4 | New `backend/tests/test_agreement_expert_boost.py` covering TC-09, TC-10 of US-22-3: integration over a small synthetic `RunState` with 3 evidence rows (one matching expert, two not). Asserts agreement uplift and the `min(S_effective, J)` invariant via `ConfidenceCalculator.calculate`. | `backend/tests/test_agreement_expert_boost.py` (NEW) | M | 5.6, 5.8 | US-22-3 AC-7 |
| 8.5 | New `backend/tests/test_instant_answer_cache.py` covering TC-01..TC-09 of US-22-4: hit + ≥ 0.85 replays, hit + < 0.85 no replay, hit + non-JUDGE_CONFIRMED no replay, cosine-similar no replay, normalisation (whitespace/punct/case), cross-user scoping, `reset_instant_cache()` clears, replayed run appears as normal terminal (mock DB writer asserts `StoppedEvent` and `RunCreated` persisted), `PriorRunHintReplayedEvent` round-trips via the orchestrator emit hook. Use `asyncio.wait_for(orch.run(), timeout=1.0)` for the latency assertion. | `backend/tests/test_instant_answer_cache.py` (NEW) | L | 6.1..6.6 | US-22-4 |
| 8.6 | Extend `backend/tests/test_agent_runner.py` (existing) with TC-07 (Wikipedia-first in `preferred_sources`) and TC-08 (mocked-LLM trivial round-1 latency < 5 s, no PlanCritiquedEvent emitted in trivial path). | `backend/tests/test_agent_runner.py` (MODIFIED) | M | 4.7, 4.8 | US-22-2 |
| 8.7 | Extend `backend/tests/test_classify_emits_new_types.py` (existing) with `QuestionClassifiedEvent` discriminator round-trip assertion. | `backend/tests/test_classify_emits_new_types.py` (MODIFIED) | S | 1.3 | US-22-1 AC-6 |
| 8.8 | Extend `backend/tests/test_domain_events.py` + `test_domain_enums.py` (existing) with cases for `ComplexityHint`, `QuestionClassifiedEvent`, `PriorRunHintReplayedEvent`, `EventType.QUESTION_CLASSIFIED`, `EventType.PRIOR_RUN_HINT_REPLAYED`. | `backend/tests/test_domain_events.py`, `backend/tests/test_domain_enums.py` (MODIFIED) | S | 1.1, 1.2, 1.3, 1.5 | RF-03 |
| 8.9 | New FE `ComplexityBadge.test.tsx`, `ExpectedExpertsList.test.tsx`. Each: 3+ render cases, `jest-axe` no violations, `aria-label` and `role` assertions. | `frontend/src/components/molecules/ComplexityBadge.test.tsx` (NEW), `ExpectedExpertsList.test.tsx` (NEW) | M | 7.2, 7.3 | US-22-1 TC-08, US-22-3 TC-11 |
| 8.10 | Extend `frontend/src/components/molecules/EventNode.test.tsx` with `PriorRunHintReplayed` row render + a11y. Extend `PlanPreview.test.tsx` with conditional rendering of the new molecules. | FE tests (MODIFIED) | S | 7.4, 7.5 | US-22-4 TC-10 |
| 8.11 | Coverage gate: run `pytest --cov=app.agent.complexity --cov=app.agent.experts --cov=app.agent.instant_cache --cov=app.agent.tasks.classify --cov=app.agent.tasks.plan --cov=app.confidence.structural --cov-fail-under=80`. FE: `vitest --coverage` on touched files ≥ 80%. | n/a (CI/local) | S | end of Phase 8 | DoD |
| 8.12 | New `backend/tests/test_agent_orchestrator_cancel_with_complexity.py` covering RF-08 cancellation preservation across the new code paths: (a) cancel during trivial path before `SEARCHING` → `user_cancelled` emitted, no `PlanCritiquedEvent`; (b) cancel during deep path after first `PlanCritiquedEvent` but before second → `user_cancelled` emitted even though `critique_passes_completed < critique_passes_target`; (c) cancel issued in the window between `try_replay` returning a hit and `_stop_from_cache` emitting synthetic events → `user_cancelled` wins; the synthetic `JudgeRuledEvent`/`StoppedEvent` are NOT emitted. Use the existing `RunCancellation` primitive and `anyio.Event` patterns from `test_agent_runner.py`. | `backend/tests/test_agent_orchestrator_cancel_with_complexity.py` (NEW) | M | 4.8, 6.4 | RF-08 preservation |

### Phase 9 — Docs & memory bank

| # | Task | File(s) | Effort | Depends on |
|---|------|---------|--------|------------|
| 9.1 | Update `.github/memory-bank/indices/knowledge-base-index.md`: register `IP-22`, the new event types, `ComplexityHint`, `expert_taxonomy`, instant cache, two new molecules. | `.github/memory-bank/indices/knowledge-base-index.md` | S | end |
| 9.2 | Append D-IP22-01..10 (this plan §3) to `.github/memory-bank/logs/decisions-history.md`. | `.github/memory-bank/logs/decisions-history.md` | S | end |
| 9.3 | Append any new lessons learned (likely: heuristic-vs-LLM trade-offs; non-compounding multiplier shape) to `.github/memory-bank/logs/lessons-learned.md`. | `.github/memory-bank/logs/lessons-learned.md` | S | post-review |

---

## 5. File Modifications

### New files
```
backend/app/agent/complexity.py
backend/app/agent/experts/__init__.py
backend/app/agent/experts/taxonomy.py
backend/app/agent/instant_cache.py
backend/tests/test_classify_complexity.py
backend/tests/test_plan_complexity_budget.py
backend/tests/test_experts_taxonomy.py
backend/tests/test_agreement_expert_boost.py
backend/tests/test_instant_answer_cache.py
frontend/src/components/molecules/ComplexityBadge.tsx
frontend/src/components/molecules/ComplexityBadge.test.tsx
frontend/src/components/molecules/ExpectedExpertsList.tsx
frontend/src/components/molecules/ExpectedExpertsList.test.tsx
docs/implementation-phase/implementation-plans/IP-22-complexity-aware-planning-and-experts.md (this file)
```

### Modified files
```
backend/app/config.py
backend/app/domain/enums.py
backend/app/domain/events.py
backend/app/llm/models.py
backend/app/llm/prompts.py   (or app/llm/roles.py — wherever the classifier+planner system prompts live)
backend/app/agent/run_state.py
backend/app/agent/runner.py
backend/app/agent/orchestrator.py
backend/app/agent/tasks/classify.py
backend/app/agent/tasks/plan.py
backend/app/confidence/structural.py
backend/app/confidence/calculator.py
backend/app/stopping/**          (any signal calling calculate_agreement)
backend/tests/test_agent_runner.py
backend/tests/test_classify_emits_new_types.py
backend/tests/test_domain_events.py
backend/tests/test_domain_enums.py
frontend/src/types/events.ts          (auto-regenerated)
frontend/src/components/molecules/PlanPreview.tsx
frontend/src/components/molecules/PlanPreview.test.tsx
frontend/src/components/molecules/EventNode.tsx
frontend/src/components/molecules/EventNode.test.tsx
frontend/src/components/organisms/TraceTimeline.tsx
frontend/src/components/organisms/TraceTimeline.test.tsx
.github/memory-bank/indices/knowledge-base-index.md
.github/memory-bank/logs/decisions-history.md
.github/memory-bank/logs/lessons-learned.md
```

---

## 6. Database Changes

**None.** No migration. All state lives in the event log (RF-03). The instant cache is in-memory and cleared on uvicorn restart (RF-05).

---

## 7. API Contract

**No new endpoints.** All changes flow through the existing `POST /api/runs` and the SSE stream (RF-08). The new events join the discriminated union and surface through the standard streamed envelope.

---

## 8. Dependencies & Order

```
1.1, 1.2, 1.7  ─┐
1.3, 1.5       ─┼─→ 1.4, 1.6 ─→ Phase 7.1 (types) ─→ Phase 7.2..7.6 (FE) ─→ 8.9, 8.10
2.1, 2.2       ─┘
3.1, 3.2 ─→ 3.3 ─→ 3.4 ─────────→ 8.1, 8.7, 8.8
4.1..4.6 ─→ 4.7, 4.8 ─→ 4.9 ─────→ 8.2, 8.6
5.1..5.5 ─→ 5.6 ─→ 5.7, 5.8, 5.9 ─→ 8.3, 8.4
6.1..6.3 ─→ 6.4, 6.5, 6.6, 6.7 ───→ 8.5
Phase 8 ─→ 8.11 (coverage gate) ─→ Phase 9
```

Coder MUST land Phase 1 + 2 first (no caller of new types yet — pure additive). Phases 3–6 can land in any order but each ends with its own tests. Phase 7 follows after `export_types.py` runs in 7.1.

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Classifier LLM omits `confidence` field on existing prompts | Medium | High | `verdict.confidence or 1.0` fallback (Task 3.3). When fallback hits, heuristic falls through to the length/entity tests; trivial path still reachable for short single-entity factual. |
| `_count_named_entities` over-counts on ALL-CAPS acronyms ("PostgreSQL vs MongoDB") | Low | Medium | Heuristic intentionally counts these as separate entities → COMPARATIVE+two-entity ⇒ `standard`. That matches US-22-1 Scenario 2 expectation. |
| Forced second critique on `deep` infinite-loops if both critiques reject | Medium | Low | Guard: `state.critique_passes_completed >= critique_passes_target` exits the forced branch; from there, existing `max_plan_revisions=2` cap applies. |
| Agreement multiplier compounds because `_handle_judging` re-calls `calculate_agreement` per round | High | Low | Multiplier is applied per-row inside `calculate_agreement`; it is NOT stored on `EvidenceItem`. Each call recomputes from scratch. AC-05 test enforces non-compounding directly. |
| Instant cache replay confuses fork lineage (BRD-15) | Medium | Low | Replayed runs have `parent_run_id=None` (they are NOT forks). `PriorRunHintReplayedEvent.source_run_id` is informational only; the History panel and fork modal continue to treat the replayed run as a fresh terminal run. Tests assert this in TC-08 of US-22-4. |
| `QuestionClassifiedEvent` insertion shifts `step_index` numbering and breaks the resume `_fold_events` | High | Low | `_fold_events` keys by `event.type`, not `step_index`. The `RESUMED_AFTER_*` pre-scan reads `step_index` only for the STOPPED-resume pairing, which is unaffected. Resume tests in `test_agent_runner` must be re-run (Task 8.6). |
| FE `ComplexityHint` enum and types out-of-sync because dev forgets `export_types.py` | Medium | Medium | CI / pre-commit runs `python scripts/export_types.py && git diff --exit-code frontend/src/types/events.ts` (existing pattern). Task 7.1 is a hard gate before Phase 7.2. |
| `expected_experts` from LLM is hallucinated outside the vocabulary | Low | Medium | `match()` silently ignores unknown labels (AC-9) and logs at DEBUG. No multiplier applied. Trust surface still renders the chips, which acts as visible feedback. |

---

## 10. Acceptance Mapping (BRD-22 AC → tasks/tests)

| BRD-22 AC | Tasks covering it | Tests asserting it |
|---|---|---|
| AC-01 trivial fact short-circuit | 3.1–3.4, 4.1–4.8 | 8.1 TC-01, 8.2 TC-01, 8.6 TC-08 |
| AC-02 standard unchanged | 4.1–4.4 | 8.2 TC-03 |
| AC-03 deep extra critique | 4.1, 4.7, 4.8 | 8.2 TC-04 |
| AC-04 expert multiplier | 5.5, 5.6 | 8.3 TC-01, 8.4 TC-09 |
| AC-05 non-compounding | 5.5 | 8.3 TC-05 |
| AC-06 cache replay ≤ 1 s | 6.1–6.6 | 8.5 TC-01 |
| AC-07 cache miss falls through | 6.2 | 8.5 (no-hit case) |
| AC-08 low-confidence ignored | 6.2 | 8.5 TC-02 |
| AC-09 historical replay | 1.4, 4.4, 4.9, 6.7 | 8.1 TC-07, 8.2 (replay tolerates missing fields case), 8.7, 8.8 |
| RF-08 cancellation preserved | 4.8, 6.4 | 8.12 |

---

## 11. Open Questions for Auditor (F2)

1. Should the second critique pass on `deep` always force a revision even when the first critique is `acceptable=true`? **Plan choice: yes** (US-22-2 AC-3 says "Exactly two PlanCritiquedEvent events"). Confirm.
2. Should `_handle_critiquing` count `PlanRevisedEvent` toward `critique_passes_completed` or only `PlanCritiquedEvent`? **Plan choice: only `PlanCritiquedEvent`** (the name is literal).
3. Multiplier on contradictions: should expert-matched contradicting evidence get a 1.1× boost as well? **Plan choice: no** (Task 5.6 — multiplier is for agreement strength only; boosting contradictions would punish expert sources, contradicting BRD intent). Confirm.

---

## 12. Definition of Done

- [ ] All Phase 1–9 tasks completed
- [ ] All new + modified tests green (`pytest backend/tests` + `vitest run` in frontend)
- [ ] Coverage ≥ 80% on every new module + every modified module
- [ ] `python scripts/export_types.py` produces no diff after commit
- [ ] Memory bank updated (`decisions-history.md` + `knowledge-base-index.md` + `lessons-learned.md`)
- [ ] No new RF violations; `min(S_effective, J)` invariant manually verified via Task 8.4
- [ ] Reviewer score ≥ 9/10 (F4 gate)

---

## 13. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | Orchestrator Agent | Initial plan (F2 iter 1) |
| 1.1 | 2026-05-27 | Orchestrator Agent | F2 iter 2: applied AUDIT-IP-22 iter 1 feedback — Tasks 2.1, 2.2 (English-policy note), 3.2 (entity heuristic clarified), 4.4 (revise_plan STANDARD fallback + log), 4.6 (replay-determinism strategy for critique counters), 4.9 (recompute counters during fold), 6.7 (explicit fold contract for replay events + fork test), §10 (AC-09 + RF-08 rows); added Task 8.12 (cancellation tests). |
