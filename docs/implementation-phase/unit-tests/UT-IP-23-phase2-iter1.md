# UT-IP-23 Phase 2 — Temporal Sensitivity Routing (WP-1)

**Phase**: 2 (WP-1 Temporal Sensitivity)
**Iteration**: 1
**Date**: 2026-05-28

## New test files

| File | Tests | Purpose |
|---|---|---|
| [backend/tests/test_classify_temporal.py](backend/tests/test_classify_temporal.py) | 10 | `derive_temporal_sensitivity` heuristic over all 4 buckets + edge cases (capital→static, 2025 year→volatile, current price→realtime, COMPARATIVE→volatile, population→slow_changing) |
| [backend/tests/test_plan_temporal_routing.py](backend/tests/test_plan_temporal_routing.py) | 4 | `create_plan` source routing: REALTIME→`["tavily"]`; VOLATILE→`["tavily","wikipedia"]`; STATIC+TRIVIAL+FACTUAL→`["wikipedia"]`; SLOW_CHANGING→no override; mirrored on `PlanCreatedEvent.temporal_sensitivity` |
| [backend/tests/test_kind_ceiling_temporal_penalty.py](backend/tests/test_kind_ceiling_temporal_penalty.py) | 3 | `apply_ceiling` ×0.85 only when DIRECT + volatile/realtime + stale_majority; STATIC + stale → no penalty; WEIGHTED + stale → no penalty; `is_stale_majority` semantics (missing dates count as stale ≥ 50%) |
| [frontend/src/components/molecules/TemporalSensitivityBadge.test.tsx](frontend/src/components/molecules/TemporalSensitivityBadge.test.tsx) | 5 | All 4 sensitivity values render with correct label/variant; realtime uses warning variant |

## Modified test files

| File | Reason |
|---|---|
| [backend/tests/test_agent_orchestrator.py](backend/tests/test_agent_orchestrator.py) | 3× `_FakeSource.search` now accepts `**_kwargs` for new `days` keyword |
| [backend/tests/test_agent_tasks_search.py](backend/tests/test_agent_tasks_search.py) | `_FakeSource.search` accepts `**_kwargs` |
| [backend/tests/test_tool_called_query_length.py](backend/tests/test_tool_called_query_length.py) | `_FakeSource.search` accepts `**_kwargs` |
| [backend/tests/test_seams_source.py](backend/tests/test_seams_source.py) | `_Fake` adds `fetch_full` to satisfy extended Source Protocol |
| [frontend/src/components/molecules/PlanPreview.test.tsx](frontend/src/components/molecules/PlanPreview.test.tsx) | Pre-existing; covers new `temporalSensitivity` prop wiring (6/6 pass) |

## Test results

### Backend (full suite)

```
686 passed in 117.67s
```

(`pytest_ip23_phase2_iter2.txt` initial run had 1 unrelated fail in `test_seams_source.py::test_source_protocol_is_runtime_checkable` due to Protocol extension; fixed in iter 3 → 686/686 green.)

### Frontend (targeted)

```
src/components/molecules/TemporalSensitivityBadge.test.tsx (5 tests) ✓
src/components/molecules/PlanPreview.test.tsx (6 tests) ✓
Test Files  2 passed (2)
     Tests  11 passed (11)
```

### Frontend (full suite)

```
Test Files  1 failed | 66 passed (67)
     Tests  1 failed | 469 passed (470)
```

**Single failure pre-exists**: `UsernameModal.test.tsx` expects `data-variant="default"` but the component sets `variant="strong"`. UsernameModal source + test were NOT touched in Phase 2. Documented as DEGRADED — out-of-scope follow-up.

## Coverage

All new code paths in WP-1 reached:

- `derive_temporal_sensitivity` (all 4 buckets, all marker types)
- `create_plan` temporal routing branches
- `apply_ceiling` stale-penalty branch (positive + negative)
- `is_stale_majority` (missing/fresh/stale mix, days_filter=None, empty list)
- `EvidenceItem.source_published_date` (parsed in `_fold_events`, surfaced via search.py)
- Frontend `TemporalSensitivityBadge` (all variants)
- Frontend `PlanPreview` temporal-only and complexity+temporal render branches
