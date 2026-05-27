# Implementation Plan: BRD-09 Stopping Signal Policy

**Plan ID:** IP-09
**BRD Reference:** [BRD-09-stopping-signals.md](../brds/BRD-09-stopping-signals.md)
**Created:** 2026-05-26
**Status:** Ready for Auditor (F2.S3)
**Implementation Order:** 10 of 19

---

## 1. Overview

Implement the **layered stopping policy (A + D + B + E + F)** mandated by RF-01 / RF-04
behind the second of the three plugin seams (`StoppingSignal`). The deliverable is a
self-contained `app.stopping/` package plus **three surgical edits** to
`backend/app/agent/orchestrator.py` so the FSM consults the policy at every decision
point instead of relying on the inline ad-hoc checks introduced by BRD-07.

```
final decision ← stopping_policy.evaluate(state, judge_confidence?)
                 ├── E HonestStop   (priority 10) → STOP {honest_*}
                 ├── F Budget       (priority 20) → STOP {stopped_by_budget}
                 ├── A Coverage     (priority 30) → DEFER | CONTINUE
                 ├── D Agreement    (priority 35) → DEFER | CONTINUE
                 └── B Judge        (priority 40) → STOP {judge_confirmed} | CONTINUE
```

**In scope (BRD-09 §2 RF coverage):**
- **RF-01** — autonomous stopping; all 7 `stop_reason` values reachable from the FSM.
- **RF-04** — honest stops for contradictions / ambiguity / insufficient evidence.

**Non-goals (deferred):**
- `DomainSafety` and `ConfidencePlateau` signals — BRD-09 §10 (V2).
- Adaptive / user-customisable thresholds — BRD-09 §10.
- Persisting a `StoppingPolicyEvaluatedEvent` — `StoppedEvent` already carries `stop_reason`.
- Wiring an `AmbiguityDetectedEvent` **emitter** (no current FSM step produces it).
  The signal **reads** a flag on `RunState`; emitting is future work (see O-05).

---

## 2. Architectural Alignment

| Rule (`copilot-instructions.md §3`) | Compliance |
|---|---|
| #1 Three plugin seams (`Source`, `StoppingSignal`, `OutputRenderer`) | This BRD implements **seam #2**. `StoppingSignal` is added as a `@runtime_checkable` `Protocol` in `app/seams/stopping.py`, alongside the existing `app/seams/source.py`. |
| #2 Three not-seams (planner / storage / LLM) | The policy **coordinator** (`StoppingPolicy`) is **not** a seam — it is a single concrete class with a static set of registered signals. New signals plug behind the `StoppingSignal` Protocol, not behind a "policy" abstraction. |
| #3 `stop_reason` is an enum | Every signal that returns `SignalResult.STOP` MUST set `stop_reason: StopReason` from the existing `app.domain.enums.StopReason`. The `StopSignalOutput.stop_reason` field is typed `StopReason \| None`. No free-text mapping. |
| #4 Events are append-only | The policy emits **zero** new events. The orchestrator continues to emit `StoppedEvent` (and the existing `ConfidenceMismatchEvent` from BRD-08). No event mutation. |
| #5 Schema evolution = `extra="allow"` | One new optional `RunState` field (`has_ambiguity: bool = False`). `RunState` already declares `ConfigDict(extra="allow")` (verified in [backend/app/agent/run_state.py:43](../../../backend/app/agent/run_state.py)). |
| #6 UI surfaces every trust guarantee | No FE work in this BRD. The stop reason continues to flow through `StoppedEvent.stop_reason`; the existing FE renderer (BRD-13) already shows it. |
| #7 FE↔BE contract | No event-shape changes. `scripts/export_types.py` does **not** run. |
| #8 `final_confidence = min(S, J)` | The Judge signal calls `min(structural, judge)` exactly once and gates on `>= threshold`. The structural component is obtained from `calculate_structural_confidence(state)` — never recomputed locally. |
| English-only artifacts (L-001 / language-policy) | All identifiers, docstrings, log keys, exception messages, signal names in English. |
| `pyright --strict` + `ruff` clean | `from __future__ import annotations` on every new module; PEP 604 unions; no `Any` leak; no `Optional` import from `typing`. |
| Async-first | `StoppingSignal.evaluate` is `async` (matches the BRD Protocol). Signals are **pure** today — no IO — but the `async` signature reserves the right for a future signal (e.g. `DomainSafety` calling an LLM) without breaking the seam. |
| Mandatory unit tests (L-002) | Coder ships **≥ 30 unit tests**, target ≥ 95 % coverage on `app/stopping/` and `app/seams/stopping.py`. The orchestrator regression suite is updated, not extended (no new orchestrator test files). |

---

## 3. Coordination with BRD-08 (Confidence Calculation Engine)

BRD-08 is being implemented in a **parallel session**. The current state on `main`
(verified via `list_dir backend/app/confidence/`) is:

- `app/confidence/__init__.py`, `structural.py`, `calculator.py`, `mismatch.py` all exist.
- `app/agent/orchestrator.py` already imports `detect_mismatch` from `app.confidence`.
- The `TODO(BRD-09)` marker is at [`orchestrator.py:189`](../../../backend/app/agent/orchestrator.py) just above `_handle_judging`. **This is the wiring site for IP-09.**

### Boundary rules (binding)

| Area | BRD-08 (parallel session) | BRD-09 (this plan) |
|---|---|---|
| `app/confidence/**` | Owns. May modify. | **Read-only** — IP-09 only **imports**. |
| `detect_mismatch` (already wired in `_handle_judging`) | Owns. | Untouched. |
| `calculate_structural_confidence(state)` | Owns. | Imported by `JudgeSignal`. |
| `ConfidenceCalculator.check_sufficient` | Owns; not wired (per IP-08 O-08). | **Superseded** by the layered policy — IP-09 does NOT call it, leaves it intact (BRD-08 tests still pass). |
| `app/agent/orchestrator.py` | Modifies divergence logic (IP-08 O-05). | Modifies three handlers (`_handle_searching`, `_handle_analyzing`, `_handle_judging`); does NOT touch the divergence block already merged. |
| `app/agent/run_state.py` | No changes expected per IP-08. | Adds **one** field: `has_ambiguity: bool = False`. |
| `tests/test_agent_orchestrator.py` | Updates divergence asserts (IP-08 §6.4). | Updates stop-reason asserts (this plan §6.4). |

