# BRD-23: Research-Quality Improvements — Temporal Awareness, Source Authority, Deep Fetch, Query Hygiene

**Document ID:** BRD-23
**Version:** 1.1
**Status:** Draft (F1 — awaiting Auditor; open questions resolved by PO)
**Author:** BSA Agent
**Date:** 2026-05-27
**Implementation Order:** 23 of N

---

## 1. Executive Summary

BRD-22 made the agent **cheap on trivial questions and expert-aware on non-trivial ones**. The four work packages in this BRD make the agent **honest about time, faithful to source quality, willing to look deeper when needed, and concise in how it asks the web** — four research-quality levers borrowed from Anthropic's published research-method writeups (decompose → broad-then-narrow → critique → tiered sources).

Each WP is **independently shippable** (separate User Story, separate IP). Together they tighten the four signals the existing pipeline already produces — coverage `C_coverage`, agreement `C_agreement`, diversity `C_independence`, judge `J` — without adding a new FSM state, a new plugin seam, or a new infrastructure dependency.

- **WP1 — Temporal sensitivity.** A 4-valued classifier hint (`static | slow_changing | volatile | realtime`) that drives source selection, Tavily date filters, and a per-`AnswerKind` confidence ceiling adjustment when citations are stale on volatile topics. Additive field on `QuestionClassifiedEvent`; mirrored on `PlanCreatedEvent`; consumed by judge.
- **WP2 — Deep-fetch escalation.** Optional `fetch_full(url, *, timeout)` method on the existing `Source` protocol (default `None` for backward compat), implemented for Tavily (via `extract`) and Wikipedia (full article body). Triggered when the judge flags a critical-path claim as *supported but shallow* AND the snippet is below a configurable threshold. Bounded by complexity (0 / 2 / 3). New event `DeepFetchPerformed`.
- **WP3 — Source-authority tiering.** Static domain → tier table (`primary_authoritative | reputable_secondary | general | low_signal`) used as a **multiplier on the diversity/coverage component of `S_raw` only**. `final_confidence = min(S_effective, J)` invariant (RF-12) is preserved — the change is internal to `S`. Adds `tier` as an optional field on `EvidenceAddedEvent` for trace UX. The formula amendment lives in [confidence-calculation.md](../../understanding-phase/confidence-calculation.md) and is **flagged** here, not written here.
- **WP4 — Query hygiene.** A planner system-prompt constraint (≤ 6 words per query, no stop-words except technical connectors, quotes only for required exact matches) and a new optional `query_length_tokens` field on the existing `ToolCalledEvent` for observability. No new event types.

Binding success metrics live in §11. The expected outcome is a measurable drop in residual-contradiction rate and low-tier source ratio without any latency regression on trivial paths (BRD-22 baseline preserved).

> **Assumption flagged for Auditor.** The user prompt referenced a `SearchQueryEmitted` event. The current code emits one event per search call: `ToolCalledEvent` (`EventType.TOOL_CALLED`), which already carries `query`. WP-4 attaches `query_length_tokens` to that event. If the Auditor or PO prefers a dedicated new event type, the change is mechanical and additive — but **the default in this BRD is to extend `ToolCalledEvent`** to honour the *"no new event types in WP-4"* constraint.

---

## 2. RF Traceability

All RFs interpreted under the **Amendment 2026-05-27** (`stop_reason` is the 4-value enum `judge_confirmed | stopped_by_budget | user_cancelled | errored`; no `honest_*` short-circuit; `AnswerKind` taxonomy applies; `final_confidence = min(S_effective, J)`).

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-01·A / RF-01·D | Layered stopping (coverage + agreement + judge) | **Extends** — WP-3 modulates the diversity/coverage component of `S_raw` by source authority; WP-2 raises evidence quality for critical-path claims before judge re-evaluates. Gate definitions unchanged. |
| RF-04 (messy reality / heterogeneity / source failure) | Cross-source agreement & cascading fallback | **Extends** — WP-1 lets the planner prefer Tavily over Wikipedia for volatile/realtime topics and inject `days=N` date filters. WP-2 adds an optional escalation path (snippet → full page) inside the existing `Source` seam. |
| RF-06 (question-type classification) | Five supported types | **Extends** — WP-1 enriches the classifier output with `temporal_sensitivity`. Question-type taxonomy unchanged. |
| RF-06-quater (UI as trust contract) | Trust surfaces | **Extends** — `temporal_sensitivity`, `DeepFetchPerformed` and `tier` are all rendered in the trace panel (RF-13). |
| RF-12 (`final_confidence = min(S_effective, J)`) | Confidence formula invariant | **Preserved unchanged.** WP-3's multiplier acts on `C_independence` / `C_coverage` inputs to `S_raw`, then `S_effective = S_raw · kind_ceiling[AnswerKind]` as today. The `min(·, J)` aggregator is untouched. WP-1 adjusts `kind_ceiling` for `static` answers with stale citations on volatile topics — this is a **per-`AnswerKind` ceiling tweak**, not a new aggregation. |
| RF-17 (`AnswerKind`) | Six-template synthesis | **Preserved** — no AnswerKind is added or removed. |
| RF-18 (saturation) | Embedding novelty signal | **Untouched.** |
| RF-19 (judge on different provider) | Anthropic Haiku judge | **Untouched.** WP-1's judge prompt change is additive (penalize stale citations on volatile topics); no provider change. |

**RFs flagged for text amendment** in `requirement-understanding.md` (BSA flags; the amendment is a separate doc-only PR):

