# Code Review Report: BRD-02 Pydantic Domain Models & Event System

**Review ID:** CR-02-001
**BRD Reference:** [BRD-02-domain-models.md](../brds/BRD-02-domain-models.md)
**Implementation Plan:** [IP-02-domain-models.md](../implementation-plans/IP-02-domain-models.md)
**Reviewer:** Reviewer Agent
**Date:** 2026-05-26
**Iteration:** 1

---

## Executive Summary

The implementation delivers the complete Pydantic v2 domain layer required by BRD-02: the six domain enums (`StopReason` × 7, `QuestionType` × 5, `OutputFormat` × 2, `EventType` × 19, `EvidencePolarity` × 3, `SourceType` × 2), the 19 event classes with `BaseEvent` and all nested DTOs, the `Event` discriminated union with `EVENT_TYPE_MAP` and `FORKABLE_EVENTS` registries, the run DTOs (`RunCreate`, `RunResponse`, `RunListItem`, `RunForkRequest`), the confidence DTOs with a weighted `StructuralConfidence.score` property, the rewritten `scripts/export_types.py` that writes a non-empty TypeScript file, and a committed auto-generated `frontend/src/types/events.ts` that is strict-clean. The package re-exports a coherent public API from `backend/app/domain/__init__.py`.

The Coder's four declared deviations from BRD §4 (PEP-604 `X | None` for ruff `UP` compliance, file-write instead of stdout in the exporter, enums + JSON Schema only in `events.ts` rather than concrete TS interfaces, and exporting `EvidencePolarity` + `SourceType` in addition to the four BRD-listed enums) are all justified, ruff/pyright-clean, and consistent with IP-02 §5. Every architectural rule from §3 of the Copilot instructions and from `docs/technical-phase/architecture.md` that applies to a pure DTO layer is honored: `model_config = ConfigDict(extra="allow")` is present on `BaseEvent`, on every nested `BaseModel` (`SubClaim`, `SourceResult`, `ContradictionSource`, `AnswerSection`, `Citation`, `StructuralConfidence`, `ConfidenceResult`), the discriminated union exposes a single parse entry point, the storage layer is not abstracted, the weights of the structural confidence formula match RF-12 exactly (0.35 / 0.30 / 0.20 / 0.15), and `FORKABLE_EVENTS` contains exactly the five RF-03 decision points.

The unit-test suite is the strongest aspect of this iteration: 55 tests covering all five ACs by name, parametrized over all 19 event types for AC-02, asserting exact enum value sets against the BRD-01 migration vocabulary, validating bounds for every `Field(..., ge=, le=)` constraint, and checking that `EVENT_TYPE_MAP` is bijective with `EventType`. Tests run offline in 0.07 s — no DB, no network, no LLM.

### Overall Score: **9.6 / 10**

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Code quality | 9.5 / 10 | 25 % | 2.375 |
| Test coverage | 9.5 / 10 | 20 % | 1.900 |
| Architecture compliance | 10 / 10 | 20 % | 2.000 |
| Documentation | 9 / 10 | 15 % | 1.350 |
| Security | 10 / 10 | 10 % | 1.000 |
| Performance | 10 / 10 | 10 % | 1.000 |
| **TOTAL** | | | **9.63** |

Rounded to one decimal: **9.6 / 10**.

### Verdict: APPROVED

Score exceeds the 9.0 pass threshold by 0.6. Zero Blockers, zero Majors, three Minors and two Advisories — all deferrable.

---

## Per-Criterion Breakdown

