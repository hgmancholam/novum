# Audit Report — IP-22

<!-- STATUS HEADER — overwritten on every iteration -->
**Artifact:** IP-22-complexity-aware-planning-and-experts.md
**Phase:** F2 (Implementation Plan audit)
**Auditor:** Auditor Agent
**Latest Iteration:** 1
**Latest Date:** 2026-05-27
**Latest Score:** 9.10/10
**Latest Verdict:** ✅ APPROVED
**Iteration Log:**
| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-27 | 9.10 | ✅ APPROVED |

---

## Iter 1 — 2026-05-27

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 9.5/10 | 30% | 2.85 |
| Acceptance Criteria Completeness | 9.0/10 | 20% | 1.80 |
| Blind-Path Absence | 8.5/10 | 25% | 2.13 |
| Traceability | 9.5/10 | 15% | 1.43 |
| Consistency w/ docs | 9.0/10 | 10% | 0.90 |
| **TOTAL** | | | **9.10/10** |

### 2. Verdict

**✅ APPROVED (≥9)**

The plan is comprehensive, well-structured, and demonstrates strong awareness of the architectural constraints and RF traceability. The autonomous decisions (D-IP22-01..10) are thoughtfully reasoned and resolve genuine ambiguities in the BRD. The task breakdown is detailed with clear dependencies, and the test coverage is thorough.

**Minor deductions** stem from three areas: (1) incomplete blind-path coverage for the cancel-during-cache-replay scenario, (2) missing explicit guidance on LRU eviction behavior in the instant cache, and (3) a subtle architectural tension between the plan's "zero new FSM states" claim and the critique-skip mechanism's reliance on state counters.

Proceed to **F3: IMPLEMENT** (Coder).

---

### 3. Requirements Coverage Matrix

| RF | Covered? | Where (section/task/test) | Notes |
|---|---|---|---|
| **RF-01·A** | ✅ | §1, §3 D-IP22-03/06, Tasks 4.1–4.9, Tests 8.2 | Planner budget extended with `ComplexityHint` axis; coercion logic explicitly handles incompatible combinations |
| **RF-01·F** | ✅ | §1, implicit in orchestrator loop (no new task) | Budget cap preserved; no change required (trivial/deep both execute inside existing loop) |
| **RF-02** | ✅ | §1, Tasks 1.2, 1.5 (new event types), D-IP22-09 | New event types map to existing stop_reason values; instant cache emits synthetic `JudgeRuled → Stopped` |
| **RF-03** | ✅ | §1, §6, Tasks 1.3/1.5/1.6, 4.9, 6.7 | Events append-only; new events use `extra="allow"`; replay tolerates missing fields |
| **RF-04** | ✅ | §1, §3 D-IP22-08, Tasks 5.1–5.9, Tests 8.3, 8.4 | Expert multiplier on agreement (non-compounding, clamped); heterogeneity preserved |
| **RF-05** | ✅ | §6, §9, Tasks 6.1–6.3, D-IP22-07 | In-memory cache, cleared on restart; cross-user scoping via `(username, normalised_question)` key |
| **RF-06-quater** | ✅ | §1, §4.10, Tasks 7.2–7.6, Tests 8.9, 8.10 | Three new trust elements: `ComplexityBadge`, `ExpectedExpertsList`, `PriorRunHintReplayed` trace row |
| **RF-08** | ⚠️ | Implicit (no new task); cache replay path | Cancel handling on non-cache path unchanged; cache replay bypasses classify/plan — **see Finding F-01** |
| **RF-12** | ✅ | §1, §3 D-IP22-04, Tasks 5.6–5.9, Tests 8.4 TC-10 | `final_confidence = min(S_effective, J)` invariant explicitly preserved; multiplier inside agreement only |
| **RF-13** | ✅ | §1, §4.10, Tasks 7.2–7.6 | UI surfaces all three new capabilities; microcopy pinned in plan §4.10 |
| **RF-17** | ✅ | §1 (untouched) | Six-template synthesis preserved; no capability touches AnswerKind logic |
| **RF-18** | ✅ | §1 (untouched) | Saturation unchanged |
| **RF-19** | ✅ | §1 (untouched) | Judge provider unchanged |

