# Code Review Report — BRD-07 Agent FSM & Research Loop

**Review ID:** CR-07-001
**BRD:** [BRD-07-agent-fsm.md](../brds/BRD-07-agent-fsm.md)
**Implementation Plan:** [IP-07-agent-fsm.md](../implementation-plans/IP-07-agent-fsm.md)
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

Quality gate ≥ 9.0 → **passed**. Coder reports 77 tests / 97.4 % coverage on `app/agent/`; no contradictions found in the source while spot-checking.

---

## 2. Acceptance-Criteria Compliance

| AC | Requirement | Status | Evidence |
|----|-------------|:------:|----------|
| AC-01 | FSM follows valid transitions (INIT → PLANNING → CRITIQUING → SEARCHING …) | ✅ | [states.py#L23-L48](../../../backend/app/agent/states.py#L23-L48) + parametrised happy-path test [test_agent_states.py#L55-L72](../../../backend/tests/test_agent_states.py#L55-L72) + end-to-end `test_run_happy_path` [test_agent_orchestrator.py#L162-L201](../../../backend/tests/test_agent_orchestrator.py#L162-L201) |
| AC-02 | Plan critic limits revisions to 2 then proceeds (RF-14) | ✅ | [orchestrator.py#L116-L141](../../../backend/app/agent/orchestrator.py#L116-L141) + `test_rf14_max_revisions_then_proceed` asserts `plan_revision_count == 2` and exactly 2 `PlanRevisedEvent` + 3 `PlanCritiquedEvent` |
| AC-03 | Search budget enforced (`STOPPED_BY_BUDGET`) | ✅ | [orchestrator.py#L143-L152](../../../backend/app/agent/orchestrator.py#L143-L152), `_handle_analyzing` budget branches [orchestrator.py#L154-L188](../../../backend/app/agent/orchestrator.py#L154-L188), `test_budget_exhausted_no_coverage` |
| AC-04 | Judge approval stops run with `JUDGE_CONFIRMED` and `answer_prose` populated | ✅ | [orchestrator.py#L194-L201](../../../backend/app/agent/orchestrator.py#L194-L201) + [orchestrator.py#L249-L264](../../../backend/app/agent/orchestrator.py#L249-L264) (`_stop` only assigns `answer_prose` for `JUDGE_CONFIRMED`); `test_run_happy_path` asserts `stopped.answer_prose == "answer"` |
| AC-05 | Cancellation works | ✅ | `_cancelled` flag checked at top of every loop iteration [orchestrator.py#L82-L84](../../../backend/app/agent/orchestrator.py#L82-L84); `test_cancel_mid_loop` triggers `cancel()` from inside `emit` after `PlanCritiquedEvent` and asserts `USER_CANCELLED` |
| AC-06 (O-04) | RF-06 buckets 6/7/8 → `HONEST_UNANSWERABLE` **before** PLANNING | ✅ | [classify.py#L24-L40](../../../backend/app/agent/tasks/classify.py#L24-L40) + [orchestrator.py#L106-L113](../../../backend/app/agent/orchestrator.py#L106-L113); `test_rf06_unanswerable_stops_before_planning` asserts events == `[QuestionAskedEvent, StoppedEvent]` |
| AC-07 (O-09) | Judge max attempts never yields silent `JUDGE_CONFIRMED` | ✅ | [orchestrator.py#L203-L206](../../../backend/app/agent/orchestrator.py#L203-L206) maps the exhausted branch to `STOPPED_BY_BUDGET`; `test_judge_max_attempts_stops_by_budget_not_silent_confirm` asserts 3 rejections + final `STOPPED_BY_BUDGET` |
| AC-08 (O-14) | RF-15 disconfirmation: re-opens claims + emits `ConfidenceMismatchEvent` when `|S-J| > 0.3` | ✅ | [orchestrator.py#L208-L235](../../../backend/app/agent/orchestrator.py#L208-L235); `test_rf15_disconfirmation_emits_confidence_mismatch` queues S≈1.0, J=0.1 → exactly one mismatch with `divergence > 0.3`, then approve on retry |
| AC-09 (O-11) | `ClaimCoveredEvent.evidence_ids` equal the in-memory `EvidenceItem.event_id` set | ✅ | [search.py#L70-L94](../../../backend/app/agent/tasks/search.py#L70-L94) reuses the same `ev_id` for both the event and the `EvidenceItem`; `test_evidence_ids_in_claim_covered_match_in_memory` asserts `emitted_ids == in_memory_ids == set(covered_events[0].evidence_ids)` |

All 9 acceptance criteria are exercised by at least one assertion that materially observes the behaviour (not just smoke).

---

## 3. Override Compliance (IP-07 §3)

| O-# | Override | Status | Evidence |
|-----|----------|:------:|----------|
| O-01 | No new `CRITIC` role; critique uses `LLMRole.PLANNER` | ✅ | `grep` over `app/agent/**` finds **zero** references to `LLMRole.CRITIC`; [plan.py#L48](../../../backend/app/agent/tasks/plan.py#L48) calls `role=LLMRole.PLANNER` for `critique_plan` with `CritiqueOutput` |
| O-02 | `CritiqueOutput` added to `app/llm/models.py` with the exact 4 fields | ✅ | [models.py#L67-L77](../../../backend/app/llm/models.py#L67-L77) — `acceptable`, `summary`, `issues`, `suggested_changes` match spec verbatim; re-exported in [llm/__init__.py#L16](../../../backend/app/llm/__init__.py#L16) and [#L27](../../../backend/app/llm/__init__.py#L27) |
| O-03 | All `llm.call` sites use `messages=[{"role": "user", …}]` | ✅ | `grep` finds 7 call sites in `app/agent/**`, every one wraps the prompt in a single-element user-message list (classify.py, plan.py ×3, draft.py ×3). No positional misuse, no system-message duplication |
| O-04 | RF-06 honest stop before PLANNING | ✅ | See AC-06. The orchestrator returns `HONEST_UNANSWERABLE` from `run()` directly when `_detect_question_type()` fails — PLANNING is never entered |
| O-05 | No `datetime.utcnow()` anywhere in `app/agent/` | ✅ | `grep` for `utcnow` in `app/agent/**` → 0 matches; sole datetime usage is [run_state.py#L51](../../../backend/app/agent/run_state.py#L51) `datetime.now(UTC)` |
| O-06 | `RunState` modernised: `list[str]` not `set[str]`, `X | None`, `ConfigDict(extra="allow")`, typed event lists | ✅ | [run_state.py#L40-L88](../../../backend/app/agent/run_state.py#L40-L88) — `covered_claims/uncoverable_claims/failed_sources` are `list[str]`; `contradictions: list[ContradictionDetectedEvent]`; `draft_sections: list[AnswerSection] \| None`; all optionals use `X \| None`; `model_config = ConfigDict(extra="allow", arbitrary_types_allowed=False)`. Round-trip serialisation verified by `test_json_round_trip` |
| O-07 | `can_transition` imported at module level (no lazy import inside `transition_to`) | ✅ | [run_state.py#L14](../../../backend/app/agent/run_state.py#L14) imports `can_transition` at the top; `transition_to` body references it directly |
| O-08 | `max_searches` is rounds, not individual tool calls; documented | ✅ | [run_state.py#L62-L65](../../../backend/app/agent/run_state.py#L62-L65) inline comment "measured in rounds (one full call to the search handler), not in individual tool calls (O-08)"; `_handle_searching` increments `search_count` exactly once per round |
| O-09 | Judge exhaustion → `STOPPED_BY_BUDGET`, never silent `JUDGE_CONFIRMED` | ✅ | See AC-07 |
| O-10 | `_stop` folds answer assembly; `answer_prose` populated **only** for `JUDGE_CONFIRMED` | ✅ | [orchestrator.py#L253](../../../backend/app/agent/orchestrator.py#L253) `answer = self.state.draft_answer if reason == StopReason.JUDGE_CONFIRMED else None`; explicitly asserted by `test_budget_exhausted_no_coverage` (`stopped.answer_prose is None`) and `test_rf06_unanswerable_stops_before_planning` |
| O-11 | `EvidenceItem.event_id` equals the UUID of the emitted `EvidenceAddedEvent` | ✅ | See AC-09. The shared `ev_id = uuid4()` is reused in both the event constructor and the `EvidenceItem` constructor — no second `uuid4()` call |
| O-12 | `total_tokens` tracked best-effort via `count_tokens` on input | ✅ partial | [orchestrator.py#L78](../../../backend/app/agent/orchestrator.py#L78) increments once for the original question. The IP allows a lower-bound estimate; only initial question is counted (see Minor M-2) |
| O-13 | Safety-net: `coverage_ratio() == 0.0` AND `search_count >= 5` → `HONEST_UNANSWERABLE` | ✅ | [orchestrator.py#L167-L172](../../../backend/app/agent/orchestrator.py#L167-L172) with constant `_HONEST_UNANSWERABLE_SAFETY_ROUNDS = 5` ([orchestrator.py#L44](../../../backend/app/agent/orchestrator.py#L44)); `test_safety_net_honest_unanswerable_after_5_empty_rounds` |
| O-14 | `ConfidenceMismatchEvent` only when `|S-J| > 0.3` AND judge rejects | ✅ | The divergence branch [orchestrator.py#L218-L228](../../../backend/app/agent/orchestrator.py#L218-L228) is unreachable when `judge_event.passed` is true (early return at L201). The `> 0.3` strict inequality matches spec |
| O-15 | Cancellation checked **before** each handler, handlers idempotent on cancel | ✅ | `if self._cancelled: return await self._stop(StopReason.USER_CANCELLED)` sits at the top of every loop iteration before the `match`; no handler mutates `state.draft_answer` until the LLM call returns (assignment happens inside `draft_answer` *after* `llm.call` resolves — [draft.py#L62-L64](../../../backend/app/agent/tasks/draft.py#L62-L64)) |

**All 15 binding overrides implemented exactly as specified.**

---

## 4. Architectural & Spec Compliance

| Rule | Status | Notes |
|------|:------:|-------|
| Rule #1 — Three plugin seams untouched | ✅ | `search.py` consumes `Source` via `app.sources.registry.get_registry()`; no new seam abstraction introduced. `StoppingSignal` / `OutputRenderer` seams not touched (correctly deferred to BRD-09/BRD-16) |
| Rule #2 — Planner / storage / LLM are NOT seams | ✅ | The FSM **is** the planner. `llm.call` is invoked directly from task modules; no orchestrator-level LLM abstraction layer. No storage code in `app/agent/` |
| Rule #3 — `stop_reason` is a 7-value enum | ✅ | Every `_stop(...)` call uses a `StopReason` enum value: `JUDGE_CONFIRMED`, `STOPPED_BY_BUDGET`, `USER_CANCELLED`, `HONEST_UNANSWERABLE`, `ERRORED`. The unused `HONEST_CONTRADICTION` / `HONEST_AMBIGUOUS` are correctly deferred to BRD-09 |
| Rule #4 — Events append-only | ✅ | Orchestrator only emits via `self._emit`; never reads back, never mutates. `QuestionAskedEvent` is emitted once with `detected_question_type=None` and not retroactively updated after classification — matches the IP code sample |
| Rule #5 — Schema evolution: `extra="allow"` | ✅ | `EvidenceItem` and `RunState` both set `ConfigDict(extra="allow")`; `CritiqueOutput` lives in `app/llm/models.py` which already enforces the project Pydantic convention |
| Rule #7 — FE↔BE type contract | n/a | No event payload shapes were modified; `CritiqueOutput` is internal to LLM-side. `scripts/export_types.py` does not need to run (per IP §2) |
| Rule #8 — `final_confidence = min(S, J)` | ✅ | [draft.py#L85-L86](../../../backend/app/agent/tasks/draft.py#L85-L86) — `final_confidence = min(judge_confidence, structural_confidence)` with `structural_confidence = state.coverage_ratio()` as the documented BRD-08 placeholder |
| English-only language policy | ✅ | Every docstring, comment, log key, error message, prompt template, and identifier is English. Synthesizer prompt remains the BRD-05 English template (which itself instructs the LLM to reply in the user's language) |
| `pyright --strict` / `ruff` cleanliness | ✅ (per Coder report) | `from __future__ import annotations` present in every new module; `type EventCallback = …` (PEP-695); no bare `Any`; `Awaitable`/`Callable` imported from `collections.abc`. Coder reports green; no obvious red flags on read-through |
| Async-first | ✅ | Every handler is `async def`; no blocking IO. The orchestrator never holds a lock |
| No Redis / vector DB / LangGraph references | ✅ | Confirmed by reading every new module |
| Mandatory unit tests (≥ 90 % coverage on `app/agent/`) | ✅ | Coder reports 97.4 % over 77 tests |

---

## 5. Strengths

1. **Override fidelity is exemplary.** Every one of the 15 binding overrides in IP-07 §3 is implemented exactly as specified, including the subtle ones (O-09 STOPPED_BY_BUDGET vs JUDGE_CONFIRMED on judge exhaustion, O-11 shared `ev_id` between event and `EvidenceItem`, O-13 safety-net constant `_HONEST_UNANSWERABLE_SAFETY_ROUNDS = 5`). The implementation reads as if written from the IP rather than the BRD — exactly the intended workflow.
2. **State-machine modelling is crisp.** `TRANSITIONS` is the single source of truth, `transition_to` validates against it, and `_stop` correctly handles the dual terminal targets (`STOPPED` for honest/budget/cancel/judge, `ERRORED` for exception path) by choosing the legal target before transitioning. The `INIT → STOPPED` edge is deliberate to support the RF-06 honest-stop path without entering PLANNING; that justifies the deviation from BRD-07 §4.2's table.
3. **Test depth is genuine, not smoke.** The orchestrator tests use a `_LLMStub` keyed by `response_model.__name__` and a `_FakeRegistry` with deterministic source results, then assert on the *exact* event-type sequence and on **semantic invariants** (e.g. `emitted_ids == in_memory_ids == set(covered_events[0].evidence_ids)` for AC-09; exactly one `ConfidenceMismatchEvent` with `divergence > 0.3` for AC-08). Every AC has a test that would catch a regression in the contract it encodes.
4. **Layered cleanup of BRD-07 drift.** The IP correctly identified six structural problems in BRD-07 §4 (missing `CritiqueOutput`, wrong `llm.call` signature, missing `CRITIC` role, `utcnow` deprecation, `set[str]` Pydantic footgun, judge-max-attempts false positive). The Coder corrected all six without re-litigating the design.
5. **Failure paths are first-class.** `SourceError` is caught inside the search loop and cascades to Wikipedia ([search.py#L57-L67](../../../backend/app/agent/tasks/search.py#L57-L67)). Anything else propagates to `AgentOrchestrator.run()` → `_handle_error` → `AgentErroredEvent` + `StoppedEvent(stop_reason=ERRORED)` — and a test (`test_error_path_emits_agent_errored`) verifies the exact sequence with a non-`SourceError` `RuntimeError`.
6. **Orchestrator constructor refactored sensibly.** `AgentOrchestrator(state, emit)` (taking a pre-built `RunState` and an emit callback) is cleaner than the BRD's `(run_id, question, …, on_event=None)` and is what the future BRD-10 worker will want. IP-07 did not bless either signature, but the chosen shape minimises coupling.

---

## 6. Issues

### 6.1 Blocking

**None.**

### 6.2 Major

**None.**

### 6.3 Minor (non-blocking — informational)

| # | Severity | Location | Observation |
|---|----------|----------|-------------|
| M-1 | Minor | [test_agent_run_state.py#L31-L36](../../../backend/tests/test_agent_run_state.py#L31-L36) | `test_transition_illegal_raises` contains a dead-code line: `state.transition_to(AgentState.STOPPED) if False else None`. The actual assertion-trigger is the next line (`transition_to(DRAFTING)`). The `if False` line is a no-op and probably a refactor leftover (note that `INIT → STOPPED` is in fact a *legal* edge in this implementation, so leaving the line live would have broken the test). Recommend deleting the dead expression — harmless but confusing on read-through. |
| M-2 | Minor | [orchestrator.py#L78](../../../backend/app/agent/orchestrator.py#L78) | O-12 `total_tokens` is incremented exactly once (for the initial question). Every subsequent LLM input (plan prompt, critique prompt, search query, draft prompt, judge prompt, issue-mapping prompt) goes uncounted. IP-07 O-12 calls it a "lower-bound estimate" so this is technically compliant, but a tighter estimate would `count_tokens(user_msg)` inside each task before the `llm.call`. Defer to BRD-17 (calibration) where token accounting becomes load-bearing. |
| M-3 | Minor | [orchestrator.py#L154-L188](../../../backend/app/agent/orchestrator.py#L154-L188) | `_handle_analyzing` has three overlapping branches for the "budget exhausted with no coverage" case: lines 162-166 (all claims resolved, zero coverage), lines 174-178 (search_count >= max with coverage), and lines 179-182 (search_count >= max without coverage). Behaviour is correct but logic flow is slightly tangled — a single `if self.state.search_count >= self.state.max_searches: …` block at the top would compress the three branches into one. Refactor candidate, not a defect. |
| M-4 | Minor | [draft.py#L48-L70](../../../backend/app/agent/tasks/draft.py#L48-L70) | `draft_answer` formats `state.user_context` into the prompt via plain f-string interpolation. Since `user_context` is user-controlled, a hostile user could inject prompt instructions through that field. Not a V1 blocker (the LLM is the only consumer; no downstream eval/exec), but worth a hardening sweep when BRD-10 wires the route — at minimum a sentinel like `<<USER_CONTEXT>>…<</USER_CONTEXT>>` and a system-prompt reminder to ignore instructions inside it. |
| M-5 | Minor | [orchestrator.py#L96](../../../backend/app/agent/orchestrator.py#L96) | The top-level catch is `except Exception as exc: # noqa: BLE001`. This is necessary for the "agent never crashes the worker" invariant and is annotated correctly; however, `BaseException` (e.g. `KeyboardInterrupt`, `asyncio.CancelledError`) will *not* be caught, which is correct asyncio etiquette but worth a one-line docstring note for the next reader. |
| M-6 | Minor | [search.py#L70-L94](../../../backend/app/agent/tasks/search.py#L70-L94) | The cascade `break` fires after a *successful* `search()` call **even if the result list is empty**. This means: Tavily returns `[]` (legitimate "no results") → Wikipedia is skipped. The IP's worded contract ("got results from this source, skip the cascade") is ambiguous here. Current behaviour is acceptable for V1 (the analyser will mark the claim uncoverable after enough rounds), but worth revisiting in BRD-09 where the layered policy gets explicit. Not a defect. |

---

## 7. Code-Quality Findings

- **Naming / typing**: `type EventCallback = Callable[[BaseEvent], Awaitable[None]]` uses PEP-695 syntax cleanly. `_DIVERGENCE_THRESHOLD` and `_HONEST_UNANSWERABLE_SAFETY_ROUNDS` are module-level constants, not magic numbers in handlers — good.
- **Structlog discipline**: every log call uses keyword fields (`run_id=str(self.state.run_id)`, `stop_reason=reason.value`, `iterations=...`). Matches the convention in [llm/client.py](../../../backend/app/llm/client.py).
- **Defensive guards**: `map_issues_to_claims` returns `[]` early when `issues` or `sub_claims` are empty, and filters LLM-returned IDs against the actual claim set ([draft.py#L121-L123](../../../backend/app/agent/tasks/draft.py#L121-L123)) — defends against the planner hallucinating a non-existent claim ID.
- **No dead exports**: `app/agent/__init__.py` and `app/agent/tasks/__init__.py` re-export exactly what is documented in IP §5.9 / §5.10.

---

## 8. Test-Quality Findings

Each AC has at least one **assertion that observes the contract**, not just "the code didn't crash":

| AC | Test | What it actually asserts |
|----|------|--------------------------|
| AC-01 | `test_happy_path_edges_are_legal` (parametrised over 11 edges) + `test_init_cannot_jump_directly_to_searching` | Both positive *and* negative transitions exercised; not just a smoke run |
| AC-02 | `test_rf14_max_revisions_then_proceed` | Asserts `plan_revision_count == 2`, exactly 2 `PlanRevisedEvent` and 3 `PlanCritiquedEvent` — would fail if the cap were off-by-one |
| AC-03 | `test_budget_exhausted_no_coverage` + `test_judge_max_attempts_…` | Both budget axes (search rounds and judge attempts) covered |
| AC-04 | `test_run_happy_path` | Asserts the full event-type sequence and `stopped.answer_prose == "answer"` (would fail if O-10 regressed) |
| AC-05 | `test_cancel_mid_loop` | Triggers cancel from inside `emit` after `PlanCritiquedEvent`, asserts `USER_CANCELLED` — exercises the "between handlers" check, not a synthetic flag flip |
| AC-06 | `test_rf06_unanswerable_stops_before_planning` | Asserts `events == [QuestionAskedEvent, StoppedEvent]` — would fail if a `PlanCreatedEvent` leaked through |
| AC-07 | `test_judge_max_attempts_stops_by_budget_not_silent_confirm` | Asserts both `STOPPED_BY_BUDGET` and `all(not e.passed for e in judge_events)` — guards against the original BRD's false-positive bug |
| AC-08 | `test_rf15_disconfirmation_emits_confidence_mismatch` | Asserts exactly 1 `ConfidenceMismatchEvent`, `divergence > 0.3`, and final approval after re-search — exercises the full disconfirmation loop |
| AC-09 | `test_evidence_ids_in_claim_covered_match_in_memory` | Three-way set equality `emitted_ids == in_memory_ids == set(covered_events[0].evidence_ids)` |

No shallow `assert result is not None` style tests in the orchestrator suite. Task-level test files (`test_agent_tasks_*.py`) cover each task in isolation with `AsyncMock` stubs and parametrised scenarios (bucket 1-5/6-8 split in `classify`, threshold-pass/fail/reject matrix in `draft`, cascade/cap/skip scenarios in `search`).

---

## 9. Recommendation

**APPROVE → proceed to F5 COMPLETE.**

The implementation follows IP-07 with the discipline this kind of cross-module BRD demands. Every override is honoured, every AC has a behavioural test, and the architectural invariants (append-only events, enum-only stop reasons, single-source-of-truth `TRANSITIONS`) are preserved. No blocking or major findings.

Minor items M-1 (dead-code line in one test) and M-2 (tighter token accounting) are cosmetic and may be folded into a future cleanup BRD; they do **not** warrant a re-review cycle.

---

## 10. Items Deferred to Future BRDs

The following are out of scope for BRD-07 and correctly deferred — listed here so the Orchestrator can sequence them:

| Topic | Should land in |
|-------|----------------|
| Real structural confidence S (replaces `coverage_ratio()` placeholder) | BRD-08 |
| Layered stopping policy A+D+B+E+F; `HONEST_CONTRADICTION` and `HONEST_AMBIGUOUS` stop reasons | BRD-09 |
| Persistence of emitted events, run-worker registry, SSE transport, `Last-Event-ID` resume | BRD-10 |
| User-context prompt-injection hardening (M-4) | BRD-10 (route + worker) |
| Tighter `total_tokens` accounting per LLM call (M-2) | BRD-17 (calibration) |
| Logic simplification in `_handle_analyzing` (M-3) | Optional cleanup; bundle with BRD-09 when the layered policy rewrites this handler |
| Cascade behaviour when a source returns `[]` (M-6) | BRD-09 layered policy |
| Fork & resume from ERRORED state | BRD-15 |
| Dedicated `LLMRole.CRITIC` (if ever needed) | Future BRD; not required by V1 |

---

## 11. Memory-Bank Updates

To be appended by Orchestrator on completion:

- `decisions-history.md`: BRD-07 approved at iteration 1 with score 9.40 / 10. Confirms D-017 from Coder report.
- `lessons-learned.md`: Two new entries worth recording —
  1. *Binding overrides in the IP catch BRD drift cheaply.* IP-07 §3 caught six structural bugs in BRD-07 §4 (missing model, wrong signature, deprecated stdlib, Pydantic footgun, false-positive terminal, missing enum value). Pattern: when the BRD is detailed code, audit it against the actual current API surface in the IP, and bind the deltas as numbered overrides.
  2. *Shared UUID between event and in-memory shadow.* Reusing a single `uuid4()` for both an emitted event and its in-memory mirror (`EvidenceItem.event_id`) avoids a future identity-reconciliation step when the worker persists events and is cheap to enforce in tests via set-equality (`emitted_ids == in_memory_ids`).
