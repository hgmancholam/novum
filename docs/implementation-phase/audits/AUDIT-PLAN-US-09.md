# Audit Report — IP-09 Stopping Signal Policy

<!-- STATUS HEADER — overwritten on every iteration -->
**Artifact:** PLAN-US-09 ([IP-09-stopping-signals.md](../implementation-plans/IP-09-stopping-signals.md))
**Phase:** F2 (PLAN)
**Auditor:** Auditor Agent
**Latest Iteration:** 1
**Latest Date:** 2026-05-26
**Latest Score:** 9.75/10
**Latest Verdict:** ✅ APPROVED

**Iteration Log:**

| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-26 | 9.75 | ✅ APPROVED |

---

## Iter 1 — 2026-05-26

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 10/10 | 30% | 3.00 |
| Acceptance Criteria Completeness | 10/10 | 20% | 2.00 |
| Blind-Path Absence | 9/10 | 25% | 2.25 |
| Traceability | 10/10 | 15% | 1.50 |
| Consistency w/ docs | 10/10 | 10% | 1.00 |
| **TOTAL** | | | **9.75/10** |

### 2. Verdict

✅ **APPROVED** (score ≥ 9). Proceed to **F3: IMPLEMENT** (hand off to Coder).

### 3. Requirements Coverage Matrix

| RF | Covered? | Where in IP-09 | Notes |
|---|---|---|---|
| RF-01 (autonomous stopping, 7 stop_reason values) | ✅ | §1 (scope), §5.1 (`StopReason` typing), §5.5 (3 handler edits) | All 5 in-scope `stop_reason` values reachable: `JUDGE_CONFIRMED` (JudgeSignal), `STOPPED_BY_BUDGET` (BudgetSignal + judge-attempts inline), `HONEST_CONTRADICTION` / `HONEST_AMBIGUOUS` / `HONEST_UNANSWERABLE` (HonestStopSignal). `USER_CANCELLED` and `ERRORED` remain owned by `AgentOrchestrator.run()` / `_handle_error` — out of scope (cancellation lives at the top of the FSM loop and is untouched). |
| RF-04 (honest stops) | ✅ | §5.5 Edit A/B/C, §7.5 HonestStopSignal tests | Contradiction, ambiguity, unanswerable each have a dedicated branch and ≥ 2 tests. |
| RF-12 (`final = min(S, J)`) | ✅ | §2 row "rule #8", §5.5 Edit C, §7.6 `test_judge_final_uses_min_S_J` | Single call to `calculate_structural_confidence(state)` per evaluate; min computed inside `JudgeSignal`. |
| RF-15 (disconfirmation independence) | ✅ | §5.5 Edit C (preserves `detect_mismatch` block) + O-04 | Coverage / agreement gates inside `JudgeSignal` prevent judge-only confirmation, which is exactly the RF-15 guarantee at the policy layer. |

No RF declared in scope is left uncovered.

### 4. Blind-Path Findings

Running the 8-item Blind-Path Detection Checklist:

| # | Check | Status | Notes |
|---|---|---|---|
| 1 | Path completeness in the 3 edited handlers | ✅ | Every branch in §5.5 Edit A/B/C ends in `transition_to`, `_stop`, or `return`. The defensive `_stop(HONEST_UNANSWERABLE)` fallback in Edit B covers the impossible `total_claims == 0` case. |
| 2 | Error handling | ✅ | Signals are pure; the policy is wrapped by the orchestrator's outer `try/except` (orchestrator.py:96-103, unchanged). Risk §9 row 10 replaces bare `assert` with `RuntimeError` for `PYTHONOPTIMIZE` safety. |
| 3 | User feedback continuity | ✅ | No new events; the existing `StoppedEvent` carries `stop_reason`. No FE state can be orphaned. |
| 4 | Terminal reachability (all 7 `stop_reason`) | ✅ | See §3 above. The 5 in-scope reasons are reachable; the 2 out-of-scope ones (`USER_CANCELLED`, `ERRORED`) remain reachable in unchanged code paths. |
| 5 | Cancellation honored | ✅ | `self._cancelled` check at the top of the FSM loop (orchestrator.py:84-85) is **not** modified. The plan correctly scopes edits to body handlers, not the loop header. |
| 6 | Resume coverage | ✅ | No new event types → no new resume paths required. `has_ambiguity` is a `RunState` field, not an event — and §11 explicitly defers the emitter, so no false promise is made. |
| 7 | Budget cap reachable | ✅ | `BudgetSignal` fires on `search_count >= max_searches` (O-03); judge-attempts cap fires inline in `_handle_judging` (O-07). Both map to `STOPPED_BY_BUDGET`. |
| 8 | Schema evolution backward-compat | ✅ | Only `RunState.has_ambiguity: bool = False` is added; `RunState` already has `ConfigDict(extra="allow")` (verified at [run_state.py:42](../../../backend/app/agent/run_state.py)). No new event fields. |

