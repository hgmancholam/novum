# Audit Report — IP-23 (F2 sub-loop, iter 1)

**Artifact under audit:** [IP-23 — Research-Quality Improvements](../implementation-plans/IP-23-research-quality-improvements.md)
**Plan version:** 1.0 (2026-05-27)
**Parent BRD:** [BRD-23 v1.1](../brds/BRD-23-research-quality-improvements.md)
**Sub-loop:** F2 (PLAN) — Auditor of Implementation Plan
**Iteration:** 1
**Complexity profile:** L (`quality_profiles.L` → `min_score = 9`, `max_iter = 3`)
**Date:** 2026-05-27
**Auditor:** Auditor Agent

---

## 1. Per-dimension scores

| # | Dimension | Score | Weight | Weighted |
|---|---|---:|---:|---:|
| 1 | Completeness (AC + Schema mapping) | 9.5 | 15% | 1.425 |
| 2 | Atomicity (file-anchored, testable) | 9.5 | 10% | 0.950 |
| 3 | Sequencing (phase order, deps) | 10.0 | 10% | 1.000 |
| 4 | Test coverage plan (per-AC + ≥ 80 %) | 10.0 | 10% | 1.000 |
| 5 | Blind-path detection | 9.0 | 25% | 2.250 |
| 6 | Rollback feasibility | 10.0 | 10% | 1.000 |
| 7 | Schema-compatibility (T \| None) | 10.0 | 10% | 1.000 |
| 8 | Memory protocol touchpoints | 10.0 | 10% | 1.000 |
| | **Weighted total (informational)** | | | **9.625** |
| | **Final = `min(dimension_scores)`** | | | **9.0** |

> Per user instruction the verdict is gated by `min()`, not by the weighted sum. Final = **9.0/10**.

---

## 2. Evidence per dimension

### D1 — Completeness — **9.5 / 10**

- All 11 BRD-23 ACs are mapped to ≥ 1 task in §2.*.3 test plan:
  - AC-01 → T-23-2-04/07/08 + `test_plan_temporal_routing.py::test_volatile_routes_tavily_first_with_180_day_filter`.
  - AC-02 → T-23-2-04 + `test_static_when_factual_no_marker`, `test_static_keeps_no_days_filter_and_brd22_trivial_path_preserved`.
  - AC-03 → T-23-2-07/08 + `test_realtime_excludes_wikipedia_evidence_and_sets_7_day_filter`.
  - AC-04 → T-23-2-12/13 + `test_direct_kind_ceiling_lowered_when_majority_stale_on_volatile`, `test_min_s_effective_j_invariant_holds_after_penalty`.
  - AC-05 → T-23-4-08/11 + `test_triggers_on_supported_but_shallow_claim_with_short_snippet`.
  - AC-06 → T-23-4-03/09 + `test_trivial_complexity_emits_zero_deep_fetches`.
  - AC-07 → T-23-3-05/07/08 + `test_primary_authoritative_row_contributes_1_05x_to_c_coverage`, `test_final_confidence_equals_min_s_effective_j_after_authority`.
  - AC-08 → T-23-3-07 + `test_low_signal_rows_clamp_c_independence_at_or_below_0_50`.
  - AC-09 → T-23-1-04, T-23-2-14, T-23-3-09, T-23-4-12 + `test_pre_brd23_trace_replays_cleanly` and the three per-event `test_..._accepts_..._field` modified tests.
  - AC-10 → T-23-1-02/03 + `test_planner_system_prompt_contains_*` (4 cases) + `test_query_length_tokens_set_on_every_tool_called_event`.
  - AC-11 → T-23-4-05/08 + `test_returns_none_on_timeout`, `test_failure_is_non_fatal_run_does_not_error`.
- BRD-23 §9 Schema Compatibility entries: every new optional field + `DeepFetchPerformedEvent` + `Source.fetch_full` is mapped to an explicit task (T-23-1-01, T-23-2-02, T-23-3-02, T-23-4-02/04).
- **Minor gap (−0.5):** AC-09 references a "pre-BRD-23 JSONL fixture" but the only on-disk artefact at `backend/tests/fixtures/runs/` today is `.gitkeep`. IP-23 marks `test_agent_runner.py::test_pre_brd23_trace_replays_cleanly` as **MODIFIED**, never as **NEW (fixture)**. The fixture file itself is not enumerated as a deliverable.

### D2 — Atomicity — **9.5 / 10**

