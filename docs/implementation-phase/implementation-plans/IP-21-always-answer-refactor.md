# Implementation Plan: "Always Answer" Refactor (RF-17 / RF-18 / RF-19)

**Plan ID:** IP-21
**Source proposal:** [`docs/understanding-phase/research-method-refactor-proposal.md`](../../understanding-phase/research-method-refactor-proposal.md) (ratified 2026-05-27)
**Amended RFs:** RF-01·E, RF-02, RF-06 (overrides) + RF-17, RF-18, RF-19 (new)
**Created:** 2026-05-27
**Status:** Ready for Coder (autonomous execution) — gaps closed 2026-05-27 — 3 post-audit holes closed (Fixes A/B/C)
**Implementation order:** Single multi-phase plan; supersedes any future IP-* for the same surfaces

---

## 0. Context for autonomous Copilot execution

### 0.1 What this plan delivers

Move Novum from "stop honestly when sources fail" to "**always emit a useful answer**, with a confidence and ceiling that reflects what the evidence actually supports". The 7 `StopReason` values collapse to **4** (`judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`). The `honest_*` rejection paths are replaced by **six answer templates** chosen via a deterministic `AnswerKind` resolver and bounded by a per-kind confidence ceiling.

### 0.2 Binding documents (read first; do not diverge silently)

| Topic | File |
|---|---|
| Refactor proposal (the contract) | `docs/understanding-phase/research-method-refactor-proposal.md` |
| RF amendments table | `docs/understanding-phase/requirement-understanding.md` (amendment block at top) |
| Per-kind ceilings + new weights | `docs/understanding-phase/confidence-calculation.md` (amendment block) |
| Mapping `honest_*` → `AnswerKind` | `docs/understanding-phase/stopping-signal-analysis.md` (amendment block) |
| Judge provider (Anthropic Haiku) | `docs/technical-phase/ai-services.md` (amendment block) |
| Repo conventions | `.github/copilot-instructions.md` |

### 0.3 Architectural rules that constrain every WP

From `.github/copilot-instructions.md` §3:

1. **Plugin seams stay limited to three** (`Source`, `StoppingSignal`, `OutputRenderer`). Do **not** introduce a new "AnswerRenderer" seam — the six templates live inside the synthesizer prompt + a single internal renderer.
2. **Planner / storage / LLM provider are deliberately not seams.** Adding Anthropic Haiku in WP-5 is **not** a new abstraction: extend the existing `llm/client.py` provider switch.
3. `stop_reason` is an enum, never free text. The collapse from 7 → 4 lives in `app/domain/enums.py` + the Alembic migration + the FE generated types — nowhere else.
4. **Events are append-only.** Add new event types (`SaturationDetected`, `JudgeProviderDegraded`) as new discriminated-union members; never mutate existing event shapes destructively. Optional fields only.
5. **Schema evolution = `extra="allow"` + optional keys only.** Every new field on an existing event MUST be `X | None = None`.
6. **UI surfaces every trust guarantee.** When ceilings clip `S`, the trace must show it (RF-19).
7. **FE↔BE contract is generated**, never hand-edited (`scripts/export_types.py`).
8. `final_confidence = min(S_effective, J)` where `S_effective = S_raw · kind_ceiling[AnswerKind]` (was `min(S, J)`).

### 0.4 Current repo state (as of 2026-05-27, post-partial WP-1)

Edits already in main that this plan must **finish, not redo**:

| File | State |
|---|---|
| `backend/app/domain/enums.py` | ✅ `AnswerKind` added; `QuestionType` extended to 8 values; `StopReason` still 7. |
| `backend/app/domain/events.py` | ✅ Optional `answer_kind` field on `JudgeRuledEvent` and `StoppedEvent`. |
| `backend/app/llm/models.py` | ✅ Optional `answer_kind` on `SynthesizedAnswer`. |
| `backend/tests/test_domain_enums.py` | ✅ Counts updated to 8 / 6 / 7; `AnswerKind` tests added. |
| `backend/app/agent/tasks/__init__.py` | ⚠️ **Broken import** — references `select_answer_kind` module that the user deleted. **WP-1 Step 1 below recreates the module.** |
| `backend/app/agent/tasks/select_answer_kind.py` | ❌ Missing. Recreate in WP-1. |

**First action of WP-1 is to make the repo green again.** Do not start WP-2 until `pytest -q` is fully green.

### 0.5 Phase order (non-negotiable)

```
WP-0    Reconciliation (make repo green)
WP-1    Additive prelude (AnswerKind resolver + tests)         ← finishes here
WP-2    Six synthesizer templates + draft.py routing
          └─ WP-2.0  Classifier prompt extension (8 QuestionType values)
WP-2.5  Contradiction detector audit & contract
WP-3    Per-kind ceilings + StopReason collapse + migration   (depends on WP-2.5)
WP-4    Saturation signal + in-memory embeddings
WP-5    Independent verifier (Anthropic Claude Haiku)
WP-6    Cross-run question memory (in-memory only)
```

Each WP ends with a hard gate: `pytest -q` + `pyright --strict` + `ruff check` + frontend `vitest run --reporter=basic` must all pass before opening the next WP.

### 0.6 Language and style rules

- Code, comments, docstrings, log messages, exception messages, LLM **system** prompts, migration descriptions, env var names → **English** only.
- LLM **runtime** outputs follow the user's language (Spanish by default) via a prompt instruction.
- No `Any` leaks. PEP 604 unions (`X | None`). `from __future__ import annotations` at the top of every new module.
- Imports sorted by `ruff`. No `noqa` unless paired with a `# ruff: ` comment explaining why.
- Tests are mandatory in the same change. ≥ 80 % line coverage on every new module; aim higher on pure-logic modules (resolver, ceilings, embeddings).

### 0.7 Memory protocol (mandatory)

Before each WP:
1. Read `.github/memory-bank/shared/project-context.md`
2. Read `.github/memory-bank/logs/lessons-learned.md`

After each WP:
1. Append a row to `.github/memory-bank/logs/decisions-history.md` (`WP-x landed`, files touched, gate result).
2. Append a lesson to `.github/memory-bank/logs/lessons-learned.md` only if a non-obvious issue was hit (failed import, FE type drift, etc.).
3. Do **not** create new top-level memory files for this refactor.

### 0.8 Question → AnswerKind acceptance matrix (BINDING)

This matrix is the authoritative smoke-test contract derived from `docs/q-for-testing.md`. **Every WP that touches the resolver, the synthesizer templates, or the stop logic MUST keep this table green.** The matrix exists because the challenge spec values *defensible behaviour on real questions* over abstract correctness.

| # | Question (abridged) | `QuestionType` | Expected `AnswerKind` | Resolver inputs (S, cov, agr, amb) | Critical capabilities exercised |
|---|---|---|---|---|---|
| 1 | Capital of Japan | `FACTUAL` | `DIRECT` | `S=0.95, cov=1.0, agr=1.0, amb=False` | early-stop on round 1 (G8) |
| 2 | PostgreSQL vs MongoDB for a small SaaS | `COMPARATIVE` | `WEIGHTED` | `S=0.70, cov=1.0, agr=0.55, amb=False` | criteria generation, context awareness |
| 3 | What is the best programming language? | `COMPARATIVE` + `AmbiguityDetected` | `BEST_EFFORT` | `S=0.60, cov=0.8, agr=0.5, amb=True` | empty-comparative detector (G9) |
| 4 | Is intermittent fasting healthy? | `FACTUAL` or `CAUSAL` | `WEIGHTED` | `S=0.65, cov=1.0, agr=0.45, amb=False` | mandatory `contradictions` field (G10) |
| 5 | Long-term risks of AI-generated code | `PREDICTIVE_FUTURE` | `SCENARIO` | `S=0.60, cov=0.7, agr=0.6, amb=False` (QuestionType priority wins) | probability bands, drivers |
| 6 | EDA vs synchronous microservices at scale | `COMPARATIVE` (architecture tradeoff) | `WEIGHTED` | `S=0.70, cov=1.0, agr=0.55, amb=False` — routes via `cov_complete AND agr<0.6 → WEIGHTED` (WP-0 resolver) | Architecture tradeoff between two named alternatives — `WEIGHTED` candidates with criteria-weighted scores is defensible. |
| 7 | Best long-term memory approach for AI agents | `STATE_OF_ART` | `WEIGHTED` if converges; `BEST_EFFORT` if saturated | `S=0.55, cov=0.6, agr=0.55, amb=False` | real saturation signal (G1), high budget (G11) |
| 8 | Could AI replace mid-level engineers in 10y? | `PREDICTIVE_FUTURE` | `SCENARIO` | `S=0.50, cov=0.7, agr=0.4, amb=False` (QuestionType priority wins) | multi-scenario + expert contradictions surfaced |

> **Resolver-input footnote (binding for `test_resolver_acceptance.py`, G13).** Numbers are calibrated against the resolver thresholds (`_DIRECT_MIN_S=0.75`, `_DIRECT_MIN_COVERAGE=1.0`, `_DIRECT_MIN_AGREEMENT=0.6`, `_WEIGHTED_AGREEMENT_CEILING=0.6`, `_BEST_EFFORT_COVERAGE_FLOOR=0.5`) so each row deterministically routes to its expected kind. They represent realistic post-search scores, not the LLM judge's optimism. Rows 5 and 8 carry `QuestionType = PREDICTIVE_FUTURE`, which wins at the resolver's priority stage before any S/cov/agr/amb branch is reached — the numeric columns are kept for symmetry and to document the underlying evidence quality. Row 6 (post-audit fix C, 2026-05-27) is classified as `COMPARATIVE` and routes through the numeric branch: `coverage=1.0` is complete AND `agreement=0.55 < 0.6` → `WEIGHTED`. The 0.55 agreement reflects the realistic spread between EDA-favouring and microservices-favouring expert sources at scale; nudging it ±0.05 keeps the same routing.

