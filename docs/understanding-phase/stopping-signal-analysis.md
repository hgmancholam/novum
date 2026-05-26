# Stopping Signal Analysis — RF-01

> Expert evaluation of the six candidate stopping signals for the Novum research agent, scored against eight design criteria, followed by a defended recommendation.

---

## 0. The six candidates

| ID | Signal | One-line description |
|----|--------|----------------------|
| **A** | **Claim coverage** | Decompose the question into sub-claims; stop when every sub-claim has ≥ *N* supporting sources. |
| **B** | **LLM-as-judge sufficiency** | A separate evaluator prompt reads the accumulated evidence and answers "can I answer the original question now, yes/no, and why?". |
| **C** | **Saturation / diminishing returns** | Stop when the last *k* retrievals add no new information (semantic novelty falls below a threshold). |
| **D** | **Source agreement** | Stop when *N* independent sources agree on the answer; do not stop while a real contradiction is unresolved. |
| **E** | **Honest stop** | Stop *and say so* when the question is unanswerable, ambiguous, or contradictions cannot be resolved. |
| **F** | **Budget guardrail** | Hard cap on tokens / wall-clock / tool calls. Used only to prevent runaway, never as the actual decision. |

---

## 1. Scoring matrix

Scale: **★★★** strong / **★★** acceptable / **★** weak / **—** N/A.
For *Cost*, lower is better and is rendered inverted (★★★ = cheap).

| Criterion | A · Claim coverage | B · LLM-as-judge | C · Saturation | D · Source agreement | E · Honest stop | F · Budget |
|---|---|---|---|---|---|---|
| **Correctness on simple Qs** | ★★★ | ★★★ | ★★ | ★★★ | ★★ | ★ |
| **Correctness on ambiguous Qs** | ★ | ★★ | ★ | ★ | ★★★ | ★ |
| **Correctness on unanswerable Qs** | ★ | ★★ | ★★ | ★ | ★★★ | ★★ |
| **Defensibility (auditable why-stop)** | ★★★ | ★★ | ★★ | ★★★ | ★★★ | ★★★ |
| **Detects contradictions** | ★★ | ★★ | — | ★★★ | ★★★ (when wired to D) | — |
| **Survives information bubbles** | ★ | ★★ | ★ | ★ | ★★ | — |
| **Allows honest "no answer"** | ★ | ★★ | ★ | ★ | ★★★ | ★★ |
| **Cost per iteration (lower = better)** | ★★ (extra LLM call to decompose + match) | ★ (full evaluator call each loop) | ★★★ (cheap embeddings only) | ★★ (clustering / NLI) | ★★★ (piggybacks on B) | ★★★ (free) |
| **Scales to long runs** | ★★ | ★ | ★★★ | ★★ | ★★★ | ★★★ |
| **Sensitivity to thresholds** | ★ (needs *N*) | ★★ (needs confidence cut) | ★ (needs *k* and novelty τ) | ★ (needs *N* and "independent") | ★★★ (qualitative) | ★ (arbitrary cap) |
| **Re-attempt friendly (replayable)** | ★★★ (claims are state) | ★★ (judge is deterministic only if seeded) | ★★ (needs novelty history) | ★★★ (source set is state) | ★★★ | ★★★ |
| **Generalizes across Q types** | ★★ (great for factual/comparative, weak for open) | ★★★ | ★★ | ★★ (great for factual, weak for open) | ★★★ | ★★★ |
| **Gaming / collapse risk** | ★ (agent can manufacture trivial claims) | ★ (judge can be sycophantic / agree with itself) | ★★ (agent can re-query to inflate novelty) | ★★ (agent can pick echo-chamber sources) | ★★★ (no metric to game) | ★★★ |

---

## 2. Per-option deep dive

### A · Claim coverage
**What it is.** The agent (or a planner step) decomposes the question into a checklist of atomic sub-claims. The loop ends when each sub-claim has ≥ *N* supporting passages from distinct sources.

**Strengths.**
- Highly **defensible**: the trace literally shows "claim X was supported by sources Y, Z" — auditable line by line.
- Excellent for **factual and comparative** questions ("Compare A vs B on dimensions D1..Dk").
- Maps cleanly to **re-attempt**: claims are first-class persisted state, so a branch can reuse confirmed claims and re-attack only the missing ones.