**Minor narrative gap (item 1, partial deduction):** §5.5 Edit A states the policy is called at the top of `_handle_searching`. If `HonestStopSignal` fires there with `covered_claims` already populated (e.g. contradictions detected in the prior `_handle_analyzing` tick), the run stops without drafting the partial answer. This is arguably correct per RF-04 (honest contradiction overrides a partial draft) but the prose only justifies the *budget* override of partial drafts in Edit B; it does not address the *honest-stop* case in Edit A. One-line clarification suffices — see §5 below.

### 5. Required Changes (none blocking)

The plan is approved as-is. The following are **non-blocking nits** the Coder may fold into the PR description or as inline comments; they do **not** require returning to the Orchestrator:

1. **[Minor]** `IP-09 §5.5 Edit A` — add a one-line note clarifying that if `HonestStopSignal` fires when `state.covered_claims` is non-empty, the partial draft is discarded by design (RF-04 precedence over partial answers). Mirrors the symmetric explanation already present in Edit B for the budget case.
2. **[Minor]** `IP-09 §7.5` — rename `test_honest_contradiction_low_priority_when_resolved` to `test_honest_contradiction_defers_when_no_conflict_high`. The current name implies a priority mechanism, but the assertion is actually about the `no_conflict ≥ 0.3` defer branch.
3. **[Minor]** `IP-09 §7.7 row test_policy_uses_structural_confidence_once` — prefer injecting a recording fake signal via the new `StoppingPolicy(signals=…)` kwarg over monkey-patching `app.confidence.calculate_structural_confidence`. Reason: BRD-08 is being implemented in parallel and may move the import surface; the kwarg path is contract-stable.

### 6. Positive Highlights (informational)

- **O-03** (`search_count` vs `iteration_count`) catches a real bug in BRD-09 §4.5: mapping `state.iteration_count → max_iterations` would have fired `BudgetSignal` after ~5 search rounds because each search round consumes multiple FSM ticks. Correctly traced to `orchestrator.py:81`.
- **O-04** (coverage + agreement gates inside `JudgeSignal`) fixes a real contradiction in BRD-09 AC-03: without these gates, judge sycophancy (high `J`, low `S`) would emit `JUDGE_CONFIRMED` even when coverage/agreement were below threshold — directly violating RF-15. The fix is centralised inside `JudgeSignal` (not split between Coverage/Agreement signal ordering), which removes any dependency on signal-ordering correctness.
- **O-06** (all-claims-failed instead of half-uncoverable) prevents the policy from orphaning a draftable answer. Correctly cross-referenced against the existing `orchestrator.py:170` safety net.
- **O-07** correctly preserves the `judge_attempts` sub-loop counter as a separate inline safety net, avoiding the coupling trap of folding two independent budgets into one signal.
- **O-08** (no module-level singleton) plus the `stopping_policy: StoppingPolicy | None = None` ctor kwarg gives tests a clean injection point with zero monkey-patching.
- **BRD-08 boundary** in §3 is unusually explicit — explicit row-by-row ownership table, named line ranges for the disjoint edits, and an explicit canary (the orchestrator suite). This is the right defensive posture for two parallel sessions.
- **Test plan completeness:** §7 enumerates ~51 tests across 5 files (well above the ≥ 30 claim); §8 maps every BRD-09 AC to ≥ 2 test IDs.
- **Done definition (§10):** measurable, file-level, and ties back to §3's BRD-08 boundary (explicit "NO touches to the BRD-08 divergence / `detect_mismatch` block").
- **Risks (§9):** 10 risks, each with a concrete mitigation. The `assert` → `RuntimeError` swap under `PYTHONOPTIMIZE` is a non-obvious correctness fix that many plans miss.