If the BRD-08 session lands its `tests/test_agent_orchestrator.py` edits before BRD-09 merges, the BRD-09 Coder MUST rebase and re-run the full orchestrator suite. The two edits do not overlap textually (one touches the divergence/mismatch lines, the other touches the budget / honest / judge-pass lines), so a textual merge conflict is not expected, but a semantic one is possible — the regression suite is the canary.

---

## 4. Deviations from BRD-09 §4 (binding overrides)

BRD-09 §4 was authored before this plan inspected the existing orchestrator code and the
final BRD-08 surface. Each override below is binding for the Coder.

### O-01. `StopSignalOutput` and `StopContext` are `@dataclass(frozen=True)`, not plain classes

BRD-09 §4.3 defines both as plain Python classes with `__init__`. Per the repo
convention (mirrors `app.confidence.mismatch.MismatchResult`, IP-08 O-06), they are
transient internal value objects: never serialised, never persisted, never crossing
process boundaries. Pydantic adds no value. Use `@dataclass(frozen=True)` for:

- immutability (signals must not mutate the context),
- free `__repr__` for structlog,
- zero boilerplate.

### O-02. PEP 604 unions — no `Optional` from `typing`

BRD-09 §4.3 imports `Optional` and writes `Optional[StopReason]`. Repo convention is
`X | None`. Replace and add `from __future__ import annotations` at the top of every
new module.

### O-03. `StopContext` field naming — use `search_count` / `max_searches`, NOT `iteration_count` / `max_iterations`

BRD-09 §4.3 declares:

```python
iteration_count: int
max_iterations: int
```

and the policy in §4.5 maps `iteration_count=state.iteration_count` and
`max_iterations=state.max_searches`. **This is a bug.** `state.iteration_count` counts
**every FSM tick** (PLANNING, CRITIQUING, REVISING, SEARCHING, ANALYZING, DRAFTING,
JUDGING — see `orchestrator.py:81`), not search rounds. The "budget" guard is the
research **search-round** budget (`state.search_count` / `state.max_searches`); it has
always been so in BRD-07. Misusing `iteration_count` would fire `BudgetSignal` after
~5 search rounds because each search round burns multiple FSM ticks.

**Decision:** rename the context fields to **`search_count`** and **`max_searches`** to
match the canonical names. The mapping in `StoppingPolicy.evaluate` then reads:

```python
search_count=state.search_count,
max_searches=state.max_searches,
```

Update `BudgetSignal.evaluate` to read `context.search_count` / `context.max_searches`
(BRD-09 §4.4 currently reads `context.iteration_count` / `context.max_iterations`).

### O-04. `JudgeSignal` MUST gate on coverage AND agreement before approving (fixes BRD-09 AC-03 contradiction)

BRD-09 §5 AC-03 says:

> Given coverage >= 0.8 and agreement >= 0.7 AND judge_confidence >= threshold
> When I evaluate stopping policy
> Then result.stop_reason = JUDGE_CONFIRMED

But BRD-09 §4.4's `JudgeSignal.evaluate` only checks
`min(structural, judge) >= threshold` and returns `SignalResult.STOP`. Coverage and
Agreement signals only `DEFER` (when met) or `CONTINUE` (when not met). The policy's
loop in §4.5 returns the **first STOP** result. So with `coverage=0.5`,
`agreement=0.4`, but `judge=0.9` (e.g. judge sycophancy), the policy would emit
`JUDGE_CONFIRMED` — directly violating AC-03 and RF-15 (disconfirmation independence).

**Decision:** `JudgeSignal.evaluate` adds two explicit gates **before** the
final-confidence check:

```python
if context.coverage < 0.8:
    return StopSignalOutput(
        signal_name=self.name,
        result=SignalResult.CONTINUE,
        explanation=f"Coverage gate failed: {context.coverage:.0%} < 80%",
        confidence=context.structural_confidence,
    )
if context.agreement < 0.7:
    return StopSignalOutput(
        signal_name=self.name,
        result=SignalResult.CONTINUE,
        explanation=f"Agreement gate failed: {context.agreement:.0%} < 70%",
        confidence=context.structural_confidence,
    )
# … then the existing min(S, J) >= threshold check
```

The two thresholds (0.8 / 0.7) are intentionally identical to the ones in `CoverageSignal`
/ `AgreementSignal` (BRD-09 §4.4). Centralising them in `JudgeSignal` makes the gate
explicit at the decision point and removes any reliance on signal ordering correctness.
`CoverageSignal` / `AgreementSignal` are kept (they still drive `CONTINUE` for the
"keep searching" branch when the judge has not yet evaluated), but they no longer
carry the AC-03 guarantee on their own.

### O-05. `RunState.has_ambiguity` is a new optional field, NOT a positional arg in `StopContext`

BRD-09 §4.5 maps `has_ambiguity=False` as a hard-coded literal in `StoppingPolicy.evaluate`
with the comment "Set by agent when detected". No agent task currently sets it, so the
literal-`False` shortcut is acceptable for V1, but it makes `HonestStopSignal`'s ambiguity
branch **dead code** that cannot be exercised by integration tests.

**Decision:** add an optional field to `RunState`:

```python
# app/agent/run_state.py
has_ambiguity: bool = False  # Set by future ambiguity-detection task; read by HonestStopSignal.
```

