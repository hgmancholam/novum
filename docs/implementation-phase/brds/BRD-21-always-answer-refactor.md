# BRD-21: "Always Answer" Refactor — AnswerKind Templates, StopReason Collapse, Independent Verifier

**Document ID:** BRD-21
**Version:** 1.0
**Status:** Draft (F1 — retroactively authored to match IP-21)
**Author:** BSA Agent
**Date:** 2026-05-27
**Implementation Order:** 21 of N
**Source proposal:** [research-method-refactor-proposal.md](../../understanding-phase/research-method-refactor-proposal.md) — ratified 2026-05-27.

---

## 1. Executive Summary

Today Novum can fail in three "honest" ways encoded as terminal states: `honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`. Each produces a stop event with no useful answer text for the user, even when the agent has accumulated relevant evidence. The 7-value `StopReason` enum mixes **success contract** ("the run terminated for reason X") with **answer shape** ("I could not answer because Y") — two orthogonal concerns merged into one surface. The result: queries like *"What is the best programming language?"* or *"What are the long-term risks of AI-generated code?"* exit with an empty answer surface even though the agent gathered evidence the user would have valued.

BRD-21 makes the agent **always emit a useful answer**, with a confidence and a ceiling that honestly reflect what the evidence supports. The work splits the two concerns:

1. **`StopReason` collapses from 7 → 4 values** (`judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`). The three `honest_*` values are removed.
2. **A new `AnswerKind` enum** (6 values: `DIRECT`, `WEIGHTED`, `SCENARIO`, `TRADEOFF`, `BEST_EFFORT`, `ETHICAL_REDIRECT`) declares the **shape** of the answer that was produced. It is chosen by a deterministic resolver from `(QuestionType, S_raw, coverage, agreement, ambiguity_flag)`.
3. **Six synthesizer templates** — one per `AnswerKind` — replace the previous single-template synthesizer.
4. **Per-kind confidence ceilings** bound the final score: `final_confidence = min(S_effective, J)` where `S_effective = S_raw · kind_ceiling[AnswerKind]`. A "best-effort" answer can never claim the same confidence as a "direct" answer with the same raw evidence — the ceiling is a structural honesty guarantee.
5. **`QuestionType` extends from 6 → 8 values** to add `PERSONAL_PRIVATE` and `SUBJECTIVE_OPINION` (each maps deterministically to a specific `AnswerKind`).
6. **A new `SaturationDetected` signal** halts research when novelty per round drops below a threshold, computed from in-memory embeddings (no vector DB).
7. **An independent verifier (Anthropic Claude Haiku via `litellm`)** runs the judge step in a different provider family than the synthesizer (GitHub Models), removing same-family bias on `J`. A new `JudgeProviderDegraded` event fires when the verifier is unavailable and the judge falls back to GitHub Models — the trace records the degradation.
8. **Cross-run question memory** (in-memory only) detects when a new question is a near-duplicate of a recent run by the same user, so the trace can surface it ("You asked something similar X minutes ago").

The change is **structurally additive** on the event side (every new field is optional; every new event is a new discriminated-union member), but **breaks the `StopReason` enum** (an Alembic migration rewrites three legacy values into `stopped_by_budget` + a new `stop_rationale` text field that preserves the original reason for traceability).

Expected outcomes:

