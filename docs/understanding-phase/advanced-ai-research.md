# How Novum Performs Research

This document describes the **exact research plan Novum executes for every
question**, in the order events are emitted. It is grounded in the current
codebase (post IP-23) and the requirements catalogue (RF-01..RF-19). Anything
not listed here is deliberately not implemented in V1 — see "What Novum does
NOT do" at the bottom.

The contract is simple:

- Every step emits an **append-only event** in PostgreSQL (`events.payload JSONB`).
- The UI right panel mirrors those events 1:1 (no live LLM regeneration on read — RF-08).
- The run is **fully replayable**: opening it twice shows identical output.
- Stopping is a **first-class success outcome**, not an error (RF-02).

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

---

# Phase 2 — Building the Plan (`PLANNING`)

The planner LLM emits a `PlanCreated` event with:

## 2.1 Sub-claim decomposition

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

## 2.2 Query hygiene (IP-23 WP-4)

Each sub-claim gets a search query that obeys four hygiene clauses:

1. **≤ 6 tokens** (measured with `tiktoken`).
2. **No boolean operators** (no `AND`, `OR`, `-term`).
3. **No redundant entities** already present in the previous query.
4. **Positive framing** (search for what we want, not what we want to exclude).

`query_length_tokens` is emitted per query — visible in the trace.

## 2.3 Source routing by temporal sensitivity (IP-23 WP-1)

- `static` / `slow_changing` → Wikipedia + Semantic Scholar first, Tavily second.
- `volatile` / `real_time` → Tavily first with `search_depth="advanced"` and `days` filter; Wikipedia + Semantic Scholar second.
- Semantic Scholar's recency filter is mapped from `days` to a `year` range (the API has no day-level filter).
## 2.4 Plan self-critique (`CRITIQUING`)

Before any external call is made, the LLM critiques its own plan:

- Are the sub-claims independent?
- Do they cover the question?
- Are the queries searchable?

If the critique fails, the planner regenerates **before** spending the search
budget.

---

# Phase 3 — Gathering Evidence (`SEARCHING`)

For each sub-claim, in order:

## 3.1 Three heterogeneous Sources (RF-04)

- **Tavily** web search — `search_depth="advanced"`, with `days` filter from §2.3.
- **Wikipedia** — encyclopedic baseline, second Source plugin.
- **Semantic Scholar** — academic graph API (`api.semanticscholar.org/graph/v1`).
  Returns peer-reviewed and preprint papers with citation counts, authors,
  venue and DOI. Free tier, no API key required (optional `S2_API_KEY` raises
  the rate limit). Provides high-weight evidence for science, medical and
  technical questions.

All three are interchangeable behind the `Source` Protocol (RF-01) and live
in [backend/app/sources/registry.py](../../backend/app/sources/registry.py).
Semantic Scholar hosts (`*.semanticscholar.org`, `doi.org`) are classified
`primary_authoritative` in the tier table below — evidence from this source
lands at ×1.30 on coverage and diversity.

## 3.2 What we capture per URL

Each `SourceResult` records:

- `title`, `url`, `snippet`
- `source_published_date` (when the page declares one)
- The host, normalised for tier classification

## 3.3 Authority tier classification (IP-23 WP-3)

Every result is classified into one of four tiers by host pattern:

| `AuthorityTier` | Examples | Multiplier on `C_coverage` + `C_diversity` |
|---|---|---|
| `primary_authoritative` | `*.gov`, `*.gov.*`, `*.gob`, `*.gob.*`, `*.mil`, `*.mil.*`, `*.int`, `*.edu`, `*.edu.*`, `*.ac.*`, `who.int`, `nih.gov`, `arxiv.org`, `*.semanticscholar.org`, `doi.org`, `ietf.org`, `iso.org`, peer-reviewed journals | × 1.30 |
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

## 3.4 Tool call accounting

Every external call emits a `ToolCalled` event with provider, latency, status
and tokens (where applicable). These feed the budget signals in §6.

## 3.5 LLM call routing

All LLM calls go through `app/llm/client.py::call`, which:

- Rotates across an **N-PAT pool** for GitHub Models (4 PATs in prod).
- Retries with **tenacity** + exponential backoff on transient errors.
- **Fails fast** on permanent quota errors from OpenAI / Anthropic / Google
  (`LLMProviderQuotaExhausted`) without burning the retry budget.

