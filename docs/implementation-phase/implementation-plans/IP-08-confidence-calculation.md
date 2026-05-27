# Implementation Plan: BRD-08 Confidence Calculation Engine

**Plan ID:** IP-08
**BRD Reference:** [BRD-08-confidence-calculation.md](../brds/BRD-08-confidence-calculation.md)
**Created:** 2026-05-26
**Status:** Ready for Auditor (F2.S3)
**Implementation Order:** 9 of 19

---

## 1. Overview

Implement the **confidence calculation engine** that replaces the placeholder structural score currently used by the agent FSM (BRD-07) with the real weighted formula mandated by RF-12.

```
final_confidence = min(S, J)

S = 0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.15·C_no_conflict
J = JudgeVerdict.confidence
```

The deliverable is a self-contained `app.confidence` package plus **two surgical edits** to existing modules so the FSM consumes the new score immediately:

1. `app/agent/tasks/draft.py::evaluate_with_judge` — replace `state.coverage_ratio()` placeholder with `calculate_structural_confidence(state).score`.
2. `app/agent/orchestrator.py::_handle_judging` — replace the inline divergence calculation with `detect_mismatch()` and remove the now-redundant `_DIVERGENCE_THRESHOLD` constant.

**In scope (RF coverage from BRD-08 §2):**
- RF-12 — `final_confidence = min(S, J)` with the four weighted structural components.
- RF-15 — Source independence (domain diversity).
- RF-15 — S/J mismatch detection emitting `ConfidenceMismatchEvent`.

**Non-goals (deferred):**
- Wiring `ConfidenceCalculator.check_sufficient()` into the FSM as a stopping signal — that belongs to **BRD-09** (layered stopping policy). The method is implemented and unit-tested but not called by the orchestrator in this BRD.
- Adaptive thresholds, per-question-type weights, historical calibration — BRD-08 §10 (out of scope).
- Emitting a new dedicated `ConfidenceCalculatedEvent`. The judge already publishes structural+judge+final via `JudgeRuledEvent` (BRD-02); no new event type is added.

---

## 2. Architectural Alignment

| Rule (copilot-instructions §3) | Compliance |
|---|---|
| #1 Three plugin seams (`Source`, `StoppingSignal`, `OutputRenderer`) | The confidence package is **internal infrastructure**, not a seam. No new protocol is added. BRD-09 will wrap `ConfidenceCalculator.check_sufficient` behind a `StoppingSignal` later. |
| #2 Three not-seams (planner / storage / LLM) | Confidence is a fourth "not-seam" by inclusion: a single concrete implementation, no abstraction layer, no `@runtime_checkable` protocol. |
| #3 `stop_reason` is an enum | This BRD does not introduce any new stop reason. `judge_confirmed` continues to be the only confidence-gated terminal state. |
| #4 Events are append-only | No event mutation. `ConfidenceMismatchEvent` is already emitted by the orchestrator; this BRD only changes **how the divergence is computed**, not how it is recorded. |
| #5 Schema evolution = `extra="allow"` | `StructuralConfidence` and `ConfidenceResult` (in `app/domain/confidence.py`) already declare `ConfigDict(extra="allow")`. No changes to those models. |
| #7 FE↔BE contract | No event-shape changes. `scripts/export_types.py` does **not** need to run. |
| #8 `final_confidence = min(S, J)` (RF-12) | This BRD is the canonical implementation of rule #8. |
| English-only artifacts (L-001 / language policy) | All identifiers, docstrings, log keys, exception messages in English. |
| `pyright --strict` + `ruff` clean | `from __future__ import annotations`, no `Optional` from `typing` (use PEP 604 `X \| None`), explicit types, no `Any` leak. |
| Async-first | All public functions are **pure / synchronous** because they operate only on in-memory state. No async signature is added without need. |
| Mandatory unit tests (L-002) | Coder ships ≥ 25 unit tests, target ≥ 95 % coverage on `app/confidence/`. Existing tests under `backend/tests/test_agent_tasks_draft.py` and `test_agent_orchestrator.py` are updated to match the new structural score. |

---

## 3. Deviations from BRD-08 §4 (binding overrides)

BRD-08 §4 was authored before this plan inspected the existing FSM code. Each override below is binding for the Coder.

