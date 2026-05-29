# AI Services — Novum

> Catalog of every external AI / retrieval service Novum depends on, with role, mechanics, cost, and rationale. Companion to [tech-stack.md](tech-stack.md), [infrastructure.md](infrastructure.md), and [architecture.md](architecture.md).
>
> **Scope:** all services that either run a model or feed evidence to a model. Pure-storage and pure-infrastructure services live in `infrastructure.md`.

## Amendment 2026-05-28 — provider-agnostic LLM interface + Anthropic-only V1

This amendment supersedes the 2026-05-27 "second LLM provider for the judge" note (which is now subsumed) and rewrites §1 below.

**Doctrinal change.** The LLM call layer is a **provider-agnostic interface** (`app/llm/client.py::call` over `litellm`). The system is *prepared* to operate against four providers:

1. **Anthropic** (Claude)
2. **Google** (Gemini)
3. **OpenAI** (GPT family, direct API)
4. **GitHub Models** (multi-family gateway: OpenAI, DeepSeek, Meta, Mistral, …)

**For practical V1 purposes, only Anthropic Claude is enabled.** The other three providers are wired in code and reachable via environment configuration, but disabled by default — no API keys required, no traffic sent.

**V1 role-to-model assignment (all roles → Anthropic).**

| Role | Model | When it runs |
|---|---|---|
| **Classifier** (RF-06) | `anthropic/claude-haiku-4-5` | Once per run, before `PlanCreated`. |
| **Planner** | `anthropic/claude-sonnet-4-6` | Once per run, emits `PlanCreated`. |
| **Synthesizer** | `anthropic/claude-sonnet-4-6` | Near terminal state, renders the final answer. |
| **Judge** (RF-01·B) | `anthropic/claude-sonnet-4-6` | When signals A + D are green. Emits `JudgeRuled`. |
| **Meta-judge** (BRD-26) | `anthropic/claude-sonnet-4-6` | When divergence between judges crosses threshold. |

**Required env var (V1):** `ANTHROPIC_API_KEY`. The keys for the other three providers (`GITHUB_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`) remain reserved env vars; if absent, the interface simply rejects requests for those providers at config-load time.

**R6 honesty disclaimer.** The original cross-family-cross-provider judge mitigation (DeepSeek ↔ OpenAI through GitHub Models, then Anthropic-as-second-provider) is **not in force in V1**. With every role on the same Anthropic family, R6 reduces to:

- Adversarial judge prompt that explicitly asks the model to look for sycophancy and hallucinated citations.
- Hard cap `final_confidence = min(S, J)` so a flattering judge cannot pull confidence above the structural floor.
- Meta-judge tiebreak (BRD-26) when two judges diverge — still same family, but independent calls.

This trade-off is explicit and documented; the UI does **not** advertise cross-family verification on a V1 run. Re-enabling a second provider (e.g. Gemini for the judge) is a one-env-var change once budget allows.

**Cost impact.** Anthropic is **not free**. Per-run estimate: ~6–8 calls of ~1–3k tokens each → **≈ $0.01–0.04 per run** at Sonnet pricing (classifier uses Haiku → negligible). Practical V1 ceiling: **~$5/month** at the project's expected demo + validation cadence (≤ 50 runs/day for a few days, then idle).

**Read-the-doc rule.** Wherever this catalog historically said "GitHub Models is the only V1 provider" or assigned a specific role to `openai/gpt-5` / `deepseek/DeepSeek-V3-0324` / `meta/Llama-4-Scout`, the table above wins. Those models remain *reachable* through the GitHub-Models provider but are **not active** in V1.

---

## 0. At a glance

| # | Service | Role in Novum | Type | Cost (V1) | Card required? |
|---|---|---|---|---|---|
| 1 | **Anthropic Claude** (via the provider-agnostic LLM interface) | LLM gateway for the 5 agent roles (classifier, planner, synthesizer, judge, meta-judge) | LLM provider | ~$5/month ceiling (Sonnet + Haiku pricing) | Yes (Anthropic billing) |
| 2 | **Tavily** | Web search source for evidence retrieval | Search-for-LLM | Paid subscription (advanced depth, `topic="news"`, max 20 results) | Yes (Tavily billing) |
| 3 | **Wikipedia API** | Encyclopedic source for evidence retrieval | Knowledge base | $0 (unlimited at our scale) | No |