### Code Quality — 9.5 / 10
The five domain modules read cleanly and consistently. The discriminator pattern is implemented exactly as BRD §4.3 prescribes: every event class carries `type: Literal[EventType.X] = EventType.X` and is wrapped in `Annotated[..., Field(discriminator="type")]` for the `Event` alias. `BaseEvent` carries the five optional persistence fields (`id`, `run_id`, `step_index`, `parent_event_id`, `created_at`) so the same instance is reusable pre- and post-persist (correctly identified in IP-02 §5). `StructuralConfidence.score` is implemented as a `@property` — weights live in code, never in the event payload, which is the single-source-of-truth invariant from RF-12. Validation constraints on `RunCreate` (`min_length=10, max_length=2000` on `question`, `max_length=1000` on `user_context`, `ge=0.0, le=1.0` on `confidence_threshold`) are present and enforced. The exporter writes UTF-8 with explicit `\n` joins, avoiding the Windows newline risk flagged in IP-02 §8. The exporter also resolves the backend path via `Path(__file__).resolve().parent.parent / "backend"`, which is correct in this repo layout. Minor deduction: the `Event` discriminated union is a single ~370-character PEP-604 chain (`A | B | C | ...`) on one line in [events.py#L353](../../../backend/app/domain/events.py#L353). Ruff's default `line-too-long` rule does not fire (or is disabled), but the multi-line `Union[...]` form from BRD §4.3 would be easier to diff when an event type is added or removed.

### Test Coverage — 9.5 / 10
55 tests, three files, 0.07 s wall-time, no fixtures, no DB. AC-02 is parametrized over `list(EventType)` and asserts both `isinstance(parsed, _EXPECTED_CLASS[event_type])` and `parsed.type == event_type`, so the union and the map are exercised together. AC-03 is verified via `model_extra` containing both a scalar (`"future_field": "v2-only"`) and a nested dict (`"another_future_field": {"nested": 1}`), proving deep extra fields survive. `test_event_type_map_covers_every_event_type` and `test_event_type_map_values_are_unique_classes` together close the "forgotten event" risk from IP-02 §8. The enum tests assert both *count* and *exact value set* against the BRD-01 migration vocabulary — drift between `enums.py` and `001_initial_schema.py` would fail at collection. Bounds tests on `RunCreate` cover four corners (lower exclusive, upper exclusive, inclusive 0.0, inclusive 1.0). `StructuralConfidence.score` is verified for three scenarios (all-ones, all-zeros, mixed weighted formula) using `pytest.approx`. Minor deduction: there is no test that the *order* of `Event` union members matches `EVENT_TYPE_MAP` insertion order — not architecturally required, but a one-line test would document the convention. No test confirms that `scripts/export_types.py` produces a file with exactly 19 entries in the `EventType` union; this is verified manually in the Coder report and re-verified in the Verification Log below.

### Architecture Compliance — 10 / 10
Every architectural rule that applies to a DTO layer is satisfied:
- **Discriminated union for events** (architecture §4): `Event = Annotated[Union[...], Field(discriminator="type")]` exposed as the single parse entry point.
- **Schema evolution rule** (architecture §5): `ConfigDict(extra="allow")` on `BaseEvent`, `SubClaim`, `SourceResult`, `ContradictionSource`, `AnswerSection`, `Citation`, `StructuralConfidence`, `ConfidenceResult` — verified by direct read of each model.
- **`stop_reason` is an enum, never free text** (architecture §3 / RF-02): `StoppedEvent.stop_reason: StopReason` typed, and `StopReason` mirrors the seven DB enum values exactly.
- **Confidence formula** (architecture §8 / RF-12): `0.35·coverage + 0.30·agreement + 0.20·diversity + 0.15·no_conflict` — weights match BRD-08 contract and the `min(S, J)` invariant lives in `ConfidenceResult.final`.
- **`FORKABLE_EVENTS` exact set** (RF-03): `{PLAN_CREATED, AMBIGUITY_DETECTED, CONTRADICTION_DETECTED, JUDGE_RULED, STOPPED}` — verified by `test_forkable_events_exact_membership`.
- **`domain/` not `models/`**: ORM models live in `app/models/` (BRD-01) and Pydantic DTOs live in `app/domain/` — no conflation.
- **FE↔BE type contract via `scripts/export_types.py`** (architecture §7): present, runs without errors, writes a non-empty TS file with the 19-member `EventType` union.
- **No new abstractions over the planner / storage / LLM provider**: the Coder did not introduce factories or registries for the three not-seams.

### Documentation — 9 / 10
Every module has a module-level docstring citing its BRD section and the relevant RF (RF-01 for `StopReason`, RF-03 for the `extra="allow"` rationale, RF-04 for detection events, RF-11 for error/recovery events, RF-12 for confidence, RF-14 for plan critic, RF-15 for confidence mismatch). Each event class has a one-line docstring stating its purpose. `StructuralConfidence` carries the formula in its docstring. `RunCreate` field descriptions cite RF-07 and RF-12. The exporter has a module docstring with usage instructions. All artifacts are English-only — identifiers, docstrings, comments, no Spanish leakage. Minor deduction: the `Event` discriminated union and `EVENT_TYPE_MAP` would benefit from a single-line comment near their definition warning future maintainers that *both* must be updated when a new `EventType` is added (the test catches it, but the comment would prevent the failure).

### Security — 10 / 10
At this layer there are no inputs, no IO, no secrets, no SQL, no HTML. `RunCreate` bounds (`question` min 10 / max 2000, `user_context` max 1000) provide cheap input-validation at the FastAPI boundary in BRD-03. `confidence_threshold` is clamped to `[0.0, 1.0]`. Nothing to flag.

### Performance — 10 / 10
Pure Pydantic v2 with no expensive validators, no recursive types, no eager schema rebuilds. `_EVENT_ADAPTER` in the test module is constructed once at import time. The exporter runs in well under a second. No concerns.

---

## Acceptance Criteria Verification

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-01 | All events serialize correctly | PASS | [test_domain_events.py#L57](../../../backend/tests/test_domain_events.py#L57) `test_stopped_event_serializes_all_fields` — asserts `type`, `stop_reason`, nested `answer_sections`, `citations`, and metrics survive `model_dump_json()` round-trip. |
| AC-02 | Discriminated union works | PASS | [test_domain_events.py#L233](../../../backend/tests/test_domain_events.py#L233) `test_type_adapter_parses_each_event_type` — parametrized over all 19 `EventType` values; both `isinstance` and `parsed.type` asserted. |
| AC-03 | Schema evolution works | PASS | [test_domain_events.py#L246](../../../backend/tests/test_domain_events.py#L246) `test_extra_fields_preserved_in_model_extra` — extra scalar **and** extra nested dict survive in `model_extra`. |
| AC-04 | Type export generates valid TypeScript | PASS | [test_domain_events.py#L266](../../../backend/tests/test_domain_events.py#L266) `test_event_type_enum_has_19_values` + manual run of `scripts/export_types.py` produced [frontend/src/types/events.ts#L38-L57](../../../frontend/src/types/events.ts#L38) with the 19-string-literal `EventType` union and no `any`. |
| AC-05 | Forkable events set is correct | PASS | [test_domain_events.py#L270](../../../backend/tests/test_domain_events.py#L270) `test_forkable_events_exact_membership` — asserts set equality with `{PLAN_CREATED, AMBIGUITY_DETECTED, CONTRADICTION_DETECTED, JUDGE_RULED, STOPPED}`. |

All five ACs pass.

---

## Mandatory Compliance Checks

| # | Check | Status |
|---|-------|--------|
| 1 | `StopReason` (×7), `QuestionType` (×5), `OutputFormat` (×2) values match `backend/alembic/versions/001_initial_schema.py` | PASS — string-for-string match verified by direct comparison of `enums.py` with the migration enum literals. |
| 2 | Every `EventType` value has a class + a key in `EVENT_TYPE_MAP` + a member in the `Event` union | PASS — 19/19/19. `test_event_type_map_covers_every_event_type` asserts the map bijection at runtime; the union is read directly in [events.py#L353](../../../backend/app/domain/events.py#L353). |
| 3 | `FORKABLE_EVENTS` contains exactly `PLAN_CREATED, AMBIGUITY_DETECTED, CONTRADICTION_DETECTED, JUDGE_RULED, STOPPED` | PASS — `test_forkable_events_exact_membership`. |
| 4 | `ConfigDict(extra="allow")` on `BaseEvent` and every nested `BaseModel` | PASS — verified on `BaseEvent`, `SubClaim`, `SourceResult`, `ContradictionSource`, `AnswerSection`, `Citation`, `StructuralConfidence`, `ConfidenceResult`. (All seven nested models named in the mandate plus `BaseEvent` itself.) |
| 5 | `StructuralConfidence.score` weights `0.35, 0.30, 0.20, 0.15` | PASS — [confidence.py#L24](../../../backend/app/domain/confidence.py#L24); `test_structural_confidence_score_weighted_formula` recomputes the expected value with the literal weights. |
| 6 | All 5 ACs covered by at least one explicitly-named test | PASS — see AC table above. |
| 7 | English-only code | PASS — full read of the five domain modules, exporter, and three test files confirms no Spanish strings, no Spanish identifiers, no Spanish docstrings. |
| 8 | Tests run offline | PASS — 55 tests in 0.07 s with `-p no:postgresql`; no DB driver, no httpx, no LLM client touched. |
| 9 | `scripts/export_types.py` writes a file and `events.ts` is TS-strict-clean (no `any`) | PASS — `Select-String -Pattern ': any\|\bany\b' -CaseSensitive` returns no matches in `frontend/src/types/events.ts`. |
| 10 | `decisions-history.md` D-004 + `lessons-learned.md` L-004 updated | PASS — D-004 entry present with file inventory, deviations, verification block, and AC coverage; L-004 documents the `-p no:postgresql` workaround discovered during verification. |

All ten mandatory checks pass.

---

## Verification Commands and Outputs (re-run by Reviewer)

```
PS C:\...\backend> .\.venv\Scripts\python.exe -m ruff check app/domain tests/test_domain_enums.py tests/test_domain_events.py tests/test_domain_models.py
All checks passed!

PS C:\...\backend> .\.venv\Scripts\python.exe -m pyright app/domain
0 errors, 0 warnings, 0 informations

PS C:\...\backend> .\.venv\Scripts\python.exe -m pytest tests/test_domain_enums.py tests/test_domain_events.py tests/test_domain_models.py -q -p no:postgresql
.......................................................                  [100%]
55 passed in 0.07s

PS C:\...> Select-String -Path frontend/src/types/events.ts -Pattern 'export type EventType' -Context 0,20
> ... export type EventType =
    | "QuestionAsked" | "PlanCreated" | "PlanCritiqued" | "PlanRevised"
    | "ToolCalled" | "EvidenceAdded" | "ClaimCovered" | "ClaimUncoverable" | "SourceFailed"
    | "AmbiguityDetected" | "ContradictionDetected" | "ContradictionResolved" | "UserContextChallenged"
    | "JudgeRuled" | "ConfidenceMismatch"
    | "AgentErrored" | "ResumedAfterError" | "ResumedAfterCancel"
    | "Stopped";
  (19 string literals — count matches AC-04)

PS C:\...\frontend> Select-String -Path src/types/events.ts -Pattern ': any|\bany\b' -CaseSensitive
  (no matches — events.ts is `any`-free)
```

All four verification commands agree with the Coder's report. No discrepancy.

---

## Strengths

- **Exhaustive parametrized AC-02 test.** `test_type_adapter_parses_each_event_type` iterates `list(EventType)`, so adding a 20th event type without registering it in `EVENT_TYPE_MAP` or `Event` would fail two tests simultaneously. Strong refactor-proofing.
- **Bidirectional enum/migration cross-check.** `test_event_type_values`, `test_stop_reason_values`, `test_question_type_values`, and `test_output_format_values` lock the vocabulary against the BRD-01 migration. Drift in either direction is caught at test time.
- **Weights live in code, not in the event payload.** `StructuralConfidence.score` is a `@property`, not a stored field — this is the correct single-source-of-truth interpretation of RF-12 / BRD-08 and prevents weight drift across persisted events.
- **Exporter writes a file with UTF-8 + explicit `\n`** rather than relying on shell redirection. Avoids the Windows newline pitfall called out in IP-02 §8.
- **`from_attributes=True` on `RunResponse` and `RunListItem`** — correctly anticipates BRD-03 reading directly from ORM rows.
- **All seven `model_extra`-bearing nested models** carry `ConfigDict(extra="allow")`, not just `BaseEvent`. Schema evolution is uniform.
- **L-004 documented immediately** — the pytest-postgresql collection failure was turned into a reusable lesson with a one-line workaround (`-p no:postgresql`) that all subsequent DB-free BRDs will inherit.

---

## Issues Found

### Blockers
*None.*

### Majors
*None.*

### Minors

1. **`Event` discriminated union is a single ~370-character PEP-604 chain.** In [events.py#L353](../../../backend/app/domain/events.py#L353) the union is written as `A | B | C | ... | S` on one line. Functionally identical to BRD §4.3's multi-line `Union[...]` and ruff-clean as configured, but the multi-line form would diff cleanly when an event is added or removed in a future BRD. Recommend either reverting to `Union[...]` over multiple lines or splitting the chain across multiple physical lines with `\` continuations.
2. **No "both registries updated" guard comment.** When a new `EventType` value is added, three places must change: the enum, the `Event` union, and `EVENT_TYPE_MAP`. The tests catch omissions, but a single-line `# When adding an event type: also update EVENT_TYPE_MAP and the Event union above.` near `EVENT_TYPE_MAP` would prevent the test failure from being needed. Cheap defensive documentation.
3. **No test that `scripts/export_types.py` actually produces a 19-member `EventType` union in the output file.** Currently AC-04 is half-verified by `test_event_type_enum_has_19_values` (Python side) and half by manual exporter invocation (TS side). A 10-line test that invokes `_build_output()` and counts `'| "'` occurrences between `export type EventType =` and the next blank line would close the loop and catch any future regression in the exporter's enum rendering.

### Advisories

A. **The generated `events.ts` could carry an ESLint disable banner.** It already announces "DO NOT EDIT" but does not include `/* eslint-disable */` — strict TS passes today, but a future ESLint rule (e.g. `@typescript-eslint/consistent-type-definitions`) could flag the auto-generated file. Defer until the frontend ESLint config matures (BRD-11+).
B. **The exporter's "Event union" output is a comment, not a TypeScript type.** Per the Coder's declared deviation #3 in D-004, concrete TS interfaces are deferred. This is acceptable now (the JSON Schema covers runtime validation and the literal union covers compile-time `switch (event.type)` narrowing) but BRD-10 (SSE streaming) and BRD-13/14 (center/trace panels) will eventually want concrete `interface StoppedEvent { ... }` shapes. Track as a known follow-up.

---

## Final Decision

**APPROVED at 9.6 / 10.**

No required fixes. The three Minors and two Advisories are deferrable to subsequent BRDs (BRD-07 for the union-update comment, BRD-10/BRD-11 for the exporter enrichment and ESLint banner). The Coder may proceed to BRD-03 (FastAPI core / health endpoint / startup wiring) immediately.

---

## Memory Bank Updates

- `docs/implementation-phase/reviews/CR-02-001-domain-models.md` (this file).
- Decisions history will be appended with **D-005: BRD-02 Review APPROVED (9.6 / 10)** in the Orchestrator's update.
- No new lesson to add — L-004 (already filed by the Coder during verification) is the only generalizable insight from this iteration.
