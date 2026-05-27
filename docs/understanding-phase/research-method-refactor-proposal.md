# Research Method — Gap Analysis & Refactor Proposal

> Expert evaluation of Novum's current research method against the reference architecture described in [advanced-ai-research.md](advanced-ai-research.md), and a concrete refactor plan to close the gaps — under the new product constraint **"the agent must always produce a usable response; pure `honest_unanswerable` is not an acceptable terminal."**

Status: **ratified 2026-05-27.** All six decisions in §8 accepted; pgvector replaced by in-memory cosine (see WP-4 / WP-6). Next step: apply the RF edits in §5 to [requirement-understanding.md](requirement-understanding.md), then execute work packages in the order shown in §6.

---

## TL;DR

- **Where we are strong (≥ on par with the reference):** problem framing, task decomposition, iterative search/analyze loop, dual-gate confidence (`min(S, J)`), full event-log inspectability, fork/re-attempt semantics. These already exceed what most "AI research" products ship.
- **Where we are behind:** no semantic retrieval (embeddings/RAG), no cross-run memory, no parallel hypothesis exploration (tree-of-thought), saturation signal `C` is declared but not actually computed, "verifier" judge shares provider with planner/synthesizer, sources are limited to web+wiki.
- **Where the new constraint forces a rewrite:** the 7-value `stop_reason` enum collapses to **2 positive terminals + 1 hard error**. Every former "honest no-answer" path becomes a **structured answer with alternatives, scenarios, or explicit tradeoffs**, plus a calibrated confidence floor. The system never says "I cannot"; it says "**given X, the best supported response is Y, with alternatives A/B and confidence Z**".

---

## 1. Side-by-side: reference architecture vs Novum today

The reference document defines a 7-stage pipeline. Novum's current FSM implements a near-identical structure, with notable strengths and three structural gaps.

| Reference stage | Novum today (file/module) | Status | Notes |
|---|---|---|---|
| **1. Understanding the question** | [normalize.py](../../backend/app/agent/tasks/normalize.py) + [classify.py](../../backend/app/agent/tasks/classify.py) | ✅ On par | Typo/casing normalization + question-type classifier (Types 1–8). Better than most reference implementations. |
| **2. Problem decomposition** | [plan.py](../../backend/app/agent/tasks/plan.py) — `create_plan` + `critique_plan` + `revise_plan` | ✅ Ahead | Adds an explicit critique/revise sub-loop the reference does not mention. Reference mentions "tree-of-thought" — we only do linear plans with revisions. |
| **3. Information retrieval** | [sources/](../../backend/app/sources/) — Tavily + Wikipedia plugin seam | 🟡 Partial | Two keyword-based sources. No vector store, no curated corpus. No API/document/paper-specific retrievers. |
| **4. Semantic retrieval (embeddings/RAG)** | — | ❌ **Missing** | Not in V1. Largest single gap vs reference. |
| **5. Iterative reasoning loop** | [orchestrator.py](../../backend/app/agent/orchestrator.py) FSM | ✅ On par | `PLANNING → CRITIQUING → SEARCHING → ANALYZING → DRAFTING → JUDGING` loop, with disconfirmation back-edges (RF-15). |
| **6. Confidence evaluation** | [confidence/](../../backend/app/confidence/) — `final_confidence = min(S, J)` | ✅ **Ahead** | Reference describes the goal abstractly; we have a published formula with 4 weighted structural components + adversarial judge. |
| **7. Sourced answer generation** | [draft.py](../../backend/app/agent/tasks/draft.py) — `SynthesizedAnswer` with per-claim citations | ✅ On par | Every claim → ≥1 evidence chunk → original URL + capture timestamp. |
| **Memory systems** (cross-run) | — | ❌ Missing | Reference treats persistent memory as essential. Novum's "memory" is per-run only (event log). |
| **Verifier models (independent)** | [llm/](../../backend/app/llm/) — 4 roles, **same provider** (GitHub Models) | 🟡 Weak | Judge shares the provider, often the same model family, as planner/synthesizer. Real verifier separation needs a second provider. |
| **Inspectability / trace / fork** | `events` table + Level-3 trace UI + RF-03 fork | ✅ **Ahead** | The reference describes this as future state ("Re-runnable from any decision point"). We have it as V1. |