`RunState` already has `model_config = ConfigDict(extra="allow")`, so the schema change
is backward-compatible. Existing `RunState(...)` call sites do not break. Unit tests
for `HonestStopSignal` exercise the ambiguity branch by setting the flag directly. The
**emitter** of `AmbiguityDetectedEvent` is explicitly out of scope (deferred to a
future BRD that wires the question-type classifier or judge into ambiguity detection).

### O-06. `HonestStopSignal` "unanswerable" condition uses **all-claims-failed**, not "half-uncoverable"

BRD-09 §4.4's `HonestStopSignal.evaluate` says:

```python
if (
    context.uncoverable_claims > 0
    and context.uncoverable_claims >= context.total_claims * 0.5
):
    return … HONEST_UNANSWERABLE
```

The 50 %-uncoverable threshold conflicts with the BRD-07 orchestrator behaviour (which
only declares `HONEST_UNANSWERABLE` when **zero** claims are covered) and with the
existing safety net at `orchestrator.py:170` (`coverage_ratio() == 0.0` after N rounds).
Firing `HONEST_UNANSWERABLE` while half the claims are covered would orphan a
draft-able answer.

**Decision:** the condition becomes:

```python
all_resolved = (
    context.total_claims > 0
    and (context.covered_claims + context.uncoverable_claims) == context.total_claims
)
if all_resolved and context.covered_claims == 0:
    return … HONEST_UNANSWERABLE
```

Add `covered_claims: int` to `StopContext` (count, not list, to keep the dataclass
flat). This matches the orchestrator's pre-policy semantics exactly, so the regression
suite continues to pass without touching the "all uncoverable" tests.

### O-07. `BudgetSignal` does **not** subsume the judge-attempts safety net

`AgentOrchestrator._handle_judging` currently caps `judge_attempts` at
`state.max_judge_attempts` and emits `STOPPED_BY_BUDGET` when the cap is hit
(orchestrator.py:204). This is a **sub-loop counter**, not the research budget; folding
it into `BudgetSignal` would couple two independent budgets and complicate the dataclass.

**Decision:** the judge-attempts cap stays **inline** in `_handle_judging`, exactly as
today (no change). `BudgetSignal` exclusively gates `state.search_count` /
`state.max_searches`. Document this in `BudgetSignal`'s docstring.

### O-08. `StoppingPolicy` is **not** a singleton; the orchestrator owns the instance

BRD-09 §4.5 ends with `stopping_policy = StoppingPolicy()` (module-level singleton).
Singletons make tests harder to isolate and clash with parametrised tests that want a
custom signal set.

**Decision:** delete the singleton. `AgentOrchestrator.__init__` constructs **one**
`StoppingPolicy()` per orchestrator instance and stores it on `self._stopping_policy`.
Tests that want to inject a fake policy do so via the orchestrator constructor (a new
optional keyword `stopping_policy: StoppingPolicy | None = None`, default-constructed
when `None`).

### O-09. `policy.evaluate(state, judge_confidence=None)` is **kw-only** for the optional arg

`async def evaluate(self, state: RunState, judge_confidence: float | None = None)` —
the `judge_confidence` kwarg is **keyword-only** to prevent the `_handle_judging` call
site from accidentally passing it positionally. Add `*,` before it in the signature.

### O-10. Logging keys are stable structlog keys, not f-strings

All `logger.debug(...)` calls inside signals and the policy use **kwarg keys** (the
repo convention; see `orchestrator.py:222` `logger.info("agent_run_complete", run_id=…, …)`).
BRD-09 §4.5's `signal=signal.name, result=result.result, stop_reason=result.stop_reason`
is already correct; just confirm no f-strings sneak into log messages.

---

## 5. Module Layout (final, post-deviations)

```
backend/app/
├── seams/
│   └── stopping.py            # NEW — Protocol + frozen dataclasses
├── stopping/                  # NEW package
│   ├── __init__.py            # Public exports (alphabetical, RUF022)
│   ├── policy.py              # StoppingPolicy coordinator
│   └── signals/
│       ├── __init__.py        # Re-exports every signal class
│       ├── coverage.py        # A — DEFER if coverage >= 0.8 else CONTINUE
│       ├── agreement.py       # D — DEFER if agreement >= 0.7 else CONTINUE
│       ├── judge.py           # B — STOP{JUDGE_CONFIRMED} | CONTINUE (gated by O-04)
│       ├── honest.py          # E — STOP{HONEST_*} | DEFER (O-05, O-06)
│       └── budget.py          # F — STOP{STOPPED_BY_BUDGET} | DEFER (O-07)
└── agent/
    ├── orchestrator.py        # MODIFIED — 3 integration points + 1 ctor kwarg
    └── run_state.py           # MODIFIED — + has_ambiguity field (O-05)
```

### 5.1 `app/seams/stopping.py`

`from __future__ import annotations`, then:

| Symbol | Kind | Contract |
|---|---|---|
| `SignalResult` | `StrEnum` | `CONTINUE = "continue"`, `STOP = "stop"`, `DEFER = "defer"`. |
| `StopSignalOutput` | `@dataclass(frozen=True)` | Fields: `signal_name: str`, `result: SignalResult`, `stop_reason: StopReason \| None = None`, `explanation: str \| None = None`, `confidence: float = 0.0`. **Invariant:** `result == STOP ⇒ stop_reason is not None`. Enforced via `__post_init__` raising `ValueError`. |
| `StopContext` | `@dataclass(frozen=True)` | See §5.2 for the canonical field list. |
| `StoppingSignal` | `@runtime_checkable Protocol` | `name: str` (property), `priority: int` (property), `async def evaluate(self, context: StopContext) -> StopSignalOutput`. |

### 5.2 `StopContext` fields (canonical, post-O-03 / O-05 / O-06)

