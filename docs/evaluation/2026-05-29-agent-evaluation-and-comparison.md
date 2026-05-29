# Evaluation Report & Comparison vs 2026-05-28 — Novum Research Agent

**Date:** 2026-05-29
**Evaluator:** Automated audit (Copilot, expert evaluator role)
**Sample:** 8 production runs against [docs/q-for-testing.md](../q-for-testing.md) re-executed after applying the 17-gap improvement plan from
[2026-05-28-agent-evaluation-and-improvement-plan.md](2026-05-28-agent-evaluation-and-improvement-plan.md).
**Evidence source:** Live Postgres event log via MCP (`runs` + `events` tables) — users `eval91e78c` (Q1-Q6) and `evale8b651` (Q7-Q8).
**Logs:** [eval_run_2026_05_29.log](../../eval_run_2026_05_29.log), [eval_q7_q8_2026_05_29.log](../../eval_q7_q8_2026_05_29.log).

---

## 0. Executive Summary

| Metric | 2026-05-28 | 2026-05-29 | Δ |
|---|---|---|---|
| Runs analysed | 8 | 8 | — |
| Runs that **terminated honestly** (any `stop_reason`) | **8 / 8** | **5 / 8** | **−3 (regression)** |
| Runs that **never stopped** (no `Stopped` event) | 0 | **3 (Q2, Q6, Q8)** | **+3 (NEW critical bug)** |
| `judge_confirmed` terminations | 6 | **1 (Q4)** | **−5** |
| `stopped_by_budget` terminations | 2 | **4 (Q1, Q3, Q5, Q7)** | **+2** |
| `DraftSynthesized` events emitted | **0** | **≥1 per stopped run** | **+ (G13 fixed)** |
| Kind-specific blocks (`keyValue`, scenario `keyPoints`) populated | **0 / 6** | **2 / 5** (Q4 `keyValue`, Q5 scenario `keyPoints`) | **+ (G1+G2 partially fixed)** |
| Avg wall-clock — *stopped* runs only | 106 s | **232 s** | **+118 % (regression)** |
| Avg wall-clock — *all* runs | 106 s | **915 s** | **+763 %** |
| Gaps from 2026-05-28 plan: closed | — | **6 / 17** | — |
| Gaps from 2026-05-28 plan: partial | — | **3 / 17** | — |
| Gaps from 2026-05-28 plan: still open / regressed | — | **8 / 17** | — |
| **New critical bug** (post-improvements) | — | **STANDARD-lane infinite loop** on `comparative`/`predictive_future` + `volatile`/`slow_changing` questions | — |

**One-line verdict:** the **output layer is materially better** (kind-specific blocks now render, DEEP answer is richer, `DraftSynthesized` is persisted, `stop_rationale` now carries `confidence`/`confidence_kind`/`triggering_signal`). But the **stopping contract is materially worse**: 3 of 8 runs failed the core promise of RF-02 ("the agent knows when to stop") and ran indefinitely (Q2: 3050 s, Q6: 1388 s, Q8: 613 s+). The improvement plan closed 6 gaps and reopened a more severe one.

---

## 1. Run Inventory (raw evidence)

