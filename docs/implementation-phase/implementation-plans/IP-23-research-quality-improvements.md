# Implementation Plan — IP-23: Research-Quality Improvements (Temporal · Authority · Deep-Fetch · Query Hygiene)

**Plan ID:** IP-23
**Parent BRD:** [BRD-23 v1.1](../brds/BRD-23-research-quality-improvements.md)
**Parent User Stories:** US-23-1, US-23-2, US-23-3, US-23-4 *(to be authored separately downstream)*
**Date:** 2026-05-27
**Author:** Orchestrator Agent
**Complexity:** L (deep) — `quality_profiles.L`, model tier `balanced` (Claude Sonnet 4.5)
**Estimated Effort:** L (≈ 5–6 h pair-session, split across four phases)
**Iteration:** 1

---

## 1. Plan summary

IP-23 ships the four research-quality levers defined in BRD-23 v1.1 as **four sequential phases**, each additive against the post-BRD-22 baseline, each independently shippable, and each touching the event log only through optional fields or one strictly-additive event type. The agent becomes (a) **temporally aware** of how fast its answer goes stale, (b) **authority-weighted** when summing evidence into `S_raw`, (c) **willing to fetch a full page** when a critical-path claim is supported but shallow, and (d) **disciplined in how it asks the web**. No new FSM state, no new plugin seam, no new env var is required; one new event type (`DeepFetchPerformed`) and six new optional event fields cover the surface. The `final_confidence = min(S_effective, J)` invariant (RF-12) is preserved end-to-end — WP-3's multiplier acts strictly inside `C_coverage` / `C_independence`, and WP-1's stale penalty acts strictly inside `kind_ceiling["direct"]`.

### BRD-23 work packages → IP-23 phases

| BRD-23 WP | IP-23 Phase | One-line scope |
|---|---|---|
| WP-4 — Query hygiene | **Phase 1** (lowest blast radius first) | Planner prompt clause + additive `query_length_tokens` on `ToolCalledEvent`. |
| WP-1 — Temporal sensitivity | **Phase 2** | New `TemporalSensitivity` enum + classifier heuristic + planner Tavily/Wikipedia routing + Tavily `days` filter + judge stale-citation rule + `kind_ceiling["direct"]` penalty. |
| WP-3 — Authority tiering | **Phase 3** | New `AuthorityTier` enum + static domain table + per-evidence-row multiplier on `C_coverage` / `C_independence` + `confidence-calculation.md` amendment in the SAME PR. |
| WP-2 — Deep-fetch escalation | **Phase 4** (largest blast radius last) | Optional `Source.fetch_full()` method (default `None`) on the existing seam, implemented for Tavily & Wikipedia + new `DeepFetchPerformedEvent` + budget keyed on `complexity_hint`. |

### Phase-ordering rationale

The order is deliberately reversed against BRD-23 §13 (which suggested WP-1 → WP-4 → WP-3 → WP-2). The override reasons are:

1. **Phase 1 = WP-4 (pure prompt change + one additive optional field).** Zero schema risk, zero confidence-formula risk, zero fold risk. It establishes the *baseline measurement* (`query_length_tokens` on every `ToolCalledEvent`) that the smoke matrix needs *before* later phases start changing what the planner emits.
2. **Phase 2 = WP-1.** Adds the `temporal_sensitivity` field that Phase 3 cross-references for AC-04 (the stale-citation ceiling penalty is the bridge between WP-1 and WP-3) and that Phase 4 also reads to bound deep-fetch latency on `realtime` topics.
3. **Phase 3 = WP-3.** The confidence-formula change is the highest review surface. It must land *after* WP-1 (because AC-04 depends on `temporal_sensitivity`) and *before* WP-2 (because the deep-fetch trigger inside `analyze.py` re-runs `calculate_structural_confidence` after replacing evidence text — having the multiplier already wired keeps the re-computation honest). The `confidence-calculation.md` amendment **ships in the same PR** as Phase 3 code (BRD §15.3 Q6 — hard gate).
4. **Phase 4 = WP-2.** Biggest blast radius (new event type, new Protocol method, new orchestrator branch, two source implementations). It benefits from the WP-1 temporal field and the WP-3 authority chip being live in the trace UI so that a deep-fetched evidence row immediately renders with the right context.

---

## 2. Phase breakdown

> **Convention.** Each task is numbered `T-23-<phase>-<NN>`, tagged `[backend] / [frontend] / [types] / [doc] / [test]`, mapped to file paths, sized at ≤ ~80 LOC delta where practical, and cross-references the BRD-23 section it implements.

### 2.1 Phase 1 — WP-4 Query hygiene

#### 2.1.1 — Goal & BRD anchors

**Goal.** Tighten search queries via a planner system-prompt clause and expose `query_length_tokens` on every `ToolCalledEvent` so we can measure compliance.

**Satisfies ACs:** AC-10 (planner emits short queries).

**Schema additions introduced by this phase:**
- `ToolCalledEvent.query_length_tokens: int | None = None` (BRD §9, WP-4).

#### 2.1.2 — Task list

| # | Task | File(s) | Effort | Tag | BRD § |
|---|------|---------|--------|-----|-------|
| **T-23-1-01** | Add optional `query_length_tokens: int \| None = None` and `tavily_days_filter: int \| None = None` to `ToolCalledEvent`. Order: append after existing fields. `extra="allow"` already in place. **Both** fields go in this phase even though `tavily_days_filter` is logically WP-1 — they ship in the same model edit to keep Phase 2 strictly behavioural. | `backend/app/domain/events.py` | XS | [backend] | §4.4, §4.8, §9 |
| **T-23-1-02** | Extend `PLANNER_SYSTEM_PROMPT` in `app/llm/prompts.py` with the exact 4-clause English block from BRD §4.8 (≤ 6 tokens, no stop-words except inside quoted exact-match phrases, quotes only on required exact phrases, technical connectors `vs / and / + / - / site:` do not count). Add the self-rewrite instruction (*"If your draft query violates (a)-(c), rewrite it once before emitting."*). Language: **English only** per `/memories/language-policy.md`. | `backend/app/llm/prompts.py` | S | [backend] | §4.8 |
| **T-23-1-03** | At the single emission site of `ToolCalledEvent` (grep for `ToolCalledEvent(` in `backend/app/agent/`), compute `query_length_tokens = len(query.split())` and pass it on construction. If multiple emission sites exist, factor a tiny `_count_query_tokens(query: str) -> int` helper in `app/agent/tasks/search.py` to avoid drift. | `backend/app/agent/tasks/search.py` (or wherever `ToolCalledEvent` is constructed) | S | [backend] | §4.8 |
| **T-23-1-04** | Regenerate `frontend/src/types/events.ts` via `python scripts/export_types.py`. Verify `query_length_tokens` and `tavily_days_filter` appear on `ToolCalledEvent`. Commit the regenerated file. | `frontend/src/types/events.ts` | XS | [types] | §4.1 |

#### 2.1.3 — Test plan

