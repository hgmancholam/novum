# How Novum Performs Research

This document describes the **exact research plan Novum executes for every
question**, in the order events are emitted. It is grounded in the current
codebase (post IP-25 + BRD-26) and the requirements catalogue (RF-01..RF-19).
Anything not listed here is deliberately not implemented in V1 — see "What
Novum does NOT do" at the bottom.

The contract is simple:

- Every step emits an **append-only event** in PostgreSQL (`events.payload JSONB`).
- The UI right panel mirrors those events 1:1 (no live LLM regeneration on read — RF-08).
- The run is **fully replayable**: opening it twice shows identical output.
- Stopping is a **first-class success outcome**, not an error (RF-02).
- **Not every run executes the same pipeline.** Post IP-25, the orchestrator
  routes each question to one of **three lanes** (FAST / STANDARD / DEEP)
  based on the output of CLASSIFYING. Lanes share the same events, the same
  stopping enum, the same confidence formula and the same seams — but they
  compose different strategies and have different per-lane stopping
  checkpoints. See Phase 1.6 for the routing rules and Phase 2 onward for
  each lane's flow.

> **Design source.** This document is the *implementation-aligned* view.
> The strategic rationale for the 3-lane decision lives in
> [building-the-plan.md](building-the-plan.md). The phased rollout (Phase 0
> = parallel search fix, Phases A–F = lane architecture) lives in
> [IP-25](../implementation-phase/implementation-plans/IP-25-three-lane-research-flow.md).
> The **agentic stopping layer** (Value-of-Continuation + Adversarial
> Completeness meta-judge that decides termination on top of the hard caps)
> lives in
> [BRD-26](../implementation-phase/brds/BRD-26-agentic-stopping-meta-judge.md)
> and is summarised in §7.6 below.

---

# Phase 0 — Identity and Run Setup

Before the first LLM call:

1. **User registration** — `username` → token. No password, no email (RF-09).
2. **Run creation** — UUID `run_id`, persisted in `runs` table.
3. **Event log opened** — every subsequent step appends to `events(payload JSONB)`.
4. **SSE stream attached** — `Last-Event-ID` resume, heartbeat 15 s (RF-08).

---

# Phase 1 — Understanding the Question (`CLASSIFYING`)

The classifier LLM runs **once** and emits a structured `QuestionClassified`
event with multiple dimensions:

## 1.1 What kind of question is it?

`QuestionType` ∈ {`direct`, `comparative`, `weighted`, `best_effort`, `scenario`, `definitional`, `causal`, …}

This drives **answer shape**, not just labels:

| `QuestionType` | Drives |
|---|---|
| `direct` | One short factual answer, ceiling 1.0 |
| `comparative` | Two-sided structured answer |
| `weighted` | Multi-criteria evaluation; ceiling 0.85 |
| `best_effort` | Ambiguous question; ceiling 0.70 |
| `scenario` | Multiple futures with explicit assumptions; ceiling 0.80 |

> **Note on `ceiling`.** `kind_ceiling[AnswerKind]` is the **maximum
> confidence that this answer shape can legitimately reach**, regardless of
> how good the evidence is. It lives in
> [backend/app/confidence/calculator.py](../../backend/app/confidence/calculator.py)
> and is applied as `S_effective = S_raw * kind_ceiling[AnswerKind]`. The
> rationale: if the question itself is ambiguous (`best_effort`) we cannot
> honestly report 1.0 even with unanimous sources — the limitation is in
> the question, not the evidence. The ceiling is a **honesty mechanism**,
> not pessimism. See `confidence-calculation.md` for the full formula.

## 1.2 How complex is it?

`complexity_hint` ∈ {`trivial`, `standard`, `deep`} — controls budgets downstream:

| Hint | `max_rounds` | `max_searches` | Deep-fetch budget |
|---|---|---|---|
| `trivial` | 3 | 4 | 0 |
| `standard` | 8 | 12 | 2 |
| `deep` | 16 | 24 | 3 |

## 1.3 Is it static, slow-changing, volatile, or real-time? (IP-23 WP-1)

`TemporalSensitivity` ∈ {`static`, `slow_changing`, `volatile`, `real_time`} —
controls **freshness filtering**:

| Sensitivity | `tavily_days_filter` | Stale-citation penalty (× 0.85) applies? |
|---|---|---|
| `static` (historical, science, definitions) | `None` (no filter) | Never |
| `slow_changing` (best practices, architecture trends) | 730 (2 years) | If older than 2 y |
| `volatile` (industry adoption, prices, policy) | 180 | If older than 180 d |
| `real_time` (news, live events) | 7 | If older than 7 d |

