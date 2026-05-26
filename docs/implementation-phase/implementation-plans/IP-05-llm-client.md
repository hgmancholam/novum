# Implementation Plan: BRD-05 LLM Client Integration

**Plan ID:** IP-05
**BRD Reference:** [BRD-05-llm-client.md](../brds/BRD-05-llm-client.md)
**Created:** 2026-05-26
**Status:** Ready for Coder
**Implementation Order:** 6 of 19

---

## 1. Overview

Implement the LLM client layer (`backend/app/llm/`) that wraps **litellm + instructor** behind a single entry point `llm.call(role, messages, response_model)`. Provides the four agent roles (**classifier, planner, synthesizer, judge**), structured outputs via Pydantic, tenacity retry on transient errors, and a tiktoken-based `count_tokens` helper.

**Source of truth resolution.** BRD-05 §4 and [docs/technical-phase/ai-services.md](../../technical-phase/ai-services.md) §1 disagree on roles, models, API base, and the `call` signature. Per `.github/copilot-instructions.md` §1, **`ai-services.md` is binding for backend LLM work**, so this plan follows ai-services.md and treats BRD-05 §4 as a structural reference (file layout, retry, instructor wrapping, prompts skeleton, acceptance-criteria shape). BRD-05 should later be amended; see §8 of this plan.

**Non-goals (deferred):**
- Token budget tracking (BRD-09).
- Streaming responses (BRD-10 handles SSE).
- Caching / dedup (V2).
- Multi-provider support (V2; `litellm` keeps it cheap to add).
- Actually wiring `llm.call` into the agent FSM (BRD-07).

---

## 2. Architectural Alignment

| Architecture rule | Compliance |
|---|---|
| English-only code artifacts (L-001) | All identifiers, docstrings, log messages, prompts in English. |
| Pyright strict / Ruff clean | `from __future__ import annotations`, explicit return types, no `Any` (use `TypeVar("T", bound=BaseModel)`). |
| LLM provider is a not-seam | No `Protocol` for the client; `llm.call` is the only entry point and is swapped by editing one file. |
| `app/llm/client.py::call` is the single LLM entrypoint (copilot-instructions §1) | Agent code (later BRDs) imports `from app.llm import llm` and only ever calls `llm.call(...)`. |
| Retries via `tenacity` (copilot-instructions §4) | `retry_llm` decorator with exponential backoff, retries `RETRYABLE_EXCEPTIONS`. |
| Structured outputs only (no manual JSON parsing) | All call sites pass a `response_model: type[BaseModel]`; `instructor` validates. |
| Cross-family judge (RF-15) | Judge model family ≠ synthesizer model family (DeepSeek vs OpenAI per ai-services.md §1.2). Enforced by a unit test on `ROLE_MODELS`. |

**Pre-existing state (verified):**
- `backend/app/llm/__init__.py` exists but is empty. ✓
- `backend/app/config.py` already has `github_token` (required), plus `llm_model_researcher/judge/planner/critic` placeholders (BRD-05 §8). We **replace** the per-role overrides with the ai-services.md set. ✓
- `litellm`, `instructor`, `tiktoken`, `tenacity`, `structlog` are pinned in `pyproject.toml`. ✓
- `pytest-httpx` is available for mocking, but the cleanest path is to monkeypatch the `instructor`-patched client (see §5.6).

---

## 3. Authoritative Role / Model Matrix

Resolved per [ai-services.md §1.2](../../technical-phase/ai-services.md):

| Role | Model ID | Family | Temperature | Max tokens | Cross-family vs Synth? |
|---|---|---|---|---|---|
| `classifier` | `meta/Llama-4-Scout-17B-16E-Instruct` | Meta | 0.0 | 512 | n/a |
| `planner` | `deepseek/DeepSeek-V3-0324` | DeepSeek | 0.2 | 2048 | n/a |
| `synthesizer` | `openai/gpt-5` | OpenAI | 0.3 | 4096 | reference |
| `judge` | `deepseek/DeepSeek-V3-0324` | DeepSeek | 0.0 | 2048 | ✅ different from synthesizer (RF-15) |

