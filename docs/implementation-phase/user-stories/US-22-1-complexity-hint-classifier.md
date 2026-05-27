# US-22-1: Complexity hint emitted by the classifier

**Story ID:** US-22-1
**Title:** Classifier emits `complexity_hint` on `QuestionClassifiedEvent`
**BRD Reference:** BRD-22
**Priority:** High
**Estimated Effort:** S
**Status:** Draft (F1 — awaiting Auditor)

---

## User Story

**As a** research-agent orchestrator
**I want** the classifier to label each question as `trivial`, `standard`, or `deep` immediately after typing it
**So that** downstream planning can scale claim count, source count, and critique passes to the question's actual research depth — and trivial-fact questions like "What is the capital of Japan?" stop burning ~10 min of round-1 work

---

## Acceptance Criteria

### Scenario 1: Trivial fact question
```gherkin
Given the user submits "What is the capital of Japan?"
And the classifier LLM returns question_type="factual" with classifier_confidence=0.93
When classify_question runs
Then the emitted QuestionClassifiedEvent.complexity_hint == "trivial"
And  the heuristic recorded len(words)=6 AND single_named_entity=True AND confidence>=0.80
```

### Scenario 2: Standard comparative question
```gherkin
Given the user submits "PostgreSQL vs MongoDB for a small SaaS team"
And the classifier returns question_type="comparative" with classifier_confidence=0.78
When classify_question runs
Then QuestionClassifiedEvent.complexity_hint == "standard"
And  the trivial branch is rejected because question_type is not in {factual, definitional}
```

### Scenario 3: Deep state-of-art question
```gherkin
Given the user submits "What are the long-term societal risks of AI-generated code reaching production in 2026?"
And the classifier returns question_type="state_of_art" with classifier_confidence=0.71
When classify_question runs
Then QuestionClassifiedEvent.complexity_hint == "deep"
And  the heuristic recorded len(words)>=16 OR classifier_confidence<0.55
```

### Scenario 4: FACTUAL but multi-entity → coerced to standard
```gherkin
Given the user submits "Compare the capital of Japan with the capital of South Korea"
And the classifier returns question_type="factual" with classifier_confidence=0.82
When classify_question runs
Then QuestionClassifiedEvent.complexity_hint == "standard"
And  the trivial branch was rejected because two named entities were detected
```

### Scenario 5: Low-confidence classification never triggers `trivial`
```gherkin
Given the classifier returns classifier_confidence=0.55 for any question_type
When classify_question runs
Then QuestionClassifiedEvent.complexity_hint != "trivial"
```

### Scenario 6: Replay of pre-BRD-22 event tolerates missing field
```gherkin
Given a historical events.jsonl row with QuestionClassifiedEvent lacking complexity_hint
When the orchestrator replays it
Then no validation error is raised
And  the field is treated as None (downstream consumers default to "standard")
```

---

## Technical Notes

### Backend Considerations
- Heuristic is **deterministic** and **synchronous** — no extra LLM call. Runs after `llm.call(role=CLASSIFIER)` returns.
- New enum `ComplexityHint` in `app/domain/enums.py`. String values: `"trivial"`, `"standard"`, `"deep"`.
- New optional field `complexity_hint: ComplexityHint | None = None` on `QuestionClassifiedEvent` (`extra="allow"` preserved).
- Single-entity heuristic: scan for **contiguous capitalised tokens** (excluding sentence-initial common words like "What", "Why", "How", "Is", "Are"). One span = single entity; ≥ 2 distinct spans = multi-entity.
- Thresholds (`min_trivial_confidence=0.80`, `max_trivial_words=8`, `min_deep_words=16`, `max_deep_confidence=0.55`) live in `app/config.py` for tunability — defaults from BRD-22 §4.5.
- Language policy: identifiers, log messages, comments — all English (per `/memories/language-policy.md`).

### Frontend Considerations
- `scripts/export_types.py` regenerates `frontend/src/types/events.ts` after the Pydantic change. Never hand-edit.
- New molecule `ComplexityBadge.tsx` consuming the field; render in Center Panel `C5` planning state and `C13` terminal state (per `ui-prototype.md §3`).

### Database Changes
- None. Event log additive only.

### API Changes
- None at the route level. The SSE stream automatically carries the new field via the existing `events` envelope.

---

## UI/UX Notes

- `ComplexityBadge` strings (microcopy per BRD-22 §4.10):
  - `trivial` → `"Quick lookup"`
  - `standard` → `"Standard research"`
  - `deep` → `"Deep investigation"`
- Use existing shadcn `Badge` primitive; variants `secondary` / `default` / `outline` respectively.
- a11y: badge has `role="status"` and `aria-label` mirroring the visible text.

---

## Dependencies

- [ ] BRD-22 approved (F1)
- [ ] `QuestionClassifiedEvent` exists (BRD-02 / BRD-07)

---

## Test Cases

| ID | Test Description | Type | Priority |
|---|---|---|---|
| TC-01 | Trivial: "What is the capital of Japan?" → `trivial` | Unit | High |
| TC-02 | Standard comparative → `standard` | Unit | High |
| TC-03 | Deep state-of-art (≥ 16 words) → `deep` | Unit | High |
| TC-04 | Multi-entity FACTUAL → `standard` (NOT `trivial`) | Unit | High |
| TC-05 | classifier_confidence=0.55 + FACTUAL → `standard` | Unit | High |
| TC-06 | Single-entity + classifier_confidence=0.81 + 6 words + DEFINITIONAL → `trivial` | Unit | Medium |
| TC-07 | Historical replay tolerates missing field | Unit | High |
| TC-08 | FE: ComplexityBadge renders each variant; jest-axe passes | Unit | Medium |

Test file: `backend/tests/test_classify_complexity.py`.
FE test file: `frontend/src/components/molecules/ComplexityBadge.test.tsx`.

---

## Definition of Done

- [ ] `ComplexityHint` enum added and exported
- [ ] `QuestionClassifiedEvent.complexity_hint` field present (optional)
- [ ] `classify_question` returns the heuristic value
- [ ] `backend/tests/test_classify_complexity.py` covers TC-01..TC-07, all green
- [ ] `scripts/export_types.py` regenerated and committed
- [ ] `ComplexityBadge.tsx` + test exist; jest-axe a11y green
- [ ] Coverage ≥ 80 % on modified modules
- [ ] Reviewer score ≥ 9 / 10 (F4)
- [ ] Memory bank updated (`decisions-history.md`)

---

## Notes

The heuristic intentionally does NOT call an LLM — it must be free of latency and provider risk. Edge cases that escape the heuristic (e.g. ambiguous "Paris" — city or person) are caught later by the existing IP-21 G9 empty-comparative detector and surfaced via `AmbiguityDetectedEvent`.

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | BSA Agent | Initial creation (F1) |
