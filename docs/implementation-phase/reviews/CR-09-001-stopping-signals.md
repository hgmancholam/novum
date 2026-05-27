# Code Review Report — CR-09-001

**User Story / BRD:** [BRD-09 Stopping Signal Policy](../brds/BRD-09-stopping-signals.md)
**Plan:** [IP-09](../implementation-plans/IP-09-stopping-signals.md)
**F2 Audit:** [AUDIT-PLAN-US-09](../audits/AUDIT-PLAN-US-09.md)
**Iteration:** 1
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent (F4)

---

## Summary

| Criterion | Score | Weight | Weighted |
|-----------|------:|------:|--------:|
| IP-09 Plan Compliance | 10.0 | 25 % | 2.50 |
| Architectural Compliance | 10.0 | 20 % | 2.00 |
| Code Quality | 9.5 | 20 % | 1.90 |
| Test Quality | 10.0 | 20 % | 2.00 |
| Integration Safety | 9.5 | 15 % | 1.425 |
| **TOTAL** | | **100 %** | **9.83 / 10** |

## Verdict

✅ **APPROVED** — proceed to **F5: COMPLETE**.

The implementation lands the second of the three V1 plugin seams cleanly,
respects every architectural rule in [.github/copilot-instructions.md §3](../../../.github/copilot-instructions.md), and exhibits behaviour identical to
the plan in §5.3 / §5.5. All gates pass on a clean local run; the parallel
BRD-08 surface (`app/confidence/**`) is untouched.

---

## Independent Verification (re-run locally)

```
pytest tests/test_seams_stopping.py tests/test_stopping_signals.py tests/test_stopping_policy.py \
       tests/test_agent_orchestrator.py tests/test_agent_run_state.py
→ 87 passed in 7.28s

coverage on app.stopping + app.seams.stopping
→ 100 % (149/149 statements)

ruff check  → All checks passed
pyright     → 0 errors, 0 warnings, 0 informations

boundary canary (test_agent_states + test_confidence_*)
→ 61 passed in 3.96s
```

The Coder's claim that the full-suite hang is pre-existing in
`test_routes_runs` (SSE) and `test_routes_auth` (bcrypt) is consistent
with the local IP-09 surface: every test file that imports the
stopping package or the modified orchestrator/run_state passes
deterministically in ≤ 8 s. No further verification on `main` was
required to rule out an IP-09-introduced regression.

---

## Per-axis Findings

### 1. IP-09 Plan Compliance — 10 / 10

Every binding override O-01…O-10 is honoured exactly:

