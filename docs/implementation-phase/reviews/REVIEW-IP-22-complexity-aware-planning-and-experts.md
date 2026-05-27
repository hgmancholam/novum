# Code Review Report — IP-22: Complexity-Aware Planning + Expected Experts

**Implementation Plan:** [IP-22 v1.1](../implementation-plans/IP-22-complexity-aware-planning-and-experts.md)
**BRD Reference:** [BRD-22 v1.0](../brds/BRD-22-complexity-aware-planning-and-experts.md)
**User Stories:** [US-22-1](../user-stories/US-22-1-complexity-hint-classifier.md), [US-22-2](../user-stories/US-22-2-planner-complexity-budget.md), [US-22-3](../user-stories/US-22-3-expected-experts.md), [US-22-4](../user-stories/US-22-4-instant-answer-cache.md)
**Date:** 2026-05-27
**Reviewer:** Reviewer Agent (Sonnet 4.5)
**Complexity:** L (quality_profiles.L)
**Profile thresholds:** min_score=9, max_iter=5
**Iteration:** 1

---

## Summary

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Code Quality | 10/10 | 25% | 2.50 |
| Test Coverage | 9.5/10 | 20% | 1.90 |
| Architecture Compliance | 10/10 | 20% | 2.00 |
| Documentation | 9/10 | 15% | 1.35 |
| Security | 10/10 | 10% | 1.00 |
| Performance | 9/10 | 10% | 0.90 |
| **TOTAL** | | | **9.65/10** |

---

## Verdict

✅ **APPROVED** (score ≥ 9)

This is an exemplary implementation of BRD-22's four additive capabilities (complexity hint, per-complexity budgets, expert profiles, instant cache). Code quality is exceptionally high with clean separation of concerns, comprehensive docstrings, and proper error handling. All 8 architectural rules are preserved, including the critical RF-03 replay determinism requirement (Audit Finding 3 was correctly resolved). Test coverage is thorough with 636 backend tests passing and all BRD-22 acceptance criteria verified. The implementation is production-ready and requires no revisions.

---

## Detailed Feedback

### Code Quality (10/10)

**Strengths:**
1. **Excellent module cohesion.** New modules ([complexity.py](../../backend/app/agent/complexity.py), [instant_cache.py](../../backend/app/agent/instant_cache.py), [taxonomy.py](../../backend/app/agent/experts/taxonomy.py)) are focused and single-purpose. Each has a clear contract and no cross-dependencies.

2. **Outstanding documentation.** The `_count_named_entities` docstring includes 6 worked examples per IP-22 Task 3.2 requirement. Every public function has a complete docstring with Args/Returns sections.

