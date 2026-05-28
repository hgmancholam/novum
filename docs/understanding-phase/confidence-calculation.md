# Confidence Score Calculation — Novum

> The exact method by which Novum computes the `final_confidence` value that gates `judge_confirmed` against the user-set `confidence_threshold` (RF-12).

## Amendment 2026-05-28 — Per-evidence-row authority-tier multiplier (BRD-23 WP-3)

Ratified alongside BRD-23 §4.7 ([BRD-23](../implementation-phase/brds/BRD-23-research-quality-improvements.md)) and required to ship in the same PR (BRD §15.3 Q6 — hard gate).

**Change.** Every evidence row carries an `authority_tier ∈ {primary_authoritative, reputable_secondary, general, low_signal}` (classified statically from the source host, see [`backend/app/agent/sources_authority/tiers.py`](../../backend/app/agent/sources_authority/tiers.py)). When `S` is composed, the row's contribution to **`C_coverage` and `C_diversity` (only)** is multiplied by the BRD §4.7 table:

| `AuthorityTier`         | Multiplier |
|---|---:|
| `PRIMARY_AUTHORITATIVE` | **1.05** |
| `REPUTABLE_SECONDARY`   | **1.00** |
| `GENERAL`               | **0.90** |
| `LOW_SIGNAL`            | **0.50** |

After multiplication each component is clamped to `[0.0, 1.0]` (so a single `.gov` source cannot push `C_coverage` above 1.0). Missing `authority_tier` (e.g. pre-BRD-23 traces being replayed) falls back to `GENERAL` — replay-safe.

**Scope (intentional restriction).** The multiplier touches `C_coverage` and `C_diversity` only. `C_agreement` and `C_no_conflict` are **untouched** because authority is about *who* speaks, not *whether speakers agree* nor *whether anyone contradicts*. This keeps the WP-3 multiplier orthogonal to BRD-22's expert-credibility boost (which acts on `C_agreement`).

**Asymmetric design (`1.05` vs `0.50`).** Authority is asymmetric in real life: knowing a source is a primary authority is weak positive evidence (the source can still be wrong, hence only `+5 %`), but knowing a source is content-mill / SEO-farm is strong negative evidence (the source is structurally incentivised against accuracy, hence the steep `−50 %`). The `[0, 1]` clamp absorbs over-saturation when many primary sources stack on one claim.

**RF-12 invariant preserved.** The change is internal to `S`; `final_confidence = min(S_effective, J)` is unchanged. The judge score `J` is not affected by tier. The mismatch flag (§3.6) still triggers on `|S_effective − J| > 0.3` regardless of how `S` was composed.

**Replay tolerance.** `EvidenceAddedEvent.authority_tier` is optional with default `None`. The fold layer (`backend/app/agent/runner.py::_fold_events`) tolerates absence and missing values; runs predating BRD-23 replay byte-identically except that all evidence rows inherit `GENERAL` (multiplier `0.90`) — the same value the legacy formula assumed implicitly when it weighted every row by `1.0` minus the diversity penalty.

See BRD-23 §4.7 for the full domain table and §15.3 Q6 for the doc-gate rationale.

---

## Amendment 2026-05-27 — `AnswerKind` ceiling + `C_kind_appropriateness`

Ratified on 2026-05-27 alongside the "always answer" refactor ([research-method-refactor-proposal.md](research-method-refactor-proposal.md)). Two changes to the formula in this document; everything else (the four `C_*` components, the disconfirmation/independence extensions, the mismatch flag) stays as written.

**Change 1 — per-`AnswerKind` ceiling on `S`.** Before entering the `min(S, J)`, the structural score is multiplied by a `kind_ceiling` factor that reflects the epistemic ceiling of the chosen answer shape:

```
S_effective = S_raw · kind_ceiling[AnswerKind]
final_confidence = min(S_effective, J)
```

