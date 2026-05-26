# Decisions History

> Chronological log of all decisions made during the Novum development.
> Each decision follows the decision record template.

**Last Updated:** 2026-05-26
**Total Decisions:** 8

---

## Recent Decisions

## D-008: BRD-11 Frontend Layout — IP Reconciliations Honored

**Date:** 2026-05-26
**Agent:** Orchestrator (planning) / Coder (implementation) / Reviewer (9.2/10 — APPROVED)
**Category:** Frontend / Implementation
**Status:** Implemented

### Context
BRD-11 and `ui-prototype.md` disagreed on routes, page folder, template names, panel widths, and theme. IP-11 §2 reconciled all of them in favor of `ui-prototype.md` (binding per `copilot-instructions.md` §2).

### Decisions
1. **Routes & pages folder kept as-is** — `/runs/:runId` + `/diff/:runA/:runB` in existing `router.tsx`; `src/pages/` (not `src/components/pages/`).
2. **3 panel templates over single `MainLayout`** — `AppShell` orchestrates breakpoints and drawers; `HistoryPanel` / `CenterPanel` / `TracePanel` are geometry-only with header/body/(footer|outcomeBar) slots.
3. **Widths from `ui-prototype.md` §2** — `w-[260px]` left, `w-[360px]` right desktop, `w-[320px]` right on tablet.
4. **Dark theme via CSS custom properties only** — no hardcoded hex anywhere; `var(--bg-primary)`, `var(--accent)`, `var(--semantic-*)`, `var(--glass-*)`, `var(--text-*)`.
5. **Responsive policy:** desktop shows all 3 panels; tablet collapses left to drawer (right stays at 320 px); mobile shows only center with both panels as overlay drawers. Drawer state lives in `useSelectionStore`.
6. **`StopReason` imported from generated `@/types/events`** — never hand-edited (RF type-contract rule).
7. **Test suite uses `forceBreakpoint` prop on `AppShell`** for deterministic breakpoint testing instead of mocking `matchMedia` per case.

### Reviewer Follow-ups (non-blocking, before BRD-12)
- Declare the CSS custom properties referenced everywhere in `frontend/src/index.css` (gap in IP-11 §5.2 file list).
- Align `StatusBadge` labels with `ui-prototype.md` §7.4 canonical microcopy.

### References
- Plan: `docs/implementation-phase/implementation-plans/IP-11-frontend-layout.md`
- Review: `docs/implementation-phase/reviews/REV-11-frontend-layout.md`
- UT doc: `docs/implementation-phase/unit-tests/UT-11-frontend-layout.md`

---

## D-007: BRD-03 FastAPI Core — Tightenings Applied

**Date:** 2026-05-26
**Agent:** Orchestrator (planning) / Coder (implementation) / Reviewer (9.55/10 — APPROVED)
**Category:** Backend API / Implementation
**Status:** Implemented

### Context
BRD-03 §4 contained copy-paste-ready code blocks. IP-03 §5 documented three deliberate tightenings before delegating to the Coder.

### Decisions
1. **`datetime.now(UTC)` over `datetime.utcnow()`** — Python 3.12 deprecated `utcnow()`; DB column is `TIMESTAMPTZ` so a tz-aware UTC value is correct.
2. **`Last-Event-ID` via `Header(alias="Last-Event-ID", convert_underscores=False)`** — the SSE spec sends it as a header on reconnect, not a query parameter. BRD-03 typo corrected pre-emptively to avoid rework in BRD-10.
3. **Single canonical `get_db`** lives in `app/dependencies.py`; `app/database.py` retains only `engine` and `async_session_maker` plus a contract comment. Avoids drift between the two definitions originally present in BRD-01/BRD-03.
4. **`/api/runs/{id}/events` returns explicit `HTTPException(501)`** instead of `raise NotImplementedError` (which would surface as 500). BRD-10 will replace it with the real SSE stream.
5. **Tests use SQLite (`aiosqlite` + `StaticPool`) with a `compiles`-hook fallback** for PG-specific types (`JSONB`/`UUID`/`ENUM`) → keeps the test suite DB-free per L-004 without modifying production ORM types.
6. **`GET /api/runs/{id}` intentionally unauthenticated** per RF-05 (runs are public-by-URL); locked by a named test so reviewers don't mistake it for a bug.