**Score rationale:** Near-perfect coverage. All in-scope RFs are mapped to concrete tasks or explicitly noted as untouched. The RF-08 gap is minor (see Finding F-01) and does not block approval given the 9/10 threshold.

---

### 4. Blind-Path Findings

#### F-01: Cancel-during-instant-cache-replay path not explicitly documented

- **Location:** §4.8 cache replay logic / Task 6.4 / RF-08 cancellation requirement
- **Type:** missing_cancel
- **Affected RF:** RF-08
- **Severity:** minor

**Description:**
The cache replay path (Task 6.4) emits `QuestionAskedEvent → PriorRunHintReplayedEvent → JudgeRuled → Stopped` "at the very top of the `is_fresh` branch" and "BEFORE" the classify step. The plan claims the replay completes in ≤ 1 s (AC-06). However, RF-08 mandates cancellation is honored at every long-running step.

The plan does not explicitly address: *what happens if the user clicks Cancel between `QuestionAskedEvent` and the synthetic `Stopped`?* The orchestrator's `_stop` method is synchronous and emits a terminal `StoppedEvent`; the cache-replay block could theoretically race with a concurrent `cancel(run_id)` call.

**Expected behavior:**
One of:
1. Cancel during replay still emits `Stopped(user_cancelled)` (overrides cache), OR
2. Replay is atomic (cancellation queued but not applied until the synthetic `Stopped` completes), OR
3. Cancel during replay is silently ignored (defensible given ≤ 1 s window).

Choice (1) is most consistent with RF-08. Choice (3) requires a BRD note justifying the exception.

**Fix recommendation:**
Add Task 6.4b: In `_stop_from_cache`, check `self._cancel_requested` before emitting synthetic events. If cancelled, emit `Stopped(user_cancelled)` instead of replaying. Alternatively, add a note in §9 Risks that the ≤ 1 s replay window is too short to warrant cancel handling and cite it as a deliberate exception (acceptable for approval but must be documented).

---

#### F-02: LRU eviction on `OrderedDict` may silently drop high-value entries

- **Location:** Task 6.1 (`OrderedDict[tuple[str, str], CachedRun]`)
- **Type:** no_user_feedback (silent state loss)
- **Affected RF:** RF-13 (trust contract — user must know when cache misses occur)
- **Severity:** minor

**Description:**
The plan specifies an LRU-capped `OrderedDict` (Task 6.1) with `settings.instant_cache_max_size = 256` (Task 1.7). When the cache fills, the oldest entry is evicted. This is correct behavior, but the plan does not specify whether eviction is logged or surfaced to the user.

A user who asks the same question twice within a session expects a cache hit (≤ 1 s), but if 256 other questions were asked in between, the cache has silently evicted their entry and they experience full-pipeline latency (~90 s for trivial, ~600 s for standard). From the user's perspective, this looks like a regression or a bug.

**Expected behavior:**
Eviction should emit a structured log entry (`cache_evicted key=<question_hash> reason=lru_cap`) at DEBUG or INFO level so operators can tune `max_size` if cache-miss rates spike.

**Fix recommendation:**
Add to Task 6.1: In `record_run`, when `len(cache) >= max_size`, emit structured log `cache_evicted reason=lru_cap evicted_question=<normalised>` before popping the oldest key. No UI surface required (eviction is expected behavior, not an error). Alternatively, add a sentence in §9 Risks acknowledging the tradeoff: "LRU eviction is silent; users may experience cache misses on repeated questions if >256 unique questions are asked in a session. Tunable via config; logged at DEBUG."

---

#### F-03: No explicit guard for concurrent `record_run` calls on the same `(username, question)` key

- **Location:** Task 6.6 (cache recording hook)
- **Type:** missing_transition (unhandled concurrency)
- **Affected RF:** RF-05 (single-writer-per-run discipline)
- **Severity:** minor