The classifier infers this from the question text (e.g. "What is the capital of
Japan?" → `static`; "What did OpenAI announce last week?" → `real_time`).

## 1.4 Which experts should we hear from?

`expected_experts[]` ∈ {`academic`, `medical_researcher`, `journalist`,
`practitioner_engineer`, `industry_analyst`, `policymaker`, …}

These are hints surfaced to the UI (RF-13) and steer the planner's source
heterogeneity preference.

## 1.5 Ambiguity resolution

Before planning, a resolver pass detects:

- **Empty comparative** ("X vs nothing")
- **Pure ambiguity** ("What is the best programming language?")
- Overrides `QuestionType` / `AnswerKind` if needed

For Q3 ("best programming language"), this is what pushes the run to
`AnswerKind=best_effort` with a 0.70 ceiling — the system **acknowledges the
question is ill-posed** rather than pretending to answer it.

## 1.6 Lane routing (`RouteSelected`)

The three dimensions emitted by CLASSIFYING (1.1 + 1.2 + 1.3) are the input
to a **deterministic** lane selector. No new LLM call is made: the selector
is pure Python in `app/agent/lane_router.py::select_lane`.

| Lane | Trigger | Typical questions |
|---|---|---|
| **FAST** | `complexity_hint == trivial` Y `question_type ∈ {direct, definitional}` Y `temporal_sensitivity != real_time` | "Capital of Japan?", "What is CRISPR?" |
| **DEEP** | `complexity_hint == deep` Y (`question_type ∈ {causal, scenario, predictive_future, best_effort}` O ambiguity detected by §1.5 resolver) | "Why did X fail?", "What would happen if Y?" |
| **STANDARD** | Everything else (default) | Comparative, weighted, state-of-art, complex direct |

**Safety rule:** `question_type == predictive_future` forces
`complexity_hint >= standard` regardless of the classifier output (no
valid trivial prediction exists).

The orchestrator emits a `RouteSelected` event with `lane`, `reason`, and
the three Self-Ask dimensions that justified the decision, then dispatches
to the lane handler. The event is additive (RF-03) and surfaced in the UI
trace panel.

---

# Phase 2 — Lane FAST (trivial factual lookups)

For `lane == FAST`. Target: 2 LLM calls, ≤ 15 s wall-clock.

## 2.1 Single combined search

One `ToolCalled` round with the original question as query — no sub-claim
decomposition. Wikipedia + Tavily fire **in parallel** (top-3 each).

## 2.2 Short synthesizer

The synthesizer produces a 1–2 sentence answer with inline citations
(`FAST_SYNTH_PROMPT`). No structured `AnswerKind` shape beyond `direct`.

## 2.3 Mini-judge

A short structured LLM call (`FAST_MINI_JUDGE_PROMPT`) returns
`MiniJudgeVerdict { ok: bool, j_score: float, reason: str }`. This is
**not** the full DeepSeek judge — it is a degraded CoVe-style check focused
on *do the citations exist, do they support the claim, is there an obvious
between-source contradiction*.

## 2.4 Stopping evaluator

Two outcomes:

- `S_effective ≥ 0.85` Y `mini_judge.ok == True` → `stop_reason = judge_confirmed`.
- Otherwise → emit `LaneEscalated { from_lane: FAST, to_lane: STANDARD, reason }`
  and continue into the STANDARD pipeline starting at Phase 3. Escalation is
  **transparent** — the user never sees a failure, only the eventual
  STANDARD result. Confidence reported reflects the STANDARD run.

Skips relative to STANDARD: no `CRITIQUING`, no sub-claims, no
deep-fetch, no re-decomposition, no full judge.

---

# Phase 3 — Lane STANDARD: Plan (`PLANNING`)

For `lane == STANDARD` (default path). Reused by FAST after escalation.
The planner LLM emits a `PlanCreated` event with:

The planner LLM emits a `PlanCreated` event with:

## 3.1 Sub-claim decomposition

The main question is split into 2–7 verifiable sub-claims. Each sub-claim is
something a source can directly support or contradict.

Example for "Should a high-scale AI platform use event-driven architecture or
synchronous microservices?":

```
sub_claims:
  - Event-driven systems scale better under bursty load
  - Synchronous microservices have lower operational complexity
  - Latency-critical paths favour synchronous request/response
  - Observability tooling for EDA has matured since 2022
  - Team maturity is a stronger predictor than architecture style
```

## 3.2 Query hygiene (IP-23 WP-4)

Each sub-claim gets a search query that obeys four hygiene clauses:

1. **≤ 6 tokens** (measured with `tiktoken`).
2. **No boolean operators** (no `AND`, `OR`, `-term`).
3. **No redundant entities** already present in the previous query.
4. **Positive framing** (search for what we want, not what we want to exclude).

`query_length_tokens` is emitted per query — visible in the trace.

## 3.3 Source routing by temporal sensitivity (IP-23 WP-1)

- `static` / `slow_changing` → Wikipedia + Semantic Scholar + OpenAlex first, Tavily second.
- `volatile` / `real_time` → Tavily first with `search_depth="advanced"` and `days` filter; Wikipedia + Semantic Scholar + OpenAlex second.
- Semantic Scholar's and OpenAlex's recency filter is mapped from `days` to a `year` range (neither API has a day-level filter).

## 3.4 Source routing by question type (commit C5, 2026-05-28)

On top of temporal routing, the planner appends the **academic pair**
`["semantic_scholar", "openalex"]` to `preferred_sources` when **all three**
hold:

- `question_type ∈ {STATE_OF_ART, PREDICTIVE_FUTURE, CAUSAL, COMPARATIVE}`
- `complexity ∈ {STANDARD, DEEP}`
- `temporal_sensitivity != real_time` (peer-reviewed material is stale by
  definition on real-time topics)

This keeps Semantic Scholar / OpenAlex quota for the questions that
actually benefit from peer-reviewed evidence and avoids burning it on
`FACTUAL` or `DEFINITIONAL` queries.

## 3.5 Abductive hypotheses (DEEP only, IP-25 Phase D)

When `lane == DEEP` **or** `question_type ∈ {causal, scenario, predictive_future, best_effort}`,
the planner additionally emits **2–4 competing hypotheses** in a
`HypothesesGenerated` event. Each `Hypothesis` carries `id`, `text`,
`priority` and a starting `verdict = "pending"`. These are the targets of
the ReAct loop (Phase 5b) and, for `AnswerKind == scenario`, the skeleton of
the final output — one scenario per confirmed hypothesis with its
independent confidence.

## 3.6 Plan self-critique (`CRITIQUING`)

Before any external call is made, the LLM critiques its own plan:

- Are the sub-claims independent?
- Do they cover the question?
- Are the queries searchable?

If the critique fails, the planner regenerates **before** spending the search
budget.

---

# Phase 4 — Gathering Evidence (`SEARCHING`)

For each pending sub-claim. **Searches across claims execute in parallel**
(IP-25 Phase 0, `asyncio.gather` in `execute_search_round`). Within a single
claim the source cascade runs sequentially.

## 4.1 Four heterogeneous Sources (RF-04)

- **Tavily** web search — `search_depth="advanced"`, with `days` filter from §2.3.
- **Wikipedia** — encyclopedic baseline, second Source plugin.
- **Semantic Scholar** — academic graph API (`api.semanticscholar.org/graph/v1`).
  Returns peer-reviewed and preprint papers with citation counts, authors,
  venue and DOI. Free tier, no API key required (optional `S2_API_KEY` raises
  the rate limit). Provides high-weight evidence for science, medical and
  technical questions.
- **OpenAlex** — open scholarly graph (`api.openalex.org/works`). Independent
  index of works, authors, venues and citation counts; complements Semantic
  Scholar for source heterogeneity within the academic tier. Free, no API
  key required.

All four are interchangeable behind the `Source` Protocol (RF-01) and live
in [backend/app/sources/registry.py](../../backend/app/sources/registry.py).
Semantic Scholar and OpenAlex hosts (`*.semanticscholar.org`,
`*.openalex.org`, `doi.org`) are classified `primary_authoritative` in the
tier table below — evidence from these sources lands at ×1.30 on coverage
and diversity.

### 4.1.1 Citation-weighted ranking inside academic sources (commit C6, 2026-05-28)

Semantic Scholar and OpenAlex share a `_citation_bump` helper that lifts
well-cited works in the result list **without overriding search-engine
relevance**:

```
bump(c)  = min(0.30, log10(1 + c) / log10(1001) * 0.30)
final_score = clamp(base_relevance + bump(citation_count), 0, 1)
```

- `base_relevance = max(0.1, 1.0 - rank * 0.05)` (existing rank decay).
- Cap at +0.30 ensures citations **break ties** at deeper ranks (≥ 6) but
  cannot override a top-ranked topical hit. The seam contract
  `relevance_score ∈ [0, 1]` is preserved.

## 4.2 What we capture per URL

Each `SourceResult` records:

- `title`, `url`, `snippet`
- `source_published_date` (when the page declares one)
- The host, normalised for tier classification

## 4.3 Adaptive query reformulation (IP-25 Phase 0)

If **every** Tavily result for a claim returns `relevance_score < 0.3`, the
source fires a **single** reformulated query that concatenates the claim
text with the first 40 chars of the original question. This emits a
`QueryReformulated` event with `original_query`, `reformulated_query`,
`target_claim_id`, and `reason = "low_relevance"`. Capped at one
reformulation per claim per round — no loop.

## 4.4 Authority tier classification (IP-23 WP-3)

Every result is classified into one of four tiers by host pattern:

| `AuthorityTier` | Examples | Multiplier on `C_coverage` + `C_diversity` |
|---|---|---|
| `primary_authoritative` | `*.gov`, `*.gov.*`, `*.gob`, `*.gob.*`, `*.mil`, `*.mil.*`, `*.int`, `*.edu`, `*.edu.*`, `*.ac.*`, `who.int`, `nih.gov`, `arxiv.org`, `*.semanticscholar.org`, `*.openalex.org`, `doi.org`, `ietf.org`, `iso.org`, peer-reviewed journals | × 1.30 |
| `reputable` | Wikipedia, Britannica, NYT, BBC, Reuters, AP News | × 1.10 |
| `general` | Most blogs, vendor docs, Stack Overflow, Reddit, plain country TLDs (`.es`, `.mx`, `.co`, …) | × 1.00 |
| `low_signal` | Medium, Quora, geeksforgeeks, w3schools, `*.blogspot.com`, `*.wordpress.com`, `*.substack.com`, `.biz`, `.info`, `.xyz`, `.top` | × 0.70 |

Multipliers **only** apply to coverage and diversity. `C_agreement` and
`C_no_conflict` are untouched (avoiding double counting).

### TLD policy

- **Government / academic / military / treaty TLDs** are recognised in any
  country form (`.gov`, `.gov.uk`, `.gob.mx`, `.gob.es`, `.mil.co`,
  `.edu.mx`, `.ac.jp`, `.int`, …). We do **not** maintain a country
  whitelist — that would exclude valid authoritative sources from any
  country we forgot to list.
- **Plain country TLDs** (`.es`, `.mx`, `.co`, `.us`, …) stay `general`.
  A country TLD alone says nothing about authority; only the
  governmental / academic subdomain does.
- **`.org`** stays `general`. Anyone can register an `.org`; specific
  trustworthy hosts (Wikipedia, IETF, ISO, …) are promoted by host rule,
  not TLD.
- **Cheap / spam-prone TLDs** (`.biz`, `.info`, `.xyz`, `.top`) are
  globally classified `low_signal` regardless of host. They are dominated
  by content farms in practice.

Rules live in
[backend/app/agent/sources_authority/tiers.py](../../backend/app/agent/sources_authority/tiers.py)
and are first-match-wins.

## 4.5 Tool call accounting

Every external call emits a `ToolCalled` event with provider, latency, status
and tokens (where applicable). These feed the budget signals in §7.

## 4.6 LLM call routing

All LLM calls go through `app/llm/client.py::call`, which:

- Routes through the **provider-agnostic interface** (litellm) which supports Anthropic, Google, OpenAI, and GitHub Models. **V1 only enables Anthropic Claude.**
- Retries with **tenacity** + exponential backoff on transient errors.
- **Fails fast** on permanent quota errors from OpenAI / Anthropic / Google
  (`LLMProviderQuotaExhausted`) without burning the retry budget.

---

# Phase 5 — Analysing Evidence (`ANALYZING`)

## 5.1 Per-claim indexing

Each piece of evidence is attached to a specific sub-claim. The
`question_index` ensures isolation between runs — evidence from run A never
contaminates run B.

## 5.2 Evidence aggregation

`AnalyzedEvidence` events fold:

- Text snippet
- Citation
- `AuthorityTier`
- `source_published_date`
- The sub-claim it supports or contradicts

## 5.3 Dynamic re-decomposition (STANDARD only, IP-25 Phase B)

After `S_raw` is computed (Phase 6) and **before** synthesizing, the
orchestrator may invoke one extra planner pass when:

- `state.redecomposition_count < state.max_redecomposition` (default 1), Y
- `S_raw < confidence_threshold + 0.10` (the answer is borderline).

`identify_plan_gaps` asks the planner *"given the original question, the
current sub-claims and the evidence summary, which angles are not yet
covered?"* and returns up to 3 short gap descriptions. These become new
`SubClaim` entries appended to `state.sub_claims`, a
`PlanGapsDetected` event is emitted, and the FSM transitions
`ANALYZING → SEARCHING` for the extra round. Cap of 1 extra round per run.

This closes the main gap vs. ReAct (static plan) **without** introducing a
reasoning loop in STANDARD.

## 5.4 Echo chamber penalty (IP-25 Phase 0)

When ≥ 3 sources for the same claim have non-null
`source_published_date`, all fall within a 7-day window, AND
`C_agreement == 1.0`, `C_diversity` is multiplied by **0.85** and an
`EchoChamberDetected` event is emitted with `claim_id`, `n_sources` and
`date_window_days`. This penalises unanimous agreement that traces back to a
single news cycle propagating across outlets.

## 5.5 Lane DEEP — ReAct sub-FSM (replaces 5.3 when `lane == DEEP`)

For `lane == DEEP`, after the abductive hypotheses (§3.5) and one
initial parallel search round, the orchestrator enters a **ReAct loop**
(`app/agent/react/loop.py`) instead of the static decompose→analyse→synth
flow.

Each step emits three events:

- `AgentThought { step, thought }` — LLM call with the running history.
- `AgentAction { step, action_type, args }` — structured output of a
  **closed enum** of actions: `search`, `deep_fetch`, `evaluate_hypothesis`,
  `finish`. Anything else is rejected and re-prompted (step does not count).
- `AgentObservation { step, result_summary, tokens }` — result of the action
  via the existing `Source` seam.

`evaluate_hypothesis(hypothesis_id, verdict)` updates a hypothesis to
`confirmed` / `refuted` and emits `HypothesisEvaluated` with the supporting
`evidence_ids[]`.

**Guardrails:**

- Hard cap `max_react_steps = 8` (no exceptions).
- History summarised by the synthesizer when token count exceeds 15 000
  (keeps last 4 steps verbatim, summarises the rest, emits
  `HistorySummarized`).
- Stopping evaluated **after every observation** — see Phase 7.5.

---

# Phase 6 — Structural Confidence (`S_raw`)

Confidence is **not** asked to the LLM. It is computed from the evidence shape
(RF-12). Four components, each in `[0, 1]`:

| Component | Question it answers |
|---|---|
| `C_coverage` | Did we get evidence for every sub-claim? |
| `C_diversity` | Did the evidence come from independent sources? |
| `C_agreement` | Do the sources point in the same direction? |
| `C_no_conflict` | Are there explicit contradictions between sources? |

Then:

1. `S_raw = weighted_sum(C_coverage, C_diversity, C_agreement, C_no_conflict)`
2. `S_raw` is multiplied per-evidence by `AuthorityTier` multiplier (only on coverage + diversity).
3. **Echo chamber penalty** (§5.4) may multiply `C_diversity` by 0.85.
4. **Stale-citation penalty** (× 0.85 on `kind_ceiling["direct"]`) if citations are older than the temporal sensitivity threshold from §1.3.
5. `S_effective = S_raw × kind_ceiling[AnswerKind]` — caps confidence by what the question type can legitimately deliver.

`S_effective` is the **structural** half of the final score. The other half is
the judge's verdict (§9).

---

# Phase 7 — Stopping Signals (RF-02)

Stopping is evaluated **after every round** — where "round" is
lane-specific:

| Lane | Round = |
|---|---|
| FAST | one pass after `mini_judge` |
| STANDARD | one full Search → Analyze → Synth → Judge cycle |
| DEEP | each ReAct `AgentObservation` and each CoVe pass |

The orchestrator iterates every configured `StoppingSignal` plugin in
priority order. Four categories: hard global signals, anti-stall, early-exit
checkpoints, and the agentic meta-judge decision (BRD-26).

## 7.1 Hard global signals (all lanes)

1. **`BudgetExhaustedSignal`** — `max_rounds`, `max_searches`, `max_tokens`, `max_seconds_wall_clock` from §1.2.
2. **`UserCancelledSignal`** — the FE asked us to stop.
3. **`JudgeSignal`** — fires when the judge returns `verdict == "approve"`. Maps to `STOP{JUDGE_CONFIRMED}`.

## 7.2 Anti-stall signal (STANDARD + DEEP, IP-25 Phase B)

**`NoProgressSignal`** fires when `len(confidence_history) >= 3` AND
`confidence_history[-1] - confidence_history[-3] < 0.05`. It does not kill
the run — it forces a transition to `SYNTHESIZING` with the current
evidence and emits `NoProgressDetected { delta_3rounds, current_confidence }`.
Prevents the "20 minutes without progress" scenario.

## 7.3 Early-exit checkpoints (skip costly downstream steps)

These checkpoints short-circuit work that would be wasted given strong
evidence. Evaluated with a small safety margin (`threshold + 0.05`) to avoid
cutting marginal cases.

| Checkpoint | Lane | Where | Condition | Skips |
|---|---|---|---|---|
| `S_after_retrieval_high` | STANDARD | After parallel retrieval, before re-decomp | `S_raw ≥ 0.85` Y `n_sources ≥ 3` Y `C_no_conflict == 1.0` | Re-decomposition (§5.3) |
| `judge_first_pass_strong` | STANDARD | After first judge, before deep-fetch | `judge.verdict == approve` Y `final_confidence ≥ threshold + 0.05` Y `shallow_claims == []` | Deep-fetch and re-judge |
| `hypothesis_decisively_supported` | DEEP | After each `AgentObservation` | 1 hypothesis `confirmed` Y `S_effective ≥ threshold` Y rest refuted | Terminates ReAct early → `judge_confirmed` |
| `hypotheses_all_refuted` | DEEP | Inside ReAct loop | All hypotheses `refuted` with `primary_authoritative` evidence | Terminates ReAct → `stopped_by_budget` + `best_effort` |
| `cove_no_contradictions` | DEEP | After first CoVe pass | 0 contradictions Y `j_score ≥ threshold` | CoVe re-draft |

## 7.4 Hard caps (safety floors, no longer the decision)

Since BRD-26 the hard caps are **floors that guarantee termination**, not the
mechanism that *decides* termination. The agentic meta-judge in §7.6 owns
the decision ("is another round worth it?"); the cap only fires when the
meta-judge has already said `continue` N times in a row.

| Cap | Default | Lane(s) | On reach |
|---|---|---|---|
| `max_redecomposition` | 1 (STANDARD), 2 (DEEP) | STANDARD | Force synthesis with current evidence |
| `max_judge_attempts` | 3 (single default in `RunState`) | STANDARD, DEEP | Invoke `draft_best_effort_fallback`. The meta-judge usually stops earlier; this cap is the safety floor when meta-judge keeps returning `continue`. |
| `max_deep_fetch_per_run` | 2 (STANDARD), 3 (DEEP) | STANDARD, DEEP | Accept shallow evidence |
| `max_react_steps` | 8 | DEEP | Force synthesis with ReAct history |
| `max_cove_rounds` | 1 | DEEP | Accept draft without further verification |

## 7.5 Agentic stopping decision — VoC + AC meta-judge (BRD-26)

The stopping decision is **delegated to a small LLM reasoning step** that
runs after every standard candidate-stop point. It does **not** replace the
judge of §9 — the judge owns *is-the-draft-supported*, the meta-judge owns
*is-another-round-worth-it*. Two distinct LLM responsibilities, two distinct
prompts, two distinct persisted events.

**Where it lives (actual code):** a single helper
[`maybe_run_meta_judge`](../../backend/app/agent/meta_judge_hook.py) in
`app/agent/meta_judge_hook.py`, invoked imperatively from the orchestrator
(STANDARD `after_judge`) and the DEEP lane (`after_cove`). It is **not**
implemented as a `StoppingSignal` plugin — keeping it lane-aware and on the
orchestrator side avoided a synthetic adapter for the DEEP CoVe pre-judge
call site, which has no `JudgeRuled` event to react to. The underlying LLM
calls (`evaluate_value_of_continuation`, `generate_adversarial_objections`)
live in [`app/llm/meta_judge.py`](../../backend/app/llm/meta_judge.py) and
go through the standard `app/llm/client.py::call` router, same model family
as the judge by default (`anthropic/claude-sonnet-4-6` in V1).

**Opt-in default.** `settings.meta_judge_enabled` defaults to **`False`**.
The feature is dark-launched: events, helper and tests ship together but
production rollout is one env var (`META_JUDGE_ENABLED=true`) away. The
`meta_judge_min_delta_s` threshold (default `0.03`) is also a setting.

### 7.5.1 Hook points per lane

| Lane | Hook | Status | When |
|---|---|---|---|
| FAST | none | n/a | Cost-prohibitive — FAST only spends 2 LLM calls; the existing mini-judge already plays the binary stop role at the right cost level. |
| STANDARD | `after_judge` | ✅ implemented | Right after `JudgeRuled`, **before** evaluating `max_judge_attempts`. Orchestrator calls `maybe_run_meta_judge(state, emit, judge_event, hook="after_judge")`. |
| DEEP | `after_cove` | ✅ implemented | After the explicit CoVe pass and **before** the mini-judge. The lane synthesises a `_CoveSignal` placeholder (`passed=False`, current `judge_confidence` / `structural_confidence` from `RunState`, rationale `"after_cove pre-judge: no judge ruling yet on this draft"`) so the hook helper signature stays uniform across hooks. |
| DEEP | `after_react_observation` | ⏸ deferred | The `MetaJudgeHook` enum already accepts the value, but the call site inside the ReAct loop is **not** wired yet pending a cost gate (per-step LLM call needs `max_meta_judge_calls` cap + `meta_judge_min_step_delta` gate + lane-aware activation, e.g. `react_steps_so_far >= 2`). Until then, ReAct still terminates exclusively via `max_react_steps`, `hypothesis_decisively_supported` and `hypotheses_all_refuted`. |

Happy-path skip conditions (all evaluated at the top of `maybe_run_meta_judge`):

1. `settings.meta_judge_enabled is False` → `skipped`.
2. `state.selected_lane == Lane.FAST` → `skipped`.
3. `judge_signal.passed is True` → `skipped` (the cheap path already terminated).
4. `state.judge_attempts >= state.max_judge_attempts` → `skipped` (cap will fire next; the hard floor owns the stop).

### 7.5.2 Value of Continuation (VoC)

First meta-judge pass. Asks: *"If we ran one more round, what concrete
search would we issue, and what is the expected gain on `S_effective`?"*

Returns a structured `ValueOfContinuationVerdict` persisted as a
`MetaStopVerdict` event:

| Field | Meaning |
|---|---|
| `decision` | `stop` / `continue` / `stop_best_effort` |
| `expected_delta_s` | Realistic estimate of how much `S_effective` would move with one more round, in `[0, 1]` |
| `next_action_hypothesis` | A **concrete** next query, or `null` if the model cannot name one |
| `reason` | One-sentence English rationale, persisted verbatim |

Decision rules (applied in order inside the prompt):

1. No concrete `next_action_hypothesis` → `stop_best_effort`.
2. `expected_delta_s < 0.03` → `stop_best_effort`.
3. `S_effective ≥ threshold` AND judge approved → `stop`.
4. Otherwise → `continue`.

### 7.5.3 Adversarial Completeness (AC)

Fires **only** when VoC returns `continue` with `expected_delta_s ≥ 0.03`.
Asks the same model to play **skeptical reviewer**: produce exactly 3
different objections against the current draft, each classified as:

- `answered_by_evidence` — existing cited evidence already covers it; the
  evidence ids that answer it are listed.
- `unanswered_needs_search` — a new search could answer it; carries a
  `suggested_query` (≤ 6 tokens, query-hygiene rules from §3.2).
- `unanswered_no_search_possible` — real objection, but no available source
  can decide it (e.g. requires non-public data).

Persisted as `AdversarialObjectionsGenerated`. Two outcomes:

- **All 3 answered** (`ac.all_answered is True`) → helper returns
  `"confirm"`. Caller maps this to `STOP{JUDGE_CONFIRMED}` regardless of
  `judge_attempts`. The strongest possible "we are done" signal: the LLM
  was asked to attack the draft and failed.
- **Any `unanswered_needs_search` objection** → mint one new `SubClaim`
  per actionable objection and append it to `state.sub_claims` (status
  `"pending"`). The sub-claim text is the objection's `suggested_query`
  when present, otherwise the objection text. Emit
  `DirectedSubclaimsFromObjections { objection_texts[], new_subclaim_ids[] }`,
  then return `"continue"`; the orchestrator's regular flow drives
  `ANALYZING → SEARCHING` for the next directed round. The minting is
  **lane-uniform** in V1: both STANDARD and DEEP append `SubClaim` entries.
  Per-hypothesis routing in DEEP (token-overlap matching against pending
  `Hypothesis` entries) is on the BRD-26 backlog but **not** implemented.
- **All objections `unanswered_no_search_possible`** → helper returns
  `"continue"` with no new sub-claims (nothing to direct toward). The hard
  caps (`max_judge_attempts`, `max_searches`) own the eventual stop.

### 7.5.4 Cost

- STANDARD: +1 VoC call per non-happy-path round; +1 AC call only when VoC
  said `continue` with `expected_delta_s ≥ meta_judge_min_delta_s`.
  Telemetry target: `meta_judge_calls_per_run ≤ 3`.
- DEEP `after_cove`: +1 VoC call per CoVe pass; +1 AC call on the same
  conditions as STANDARD.
- DEEP `after_react_observation`: **0 calls today** (hook deferred — see
  §7.5.1). When wired, it will add ≤ 8 VoC calls per run, gated by the
  cost knobs described above.

Absorbed by the Anthropic Claude provider in V1 (well within tier-1 Anthropic rate limits). Any LLM error inside the
meta-judge is caught and downgraded to `"skipped"` — the meta-judge can
never block a run.

### 7.5.5 Replay determinism (RF-08)

Every meta-judge output is persisted verbatim. On read, the FE renders from
the event log; the meta-judge is **never** re-invoked. Forking from a point
**before** a `MetaStopVerdict` re-runs the meta-judge on the fork — that is
the intended fork semantics (replay = read, fork = re-run).

## 7.6 The four `stop_reason` enum values

All lanes terminate in one of:

- `judge_confirmed`
- `stopped_by_budget`
- `user_cancelled`
- `errored`

> **Why no `honest_*` values.** The earlier enum had `honest_contradiction`,
> `honest_unanswerable` and `honest_ambiguous`. They were removed in WP-3
> (always-answer refactor). Honest finals are now expressed as
> `stopped_by_budget` with `answer_kind = best_effort` and a descriptive
> `stop_rationale`. The UI distinguishes the case via the best-effort badge.

---

# Phase 8 — Drafting an Answer (`SYNTHESIZING`)

The synthesizer LLM (`anthropic/claude-sonnet-4-6`) emits a `DraftSynthesized` event.

## 8.1 Shape follows `AnswerKind`

- `direct` → short paragraph, single citation cluster.
- `comparative` → two-column tradeoff with shared dimensions.
- `weighted` → criteria-weighted table.
- `best_effort` → explicit acknowledgement of ambiguity + best-attempt sketch.
- `scenario` → multiple labelled scenarios with stated assumptions. In DEEP,
  the skeleton is the list of `Hypothesis.verdict == confirmed` from §3.5.

The shape is enforced by a Pydantic `StructuredAnswerData` model — the LLM
cannot return free-form prose when a structured shape is required.

## 8.2 Citations inline

Every claim in the draft carries citations attached to specific
`AnalyzedEvidence` ids. The FE renders them as inline chips.

## 8.3 Language

The draft is generated in the **user's language** (Spanish by default for this
project). Internal prompts, identifiers and logs stay in English.