- Zero runs end with an empty answer surface.
- `final_confidence` for `BEST_EFFORT` answers is capped below the threshold normally required to trigger `judge_confirmed`, so the UI's trust signals stay honest.
- Same-family bias on the judge is removed: the verifier is Anthropic Haiku in production; falls back to GitHub Models only when the Anthropic key is missing or quota-exhausted (with a visible degradation event).
- Saturation is detected by embedding novelty, not by a hard round cap — research stops when a new round adds < 10 % new information vs. the previous one.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|---|---|---|
| RF-01·E (layered stopping) | Coverage / agreement / judge gates | **Extends** — adds `SaturationDetected` signal (novelty-based, embedding distance) as a `StoppingSignal` plugin of the existing seam. |
| RF-02 (stopping is success) | Honest stops are first-class outcomes | **Amended** — the enum collapses from 7 to 4 values. Honest finals are now expressed as `stopped_by_budget` + `AnswerKind ∈ {BEST_EFFORT, SCENARIO, TRADEOFF, WEIGHTED, ETHICAL_REDIRECT}` + a new optional `stop_rationale: str` field on `StoppedEvent` that preserves the legacy reason text. |
| RF-06 (synthesis) | Synthesizer produces the final answer | **Amended** — the single synthesizer template becomes six discriminated templates keyed on `AnswerKind`. Routing lives entirely in the synthesizer prompt + a small `app/output/templates.py` module; no new plugin seam. |
| RF-12 (`final_confidence`) | Confidence formula | **Amended** — `final_confidence = min(S_effective, J)` where `S_effective = S_raw · kind_ceiling[AnswerKind]`. Pre-BRD-21 traces (where `kind_ceiling` is absent) replay with `S_effective = S_raw` (default ceiling 1.0 — see §4.11 backward-compat note). |
| RF-13 (UI as trust surface) | Surface every guarantee | **Extends** — the trace renders `AnswerKind`, the `kind_ceiling` applied, the `stop_rationale` quote, the `SaturationDetected` event when present, and the `JudgeProviderDegraded` event when the verifier falls back. |
| RF-17 (always answer — NEW) | The agent must produce a useful answer for every run that does not error or cancel | **New RF, added by this BRD.** Wording in §12. |
| RF-18 (per-kind ceilings — NEW) | Confidence ceilings depend on `AnswerKind` to keep trust honest | **New RF, added by this BRD.** Wording in §12. |
| RF-19 (independent verifier — NEW) | The judge runs in a different LLM family than the synthesizer when possible | **New RF, added by this BRD.** Wording in §12. |
| RF-03 (event log append-only) | Schema additive | **Preserved unchanged.** New events (`SaturationDetected`, `JudgeProviderDegraded`, `QuestionMemoryHit`) are additive. New fields on existing events (`answer_kind`, `kind_ceiling`, `s_effective`, `stop_rationale`) are all `X \| None = None`. Pre-BRD-21 traces replay byte-identically when the migration is applied. |
| RF-05 (single-server) | `uvicorn --workers 1` | **Preserved unchanged.** All new components are in-process: in-memory embeddings, in-memory question index, in-process verifier call. |
| RF-08 (read determinism) | No live LLM regeneration on read | **Preserved unchanged.** Every LLM output (synth, judge, saturation novelty score) is persisted; replay never re-invokes. |

> **Doc updates (binding, in scope of this BRD):**
> - `requirement-understanding.md` — top-of-file amendment block adding RF-17, RF-18, RF-19; marking RF-02, RF-06, RF-12 as amended.
> - `confidence-calculation.md` — amendment block defining `kind_ceiling[]` and the new `S_effective` formula.
> - `stopping-signal-analysis.md` — mapping table `honest_*` legacy values → new `AnswerKind` + `stop_rationale`.
> - `ai-services.md` — Anthropic Haiku as judge provider in V1; OpenAI `text-embedding-3-small` as the embedding provider.

---

## 3. Dependencies

| Depends On | Required For |
|---|---|
| BRD-01 (DB schema) | Alembic migration for the `StopReason` collapse and the new `stop_rationale` column. |
| BRD-02 (domain events) | Discriminated-union additions for the 3 new event types + 4 new optional fields. |
| BRD-05 (LLM client) | Provider switch in `app/llm/client.py` to route the judge call to Anthropic Haiku when the Anthropic key is configured; embedding call routed to OpenAI via the same client. |
| BRD-08 (confidence calculation) | `final_confidence = min(S_effective, J)` replaces `min(S, J)`. |
| BRD-09 (StoppingSignals seam) | `SaturationDetected` is a `StoppingSignal` plugin. |

**New external services:**

- **Anthropic Claude Haiku** — judge provider in V1. New env: `ANTHROPIC_API_KEY: SecretStr`. Missing key → fallback to GitHub Models + `JudgeProviderDegraded` event.
- **OpenAI `text-embedding-3-small`** via `litellm` — embedding provider for saturation novelty + question memory. New env: `OPENAI_API_KEY: SecretStr`. **Required**; missing key disables `SaturationDetected` and question memory (graceful degradation; no crash).