Three layers of enforcement (built across the WPs):
- **Static (CI)**: `backend/tests/test_resolver_acceptance.py` (G13) builds representative `AnswerKindInputs` per row and asserts the resolver output. Runs on every commit, independent of LLM availability.
- **Dynamic (golden trace)**: each WP's golden-trace fixture in `backend/tests/fixtures/runs/` covers at least one row with mocked LLM/Tavily responses.
- **Smoke (pre-release per WP)**: run all 8 questions against `https://novum.duckdns.org`; record run IDs in the WP-final memory log.

If a future change collapses two rows into the same kind or makes the matrix unstable, that change is **out of scope** for this plan — open a new IP.

### 0.9 Embedding provider decision (M1 — FINAL)

All embeddings (saturation novelty in WP-4, question index in WP-6) use **OpenAI `text-embedding-3-small` via `litellm`**, not local `sentence-transformers` and not GitHub Models. Reasons:
- Hetzner VPS has limited disk for ML wheels (~200 MB saved vs local models).
- `litellm` already wraps the LLM provider switch; one less abstraction.
- Cold-start latency on local models is unacceptable for the 15-second SSE heartbeat budget.
- **GitHub Models does not currently expose `text-embedding-*` endpoints (verified 2026-05-27).** A dedicated OpenAI key is required.

Binding configuration:
- litellm model string: `openai/text-embedding-3-small`
- New required env var: `OPENAI_API_KEY: SecretStr` (added in `app/config.py` in WP-4; documented in `docs/technical-phase/ai-services.md`)
- Cost note: ~$0.02 / 1M tokens; saturation + question-index combined budget per run < 1k tokens → negligible.

---

## WP-0 — Reconciliation (≈ 15 min)

### Objective
Restore green pipeline before adding more code. No behavioural change.

### Steps

1. **Recreate `backend/app/agent/tasks/select_answer_kind.py`** with the exact resolver below. This is the same module the user deleted; it is required by the existing `tasks/__init__.py` import.
2. Run `cd backend && uv run pytest -q` to confirm all existing tests pass plus the new `test_domain_enums.py` assertions.
3. Run `uv run pyright --strict backend/app backend/tests` and `uv run ruff check backend`.

### File: `backend/app/agent/tasks/select_answer_kind.py` (new)

```python
"""Deterministic ``AnswerKind`` resolver (RF-17; consumed by WP-2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import AnswerKind, QuestionType


@dataclass(frozen=True, slots=True)
class AnswerKindInputs:
    """Inputs to :func:`select_answer_kind`. All scores in ``[0, 1]``."""

    question_type: QuestionType
    structural_confidence: float
    coverage: float
    agreement: float
    ambiguity_flag: bool = False


_DIRECT_MIN_S = 0.75
_DIRECT_MIN_COVERAGE = 1.0
_DIRECT_MIN_AGREEMENT = 0.6
_WEIGHTED_AGREEMENT_CEILING = 0.6
_BEST_EFFORT_COVERAGE_FLOOR = 0.5


def select_answer_kind(inputs: AnswerKindInputs) -> AnswerKind:
    """Return the ``AnswerKind`` for the given run state (deterministic).

    Priority order:
      1. ``personal_private``     → ``ETHICAL_REDIRECT``
      2. ``predictive_future``    → ``SCENARIO``
      3. ``subjective_opinion``   → ``TRADEOFF``
      4. ambiguity OR cov < 0.5   → ``BEST_EFFORT``
      5. cov complete, agr < 0.6  → ``WEIGHTED``
      6. cov complete, S ≥ 0.75,
         agr ≥ 0.6                → ``DIRECT``
      7. else                     → ``BEST_EFFORT``
    """
    match inputs.question_type:
        case QuestionType.PERSONAL_PRIVATE:
            return AnswerKind.ETHICAL_REDIRECT
        case QuestionType.PREDICTIVE_FUTURE:
            return AnswerKind.SCENARIO
        case QuestionType.SUBJECTIVE_OPINION:
            return AnswerKind.TRADEOFF
        case _:
            pass

    if inputs.ambiguity_flag or inputs.coverage < _BEST_EFFORT_COVERAGE_FLOOR:
        return AnswerKind.BEST_EFFORT

    coverage_complete = inputs.coverage >= _DIRECT_MIN_COVERAGE
    if coverage_complete and inputs.agreement < _WEIGHTED_AGREEMENT_CEILING:
        return AnswerKind.WEIGHTED
    if (
        coverage_complete
        and inputs.structural_confidence >= _DIRECT_MIN_S
        and inputs.agreement >= _DIRECT_MIN_AGREEMENT
    ):
        return AnswerKind.DIRECT
    return AnswerKind.BEST_EFFORT


__all__ = ("AnswerKindInputs", "select_answer_kind")
```

### Acceptance
- `pytest -q` → 0 failed, 0 errors.
- `pyright --strict` → 0 errors.
- `ruff check` → clean.

---

## WP-1 — Additive prelude (resolver tests) (≈ 30 min)

### Objective
Lock down the resolver with explicit unit tests. No production behaviour change yet.

### Files

| File | Action |
|---|---|
| `backend/tests/test_select_answer_kind.py` | new |

### Test matrix (must all be present)

| ID | Inputs | Expected `AnswerKind` |
|---|---|---|
| T1 | `PERSONAL_PRIVATE`, S=0.9, cov=1.0, agr=1.0, amb=False | `ETHICAL_REDIRECT` |
| T2 | `PREDICTIVE_FUTURE`, S=0.9, cov=1.0, agr=1.0, amb=False | `SCENARIO` |
| T3 | `SUBJECTIVE_OPINION`, S=0.9, cov=1.0, agr=1.0, amb=False | `TRADEOFF` |
| T4 | `FACTUAL`, S=0.8, cov=1.0, agr=0.7, amb=False | `DIRECT` |
| T5 | `COMPARATIVE`, S=0.6, cov=1.0, agr=0.4, amb=False | `WEIGHTED` |
| T6 | `FACTUAL`, S=0.9, cov=0.4, amb=False | `BEST_EFFORT` (coverage floor) |
| T7 | `STATE_OF_ART`, S=0.9, cov=1.0, agr=0.9, amb=True | `BEST_EFFORT` (ambiguity wins) |
| T8 | `CAUSAL`, S=0.7, cov=1.0, agr=0.7, amb=False | `BEST_EFFORT` (S below 0.75, agr above weighted ceiling → falls through) |
| T9 | Parametrised: all 8 `QuestionType` with the "good" path | each returns the correct kind |

Use `pytest.mark.parametrize` for T9. No mocks — pure function.

### Acceptance
- `pytest backend/tests/test_select_answer_kind.py -q` → all pass.
- Branch coverage on `select_answer_kind.py` = 100 %.
- Memory: append `D-WP-1 done` to `decisions-history.md`.

---

## WP-2 — Six synthesizer templates + ambiguity wiring + contradiction surfacing (≈ 4 h)

### Objective
Make the synthesizer LLM produce one of six structured payload shapes driven by `AnswerKind`. Wire `draft.py` to pass the kind to the synthesizer and validate the response shape. **Also fix three gaps that block matrix questions 3, 4 and 8 (G3 / G9 / G10):**
- Derive `ambiguity_flag` from the run's events instead of leaving it dangling (G3).
- Make `classify.py` / `plan.py` emit `AmbiguityDetectedEvent` for empty comparatives ("best X", "should I") that lack stated criteria (G9).
- When any `ContradictionDetectedEvent` exists in the run, force the synthesizer to populate the new `contradictions` field; reject the output otherwise (G10).

### WP-2.0 — Classifier prompt extension (post-audit Fix A, 2026-05-27)

**Run this BEFORE the synthesizer-template subtasks.** It unblocks matrix rows 5 (Q5 — long-term AI risks), 6 (Q6 — EDA vs microservices, now `COMPARATIVE`), and 8 (Q8 — AI replacing engineers, plus Q7 "best programming language" subjectivity, plus the personal-private guardrail).

**Goal.** Extend the classifier system prompt so the LLM can emit all 8 `QuestionType` values instead of only the original 5. WP-1 added `PREDICTIVE_FUTURE`, `SUBJECTIVE_OPINION`, `PERSONAL_PRIVATE` to the Python enum, but the LLM prompt was never updated — in production the classifier would never emit Types 6/7/8 and Q5/Q6/Q8 would silently misroute.

**Files.** Discovery rule for the Coder:
- If `backend/app/llm/prompts/classifier.py` exists, **that** is the canonical prompt module — modify there.
- Otherwise the system prompt lives inline in `backend/app/agent/tasks/classify.py` — modify the prompt string there.
- Grep target: `grep -rn "QuestionType\|classifier" backend/app/llm/prompts backend/app/agent/tasks/classify.py`. Pick whichever file already holds the system-prompt string.

**Required content of the new prompt section.** Add (English only) a markdown bullet list with one line per `QuestionType`, in the exact form below — examples are binding for the new types so the LLM has anchor points the classifier tests can rely on:

- `factual` — single verifiable fact. Example: "What is the capital of Japan?"
- `comparative` — explicit comparison of named alternatives, including "Should X use A or B?" style architecture decisions. Example: "Is PostgreSQL or MongoDB better for a small SaaS?", "Should a high-scale AI platform use event-driven architecture or synchronous microservices?"
- `definitional` — asks what a concept means. Example: "What is event sourcing?"
- `state_of_art` — asks the current best/leading approach for a technical problem. Example: "What is the most promising approach for long-term memory in AI agents?"
- `causal` — asks why or how-caused. Example: "Why did the 2008 crisis happen?"
- `predictive_future` — asks about future risks/trends/long-term outcomes with explicit time horizon or "long-term" wording. Example: "What are the long-term risks of AI-generated code in enterprise systems?", "Could AI systems replace mid-level software engineers within the next 10 years?"
- `subjective_opinion` — asks for a personal "best" with NO objective criteria. Distinguish from `comparative` (which names alternatives). Example: "What is the best programming language?"
- `personal_private` — solicits private/medical/financial advice about the user's own life. Example: "Should I quit my job?"

**Output contract.** The LLM must return exactly one of these 8 strings (lowercase, snake_case): `factual | comparative | definitional | state_of_art | causal | predictive_future | subjective_opinion | personal_private`.

**Validation.** Extend the existing pydantic model that wraps the classifier output (likely a `Literal[QuestionType, ...]` or a model with a `question_type: QuestionType` field). The Coder MUST verify the model already accepts the 3 new values; if it was hard-coded to the original 5 (e.g. inline `Literal["factual", "comparative", "definitional", "state_of_art", "causal"]`), widen it to the full enum.

**Cross-check with Fix C.** The `comparative` example wording above quotes Q6 verbatim. Q6 routes to `COMPARATIVE → WEIGHTED` per the updated §0.8 row 6. If you change one, change the other.

**Acceptance criterion (Fix A).**
- New test `backend/tests/test_classify_emits_new_types.py` OR extension of `backend/tests/test_agent_tasks_classify.py` with one parametrised row per new `QuestionType`:
  - `PREDICTIVE_FUTURE` → "What are the long-term risks of AI-generated code in enterprise systems?"
  - `PREDICTIVE_FUTURE` → "Could AI systems replace mid-level software engineers within the next 10 years?"
  - `SUBJECTIVE_OPINION` → "What is the best programming language?"
  - `PERSONAL_PRIVATE` → "Should I quit my job?"
  - `COMPARATIVE` → "Should a high-scale AI platform use event-driven architecture or synchronous microservices?" (Q6 — cross-checks Fix C)
- Each row asserts the classifier returns the expected type (mock the LLM call with the canned response matching the expected enum value to keep the test deterministic).

### Files

| File | Action |
|---|---|
| `backend/app/llm/models.py` | extend `SynthesizedAnswer` with kind-specific optional payloads + `contradictions` + `remaining_uncertainties` (G5/G10) |
| `backend/app/llm/prompts/synthesizer.py` (new) | one prompt builder per kind; per-kind token budget enforced (M3) |
| `backend/app/agent/tasks/draft.py` | derive `ambiguity_flag` (G3), enforce contradictions when needed (G10), call `select_answer_kind`, validate output |
| `backend/app/agent/tasks/classify.py` | extend to detect empty comparatives and emit `AmbiguityDetectedEvent` (G9) |
| `backend/app/agent/run_state.py` | Add helper `def has_event(self, event_type: EventType) -> bool: return any(e.type == event_type for e in self.events)`. Add fields `selected_answer_kind: AnswerKind \| None = None` and `ambiguity_dimensions: list[str] = Field(default_factory=list)`. Both fields are persisted in the run snapshot. |
| `backend/app/domain/events.py` | extend `AmbiguityDetectedEvent` with `dimensions: list[str] \| None = None` (optional, additive) |
| `backend/tests/test_agent_tasks_draft.py` | extend with one test per kind + contradictions-required test (G10) |
| `backend/tests/test_agent_tasks_classify.py` | extend with empty-comparative tests for Q3-style inputs (G9) |
| `backend/tests/fixtures/synthesizer/*.json` | one canned LLM response per kind |

### `SynthesizedAnswer` extension (drop into `app/llm/models.py`)

Add **optional** fields. Existing `prose`/`key_points`/`citations`/`gaps` stay; they are reused by `DIRECT` and `BEST_EFFORT`.

```python
class ScenarioBranch(BaseModel):
    label: str
    probability_band: Literal["low", "medium", "high"]
    summary: str
    drivers: list[str]


class WeightedCandidate(BaseModel):
    label: str
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: str


class TradeoffCriterion(BaseModel):
    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    notes: str


class SynthesizedAnswer(BaseModel):
    # ... existing fields ...
    answer_kind: AnswerKind | None = Field(default=None)
    # kind-specific payloads (exactly one populated when answer_kind != None)
    scenarios: list[ScenarioBranch] | None = None        # SCENARIO
    candidates: list[WeightedCandidate] | None = None    # WEIGHTED
    criteria: list[TradeoffCriterion] | None = None      # TRADEOFF
    redirect_alternatives: list[str] | None = None       # ETHICAL_REDIRECT
    interpretation: str | None = None                    # BEST_EFFORT (top guess)
    alternative_interpretations: list[str] | None = None # BEST_EFFORT
    # Cross-kind surfacing (G5 / G10) — visible to user, never optional when
    # the run produced contradictions.
    contradictions: list[str] | None = None
    remaining_uncertainties: list[str] | None = None
```

Add a Pydantic `model_validator(mode="after")` that asserts:
1. For each `answer_kind`, the matching kind-specific field is populated and the other kind-specific fields are `None`. Skip when `answer_kind is None` (back-compat with WP-1 callers).
2. **G10 enforcement**: when the validator receives a context flag `_requires_contradictions=True` (passed by `draft.py` when the run has any `ContradictionDetectedEvent`), `contradictions` MUST be a non-empty list. Otherwise raise `ValueError("contradictions required: run surfaced ContradictionDetectedEvent but synthesizer omitted them")`.

Use `model_validator(mode="after")` + `info.context` (Pydantic v2) to access `_requires_contradictions`.

#### Threading the validation context

The `_requires_contradictions` flag is threaded from `draft.py` into the validator via Pydantic v2's validation context. Exact call site in `draft.py`:

```python
# In draft.py, after the LLM returns raw_payload:
synthesized = SynthesizedAnswer.model_validate(
    raw_payload,
    context={"_requires_contradictions": requires_contradictions},
)
```

Inside the `model_validator(mode='after')`, read the flag via `info.context.get('_requires_contradictions', False)` (use `@model_validator(mode='after')` with the second parameter `info: ValidationInfo`).

#### Per-kind output token budgets (M3)

Enforce in `build_synthesizer_prompt` via `max_tokens` and assert at test time with `tiktoken`:

| Kind | `max_tokens` |
|---|---|
| `DIRECT` | 800 |
| `BEST_EFFORT` | 800 |
| `ETHICAL_REDIRECT` | 400 |
| `SCENARIO` | 1200 |
| `TRADEOFF` | 1200 |
| `WEIGHTED` | 1500 |

### Synthesizer prompt structure

`backend/app/llm/prompts/synthesizer.py` exports:

```python
def build_synthesizer_prompt(
    question: str,
    evidence: list[EvidenceSnippet],
    answer_kind: AnswerKind,
    user_language: str = "es",
) -> str: ...
```

Six branches, each ending with: *"Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `<X>`."*. The system prompt is shared; only the per-kind instruction block differs. Cite the binding proposal §WP-2 (templates) verbatim in module docstring.

### `draft.py` changes

1. **G3 wiring**: derive `ambiguity_flag = state.has_event(EventType.AMBIGUITY_DETECTED)` before invoking the resolver. Never default it to `False`.
2. **G10 wiring**: compute `requires_contradictions = state.has_event(EventType.CONTRADICTION_DETECTED)`.
3. Compute judge inputs (S, coverage, agreement, ambiguity_flag).
4. Call `select_answer_kind(AnswerKindInputs(...))`.
5. Persist the chosen kind on `RunState.selected_answer_kind`.
6. Build the prompt: `build_synthesizer_prompt(question, evidence, answer_kind=kind, user_language=run.language, requires_contradictions=requires_contradictions)`. The prompt MUST inject the hard sentence *"You MUST populate `contradictions` with at least one entry summarising the disagreement."* when the flag is true.
7. Call the synthesizer LLM; validate via `SynthesizedAnswer.model_validate(payload, context={"_requires_contradictions": requires_contradictions})`.
8. On `answer_kind` mismatch: retry **once** with a hardened prompt prefix; then raise `LLMContractError`.
9. On `contradictions` missing while required: retry **once** with an even harder prefix; then raise `LLMContractError`.
10. Surface `answer_kind` to the `JudgeRuledEvent` and `StoppedEvent` emitters (already optional in the schema).

### `classify.py` changes (G9 — empty comparative detector)

After the LLM classifier returns its `QuestionType` guess, run a deterministic post-check:

```python
_EMPTY_COMPARATIVE_MARKERS = ("best", "mejor", "better", "should i", "vale la pena", "worth it")

def detect_empty_comparative(question: str, classified_type: QuestionType) -> list[str] | None:
    """Return a list of plausible evaluation dimensions if the question is an
    underspecified comparative; None otherwise. Triggers ``AmbiguityDetectedEvent``.
    """
    if classified_type not in {QuestionType.COMPARATIVE, QuestionType.SUBJECTIVE_OPINION}:
        return None
    lowered = question.lower()
    if not any(m in lowered for m in _EMPTY_COMPARATIVE_MARKERS):
        return None
    # Heuristic: question has no explicit "for X" / "to Y" / "in Z" clause.
    if any(c in lowered for c in (" for ", " to ", " in ", " para ", " en ")):
        return None
    # Ask the classifier LLM for plausible dimensions (small structured call).
    return await classify_dimensions(question)  # returns >= 2 strings
```

#### `classify_dimensions` contract (G9 — binding)