---

# Phase 9 — Judging the Draft (`JUDGING`)

A verifier LLM — in V1 the **same family** as the synthesizer
(`anthropic/claude-sonnet-4-6`) — verifies the
draft. The cross-family verification originally planned (DeepSeek judge vs
OpenAI synthesizer) is **deferred** in V1; the R6 mitigation now relies on
an adversarial judge prompt plus the `min(S, J)` cap (see
[ai-services.md §1.3](../technical-phase/ai-services.md)). The provider-agnostic
interface supports swapping per-role to `google/gemini-2.5-flash`,
`openai/gpt-5` or a GitHub-Models route via env vars when stronger
independence is needed.

The `JudgeRuled` event carries a structured `JudgeVerdict`:

| Field | Meaning |
|---|---|
| `sufficient` | Is the evidence sufficient for this `AnswerKind`? |
| `supported` | Is every claim backed by cited evidence? |
| `contradictions_detected[]` | Specific contradictions the judge spotted |
| `supported_but_shallow_claim_ids[]` | Claims supported only by snippets — candidates for deep-fetch |
| `j_score` | Judge confidence in [0, 1] |

## 9.1 Final confidence (logged, not gating)

```
final_confidence = min(S_effective, J)
```

This is the rule from RF-12. The lower of structural and judge confidence
wins. The judge cannot raise confidence above what the evidence structurally
supports.