| Field | Type | Source | Notes |
|---|---|---|---|
| `coverage` | `float` | `calculate_coverage(state)` | RF-12 component |
| `agreement` | `float` | `calculate_agreement(state.evidence)` | RF-12 component |
| `diversity` | `float` | `calculate_diversity(state.evidence)` | RF-12 component (unused today; reserved for V2 signal) |
| `no_conflict` | `float` | `calculate_no_conflict(state)` | RF-12 component |
| `structural_confidence` | `float` | `calculate_structural_confidence(state).score` | RF-12 `S` |
| `judge_confidence` | `float \| None` | passed from `_handle_judging` | `None` outside JUDGING state |
| `threshold` | `float` | `state.confidence_threshold` | user-set, RF-12 |
| `search_count` | `int` | `state.search_count` | O-03 |
| `max_searches` | `int` | `state.max_searches` | O-03 |
| `has_contradictions` | `bool` | `len(state.contradictions) > 0` | RF-04 |
| `has_ambiguity` | `bool` | `state.has_ambiguity` | O-05 |
| `uncoverable_claims` | `int` | `len(state.uncoverable_claims)` | count, not list (O-06) |
| `covered_claims` | `int` | `len(state.covered_claims)` | count, not list (O-06) |
| `total_claims` | `int` | `len(state.sub_claims)` | O-06 |

**Note:** the four RF-12 components (`coverage` / `agreement` / `diversity` /
`no_conflict`) are obtained from a **single** call to
`calculate_structural_confidence(state)` — never recomputed per-signal. The four
component fields are extracted from the returned `StructuralConfidence` for ergonomic
signal access; `structural_confidence` is its `.score`.

### 5.3 `app/stopping/policy.py` (post-O-08)

```python
class StoppingPolicy:
    """Coordinates layered stopping signals (E + F + A + D + B, in priority order)."""

    def __init__(self, signals: Sequence[StoppingSignal] | None = None) -> None:
        registered = signals or (
            HonestStopSignal(),
            BudgetSignal(),
            CoverageSignal(),
            AgreementSignal(),
            JudgeSignal(),
        )
        self._signals: tuple[StoppingSignal, ...] = tuple(
            sorted(registered, key=lambda s: s.priority)
        )

    async def evaluate(
        self,
        state: RunState,
        *,
        judge_confidence: float | None = None,
    ) -> StopSignalOutput: ...

    @staticmethod
    def should_stop(result: StopSignalOutput) -> bool:
        return result.result is SignalResult.STOP
```

The optional `signals` kwarg lets tests inject a custom signal set without monkey-patching
(makes priority-order tests trivial).

### 5.4 `app/stopping/__init__.py`

Public re-exports (alphabetical, RUF022):

```python
from app.stopping.policy import StoppingPolicy
from app.stopping.signals.agreement import AgreementSignal
from app.stopping.signals.budget import BudgetSignal
from app.stopping.signals.coverage import CoverageSignal
from app.stopping.signals.honest import HonestStopSignal
from app.stopping.signals.judge import JudgeSignal

__all__ = [
    "AgreementSignal",
    "BudgetSignal",
    "CoverageSignal",
    "HonestStopSignal",
    "JudgeSignal",
    "StoppingPolicy",
]
```

### 5.5 Orchestrator integration (three edits)

The new `AgentOrchestrator.__init__` accepts `stopping_policy: StoppingPolicy | None = None`
and stores `self._stopping_policy = stopping_policy or StoppingPolicy()`.

#### Edit A — `_handle_searching` (replaces inline budget check)

```python
async def _handle_searching(self) -> None:
    result = await self._stopping_policy.evaluate(self.state)
    if self._stopping_policy.should_stop(result):
        assert result.stop_reason is not None
        await self._stop(result.stop_reason)
        return
    events = await execute_search_round(self.state)
    for ev in events:
        await self.emit(ev)
    self.state.search_count += 1
    self.state.transition_to(AgentState.ANALYZING)
```

The removed line is:

```python
if self.state.search_count >= self.state.max_searches:
    await self._stop(StopReason.STOPPED_BY_BUDGET)
    return
```

`BudgetSignal` reproduces the exact semantics (`>=`), so the regression suite is
unchanged. Honest signals also get a chance here (e.g. a late-detected contradiction).

**Behaviour note (symmetric to Edit B):** if `HonestStopSignal` fires in
`_handle_searching` with `covered_claims` already non-empty, the partial draft is
**discarded** — the run terminates with `HONEST_*` and no `DRAFTING` happens. This is
the intended RF-04 semantics: an honest stop trumps a partial answer (contradictions /
ambiguity invalidate prior coverage). Budget, in contrast, lets the draft proceed
(Edit B), because exhausting the search budget does not invalidate the evidence
already gathered.

#### Edit B — `_handle_analyzing` (replaces safety net + budget block)

The current handler (orchestrator.py:151-186) ends with this branch tree:

```
all_claims_resolved? → DRAFTING or _stop(BUDGET) or _stop(UNANSWERABLE)
coverage==0 AND search_count >= 5? → _stop(UNANSWERABLE)
search_count >= max_searches? → DRAFTING or _stop(BUDGET)
else → SEARCHING
```

Replace with:

```python
if self.state.all_claims_resolved():
    if self.state.covered_claims:
        self.state.transition_to(AgentState.DRAFTING)
        return
    # No coverage and no pending claims — let the policy decide between
    # BUDGET (search_count >= max_searches) and HONEST_UNANSWERABLE.
    result = await self._stopping_policy.evaluate(self.state)
    if self._stopping_policy.should_stop(result):
        assert result.stop_reason is not None
        await self._stop(result.stop_reason)
    else:
        # Defensive: total_claims==0 case is impossible after planning; fall back.
        await self._stop(StopReason.HONEST_UNANSWERABLE)
    return

result = await self._stopping_policy.evaluate(self.state)
if self._stopping_policy.should_stop(result):
    assert result.stop_reason is not None
    # Honour the policy's BUDGET stop only if we have nothing to draft.
    if result.stop_reason is StopReason.STOPPED_BY_BUDGET and self.state.covered_claims:
        self.state.transition_to(AgentState.DRAFTING)
    else:
        await self._stop(result.stop_reason)
    return

self.state.transition_to(AgentState.SEARCHING)
```

