# AI Services — Novum

> Catalog of every external AI / retrieval service Novum depends on, with role, mechanics, cost, and rationale. Companion to [tech-stack.md](tech-stack.md), [infrastructure.md](infrastructure.md), and [architecture.md](architecture.md).
>
> **Scope:** all services that either run a model or feed evidence to a model. Pure-storage and pure-infrastructure services live in `infrastructure.md`.

## Amendment 2026-05-27 — second LLM provider for the judge (RF-19)

Ratified on 2026-05-27 alongside the "always answer" refactor ([research-method-refactor-proposal.md](research-method-refactor-proposal.md) — WP-5). Single change to this catalog: a **second LLM provider** is added for the judge role only.

| # | Service | Role | Type | Cost (V1) | Card? |
|---|---|---|---|---|---|
| 4 | **Anthropic Claude Haiku** | **Judge** LLM (default). Replaces GitHub Models for the `LLMRole.JUDGE` only. | LLM provider | Pay-as-you-go (~$0.001/run at Haiku pricing) | Yes |

**Routing.** `app/llm/client.py::call` reads two new env vars on the `judge` role:

- `JUDGE_PROVIDER` — `anthropic` (default) | `github` (fallback)
- `JUDGE_MODEL` — `claude-haiku-...` (default for anthropic) | `deepseek/DeepSeek-V3-0324` (when forced to github)

Planner, synthesizer, and classifier continue to route through GitHub Models unchanged (§1.2 table below).

**Graceful degradation.** If the Anthropic call fails for any reason (missing key, 5xx, rate limit after one retry):

1. The agent emits a new `JudgeProviderDegraded(reason, attempted_provider, fallback_provider)` event.
2. The judge call is retried once on the GitHub-Models judge model.
3. The UI surfaces a small warning on the confidence badge: *"verifier ran on the same family as the synthesizer on this run."*

**Why a second provider.** The R6 mitigation (judge sycophancy) the original §1.2 relied on was *cross-family-inside-one-provider* (DeepSeek judge vs OpenAI synthesizer). That is weaker than *cross-provider-and-cross-family*. Anthropic Haiku is the cheapest option that achieves both at once.

**Cost impact.** Anthropic does not have a meaningful free tier comparable to GitHub Models, so this is the first non-zero line item in V1. Budget: a Claude Haiku judge call is ~500 input tokens + 200 output tokens ≈ $0.0003 per invocation. With 1–3 judge calls per run, real-world cost is **< $0.001 per run**. Practical V1 ceiling: **$5/month** even with 50 runs/day. Acceptable.

**Why not OpenRouter or Groq.** OpenRouter routes through other providers and breaks the cross-provider guarantee. Groq's free tier is wide but its model catalog drifts; Anthropic Haiku is stable, well-priced, and SDK-supported in `litellm` without configuration tricks.

**Env var addition.** `ANTHROPIC_API_KEY` must be exported on the VM and on dev machines. Missing key is **non-fatal** (degradation path above).

**Read-the-doc rule:** wherever §1.2 below assigns the judge role to `deepseek/DeepSeek-V3-0324`, the amendment above wins. DeepSeek-V3 remains the **fallback** judge model when `JUDGE_PROVIDER=github`.

---

---

## 0. At a glance

| # | Service | Role in Novum | Type | Cost (V1) | Card required? |
|---|---|---|---|---|---|
| 1 | **GitHub Models** | LLM gateway for 4 agent roles (classifier, planner, synthesizer, judge) | LLM provider | $0 (free tier) | No |
| 2 | **Tavily** | Web search source for evidence retrieval | Search-for-LLM | $0 (1000 req/mo free tier) | No |
| 3 | **Wikipedia API** | Encyclopedic source for evidence retrieval | Knowledge base | $0 (unlimited at our scale) | No |

