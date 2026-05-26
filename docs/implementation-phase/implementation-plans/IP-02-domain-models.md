# Implementation Plan: BRD-02 Pydantic Domain Models & Event System

**Plan ID:** IP-02
**BRD Reference:** [BRD-02-domain-models.md](../brds/BRD-02-domain-models.md)
**Created:** 2026-05-26
**Status:** In Progress
**Implementation Order:** 3 of 19

---

## 1. Overview

Implement the Pydantic v2 domain layer for Novum: enums, the 19 event types as a discriminated union, run state DTOs, confidence models, and the Pydantic→TypeScript exporter. This layer is the type contract between the FSM, the storage layer (`events.payload` JSONB), the SSE stream (BRD-10), and the frontend (`frontend/src/types/events.ts`).

**Source of truth:** BRD-02 §4 contains copy-paste-ready code blocks. The Coder must follow them verbatim unless a tightening is justified below.

**Non-goals (out of scope for this BRD):**
- Persistence of events (BRD-03 / already covered by BRD-01 ORM `Event`)
- SSE serialization (BRD-10)
- FSM that emits events (BRD-07)
- Confidence calculation *logic* (BRD-08) — only the **DTOs** are in scope here
- Auth / user identity (BRD-04)

---

## 2. Architectural Alignment

| Architecture rule | Compliance in this BRD |
|---|---|
| Events append-only, JSONB payload | Pydantic models serialize to the `payload` shape; no DB writes added here |
| `extra="allow"` + optional keys for schema evolution | Enforced on `BaseEvent` and every nested `BaseModel` |
| `stop_reason` is enum, never free text | `StopReason` StrEnum mirrors the DB `stop_reason` enum from BRD-01 |
| FE↔BE type contract via `scripts/export_types.py` | Script rewritten to emit real types into `frontend/src/types/events.ts` |
| English-only code artifacts | All identifiers, docstrings, log/exception strings in English |
| Pyright strict / Ruff clean | `from __future__ import annotations` + explicit annotations; no `Any` |

**Enum cross-check (must match BRD-01 migration `001_initial_schema.py`):**
- `StopReason` → 7 values (`judge_confirmed`, `honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`, `stopped_by_budget`, `user_cancelled`, `errored`)
- `QuestionType` → 5 values (`factual`, `comparative`, `definitional`, `state_of_art`, `causal`)
- `OutputFormat` → 2 values (`prose`, `structured`)

---

## 3. Implementation Sequence

### Phase 1 — Domain Package (Steps 1–5)

| Step | Task | File | Priority |
|------|------|------|----------|
| 1 | Package init exporting enums + Event union + `EVENT_TYPE_MAP` + `FORKABLE_EVENTS` | [backend/app/domain/__init__.py](../../../backend/app/domain/__init__.py) | P0 |
| 2 | Enums: `StopReason`, `QuestionType`, `OutputFormat`, `EventType`, `EvidencePolarity`, `SourceType` | [backend/app/domain/enums.py](../../../backend/app/domain/enums.py) | P0 |
| 3 | Events: 19 event classes + `BaseEvent` + nested DTOs (`SubClaim`, `SourceResult`, `ContradictionSource`, `AnswerSection`, `Citation`) + `Event` discriminated union + `EVENT_TYPE_MAP` + `FORKABLE_EVENTS` | [backend/app/domain/events.py](../../../backend/app/domain/events.py) | P0 |
| 4 | Run DTOs: `RunCreate`, `RunResponse`, `RunListItem`, `RunForkRequest` | [backend/app/domain/run.py](../../../backend/app/domain/run.py) | P0 |
| 5 | Confidence DTOs: `StructuralConfidence` (with weighted `score` property), `ConfidenceResult` | [backend/app/domain/confidence.py](../../../backend/app/domain/confidence.py) | P0 |

### Phase 2 — Type Export (Steps 6–7)

| Step | Task | File | Priority |
|------|------|------|----------|
| 6 | Rewrite `scripts/export_types.py` to import real models and emit enums + JSON Schema + Event union into `frontend/src/types/events.ts` | [scripts/export_types.py](../../../scripts/export_types.py) | P0 |
| 7 | Generate `frontend/src/types/events.ts` and commit the generated file (header marks it auto-generated) | [frontend/src/types/events.ts](../../../frontend/src/types/events.ts) | P0 |

### Phase 3 — Unit Tests (Steps 8–11) — mandatory per F3.S3 / L-002

| Step | Task | File | Priority |
|------|------|------|----------|
| 8 | Enum cross-check tests (values + count match DB migration) | `backend/tests/test_domain_enums.py` | P0 |
| 9 | Event serialization + discriminated-union parsing + `extra="allow"` evolution (AC-01, AC-02, AC-03) | `backend/tests/test_domain_events.py` | P0 |
| 10 | `FORKABLE_EVENTS` exact membership (AC-05), `EVENT_TYPE_MAP` covers every `EventType` | (same file) | P0 |
| 11 | Confidence weighted score + run DTO validation (`question` min length, threshold bounds) | `backend/tests/test_domain_models.py` | P0 |