The `_HONEST_UNANSWERABLE_SAFETY_ROUNDS = 5` constant becomes **unused**. Delete it
(ruff `F841`/`F401`-equivalent unused-binding). The 5-round safety net is replaced by
`HonestStopSignal` (O-06): after enough search rounds, all claims will be marked
`uncoverable` by `analyze_evidence`, and the all-resolved branch fires.

Note: when `BudgetSignal` fires but we still have covered claims, we still draft — this
matches the existing behaviour and is critical for "ran out of budget but produced an
answer" runs (RF-01 / RF-12).

#### Edit C — `_handle_judging` (replaces `judge_event.passed` check)

Remove the inline `if judge_event.passed: await self._stop(JUDGE_CONFIRMED); return`
and call the policy:

```python
async def _handle_judging(self) -> None:
    judge_event = await evaluate_with_judge(self.state)
    await self.emit(judge_event)
    self.state.last_judge_confidence = judge_event.judge_confidence
    self.state.last_structural_confidence = judge_event.structural_confidence
    self.state.judge_attempts += 1

    result = await self._stopping_policy.evaluate(
        self.state,
        judge_confidence=judge_event.judge_confidence,
    )
    if self._stopping_policy.should_stop(result):
        assert result.stop_reason is not None
        await self._stop(result.stop_reason)
        return

    # Judge sub-loop safety net (O-07): not part of the layered policy.
    if self.state.judge_attempts >= self.state.max_judge_attempts:
        await self._stop(StopReason.STOPPED_BY_BUDGET)
        return

    # RF-15 disconfirmation (unchanged from BRD-08).
    mismatch = detect_mismatch(
        structural=judge_event.structural_confidence,
        judge=judge_event.judge_confidence,
    )
    if mismatch.has_mismatch:
        assert mismatch.trust_flag is not None
        await self.emit(
            ConfidenceMismatchEvent(
                structural_confidence=judge_event.structural_confidence,
                judge_confidence=judge_event.judge_confidence,
                divergence=mismatch.divergence,
                trust_flag=mismatch.trust_flag,
            )
        )

    issues = judge_event.suggested_improvements or []
    if issues:
        claim_ids = await map_issues_to_claims(issues[:2], self.state.sub_claims)
        for cid in claim_ids:
            for c in self.state.sub_claims:
                if c.id == cid and c.status == "covered":
                    c.status = "pending"
                    if cid in self.state.covered_claims:
                        self.state.covered_claims.remove(cid)

    self.state.transition_to(AgentState.SEARCHING)
```

The `# TODO(BRD-09)` comment line (orchestrator.py:189) is **deleted**.

**Crucial preservation:** `judge_event.passed` was computed inside `evaluate_with_judge`
as `min(structural, judge) >= threshold`. The new `JudgeSignal` recomputes the same
condition from the same inputs, plus the coverage / agreement gates from O-04. For
every existing fixture where `judge_event.passed == True` AND coverage / agreement
already met the gates (the normal happy path), behaviour is identical. The only
behaviour change is the case where `passed == True` but coverage < 0.8 or agreement < 0.7
— that case now keeps iterating instead of confirming, which is the **intended** fix
of AC-03.

### 5.6 `RunState` change

```python
# Insert after `confidence_threshold` (alphabetical-ish near other Field-defaulted bools is fine).
has_ambiguity: bool = False
```

That is the **only** field added. No method changes.

---

## 6. Implementation Steps (ordered)

| # | File | Action | LOC est. |
|---|---|---|---|
| 1 | `backend/app/seams/stopping.py` | Create Protocol + 2 dataclasses + `SignalResult` enum (§5.1) | ~75 |
| 2 | `backend/app/stopping/__init__.py` | Re-exports (§5.4) | ~15 |
| 3 | `backend/app/stopping/signals/__init__.py` | Re-export the 5 signal classes | ~15 |
| 4 | `backend/app/stopping/signals/coverage.py` | `CoverageSignal` (priority 30) | ~35 |
| 5 | `backend/app/stopping/signals/agreement.py` | `AgreementSignal` (priority 35) | ~35 |
| 6 | `backend/app/stopping/signals/budget.py` | `BudgetSignal` (priority 20, O-07) | ~40 |
| 7 | `backend/app/stopping/signals/honest.py` | `HonestStopSignal` (priority 10, O-05 + O-06) | ~75 |
| 8 | `backend/app/stopping/signals/judge.py` | `JudgeSignal` (priority 40, O-04 gates) | ~65 |
| 9 | `backend/app/stopping/policy.py` | `StoppingPolicy` (§5.3, no singleton) | ~90 |
| 10 | `backend/app/agent/run_state.py` | + `has_ambiguity: bool = False` (O-05) | 1 |
| 11 | `backend/app/agent/orchestrator.py` | 3 edits (§5.5) + ctor kwarg + delete `_HONEST_UNANSWERABLE_SAFETY_ROUNDS` + delete `TODO(BRD-09)` line | ~35 net delta |
| 12 | `backend/tests/test_seams_stopping.py` | New — Protocol shape + dataclass invariants | ~90 |
| 13 | `backend/tests/test_stopping_signals.py` | New — per-signal unit tests (§7.1–7.5) | ~330 |
| 14 | `backend/tests/test_stopping_policy.py` | New — policy coordinator integration (§7.6) | ~140 |
| 15 | `backend/tests/test_agent_orchestrator.py` | Update stop-reason / trace assertions (§7.7) | ~20 |
| 16 | `backend/tests/test_agent_run_state.py` | Add 1 test for `has_ambiguity` default | ~10 |

**Total LOC budget:** ~1 100 (under the 4–6 h pair-session ceiling per
`copilot-instructions.md §6`).

