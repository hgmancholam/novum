# US-22-2: Per-complexity planner budget + conditional critique pass

**Story ID:** US-22-2
**Title:** Planner scales claim count, source count, and critique passes by `complexity_hint`
**BRD Reference:** BRD-22
**Priority:** High
**Estimated Effort:** M
**Status:** Draft (F1 — awaiting Auditor)

---

## User Story

**As a** research-agent orchestrator
**I want** the planner to size the plan (claim count, source count, critique passes) based on the classifier's `complexity_hint`
**So that** trivial-fact questions skip the critique pass and request only one source, standard questions behave exactly as today, and deep questions get an extra critique pass that earns better evidence

---

## Acceptance Criteria

### Scenario 1: Trivial fact → 1 claim, 1 source, no critique
```gherkin
Given QuestionClassifiedEvent.complexity_hint == "trivial"
And  QuestionClassifiedEvent.question_type == "factual"
When create_plan runs
Then PlanCreatedEvent.sub_claims has exactly 1 entry
And  PlanCreatedEvent.sources_per_claim == 1
And  No PlanCritiquedEvent is emitted before SearchStartedEvent
And  the FSM transitions PLANNING → SEARCHING without entering CRITIQUING
```

### Scenario 2: Standard question → current behaviour
```gherkin
Given QuestionClassifiedEvent.complexity_hint == "standard"
And  QuestionClassifiedEvent.question_type == "comparative"
When create_plan runs
Then PlanCreatedEvent.sub_claims length is in [2, 4]
And  Exactly one PlanCritiquedEvent is emitted in round 1
And  All other plan fields are byte-identical to pre-BRD-22 output for the same input (regression guard)
```

### Scenario 3: Deep question → extra critique pass
```gherkin
Given QuestionClassifiedEvent.complexity_hint == "deep"
And  QuestionClassifiedEvent.question_type == "state_of_art"
When create_plan runs
Then PlanCreatedEvent.sub_claims length is in [4, 8]
And  Exactly two PlanCritiquedEvent events are emitted in round 1
And  Each PlanCritiquedEvent has a distinct critique_pass_index (1, 2)
```

### Scenario 4: Trivial coercion for incompatible question types
```gherkin
Given QuestionClassifiedEvent.complexity_hint == "trivial"
And  QuestionClassifiedEvent.question_type == "state_of_art"
When create_plan runs
Then the planner coerces complexity to "standard"
And  a structured log entry "complexity_coerced reason=incompatible_type" is recorded
And  PlanCreatedEvent.sub_claims length is in [3, 6]  // standard STATE_OF_ART
```

### Scenario 5: Wikipedia-preferred routing for trivial-factual
```gherkin
Given QuestionClassifiedEvent.complexity_hint == "trivial"
And  QuestionClassifiedEvent.question_type == "factual"
When create_plan runs
Then PlanCreatedEvent.preferred_sources contains "wikipedia"
And  the search step issues a Wikipedia query BEFORE any Tavily query
```

### Scenario 6: Missing `complexity_hint` (replay / pre-BRD-22)
```gherkin
Given QuestionClassifiedEvent.complexity_hint is None
When create_plan runs
Then the planner uses the CLAIM_BUDGETS row keyed by question_type only (current pre-BRD-22 behaviour)
And  PlanCreatedEvent.complexity_hint is None
```

### Scenario 7: Integration — trivial path latency
```gherkin
Given a mocked LLM that returns canned classify/plan/synthesize/judge payloads in <100 ms each
And  question "What is the capital of Japan?"
When the full round-1 pipeline runs
Then total wall-clock from RunCreated to Stopped is < 5 s in the test
And  No PlanCritiquedEvent appears in the event stream
```

---

## Technical Notes

### Backend Considerations
- Replace the flat `CLAIM_BUDGETS: dict[QuestionType, tuple[int, int]]` with a 2-D table keyed on `(QuestionType, ComplexityHint)`, tuple shape `(claims_min, claims_max, sources_per_claim, critique_passes)`. Exact values from BRD-22 §4.6.
- Default fallback (when `complexity_hint` is `None`): treat as `standard`. Preserves replay compatibility.
- `PlanCreatedEvent` gains TWO new optional fields:
  - `expected_experts: list[str] | None = None` (delivered by US-22-3, allocated here)
  - `complexity_hint: ComplexityHint | None = None` (mirrored from classifier for trace-panel UX)
- `critique_passes = 0` ⇒ the orchestrator skips the `CRITIQUING` state. No `PlanCritiquedEvent` emitted, no `PlanRevisedEvent` emitted.
- `preferred_sources: list[str] | None = None` is added as an optional field on `PlanCreatedEvent` to signal Wikipedia-first routing for trivial-factual.
- All identifiers, log messages, comments — English.

### Frontend Considerations
- `TracePanel` already renders critique events; when zero pass, the row is simply absent — no FE change required for skip.
- Render `ComplexityBadge` (from US-22-1) inside the Plan card block.

### Database Changes
- None.

### API Changes
- None.

---

## UI/UX Notes

- When `critique_passes == 0`, the trace shows: `Plan → Search` (no Critique step). The user must be able to see this; the existing trace ordering naturally satisfies it (RF-06-quater).
- No new microcopy strings introduced by this story.

---

## Dependencies

- [ ] US-22-1 merged (`complexity_hint` available)
- [ ] BRD-22 approved (F1)

---

## Test Cases

| ID | Test Description | Type | Priority |
|---|---|---|---|
| TC-01 | Trivial + FACTUAL → 1 claim, 1 source | Unit | High |
| TC-02 | Trivial + DEFINITIONAL → 1 claim, no critique | Unit | High |
| TC-03 | Standard + COMPARATIVE → 2–4 claims, 1 critique | Unit | High |
| TC-04 | Deep + STATE_OF_ART → 4–8 claims, 2 critiques | Unit | High |
| TC-05 | Trivial + STATE_OF_ART → coerced to standard | Unit | High |
| TC-06 | `complexity_hint=None` → standard fallback | Unit | High |
| TC-07 | Trivial + FACTUAL → Wikipedia search before Tavily | Integration | Medium |
| TC-08 | Mocked-LLM round-1 latency < 5 s end-to-end | Integration | High |
| TC-09 | Replay of pre-BRD-22 PlanCreatedEvent succeeds | Unit | High |

Test files: `backend/tests/test_plan_complexity_budget.py` (TC-01..06, TC-09), `backend/tests/test_agent_runner.py` (TC-07, TC-08 — extend existing).

---

## Definition of Done

- [ ] `CLAIM_BUDGETS` upgraded to 2-D table per BRD-22 §4.6
- [ ] Critique skip wired in `app/agent/orchestrator.py` (PLANNING → SEARCHING when `critique_passes==0`)
- [ ] Deep adds second critique pass (PLANNING → CRITIQUING → CRITIQUING → SEARCHING)
- [ ] `PlanCreatedEvent` extended with `complexity_hint`, `expected_experts` (placeholder), `preferred_sources`
- [ ] `backend/tests/test_plan_complexity_budget.py` green
- [ ] Integration test in `test_agent_runner.py` asserts no PlanCritiquedEvent in trivial path
- [ ] FE types regenerated
- [ ] Coverage ≥ 80 %
- [ ] Reviewer score ≥ 9 / 10
- [ ] Memory bank updated

---

## Notes

Adding a **second** critique pass for `deep` is a deliberate cost: it spends extra LLM calls in exchange for evidence quality. The open question of whether deep should use 1 vs 2 critique passes is flagged for the Auditor (see BSA reply).

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | BSA Agent | Initial creation (F1) |