**Schema migration required** (single migration for the `StopReason` collapse + `stop_rationale` column).

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    domain/
      enums.py                              # MODIFY: AnswerKind (6 values, NEW);
                                            #          QuestionType +PERSONAL_PRIVATE,
                                            #          +SUBJECTIVE_OPINION (6 → 8);
                                            #          StopReason 7 → 4 values
      events.py                             # MODIFY: +SaturationDetectedEvent,
                                            #          +JudgeProviderDegradedEvent,
                                            #          +QuestionMemoryHitEvent;
                                            #          +answer_kind, +kind_ceiling, +s_effective
                                            #          on JudgeRuledEvent;
                                            #          +answer_kind, +stop_rationale on StoppedEvent
    llm/
      client.py                             # MODIFY: provider routing — judge → Anthropic Haiku
                                            #          when ANTHROPIC_API_KEY set; embeddings →
                                            #          openai/text-embedding-3-small via litellm
      models.py                             # MODIFY: +answer_kind on SynthesizedAnswer (optional)
      prompts.py                            # MODIFY: six synthesizer templates keyed on AnswerKind
    agent/
      tasks/
        select_answer_kind.py               # NEW: deterministic AnswerKindInputs resolver
        draft.py                            # MODIFY: call resolver, route to template per kind
      run_state.py                          # MODIFY: +answer_kind, +s_effective, +kind_ceiling
    output/
      templates.py                          # NEW: pure helper rendering the 6 template skeletons
    stopping/
      saturation.py                         # NEW: SaturationDetectedSignal (embedding-novelty)
      __init__.py                           # MODIFY: register SaturationDetected at correct priority
    confidence/
      structural.py                         # MODIFY: emit s_effective = s_raw × kind_ceiling
    services/
      question_memory.py                    # NEW: in-memory recent-question index (per user)
    config.py                               # MODIFY: +ANTHROPIC_API_KEY, +OPENAI_API_KEY
  alembic/
    versions/
      2026_05_27_collapse_stop_reason.py    # NEW: rewrite honest_* → stopped_by_budget +
                                            #       populate stop_rationale; check constraint update
  tests/
    test_resolver_acceptance.py             # NEW: 8-row binding matrix (see §10)
    test_select_answer_kind.py              # NEW: branch coverage on resolver
    test_synth_templates.py                 # NEW: per-template prompt structure
    test_kind_ceiling_applied.py            # NEW: S_effective math invariant
    test_stop_reason_collapse_migration.py  # NEW: Alembic round-trip on legacy fixtures
    test_saturation_signal.py               # NEW: novelty score firing/not firing
    test_judge_provider_independence.py     # NEW: Anthropic path emits no degraded event;
                                            #       missing key fires JudgeProviderDegraded
    test_question_memory.py                 # NEW: in-memory near-duplicate detection
    fixtures/runs/2026-05-27-best-effort.jsonl   # NEW golden trace
    fixtures/runs/2026-05-27-scenario.jsonl      # NEW golden trace
    fixtures/runs/2026-05-27-ethical-redirect.jsonl  # NEW golden trace
frontend/
  src/
    types/
      events.ts                             # REGEN via scripts/export_types.py
```

### 4.2 New enum: `AnswerKind`

```python
class AnswerKind(StrEnum):
    DIRECT             = "direct"               # one-shot factual; confidence ceiling 1.00
    WEIGHTED           = "weighted"             # criteria-weighted comparative; ceiling 0.90
    SCENARIO           = "scenario"             # multi-future with probability bands; ceiling 0.80
    TRADEOFF           = "tradeoff"             # opinion / subjective tradeoff frame; ceiling 0.80
    BEST_EFFORT        = "best_effort"          # honest partial answer; ceiling 0.70
    ETHICAL_REDIRECT   = "ethical_redirect"     # privacy/PII redirect; ceiling 1.00 (judged on policy fit, not coverage)
```

### 4.3 `StopReason` collapse (4 values, breaking)

```python
class StopReason(StrEnum):
    JUDGE_CONFIRMED   = "judge_confirmed"     # judge approved; happy path
    STOPPED_BY_BUDGET = "stopped_by_budget"   # any honest stop, with stop_rationale + AnswerKind
    USER_CANCELLED    = "user_cancelled"
    ERRORED           = "errored"
```

Legacy mapping (applied by the migration to all historical events):

| Legacy value | New `StopReason` | New `stop_rationale` (verbatim text persisted) | Typical new `AnswerKind` |
|---|---|---|---|
| `honest_unanswerable` | `stopped_by_budget` | `"honest_unanswerable: <legacy reason field>"` | `BEST_EFFORT` |
| `honest_contradiction` | `stopped_by_budget` | `"honest_contradiction: <legacy reason field>"` | `WEIGHTED` |
| `honest_ambiguous` | `stopped_by_budget` | `"honest_ambiguous: <legacy reason field>"` | `BEST_EFFORT` |

### 4.4 `QuestionType` extension (6 → 8)

```python
class QuestionType(StrEnum):
    FACTUAL              = "factual"
    COMPARATIVE          = "comparative"
    CAUSAL               = "causal"
    STATE_OF_ART         = "state_of_art"
    PREDICTIVE_FUTURE    = "predictive_future"
    DEFINITIONAL         = "definitional"
    PERSONAL_PRIVATE     = "personal_private"      # NEW — PII / private-data requests
    SUBJECTIVE_OPINION   = "subjective_opinion"    # NEW — taste / preference questions
```

The classifier system prompt is extended to recognize the two new types; classifier output validation rejects unknown values.

### 4.5 `AnswerKind` resolver

```python
@dataclass(frozen=True, slots=True)
class AnswerKindInputs:
    question_type: QuestionType
    structural_confidence: float    # S_raw, in [0, 1]
    coverage: float                 # in [0, 1]
    agreement: float                # in [0, 1]
    ambiguity_flag: bool = False