**Order matters:**
- Steps 1–3 are independent foundation; do first.
- Steps 4–8 depend on step 1 (Protocol + dataclasses); MAY be done in parallel.
- Step 9 depends on steps 4–8.
- Step 10 (`RunState` field) MUST land before step 7 (`HonestStopSignal` reads it).
- Step 11 (orchestrator) depends on step 9.
- Steps 12–14 depend on steps 1–9 respectively.
- Step 15 depends on step 11 — **run `pytest backend/tests/test_agent_orchestrator.py -v` immediately after step 11 to confirm the canary still passes** (or makes the precisely-expected diff).

---

## 7. Test Plan

All tests use **pytest + pytest-asyncio**. Target ≥ 95 % coverage on `app/stopping/`
and `app/seams/stopping.py`. The orchestrator suite remains the integration canary.

### 7.1 `test_seams_stopping.py`

| Case | Assertion |
|---|---|
| `test_signal_result_values` | Enum has exactly `CONTINUE`, `STOP`, `DEFER` and their string values |
| `test_stop_signal_output_stop_requires_reason` | `StopSignalOutput(result=STOP, stop_reason=None)` raises `ValueError` |
| `test_stop_signal_output_defer_allows_no_reason` | `StopSignalOutput(result=DEFER)` is valid |
| `test_stop_signal_output_frozen` | Mutating a field raises `FrozenInstanceError` |
| `test_stop_context_frozen` | Mutating a field raises `FrozenInstanceError` |
| `test_stopping_signal_protocol_runtime_check` | A minimal duck-typed class passes `isinstance(x, StoppingSignal)` |
| `test_stopping_signal_protocol_missing_attr_fails` | A class missing `priority` fails the runtime check |

### 7.2 `CoverageSignal` (in `test_stopping_signals.py`)

| Case | Inputs | Expected |
|---|---|---|
| `test_coverage_high_defers` | `coverage=0.85` | `DEFER` |
| `test_coverage_at_threshold_defers` | `coverage=0.80` | `DEFER` (strict `>=`) |
| `test_coverage_low_continues` | `coverage=0.50` | `CONTINUE` |
| `test_coverage_priority_is_30` | — | `signal.priority == 30` |
| `test_coverage_name` | — | `signal.name == "Coverage"` |

### 7.3 `AgreementSignal`

| Case | Inputs | Expected |
|---|---|---|
| `test_agreement_high_defers` | `agreement=0.80` | `DEFER` |
| `test_agreement_at_threshold_defers` | `agreement=0.70` | `DEFER` |
| `test_agreement_low_continues` | `agreement=0.50` | `CONTINUE` |
| `test_agreement_priority_is_35` | — | `signal.priority == 35` |

### 7.4 `BudgetSignal`

| Case | Inputs | Expected |
|---|---|---|
| `test_budget_under_limit_defers` | `search_count=10, max_searches=20` | `DEFER` |
| `test_budget_at_limit_stops` | `search_count=20, max_searches=20` | `STOP{STOPPED_BY_BUDGET}` |
| `test_budget_over_limit_stops` | `search_count=25, max_searches=20` | `STOP{STOPPED_BY_BUDGET}` (defensive) |
| `test_budget_does_not_use_judge_attempts` | — | Verified via docstring assertion + grep in test (search `judge_attempts` MUST NOT appear in `budget.py`) |
| `test_budget_priority_is_20` | — | `signal.priority == 20` |

### 7.5 `HonestStopSignal`

| Case | Inputs | Expected |
|---|---|---|
| `test_honest_contradiction_fires` | `has_contradictions=True, no_conflict=0.1` | `STOP{HONEST_CONTRADICTION}` |
| `test_honest_contradiction_defers_when_no_conflict_high` | `has_contradictions=True, no_conflict=0.5` | `DEFER` (`no_conflict >= 0.3` branch, BRD-09 §4.4) |
| `test_honest_ambiguity_fires` | `has_ambiguity=True` | `STOP{HONEST_AMBIGUOUS}` |
| `test_honest_unanswerable_all_failed` | `total_claims=4, covered_claims=0, uncoverable_claims=4` | `STOP{HONEST_UNANSWERABLE}` |
| `test_honest_no_unanswerable_when_partially_covered` | `total_claims=4, covered_claims=1, uncoverable_claims=3` | `DEFER` (O-06 fix) |
| `test_honest_no_unanswerable_when_pending` | `total_claims=4, covered_claims=0, uncoverable_claims=2` | `DEFER` (not all resolved) |
| `test_honest_no_unanswerable_when_zero_claims` | `total_claims=0` | `DEFER` (defensive, before planning) |
| `test_honest_defers_when_clean` | all flags clean | `DEFER` |
| `test_honest_priority_is_10` | — | Highest |
| `test_honest_contradiction_beats_ambiguity` | both set | `HONEST_CONTRADICTION` (check order inside `evaluate`) |

### 7.6 `JudgeSignal` (O-04 is critical)

| Case | Inputs | Expected |
|---|---|---|
| `test_judge_no_confidence_continues` | `judge_confidence=None` | `CONTINUE` |
| `test_judge_passes_all_gates` | `cov=0.85, agr=0.75, S=0.8, J=0.85, thr=0.7` | `STOP{JUDGE_CONFIRMED}` |
| `test_judge_coverage_gate_blocks` | `cov=0.50, agr=0.80, S=0.6, J=0.9` | `CONTINUE` (O-04) |
| `test_judge_agreement_gate_blocks` | `cov=0.85, agr=0.50, S=0.7, J=0.9` | `CONTINUE` (O-04) |
| `test_judge_under_threshold_continues` | `cov=0.85, agr=0.80, S=0.8, J=0.5, thr=0.7` | `CONTINUE` (final 0.5 < 0.7) |
| `test_judge_final_uses_min_S_J` | `cov=0.85, agr=0.80, S=0.4, J=0.9, thr=0.7` | `CONTINUE` (final = min = 0.4) |
| `test_judge_priority_is_40` | — | Lowest |

### 7.7 `StoppingPolicy` (integration, `test_stopping_policy.py`)

