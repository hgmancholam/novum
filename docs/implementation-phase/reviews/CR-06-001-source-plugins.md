# Code Review Report — BRD-06 Source Plugins (Tavily + Wikipedia)

**Review ID:** CR-06-001
**BRD:** [BRD-06-source-plugins.md](../brds/BRD-06-source-plugins.md)
**Implementation Plan:** [IP-06-source-plugins.md](../implementation-plans/IP-06-source-plugins.md)
**Iteration:** 1 of max 5
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent
**Verdict:** ✅ **APPROVED**

---

## 1. Summary

| Criterion              | Score | Weight | Weighted |
|------------------------|------:|-------:|---------:|
| Architecture Compliance| 10/10 |   20 % |    2.00 |
| Code Quality           |  9/10 |   25 % |    2.25 |
| Test Coverage          | 10/10 |   20 % |    2.00 |
| Documentation          |  9/10 |   15 % |    1.35 |
| Security               |  9/10 |   10 % |    0.90 |
| Performance            |  9/10 |   10 % |    0.90 |
| **TOTAL**              |       |        | **9.40 / 10** |

Quality gate ≥ 9.0 → **passed**. Verified: 45 unit tests pass (orchestrator).

---

## 2. Acceptance-Criteria Compliance

| AC | Requirement | Status | Evidence |
|----|-------------|:------:|----------|
| AC-01 | Tavily.search returns mapped `SourceResult` list | ✅ | [tavily.py#L33-L67](../../../backend/app/sources/tavily.py#L33-L67) + [test_sources_tavily.py#L24-L60](../../../backend/tests/test_sources_tavily.py#L24-L60) |
| AC-02 | Wikipedia.search returns hits + content | ✅ | [wikipedia.py#L36-L66](../../../backend/app/sources/wikipedia.py#L36-L66) + [test_sources_wikipedia.py#L40-L98](../../../backend/tests/test_sources_wikipedia.py#L40-L98) |
| AC-03 | Registry exposes Tavily + Wikipedia | ✅ | [registry.py#L23-L42](../../../backend/app/sources/registry.py#L23-L42) + [test_sources_registry.py#L40-L48](../../../backend/tests/test_sources_registry.py#L40-L48) |
| AC-04 | `SourceError` raised on upstream failure with correct type & `recoverable=True` | ✅ | [tavily.py#L45-L51](../../../backend/app/sources/tavily.py#L45-L51), [wikipedia.py#L58-L65](../../../backend/app/sources/wikipedia.py#L58-L65), tests `test_search_raises_source_error_on_client_exception`, `test_search_raises_source_error_on_unexpected_exception` |
| AC-05 | `health_check()` returns True on good creds, False on failure | ✅ | Tests `test_health_check_returns_true_on_success` / `..._false_on_exception` for both sources |

---

## 3. Architecture & Spec Compliance

| Rule | Status | Notes |
|------|:------:|-------|
| Rule #1 — Three plugin seams; `Source` is one | ✅ | `runtime_checkable` `Protocol` in [seams/source.py](../../../backend/app/seams/source.py); registered via [sources/registry.py](../../../backend/app/sources/registry.py). |
| Rule #2 — FSM/storage/LLM are NOT seams | ✅ | Source modules import only from `app.config`, `app.domain.enums`, `app.seams.source`. No imports from `app.llm`, `app.services`, `app.models`. |
| `ai-services.md` §2 Tavily — `search_depth="advanced"`, `include_answer=False`, `include_raw_content=True` | ✅ | [tavily.py#L40-L44](../../../backend/app/sources/tavily.py#L40-L44). |
| `ai-services.md` §3 Wikipedia — second Source for heterogeneity (RF-15) | ✅ | Always-on (no API key dependency); Tavily is conditionally registered. |
| English-only policy | ✅ | All identifiers, docstrings, log keys, exception messages in English. |
| Async-first | ✅ | Wikipedia blocking calls dispatched with `anyio.to_thread.run_sync` ([wikipedia.py#L44-L54](../../../backend/app/sources/wikipedia.py#L44-L54)); explicitly verified by `test_search_runs_sync_calls_off_the_event_loop`. |
| `pyright --strict` cleanliness | ✅ | Full annotations (`dict[str, Any]`, `list[SourceResult]`, `SourceType | None`), `from __future__ import annotations`, no bare `Any` leaks outside the Tavily response envelope, no `from typing import Dict/List`. |
| `ruff` cleanliness | ✅ | No unused imports; no unused `abstractmethod` (BRD's drift removed per IP §4.1); `Field(ge=0.0, le=1.0)` matches numeric-constraint idiom in `app/domain/events.py`. |
| No Redis / vector DB / LangGraph references | ✅ | Confirmed by reading every new module. |
| Append-only event constraints (RF-03) | n/a | Sources are stateless retrieval — no event emission here (per IP §2). |

---

## 4. Strengths

1. **Faithful execution of IP-06 overrides** — every binding deviation from BRD §4 (Pydantic-v2 `SourceResult`, mixin-style `BaseSource` without abstract redeclarations, module-level lazy registry, `anyio.to_thread.run_sync` wrapping, fallback variation pruning, `from exc` chaining, conditional Tavily registration) is implemented exactly as specified.
2. **Test depth is excellent (45 tests)** — protocol structural check + rejection, frozen-model invariants, score-range validation, max_results clamp to [1, 10] in both directions, exception chaining (`__cause__` assertion), thread-offloading verification, fallback variation behavior, deduplication by URL, registry singleton identity, and `reset_registry` semantics for test isolation. The dedicated `test_search_propagates_source_error_unchanged` test guards against accidental double-wrapping — a non-obvious failure mode.
3. **Layer hygiene is crisp** — `sources/__init__.py` does **not** re-export `SourceError` (per IP §4.11); the seam stays the canonical home for the contract types. `BaseSource` is a tiny pure-helper class, avoiding the four-fold method-signature duplication the BRD originally proposed.
4. **Security posture is sound** — API key never logged; user-controlled `query` flows only into the upstream client (no string interpolation into SQL/shell/log message bodies); `User-Agent` for Wikipedia includes a contact per Wikimedia etiquette; conditional Tavily registration prevents constructor explosion when `TAVILY_API_KEY` is unset (relevant for CI).
5. **Structured logging discipline** — every log call uses keyword fields (`query=`, `error=`, `result_count=`), matching the structlog conventions used in [llm/client.py](../../../backend/app/llm/client.py).

---

## 5. Issues

### 5.1 Minor (non-blocking — informational)

| # | Severity | Location | Observation |
|---|----------|----------|-------------|
| M-1 | Minor | [test_sources_wikipedia.py#L194-L210](../../../backend/tests/test_sources_wikipedia.py#L194-L210) | `test_search_propagates_source_error_unchanged` monkeypatches `wikipedia_module.anyio.to_thread.run_sync` by direct assignment + `try/finally` instead of `monkeypatch.setattr`. Functionally correct (and restored on `finally`), but the surrounding test in the same file (`test_search_runs_sync_calls_off_the_event_loop`) already shows the idiomatic `monkeypatch.setattr` pattern — would be consistent to use it here too. **No fix required.** |
| M-2 | Minor | [wikipedia.py#L68-L78](../../../backend/app/sources/wikipedia.py#L68-L78) | `_search_suggestions` includes the original `query` as the first variation, which the caller already tried in the outer branch. One redundant network call in the not-found fallback path. Tiny waste; deferable to V2 with caching. |
| M-3 | Minor | [tavily.py#L70-L78](../../../backend/app/sources/tavily.py#L70-L78) | `health_check` uses `search_depth="basic"` (good — cheaper) but the docstring should also mention the call counts against the Tavily monthly quota; consider noting in a follow-up doc rather than the code. |
| M-4 | Minor | [seams/source.py#L36-L48](../../../backend/app/seams/source.py#L36-L48) | `SourceError` is a plain `Exception` subclass (not `BaseModel`); `recoverable` defaults to `True`. Fine for V1, but when BRD-07 wires `SourceFailed` events, ensure the `recoverable` flag is propagated into the event payload — out of scope here. |

### 5.2 Blocking issues

**None.**

---

## 6. Coverage Snapshot

Orchestrator-verified: `pytest tests/test_seams_source.py tests/test_sources_base.py tests/test_sources_registry.py tests/test_sources_tavily.py tests/test_sources_wikipedia.py -q` → **45 passed**.

Branch coverage spot-check:
- Happy paths: ✅ both sources
- Empty results: ✅ Tavily (`test_search_handles_empty_results_list`, `..._missing_results_key`), Wikipedia (`test_search_returns_empty_when_nothing_found`)
- Error paths: ✅ both sources raise + chain
- Edge cases: ✅ max_results clamping, content truncation, missing optional fields, frozen-model immutability, score-range validation
- Registry isolation: ✅ `reset_registry` fixture, conditional Tavily disablement on missing key

---

## 7. Recommendation

**APPROVE → proceed to F5 COMPLETE.**

The implementation matches the binding IP-06 specification more closely than the BRD itself (which was intentionally overridden in IP §4). Tests are thorough and exercise the exact contracts BRD-07 will depend on (Protocol satisfaction, `SourceError` shape with `source_type` + `recoverable`, registry singleton identity). No blocking concerns. Minor stylistic notes M-1 through M-4 may be folded into future refactors but do not warrant a re-review cycle.

---

## 8. Memory-Bank Updates

To be appended by Orchestrator on completion:
- `decisions-history.md`: BRD-06 approved at iteration 1 with score 9.40/10.
- `lessons-learned.md`: IP-driven overrides of a BRD work well when the IP cites concrete reasons (e.g., `pyright`/`ruff` cleanliness, `anyio` correctness) — pattern worth repeating.