- All tasks are file-anchored (every row of §2.N.2 names a path), tagged `[backend|frontend|types|doc|test]`, and sized XS / S / M / L.
- The single L-sized task is **T-23-4-08** (`deep_fetch.py` orchestrator). Its body is described as ≤ ~100 LOC with explicit pseudo-code reproduced from BRD §4.6 — acceptable for L tier.
- Two helper tasks (T-23-4-09 `_deep_fetch_budget`, T-23-4-10 `_count_deep_fetches`) are correctly split out as XS tasks alongside the L module.
- **Minor (−0.5):** T-23-3-07 says *"modify `calculate_coverage(...)` and `calculate_independence(...)` (or whatever their actual names are — verify with grep)"*. The real symbol in `backend/app/confidence/structural.py` is **`calculate_diversity`** (verified: line 86), not `calculate_independence`. The plan acknowledges the uncertainty with a grep instruction, so atomicity is preserved but the naming is loose.

### D3 — Sequencing — **10.0 / 10**

- Phase order (WP-4 → WP-1 → WP-3 → WP-2) overrides BRD §13 and the override is justified in §1 with four numbered reasons that hold under inspection.
- T-23-1-01 deliberately introduces **two** optional fields (`query_length_tokens`, `tavily_days_filter`) so Phase 2 is purely behavioural — matches PO confirmation #5.
- T-23-2-11 (judge stale-citation paragraph) and T-23-4-07 (judge `supported_but_shallow_claim_ids` field) are sequenced one per phase but converge on the same `JUDGE_SYSTEM_PROMPT` — T-23-4-07 explicitly says *"verify the WP-2 wording is present"*, preventing accidental overwrite.
- Cross-phase dependencies (Phase 3 reads `temporal_sensitivity` from Phase 2; Phase 4 reads `tavily_days_filter` already in `ToolCalledEvent` from Phase 1) are explicit and feasible.

### D4 — Test coverage plan — **10.0 / 10**

- Every AC has at least one named test function (table above).
- Each phase declares an explicit pytest coverage gate (`--cov-fail-under=80`) on the touched modules (§2.N.3 last line of each test plan).
- Frontend `vitest --coverage ≥ 80 %` declared per new atom/molecule.
- A11y (`jest-axe`) and ARIA-label assertions are required for the three new visual surfaces (`TemporalSensitivityBadge`, `AuthorityTierChip`, `DeepFetchEntry`).
- Schema-compat tests are MODIFIED (not added wholesale) on the existing `test_domain_events.py` / `test_domain_enums.py`, which preserves the BRD-22 test surface.

### D5 — Blind-path detection — **9.0 / 10**