---

# Phase 4 — Analysing Evidence (`ANALYZING`)

## 4.1 Per-claim indexing

Each piece of evidence is attached to a specific sub-claim. The
`question_index` ensures isolation between runs — evidence from run A never
contaminates run B.

## 4.2 Evidence aggregation

`AnalyzedEvidence` events fold:

- Text snippet
- Citation
- `AuthorityTier`
- `source_published_date`
- The sub-claim it supports or contradicts

---

# Phase 5 — Structural Confidence (`S_raw`)

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
3. **Stale-citation penalty** (× 0.85 on `kind_ceiling["direct"]`) if citations are older than the temporal sensitivity threshold from §1.3.
4. `S_effective = S_raw × kind_ceiling[AnswerKind]` — caps confidence by what the question type can legitimately deliver.

`S_effective` is the **structural** half of the final score. The other half is
the judge's verdict (§8).

---

# Phase 6 — Stopping Signals (per round, RF-02)

After analysis and confidence are updated, the orchestrator checks every
configured `StoppingSignal` plugin:

1. **`BudgetExhaustedSignal`** — `max_rounds`, `max_searches`, `max_tokens` from §1.2.
2. **`ConfidenceThresholdSignal`** — `S_effective ≥ confidence_threshold` (default 0.70).
3. **`UserCancelledSignal`** — the FE asked us to stop.
4. **`JudgeConfirmedSignal`** — the judge approved the draft (set in §8).

If **none** fire, the orchestrator schedules another round of `SEARCHING` →
`ANALYZING`. If any fires, we move to `SYNTHESIZING`.

The stop is mapped to one of **four** enum values (post 2026-05-27 amendment):

- `judge_confirmed`
- `stopped_by_budget`
- `user_cancelled`
- `errored`

A `stopped_by_budget` with low confidence is still a **success** — the user
sees the partial findings, the confidence number, and the reason. We never
fabricate certainty to "finish".

---

# Phase 7 — Drafting an Answer (`SYNTHESIZING`)

The synthesizer LLM emits a `DraftSynthesized` event:

## 7.1 Shape follows `AnswerKind`

- `direct` → short paragraph, single citation cluster.
- `comparative` → two-column tradeoff with shared dimensions.
- `weighted` → criteria-weighted table.
- `best_effort` → explicit acknowledgement of ambiguity + best-attempt sketch.
- `scenario` → multiple labelled scenarios with stated assumptions.

The shape is enforced by a Pydantic `StructuredAnswerData` model — the LLM
cannot return free-form prose when a structured shape is required.

## 7.2 Citations inline

Every claim in the draft carries citations attached to specific
`AnalyzedEvidence` ids. The FE renders them as inline chips.

## 7.3 Language

The draft is generated in the **user's language** (Spanish by default for this
project). Internal prompts, identifiers and logs stay in English.

---

# Phase 8 — Judging the Draft (`JUDGING`)

A **second, independent LLM** (Anthropic Haiku — RF-19) verifies the draft.
This is the verifier model the literature recommends.

The `JudgeRuled` event carries a structured `JudgeVerdict`:

| Field | Meaning |
|---|---|
| `sufficient` | Is the evidence sufficient for this `AnswerKind`? |
| `supported` | Is every claim backed by cited evidence? |
| `contradictions_detected[]` | Specific contradictions the judge spotted |
| `supported_but_shallow_claim_ids[]` | Claims supported only by snippets — candidates for deep-fetch |
| `j_score` | Judge confidence in [0, 1] |

## 8.1 Final confidence

```
final_confidence = min(S_effective, J)
```

This is the rule from RF-12. The lower of structural and judge confidence
wins. The judge cannot raise confidence above what the evidence structurally
supports.

---

# Phase 9 — Deep-Fetch Escalation (conditional, IP-23 WP-2)

If the judge marks any claim as `supported_but_shallow`:

