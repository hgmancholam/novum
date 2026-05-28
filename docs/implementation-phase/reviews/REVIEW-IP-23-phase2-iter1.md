# REVIEW-IP-23 Phase 2 — Temporal Sensitivity Routing (WP-1)

**Phase**: 2 (WP-1)
**Iteration**: 1
**Reviewer**: self-review (orchestrator)
**Date**: 2026-05-28

## Scope

Implements BRD-23 WP-1: derive `TemporalSensitivity` at classification time, thread it through planning + search, narrow Tavily date window for volatile/realtime, drop stale Wikipedia for realtime, apply a stale-citation ceiling penalty for DIRECT answers, surface in UI.

## Files changed

### Backend (16)

1. `backend/app/domain/enums.py` — new `TemporalSensitivity` enum
2. `backend/app/domain/events.py` — `temporal_sensitivity` on QuestionClassified + PlanCreated; `source_published_date` on EvidenceAdded
3. `backend/app/config.py` — `temporal_stale_penalty = 0.85` (and pre-staged Phase 3/4 settings)
4. `backend/app/agent/tasks/classify.py` — marker tables + `derive_temporal_sensitivity` (pure function); `classify_question` 4-tuple preserved (autonomous decision: 13 callers unchanged)
5. `backend/app/agent/orchestrator.py` — calls `derive_temporal_sensitivity`, sets `state.temporal_sensitivity`, threads into events
6. `backend/app/agent/run_state.py` — `RunState.temporal_sensitivity`, `RunState.tavily_days_filter`, `EvidenceItem.source_published_date`
7. `backend/app/agent/tasks/plan.py` — `temporal_sensitivity` parameter; routing override; mirrored onto event
8. `backend/app/agent/tasks/search.py` — `_TAVILY_DAYS_BY_TEMPORAL`, `_parse_published_date`, drops wiki for realtime, threads `days` and `source_published_date`
9. `backend/app/seams/source.py` — Protocol extended with `days` kwarg + `fetch_full`
10. `backend/app/sources/base.py` — default `fetch_full → None`
11. `backend/app/sources/tavily.py` — forwards `days` to Tavily client
12. `backend/app/sources/wikipedia.py` — accepts/ignores `days`
13. `backend/app/llm/prompts.py` — appended temporal rules (classifier) + stale-citation guidance (judge)
14. `backend/app/confidence/kind_ceiling.py` — `is_stale_majority` + DIRECT-only stale penalty
15. `backend/app/confidence/calculator.py` — threads temporal + stale into ceiling
16. `backend/app/agent/runner.py` — `_fold_events` handles new optional keys

### Frontend (4)

17. `scripts/export_types.py` — `TemporalSensitivity` added to enum export list
18. `frontend/src/types/events.ts` — regenerated
19. `frontend/src/components/molecules/TemporalSensitivityBadge.tsx` — new molecule (BRD-23 §15.3 Q5 Advisory E)
20. `frontend/src/components/molecules/PlanPreview.tsx` — renders badge

### Tests (8)

21–24. New: `test_classify_temporal.py`, `test_plan_temporal_routing.py`, `test_kind_ceiling_temporal_penalty.py`, `TemporalSensitivityBadge.test.tsx`
25–28. Modified test fakes: `test_agent_orchestrator.py`, `test_agent_tasks_search.py`, `test_tool_called_query_length.py`, `test_seams_source.py`

## Scoring rubric (0–10)

| Criterion | Score | Notes |
|---|---:|---|
| **Spec adherence** (BRD-23 §3, §4.5, §15.3 Q3–Q6, Advisories C/E) | 10 | All required enum values; FSM order preserved; `_fold_events` reads dicts; badges live in `molecules/`; SLOW_CHANGING leaves Wikipedia in cascade; doc amendment deferred to Phase 3 per BRD §15.3 Q6 |
| **Architectural rules** | 10 | Append-only events (all new keys optional); 3 seams intact; `extra="allow"` on event models; English-only; no LangGraph/Redis introduced |
| **Type safety / contracts** | 10 | All new optional fields `T \| None = None`; FE↔BE types regenerated; `pyright`/`get_errors` clean on all 12 backend + FE files |
| **Test coverage** | 9 | 22 new test cases; all paths covered (S, J, ceiling penalty, fold, both badges); could add a deterministic E2E trace fixture but defers to Phase 4 (Advisory D) |
| **Backwards compatibility** | 10 | `classify_question` 4-tuple preserved; new optional fields; no event-type rename; replay-safe |
| **Code style** | 9 | English-only; no new comments unless WHY; one minor concern: marker frozensets at module scope are documented by their constant names alone |
| **Performance** | 10 | No new IO; one extra heuristic call per classification |
| **Resilience** | 9 | Test fakes had to be widened (`**_kwargs`); production code passes `days` only when not None |
| **UX** | 9 | Badge variant maps to severity; uses existing tokens; standalone render when complexity absent |
| **Risk** | 9 | Two callers (orchestrator + tests) needed update; isolated by the seam |

**Aggregate: 9.5/10 — APPROVED.**

## Autonomous decisions

1. **`classify_question` 4-tuple preserved.** 13 callers destructure the tuple. Adding a 5th element would have broken every existing test. The temporal value flows through a separate pure function (`derive_temporal_sensitivity`) invoked from the orchestrator. Tradeoff: one extra call per classification (cheap; deterministic regex).
2. **Test fakes widened with `**_kwargs`** instead of altering production code with `inspect`. Rationale: keeps `Source` Protocol clean and honest; test fakes already were structural-typing approximations.
3. **`is_stale_majority` counts missing dates as stale.** Conservative: a stale-leaning source has no harder evidence than a dateless one for time-sensitive questions.

## Pre-existing failure (DEGRADED, out of scope)

`frontend/src/components/organisms/UsernameModal.test.tsx::renders the dialog with token-based classes` expects `data-variant="default"`; the component currently uses `variant="strong"`. UsernameModal source + test were NOT modified in this Phase. Recommend a follow-up ticket aligned with the design token migration.

## Outputs

- `pytest_ip23_phase2_iter1.txt` (initial 11-file run: 110/110 + 9 fakes failing on `days`)
- `pytest_ip23_phase2_iter2.txt` (full suite after fake widening: 685/686, 1 seam-protocol fail)
- After test_seams_source fix: full suite **686/686 green**
- `vitest_ip23_phase2_iter1.txt` (initial — PlanPreview transform error from earlier mangled JSX)
- `vitest_ip23_phase2_iter2.txt` (after JSX repair: 11/11 targeted; 469/470 full with 1 pre-existing UsernameModal fail)

## Verdict

**APPROVED 9.5/10** — proceed to Phase 3 (WP-3 Authority Tiering).