| # | Question | qtype / complexity / temporal | classifier conf | Lane (route) | `answer_kind` | Stop reason | `stop_rationale.confidence` | Dur (s) | Events of note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Capital of Japan? | factual / trivial / static | 0.99 | **FAST → escalated to STANDARD** | `best_effort` | `stopped_by_budget` | 0.82 (judge) | **98** | LaneEscalated=1, JudgeRuled=3, DraftSynthesized=3, ConfidenceMismatch=2, ClaimUncoverable=1, ToolCalled=4, EvidenceAdded=3 |
| 2 | PostgreSQL vs MongoDB | comparative / standard / volatile | 0.95 | STANDARD | — | **NULL (never stopped)** | — | **3050** | **EvidenceAdded=171**, ToolCalled=57, **0 DraftSynthesized**, **0 JudgeRuled**, **0 QueryReformulated** |
| 3 | Best programming language? | subjective_opinion / standard / slow | 0.95 | STANDARD | `best_effort` | `stopped_by_budget` | 0.85 (judge) | **82** | AmbiguityDetected=1, DraftSynthesized=3, JudgeRuled=3, ConfidenceMismatch=2, **no ToolCalled/EvidenceAdded** |
| 4 | Intermittent fasting healthy? | subjective_opinion / standard / slow | 0.72 | STANDARD | **`tradeoff`** | **`judge_confirmed`** | **0.72 (no `confidence_kind`)** | **101** | ClaimCovered=5, DraftSynthesized=1, JudgeRuled=1, ToolCalled=5, EvidenceAdded=15 + **`keyValue` block "Trade-off criteria" with 5 weighted rows** |
| 5 | Long-term risks of AI-gen code | predictive_future / standard / slow | 0.95 | STANDARD | `best_effort` | `stopped_by_budget` | 0.62 (judge) | **757** | ClaimCovered=9, DraftSynthesized=3, JudgeRuled=3, ConfidenceMismatch=2, EvidenceAdded=27, ToolCalled=9 + **4 scenario `keyPoints` blocks with Drivers/Assumptions** |
| 6 | EDA vs sync microservices | comparative / standard / volatile | 0.95 | STANDARD | — | **NULL (never stopped)** | — | **1388** | EvidenceAdded=120, **QueryReformulated=40**, ToolCalled=80, **0 DraftSynthesized**, **0 JudgeRuled** |
| 7 | LT memory for autonomous agents | state_of_art / standard / volatile | 0.92 | **DEEP** | **null** | `stopped_by_budget` | **null** (`confidence_kind=null`) | **123** | AgentAction=8, AgentObservation=8, AgentThought=8, DraftSynthesized=1, EvidenceAdded=17, ToolCalled=8, HypothesesGenerated=1, VerificationQuestionsGenerated=1 + 17 citations + 6 prose paragraphs |
| 8 | Will AI replace mid-level eng? | predictive_future / standard / slow | 0.92 | STANDARD | — | **NULL (timed out at 613)** | — | **613+** | EvidenceAdded=36, ToolCalled=13, ClaimCovered=4, PlanCreated=1, **0 DraftSynthesized**, **0 JudgeRuled** |

**Notable absences across all 8 runs** (same as yesterday): zero `MetaStopVerdict`, zero `AdversarialObjectionsGenerated`, zero `PlanGapsDetected`, zero `NoProgressDetected`, zero `EchoChamberDetected` — the meta-judge layer (BRD-26) still does not exist (G8 unchanged).

---

## 2. Per-Run Evaluation

Severity rubric: 1 = cosmetic, 5 = breaks the contract with the user.

### Run 1 — "What is the capital of Japan?"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Speed (stop quickly on trivia) | Single source, < 15 s | **98 s**, FAST escalated to STANDARD, 3 judge rejections, ended on budget | **G7 / G16 unchanged** — FAST lane still over-escalates with `_FAST_S_THRESHOLD = 0.85` + `n/6` proxy | **4** | **WORSE** (51 s → 98 s, was `judge_confirmed`, now `stopped_by_budget`) |
| Format | Short factual paragraph + sources | Correct prose, 3 sources, alternative interpretations block | OK | 1 | OK |
| `stop_rationale` | Honest + numeric | `reason=stopped_by_budget`, `confidence_kind=judge`, `confidence=0.82`, `triggering_signal=judge_cap`, `summary="Judge rejected the draft after 3 attempts"` | **G4 fixed for STANDARD path** | 1 | **BETTER** |
| Confidence display | ≥ 0.8 | 82 % shown | OK (G5 fixed here) | — | OK |

### Run 2 — "PostgreSQL or MongoDB better for a small SaaS?"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Stop honestly | Any `stop_reason` after a defendable budget | **NEVER STOPPED** (3050 s wall, no `Stopped` event, no `JudgeRuled`, no `DraftSynthesized`, no `QueryReformulated`) — pure evidence-ingestion loop (171 `EvidenceAdded`, 57 `ToolCalled`) | **NEW critical bug** — STANDARD lane on `comparative + volatile` enters a tool-call/evidence-add loop that never transitions to the draft → judge phase | **5** | **REGRESSION** (was 80 s `judge_confirmed`) |
| Output | Comparison table | **No output produced** | G1/G2 cannot be measured here | **5** | REGRESSION |