- **Signature:** `async def classify_dimensions(question: str) -> list[str]`
- **LLM role:** `LLMRole.CLASSIFIER` (reuse existing role — do NOT add a new role).
- **Structured output schema:**
  ```python
  class AmbiguityDimensions(BaseModel):
      dimensions: list[str] = Field(min_length=2, max_length=6)
  ```
- **System prompt (English, ≤ 15 lines):** instruct the LLM to enumerate 2-6 plausible evaluation dimensions that would change the answer to the question. Example wording the Coder should follow:
  > *"You receive an underspecified comparative or opinion question (e.g. 'best programming language'). Output 2-6 short evaluation dimensions that, if the user picked one, would meaningfully change the answer (e.g. 'performance', 'ecosystem maturity', 'learning curve', 'job market'). One to three words each, English only, no duplicates, no dimensions that are restatements of the question. Return strict JSON matching the `AmbiguityDimensions` schema."*
- **Hard rule:** if the LLM returns 0 or 1 dimensions, retry **once** with a hardened prefix (e.g. *"Your previous answer had fewer than 2 dimensions. Enumerate AT LEAST 2 orthogonal dimensions or return an empty list."*); if the retry also fails the min-length check, return `[]`. An empty list is interpreted by the caller as "not ambiguous after all" and **no** `AmbiguityDetectedEvent` is emitted.

If the function returns a non-empty list, emit `AmbiguityDetectedEvent(dimensions=...)` before the planner runs. The planner is still called (it generates sub-claims to *explore* the dimensions), but the resolver in `draft.py` will see `ambiguity_flag=True` and route to `BEST_EFFORT`.

### Tests
- Six new tests in `test_agent_tasks_draft.py`, one per kind, mocking `LLMClient.call` to return the matching fixture. Assert `StoppedEvent.answer_kind` and that the kind-specific field is populated.
- Negative test: kind mismatch → retry → `LLMContractError`.
- **G10 test**: run state with one `ContradictionDetectedEvent`; first synthesizer call returns no `contradictions`; assert one retry, then either success (contradictions populated) or `LLMContractError`.
- **G9 tests** in `test_agent_tasks_classify.py`: inputs `"What is the best programming language?"`, `"¿Cuál es el mejor framework?"`, `"Should I use Rust?"` → all emit `AmbiguityDetectedEvent` with ≥ 2 `dimensions`. Counter-tests with criteria-bound questions (`"best language for embedded systems"`) MUST NOT trigger.
- Token-budget test (M3): for each kind, assert the rendered prompt's `max_tokens` matches the table.

### Acceptance
- All draft + classify tests green; no orchestrator changes required (HONEST_* paths still exist).
- Coverage on `prompts/synthesizer.py` ≥ 90 %.
- Matrix rows 3, 4, 5, 6, 8 of §0.8 pass at the **resolver level** (i.e. given mocked inputs they return the expected kind). Row 6 is now `COMPARATIVE → WEIGHTED` per Fix C — the parametrised assertion MUST reflect this.
- [ ] Classifier prompt enumerates all 8 `QuestionType` values; new types reachable in tests (WP-2.0 / Fix A).
- Memory: log `D-WP-2 done`.

---

## WP-2.5 — Contradiction detector audit & contract (post-audit Fix B, 2026-05-27) (≈ 1.5 h)

**Depends on:** WP-2. **Blocks:** WP-3.

### Objective
Guarantee that `ContradictionDetectedEvent` reliably fires whenever evidence pieces disagree, so that G10's mandatory `contradictions` enforcement on `SynthesizedAnswer` (WP-2) actually triggers in production for Q4 (intermittent fasting) and Q8 (AI replacing engineers). Without this WP, G10 is a dead branch: the validator demands a non-empty list only `when state.has_event(EventType.CONTRADICTION_DETECTED)`, and that predicate is never true if the analyzer never emits the event.

### Audit step (mandatory, before writing code)

The Coder MUST open `backend/app/agent/tasks/analyze.py` and the matching `backend/tests/test_agent_tasks_analyze.py`, then record findings inline in this WP section as a literal checklist:

- [ ] Identify the current trigger for `ContradictionDetectedEvent` emission (which LLM field, threshold, or heuristic).
- [ ] Confirm it operates on pairs of evidence chunks bound to the same claim / sub-question (not on the question as a whole).
- [ ] Confirm at least one polarity / disagreement signal is used — either an LLM-judged `supports` vs `contradicts` label, or a numeric disagreement above a configurable threshold.

If all three boxes are checked from the existing code, jump straight to the regression test (last bullet of the Tests block). Otherwise implement the contract below.

### Required contract (implement if the audit reveals it is missing)

1. **Stance annotation on evidence chunks.** The analyzer LLM call MUST annotate each evidence chunk with a `stance ∈ {supports, contradicts, neutral}` relative to a working hypothesis. The working hypothesis is the planner-emitted claim / sub-question the chunk was retrieved for.
2. **Trigger.** `ContradictionDetectedEvent` MUST be emitted when the same claim has ≥ 1 chunk with `stance == supports` AND ≥ 1 chunk with `stance == contradicts`, evaluated either within the current round OR across rounds `1..r` (cumulative is preferred so cross-round contradictions are caught).
3. **Event payload** (extending the existing `ContradictionDetectedEvent` shape, additive only — `extra="allow"` per architecture rule 5):
   ```python
   {
       "claim": str,                              # the planner sub-claim / sub-question
       "supporting_chunk_ids": list[str],         # evidence ids with stance=supports
       "contradicting_chunk_ids": list[str],      # evidence ids with stance=contradicts
       "round": int,                              # round at which the disagreement was first observed
   }
   ```
   Any pre-existing field on the event stays untouched; new fields are optional (`X | None = None`) to keep replay of historical events safe.
4. **No new event type.** Reuse `ContradictionDetectedEvent`. Do NOT add a new `EventType` member.

### Files

| File | Action |
|---|---|
| `backend/app/agent/tasks/analyze.py` | Audit; if contract missing, add `stance` annotation in the analyzer LLM structured output + emit `ContradictionDetectedEvent` with the new payload. |
| `backend/app/domain/events.py` | Extend `ContradictionDetectedEvent` with optional `claim`, `supporting_chunk_ids`, `contradicting_chunk_ids`, `round` (all `X \| None = None`). |
| `backend/tests/test_agent_tasks_analyze.py` | Add positive + negative tests (see below). Keep all existing tests passing. |
| `backend/tests/test_analyze_emits_contradiction_event.py` | OPTIONAL — only create if the existing test file is too crowded; otherwise extend in place per project convention. |

### Tests

- **Positive (required).** Two synthetic evidence chunks for the same claim with opposite stances (`supports` + `contradicts`) → assert exactly one `ContradictionDetectedEvent` is appended with the new payload fields populated and `round` set correctly.
- **Negative (required).** Two `supports` chunks for the same claim → assert NO `ContradictionDetectedEvent` is emitted.
- **Cross-round (required when cumulative trigger is implemented).** `supports` in round 1, `contradicts` in round 2 for the same claim → event fires in round 2.
- **Audit-only path** (if the existing analyzer already satisfies the three audit boxes): add one **regression** test that constructs the legacy disagreement input shape and asserts the event still fires — lock in current behaviour.

### Done checklist
- [ ] Audit checklist above filled in (each box explicitly ticked or annotated "missing → implemented in this WP").
- [ ] `app/agent/tasks/analyze.py` emits `ContradictionDetectedEvent` per the contract above (or already did, per audit).
- [ ] Stance annotation present in the analyzer LLM structured output schema.
- [ ] Positive + negative tests pass; cross-round test passes if cumulative trigger is used.
- [ ] `pyright --strict` + `ruff check` + `pytest -q` all green.
- [ ] Memory: log `D-WP-2.5 done`; add a lesson if the analyzer needed rewiring.

### Acceptance
- Matrix row 4 (intermittent fasting) and row 8 (AI replacing engineers) reliably surface a `ContradictionDetectedEvent` in their golden traces — which in turn forces `SynthesizedAnswer.contradictions` to be non-empty via the WP-2 validator (G10).

---

## WP-3 — Per-kind ceilings + StopReason collapse + StopRationale + early-stop + migration (≈ 5 h)

This is the **destructive** WP. Do every step in order; do not split.

### Objective
- Apply `S_effective = S_raw · ceiling[kind]`.
- Re-weight the structural formula (`C_no_conflict` 0.15 → 0.05, add `C_kind_appropriateness` 0.10).
- Collapse `StopReason` from 7 → 4 (`judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`).
- **G2** — Add `StopRationale` structured payload to `StoppedEvent` so the FE can render the canonical "why we stopped" card the challenge expects.
- **G8** — Add early-stop signal: when `coverage == 1.0 AND C_agreement ≥ EARLY_STOP_MIN_AGREEMENT AND J ≥ EARLY_STOP_MIN_JUDGE`, exit the loop on round 1. This is what makes matrix row 1 (capital of Japan) feel snappy.
- **G13** — Add `test_resolver_acceptance.py` enforcing the §0.8 matrix in CI.
- Remove `HONEST_*` emission paths from the orchestrator.
- Ship Alembic migration `002_collapse_stop_reasons` that **preserves the legacy value** in `payload.legacy_stop_reason` (M2).
- Regenerate frontend types.
- Delete UI rejection screens that handled `honest_*`; add `AnswerKindBadge` + `StopRationaleCard` (M4 microcopy).
- **G7** — Fork/resume regression tests for every new field/event added in this WP.

### Files