| Case | Scenario | Expected |
|---|---|---|
| `test_policy_default_signal_order` | Construct default policy | Order: HonestStop, Budget, Coverage, Agreement, Judge |
| `test_policy_custom_signal_set` | `StoppingPolicy(signals=[BudgetSignal()])` | Only Budget runs |
| `test_policy_honest_fires_before_budget` | Contradictions AND `search_count >= max` | `HONEST_CONTRADICTION` (NOT `STOPPED_BY_BUDGET`) |
| `test_policy_budget_fires_before_judge` | `search_count >= max` AND would-pass-judge | `STOPPED_BY_BUDGET` |
| `test_policy_judge_confirmation_full_path` | All gates pass, judge approves | `JUDGE_CONFIRMED` |
| `test_policy_continue_when_everyone_defers_or_continues` | Mid-research state, no judge yet | `CONTINUE` |
| `test_policy_should_stop_helper` | `result.result is STOP` ⇒ `should_stop == True` | static-method check |
| `test_policy_uses_structural_confidence_once` | Inject a recording fake `StoppingSignal` via the new `StoppingPolicy(signals=[...])` kwarg that captures the `StopContext` it receives; assert all 5 default signals (when run together) see the **same** `structural_confidence` value (proves it is computed once and shared, without monkey-patching `app.confidence` — BRD-08 may move that import surface in parallel) | recorded context identity check |
| `test_policy_log_keys_are_stable` | Capture structlog events | Keys: `signal`, `result`, `stop_reason` (no f-strings) |

### 7.8 Orchestrator regression updates (`test_agent_orchestrator.py`)

The existing test file (verified via `read_file`) covers:
- happy-path JUDGE_CONFIRMED
- divergence → ConfidenceMismatchEvent (BRD-08 territory; do not touch)
- contradiction handling
- cancellation (L-010 pattern)
- max-searches → STOPPED_BY_BUDGET
- zero-coverage → HONEST_UNANSWERABLE

**Updates required:**

| Test | What changes |
|---|---|
| Happy-path JUDGE_CONFIRMED | If the existing fixture has `coverage < 0.8` (likely — only one claim, one evidence), increase the fixture's covered-claim count or relax the assertion to allow extra iterations before `JUDGE_CONFIRMED`. Document the new expected event count in the test. |
| Zero-coverage HONEST_UNANSWERABLE | Should still fire — `HonestStopSignal` returns the same reason via O-06, **only when all claims are uncoverable** (slight behaviour delta: the old safety net fired at 5 rounds regardless of resolution; the new policy waits until all claims are marked uncoverable). The fixture already exhausts `max_searches=20`, so `BudgetSignal` fires instead at the last round — accepted behaviour. **The Coder must verify the existing fixture and update either the fixture (mark all claims uncoverable) or the assertion (accept `STOPPED_BY_BUDGET` here). The plan does NOT pre-decide this; the Coder picks the smaller diff.** |
| `_HONEST_UNANSWERABLE_SAFETY_ROUNDS` symbol | Now unused. If any test imports it, remove the import. |
| New `test_orchestrator_uses_injected_policy` | Inject a `StoppingPolicy(signals=[<fake>])` via the new ctor kwarg, run, assert the fake was consulted. ~25 LOC. |

**Forbidden updates (BRD-08 boundary):**

- `test_orchestrator_emits_confidence_mismatch` and any divergence/`trust_flag` assertion: untouched.

### 7.9 `test_agent_run_state.py`

| Case | Assertion |
|---|---|
| `test_run_state_has_ambiguity_default_false` | `RunState(...).has_ambiguity is False` |

### 7.10 Verification commands

```powershell
# Backend, from repo root
cd backend
uv run pytest tests/test_seams_stopping.py tests/test_stopping_signals.py tests/test_stopping_policy.py -v
uv run pytest tests/test_agent_orchestrator.py tests/test_agent_run_state.py -v
uv run pytest --cov=app.stopping --cov=app.seams.stopping --cov-report=term-missing
uv run ruff check app/stopping/ app/seams/stopping.py app/agent/orchestrator.py app/agent/run_state.py tests/test_seams_stopping.py tests/test_stopping_signals.py tests/test_stopping_policy.py
uv run pyright app/stopping/ app/seams/stopping.py app/agent/orchestrator.py
```

All five commands MUST exit with code 0. Coverage on `app.stopping` + `app.seams.stopping`
MUST be ≥ 95 %.

---

## 8. Acceptance Criteria → Test Mapping

| BRD-09 AC | Test ID(s) |
|---|---|
| AC-01 Honest Stops Fire First | `test_policy_honest_fires_before_budget`, `test_honest_contradiction_fires` |
| AC-02 Budget Safety Net Works | `test_policy_budget_fires_before_judge`, `test_budget_at_limit_stops` |
| AC-03 Judge Confirmation Requires Coverage+Agreement | `test_judge_passes_all_gates`, `test_judge_coverage_gate_blocks`, `test_judge_agreement_gate_blocks`, `test_policy_judge_confirmation_full_path` |
| AC-04 Continue When Insufficient | `test_policy_continue_when_everyone_defers_or_continues`, `test_coverage_low_continues`, `test_judge_under_threshold_continues` |