Since commit C2 (2026-05-28), `final_confidence` is **recorded as a metric
on the `Stopped` event and shown in the UI**, but it is **not** re-checked
as a stopping gate — the judge LLM owns the approve/reject call (§7).

## 9.2 Best-effort fallback (BRD-26-aware)

The judge can reject a draft. When that happens the orchestrator first runs
the meta-judge (§7.5) — which now owns the loop-or-stop decision — and only
loops back to `ANALYZING` (or `SEARCHING` if deep-fetch §10 applies) when
the meta-judge says `continue`. `max_judge_attempts` (default `3`) remains
as the absolute safety floor (see §7.4).

There are now **two routes** into the best-effort fallback on STANDARD:

1. **Meta-judge route (preferred).** VoC returns `stop_best_effort`
   (saturation: no concrete next action, or `expected_delta_s < meta_judge_min_delta_s`).
   The `stop_rationale` quotes `ValueOfContinuationVerdict.reason`
   verbatim — the user sees *why* we stopped, not just *that* we stopped.
2. **Hard-cap route (safety floor).** `judge_attempts` reaches
   `max_judge_attempts` while the meta-judge is still saying `continue`.
   The `stop_rationale` cites the cap.

On DEEP the `after_cove` hook reuses the same outcomes but takes a
shorter path: `stop_best_effort` sets `state.final_answer = draft_text`,
`state.budget_exhausted_kind = "react_steps"` and returns
`StopReason.STOPPED_BY_BUDGET` directly from the lane; `confirm` returns
`StopReason.JUDGE_CONFIRMED` and skips the mini-judge entirely. The lane
does not currently route through `draft_best_effort_fallback` — the DEEP
draft already exists at that point.