**Verdict.** On structure and discipline (decomposition, confidence, trace, fork) Novum is at or above the reference. On *information substrate* (semantic retrieval, memory, source heterogeneity, verifier independence) Novum is materially behind.

---

## 2. The new product constraint and why it changes the design

> *"The agent must always produce a useful answer. `honest_unanswerable` is not acceptable — at minimum it must propose alternatives, scenarios, or framings."*

This is a **product decision that overrides RF-01·E and RF-06** as currently written. The reference document agrees in spirit: see *"§7 The system stopped because…"* — the reference always describes a stop that **produced an answer**, never a stop that produced silence. Pure refusal is treated by the reference as a **calibration problem**, not a feature.

The implications are concrete:

1. **`stop_reason` collapses from 7 values to 3.** The honest-stop family (`honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`) is removed as a positive terminal class. Their **conditions still exist** — they just no longer terminate the run; they shape the *answer template*.
2. **Confidence becomes the only honesty signal.** Instead of refusing, the agent commits to an answer and lowers `final_confidence` accordingly. The trust contract moves from *"we tell you when we cannot answer"* to *"we always answer, and we tell you how much to trust each part."*
3. **A new synthesis pathway is required** that consumes `{ambiguity, contradiction, sparsity}` flags and produces a **structured response with explicit alternatives**, not a refusal screen.
4. **The classifier no longer rejects question types**, it routes them to specialized response templates (predictive → scenario response, opinion → tradeoff matrix, personal/private → ethical refusal with public alternatives).
5. **The UI rejection screens disappear.** Every run lands on the answer screen, with confidence and alternative-answer panels surfaced by default.

This does **not** weaken the trust contract — it relocates the honesty from *"binary refuse vs answer"* to *"every answer carries calibrated alternatives and confidence."* Arguably it is more honest, because total refusal often hides a defensible best-guess behind a procedural wall.

---

## 3. Refactor proposal — 6 work packages, ordered by ROI

Each package is sized in "pair-session days" (PSD) where 1 PSD ≈ 4–6 focused hours. Total budget if all six land: **~9 PSD**. The first three are **mandatory for the new product constraint**; the last three close the gaps vs the reference and are independently sequenceable.

### WP-1 · Collapse `stop_reason` and introduce `AnswerKind` (mandatory)

**Scope.**

- Reduce `StopReason` enum to: `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`. Drop `honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`.
- Introduce a new field on `JudgeRuledEvent.payload` and on the final `SynthesizedAnswer`:

  ```python
  class AnswerKind(StrEnum):
      DIRECT = "direct"                # high confidence, single best answer
      WEIGHTED = "weighted"            # multiple candidate answers ranked by support
      SCENARIO = "scenario"            # predictive / future-state, framed as scenarios
      TRADEOFF = "tradeoff"            # subjective / opinion, framed as criteria matrix
      ETHICAL_REDIRECT = "ethical_redirect"   # personal/private — refuses with public alternatives
      BEST_EFFORT = "best_effort"      # ambiguous or sparse evidence — top interpretation + alternatives
  ```

- The orchestrator's final transition is **always** `→ STOPPED(judge_confirmed)` unless budget/cancel/error. The shape of the answer (`AnswerKind`) carries what used to be the differentiation of the honest-stop family.
- Persist `AnswerKind` in the event log for diff-ability across runs.

**Migration impact.** Touches `domain/enums.py`, `domain/events.py`, `agent/orchestrator.py`, `agent/tasks/classify.py` (no longer short-circuits), the judge prompt (now also picks `AnswerKind`), the synthesizer prompt (consumes `AnswerKind` and renders the right template), the trace UI (removes rejection screen, adds AnswerKind badge), the type-export script. Estimated **~150 LOC + prompt rewrites**.

**Cost.** 2 PSD.

---

### WP-2 · Six answer templates in the synthesizer (mandatory)

**Scope.** Extend `draft_answer` and the synthesizer prompt so a single planner/judge pair can produce all six shapes:

| AnswerKind | Triggering conditions | Required components in the final payload |
|---|---|---|
| `direct` | All claims covered, judge sufficient, `S ≥ 0.75`, no open contradictions | `summary`, `sections[]`, `citations[]` — same as today |
| `weighted` | Coverage met but `C_agreement < 0.6` (sources split) | `summary`, `candidates: [{answer, supporting_sources[], strength: 0..1}]`, **rank ordered**, top one labeled "best supported" |
| `scenario` | `question_type == predictive_future` | `scenarios: [{name, premise, likelihood: 0..1, supporting_evidence[]}]`, with a "current expert consensus" rollup section |
| `tradeoff` | `question_type == subjective_opinion` | `criteria: [{name, importance}]` + `options: [{name, scores_by_criterion, who_should_pick_this}]` |
| `ethical_redirect` | `question_type == personal_private` | Short ethical refusal (one paragraph) + `alternatives: [{kind: "public_profile" \| "official_channel" \| "general_method", url?, description}]` |
| `best_effort` | Ambiguity flag OR `C_coverage < 0.5` after dispute resolution | Top interpretation labeled "primary"; `alternative_interpretations: [{interpretation, hypothetical_answer, why_we_didnt_pick_it}]` |

**Selection rule.** A small deterministic resolver in `agent/tasks/select_answer_kind.py` chooses the kind from `(question_type, S, C_coverage, C_agreement, ambiguity_flag)`. The judge confirms or overrides via a structured field, but never goes back to `unanswerable`. The judge's only "no" option is to **lower confidence**, not to refuse.

**Cost.** 2 PSD. Largely prompt + Pydantic model work, modest LOC in Python.

---

### WP-3 · Confidence floors per `AnswerKind` (mandatory)

The collapse only stays honest if confidence is *visibly lower* on the new templates. Without this WP, "always answer" becomes "always lie."

**Scope.**

- Add a per-kind soft floor on the displayed confidence in the UI:

  | AnswerKind | Max displayed `final_confidence` |
  |---|---|
  | `direct` | 1.00 |
  | `weighted` | 0.80 |
  | `scenario` | 0.55 |
  | `tradeoff` | 0.50 |
  | `best_effort` | 0.45 |
  | `ethical_redirect` | n/a (no claim being made) |

  Implementation: the structural score `S` is multiplied by a `kind_ceiling` factor before being fed into `min(S, J)`. The trace shows both the raw `S` and the post-ceiling `S` so the rule is auditable.

- Extend `C_*` components:
  - **New:** `C_kind_appropriateness` (weight 0.10, redistributed from `C_no_conflict`): the judge rates whether the chosen `AnswerKind` matches the evidence shape. Penalizes a `direct` shape on a 3-way contradiction.

- UI: the confidence badge on every answer shows `kind` next to the percentage (e.g. `Scenario · 42%`). No standalone number without its kind.

**Cost.** 1 PSD (formula change + UI badge + one extra LLM output field).

---

### WP-4 · Semantic retrieval and saturation signal (closes reference §4 + §C)

This is the **largest gap vs the reference architecture** and the cheapest one to close at the right scope.

**Scope.**

- Add an **in-process embedding cache per run** keyed by chunk text. Use a small open model (e.g. `text-embedding-3-small` via the existing LLM provider, or a local `bge-small-en-v1.5` via `sentence-transformers`). Embeddings live **only in the per-run `RunState`** as a `dict[chunk_id, np.ndarray]` and are dropped when the run ends. **No pgvector, no vector DB, no persisted vectors.** Resume after a crash re-embeds from the event log (cheap: ≤ 50 chunks per run).
- Use embeddings for two concrete jobs:
  1. **Saturation signal `C` (finally real).** Compute novelty of the last `k` retrieved chunks as `1 - mean(max_cosine_similarity to prior corpus)`. When novelty < 0.15 for `k=3`, emit a `SaturationDetected` event the judge can read.
  2. **Claim-to-evidence matching.** Replace the current text-overlap heuristic with cosine similarity; only chunks with `sim > 0.55` count toward `C_coverage`. Reduces false coverage from off-topic snippets.

- **What we deliberately do NOT add in V1.** A persistent shared vector index across runs (deferred), full RAG over a curated corpus (deferred), reranker models (deferred), **pgvector or any DB-side vector storage** (rejected at ratification — in-memory only).