`api_base = "https://models.github.ai/inference"` (ai-services.md §1.1). The `models.inference.ai.azure.com` URL in BRD-05 §4.7 is **wrong**; do not use it.

> Temperatures and max-token caps above are working defaults; tune in BRD-07/08 once the FSM exercises them.

---

## 4. File Layout

Create (or replace, where it exists empty):

```
backend/app/llm/
  __init__.py        # re-exports llm, LLMRole, response models
  roles.py           # LLMRole StrEnum + ROLE_MODELS dict + RoleConfig
  retry.py           # tenacity decorator + RETRYABLE_EXCEPTIONS
  prompts.py         # 4 system prompts (CLASSIFIER, PLANNER, SYNTHESIZER, JUDGE)
  models.py          # Pydantic models for structured outputs
  client.py          # LLMClient + llm singleton + count_tokens
```

No other directories touched (config.py is amended in step 2).

---

## 5. Implementation Sequence

### Phase 1 — Configuration alignment (Step 1–2)

| Step | Task | File | Priority |
|------|------|------|----------|
| 1 | Add `LLM_API_BASE` to `Settings` (default `"https://models.github.ai/inference"`). | [backend/app/config.py](../../../backend/app/config.py) | P0 |
| 2 | Replace the four `llm_model_*` fields with `llm_model_classifier`, `llm_model_planner`, `llm_model_synthesizer`, `llm_model_judge`, defaults per §3. Update `.env.test` shim in `tests/conftest.py` only if needed (no new required vars). | [backend/app/config.py](../../../backend/app/config.py) | P0 |

> Renaming `llm_model_researcher → llm_model_synthesizer` etc. is a breaking config change, but no code currently references these (verified by `grep_search llm_model_`). Safe to do without a shim.

### Phase 2 — Roles, retry, models (Steps 3–5)

| Step | Task | File | Priority |
|------|------|------|----------|
| 3 | Implement `LLMRole` (`StrEnum`: `CLASSIFIER, PLANNER, SYNTHESIZER, JUDGE`) and `ROLE_CONFIGS: dict[LLMRole, RoleConfig]` populated from `settings` (read at module import). `RoleConfig` is a `NamedTuple(model: str, temperature: float, max_tokens: int, description: str)`. | [backend/app/llm/roles.py](../../../backend/app/llm/roles.py) | P0 |
| 4 | Implement `retry.py` per BRD-05 §4.4 verbatim: `RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)`, `create_retry_decorator(max_attempts)`, `retry_llm = create_retry_decorator(3)`, `retry_llm_critical = create_retry_decorator(5)`. Use `before_sleep_log(logger, logging.WARNING)` (note: `logging.WARNING`, not the string `"warning"` — BRD-05 typo). | [backend/app/llm/retry.py](../../../backend/app/llm/retry.py) | P0 |
| 5 | Implement `models.py` with the structured-output Pydantic models. Replace BRD-05's `EvidenceAnalysis` / `AnswerDraft` / `SearchQueryOutput` with role-aligned ones (see §6.1 below). Keep `PlanOutput`, `SubClaimOutput`, `JudgeVerdict`. | [backend/app/llm/models.py](../../../backend/app/llm/models.py) | P0 |

### Phase 3 — Prompts & client (Steps 6–8)

