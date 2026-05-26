# Code Review Report: BRD-05 LLM Client Integration

**Review ID:** CR-05-001
**BRD Reference:** [BRD-05-llm-client.md](../brds/BRD-05-llm-client.md)
**Implementation Plan:** [IP-05-llm-client.md](../implementation-plans/IP-05-llm-client.md)
**Reviewer:** Reviewer Agent
**Date:** 2026-05-26
**Iteration:** 1

---

## Executive Summary

The implementation delivers the full `app/llm/` package described in IP-05 §4–§6: the four-role `LLMRole` `StrEnum` (`CLASSIFIER`, `PLANNER`, `SYNTHESIZER`, `JUDGE`) with a `ROLE_CONFIGS` `dict[LLMRole, RoleConfig]` populated from `settings`, the `tenacity`-based retry decorator family (`retry_llm`, `retry_llm_critical`) with the BRD-05 §4.4 corrections applied (stdlib `logging.WARNING` int, not the string `"warning"`), the five Pydantic structured-output models (`QuestionClassification`, `SubClaimOutput`, `PlanOutput`, `SynthesizedAnswer`, `JudgeVerdict`), the four English-only system prompts (with the synthesizer prompt instructing the LLM to reply in the user's language as data inside an English prompt — L-001 compliant), the `LLMClient.call(role, messages, response_model)` entry point with module-level litellm wiring (`api_base = settings.llm_api_base`, `api_key = settings.github_token`) and an `instructor.from_litellm(litellm.acompletion)` client, a sync `count_tokens` helper with a `cl100k_base` fallback, and a coherent `app/llm/__init__.py` public re-export surface.

The `app/config.py` migration from BRD-05's `llm_model_researcher/judge/planner/critic` to the ai-services.md `llm_model_classifier/planner/synthesizer/judge` set is clean, with the new `llm_api_base` default pointing at the correct GitHub Models URL (`https://models.github.ai/inference`) — fixing the BRD-05 §4.7 typo (`models.inference.ai.azure.com`). The 23 LLM-suite tests in 25 s and the full 169-test suite in 34 s both pass offline; the implementation strictly follows IP-05's override of BRD-05 (no `CRITIC` role, no `EvidenceAnalysis` / `SearchQueryOutput` / `CritiqueOutput` / `AnswerDraft`, sync `count_tokens`, ai-services.md `(role, messages, response_model)` signature).

The Coder's two declared deviations from BRD-05 are both correct calls and explicitly authorised by IP-05 §8.4 and §8.5: (1) `client: Any` at the `instructor.from_litellm(...)` boundary with a single targeted `# pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]`, with strict typing re-established at `LLMClient.call` via `TypeVar("T", bound=BaseModel)` and a final `cast("T", result)`; (2) replacing the structlog logger in `retry.py` with a stdlib `logging.getLogger("app.llm.retry")` because `tenacity.before_sleep_log` requires a stdlib `logging.Logger` (a `structlog.BoundLogger` would not satisfy its contract). Both are minimum-`Any` pragmatic choices, not architecture violations.

### Overall Score: **9.5 / 10**

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Code quality | 9.5 / 10 | 25 % | 2.375 |
| Test coverage | 9.5 / 10 | 20 % | 1.900 |
| Architecture compliance | 10 / 10 | 20 % | 2.000 |
| Documentation | 9.5 / 10 | 15 % | 1.425 |
| Security | 9.5 / 10 | 10 % | 0.950 |
| Performance | 10 / 10 | 10 % | 1.000 |
| **TOTAL** | | | **9.65** |

Rounded to one decimal: **9.5 / 10** (conservative round-down — see Minors below).

### Verdict: APPROVED

Score exceeds the 9.0 pass threshold by 0.5. Zero Blockers, zero Majors, three Minors and two Advisories — all deferrable.

---

## Per-Criterion Breakdown

### Code Quality — 9.5 / 10

Six small modules read cleanly and consistently. `from __future__ import annotations` is present in every file. No `Any` leaks into the public API surface: `LLMRole`, `RoleConfig`, `ROLE_CONFIGS`, `LLMClient.call`, `count_tokens`, and the five Pydantic models are all fully typed; the only `Any` is the `client: Any` at the litellm/instructor seam, which IP-05 §8.4 and §8.7 explicitly authorise. The `_has_system_message` helper in [client.py#L41](../../../backend/app/llm/client.py#L41) is a clean one-liner that keeps the prepend-vs-not branch in `call` readable. The `retry.py` decorator factory pattern (`create_retry_decorator(max_attempts)` returning a `Callable[..., Any]`) cleanly produces both `retry_llm` (3 attempts) and `retry_llm_critical` (5 attempts) without duplication. `ROLE_CONFIGS` is populated from `settings.*` at module import, so a deployment can override any model via env var without code change — matches IP-05 §3 and the rate-limit mitigation in ai-services.md §1.4. The prompts module is plain string constants plus a `ROLE_PROMPTS` dict — no premature abstraction. Minor deduction: the `cast("T", result)` in [client.py#L88](../../../backend/app/llm/client.py#L88) is technically redundant because `client: Any` makes `client.chat.completions.create(...)` return `Any` and pyright accepts `Any` as `T`; keeping the cast is fine (it documents intent) but a one-line comment explaining why the cast survives the `Any` boundary would help a future reader.

### Test Coverage — 9.5 / 10

23 tests across four files, 25 s wall-time, no DB, no real network. Coverage of the public surface is effectively 100 %:

- **`test_llm_roles.py`** (4 tests) — asserts all four enum string values, `ROLE_CONFIGS` covers exactly the four roles, every config is well-formed (`model` non-empty, `0.0 ≤ temperature ≤ 1.0`, `max_tokens > 0`, non-empty description), and the **RF-15 cross-family** invariant (`judge_family != synthesizer_family` via the `provider/` prefix split) — this is **AC-06 from IP-05 §7** and is the single most important architectural test in this BRD.
- **`test_llm_retry.py`** (5 tests) — `RETRYABLE_EXCEPTIONS` contains all three `httpx` errors; retries on `TimeoutException` until success on attempt 3; gives up after 3 attempts and re-raises (`reraise=True`); does **not** retry on `ValueError` (non-retryable); `create_retry_decorator(max_attempts=5)` honours the parameter. Covers AC-04 from BRD-05 §5.
- **`test_llm_client.py`** (10 tests) — one happy-path test per role asserting the right `model` / `temperature` / `max_tokens` / `response_model` are forwarded to `client.chat.completions.create`, plus the two prepend-system-prompt invariants (prepend when absent, **do not duplicate** when caller-supplied — IP-05 AC-07), plus a parametrized 4-role success-path test. Covers AC-01 / AC-03 from BRD-05 §5.
- **`test_llm_tokens.py`** (4 tests) — empty string → 0, non-empty → positive, known OpenAI model uses `encoding_for_model`, **monkeypatched `KeyError` falls back to `cl100k_base`** (the test even asserts the fallback encoding name). Covers AC-05.

The mocking strategy (`monkeypatch.setattr(client_module.client.chat.completions, "create", AsyncMock())`) matches IP-05 §5 step 11 verbatim — below the HTTP layer, no `pytest-httpx`, no real LLM calls. Minor deduction: there is no explicit test that `litellm.api_base` and `litellm.api_key` are actually set from `settings` at import time. This is asserted implicitly (a wrong base/key would not change the mocked test outcomes) but a one-line `assert litellm.api_base == settings.llm_api_base` test would close the loop and catch a future refactor that drops the module-level assignment.

### Architecture Compliance — 10 / 10

Every architectural rule from `.github/copilot-instructions.md` §1, §3, §4 and from `docs/technical-phase/ai-services.md` §1 that applies to this BRD is satisfied:

- **`app/llm/client.py::call` is the single LLM entry point** (copilot-instructions §1, ai-services §1.3). No agent code path in this BRD calls `litellm` or `httpx` directly. The `instructor.from_litellm(litellm.acompletion)` wiring is encapsulated.
- **LLM provider is a not-seam** (copilot-instructions §3.2): no `Protocol`, no factory, no registry — the provider is swappable by editing this single module.
- **Four roles, no CRITIC** (ai-services §1.2, IP-05 §8.2): `LLMRole` has exactly `CLASSIFIER, PLANNER, SYNTHESIZER, JUDGE`. No `Critic`, no `Researcher`. The BRD-05 `Researcher`/`Critic` roles and the `CritiqueOutput`/`EvidenceAnalysis`/`SearchQueryOutput`/`AnswerDraft` models were correctly dropped.
- **Correct model assignments** (ai-services §1.2): defaults are `meta/Llama-4-Scout-17B-16E-Instruct`, `deepseek/DeepSeek-V3-0324`, `openai/gpt-5`, `deepseek/DeepSeek-V3-0324`.
- **Correct `api_base`** (ai-services §1.1): `https://models.github.ai/inference`. The BRD-05 `models.inference.ai.azure.com` URL is rejected.
- **Cross-family judge** (RF-15, ai-services §1.2): judge (`deepseek/`) ≠ synthesizer (`openai/`). **Enforced by a dedicated test** ([test_llm_roles.py#L33](../../../backend/tests/test_llm_roles.py#L33) `test_judge_is_cross_family_vs_synthesizer`).
- **Signature matches ai-services §1.3**: `async def call(self, role: LLMRole, messages: list[dict[str, str]], response_model: type[T]) -> T`.
- **Structured outputs only**: every call site passes `response_model`; `instructor` validates. No manual JSON parsing.
- **Retries via tenacity with exponential backoff** (copilot-instructions §4): present, with the BRD-05 `"warning"` typo fixed to `logging.WARNING`.
- **`count_tokens` is sync** (IP-05 §8.7): `def count_tokens(...)` — tiktoken is CPU-bound, so the BRD-05 `async def` was wrong; the implementation correctly drops `async`.
- **English-only artifacts** (L-001): every identifier, docstring, comment, log key, and prompt is English. The single Spanish reference ("Reply in the same language the user used (Spanish by default for user-facing content)" in the synthesizer prompt) is **data inside an English-language prompt**, which IP-05 §8.9 explicitly authorises.
- **Pyright strict + ruff clean** on all changed files (verified — see Verification Log).
- **No new abstractions over the three not-seams** (planner, storage, LLM provider): none introduced.

### Documentation — 9.5 / 10

Every module has a module-level docstring citing the originating doc section (ai-services.md §1.1, IP-05 §5 step 4, RF-06, RF-12, RF-15, L-001). `LLMRole`, `RoleConfig`, the four prompt constants, `LLMClient`, `LLMClient.call`, `count_tokens`, `_has_system_message`, and every Pydantic model carry concise docstrings. The `call` docstring states the prepend-system-prompt contract explicitly. The `client: Any` line carries an inline comment explaining the boundary trade-off. The `retry.py` docstring documents the BRD-05 typo correction. The `prompts.py` docstring documents the Spanish-in-English-prompt nuance for L-001 auditors. Minor deduction: `ROLE_CONFIGS` would benefit from a one-line `# IMPORTANT: judge.model.split('/')[0] must differ from synthesizer.model.split('/')[0] — RF-15` comment near the `JUDGE` entry. The test catches a violation, but the comment would prevent the violation in the first place.

### Security — 9.5 / 10

- `github_token` is read from `settings` (env-only, never logged) and assigned to `litellm.api_key` at module import. `litellm` does not log it.
- `logger.info("llm_call_start", ...)` logs `role`, `model`, `response_model.__name__` — **not** message contents — which avoids leaking user input or prompt secrets into structured logs. IP-05 §8.8 mandate satisfied.
- `_has_system_message` is a pure dict-key check with no injection surface.
- No `eval`, no `exec`, no `subprocess`, no file IO, no SQL.
- `RETRYABLE_EXCEPTIONS` does **not** include `httpx.HTTPError` (the bare parent class), which would over-retry on auth/422 errors. The chosen `TimeoutException` + `ConnectError` + `HTTPStatusError` triple correctly excludes connection-refused-style permanent failures from the retry loop's perspective in this version. Note that `httpx.HTTPStatusError` is broad — it includes 4xx and 5xx alike, so a 401 (bad token) would be retried 3× before raising; this is an Advisory (A-2) below, not a Blocker.

Half-point deduction: `httpx.HTTPStatusError` retry breadth (Advisory A-2). No Blockers.

### Performance — 10 / 10

- Module-level litellm config and instructor patching run once at import — zero per-call overhead.
- `count_tokens` is sync (correctly): tiktoken is CPU-bound, so promoting it to `async` would have created spurious event-loop-blocking surprises with no concurrency benefit.
- `_has_system_message` is `O(n)` over a short messages list.
- Exponential backoff `wait_exponential(multiplier=1, min=1, max=10)` is appropriate for GitHub Models rate-limit behaviour (ai-services §1.4).
- No N+1, no synchronous IO in async paths, no blocking calls inside `LLMClient.call`.

---

## Acceptance Criteria Verification (per IP-05 §7)

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-01 | Planner produces valid `PlanOutput` | PASS | [test_llm_client.py#L57](../../../backend/tests/test_llm_client.py#L57) `test_call_planner_returns_plan_output` |
| AC-02 | Critic evaluates plan | N/A | Deferred to BRD-07 per IP-05 §7 (no CRITIC role in V1) |
| AC-03 | Judge returns `JudgeVerdict` with confidence ∈ [0, 1] | PASS | [test_llm_client.py#L92](../../../backend/tests/test_llm_client.py#L92) `test_call_judge_returns_verdict` (asserts `0.0 <= result.confidence <= 1.0`) |
| AC-04 | Retry on transient errors (3 attempts, exponential backoff) | PASS | [test_llm_retry.py#L16](../../../backend/tests/test_llm_retry.py#L16) `test_retries_on_timeout_then_succeeds` + [test_llm_retry.py#L31](../../../backend/tests/test_llm_retry.py#L31) `test_gives_up_after_three_attempts` |
| AC-05 | Token counting works | PASS | [test_llm_tokens.py#L11](../../../backend/tests/test_llm_tokens.py#L11) `test_count_tokens_returns_zero_for_empty_string` + `test_count_tokens_returns_positive_for_non_empty_string` |
| AC-06 (new) | Judge is cross-family vs synthesizer (RF-15) | PASS | [test_llm_roles.py#L33](../../../backend/tests/test_llm_roles.py#L33) `test_judge_is_cross_family_vs_synthesizer` — asserts `judge.model.split("/")[0] != synthesizer.model.split("/")[0]` |
| AC-07 (new) | Caller-supplied `system` is not duplicated | PASS | [test_llm_client.py#L125](../../../backend/tests/test_llm_client.py#L125) `test_call_does_not_prepend_system_when_present` — asserts exactly one `system` message survives in the forwarded payload |

All 6 applicable ACs pass. AC-02 is correctly deferred.

---

## Mandatory Compliance Checks

| # | Check | Status |
|---|-------|--------|
| 1 | `LLMRole` has exactly `CLASSIFIER, PLANNER, SYNTHESIZER, JUDGE` — no `CRITIC` / `RESEARCHER` | PASS — verified in [roles.py#L18](../../../backend/app/llm/roles.py#L18); `test_role_configs_has_all_four_roles` asserts set equality. |
| 2 | Models match ai-services.md §1.2 defaults | PASS — `meta/Llama-4-Scout-17B-16E-Instruct`, `deepseek/DeepSeek-V3-0324`, `openai/gpt-5`, `deepseek/DeepSeek-V3-0324` in [config.py#L22](../../../backend/app/config.py#L22). |
| 3 | `api_base = "https://models.github.ai/inference"` (not the Azure URL from BRD-05) | PASS — [config.py#L21](../../../backend/app/config.py#L21) and [client.py#L29](../../../backend/app/llm/client.py#L29). |
| 4 | Cross-family judge enforced by a unit test (RF-15) | PASS — `test_judge_is_cross_family_vs_synthesizer`. |
| 5 | `llm.call(role, messages, response_model)` signature matches ai-services.md §1.3 | PASS — [client.py#L51](../../../backend/app/llm/client.py#L51). |
| 6 | `count_tokens` is sync, not async, with `cl100k_base` fallback | PASS — [client.py#L94](../../../backend/app/llm/client.py#L94); `test_count_tokens_falls_back_to_cl100k_base_on_unknown_model`. |
| 7 | `before_sleep_log` uses `logging.WARNING` int (not BRD-05's `"warning"` string) | PASS — [retry.py#L40](../../../backend/app/llm/retry.py#L40). |
| 8 | English-only code (L-001) | PASS — full read of six modules + four test files confirms no Spanish identifiers, docstrings, or log keys. The Spanish reference is inside the synthesizer prompt's instruction to the LLM, not in code. |
| 9 | Tests run offline (no real LLM / HTTP calls) | PASS — `monkeypatch.setattr` on `client.chat.completions.create`; `pytest-httpx` not used; 23/23 tests pass with `-p no:postgresql`. |
| 10 | `pyright --strict` and `ruff check` clean on changed files | PASS — `0 errors, 0 warnings, 0 informations` and `All checks passed!` (re-verified by Reviewer, see Verification Log). |
| 11 | Full test suite still green after the BRD-05 → ai-services.md config rename | PASS — `169 passed in 33.65s`. |

All 11 mandatory checks pass.

---

## Declared Deviations Assessment

| # | Coder's deviation | Reviewer verdict | Rationale |
|---|---|---|---|
| 1 | `client: Any = instructor.from_litellm(...)  # pyright: ignore[...]` at the litellm/instructor boundary; strict typing re-established at `LLMClient.call` via `TypeVar("T", bound=BaseModel)` + `cast("T", result)`. | **Acceptable.** | `litellm.acompletion` and `instructor.from_litellm` ship without full type stubs. The minimum-`Any` posture localises the opacity to one line, with a targeted pyright suppression listing the two specific rule codes (not a blanket ignore). IP-05 §8.4 + §8.7 authorise this exact pattern. Public API surface stays fully typed. |
| 2 | `retry.py` uses a stdlib `logging.getLogger("app.llm.retry")` instead of `structlog.get_logger()`. | **Acceptable.** | `tenacity.before_sleep_log` is typed against `logging.Logger` and uses `Logger.log(level, msg)` directly; a `structlog.BoundLogger` does not satisfy that contract. The remaining LLM logs (`llm_call_start`, `llm_call_complete` in [client.py#L70](../../../backend/app/llm/client.py#L70)) still go through `structlog`, so the project-wide structured-logging discipline is preserved everywhere it matters. |

No undeclared deviations were found.

---

## Issues

### Blockers — none

### Majors — none

### Minors

- **M-1.** Add a one-line `# RF-15: judge family must differ from synthesizer family` comment next to the `LLMRole.JUDGE` entry in `ROLE_CONFIGS` at [roles.py#L52](../../../backend/app/llm/roles.py#L52). The test (`test_judge_is_cross_family_vs_synthesizer`) already catches a violation, but the comment would prevent it.
- **M-2.** Add a tiny test that asserts `litellm.api_base == settings.llm_api_base` and `litellm.api_key == settings.github_token` after importing `app.llm.client` — closes the loop on the module-level wiring step (IP-05 §5 step 7) which is currently only verified transitively.
- **M-3.** Consider documenting on the `client: Any` line at [client.py#L40](../../../backend/app/llm/client.py#L40) why the `cast("T", result)` at [client.py#L88](../../../backend/app/llm/client.py#L88) survives the `Any` boundary (i.e. why pyright does not strip it). One short comment is enough.

### Advisories

- **A-1.** `retry_llm: Callable[..., Any]` annotation in [retry.py#L43](../../../backend/app/llm/retry.py#L43) loses the wrapped function's signature for downstream call sites. This is a known `tenacity` limitation, not something to fix in this BRD, but worth keeping in mind if a future test wants to call `retry_llm(some_async)` and pyright complains about the loss of return-type fidelity.
- **A-2.** `RETRYABLE_EXCEPTIONS` includes the full `httpx.HTTPStatusError`, which means a `401` (bad `github_token`) gets retried 3× before raising. For V1 this is acceptable (free-tier rate-limits surface as `429` inside the same class), but BRD-09 (token-budget) should narrow this to only `4xx` rate-limit and `5xx` codes when it lands.

None of the above block approval. All are deferrable.

---

## Verification Commands and Outputs (re-run by Reviewer)

```
PS C:\...\novum\backend> python -m ruff check .
All checks passed!

PS C:\...\novum\backend> python -m pyright app/llm app/config.py tests/test_llm_roles.py tests/test_llm_retry.py tests/test_llm_client.py tests/test_llm_tokens.py
0 errors, 0 warnings, 0 informations

PS C:\...\novum\backend> python -m pytest tests/test_llm_roles.py tests/test_llm_retry.py tests/test_llm_client.py tests/test_llm_tokens.py -q -p no:postgresql
.......................                                                  [100%]
23 passed in 25.18s

PS C:\...\novum\backend> python -m pytest tests/ -q -p no:postgresql
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 33.65s
```

All four gates pass independently of the Coder's report.

---

## Files Reviewed

| File | LOC (approx.) | Verdict |
|------|---------------|---------|
| [backend/app/config.py](../../../backend/app/config.py) | 47 | OK — clean migration to ai-services.md model set; `llm_api_base` default correct. |
| [backend/app/llm/__init__.py](../../../backend/app/llm/__init__.py) | 34 | OK — alphabetised re-exports, complete public surface, no `Critic`/`Researcher` leakage. |
| [backend/app/llm/roles.py](../../../backend/app/llm/roles.py) | 61 | OK — four-role `StrEnum`, `RoleConfig` `NamedTuple`, `ROLE_CONFIGS` populated from settings. |
| [backend/app/llm/retry.py](../../../backend/app/llm/retry.py) | 47 | OK — stdlib `logging.WARNING`, `reraise=True`, factory pattern reused for `retry_llm` and `retry_llm_critical`. |
| [backend/app/llm/models.py](../../../backend/app/llm/models.py) | 68 | OK — five Pydantic models with `Field(...)` bounds; no dropped role leakage. |
| [backend/app/llm/prompts.py](../../../backend/app/llm/prompts.py) | 84 | OK — four English-only prompts, `ROLE_PROMPTS` dict keyed by `LLMRole`. |
| [backend/app/llm/client.py](../../../backend/app/llm/client.py) | 108 | OK — single boundary `Any`, strict-typed `LLMClient.call`, sync `count_tokens`, structured logs without payload leakage. |
| [backend/tests/test_llm_roles.py](../../../backend/tests/test_llm_roles.py) | 41 | OK — RF-15 test is the most important architectural assertion in this BRD. |
| [backend/tests/test_llm_retry.py](../../../backend/tests/test_llm_retry.py) | 73 | OK — covers retry, give-up, non-retryable, parametrised max-attempts. |
| [backend/tests/test_llm_client.py](../../../backend/tests/test_llm_client.py) | 187 | OK — 10 tests, including parametrised 4-role coverage and the prepend-vs-not invariant. |
| [backend/tests/test_llm_tokens.py](../../../backend/tests/test_llm_tokens.py) | 42 | OK — covers empty, non-empty, known-model, and `KeyError` fallback path. |

Total ≈ 790 LOC added across 11 files for the LLM client integration.

---

## Recommendation

**APPROVED — proceed to F5: COMPLETE.**

The three Minors (M-1, M-2, M-3) and two Advisories (A-1, A-2) are documentation / test-hardening polish that does not affect correctness, security, or architecture. They are noted here for the Coder to fold into the next BRD (BRD-07 will touch `LLMRole` and `ROLE_CONFIGS` again when wiring the agent FSM, which is the natural place to land M-1 and M-3; A-2 belongs in BRD-09 as documented).

The implementation faithfully follows IP-05's resolution of the BRD-05 vs ai-services.md divergence, the test suite locks the four most consequential invariants (RF-15 cross-family judge, single LLM entrypoint, no-CRITIC role surface, prepend-system-prompt contract), and all four quality gates pass on the Reviewer's independent re-run.