### Outcome
- 108/108 tests green; pyright strict clean; ruff clean.
- All 5 ACs (AC-01 create, AC-02 list, AC-03 fork, AC-04 cancel, AC-05 resume) have named tests.
- Review score: **9.55 / 10 — APPROVED**. Five Minor items deferred to BRD-04 / BRD-07 / BRD-15 (cross-user authz, single-writer lock on `append_event`, fork-event-belongs-to-run invariant).

### Files
- New: `app/dependencies.py`, `app/exceptions.py`, `app/routes/{__init__,health,runs,events}.py`, `app/services/{run_service,event_service}.py`
- Modified: `app/main.py`, `app/database.py`, `app/config.py`, `app/services/__init__.py`, `app/routes/__init__.py`, `pyproject.toml`, `tests/conftest.py`
- Tests: `tests/test_run_service.py`, `tests/test_event_service.py`, `tests/test_routes_runs.py`

---

## D-006: Reaffirm Mandatory Unit Tests (Backend + Frontend)

**Date:** 2026-05-26
**Agent:** Orchestrator
**Category:** Process & Workflow
**Status:** Active rule

### Context
User explicitly reaffirmed: *"siempre se deben hacer las unit tests, mandatorio, tanto en frontend como backend"*. Rule already existed as **L-002** in `lessons-learned.md` and as workflow step **F3.S3**, but was being tracked only in user-scoped memory instead of the project memory bank — violating the Memory Protocol (copilot-instructions.md §7.4).

### Decision
Unit tests are a **non-negotiable gate** for every BRD / User Story, in both stacks:
- **Backend:** `pytest` (+ `pytest-asyncio`, `pytest-httpx`, `pytest-postgresql` when DB is touched). Tests live under `backend/tests/`, mirroring module structure.
- **Frontend:** `Vitest` + Testing Library + `jest-axe` (a11y) + MSW (network mocks). Tests co-located with components (`*.test.ts(x)`).
- **Coverage gate:** ≥ 80% (per copilot-instructions.md §7.7).
- No implementation may advance to F4 (REVIEW) without F3.S3 executed and tests green.

### Enforcement
- Orchestrator MUST verify F3.S3 artifacts before delegating to Reviewer.
- Reviewer MUST score down (Blocker) any submission lacking tests for new/changed logic.
- See **L-002** for the originating incident and prevention checklist.

---

## D-005: BRD-02 Domain Models — Review Approved (Orchestrator)

**Date:** 2026-05-26
**Agent:** Orchestrator
**Phase:** F5 (COMPLETE)

CR-02-001 scored 9.6/10 on iteration 1 — above the 9.0 quality gate, no Blockers or Majors. Implementation accepted. Knowledge-base index updated: BRD-02 marked Implemented, all 6 BRD-02 artifacts (`domain/enums.py`, `domain/events.py`, `domain/run.py`, `domain/confidence.py`, `scripts/export_types.py`, `frontend/src/types/events.ts`) flipped to ✅. IP-02 logged. CR-02-001 added to reviews table. Three Minors deferred (Event-union line wrapping, registry-sync comment, exporter integration test) — to be addressed opportunistically in a future BRD; not blocking BRD-03.

**Next:** BRD-03 (FastAPI Core & API Skeleton) is unblocked.

---

## D-004: BRD-02 Domain Models — Implementation Complete

**Date:** 2026-05-26
**Agent:** Coder
**Category:** Implementation
**Status:** Ready for Review

### Context
Implemented the Pydantic v2 domain layer per BRD-02 §4 and IP-02: enums, 19 event types as a discriminated union, run DTOs, confidence DTOs, and the Pydantic→TypeScript exporter that overwrites `frontend/src/types/events.ts`.

### Decision
Files created/modified verbatim from BRD-02 §4 except for the deviations listed below.