| Step | Task | File | Priority |
|------|------|------|----------|
| 6 | Implement `prompts.py` with **four** system prompts: `CLASSIFIER_SYSTEM_PROMPT`, `PLANNER_SYSTEM_PROMPT`, `SYNTHESIZER_SYSTEM_PROMPT`, `JUDGE_SYSTEM_PROMPT`. Reuse BRD-05's Planner and Judge text. Reuse Researcher prompt for the Synthesizer (re-titled). Add a minimal Classifier prompt (see §6.2). | [backend/app/llm/prompts.py](../../../backend/app/llm/prompts.py) | P0 |
| 7 | Implement `client.py` with the ai-services.md signature: `async def call(role: LLMRole, messages: list[dict[str, str]], response_model: type[T]) -> T`. Configure litellm (`api_base`, `api_key` from `settings`), build `client = instructor.from_litellm(litellm.acompletion)`, prepend `{"role": "system", "content": ROLE_PROMPTS[role]}` if absent, decorate with `@retry_llm`. Also implement `count_tokens(text: str, model: str = "openai/gpt-5") -> int` using tiktoken with a `cl100k_base` fallback. Expose a module-level `llm = LLMClient()` singleton. | [backend/app/llm/client.py](../../../backend/app/llm/client.py) | P0 |
| 8 | Populate `app/llm/__init__.py` to re-export `llm`, `LLMClient`, `LLMRole`, `ROLE_CONFIGS`, `RoleConfig`, and all response models. | [backend/app/llm/__init__.py](../../../backend/app/llm/__init__.py) | P0 |

### Phase 4 — Tests (Steps 9–12) — mandatory per L-002

| Step | Task | File | Priority |
|------|------|------|----------|
| 9 | Unit tests for `roles.py`: enum values, `ROLE_CONFIGS` has all 4 roles, judge model family ≠ synthesizer model family (string-prefix check on the slash-separated provider — `"deepseek/"` vs `"openai/"`). | [backend/tests/test_llm_roles.py](../../../backend/tests/test_llm_roles.py) | P0 |
| 10 | Unit tests for `retry.py`: decorator retries on `httpx.TimeoutException` (use a counter mock raising twice then succeeding), gives up after 3 attempts, does **not** retry on `ValueError` (non-retryable). Use `tenacity.RetryError` or `reraise=True` semantics. | [backend/tests/test_llm_retry.py](../../../backend/tests/test_llm_retry.py) | P0 |
| 11 | Unit tests for `client.py`: monkeypatch `app.llm.client.client.chat.completions.create` with an `AsyncMock` returning a Pydantic instance and verify (a) the right model id is forwarded, (b) the role's system prompt is prepended when absent, (c) temperature/max_tokens come from `ROLE_CONFIGS`, (d) when the user supplies their own system message, it is **not** duplicated. Also test the success path for each of the 4 roles by parametrizing. | [backend/tests/test_llm_client.py](../../../backend/tests/test_llm_client.py) | P0 |
| 12 | Unit test for `count_tokens`: returns positive int for non-empty string, returns 0 for empty string, falls back to `cl100k_base` when `encoding_for_model` raises `KeyError` (monkeypatch tiktoken). | [backend/tests/test_llm_tokens.py](../../../backend/tests/test_llm_tokens.py) | P0 |

> All LLM tests are pure-Python mocks. Do not hit the real GitHub Models endpoint; the test suite stays offline. Manual smoke test against the live API is documented in BRD-05 §7 and is out of scope for the automated suite.

---

## 6. Detailed Specifications

### 6.1 Response models (`app/llm/models.py`)

Keep the structurally fine BRD-05 models, rename role-specific ones:

```python
# Classifier
class QuestionClassification(BaseModel):
    """Output of the classifier (RF-06 question typing)."""
    question_type: int = Field(..., ge=1, le=8)  # 1-5 continue, 6-8 honest_unanswerable
    rationale: str
    answerable: bool  # convenience: True iff question_type in {1,2,3,4,5}

# Planner — unchanged from BRD-05 §4.5
class SubClaimOutput(BaseModel): ...
class PlanOutput(BaseModel): ...

# Synthesizer (replaces BRD-05 AnswerDraft + EvidenceAnalysis + SearchQueryOutput)
class SynthesizedAnswer(BaseModel):
    """Final answer produced by the synthesizer."""
    prose: str
    key_points: list[str]
    citations: list[str] = Field(default_factory=list)  # URLs of cited evidence
    gaps: list[str] = Field(default_factory=list)

# Judge — unchanged from BRD-05 §4.5
class JudgeVerdict(BaseModel): ...
```