On STANDARD, both routes invoke `draft_best_effort_fallback(state)`, which:

1. Reuses the synthesizer system prompt with a *FALLBACK MODE* directive.
2. Pins `AnswerKind.BEST_EFFORT` so the UI can render the distinct
   *best-effort* badge (`CenterPanelView` warning banner) instead of
   presenting the answer as confirmed.
3. Structures the reply in 4 explicit parts: what evidence we have / what
   we couldn't confirm **and why we couldn't confirm it** (populated from
   the meta-judge `reason` on the meta-judge route) / our best current
   take / what specific new evidence would close the gap.

The run terminates as `STOPPED_BY_BUDGET` **with an honest best-effort
answer**, not a silent failure.

## 9.3 Explicit CoVe in DEEP (IP-25 Phase F)

For `lane == DEEP` only, after the ReAct loop produces a draft the lane
runs a **literal CoVe pass** — not the implicit verification the judge
already performs, but a separate cycle, **before** the mini-judge:

1. The synthesizer (`claude-sonnet-4-6`) generates **3 verification questions**
   targeting specific claims in the draft. Emits
   `VerificationQuestionsGenerated { questions[] }`.
2. For each question, the **judge** (same Claude tier in V1 — cross-family
   verification deferred) runs a small directed search via the `Source` seam and
   returns whether the new evidence contradicts the draft.