| Test file | Test name | Verifies AC | New / Modified |
|---|---|---|---|
| `backend/tests/test_planner_query_hygiene.py` | `test_planner_system_prompt_contains_6_token_clause` | AC-10 (prompt content) | NEW |
| `backend/tests/test_planner_query_hygiene.py` | `test_planner_system_prompt_contains_stopword_rule` | AC-10 | NEW |
| `backend/tests/test_planner_query_hygiene.py` | `test_planner_system_prompt_contains_quoted_phrase_rule` | AC-10 | NEW |
| `backend/tests/test_planner_query_hygiene.py` | `test_planner_system_prompt_contains_technical_connectors_exception` | AC-10 | NEW |
| `backend/tests/test_tool_called_query_length.py` | `test_query_length_tokens_set_on_every_tool_called_event` | AC-10 | NEW |
| `backend/tests/test_tool_called_query_length.py` | `test_query_length_tokens_counts_whitespace_split_only` (no NLP) | AC-10 | NEW |
| `backend/tests/test_tool_called_query_length.py` | `test_query_length_tokens_absent_on_pre_brd23_replay` (None tolerated) | AC-09 | NEW |
| `backend/tests/test_domain_events.py` (existing) | `test_tool_called_event_accepts_query_length_tokens_and_tavily_days_filter` | AC-09, schema-compat | MODIFIED |

Coverage gate: `pytest --cov=app.llm.prompts --cov=app.agent.tasks.search --cov-fail-under=80` on the new code paths.

#### 2.1.4 — Risks & mitigations specific to Phase 1

| Risk | Mitigation |
|---|---|
| Planner under-performs on multi-entity comparative questions because of the 6-token cap. | Technical connectors (`vs`, `+`, `-`, `site:`) are explicitly excluded from the cap in the prompt clause; the rule is a soft guardrail (no code-enforced rejection), so the LLM can self-violate when needed. AC-10 only asks for ≥ 90 % compliance, not 100 %. *(BRD §11 row 7.)* |
| `query_length_tokens` set inconsistently if `ToolCalledEvent` is emitted from > 1 site. | T-23-1-03 grep-step explicitly enumerates emission sites and factors a helper if > 1 exists. |

#### 2.1.5 — Rollback strategy

Revert T-23-1-02 (single prompt block) → planner reverts to pre-BRD-23 prompt verbatim. Revert T-23-1-01 → field disappears from the model; `extra="allow"` means any persisted event with the field still round-trips. T-23-1-04 (FE types) re-runs `export_types.py` on the reverted backend to regenerate without the field. No DB migration to roll back.

---

### 2.2 Phase 2 — WP-1 Temporal sensitivity

#### 2.2.1 — Goal & BRD anchors

**Goal.** Classify every question on a 4-valued temporal scale, route Tavily-first / inject a `days` filter on volatile/realtime topics, penalize stale citations in the judge prompt, and lower `kind_ceiling["direct"]` by `0.85` when the stale-citation condition is met.

**Satisfies ACs:** AC-01 (volatile → Tavily + 180-day filter), AC-02 (static unchanged, BRD-22 regression preserved), AC-03 (realtime excludes Wikipedia evidence), AC-04 (stale-citation ceiling penalty), AC-09 (replay tolerance for the new fields).

**Schema additions introduced by this phase:**
- `TemporalSensitivity` StrEnum (`static / slow_changing / volatile / realtime`) — `app/domain/enums.py`.
- `QuestionClassifiedEvent.temporal_sensitivity: TemporalSensitivity | None = None`.
- `PlanCreatedEvent.temporal_sensitivity: TemporalSensitivity | None = None` (mirrored).
- `EvidenceAddedEvent.source_published_date: datetime | None = None` (consumed by judge stale-check).

(`ToolCalledEvent.tavily_days_filter` was already added in Phase 1.)

#### 2.2.2 — Task list