**Weaknesses.**
- For **open / ambiguous** questions ("What is the future of X?"), claim decomposition itself is the hard part and can be wrong, producing false confidence.
- Gameable: the agent can decompose into trivially-coverable claims that miss the real intent.
- Sensitive to *N* (how many sources per claim) and to what counts as "supporting".
- Says nothing about **contradictions** or **unanswerable** cases on its own.

**Verdict.** Strong **structural** signal, weak as a sole criterion.

---

### B · LLM-as-judge sufficiency
**What it is.** A separate evaluator prompt — ideally a different model or at least a different system prompt — reads (question, evidence so far) and outputs `{ sufficient: bool, confidence: 0..1, missing: [...], reasoning: "..." }`.

**Strengths.**
- The **only** signal that can reason qualitatively about whether the evidence actually answers the user's *intent*, not a proxy for it.
- Generalizes across question types.
- Naturally produces a written justification that can be stored verbatim → defensible.

**Weaknesses.**
- **Expensive**: a full LLM call every loop, on growing context.
- **Sycophancy / self-agreement** risk, especially if the same model also produced the evidence summaries. Mitigation: different model family, adversarial prompt ("argue why this is *not* enough"), or two-judge disagreement.
- **Calibration** of the confidence threshold is fuzzy.
- Non-deterministic → harder to replay exactly unless seeded.

**Verdict.** Necessary for open questions, dangerous as a *sole* gate.

---

### C · Saturation / diminishing returns
**What it is.** Track novelty of retrieved chunks (embedding distance to prior corpus). Stop when novelty over the last *k* steps falls below threshold τ.

**Strengths.**
- **Cheap** (embeddings only, no extra LLM calls).
- Captures a real epistemic property: *more searching is not producing more information*.
- Good **runaway protection** as a secondary signal.

**Weaknesses.**
- Confuses *"I have enough"* with *"I am searching badly"* — a stuck agent issuing repetitive queries will trigger this falsely.
- Vulnerable to **information bubbles**: the same wrong fact repeated across sources looks like saturation.
- Doesn't know what the question *was*; purely retrieval-side.
- Doesn't detect contradiction or unanswerability.

**Verdict.** Useful **secondary** signal, never primary.

---

### D · Source agreement
**What it is.** Cluster the answers/claims extracted from each source. Stop when ≥ *N* *independent* sources converge; do **not** stop while a meaningful disagreement is open — instead route to a contradiction-resolution branch.

**Strengths.**
- Directly attacks the brief's "sources that contradict each other" requirement.
- Highly defensible: "3 of 4 independent sources said X; 1 dissenter explained by Y."
- Makes contradiction a **first-class event**, which is exactly the behavior the interviewers will probe.

**Weaknesses.**
- "Independent" is hard to define operationally (web pages cite each other).
- Echo-chamber failure mode: *N* sources can agree and all be wrong.
- Weak for **open / generative** questions where there is no single fact to vote on.
- Needs careful claim alignment (two sources may say "the same thing" in incompatible language).

**Verdict.** Essential **for factual questions and contradiction handling**, insufficient alone.

---

### E · Honest stop
**What it is.** A first-class outcome: the agent can stop and emit `unanswerable | ambiguous | contradictory_unresolved`, with reasoning, instead of forcing a synthesis.

**Strengths.**
- The most **interview-defensible** behavior in the entire system. Demonstrating an honest stop on one of the three demo questions is probably the single biggest signal of seniority.
- Cannot be gamed — there is no scalar to optimize.
- Replay-friendly: the stop reason is just a labeled terminal state.
- Generalizes trivially across question types.

**Weaknesses.**
- Not a *measurement* — it is an *option* the other signals must explicitly enable. Needs A/B/D to surface the conditions (no coverage achievable, judge unsure, irreconcilable disagreement) that justify the honest stop.
- Risk of overuse: an agent that bails too easily looks lazy.

**Verdict.** Not a competitor to the others — a **required outcome class** that the others must be able to trigger.

---

### F · Budget guardrail
**What it is.** A hard ceiling on tokens, wall-clock, or tool calls. If reached, the run terminates with a labeled `stopped_by_budget` state.