### Files Created
- `backend/app/domain/__init__.py` — public API re-exports
- `backend/app/domain/enums.py` — `StopReason` (7), `QuestionType` (5), `OutputFormat` (2), `EventType` (19), `EvidencePolarity`, `SourceType`
- `backend/app/domain/events.py` — `BaseEvent` + 19 events + nested DTOs + `Event` discriminated union + `EVENT_TYPE_MAP` + `FORKABLE_EVENTS`
- `backend/app/domain/run.py` — `RunCreate`, `RunResponse`, `RunListItem`, `RunForkRequest`
- `backend/app/domain/confidence.py` — `StructuralConfidence` (with weighted `score` property) + `ConfidenceResult`
- `backend/tests/test_domain_enums.py` — 11 tests; cross-checks values + counts against the BRD-01 migration
- `backend/tests/test_domain_events.py` — 26 tests; covers AC-01..AC-05 + `EVENT_TYPE_MAP` coverage
- `backend/tests/test_domain_models.py` — 14 tests; `RunCreate` validation, weighted formula, `ConfidenceResult` shape

### Files Modified
- `scripts/export_types.py` — replaced placeholder; writes `frontend/src/types/events.ts` with header + 6 enum unions + `EventSchema` JSON Schema (`as const`) + commented `Event` union listing
- `frontend/src/types/events.ts` — regenerated from Pydantic; TypeScript strict-clean (no `any`)

### Deviations from BRD-02
1. **Typing modernization (forced by ruff `UP` rules):** `Optional[X]` → `X | None`, `Union[A, B]` → `A | B`. Identical semantics; required to pass `ruff check`.
2. **`export_types.py` writes a file instead of printing to stdout** — as tightened by IP-02 §5. Avoids shell-redirection problems on Windows and lets CI diff the committed artifact.
3. **Generated `events.ts` emits enums + JSON Schema only**, not concrete Pydantic-derived TS interfaces. The `Event` union is included as a comment listing the 19 event class names. Keeps the file TS strict-clean; concrete interfaces are deferred (frontend can validate at runtime via `EventSchema`).
4. **Exporter also exports `EvidencePolarity` and `SourceType`** in addition to the four enums named in the BRD §4.6 example. They are part of the public domain API.

### Verification
- `ruff check app/domain tests/test_domain_*.py` → clean
- `python -m pyright app/domain` → 0 errors, 0 warnings (strict mode)
- `pytest tests/test_domain_enums.py tests/test_domain_events.py tests/test_domain_models.py -q` → **55 passed**
- `python scripts/export_types.py` → wrote `frontend/src/types/events.ts` (contains `EventType` union with 19 string literals)
- Full backend suite: `pytest -q -p no:postgresql` → **74 passed** (no regressions). The `-p no:postgresql` flag works around a pre-existing local environment issue: `psycopg` lacks a libpq wrapper in this venv (unrelated to this BRD).

### Acceptance Criteria Coverage
| AC | Test |
|----|------|
| AC-01 | `test_domain_events.py::test_stopped_event_serializes_all_fields` |
| AC-02 | `test_domain_events.py::test_type_adapter_parses_each_event_type` (parametrized over all 19) |
| AC-03 | `test_domain_events.py::test_extra_fields_preserved_in_model_extra` |
| AC-04 | `test_domain_events.py::test_event_type_enum_has_19_values` + generated `events.ts` contains the 19-value `EventType` union |
| AC-05 | `test_domain_events.py::test_forkable_events_exact_membership` |

### Consequences
- BRD-07 (FSM) can now consume `Event`, `EVENT_TYPE_MAP`, `FORKABLE_EVENTS`.
- BRD-15 (Fork/Resume) can rely on `FORKABLE_EVENTS` as the canonical set.
- Frontend can import `StopReason`, `QuestionType`, `EventType`, etc., directly from `src/types/events.ts`.

---

## D-003: BRD-01 Database Schema — Review APPROVED (9.0/10)

**Date:** 2026-05-26
**Agent:** Reviewer
**Category:** Review
**Status:** Approved