| # | Task | File(s) | Effort | Tag | BRD § |
|---|------|---------|--------|-----|-------|
| **T-23-2-01** | Add `TemporalSensitivity(StrEnum)` with the four values from BRD §4.4. | `backend/app/domain/enums.py` | XS | [backend] | §4.4 |
| **T-23-2-02** | Add optional `temporal_sensitivity: TemporalSensitivity \| None = None` to `QuestionClassifiedEvent` and `PlanCreatedEvent`. Add optional `source_published_date: datetime \| None = None` to `EvidenceAddedEvent`. All `extra="allow"` preserved. | `backend/app/domain/events.py` | S | [backend] | §4.4, §9 |
| **T-23-2-03** | Add settings to `app/config.py`: `temporal_stale_penalty: float = 0.85` (env `TEMPORAL_STALE_PENALTY`). No other env vars introduced by Phase 2. | `backend/app/config.py` | XS | [backend] | §8 |
| **T-23-2-04** | Implement deterministic `derive_temporal_sensitivity(question: str, question_type: QuestionType) -> TemporalSensitivity` in a new helper at the top of `app/agent/tasks/classify.py` (or in `app/agent/complexity.py` as a sibling — prefer `classify.py` to keep the temporal heuristic next to its single consumer). Implements the §4.5 rules verbatim: `realtime` markers, last-18-month year markers ⇒ `volatile`, `STATE_OF_ART`/`COMPARATIVE` ⇒ `volatile`, `population`/`ranking`/`top`/`in 20XX`/`as of` ⇒ `slow_changing`, FACTUAL/DEFINITIONAL with no temporal marker ⇒ `static`. Pure synchronous, no LLM call. Marker lists are module-level frozen sets, all lowercase. | `backend/app/agent/tasks/classify.py` | M | [backend] | §4.5 |
| **T-23-2-05** | Wire `derive_temporal_sensitivity` into `classify_question`: extend the return tuple with the temporal value and write it into the `QuestionClassifiedEvent` payload emitted by `_detect_question_type` in `orchestrator.py`. Add `state.temporal_sensitivity: TemporalSensitivity \| None = None` to `RunState`. | `backend/app/agent/tasks/classify.py`, `backend/app/agent/orchestrator.py`, `backend/app/agent/run_state.py` | S | [backend] | §4.5 |
| **T-23-2-06** | Add a single sentence to `CLASSIFIER_SYSTEM_PROMPT` in `app/llm/prompts.py` instructing the model to consider temporal cues. **The heuristic in T-23-2-04 is authoritative**; the prompt sentence is a soft hint to keep the LLM's classification consistent with the heuristic. Language: **English** (per `/memories/language-policy.md`). | `backend/app/llm/prompts.py` | XS | [backend] | §4.5 |
| **T-23-2-07** | In `app/agent/tasks/plan.py`, implement the §4.5 routing table. On `volatile` ⇒ planner prefers `tavily` first via `PlanCreatedEvent.preferred_sources = ["tavily", "wikipedia"]`; on `realtime` ⇒ `PlanCreatedEvent.preferred_sources = ["tavily"]` (Wikipedia filtered out of evidence collection but still allowed as a definitional anchor — orchestrator already handles `preferred_sources` ordering from IP-22 §4.6/Task 4.3). Mirror `temporal_sensitivity` into the new `PlanCreatedEvent.temporal_sensitivity` field. | `backend/app/agent/tasks/plan.py` | S | [backend] | §4.5 |
| **T-23-2-08** | In `app/agent/tasks/search.py`, when constructing each Tavily `ToolCalledEvent`, set `tavily_days_filter` per the table: `slow_changing→730`, `volatile→180`, `realtime→7`, `static→None`. Pass the corresponding `days` kwarg to the existing `TavilySource.search(...)` call (extend the `Source.search` signature if needed — see T-23-2-09). | `backend/app/agent/tasks/search.py` | S | [backend] | §4.5 |
| **T-23-2-09** | Extend `Source.search(...)` Protocol in `app/seams/source.py` with an optional `days: int \| None = None` keyword. `TavilySource.search` forwards it to the Tavily client `search_depth="advanced", days=days`. `WikipediaSource.search` ignores `days` (returns same results). Default `None` keeps every existing call-site valid. **Strictly additive** — Architecture rule #1 preserved. | `backend/app/seams/source.py`, `backend/app/sources/tavily.py`, `backend/app/sources/wikipedia.py`, `backend/app/sources/base.py` | M | [backend] | §4.5 |
| **T-23-2-10** | In `app/agent/tasks/search.py`, when an `EvidenceAddedEvent` is built from a Tavily / Wikipedia hit, populate `source_published_date` from the source's `published_date` field if present, else `None`. Both `SourceResult` models already expose this on Tavily (it's part of the upstream payload); for Wikipedia leave `None` for V1. | `backend/app/agent/tasks/search.py`, `backend/app/sources/tavily.py` | S | [backend] | §4.4 |
| **T-23-2-11** | Extend `JUDGE_SYSTEM_PROMPT` in `app/llm/prompts.py` with the exact paragraph from BRD §4.5 (soft penalty up to 0.10 on stale citations when temporal is `volatile/realtime`; flag `supported_but_shallow` on the claim when every supporting citation is older than `days_filter`). Language: **English**. | `backend/app/llm/prompts.py` | S | [backend] | §4.5 |
| **T-23-2-12** | Modify `app/confidence/kind_ceiling.py` to accept `temporal_sensitivity` + a per-evidence-row stale flag. When `AnswerKind == direct` AND `temporal_sensitivity ∈ {volatile, realtime}` AND `≥ 50 %` of supporting evidence has `source_published_date` older than the active `days_filter` (read from the corresponding `ToolCalledEvent.tavily_days_filter`), multiply the existing `kind_ceiling["direct"]` (= `1.00`) by `settings.temporal_stale_penalty` (= `0.85`). Never raises the ceiling — only lowers it. RF-12 `min(S_effective, J)` invariant unchanged. | `backend/app/confidence/kind_ceiling.py` | M | [backend] | §4.5 |
| **T-23-2-13** | Thread `temporal_sensitivity` and the stale-evidence flag from `state` into `calculate_structural_confidence(...)` in `app/confidence/structural.py` and into `ConfidenceCalculator.calculate` (`app/confidence/calculator.py`). Stale flag is computed once at the top of `calculate_structural_confidence` from `state.evidence` and `state.tavily_days_filter` (which is folded from `ToolCalledEvent`). | `backend/app/confidence/structural.py`, `backend/app/confidence/calculator.py` | M | [backend] | §4.5 |
| **T-23-2-14** | Update `runner.py::_fold_events`: fold the new optional fields on `QuestionClassifiedEvent`, `PlanCreatedEvent`, `EvidenceAddedEvent`, and `ToolCalledEvent`. Tolerate absence (replay pre-BRD-23). No new persisted state — `tavily_days_filter` lives on the event, the fold writes it back onto `state` for the synthesizer to consume. | `backend/app/agent/runner.py` | S | [backend] | §9, RF-03 |
| **T-23-2-15** | Create atom `TemporalSensitivityBadge.tsx` (props `value: TemporalSensitivity`). Microcopy strings (English, mandatory exact match — see §3): `Static fact / Slow-changing / Volatile topic / Real-time`. Use existing `Badge` atom with variant mapping `static→secondary`, `slow_changing→secondary`, `volatile→default`, `realtime→destructive`. `role="status"`, `aria-label` mirrors visible text. Co-locate `.test.tsx` (3+ render cases, jest-axe clean). | `frontend/src/components/atoms/TemporalSensitivityBadge.tsx`, `.test.tsx` | M | [frontend] | §4.10 |
| **T-23-2-16** | Render `<TemporalSensitivityBadge>` next to the existing `<ComplexityBadge>` inside `PlanPreview.tsx` (or in `RunHeader.tsx` — whichever organism already hosts `ComplexityBadge`; verify with grep). Hide when the field is missing. Update the corresponding `.test.tsx`. | `frontend/src/components/molecules/PlanPreview.tsx` (or `organisms/RunHeader.tsx`), `.test.tsx` | S | [frontend] | §4.11 |
| **T-23-2-17** | Regenerate `frontend/src/types/events.ts` via `python scripts/export_types.py`. Verify `TemporalSensitivity` enum + new optional fields are present. | `frontend/src/types/events.ts` | XS | [types] | §4.1 |

#### 2.2.3 — Test plan

| Test file | Test name | Verifies AC | New / Modified |
|---|---|---|---|
| `backend/tests/test_classify_temporal.py` | `test_volatile_when_state_of_art_with_year_marker` | AC-01 | NEW |
| `backend/tests/test_classify_temporal.py` | `test_static_when_factual_no_marker` (capital of Japan) | AC-02 | NEW |
| `backend/tests/test_classify_temporal.py` | `test_realtime_when_current_price_marker` | AC-03 | NEW |
| `backend/tests/test_classify_temporal.py` | `test_slow_changing_when_population_marker` | §4.5 | NEW |
| `backend/tests/test_classify_temporal.py` | `test_temporal_sensitivity_emitted_on_question_classified_event` | AC-01, AC-09 | NEW |
| `backend/tests/test_plan_temporal_routing.py` | `test_volatile_routes_tavily_first_with_180_day_filter` | AC-01 | NEW |
| `backend/tests/test_plan_temporal_routing.py` | `test_realtime_excludes_wikipedia_evidence_and_sets_7_day_filter` | AC-03 | NEW |
| `backend/tests/test_plan_temporal_routing.py` | `test_static_keeps_no_days_filter_and_brd22_trivial_path_preserved` | AC-02 | NEW |
| `backend/tests/test_plan_temporal_routing.py` | `test_slow_changing_sets_730_day_filter` | §4.5 | NEW |
| `backend/tests/test_kind_ceiling_temporal_penalty.py` | `test_direct_kind_ceiling_lowered_when_majority_stale_on_volatile` | AC-04 | NEW |
| `backend/tests/test_kind_ceiling_temporal_penalty.py` | `test_direct_kind_ceiling_unchanged_when_static_topic` | AC-02 | NEW |
| `backend/tests/test_kind_ceiling_temporal_penalty.py` | `test_min_s_effective_j_invariant_holds_after_penalty` | AC-04, RF-12 | NEW |
| `backend/tests/test_domain_events.py` (existing) | `test_question_classified_event_accepts_temporal_sensitivity` | schema-compat | MODIFIED |
| `backend/tests/test_domain_events.py` (existing) | `test_plan_created_event_accepts_temporal_sensitivity` | schema-compat | MODIFIED |
| `backend/tests/test_domain_events.py` (existing) | `test_evidence_added_event_accepts_source_published_date` | schema-compat | MODIFIED |
| `backend/tests/test_domain_enums.py` (existing) | `test_temporal_sensitivity_enum_values` | §4.4 | MODIFIED |
| `frontend/src/components/atoms/TemporalSensitivityBadge.test.tsx` | 4 variants render, aria-label correct, jest-axe clean | §4.10 | NEW |