**Description:**
RF-05 enforces single-writer-per-run via the in-process task registry. However, the instant cache is keyed by `(username, normalised_question)`, not `run_id`. Two users (or the same user in two tabs) could submit the identical question simultaneously, producing two concurrent runs with different `run_id`s. Both will eventually call `record_run` with the same cache key.

The plan does not specify: *which run wins?* Last-writer-wins is safe (no corruption), but it could silently replace a high-confidence entry with a lower one if the runs complete in unlucky order.

**Expected behavior:**
Last-writer-wins is acceptable (and matches the `OrderedDict` semantics), but it should be documented in Task 6.6 or §9 Risks so the Coder does not add a lock that contradicts the single-server scope (RF-05).

**Fix recommendation:**
Add a note in Task 6.6: "Concurrent `record_run` calls for the same `(username, question)` are safe — last-writer-wins. No lock required (RF-05 single-server scope). If two runs for identical questions complete simultaneously, the later one replaces the earlier in cache. This is acceptable; the replaced entry is still in the DB and forkable."

---

### 5. Acceptance Criteria Mapping

All 9 BRD-22 acceptance criteria and all US-22-x criteria are covered by tasks + tests. Mapping:

| BRD-22 AC | Tasks | Tests | Status |
|---|---|---|---|
| AC-01 (trivial short-circuit) | 3.1–3.4, 4.1–4.8 | 8.1 TC-01, 8.2 TC-01, 8.6 TC-08 | ✅ |
| AC-02 (standard unchanged) | 4.1–4.4 | 8.2 TC-03 | ✅ |
| AC-03 (deep extra critique) | 4.1, 4.7, 4.8 | 8.2 TC-04 | ✅ |
| AC-04 (expert multiplier) | 5.5, 5.6 | 8.3 TC-01, 8.4 TC-09 | ✅ |
| AC-05 (non-compounding) | 5.5 | 8.3 TC-05 | ✅ |
| AC-06 (cache replay ≤ 1 s) | 6.1–6.6 | 8.5 TC-01 | ✅ |
| AC-07 (cache miss fallthrough) | 6.2 | 8.5 (no-hit case) | ✅ |
| AC-08 (low-confidence ignored) | 6.2 | 8.5 TC-02 | ✅ |
| AC-09 (historical replay) | 1.4, 4.9, 6.7 | 8.7, 8.8 | ✅ |

**US-22-1 (complexity hint):**
All 6 scenarios → Tasks 3.1–3.4 + Tests 8.1 TC-01..07. ✅

**US-22-2 (planner budget):**
All 7 scenarios → Tasks 4.1–4.9 + Tests 8.2 TC-01..06, 8.6 TC-07/08. ✅

**US-22-3 (expected experts):**
All 9 scenarios → Tasks 5.1–5.9 + Tests 8.3 TC-01..08, 8.4 TC-09/10. ✅

**US-22-4 (instant cache):**
All 9 scenarios → Tasks 6.1–6.7 + Tests 8.5 TC-01..09. ✅

**Score rationale:** Perfect mapping. Every AC has at least one task AND at least one test. The plan is unusually thorough in this regard.

---

### 6. Traceability

- **Plan ID:** IP-22 ✅
- **Parent links:** BRD-22, US-22-1/2/3/4 all cited with paths ✅
- **Task structure:** Each task lists files, effort, dependencies, RFs/USs satisfied ✅
- **Dependency graph:** Section 8 provides a clear DAG; no forward dependencies ✅
- **Autonomous decisions:** 10 decisions (D-IP22-01..10) are explicitly recorded in §3 with rationale ✅