### 7. Scope Self-Check

For each item flagged above, verified:

- [x] All findings fall within IP-09's declared scope (the 3 orchestrator edits + the `app/stopping/` package + the one `RunState` field + the listed test files).
- [x] No finding crosses into BRD-08 territory (`app/confidence/**`, `detect_mismatch`, `ConfidenceMismatchEvent`).
- [x] No finding demands work owned by future BRDs (`AmbiguityDetectedEvent` emitter, `DomainSafety`, `ConfidencePlateau`, adaptive thresholds — all correctly deferred in §11).
- [x] No finding maps to an RF outside `{RF-01, RF-04, RF-12, RF-15}`.

### 8. Architectural Compliance (copilot-instructions.md §3, 8 rules)

| Rule | Verdict | Evidence |
|---|---|---|
| #1 Three plugin seams | ✅ | New `StoppingSignal` Protocol in `app/seams/stopping.py` alongside `app/seams/source.py`. |
| #2 Three not-seams | ✅ | `StoppingPolicy` is a concrete class, not a Protocol. New signals plug behind `StoppingSignal`, not behind a "policy" abstraction. |
| #3 `stop_reason` is enum | ✅ | `StopSignalOutput.stop_reason: StopReason \| None`; invariant `STOP ⇒ stop_reason is not None` enforced in `__post_init__`. |
| #4 Events are append-only | ✅ | Zero new events; `StoppedEvent` continues to carry `stop_reason`. |
| #5 `extra="allow"` for schema evolution | ✅ | Only an optional `RunState.has_ambiguity: bool = False` is added; `RunState` already has `ConfigDict(extra="allow")`. |
| #6 UI surfaces every trust guarantee | ✅ N/A | No FE work in this BRD; existing renderer (BRD-13) already shows `stop_reason`. |
| #7 FE↔BE type contract | ✅ | No event-shape changes; `scripts/export_types.py` correctly NOT re-run. |
| #8 `final_confidence = min(S, J)` | ✅ | Single call to `calculate_structural_confidence(state)` per `evaluate`; `min(S, J)` computed inside `JudgeSignal` exactly once. |

### 9. Override Soundness Audit (O-01 … O-10)

| Override | Justified? | Internally consistent? | Introduces contradiction? | Verdict |
|---|---|---|---|---|
| O-01 frozen dataclasses | ✅ (mirrors `MismatchResult`) | ✅ | ❌ | Accept |
| O-02 PEP 604 unions | ✅ (repo convention) | ✅ | ❌ | Accept |
| O-03 `search_count` rename | ✅ (real bug fix, see §6) | ✅ | ❌ | Accept |
| O-04 Judge gates on coverage+agreement | ✅ (fixes AC-03 semantic, see §6) | ✅ | ❌ (aligns AC-03 with its own Gherkin) | Accept |
| O-05 `has_ambiguity` on `RunState` | ✅ (avoids dead literal) | ✅ | ❌ (emitter deferred in §11) | Accept |
| O-06 all-claims-failed condition | ✅ (preserves existing semantics) | ✅ | ❌ | Accept |
| O-07 judge-attempts stays inline | ✅ (two independent budgets) | ✅ | ❌ | Accept |
| O-08 no singleton, ctor injection | ✅ (test isolation) | ✅ | ❌ | Accept |
| O-09 kw-only `judge_confidence` | ✅ (call-site safety) | ✅ | ❌ | Accept |
| O-10 stable structlog keys | ✅ (repo convention) | ✅ | ❌ | Accept |

All 10 overrides are sound. No new contradictions introduced.

### 10. Integration Correctness (the 3 orchestrator edits)