| AnswerKind | `kind_ceiling` | Rationale |
|---|---:|---|
| `direct`            | 1.00 | High-coverage, agreement, no contradictions — the historical happy path. |
| `weighted`          | 0.80 | Multiple supported answers; even with great structure, the answer is plural by nature. |
| `scenario`          | 0.55 | Predictive / future-state; no source can fact-check tomorrow. |
| `tradeoff`          | 0.50 | Subjective / opinion; the "right answer" is a function of the reader's priorities. |
| `best_effort`       | 0.45 | Ambiguity or sparse coverage; we are committing to a primary interpretation. |
| `ethical_redirect`  | n/a  | No claim is being made; the response is a refusal + alternatives. Confidence is not displayed. |

The trace's `JudgeRuled.payload.structural` block surfaces **both** `S_raw` and `S_effective` plus the `kind_ceiling` and the chosen `AnswerKind`, so the rule is auditable.

**Change 2 — new component `C_kind_appropriateness` (weight 0.10).** Re-balances the four structural components so the judge can penalize a wrong-shape answer (e.g., `direct` chosen on a 3-way contradiction):

| Component | Old weight | New weight |
|---|---:|---:|
| `C_coverage`            | 0.35 | 0.35 |
| `C_agreement`           | 0.30 | 0.30 |
| `C_diversity`           | 0.20 | 0.20 |
| `C_no_conflict`         | 0.15 | **0.05** |
| `C_kind_appropriateness`| —    | **0.10** |

`C_no_conflict` drops from 0.15 → 0.05 because its job (residual-contradiction penalty) is largely subsumed by `C_kind_appropriateness`: a residual contradiction now manifests as a `weighted` or `best_effort` kind with its own ceiling, not as a deduction inside `C_no_conflict`. It remains as a defense-in-depth term.

`C_kind_appropriateness` is **judge-reported** in `[0, 1]`: the judge prompt now asks *"does the chosen `AnswerKind` match the actual evidence shape?"* and returns a score plus a one-line reason. Computation is therefore **free of new infra** — it is one extra field in the existing judge response model.

**Read-the-doc rule:** the formula stated in §2 (`0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.15·C_no_conflict`) is **superseded** by the weights in the table above. References to `final_confidence = min(S, J)` elsewhere in the doc should be read as `min(S_effective, J)` where `S_effective = S_raw · kind_ceiling[AnswerKind]`.

---

This document is the **authoritative reference** for how confidence is calculated, what each input means operationally, how it is persisted in the trace, and how it can be defended in the pair session.

> **Methodological lineage.** The structural score `S` is a computable analogue of **GRADE** (BMJ, 2004–) — the four `C_*` components map to GRADE's independent quality dimensions (risk of bias / inconsistency / indirectness / imprecision / publication bias), and `final_confidence = min(S, J)` mirrors GRADE's separation of *certainty rating* from the recommendation itself. The disconfirmation pass that feeds `C_agreement` (RF-15) operationalises **Heuer's ACH** rule that disconfirming evidence must be sought, not just accepted when stumbled upon. Full rationale and rejected alternatives in [research-method-selection.md](research-method-selection.md).

---

## 1. Goal and constraints

The confidence score must be:

1. **Principled, not vibes.** Every input is a measurable quantity from the run state, not a free-text impression.
2. **Auditable.** Anyone opening the run can recompute the number from the trace.
3. **Cheap.** Computable from existing state with at most **one extra LLM output field** — no additional model calls per evaluation.
4. **Robust to gaming.** Cannot be inflated by a sycophantic judge alone or by a structurally trivial coverage alone.
5. **Inspectable.** The breakdown is part of the `JudgeRuled` event payload, visible in the trace UI and in the diff viewer.

---

## 2. The formula at a glance

```
final_confidence = min(S, J)

where:

S = 0.35·C_coverage
  + 0.30·C_agreement
  + 0.20·C_diversity
  + 0.15·C_no_conflict

J = judge.confidence       (∈ [0, 1], reported by the LLM-as-judge)

S, J, final_confidence ∈ [0, 1]
```

- **S** = *Structural confidence* — deterministic, computed from run state.
- **J** = *Judge confidence* — qualitative, reported by the adversarially-prompted LLM judge.
- **`min(S, J)`** = conservative aggregation; both gates must agree.