Coverage gate: `pytest --cov=app.agent.tasks.classify --cov=app.agent.tasks.plan --cov=app.agent.tasks.search --cov=app.confidence.kind_ceiling --cov=app.confidence.structural --cov-fail-under=80`. Frontend: `vitest --coverage` on the new atom ≥ 80 %.

#### 2.2.4 — Risks & mitigations specific to Phase 2

| Risk | Mitigation |
|---|---|
| Heuristic misclassifies a volatile topic as `static` → stale answer not penalised. *(BRD §11 row 1.)* | Heuristic is conservative (`static` is the default only for FACTUAL/DEFINITIONAL with **zero** temporal markers); the judge prompt independently flags stale citations even when the classifier says `static`. |
| `days` filter on volatile topics removes a still-correct long-form authoritative article. *(BRD §11 row 6.)* | Judge can lift the penalty via `kind_appropriateness`; the stale rule penalises *citations*, not *sources*; AC-04 ceiling drop is bounded (`× 0.85`, not `× 0.5`). |
| `Source.search` signature change breaks the existing source registry test set. | New `days: int \| None = None` kwarg is **optional**, default `None`; every existing call-site stays valid. Coverage test in `test_agent_runner.py` re-asserts the cascade. |
| `tavily_days_filter` not folded into `state` ⇒ `kind_ceiling` cannot tell if a citation is stale. | T-23-2-14 fold step is explicitly tested by `test_kind_ceiling_temporal_penalty.py::test_min_s_effective_j_invariant_holds_after_penalty`. |

#### 2.2.5 — Rollback strategy

Revert T-23-2-12 + T-23-2-13 (kind-ceiling penalty + threading) → ceiling reverts to `1.00`; everything else degrades to "label-only" behaviour without affecting confidence math. Revert T-23-2-07 + T-23-2-08 → planner stops routing by temporal sensitivity and Tavily stops receiving `days`. Revert T-23-2-02 → fields disappear from the models; `extra="allow"` means persisted events still round-trip. Revert T-23-2-15..T-23-2-17 → FE loses the badge but does not crash (badge is rendered behind a truthy check on the field). No DB migration to roll back.

---

### 2.3 Phase 3 — WP-3 Authority tiering

#### 2.3.1 — Goal & BRD anchors

**Goal.** Bucket every evidence source into one of four authority tiers and multiply its contribution to `C_coverage` and `C_independence` by the tier multiplier. `C_agreement` and `C_no_conflict` are untouched. RF-12 `min(S_effective, J)` invariant preserved.

**Satisfies ACs:** AC-07 (`.gov` boost), AC-08 (`low_signal` penalty), AC-09 (replay tolerance for the `authority_tier` field).

**Schema additions introduced by this phase:**
- `AuthorityTier` StrEnum (`primary_authoritative / reputable_secondary / general / low_signal`) — `app/domain/enums.py`.
- `EvidenceAddedEvent.authority_tier: AuthorityTier | None = None`.

**Doc gate (hard requirement, BRD §15.3 Q6).** The amendment to `docs/understanding-phase/confidence-calculation.md` MUST land in the same PR as the Phase 3 code change. Phase 3 ships only when both are reviewed together.

#### 2.3.2 — Task list

| # | Task | File(s) | Effort | Tag | BRD § |
|---|------|---------|--------|-----|-------|
| **T-23-3-01** | Add `AuthorityTier(StrEnum)` with the four values from BRD §4.4. | `backend/app/domain/enums.py` | XS | [backend] | §4.4 |
| **T-23-3-02** | Add optional `authority_tier: AuthorityTier \| None = None` to `EvidenceAddedEvent`. `extra="allow"` preserved. | `backend/app/domain/events.py` | XS | [backend] | §4.4, §9 |
| **T-23-3-03** | Add config knobs to `app/config.py`: `authority_multiplier_primary: float = 1.05`, `authority_multiplier_reputable: float = 1.00`, `authority_multiplier_general: float = 0.90`, `authority_multiplier_low: float = 0.50` (env vars `AUTHORITY_MULTIPLIER_PRIMARY`, `..._GENERAL`, `..._LOW`). | `backend/app/config.py` | XS | [backend] | §8 |
| **T-23-3-04** | Create new package `backend/app/agent/sources_authority/__init__.py` exporting `match`, `AuthorityTier`. | `backend/app/agent/sources_authority/__init__.py` (NEW) | XS | [backend] | §4.7 |
| **T-23-3-05** | Create `backend/app/agent/sources_authority/tiers.py` with the static `_TIER_RULES` list verbatim from BRD §4.7 (compiled regex tuples). Public API: `def match(source_url_or_host: str) -> AuthorityTier` — host extraction via `urllib.parse.urlparse` (lowercase, strip `www.`); on no-match returns `AuthorityTier.GENERAL`. Pure, synchronous, no I/O. Patterns are compiled once at module import (module-level `_COMPILED: list[tuple[Pattern, AuthorityTier]]`). | `backend/app/agent/sources_authority/tiers.py` (NEW) | M | [backend] | §4.7 |
| **T-23-3-06** | At the single emission site of `EvidenceAddedEvent` (in `app/agent/tasks/search.py` or `app/agent/tasks/analyze.py` — grep first), call `authority_tier = match(source_url)` and set the new field. | `backend/app/agent/tasks/search.py` (or `analyze.py`) | S | [backend] | §4.7 |
| **T-23-3-07** | In `app/confidence/structural.py`, modify `calculate_coverage(...)` and `calculate_independence(...)` (or whatever their actual names are — verify with grep) to accept the per-evidence-row tier and apply the multiplier table from BRD §4.7. After multiplication each component is clamped to `[0.0, 1.0]`. **`calculate_agreement` and `calculate_no_conflict` are NOT modified** — authority is about *who*, not *whether they agree*. Read multipliers from `settings.*` (T-23-3-03). | `backend/app/confidence/structural.py` | M | [backend] | §4.7 |
| **T-23-3-08** | Update `calculate_structural_confidence(state, ...)` to read `evidence.authority_tier` (with `GENERAL` fallback when `None` — preserves pre-BRD-23 trace behaviour) and thread it into the two component calculators. | `backend/app/confidence/structural.py`, `backend/app/confidence/calculator.py` | S | [backend] | §4.7 |
| **T-23-3-09** | Update `runner.py::_fold_events` to fold `authority_tier` from `EvidenceAddedEvent` onto `state.evidence[*]`. | `backend/app/agent/runner.py` | XS | [backend] | RF-03 |
| **T-23-3-10** | **Doc gate (hard, ship in this PR).** Amend `docs/understanding-phase/confidence-calculation.md` with a new subsection: *"Per-evidence-row authority-tier multiplier"* explaining the BRD §4.7 table, the `C_coverage` / `C_independence`-only scope, the `[0, 1]` clamp, the asymmetric design (`1.05` vs `0.50`), and the explicit RF-12 preservation argument. Cross-link BRD-23 §4.7 and §15.3 Q6. | `docs/understanding-phase/confidence-calculation.md` | M | [doc] | §15.3 Q6 |
| **T-23-3-11** | Create atom `AuthorityTierChip.tsx` (props `tier: AuthorityTier`). Microcopy strings (English, mandatory exact match — see §3): `Primary / Reputable / General / Low signal`. Variant mapping: `primary_authoritative→default`, `reputable_secondary→secondary`, `general→outline`, `low_signal→destructive`. `role="status"`, `aria-label` mirrors visible text. Co-locate `.test.tsx`. | `frontend/src/components/atoms/AuthorityTierChip.tsx`, `.test.tsx` | M | [frontend] | §4.10 |
| **T-23-3-12** | Render `<AuthorityTierChip>` on each citation row inside `SourcesCard.tsx` (the organism that lists citations — verify the exact component with `grep_search`). Hide when `authority_tier` is missing. Update `SourcesCard.test.tsx`. | `frontend/src/components/organisms/SourcesCard.tsx`, `.test.tsx` | S | [frontend] | §4.11 |
| **T-23-3-13** | Regenerate `frontend/src/types/events.ts` via `python scripts/export_types.py`. Verify `AuthorityTier` enum + the new optional field appear. | `frontend/src/types/events.ts` | XS | [types] | §4.1 |