### Run 3 — "What is the best programming language?"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Ambiguity handling | Lead with "the question is ambiguous because…" | `AmbiguityDetected` fires AND `answer_kind` is now **`best_effort`** (yesterday `tradeoff`), prose explicitly says *"No existe un lenguaje de programación universalmente 'mejor'"* and lists 3 alternative interpretations | **G6 fixed**: `select_answer_kind` now honours `ambiguity_detected` | — | **BETTER** |
| Stop speed on un-answerable | < 30 s honestly unanswerable | **82 s**, 3 judge rejections, ended on budget — agent argued internally instead of declaring `honest_ambiguous` | **G17 partially fixed**: faster than 97 s but still not the < 20 s "honest_ambiguous" stop the rubric expects | 3 | better |
| Output | Best-effort answer + reformulation suggestions | Best-effort prose + "se recomienda reformular" — also no evidence/tool calls in event log (judge worked on prior knowledge) | OK | 1 | BETTER |

### Run 4 — "Is intermittent fasting healthy?"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Contradiction surfacing | Explicit tension between studies | Prose names the contradiction (*"Un metanálisis…"* vs *"un estudio observacional con casi 19 000 participantes…135 % más de riesgo de mortalidad cardiovascular"*) and weights it inside the `keyValue` block | **G10 fixed** | 1 | **BETTER** |
| Format for `tradeoff` | Multi-criteria weighted table | **`answer_structured_data.blocks[0]` is a `keyValue` block titled "Trade-off criteria" with 5 rows (Beneficios metabólicos 30 %, Riesgo CV 30 %, Adherencia 20 %, Seguridad psicológica 12 %, Perfil individual 8 %)** | **G1 fixed (`criteria` payload now persisted and rendered)** | 1 | **BETTER (was sev 5)** |
| Stop transparency | Defendable stop | `reason=judge_confirmed`, `summary="Answered as tradeoff with confidence 0.72"`, `triggering_signal=judge`, `confidence=0.72` — but `confidence_kind=null` (should be `judge`) | **G5 partial** | 2 | better |
| Confidence display | A real number | **72 % shown with "✅ Verified" badge** (yesterday was 0 % "Research Limit Reached") | **G5 fixed for `judge_confirmed`** | — | **BETTER** |

### Run 5 — "Long-term risks of AI-generated code"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Format for `scenario` | Multiple scenario branches with drivers/assumptions | **4 `keyPoints` blocks** titled *"Acumulación sistémica… (high)"*, *"Erosión de competencias… (high)"*, *"Exposición legal… (medium)"*, *"Homogeneización… (low)"*, each with Driver / Assumption bullets | **G1 fixed (scenarios payload now persisted)** | 1 | **BETTER (was sev 5)** |
| Stop honestly | Within a defendable budget | **757 s** to stop — 5.3× yesterday's 144 s; 3 judge rejections before giving up on budget | **Performance regression** introduced by the new structured-payload extraction (more re-drafts per turn) | 3 | **WORSE** |
| `stop_rationale` | Numeric + judge attribution | `reason=stopped_by_budget`, `confidence_kind=judge`, `confidence=0.62`, `triggering_signal=judge_cap` | **G4 fixed** | — | BETTER |
| Acknowledge data gaps | "Long-term evidence is limited" | Not explicitly stated; confidence label *"medium"/"low"* on the last 2 scenarios partially compensates | minor | 2 | similar |