**Strengths.**
- Trivially cheap, trivially defensible, mandatory for any production-grade agent.
- Prevents runaway during a live demo, which matters more than it sounds.

**Weaknesses.**
- Says nothing about epistemic sufficiency.
- If it ever fires *as the actual reason for stopping*, the system has failed the brief — so it must be visibly distinct from a "real" stop.

**Verdict.** **Mandatory safety net**, never a decision criterion.

---

## 3. What no single signal solves

| Failure mode | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Open / generative questions | ✗ | ✓ | ✗ | ✗ | ✓ | — |
| Contradictory sources | ~ | ~ | ✗ | ✓ | ✓ | — |
| Information bubbles (all sources wrong) | ✗ | ~ | ✗ | ✗ | ~ | — |
| Unanswerable questions | ✗ | ~ | ~ | ✗ | ✓ | ~ |
| Cheap to evaluate every loop | ~ | ✗ | ✓ | ~ | ✓ | ✓ |
| Resistant to gaming | ✗ | ✗ | ~ | ~ | ✓ | ✓ |

No single signal covers all rows. **The recommendation must be a composition.**

---

## 4. Recommendation

**Adopt a layered stopping policy with four roles:**

```
                ┌────────────────────────────────────────────┐
                │  Honest Stop (E) — terminal outcome class  │
                └────────────────────────────────────────────┘
                                  ▲
                                  │ triggered by
   ┌──────────────────────────────┼──────────────────────────────┐
   │                              │                              │
┌──────────────┐         ┌──────────────────┐         ┌──────────────────┐
│ Structural   │         │ Qualitative      │         │ Conflict         │
│ A · Claim    │ ──────► │ B · LLM-as-judge │ ◄────── │ D · Source       │
│   coverage   │         │   sufficiency    │         │   agreement      │
└──────────────┘         └──────────────────┘         └──────────────────┘
                                  ▲
                                  │ informs (not gates)
                          ┌────────────────┐
                          │ C · Saturation │
                          └────────────────┘
                                  ▲
                                  │ wraps everything
                          ┌────────────────┐
                          │ F · Budget cap │  (safety net only)
                          └────────────────┘
```

**Concretely:**

1. **A (claim coverage)** is the **primary structural gate**. The agent decomposes the question into sub-claims up front and tracks coverage as evidence arrives. This produces the per-claim audit trail.
2. **D (source agreement)** runs continuously over the evidence supporting each claim. Any *unresolved contradiction* emits a **`block` vote** — the third value of the `StoppingSignal` contract (`stop` | `continue` | `block`). While any signal votes `block`, the aggregator forbids termination even if other signals would vote `stop`; the FSM routes into the dispute-resolution sub-task instead. This is the contradiction-handling requirement (RF-04) made operational.
3. **B (LLM-as-judge)** is the **final qualitative confirmer**, invoked **only when A is satisfied and D reports no open conflicts** (i.e., D is no longer voting `block`). This caps the cost of B (it does not run every loop), avoids using it as the sole gate, and makes B the **only** path to a positive terminal — there is no `coverage_met` bypass. The judge is **edge-triggered** on transitions of A from incomplete to complete (including when a `ClaimUncoverable` event closes the open set), not on every `EvidenceAdded`. To prevent the adversarial prompt from rejecting indefinitely on unfillable gaps, `RunState.judge_rejections` is capped at `max_judge_rejections` (default 3); on overflow, the run terminates as `Stopped(honest_unanswerable, sub_reason=judge_loop_stalled)` — the anti-cycle guard.
4. **C (saturation)** is consulted as a **hint to the judge**, not a gate: when novelty collapses but coverage is incomplete, that is *evidence the question may be unanswerable*, which the judge can use to recommend E.
5. **E (honest stop)** is the **terminal outcome** whenever:
   - the judge (B) declines after exhausting reasonable exploration, **or**
   - D reports a contradiction that cannot be resolved, **or**
   - C indicates saturation with insufficient coverage.
6. **F (budget)** wraps the entire loop and, if it fires, emits a clearly-labeled `stopped_by_budget` terminal state — visibly distinct from a real stop.

### Two classes of signals in the registry

For clarity in the pair session, the five signals split into two operational classes — a distinction the contract itself does not enforce, but which makes the design legible:

- **Epistemic signals** (A, D, B, E) — reason about whether the evidence is sufficient. They participate in the `vote: stop | continue | block` aggregation and *cause* the agent to converge or to honest-stop.
- **Operational signals** (F) — do not reason; they interrupt. F caps wall-clock / token budget regardless of epistemic state. User-cancel and LLM-provider-error transitions (RF-08, RF-11) follow the same *operational* shape — ortogonal interrupts that route to a labeled terminal without engaging the epistemic stack — even though V1 implements them as FSM transitions rather than registry plugins.

The pair session's likely *"add a per-sub-claim timeout"* is therefore an **operational** signal sibling of F; *"add a domain-safety evaluator that blocks on medical advice"* is an **epistemic** signal sibling of E.

### Why this composition wins on every criterion

- **Correctness.** A handles factual/comparative cleanly. B catches what A misses on open questions. D catches contradictions. E covers unanswerable. The weak spots of each are compensated.
- **Defensibility.** Every stop produces: the claim coverage table (A), the contradiction ledger (D), the judge's written verdict (B), and the terminal outcome class (E or F). A reviewer can answer *"why did it stop?"* in one sentence on any run.
- **Robustness.** Contradictions block stopping (not ignored). Bubbles are mitigated because B is asked to *argue against* sufficiency, and saturation-without-coverage routes to honest stop instead of false confidence.
- **Cost.** B — the expensive signal — runs only when A and D are already green. A and C are cheap. F is free.
- **Sensitivity.** Only A and D carry tunable thresholds (*N* per claim, *N* independent sources). Both have intuitive defaults (e.g., N=2) and degrade gracefully.
- **Re-attempt.** Claims, sources, and the contradiction ledger are all serializable state. A branch from step *k* reuses confirmed claims and replays the judge with the new evidence.
- **Generalization.** A+D cover factual, B covers open, E covers ambiguous/unanswerable. Uniform pipeline, no per-question-type code paths.
- **Anti-gaming.** B is asked adversarially ("argue this is *not* enough") and can be a different model than the synthesizer. D requires *independent* sources, not repeated ones. E removes the incentive to fake a confident answer.

### What I would *not* do

- Use **B alone** — too expensive, too sycophantic, not auditable enough.
- Use **A alone** — fails on open questions, blind to contradictions.
- Use **F as the actual decision** — a run that stops because it ran out of budget has failed the brief.
- Run **B every loop** — kills the token budget and adds little over A+D until they are both green.

---

## 5. The one thing I am most worried about

That **B (the judge) silently dominates** the policy in practice — that A and D become rubber stamps and the system collapses into "ask GPT if it's done". Mitigation: in every trace, the *gating* contribution of A and D must be visible (which claims went from uncovered to covered this iteration, which contradictions were resolved), and the judge's verdict must reference them explicitly. If a stop ever happens with the judge as the only justification on the trace, that is a bug.

---

## 6. TL;DR

> **Primary: A (claim coverage) + D (source agreement), gated by B (LLM-as-judge) as final confirmer.
> Terminal outcome class: E (honest stop) — must be reachable from all three.
> Safety net: F (budget). C (saturation) is an input to the judge, not a gate.**

This composition is the one I will defend in the pair session.

---

## 7. Extensions added after methodology review (RF-14 / RF-15)

The six-signal policy above is the core. After an expert-review pass on the method itself, three extensions were folded in to close grietas that A/D/B/E/F together do not address. They do not introduce a new top-level signal — they **harden the existing ones**.

### 7.1 Plan critic + iterative re-plan (RF-14) — strengthens A

**Why.** A's structural score is only as meaningful as the sub-claim decomposition it scores. A planner that emits trivial, overlapping, or off-intent claims produces a high `C_coverage` over the wrong question. The original design relied on B to flag bad plans implicitly, late, and after budget had already been burned.

**Mechanism.**
- A `plan_critic` LLM call runs immediately after `PlanCreated` and emits `PlanCritiqued(approved, issues, reasoning)`. Two attempts max; second failure → `Stopped(honest_ambiguous, sub_reason="plan_unstable")`.
- During search, `PlanRevised(added[], removed[], modified[])` can be appended up to `max_replans` times (default 2) when the judge's `gaps[]` look like missing sub-claims rather than missing evidence, or when an `S_low_J_high` `ConfidenceMismatch` (§7.3) persists.
- A's denominator recomputes against the **current** plan, never against a stale one. Removed claims keep their evidence in the log for audit but stop counting.