3. If ≥ 1 question detects contradiction AND `cove_rounds < max_cove_rounds`
   (default 1), `CoveContradictionDetected` is emitted and the synthesizer
   re-drafts with the contradicting evidence as context. Loop bounded by
   `max_cove_rounds`.
4. The lane then evaluates the **`after_cove` meta-judge hook** (§7.5.1)
   on the post-CoVe draft. The hook can short-circuit into
   `STOPPED_BY_BUDGET` (best-effort), `JUDGE_CONFIRMED` (confirm) or fall
   through to the mini-judge as the regular path.
5. The judge verdict on the final draft (mini-judge if the hook fell
   through; otherwise the meta-judge outcome) is what the `Stopped`
   event records.

Rationale: the DEEP draft comes from a ReAct loop, not from pre-decomposed
sub-claims, so per-claim coverage is not guaranteed by construction the
way it is in STANDARD. CoVe restores that guarantee, and the `after_cove`
meta-judge layered on top decides whether the verified draft is good
enough to ship without spending another mini-judge call.

---

# Phase 10 — Deep-Fetch Escalation (conditional, IP-23 WP-2)

If the judge marks any claim as `supported_but_shallow`:

1. `maybe_deep_fetch` checks the deep-fetch budget from §1.2.
2. For each shallow claim, fetch the **full page text** of its citation URL via `Source.fetch_full(url)`.
3. Emit a `DeepFetchPerformed` event (additive).
4. Replace the snippet with the full text in the evidence index.
5. Transition `JUDGING → ANALYZING` (not `SEARCHING` — the URL is already known; another search round would waste budget).
6. Recompute confidence, re-draft, re-judge.

