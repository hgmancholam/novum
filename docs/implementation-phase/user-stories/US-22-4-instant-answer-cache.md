# US-22-4: Same-question instant-answer cache

**Story ID:** US-22-4
**Title:** Replay prior high-confidence run when the same question is asked again
**BRD Reference:** BRD-22
**Priority:** High
**Estimated Effort:** S
**Status:** Draft (F1 — awaiting Auditor)

---

## User Story

**As a** demo user (and as Giovanny, the primary persona)
**I want** the agent to instantly reuse a prior high-confidence answer when I ask the exact same question again in the same server session
**So that** the second ask completes in ≤ 1 s and the trust surface clearly shows "this is a reused result" instead of silently faking a fresh run

---

## Acceptance Criteria

### Scenario 1: Exact same question, prior run high-confidence → replay
```gherkin
Given a prior run P exists in the in-memory QuestionIndex
And  P.normalised_question == "what is the capital of japan"
And  P.final_confidence == 0.92
And  P.stop_reason == "judge_confirmed"
When a new run for "What is the capital of Japan?" is started
Then RunCreatedEvent is emitted (the new run has its own id)
And  PriorRunHintReplayedEvent is emitted with source_run_id == P.id
And  PriorRunHintReplayedEvent.source_final_confidence == 0.92
And  JudgeRuledEvent and StoppedEvent are emitted, carrying the prior run's verdict and answer payload
And  No QuestionClassifiedEvent, PlanCreatedEvent, SearchStartedEvent, EvidenceAddedEvent are emitted
And  end-to-end wall-clock from RunCreated to Stopped is ≤ 1 s
```

### Scenario 2: Same question, prior run low-confidence → no replay
```gherkin
Given a prior run P with normalised_question == "what is the capital of japan"
And  P.final_confidence == 0.70
When a new run for "What is the capital of Japan?" is started
Then NO PriorRunHintReplayedEvent is emitted
And  the full pipeline runs from classify onward
```

### Scenario 3: Same question, prior run STOPPED_BY_BUDGET → no replay
```gherkin
Given a prior run P with normalised_question == "what is the capital of japan"
And  P.stop_reason == "stopped_by_budget"
And  P.final_confidence == 0.88
When a new run is started
Then NO PriorRunHintReplayedEvent is emitted
And  the full pipeline runs
```

### Scenario 4: Cosine-similar but not identical → no replay
```gherkin
Given a prior run P with normalised_question == "what is the capital of japan"
When a new run is started for "Tell me Japan's capital city"
Then NO PriorRunHintReplayedEvent is emitted
And  the full pipeline runs
```

### Scenario 5: Question normalisation — punctuation and whitespace
```gherkin
Given a prior run P with normalised_question == "what is the capital of japan"
When a new run is started for "  What is THE capital of Japan?? "
Then PriorRunHintReplayedEvent IS emitted (case + punctuation + whitespace ignored)
```

### Scenario 6: Server restart clears the cache (RF-05)
```gherkin
Given a prior run P matched the cache before restart
When the uvicorn worker restarts
And  a new run for the same question is started
Then NO PriorRunHintReplayedEvent is emitted
And  the full pipeline runs
```

### Scenario 7: Trust surface shows the replay
```gherkin
Given PriorRunHintReplayedEvent is in the SSE stream of a run
When the Trace panel renders
Then a row labeled "Same question answered ≤ {Δt} ago (confidence 0.92). Reused that result." is visible
And  the row links to source_run_id via the History panel
```

### Scenario 8: Cache does not leak across users
```gherkin
Given user "alice" has a prior run P matching question Q with confidence 0.92
When user "bob" starts a new run for the same Q
Then NO PriorRunHintReplayedEvent is emitted for bob's run
And  bob's full pipeline runs
```

### Scenario 9: Replay survives FE history pagination
```gherkin
Given a replayed run R was created for user "alice"
When alice loads the History panel
Then R appears as a normal terminal run with stop_reason == "judge_confirmed"
And  R is selectable, forkable, deletable per BRD-20
```

---

## Technical Notes