### O-01. Reuse existing domain models — do **not** duplicate `StructuralConfidence` / `ConfidenceResult`

BRD-08 §4.3 imports `StructuralConfidence` and `ConfidenceResult` from `app.domain.confidence`. **Both already exist** in [backend/app/domain/confidence.py](../../../backend/app/domain/confidence.py) with:

- `StructuralConfidence` — fields `coverage`, `agreement`, `diversity`, `no_conflict`, plus a `score` property that already computes the weighted sum with the exact weights from RF-12.
- `ConfidenceResult` — fields `structural`, `judge`, `final`, `threshold`, `passed`.

**Decision:** the Coder MUST import these models, not redefine them. The `StructuralWeights` dataclass in BRD-08 §4.3 is kept for **configurability of the calculator** (future tweaks) but the **canonical weights** are the ones baked into `StructuralConfidence.score`. To keep both consistent without divergence, `calculate_structural_confidence` does **not** accept a `weights` argument in V1 — it just returns a `StructuralConfidence` and the score property does the math. The `StructuralWeights` dataclass is **removed** from the plan.

### O-02. Remove unused `MismatchResult` import from `calculator.py`

BRD-08 §4.4 contains `from app.confidence.mismatch import detect_mismatch, MismatchResult` but `MismatchResult` is not referenced inside `calculator.py`. Drop it (ruff `F401`).

### O-03. PEP 604 union syntax — no `Optional` from `typing`

BRD-08 §4.5 declares `trust_flag: Optional[str]`. The repo convention is `str | None`. Replace:

```python
from typing import Optional
trust_flag: Optional[str] = None
```

with:

```python
trust_flag: str | None = None
```

and add `from __future__ import annotations` at the top of every new module.

### O-04. Replace the FSM placeholder in `tasks/draft.py`

`backend/app/agent/tasks/draft.py::evaluate_with_judge` currently contains:

```python
# Placeholder structural confidence until BRD-08 ships.
structural_confidence = state.coverage_ratio()
```

Replace with:

```python
from app.confidence import calculate_structural_confidence
...
structural_confidence = calculate_structural_confidence(state).score
```

The placeholder comment is deleted. `final_confidence = min(judge_confidence, structural_confidence)` already implements rule #8 and stays unchanged.

### O-05. Replace inline divergence in `orchestrator.py` and harmonize threshold to 0.2

`backend/app/agent/orchestrator.py` defines `_DIVERGENCE_THRESHOLD = 0.3` and computes:

```python
divergence = abs(judge_event.structural_confidence - judge_event.judge_confidence)
if divergence > _DIVERGENCE_THRESHOLD:
    await self.emit(ConfidenceMismatchEvent(..., trust_flag="structural/judge divergence > 0.3"))
```

BRD-08 §4.5 specifies the default mismatch threshold as **0.2** with a richer human-readable `trust_flag`. The orchestrator is the **only** call site of `_DIVERGENCE_THRESHOLD`, so the migration is local and safe.

**Decision:**
1. Delete `_DIVERGENCE_THRESHOLD = 0.3` and `_HONEST_UNANSWERABLE_SAFETY_ROUNDS` stays untouched.
2. Call `detect_mismatch(structural=..., judge=...)` and use its `has_mismatch` and `trust_flag` fields to emit the event.
3. The `ConfidenceMismatchEvent` schema in `app.domain.events` is **not modified**. The `trust_flag` string carried in the event is the one returned by `detect_mismatch`.

The change strictly tightens the gating from 0.3 to 0.2 (more events emitted, never fewer); no event becomes invalid retroactively. Existing tests that assert the old string literal `"structural/judge divergence > 0.3"` are updated to assert on the new richer string (see §6).

### O-06. `MismatchResult` stays a `@dataclass` (not Pydantic)

It is a transient internal helper, never serialized, never persisted, never crossing process boundaries. Pydantic adds no value here. Mark `frozen=True`.

### O-07. `ConfidenceCalculator.calculate(...)` ignores the unused import

BRD-08 §4.4 also imports `MismatchResult` and re-imports `StructuralConfidence` inside `calculator.py`. The `calculate(...)` method does **not** call `detect_mismatch` — mismatch detection is the orchestrator's job (O-05). Keep the imports minimal: `RunState`, `calculate_structural_confidence`, `ConfidenceResult`.