def select_answer_kind(inputs: AnswerKindInputs) -> AnswerKind:
    # Priority order (deterministic; binding):
    # 1. PERSONAL_PRIVATE        → ETHICAL_REDIRECT
    # 2. PREDICTIVE_FUTURE       → SCENARIO
    # 3. SUBJECTIVE_OPINION      → TRADEOFF
    # 4. ambiguity OR cov < 0.5  → BEST_EFFORT
    # 5. cov ≥ 1.0, agr < 0.6    → WEIGHTED
    # 6. cov ≥ 1.0, S ≥ 0.75,
    #    agr ≥ 0.6               → DIRECT
    # 7. else                    → BEST_EFFORT
```

Thresholds are constants in `select_answer_kind.py` (`_DIRECT_MIN_S`, `_DIRECT_MIN_COVERAGE`, `_DIRECT_MIN_AGREEMENT`, `_WEIGHTED_AGREEMENT_CEILING`, `_BEST_EFFORT_COVERAGE_FLOOR`) — calibrated against the 8-row acceptance matrix in §10.

### 4.6 Per-kind ceilings + new confidence formula

```python
kind_ceiling: dict[AnswerKind, float] = {
    AnswerKind.DIRECT:           1.00,
    AnswerKind.ETHICAL_REDIRECT: 1.00,
    AnswerKind.WEIGHTED:         0.90,
    AnswerKind.SCENARIO:         0.80,
    AnswerKind.TRADEOFF:         0.80,
    AnswerKind.BEST_EFFORT:      0.70,
}

S_effective    = S_raw * kind_ceiling[answer_kind]
final_confidence = min(S_effective, J)
```

`JudgeRuledEvent` carries `answer_kind`, `kind_ceiling` (the value applied), and `s_effective` so the FE renders the ceiling explicitly in the trust surface (RF-13).

### 4.7 Six synthesizer templates

All six templates live in `app/output/templates.py` as pure render helpers + matching prompt sections in `app/llm/prompts.py`. Each template:

- Reuses the existing citation + evidence-block convention.
- Imposes a structure proper to the kind (e.g. `SCENARIO` requires 2–4 labeled scenarios with probability bands; `TRADEOFF` requires a tradeoff matrix; `WEIGHTED` requires criteria + per-criterion scores; `BEST_EFFORT` requires the 4-part honest structure: what we know / what we couldn't confirm / our best current take / what would close the gap).
- Carries the language rule ("Reply in the same language the user has been using; Spanish by default") in the user-prompt block.

### 4.8 `SaturationDetected` signal

```python
class SaturationDetectedSignal(StoppingSignal):
    """Fires when a new search round adds < 10% novel information vs. the previous round."""