### Run 6 — "EDA vs synchronous microservices"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Stop honestly | Any `stop_reason` | **NEVER STOPPED** (1388 s; 0 `DraftSynthesized`, 0 `JudgeRuled`, **40 `QueryReformulated`**, 80 `ToolCalled`, 120 `EvidenceAdded`) — clear **query-reformulation loop**: each round adds 3 search rounds and reformulates without ever advancing to draft synthesis | **NEW critical bug** — STANDARD lane on `comparative + volatile` reformulates indefinitely instead of cutting losses and synthesising | **5** | **REGRESSION** (was 137 s `judge_confirmed`) |
| Output | Weighted candidates table | **No output produced** | cannot measure | **5** | REGRESSION |

### Run 7 — "Most promising approach for long-term agent memory"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Format depth | DEEP answer richer than FAST | **6 prose paragraphs, 17 citations** (vs yesterday's 2 paragraphs) — argues for "hybrid memory architectures", contrasts H1-H4 hypotheses, names Mem0, JoyAgent-JDGenie, VLA agents | **G3 fixed** — DEEP lane no longer uses `FAST_SYNTH_PROMPT` for the final draft | 1 | **BETTER (was sev 5)** |
| `answer_kind` | Non-null kind | **still `null`** | **G15 NOT fixed** — DEEP lane never invokes `select_answer_kind` | 4 | unchanged |
| `stop_rationale` for DEEP | Correct cause | `summary="Reached ReAct step limit (8/8 steps)"`, `triggering_signal=budget` | **G4 fixed (DEEP path now reports correct signal)** | — | **BETTER** |
| Confidence display | Best-effort score, not 0 % | **`confidence=null`, `confidence_kind=null` → answer_structured still renders "Score 0 %"** | **G5 NOT fixed for DEEP** — only the STANDARD-judge path populates confidence; DEEP still passes null | **5** | unchanged |
| Stop speed | < 200 s defendable | 123 s, 8/8 ReAct steps | OK (capped by ReAct, not by lack of meta-judge — G8 still missing) | 2 | better (was 84 s) |

### Run 8 — "Will AI replace mid-level engineers in 10 years?"

| Criterion | Expected | Obtained | Gap | Sev | Δ vs 28/05 |
|---|---|---|---|---|---|
| Stop honestly | Any `stop_reason` | **NEVER STOPPED** before client timeout at 613 s (36 `EvidenceAdded`, 13 `ToolCalled`, 4 `ClaimCovered`, 1 `QueryReformulated`, 0 `DraftSynthesized`, 0 `JudgeRuled`) — same `comparative/predictive` STANDARD-lane stall | **NEW critical bug** | **5** | **REGRESSION** (was 154 s `judge_confirmed`) |
| Scenarios | Multiple branches with probability bands | **No output produced** | cannot measure | **5** | REGRESSION |

---

## 3. Aggregated Gap Map — status vs 2026-05-28 plan

