# Research Method Selection — Novum

> Why Novum's research method is an **executable adaptation of Analysis of Competing Hypotheses (Heuer, 1999) + GRADE (BMJ, 2004–)**, and not any of the other candidate methodologies considered.

This document is the **single source of truth** for the methodological lineage of the system. Every other doc (RFs, stopping-signal analysis, confidence calculation, design doc, architecture) cites this file when justifying the *epistemic* choices behind Novum.

---

## 1. The question

If a panel reviewer asks *"why did you choose this research method and not another one?"*, the answer must be defensible in two minutes, anchored on published methodology, and free of hand-waving. This file is that answer.

The method under defence:

> Decompose the question into atomic sub-claims → search for supporting evidence → **actively search for refuting evidence** → score each claim along independent quality dimensions → emit a verdict with a confidence rating **separated from the answer**, or stop honestly when the evidence does not support a verdict.

---

## 2. Selection criteria

Six criteria were fixed **before** evaluating any candidate, to prevent reverse-engineering the rationale from a pre-chosen method:

| # | Criterion | Why it matters for Novum |
|---|---|---|
| **C1** | **Operationalisable as deterministic code** | Must compile into a finite-state machine, not stay in philosophy. Anything that requires *"analyst judgment"* as a primitive is disqualified. |
| **C2** | **Designed for a fallible, biased reasoner** | LLM sycophancy = the analyst's confirmation bias under another name. The method must assume the reasoner is *not* impartial. |
| **C3** | **Produces an auditable artifact separate from the verdict** | RF-02 requires an append-only event log. The method must yield a trail anyone can recompute the verdict from. |
| **C4** | **"Cannot conclude" is a legitimate output, not a failure** | RF-01·E and RF-13 require honest non-answer as a first-class terminal. Methods that treat refusal as an error are disqualified. |
| **C5** | **Validated empirically in high-stakes settings for years** | In a 30-minute demo there is no time to defend a method invented yesterday. Track record outranks novelty. |
| **C6** | **Portable across domains** | Medical, legal, technical, opinion, history — the method cannot be tied to one corpus or jurisdiction. |

A passing methodology must score **★★★** (strong) or **★★** (acceptable) on every criterion. Any **★** (weak) on a single criterion is disqualifying.

---

## 3. Candidates considered

Eleven candidates were evaluated, drawn from four traditions:

| Tradition | Candidate | One-line |
|---|---|---|
| Intelligence analysis | **Analysis of Competing Hypotheses (ACH)** — Heuer, CIA, 1999 | Matrix of evidence × hypotheses, weights disconfirming evidence more. |
| Evidence-based medicine | **GRADE** — BMJ Working Group, 2004– | Multi-dimensional certainty grading separated from the recommendation. |
| Argumentation theory | **Toulmin model** — *The Uses of Argument*, 1958 | Atom of one argument: claim + grounds + warrant + backing + rebuttal + qualifier. |
| Philosophy of science | **Falsificationism / Critical Rationalism** — Popper, 1934 | A claim is corroborated only after surviving genuine refutation attempts. |
| Probability theory | **Bayesian confirmation theory** — Carnap, Jeffrey, 20th c. | Posterior probability of hypothesis given evidence. |
| Philosophy of science | **Classical scientific method** | Hypothesis → prediction → experiment → conclusion. |
| Evidence synthesis | **PRISMA / systematic review** — 2009, 2020 | Multi-week protocol-driven exhaustive review with dual reviewers. |
| Legal reasoning | **IRAC** | Issue → Rule → Application → Conclusion. |
| Continental philosophy | **Hegelian dialectic** | Thesis → antithesis → synthesis. |
| ML / NLP | **SAFE, FActScore, Reflexion, Self-RAG, RARR** | Implementation techniques for fact verification or self-critique loops. |

---

## 4. Scoring matrix

★★★ strong · ★★ acceptable · ★ weak (disqualifying on any single row) · — N/A.

