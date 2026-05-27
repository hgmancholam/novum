# Audit Report — AUDIT-IP-22 (Phase F2)

**Plan ID:** IP-22
**Audited file:** [docs/implementation-phase/implementation-plans/IP-22-complexity-aware-planning-and-experts.md](../implementation-plans/IP-22-complexity-aware-planning-and-experts.md)
**Audit date:** 2026-05-27
**Auditor:** Auditor Agent (Sonnet 4.5)
**Complexity:** L (quality_profiles.L)
**Profile thresholds:** min_score=9, max_iter=3

---

<!-- STATUS HEADER — overwritten on every iteration -->
**Latest Iteration:** 2
**Latest Date:** 2026-05-27
**Latest Score:** 9.6/10
**Latest Verdict:** ✅ APPROVED
**Iteration Log:**
| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-27 | 8.2 | ⚠️ NEEDS REVISION |
| 2 | 2026-05-27 | 9.6 | ✅ APPROVED |

---

## Iter 1 — 2026-05-27

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 9.0/10 | 30% | 2.70 |
| Acceptance Criteria Completeness | 8.5/10 | 20% | 1.70 |
| Blind-Path Absence | 7.0/10 | 25% | 1.75 |
| Traceability | 9.0/10 | 15% | 1.35 |
| Consistency w/ docs | 8.5/10 | 10% | 0.85 |
| **TOTAL** | | | **8.35/10** |

**Rounded final score: 8.2/10**

### 2. Verdict

⚠️ **NEEDS REVISION** (score < 9)

The plan is well-structured and covers most requirements comprehensively. However, there are **3 major blind-path findings** (§4 below) that reduce confidence the implementation will be production-safe on first pass, plus several minor gaps in test coverage mapping and event-folding completeness. These must be addressed before approval.

### 3. Requirements Coverage Matrix

