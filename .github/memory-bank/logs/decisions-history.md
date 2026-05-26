# Decisions History

> Chronological log of all decisions made during the Novum development.
> Each decision follows the decision record template.

**Last Updated:** 2026-05-26
**Total Decisions:** 15

---

## Recent Decisions

## D-015: BRD-13 Center Panel — V1 Scope Trimmed to Match Actual Backend

**Date:** 2026-05-26
**Agent:** Orchestrator (IP-13) + Coder + Reviewer
**Category:** Frontend / Scope Alignment
**Status:** Implemented (CR-13-001: 9.6/10 — Approved)

### Context
BRD-13 was authored against an ideal backend (SSE event stream, dedicated `AnswerDrafted` / `ConfidenceCalculated` events, camelCase `RunResponse` with a `status` field). The real V1 backend (BRD-03 + BRD-04) only exposes `GET /api/runs/{id}` (snake_case), `POST /{id}/cancel`, `POST /{id}/fork`; `GET /{id}/events` returns 501 and the schema has no `AnswerDrafted` event — terminal answer lives inside `StoppedEvent`.

### Decisions
1. Ship V1 covering ACs achievable today (AC-01, AC-03); defer AC-02 (live answer streaming) and AC-04 (confidence formula UI) to BRD-10. Per L-003, IP-13 is the binding contract for review.
2. Derive `status` client-side: `stop_reason == null && stopped_at == null → "running"`, else `"stopped"`. No backend `status` field needed.
3. Name the organism `CenterPanelView` to avoid collision with existing `templates/CenterPanel` geometry (BRD-11).
4. Keep `useRun` data hook in `pages/CenterPanelContainer.tsx`; organisms stay pure presentational per atomic-design ESLint policy (`import/no-restricted-paths`).
5. Ship `ActionBar` cancel-only; Fork button rendered disabled with tooltip until BRD-15.
6. `mapRun` adapter in `frontend/src/types/run.ts` is the single source of FE↔BE shape mapping (`confidence_threshold`, `output_format` rename touches only this file).
7. UI-prototype states C4/C5/C6/C11/C12/C13 deferred (need events stream).

### Consequences
- AC-02 + AC-04 re-open as part of BRD-10 (SSE Streaming & Resume).
- 40 new frontend tests (8 files) across organisms, hook, container, types; 219/219 total tests pass.
- Non-blocking follow-ups captured by Reviewer (fold into BRD-10):
  1. `ResearchingBanner` announces "Researching…" twice (Spinner `aria-label` + visible span inside `role=status`).
  2. `ActionBar` Fork button forwards `onClick` / `loading` while permanently `disabled` — dead props until BRD-15.
  3. `@vitest/coverage-v8` not installed → numeric coverage not enforced (qualitative ≥ 80% met).

### Related
IP-13-center-panel.md, CR-13-001-center-panel.md, BRD-10, BRD-14, BRD-15, ui-prototype.md §3 (C1–C13), RF-02, RF-12.

---

## D-014: BRD-06 Source Plugins — Tavily + Wikipedia behind `Source` seam

**Date:** 2026-05-26
**Agent:** Orchestrator (IP-06) + Coder + Reviewer
**Category:** Backend / Plugin Seams
**Status:** Implemented (CR-06-001: 9.4/10 — Approved)