| Pre-IP-09 stop path | Where it lived | Post-IP-09 home | Equivalent? |
|---|---|---|---|
| `search_count >= max_searches` at top of `_handle_searching` (orchestrator.py:144-146) | inline | `BudgetSignal` via Edit A | ✅ exact `>=` preserved |
| `all_claims_resolved() and not covered_claims and search_count >= max` → BUDGET (orchestrator.py:158-159) | inline | Edit B branch via policy | ✅ |
| `all_claims_resolved() and not covered_claims` → HONEST_UNANSWERABLE (orchestrator.py:160-161) | inline | `HonestStopSignal` via Edit B (O-06) | ✅ (`all_resolved && covered==0`) |
| `coverage_ratio() == 0.0 and search_count >= 5` → HONEST_UNANSWERABLE (orchestrator.py:167-171) | inline (`_HONEST_UNANSWERABLE_SAFETY_ROUNDS = 5`) | Subsumed by `HonestStopSignal` (O-06) once all claims are marked uncoverable by `analyze_evidence` | ⚠️ stronger condition (waits until all resolved). Risk §9 row 2 explicitly calls out the fixture choice. |
| `search_count >= max and covered_claims` → DRAFTING (orchestrator.py:179-180) | inline | Edit B special-cases `result.stop_reason is STOPPED_BY_BUDGET and covered_claims` → DRAFTING | ✅ |
| `search_count >= max and not covered_claims` → BUDGET (orchestrator.py:181-182) | inline | `BudgetSignal` via Edit B | ✅ |
| `judge_event.passed` → JUDGE_CONFIRMED (orchestrator.py:191-193) | inline | `JudgeSignal` via Edit C | ⚠️ stricter (adds O-04 gates). Risk §9 row 3 explicitly flags the happy-path fixture audit. |
| `judge_attempts >= max_judge_attempts` → BUDGET (orchestrator.py:195-198) | inline | inline (Edit C, **kept** per O-07) | ✅ exact |
| `detect_mismatch` divergence block (orchestrator.py:200-217) | inline (BRD-08) | inline (BRD-08, **untouched**) | ✅ boundary respected |

Every legal FSM transition (`SEARCHING → ANALYZING`, `ANALYZING → SEARCHING|DRAFTING`, `JUDGING → SEARCHING|STOPPED`) is preserved. No new transitions introduced; `app/agent/states.py` is correctly identified as out-of-scope (read-only). The deleted `_HONEST_UNANSWERABLE_SAFETY_ROUNDS = 5` is replaced by the **stricter** all-claims-resolved condition (O-06) — the two flagged behaviour deltas (rows ⚠️) are explicitly disclosed in §9 risks 2 and 3 with named mitigations in §7.8.

### 11. Test Plan Completeness

| Required coverage | Found? | Tests |
|---|---|---|
| Happy path per signal | ✅ | §7.2–7.6, every signal has ≥ 1 success case |
| Boundary per signal | ✅ | §7.2 `_at_threshold_defers`, §7.4 `_at_limit_stops` / `_over_limit_stops`, §7.5 `_no_unanswerable_when_zero_claims` |
| Failure / negative per signal | ✅ | §7.5 `_no_unanswerable_when_partially_covered`, §7.6 `_coverage_gate_blocks` / `_agreement_gate_blocks` |
| Policy ordering | ✅ | §7.7 `_default_signal_order`, `_honest_fires_before_budget`, `_budget_fires_before_judge` |
| Policy injection (O-08) | ✅ | §7.7 `_custom_signal_set` + §7.8 `_uses_injected_policy` |
| Orchestrator regression preserved | ✅ | §7.8 row-by-row delta with the canary command in §6 step 15 |
| AC → test mapping | ✅ | §8, every AC ≥ 2 tests |

### 12. Next Step

✅ APPROVED → proceed to **F3: IMPLEMENT**. Hand off to Coder.

The Coder should:
1. Apply the 3 non-blocking nits in §5 above (rename test, add one prose line to Edit A, swap monkey-patch for fake-signal injection).
2. Run the canary `pytest tests/test_agent_orchestrator.py -v` **immediately after step 11** of §6 to detect any BRD-08 merge surprise.
3. Resolve the fixture choice flagged in §9 risks 2 and 3 (smaller diff wins; document in PR).