**Cost.** 2 PSD. Zero new infra (pure Python + numpy). Risk: cold-resume re-embed cost — mitigated by capping run chunks (≤ 50) and batching embeddings per `analyze` round, not per chunk.

---

### WP-5 · Independent verifier (closes reference "verifier models")

**Scope.**

- Allow the judge role to be configured to a **different provider** than planner/synthesizer. Cheapest viable path: route `LLMRole.JUDGE` to **Anthropic Claude Haiku** (or any non-GitHub-Models model) via the existing `litellm` abstraction. Single env var: `JUDGE_PROVIDER=anthropic` / `JUDGE_MODEL=claude-haiku-...`.
- If the second provider is unavailable at runtime, **degrade gracefully**: fall back to the GitHub Models judge but emit a `JudgeProviderDegraded` event so the trace shows the verifier was not independent on that run. UI surfaces this as a small warning on the confidence badge.
- Add a "judge disagreement" signal: when the two-judge mode is enabled (V2), confidence is dampened by `1 - |J1 - J2|`. V1 ships the single-judge cross-provider path only.

**Cost.** 1 PSD. Mostly config + a fallback branch + one new event type.

---

### WP-6 · Cross-run memory (closes reference "memory systems")

**Scope.**

- Introduce a **read-only retrieval over past runs** when a new question is classified. Concretely: after `classify_question`, run a cosine-similarity search over question embeddings and surface the top 3 prior runs of the same `question_type` as **suggested-related** in the planner prompt (not in the synthesizer — prevents stale evidence from being cited as if fresh).
- **Storage (in-memory only, no pgvector).** Add a process-level singleton `QuestionEmbeddingIndex` (a Python `dict[run_id, np.ndarray]`) populated on `QuestionAsked` and on server startup by replaying questions from the `runs` table and re-embedding them. The bytes column `runs.question_embedding BYTEA` is acceptable as a cache to avoid re-embedding on every restart, but **no vector index, no pgvector, no similarity search in SQL** — similarity is computed in Python over the in-memory dict.
- UI: a "related prior runs" strip on the answer screen, each linkable and forkable.

**Cost.** 1 PSD. The hardest part is making sure prior-run evidence is presented to the planner as *hints*, not as *evidence* (which would break the citation contract). Re-embed-on-startup cost is bounded by the demo corpus size (≤ a few hundred runs).

---

## 4. What we deliberately keep as-is

- **Single-server architecture (RF-05).** No distributed locks, no Redis. The reference architecture talks about scale; for this build that is the wrong axis.
- **Event log as source of truth.** Already aligned with the reference's "inspectable runs" pillar. No change.
- **Plugin seams (`Source`, `StoppingSignal`, `OutputRenderer`).** Already aligned with the reference's modularity expectations.
- **Single LLM provider for planner + synthesizer.** Only the judge migrates (WP-5). The reference does not require provider diversity for all roles.
- **No LangGraph / LangChain.** The reference does not assume them; our custom FSM is more inspectable.

---

## 5. RF changes required if this proposal is ratified

The following RF edits in [requirement-understanding.md](requirement-understanding.md) are the minimum needed for code and docs to stay coherent. **Do not start WP-1 before these are merged.**

| RF | Current text (summary) | Proposed change |
|---|---|---|
| **RF-01·E** | "Honest stop is a first-class terminal outcome." | "Honest stop is not a terminal outcome. The conditions that previously produced it (ambiguity, contradiction, sparsity, out-of-scope type) now drive `AnswerKind` selection." |
| **RF-02** | 7-value `stop_reason` enum. | 4-value enum: `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`. |
| **RF-06** | Types 6/7/8 emit `honest_unanswerable` immediately. | Types 6/7/8 route to `scenario`, `tradeoff`, `ethical_redirect` AnswerKinds respectively; no short-circuit, full pipeline runs. |
| **RF-12** | `final_confidence = min(S, J)`, threshold gates positive terminal. | Unchanged formula, plus per-`AnswerKind` ceiling on `S` (WP-3). Threshold still gates `judge_confirmed`, but failing it now lowers confidence on the answer, not refuses it. |
| **RF-13** | UI surfaces "trust guarantees" including honest-stop screens. | UI surfaces `AnswerKind` badge + per-section confidence + alternatives panel. No rejection screen. |
| **RF-04** | "Honest stop when contradictions cannot be resolved." | "Render contradictions as `AnswerKind=weighted` with candidate answers ranked by support strength." |
| **(new) RF-17** | — | "Every terminal positive run produces an answer with a declared `AnswerKind` and per-kind-bounded confidence." |
| **(new) RF-18** | — | "Saturation signal `C` is computed from embedding novelty and emitted as `SaturationDetected`." |