### Phase 4 — Verification (Step 12)

| Step | Task | Priority |
|------|------|----------|
| 12 | `ruff check backend && pyright backend/app/domain && pytest backend/tests -q` all green | P0 |

---

## 4. File Inventory

```
backend/
  app/
    domain/
      __init__.py          # NEW — package re-exports
      enums.py             # NEW
      events.py            # NEW
      run.py               # NEW
      confidence.py        # NEW
  tests/
    test_domain_enums.py   # NEW
    test_domain_events.py  # NEW
    test_domain_models.py  # NEW
scripts/
  export_types.py          # MODIFY — replace placeholder
frontend/
  src/
    types/
      events.ts            # OVERWRITE — auto-generated
```

---

## 5. Technical Decisions

| Decision | Rationale | Source |
|----------|-----------|--------|
| `domain/` (not `models/`) for Pydantic | `models/` is reserved for SQLAlchemy ORM (BRD-01). Keeping them separate prevents conflating row state with event payloads. | BRD-02 §4.1 |
| `BaseEvent` carries optional `id`, `run_id`, `step_index`, `parent_event_id`, `created_at` | Same instance can be used both pre-persist (FSM-emitted) and post-persist (DB-hydrated) | BRD-02 §4.3 |
| `model_config = ConfigDict(extra="allow")` on every event + nested model | Schema evolution rule (architecture §5) | RF-03 |
| `Annotated[Union[...], Field(discriminator="type")]` exposed as `Event` | Single entry point for parsing `events.payload` JSONB | BRD-02 §4.3 |
| `EVENT_TYPE_MAP` and `FORKABLE_EVENTS` exported from both `events.py` and `domain/__init__.py` | FSM (BRD-07) and Fork endpoint (BRD-15) consume them directly | BRD-02 §4.3 |
| `StructuralConfidence.score` is a `@property`, not a stored field | Weights live in code, never in the event payload — single source of truth for the formula | RF-12 / BRD-08 |
| Type exporter writes file (not stdout) and includes ISO-timestamped DO-NOT-EDIT header | Avoids shell-redirection mistakes on Windows; CI can diff against committed file | BRD-02 §4.6 (tightened) |
| Generated `events.ts` is committed | Frontend doesn't require Python at build time; ESLint can ignore the file | Tech stack |
| No runtime DB needed for any test in this BRD | Pure Pydantic / pure Python — keeps CI fast (per L-003) | BRD-02 §7 |

---

## 6. Acceptance-Criteria → Test Mapping

| AC | Verified by |
|----|-------------|
| AC-01 Serialization | `test_domain_events.py::test_stopped_event_serializes_all_fields` |
| AC-02 Discriminated union | `test_domain_events.py::test_type_adapter_parses_each_event_type` (parametrized over all 19) |
| AC-03 Schema evolution | `test_domain_events.py::test_extra_fields_preserved_in_model_extra` |
| AC-04 Type export | `test_domain_events.py::test_event_type_enum_has_19_values` + manual run of `export_types.py` producing a non-empty `events.ts` |
| AC-05 Forkable set | `test_domain_events.py::test_forkable_events_exact_membership` |

---

## 7. Verification Criteria

### Static
- [ ] `ruff check backend` clean (incl. new `app/domain/` and new tests)
- [ ] `pyright backend/app/domain` strict-clean
- [ ] `scripts/export_types.py` runs without errors and writes a non-empty `frontend/src/types/events.ts`

### Tests
- [ ] `pytest backend/tests -q` green
- [ ] All 5 ACs covered by at least one named test
- [ ] Every `EventType` value has a corresponding event class in `EVENT_TYPE_MAP`

### Documentation
- [ ] No deviation from BRD-02 §4 code blocks except those listed in §5 above
- [ ] `knowledge-base-index.md` updated: Event Models row flipped from `⏳ BRD-02` to `✅ BRD-02` and path corrected to `backend/app/domain/events.py`

---

## 8. Risks & Mitigations (this iteration)

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Enum value drift vs. BRD-01 migration | Low | Step 8 cross-check test asserts exact string values |
| Forgetting to add a new event to `EVENT_TYPE_MAP` or `Event` union | Medium | Coverage test iterates `EventType` and asserts both maps |
| `export_types.py` failing on Windows newlines | Low | Write with `encoding="utf-8"` and explicit `\n` |
| Generated `events.ts` causing TS strict errors | Medium | Only emit string-literal type aliases for enums + a `const`-asserted schema; no `any` |

---

## 9. Effort & Sequencing

Total estimated effort: ~2 hours coding + ~1 hour tests + ~30 min export script. No DB, no network, no LLM calls. Single Coder pass should be enough to reach review.