### Context
First of the three V1 plugin seams (architecture rule #1). Two concrete sources required by `ai-services.md` §2/§3: Tavily (web, advanced depth) and Wikipedia (heterogeneous corpus per RF-04). Sources must be addressable by `SourceType` enum (already in `domain/enums.py`) and must not leak into the FSM/storage/LLM layers (rule #2).

### Decisions
1. **`Source` is a `runtime_checkable` `Protocol`** in `backend/app/seams/source.py` with `source_type`, `name`, `async search(...)`, `async health_check()`. Implementations are duck-typed; `BaseSource` is a mixin offering truncation only — not an ABC.
2. **`SourceResult` is a Pydantic-v2 model** (not a dataclass) — keeps the doors open for JSON-serialized evidence payloads in BRD-07/08.
3. **`SourceError` carries `source_type` + cause chaining** (`raise SourceError(...) from exc`). Non-`SourceError` exceptions are wrapped; existing `SourceError`s are propagated unchanged (no double-wrapping).
4. **Wikipedia sync client is wrapped with `anyio.to_thread.run_sync`** — the only way to keep the seam async-first without forking the lib.
5. **`SourceRegistry` is a module-level singleton** built lazily on first import; Tavily is registered only when `settings.tavily_api_key` is set (graceful degradation in dev/test). Per-test instances created via `SourceRegistry()` for isolation.
6. **No `tenacity` retries at the seam.** Tavily's client has its own retry; Wikipedia is best-effort. Retries (if needed) belong to the FSM's source-cascade logic in BRD-07.
7. **Not wired to FSM/events yet.** No `EvidenceAdded`/`SourceFailed` emission here — that is BRD-07's job.

### Consequences
- Architecture rule #1 satisfied; rule #2 preserved (no imports from `app/llm/` or `app/services/`).
- 45 unit tests cover protocol structural checks, truncation, registry isolation, conditional registration, error-wrapping symmetry, and thread-offload.
- The FSM in BRD-07 can depend on `get_source(SourceType)` without further refactoring.

### Related
IP-06-source-plugins.md, BRD-06, CR-06-001-source-plugins.md, ai-services.md §2/§3, architecture.md rule #1.

---

## D-013: Auth Wiring Closed via IP-11 iter 2 (No New BRD)

**Date:** 2026-05-26
**Status:** Accepted
**Context:** IP-04 iter 1 shipped `UsernameModal` + `userStore` but explicitly deferred mounting them. IP-11 iter 1 shipped the layout shell but explicitly deferred the modal/`useUser` wiring. Net effect on deployed app: no login path exists in the UI.
**Decision:** Close the auth wiring gap via an iteration 2 of IP-11 rather than authoring a new BRD. Shell ownership (TopBar, global overlays, boot wiring) belongs to BRD-11; the wiring is purely UI plumbing — no new requirements.
**Rationale:** The gap is the seam between BRD-04 §4.9 ("ready to be mounted later") and IP-11 iter 1 §3. A new BRD would duplicate existing requirements. Iter 2 plan covers `<AppBoot>` initialize, global `UsernameModalContainer`, unified TopBar with `IdentitySlot`, token-only modal re-skin, and logout/re-open flow.
**Consequences:** IP-11 iter 2 is the binding plan; `userStore.ts` stays untouched; modal styling moves from hardcoded Tailwind colors to design tokens (adds `--overlay-scrim` to `:root`).
**Related:** IP-11-frontend-layout-iter2.md, BRD-11, BRD-04 §4.8/§4.9, ui-prototype.md §1.3 / §2 / §3.2

---

## D-012: BRD-05 LLM Client — Roles/Models Realigned to ai-services.md

**Date:** 2026-05-26
**Agent:** Orchestrator (IP-05) + Coder + Reviewer
**Category:** Backend / LLM Integration
**Status:** Implemented

### Context
BRD-05 §4 specified four LLM roles (researcher, judge, planner, critic) on OpenAI models (`gpt-4o`, `o1-mini`, `gpt-4o-mini`) hitting `models.inference.ai.azure.com`, with a `call(role, user_message, response_model, context)` signature. `docs/technical-phase/ai-services.md` §1 (binding per copilot-instructions §1) specifies four different roles (classifier, planner, synthesizer, judge) on `meta/Llama-4-Scout-17B-16E-Instruct`, `deepseek/DeepSeek-V3-0324`, `openai/gpt-5`, `deepseek/DeepSeek-V3-0324` hitting `models.github.ai/inference`, with signature `call(role, messages, response_model)`.

### Decisions
1. **ai-services.md wins.** IP-05 follows it verbatim for roles, model IDs, `api_base`, and the `call` signature. BRD-05 §4 is treated as a structural reference (file layout, retry, instructor wrapping, AC shape) and should be amended in a follow-up doc PR.
2. **No CRITIC role in V1.** Plan-criticism becomes the planner's own self-correction loop (BRD-07 / RF-14, max 2 attempts). Dropped `CRITIC` from the enum, prompts, models, and config.
3. **Cross-family judge (RF-15) enforced by a test.** `test_judge_is_cross_family_vs_synthesizer` asserts judge provider prefix (`deepseek/`) ≠ synthesizer's (`openai/`).
4. **`count_tokens` is sync `def`.** BRD-05 wrote `async def`; tiktoken is sync CPU-bound — promoting it to sync prevents accidental event-loop blocking semantics.
5. **`before_sleep_log(logger, logging.WARNING)`** uses the stdlib logging int, not the string `"warning"` (BRD-05 typo).
6. **`models.inference.ai.azure.com` is wrong;** use `https://models.github.ai/inference`.
7. **Dropped response models for unused roles in this BRD:** `EvidenceAnalysis`, `SearchQueryOutput`, `AnswerDraft`, `CritiqueOutput`. They belong to BRD-06 / BRD-07.
8. **Test isolation via `AsyncMock`** on `app.llm.client.client.chat.completions.create`; no real network, no `pytest-httpx` for this BRD.
9. **Boundary `Any`.** `instructor.from_litellm(litellm.acompletion)` is typed `Any` with a localized `# pyright: ignore`; strict typing is re-established at `LLMClient.call` via `TypeVar("T", bound=BaseModel)`. Minimum-Any posture compatible with pyright strict.

### References
- Plan: `docs/implementation-phase/implementation-plans/IP-05-llm-client.md`
- BRD: `docs/implementation-phase/brds/BRD-05-llm-client.md`
- Binding tech doc: `docs/technical-phase/ai-services.md` §1
- Review: `docs/implementation-phase/reviews/CR-05-001-llm-client.md` (9.5/10, Approved)

### Results
- 169/169 backend tests pass (23 new LLM tests).
- `ruff check` clean, `pyright --strict` clean on all changed files.
- 6 of 7 ACs covered (AC-02 critic correctly deferred to BRD-07).
- 3 Minors (RF-15 inline comment near JUDGE config, api_base/api_key wiring test, a `cast` survival comment) deferred as non-blocking polish.

---

## D-011: BRD-12 History Panel — Presentational Organism + Page-Owned Hook

**Date:** 2026-05-26
**Context:** BRD-12 example code put `useRunHistory` inside an organism `HistoryPanel`. The repo's ESLint `import/no-restricted-paths` rule forbids any component below `pages/` from importing `useRun*`. The backend (BRD-03) also exposes only `GET /api/runs?limit&offset` returning `RunListItem`, with no filters/search/cursor/DELETE.

**Decision:**
- `HistoryList`, `RunRow`, `HistoryFilters` are presentational organisms (no data fetching).
- `useRunHistory` (TanStack `useInfiniteQuery` over offset pagination) lives in `frontend/src/hooks/` but is only imported by `pages/HistoryPanelContainer.tsx`.
- `HistoryPanelContainer` (page-level) reuses the existing `templates/HistoryPanel` geometry shell (BRD-11) via its `header` / `body` slots.
- Filtering by status / stop reason / search runs client-side over the loaded pages.
- DELETE, confidence bar, fork badge: out of scope (BRD-12 §10 + missing backend support).

**Status derivation:** `stop_reason == null` → `running`; `judge_confirmed` → `completed`; else → `stopped`.

**Outcome:** 35 new tests (148 total, all green), typecheck clean, lint clean for new files, AC-01..AC-04 covered. See [CR-12-001](../../../docs/implementation-phase/reviews/CR-12-001-history-panel.md) and [IP-12](../../../docs/implementation-phase/implementation-plans/IP-12-history-panel.md).

---

## D-010: BRD-04 User Identity — Lightweight Auth Implemented

**Date:** 2026-05-26
**Agent:** Coder (BRD-04)
**Category:** Backend + Frontend / Auth
**Status:** Implemented

### Context
BRD-04 / IP-04 ships RF-05 lightweight identity: username + random 64-hex token, hashed SHA-256. Upgrades the placeholder `get_current_username` to require both `X-Username` and `X-Token`, and adds `/api/auth/{register,verify}` + `/api/auth/users/{username}`. Frontend adds `lib/auth.ts`, `userStore`, and `UsernameModal` organism.

### Decisions
1. **Existing `User` ORM model reused as-is** (BRD-02). No re-declaration.
2. **`get_current_username` extended in-place** in `app/dependencies.py`; single source of truth. Symmetric 401 messages — same error for unknown user and wrong token.
3. **`POST /api/auth/verify` never raises 401** — returns `{valid: false}` on any failure so it cannot be used as a guard (only `get_current_username` short-circuits requests).
4. **Username normalization (`strip().lower()`) centralized in `AuthService.register`**, not in the route.
5. **`InvalidTokenError` raised for both "unknown user" and "wrong token"** so timing and message symmetry are preserved.
6. **`seeded_user` fixture upgraded to register via `AuthService`** (real `token_hash`), and a new `auth_headers` fixture exposes the matching `X-Username` + `X-Token` pair. All BRD-03 route tests updated to send both headers.
7. **Frontend tests use `vi.spyOn(globalThis, "fetch")`** (no MSW yet, per IP-04 §5.8).
8. **Network errors in `userStore.initialize` keep the stored identity** (offline support) — explicit test added.

### References
- Plan: `docs/implementation-phase/implementation-plans/IP-04-user-identity.md`
- BRD: `docs/implementation-phase/brds/BRD-04-user-identity.md`

### Results
- 146/146 backend tests pass (12 new auth tests + 13 token tests + 7 dependency tests).
- 113/113 frontend tests pass (10 new `auth.ts` tests + 8 `userStore` tests).
- `ruff` clean, `pyright` clean, `tsc` clean on changed files.

---

## D-009: BRD-11 Reviewer Follow-ups — Tokens Declared + Canonical Microcopy

**Date:** 2026-05-26
**Agent:** Coder (BRD-11 follow-up)
**Category:** Frontend / Tokens & Microcopy
**Status:** Implemented

### Context
The Reviewer (REV-11, 9.2/10) flagged two non-blocking gaps before BRD-12:
1. CSS custom properties referenced everywhere (`--bg-primary`, `--accent`, `--semantic-*`, `--glass-*`, `--text-*`, `--radius-*`) were never declared in `frontend/src/index.css` — runtime visual breakage not caught by JSDOM.
2. `StatusBadge` labels diverged from the canonical microcopy in `ui-prototype.md` §7.4.

### Decisions
1. **Declared all Novum design tokens** from `ui-prototype.md` §1.3 in `frontend/src/index.css` under `:root`. The existing shadcn HSL token block is kept for `components.json` compatibility, with its conflicting `--accent` redeclaration removed so the Novum `#007AFF` is canonical.
2. **`body` styled with `var(--bg-primary)` + `var(--text-primary)`** so the dark theme is the default render.
3. **`StatusBadge` labels aligned with §7.4 canonical strings:** `judge_confirmed` → "Judge confirmed"; `honest_*` → "Honest stop — <variant>"; `stopped_by_budget` → "Stopped on budget"; `user_cancelled` → "Cancelled"; `errored` → "Errored". Running label updated to **"Researching…"** per §7.5.
4. **`StatusBadge` accepts an optional `errorReason` prop** that produces "Errored — <reason>" only when `stopReason === "errored"`; otherwise it is ignored.
5. **Test suite updated** (`StatusBadge.test.tsx`): canonical labels asserted + 2 new cases for `errorReason` behavior. 95/95 tests pass, `tsc` clean.

### References
- Tokens: `docs/understanding-phase/ui-prototype.md` §1.3
- Microcopy: `docs/understanding-phase/ui-prototype.md` §7.4 / §7.5
- Review that triggered this: `docs/implementation-phase/reviews/REV-11-frontend-layout.md`

---

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