#### 2.3.3 — Test plan

| Test file | Test name | Verifies AC | New / Modified |
|---|---|---|---|
| `backend/tests/test_sources_authority_tiers.py` | `test_gov_suffix_primary_authoritative` | AC-07 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_gov_country_code_primary_authoritative` | §4.7 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_edu_suffix_primary_authoritative` | §4.7 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_wikipedia_reputable_secondary` | §4.7 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_medium_quora_substack_low_signal` (each LOW_SIGNAL seed domain) | §4.7 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_reddit_stays_general_not_low_signal` (BRD §15.3 Q3) | §15.3 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_unknown_domain_general_fallback` | §4.7 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_url_with_path_and_query_extracts_host_only` | §4.7 | NEW |
| `backend/tests/test_sources_authority_tiers.py` | `test_www_prefix_stripped` | §4.7 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_primary_authoritative_row_contributes_1_05x_to_c_coverage` | AC-07 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_general_row_contributes_0_90x_to_c_coverage` | AC-07 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_low_signal_rows_clamp_c_independence_at_or_below_0_50` | AC-08 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_c_coverage_clamped_to_1_0_after_multiplier` | AC-07 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_c_agreement_untouched_by_authority_multiplier` (orthogonality vs BRD-22 expert boost) | §11 row 5 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_final_confidence_equals_min_s_effective_j_after_authority` | AC-07, RF-12 | NEW |
| `backend/tests/test_confidence_authority_multiplier.py` | `test_authority_tier_missing_defaults_to_general_on_replay` | AC-09 | NEW |
| `backend/tests/test_domain_events.py` (existing) | `test_evidence_added_event_accepts_authority_tier` | schema-compat | MODIFIED |
| `backend/tests/test_domain_enums.py` (existing) | `test_authority_tier_enum_values` | §4.4 | MODIFIED |
| `frontend/src/components/atoms/AuthorityTierChip.test.tsx` | 4 variants render, aria-label correct, jest-axe clean | §4.10 | NEW |

Coverage gate: `pytest --cov=app.agent.sources_authority --cov=app.confidence.structural --cov-fail-under=80`. Frontend: `vitest --coverage` on the new atom ≥ 80 %.

#### 2.3.4 — Risks & mitigations specific to Phase 3

| Risk | Mitigation |
|---|---|
| Authority table biases against non-English / non-Western sources. *(BRD §11 row 4.)* | Initial table includes `who.int`, `nih.gov`, `iso.org`, `ietf.org`, `*.gov.<cc>`, `*.ac.<cc>`. The `GENERAL` fallback never penalises hard (0.90, not 0.50). Expansion is a code-only PR (no migration). |
| Authority multiplier silently breaks BRD-22 expert boost composition. *(BRD §11 row 5.)* | WP-3 multiplier hits `C_coverage` / `C_independence` only; BRD-22's expert multiplier hits `C_agreement`. The two are orthogonal by construction. `test_c_agreement_untouched_by_authority_multiplier` enforces this. |
| Doc / code divergence on `confidence-calculation.md`. *(BRD §11 row 9; §15.3 Q6.)* | T-23-3-10 is a **hard gate** — Phase 3 PR is rejected at review if the doc amendment is missing. |
| Per-row multiplier saturates against `[0, 1]` clamp on long evidence lists. | Boost above baseline is intentionally small (`1.05`, not `1.10`); penalty asymmetry (`0.50`) is the dominant lever. Clamp is applied per-component, not per-row. |

#### 2.3.5 — Rollback strategy

Revert T-23-3-07 + T-23-3-08 (component multipliers + thread) → `S_raw` reverts to pre-BRD-23 math; `EvidenceAddedEvent.authority_tier` becomes a label without effect. Revert T-23-3-10 (doc amendment) if confidence-formula change is rolled back — keep the doc and the math in lock-step. Revert T-23-3-11 + T-23-3-12 → FE loses the chip but does not crash. No DB migration to roll back.

---

### 2.4 Phase 4 — WP-2 Deep-fetch escalation

#### 2.4.1 — Goal & BRD anchors

**Goal.** When the judge flags a critical-path claim as `supported_but_shallow` AND the supporting snippet is below threshold AND the per-complexity budget allows, fetch the full page (via the new optional `Source.fetch_full(...)` method) and replace the evidence's `extracted_text` with the deeper content. Emit a `DeepFetchPerformedEvent` for trace UX. Re-enter the existing `Analyzing → Critiquing` loop — no new FSM state.

**Satisfies ACs:** AC-05 (deep-fetch triggers on shallow critical claim), AC-06 (trivial complexity emits zero deep fetches), AC-11 (deep-fetch failure is non-fatal), AC-09 (replay tolerance for the new event type).

**Schema additions introduced by this phase:**
- `EventType.DEEP_FETCH_PERFORMED = "DeepFetchPerformed"`.
- `DeepFetchPerformedEvent` (new event class, all fields per BRD §4.4).
- `Source.fetch_full(url: str, *, timeout: float = 10.0) -> SourceResult | None` (optional Protocol method, default `None` in `BaseSource`).

#### 2.4.2 — Task list

| # | Task | File(s) | Effort | Tag | BRD § |
|---|------|---------|--------|-----|-------|
| **T-23-4-01** | Add `EventType.DEEP_FETCH_PERFORMED = "DeepFetchPerformed"` to `app/domain/enums.py`. | `backend/app/domain/enums.py` | XS | [backend] | §4.4 |
| **T-23-4-02** | Add `DeepFetchPerformedEvent(BaseEvent)` to `app/domain/events.py` with the exact fields from BRD §4.4: `source_id: SourceType`, `url: str`, `triggered_by_claim_id: str`, `fetch_ms: int`, `content_length: int`, `success: bool`, `failure_reason: str \| None = None`. `model_config = ConfigDict(extra="allow")`. Add to the discriminated `Event` union. **Not forkable** — do not add to `FORKABLE_EVENTS`. | `backend/app/domain/events.py` | S | [backend] | §4.4 |
| **T-23-4-03** | Add settings to `app/config.py`: `deep_fetch_min_snippet_chars: int = 400`, `deep_fetch_top_k: int = 2`, `deep_fetch_timeout_s: float = 10.0`, `deep_fetch_max_per_run_trivial: int = 0`, `deep_fetch_max_per_run_standard: int = 2`, `deep_fetch_max_per_run_deep: int = 3` (env vars per BRD §8). | `backend/app/config.py` | XS | [backend] | §8 |
| **T-23-4-04** | Extend the `Source` Protocol in `app/seams/source.py` with `async def fetch_full(self, url: str, *, timeout: float = 10.0) -> SourceResult \| None: ...`. Add the default implementation `async def fetch_full(...) -> None: return None` in `BaseSource` (`app/sources/base.py`). **No new seam** — Architecture rule #1 preserved. Existing sources continue to satisfy the Protocol without changes. | `backend/app/seams/source.py`, `backend/app/sources/base.py` | S | [backend] | §4.6 |
| **T-23-4-05** | Implement `TavilySource.fetch_full(url, *, timeout)` using `AsyncTavilyClient.extract(urls=[url])`. Truncate `content` to `DEFAULT_MAX_CONTENT_CHARS * 4 = 20000`. On timeout / API error, return `None` (and let the caller emit `success=false, failure_reason=...`). | `backend/app/sources/tavily.py` | M | [backend] | §4.6 |
| **T-23-4-06** | Implement `WikipediaSource.fetch_full(url, *, timeout)` using the existing full-article `extract` endpoint. No second API call — same client. Truncate to the same cap. | `backend/app/sources/wikipedia.py` | S | [backend] | §4.6 |
| **T-23-4-07** | Extend `JUDGE_SYSTEM_PROMPT` (`app/llm/prompts.py`) with the §4.5 / §4.6 `supported_but_shallow` flag instruction (already partly added in Phase 2 T-23-2-11; verify the WP-2 wording is present). Extend `JudgeResponse` Pydantic model (`app/llm/models.py`) with optional `supported_but_shallow_claim_ids: list[str] \| None = None`. Language: **English** (per `/memories/language-policy.md`). | `backend/app/llm/prompts.py`, `backend/app/llm/models.py` | S | [backend] | §4.5, §4.6 |
| **T-23-4-08** | Create new module `backend/app/agent/tasks/deep_fetch.py` exposing `async def maybe_deep_fetch(state: RunState, judge_response: JudgeResponse, *, registry: SourceRegistry) -> list[DeepFetchPerformedEvent]`. Implements the §4.6 pseudo-code: iterate `judge.supported_but_shallow_claim_ids ∩ state.plan.critical_path_claim_ids`, check `snippet_length < settings.deep_fetch_min_snippet_chars`, check `deep_fetch_remaining[complexity] > 0`, then call `fetch_full` for up to `settings.deep_fetch_top_k` evidence rows per claim. Each call wrapped in `asyncio.wait_for(..., timeout=settings.deep_fetch_timeout_s)` — `TimeoutError` ⇒ `success=false, failure_reason="timeout"`. Each call emits one `DeepFetchPerformedEvent`. Replaces `evidence.extracted_text` in-place when `result is not None`. Pure orchestration, never raises. | `backend/app/agent/tasks/deep_fetch.py` (NEW) | L | [backend] | §4.6 |
| **T-23-4-09** | Add helper `_deep_fetch_budget(complexity_hint: ComplexityHint \| None) -> int` to `deep_fetch.py` returning `0 / 2 / 3` for `trivial / standard / deep`; `None` defaults to `standard` budget (= 2). | `backend/app/agent/tasks/deep_fetch.py` | XS | [backend] | §4.6 |
| **T-23-4-10** | Add helper `_count_deep_fetches(events: list[Event]) -> int` to `deep_fetch.py` — recomputes the per-run counter from `EventType.DEEP_FETCH_PERFORMED` events. **No new `RunState` field carries the counter** (L-015 rule: deep-fetch counter is derived from the event log; see BRD §4.6 last paragraph). | `backend/app/agent/tasks/deep_fetch.py` | XS | [backend] | §4.6, L-015 |
| **T-23-4-11** | Wire `maybe_deep_fetch` into `AgentOrchestrator._handle_analyzing` (or `_handle_critiquing` — whichever path emits `JudgeRuledEvent` with `passed == false`). The call sequence per BRD §4.6: judge ruled `passed=false` AND `judge_response.supported_but_shallow_claim_ids` non-empty ⇒ `await maybe_deep_fetch(...)` ⇒ emit each returned `DeepFetchPerformedEvent` ⇒ if at least one `success=true` event was emitted, transition back to `ANALYZING` to re-run `calculate_structural_confidence` and re-emit the judge. **Cancellation check at the top of every loop iteration** (RF-08). | `backend/app/agent/orchestrator.py` | M | [backend] | §4.6 |
| **T-23-4-12** | Update `runner.py::_fold_events` to recognise `DeepFetchPerformedEvent` — informational only; do NOT mutate canonical state fields. (The fold *may* update `state.evidence[i].extracted_text` if a `success=true` event references that row, so that resume + replay restore the deeper text.) | `backend/app/agent/runner.py` | S | [backend] | RF-03, §4.6 |
| **T-23-4-13** | Create molecule `DeepFetchEntry.tsx` (props `event: DeepFetchPerformedEvent`). Renders `"Fetched full page for «{title}» ({fetch_ms} ms, {content_length} chars)"` on success; `"Deep-fetch failed: {failure_reason}"` on failure. `title` derived from `url` host (fallback to `url` itself). Co-locate `.test.tsx`. | `frontend/src/components/molecules/DeepFetchEntry.tsx`, `.test.tsx` | M | [frontend] | §4.10 |
| **T-23-4-14** | Extend `EventNode.tsx` (the atom/molecule that renders trace rows in `TraceTimeline`) to dispatch `DeepFetchPerformed` events to `<DeepFetchEntry>`. Icon `Download` from `lucide-react`. Update `EventNode.test.tsx`. | `frontend/src/components/molecules/EventNode.tsx`, `.test.tsx` | S | [frontend] | §4.10, §4.11 |
| **T-23-4-15** | Register the new event type in `frontend/src/lib/eventLabels.ts` (the label map used by `TraceTimeline` / `EventNode`). Add the microcopy from §3 below. | `frontend/src/lib/eventLabels.ts` | XS | [frontend] | §4.10 |
| **T-23-4-16** | Regenerate `frontend/src/types/events.ts` via `python scripts/export_types.py`. Verify `DeepFetchPerformedEvent` + `EventType.DEEP_FETCH_PERFORMED` appear. | `frontend/src/types/events.ts` | XS | [types] | §4.1 |

#### 2.4.3 — Test plan

| Test file | Test name | Verifies AC | New / Modified |
|---|---|---|---|
| `backend/tests/test_deep_fetch_trigger.py` | `test_triggers_on_supported_but_shallow_claim_with_short_snippet` | AC-05 | NEW |
| `backend/tests/test_deep_fetch_trigger.py` | `test_does_not_trigger_when_snippet_above_threshold` | AC-05 | NEW |
| `backend/tests/test_deep_fetch_trigger.py` | `test_does_not_trigger_when_claim_not_critical_path` | §4.6 | NEW |
| `backend/tests/test_deep_fetch_trigger.py` | `test_triggers_top_k_evidence_rows_per_claim` | §4.6 | NEW |
| `backend/tests/test_deep_fetch_trigger.py` | `test_re_enters_analyzing_after_at_least_one_success` | §4.6 | NEW |
| `backend/tests/test_deep_fetch_trigger.py` | `test_cancellation_during_deep_fetch_loop_emits_user_cancelled` (RF-08) | RF-08 | NEW |
| `backend/tests/test_deep_fetch_budget.py` | `test_trivial_complexity_emits_zero_deep_fetches` | AC-06 | NEW |
| `backend/tests/test_deep_fetch_budget.py` | `test_standard_complexity_caps_at_2_deep_fetches` | AC-05 | NEW |
| `backend/tests/test_deep_fetch_budget.py` | `test_deep_complexity_caps_at_3_deep_fetches` | §4.6 | NEW |
| `backend/tests/test_deep_fetch_budget.py` | `test_counter_recomputed_from_event_log_on_resume` (L-015) | RF-03 | NEW |
| `backend/tests/test_deep_fetch_budget.py` | `test_failure_is_non_fatal_run_does_not_error` | AC-11 | NEW |
| `backend/tests/test_tavily_fetch_full.py` | `test_returns_source_result_with_extracted_markdown_on_success` | §4.6 | NEW |
| `backend/tests/test_tavily_fetch_full.py` | `test_returns_none_on_timeout` | AC-11 | NEW |
| `backend/tests/test_tavily_fetch_full.py` | `test_truncates_content_at_20000_chars` | §4.6 | NEW |
| `backend/tests/test_wikipedia_fetch_full.py` | `test_returns_source_result_with_full_article_extract` | §4.6 | NEW |
| `backend/tests/test_wikipedia_fetch_full.py` | `test_returns_none_on_unknown_page` | AC-11 | NEW |
| `backend/tests/test_domain_events.py` (existing) | `test_deep_fetch_performed_event_round_trip` (discriminator) | AC-09, §9 | MODIFIED |
| `backend/tests/test_domain_enums.py` (existing) | `test_event_type_deep_fetch_performed_value` | §4.4 | MODIFIED |
| `backend/tests/test_agent_runner.py` (existing) | `test_pre_brd23_trace_replays_cleanly` (AC-09 fixture under `tests/fixtures/runs/`) | AC-09 | MODIFIED |
| `frontend/src/components/molecules/DeepFetchEntry.test.tsx` | success / failure render cases, aria-label correct, jest-axe clean | §4.10 | NEW |
| `frontend/src/components/molecules/EventNode.test.tsx` (existing) | `DeepFetchPerformed` branch renders | §4.10 | MODIFIED |

Coverage gate: `pytest --cov=app.agent.tasks.deep_fetch --cov=app.sources.tavily --cov=app.sources.wikipedia --cov=app.seams.source --cov-fail-under=80`. Frontend: `vitest --coverage` on the new molecule ≥ 80 %.

#### 2.4.4 — Risks & mitigations specific to Phase 4

| Risk | Mitigation |
|---|---|
| Deep-fetch latency budget exceeded on `deep` complexity (3 × 10 s = 30 s added). *(BRD §11 row 2.)* | Cap reduced from 5 → 3 (BRD §15.3 Q4 resolved); each call bounded by `DEEP_FETCH_TIMEOUT_S=10`; trigger fires only after judge flagged a critical-path claim, so cost is paid only when it can move `passed` from false to true. |
| Tavily `extract` rate-limit hit on free tier. *(BRD §11 row 3.)* | `DEEP_FETCH_TOP_K=2` caps per-claim escalations; AC-11 makes failure non-fatal (test `test_failure_is_non_fatal_run_does_not_error`). |
| `Source.fetch_full` default `None` lets a future source silently disable deep-fetch. *(BRD §11 row 8.)* | Telemetry: orchestrator emits `DeepFetchPerformedEvent(success=false, failure_reason="not_supported")` when `fetch_full` returns `None`; trace UI surfaces the missed escalation. |
| Counter drifts on replay if persisted on `RunState`. | T-23-4-10 enforces "recompute from event log" per L-015; no `RunState` field carries the counter. `test_counter_recomputed_from_event_log_on_resume` enforces this. |
| Cancellation arrives mid-`fetch_full` and the call doesn't return. | `asyncio.wait_for(..., timeout=settings.deep_fetch_timeout_s)` bounds every call; explicit cancel check before every iteration in T-23-4-11 (RF-08 preservation, mirrors IP-22 §AD-04 pattern). |

#### 2.4.5 — Rollback strategy

Revert T-23-4-11 (orchestrator wiring) → deep-fetch never triggers; new event type and Protocol method become dormant additive surface. Revert T-23-4-08 + T-23-4-05 + T-23-4-06 → `fetch_full` reverts to the `BaseSource` default (`None`), Protocol still satisfied. Revert T-23-4-02 → event class removed; `extra="allow"` keeps any persisted historical event round-trippable as a generic dict. Revert T-23-4-13..T-23-4-15 → FE drops the row but does not crash (`TraceTimeline` already tolerates unknown event types via a default render branch). No DB migration to roll back.

---

## 3. Cross-cutting tasks

### 3.1 Type-contract regeneration (one run per phase, mandatory before FE work)

After each phase's last backend task, run:

```powershell
cd C:\Users\HarolGiovannyManchol\source\repos\novum
.\backend\.venv\Scripts\Activate.ps1
python scripts/export_types.py
git diff --exit-code frontend/src/types/events.ts   # must be 0 after commit
```

This is a **hard gate** before any frontend task in the same phase starts. The CI pre-commit hook already enforces it; surface a clear failure message when the diff is non-zero.

### 3.2 Microcopy strings (English, exact match required)

These are the **only** strings any frontend task in this IP may use. Hard-coded fallback strings in code must match verbatim (per `/memories/language-policy.md`):

| Surface | String (exact, English) | Phase |
|---|---|---|
| `TemporalSensitivityBadge` — `static` | `Static fact` | Phase 2 |
| `TemporalSensitivityBadge` — `slow_changing` | `Slow-changing` | Phase 2 |
| `TemporalSensitivityBadge` — `volatile` | `Volatile topic` | Phase 2 |
| `TemporalSensitivityBadge` — `realtime` | `Real-time` | Phase 2 |
| `TemporalSensitivityBadge` — `aria-label` template | `Temporal sensitivity: {label}` | Phase 2 |
| `AuthorityTierChip` — `primary_authoritative` | `Primary` | Phase 3 |
| `AuthorityTierChip` — `reputable_secondary` | `Reputable` | Phase 3 |
| `AuthorityTierChip` — `general` | `General` | Phase 3 |
| `AuthorityTierChip` — `low_signal` | `Low signal` | Phase 3 |
| `AuthorityTierChip` — `aria-label` template | `Source authority: {label}` | Phase 3 |
| `DeepFetchEntry` — success | `Fetched full page for «{title}» ({fetch_ms} ms, {content_length} chars)` | Phase 4 |
| `DeepFetchEntry` — failure | `Deep-fetch failed: {failure_reason}` | Phase 4 |
| `DeepFetchEntry` — event timeline label | `Deep fetch performed` | Phase 4 |
| `eventLabels.ts` — `DeepFetchPerformed` short label | `Deep fetch` | Phase 4 |

The runtime user-facing chat reply remains in Spanish via the existing system-prompt rule — **none of these strings are user-facing chat output**; they are trust-surface labels rendered by the React UI, which is English by project decision.

### 3.3 Documentation PR — `confidence-calculation.md` (HARD GATE for Phase 3)

Per BRD §15.3 Q6, the amendment to `docs/understanding-phase/confidence-calculation.md` **must ship in the same PR as the Phase 3 code**. This is enforced by T-23-3-10. The reviewer is instructed (in Phase 3's DoD) to reject the PR if the doc is missing the per-evidence-row multiplier subsection.

---

## 4. Phase ordering / Gantt-style sequence

```
Phase 1 (WP-4)  ──────────────►  baseline: query_length_tokens on every ToolCalledEvent
   │
   ▼