The run terminates as `judge_confirmed` **iff**:

```
judge.sufficient == true  AND  final_confidence >= confidence_threshold
```

If `sufficient` is true but `final_confidence < confidence_threshold`, the agent **keeps searching** (raises the bar; does not silence the judge).

If the budget cap (F) fires before the threshold is ever crossed, the run terminates as:

```
Stopped(honest_unanswerable, {
  sub_reason: "confidence_below_threshold",
  best_confidence: max final_confidence observed,
  threshold: <user's threshold>
})
```

---

## 3. Each input, in operational detail

All four structural components are in `[0, 1]`. All are computed from events already in the log — no extra retrievals, no extra LLM calls.

### 3.1 `C_coverage` — Claim coverage ratio · weight 0.35

**Definition.**

$$
C_{\text{coverage}} = \frac{|\{ c \in \text{Claims} : |\text{evidence}(c)| \geq N_{\min}\}|}{|\text{Claims}|}
$$

- `Claims` = the set of sub-claims emitted by `PlanCreated` (and any added later by `PlanRevised`, future event).
- `evidence(c)` = the set of evidence chunks attached to claim `c` via `EvidenceAdded` events.
- `N_min` = 2 by default (RF-01·A): a claim is "covered" if it has at least 2 supporting evidence chunks from distinct sources.

**Edge cases.**

- If `Claims` is empty (degenerate plan), `C_coverage = 0`. The run cannot stop on judge confirmation with no claims.
- A claim explicitly marked `unknowable` by the planner does not count toward the denominator.
- A claim for which a `ClaimUncoverable` event has been emitted (all source strategies exhausted, RF-04) is also **excluded from the denominator**. The rationale: forcing such a claim into the denominator guarantees `C_coverage < 1` forever and pushes every run with a flaky source into `stopped_by_budget` or `confidence_below_threshold`, which is dishonest — the agent *knew* the claim was uncoverable but kept the score artificially low. Excluding it lets the judge rule on the remaining (covered) claims and produce an answer of the form *"X is true; Y could not be verified — see `ClaimUncoverable` event"*. The final synthesizer is required to mention uncoverable claims explicitly in its output.

**Why this weight (0.35).** Coverage is the most direct operationalization of RF-01·A. It is the strongest signal that the agent actually addressed the question, not a tangent.

---

### 3.2 `C_agreement` — Polarity-aware source agreement per claim · weight 0.30

**Definition.**

For each covered claim `c`, compute its **agreement score** `a(c) ∈ [0, 1]`:

1. Cluster the evidence chunks supporting `c` by their **extracted assertion** (the short factual statement each chunk makes about `c`). Clustering is semantic, done by the planner/extractor at evidence-ingestion time and stored in the `EvidenceAdded.payload.assertion_cluster_id`.
2. **Polarity is part of the cluster key.** Refuting (`polarity="refuting"`) and limiting (`polarity="limiting"`) chunks form their own clusters even when their underlying assertion is semantically related to the supporting one. This is the RF-15 disconfirmation contract: a found refutation must lower agreement, never be averaged into a confirming bucket.
3. Let `n_total(c)` = total evidence chunks for `c` (across all polarities). Let `n_majority(c)` = size of the largest cluster.
4. `a(c) = n_majority(c) / n_total(c)`.

Then:

$$
C_{\text{agreement}} = \frac{1}{|\text{CoveredClaims}|} \sum_{c \in \text{CoveredClaims}} a(c)
$$

**Edge cases.**

- Claim with 0 evidence → not in `CoveredClaims`, ignored.
- Claim with all chunks in one cluster → `a(c) = 1` (perfect agreement).
- Claim with 2 chunks in different clusters → `a(c) = 0.5` (a tie; this is a real contradiction signal).
- Claim where the disconfirmation pass (RF-15) returns no refuting evidence → only the supporting cluster exists; `a(c)` is unaffected. The disconfirmation pass only changes `a(c)` when it *succeeds at finding* counter-evidence — i.e., exactly when agreement *should* drop.