| # | Gap (verbatim from 28/05) | Runs affected today | Severity | Status |
|---|---|---|---|---|
| **G1** | Kind-specific payload (`candidates`, `scenarios`, `criteria`) is dropped between `tasks/draft.py` and the `Stopped` event | 4 ✅, 5 ✅, (2/6/8 N/A — no output) | 5 | **CLOSED** for STANDARD-tradeoff/scenario (Q4 `keyValue`, Q5 `keyPoints[]`). Still untested for `weighted` (Q2/Q6 never produced output). |
| **G2** | `StructuredRenderer.build_data` cannot render kind-specific blocks | 4, 5 | 5 | **CLOSED** (verified by `answer_structured_data.blocks` shape in Stopped payloads). |
| **G3** | DEEP lane uses `FAST_SYNTH_PROMPT` (1-2 sentence) for its final draft | 7 | 5 | **CLOSED** — Q7 produced 6 substantial paragraphs and 17 citations. |
| **G4** | `stop_rationale` for DEEP-with-budget reports wrong cause | 7 | 5 | **CLOSED** (`summary="Reached ReAct step limit (8/8 steps)"`, `triggering_signal=budget`). |
| **G5** | `stopped_by_budget` confidence rendered as "0 %" | 1 OK, 3 OK, 5 OK, 7 ❌ | 5 | **PARTIAL** — STANDARD-judge path populates `confidence` + `confidence_kind=judge`. DEEP path still emits `null` → renderer still shows "Score 0 %" on Q7. |
| **G6** | `select_answer_kind` ignores `ambiguity_detected` (subjective_opinion → tradeoff always) | 3 | 4 | **CLOSED** — Q3 now `best_effort` after `AmbiguityDetected`. |
| **G7** | FAST lane escalates trivial factual questions to STANDARD | 1 | 4 | **NOT FIXED** — Q1 still escalates and now also fails to `judge_confirm`, ending on budget at 98 s. |
| **G8** | Meta-judge (BRD-26 VoC + Adversarial Completeness) does not exist | all | 4 | **NOT FIXED** — `MetaStopVerdict`/`AdversarialObjectionsGenerated` still 0 occurrences. This is the direct enabler of the new hang bug (no second-order signal to declare progress is stalled). |
| **G9** | `PlanGapsDetected`, `NoProgressDetected`, `EchoChamberDetected` never fire | 2, 5, 6, 8 | 3 | **NOT FIXED** — still 0 occurrences. Q2/Q6/Q8 hangs are the perfect example of `NoProgressDetected` being needed. |
| **G10** | Contradictions detected but not surfaced as a visible bullet | 4 ✅ | 3 | **CLOSED** for Q4 (contradiction surfaced inside `keyValue` rows). Other contradictions runs (8) did not complete. |
| **G11** | `weighted` answers come out assertive without surfacing context-dependency | 2/6 N/A | 3 | **NOT MEASURABLE** (no `weighted` run completed). |
| **G12** | `scenario` answers do not list explicit assumptions / drivers / probability bands | 5 ✅ | 3 | **CLOSED** — Q5 scenarios now carry explicit "Driver:" and "Assumption:" bullets. |
| **G13** | No `DraftSynthesized` event persisted | all stopped runs | 2 | **CLOSED** — Q1 (3), Q3 (3), Q4 (1), Q5 (3), Q7 (1) all emit `DraftSynthesized`. |
| **G14** | DEEP ReAct capped at 8 steps with no negotiation | 7 | 2 | **NOT FIXED** — Q7 hit 8/8 again. Acceptable until meta-judge exists. |
| **G15** | DEEP lane never invokes the kind-specific synth prompt → `answer_kind` null | 7 | 4 | **NOT FIXED** — Q7 still `answer_kind=null`. |
| **G16** | `_FAST_S_THRESHOLD = 0.85` proxy is `min(1, n_evidence/6)` — brittle | 1 | 3 | **NOT FIXED** — see G7. |
| **G17** | Ambiguous questions run full STANDARD pipeline instead of honest fast-stop | 3 | 3 | **PARTIAL** — Q3 now declares ambiguity and produces `best_effort` (97 s → 82 s), still not the < 20 s `honest_ambiguous` the rubric expects. |