**Finding (non-blocking):** Task 8.11 (coverage gate) is listed as effort "S" but depends on "end of Phase 8" — this makes it a gate, not a task. Should be labeled "Gate" and have effort "XS" (it's a pass/fail check, not implementation work). This is a documentation nit, not a logical error.

**Score rationale:** Near-perfect. The plan is exceptionally well-linked. Minor dock for the gate/task confusion.

---

### 7. Architectural & Tech-Stack Consistency

**8 Architectural Rules (from architecture.md §1):**

| Rule | Compliance | Evidence |
|---|---|---|
| 1. Event log is source of truth | ✅ | Tasks 1.3/1.5 append events; no mutation |
| 2. Stop reasons are enum | ✅ | D-IP22-09 maps cache replay to existing `judge_confirmed` |
| 3. Three plugin seams | ✅ | Plan explicitly states "no new plugin seam" (§10 Out of Scope) |
| 4. Read determinism | ✅ | Cache replay emits synthetic events with prior values (D-IP22-09) |
| 5. Schema evolution = `extra="allow"` | ✅ | Tasks 1.3, 1.4, 1.5 all use `extra="allow"` |
| 6. Single-server scope | ✅ | In-memory cache (Task 6.1), no Redis, no distributed locks |
| 7. Honest stops as successes | ✅ | Preserved; no honest-stop changes in this plan |
| 8. UI surfaces trust | ✅ | Tasks 7.2–7.6 add three new trust elements (RF-13) |

**Banned tech check (tech-stack.md):**
- ❌ Redis → not used ✅
- ❌ Docker → not mentioned ✅
- ❌ LangGraph/LangChain → not used ✅
- ❌ Celery/RQ → not used ✅
- ❌ WebSockets → not used (SSE preserved) ✅
- ❌ vector DB → not used (in-memory only) ✅

**LLM routing check (ai-services.md §1.3):**
- Task 2.1 extends classifier LLM model → calls go through existing `app/llm/client.py::call` ✅
- Task 2.2 extends planner LLM model → same routing ✅
- No new LLM call introduced outside the client wrapper ✅

**Type contract (architecture §7):**
- Task 7.1 explicitly runs `scripts/export_types.py` and commits the regenerated types ✅
- Plan warns against hand-editing `events.ts` ✅

**Finding (non-blocking tension):** The plan claims "no new FSM state" (§1, §10), but the critique-skip mechanism (Task 4.7, 4.8) relies on `RunState.critique_passes_target` and `critique_passes_completed` counters. While these are not *named states*, they do represent a modal distinction (`target=0` → skip CRITIQUING, `target=2` → force second pass). This is technically consistent with "no new FSM state" (the states remain the same 9 from BRD-07), but the FSM's transition logic is now parameterized by these counters, which is a subtle departure from the "no new state" framing. Consider rephrasing §1 / §4.6 to say "no new FSM *state*, but adds parameterized transition logic" to avoid misleading a future auditor.

**Score rationale:** Excellent compliance. Minor dock for the FSM framing ambiguity.

---

### 8. Open Questions from Plan §11

The plan poses three open questions for the Auditor. Responding:

**Q1: Should the second critique pass on `deep` always force a revision even when the first critique is `acceptable=true`?**
**Answer:** ✅ Yes. US-22-2 AC-3 explicitly states "Exactly two `PlanCritiquedEvent` events" for deep. The plan's choice (Task 4.8: force path when `critique_passes_completed < critique_passes_target`) is correct. The word "critique" in AC-3 means *two invocations of the critic LLM*, not *two rejections*. Confirm approved.

**Q2: Should `_handle_critiquing` count `PlanRevisedEvent` toward `critique_passes_completed` or only `PlanCritiquedEvent`?**
**Answer:** ✅ Only `PlanCritiquedEvent`. The plan's choice is correct. `critique_passes_completed` tracks *how many times the critic ran*, not how many times the plan was revised. A single critique pass can produce zero or one `PlanRevisedEvent` depending on `acceptable`. The counter increments at the top of `_handle_critiquing` (Task 4.8), which is when the LLM call completes. Confirm approved.

**Q3: Multiplier on contradictions — should expert-matched contradicting evidence get a 1.1× boost as well?**
**Answer:** ✅ No. The plan's choice (Task 5.6: multiplier applies only to `polarity ∈ ("supports", "neutral")`) is correct. Boosting contradictions would **penalize** expert sources by inflating the denominator of the agreement formula, which contradicts the intent of BRD-22 §4.7 ("sources whose domain matches… tilt agreement toward better-grounded answers"). An expert contradiction is still a contradiction; the multiplier's job is to amplify *support strength*, not conflict strength. Confirm approved.

---

### 9. Risk Assessment

The plan's §9 risk table is comprehensive and includes mitigations for 8 risks. **Additional risk identified during audit:**

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| **(Audit-flagged)** Cache replay bypasses plan critic (RF-14) and disconfirmation pass (RF-15) for the second ask of the same question, even if the prior run's plan was weak or its evidence was one-sided. | Medium | Low | Acceptable trade-off. The cache condition already requires `final_confidence ≥ 0.85` AND `stop_reason=judge_confirmed` (Task 6.2), so the prior run passed the judge. Weak plans that failed the judge are not cached. Document this in §9 with the justification: "Cache replay intentionally skips re-critique and re-disconfirmation; the ≥ 0.85 confidence + judge-confirmed gate ensures only high-quality runs are eligible." |

---

### 10. Required Changes

None. All findings (F-01, F-02, F-03) are **minor** and do not block approval at the 9/10 threshold. They are recommendations for the Coder to address during implementation, not blockers for the plan.

---

### 11. Recommended (Non-Blocking) Changes

1. **Task 6.4 (F-01 cancel path):** Add a sentence: *"If `self._cancel_requested` is set during the replay block, emit `Stopped(user_cancelled)` instead of the synthetic `JudgeRuled`. The ≤ 1 s window makes this unlikely but RF-08 mandates completeness."*

2. **Task 6.1 (F-02 eviction logging):** Add: *"When evicting the oldest entry due to LRU cap, emit structured log `cache_evicted key=<question> reason=lru_cap` at DEBUG level for operational visibility."*

3. **Task 6.6 (F-03 concurrency note):** Add: *"Concurrent `record_run` calls for the same key are safe (last-writer-wins). No lock required per RF-05. Document in a code comment."*

4. **Task 8.11 (gate vs. task):** Relabel as "Gate 8.11: Coverage threshold" and change effort from "S" to "Gate" or "XS".

5. **Plan §1 / §4.6 (FSM framing):** Rephrase *"no new FSM state"* to *"no new FSM state; adds parameterized transition logic via `critique_passes_target`"* to avoid ambiguity.

6. **Plan §9 (cache-replay risk):** Add the cache-vs-RF-14/15 trade-off (see §9 above) to the risk table with mitigation = "acceptable by design."

---

### 12. Positive Highlights

- **Autonomous decisions are exemplary.** D-IP22-01..10 show deep engagement with the BRD ambiguities and trace every choice to a requirement or test case. This is the correct use of the decision-record mechanism.
- **Test coverage is unusually thorough.** 11 new test files + 6 extended test files cover every TC from all four user stories. The plan explicitly asserts ≥ 80% coverage (Task 8.11) and ties it to the DoD.
- **Scope discipline is excellent.** The "Out of Scope" section (§10) explicitly calls out what V1 will NOT do (dynamic taxonomy, cross-tenant cache, cosine-match cache, etc.), which prevents feature creep during implementation.
- **Dependency graph is clear and realistic.** Section 8's DAG is correct; Phases 1+2 land first (additive), then 3–6 in parallel, then 7 after type generation, then 8 (tests), then 9 (docs). No circular dependencies.
- **Traceability to RFs is meticulous.** Every task cites which RF / US / AC it satisfies. This makes the audit straightforward and sets a high bar for future plans.

---

### 13. Next Step

✅ **APPROVED** — Proceed to **F3: IMPLEMENT** (Coder).

The plan is ready for implementation. The three findings are documented as recommendations for the Coder; none block the 9.10/10 score or the approval decision. The plan demonstrates strong command of the architecture, requirements, and testing policy.

---

**Auditor signature:** Auditor Agent, 2026-05-27
**Memory bank updates pending:** `decisions-history.md` (D-IP22-01..10), `knowledge-base-index.md` (IP-22 entry), this audit report path.