**Why this weight (0.30).** Operationalizes RF-01·D. Penalizes contradictions that the dispute-resolution loop (RF-04) was unable to resolve, and — with the polarity extension — penalizes confirmation that the agent failed to challenge.

---

### 3.3 `C_diversity` — Source diversity (kind + domain independence) · weight 0.20

**Definition.** `C_diversity` is a 50/50 blend of two sub-scores:

$$
C_{\text{diversity}} = 0.5 \cdot C_{\text{kinds}} + 0.5 \cdot C_{\text{independence}}
$$

**`C_kinds` — diversity of registered source kinds.**

$$
C_{\text{kinds}} = \min\left( 1, \; \frac{|\text{DistinctSourceKinds}|}{K_{\text{target}}} \right)
$$

- `DistinctSourceKinds` = the set of distinct `source.metadata.kind` values appearing in the run's evidence (e.g., `web_search`, `wikipedia`, `arxiv`).
- `K_target` = number of registered source kinds in the active source registry. With the V1 minimum (web + Wikipedia), `K_target = 2`.

**`C_independence` — domain-level independence (RF-15).**

$$
C_{\text{independence}} = \frac{|\text{DistinctDomains}|}{|\text{EvidenceChunks}|}, \;\; \text{clamped to } [0, 1]
$$

- `DistinctDomains` = the set of distinct **eTLD+1** values across the URLs of every evidence chunk (e.g., `wikipedia.org`, `medium.com`, `arxiv.org` — `en.wikipedia.org` and `de.wikipedia.org` both collapse to `wikipedia.org`).
- Operationalized with `tldextract` (or equivalent eTLD list); the host is normalised before counting.

**Why both, and not just one.** `C_kinds` answers *"did I look in different libraries?"* `C_independence` answers *"did I actually hear different voices?"* Five Medium blog posts pass `C_kinds` trivially (1 kind out of 2 = 0.5) but score `C_independence = 0.2` (one domain over five chunks) — a 0.35 final diversity instead of 0.5. Coordinated misinformation is now visibly penalised.

**Edge cases.**

- All evidence from a single domain on a single kind → `C_kinds = 0.5`, `C_independence = 1/n` → final pulled toward zero as evidence grows.
- Evidence spans all kinds and all chunks come from distinct domains → `C_diversity = 1`.
- Wikipedia is over-weighted (high authority but single domain) → still capped by `C_independence`; the formula does not let one trusted source carry the whole diversity score on its own.

**Why the overall weight stays 0.20.** The internal composition of `C_diversity` changed; its weight in the top-level formula did not. The overall confidence formula remains `0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.15·C_no_conflict` so RF-15 does not invalidate any prior calibration intuition.

**Why this weight (0.20).** Mitigates R3 (echo-chamber failure) from the risk register. A high-coverage, high-agreement answer drawn from one domain family is now visibly weaker than the same numbers spread across independent hosts.

---

### 3.4 `C_no_conflict` — Unresolved-contradiction penalty · weight 0.15

**Definition.**

$$
C_{\text{no\_conflict}} = 1 - \frac{|\text{UnresolvedContradictions}|}{|\text{Claims}|}
$$

- `UnresolvedContradictions` = the set of `ContradictionDetected` events for which **no** subsequent `ContradictionResolved` event exists (or where the dispute-resolution loop exhausted its 2-attempt cap per RF-04).
- Bounded at `[0, 1]`; if for any reason the count exceeds the number of claims, clamp to 0.

**Edge cases.**

- No contradictions at all → `C_no_conflict = 1`.
- Every claim has an unresolved contradiction → `C_no_conflict = 0` and the run should not be hitting the judge anyway; it should be heading to `honest_contradiction`. This component exists as a defense-in-depth signal, not a primary one.

**Why this weight (0.15).** The lowest weight because the *categorical* contradiction handling already lives elsewhere (the dispute-resolution loop and `honest_contradiction` outcome). This term ensures that *residual* contradiction always pulls the score down, even if the agent decides to proceed.