1. **RF-01·A / RF-04** — list `temporal_sensitivity` and the deep-fetch escalation among the sanctioned planner inputs.
2. **RF-06-quater** — add `temporal_sensitivity` badge, `DeepFetchPerformed` entry, and `tier` chip on citations to the enumerated trust-surface elements.
3. **RF-12 / confidence-calculation.md** — add an amendment subsection: `C_independence` and `C_coverage` are multiplied by a per-evidence-row `authority_tier_multiplier ∈ [0.5, 1.05]` before being weighted into `S_raw`. The `min(S_effective, J)` invariant is **preserved**.

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-05 (LLM client) | WP-1 (classifier prompt), WP-4 (planner prompt) — all routed via `app/llm/client.py::call`. |
| BRD-06 (Source plugins — Tavily + Wikipedia) | WP-2 (extend the `Source` protocol). |
| BRD-07 (Agent FSM) | WP-2 deep-fetch trigger lives inside `Searching` / `Critiquing`; **no new FSM state**. |
| BRD-08 (Confidence calculation) | WP-3 multiplier wires through `calculate_diversity` / `calculate_coverage`. |
| BRD-22 (Complexity hint) | WP-2 deep-fetch budget table is **keyed on `complexity_hint`** (mirrors BRD-22 ladder). |

No new env vars. No Alembic migration. No new external service. No new plugin seam — WP-2 extends the existing `Source` Protocol with an optional method.

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    domain/
      enums.py                        # MODIFY: +TemporalSensitivity, +AuthorityTier,
                                      #          +EventType.DEEP_FETCH_PERFORMED
      events.py                       # MODIFY: +temporal_sensitivity on QuestionClassifiedEvent,
                                      #          +temporal_sensitivity on PlanCreatedEvent,
                                      #          +tier on EvidenceAddedEvent,
                                      #          +query_length_tokens on ToolCalledEvent,
                                      #          +DeepFetchPerformedEvent (new event)
    agent/
      tasks/
        classify.py                   # MODIFY (WP-1): derive temporal_sensitivity heuristic
                                      #                + LLM prompt extension (1-line)
        plan.py                       # MODIFY (WP-1+WP-4): mirror temporal_sensitivity,
                                      #                      prefer Tavily on volatile/realtime,
                                      #                      inject Tavily days filter,
                                      #                      tighten query system prompt (WP-4)
        analyze.py                    # MODIFY (WP-3): pass authority_tier to confidence calcs
        draft.py                      # MODIFY (WP-1+WP-2): expose claim "supported_but_shallow"
                                      #                      flag in the judge response;
                                      #                      apply temporal penalty hook
        deep_fetch.py                 # NEW (WP-2): orchestrate the snippet→full-page escalation
      sources_authority/
        __init__.py                   # NEW (WP-3)
        tiers.py                      # NEW (WP-3): domain → AuthorityTier table + match() helper
    confidence/
      structural.py                   # MODIFY (WP-3): authority_tier_multiplier hook
                                      #                in C_coverage and C_independence inputs
      kind_ceiling.py                 # MODIFY (WP-1): stale-citation penalty for
                                      #                AnswerKind.direct on volatile topics
    seams/
      source.py                       # MODIFY (WP-2): add optional `fetch_full(url, *, timeout)`
                                      #                method to Source Protocol (default None)
    sources/
      tavily.py                       # MODIFY (WP-2): implement fetch_full via Tavily extract
      wikipedia.py                    # MODIFY (WP-2): implement fetch_full via full page extract
      registry.py                     # (no change — Source contract is structurally compatible)
    llm/
      prompts/
        planner.py                    # MODIFY (WP-4): query hygiene system-prompt clause
        classifier.py                 # MODIFY (WP-1): temporal_sensitivity instruction
        judge.py                      # MODIFY (WP-1): stale-citation penalty instruction
  tests/
    test_classify_temporal.py         # NEW (WP-1, US-23-1)
    test_plan_temporal_routing.py     # NEW (WP-1, US-23-1)
    test_sources_authority_tiers.py   # NEW (WP-3, US-23-3)
    test_confidence_authority_multiplier.py  # NEW (WP-3, US-23-3)
    test_deep_fetch_trigger.py        # NEW (WP-2, US-23-2)
    test_deep_fetch_budget.py         # NEW (WP-2, US-23-2)
    test_tavily_fetch_full.py         # NEW (WP-2, US-23-2)
    test_wikipedia_fetch_full.py      # NEW (WP-2, US-23-2)
    test_planner_query_hygiene.py     # NEW (WP-4, US-23-4)
    test_tool_called_query_length.py  # NEW (WP-4, US-23-4)

frontend/
  src/
    types/
      events.ts                       # REGENERATED via scripts/export_types.py
    components/
      atoms/
        TemporalSensitivityBadge.tsx  # NEW (WP-1)
        AuthorityTierChip.tsx         # NEW (WP-3)
      molecules/
        DeepFetchEntry.tsx            # NEW (WP-2, trace row)
      organisms/
        TracePanel.tsx                # MODIFY: render new badges, chips, and DeepFetch entries
```

### 4.2 Database Schema

**No migration required.** All state derives from the event log (RF-03 invariant). The new event type is just another `payload JSONB` row in `events`.

### 4.3 Alembic Migration

None.

### 4.4 Pydantic Models (all additive, `extra="allow"` preserved)

```python
# app/domain/enums.py (additive)
from enum import StrEnum

class TemporalSensitivity(StrEnum):
    STATIC = "static"               # Answer does not change once known (capitals, history dates).
    SLOW_CHANGING = "slow_changing" # Drifts over months/years (population estimates, top-X lists).
    VOLATILE = "volatile"           # Drifts within weeks (frameworks "best of 2026", market share).
    REALTIME = "realtime"           # Hours to a day (prices, news, sports scores).

class AuthorityTier(StrEnum):
    PRIMARY_AUTHORITATIVE = "primary_authoritative"  # *.gov, *.edu, WHO, ISO, IETF, peer-reviewed journals
    REPUTABLE_SECONDARY   = "reputable_secondary"    # wikipedia.org, encyclopedia.com, major news allow-list
    GENERAL               = "general"                # everything else not matched
    LOW_SIGNAL            = "low_signal"             # known content-mill / SEO-farm / forum domains