`EvidenceAnalysis`, `SearchQueryOutput`, `CritiqueOutput`, `AnswerDraft` from BRD-05 are **dropped** for this BRD — they belong to the FSM (BRD-07) and the source-failure cascade (BRD-06). Re-introduce them there when needed.

### 6.2 Classifier prompt (`app/llm/prompts.py`)

BRD-05 has no classifier prompt; supply a minimal one (refined in BRD-07):

```python
CLASSIFIER_SYSTEM_PROMPT = """You are a question classifier for a research agent. You decide whether a question is answerable.

Question types:
  1. Factual lookup (single verifiable fact)
  2. Comparative (comparing entities)
  3. Definitional (what is X?)
  4. Causal (why / how does X happen?)
  5. Aggregate (lists, summaries)
  6. Subjective opinion (no objective answer)
  7. Future prediction (unknowable)
  8. Personal advice / private information

Types 1-5 are answerable by research. Types 6-8 must be reported as honest_unanswerable.

Output format: JSON matching the QuestionClassification schema."""
```

### 6.3 `LLMClient.call` signature

```python
async def call(
    self,
    role: LLMRole,
    messages: list[dict[str, str]],
    response_model: type[T],
) -> T:
```

- The caller passes a list of `{"role": "user"|"assistant"|"system", "content": str}` dicts.
- If no `system` message is in `messages`, the client prepends `ROLE_PROMPTS[role]`.
- If a `system` message is already present, the client **does not** prepend (caller is in control).
- Returns a validated Pydantic instance of `response_model`.

This matches ai-services.md §1.3 and is the public contract every downstream BRD will rely on.

### 6.4 Settings amendment (`app/config.py`)

```python
# LLM
github_token: str
llm_api_base: str = "https://models.github.ai/inference"
llm_model_classifier: str = "meta/Llama-4-Scout-17B-16E-Instruct"
llm_model_planner: str = "deepseek/DeepSeek-V3-0324"
llm_model_synthesizer: str = "openai/gpt-5"
llm_model_judge: str = "deepseek/DeepSeek-V3-0324"
```

Remove `llm_model_researcher`, `llm_model_judge` (existing), `llm_model_planner` (existing), `llm_model_critic`. Verified no current code reads them.

---

## 7. Acceptance Criteria Mapping

| AC (BRD-05 §5, reinterpreted) | Verifying test |
|---|---|
| AC-01 Planner produces valid `PlanOutput` | `test_llm_client.py::test_call_planner_returns_plan_output` |
| AC-02 Critic evaluates plan — **deferred to BRD-07** (no critic role in V1) | N/A this BRD |
| AC-03 Judge returns `JudgeVerdict` with confidence ∈ [0, 1] | `test_llm_client.py::test_call_judge_returns_verdict` |
| AC-04 Retry on transient errors (3 attempts, exponential backoff) | `test_llm_retry.py::test_retries_on_timeout` + `test_gives_up_after_three_attempts` |
| AC-05 Token counting works | `test_llm_tokens.py::test_count_tokens_*` |
| **AC-06 (new)** Judge model is cross-family vs synthesizer (RF-15) | `test_llm_roles.py::test_judge_is_cross_family` |
| **AC-07 (new)** Caller-supplied `system` is not duplicated | `test_llm_client.py::test_call_does_not_prepend_system_when_present` |

---

## 8. Implementation Notes / Tightenings