**Where it sits in the policy.** A becomes a function of the *current* plan, not a fixed checklist. The voting contract (`stop` | `continue` | `block`) is unchanged.

### 7.2 Disconfirmation pass + source independence (RF-15) — strengthens A and D

**Why.** A and D both have a confirmation bias: A counts how many sources *support* a claim, D measures how many agree. Neither asks "did anyone refute this?". And D's "independent sources" requirement was asserted on `source.kind` (web / wikipedia / arxiv), not verified on actual domain identity — five blogs on `medium.com` were one source epistemically, three "kinds" structurally.

**Mechanism.**
- **Disconfirmation pass:** when a claim reaches `C_coverage(c) ≥ N_min`, the searcher issues **one** adversarial query (`query_intent="refuting"`) before the claim is forwarded to the judge. Returned chunks are stored with `polarity ∈ {supporting, refuting, limiting}` and clustered into their own agreement bucket. Refuting evidence **lowers `C_agreement` correctly**, instead of being averaged away.
- **Source independence:** `C_diversity` becomes `0.5 · diversity_kinds + 0.5 · C_independence`, where `C_independence = |distinct_etld+1_domains| / |evidence_chunks|`. Coordinated misinformation across five identical hosts now scores as low diversity, not high.

**Where it sits in the policy.** A's "covered" threshold is unchanged but is now followed by a *mandatory disconfirmation step* before A votes `stop`. D's agreement calculation respects polarity. F (budget) is the only thing that caps this — the disconfirmation pass costs one extra retrieval per covered claim, amortized once per claim's lifetime.

### 7.3 Confidence-mismatch trust-flag (RF-15) — narrates B's relationship to A+D

**Why.** The original `final_confidence = min(S, J)` is correct but **loses information**. Both `S=0.9 / J=0.3` and `S=0.4 / J=0.95` produce "keep searching" — yet they are epistemically opposite cases:
- `S_high_J_low` → evidence looks structurally complete, judge sees something subtle → continue is the right move.
- `S_low_J_high` → judge is confident on thin evidence → **alarm**: either the structural scorer underestimates, or the judge is overconfident (R6).

**Mechanism.**
- After every `JudgeRuled`, compute `|S − J|`. If `> 0.3`, emit `ConfidenceMismatch(S, J, delta, regime)`.
- Non-blocking: the event does not change the stop decision. It is surfaced in the UI's `TrustSummary` as a yellow trust-flag.
- `S_low_J_high` mismatches are also a **trigger for `PlanRevised`** (§7.1): persistent judge overconfidence on thin coverage suggests the wrong claims are being scored.

**Where it sits in the policy.** Not a vote, not a gate — a **trace artifact** that makes the conservative `min()` legible. It is the closest V1 gets to peer-review-style structured disagreement without a second judge.

### Summary

| RF | What it changes | Signal hardened |
|---|---|---|
| 14 | Plan critic + `PlanRevised` | A — coverage is now over the *right* claims |
| 15 (1.1) | Disconfirmation pass, `polarity` on evidence | A + D — false confirmation cannot inflate the score |
| 15 (1.3) | `C_independence` inside `C_diversity` | D — domain echo chambers penalised |
| 15 (1.2) | `ConfidenceMismatch` trust-flag | B — disagreement with A+D becomes legible |
| 16 | 5-question eval set, `make eval` | All — weights and behavior are validated, not just asserted |

None of these introduces a new vote in the `StoppingSignal` contract. They make the existing votes harder to game.

---

## 8. Methodological lineage (pointer)

The layered policy in this file is not an invention. It is an **executable adaptation of Analysis of Competing Hypotheses (Heuer, 1999) + GRADE (BMJ, 2004–)**, with Popper's falsificationism as the philosophical anchor for RF-15 and Toulmin's argument model as the atomic data shape of `EvidenceAdded`.

The full rationale — selection criteria, scoring matrix against eleven candidate methodologies, complementarity argument, and what survives from the rejected candidates — lives in a dedicated document: [research-method-selection.md](research-method-selection.md). Every doc that needs to defend an epistemic choice cites that file as the single source of truth.