---

### 3.5 `J` — Judge self-reported confidence

**Definition.** A number in `[0, 1]` emitted by the LLM-as-judge in its structured response:

```json
{
  "sufficient": true,
  "confidence": 0.65,
  "reasoning": "..."
}
```

**Prompting discipline (mandatory).** To mitigate R6 (judge sycophancy), the judge is invoked with an **adversarial system prompt**:

> *"Argue why this evidence is NOT sufficient to answer the question. List every gap, every weak inference, every source you would not bet on. Only after you have stated the strongest case against, give your final `sufficient` decision and your `confidence` ∈ [0, 1]."*

This forces the judge to populate `reasoning` with skeptical content before the confidence number, which empirically reduces overconfidence and gives the trace a falsifiable rationale.

**Provider separation (planned).** Whenever multiple LLM providers are available, the judge runs on a **different model family** than the synthesizer. This breaks self-reinforcement at the model level. Documented as a stack decision; default-on whenever feasible.

---

### 3.6 `ConfidenceMismatch` — the |S − J| trust-flag (RF-15)

**Why this exists.** `final_confidence = min(S, J)` is conservative but **information-lossy**. Both `S=0.9 / J=0.3` and `S=0.4 / J=0.95` produce "keep searching" — but they are epistemically opposite cases. The first is the system working as designed; the second is a red flag.

**Definition.** After every `JudgeRuled` event the engine computes `delta = |S − J|`. If `delta > 0.3` (default) it appends a new event:

```json
{
  "event": "ConfidenceMismatch",
  "payload": {
    "S": 0.85,
    "J": 0.40,
    "delta": 0.45,
    "regime": "S_high_J_low",
    "interpretation": "structural_evidence_judge_skeptical",
    "blocking": false
  }
}
```

**Two regimes, two meanings.**

| Regime | What it means | What the system does |
|---|---|---|
| `S_high_J_low` (S > J + 0.3) | Structural evidence looks complete; judge sees something subtle the scorer cannot measure. | Continue searching is the right move (already happening via `min`). UI surfaces a neutral note: *"the evidence looks complete but the judge is skeptical."* |
| `S_low_J_high` (J > S + 0.3) | Judge is confident on thin evidence — either sycophancy or the structural scorer is under-counting. | **Alarm.** UI shows a yellow trust-flag inside `TrustSummary`. If this regime persists across **two consecutive** `JudgeRuled` events, it becomes a trigger for `PlanRevised` (RF-14): the wrong claims are being scored. |

**Non-blocking by design.** `ConfidenceMismatch` does not change `final_confidence`, does not vote `stop` / `continue` / `block` in the signal aggregator, and does not delay the run. It is a **trace artifact**: legible disagreement made visible. The conservative `min(S, J)` keeps doing its job; the mismatch event tells the user (and the diff viewer) *what disagreement the `min` was hiding*.

**Threshold (0.3) rationale.** Smaller deltas live within the natural noise of an LLM-reported confidence. 0.3 is the smallest gap at which the two scorers "disagree" in a way a reviewer would also see as disagreement. Configurable in `RunState.confidence_mismatch_threshold`; calibration in V2 (see §6).

---

## 4. Why `min(S, J)` and not a weighted average

The two natural aggregations are:

| Aggregation | Behavior | Failure mode |
|---|---|---|
| `0.6·S + 0.4·J` (weighted avg) | Smooth, forgiving. | A sycophantic high `J` can carry a weak `S` across the threshold. Coverage of 0.5 and judge of 0.9 → 0.66. |
| **`min(S, J)`** | **Conservative; both must be high.** | Slightly lower scores on average; demands real evidence quality AND real LLM agreement. |

**Choice: `min(S, J)`.** The brief explicitly values *"knowing when to stop"*. A score that can be inflated by either side defeats the point. `min` is the cheapest way to express the policy *"I do not trust either signal alone."*

This is also a clean one-sentence defense in the pair session:

> *"I do not trust the fórmula by itself and I do not trust the LLM by itself. Both must agree."*

