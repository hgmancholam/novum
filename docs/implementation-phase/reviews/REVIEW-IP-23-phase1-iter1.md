# Review — IP-23 Phase 1 (WP-4 Query Hygiene) — Iter 1

**Plan:** docs/implementation-phase/implementation-plans/IP-23-research-quality-improvements.md
**Scope tasks:** T-23-1-01 … T-23-1-04
**Iteration:** 1
**Reviewer:** Orchestrator (self-review; profile L, fast-tier escalation reserved for failures)

## Files changed (4)
- [backend/app/domain/events.py](../../backend/app/domain/events.py) — added `query_length_tokens: int | None = None` and `tavily_days_filter: int | None = None` on `ToolCalledEvent`.
- [backend/app/llm/prompts.py](../../backend/app/llm/prompts.py) — extended `PLANNER_SYSTEM_PROMPT` with 4-clause query-hygiene block (≤6 tokens, no stop-words outside quoted phrases, quote rule, technical-connector exception).
- [backend/app/agent/tasks/search.py](../../backend/app/agent/tasks/search.py) — added `_count_query_tokens` helper and populated `query_length_tokens=_count_query_tokens(query)` at the single `ToolCalledEvent` construction site.
- [frontend/src/types/events.ts](../../frontend/src/types/events.ts) — auto-regenerated via `python scripts/export_types.py`.

## Tests
- New: [backend/tests/test_planner_query_hygiene.py](../../backend/tests/test_planner_query_hygiene.py) — 5 tests covering the four prompt clauses + self-rewrite directive.
- New: [backend/tests/test_tool_called_query_length.py](../../backend/tests/test_tool_called_query_length.py) — 4 tests: helper purity, event field set at emission, pre-BRD-23 replay tolerated (AC-09), explicit constructor acceptance.

## Results
- Targeted: `pytest tests/test_planner_query_hygiene.py tests/test_tool_called_query_length.py tests/test_domain_events.py tests/test_agent_tasks_search.py` → **47 passed** ([pytest_ip23_phase1_iter1.txt](../../pytest_ip23_phase1_iter1.txt)).
- Full suite: `pytest tests/` → **669 passed in 126.98s** ([pytest_ip23_phase1_full.txt](../../pytest_ip23_phase1_full.txt)). Zero regressions.

## Acceptance criteria
| AC | Status | Note |
|----|--------|------|
| AC-09 schema additive (replay-safe) | ✅ | `test_query_length_tokens_absent_on_pre_brd23_replay` passes; both new fields default to `None`. |
| AC-10 planner emits hygiene-compliant queries | ✅ (instructional) | Prompt clauses enforced; deterministic post-validation deferred (no AC requires it). |
| Observability of query length | ✅ | `query_length_tokens` set on every emitted `ToolCalledEvent`. |
| RF-03 / RF-04 invariants preserved | ✅ | Events still append-only; both fields `Optional[T] = None`. |
| TS contract synced | ✅ | `events.ts` regenerated; only adds two optional `number | null` fields. |

## Score: **9.5 / 10**

Threshold (profile L review.min_score = 9): **PASS**. No iteration needed.

Deductions: −0.5 — `tavily_days_filter` field is declared but not yet populated by any code path (Phase 2 will wire it). Acceptable per plan sequencing.