Phase 2 (WP-1)  ──────────────►  TemporalSensitivity + Tavily days + kind_ceiling penalty
   │                              (depends on Phase 1's tavily_days_filter event field)
   ▼
Phase 3 (WP-3)  ──────────────►  AuthorityTier multiplier on C_coverage / C_independence
   │                              + confidence-calculation.md amendment (same PR)
   │                              (cross-references Phase 2 for AC-04 stale-citation context)
   ▼
Phase 4 (WP-2)  ──────────────►  Source.fetch_full + DeepFetchPerformedEvent + budget
                                  (benefits from Phase 2 + Phase 3 signals already live in trace UI)
```

Each phase ends in a green pytest run + a successful smoke matrix on `scripts/smoke_ip21.py` Q1 (BRD-22 trivial-path regression guard). Phases 1 and 2 may be parallelised across two PRs *only if* T-23-1-01 (the joint `ToolCalledEvent` field addition) is sequenced first.

---

## 5. Definition of Done

### 5.1 Per-phase DoD (applied independently)

For each Phase N ∈ {1, 2, 3, 4}:

- [ ] All Phase N tasks completed (file edits, prompts, types, FE components).
- [ ] `pytest backend/tests` — all Phase N tests green (see §2.N.3 test plan).
- [ ] Coverage ≥ 80 % on every new module and every modified module in Phase N (`--cov-fail-under=80`).
- [ ] `ruff check backend` clean; `pyright backend` clean.
- [ ] `vitest run` in `frontend/` — all Phase N tests green.
- [ ] `python scripts/export_types.py` produces zero diff after commit.
- [ ] BRD-23 AC verification table marked for ACs in Phase N's §2.N.1 list.
- [ ] **No regression on the BRD-22 smoke matrix.** `python scripts/smoke_ip21.py` Q1 still ≤ 90 s wall-clock (AC-02 regression guard).
- [ ] **(Phase 3 only.)** `docs/understanding-phase/confidence-calculation.md` includes the per-evidence-row authority-tier subsection (BRD §15.3 Q6 hard gate).

### 5.2 Overall DoD (applied at the end of Phase 4)

- [ ] All 11 BRD-23 ACs (AC-01 … AC-11) have at least one mapped, green test from §2.*.3.
- [ ] `pytest backend/tests` — full suite green.
- [ ] `vitest run` in `frontend/` — full suite green (modulo pre-existing failures not introduced by IP-23).
- [ ] `python scripts/smoke_ip21.py` (or `make eval` if it lands first) reports:
  - Residual-contradiction rate **down 30 %** vs. pre-BRD-23 baseline (BRD §10.1 row 1).
  - Mean queries per run on trivial complexity **unchanged** vs. BRD-22 baseline (BRD §10.1 row 2).
  - Mean snippet length on `supported_but_shallow` flagged claims **≥ 2×** after deep-fetch (BRD §10.1 row 3).
  - Ratio of `low_signal` citations in final answers **≤ 5 %** (BRD §10.1 row 4).
- [ ] Memory bank updated (see §7).
- [ ] Reviewer score ≥ 9/10 (F4 gate) for the final PR (or for each phase PR if phases ship separately).

---

## 6. Out of scope reminder (echoed verbatim from BRD §12)

> - **No new plugin seam.** `Source.fetch_full` extends the existing seam; no `DeepFetcher` interface, no `AuthorityTier` plugin, no `TemporalClassifier` plugin.
> - **No persistence of the authority table to DB.** Code-only static dict; expansion is a PR.
> - **No automated learning of authority tiers** (would require an LLM call per domain or a dataset; out of V1 scope).
> - **No change to `kind_ceiling` values for `weighted`, `scenario`, `tradeoff`, `best_effort`, `ethical_redirect`.** WP-1 only tweaks `direct`.
> - **No change to `C_agreement` or `C_no_conflict` formulas.** WP-3 modulates `C_coverage` and `C_independence` only.
> - **No change to the 4-value `stop_reason` enum.** The amendment-of-2026-05-27 invariant holds.
> - **No change to the FSM.** No new states, no new transitions.
> - **No new LLM provider.** Judge stays on Anthropic Haiku per RF-19; planner / synthesizer / classifier stay on GitHub Models.
> - **No new infra.** Single-server scope preserved (RF-05); no Redis, no vector DB, no queue.
> - **Per-domain authority overrides per user / per workspace.** Out of V1.
> - **Real-time scraping fallback when Tavily `extract` fails.** Out of V1; AC-11 already covers the failure path.

Coder MUST refuse any task in this IP that contradicts the above list, even when "convenient".

---

## 7. Memory bank touchpoints

After each phase ships (per Memory Protocol §7.4 in `.github/copilot-instructions.md`):

| File | Update | Trigger |
|---|---|---|
| `.github/memory-bank/logs/decisions-history.md` | Append `D-IP23-PHASE<N>-IMPL` decision record per phase summarizing autonomous decisions, AC coverage, files touched, and invariant-preservation evidence. | After each phase merges |
| `.github/memory-bank/logs/lessons-learned.md` | Add lessons only when a non-obvious decision was forced. Candidates: (a) heuristic-vs-LLM trade-off for temporal classification (Phase 2); (b) asymmetric multiplier shape `1.05 / 0.50` to avoid clamp saturation (Phase 3); (c) "recompute counter from event log" pattern reused (Phase 4 — likely already covered by L-015, add only if a new wrinkle appears). | Post-review (F4) |
| `.github/memory-bank/indices/knowledge-base-index.md` | (a) Add an `IP-23` row to the Implementation Plans table with status `Draft` initially, flipped to `Implemented` after Phase 4 merges. (b) Add a `BRD-23` row update flipping status from `Draft (F1)` to `Implemented`. (c) Register the new event type `DeepFetchPerformed` and the new enums `TemporalSensitivity`, `AuthorityTier`. | At plan creation (this commit) for IP-23 row; after each phase for the rest |

The `D-IP23-PLAN-CREATED` decision record + the initial `IP-23` index row are committed alongside this file (see §7 of the Orchestrator response message).

---

## 8. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | Orchestrator Agent | Initial plan (F2 iter 1) drafted from BRD-23 v1.1. Phase ordering overridden vs. BRD §13 suggestion: WP-4 → WP-1 → WP-3 → WP-2 (rationale in §1). |