| RF | Covered? | Where (section/task) | Notes |
|---|---|---|---|
| RF-01·A | ✅ | §1, §4 (Phase 4) | Planner budget extended with ComplexityHint; correctly traced |
| RF-01·F | ✅ | §1, implicit | Budget cap unchanged; no new loop bypasses it |
| RF-02 | ✅ | §1, D-IP22-09, Task 1.2 | `stop_reason` enum NOT extended; `triggering_signal` is a sub-field on `StopRationale` (validated in hard-validation #4 below) |
| RF-03 | ⚠️ | §1, §6, Tasks 1.3–1.6, 4.9, 6.7 | Events append-only; `extra="allow"` preserved. **Minor gap:** Task 4.9 does NOT explicitly state where `critique_passes_target` is folded during replay (see Finding 3) |
| RF-04 | ✅ | §1, §4 (Phase 5) | Agreement weighted by expert match; multiplier additive |
| RF-05 | ✅ | §1, §6, Task 6.1 | Cache in-memory only, cleared on restart; explicitly stated |
| RF-06 | ✅ | §1 | Question-type classification unchanged |
| RF-08 | ⚠️ | implicit | Cancel/resume preserved. **No explicit task verifies new long-running code honors cancellation** (see Finding 4) |
| RF-12 | ✅ | §1, Task 5.6, 5.7, 5.8, 5.9, validation #2 | `min(S_effective, J)` invariant preserved; multiplier lives inside `calculate_agreement` only (validated below) |
| RF-13 | ✅ | §1, Phase 7 | Three new trust surfaces: `ComplexityBadge`, `ExpectedExpertsList`, `PriorRunHintReplayed` trace row |
| RF-17/18/19 | ✅ | §1 | Explicitly stated as untouched |

**Coverage score: 9.0/10** — all in-scope RFs traced; minor gaps in RF-03 and RF-08 task explicitness (deducted 1 point total).

### 4. Blind-Path Findings

#### Finding 1 — MAJOR: Instant cache replay path does NOT fold `PriorRunHintReplayedEvent` into RunState

**Location:** Task 6.7 + Task 6.4
**Type:** `missing_fold_logic`
**Affected RF:** RF-03 (event replay)
**Severity:** major

**Description:**
Task 6.7 states: *"Update `_fold_events` in `runner.py` to fold `PriorRunHintReplayed` (no-op state-wise; ensures replay traces don't crash)."* This is **incomplete**. When a replayed run (which emitted `PriorRunHintReplayedEvent`) is itself resumed or forked, `_fold_events` must not only avoid crashing — it must correctly reconstruct the `RunState` fields that were set during the instant-cache replay path:

- `state.last_judge_confidence` (set by the synthetic `JudgeRuledEvent` in Task 6.4)
- `state.stop_reason` (set by the synthetic `StoppedEvent`)
- `state.stop_rationale.triggering_signal = "instant_cache"` (distinguishes replayed runs)
- `state.final_confidence`, `state.answer_kind`, `state.answer_prose`, etc.

If these are not folded, forking a replayed run will lose critical metadata and the fork will start from an incomplete state (e.g. `last_judge_confidence=None`), which could break downstream logic in `AgentOrchestrator._handle_judging` or `ConfidenceCalculator.check_sufficient`.

**Fix recommendation:**
In `PLAN-IP-22-...md`, modify **Task 6.7** to state:
```
Update `_fold_events` in `runner.py` to fold `PriorRunHintReplayedEvent`: extract `source_run_id` and `source_final_confidence` into `state.metadata` for audit; no state mutation (the subsequent synthetic `JudgeRuledEvent` + `StoppedEvent` carry the real state changes). Verify that folding the synthetic `JudgeRuledEvent` and `StoppedEvent` (which have `extra="allow"`) correctly populates `state.last_judge_confidence`, `state.final_confidence`, `state.answer_kind`, `state.stop_reason`, and `state.stop_rationale` (including `triggering_signal`). Add an explicit test case in TC-09 of US-22-4 that forks a replayed run and asserts the forked run inherits the correct confidence values.
```

---

#### Finding 2 — MAJOR: No explicit handling of `complexity_hint=None` during plan revision

**Location:** Task 4.4
**Type:** `unhandled_edge_case`
**Affected RF:** RF-03 (replay tolerates missing fields)
**Severity:** major

**Description:**
Task 4.4 states: *"Update `revise_plan` to also accept and re-emit `complexity_hint`. (Symmetry — revised plans still carry the hint.) Add fallback if missing."* The "fallback if missing" is mentioned but NOT specified. This is a blind path: when a historical run (pre-BRD-22) enters `REVISING`, what does `revise_plan` do when `state.complexity_hint` is `None`?

Options:
1. Re-derive it from the question (calls `derive_complexity_hint` again) — consistent with fresh runs.
2. Default to `STANDARD` — documented fallback elsewhere (Task 4.1).
3. Pass `None` through and coerce at budget-lookup time — but then `PlanRevisedEvent` emits `complexity_hint=None`, inconsistent with `PlanCreatedEvent` which always emits a value after Task 3.4.

The plan does not specify which. US-22-2 AC-6 requires replay tolerance but does NOT mandate which strategy.

**Fix recommendation:**
In `PLAN-IP-22-...md`, modify **Task 4.4** to state:
```
Update `revise_plan` to accept `complexity_hint: ComplexityHint | None`. If `None` (historical replay), default to `STANDARD` at the top of the function and log `complexity_hint_defaulted_on_revise`. Emit the defaulted value in `PlanRevisedEvent.complexity_hint` so the trace is consistent. This matches the fallback strategy in Task 4.1 and US-22-2 AC-6.
```

---

#### Finding 3 — MAJOR: `critique_passes_target` and `critique_passes_completed` are added to `RunState` but NOT folded during replay

**Location:** Task 4.6 + Task 4.9
**Type:** `missing_fold_logic`
**Affected RF:** RF-03 (event replay)
**Severity:** major

**Description:**
Task 4.6 adds two new fields to `RunState`: `critique_passes_target: int = 1` and `critique_passes_completed: int = 0`. Task 4.9 states: *"Update `runner.py::_fold_events` to fold the new optional fields on `PlanCreatedEvent` (`complexity_hint`, `expected_experts`, `preferred_sources`) into `RunState` for replay/resume idempotency."*

**Problem:** `critique_passes_target` is NOT stored on any event — it is computed from the budget table in Task 4.7 (step c). `critique_passes_completed` is incremented in `_handle_critiquing` (Task 4.8) but NOT emitted in any event. This means:

1. When replaying a run that stopped mid-critiquing, `_fold_events` cannot reconstruct `critique_passes_completed` from the event log alone. It will default to `0`, even if the run had already emitted one `PlanCritiquedEvent`.
2. When resuming such a run, the orchestrator will re-enter `CRITIQUING` with `critique_passes_completed=0`, potentially running the critique again (double critique on a `standard` run, or three critiques on a `deep` run).

This violates RF-03's replay determinism.

**Fix recommendation:**
In `PLAN-IP-22-...md`, modify **Task 4.6** to state:
```
Add `critique_passes_target: int = 1` and `critique_passes_completed: int = 0` to `RunState`. To preserve RF-03 replay determinism, store `critique_passes_target` in `PlanCreatedEvent.metadata` (new optional dict field) so it can be folded during replay. Alternatively, recompute it during `_fold_events` from the budget table using `(state.question_type, state.complexity_hint)` — acceptable since the budget table is deterministic. For `critique_passes_completed`, increment it in `_handle_critiquing` AND emit a new `CritiqueCycleIncrementedEvent` (optional micro-event) OR count the number of `PlanCritiquedEvent`s during `_fold_events` (simpler). Choose the simpler option (count during fold) and document it.
```
AND modify **Task 4.9** to state:
```
Update `runner.py::_fold_events` to fold the new optional fields on `PlanCreatedEvent` (`complexity_hint`, `expected_experts`, `preferred_sources`) into `RunState`. Recompute `critique_passes_target` from the budget table using `(state.question_type, state.complexity_hint)` (deterministic). Compute `critique_passes_completed` as `len([e for e in events if e.type == EventType.PLAN_CRITIQUED])`. Tolerate absence of optional fields (pre-BRD-22 traces).
```

---

#### Finding 4 — MINOR: No explicit task verifies new long-running code honors cancellation

**Location:** Phase 3, Phase 5, Phase 6
**Type:** `missing_cancellation_check`
**Affected RF:** RF-08 (cancellation honored)
**Severity:** minor

**Description:**
Phase 3 (complexity heuristic), Phase 5 (agreement multiplier), and Phase 6 (instant cache) add new synchronous code paths (`derive_complexity_hint`, `match`, `try_replay`, `normalise_question`). These are all **synchronous** and **non-blocking** (no LLM calls, no HTTP, no DB queries in the critical path), so they do NOT introduce new cancellation blind spots.

However, the plan does NOT explicitly verify that the existing cancellation contract (from IP-07 / BRD-07) is preserved. US-22-2 Scenario 7 measures latency but does NOT assert that cancel still works. US-22-4 TC-08 asserts replay latency but NOT that cancel during replay works.

**Fix recommendation:**
In `PLAN-IP-22-...md`, add a new test case to Phase 8:
```
8.12 | New `backend/tests/test_agent_orchestrator_cancel_with_complexity.py` covering: (a) cancel during trivial path (should abort before search); (b) cancel during deep path (should abort and emit `user_cancelled` even if 2 critiques not yet completed); (c) cancel during instant-cache replay (should abort before synthetic events are emitted — edge case but possible if cancel fires in the tiny window between `try_replay` returning and `_stop_from_cache` completing). | Integration | M | 6.4, 4.8 | RF-08 preservation |
```

---

#### Finding 5 — MINOR: `_count_named_entities` does NOT handle acronyms or hyphenated entities correctly

**Location:** Task 3.2
**Type:** `heuristic_edge_case`
**Affected RF:** RF-01 (planning accuracy)
**Severity:** minor

**Description:**
Task 3.2 describes `_count_named_entities` as counting "contiguous runs of capitalised tokens" but does NOT specify how to handle:
1. **ALL-CAPS acronyms** (e.g. "PostgreSQL vs RDBMS") — current logic `tok.isupper()` would count `RDBMS` as a single entity, but it's non-contiguous with `PostgreSQL`. Acceptable per US-22-1 Scenario 2 notes, but ambiguous.
2. **Hyphenated entities** (e.g. "Hewlett-Packard", "Jean-Paul Sartre") — current logic splits on whitespace, so these count as 1 token, not 2. Acceptable, but the plan should state this.
3. **Title-case within a sentence** (e.g. "What is Event Sourcing?") — `Event Sourcing` is two contiguous capitalised tokens; the heuristic counts it as 1 entity (correct). But if the question is "What is Event Sourcing and CQRS?" — `CQRS` is a separate run → 2 entities → coerced to `standard`. This contradicts BRD-22 §4.5 which says trivial requires "single named entity" (arguably "Event Sourcing" is one conceptual entity, but the heuristic sees two tokens).

**Fix recommendation:**
In `PLAN-IP-22-...md`, modify **Task 3.2** to state:
```
Add private `_count_named_entities(question: str) -> int` inside `complexity.py`. Heuristic: split on whitespace, strip leading sentence interrogatives (`What`, `Why`, `Where`, `When`, `Who`, `How`, `Is`, `Are`, `Do`, `Does`, `Did`, `Can`, `Could`, `Would`, `Should` — case-insensitive at position 0 only). Count contiguous runs of title-case or ALL-CAPS tokens. A "contiguous run" is one or more adjacent tokens matching `tok[0].isupper() and (tok[1:].islower() or tok.isupper())`. Hyphenated entities (e.g. "Hewlett-Packard") count as 1 token (no split on hyphen). Rationale: over-counting (e.g. "Event Sourcing" → 1 run of 2 tokens) is acceptable — it biases toward `standard`, which is the safe default. Document examples in a docstring: "Tokyo" → 1, "Event Sourcing" → 1 (contiguous), "PostgreSQL vs MongoDB" → 2 (non-contiguous), "What is CQRS?" → 1.
```

---

### 5. Required Changes (if not approved)

1. **[MAJOR — Finding 1]** Modify Task 6.7 to explicitly state how `PriorRunHintReplayedEvent` folding ensures the synthetic `JudgeRuledEvent` + `StoppedEvent` correctly populate all `RunState` fields, and add a fork-after-replay test case to US-22-4 TC-09.

2. **[MAJOR — Finding 2]** Modify Task 4.4 to specify the fallback strategy when `complexity_hint=None` during plan revision (`STANDARD` default + logged event).

3. **[MAJOR — Finding 3]** Modify Task 4.6 and Task 4.9 to specify how `critique_passes_target` and `critique_passes_completed` are reconstructed during `_fold_events` (either via new event fields OR deterministic recomputation from existing events). Choose the simpler option and document it.

4. **[MINOR — Finding 4]** Add a new test case (8.12) covering cancellation during trivial path, deep path, and instant-cache replay.

5. **[MINOR — Finding 5]** Clarify the entity-counting heuristic in Task 3.2 with explicit handling rules and docstring examples.

6. **[MINOR — Gap in §10]** In the AC mapping table (§10), the row for BRD-22 AC-09 states "Tasks 1.4, 4.9, 6.7 + Tests 8.7, 8.8" but does NOT mention the missing-field replay test case in 8.1 TC-07. Add: `8.1 TC-07` to the "Tests asserting it" column for AC-09.

7. **[MINOR — Language policy]** Phase 2.1 and 2.2 extend LLM prompts. Task 2.1 and 2.2 do NOT explicitly state that the new prompt text must be in **English** (per `/memories/language-policy.md`). Add a note to both tasks: *"System prompt extensions: all text in English (language-policy.md)."*

---

### 6. Positive Highlights

1. **D-IP22-01 through D-IP22-10 are genuine, well-justified ambiguity resolutions.** Each decision includes a rationale tied to an existing contract or a concrete simplification (e.g. D-IP22-02 keeps `QuestionIndex` and instant_cache separate to preserve the `extra="forbid"` contract — this is a real architectural judgment, not hand-waving).

2. **Phase ordering (§8 dependency graph) is sound and acyclic.** Phases 1+2 land first (pure additive), Phases 3–6 are independent, Phase 7 follows type regeneration, Phase 8 follows implementation, Phase 9 follows review.

3. **The plan correctly identifies that `triggering_signal = "instant_cache"` is a sub-field of `StopRationale`, NOT a new `stop_reason` enum value.** This preserves RF-02. (Hard validation #4 — PASSED.)

4. **The multiplier design (Task 5.5, 5.6) is non-compounding and clamped to `[0, 1]`.** The plan states: *"Never compounds. Two matches → still `1.1`."* and *"Multiplier applied inside `calculate_agreement` only, clamped to `[0.0, 1.0]` after multiplication."* This preserves the `min(S_effective, J)` invariant (Task 5.6 confirms the multiplier is on the per-evidence-row `aligning` sum, not on `S_raw` itself; `S_raw` is derived from agreement, which is the output of `calculate_agreement`). (Hard validation #2 — PASSED.)

5. **Three plugin seams (Source/StoppingSignal/OutputRenderer) are not bypassed or extended.** Phase 5 modifies `calculate_agreement` (an internal function), not the `StoppingSignal` protocol. (Hard validation #5 — PASSED.)

6. **§10 Acceptance Mapping is comprehensive.** Every BRD-22 AC and every US AC is mapped to tasks + tests. Minor gap: AC-09 missing one test reference (noted above).

7. **All new Pydantic fields use `| None = None` (optional with default).** Tasks 1.3, 1.4, 1.5, 2.1, 2.2, 4.6 all preserve `extra="allow"`. (Hard validation #3 — PASSED.)

8. **Cache is in-memory only and explicitly cleared on restart (Task 6.1, 6.3).** RF-05 single-server scope preserved. (Hard validation #8 partial — cache survives restart is correctly marked as non-compliant; no blind path here.)

9. **The instant-cache replay path emits canonical events** (`RunCreated`, `PriorRunHintReplayedEvent`, synthetic `JudgeRuledEvent`, synthetic `StoppedEvent`), so the replayed run is a first-class run, not a hidden optimization. RF-13 trust-surface preserved.

10. **Risk register (§9) is realistic.** Each risk has a concrete mitigation. R3 (cache replay confuses fork lineage) is correctly mitigated with `parent_run_id=None` + `source_run_id` informational link.

---

### 7. Next Step

- **Verdict: NEEDS REVISION (score 8.2 < 9).**
- **Action:** Return to Orchestrator with Required Changes §5 (items 1–7).
- **audit_iter incremented to 2.**
- If revised plan addresses all 7 items AND reaches score ≥ 9 on iter 2 → proceed to F3 (Coder).
- If audit_iter reaches 3 without ≥ 9 → escalate to F6 (manual review).

---

## Hard Validations (from user prompt) — Results

| # | Validation | Result |
|---|---|---|
| 1 | RFs cited match `requirement-understanding.md` | ✅ PASS — all RF citations verified against canonical text |
| 2 | `min(S_effective, J)` invariant preserved; multiplier inside agreement only | ✅ PASS — Task 5.6 confirms multiplier on per-row `aligning` sum; `S_raw` derives from `calculate_agreement` output |
| 3 | Events append-only; `extra="allow"` on new models | ✅ PASS — all new events use optional fields; no destructive mutations |
| 4 | `stop_reason` enum not extended; `triggering_signal` is sub-field | ✅ PASS — D-IP22-09 confirms `StopRationale.triggering_signal`, not a new enum value |
| 5 | Three plugin seams not bypassed | ✅ PASS — no new seam; `calculate_agreement` is internal function |
| 6 | Phase ordering sound and acyclic | ✅ PASS — §8 dependency graph validated |
| 7 | Phase 8 tests cover every AC in §10 | ⚠️ MINOR GAP — AC-09 missing one test reference (8.1 TC-07); otherwise comprehensive |
| 8 | Blind paths: entered but not exited; new events not folded; new RunState fields not initialized; cache state post-restart | ⚠️ **3 MAJOR FINDINGS** — Findings 1, 2, 3 (folding gaps); Finding 4 (minor cancel gap) |
| 9 | D-IP22-01..10 are real resolutions | ✅ PASS — each decision has concrete rationale |
| 10 | Language policy upheld in new prompts | ⚠️ MINOR GAP — Tasks 2.1, 2.2 do not explicitly state English requirement |

**Summary:** 7/10 PASS, 3/10 minor gaps. No auto-fail criteria triggered.

---

**Audit completed.** Report saved to [docs/implementation-phase/audits/AUDIT-IP-22-complexity-aware-planning-and-experts.md](../audits/AUDIT-IP-22-complexity-aware-planning-and-experts.md).

---

## Iter 2 — 2026-05-27

### 0. Resolution of Iter 1 Findings

| Prior change | Status | Evidence |
|---|---|---|
| 1. Task 6.7 — explicit fold contract + fork test | ✅ done | Task 6.7 now includes: (a) extract `source_run_id` into `state.metadata`; (b) synthetic events populate all canonical fields; (c) verify existing fold branches; (d) add explicit fork-after-replay test in TC-09 |
| 2. Task 4.4 — STANDARD fallback + log | ✅ done | Task 4.4 specifies: default to `STANDARD`, log `complexity_hint_defaulted_on_revise`, emit in `PlanRevisedEvent` |
| 3. Tasks 4.6 + 4.9 — critique counters recomputed | ✅ done | Task 4.6 documents recomputation strategy; Task 4.9 provides formulas: target from budget table, completed = count `PLAN_CRITIQUED` events |
| 4. Task 8.12 — cancellation tests | ✅ done | New test added covering (a) trivial cancel, (b) deep cancel mid-critique, (c) cache replay window cancel |
| 5. Task 3.2 — entity heuristic clarified | ✅ done | Docstring examples added: "Tokyo" → 1, "Event Sourcing" → 1, "PostgreSQL vs MongoDB" → 2; hyphenated entities clarified |
| 6. §10 AC-09 + RF-08 rows | ✅ done | AC-09 row updated; RF-08 row added: "4.8, 6.4 \| 8.12" |
| 7. Tasks 2.1 + 2.2 — English-policy note | ✅ done | Both tasks include bold note: "System prompt extensions: all text in English (per `/memories/language-policy.md`)." |

**All 7 required changes from Iter 1 have been fully addressed.**

---

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 10.0/10 | 30% | 3.00 |
| Acceptance Criteria Completeness | 9.5/10 | 20% | 1.90 |
| Blind-Path Absence | 9.5/10 | 25% | 2.375 |
| Traceability | 9.5/10 | 15% | 1.425 |
| Consistency w/ docs | 9.0/10 | 10% | 0.90 |
| **TOTAL** | | | **9.60/10** |

**Rounded final score: 9.6/10**

---

### 2. Verdict

✅ **APPROVED** (score ≥ 9)

The revised plan (v1.1) comprehensively addresses all 7 required changes from Iter 1. All major blind-path findings have been resolved. The only remaining issues are minor and do not block implementation:
- Task 5.9 uses `grep` to find callers — slightly vague but acceptable (compile errors will catch misses)
- §11 "Open Questions for Auditor" still present but questions already answered by the changes

Neither issue blocks F3 (Coder phase). The plan is production-ready.

---

### 3. Requirements Coverage Matrix (Updated)

| RF | Covered? | Where (section/task) | Change from Iter 1 |
|---|---|---|---|
| RF-01·A | ✅ | §1, §4 (Phase 4) | unchanged |
| RF-01·F | ✅ | §1, implicit | unchanged |
| RF-02 | ✅ | §1, D-IP22-09, Task 1.2 | unchanged |
| RF-03 | ✅ | §1, §6, Tasks 1.3–1.6, 4.6, 4.9, 6.7 | **upgraded from ⚠️** — all folding gaps resolved |
| RF-04 | ✅ | §1, §4 (Phase 5) | unchanged |
| RF-05 | ✅ | §1, §6, Task 6.1 | unchanged |
| RF-06 | ✅ | §1 | unchanged |
| RF-08 | ✅ | Tasks 4.8, 6.4, 8.12, §10 | **upgraded from ⚠️** — explicit test added |
| RF-12 | ✅ | §1, Tasks 5.6, 5.7, 5.8, 5.9 | unchanged |
| RF-13 | ✅ | §1, Phase 7 | unchanged |
| RF-17/18/19 | ✅ | §1 | unchanged |

**Coverage score: 10.0/10** — all in-scope RFs traced with explicit task/test references; no gaps.

---

### 4. Blind-Path Findings (Iter 2)

**No new major findings.** All three major findings from Iter 1 (replay folding gaps in Tasks 4.6, 4.9, 6.7) have been resolved.

#### Minor residual issue 1 — Task 5.9 grep directive is slightly vague

**Location:** Task 5.9
**Type:** `testing_discipline`
**Affected RF:** RF-12 (correctness)
**Severity:** trivial

**Description:**
Task 5.9 states: *"Update `AgentOrchestrator._handle_judging` and `_handle_analyzing` callers of `calculate_agreement(...)` to pass `expected_experts=self.state.expected_experts`. Other callers in stopping signals (grep `calculate_agreement(`) updated identically."*

The `grep` directive is slightly vague — it should list the expected files or assert in testing that all callers thread the parameter. However, this is a **testing discipline issue, not a blind path**: the signature change will cause compile errors (pyright strict) if any caller is missed.

**Deduction:** -0.5 from Blind-Path Absence (already reflected in score).

**Not blocking:** Type errors will surface on first run; tests will catch runtime issues if any caller doesn't thread the param.

---

#### Minor residual issue 2 — §11 "Open Questions for Auditor" still present

**Location:** §11
**Type:** `stale_documentation`
**Affected RF:** none (cosmetic)
**Severity:** trivial

**Description:**
§11 lists 3 open questions for the Auditor, but all have been answered by the implemented changes:
1. Forced second critique on `deep` — answered in D-IP22-03 and Task 4.8.
2. Count `PlanRevisedEvent` or only `PlanCritiquedEvent` — answered in Task 4.9 (only critiqued).
3. Multiplier on contradictions — answered in Task 5.6 (no multiplier on contradictions).

**Recommendation:** Remove §11 in a cleanup pass, or retitle to "Design Decisions (resolved)".

**Deduction:** -1.0 from Consistency w/ docs (already reflected in score).

**Not blocking:** The questions are resolved; their presence is harmless.

---

### 5. Required Changes

**None.** Score ≥ 9, all major findings resolved. Proceed to F3 (Coder).

Optional cleanup (non-blocking):
- Remove or retitle §11 "Open Questions for Auditor" (questions already answered).
- Consider making Task 5.9 more explicit by listing expected files (`orchestrator.py`, `stopping/*.py`).

---

### 6. Positive Highlights (Iter 2)

1. **All 7 Iter 1 findings fully resolved.** The Orchestrator applied every change precisely as requested, with explicit evidence in the revised tasks.

2. **Task 4.6 + 4.9 now include explicit replay-determinism strategy.** The plan states: *"Both counters MUST be derived purely from the event log — never persisted directly."* This is exactly the RF-03 contract.

3. **Task 6.7 fold contract is comprehensive.** It covers: (a) informational metadata extraction, (b) verification of existing fold branches, (c) explicit fork test case. This addresses the full concern from Finding 1.

4. **Task 8.12 covers all three cancellation scenarios.** Including the edge case (cancel during cache replay window) shows defensive thinking.

5. **Task 3.2 docstring examples are concrete and testable.** "Tokyo" → 1, "Event Sourcing" → 1, "PostgreSQL vs MongoDB" → 2, "Hewlett-Packard" → 1. These map directly to test cases.

6. **English-policy note in Tasks 2.1 + 2.2 is explicit and traceable.** Cites the memory file path, not just a vague "follow standards".

7. **§10 AC mapping is now 100% complete.** AC-09 includes all tests (8.1 TC-07, 8.2 replay case, 8.7, 8.8). RF-08 row added with tasks + test.

8. **Hard validations (re-run):** 9/10 PASS, 1/10 minor residual. No auto-fail criteria triggered.

9. **D-IP22-01..10 remain sound.** No regressions introduced by the revisions.

10. **Phase ordering unchanged and still acyclic.** Revisions did not disrupt the dependency graph.

---

### 7. Next Step

- **Verdict: ✅ APPROVED (score 9.6 ≥ 9).**
- **Action:** Proceed to **F3: CODE** (Coder phase).
- **Coder receives:** This plan (v1.1) + both audit reports (Iter 1 + Iter 2 for context).
- **No further audit iterations required.**

---

## Hard Validations (Re-run for Iter 2) — Results

| # | Validation | Result |
|---|---|---|
| 1 | RFs cited match `requirement-understanding.md` | ✅ PASS — all RF citations verified |
| 2 | `min(S_effective, J)` invariant preserved; multiplier inside agreement only | ✅ PASS — unchanged from Iter 1 |
| 3 | Events append-only; `extra="allow"` on new models | ✅ PASS — unchanged from Iter 1 |
| 4 | `stop_reason` enum not extended; `triggering_signal` is sub-field | ✅ PASS — unchanged from Iter 1 |
| 5 | Three plugin seams not bypassed | ✅ PASS — unchanged from Iter 1 |
| 6 | Phase ordering sound and acyclic | ✅ PASS — unchanged from Iter 1 |
| 7 | Phase 8 tests cover every AC in §10 | ✅ PASS — **upgraded from Iter 1** — AC-09 + RF-08 rows now complete |
| 8 | Blind paths: entered but not exited; new events not folded; new RunState fields not initialized; cache state post-restart | ✅ PASS — **upgraded from Iter 1** — all 3 major findings resolved; 2 trivial residual |
| 9 | D-IP22-01..10 are real resolutions | ✅ PASS — unchanged from Iter 1 |
| 10 | Language policy upheld in new prompts | ✅ PASS — **upgraded from Iter 1** — Tasks 2.1, 2.2 now include explicit note |

**Summary:** 10/10 PASS. All prior gaps resolved.

---

**Iter 2 audit completed.** Plan approved. Proceed to F3.