- **Schema-evolution (Arq #5):** every new event field is `T | None = None` (§4.4 BRD reproduced in T-23-1-01, T-23-2-02, T-23-3-02, T-23-4-02). `extra="allow"` is preserved. ✅
- **L-015 fold strategy:** T-23-4-10 explicitly forbids a `RunState` counter and recomputes deep-fetch usage from the event log; `test_counter_recomputed_from_event_log_on_resume` enforces it. ✅
- **`final_confidence = min(S, J)` (RF-12):** T-23-2-12 (kind-ceiling) and T-23-3-07 (per-component multiplier with `[0, 1]` clamp) act only on `S` inputs; `test_min_s_effective_j_invariant_holds_after_penalty` and `test_final_confidence_equals_min_s_effective_j_after_authority` directly enforce the invariant. ✅
- **Cancellation (RF-08):** T-23-4-11 mandates *"Cancellation check at the top of every loop iteration"*; `test_cancellation_during_deep_fetch_loop_emits_user_cancelled` enforces it. ✅
- **Budget cap (RF-01·F):** §4.3 declares `deep_fetch_max_per_run_{trivial,standard,deep} = 0/2/3`; tests `test_trivial_complexity_emits_zero_deep_fetches`, `test_standard_complexity_caps_at_2_deep_fetches`, `test_deep_complexity_caps_at_3_deep_fetches` enforce it. ✅
- **Error handling:** AC-11 + T-23-4-08 (`asyncio.wait_for` + `TimeoutError ⇒ success=false`) + `test_failure_is_non_fatal_run_does_not_error`. ✅
- **Authority orthogonality** vs. BRD-22 expert boost: `test_c_agreement_untouched_by_authority_multiplier` explicitly enforces the non-interference promised in §11 row 5. ✅
- **Minor (−0.5):** T-23-4-11 says *"Wire `maybe_deep_fetch` into `AgentOrchestrator._handle_analyzing` (or `_handle_critiquing` — whichever path emits `JudgeRuledEvent` with `passed == false`)"*. In the current code (verified: `backend/app/agent/orchestrator.py:260`), `_handle_critiquing` is the **plan-critique** state (`critique_plan(state.question, state.sub_claims)`), not a post-judge state. The exact hook for `JudgeRuledEvent` is not specified; the Coder is asked to discover it. Not a blind path (trigger condition is well-defined) but a sourcing ambiguity that increases the chance of an iter F4 ping-back.
- **Minor (−0.5):** IP-23 §6 "Implementation Checklist" line *"Deep-fetch fold contract — `backend/app/agent/run_state.py::_fold_events`"* is internally inconsistent with T-23-4-12 (which correctly says `backend/app/agent/runner.py`). Verified: `_fold_events` is defined at `backend/app/agent/runner.py:100`, not in `run_state.py`. The checklist echoes the BRD wording rather than the corrected task list.

### D6 — Rollback feasibility — **10.0 / 10**

- Each phase has a §2.N.5 "Rollback strategy" subsection that reverts task-by-task; no DB migration to roll back (BRD §4.2 / §4.3).
- `extra="allow"` guarantees that persisted events with the removed fields still round-trip after a revert.
- Phase 3 rollback explicitly couples doc revert with code revert (keeps `confidence-calculation.md` in lock-step) — matches BRD §15.3 Q6 hard gate.

### D7 — Schema-compatibility — **10.0 / 10**

- Six new optional fields, all `T | None = None` (verified against BRD §9 table); one new event `DeepFetchPerformedEvent` with `model_config = ConfigDict(extra="allow")` and explicitly **not** added to `FORKABLE_EVENTS` (T-23-4-02).
- `Source.fetch_full` default returns `None` in `BaseSource` so every existing source continues to satisfy the Protocol without changes (T-23-4-04). Architecture rule #1 (no new seam) preserved.
- Pre-BRD-23 replay tolerance is asserted via AC-09 fixture (subject to the D1 minor about the JSONL file).

### D8 — Memory-protocol touchpoints — **10.0 / 10**

- §7 enumerates the three required files (`decisions-history.md`, `lessons-learned.md`, `knowledge-base-index.md`) with the trigger and the content to record.
- Three candidate lessons-learned anchors are pre-identified (heuristic-vs-LLM trade-off, asymmetric `1.05 / 0.50`, L-015 reuse) — good discipline for the Coder.

---

## 3. PO confirmations — feasibility check against the codebase

| # | PO confirmation | Verified in repo | Reflected in IP-23 |
|---|---|---|---|
| 1 | Prompts live in `backend/app/llm/prompts.py` (single file) | ✅ `backend/app/llm/prompts.py` lines 16/44/76/97 hold `CLASSIFIER/PLANNER/SYNTHESIZER/JUDGE_SYSTEM_PROMPT` | ✅ T-23-1-02, T-23-2-06/11, T-23-4-07 all target `app/llm/prompts.py` |
| 2 | `EvidenceAddedEvent` / `ToolCalledEvent` emission site assumed in `app/agent/tasks/search.py` | ✅ verified single emission site at `backend/app/agent/tasks/search.py:46` (`ToolCalledEvent(...)`) and `:74` (`EvidenceAddedEvent(...)`); no other constructor calls in `backend/app` | ✅ T-23-1-03 (grep + factor helper if > 1); T-23-2-08/10 + T-23-3-06 target the same file |
| 3 | `TemporalSensitivityBadge` next to `ComplexityBadge` in `molecules/PlanPreview.tsx` | ✅ `frontend/src/components/molecules/PlanPreview.tsx:13,59` already imports + renders `ComplexityBadge` | ⚠️ T-23-2-15 places the new badge in **`atoms/`** while `ComplexityBadge` itself lives in `molecules/`. Atomic-design layering inconsistency, not blocking, but worth aligning during F3. |
| 4 | Authority chip in `organisms/SourcesCard.tsx` | ✅ `frontend/src/components/organisms/SourcesCard.tsx` exists | ⚠️ Same comment as #3: T-23-3-11 places `AuthorityTierChip.tsx` in **`atoms/`**; the wrapped `Badge` is the atom, so the chip is more accurately a molecule. |
| 5 | `tavily_days_filter` ships in WP-4 phase | n/a (plan-level decision) | ✅ T-23-1-01 bundles both fields in Phase 1; §2.1.1 explains the rationale |

The two atomic-design inconsistencies (#3, #4) are **not** scored as deductions here because the user's "Hard rules" forbid speculating on code behaviour; they are flagged as informational under §5 of this audit for the Orchestrator's awareness.

---

## 4. Verdict

**APPROVED** (final = 9.0 / 10, meets `quality_profiles.L.min_score = 9`).

The plan is complete, well-sequenced, schema-safe, rollback-aware, and faithful to BRD-23 v1.1 plus all five PO confirmations. The two minor blind-path deductions (D5) are sourcing/checklist nits that the Coder can resolve trivially during F3 via local grep — they do **not** constitute a blind path in the agent control flow.

---

## 5. Green-light items handed to F3 (Coder)

The Orchestrator may dispatch the following ordered phase queue:

1. **Phase 1 — WP-4 Query hygiene.** Tasks T-23-1-01 … T-23-1-04. Hard gate: `python scripts/export_types.py` exits 0; `pytest backend/tests/test_planner_query_hygiene.py backend/tests/test_tool_called_query_length.py` green.
2. **Phase 2 — WP-1 Temporal sensitivity.** Tasks T-23-2-01 … T-23-2-17. Hard gate: AC-01/02/03/04/09 tests green; BRD-22 trivial-path smoke (`scripts/smoke_ip21.py` Q1 ≤ 90 s) unchanged.
3. **Phase 3 — WP-3 Authority tiering.** Tasks T-23-3-01 … T-23-3-13. **Hard gate (BRD §15.3 Q6):** `docs/understanding-phase/confidence-calculation.md` amendment lands in the same PR (T-23-3-10).
4. **Phase 4 — WP-2 Deep-fetch.** Tasks T-23-4-01 … T-23-4-16. Hard gate: AC-05/06/11 tests green; `test_counter_recomputed_from_event_log_on_resume` green; cancellation test green.

**Coder advisories (non-blocking, please apply during F3):**

- A. Before T-23-3-07, grep `backend/app/confidence/structural.py` for the actual symbol — it is `calculate_diversity`, not `calculate_independence`. Apply the multiplier inside `calculate_coverage` and `calculate_diversity`; do **not** rename the function.
- B. Before T-23-4-11, grep `backend/app/agent/orchestrator.py` and `backend/app/agent/tasks/analyze.py` for the actual emission site of `JudgeRuledEvent`. The current `_handle_critiquing` is the **plan-critique** state and is not the post-judge re-entry point.
- C. Treat the §6 Implementation Checklist line *"Deep-fetch fold contract — `backend/app/agent/run_state.py::_fold_events`"* as a typo; the authoritative path is `backend/app/agent/runner.py::_fold_events` (matches T-23-4-12). Update IP-23 §6 in your impl PR if you want the doc to stay clean.
- D. AC-09 requires a pre-BRD-23 fixture under `backend/tests/fixtures/runs/`. The folder currently contains only `.gitkeep`. Create one minimal JSONL fixture as part of Phase 4 and reference it from `test_pre_brd23_trace_replays_cleanly`.
- E. The atomic-design layer for `TemporalSensitivityBadge` and `AuthorityTierChip` is more accurately **molecule** (each wraps the existing `Badge` atom, like `ComplexityBadge` does at `frontend/src/components/molecules/ComplexityBadge.tsx`). Move them to `molecules/` to keep the ESLint `import/no-restricted-paths` policy clean.

None of A–E is a Required Change. They are pre-validated hints to keep F3↔F4 iterations cheap.

---

## 6. Memory-protocol touchpoints to update during F3

(Already declared in IP-23 §7; reproduced here for the Orchestrator's convenience.)

- `.github/memory-bank/logs/decisions-history.md` — append `D-IP23-PHASE<N>-IMPL` after each phase merges.
- `.github/memory-bank/logs/lessons-learned.md` — record any non-obvious decision (candidates listed in IP-23 §7).
- `.github/memory-bank/indices/knowledge-base-index.md` — flip IP-23 status from `Draft (F2)` → `Implemented` after Phase 4 merges; register new event type `DeepFetchPerformed` and new enums `TemporalSensitivity`, `AuthorityTier`.

---

## 7. Iteration log

| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-27 | 9.0 | ✅ APPROVED |