| File | Action |
|---|---|
| `backend/app/confidence/kind_ceiling.py` (new) | `dict[AnswerKind, float]` + `apply_ceiling(S, kind)` |
| `backend/app/confidence/structural.py` | reweight + add `C_kind_appropriateness` |
| `backend/app/confidence/calculator.py` | call `apply_ceiling` after computing `S_raw` |
| `backend/app/config.py` | add `EARLY_STOP_MIN_AGREEMENT=0.9`, `EARLY_STOP_MIN_JUDGE=0.85` (G8) with justifying comment (M5) |
| `backend/app/domain/enums.py` | delete `HONEST_*` members |
| `backend/app/domain/events.py` | new `StopRationale` sub-model (G2); make `answer_kind` **required** on `JudgeRuledEvent`/`StoppedEvent` when `stop_reason == JUDGE_CONFIRMED`; remove `honest_explanation` field; add optional `rationale: StopRationale \| None` to `StoppedEvent` |
| `backend/app/agent/orchestrator.py` | remove the 4 `HONEST_*` emission sites; add early-stop check after each judge call (G8); build & attach `StopRationale` before emitting `StoppedEvent` (G2) |
| `backend/alembic/versions/002_collapse_stop_reasons.py` (new) | preserve legacy value in `payload.legacy_stop_reason` (M2), then update enum |
| `backend/alembic/versions/001_initial_schema.py` | **do not edit**; new migration handles diff |
| `backend/tests/test_domain_enums.py` | `len(StopReason) == 4`, update expected set |
| `backend/tests/test_agent_orchestrator.py` | rewrite the 4 HONEST_* paths to assert new routing; add early-stop test (G8); add `StopRationale` populated assertion (G2) |
| `backend/tests/test_resolver_acceptance.py` (new) | one parametrised test per row of §0.8 matrix (G13). Row 6 (Q6: EDA vs microservices) MUST expect `AnswerKind.WEIGHTED` with `QuestionType.COMPARATIVE` and inputs `S=0.70, cov=1.0, agr=0.55, amb=False` per Fix C (2026-05-27). Row 3 stays `BEST_EFFORT`; rows 5 and 8 stay `SCENARIO`. |
| `backend/tests/test_migrations.py` | extend to verify migration 002 + `legacy_stop_reason` backfill (M2) |
| `backend/tests/test_routes_runs.py` | extend fork test to cover new `StopRationale` field and new events (G7) |
| `scripts/export_types.py` | run, commit the regenerated `frontend/src/types/events.ts` |
| `frontend/src/components/...` | delete components / branches switching on `honest_*`; add `AnswerKindBadge` (atom) + `StopRationaleCard` (molecule) |
| `frontend/src/lib/microcopy.ts` | Create if absent — the project has no i18n layer; this is a plain Spanish string constants module. Export `ANSWER_KIND_LABELS: Record<AnswerKind, string>` and `STOP_RATIONALE_LABELS: Record<keyof StopRationale, string>`. Reference these from `AnswerKindBadge` and `StopRationaleCard`. UI-prototype §7 is binding for the strings themselves (see M4 binding block below). |

### M4 — Microcopy strings (binding)

These are the exact runtime user-facing Spanish strings to ship in `frontend/src/lib/microcopy.ts`. Do not paraphrase; do not translate to English; do not add accents the entries don't already have.

```ts
export const ANSWER_KIND_LABELS: Record<AnswerKind, string> = {
  direct: "Respuesta directa",
  weighted: "Candidatos ponderados",
  scenario: "Escenarios",
  tradeoff: "Análisis de tradeoffs",
  ethical_redirect: "Redirección con alternativas",
  best_effort: "Mejor interpretación disponible",
};

export const STOP_RATIONALE_LABELS: Record<keyof StopRationale, string> = {
  evidence_quality: "Calidad de evidencia",
  source_agreement: "Acuerdo entre fuentes",
  new_information_gain: "Información nueva",
  final_confidence: "Confianza final",
  kind_ceiling_applied: "Techo aplicado",
  human_summary: "Resumen",
};
```

### `StopRationale` model (G2)

Drop into `app/domain/events.py` next to `StoppedEvent`:

```python
class StopRationale(BaseModel):
    """Structured 'why we stopped' payload (RF-13 / RF-19).

    Aggregates the four signals the challenge spec expects to see on a
    terminal run: evidence quality, source agreement, novelty (information
    gain), and final confidence — plus the ceiling actually applied and a
    short human-readable summary from the judge.
    """

    model_config = ConfigDict(extra="allow")

    evidence_quality: float          # = S_raw (pre-ceiling)
    source_agreement: float          # = C_agreement
    new_information_gain: float      # = 1 - last_saturation_novelty (1.0 if no saturation measured)
    final_confidence: float          # = min(S_effective, J)
    kind_ceiling_applied: float      # = KIND_CEILING[answer_kind]
    human_summary: str               # <= 280 chars, judge-authored
```

The orchestrator builds the rationale **exactly once** in `_emit_stopped(...)` right before publishing `StoppedEvent`. For non-`judge_confirmed` terminals (`stopped_by_budget`, `user_cancelled`, `errored`) the rationale is optional: emit when scores are available, omit otherwise.

### Early-stop logic (G8)

In `orchestrator._after_judge`:

```python
if (
    judge_verdict.passed
    and state.last_coverage >= 1.0
    and state.last_agreement >= settings.EARLY_STOP_MIN_AGREEMENT
    and judge_verdict.confidence >= settings.EARLY_STOP_MIN_JUDGE
):
    return self._transition_to_stop(StopReason.JUDGE_CONFIRMED)
```

This check runs after **every** judge call, so it fires on round 1 for trivial facts (matrix row 1) but also short-circuits deeper runs that happen to converge early.

### Ceiling table (from confidence-calculation.md amendment)

```python
KIND_CEILING: dict[AnswerKind, float] = {
    AnswerKind.DIRECT:           1.00,
    AnswerKind.WEIGHTED:         0.85,
    AnswerKind.SCENARIO:         0.60,
    AnswerKind.TRADEOFF:         0.70,
    AnswerKind.BEST_EFFORT:      0.55,
    AnswerKind.ETHICAL_REDIRECT: 0.50,
}
```

### Structural reweight

`S_raw = 0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.05·C_no_conflict + 0.10·C_kind_appropriateness`.

`C_kind_appropriateness` is set by the judge (B) in `JudgeVerdict`. Add a `kind_appropriateness: float = 1.0` field on `JudgeVerdict` (default 1.0 = "kind fits the question").

### Alembic migration template (M2 — preserves legacy value)

```python
"""Collapse stop reasons to 4 values and require answer_kind on positive terminals."""

revision = "002"
down_revision = "001"

def upgrade() -> None:
    # 1. Preserve the original honest_* value under payload.legacy_stop_reason
    #    BEFORE collapsing it. Defensible audit trail (M2).
    op.execute("""
        UPDATE events
        SET payload = jsonb_set(
            payload,
            '{legacy_stop_reason}',
            to_jsonb(payload->>'stop_reason')
        )
        WHERE payload->>'stop_reason' IN
              ('honest_unanswerable','honest_contradiction','honest_ambiguous')
    """)
    # 2. Backfill the new value
    op.execute("""
        UPDATE events
        SET payload = jsonb_set(
            payload,
            '{stop_reason}',
            '"judge_confirmed"'
        )
        WHERE payload->>'stop_reason' IN
              ('honest_unanswerable','honest_contradiction','honest_ambiguous')
    """)
    # 3. Replace enum on the runs table
    op.execute("ALTER TYPE stop_reason RENAME TO stop_reason_old")
    op.execute(
        "CREATE TYPE stop_reason AS ENUM "
        "('judge_confirmed','stopped_by_budget','user_cancelled','errored')"
    )
    op.execute(
        "ALTER TABLE runs ALTER COLUMN stop_reason TYPE stop_reason "
        "USING (CASE WHEN runs.stop_reason::text IN "
        "('honest_unanswerable','honest_contradiction','honest_ambiguous') "
        "THEN 'judge_confirmed' ELSE runs.stop_reason::text END)::stop_reason"
    )
    op.execute("DROP TYPE stop_reason_old")

def downgrade() -> None:
    raise NotImplementedError("Forward-only migration (WP-3).")
```

Confirm with `alembic upgrade head` against `pytest-postgresql` ephemeral DB.

### Acceptance
- `pytest -q` green including new migration test and `test_resolver_acceptance.py` (all 8 §0.8 rows pass at resolver level).
- `grep -r "honest_" backend/app` → no matches (only docstrings / migrations may mention legacy values).
- Early-stop test asserts matrix row 1 finishes in exactly **1 round** with `AnswerKind.DIRECT` and `StopRationale.new_information_gain == 1.0`.
- `StopRationale` populated on every `StoppedEvent` with `stop_reason == JUDGE_CONFIRMED` in the orchestrator tests.
- Fork test: a run forked from a `StoppedEvent` carrying `StopRationale` replicates the rationale on the child run snapshot (G7).
- Migration test asserts `events.payload.legacy_stop_reason` is present for backfilled rows (M2).
- `scripts/export_types.py` produces the regenerated `frontend/src/types/events.ts`; FE `vitest run` is green; new microcopy strings (M4) exist for all 6 `AnswerKind` values.
- Memory: log `D-WP-3 done`, append lesson if migration backfill surprised anyone.

---

## WP-4 — Saturation signal (novelty-based) + in-memory embeddings + budget audit (≈ 4 h)

### Objective
Implement the **novelty-based** saturation metric C exactly as the binding proposal §WP-4 defines it (G1 correction):

> `novelty = 1 - mean(max_cosine_similarity(chunk_i, prior_corpus))` over the last k=3 retrieved chunks. When `novelty < NOVELTY_FLOOR` (default 0.15) the signal fires.

The `SaturationDetectedEvent` **feeds the judge as additional context**. It does NOT mutate `ambiguity_flag` and does NOT directly force `BEST_EFFORT`. The stop continues to be owned by the budget cap / judge cycle. The saturation value also feeds `StopRationale.new_information_gain` (G2).