| | C1 op. | C2 bias-aware | C3 audit | C4 no-conclusion | C5 track record | C6 portable | **Process** | **Measurement** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **ACH** (Heuer 1999) | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ (25 yr · CIA / NATO / MI6 / ICIJ) | ★★★ | **★★★** | ★ |
| **GRADE** (BMJ 2004) | ★★★ | ★★★ | ★★★ | ★★★ (*Very Low* tier) | ★★★ (20 yr · Cochrane / WHO / NICE) | ★★★ | ★ | **★★★** |
| Toulmin (1958) | ★★★ (per atom) | ★★ | ★★★ | ★ (no protocol for refusal) | ★★★ | ★★★ | ★ (no aggregation) | ★ |
| Popper / falsificationism | ★ (principle, not procedure) | ★★★ | ★★ | ★★★ | ★★★ | ★★★ | ★★ (only the *seek refutation* step) | — |
| Bayesian confirmation | ★★ (math is clear, priors are not) | ★★ | ★ (imagined priors are not auditable) | ★★ | ★★★ | ★★★ | — | ★★ |
| Classical scientific method | ★ (designed to *generate*, not retrieve) | ★★ | ★★ | ★★ | ★★★ | ★★★ | ★ | ★ |
| PRISMA / systematic review | ★ (multi-week cadence) | ★★★ | ★★★ | ★★★ | ★★★ (Cochrane standard) | ★★ | ★★ (too slow) | ★★ |
| IRAC (legal) | ★★ | ★★ | ★★ | ★ (must conclude) | ★★★ | ★ (legal only) | ★★ | ★ |
| Hegelian dialectic | ★ | ★★ | ★ | ★★ | ★ | ★★ | ★ | — |
| SAFE / FActScore / Reflexion / Self-RAG / RARR | ★★★ | ★★ | ★★ | ★ (optimised for *answered-correctly*) | ★ (≤ 3 yr, no adversarial track record) | ★★ (assumes Wikipedia GT) | ★★ (per technique) | ★ (none has a quality rubric) |

**Only two candidates pass all six criteria: ACH and GRADE.**

---

## 5. Why both, not just one — complementarity

ACH and GRADE are not redundant. They are **orthogonal in their strengths**:

| | Process (*how do I investigate?*) | Measurement (*how confident should I be?*) |
|---|:---:|:---:|
| **ACH** | ★★★ — matrix + disconfirmation rule + inconclusive-as-output | ★ — Heuer gives an informal *"inconsistency score"* only |
| **GRADE** | ★ — assumes the review is already done | ★★★ — five independent dimensions, four discrete tiers |

Using both is engineering, not eclecticism: **ACH structures the agent loop, GRADE structures the scorer.**

