# UT-IP-23 Phase 4 — Deep-Fetch on Shallow Evidence (WP-2)

**Phase**: 4 (WP-2)
**Iteration**: 1
**Date**: 2026-05-28

## Test inventory (Phase 4 delta)

### Backend — new files

#### `backend/tests/test_deep_fetch_task.py` (7 cases)

| # | Case | Behavior asserted |
|---|------|-------------------|
| 1 | `test_deep_fetch_budget_table_matches_settings` | budget per `ComplexityHint` matches `settings.deep_fetch_budget_*` |
| 2 | `test_count_deep_fetches_uses_max_of_folded_and_live` | `_count_deep_fetches` returns `max(state.events_count, state.metadata["deep_fetch_count_live"])` |
| 3 | `test_no_shallow_ids_is_a_noop` | empty/None shallow list → returns False, no event emitted |
| 4 | `test_trivial_complexity_blocks_deep_fetch` | TRIVIAL budget = 0 short-circuits even with shallow IDs |
| 5 | `test_success_path_emits_event_updates_text_and_bumps_counter` | success emits `DeepFetchPerformedEvent(success=True)`, replaces `evidence.text`, increments `state.metadata["deep_fetch_count_live"]` |
| 6 | `test_failure_path_emits_event_with_failure_reason` | source returns None → emits event with `success=False, failure_reason="…"` |
| 7 | `test_skips_claims_whose_evidence_is_already_long_enough` | evidence with `len(text) >= deep_fetch_min_snippet_chars` is not re-fetched |

#### `backend/tests/test_sources_fetch_full.py` (6 cases)

Tavily:
1. `test_tavily_fetch_full_returns_source_result_and_truncates` — uses
   `AsyncMock` on `src._client.extract`; asserts content length =
   `DEFAULT_MAX_CONTENT_CHARS * 4 + 3` (incl. `"..."`).
2. `test_tavily_fetch_full_returns_none_on_empty_results` —
   `{"results": []}` → None.
3. `test_tavily_fetch_full_returns_none_on_exception` — extract raises → None.

Wikipedia:
4. `test_wikipedia_fetch_full_returns_source_result_and_truncates` —
   `patch.object(src._wiki, "page", return_value=fake_page)` with
   `MagicMock(exists=lambda: True, text=long_text, fullurl, title,
   summary)`; asserts same truncation cap.
5. `test_wikipedia_fetch_full_returns_none_when_page_missing` —
   `exists() == False` → None.
6. `test_wikipedia_fetch_full_returns_none_on_exception` — `page` raises → None.

#### `backend/tests/test_pre_brd23_wp2_replay.py` (AC-09, 4 cases)

1. `test_pre_wp2_trace_replays_without_deep_fetch_events` — legacy
   `QuestionAsked` line validates through the discriminated `Event`
   `TypeAdapter`.
2. `test_deep_fetch_event_type_is_registered` — `EventType.DEEP_FETCH_PERFORMED`
   and `EVENT_TYPE_MAP["DeepFetchPerformed"] is DeepFetchPerformedEvent`.
3. `test_deep_fetch_event_success_payload_round_trips` — minimal success
   payload validates; `failure_reason is None`.
4. `test_deep_fetch_event_failure_payload_round_trips` — failure payload
   with reason validates; SourceType resolves to WIKIPEDIA.

### Backend — modified

- `backend/tests/test_domain_events.py` — bumped `len(EventType) == 25`,
  added `DEEP_FETCH_PERFORMED` payload in `_payload_for` and
  `DeepFetchPerformedEvent` in `_EXPECTED_CLASS`.
- `backend/tests/test_domain_enums.py` — bumped count to 25 and added
  `"DeepFetchPerformed"` to the expected values set.

### Frontend — new

#### `frontend/src/components/molecules/DeepFetchEntry.test.tsx` (5 cases)

1. `renders success microcopy with title, ms and chars`
2. `falls back to host when title is missing`
3. `renders failure microcopy with reason`
4. `renders failure with default reason when none provided`
5. `has no a11y violations` (jest-axe)

### Frontend — modified

- `frontend/src/lib/eventVisuals.test.ts` — appended
  `"DeepFetchPerformed"` to `ALL_EVENT_TYPES` so the exhaustiveness
  test covers the new event.

## Coverage signal

- Backend: 747 tests (was 732 at Phase 3) — +15 net.
- All 15 new Phase 4 tests pass in `pytest -q` (114.77 s).
- Frontend: 481 / 482 pass (1 pre-existing DEGRADED in UsernameModal).
  All 5 new DeepFetchEntry tests + exhaustiveness test pass.

## Mocks & fixtures

- Tavily: `AsyncMock` patched onto `src._client.extract`.
- Wikipedia: `patch.object(src._wiki, "page", return_value=MagicMock(...))`
  to avoid network access. `anyio.to_thread.run_sync` is exercised
  normally in-process.
- Orchestrator wiring tested indirectly via the task suite + state
  transition tests; no orchestrator integration test was added (see
  REVIEW −0.2 follow-up).

## Acceptance criteria coverage

| AC | Where covered |
|----|----------------|
| AC-01 (judge marks shallow → deep fetch fires) | `test_success_path_emits_event_updates_text_and_bumps_counter` |
| AC-02 (deep fetch updates `evidence.text`) | same case + frontend molecule renders new content length |
| AC-03 (failure persists `failure_reason`) | `test_failure_path_emits_event_with_failure_reason` |
| AC-04 (per-run budget enforced) | `test_deep_fetch_budget_table_matches_settings` + `test_trivial_complexity_blocks_deep_fetch` |
| AC-05 (top-K cap) | enforced by `settings.deep_fetch_top_k`; exercised in the success path test |
| AC-06 (Wikipedia + Tavily both supported) | both branches in `test_sources_fetch_full.py` |
| AC-07 (page text truncated) | `*_truncates` cases on both sources |
| AC-08 (event surfaces in trace UI) | `DeepFetchEntry.test.tsx` + `eventVisuals.test.ts` |
| AC-09 (pre-WP-2 traces replay) | `test_pre_brd23_wp2_replay.py` (all 4 cases) |