If the budget is exhausted, we accept the shallow evidence and proceed with
the lower confidence — honest is preferred over fabricated depth.

---

# Phase 11 — Stopping and Replay

## 11.1 The terminal event

The `Stopped` event carries everything needed to render the final view:

- `stop_reason` (one of the 4 enum values)
- `stop_rationale` (human-readable explanation)
- `answer_kind`
- `answer_prose` or `answer_structured_data`
- `final_confidence`
- `total_tokens`, `total_duration_seconds`

## 11.2 Determinism (RF-08)

Reading a stopped run never re-invokes the LLM. The FE renders directly from
the event log. Two visits, identical output.

## 11.3 Fork and resume

A run can be **forked from any past event** (append-only — the original is
never mutated). This is the "Runs Must Be Re-examinable" requirement: try a
different reasoning path from the same starting point and compare.

---

# Cross-Cutting Guarantees

These run continuously throughout the pipeline:

| Guarantee | Mechanism |
|---|---|
| **Append-only audit log** | `events` table, ~39 event types post IP-25 + BRD-26, additive schema (`extra="allow"`) |
| **SSE resume** | `Last-Event-ID`, 15 s heartbeat |
| **Read determinism** | No LLM on read paths |
| **Replay safety** | Fork/resume append; never mutate |
| **Trust surface** | FE renders every RF-13 signal (sources, tiers, confidence, dates, lane, hypotheses, ReAct steps) |
| **Single-writer per run** | In-process advisory lock; `uvicorn --workers 1` |
| **Provider-agnostic LLM call** | `app/llm/client.py::call` via litellm; supports Anthropic / Gemini / OpenAI / GitHub Models; V1 active = Anthropic only (`ANTHROPIC_API_KEY`) |
| **Provider quota fail-fast** | `LLMProviderQuotaExhausted` skips retry budget |
| **Parallel search within a round** | `asyncio.gather` over pending claims (IP-25 Phase 0) |
| **Lane isolation** | Each lane has its own state-machine path but shares the `Source` / `StoppingSignal` / `OutputRenderer` seams |