---

## 5. Persistence in the trace

Every `JudgeRuled` event carries the **full breakdown** in its payload — not just the final number:

```json
{
  "event": "JudgeRuled",
  "id": "evt_42",
  "run_id": "run_a1b2",
  "step_index": 8,
  "timestamp": "2026-05-25T14:32:11Z",
  "payload": {
    "structural": {
      "C_coverage":    0.92,
      "C_agreement":   0.78,
      "C_diversity": {
        "kinds":        1.00,
        "independence": 0.80,
        "value":        0.90
      },
      "C_no_conflict": 1.00,
      "S":             0.860
    },
    "judge": {
      "confidence":    0.65,
      "sufficient":    true,
      "reasoning":     "Skeptical pass: the 2026 framework comparison relies on..."
    },
    "final_confidence": 0.65,
    "threshold":        0.60,
    "decision":         "judge_confirmed",
    "mismatch": {
      "delta":  0.21,
      "regime": null
    }
  }
}
```

The `C_diversity` payload now breaks out the `kinds` and `independence` sub-scores so the diff viewer (RF-02 Level 3) can attribute changes to either component. The `mismatch` sub-object records the |S − J| delta on every judge ruling; a separate `ConfidenceMismatch` event is **only** emitted when `delta > threshold` (see §3.6).

This means:

- The trace UI shows the breakdown on hover/click of any `JudgeRuled` event.
- The diff viewer (RF-02 Level 3) can highlight *which component changed* between a parent run and its fork — *"the fork stopped earlier because `C_diversity` rose from 0.5 to 1.0 after adding arXiv as a source."*
- Anyone can recompute `S` independently from the other events in the log and verify the number.

---

## 6. Calibration plan

The weights `(0.35, 0.30, 0.20, 0.15)` are **intuitive defaults**, not empirically calibrated. This is acknowledged debt, not a hidden assumption.

**V1 calibration — minimal eval set (RF-16):** five hand-labeled questions covering the five supported types (factual, comparative, definitional, SotA, causal), stored in `backend/tests/fixtures/eval/v1_seed.yaml`. Each fixture declares:

```yaml
- id: q01_factual
  question: "When was PostgreSQL first released?"
  question_type: factual
  expected_stop_reason: judge_confirmed
  expected_min_confidence: 0.7
  notes: "Should converge on 1996 with Wikipedia + web agreeing."
```

A `make eval` target runs the agent against the fixture set, dumps `JudgeRuled.payload` and `Stopped.payload` into `eval-runs/<timestamp>.csv`, and prints a delta report:

- mismatch in `stop_reason` → hard fail;
- `final_confidence` below the expected floor → soft fail (flagged but non-blocking);
- weight pathology check: any single `C_*` component above 0.95 or below 0.1 on every question → warning that the weight may be doing no work.

V1's job is **not** to optimize the weights — it is to **prove they are not pathological** on a non-trivial set and to make the calibration debt empirical instead of rhetorical. The CSV is the artifact that converts *"these weights are my intuition"* into *"these weights survived five labeled cases on the day of the demo."*