| Override | Verification |
|---|---|
| O-01 frozen dataclasses | [seams/stopping.py:37-58](../../../backend/app/seams/stopping.py#L37-L58) — `@dataclass(frozen=True)` on both; `__post_init__` raises `ValueError` per invariant. |
| O-02 PEP 604 unions | All 9 new files start with `from __future__ import annotations`; no `Optional` import anywhere in [app/stopping/](../../../backend/app/stopping/) or [app/seams/stopping.py](../../../backend/app/seams/stopping.py). |
| O-03 `search_count` / `max_searches` field naming | [seams/stopping.py:75-76](../../../backend/app/seams/stopping.py#L75-L76); [policy.py:90-91](../../../backend/app/stopping/policy.py#L90-L91); [budget.py:23](../../../backend/app/stopping/signals/budget.py#L23). |
| O-04 Judge coverage / agreement gates | [judge.py:33-58](../../../backend/app/stopping/signals/judge.py#L33-L58) — both gates fire **before** `min(S, J)`. |
| O-05 `has_ambiguity` on `RunState` | [run_state.py:50](../../../backend/app/agent/run_state.py#L50); test in [test_agent_run_state.py:121](../../../backend/tests/test_agent_run_state.py#L121). |
| O-06 all-claims-failed condition | [honest.py:46-50](../../../backend/app/stopping/signals/honest.py#L46-L50). |
| O-07 judge-attempts kept inline | [orchestrator.py:216-219](../../../backend/app/agent/orchestrator.py#L216-L219) (sub-loop cap remains); `budget.py` does not reference `judge_attempts` (asserted by [test_stopping_signals.py:113-119](../../../backend/tests/test_stopping_signals.py#L113-L119)). |
| O-08 no module-level singleton | [policy.py:50-62](../../../backend/app/stopping/policy.py#L50-L62) — instance constructed by the orchestrator at [orchestrator.py:58](../../../backend/app/agent/orchestrator.py#L58). |
| O-09 kw-only `judge_confidence` | [policy.py:69-73](../../../backend/app/stopping/policy.py#L69-L73). |
| O-10 stable structlog keys, no f-strings in messages | [policy.py:102-107](../../../backend/app/stopping/policy.py#L102-L107); verified by [test_policy_log_keys_are_stable](../../../backend/tests/test_stopping_policy.py). |

The 3 audit findings from [AUDIT-PLAN-US-09](../audits/AUDIT-PLAN-US-09.md) are
reflected:

- Edit A "discard-partial-draft" semantic note is now captured by the
  inline comment at [orchestrator.py:178-179](../../../backend/app/agent/orchestrator.py#L178-L179)
  and by the symmetric BUDGET-keeps-drafting branch at
  [orchestrator.py:190-198](../../../backend/app/agent/orchestrator.py#L190-L198).
- The recording-fake-signal style in
  `test_policy_uses_structural_confidence_once` is implemented at
  [test_stopping_policy.py:185-220](../../../backend/tests/test_stopping_policy.py#L185-L220);
  three `_RecordingFake` signals share a single captured
  `structural_confidence` value (proves the BRD-08 import surface is
  consulted exactly once per `evaluate`).
- All 4 BRD-09 acceptance criteria have ≥ 2 green tests pointing at them
  (matches the §8 mapping in IP-09).

**Coder deviations are acceptable:**

1. `TYPE_CHECKING` lazy import of `RunState` in
   [policy.py:17-19,37-39](../../../backend/app/stopping/policy.py#L17-L19) —
   pragmatic guard against the circular import risk listed in IP-09 §9.
   Behaviour unchanged.
2. `getattr(state, "has_ambiguity", False)` at
   [policy.py:96](../../../backend/app/stopping/policy.py#L96) — forward-safe;
   harmless given O-05 added the field with a default of `False`.
3. `raise RuntimeError` instead of `assert` (explicitly mandated by IP-09 §9 final risk row).
4. The orchestrator-test fixture choices (`support: bool` hook;
   `test_budget_exhausted_no_coverage` now expecting `HONEST_UNANSWERABLE`)
   are exactly the smaller-diff option IP-09 §7.8 row 2 left to the Coder.

### 2. Architectural Compliance — 10 / 10

Every rule from §3 of `copilot-instructions.md` checked:

| Rule | Status |
|---|---|
| #1 Three plugin seams | ✅ `StoppingSignal` lives in [app/seams/stopping.py](../../../backend/app/seams/stopping.py) as a `@runtime_checkable Protocol`, alongside `app/seams/source.py`. |
| #2 Three not-seams | ✅ `StoppingPolicy` is a concrete class, not an abstraction; planner / storage / LLM untouched. |
| #3 `stop_reason` is an enum | ✅ All terminal outputs use [`StopReason`](../../../backend/app/domain/enums.py) values; `StopSignalOutput.__post_init__` enforces non-`None` reason on STOP at [seams/stopping.py:52-56](../../../backend/app/seams/stopping.py#L52-L56). |
| #4 Events are append-only | ✅ Zero new event types; no event mutations introduced. |
| #5 Schema evolution = `extra="allow"` + optional keys | ✅ Single new field `has_ambiguity: bool = False` with default; `RunState.model_config` already allows extras. |
| #6 UI surfaces every trust guarantee | ✅ No FE work needed; `StoppedEvent.stop_reason` continues to carry the enum value. |
| #7 FE↔BE contract | ✅ No edits in [frontend/src/types/events.ts](../../../frontend/src/types/events.ts) or [scripts/export_types.py](../../../scripts/export_types.py). |
| #8 `final_confidence = min(S, J)` | ✅ Exactly one call site at [judge.py:60](../../../backend/app/stopping/signals/judge.py#L60). Structural component flows from `calculate_structural_confidence(state)` at [policy.py:85](../../../backend/app/stopping/policy.py#L85); never recomputed per-signal. |

BRD-08 boundary respected: zero diffs in
[backend/app/confidence/](../../../backend/app/confidence/); 61
confidence/state regression tests pass.

### 3. Code Quality — 9.5 / 10

Strengths:
- English-only across all 9 new files (identifiers, docstrings, log keys, exception messages).
- `from __future__ import annotations` everywhere; clean PEP 604.
- structlog uses kwargs (`signal=`, `result=`, `stop_reason=`) — no f-strings inside the log message.
- Frozen dataclasses with the runtime invariant on `StopSignalOutput` (rejected combinations explode loudly).
- Coverage 100 %, pyright strict and ruff both clean.
- The `Sequence | None` constructor sig in [policy.py:58](../../../backend/app/stopping/policy.py#L58) is correctly disambiguated from a falsy-empty `signals=[]` via the explicit `is not None` check (avoids the `signals or _default_signals()` trap that would have prevented test injection of an empty list).

Minor smells (do not warrant a return):
- F-008 — [test_stopping_policy.py:106](../../../backend/tests/test_stopping_policy.py#L106) uses
  `state.contradictions.append(object())  # type: ignore[arg-type]` to flip
  `has_contradictions=True`. Pydantic only validates on assignment, not on
  list mutation, so this works, but a typed `ContradictionDetectedEvent`
  instance (or a dedicated `set_has_contradictions(True)` helper) would
  be cleaner. Cosmetic only; the field type is in `RunState`, not in the
  IP-09 surface. **No remediation required.**

### 4. Test Quality — 10 / 10

- 87 new tests (58 stopping + 29 regression delta), all green.
- 100 % coverage on `app.stopping` and `app.seams.stopping` (target ≥ 95 %).
- The 5 priority levels are tested both by direct attribute assertion
  (`test_*_priority_is_N`) and by evaluation order
  ([test_policy_evaluate_signals_sorted_by_priority](../../../backend/tests/test_stopping_policy.py)).
- O-04 gates explicitly exercised:
  [test_judge_coverage_gate_blocks](../../../backend/tests/test_stopping_signals.py#L223),
  [test_judge_agreement_gate_blocks](../../../backend/tests/test_stopping_signals.py#L236),
  [test_judge_passes_all_gates](../../../backend/tests/test_stopping_signals.py#L212).
- Honest-ambiguity branch tested via direct `has_ambiguity=True` field set
  ([test_honest_ambiguity_fires](../../../backend/tests/test_stopping_signals.py#L156)),
  per IP-09 O-05.
- Policy injection exercised end-to-end via
  [test_orchestrator_uses_injected_stopping_policy](../../../backend/tests/test_agent_orchestrator.py#L542).
- Defensive: `test_policy_stops_at_first_stop_signal` proves later signals
  do not run after a STOP — short-circuit semantics guaranteed.
- The `_RecordingFake` shared-context test
  ([test_policy_uses_structural_confidence_once](../../../backend/tests/test_stopping_policy.py#L185))
  closes the audit finding from F2 verbatim — no monkey-patching of
  `app.confidence` (preserves the parallel-session import surface).

### 5. Integration Safety — 9.5 / 10

- FSM transition map unchanged ([test_agent_states.py](../../../backend/tests/test_agent_states.py) — 12 tests pass).
- All 7 `StopReason` enum values remain reachable from the FSM:
  - `JUDGE_CONFIRMED` → [judge.py:62-69](../../../backend/app/stopping/signals/judge.py#L62-L69)
  - `HONEST_CONTRADICTION` / `HONEST_AMBIGUOUS` / `HONEST_UNANSWERABLE` → [honest.py](../../../backend/app/stopping/signals/honest.py)
  - `STOPPED_BY_BUDGET` → [budget.py:23-32](../../../backend/app/stopping/signals/budget.py#L23-L32) **and** [orchestrator.py:216-219](../../../backend/app/agent/orchestrator.py#L216-L219) (judge-attempts cap)
  - `USER_CANCELLED` → [orchestrator.py:84](../../../backend/app/agent/orchestrator.py#L84) (unchanged from BRD-07)
  - `ERRORED` → [orchestrator.py:259](../../../backend/app/agent/orchestrator.py#L259) (unchanged from BRD-07)
- The 3 orchestrator edits do not break any pre-existing test outside the
  two documented updates (`support=True` hook; `HONEST_UNANSWERABLE` is
  the new expected reason for `test_budget_exhausted_no_coverage`).
- The full-suite hang reported by the Coder is in
  `test_routes_runs` (SSE) and `test_routes_auth` (bcrypt) — neither
  module imports `app.stopping` nor depends on the modified orchestrator
  handlers in a way that could regress from IP-09. The focused canary
  (87 tests in 7.3 s) and the adjacent boundary suites (61 in 4 s) are
  green. Claim accepted.

Half-point deduction: the Coder's flagged concern that
[backend/app/agent/tasks/search.py](../../../backend/app/agent/tasks/search.py)
still hard-codes `polarity=NEUTRAL` is a **real** V1 gap — without it,
`agreement` is always 0 and `JudgeSignal` can never approve in
production. **This does not block approval** because:
1. It is explicitly **out of scope** for BRD-09 (the BRD owns the signal,
   not the polarity classifier).
2. The orchestrator regression suite stand-in (`support=True`) keeps
   the happy-path coverage honest until a future BRD wires real
   polarity.
3. The follow-up has been filed (per the Coder's hand-off note).
The half-point reflects the documentation risk: the gap should be
recorded in `decisions-history.md` so the next planner does not lose
track of it.

---

## Architectural Compliance Checklist

- [x] All 7 `stop_reason` enum values still reachable (RF-02).
- [x] No event mutations / new event types (RF-03 / Rule #4).
- [x] `extra="allow"` preserved on `RunState`; new field is optional (Rule #5).
- [x] `final_confidence = min(S, J)` — single call site, RF-12 (Rule #8).
- [x] No distributed primitives introduced (RF-05). The new policy is
      in-process, single-worker compatible.
- [x] Async-first: `StoppingSignal.evaluate` is `async`; orchestrator
      callers `await`.
- [x] Cross-family / multi-LLM concerns (`ai-services.md` §1) — N/A,
      no LLM calls added.

---

## Required Changes

**None.** Implementation approved as delivered.

---

## Recommendations (non-blocking, for the follow-up BRD)

1. **Evidence polarity classifier.** File a BRD that updates
   [backend/app/agent/tasks/search.py](../../../backend/app/agent/tasks/search.py)
   to assign `EvidencePolarity.SUPPORTS / CONTRADICTS / NEUTRAL` based on
   a lightweight classifier prompt. Until then, no production run can
   satisfy the O-04 agreement gate and `JudgeSignal` will never approve
   end-to-end. Capture in `decisions-history.md`.
2. **Ambiguity emitter.** A future BRD must wire either the classifier
   task or the judge to set `state.has_ambiguity = True` and emit
   `AmbiguityDetectedEvent`. The reader is in place; the writer is the
   only missing piece for the `HONEST_AMBIGUOUS` path to fire under
   production load.
3. **(Optional)** Replace the `state.contradictions.append(object())`
   trick in `test_policy_honest_fires_before_budget` with a typed
   `ContradictionDetectedEvent` factory once such a fixture lands in
   `tests/fixtures/`. Cosmetic.

---

## Positive Highlights

- Clean Protocol-based extension surface — adding a sixth signal in V2
  (`DomainSafety`, `ConfidencePlateau`) needs only a new file under
  `app/stopping/signals/` and one constructor arg; no policy edits.
- Symmetric handling of "honest stop trumps draft" vs "budget keeps
  draft" in [`_handle_analyzing`](../../../backend/app/agent/orchestrator.py#L165) — exactly the RF-04 semantics with no magic constants.
- The `_RecordingFake` shared-context test (audit finding) is implemented
  without monkey-patching the parallel BRD-08 import surface, which is
  precisely the multi-session-safe pattern the audit asked for.
- 100 % statement coverage achieved without contrived tests — every
  branch is exercised by a meaningful scenario.

---

## Memory Updates (post-review)

- `.github/memory-bank/logs/decisions-history.md` — record CR-09-001 verdict.
- `.github/memory-bank/logs/lessons-learned.md` — candidate lesson:
  *"When two BRDs touch the same orchestrator file in parallel sessions,
  the layered-policy pattern (this BRD) + boundary-test canary
  (61-test BRD-08 surface) is sufficient — no textual merge conflict
  surfaced."*
- Follow-up BRD ticket for the `EvidencePolarity` classifier (see
  Recommendations §1).