```

Mechanics:

1. Each round's accumulated evidence is summarized into a single embedding via OpenAI `text-embedding-3-small`.
2. Novelty = `1 - cosine_similarity(emb_round_n, emb_round_n-1)`.
3. If `novelty < 0.10` AND `len(rounds) >= 2`, the signal fires.
4. Decision: forces `SYNTHESIZING`; the judge + best-effort fallback decide the final stop. Emits `SaturationDetectedEvent { round_n, novelty_score, threshold }`.
5. Priority: **medium** — after `BudgetExhausted` and `UserCancelled`, before the judge-loop cap.

**Graceful degradation**: if `OPENAI_API_KEY` is missing, the signal returns `should_fire=False` permanently and logs a single startup warning.

### 4.9 Independent verifier (Anthropic Claude Haiku)

`llm/client.py` routes `LLMRole.JUDGE` to Anthropic Haiku when `ANTHROPIC_API_KEY` is configured. The synthesizer continues to use GitHub Models — the two LLM families are independent.

Fallback policy:

- Missing `ANTHROPIC_API_KEY` at startup → judge stays on GitHub Models; a single `JudgeProviderDegraded` event is emitted **once per run** when the first judge call is made.
- Runtime Anthropic 429 / 5xx / quota → tenacity retries up to 3 with exponential backoff; on definitive failure, the orchestrator emits `JudgeProviderDegraded` and continues with GitHub Models. **The run does not error** — degradation is observability, not failure (RF-19).

The trace UI renders `JudgeProviderDegraded` so users see when same-family bias was unavoidable.

### 4.10 Cross-run question memory (in-memory only)

A small per-user index `services/question_memory.py`:

- Stores `(question_embedding, run_id, timestamp)` for the last 50 runs per user, in-memory.
- On a new run, embeds the question and finds the highest cosine match.
- If similarity > 0.92 AND the matched run is the same user's AND within the last 24 h, emits `QuestionMemoryHitEvent { previous_run_id, similarity_score }`.
- No persistence to DB — process restart resets the index. Cold-start cost = 0.

### 4.11 Backward compatibility on replay

Pre-BRD-21 events lack `answer_kind`, `kind_ceiling`, `s_effective`, `stop_rationale`. `_fold_events` defaults each to a sentinel:

- `answer_kind` → `None` (render as `"(legacy)"` in trace UI).
- `kind_ceiling` → `1.0` (so `S_effective = S_raw`; identical numeric behaviour to pre-BRD-21).
- `stop_rationale` → `None`.

Legacy `StopReason` values in the `events` table are **rewritten by the Alembic migration** (not by `_fold_events`) to keep the enum check constraint valid post-migration. The migration is reversible: down-revision restores the legacy values from `stop_rationale` parsing.

### 4.12 What does NOT change

- The 3 plugin seams (`Source`, `StoppingSignal`, `OutputRenderer`). No new seam — the synthesizer template router is in-process logic, not an extension point.
- The SSE protocol (new events ship via the existing channel; new fields are optional).
- The number of LLM provider abstractions — `litellm` already wraps Anthropic; no new provider layer.
- The classifier role assignment (still GitHub Models).
- The append-only invariant of the event log (RF-03).

---

## 5. Functional Requirements

| FR | Description | Verification |
|---|---|---|
| FR-21-01 | Every non-errored, non-cancelled run emits a `Stopped` event with a non-empty answer surface. The synthesizer is never skipped. | AC-01 |
| FR-21-02 | `StopReason` enum has exactly 4 values; the three `honest_*` values are absent from the codebase. | AC-02 |
| FR-21-03 | `AnswerKind` enum has exactly 6 values and is persisted on `JudgeRuledEvent` and `StoppedEvent` for every new run. | AC-03 |
| FR-21-04 | `QuestionType` has exactly 8 values; the classifier recognizes `PERSONAL_PRIVATE` and `SUBJECTIVE_OPINION`. | AC-04 |
| FR-21-05 | `select_answer_kind` is deterministic and returns the documented kind for every row of the 8-row acceptance matrix in §10. | AC-05 |
| FR-21-06 | `final_confidence = min(S_effective, J)` where `S_effective = S_raw × kind_ceiling[answer_kind]` and `kind_ceiling` follows §4.6. | AC-06 |
| FR-21-07 | The synthesizer routes to one of 6 templates keyed on `AnswerKind`; each template enforces its documented structure. | AC-07 |
| FR-21-08 | `SaturationDetectedSignal` fires when novelty < 0.10 between two consecutive rounds and emits `SaturationDetectedEvent`; it forces `SYNTHESIZING` rather than terminating directly. | AC-08 |
| FR-21-09 | The judge LLM call routes to Anthropic Claude Haiku when `ANTHROPIC_API_KEY` is configured; otherwise it routes to GitHub Models with a single `JudgeProviderDegraded` event per run. | AC-09 |
| FR-21-10 | Anthropic provider failures (429 / 5xx / quota) trigger tenacity retries and, on definitive failure, fall back to GitHub Models with `JudgeProviderDegraded` — the run does not error. | AC-10 |
| FR-21-11 | Question memory emits `QuestionMemoryHitEvent` when a new question by the same user is > 0.92 cosine-similar to a question from the last 24 h. | AC-11 |
| FR-21-12 | Embedding calls route to `openai/text-embedding-3-small` via `litellm`; missing `OPENAI_API_KEY` disables saturation + question memory gracefully with one startup warning. | AC-12 |
| FR-21-13 | Legacy `honest_*` `StopReason` values in the `events` table are rewritten by the Alembic migration to `stopped_by_budget` + a `stop_rationale` text preserving the legacy reason. | AC-13 |
| FR-21-14 | Pre-BRD-21 traces replay byte-identically: `S_effective` defaults to `S_raw` (ceiling 1.0) and missing fields surface as `None`. | AC-14 |
| FR-21-15 | The trace UI renders `AnswerKind`, `kind_ceiling`, `s_effective`, and the `stop_rationale` (when present); `JudgeProviderDegraded` and `SaturationDetected` events are visible. | AC-15 |
| FR-21-16 | The 8-row binding matrix (§10) passes in CI on every commit, independent of LLM availability (mocked). | AC-16 |

---

## 6. Non-Functional Requirements

| NFR | Requirement | Verification |
|---|---|---|
| NFR-21-01 | The resolver, the templates and the kind ceilings have **zero LLM dependency** — they are pure Python functions with deterministic outputs. | Unit test suite runs offline. |
| NFR-21-02 | Anthropic Haiku judge call has p95 < 2.0 s for a typical run; on degradation, the run latency is unchanged vs. pre-BRD-21. | Smoke fixture timing. |
| NFR-21-03 | Embedding calls cost < $0.001 per run at the configured budget (saturation + question memory combined < 1k tokens / run). | Cost telemetry. |
| NFR-21-04 | `pyright --strict` + `ruff check` clean on every new and modified file. | CI. |
| NFR-21-05 | Coverage ≥ 80 % on every new module (`select_answer_kind.py`, `templates.py`, `saturation.py`, `question_memory.py`, judge-routing branches in `llm/client.py`). | `pytest --cov`. |
| NFR-21-06 | All new prompts, identifiers, log messages and `stop_rationale` strings are English. User-facing replies follow the existing user-language rule. | Manual + grep. |
| NFR-21-07 | The Alembic migration is reversible (down-revision restores legacy `StopReason` values from `stop_rationale` parsing). | Migration test. |
| NFR-21-08 | Single-server / single-worker (RF-05). All new state is in-process; no new infra dependency. | Architecture review. |

---

## 7. Acceptance Criteria

| AC | Statement |
|---|---|
| AC-01 | Integration test: across 8 representative questions, every run emits `Stopped` with non-empty `answer_prose` (or, for `ETHICAL_REDIRECT`, a non-empty policy explanation). |
| AC-02 | Unit test: `StopReason` has exactly 4 members; `grep -rni "honest_unanswerable\|honest_contradiction\|honest_ambiguous" backend/app` returns no Python code matches. |
| AC-03 | Unit test: every `JudgeRuledEvent` and `StoppedEvent` produced post-migration has a non-null `answer_kind` matching one of the 6 enum values. |
| AC-04 | Classifier integration test: questions tagged `PERSONAL_PRIVATE` and `SUBJECTIVE_OPINION` are recognized; unknown values raise `ValidationError`. |
| AC-05 | Table-driven test `test_resolver_acceptance.py` enforces the 8-row matrix in §10; every row must produce its documented `AnswerKind`. Test runs in CI offline. |
| AC-06 | Property test on `_fold_events`: across all golden traces, `final_confidence == min(s_raw * kind_ceiling[answer_kind], J)`. |
| AC-07 | Unit test per template: prompt body contains the documented structural sections (scenarios for SCENARIO, tradeoff matrix for TRADEOFF, criteria for WEIGHTED, 4-part shape for BEST_EFFORT, etc.). |
| AC-08 | Unit test: synthetic round embeddings with cosine similarity 0.95 → novelty=0.05 → `SaturationDetectedSignal` fires and emits the event; similarity 0.70 → does not fire. |
| AC-09 | Integration test: with `ANTHROPIC_API_KEY` set, the judge call routes through Anthropic; no `JudgeProviderDegraded` event emitted. Without the key, the judge routes through GitHub Models and exactly one `JudgeProviderDegraded` event is emitted on the first judge call of the run. |
| AC-10 | Integration test: simulated Anthropic 5xx → tenacity retries → on definitive failure, fallback to GitHub Models + `JudgeProviderDegraded`. Run completes successfully. |
| AC-11 | Unit test: a question 0.95-similar to a 1-hour-old question by the same user → `QuestionMemoryHitEvent` emitted. Same question by a different user → no event. Older than 24 h → no event. |
| AC-12 | Startup test: missing `OPENAI_API_KEY` produces one warning log line, `SaturationDetectedSignal.should_fire` is permanently `False`, and `QuestionMemoryHitEvent` is never emitted. The run completes normally. |
| AC-13 | Migration test: applying the migration on a fixture DB with 3 legacy `honest_*` events rewrites them to `stopped_by_budget` + the documented `stop_rationale` text. |
| AC-14 | Golden-trace replay: a pre-BRD-21 trace replays with `S_effective == S_raw` and `final_confidence` equals the historical value. |
| AC-15 | FE component test: trace panel renders `AnswerKind`, the `kind_ceiling` applied, and the `stop_rationale` text; `JudgeProviderDegraded` and `SaturationDetected` show as distinct rows in the timeline. |
| AC-16 | CI gate: `pytest -q` + `pyright --strict` + `ruff check backend` + `vitest run --reporter=basic` pass on every commit; failing the 8-row matrix blocks merge. |

---

## 8. Test Plan (binding)

**New backend test files:**

| File | Scope |
|---|---|
| `tests/test_resolver_acceptance.py` | 8-row binding matrix (§10). |
| `tests/test_select_answer_kind.py` | Branch coverage on resolver (each of the 7 documented branches). |
| `tests/test_synth_templates.py` | Per-template prompt structure assertions. |
| `tests/test_kind_ceiling_applied.py` | `S_effective` math invariant. |
| `tests/test_stop_reason_collapse_migration.py` | Alembic round-trip on legacy fixtures. |
| `tests/test_saturation_signal.py` | Novelty score firing / not firing; graceful degradation when key missing. |
| `tests/test_judge_provider_independence.py` | Anthropic happy path; missing key fires degraded event; runtime failure falls back. |
| `tests/test_question_memory.py` | In-memory near-duplicate detection; per-user isolation; 24 h window. |
| `tests/fixtures/runs/2026-05-27-best-effort.jsonl` | New golden trace exercising `BEST_EFFORT`. |
| `tests/fixtures/runs/2026-05-27-scenario.jsonl` | New golden trace exercising `SCENARIO`. |
| `tests/fixtures/runs/2026-05-27-ethical-redirect.jsonl` | New golden trace exercising `ETHICAL_REDIRECT`. |
| `tests/fixtures/runs/<pre-BRD-21 fixture>.jsonl` | Existing golden traces — must replay byte-identically (AC-14). |

Coverage gate ≥ 80 % on every new file.

---

## 9. Out of Scope

| Item | Reason |
|---|---|
| Persistent vector store / pgvector for question memory | RF-05 (single-server) + the 50-run in-memory window covers V1 expectations. Reconsider in V2 if cross-server question memory is needed. |
| Additional `AnswerKind` values beyond the 6 listed | The 6-value enum is the V1 contract; matrix-driven addition would require a new BRD. |
| Replacing the synthesizer template router with a plugin seam | Three seams is the architectural rule; a fourth would proliferate without benefit. |
| Streaming the answer token-by-token from the backend | RF-08 (read determinism) keeps the synthesizer atomic; presentation animation is BRD-24's concern. |
| Replacing GitHub Models with Anthropic everywhere | Only the **judge** role benefits from cross-family independence in V1; synthesizer and classifier stay on GitHub Models. |
| Tuning resolver thresholds at runtime via config | Thresholds are constants by design (deterministic, test-locked); tuning is a code change. |

---

## 10. Acceptance Matrix (binding — §0.8 of IP-21 verbatim)

The 8-row matrix below is the authoritative smoke contract for the resolver, the templates, and the stop logic. Every WP that touches these surfaces must keep the matrix green. The matrix runs offline in CI (`test_resolver_acceptance.py`, AC-05/AC-16) and is mirrored by per-row golden traces.

| # | Question (abridged) | `QuestionType` | Expected `AnswerKind` | Resolver inputs (S, cov, agr, amb) | Critical capability |
|---|---|---|---|---|---|
| 1 | Capital of Japan | `FACTUAL` | `DIRECT` | `S=0.95, cov=1.0, agr=1.0, amb=False` | early-stop |
| 2 | PostgreSQL vs MongoDB for a small SaaS | `COMPARATIVE` | `WEIGHTED` | `S=0.70, cov=1.0, agr=0.55, amb=False` | criteria-weighted |
| 3 | Best programming language? | `COMPARATIVE` + ambiguity | `BEST_EFFORT` | `S=0.60, cov=0.8, agr=0.5, amb=True` | empty-comparative detector |
| 4 | Is intermittent fasting healthy? | `FACTUAL` / `CAUSAL` | `WEIGHTED` | `S=0.65, cov=1.0, agr=0.45, amb=False` | contradictions surfaced |
| 5 | Long-term risks of AI-generated code | `PREDICTIVE_FUTURE` | `SCENARIO` | `S=0.60, cov=0.7, agr=0.6, amb=False` | scenarios + probability bands |
| 6 | EDA vs sync microservices at scale | `COMPARATIVE` | `WEIGHTED` | `S=0.70, cov=1.0, agr=0.55, amb=False` | architecture tradeoff |
| 7 | Best long-term memory approach for AI agents | `STATE_OF_ART` | `WEIGHTED` (converges) / `BEST_EFFORT` (saturated) | `S=0.55, cov=0.6, agr=0.55, amb=False` | saturation signal |
| 8 | AI replacing mid-level engineers in 10y? | `PREDICTIVE_FUTURE` | `SCENARIO` | `S=0.50, cov=0.7, agr=0.4, amb=False` | multi-scenario + contradictions |

---

## 11. Success Metrics (binding, measured 2 weeks post-rollout)

| Metric | Baseline (pre BRD-21) | Target |
|---|---|---|
| Runs ending with empty answer surface (legacy `honest_*`) | ~12 % of completed runs | **0 %** |
| `final_confidence` reported for `BEST_EFFORT` answers | up to 0.95 (honest_unanswerable could still report S) | **≤ 0.70** (ceiling-clipped) |
| Judge same-family bias (synthesizer + judge both GitHub Models) | 100 % of runs | **< 5 %** of runs (only when Anthropic key missing or quota-exhausted) |
| Saturation-triggered early stops on `STATE_OF_ART` queries | 0 % | **measurable** (not a hard target; signal must be visible when it fires) |
| Cross-run question memory hit rate | 0 % | **measurable** (typically 2–8 % depending on user behaviour) |
| Replay determinism | 100 % | **100 %** (pre- and post-BRD-21 golden traces stable across 10 replays) |
| 8-row acceptance matrix pass rate | n/a | **100 %** on every commit |

---

## 12. New RF wording (binding additions to `requirement-understanding.md`)

**RF-17 — Always-answer guarantee.** For every run that terminates with `StopReason ∈ {judge_confirmed, stopped_by_budget}`, the system MUST produce a non-empty answer surface (answer text or a policy explanation for `ETHICAL_REDIRECT`). The previous `honest_unanswerable / honest_contradiction / honest_ambiguous` terminal states are removed; their semantic content lives in the optional `stop_rationale` text on `Stopped` plus the `AnswerKind` shape descriptor.

**RF-18 — Per-kind confidence ceilings.** The reported `final_confidence` MUST be bounded by a per-`AnswerKind` ceiling (table in §4.6). `final_confidence = min(S_effective, J)` where `S_effective = S_raw × kind_ceiling[answer_kind]`. The ceiling exists to keep the trust surface honest — a best-effort answer cannot present the same confidence as a direct answer on the same `S_raw`.

**RF-19 — Independent verifier.** The judge LLM call SHOULD run in a different LLM family than the synthesizer when that family is available. In V1, the synthesizer is GitHub Models and the judge is Anthropic Claude Haiku via `litellm`. When the Anthropic provider is unavailable (missing key, runtime quota exhaustion, definitive HTTP failure), the system MUST fall back to GitHub Models AND emit a `JudgeProviderDegraded` event on the trace so users see when same-family bias was unavoidable. The run MUST NOT error on degradation.

---

## 13. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Resolver thresholds drift after future refactors and the 8-row matrix breaks | Medium | High | Matrix runs in CI offline (AC-05/AC-16); any drift fails a PR. |
| Anthropic provider key not yet provisioned on production | High | Medium | Graceful degradation + `JudgeProviderDegraded` event (AC-09). |
| OpenAI embedding key missing in some envs | Medium | Low | Saturation + question memory disabled at startup with one warning (AC-12); no crash. |
| Alembic migration corrupts legacy events | Low | High | Round-trip test on a representative legacy fixture (AC-13); migration is reversible. |
| `kind_ceiling` for `ETHICAL_REDIRECT = 1.0` could over-state confidence on policy redirects | Low | Medium | `ETHICAL_REDIRECT` answers are scored on policy fit, not coverage — the ceiling protects the user from a confidence drop on a deliberate non-research response. |
| Synthesizer routing collapses two templates into one in a future change | Low | Medium | One `test_synth_templates.py` test per template asserts the structural sections; collapse fails CI. |
| Cross-run question memory leaks PII across users | High if mishandled | High | The index is **per-user** by construction (key = `username`); a cross-user test (AC-11) asserts isolation. |
| Replay determinism breaks because new events appear in old traces | High if mishandled | High | Golden-trace replay (AC-14) freezes the contract; `_fold_events` defaults all new fields when absent. |
| Anthropic Haiku rejects the judge prompt format | Medium | Medium | Reuse the existing judge structured-output schema via `instructor`; provider-agnostic. |
| Saturation false positives on legitimately-low-novelty topics | Medium | Low | Signal forces `SYNTHESIZING`, not termination — the judge has the final say. |

---

## 14. References

- IP-21 implementation plan: [IP-21](../implementation-plans/IP-21-always-answer-refactor.md)
- Source proposal: [research-method-refactor-proposal.md](../../understanding-phase/research-method-refactor-proposal.md)
- Confidence formula (amended by this BRD): [confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- Stopping policy (amended by this BRD): [stopping-signal-analysis.md](../../understanding-phase/stopping-signal-analysis.md)
- AI services (amended by this BRD): [ai-services.md](../../technical-phase/ai-services.md)
- Dependencies: BRD-01 (schema), BRD-02 (events), BRD-05 (LLM client), BRD-08 (confidence), BRD-09 (StoppingSignals).
- Builds toward: BRD-22 (complexity-aware planning consumes `AnswerKind`), BRD-23 (research quality preserves `min(S_effective, J)`), BRD-25 (3-lane flow preserves the 4-value `StopReason`), BRD-26 (agentic stopping preserves the 4-value enum and routes honest stops through `stop_rationale`).
- Requirements catalogue: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