**Total V1 cost: $0/month.** All three are pluggable behind their respective seams (`llm.call` for #1, `Source` seam for #2 and #3).

---

## 1. GitHub Models

### 1.1 What it is

GitHub's hosted LLM gateway (`https://models.github.ai/inference`). An OpenAI-SDK-compatible endpoint that fronts multiple model families (OpenAI, DeepSeek, Meta, Mistral, …) under a single GitHub PAT.

### 1.2 Role in Novum

The **only LLM provider in V1**. Powers the four agent roles defined in the custom FSM:

| Role | Model | Family | When it runs |
|---|---|---|---|
| **Classifier** (RF-06) | `meta/Llama-4-Scout-17B-16E-Instruct` | Meta | Once per run, before `PlanCreated`. Decides if the question is Type 1–5 (continue) or 6–8 (`honest_unanswerable`). |
| **Planner** | `deepseek/DeepSeek-V3-0324` | DeepSeek | Once per run, emits `PlanCreated` with sub-claims and `question_type`. |
| **Synthesizer** | `openai/gpt-5` | OpenAI | Once per run, near terminal state. Renders the final answer via the selected `OutputRenderer` (prose or structured). |
| **Judge** (RF-01·B) | `deepseek/DeepSeek-V3-0324` | DeepSeek | Invoked when signals A (coverage) and D (agreement) are green. Emits `JudgeRuled { sufficient, confidence, S, J, rationale }`. |

**Why two families:** the judge is **cross-family** against the synthesizer (DeepSeek ↔ OpenAI). This is the explicit R6 mitigation against judge sycophancy — a model is less likely to rubber-stamp text generated by a model from a different lineage.

### 1.3 How it works in the codebase

Every LLM call goes through one thin wrapper, `app/llm/client.py::call`:

```python
async def call(
    role: Literal["classifier", "planner", "synthesizer", "judge"],
    messages: list[dict],
    response_model: type[BaseModel] | None = None,
) -> Any: ...
```

- `role` → looked up in `app/llm/models.py` to resolve `(model_id, temperature, max_tokens)`.
- `litellm` translates the call to GitHub Models with the right URL + auth headers.
- `instructor` wraps the call when `response_model` is provided → forces a Pydantic-validated structured response (no manual JSON parsing).
- `tenacity` retries once on transient errors (rate limit, 5xx, timeout); on second failure → raises `AgentLLMError` → loop emits `AgentErrored`.

Agent code **never** calls `litellm` or `httpx` directly — `llm.call` is the only entry point. This keeps the LLM provider as a "not-seam": swappable by editing one module, not by implementing a protocol.

### 1.4 Cost and limits

| Tier | Limit (May 2026, approximate) | Models affected |
|---|---|---|
| Low-tier | ~150 req/day, 50 req/min | `meta/Llama-4-Scout` (classifier) |
| High-tier | ~50 req/day, 10–15 req/min | `openai/gpt-5` (synthesizer), `deepseek/DeepSeek-V3-0324` (planner + judge) |

**Per-run LLM call count:** ~5–8 (1 classifier + 1 planner + N planner-extensions + 1 synthesizer + 1–3 judge invocations).

**Practical budget on the free tier:** ~6–8 complete runs per day on the High-tier models. Sufficient for:
- 4–6 h pair-session build with mocked LLM calls in most tests.
- ~50 validation runs across multiple days before the demo.
- 3 live demo runs.

**Mitigation during build:** use `meta/Llama-4-Scout` for every role during development (Low tier has 3× headroom); switch to the final assignment for validation and demo.

**Cost: $0** within free-tier limits. No card required.

### 1.5 Rationale

| Why GitHub Models (over Groq, OpenAI direct, Anthropic, OpenRouter…) | Detail |
|---|---|
| **One key for all four roles** | A single `GITHUB_TOKEN` (a GitHub PAT) authenticates classifier, planner, synthesizer, and judge across three model families. No fan of API keys to manage. |
| **Free tier is meaningful** | Most competitors give trial credits that expire; GitHub Models is free-as-in-quota indefinitely. |
| **OpenAI-SDK-compatible** | Native litellm support, no custom client code. |
| **Cross-family coverage in one provider** | Lets us mitigate R6 (judge sycophancy) without adding a second API. |
| **No card required** | Aligns with the $0 V1 infrastructure goal. |
| **Reviewable for the pair session** | "I use a single LLM gateway with three model families, the judge is cross-family to the synthesizer" is a one-line defensible architectural choice. |

### 1.6 Risks and caveats

| Risk | Mitigation |
|---|---|
| Free-tier limits change at any moment | `litellm` makes swapping to OpenAI-direct or Groq a one-line change. `OPENROUTER_API_KEY` / `GROQ_API_KEY` env vars are reserved but unused in V1 (see tech-stack §5). |
| Model deprecation (e.g., `gpt-5` removed from GitHub Models) | Same mitigation — change the model ID string in `app/llm/models.py`. |
| Higher latency than direct OpenAI | Acceptable for an agent that runs over seconds, not milliseconds. |
| Rate limit hit during live demo | Plan B = throttle UI via `VITE_DEMO_SLOWDOWN`, fall back to localhost with personal API keys via Cloudflare Tunnel (see infrastructure §5.4). |

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

| Service | Why not |
|---|---|
| **OpenAI direct API** | GitHub Models gives access to `gpt-5` for free. Direct API kept as Plan B (`OPENROUTER_API_KEY` env var reserved). |
| **Anthropic Claude API** | Not available through GitHub Models. Cross-family R6 mitigation already satisfied by OpenAI ↔ DeepSeek. |
| **Groq / Cerebras** | Reserved as Plan B for latency-critical demo fallback (env vars `GROQ_API_KEY`). |
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
GITHUB_TOKEN=<github_pat>          # GitHub Models (all 4 LLM roles)
TAVILY_API_KEY=<tvly-...>          # Tavily web search
# Wikipedia: no key required (only a User-Agent header set in client code)

# Reserved Plan B (unused in V1)
OPENROUTER_API_KEY=<...>
GROQ_API_KEY=<...>
OPENAI_API_KEY=<...>
```

All of these are gitignored. See `.gitignore` (the `*api_key*`, `*secret*`, `.env*` rules added during the V1 security pass).