**Summary**: 6 CLOSED · 3 PARTIAL · 6 NOT FIXED · 2 N/A (couldn't measure due to hangs).

---

## 4. New issues introduced (post-improvements)

### N1 — STANDARD-lane infinite loop on `comparative` / `predictive_future` questions (Severity 5)

**Symptom.** Q2, Q6, Q8 produced **no `Stopped`, `DraftSynthesized`, or `JudgeRuled` events** despite running for 3050 s / 1388 s / 613 s respectively. The FSM never reaches the *synthesise → judge → stop* phase.

**Two distinct failure modes observed in the event log:**

| Run | qtype + temporal | Trace shape | Hypothesis |
|---|---|---|---|
| Q2 (`comparative + volatile`) | `EvidenceAdded=171`, `ToolCalled=57`, **0 QueryReformulated**, 0 ClaimCovered | Sources keep returning evidence; the FSM never decides the evidence is sufficient and never reformulates. Likely the new structural-confidence path raised the "enough evidence" bar and the loop has no upper bound. | "Evidence ceiling never reached" |
| Q6 (`comparative + volatile`) | `EvidenceAdded=120`, `ToolCalled=80`, **`QueryReformulated=40`**, 0 ClaimCovered | Reformulation fires repeatedly, never satisfies whatever signal the reformulator is watching, never breaks out into the draft phase. | "Reformulation loop never terminates" |
| Q8 (`predictive_future + slow_changing`) | `EvidenceAdded=36`, `ToolCalled=13`, `QueryReformulated=1`, `ClaimCovered=4`, `PlanCreated=1`, `HypothesesGenerated=1` | More balanced trace but still no DraftSynthesized after 613 s. Probably the same ceiling issue with a smaller search budget. | "Slower-burn variant of Q2" |

**Why this matters.** This breaks the **single most fundamental contract** of the system (RF-02: every run terminates with one of the 7 `stop_reason` enum values; "the agent knows when to stop"). Yesterday's report scored the agent 8/8 on this dimension. Today: **5/8**.

**Recommended next fix (Á0, blocker before any other improvement):**

1. **Add a global wall-clock budget per run** (e.g. 300 s for STANDARD, 240 s for DEEP) that **unconditionally** transitions to `stopped_by_budget` with whatever evidence is present. This must run before all other lane logic. The 7-state `stop_reason` enum already supports this.
2. **Wire `NoProgressDetected`** (G9): if the last *k* events are all `EvidenceAdded` or `QueryReformulated` with no `ClaimCovered` delta and no `DraftSynthesized`, force-transition to the draft phase.
3. **Cap `QueryReformulated`** to ≤ 5 per run (Q6 had 40).
4. **Cap `EvidenceAdded`** to ≤ 60 per run (Q2 had 171).
5. **Then** add the missing meta-judge (G8) to make the cap dynamic instead of a hardcoded ceiling.

### N2 — Performance regression on `judge_confirmed`/`stopped_by_budget` runs (Severity 3)

| Run | 28/05 | 29/05 | Δ |
|---|---|---|---|
| Q3 (best language) | 97 s | 82 s | −15 s (BETTER) |
| Q4 (fasting) | 158 s | 101 s | −57 s (BETTER) |
| Q5 (AI risks) | 144 s | **757 s** | **+613 s** |
| Q7 (memory) | 84 s | 123 s | +39 s |
| Q1 (Tokyo) | 51 s | 98 s | +47 s |

The Q5 jump (5.3×) is the most concerning; it's the same lane as Q3/Q4 but ran 3 judge attempts and emitted 3 `DraftSynthesized`. The new structured payload likely makes each draft slower to generate, multiplying any judge rejection by the draft cost.

### N3 — Q1 regression: `judge_confirmed` → `stopped_by_budget` (Severity 4)

Yesterday Q1 cleared `judge_confirmed` in 51 s with confidence 0.92. Today it required FAST→STANDARD escalation and exhausted the judge cap (3 rejections) before stopping at 98 s with confidence 0.82. Same gap as 28/05 (G7) but **worse**: the judge cap is now more punitive after the prompt changes.

---

## 5. What actually got better (concrete evidence)

1. **Kind-specific blocks render correctly** for `tradeoff` (Q4) and `scenario` (Q5). The `answer_structured_data.blocks` JSON now contains `keyValue` rows with weights and `keyPoints` blocks titled with confidence labels. This was the single most impactful gap on 28/05 and is now demonstrably closed for those two kinds.
2. **`stop_rationale` is a structured object** with `reason`, `summary`, `confidence`, `confidence_kind`, `triggering_signal` — yesterday it was a single string. Five of five stopped runs populate the first three correctly.
3. **DEEP-lane prose is now substantive.** Q7 produced 6 paragraphs / 17 citations / explicit hypothesis comparison, where yesterday's equivalent (Q7) produced 2 paragraphs.
4. **`DraftSynthesized` events are persisted** (G13), restoring the "every step is an event" guarantee for the synthesise step.
5. **Ambiguity routes to `best_effort`** (G6). Q3 now leads with *"No existe un lenguaje de programación universalmente 'mejor'"* and offers reformulation suggestions instead of forcing a tradeoff verdict.
6. **DEEP `stop_rationale` reports the right cause** (G4). Q7 now says `"Reached ReAct step limit (8/8 steps)"` instead of yesterday's bogus `"Reached search limit (0 rounds)"`.

---

## 6. Conclusion

The 28/05 plan was technically successful on the **output / honesty surface**: the agent now persists and renders kind-specific structured data, surfaces ambiguity, and emits the `DraftSynthesized` audit event. Six of the seventeen identified gaps are unambiguously closed, three more are partially closed, and the user-visible answer quality for `tradeoff` (Q4) and `scenario` (Q5) is now what the original RF contract promised.

However, the same release **broke the stopping contract** for the `comparative` and `predictive_future` STANDARD-lane questions. Three of eight runs (37.5 %) failed RF-02 entirely — they did not produce a `Stopped` event at all and would have run until manually killed. This is a regression severe enough to block any further format work until it is fixed.

**Concrete next move (single highest-impact PR):** implement an **unconditional wall-clock budget transition** in the orchestrator FSM (≤ 300 s STANDARD / ≤ 240 s DEEP), plus a hard cap on `QueryReformulated` (≤ 5) and `EvidenceAdded` (≤ 60) per run. That single change would have rescued Q2, Q6, and Q8 with no impact on the runs that already stop honestly, restoring the 8/8 termination rate from 28/05 while keeping today's output-quality gains.

---

## Annex A — Stopped payload structural fingerprints (verified)

```text
Q1 (factual/FAST→STANDARD/best_effort/budget):
  answer_structured_data.blocks = [paragraph, keyPoints("Alternative interpretations"), paragraph×3]
  stop_rationale = {reason: stopped_by_budget, confidence: 0.82, confidence_kind: judge,
                    triggering_signal: judge_cap, summary: "Judge rejected the draft after 3 attempts"}

Q3 (subjective/STANDARD/best_effort/budget):
  answer_structured_data.blocks = [paragraph, keyPoints("Alternative interpretations"), paragraph×5]
  stop_rationale = {reason: stopped_by_budget, confidence: 0.85, confidence_kind: judge,
                    triggering_signal: judge_cap, summary: "Judge rejected the draft after 3 attempts"}

Q4 (subjective/STANDARD/tradeoff/judge_confirmed):
  answer_structured_data.blocks = [keyValue("Trade-off criteria", 5 rows w/ weights), paragraph×5]
  stop_rationale = {reason: judge_confirmed, confidence: 0.72, confidence_kind: null,
                    triggering_signal: judge, summary: "Answered as tradeoff with confidence 0.72"}

Q5 (predictive/STANDARD/best_effort/budget):
  answer_structured_data.blocks = [keyPoints×4 (scenarios with Driver/Assumption), paragraph×2]
  stop_rationale = {reason: stopped_by_budget, confidence: 0.62, confidence_kind: judge,
                    triggering_signal: judge_cap, summary: "Judge rejected the draft after 3 attempts"}

Q7 (state_of_art/DEEP/null/budget):
  answer_structured_data.blocks = [paragraph, keyPoints("Alternative interpretations"), paragraph×6]
  stop_rationale = {reason: stopped_by_budget, confidence: null, confidence_kind: null,
                    triggering_signal: budget, summary: "Reached ReAct step limit (8/8 steps)"}

Q2, Q6, Q8: NO Stopped event in events table. Run rows have stop_reason = NULL.
```

## Annex B — Run IDs (for re-query)

```text
Q1 da075de9-f926-48b4-b76c-a8c141a33beb  user eval91e78c
Q2 55a93f0b-5542-4e77-ad37-8d54510565c0  user eval91e78c  (hung)
Q3 03bd6725-9510-4477-b500-badc5a339232  user eval91e78c
Q4 40104907-07a3-4764-b44f-13c110c75ab5  user eval91e78c
Q5 ca6838cc-ad27-4b78-9c21-9e394d2eef28  user eval91e78c
Q6 a5c8ea28-b442-45ed-b574-94c29919402b  user eval91e78c  (hung)
Q7 32fef1ea-627a-4451-bd27-c8e1bba63709  user evale8b651
Q8 088eeece-c6f5-4bff-bd97-9e18de795dba  user evale8b651  (hung)
```