| Novum artefact | Comes from |
|---|---|
| FSM `Planning → PlanCritiquing → Searching → Judging` loop | ACH (the iterative refinement of the hypothesis matrix) |
| RF-14 plan critic + replan | ACH ("Most analytical failures come from anchoring on the first plausible hypothesis." — Heuer 1999) |
| RF-15 disconfirmation pass (`query_intent='refuting'`, `polarity` tags) | ACH (disconfirming evidence is the diagnostic — confirming evidence is consistent with multiple hypotheses) |
| Honest-stop terminals (`honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`) | ACH (*"Inconclusive"* is an approved ACH output) + GRADE (*"Very Low certainty"* tier) |
| Structural score `S = 0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.15·C_no_conflict` | GRADE (computable analogue of GRADE's five quality dimensions: risk of bias → coverage; inconsistency → no_conflict; indirectness → coverage; imprecision → diversity/independence; publication bias → independence) |
| `final_confidence = min(S, J)` rendered separately from the synthesised answer | GRADE (*certainty rating* is reported separately from the *recommendation*) |
| `ConfidenceMismatch` event (RF-15) | GRADE (when independent quality dimensions disagree, the disagreement is itself information) |

---

## 6. What survives from the rejected candidates

A method being rejected as the *master framework* does not mean it contributes nothing. Each survivor lives inside Novum as a sub-component:

| Rejected candidate | Where it survives in Novum |
|---|---|
| **Toulmin (1958)** | Atomic data shape: each `EvidenceAdded` is a Toulmin atom (claim + grounds + warrant + backing + rebuttal + qualifier → `polarity` field). The unit-level argument grammar is Toulmin's; the aggregation grammar is not. |
| **Popper / falsificationism** | Philosophical anchor for RF-15. The disconfirmation pass is the **operationalisation of falsifiability**: a claim that has not been actively challenged is not yet corroborated. Popper supplies the *why*; ACH supplies the *how*. |
| **Bayesian confirmation theory** | Inspired `C_independence` (RF-15): independent sources weigh more than echo-chamber repetitions. The Bayesian insight without the unauditable arithmetic of imagined priors. |
| **Classical scientific method** | Vocabulary only (*hypothesis*, *evidence*, *conclusion*). The cycle does not fit a retrieval agent. |
| **PRISMA** | Inspired the *spirit* — exhaustive search, dual review (`S` vs `J`), separation of search protocol from interpretation. The multi-week cadence is incompatible. |
| **IRAC** | Inspired nothing operational; mentioned only to head off the *"why not a legal-reasoning framework?"* question. |
| **Hegelian dialectic** | Nothing. Mentioned only to acknowledge the user's likely intuitive prior. |
| **SAFE / FActScore / Reflexion / Self-RAG / RARR** | Inspired the *techniques* inside individual steps: claim decomposition (SAFE / FActScore), adversarial judge prompting (Reflexion), self-critique (Self-RAG), revise-and-retry (RARR). Cited as *related work*, not as the methodological foundation, because none has *honest stop* as a first-class terminal — they are all optimised for *answered-correctly* on a closed corpus (Wikipedia), not for *refuse-calibratedly* on the open web. |

---

## 7. The defensible one-liner

If interrupted in the panel and given one sentence:

> *"Novum is an executable adaptation of **Analysis of Competing Hypotheses (Heuer, 1999)** for the process and **GRADE (BMJ, 2004–)** for the certainty grading, with Popper's falsificationism as the philosophical anchor for the disconfirmation pass and Toulmin's argument model as the atomic data shape. The contribution is the mechanisation: turning protocols designed for human analysts and Cochrane committees into an FSM with an append-only event log, where 'cannot answer' is a first-class terminal."*

Two minutes if pressed:

> *"I fixed six criteria before looking at candidates: operationalisable, bias-aware, audit-trail, refusal-as-valid-output, decades of track record, domain-portable. Only ACH and GRADE pass all six. They are complementary — ACH supplies the process (the evidence × hypothesis matrix, the disconfirmation rule, inconclusive-as-output) and GRADE supplies the measurement (independent quality dimensions, certainty separated from recommendation). Toulmin and Popper survive as sub-components, not as the master framework. The ML-side methods — SAFE, FActScore, Reflexion, Self-RAG — are implementation techniques, not methodologies; none has honest-stop as a first-class concept. I am not inventing a research method; I am compiling two established ones into code."*

---

## 8. Audit pointers

- The selection criteria (§2) were fixed before the matrix (§4) was built, to avoid post-hoc rationalisation.
- The scoring (§4) is reviewable: each ★ rating can be challenged with a counter-example from the candidate's literature.
- Every cross-reference from the rest of the docs ([requirement-understanding.md §RF-01](requirement-understanding.md), [stopping-signal-analysis.md §8](stopping-signal-analysis.md#8-methodological-lineage-pointer), [confidence-calculation.md header](confidence-calculation.md), [design-doc.md "Research method"](../technical-phase/design-doc.md)) points back to this file as the canonical source.
- If a future RF replaces or augments the master framework, that change is logged here first; the cross-references update afterwards.

---

## References

- Heuer, R. J. Jr. (1999). *Psychology of Intelligence Analysis*. Center for the Study of Intelligence, CIA. — Chapter 8: *"Analysis of Competing Hypotheses"*.
- GRADE Working Group (2004). *Grading quality of evidence and strength of recommendations*. BMJ 328:1490. — and the GRADE handbook (Schünemann et al., 2013).
- Toulmin, S. (1958). *The Uses of Argument*. Cambridge University Press.
- Popper, K. (1934). *Logik der Forschung* (translated 1959 as *The Logic of Scientific Discovery*). Routledge.
- Moher, D. et al. (2009, updated 2020). *PRISMA 2020 statement*. BMJ 372:n71.
- Min, S. et al. (2023). *FActScore: Fine-grained Atomic Evaluation of Factual Precision*. EMNLP.
- DeepMind (2024). *SAFE: Search-Augmented Factuality Evaluator*.
- Shinn, N. et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning*. NeurIPS.
- Asai, A. et al. (2023). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*. ICLR 2024.
- Gao, L. et al. (2022). *RARR: Researching and Revising What Language Models Say*. Google.