class EventType(StrEnum):
    # ... existing values unchanged ...
    DEEP_FETCH_PERFORMED = "DeepFetchPerformed"   # NEW (WP-2)
```

```python
# app/domain/events.py (additive fields, new event)

class QuestionClassifiedEvent(BaseEvent):
    # ... existing fields ...
    temporal_sensitivity: TemporalSensitivity | None = None      # NEW (WP-1)

class PlanCreatedEvent(BaseEvent):
    # ... existing fields ...
    temporal_sensitivity: TemporalSensitivity | None = None      # NEW (WP-1, mirrored)

class ToolCalledEvent(BaseEvent):
    # ... existing fields ...
    query_length_tokens: int | None = None                       # NEW (WP-4)
    tavily_days_filter: int | None = None                        # NEW (WP-1, optional)

class EvidenceAddedEvent(BaseEvent):
    # ... existing fields ...
    authority_tier: AuthorityTier | None = None                  # NEW (WP-3)
    source_published_date: datetime | None = None                # NEW (WP-1, used by judge stale-check)

class DeepFetchPerformedEvent(BaseEvent):                        # NEW (WP-2)
    """Snippet-to-full-page escalation triggered by judge `supported_but_shallow`."""
    model_config = ConfigDict(extra="allow")
    type: Literal[EventType.DEEP_FETCH_PERFORMED] = EventType.DEEP_FETCH_PERFORMED
    source_id: SourceType
    url: str
    triggered_by_claim_id: str
    fetch_ms: int
    content_length: int
    success: bool
    failure_reason: str | None = None
```

**Every new field is `X | None = None`.** **Every new event is additive.** No existing event is mutated destructively. Pre-BRD-23 traces replay without modification (verified by AC-09).

### 4.5 WP-1 — Temporal sensitivity (`classify` → `plan` → `judge`)

**Classifier (`classify.py`).** A deterministic heuristic runs **after** the LLM classifier verdict returns. No second LLM call.

```text
realtime       ⟺ contains markers in {"now", "current price", "today",
                                       "live", "right now", "this week"}
                OR question_type ∈ {STATE_OF_ART} AND length ≤ 8 words

volatile       ⟺ contains year markers within last 18 months
                OR question_type ∈ {STATE_OF_ART, COMPARATIVE}

slow_changing  ⟺ contains markers in {"population", "ranking", "top",
                                        "in 20XX", "as of"}

static         ⟺ default for FACTUAL / DEFINITIONAL question types
                AND no temporal marker detected
```

**Planner (`plan.py`).** Three additive behaviours, all gated by `temporal_sensitivity`:

| `temporal_sensitivity` | Source preference | Tavily `days` filter | Notes |
|---|---|---|---|
| `static`         | balanced (default) | None | No change vs. today. |
| `slow_changing`  | balanced           | `days=730` | 2-year window. |
| `volatile`       | **Tavily first**, Wikipedia second | `days=180` | 6-month window. |
| `realtime`       | **Tavily only**    | `days=7`   | Wikipedia is filtered out for evidence collection (still allowed as a definitional anchor). |

`tavily_days_filter` is recorded on each `ToolCalledEvent` for trace auditability.

**Judge (`judge.py`).** Prompt extension (English, additive 1-paragraph):

> *"If the question is volatile or realtime, treat any citation older than `days_filter * 2` as a soft penalty (lower `J` by up to 0.10). If every citation supporting a key claim is older than the date filter, flag that claim as `supported_but_shallow` so a deeper fetch can be attempted."*

**Kind ceiling (`kind_ceiling.py`).** When `AnswerKind == direct` AND `temporal_sensitivity ∈ {volatile, realtime}` AND ≥ 50 % of supporting evidence has `source_published_date` older than `days_filter`, multiply the existing `kind_ceiling["direct"]=1.00` by `0.85`. This **never raises** the ceiling — only lowers it for the demonstrably-stale case. Result `S_effective = S_raw · 0.85` instead of `S_raw · 1.00`. `min(·, J)` invariant unchanged.

### 4.6 WP-2 — Deep-fetch escalation (`Source.fetch_full` + budget)

**Protocol extension (`seams/source.py`).** Strictly additive:

```python
@runtime_checkable
class Source(Protocol):
    # ... existing ...
    async def fetch_full(self, url: str, *, timeout: float = 10.0) -> SourceResult | None:
        """Optional. Return full-page content for `url`, or None if not supported / failed.

        Default implementation (mixin in BaseSource): returns None. Implementations that
        cannot offer a deep fetch (or for which the snippet IS the full content) MUST
        keep returning None — the orchestrator treats None as 'no escalation possible'.
        """
        ...
```

`BaseSource` provides the default `async def fetch_full(...) -> None: return None`. **Existing sources continue to satisfy the Protocol without changes** — Architecture rule #1 (single `Source` seam) is preserved; **no parallel hierarchy** is introduced.

**Implementations.**

- **`tavily.py`** — uses Tavily's `extract` endpoint (`AsyncTavilyClient.extract(urls=[url])`). Returns a `SourceResult` with `content` = extracted markdown, truncated to `DEFAULT_MAX_CONTENT_CHARS * 4` (the existing snippet cap is 5000 chars; the deep cap is 20 000).
- **`wikipedia.py`** — uses the existing full-article HTML endpoint. The Wikipedia "snippet" already maps to the article summary (`extract`); deep fetch returns the full `extract` of the page (still cheap, no second API).

**Trigger.** Inside `analyze.py` after a `JudgeRuledEvent` is emitted with `passed == false` AND the judge response contains a `supported_but_shallow` flag on any covered claim:

```
for claim in judge.missing_evidence_or_shallow:
    if claim.is_critical_path        # claim is on the draft's outline
       and snippet_length < cfg.deep_fetch_min_snippet_chars   # default 400
       and deep_fetch_remaining[complexity] > 0:
        for ev in evidence_for(claim)[:cfg.deep_fetch_top_k]:  # default 2
            result = await source_for(ev).fetch_full(ev.source_url)
            emit DeepFetchPerformedEvent(...)
            if result: replace ev.extracted_text with deeper text
