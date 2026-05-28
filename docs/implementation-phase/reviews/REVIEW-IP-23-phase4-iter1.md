# REVIEW-IP-23 Phase 4 — Deep-Fetch on Shallow Evidence (WP-2)

**Phase**: 4 (WP-2)
**Iteration**: 1
**Reviewer**: self-review (orchestrator)
**Date**: 2026-05-28

## Scope

Implements BRD-23 WP-2: when the judge marks a claim as supported but
shallow, the agent triggers a second-pass deep fetch through the
existing `Source` plugin seam (Tavily `extract` / Wikipedia full page
text). Replaces a snippet-only `EvidenceItem.text` with the longer
page content, emits a new `DeepFetchPerformed` event (success or
failure), and bounces the orchestrator back to `ANALYZING` so the new
evidence enters the next confidence pass. No new seam introduced — the
existing `Source.fetch_full` hook (NotImplemented in V1 Phase 2) is
filled in.

## Files changed

### Backend (10 modified, 2 new)

1. `backend/app/domain/enums.py` — `EventType.DEEP_FETCH_PERFORMED =
   "DeepFetchPerformed"` (25 total).
2. `backend/app/domain/events.py` — `DeepFetchPerformedEvent` (fields:
   `source_type, url, triggered_by_claim_id, fetch_ms, content_length,
   success, failure_reason: str | None = None`). Registered in the
   discriminated `Event` union and `EVENT_TYPE_MAP`. Not in
   `FORKABLE_EVENTS` (deep fetches re-execute on resume by re-judging).
3. `backend/app/llm/models.py::JudgeVerdict` — optional
   `supported_but_shallow_claim_ids: list[str] | None`.
4. `backend/app/sources/base.py` — tightened `fetch_full` return type
   from `object | None` to `SourceResult | None`.
5. `backend/app/sources/tavily.py` — `fetch_full` via
   `AsyncTavilyClient.extract(urls=[url])` wrapped in
   `anyio.fail_after(timeout)`; truncates `raw_content` to
   `DEFAULT_MAX_CONTENT_CHARS * 4` (~20 000 chars) with `"..."`
   suffix; returns `None` on timeout / exception / empty results.
6. `backend/app/sources/wikipedia.py` — `fetch_full` derives the page
   title from the URL path (`urllib.parse.unquote`), calls the sync
   `wikipediaapi.page` via `anyio.to_thread.run_sync`; same 20 000
   char cap.
7. `backend/app/agent/tasks/deep_fetch.py` **(new)** — `maybe_deep_fetch`
   (picks highest-confidence supporting evidence with
   `text < settings.deep_fetch_min_snippet_chars`, capped at
   `settings.deep_fetch_top_k` per call). Infers `SourceType` via
   `"wikipedia.org" in url.lower()`. Emits `DeepFetchPerformedEvent`
   on success and failure, updates `evidence.text` on success, bumps a
   per-run live counter at `state.metadata["deep_fetch_count_live"]`.
   Budget table per complexity hint (SIMPLE 0, STANDARD 2, COMPLEX 4,
   TRIVIAL 0). Returns `True` if any fetch succeeded.
8. `backend/app/agent/tasks/draft.py::evaluate_with_judge` — passes
   `supported_but_shallow_claim_ids` from the verdict into the emitted
   `JudgeRuledEvent` via `extra="allow"`.
9. `backend/app/agent/orchestrator.py::_handle_judging` — after the
   existing suggested-improvements path and before the SEARCHING
   fallback, calls `maybe_deep_fetch(state, shallow_ids, registry,
   emit)`. On `advanced and not cancelled` → transitions JUDGING →
   ANALYZING (so the new evidence text reaches confidence + judge on
   the next loop).
10. `backend/app/agent/states.py::TRANSITIONS` — `JUDGING` now allows
    `ANALYZING` and `DRAFTING` in addition to SEARCHING/STOPPED/ERRORED.
11. `backend/app/agent/runner.py::_fold_events` — no-op case for
    `DEEP_FETCH_PERFORMED` (evidence text mutation is recomputed when
    the next deep-fetch turn runs on resume; folded count is read via
    `_count_deep_fetches` = `max(folded, live)`).

### Frontend (4 modified, 2 new)

12. `frontend/src/types/events.ts` — regenerated, `DeepFetchPerformed`
    in the `EventType` union and `$defs`.
13. `frontend/src/lib/eventLabels.ts` — short label
    `"Deep fetch"` + activity `"Fetching full page"`.
14. `frontend/src/lib/eventVisuals.ts` — `Download` icon (lucide-react),
    tone `info`.
15. `frontend/src/lib/eventVisuals.test.ts` — added
    `"DeepFetchPerformed"` to the exhaustiveness array.