**Inactive but wired (no traffic, no cost):** GitHub Models, OpenAI direct, Google Gemini. Each is reachable by setting the corresponding env var (`GITHUB_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`) and pointing one role at it in `app/llm/models.py`.

**Total V1 cost: ≈ $5/month ceiling (Anthropic) + Tavily paid subscription.** Wikipedia stays $0; Tavily is now a paid service (upgraded from free tier to unlock advanced search depth, `topic="news"` for temporal queries, and up to 20 results per call). All services are pluggable behind their respective seams (`llm.call` for #1, `Source` seam for #2 and #3).

---

## 1. LLM interface layer (provider-agnostic)

### 1.1 What it is

A single thin wrapper, `app/llm/client.py::call`, that routes every LLM call through **litellm**. litellm normalises the request/response shape across providers so the agent code never sees provider-specific URLs, auth headers, or response schemas.

### 1.2 Supported providers (interface-level)

| Provider | Status in V1 | Auth env var | Notes |
|---|---|---|---|
| **Anthropic** (Claude) | ✅ **Active** — all 5 roles | `ANTHROPIC_API_KEY` | Sole active provider in V1. |
| **Google** (Gemini) | ⚪ Wired, disabled | `GOOGLE_API_KEY` | Re-enable by pointing a role at `gemini/...`. |
| **OpenAI** (direct) | ⚪ Wired, disabled | `OPENAI_API_KEY` | Re-enable by pointing a role at `openai/...`. |
| **GitHub Models** | ⚪ Wired, disabled | `GITHUB_TOKEN` | Multi-family gateway (OpenAI, DeepSeek, Meta, …) — kept as zero-cost fallback. |

"Wired, disabled" means: the code path exists, `litellm` knows how to reach the provider, but no role in `app/llm/models.py` resolves to that provider in V1 → no traffic, no key needed.

### 1.3 V1 role-to-model assignment (Anthropic Claude)

| Role | Model | Family | When it runs |
|---|---|---|---|
| **Classifier** (RF-06) | `anthropic/claude-haiku-4-5` | Anthropic | Once per run, before `PlanCreated`. Cheap fast tier. |
| **Planner** | `anthropic/claude-sonnet-4-6` | Anthropic | Once per run, emits `PlanCreated` with sub-claims and `question_type`. |
| **Synthesizer** | `anthropic/claude-sonnet-4-6` | Anthropic | Once per run, near terminal state. Renders the final answer via the selected `OutputRenderer`. |
| **Judge** (RF-01·B) | `anthropic/claude-sonnet-4-6` | Anthropic | Invoked when signals A (coverage) and D (agreement) are green. Emits `JudgeRuled { sufficient, confidence, S, J, rationale }`. |
| **Meta-judge** (BRD-26) | `anthropic/claude-sonnet-4-6` | Anthropic | Tiebreak when two judge calls diverge beyond threshold. |

**On R6 (judge sycophancy).** With every role on the same family, the cross-family verification guarantee is **not in force**. The mitigation in V1 is:

1. Adversarial judge prompt (explicitly asks the model to look for sycophancy and hallucinated citations).
2. Hard cap `final_confidence = min(S, J)` (RF-12).
3. Meta-judge tiebreak on divergence (BRD-26).

The UI does **not** show a "cross-family verified" badge in V1. Re-enabling a second provider for the judge role is a one-line change in `app/llm/models.py` plus exporting the corresponding API key.

### 1.4 How it works in the codebase

Every LLM call goes through one thin wrapper, `app/llm/client.py::call`:

```python
async def call(
    role: Literal["classifier", "planner", "synthesizer", "judge", "meta_judge"],
    messages: list[dict],
    response_model: type[BaseModel] | None = None,
) -> Any: ...
```

- `role` → looked up in `app/llm/models.py` to resolve `(provider, model_id, temperature, max_tokens)`.
- `litellm` translates the call to the resolved provider with the right URL + auth headers.
- `instructor` wraps the call when `response_model` is provided → forces a Pydantic-validated structured response (no manual JSON parsing).
- `tenacity` retries once on transient errors (rate limit, 5xx, timeout); on second failure → raises `AgentLLMError` → loop emits `AgentErrored`.

Agent code **never** calls `litellm` or `httpx` directly — `llm.call` is the only entry point. The provider is therefore a **"not-seam"**: swappable by editing one module (`app/llm/models.py`), not by implementing a protocol.

### 1.5 Cost and limits

Anthropic pricing (May 2026, approximate):

| Tier | Input ($/Mtok) | Output ($/Mtok) | Used for |
|---|---|---|---|
| Haiku 4.5 | $0.25 | $1.25 | Classifier |
| Sonnet 4.6 | $3.00 | $15.00 | Planner, Synthesizer, Judge, Meta-judge |

**Per-run estimate:** ~6–8 LLM calls totalling ~10–30k tokens → **≈ $0.01–0.04 per run**.

**Practical V1 budget:** **~$5/month ceiling** at expected cadence (≤ 50 runs/day during validation + demo; idle otherwise).

**Rate limits:** Anthropic standard tier-1 limits (50 RPM, 40k input tok/min, 8k output tok/min). One concurrent run uses a fraction of this; the single-server scope (RF-05) means no risk of saturation.

### 1.6 Rationale (Anthropic as V1 active provider)

| Why Anthropic Claude in V1 | Detail |
|---|---|
| **Quality leader for structured reasoning** | Sonnet 4.6 ranks at or near the top for plan-decomposition and citation-faithful synthesis tasks. |
| **Strong instruction-following** | Reduces the failure mode where the synthesizer ignores "cite every claim or say `I don't know`". |
| **Stable model catalog** | Anthropic deprecates models on a long, well-announced cycle. Lower risk than GitHub Models' rotating preview catalog. |
| **One key, five roles** | A single `ANTHROPIC_API_KEY` covers the whole agent loop. |
| **Provider-agnostic interface preserved** | Switching one role to Gemini or GitHub Models is one env var + one line in `app/llm/models.py` — no refactor. |

### 1.7 Risks and caveats

| Risk | Mitigation |
|---|---|
| Anthropic outage during demo | Interface is provider-agnostic. Plan B: set `GITHUB_TOKEN` and point all roles at `openai/gpt-5` (or DeepSeek-V3) in `app/llm/models.py`. Documented in infrastructure §5.4. |
| Cost overrun | Per-run cost is bounded by the token budget (RF-01·F). A run hitting the cap costs ~$0.04. Hard cap on total monthly spend lives in Anthropic billing console, not in code. |
| Same-family judge (R6 weakening) | Documented above (§1.3). Re-enabling a second provider for the judge role is the explicit V1+ escape hatch. |
| Model deprecation (e.g., `claude-sonnet-4-6` retired) | Change the model ID string in `app/llm/models.py`. |
| Higher latency than free-tier alternatives | Acceptable for an agent that runs over seconds, not milliseconds. |

---

## 2. Tavily

### 2.1 What it is

A search API designed for LLM agents (`https://api.tavily.com`). Unlike Google Search APIs that return only URLs + snippets, Tavily returns **extracted page content** ready to feed into an LLM.

### 2.2 Role in Novum

The **web-search `Source` plugin** — one of the two implementations of Seam 1 in V1 (the other is Wikipedia, §3). Provides evidence chunks during the `Searching` and `DisputeResolution` phases of the agent FSM.

| When the agent calls Tavily | What happens |
|---|---|
| `Searching` phase, per sub-claim | `await tavily.search(query, max_results=k)` → returns `list[Evidence]` → appended to the run as `EvidenceAdded` events. |
| `DisputeResolution` phase (RF-04) | Up to **2** reformulated dispute-oriented queries to try to resolve a contradiction before emitting `honest_contradiction`. |
| Source-failure cascade | On 0 results / HTTP error / timeout: retry once → reformulate query with an LLM call → retry → switch source to Wikipedia. Each attempt emits `SourceFailed`. |

### 2.3 How it works in the codebase

```python
class WebSearchSource(Source):
    name = "web_tavily"
    async def search(self, query: str, k: int) -> list[Evidence]:
        result = await self.client.search(
            query=query,
            max_results=k,
            search_depth="advanced",  # returns extracted content, not just snippets
        )
        return [
            Evidence(
                text=r["content"],
                url=r["url"],
                source=self.name,
                captured_at=utcnow(),
            )
            for r in result["results"]
        ]
```

The returned `Evidence` chunks feed three downstream consumers:
- **Coverage signal A** — counts toward sub-claim coverage if the chunk semantically matches a sub-claim.
- **Agreement signal D** — compared against Wikipedia evidence to detect agreement or contradiction.
- **Citation traceability** (RF §6-quater) — every chunk carries `url` + `captured_at` so the final answer cites the source with timestamp.

### 2.4 Cost and limits

| Plan | Limit | Card required? |
|---|---|---|
| **Free** | **1000 searches/month** | No |
| Pro | 4000 / mo for $30/mo | Yes |

**Per-run search count:** ~3–6 web queries (1–2 per sub-claim, plus dispute-resolution retries).

**Practical budget on the free tier:** ~150–300 runs/month. Way more than the demo + testing needs combined.

**Cost: $0** in V1.

### 2.5 Rationale

| Why Tavily (over SerpAPI, Brave Search API, scraping with `trafilatura`…) | Detail |
|---|---|
| **Returns extracted content, not URLs** | Saves a scraping step — no need for `trafilatura`, paywall handling, robots.txt logic in V1. |
| **API designed for agents** | Parameters like `search_depth`, `include_raw_content`, `max_results` map directly to RAG patterns. |
| **Free tier is realistic** | 1000/mo without a card; SerpAPI's free tier is 100/mo with stricter terms. |
| **Official Python SDK** (`tavily-python`) | Async-friendly, no custom `httpx` wrapping. |
| **Heterogeneity with Wikipedia** | Different ranking, different corpus, different update cadence → the D signal becomes meaningful (one source can't contradict itself). |

### 2.6 Risks and caveats

| Risk | Mitigation |
|---|---|
| Quality varies by query phrasing | LLM-driven query reformulation in the source-failure cascade (RF-04). |
| Content extraction can fail on dynamic pages | Documented as a non-guarantee — `SourceFailed` events surface the failure in the trace. |
| Free-tier quota burned during demo | Same Plan B as for GitHub Models — localhost fallback with personal keys. |
| Vendor lock-in | None — the `Source` seam means swapping to Brave Search or Exa is a new class implementing the same `Source` protocol. |

### 2.7 Not Perplexity

Tavily and Perplexity occupy the same category ("search APIs for AI"), but they play **opposite roles**:

- **Tavily = retriever.** Returns raw evidence; your agent does the reasoning.
- **Perplexity = full agent.** Returns a synthesized answer; the reasoning is its blackbox.

Using Perplexity in Novum would defeat RF-01 (defensible stopping), RF-02 (inspectability), and RF-03 (fork from intermediate steps) — there are no intermediate steps to inspect or fork. Tavily is in scope; Perplexity is explicitly out of scope as a V1 source.

---

## 3. Wikipedia API

### 3.1 What it is

The official Wikimedia REST + Action API (`https://en.wikipedia.org/api/rest_v1/` and friends). Free, no key, no auth — only a `User-Agent` header identifying the client.

### 3.2 Role in Novum

The **second `Source` plugin** in V1 — complements Tavily to provide source heterogeneity (RF-04 minimum source set: ≥2 independent providers).

| Strength | Implication |
|---|---|
| Curated, editorially reviewed | High-confidence baseline for factual (Type 1) and definitional (Type 3) questions. |
| Stable URLs and revisions | Citations remain valid long after the run. |
| Different corpus from Tavily | Disagreements between Tavily and Wikipedia are real signal, not coincidence. |

### 3.3 How it works in the codebase

```python
class WikipediaSource(Source):
    name = "wikipedia"
    async def search(self, query: str, k: int) -> list[Evidence]:
        page_titles = await self.client.search_titles(query, limit=k)
        evidences = []
        for title in page_titles:
            summary = await self.client.page_summary(title)
            evidences.append(Evidence(
                text=summary["extract"],
                url=summary["content_urls"]["desktop"]["page"],
                source=self.name,
                captured_at=utcnow(),
            ))
        return evidences
```

Same `Evidence` contract as Tavily → same downstream consumers (Coverage A, Agreement D, citation traceability).

### 3.4 Cost and limits

| Plan | Limit |
|---|---|
| **Public API** | No hard quota at our scale (Wikimedia's policy: be polite, set a `User-Agent`, respect 429s). |

**Per-run call count:** ~3–6 (parallel to Tavily).

**Cost: $0.** No card, no key, no account.

### 3.5 Rationale

| Why Wikipedia (over arXiv, HN Algolia, …) | Detail |
|---|---|
| **Zero-friction** | No key, no rate-limit dance — works from minute one. |
| **Heterogeneity vs Tavily** | Different ranking algorithm, different corpus → makes signal D (source agreement) meaningful. Two clones of Google Search would not. |
| **Quality floor for factual questions** | For Type 1 (factual) and Type 3 (definitional), Wikipedia is often *the* primary source the synthesizer should cite. |
| **Stable and inspectable** | Reviewer can click any citation in the demo and verify the source still exists. |

### 3.6 Risks and caveats

| Risk | Mitigation |
|---|---|
| English bias | Acceptable for V1 (system prompts in English, runtime replies in Spanish by user request — but evidence stays English). i18n is V2. |
| Vandalism windows on hot topics | Mitigated by the cross-source agreement (D signal); if Tavily and Wikipedia disagree, `ContradictionDetected` fires. |
| Out-of-date entries for fast-moving topics | Documented non-guarantee. The `captured_at` timestamp on every evidence chunk makes staleness visible in the trace. |

---

## 4. Explicitly out of scope (V1)

> **Note:** "wired but disabled" providers (Google Gemini, OpenAI direct, GitHub Models) are *not* in this list — they are documented in §1.2 as part of the provider-agnostic interface, simply not activated. The table below covers services that are not wired at all.

| Service | Why not |
|---|---|
| **Groq / Cerebras** | Not wired in `litellm` config; reserved as future option for latency-critical workloads. |
| **OpenRouter** | Aggregator over other providers — would mask the provider identity and break per-provider cost / quota tracking. |
| **Perplexity API** | See §2.7 — wrong layer of the stack; would replace Novum instead of feeding it. |
| **Anthropic Computer Use / OpenAI Operator** | Out of agent-loop scope — Novum does not take actions in the world, it reasons over evidence. |
| **Pinecone / Weaviate / Chroma (vector DBs)** | V1 does not have a corpus to embed — every search is fresh and live. Vector DB enters only when V2 adds a `PDFCorpusSource` or similar. |
| **OpenAI embeddings** | Same reason — no corpus to embed. |
| **LangSmith / Langfuse (LLM observability)** | Free tiers exist but introduce another secret + an external dependency at demo time. The event log in Postgres already records every LLM call's tokens and latency via structlog. V2 reconsideration. |
| **arXiv / Semantic Scholar / HN Algolia** | Optional V2 `Source` implementations. Listed in tech-stack §2.4 as deferred. |

---

## 5. Environment variables for AI services

```env
# Required in V1
ANTHROPIC_API_KEY=<sk-ant-...>     # Anthropic Claude (all 5 LLM roles)
TAVILY_API_KEY=<tvly-...>          # Tavily web search
# Wikipedia: no key required (only a User-Agent header set in client code)

# Reserved for the wired-but-disabled providers (unused in V1; safe to leave unset)
GITHUB_TOKEN=<github_pat>          # Enables GitHub Models routing
OPENAI_API_KEY=<sk-...>            # Enables OpenAI direct routing
GOOGLE_API_KEY=<...>               # Enables Gemini routing
```

All of these are gitignored. See `.gitignore` (the `*api_key*`, `*secret*`, `.env*` rules added during the V1 security pass).

---

## 6. Cost & token instrumentation (RF-20)

> Added 2026-05-29 with BRD-29 / IP-29. See [BRD-29](../implementation-phase/brds/BRD-29-cost-and-token-tracking.md) and [IP-29](../implementation-phase/implementation-plans/IP-29-cost-and-token-tracking.md) for the full spec.

### 6.1 What it is

Every external billable call — one per LLM round (`app/llm/client.py::call`) and one per Source `search`/`fetch` (Tavily, Wikipedia, …) — emits exactly one append-only `CostIncurred` event into the existing `events` table. The event payload records `provider`, `kind` (`"llm"` / `"search"` / `"fetch"`), `model`, `task_name`, `prompt_tokens`, `completion_tokens`, `units`, `cost_usd`, `latency_ms`, and `price_source` (`"litellm"` / `"static_table"` / `"env_override"` / `"unknown"`). No out-of-band sidecar storage — the event log is the only source of truth (RF-03).

### 6.2 How pricing is resolved (hybrid)

| Provider kind | Primary source | Fallback |
|---|---|---|
| **LLM** (Anthropic, OpenAI, Gemini, GitHub Models) | `litellm.cost_per_token(...)` (resolved from `litellm.model_cost`) | Static per-model `(prompt_usd_per_1k, completion_usd_per_1k)` table in `app/llm/pricing.py`, optionally overridden by env (`NOVUM_LLM_PRICE_<PROVIDER>_<MODEL>_PROMPT_PER_1K`). |
| **Search / Fetch** (Tavily) | Static price table in `app/sources/pricing.py` (`tavily.search = $0.008/call`, etc.) | Env override `NOVUM_TAVILY_SEARCH_PRICE_USD`. |
| **Free** (Wikipedia) | Always `$0.0`, `price_source="static_table"`. | — |

When no price can be resolved, the event still emits with `cost_usd=0.0` and `price_source="unknown"` (RF-16 graceful degradation). The chip and breakdown stay accurate — they just under-report instead of crashing.

### 6.3 Plumbing (no global state)

Three module-level `contextvars` in `app/llm/context.py` make the run-id, current task name, and SSE emitter callable available to deep call sites without threading them through every function signature:

- `current_run_id: ContextVar[UUID | None]`
- `current_task_name: ContextVar[str | None]`
- `current_emitter: ContextVar[Callable[[BaseEvent], Awaitable[None]] | None]`

The orchestrator binds them once per run (`run_context_setup`). The cost wrappers (`app/llm/client.py::call`, `app/sources/_cost.py::record_source_call`) read them and emit the `CostIncurred` event through the bound emitter — no thread-locals, no global mutables.

### 6.4 Surfaces

- **REST.** `GET /api/runs/{run_id}/costs` returns the per-provider breakdown aggregated by the Postgres view `run_costs` (one row per `(provider, kind, model)`).
- **SSE.** Each `CostIncurred` frame is forwarded on the existing per-run stream (`/api/runs/{run_id}/stream`) — no new endpoint, no polling.
- **UI.** `TotalCostChip` in the run header (always visible) + trace-panel tab **T1d "Cost"** (`TraceCostPanel`). The hook `useRunCosts(runId)` loads the REST snapshot on mount and patches the TanStack-Query cache on every incoming `CostIncurred` SSE frame.

### 6.5 Schema evolution

The `CostIncurred` payload uses `extra="allow"` (RF-15) so future per-provider fields (e.g. `cache_creation_input_tokens` from Anthropic prompt caching) can be added without a migration. Removing or renaming a field requires an explicit Alembic migration.