### Backend Considerations
- New module `app/agent/instant_cache.py` exposing `try_replay(question: str, username: str) -> ReplayPayload | None`.
- `QuestionIndex` (IP-21 WP-6) is the storage substrate — **no new data structure**. The new helper queries it by exact normalised match (NOT cosine).
- `normalise_question`: lowercase → strip Unicode punctuation → collapse internal whitespace → `.strip()`.
- Cache scoping: keyed on `(normalised_question, username)`. Cross-user replay is forbidden (AC-08).
- Threshold constant `INSTANT_CACHE_MIN_CONFIDENCE = 0.85` in `app/config.py`.
- Allowed source stop reasons: `JUDGE_CONFIRMED` only. `STOPPED_BY_BUDGET`, `USER_CANCELLED`, `ERRORED` are NOT eligible.
- Orchestrator change in `start_run`: pre-classify cache lookup. On hit → emit `RunCreatedEvent`, then `PriorRunHintReplayedEvent`, then re-emit a synthetic `JudgeRuledEvent` and `StoppedEvent` carrying the prior payload with NEW timestamps and run_id. Transition straight to terminal state.
- New event type `PriorRunHintReplayedEvent` with fields per BRD-22 §4.4. Discriminated-union member; `extra="allow"`.
- Language policy: all identifiers and log messages English.

### Frontend Considerations
- `TracePanel.tsx`: render new event type as a distinctive "reused result" row.
- `scripts/export_types.py` regenerates `events.ts`.

### Database Changes
- None. The new run still inserts into `runs` and its synthetic events into `events` (RF-03 — event log is the source of truth). Audit trail is preserved.

### API Changes
- None. Same `POST /api/runs` and SSE stream.

---

## UI/UX Notes

- Microcopy: `"Same question answered ≤ {Δt} ago (confidence {x.xx}). Reused that result."`
- `Δt` rendered with `Intl.RelativeTimeFormat` (e.g. "3 minutes ago").
- The row uses the existing trace-event row style; a small `Recycle` Lucide icon distinguishes it.
- Clicking the row navigates to `source_run_id` via existing History-panel selection logic.
- a11y: row has `role="link"` and `aria-label` mirroring visible text including the relative time.

---

## Dependencies

- [ ] BRD-22 approved (F1)
- [ ] IP-21 WP-6 landed (verified ✅ per `IP-21-status-audit.md`)
- [ ] BRD-04 (`username` available in `Run` for cache scoping)

---

## Test Cases

| ID | Test Description | Type | Priority |
|---|---|---|---|
| TC-01 | Cache hit + ≥ 0.85 conf → replay, ≤ 1 s | Integration | High |
| TC-02 | Cache hit + < 0.85 conf → no replay | Unit | High |
| TC-03 | Cache hit + non-JUDGE_CONFIRMED stop_reason → no replay | Unit | High |
| TC-04 | Cosine-similar question → no replay (exact only) | Unit | High |
| TC-05 | Whitespace + punctuation + case normalisation | Unit | High |
| TC-06 | Cross-user scoping (alice's cache invisible to bob) | Unit | High |
| TC-07 | Cache clears on `get_index()` reinitialisation (server-restart proxy) | Unit | High |
| TC-08 | Replayed run appears in History panel as normal terminal | Integration | Medium |
| TC-09 | `PriorRunHintReplayedEvent` round-trips through SSE | Integration | High |
| TC-10 | FE: TracePanel renders replay row + a11y green | Unit | Medium |

Test files: `backend/tests/test_instant_answer_cache.py` (TC-01..09 except TC-10), `frontend/src/components/organisms/TracePanel.test.tsx` (TC-10, extend existing).

---

## Definition of Done

- [ ] `app/agent/instant_cache.py` with `try_replay()` + `normalise_question()` exists
- [ ] `PriorRunHintReplayedEvent` Pydantic model exists; included in discriminated union
- [ ] Orchestrator pre-classify hook calls `try_replay`; on hit, short-circuits to terminal
- [ ] `INSTANT_CACHE_MIN_CONFIDENCE = 0.85` lives in `app/config.py`
- [ ] Cache lookup is scoped by `(normalised_question, username)`
- [ ] `backend/tests/test_instant_answer_cache.py` green; latency assertion ≤ 1 s on TC-01
- [ ] FE types regenerated
- [ ] `TracePanel.tsx` renders new event type; jest-axe green
- [ ] Coverage ≥ 80 %
- [ ] Reviewer score ≥ 9 / 10
- [ ] Memory bank updated

---

## Notes

- **No persistence across restarts** is a deliberate RF-05 design choice — not a bug. Documented in the AC.
- The replay re-emits new events into the new run's stream so all downstream consumers (History panel, fork lineage, delete cascade) behave identically to non-cached runs. The ONLY observable difference is the `PriorRunHintReplayedEvent` marker.
- The synthesized `JudgeRuledEvent` and `StoppedEvent` carry the **prior** numerical values (`structural_confidence`, `judge_confidence`, `final_confidence`, `answer_kind`) — they are a faithful echo, not a recomputation.

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | BSA Agent | Initial creation (F1) |