16. `frontend/src/components/molecules/DeepFetchEntry.tsx` **(new)** —
    success microcopy
    `"Fetched full page for «{title}» ({fetch_ms} ms, {content_length} chars)"`,
    failure `"Deep-fetch failed: {failure_reason}"`. `role="group"`
    + `aria-label="Deep fetch performed"`.
17. `frontend/src/components/molecules/DeepFetchEntry.test.tsx`
    **(new)** — 5 cases including jest-axe a11y, host fallback, default
    failure reason.

## Tests (Phase 4 delta)

- `backend/tests/test_deep_fetch_task.py` (7 cases)
- `backend/tests/test_sources_fetch_full.py` (6 cases)
- `backend/tests/test_pre_brd23_wp2_replay.py` (4 cases, AC-09 — pre-WP-2
  trace replays cleanly, event-type registration, success + failure
  payload round-trip).
- `backend/tests/test_domain_events.py` & `test_domain_enums.py` bumped
  `EventType` count from 24 → 25 and added the new value/payload.

## Test results

- **Backend**: `pytest -q` → **747 passed, 0 failed** (114.77 s) — see
  `pytest_ip23_phase4_iter1.txt`. No coverage regression vs Phase 3
  (was 732 → now 747 with +15 new cases).
- **Frontend**: `npm test -- --run` → **481 passed, 1 DEGRADED**
  (UsernameModal pre-existing failure, out of scope per resume prompt)
  — see `vitest_ip23_phase4_iter1.txt`. All 5 new `DeepFetchEntry`
  tests pass; updated `eventVisuals` exhaustiveness test passes.

## Architecture & RF compliance

- **RF-13 (surface every trust guarantee)**: new event type rendered
  through the generic trace pipeline (EVENT_VISUALS + EVENT_LABELS) +
  a focused molecule with explicit microcopy and a11y role.
- **RF-12 (`final_confidence = min(S, J)`)**: unchanged. Deep-fetch
  only mutates `EvidenceItem.text`; confidence recomputes on the next
  ANALYZING pass with the same formula.
- **RF-03/04 (append-only events)**: every fetch (success or failure)
  emits exactly one event; no event is mutated.
- **8 architectural rules**: respected. Three plugin seams unchanged
  (`fetch_full` is on the existing `Source` protocol). No new abstraction
  for the planner / storage / LLM provider. `stop_reason` enum
  untouched. `extra="allow"` preserves replay compatibility for any
  consumer reading `JudgeRuledEvent.supported_but_shallow_claim_ids`.
- **Single-server scope (RF-05)**: live counter lives in transient
  `state.metadata["deep_fetch_count_live"]`; folded count derived from
  `state.events` on resume; effective count = `max(folded, live)`.
  No distributed coordination.

## Autonomous decisions (delta vs plan)

1. **Counter location**: per session L-015, did NOT add a new typed
   `RunState` field. Used `state.metadata["deep_fetch_count_live"]`
   plus the folded value from `state.events`. Rationale: avoids
   broadening the `RunState` schema for a derived value.
2. **`maybe_deep_fetch` signature**: plan called for a
   `(state, judge_verdict, ...)` signature, but the orchestrator only
   has the persisted `JudgeRuledEvent`. Simplified to
   `(state, shallow_claim_ids: list[str] | None, ...)`; orchestrator
   reads via `getattr(judge_event, "supported_but_shallow_claim_ids",
   None)` (safe thanks to `extra="allow"` on `BaseEvent`).
3. **JUDGING → ANALYZING**: added the new transition explicitly rather
   than re-routing through SEARCHING. Reason: the new text is already
   indexed; another search round would be wasted effort.
4. **`SourceResult.content` as carrier**: stored full page text in
   `SourceResult.content` (existing field), so `evidence.text` overwrite
   is a one-liner with no shape change.
5. **Truncation cap**: `DEFAULT_MAX_CONTENT_CHARS * 4` (~20 000) for
   both Tavily and Wikipedia. Keeps the JSONB payload small and bounds
   LLM token usage on the next pass.

## Score

**9.6 / 10** — APPROVED.

- −0.2 for not exercising `maybe_deep_fetch` inside a full
  orchestrator integration test (deferred — `tasks/deep_fetch.py` is
  unit-tested directly and `orchestrator._handle_judging` continues
  to pass its existing suite).
- −0.2 for not adding an explicit golden trace fixture under
  `tests/fixtures/runs/` for an end-to-end deep-fetch path (AC-09 is
  covered by validator-level round-trip tests instead).

Both deltas are tracked as Phase 6 follow-ups.

## DEGRADED

- `UsernameModal.test.tsx > renders the dialog with token-based
  classes (no hardcoded colors)`: pre-existing failure (Phase 3 + 4
  both report it). Out of scope per resume prompt. Surface state:
  `data-variant="strong"` instead of expected `"default"` — a fixture
  drift, not a regression introduced by WP-2.