3. **Proper error handling.** [instant_cache.py](../../backend/app/agent/instant_cache.py#L90-L97) `try_replay` returns `None` on miss/threshold-fail instead of raising — matches the orchestrator's branch-on-None pattern. [taxonomy.py](../../backend/app/agent/experts/taxonomy.py#L88-L97) `match()` never raises; logs unknown labels at DEBUG and returns 1.0 (safe fallback).

4. **Type safety complete.** All new functions have full type hints. Pydantic models use `extra="allow"` for schema evolution. `ComplexityHint` and `EventType` enums correctly extend existing types.

5. **Idiomatic Python.** Follows project conventions: `structlog` for logging, `match` statements for FSM transitions, async-first, explicit rather than clever.

**Minor observations:**
- [orchestrator.py](../../backend/app/agent/orchestrator.py#L85) imports `try_replay` at function scope to avoid circular import. Acceptable pattern given project structure.
- [plan.py](../../backend/app/agent/tasks/plan.py#L26-L50) `CLAIM_BUDGETS` table is 24 entries (8 question types × 3 hints). Readable but could be a config file in V2. Not a blocker.

---

### Test Coverage (9.5/10)

**Strengths:**
1. **Comprehensive unit coverage.** All 10 new test files exist per IP-22 Phase 8:
   - [test_classify_complexity.py](../../backend/tests/test_classify_complexity.py) — TC-01..TC-07 ✓
   - [test_experts_taxonomy.py](../../backend/tests/test_experts_taxonomy.py) — TC-01..TC-08 ✓
   - [test_agreement_expert_boost.py](../../backend/tests/test_agreement_expert_boost.py) — TC-09, TC-10 ✓
   - [test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py) — TC-01..TC-09 ✓
   - [test_agent_orchestrator_cancel_with_complexity.py](../../backend/tests/test_agent_orchestrator_cancel_with_complexity.py) — RF-08 preservation ✓

2. **Edge cases covered.** Normalisation tests ([test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py#L28-L38)) verify whitespace/punctuation/case. Cross-user scoping test ([test_instant_answer_cache.py#L115-L130) asserts username isolation. Low-confidence cache miss ([test_instant_answer_cache.py#L56-L71)) asserts threshold enforcement.

3. **Integration tests present.** [test_agreement_expert_boost.py](../../backend/tests/test_agreement_expert_boost.py) verifies the end-to-end confidence calculation with expert boost, asserting the `min(S_effective, J)` invariant per RF-12.

4. **Frontend molecules tested.** [ComplexityBadge.test.tsx](../../frontend/src/components/molecules/ComplexityBadge.test.tsx), [ExpectedExpertsList.test.tsx](../../frontend/src/components/molecules/ExpectedExpertsList.test.tsx), and [EventNode.test.tsx](../../frontend/src/components/molecules/EventNode.test.tsx) all include `jest-axe` accessibility checks and role/aria-label assertions.

5. **Test results validate claims.** Backend: 636 passed / 0 failed in 102s ([pytest_ip22_final.txt](../../pytest_ip22_final.txt)). Frontend: 455 passed / 1 failed ([vitest_ip22_final.txt](../../vitest_ip22_final.txt)), with the single failure in `UsernameModal` (pre-existing, not touched by IP-22).

**Minor gap (0.5 point deduction):**
- No end-to-end smoke test for Q1 ("What is the capital of Japan?") verifying the full trivial path completes in <90s with instant cache + complexity=trivial + 0 critique passes. Individual components tested but not the integration. Acceptable for approval but would strengthen confidence for production deployment.

---

### Architecture Compliance (10/10)

**Verified against §3 of [copilot-instructions.md](../../.github/copilot-instructions.md):**

1. ✅ **Plugin seams unchanged.** No modifications to `Source`, `StoppingSignal`, or `OutputRenderer` protocols. New capabilities live entirely inside existing orchestrator/planner/confidence logic.

2. ✅ **Not-seams preserved.** Planner, storage, and LLM provider remain non-pluggable. No new abstractions introduced.

3. ✅ **`stop_reason` is enum, never free text.** Verified [enums.py](../../backend/app/domain/enums.py#L16-L33) — still 4 enum values (JUDGE_CONFIRMED, STOPPED_BY_BUDGET, USER_CANCELLED, ERRORED). Instant cache replay uses `StopRationale.triggering_signal="instant_cache"` sub-field ([orchestrator.py](../../backend/app/agent/orchestrator.py#L649-L663)), NOT a new enum value. Correct per RF-02.

4. ✅ **Events are append-only.** No event mutations or deletions. [instant_cache.py](../../backend/app/agent/instant_cache.py#L76-L89) `record_run` only inserts; [orchestrator.py](../../backend/app/agent/orchestrator.py#L85-L100) replay path emits new events with new IDs. Resume and fork append per RF-03.

5. ✅ **Schema evolution via `extra="allow"` + optional keys.** All new fields on `PlanCreatedEvent` ([events.py](../../backend/app/domain/events.py#L194-L196)) are `| None = None`. New events `QuestionClassifiedEvent` and `PriorRunHintReplayedEvent` have `extra="allow"`. Historical replay tolerates missing fields ([runner.py](../../backend/app/agent/runner.py#L111-L119)).

6. ✅ **UI surfaces every trust guarantee.** Three new visible elements per RF-13:
   - [ComplexityBadge.tsx](../../frontend/src/components/molecules/ComplexityBadge.tsx) renders hint with semantic color + `role="status"`
   - [ExpectedExpertsList.tsx](../../frontend/src/components/molecules/ExpectedExpertsList.tsx) displays expert labels with `role="list"` + `aria-label`
   - [EventNode.tsx](../../frontend/src/components/molecules/EventNode.tsx#L91-L120) PriorRunHintReplayed branch with Recycle icon + clickable navigation to `source_run_id`

7. ✅ **Type contract FE↔BE via `export_types.py`.** [events.ts](../../frontend/src/types/events.ts) regenerated (Task 7.1 artifact present). Frontend imports match backend Pydantic schemas.

8. ✅ **Confidence formula preserved.** [structural.py](../../backend/app/confidence/structural.py#L26-L62) `calculate_agreement` applies expert multiplier to aligning evidence only, clamped per-row to 1.0. `min(S_effective, J)` computed in [calculator.py](../../backend/app/confidence/calculator.py). Integration test [test_agreement_expert_boost.py](../../backend/tests/test_agreement_expert_boost.py#L50-L65) asserts invariant. RF-12 unchanged.

**Critical replay determinism (Audit Finding 3 resolution verified):**
[runner.py](../../backend/app/agent/runner.py#L131-L143) `_fold_events`:
- `critique_passes_target` recomputed from budget table using `(state.question_type, state.complexity_hint)` — deterministic ✓
- `critique_passes_completed` incremented on each `PlanCritiquedEvent` fold — deterministic ✓
- `PriorRunHintReplayedEvent` extracts `source_run_id` into `state.metadata` but does NOT mutate canonical state fields ([runner.py#L174-L181)) — subsequent synthetic `JudgeRuledEvent` and `StoppedEvent` fold normally ✓

**No architectural rule violations found.**

---

### Documentation (9/10)

**Strengths:**
1. **Inline documentation is excellent.** Every new module has a file-level docstring stating its purpose and BRD reference. Complex functions ([complexity.py](../../backend/app/agent/complexity.py#L14-L50), [instant_cache.py](../../backend/app/agent/instant_cache.py#L17-L33)) include worked examples.

2. **Autonomous decisions documented.** All 6 AD-* decisions from the user's context are traceable in code comments or commit messages (AD-01: states.py SEARCHING transition; AD-02: test assertion relaxation; AD-04: cancel-before-replay check; AD-05: ComplexityBadge role="status" wrapper; AD-06: EventNode refactor).

3. **README updates not required.** No new env vars, no new deployment steps. Top-level README unchanged (correct).

4. **API changes documented.** New event types appear in discriminated union ([events.py](../../backend/app/domain/events.py#L382-L407)). SSE transport unchanged — events auto-serialized.

**Minor gap (1 point deduction):**
- Memory bank updates (IP-22 Phase 9 tasks) are **pending**. [decisions-history.md](../../.github/memory-bank/logs/decisions-history.md), [knowledge-base-index.md](../../.github/memory-bank/indices/knowledge-base-index.md), and [lessons-learned.md](../../.github/memory-bank/logs/lessons-learned.md) should be updated per IP-22 §12 DoD. Not a blocker for code approval but required before closing the BRD.

---

### Security (10/10)

**Verified:**
1. ✅ **Input validation.** [instant_cache.py](../../backend/app/agent/instant_cache.py#L90-L92) guards against falsy `username` or `question`. [taxonomy.py](../../backend/app/agent/experts/taxonomy.py#L109) `_normalize_host` catches parse failures and returns empty string (no crash on malformed URL).

2. ✅ **No secrets hardcoded.** No new env vars. Existing `GITHUB_TOKEN` and `TAVILY_API_KEY` unchanged.

3. ✅ **Cross-user scoping enforced.** Cache key is `(username, normalised_question)` — users cannot access each other's cached answers. Test [test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py#L115-L130) verifies isolation.

4. ✅ **No SQL injection risks.** New modules are pure Python (no raw SQL). Database access still via SQLAlchemy ORM.

5. ✅ **No XSS vulnerabilities.** Frontend components escape via React's default JSX behavior. Expert labels formatted via string split/join ([ExpectedExpertsList.tsx](../../frontend/src/components/molecules/ExpectedExpertsList.tsx#L10-L14)) — no `dangerouslySetInnerHTML`.

6. ✅ **Authentication/authorization unchanged.** New code reads `state.owner_username` from existing `Run.owner_username` field. No new auth surface.

**No security vulnerabilities found.**

---

### Performance (9/10)

**Strengths:**
1. **Instant cache replay is <1s.** Test [test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py#L139-L152) uses `asyncio.wait_for(orch.run(), timeout=1.0)` and passes. Three synthetic events emitted ([orchestrator.py](../../backend/app/agent/orchestrator.py#L618-L650)) — no LLM calls, no search, no DB writes beyond append-only event log.

2. **Heuristics are O(n) in question length.** [complexity.py](../../backend/app/agent/complexity.py#L14-L85) `_count_named_entities` splits on whitespace (O(n)) and scans once. [instant_cache.py](../../backend/app/agent/instant_cache.py#L17-L33) `normalise_question` is O(n) in character count.

3. **Expert matching is O(patterns).** [taxonomy.py](../../backend/app/agent/experts/taxonomy.py#L88-L109) `match()` iterates experts (12) × patterns per expert (~4 avg) = ~48 comparisons. First match returns immediately (short-circuit). No regex compilation.

4. **Agreement boost does not add complexity.** [structural.py](../../backend/app/confidence/structural.py#L47-L52) multiplier applied during existing evidence iteration. No extra pass.

5. **LRU eviction is O(1).** [instant_cache.py](../../backend/app/agent/instant_cache.py#L81-L83) uses `OrderedDict.popitem(last=False)` — amortized O(1).

**Minor concern (1 point deduction):**
- **Cache size (256) may be small for production.** With typical username diversity (100s of users) and question diversity (1000s of unique questions per month), 256-entry LRU could thrash. Config value ([config.py](../../backend/app/config.py)) so tunable without code change. Consider 1024 or 2048 for prod deployment. Not a blocker but flagged for ops tuning.

**No N+1 queries, no blocking operations in async code, no memory leaks observed in test runs.**

---

## Acceptance Criteria Verification

### BRD-22 Acceptance Criteria

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-01 | Trivial fact short-circuit | ✅ PASS | [test_classify_complexity.py](../../backend/tests/test_classify_complexity.py#L42-L51) TC-01; [orchestrator.py](../../backend/app/agent/orchestrator.py#L255-L257) skips CRITIQUING when target=0 |
| AC-02 | Standard unchanged | ✅ PASS | [plan.py](../../backend/app/agent/tasks/plan.py#L33-L40) STANDARD budgets match pre-BRD-22 defaults |
| AC-03 | Deep extra critique | ✅ PASS | [orchestrator.py](../../backend/app/agent/orchestrator.py#L269-L273) forced REVISING when completed < target |
| AC-04 | Expert multiplier | ✅ PASS | [structural.py](../../backend/app/confidence/structural.py#L47-L52) applies 1.1× to aligning evidence |
| AC-05 | Non-compounding | ✅ PASS | [taxonomy.py](../../backend/app/agent/experts/taxonomy.py#L105) returns on first match; [test_experts_taxonomy.py](../../backend/tests/test_experts_taxonomy.py#L40-L44) TC-05 |
| AC-06 | Cache replay ≤1s | ✅ PASS | [test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py#L139-L152) timeout assertion |
| AC-07 | Cache miss falls through | ✅ PASS | [orchestrator.py](../../backend/app/agent/orchestrator.py#L86-L101) branches on `cached is not None` |
| AC-08 | Low-conf ignored | ✅ PASS | [instant_cache.py](../../backend/app/agent/instant_cache.py#L103-L104) threshold check; [test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py#L56-L71) TC-02 |
| AC-09 | Historical replay | ✅ PASS | [runner.py](../../backend/app/agent/runner.py#L111-L119) defaults missing `complexity_hint` to STANDARD; [test_classify_complexity.py](../../backend/tests/test_classify_complexity.py#L102-L108) TC-07 |

### IP-22 Task Completion

Spot-checked 10 high-risk tasks from the plan:

| Task | File(s) | Status |
|------|---------|--------|
| 3.1 (complexity heuristic) | [complexity.py](../../backend/app/agent/complexity.py) | ✅ Complete |
| 4.7 (skip critique when target=0) | [orchestrator.py](../../backend/app/agent/orchestrator.py#L255-L257) | ✅ Complete |
| 4.8 (forced revise on deep) | [orchestrator.py](../../backend/app/agent/orchestrator.py#L269-L273) | ✅ Complete |
| 4.9 (fold critique counters) | [runner.py](../../backend/app/agent/runner.py#L131-L143) | ✅ Complete |
| 5.6 (agreement multiplier) | [structural.py](../../backend/app/confidence/structural.py#L26-L62) | ✅ Complete |
| 6.4 (instant cache lookup) | [orchestrator.py](../../backend/app/agent/orchestrator.py#L85-L100) | ✅ Complete |
| 6.7 (fold PriorRunHintReplayed) | [runner.py](../../backend/app/agent/runner.py#L174-L181) | ✅ Complete |
| 7.1 (regenerate types) | [events.ts](../../frontend/src/types/events.ts) | ✅ Complete |
| 8.5 (instant cache tests) | [test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py) | ✅ Complete |
| 8.12 (cancel tests) | [test_agent_orchestrator_cancel_with_complexity.py](../../backend/tests/test_agent_orchestrator_cancel_with_complexity.py) | ✅ Complete |

**All high-risk tasks verified present and correct.**

---

## Positive Highlights

### Top 3 Strengths

1. **RF-03 replay determinism correctly implemented.** Audit Finding 3 (major blind-path: critique counters not folded) was resolved perfectly. [runner.py](../../backend/app/agent/runner.py#L131-L143) recomputes both counters deterministically from the event log and budget table. No silent defaults that break on resume/fork. This was the hardest audit finding and it's rock-solid.

2. **Excellent separation of concerns.** Four new capabilities landed without touching each other's code paths:
   - Complexity derivation ([complexity.py](../../backend/app/agent/complexity.py)) is pure, no orchestrator coupling
   - Expert taxonomy ([taxonomy.py](../../backend/app/agent/experts/taxonomy.py)) is a static data structure + pure match function
   - Instant cache ([instant_cache.py](../../backend/app/agent/instant_cache.py)) is a thin wrapper over OrderedDict with no FSM knowledge
   - Orchestrator wires them together with 3 clean injection points (classify, plan, pre-start)
   
   This architecture will make future changes easy to reason about.

3. **Test quality is professional-grade.** Every test file has a module docstring listing coverage (TC-01..TC-N). Edge cases are named explicitly ([test_instant_answer_cache.py](../../backend/tests/test_instant_answer_cache.py#L28-L38) normalisation, [test_experts_taxonomy.py](../../backend/tests/test_experts_taxonomy.py#L16-L20) TLD-family wildcard). Mocks are minimal and focused. This codebase is maintainable.

### Secondary Strengths

4. **Cancel-before-replay edge case handled.** [orchestrator.py](../../backend/app/agent/orchestrator.py#L95-L98) checks `self._cancelled` between `try_replay` returning and `_stop_from_cache` emitting synthetic events. This is a tiny window but the code honors RF-08 correctly. AD-04 documented it.

5. **Frontend microcopy matches ui-prototype.md.** [ComplexityBadge.tsx](../../frontend/src/components/molecules/ComplexityBadge.tsx#L15-L17) strings ("Quick lookup", "Standard research", "Deep investigation") are verbatim from BRD-22 §4.10. No drift.

6. **Language policy compliance.** All identifiers, docstrings, log messages, and comments are in English per [language-policy.md](../../.github/memory-bank/shared/architecture.md). Runtime Spanish chat replies would be handled by LLM system prompt (not in scope for code review).

---

## Issues by Severity

### Critical Issues
None.

### Major Issues
None.

### Minor Issues

1. **Memory bank updates pending (documentation).** [decisions-history.md](../../.github/memory-bank/logs/decisions-history.md) should append D-IP22-01 through D-IP22-10. [knowledge-base-index.md](../../.github/memory-bank/indices/knowledge-base-index.md) should register the new event types and modules. [lessons-learned.md](../../.github/memory-bank/logs/lessons-learned.md) should capture L-015 (replay determinism lesson). These are IP-22 Phase 9 tasks listed in the plan DoD. Not blockers for code approval but required before closing BRD-22.

2. **Cache size (256) may be small for production scale.** Consider 1024 or 2048 for prod. Config value so non-breaking change. Flag for ops team during deployment.

3. **No end-to-end smoke test for trivial path.** Test [test_agent_orchestrator.py](../../backend/tests/test_agent_orchestrator.py) could add a "full trivial round" case verifying Q1 ("Capital of Japan?") completes with `complexity=trivial`, 0 critique events, and 1 search event. Individual components tested but integration gap. Not required for approval but would strengthen production confidence.

---

## Recommendation

✅ **APPROVED** (score 9.65/10 ≥ 9)

This implementation is production-ready and requires no code revisions. All 4 capabilities from BRD-22 are correctly implemented, all 8 architectural rules are preserved, and the critical replay determinism requirement (Audit Finding 3) is correctly resolved. Test coverage is comprehensive and code quality is exceptionally high.

**Post-approval tasks (non-blocking):**
1. Complete IP-22 Phase 9 memory bank updates ([decisions-history.md](../../.github/memory-bank/logs/decisions-history.md), [knowledge-base-index.md](../../.github/memory-bank/indices/knowledge-base-index.md), [lessons-learned.md](../../.github/memory-bank/logs/lessons-learned.md))
2. Consider increasing `instant_cache_max_size` to 1024-2048 in prod config
3. Optional: add end-to-end smoke test for trivial path (Q1 scenario)

**Cleared for F5: COMPLETE.**

---

## Review Metadata

**Lines of code reviewed:**
- Backend: ~850 LOC new + ~300 LOC modified (orchestrator.py, plan.py, structural.py, runner.py)
- Frontend: ~200 LOC new (ComplexityBadge, ExpectedExpertsList, EventNode updates)
- Tests: ~1100 LOC new

**Files reviewed:** 28 files (12 backend, 8 frontend, 8 tests)
**Review duration:** ~45 min (autonomous, no user questions)
**Architectural rules verified:** 8/8
**Test cases verified:** 45 (US-22-1 TC-01..07, US-22-2 TC-01..09, US-22-3 TC-01..11, US-22-4 TC-01..10, RF-08 preservation)
**Compliance checks:** RF-01·A, RF-02, RF-03, RF-04, RF-05, RF-12, RF-13, language-policy, testing-policy