Also — pre-flight (G11) — audit the run budget so deep questions (matrix rows 7 and 8) have headroom.

### Files

| File | Action |
|---|---|
| `backend/pyproject.toml` | add `numpy` as direct dep. **No `sentence-transformers`** (M1) — embeddings via `litellm` hosted endpoint. |
| `backend/app/llm/embeddings.py` (new) | `async embed(texts: list[str], *, model: str = settings.EMBEDDING_MODEL) -> list[np.ndarray]` via `litellm.aembedding` |
| `backend/app/agent/run_state.py` | add `chunk_embeddings: dict[str, np.ndarray]` (`Field(exclude=True)` for JSON), `last_novelty: float \| None` |
| `backend/app/stopping/saturation.py` (new) | `StoppingSignal` implementation; computes novelty per G1; emits `SaturationDetectedEvent` when novelty < `NOVELTY_FLOOR` for the last k=3 chunks |
| `backend/app/domain/enums.py` | add `EventType.SATURATION_DETECTED = "SaturationDetected"` |
| `backend/app/domain/events.py` | new `SaturationDetectedEvent { round_index: int, novelty: float, k: int = 3, threshold: float }` |
| `backend/app/agent/tasks/draft.py` | when assembling the judge's input, include `evidence_saturation = state.last_novelty` (judge prompt extension) |
| `backend/app/agent/orchestrator.py` | call saturation signal after each evidence round; emit event when triggered; populate `state.last_novelty` regardless |
| `backend/app/config.py` | add `EMBEDDING_MODEL: str = "openai/text-embedding-3-small"`, `OPENAI_API_KEY: SecretStr \| None = None` (required when embeddings enabled — see §0.9), `NOVELTY_FLOOR: float = 0.15`, `SATURATION_WINDOW: int = 3`; audit & raise `MAX_ROUNDS ≥ 10`, `MAX_SEARCHES_PER_ROUND ≥ 3`, `MAX_TOKENS_PER_RUN ≥ 120_000` (G11) with justifying comments (M5). Also add `OPENAI_API_KEY` row to `docs/technical-phase/ai-services.md`. |
| `backend/tests/test_stopping_saturation.py` (new) | unit tests with stubbed `embed`; golden trace verifying novelty crosses the floor |
| `backend/tests/test_routes_runs.py` | extend fork test: replicate `SaturationDetectedEvent` and `state.last_novelty` on the forked run (G7) |
| `scripts/export_types.py` | rerun |