---

## 6. Sequencing and exit criteria

```
Week 1 (mandatory product reshape):
  WP-1 → WP-2 → WP-3        ← ship: "always answers" guarantee, with calibrated confidence

Week 2 (close reference gaps, independently sequenceable):
  WP-4 (semantic retrieval + real saturation)
  WP-5 (independent verifier)
  WP-6 (cross-run memory)
```

**Exit criteria for the refactor as a whole.**

1. No run in the test corpus terminates without a final `SynthesizedAnswer`, regardless of question type — including the previously-rejected Types 6/7/8.
2. Mean displayed confidence on previously-rejected questions stays **below 0.55** (otherwise WP-3 ceilings are wrong).
3. Golden-trace tests in `tests/fixtures/runs/` still pass after migration, with stop_reason values mapped via a one-shot script.
4. UI: zero "rejection screens" in the screenshots used in the demo.
5. Reviewer-runnable: a single command `pytest -q && npm run test` is green; demo questions covering all six `AnswerKind` values produce visibly different layouts.

---

## 7. Risks and open questions

| Risk | Mitigation | Decision needed from product |
|---|---|---|
| Always answering looks like always confident-bullshitting in the demo. | WP-3 ceilings + UI badge make confidence visible at a glance; demo script includes one `scenario` and one `tradeoff` question to show the templates differ. | Confirm that "no rejection screen" is the desired demo aesthetic. |
| `ethical_redirect` still feels like a refusal to a hostile reviewer. | It is. The product constraint says "alternatives, propose something" — and proposing public/official channels is the most we can ethically offer on personal-private questions. | Confirm `ethical_redirect` is acceptable, or rename it (e.g. `redirect`). |
| Semantic retrieval (WP-4) cold-resume cost (re-embed on crash recovery). | Cap run chunks at 50; embedding model is small (`text-embedding-3-small` or `bge-small-en-v1.5`); batched per `analyze` round. No pgvector — in-memory only, decided at ratification. | None — decided. |
| Cross-provider judge (WP-5) introduces a second API key and a second monthly quota. | Single fallback path keeps the system functional on key absence. | Approve adding `ANTHROPIC_API_KEY` (or equivalent) to env. |
| Cross-run memory (WP-6) risks leaking another user's evidence into a new run's citations. | Prior runs are surfaced to the **planner** only, never to the synthesizer or judge. Hard contract enforced by the prompt and by an `assert` in the call site. | Confirm prior-runs-as-hint, never-as-evidence boundary. |

---

## 8. Decision checkpoint — ratified 2026-05-27

| # | Question | Answer |
|---|---|---|
| 1 | Collapse `stop_reason` to 4 values? | **Yes** |
| 2 | Introduce `AnswerKind` with the six values listed? | **Yes** (all six) |
| 3 | Drop the question-type pre-rejection in RF-06? | **Yes** |
| 4 | Confidence ceilings per `AnswerKind` as in WP-3? | **Yes** (as tabled) |
| 5 | Adopt pgvector for WP-4 and WP-6, with in-memory fallback? | **No** — in-memory only, no pgvector |
| 6 | Add a second LLM provider for the judge? | **Yes** (Anthropic Claude Haiku as default; `JUDGE_PROVIDER` env var) |

**Next actions, in order:**

1. Apply the RF edits in §5 to [requirement-understanding.md](requirement-understanding.md).
2. Update [confidence-calculation.md](confidence-calculation.md) for the per-kind ceiling and the new `C_kind_appropriateness` component.
3. Update [stopping-signal-analysis.md](stopping-signal-analysis.md) to reflect that honest-stop is no longer a terminal class.
4. Update [ai-services.md](../technical-phase/ai-services.md) to add the second judge provider.
5. Execute the six work packages in the order shown in §6 (WP-1 → WP-2 → WP-3 → WP-4 → WP-5 → WP-6).
