# Unit Tests — IP-23 Phase 1 (WP-4 Query Hygiene) — Iter 1

## Coverage of new code
| Symbol | Test |
|---|---|
| `ToolCalledEvent.query_length_tokens` (field) | `test_tool_called_event_accepts_query_length_tokens_and_tavily_days_filter`, `test_query_length_tokens_set_on_every_tool_called_event` |
| `ToolCalledEvent.tavily_days_filter` (field) | `test_query_length_tokens_absent_on_pre_brd23_replay`, `test_tool_called_event_accepts_...` |
| `_count_query_tokens` | `test_query_length_tokens_counts_whitespace_split_only` |
| `PLANNER_SYSTEM_PROMPT` query-hygiene clause | `test_planner_system_prompt_contains_*` ×5 |

## Results
- 47/47 passed (targeted batch).
- 669/669 passed (full backend suite, 126.98s).

## Coverage estimate
- New code (events.py +2 fields, search.py +helper+1 line, prompts.py +1 block): all covered by direct tests.
- No new branches introduced (every new value is a constant or whitespace split).
- Functional coverage **≥ 95 %** for Phase 1 deltas.