```

**Budget per complexity (mirrors BRD-22 ladder).**

| `complexity_hint` | Max `DeepFetchPerformed` per run |
|---|---:|
| `trivial`  | **0** |
| `standard` | **2** |
| `deep`     | **3** |

The counter is **recomputed from the event log** during `_fold_events` (per L-015: count of `DeepFetchPerformed` events on the current run) — no separate counter field on `RunState` that could drift on replay. Cancellation budget check fires at the top of the deep-fetch loop body.

**No new FSM state.** Deep fetch runs inside the existing `Analyzing` → `Critiquing` re-entry; the orchestrator's allowed-transitions table is untouched.

### 4.7 WP-3 — Authority tier multiplier on `S_raw`

**Static table (`sources_authority/tiers.py`).** Pure Python `dict` + suffix/regex rules. No I/O.

```python
_TIER_RULES: list[tuple[str, AuthorityTier]] = [
    # PRIMARY_AUTHORITATIVE
    (r"\.gov$",                       AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"\.gov\.[a-z]{2}$",             AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"\.edu$",                       AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"\.ac\.[a-z]{2}$",              AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^who\.int$",                   AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^nih\.gov$",                   AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^ietf\.org$",                  AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^iso\.org$",                   AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^arxiv\.org$",                 AuthorityTier.PRIMARY_AUTHORITATIVE),
    # REPUTABLE_SECONDARY
    (r"(^|\.)wikipedia\.org$",        AuthorityTier.REPUTABLE_SECONDARY),
    (r"^britannica\.com$",            AuthorityTier.REPUTABLE_SECONDARY),
    (r"^nytimes\.com$",               AuthorityTier.REPUTABLE_SECONDARY),
    (r"^bbc\.(com|co\.uk)$",          AuthorityTier.REPUTABLE_SECONDARY),
    (r"^reuters\.com$",               AuthorityTier.REPUTABLE_SECONDARY),
    (r"^apnews\.com$",                AuthorityTier.REPUTABLE_SECONDARY),
    # LOW_SIGNAL (deny-list — expanded seed; Reddit deliberately left in GENERAL)
    (r"^medium\.com$",                AuthorityTier.LOW_SIGNAL),
    (r"^quora\.com$",                 AuthorityTier.LOW_SIGNAL),
    (r"^answers\.com$",               AuthorityTier.LOW_SIGNAL),
    (r"^geeksforgeeks\.org$",         AuthorityTier.LOW_SIGNAL),
    (r"^w3schools\.com$",             AuthorityTier.LOW_SIGNAL),
    (r"^tutorialspoint\.com$",        AuthorityTier.LOW_SIGNAL),
    (r"^javatpoint\.com$",            AuthorityTier.LOW_SIGNAL),
    (r"\.blogspot\.com$",             AuthorityTier.LOW_SIGNAL),
    (r"\.wordpress\.com$",            AuthorityTier.LOW_SIGNAL),
    (r"\.substack\.com$",             AuthorityTier.LOW_SIGNAL),
]
# Fallback: AuthorityTier.GENERAL
```

The full initial table belongs to **US-23-3 Appendix A**.

**Multiplier (used inside `confidence/structural.py`).**

| `AuthorityTier`         | Multiplier on the evidence row's contribution to `C_coverage` and `C_independence` |
|---|---:|
| `PRIMARY_AUTHORITATIVE` | **1.05** |
| `REPUTABLE_SECONDARY`   | **1.00** |
| `GENERAL`               | **0.90** |
| `LOW_SIGNAL`            | **0.50** |

> **Asymmetry note.** The boost above baseline is intentionally small (`1.05`, not `1.10`) to keep `C_coverage`/`C_independence` from frequently saturating against the `[0, 1]` clamp. The penalty for `LOW_SIGNAL` (`0.50`) is intentionally large — empirically, blocking bad evidence improves S more than rewarding good evidence.

The multiplier applies **per evidence row** when summing into `C_coverage` (does this claim have enough *credible* evidence?) and `C_independence` (do we hear different *credible* voices?). After multiplication each component is **clamped to `[0.0, 1.0]`**. `C_agreement` and `C_no_conflict` are **unchanged** — authority is about *who*, not about *whether they agree*.

`S_raw` then enters the existing kind ceiling and `min(·, J)` aggregation exactly as today. **`final_confidence = min(S_effective, J)` is preserved (RF-12).** The formula amendment lives in [confidence-calculation.md](../../understanding-phase/confidence-calculation.md); this BRD only **flags** the change for that doc PR.

### 4.8 WP-4 — Query hygiene (prompt + observability field)

**Planner system-prompt addition (English, code-level):**

> *"Each search query you emit MUST satisfy:*
> *(a) at most 6 tokens (split by whitespace);*
> *(b) no stop-words ('the', 'a', 'an', 'of', 'in', 'on', 'for', 'is', 'are', 'was', 'were', 'to', 'with') except when they appear inside a quoted exact-match phrase;*
> *(c) quotes ONLY around an exact phrase whose precise wording is required to disambiguate — never around a whole query;*
> *(d) technical connectors ('vs', 'and', '+', '-', site filters like 'site:arxiv.org') are allowed and DO NOT count toward the 6-token cap.*"

**Validation.** The planner is also instructed: *"If your draft query violates (a)-(c), rewrite it once before emitting."* No hard rejection in code — soft guardrail via prompt + observability.

**Observability.** `ToolCalledEvent.query_length_tokens` is set by the orchestrator at emission time using `len(query.split())`. Trace UI shows a small chip when `query_length_tokens > 6` so we can spot drift.

### 4.9 API Endpoints

No new endpoints. Changes flow through the existing `POST /api/runs` and the SSE stream.

### 4.10 React Components

| Component | Path | Props | Notes |
|---|---|---|---|
| `TemporalSensitivityBadge` | `components/atoms/TemporalSensitivityBadge.tsx` | `value: TemporalSensitivity` | Renders next to `ComplexityBadge`. Microcopy: `Static fact` / `Slow-changing` / `Volatile topic` / `Real-time`. |
| `AuthorityTierChip` | `components/atoms/AuthorityTierChip.tsx` | `tier: AuthorityTier` | Shown on each citation. Microcopy: `Primary` / `Reputable` / `General` / `Low signal`. |
| `DeepFetchEntry` | `components/molecules/DeepFetchEntry.tsx` | `event: DeepFetchPerformedEvent` | New trace row: *"Fetched full page for «{title}» ({fetch_ms} ms, {content_length} chars)."* |
| `TracePanel` | `components/organisms/TracePanel.tsx` | (existing) | Adds three rendering branches: temporal badge in header, authority chip on citations, deep-fetch entry. |

### 4.11 UI Layout

No layout changes. New elements render inside existing **Center Panel** (header) and **Trace Panel** (citation list + event timeline). No new screens, no new states beyond what BRD-13/14 already define.

---

## 5. Acceptance Criteria

### AC-01 — Volatile topic gets Tavily first + 6-month filter (WP-1)
```gherkin
Given question "Best framework for LLM agents in 2026"
When a new run is started
Then QuestionClassifiedEvent.temporal_sensitivity == "volatile"
And  PlanCreatedEvent.temporal_sensitivity == "volatile"
And  The first emitted ToolCalledEvent has source_type == "tavily"
And  That ToolCalledEvent.tavily_days_filter == 180
```

### AC-02 — Static factual question keeps current behaviour (WP-1 regression)
```gherkin
Given question "What is the capital of Japan?"
When a new run is started
Then QuestionClassifiedEvent.temporal_sensitivity == "static"
And  No tavily_days_filter is set on emitted ToolCalledEvents
And  The BRD-22 trivial-path early-stop still fires (≤ 90 s wall-clock target)
```

### AC-03 — Realtime question excludes Wikipedia evidence (WP-1)
```gherkin
Given question "Current Bitcoin price right now"
When a new run is started
Then QuestionClassifiedEvent.temporal_sensitivity == "realtime"
And  No EvidenceAddedEvent with source_type == "wikipedia" is emitted
And  Tavily ToolCalledEvents carry tavily_days_filter == 7
```

### AC-04 — Stale citation lowers ceiling for direct AnswerKind on volatile (WP-1)
```gherkin
Given a run classified as temporal_sensitivity=="volatile"
And  All supporting evidence for the chosen direct answer is older than 12 months
When the synthesizer emits AnswerKind=="direct"
Then S_effective == S_raw * 0.85  (not S_raw * 1.00)
And  final_confidence == min(S_effective, J)  (RF-12 invariant preserved)
```

### AC-05 — Deep-fetch triggers when judge flags a shallow critical claim (WP-2)
```gherkin
Given complexity_hint == "standard"
And  The judge returns passed=false with missing_evidence containing claim "C1"
       flagged supported_but_shallow
And  Evidence for C1 has snippet length 220 (< 400 threshold)
When the orchestrator reacts to the judge ruling
Then At least one DeepFetchPerformedEvent is emitted with triggered_by_claim_id == "C1"
And  The deep-fetch counter for this run is now 1
And  No more than 2 DeepFetchPerformed events are emitted in this run
```

### AC-06 — Deep-fetch budget respects complexity (WP-2)
```gherkin
Given complexity_hint == "trivial"
When the judge flags any claim as supported_but_shallow
Then No DeepFetchPerformedEvent is ever emitted in this run
```

### AC-07 — Authority multiplier raises C_coverage for a .gov source (WP-3)
```gherkin
Given a covered claim with 2 evidence rows: one from nih.gov, one from a general blog
And  Both rows contribute base 0.50 to C_coverage before multipliers
When C_coverage is computed
Then nih.gov row contributes 0.525 (0.50 * 1.05)
And  general blog row contributes 0.45 (0.50 * 0.90)
And  C_coverage is clamped to <= 1.0
And  final_confidence == min(S_effective, J)  (RF-12 invariant preserved)
```

### AC-08 — Low-signal tier penalty hits C_independence (WP-3)
```gherkin
Given all 5 evidence rows for a claim come from medium.com posts
When C_independence is computed
Then each row's tier == "low_signal" and multiplier == 0.5
And  The clamped C_independence is at most 0.50
And  The trace shows AuthorityTierChip("Low signal") on every citation
```

### AC-09 — Pre-BRD-23 trace replays cleanly (schema compatibility)
```gherkin
Given a historical events.jsonl trace recorded before BRD-23
When the orchestrator replays it via _fold_events
Then No error is raised
And  Missing temporal_sensitivity, authority_tier, tavily_days_filter,
     query_length_tokens, DeepFetchPerformedEvent are tolerated as None / absent
And  All BRD-22 acceptance criteria still pass
```

### AC-10 — Planner emits short queries (WP-4)
```gherkin
Given any new run
When the planner emits search queries via ToolCalledEvent
Then In ≥ 90 % of emissions, query_length_tokens <= 6
And  Every ToolCalledEvent carries a non-null query_length_tokens value
```

### AC-11 — Deep-fetch failure is non-fatal (WP-2)
```gherkin
Given a deep-fetch call to Tavily.extract() raises a timeout
When the orchestrator handles the failure
Then DeepFetchPerformedEvent is emitted with success=false and failure_reason set
And  The run does NOT transition to ERRORED
And  The original snippet evidence remains in place
```

---

## 6. Implementation Checklist

- [ ] Enum additions — `backend/app/domain/enums.py` (`TemporalSensitivity`, `AuthorityTier`, `EventType.DEEP_FETCH_PERFORMED`).
- [ ] Event model additions — `backend/app/domain/events.py` (new optional fields + `DeepFetchPerformedEvent`).
- [ ] Classifier heuristic — `backend/app/agent/tasks/classify.py` (temporal sensitivity post-processing).
- [ ] Classifier prompt — `backend/app/llm/prompts/classifier.py` (1-line instruction).
- [ ] Planner routing + days filter — `backend/app/agent/tasks/plan.py`.
- [ ] Planner query-hygiene prompt — `backend/app/llm/prompts/planner.py`.
- [ ] `query_length_tokens` emission — `backend/app/agent/orchestrator.py` or wherever `ToolCalledEvent` is constructed.
- [ ] `Source` protocol extension — `backend/app/seams/source.py` + `backend/app/sources/base.py` default `fetch_full -> None`.
- [ ] `TavilySource.fetch_full` — `backend/app/sources/tavily.py`.
- [ ] `WikipediaSource.fetch_full` — `backend/app/sources/wikipedia.py`.
- [ ] Deep-fetch orchestration — `backend/app/agent/tasks/deep_fetch.py` + analyze.py hook.
- [ ] Deep-fetch fold contract — `backend/app/agent/run_state.py::_fold_events` recomputes per-run counter from event log.
- [ ] Authority tier module — `backend/app/agent/sources_authority/tiers.py`.
- [ ] Confidence multiplier wiring — `backend/app/confidence/structural.py` (`C_coverage`, `C_independence` only).
- [ ] Kind-ceiling stale-citation penalty — `backend/app/confidence/kind_ceiling.py`.
- [ ] Judge prompt extension — `backend/app/llm/prompts/judge.py` (stale-citation rule + `supported_but_shallow` flag).
- [ ] Frontend type regeneration — `python scripts/export_types.py` then commit `frontend/src/types/events.ts`.
- [ ] Frontend atoms — `TemporalSensitivityBadge.tsx`, `AuthorityTierChip.tsx`.
- [ ] Frontend molecule — `DeepFetchEntry.tsx`.
- [ ] Frontend organism extension — `TracePanel.tsx`.
- [ ] Backend unit tests — see §4.1 file list, ≥ 80 % coverage on new code.
- [ ] Frontend unit tests — `*.test.tsx` co-located, Vitest + RTL + jest-axe.
- [ ] Smoke run on Q1 (BRD-22 trivial) re-asserts no latency regression.

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (BE) | pytest | `app/agent/tasks/classify.py` (temporal), `app/agent/tasks/plan.py` (routing+queries), `app/agent/tasks/deep_fetch.py`, `app/agent/sources_authority/`, `app/confidence/structural.py`, `app/confidence/kind_ceiling.py`, `app/sources/{tavily,wikipedia}.py::fetch_full` | ≥ 80 % |
| Integration (BE) | pytest + mocked LLM + httpx mock | classify→plan→tool routing per temporal sensitivity; deep-fetch trigger end-to-end; authority multiplier end-to-end with synthetic evidence | Critical paths |
| Schema-compat (BE) | pytest | Replay one pre-BRD-23 JSONL fixture without errors (AC-09) | One fixture is sufficient |
| Unit (FE) | Vitest + RTL + jest-axe | `TemporalSensitivityBadge`, `AuthorityTierChip`, `DeepFetchEntry`, `TracePanel` extensions | ≥ 80 % |
| Smoke (prod) | `scripts/smoke_ip21.py` (existing) | Q1 still ≤ 90 s after BRD-23 lands | Q1 row only |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEP_FETCH_MIN_SNIPPET_CHARS` | No | `400` | Minimum snippet length below which a `supported_but_shallow` claim becomes a deep-fetch candidate. |
| `DEEP_FETCH_TOP_K`             | No | `2`   | Max number of `Source.fetch_full` calls per triggering claim. |
| `DEEP_FETCH_TIMEOUT_S`         | No | `10.0`| Per-call timeout passed to `fetch_full`. |
| `AUTHORITY_MULTIPLIER_PRIMARY` | No | `1.05`| Tunable for calibration. Small boost to avoid clamp saturation. |
| `AUTHORITY_MULTIPLIER_GENERAL` | No | `0.90`| Tunable. |
| `AUTHORITY_MULTIPLIER_LOW`     | No | `0.50`| Tunable. Asymmetric vs. primary on purpose. |
| `TEMPORAL_STALE_PENALTY`       | No | `0.85`| Multiplier on `kind_ceiling["direct"]` when ≥ 50 % of citations are older than the date filter on volatile/realtime questions. |
| `DEEP_FETCH_MAX_PER_RUN_DEEP`  | No | `3`   | Cap for `complexity_hint == deep`. Worst-case wall-clock add = `3 × DEEP_FETCH_TIMEOUT_S`. |

No secrets. All values configurable via `app/config.py`; tests use the defaults.

## 9. Schema Compatibility Statement

This BRD is **fully backward-compatible** with the event log (Architecture rule #5). The change set is:

**New optional fields (all `T | None = None`):**

| Event | Field | WP |
|---|---|---|
| `QuestionClassifiedEvent` | `temporal_sensitivity` | WP-1 |
| `PlanCreatedEvent` | `temporal_sensitivity` | WP-1 |
| `ToolCalledEvent` | `query_length_tokens` | WP-4 |
| `ToolCalledEvent` | `tavily_days_filter` | WP-1 |
| `EvidenceAddedEvent` | `authority_tier` | WP-3 |
| `EvidenceAddedEvent` | `source_published_date` | WP-1 |

**New event types (additive — replays without them tolerate absence):**

| Event | WP |
|---|---|
| `DeepFetchPerformedEvent` (`EventType.DEEP_FETCH_PERFORMED`) | WP-2 |

**New `Source` Protocol method:**

| Method | Default | WP |
|---|---|---|
| `fetch_full(url, *, timeout) -> SourceResult | None` | `return None` (in `BaseSource`) | WP-2 |

Every existing source — including any future user-supplied source — continues to satisfy the Protocol without modification. No event is removed, no field is renamed, no field changes type. **Per L-015**, the deep-fetch counter is recomputed during `_fold_events` from the count of `DeepFetchPerformed` events; no new `RunState` field carries hidden replay state.

## 10. Metrics to Validate the Improvement

### 10.1 Binding success metrics

| Metric | Baseline | Target | How verified |
|---|---|---|---|
| Residual-contradiction rate (`ContradictionDetected` without matching `ContradictionResolved`) on a 20-question dev set | TBD by smoke run pre-merge | **-30 %** | New `make eval` row or extension of `scripts/smoke_ip21.py`. |
| Mean queries per run on `trivial` complexity | BRD-22 baseline | **unchanged** (regression guard) | Smoke matrix Q1 latency ≤ 90 s. |
| Mean snippet length for evidence supporting any claim the judge flagged `supported_but_shallow` | TBD | **≥ 2×** after deep-fetch | Compare `len(extracted_text)` before vs. after deep-fetch on the same `target_claim_id`. |
| Ratio of `low_signal`-tier citations in any final answer | TBD | **≤ 5 %** | Aggregation over `EvidenceAddedEvent.authority_tier` filtered to evidence cited in the final answer. |

### 10.2 Secondary / observability metrics

| Metric | Target |
|---|---:|
| % of `ToolCalledEvent` with `query_length_tokens ≤ 6` | ≥ 90 % |
| % of `volatile`/`realtime` runs with at least one Tavily-first `ToolCalledEvent` | ≥ 95 % |
| Mean `DeepFetchPerformedEvent` count per `standard` run | ≤ 2 |
| % of `static` factual runs whose `kind_ceiling` was reduced by the temporal penalty | ≈ 0 % (sanity check; the penalty must NOT fire on static topics) |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Temporal heuristic mis-classifies a volatile topic as `static` → stale answer not penalised | Medium | Medium | Heuristic is conservative (default `static` only for FACTUAL/DEFINITIONAL with no year/marker); judge prompt also flags stale citations independently of the classifier hint. |
| Deep-fetch latency budget exceeded on `deep` complexity (3 × 10 s = 30 s added) | Low | Low | Cap reduced from 5 → 3 (worst case 30 s, not 50 s); each call is bounded by `DEEP_FETCH_TIMEOUT_S`; the trigger only fires when the judge has already flagged a critical-path claim — so the cost is paid only when it can move `passed` from false to true. |
| Tavily `extract` endpoint rate-limit hit on the free tier | Medium | Low | `DEEP_FETCH_TOP_K=2` caps per-claim escalations; AC-11 makes deep-fetch failure non-fatal — the run continues with the snippet evidence. |
| Authority table biases against non-English / non-Western sources | High | Medium | Initial table includes international authorities (`who.int`, `nih.gov`, `iso.org`, `ietf.org`, `*.gov.<cc>`, `*.ac.<cc>`); domain expansion is a code-only PR (no migration). The `GENERAL` fallback never penalises hard (0.90, not 0.50). |
| Authority multiplier silently breaks BRD-22 expert boost composition | High | Low | WP-3 multiplier hits `C_coverage` and `C_independence` **only**; BRD-22's expert multiplier hits `C_agreement`. The two are orthogonal by construction. Unit test `test_confidence_authority_multiplier.py` enforces this. |
| WP-1 days filter on volatile topics removes a long-form authoritative article that is still correct | Medium | Medium | The judge can lift the penalty via `kind_appropriateness`; the stale rule penalises *citations* not *sources*; AC-04 ceiling drop is bounded (`× 0.85`, not `× 0.5`). |
| Query hygiene prompt makes the planner under-perform on multi-entity comparative questions | Medium | Medium | Technical connectors (`vs`, `+`, `-`, `site:`) do not count toward the 6-token cap; the rule is a soft guardrail in the prompt, not a code-enforced rejection. |
| `Source.fetch_full` default `None` lets a buggy future source silently disable deep-fetch | Low | Medium | Telemetry: `DeepFetchPerformedEvent.success=false, failure_reason="not_supported"` is emitted when the source returns None; trace shows the missed escalation. |
| Pre-BRD-23 events lacking new fields break replay | High | Low | AC-09 fixture asserts replay determinism; every new field is `T | None = None` per Architecture rule #5. |
| Confidence formula amendment in `confidence-calculation.md` lags behind code | Medium | Medium | Doc PR is part of WP-3 — must land in the same PR set as the code change. The Auditor's F1 checklist already gates the doc/code sync. |

## 12. Out of Scope

- **No new plugin seam.** `Source.fetch_full` extends the existing seam; no `DeepFetcher` interface, no `AuthorityTier` plugin, no `TemporalClassifier` plugin.
- **No persistence of the authority table to DB.** Code-only static dict; expansion is a PR.
- **No automated learning of authority tiers** (would require an LLM call per domain or a dataset; out of V1 scope).
- **No change to `kind_ceiling` values for `weighted`, `scenario`, `tradeoff`, `best_effort`, `ethical_redirect`.** WP-1 only tweaks `direct`.
- **No change to `C_agreement` or `C_no_conflict` formulas.** WP-3 modulates `C_coverage` and `C_independence` only.
- **No change to the 4-value `stop_reason` enum.** The amendment-of-2026-05-27 invariant holds.
- **No change to the FSM.** No new states, no new transitions.
- **No new LLM provider.** Judge stays on Anthropic Haiku per RF-19; planner / synthesizer / classifier stay on GitHub Models.
- **No new infra.** Single-server scope preserved (RF-05); no Redis, no vector DB, no queue.
- **Per-domain authority overrides per user / per workspace.** Out of V1.
- **Real-time scraping fallback when Tavily `extract` fails.** Out of V1; AC-11 already covers the failure path.

---

## 13. User Stories Summary

Each WP maps to exactly one User Story. They are independently shippable (no inter-WP code dependency beyond the schema additions in WP-1).

| Story ID | Title | Priority | Estimated Effort | WP |
|---|---|---|---|---|
| US-23-1 | Temporal sensitivity classification, planner routing, and stale-citation ceiling | High | M | WP-1 |
| US-23-2 | Snippet → full-page deep-fetch escalation behind the existing `Source` seam | Medium | M | WP-2 |
| US-23-3 | Source authority tiering as a modulator of `S_raw` (coverage + independence) | Medium | M | WP-3 |
| US-23-4 | Query hygiene constraint + `query_length_tokens` observability field | Low | S | WP-4 |

Suggested implementation order: **WP-1 → WP-4 → WP-3 → WP-2** (WP-1/WP-4 are pure prompt + additive field; WP-3 is the confidence wiring; WP-2 is the heaviest and benefits from temporal + authority context already being present in events).

---

## 14. Stakeholders

| Name | Role | Interest | Involvement |
|---|---|---|---|
| Giovanny (PO) | Product owner | Research-quality lift, stale-data discipline, demo trust surface | Approver |
| BSA Agent | Requirements | This BRD + US-23-x | Author |
| Auditor Agent | F1/F2 gate | Validates BRD + US (F1 sub-loop) | Approver (F1) |
| Orchestrator Agent | Planner | Drafts IP-23-x from these stories | Consumer |

---

## 15. Appendix

### 15.1 Glossary

| Term | Definition |
|---|---|
| **Temporal sensitivity** | 4-valued classifier hint (`static / slow_changing / volatile / realtime`) describing how fast the answer to a question goes stale. |
| **Authority tier** | 4-valued bucket on the source domain (`primary_authoritative / reputable_secondary / general / low_signal`) used as a multiplier on `C_coverage` and `C_independence`. |
| **Deep fetch** | Optional `Source` operation that pulls the full page body for a URL when the snippet was too short to support a critical-path claim. |
| **Supported but shallow** | Judge response flag indicating that a claim has matching evidence but the evidence chunk text is too thin to confidently support the claim. |
| **Query hygiene** | The set of planner constraints (≤ 6 tokens, no stop-words, quotes only when required) that keep search queries short and high-signal. |

### 15.2 References

- `docs/implementation-phase/brds/BRD-22-complexity-aware-planning-and-experts.md` — complexity ladder reused by WP-2 budget.
- `docs/implementation-phase/brds/BRD-05-llm-client.md` — `llm.call` entry point reused by WP-1 / WP-4 prompt changes.
- `docs/implementation-phase/brds/BRD-06-source-plugins.md` — `Source` seam extended by WP-2.
- `docs/implementation-phase/brds/BRD-07-agent-fsm.md` — FSM untouched; deep-fetch lives inside `Analyzing` re-entry.
- `docs/implementation-phase/brds/BRD-08-confidence-calculation.md` — confidence wiring modified by WP-3.
- `docs/understanding-phase/requirement-understanding.md` — Amendment 2026-05-27, RF-04, RF-06, RF-12, RF-17.
- `docs/understanding-phase/confidence-calculation.md` — amendment target for WP-3 (separate doc PR).
- `docs/technical-phase/ai-services.md` — LLM role / Tavily / Wikipedia contracts.
- `.github/memory-bank/logs/lessons-learned.md` — L-015 (fold-strategy rule applied to the deep-fetch counter).

### 15.3 Open questions — RESOLVED by PO 2026-05-27

All six open questions were resolved before F1 audit:

1. **Event name for WP-4.** ✅ **Resolved — extend `ToolCalledEvent`.** Zero migration cost, the event already carries `query`; new event type deferred until aggregate analytics demand it.
2. **Authority multiplier values.** ✅ **Resolved — `1.05 / 1.00 / 0.90 / 0.50`** (primary boost lowered from `1.10` → `1.05` to avoid clamp saturation; penalty side kept aggressive on purpose).
3. **Initial low-signal list.** ✅ **Resolved — expanded seed** to include `medium.com`, `quora.com`, `answers.com`, `geeksforgeeks.org`, `w3schools.com`, `tutorialspoint.com`, `javatpoint.com`, `*.blogspot.com`, `*.wordpress.com`, `*.substack.com`. Reddit deliberately stays in `GENERAL` (often the best source for troubleshooting; revisit with data).
4. **Deep-fetch budget for `deep` complexity.** ✅ **Resolved — cap = 3** (worst case 30 s instead of 50 s; covers ≥ 90 % of judge-flagged-shallow cases per pre-merge expectation).
5. **Stale-citation ceiling multiplier.** ✅ **Resolved — `0.85`** (visible penalty in the confidence badge, reinforces RF-13 trust contract).
6. **`confidence-calculation.md` amendment.** ✅ **Resolved — ship in the same PR as WP-3 code** (no risk of doc/code divergence per §6 of `.github/copilot-instructions.md`).

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | BSA Agent | Initial draft (F1) — WP-1/WP-2/WP-3/WP-4, AC-01..11, schema-compat statement, metrics, risk register. |
| 1.1 | 2026-05-27 | PO + Copilot | Resolved all 6 open questions. Authority primary multiplier `1.10` → `1.05`; stale-citation penalty `0.90` → `0.85`; deep-fetch `deep` cap `5` → `3`; LOW_SIGNAL seed expanded (+7 domains); WP-4 confirmed on `ToolCalledEvent`; confidence-calculation amendment scoped to same PR as WP-3. AC-04 / AC-07 updated to match. |