**V2 calibration (planned, paired with KPI #1 from section 6-bis of the requirements doc):**

1. Grow the eval set to ~50 questions across all types and adversarial cases (ambiguous, unanswerable, contradictory).
2. For each question, run the agent and record `(S, J, final_confidence, terminal_outcome, mismatch_events[])`.
3. Optimize the weights to **maximize the appropriate-honest-stop rate** (KPI #1) while keeping a constraint on false-confident answers and on `S_low_J_high` mismatch rate.
4. Document the new weights and the eval set version in the run metadata so any production run is auditable to a specific calibration generation.

This makes the formula a **living artifact**, not a magic number set on day one.

---

## 7. What this method does *not* do (and why)

- **No token-level log-prob inspection.** Couples the solution to a specific provider and to short factual outputs; the answer is synthesized prose where logprobs are not informative.
- **No self-consistency sampling** (judge called N times, agreement measured). Triples the cost of the most expensive step in the loop for a marginal calibration win. Listed as a V2+ option if the V1 calibration is unsatisfactory.
- **No Bayesian source-as-evidence update.** Theoretically attractive, operationally heavy on unstructured text, and the gain over the structural formula is unclear at this scope.
- **No domain-specific weighting in V1.** A medical question and a vendor-comparison question use the same weights. V2 may introduce per-question-type calibration as part of the domain evaluator packs (V3 roadmap).

---

## 8. Failure modes and mitigations

| Failure mode | Why it can happen | Mitigation in V1 |
|---|---|---|
| **Inflated `J`** (judge agrees with itself) | Same-provider judge + synthesizer | Adversarial prompt; provider separation when available; `min(S, J)` caps the damage; **`ConfidenceMismatch` event surfaces `S_low_J_high` as a yellow trust-flag (RF-15)** |
| **Inflated `C_coverage`** (planner emits trivial sub-claims) | Planner gaming the structural signal | **`plan_critic` LLM call after `PlanCreated` rejects trivial/overlapping plans (RF-14)**; one re-plan attempt allowed; second failure → `Stopped(honest_ambiguous, sub_reason=plan_unstable)`. The judge is also asked to assess sufficiency *of the original question*, not the sub-claim list. |
| **Inflated `C_agreement` from confirmation bias** | Agent searches only for evidence *for* each claim | **Mandatory disconfirmation pass (RF-15) before A votes `stop`**: one adversarial query per covered claim with `query_intent="refuting"`. Refuting evidence forms its own cluster, lowering `a(c)` correctly. |
| **Inflated `C_diversity` from echo-chamber domains** | Multiple sources of the same `kind` but the same upstream | **`C_independence` (eTLD+1 domain count) blended 50/50 into `C_diversity` (RF-15)**: five Medium posts no longer score as diverse. |
| **Bogus `C_no_conflict`** (real conflict missed by clustering) | Imperfect assertion clustering | The dispute-resolution loop (RF-04) has its own retries; if it fails to detect, the structural score may be optimistic — calibration in V2 addresses this |
| **Judge rejection loop** (judge keeps returning `sufficient=false` with unfillable `gaps[]`) | Adversarial prompt cannot be satisfied; sources cannot produce evidence for the gap | `RunState.judge_rejections` counter capped at `max_judge_rejections` (default 3). On overflow, run terminates as `Stopped(honest_unanswerable, sub_reason=judge_loop_stalled, last_gaps=[…])` instead of burning the rest of the budget. Same stop_reason as `confidence_below_threshold`, different sub_reason. |
| **Stale plan** (plan was right at start, wrong after new evidence) | Initial decomposition cannot anticipate the recovered evidence | **`PlanRevised` (RF-14)** can append up to `max_replans=2` revisions. Triggered by judge `gaps[]` that look like missing sub-claims, or by persistent `S_low_J_high` mismatch. Denominator of `C_coverage` recomputes against the current plan. |
| **Threshold gaming by user** (set threshold to 0.0 to force any answer) | User intentionally lowers rigor | Allowed by design; the threshold is *user-set rigor*, not a safety check. The trust contract (RF-quater) is explicit. |

---

## 9. One-paragraph defense for the pair session

> *"Confidence in Novum is `min(S, J)`. `S` is a deterministic weighted sum of four measurable signals — claim coverage, source agreement, source diversity, residual contradiction — all computable from the event log and visible in every `JudgeRuled` event. `J` is the LLM judge's self-reported confidence, produced after an adversarial 'argue why this is not enough' pass. I take the `min` because I refuse to let either signal carry the decision alone: the formula could be gamed by a clever planner, and the LLM could be sycophantic. The user sets the threshold; if `min(S, J)` never crosses it within the budget, the run terminates honestly with `confidence_below_threshold` and the user can fork with a lower threshold or different context. The default weights are intuitive — coverage 0.35, agreement 0.30, diversity 0.20, residual-conflict 0.15 — and the calibration plan is in V2 paired with the KPI eval set."*