1. **BRD vs ai-services divergence (see overview).** Follow ai-services.md verbatim for roles, models, `api_base`, and the `call` signature. BRD-05 §4 should be amended in a follow-up doc PR; do not silently let code and BRD diverge further.
2. **No critic role in V1.** ai-services.md §1.2 lists 4 roles and the critic is not one of them — plan-criticism is part of the planner's own self-correction loop (BRD-07/RF-14, max 2 attempts). Do **not** ship a `CRITIC` enum value, prompt, or model in this BRD.
3. **`before_sleep_log` argument type.** BRD-05 §4.4 passes the string `"warning"`; `tenacity` requires a `logging` level integer. Use `logging.WARNING`.
4. **litellm/instructor wiring.** Use module-level configuration (`litellm.api_base`, `litellm.api_key`) once at import time. `instructor.from_litellm(litellm.acompletion)` returns the patched async client; call `.chat.completions.create(..., response_model=...)`. Pin to the `>=1.7.0` instructor API (already in `pyproject.toml`).
5. **Test isolation.** Monkeypatch `app.llm.client.client.chat.completions.create` directly with `AsyncMock`. Do **not** spin up the real `instructor` patch chain in tests — it adds latency and surface area without value. `pytest-httpx` is also unnecessary because we are below the HTTP layer.
6. **No DB / no FastAPI in this BRD.** No need for the SQLite fixture (L-005). New tests are pure unit tests with `pytest` + `pytest-asyncio` + `AsyncMock`.
7. **Pyright strict gotchas:**
   - `messages: list[dict[str, str]]` is acceptable; litellm accepts both `dict` and typed `ChatCompletionMessageParam`. Don't over-type here.
   - Annotate `count_tokens` return as `int`, not `Awaitable[int]`; it is sync (tiktoken is sync) — promote it to `def`, not `async def`. BRD-05 wrote `async def`; that is wrong because tiktoken is CPU-bound and sync — keep it sync to avoid spurious event-loop blocking surprises.
   - `RoleConfig` is a `NamedTuple` with explicit field annotations.
   - Avoid `Any`. The `TypeVar("T", bound=BaseModel)` flows from input `response_model` to return value.
8. **Logging.** Use `structlog.get_logger()` (project standard). Emit `llm_call_start` and `llm_call_complete` events with `role`, `model`, `response_model` (name). Do **not** log message contents (would leak prompts and user input into logs).
9. **English-only.** All prompts and log keys in English. The synthesizer prompt instructs the LLM "Reply in the same language the user used (Spanish by default)" — this is the only place where Spanish is referenced, and it is data inside an English-language prompt (per L-001).

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| `instructor` API differs between minor versions. | Pinned `>=1.7.0` in pyproject; tests assert the call shape, so a breaking upgrade fails CI immediately. |
| `litellm` module-level config bleeds across tests (global state). | Acceptable for V1 — the `api_base` and `api_key` are the same in all tests. If a future test needs to flip them, use a fixture that saves/restores. |
| `meta/Llama-4-Scout-17B-16E-Instruct` model id is wrong / deprecated on GitHub Models. | Surface as a config string (`llm_model_classifier`) — overridable by env var. No code change needed to swap. |
| Renaming config fields breaks a hypothetical reader. | Verified via `grep_search` that nothing reads `llm_model_researcher`/`critic` today. |
| Token counting fallback to `cl100k_base` may under-count for non-OpenAI models. | Documented limitation; the count is a hint, not a hard limit (BRD-09 owns the budget). |

---

## 10. Definition of Done

- All 12 steps complete.
- `pyright --strict` and `ruff check` clean on changed files.
- `pytest backend/tests/test_llm_*.py -q -p no:postgresql` green.
- `pytest backend/tests/ -q -p no:postgresql` green (full suite must still pass with config rename).
- BRD-05 §6 checklist items 1-6, 8 ticked; item 7 (integration test with real API) marked manual-only.
- Reviewer score ≥ 9/10.
- Index, decisions log, and lessons log updated per Memory Protocol.