## Event taxonomy (post IP-25 + BRD-26)

The 11 events added by IP-25 + the 3 events added by BRD-26, all additive (RF-03):

| Event | Lane(s) | Phase reference |
|---|---|---|
| `RouteSelected` | all | §1.6 |
| `LaneEscalated` | FAST → STANDARD | §2.4 |
| `QueryReformulated` | all | §4.3 |
| `EchoChamberDetected` | all | §5.4 |
| `PlanGapsDetected` | STANDARD | §5.3 |
| `NoProgressDetected` | STANDARD + DEEP | §7.2 |
| `HypothesesGenerated` | DEEP + best-effort/scenario | §3.5 |
| `AgentThought` / `AgentAction` / `AgentObservation` | DEEP | §5.5 |
| `HypothesisEvaluated` | DEEP | §5.5 |
| `HistorySummarized` | DEEP | §5.5 |
| `VerificationQuestionsGenerated` / `CoveContradictionDetected` | DEEP | §9.3 |
| `MetaStopVerdict` | STANDARD + DEEP | §7.5.2 |
| `AdversarialObjectionsGenerated` | STANDARD + DEEP | §7.5.3 |
| `DirectedSubclaimsFromObjections` | STANDARD + DEEP | §7.5.3 |

---

# Mapping to the "Core Requirements" of a Modern Research System

| Requirement | How Novum implements it |
|---|---|
| **Decide when enough evidence is collected** | §7 stopping signals (hard floors + anti-stall + early-exit checkpoints) + §7.5 agentic meta-judge (VoC + AC, BRD-26) + §9 judge + §6 structural confidence (`min(S, J)`) |
| **Every run fully inspectable** | §0 event log + FE trust surface (RF-13) |
| **Runs re-examinable and re-attemptable** | §11.3 fork from any past event |
| **Handle messy reality** | §1.3 temporal sensitivity + §1.5 ambiguity resolver + §6 conflict component + `best_effort` ceiling + `stopped_by_budget` as success |
| **Match strategy to question shape** | §1.6 lane routing + per-lane composition (FAST = decomp + mini-CoVe; STANDARD = decomp + re-decomp + judge; DEEP = abductive + ReAct + explicit CoVe) |

---

# What Novum Does NOT Do (V1)

To keep the system honest, we list what is deliberately absent **after IP-25**:

| Capability | Status | Reason |
|---|---|---|
| **Vector DB / embeddings / semantic retrieval** | ❌ | Four Source plugins (Tavily + Wikipedia + Semantic Scholar + OpenAlex) provide enough heterogeneity for the assignment scope. |
| **RAG over private corpora** | ❌ | Out of scope; no document ingestion pipeline. |
| **Abductive hypothesis generation** | ✅ | Implemented in DEEP and for `causal/scenario/predictive_future/best_effort` (§3.5). |
| **Adaptive query reformulation mid-run** | ✅ | Low-relevance reformulation per claim per round (§4.3). Cap: 1 per claim per round. |
| **Adaptive plan (re-decomposition based on intermediate findings)** | ✅ | STANDARD re-decomp (§5.3), DEEP ReAct loop (§5.5). |
| **Explicit CoVe (separate from the judge)** | ✅ | DEEP only (§9.3). FAST has a mini-CoVe degraded version. STANDARD relies on the judge for verification. |
| **Long-term memory across runs** | ❌ | Each run is isolated. Memory across runs would break read determinism. |
| **Knowledge graph construction** | ❌ | Out of V1 scope. |
| **Multi-agent debate** | ❌ | One planner, one synthesizer, one judge, one meta-judge. The meta-judge plays a *skeptical reviewer* role (BRD-26 §7.5.3 Adversarial Completeness) but as a single reasoning step, not a debate. |
| **Agentic stopping decision (VoC + Adversarial Completeness)** | ✅ (opt-in) | BRD-26 (§7.5). STANDARD `after_judge` + DEEP `after_cove` wired; DEEP `after_react_observation` deferred pending cost gate. FAST stays with mini-judge for cost reasons. Disabled by default (`META_JUDGE_ENABLED=false`); flip the env var to activate. |
| **Tree-of-Thoughts** | ❌ | Quadratic cost not justified; ReAct + abductive hypotheses covers the multi-path exploration case. |
| **Real-time browser navigation** | ❌ | We fetch URLs (deep-fetch) but do not interact with pages. |
| **Distributed execution** | ❌ | Single server, single worker (RF-05). |

These are not bugs. They are scope decisions documented in the requirements
and the architecture phase.

---

# Architecture Pointers

- Strategy rationale (3-lane decision): [building-the-plan.md](building-the-plan.md)
- Phased rollout (Phase 0 → F): [IP-25](../implementation-phase/implementation-plans/IP-25-three-lane-research-flow.md)
- FSM and event taxonomy: [architecture.md](../technical-phase/architecture.md)
- LLM role assignments: [ai-services.md](../technical-phase/ai-services.md)
- Confidence formula: [confidence-calculation.md](confidence-calculation.md)
- Stopping policy: [stopping-signal-analysis.md](stopping-signal-analysis.md)
- Requirements catalogue: [requirement-understanding.md](requirement-understanding.md)
- UI mapping: [ui-prototype.md](ui-prototype.md)