All four ACs have ≥ 2 green tests pointing at them.

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Merge conflict with BRD-08 session in `orchestrator.py` | Med | Med | The two edits touch disjoint line ranges (BRD-08 = divergence/mismatch block; BRD-09 = budget / honest / judge-pass blocks). Coder MUST rebase on `main` before pushing and re-run the full orchestrator suite. §3 above documents the boundary. |
| Existing zero-coverage HONEST_UNANSWERABLE test breaks because the 5-round safety net is gone | Med | Med | §7.8 row 2 explicitly calls out the choice between updating the fixture or the assertion. Coder picks the smaller diff and documents it in the PR. |
| AC-03 fix (coverage/agreement gates inside `JudgeSignal`) silently breaks a happy-path orchestrator test where the fixture's coverage is `< 0.8` | High | High | §7.8 row 1 mandates the fixture audit. The plan accepts that the happy-path fixture may need its `covered_claims` boosted. The 0.8 / 0.7 numbers are deliberately copied from `CoverageSignal` / `AgreementSignal` to avoid drift. |
| `RunState` field addition triggers a Pydantic v2 schema-cache rebuild in unrelated tests | Low | Low | `model_config = ConfigDict(extra="allow")` is already set; adding a default-True optional field is fully backward-compatible. Verified by the existing BRD-02 / BRD-07 test suites. |
| Ambiguity signal is untestable end-to-end because nothing emits the event | Low | High | Accepted. Unit tests set `state.has_ambiguity = True` directly. The emitter is explicitly deferred (§1 Non-goals). |
| `StoppingSignal` Protocol gets a circular import via `app.agent.run_state` → `app.stopping` → `app.confidence` → … | Low | Low | The seam module (`app/seams/stopping.py`) does NOT import `RunState`; it forward-references it inside `StopContext`'s type via `from __future__ import annotations`. The policy module imports `RunState` from `app.agent.run_state`, but `run_state.py` does not import anything from `app.stopping`. Verified by `mcp_pylance_mcp_s_pylanceImports` before merge. |
| `JudgeSignal` recomputes structural confidence (perf or drift risk) | Low | N/A | Eliminated — `StopContext.structural_confidence` is computed **once** in `StoppingPolicy.evaluate` via `calculate_structural_confidence(state).score` and passed to every signal. Signals read the cached value. |
| The default 5-element signal tuple is sorted lazily on every `evaluate()` | Low | Low | Sorted **once** in `__init__` and stored as `self._signals: tuple[…]`. Verified by `test_policy_default_signal_order` reading the stored tuple directly. |
| `assert result.stop_reason is not None` in orchestrator could fire under PYTHONOPTIMIZE | Low | Low | Replace each `assert ...` with a real `if result.stop_reason is None: raise RuntimeError("Signal returned STOP without reason")`. Documented in step 11 of §6. |

---

## 10. Done Definition (Coder → Reviewer hand-off checklist)

- [ ] `app/seams/stopping.py` created with Protocol + 2 frozen dataclasses + `SignalResult` enum.
- [ ] `app/stopping/__init__.py`, `policy.py`, `signals/__init__.py`, and the 5 signal modules created (§5).
- [ ] `app/agent/run_state.py`: `has_ambiguity: bool = False` added (single-line diff).
- [ ] `app/agent/orchestrator.py`: 3 handler edits, 1 ctor kwarg, `_HONEST_UNANSWERABLE_SAFETY_ROUNDS` deleted, `TODO(BRD-09)` comment deleted. NO touches to the BRD-08 divergence / `detect_mismatch` block.
- [ ] ≥ 30 unit tests across `test_seams_stopping.py`, `test_stopping_signals.py`, `test_stopping_policy.py`, all green.
- [ ] `test_agent_orchestrator.py` and `test_agent_run_state.py` updated and green (§7.8, §7.9).
- [ ] `ruff check` clean on every modified / created file.
- [ ] `pyright --strict` clean on `app/stopping/`, `app/seams/stopping.py`, `app/agent/orchestrator.py`.
- [ ] Coverage ≥ 95 % on `app.stopping` and `app.seams.stopping`.
- [ ] No new event type; no FE↔BE contract change; `scripts/export_types.py` NOT re-run.
- [ ] All 4 acceptance criteria from BRD-09 §5 mapped to at least one passing test (§8).
- [ ] Memory bank updated: `decisions-history.md` entry; new `L-0XX` lesson if applicable (e.g. on coordinating two BRDs in parallel sessions).

---

## 11. Out of Scope (explicit)

- `DomainSafety` and `ConfidencePlateau` signals (BRD-09 §10, V2).
- Adaptive thresholds / per-question-type policy tuning (BRD-09 §10).
- An `AmbiguityDetectedEvent` **emitter** in a task (deferred BRD — classify or judge must set `state.has_ambiguity` AND emit the event). IP-09 only wires the **reader**.
- Folding the judge-attempts cap into `BudgetSignal` (O-07).
- A FE indicator that the policy "deferred" (the existing `StoppedEvent.stop_reason` is the only externally-visible artefact).
- Persisting per-signal evaluations (debug only — they live in structlog logs).
- Replacing `ConfidenceCalculator.check_sufficient` in `app/confidence/calculator.py` (BRD-08 territory; IP-09 leaves it intact and unused, with no test changes).

---

## 12. References

- BRD-09: [docs/implementation-phase/brds/BRD-09-stopping-signals.md](../brds/BRD-09-stopping-signals.md)
- BRD-08 (parallel): [docs/implementation-phase/brds/BRD-08-confidence-calculation.md](../brds/BRD-08-confidence-calculation.md)
- IP-08 (parallel plan): [implementation-plans/IP-08-confidence-calculation.md](IP-08-confidence-calculation.md)
- BRD-07 (FSM, shipped): [docs/implementation-phase/brds/BRD-07-agent-fsm.md](../brds/BRD-07-agent-fsm.md)
- Stopping signal analysis: [docs/understanding-phase/stopping-signal-analysis.md](../../understanding-phase/stopping-signal-analysis.md)
- RF-01 / RF-04 / RF-12 / RF-15: [docs/understanding-phase/requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
- Existing FSM orchestrator: [backend/app/agent/orchestrator.py](../../../backend/app/agent/orchestrator.py)
- Existing `RunState`: [backend/app/agent/run_state.py](../../../backend/app/agent/run_state.py)
- Existing `Source` seam (template for new seam): [backend/app/seams/source.py](../../../backend/app/seams/source.py)
- Existing confidence package (read-only dependency): [backend/app/confidence/](../../../backend/app/confidence/)
- L-010 (cancellation test pattern, reused in orchestrator integration tests): `.github/memory-bank/logs/lessons-learned.md`