### Hard constraints
- Embedding cache is **process-local**. No persistence. Resume must re-embed; cap re-embeds at **50 chunks per resume** (drop oldest first).
- `NOVELTY_FLOOR = 0.15` and `SATURATION_WINDOW = 3` justified inline in `config.py` (M5): *"empirical: floor < 0.1 → system never saturates on broad questions; floor > 0.25 → false positives on rich corpora."*
- `SaturationDetectedEvent` is **observational, never terminal**. It informs the judge (`evidence_saturation` field on the judge's input payload) and feeds `StopRationale.new_information_gain`.
- Budget audit (G11): verify current `app/config.py` defaults and bump them if smaller. Document the rationale per setting: *"matrix row 7 (memory of agents) needs ≈ 8 rounds to saturate."*
- **Granularity (G1 — binding):**
  - `chunk` = one `EvidenceAddedEvent` payload (the text body of one evidence row).
  - `prior_corpus` for round `r` = the concatenation of all `EvidenceAddedEvent` chunks from rounds `1..r-1` (excludes the current round's chunks).
  - `last_k_chunks` = the most recent `SATURATION_WINDOW` chunks from round `r` only.
  - If `prior_corpus` is empty (first round), the saturation signal does NOT fire (novelty is undefined → set `state.last_novelty = None`).

### Acceptance
- `pytest backend/tests/test_stopping_saturation.py -q` green.
- Golden trace for a deep question (matrix row 7) shows novelty decreasing across rounds and the event firing at round ≥ 5.
- Judge prompt fixtures (in `tests/fixtures/judge/`) include `evidence_saturation` when present and ignore it when `None`.
- Fork regression (G7): forking from a round with `SaturationDetectedEvent` carries the novelty value forward.
- Memory: log `D-WP-4 done`.

---

## WP-5 — Independent verifier via Anthropic Claude Haiku + judge capability extension (≈ 3 h)

### Objective
Make the **judge** role both **provider-independent** (Anthropic by default, GitHub Models as fallback) **and a real verifier** (G4 — coherence + contradictions + missing evidence), not just a confidence-emitter. The judge now answers the four questions `advanced-ai-research.md` lists for verifier models.

### Files

| File | Action |
|---|---|
| `backend/app/config.py` | add `JUDGE_PROVIDER: Literal["anthropic","github"] = "anthropic"`, `JUDGE_MODEL: str = "claude-haiku-4-5"`, `ANTHROPIC_API_KEY: SecretStr \| None = None`. litellm model string: `anthropic/claude-haiku-4-5`. Fallback model string when degrading to GitHub Models: `github/deepseek/DeepSeek-V3-0324` (current judge model). |
| `backend/app/llm/models.py` | extend `JudgeVerdict` per G4: `coherence: float`, `contradictions_detected: list[str]`, `missing_evidence: list[str]`, `kind_appropriateness: float = 1.0` |
| `backend/app/llm/client.py` | route the `judge` role to the configured provider; on auth/5xx failure fall back to GitHub Models, emit `JudgeProviderDegradedEvent` |
| `backend/app/llm/prompts/judge.py` | rewrite system prompt to require the new structured fields (coherence, contradictions_detected, missing_evidence) |
| `backend/app/domain/enums.py` | add `EventType.JUDGE_PROVIDER_DEGRADED = "JudgeProviderDegraded"` |
| `backend/app/domain/events.py` | new `JudgeProviderDegradedEvent { requested_provider, fallback_provider, error_class }`; extend `JudgeRuledEvent` with optional `coherence`, `contradictions_detected`, `missing_evidence` (additive) |
| `backend/app/agent/tasks/draft.py` | propagate `contradictions_detected` from judge into `SynthesizedAnswer.contradictions` if the synthesizer omitted them; merge with planner-detected contradictions |
| `backend/tests/test_llm_client.py` | extend with fallback path (mock 401 from Anthropic → asserts GitHub Models call + event) |
| `backend/tests/test_llm_models_unwrap.py` | extend `JudgeVerdict` validation tests for new fields |
| `backend/tests/test_routes_runs.py` | fork regression (G7): forking carries new judge fields and `JudgeProviderDegradedEvent` |
| `docs/technical-phase/ai-services.md` | already updated; verify env table |
| `scripts/export_types.py` | rerun |

### Hard constraints
- Anthropic via `litellm` (no `anthropic` SDK direct import).
- Retries on Anthropic timeout (3, tenacity exponential) **before** falling back.
- Fallback is a one-shot per call — if both fail, the run errors out (`errored`), not silently degrades.
- `JudgeVerdict.contradictions_detected` and `JudgeVerdict.missing_evidence` are **required** in the structured output (Instructor mode). If the judge LLM omits them, retry once; then `LLMContractError`.

### Acceptance
- `pytest backend/tests/test_llm_client.py backend/tests/test_llm_models_unwrap.py -q` green including fallback + new-field tests.
- For matrix row 4 (intermittent fasting), the judge's `contradictions_detected` is non-empty in the golden trace.
- Fork regression (G7): forked run preserves the judge's verifier fields.
- Manual smoke test against `https://novum.duckdns.org` confirms `JudgeRuledEvent.judge_model` reflects Anthropic on happy path; trigger a forced fallback in a staging run to validate the event emission.
- Memory: log `D-WP-5 done`.

---

## WP-6 — Cross-run question memory (in-memory only) (≈ 2 h)

### Objective
Help the **planner** spot when a similar question was already answered. Hard contract: the index is **only** read by `app/agent/tasks/plan.py`; synthesizer and judge never see it.

### Files

| File | Action |
|---|---|
| `backend/app/agent/question_index.py` (new) | process-level singleton `class QuestionEmbeddingIndex { add(run_id, vec), top_k(vec, k=3) }`. Implementation: `collections.OrderedDict` keyed by `run_id`, value `(question_text, np.ndarray, sub_claims)`. On `add`, if `len >= PRIOR_RUN_INDEX_CAP`, `popitem(last=False)` evicts the oldest. On `top_k` retrieval, call `move_to_end(run_id)` for each accessed entry to maintain LRU order. No external deps. |
| `backend/app/agent/tasks/plan.py` | on planner call, embed question, query index, inject top-3 "prior similar runs" as **planning hints only** |
| `backend/app/llm/prompts/planner.py` | extend prompt: "If prior runs are relevant, you MAY borrow sub-claims; you MUST NOT borrow conclusions." |
| `backend/app/main.py` | wire index singleton into FastAPI lifespan; reset on shutdown |
| (optional) `backend/alembic/versions/003_runs_question_embedding.py` | add `runs.question_embedding BYTEA` for warm-start across restarts. **Skip if it pushes WP over budget.** |
| `backend/tests/test_question_index.py` (new) | unit tests for add/top_k + LRU eviction (cap = 256 entries) |
| `backend/tests/test_agent_tasks_plan.py` | extend: when index returns hits, planner prompt contains hint block |

### `PriorRunHint` typed contract (G6 — enforced by pyright, not by grep)

```python
class PriorRunHint(BaseModel):
    """What the planner is allowed to see from past runs.

    DELIBERATELY ABSENT: answer_kind, prose, key_points, citations,
    confidence, judge_verdict. Adding any of them is a contract violation.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    question_text: str
    sub_claims: list[str]
```

- `QuestionEmbeddingIndex.top_k(...) -> list[PriorRunHint]`. The return type is the only typed surface.
- `build_planner_prompt` accepts `prior_runs: list[PriorRunHint]`.
- `build_synthesizer_prompt` and `build_judge_prompt` accept **no** parameter of type `PriorRunHint` (and pyright `--strict` would flag any attempt to pass one).
- Replace the previously planned grep test with: `tests/test_question_index_isolation.py` that **imports** the synthesizer prompt module, inspects its signature via `inspect.signature`, and asserts no parameter annotation contains `PriorRunHint`. This is a real static check, not a string search.

### Hard constraints
- Cap 256 entries, LRU. Cap is in `app/config.py` (`PRIOR_RUN_INDEX_CAP: int = 256`).
- Index reset on process restart (acceptable — single-server scope, RF-05).
- Synthesizer / judge functions **must not** accept `PriorRunHint` in their signatures (G6, enforced via `test_question_index_isolation.py`).

### Acceptance
- `pytest backend/tests/test_question_index.py backend/tests/test_agent_tasks_plan.py backend/tests/test_question_index_isolation.py -q` green.
- `pyright --strict` clean on the planner / synthesizer / judge prompt modules.
- Memory: log `D-WP-6 done`. Append lesson on the "planner-only" typed contract.

---

## Cross-cutting checklist (run at end of each WP)

```powershell
# Backend gate
cd backend
uv run ruff check .
uv run pyright --strict
uv run pytest -q

# Type contract sync (after any event-shape change)
uv run python ../scripts/export_types.py

# Frontend gate
cd ../frontend
npm run lint
npm run typecheck
npm run test -- --run --reporter=basic
```

All five commands must exit 0 before opening the next WP.

---

## Frontend impact summary (executed mostly in WP-3)

| WP | Surface |
|---|---|
| WP-3 | Delete `HonestStopBanner` / `HonestStopScreen` (whatever name the components use today — find with `grep -ri "honest_" frontend/src`). Replace with `AnswerKindBadge` showing the chosen kind + ceiling indicator. |
| WP-3 | Regenerated `events.ts` will drop `honest_*` literal types — TypeScript will flag every dead branch. Walk each error, do not silence with `as`. |
| WP-4 | Add a small "saturated" tag in the trace panel when `SaturationDetectedEvent` exists. No new page. |
| WP-5 | Trace panel surfaces `JudgeProviderDegradedEvent` as a yellow row (RF-13 / RF-19 — never hide trust info). |
| WP-6 | No FE change. |

The **UI prototype** (`docs/understanding-phase/ui-prototype.md`) is binding: use existing design tokens, do not hardcode hex. New components live under the atomic level matching their role (`AnswerKindBadge` → atom; `SaturatedTag` → atom; `JudgeDegradedRow` → molecule).

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Migration 002 corrupts a long-running production trace by collapsing legacy `honest_*` rows | Medium | Forward-only migration uses `UPDATE` with explicit `WHERE`; backfill row count logged. Old rows become `judge_confirmed` with NO `answer_kind` (legacy reads display "(legacy)"). Confirmed acceptable in proposal §8. |
| Anthropic Haiku rate-limit during demo | Medium | Tenacity + auto-fallback to GitHub Models in WP-5. Event surfaces the degradation, demo continues. |
| In-memory embeddings exhaust RAM on long runs | Low | 50-chunk cap + per-run dict dropped at end. Process restart wipes the cross-run index. |
| Six synthesizer templates explode prompt token budget | Medium | Single shared system prompt + small kind-specific block. Token budget guard already exists in `llm/client.py`. |
| Frontend type drift after WP-3 | High | `scripts/export_types.py` is the single source. CI must fail if regenerated file differs from committed. Add this check to a pre-commit hook in WP-3. |

---

## Changelog 2026-05-27 (post-audit fixes A/B/C)

Three specification holes closed in place; no source code touched. All edits land in this same IP-21 file.

- **Fix A (HIGH) — Classifier prompt enumerates all 8 `QuestionType` values.** Added sub-task **WP-2.0** at the top of WP-2 (before "### Files"). The Coder must extend whichever file holds the classifier system prompt (canonical: `backend/app/llm/prompts/classifier.py`; fallback: inline string in `backend/app/agent/tasks/classify.py`) with the 8 typed bullets (one per `QuestionType`), each carrying an anchor example. New parametrised test (`test_classify_emits_new_types.py` or extension of `test_agent_tasks_classify.py`) covers the three previously-unreachable types plus a Q6 cross-check row. Added a Done-checklist line to WP-2.
- **Fix B (MEDIUM) — Contradiction detector audit & contract.** New work-package **WP-2.5** inserted between WP-2 and WP-3, added to the phase order in §0.5, and made a hard dependency of WP-3. The Coder first audits `analyze.py` against three explicit checks (trigger source, claim-bound pairing, polarity signal); if any are missing, implements a `stance ∈ {supports, contradicts, neutral}` annotation on each evidence chunk and emits `ContradictionDetectedEvent` whenever the same claim has both `supports` and `contradicts` chunks within or across rounds. Payload extended (additively, optional fields only) with `claim`, `supporting_chunk_ids`, `contradicting_chunk_ids`, `round`. Positive + negative tests are mandatory.
- **Fix C (MEDIUM) — Row 6 of §0.8 reverted to `COMPARATIVE → WEIGHTED`.** Row 6 (Q6: EDA vs synchronous microservices) was `SUBJECTIVE_OPINION → TRADEOFF`; reverted to `COMPARATIVE (architecture tradeoff) → WEIGHTED` with resolver inputs `S=0.70, cov=1.0, agr=0.55, amb=False` (routes via `cov_complete AND agr<0.6 → WEIGHTED` per WP-0 resolver). The Resolver-input footnote was updated: rows previously listed as priority-routed ("5, 6, 8") become "5 and 8" — row 6 now routes through the numeric branch, and the 0.55 agreement is justified inline. WP-3's `test_resolver_acceptance.py` row description spells out the new expectation; the `WEIGHTED` template in Annex A picks up a Q6 binding note plus a required `weighted_q6.json` fixture.

Status header bumped to: *"gaps closed 2026-05-27 — 3 post-audit holes closed (Fixes A/B/C)"*. No content outside these three fixes was rephrased or removed.

---

## Annex A — Synthesizer prompt bodies (binding)

These are the system-prompt templates the Coder MUST implement in `backend/app/llm/prompts/synthesizer.py`. **English only** (these are SYSTEM prompts; the runtime reply switches language via the trailing instruction). The shared system block is concatenated with exactly one per-kind block; together they form the system message. The user message carries `{question}` + `{evidence_block}`.

Placeholders the builder substitutes at call time: `{question}`, `{evidence_block}`, `{user_language}`, `{contradictions_required}` (boolean → renders the contradiction directive only when `True`).

### Shared system block (prepended to every kind)

```
You are Novum's synthesizer. You receive a research question and a curated
evidence block. Produce a structured answer that strictly validates against
the SynthesizedAnswer schema for the requested AnswerKind.

Rules:
- Cite only facts supported by the evidence block. Do not introduce outside knowledge.
- Mark uncertainty explicitly via `remaining_uncertainties` when the evidence is thin.
- Never fabricate citations. Every claim that uses a source MUST reference an
  evidence id present in the input.
- Be concise. Prose ≤ 6 short paragraphs. Bullet lists ≤ 8 items.
{contradictions_required:: When the run flagged contradictions among sources, you MUST
populate `contradictions` with at least one entry summarising the disagreement.
Omitting it is a contract violation and the output will be rejected.}
```

### Per-kind block — `DIRECT`

```
AnswerKind = DIRECT.
Payload shape: populate `prose` (the answer in 1-3 sentences), `key_points`
(≤ 5 bullets), and `citations`. Leave kind-specific fields (scenarios,
candidates, criteria, redirect_alternatives, interpretation) as null.

Example:
  question: "{question}"
  evidence: "{evidence_block}"
  expected: {{
    "answer_kind": "direct",
    "prose": "<1-3 sentence factual answer>",
    "key_points": ["<bullet 1>", "<bullet 2>"],
    "citations": [{{ "evidence_id": "ev_1" }}]
  }}

Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `direct`.
```

### Per-kind block — `WEIGHTED`

```
AnswerKind = WEIGHTED.
Payload shape: populate `candidates` (2-6 `WeightedCandidate` entries each with
label, score in [0,1], rationale). Provide `prose` as a one-paragraph overview.
Leave scenarios, criteria, redirect_alternatives, interpretation null.

Example:
  question: "{question}"
  evidence: "{evidence_block}"
  expected: {{
    "answer_kind": "weighted",
    "prose": "<one-paragraph overview>",
    "candidates": [
      {{ "label": "<option A>", "score": 0.62, "rationale": "<why>" }},
      {{ "label": "<option B>", "score": 0.38, "rationale": "<why>" }}
    ],
    "citations": [{{ "evidence_id": "ev_1" }}]
  }}

Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `weighted`.
```

> **Q6 binding (Fix C, 2026-05-27).** The `WEIGHTED` template is the template Q6 ("Should a high-scale AI platform use event-driven architecture or synchronous microservices?") routes to, since Fix C reverted row 6 of §0.8 from `SUBJECTIVE_OPINION → TRADEOFF` back to `COMPARATIVE → WEIGHTED`. The Coder MUST keep at least one synthesizer fixture (`backend/tests/fixtures/synthesizer/weighted_q6.json`) anchored to this question so the WP-2 per-kind tests cover the post-audit routing.

### Per-kind block — `SCENARIO`

```
AnswerKind = SCENARIO.
Payload shape: populate `scenarios` (2-4 `ScenarioBranch` entries each with
label, probability_band ∈ {{low, medium, high}}, summary, drivers list).
Provide `prose` framing the question's predictive nature. Leave candidates,
criteria, redirect_alternatives, interpretation null.

Example:
  question: "{question}"
  evidence: "{evidence_block}"
  expected: {{
    "answer_kind": "scenario",
    "prose": "<framing paragraph>",
    "scenarios": [
      {{ "label": "Optimistic", "probability_band": "medium",
         "summary": "<short>", "drivers": ["<d1>", "<d2>"] }},
      {{ "label": "Pessimistic", "probability_band": "medium",
         "summary": "<short>", "drivers": ["<d1>"] }}
    ]
  }}

Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `scenario`.
```

### Per-kind block — `TRADEOFF`

```
AnswerKind = TRADEOFF.
Payload shape: populate `criteria` (3-6 `TradeoffCriterion` entries with
name, weight in [0,1] summing roughly to 1.0, notes). Provide `prose`
explaining the tradeoff frame. Leave scenarios, candidates,
redirect_alternatives, interpretation null.

Example:
  question: "{question}"
  evidence: "{evidence_block}"
  expected: {{
    "answer_kind": "tradeoff",
    "prose": "<framing paragraph>",
    "criteria": [
      {{ "name": "Latency", "weight": 0.4, "notes": "<short>" }},
      {{ "name": "Operational cost", "weight": 0.3, "notes": "<short>" }},
      {{ "name": "Team familiarity", "weight": 0.3, "notes": "<short>" }}
    ]
  }}

Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `tradeoff`.
```

### Per-kind block — `ETHICAL_REDIRECT`

```
AnswerKind = ETHICAL_REDIRECT.
Use when the question targets private/personal information you cannot
ethically answer. Payload shape: populate `prose` (one short paragraph
explaining why a direct answer is withheld) and `redirect_alternatives`
(2-4 actionable, ethical alternatives). Leave scenarios, candidates,
criteria, interpretation null.

Example:
  question: "{question}"
  evidence: "{evidence_block}"
  expected: {{
    "answer_kind": "ethical_redirect",
    "prose": "<one-paragraph explanation, no judgement>",
    "redirect_alternatives": [
      "<alternative 1>",
      "<alternative 2>"
    ]
  }}

Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `ethical_redirect`.
```

### Per-kind block — `BEST_EFFORT`

```
AnswerKind = BEST_EFFORT.
The evidence is incomplete or the question is ambiguous. Payload shape:
populate `interpretation` (the most defensible reading of the question),
`alternative_interpretations` (1-3 plausible alternatives), `prose`
(the answer under the chosen interpretation), and `remaining_uncertainties`.
Leave scenarios, candidates, criteria, redirect_alternatives null.

Example:
  question: "{question}"
  evidence: "{evidence_block}"
  expected: {{
    "answer_kind": "best_effort",
    "interpretation": "<top interpretation>",
    "alternative_interpretations": ["<alt 1>", "<alt 2>"],
    "prose": "<answer under the top interpretation>",
    "remaining_uncertainties": ["<gap 1>", "<gap 2>"]
  }}

Reply in {user_language}. Output MUST validate against the SynthesizedAnswer schema for kind `best_effort`.
```

---

## Annex B — Judge prompt body (binding)

The Coder MUST implement this in `backend/app/llm/prompts/judge.py`. English-only system prompt, ≤ 60 lines.

```
You are Novum's independent verifier. You receive:
  - the user's question
  - the candidate `SynthesizedAnswer` payload
  - the evidence block the synthesizer used
  - optionally, `evidence_saturation`: a float in [0, 1] measuring how much
    novelty the most recent search rounds contributed (lower = more saturated)

You DO NOT have access to prior runs, planner hints, or cross-run memory.
Treat this verdict as a one-shot, isolated evaluation. Any attempt to
condition on past runs is a contract violation.

Return a JudgeVerdict with these fields, ALL required:
  - confidence: float in [0, 1] — your belief the answer is correct given
    only the evidence shown.
  - kind_appropriateness: float in [0, 1] — does the chosen AnswerKind fit
    the question? (1.0 = perfect fit, 0.0 = wrong template entirely.)
  - coherence: float in [0, 1] — internal logical consistency of the answer
    payload (claims do not contradict each other; structure matches the kind).
  - contradictions_detected: list[str] — short summaries of disagreements
    among the sources cited. Empty list if the evidence is unanimous.
  - missing_evidence: list[str] — concrete gaps the answer would need filled
    to raise confidence. Empty list if evidence is sufficient.
  - rationale: str — ≤ 280 characters, plain language, written in the user's
    language. This becomes `StopRationale.human_summary`.

Calibration rules:
  - If `evidence_saturation` is provided and < 0.15, additional searches are
    unlikely to help; lower `missing_evidence` weight in your verdict and
    raise `confidence` if coherence is high.
  - If `evidence_saturation` is provided and > 0.6, the run is still
    learning; be cautious with high confidence even if coherence is high.
  - For AnswerKind in {scenario, tradeoff, best_effort, ethical_redirect},
    cap `confidence` at the kind's documented ceiling (the orchestrator
    will also apply the ceiling — your job is to flag, not bypass).
  - Penalise `coherence` when claims contradict each other, when citations
    point to evidence that does not support the claim, or when the payload
    shape does not match the declared `answer_kind`.

Forbidden behaviours:
  - Do not invent evidence. If the answer cites a source not present in the
    evidence block, surface it in `missing_evidence`.
  - Do not soften your verdict for politeness. Honest low scores are valuable.
  - Do not return free-text `stop_reason` guesses; that is the orchestrator's
    decision.

Output strict JSON matching the JudgeVerdict schema. Reply rationale in the
user's language; all enum fields and keys remain English as defined by the schema.
```

---

## Annex C — Migration 002 test scaffold (binding)

This is the canonical pytest function the Coder MUST add to `backend/tests/test_migrations.py` (or extend if a similar test already exists). It validates the `legacy_stop_reason` backfill required by M2.

```python
import json
import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config


@pytest.mark.asyncio
async def test_migration_002_backfills_legacy_stop_reason(
    pg_url: str,            # provided by pytest-postgresql fixture
    alembic_cfg: Config,    # project fixture wrapping alembic.ini
    raw_engine,             # synchronous SQLAlchemy engine on pg_url
) -> None:
    # 1. Land on the previous schema.
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "001")

    # 2. Seed legacy rows via raw SQL.
    with raw_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO runs (id, user_id, question, stop_reason, created_at) "
            "VALUES (gen_random_uuid(), gen_random_uuid(), 'q', "
            "'honest_unanswerable', now())"
        ))
        conn.execute(text(
            "INSERT INTO events (id, run_id, type, payload, created_at) "
            "VALUES (gen_random_uuid(), "
            "(SELECT id FROM runs LIMIT 1), 'Stopped', "
            ":payload::jsonb, now())"
        ), {"payload": json.dumps(
            {"type": "Stopped", "stop_reason": "honest_contradiction"}
        )})

    # 3. Apply migration 002.
    command.upgrade(alembic_cfg, "head")

    # 4. Assert collapse + backfill.
    with raw_engine.connect() as conn:
        run_row = conn.execute(text(
            "SELECT stop_reason::text FROM runs LIMIT 1"
        )).one()
        ev_row = conn.execute(text(
            "SELECT payload->>'stop_reason' AS sr, "
            "payload->>'legacy_stop_reason' AS legacy FROM events LIMIT 1"
        )).one()

    assert run_row.stop_reason == "judge_confirmed"
    assert ev_row.sr == "judge_confirmed"
    assert ev_row.legacy == "honest_contradiction"
```

Fixture names (`pg_url`, `alembic_cfg`, `raw_engine`) follow the project's existing `conftest.py` conventions; the Coder reuses whatever the repo already exposes. The SQL strings are literal and binding.

---

## Done = all of the following

- [ ] WP-0 reconciliation merged; repo green.
- [ ] WP-1 resolver + test matrix merged.
- [ ] WP-2 six synthesizer templates produce one validating payload per kind; G9 ambiguity detector triggers on "best X" inputs; G10 contradictions enforcement active.
- [ ] WP-3 `StopReason` is 4 values everywhere (backend enum, DB enum, FE generated types, FE components). `pytest -q` green. `grep -r "honest_" backend/app` returns 0. `StopRationale` emitted on every `judge_confirmed` terminal. Early-stop test for matrix row 1 finishes in 1 round. `test_resolver_acceptance.py` (G13) covers all 8 §0.8 rows.
- [ ] WP-4 novelty-based saturation signal (G1) fires in golden trace fixture for a deep question (matrix row 7); `evidence_saturation` is consumed by the judge; budget audit applied.
- [ ] WP-5 Anthropic Haiku is the default judge; fallback path tested; `JudgeVerdict` returns `coherence`, `contradictions_detected`, `missing_evidence` (G4).
- [ ] WP-6 planner receives top-3 prior runs via typed `PriorRunHint`; synthesizer/judge isolation enforced by static signature inspection, not grep (G6).
- [ ] All four amended docs (`requirement-understanding.md`, `confidence-calculation.md`, `stopping-signal-analysis.md`, `ai-services.md`) match the code (no orphan amendments). The Question→AnswerKind matrix (§0.8) is also reflected in `docs/q-for-testing.md` if any question's expected kind changes.
- [ ] Memory bank logs updated per WP.
- [ ] **Smoke gate (G12)**: deploy to `novum.duckdns.org`; run all 8 questions from `docs/q-for-testing.md`; each terminates with the expected `AnswerKind` per §0.8; record the 8 run IDs in the final memory log entry. Any deviation requires a memory `lessons-learned.md` entry explaining why the matrix doesn't reflect production reality.