### O-08. `check_sufficient(...)` is implemented but NOT wired

`ConfidenceCalculator.check_sufficient(state)` is delivered with unit tests but the orchestrator does **not** call it in this BRD (would expand scope into BRD-09's layered stopping policy). A `TODO(BRD-09)` comment marks the future integration site in [orchestrator.py](../../../backend/app/agent/orchestrator.py) just above `_handle_judging`.

---

## 4. Module Layout (final, post-deviations)

```
backend/app/confidence/
├── __init__.py            # Public exports
├── structural.py          # S components + calculate_structural_confidence
├── calculator.py          # ConfidenceCalculator (calculate + check_sufficient)
└── mismatch.py            # detect_mismatch + MismatchResult dataclass
```

### 4.1 `app/confidence/structural.py`

Pure functions, all synchronous, all `from __future__ import annotations`:

| Function | Signature | Behaviour |
|---|---|---|
| `calculate_coverage` | `(state: RunState) -> float` | `len(state.covered_claims) / len(state.sub_claims)`, returns `0.0` when no sub-claims. |
| `calculate_agreement` | `(evidence: list[EvidenceItem]) -> float` | Confidence-weighted ratio of evidence with `polarity == "supports"`. Returns `0.0` when `total_weight == 0` or empty. |
| `calculate_diversity` | `(evidence: list[EvidenceItem]) -> float` | Unique-domain count → score table: `{0→0.0, 1→0.3, 2→0.5, 3→0.7, 4→0.9, ≥5→1.0}`. Domain extracted by stripping scheme + path and the literal `www.` prefix. |
| `calculate_no_conflict` | `(state: RunState) -> float` | `max(0.0, 1.0 - len(state.contradictions) / max(len(state.evidence), 1))`. When `evidence` is empty, returns `1.0` (no evidence ⇒ no conflict by construction). |
| `calculate_structural_confidence` | `(state: RunState) -> StructuralConfidence` | Composes the four components into a `StructuralConfidence`. **No `weights` parameter** (O-01). |

Edge cases that MUST have dedicated tests:
- Empty `sub_claims` → `coverage == 0.0`.
- All evidence is `polarity == "refutes"` → `agreement == 0.0`.
- Evidence with `confidence == 0.0` everywhere → `agreement == 0.0` without `ZeroDivisionError`.
- One source URL without scheme (`example.com/foo`) and one with `https://www.example.com/bar` → same domain (one entry in the set).
- `contradictions` count > `evidence` count → clamped to `0.0`, never negative.

### 4.2 `app/confidence/calculator.py`

```python
class ConfidenceCalculator:
    def __init__(self, threshold: float = 0.7) -> None: ...
    def calculate(self, state: RunState, judge_confidence: float) -> ConfidenceResult: ...
    def check_sufficient(self, state: RunState) -> bool: ...
```

Behaviour:
- `calculate(...)` builds `StructuralConfidence`, computes `final = min(structural.score, judge_confidence)`, and returns `ConfidenceResult(structural, judge_confidence, final, self.threshold, final >= self.threshold)`.
- `check_sufficient(...)` returns `True` iff `coverage >= 0.6 AND agreement >= 0.5 AND no_conflict >= 0.7`. Not called by the FSM in V1 (O-08).
- The constructor validates `0.0 <= threshold <= 1.0`; raises `ValueError` otherwise.

### 4.3 `app/confidence/mismatch.py`

```python
@dataclass(frozen=True)
class MismatchResult:
    has_mismatch: bool
    structural: float
    judge: float
    divergence: float
    trust_flag: str | None

def detect_mismatch(structural: float, judge: float, threshold: float = 0.2) -> MismatchResult: ...
```

- `divergence = abs(structural - judge)`.
- `has_mismatch = divergence > threshold` (strict greater, matches BRD-08 §4.5).
- `trust_flag` is `None` when `not has_mismatch`. When mismatch holds:
  - `structural > judge` → `"Structural metrics ({s:.0%}) exceed judge assessment ({j:.0%}). Judge may have identified issues not captured in automated scoring."`
  - `judge >= structural` → `"Judge assessment ({j:.0%}) exceeds structural metrics ({s:.0%}). Evidence may be stronger than coverage metrics suggest."`
- Boundary at `divergence == threshold` → `has_mismatch = False` (consistency with BRD-08 §4.5 "if > threshold").

### 4.4 `app/confidence/__init__.py`

```python
from app.confidence.calculator import ConfidenceCalculator
from app.confidence.mismatch import MismatchResult, detect_mismatch
from app.confidence.structural import (
    calculate_agreement,
    calculate_coverage,
    calculate_diversity,
    calculate_no_conflict,
    calculate_structural_confidence,
)

__all__ = [
    "ConfidenceCalculator",
    "MismatchResult",
    "calculate_agreement",
    "calculate_coverage",
    "calculate_diversity",
    "calculate_no_conflict",
    "calculate_structural_confidence",
    "detect_mismatch",
]
```

Alphabetical order to satisfy `ruff RUF022` (already enforced in the repo).

---

## 5. Implementation Steps (ordered)

| # | File | Action | LOC est. |
|---|---|---|---|
| 1 | `backend/app/confidence/__init__.py` | Create with exports listed in §4.4 | 15 |
| 2 | `backend/app/confidence/structural.py` | Create the five pure functions per §4.1 | ~90 |
| 3 | `backend/app/confidence/mismatch.py` | Create `MismatchResult` + `detect_mismatch` per §4.3 | ~55 |
| 4 | `backend/app/confidence/calculator.py` | Create `ConfidenceCalculator` per §4.2 | ~50 |
| 5 | `backend/app/agent/tasks/draft.py` | Replace placeholder structural score (O-04). Single 2-line edit + 1 new import. | 3 |
| 6 | `backend/app/agent/orchestrator.py` | Replace `_DIVERGENCE_THRESHOLD` + inline divergence with `detect_mismatch` (O-05). Remove the constant. | ~10 |
| 7 | `backend/tests/test_confidence_structural.py` | New unit tests — §6.1 | ~150 |
| 8 | `backend/tests/test_confidence_mismatch.py` | New unit tests — §6.2 | ~90 |
| 9 | `backend/tests/test_confidence_calculator.py` | New unit tests — §6.3 | ~100 |
| 10 | `backend/tests/test_agent_tasks_draft.py` | Update existing assertions on `structural_confidence` to match the new weighted score | ~30 |
| 11 | `backend/tests/test_agent_orchestrator.py` | Update divergence test (threshold 0.3 → 0.2, new `trust_flag` string) | ~10 |

**Total LOC budget:** ~600 (under the 4–6 h pair-session ceiling per `copilot-instructions.md §6`).

**Order matters:**
- Steps 1–4 are independent — Coder MAY create them in parallel.
- Step 5 depends on step 1 (`calculate_structural_confidence` must be importable).
- Step 6 depends on step 3.
- Steps 7–9 depend on the corresponding source files.
- Steps 10–11 depend on steps 5 and 6 respectively. **Run `pytest backend/tests/test_agent_*` before opening the PR** — the FSM tests are the canary.

---

## 6. Test Plan

All tests use **pytest + pytest-asyncio**. Target ≥ 95 % coverage on `app/confidence/` and 100 % on every public symbol.

### 6.1 `test_confidence_structural.py`

| Case | Assertion |
|---|---|
| `test_coverage_with_no_claims` | `calculate_coverage(state)` == `0.0` |
| `test_coverage_all_covered` | 3 claims, 3 covered → `1.0` |
| `test_coverage_partial` | 3 claims, 2 covered → `pytest.approx(2/3)` |
| `test_agreement_empty_evidence` | `0.0` |
| `test_agreement_all_supports` | 3 evidence@0.8 → `1.0` |
| `test_agreement_mixed` | 2 supports@0.9 + 1 refutes@0.5 → `1.8/2.3` |
| `test_agreement_zero_total_weight` | All evidence with `confidence=0.0` → `0.0` (no `ZeroDivisionError`) |
| `test_diversity_no_evidence` | `0.0` |
| `test_diversity_one_domain` | `0.3` |
| `test_diversity_two_domains` | `0.5` |
| `test_diversity_five_or_more` | `1.0` |
| `test_diversity_normalizes_www_and_scheme` | `https://www.x.com/a` and `x.com/b` collapse to 1 domain |
| `test_no_conflict_no_evidence` | `1.0` |
| `test_no_conflict_no_contradictions` | `1.0` with N evidence |
| `test_no_conflict_more_contradictions_than_evidence` | clamped to `0.0` |
| `test_structural_full_state` | Builds a realistic `RunState` and asserts the four components AND the weighted `.score` |
| AC-01 (BRD-08 §5) | Covered by `test_coverage_partial` |
| AC-02 (BRD-08 §5) | Covered by `test_diversity_two_domains` + `test_diversity_five_or_more` |

### 6.2 `test_confidence_mismatch.py`

| Case | Assertion |
|---|---|
| `test_no_mismatch_below_threshold` | `S=0.8, J=0.7` → `has_mismatch=False, trust_flag is None` |
| `test_no_mismatch_at_threshold` | `S=0.8, J=0.6` (diff exactly 0.2) → `has_mismatch=False` (strict `>`) |
| `test_mismatch_structural_higher` | `S=0.85, J=0.55` → `has_mismatch=True`, `trust_flag` contains `"Structural metrics"` and both percentages |
| `test_mismatch_judge_higher` | `S=0.30, J=0.80` → `has_mismatch=True`, `trust_flag` contains `"Judge assessment"` |
| `test_mismatch_custom_threshold` | `threshold=0.1`, `S=0.5, J=0.65` → `has_mismatch=True` |
| `test_mismatch_divergence_value` | `S=0.85, J=0.55` → `divergence == pytest.approx(0.30)` |
| AC-04 (BRD-08 §5) | Covered by `test_mismatch_structural_higher` |

### 6.3 `test_confidence_calculator.py`

| Case | Assertion |
|---|---|
| `test_init_default_threshold` | `ConfidenceCalculator().threshold == 0.7` |
| `test_init_invalid_threshold_raises` | `ConfidenceCalculator(threshold=1.5)` → `ValueError` |
| `test_calculate_final_uses_min_S_J` | S high, J low → `final == J` and vice-versa |
| `test_calculate_passed_above_threshold` | `final >= threshold` → `passed=True` |
| `test_calculate_passed_below_threshold` | `final < threshold` → `passed=False` |
| `test_calculate_returns_structural_unchanged` | Inspect the four components of `result.structural` |
| `test_check_sufficient_true` | Coverage 0.7 + agreement 0.6 + no_conflict 0.8 → `True` |
| `test_check_sufficient_low_coverage` | Coverage 0.5 → `False` |
| `test_check_sufficient_low_agreement` | Agreement 0.4 → `False` |
| `test_check_sufficient_too_many_conflicts` | no_conflict 0.5 → `False` |
| AC-03 (BRD-08 §5) | Covered by `test_calculate_final_uses_min_S_J` |
| AC-05 (BRD-08 §5) | Covered by `test_calculate_passed_above_threshold` / `_below_threshold` |

### 6.4 FSM regression updates

- `test_agent_tasks_draft.py` — `evaluate_with_judge` is mocked at the LLM seam; recompute the expected `structural_confidence` using the real `calculate_structural_confidence(state).score` against the fixture's `RunState`.
- `test_agent_orchestrator.py` — the existing divergence test that uses `S=0.8, J=0.4` (divergence 0.4) still triggers a `ConfidenceMismatchEvent` under the new 0.2 threshold; update the asserted `trust_flag` string to the new richer text. If any test was tuned exactly at the old 0.3 boundary (e.g. `S=0.7, J=0.45`, divergence 0.25 — used to NOT trigger), it MUST now assert the event IS emitted.

### 6.5 Verification commands

```powershell
# Backend, from repo root
cd backend
uv run pytest tests/test_confidence_structural.py tests/test_confidence_mismatch.py tests/test_confidence_calculator.py -v
uv run pytest tests/test_agent_tasks_draft.py tests/test_agent_orchestrator.py -v
uv run pytest --cov=app.confidence --cov-report=term-missing
uv run ruff check app/confidence/ tests/test_confidence_*.py
uv run pyright app/confidence/
```

All four commands MUST exit with code 0. Coverage on `app.confidence` MUST be ≥ 95 %.

---

## 7. Acceptance Criteria → Test Mapping

| BRD-08 AC | Test ID |
|---|---|
| AC-01 Coverage Calculation Correct | `test_coverage_partial` |
| AC-02 Diversity Rewards Multiple Sources | `test_diversity_two_domains`, `test_diversity_five_or_more` |
| AC-03 Final Uses `min(S, J)` | `test_calculate_final_uses_min_S_J` |
| AC-04 Mismatch Detected When Divergent | `test_mismatch_structural_higher`, `test_mismatch_judge_higher` |
| AC-05 Threshold Gating Works | `test_calculate_passed_above_threshold`, `test_calculate_passed_below_threshold` |

All five ACs MUST have at least one green test pointing at them.

---

## 8. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Tightening the divergence threshold (0.3 → 0.2) flakes existing orchestrator tests | Med | Med | Step 11 is explicit; the change is asserted, not silent. |
| Domain extraction is too naive (`.split("/")[0]`) and groups `https://a.example.com` with `https://b.example.com` | Med | Low | V1 ships the simple extractor (BRD-08 §10 out of scope: per-subdomain weighting). Document with an inline comment that distinguishes subdomains is BRD-08-V2 work. |
| `StructuralConfidence` weights drift between `score` property and a hypothetical `StructuralWeights` argument | High | N/A | Eliminated by O-01 — `StructuralWeights` is not introduced. |
| Floating-point asserts (`agreement == 0.625` etc.) cause test flakes | Low | Low | Use `pytest.approx` everywhere structural math is asserted. |
| Importing `app.confidence` triggers a circular import with `app.agent.run_state` | Low | Low | `structural.py` imports `RunState` and `EvidenceItem` only inside function bodies' type annotations via `from __future__ import annotations`, and at module top via direct import — `app.agent.run_state` does not import `app.confidence`, so no cycle. Verified by `mcp_pylance_mcp_s_pylanceImports` before merge. |

---

## 9. Done Definition (Coder → Reviewer hand-off checklist)

- [ ] `app/confidence/{__init__,structural,calculator,mismatch}.py` created and exported.
- [ ] `app/agent/tasks/draft.py` placeholder replaced (O-04).
- [ ] `app/agent/orchestrator.py` divergence logic replaced (O-05); `_DIVERGENCE_THRESHOLD` constant removed.
- [ ] ≥ 25 unit tests across `test_confidence_*.py` files, all green.
- [ ] FSM regression tests (`test_agent_tasks_draft.py`, `test_agent_orchestrator.py`) updated and green.
- [ ] `ruff check` clean on every modified file.
- [ ] `pyright --strict` clean on `app/confidence/`.
- [ ] Coverage ≥ 95 % on `app/confidence/`.
- [ ] No new event type; no FE↔BE contract change; `scripts/export_types.py` not re-run.
- [ ] All 5 acceptance criteria from BRD-08 §5 mapped to at least one passing test (§7).
- [ ] Memory bank updated: `decisions-history.md` entry and (if applicable) a new `L-0XX` lesson.

---

## 10. Out of Scope (explicit)

- Wiring `check_sufficient()` into the stopping policy (BRD-09).
- Per-subdomain or PageRank-weighted diversity (BRD-08 V2).
- Adaptive / user-tuned `StructuralWeights` (BRD-08 §10).
- Persisting a `ConfidenceCalculatedEvent` — `JudgeRuledEvent` already carries `structural_confidence` + `final_confidence`.
- UI surfacing of the four S components — the frontend gets them via the unchanged `JudgeRuledEvent` payload (BRD-13).

---

## 11. References

- BRD-08: [docs/implementation-phase/brds/BRD-08-confidence-calculation.md](../brds/BRD-08-confidence-calculation.md)
- BRD-07 (FSM, already shipped): [docs/implementation-phase/brds/BRD-07-agent-fsm.md](../brds/BRD-07-agent-fsm.md)
- IP-07 (FSM plan, predecessor): [implementation-plans/IP-07-agent-fsm.md](IP-07-agent-fsm.md)
- RF-12 (confidence formula): [docs/understanding-phase/requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
- RF-15 (source independence + mismatch): same.
- Confidence calculation deep-dive: [docs/understanding-phase/confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- Existing domain models: [backend/app/domain/confidence.py](../../../backend/app/domain/confidence.py)
- Placeholder being replaced: [backend/app/agent/tasks/draft.py](../../../backend/app/agent/tasks/draft.py) line 85.
- Divergence logic being replaced: [backend/app/agent/orchestrator.py](../../../backend/app/agent/orchestrator.py) line 213.