### Context
Iteration 1 review of BRD-01 (PostgreSQL schema + Alembic migration + ORM models). Coder declared 7 intentional deviations from BRD §4.4 code blocks (all typing/SQLAlchemy 2.0 idiomatic improvements). 16 unit tests passed in 0.15 s.

### Decision
APPROVED at exactly 9.0/10 weighted score. Zero Blockers, zero Majors. Two Minors filed for follow-up in BRD-02:
- Add a downgrade-ordering static test to close the AC-05 gap.
- Tighten `Mapped[str | None]` enum columns to `Literal[...]` or `Enum` when domain models land.

### Consequences
- Proceed to BRD-02 (Pydantic domain models & event types).
- The Coder's `text()` wrapping of every `server_default` and explicit `postgresql.UUID(as_uuid=True)` become the project standard.
- The `pgcrypto` extension creation (added by Coder, missing from BRD §4.3) is acknowledged as a substantive correctness fix.

### Artifacts Created
- Review report: [CR-01-001-database-schema.md](../../../docs/implementation-phase/reviews/CR-01-001-database-schema.md)

---

## D-002: BRD-00 Implementation — Project Setup

**Date:** 2026-05-26
**Agent:** Orchestrator
**Category:** Implementation
**Status:** Completed

### Context
First implementation in the Novum project. Needed to establish the complete folder structure and tooling configuration for both backend (Python/FastAPI) and frontend (React/Vite).

### Decision
Implement BRD-00 as the foundation for all subsequent BRDs:
- Backend: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic
- Frontend: React 19 + Vite + Tailwind v4 (plugin, no config)
- Full atomic design structure for components

### Consequences
- All subsequent BRDs can build on this foundation
- Tailwind v4 uses `@import "tailwindcss"` (not v3 directives)
- Path aliases configured via `vite-tsconfig-paths`
- Agent tooling updated to include full toolset for subagents

### Artifacts Created
- `backend/` complete structure (pyproject.toml, app/, alembic/, tests/)
- `frontend/` complete structure (package.json, src/, components/, lib/)
- `scripts/` (dev.ps1, export_types.py)
- Implementation plan: `docs/implementation-phase/implementation-plans/IP-00-project-setup.md`

---

## D-001: Spec-Driven Development with Comprehensive BRDs

**Date:** 2026-05-26
**Agent:** BSA
**Category:** Process
**Status:** Accepted

### Context
The project needed detailed specifications to enable AI-assisted implementation with GitHub Copilot. Traditional BRDs were too high-level and didn't include the technical details needed for copy-paste implementation.

### Decision
Create 19 comprehensive BRDs (BRD-00 to BRD-18) in strict implementation order with:
- Complete file structures with paths
- Copy-paste ready code blocks
- Alembic migrations
- Pydantic models
- React components
- Acceptance criteria in Gherkin format
- Implementation checklists

### Consequences
- Development will follow strict sequence
- Each BRD is self-contained for implementation
- Code can be directly copied from BRDs
- Reduces ambiguity and decision-making during coding

### Artifacts Created
- 19 BRDs in `docs/implementation-phase/brds/`
- Updated knowledge base index
- Enhanced BRD template in memory bank

---

## Decision Categories

### Architecture Decisions
_None yet._

### Technology Decisions
_None yet._

### Process Decisions
- D-001: Spec-Driven Development with Comprehensive BRDs

### Design Decisions
_None yet._

---

## Template

When adding a new decision, use this format:

```markdown
## D-{number}: {Title}

**Date:** {YYYY-MM-DD}
**Agent:** {agent name}
**Category:** Architecture | Technology | Process | Design
**Status:** Accepted

### Context
{Why was this decision needed?}

### Decision
{What was decided?}

### Rationale
{Why was this the best choice?}

### Consequences
- {Positive/negative consequence}

### References
- {Link to related document}

---
```

---

## How to Add Decisions

1. Increment the decision number (D-001, D-002, etc.)
2. Fill out the template completely
3. Update the "Total Decisions" count above
4. Add to the appropriate category section
5. Update the "Recent Decisions" section (keep last 5)