1. `maybe_deep_fetch` checks the deep-fetch budget from §1.2.
2. For each shallow claim, fetch the **full page text** of its citation URL via `Source.fetch_full(url)`.
3. Emit a `DeepFetchPerformed` event (event type #25, additive).
4. Replace the snippet with the full text in the evidence index.
5. Transition `JUDGING → ANALYZING` (not `SEARCHING` — the URL is already known; another search round would waste budget).
6. Recompute confidence, re-draft, re-judge.

If the budget is exhausted, we accept the shallow evidence and proceed with
the lower confidence — honest is preferred over fabricated depth.

---

# Phase 10 — Stopping and Replay

## 10.1 The terminal event

The `Stopped` event carries everything needed to render the final view:

- `stop_reason` (one of the 4 enum values)
- `stop_rationale` (human-readable explanation)
- `answer_kind`
- `answer_prose` or `answer_structured_data`
- `final_confidence`
- `total_tokens`, `total_duration_seconds`

## 10.2 Determinism (RF-08)

Reading a stopped run never re-invokes the LLM. The FE renders directly from
the event log. Two visits, identical output.

## 10.3 Fork and resume

A run can be **forked from any past event** (append-only — the original is
never mutated). This is the "Runs Must Be Re-examinable" requirement: try a
different reasoning path from the same starting point and compare.

---

# Cross-Cutting Guarantees

These run continuously throughout the pipeline:

| Guarantee | Mechanism |
|---|---|
| **Append-only audit log** | `events` table, ~25 event types, additive schema (`extra="allow"`) |
| **SSE resume** | `Last-Event-ID`, 15 s heartbeat |
| **Read determinism** | No LLM on read paths |
| **Replay safety** | Fork/resume append; never mutate |
| **Trust surface** | FE renders every RF-13 signal (sources, tiers, confidence, dates) |
| **Single-writer per run** | In-process advisory lock; `uvicorn --workers 1` |
| **N-PAT rotation** | `GITHUB_TOKENS` env, round-robin per call |
| **Provider quota fail-fast** | `LLMProviderQuotaExhausted` skips retry budget |

---

# Mapping to the "Core Requirements" of a Modern Research System

| Requirement | How Novum implements it |
|---|---|
| **Decide when enough evidence is collected** | §6 stopping signals + §8 judge + §5 structural confidence (`min(S, J)`) |
| **Every run fully inspectable** | §0 event log + FE trust surface (RF-13) |
| **Runs re-examinable and re-attemptable** | §10.3 fork from any past event |
| **Handle messy reality** | §1.3 temporal sensitivity + §1.5 ambiguity resolver + §5 conflict component + `best_effort` ceiling + `stopped_by_budget` as success |

---

# What Novum Does NOT Do (V1)

To keep the system honest, we list what is deliberately absent:

| Capability | Status | Reason |
|---|---|---|
| **Vector DB / embeddings / semantic retrieval** | ❌ | Three Source plugins (Tavily + Wikipedia + Semantic Scholar) provide enough heterogeneity for the assignment scope. |
| **RAG over private corpora** | ❌ | Out of scope; no document ingestion pipeline. |
| **Abductive hypothesis generation** | ❌ | Deep-fetch is reactive (escalates on judge feedback), not generative. |
| **Adaptive query reformulation mid-run** | ❌ | Queries are decided at plan time and not rewritten based on intermediate findings. |
| **Long-term memory across runs** | ❌ | Each run is isolated. Memory across runs would break read determinism. |
| **Knowledge graph construction** | ❌ | Out of V1 scope. |
| **Multi-agent debate** | ❌ | One planner, one synthesizer, one judge. No adversarial agents. |
| **Real-time browser navigation** | ❌ | We fetch URLs (deep-fetch) but do not interact with pages. |
| **Distributed execution** | ❌ | Single server, single worker (RF-05). |

These are not bugs. They are scope decisions documented in the requirements
and the architecture phase.

---

# Architecture Pointers

- FSM and event taxonomy: [architecture.md](../technical-phase/architecture.md)
- LLM role assignments: [ai-services.md](../technical-phase/ai-services.md)
- Confidence formula: [confidence-calculation.md](confidence-calculation.md)
- Stopping policy: [stopping-signal-analysis.md](stopping-signal-analysis.md)
- Requirements catalogue: [requirement-understanding.md](requirement-understanding.md)
- UI mapping: [ui-prototype.md](ui-prototype.md)
