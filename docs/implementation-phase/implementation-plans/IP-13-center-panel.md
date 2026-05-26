# IP-13: Center Panel — Implementation Plan

**Source BRD:** [BRD-13-center-panel.md](../brds/BRD-13-center-panel.md)
**Status:** In progress
**Date:** 2026-05-26
**Author:** Orchestrator

---

## 1. Scope & Deviations from BRD-13

BRD-13 was written against an ideal backend (SSE events, dedicated `AnswerDrafted`/`ConfidenceCalculated` events). The actual backend (BRD-03 + BRD-04) exposes only `GET /api/runs/{id}` (snake_case `RunResponse`) plus `POST /{id}/cancel` and `POST /{id}/fork`; `GET /{id}/events` returns **501** (deferred to BRD-10). The V1 event schema (`backend/app/domain/events.py`) has no `AnswerDrafted` event — terminal data lives inside `StoppedEvent` (`answer_prose`, `answer_sections`, `citations`, `honest_explanation`), and there is no list-events endpoint.

This plan adapts to that reality while preserving every BRD-13 acceptance criterion that is achievable in V1.

| BRD-13 assumption | Actual backend | Decision |
|---|---|---|
| `useRun` streams events via `useRunStream` | No SSE endpoint, no `useRunStream` hook | `useRun` only wraps `GET /api/runs/{id}` + cancel/fork mutations. SSE/event integration deferred to BRD-10 wiring. |
| Camel-case `RunResponse { question, outputFormat, threshold, status }` | Snake-case `{ question, output_format, confidence_threshold, started_at, stopped_at, stop_reason }`; no `status` field | Add typed DTO in `lib/api.ts`. Derive `status` client-side: `stop_reason == null && stopped_at == null → "running"`, else `"stopped"`. Read `output_format` / `confidence_threshold` directly. |
| Live answer streaming (`AnswerDrafted`) | No such event; answer lives in `StoppedEvent` once terminal, no events GET endpoint | `AnswerDisplay` defers to BRD-10 (when events GET / SSE lands). V1 renders only the question + status + stop reason card. |
| `ConfidenceCalculated` event | Schema has `JudgeRuledEvent` (`final_confidence`, `judge_confidence`, `structural_confidence`, `passed`) + `ConfidenceMismatchEvent`; no GET endpoint to fetch them | `ConfidenceCard` deferred (BRD-10). Out of scope here. |
| Organism `CenterPanel` owns data via `useRun` | ESLint `import/no-restricted-paths` forbids organisms from importing `useRun*` | Same pattern as IP-12: organism `CenterPanelView` is **presentational**. Data hook lives in a page-level container (`pages/CenterPanelContainer.tsx`) that renders inside the existing geometry `templates/CenterPanel`. |
| Organism named `CenterPanel.tsx` | A geometry `templates/CenterPanel.tsx` already exists (BRD-11) | Name organism `CenterPanelView.tsx` to avoid collision; export via `organisms/index.ts`. |
| `forkableEvents` filter + dropdown inside `ActionBar` | No event list available, fork UX belongs to BRD-15 (Trace Panel) | `ActionBar` ships **cancel-only** in V1. Fork button is rendered but disabled with a "Select a step from the trace" tooltip; full picker is BRD-15. |

UI-prototype state coverage in V1:

| State | Covered | How |
|---|---|---|
| C1 initial loading | ✅ | Spinner while `useRun` is pending |
| C2 question displayed | ✅ | `QuestionDisplay` |
| C3 researching | ✅ (lightweight) | Animated "Researching…" banner when `status === "running"` |
| C4 evidence gathering | ❌ | Deferred (needs events; BRD-10/BRD-14/BRD-15) |
| C5 judging | ❌ | Deferred (needs events) |
| C6 answer streaming | ❌ | Deferred (BRD-10) |
| C7 completed confirmed | ✅ (partial) | `StopReasonCard` variant=success |
| C8 honest stop | ✅ | `StopReasonCard` variants for `honest_*` and `stopped_by_budget` |
| C9 error state | ✅ | `StopReasonCard` variant=error (when `stop_reason === "errored"`) + load-error fallback |
| C10 cancelled | ✅ | `StopReasonCard` variant=info for `user_cancelled` |
| C11 fork point selection | ❌ | Deferred to BRD-15 |
| C12 low confidence | ❌ | Deferred (needs events) |
| C13 mismatch alert | ❌ | Deferred (needs events) |

## 2. Task Breakdown

| # | Task | File(s) | Notes |
|---|---|---|---|
| 1 | API DTO + wrapper | `frontend/src/lib/api.ts` | Add `RunDto` (snake_case shape from `RunResponse`), `getRun(id)`, `cancelRun(id)`, `forkRun(id, eventId)`. Auth headers via existing `auth.ts` helper. |
| 2 | Types | `frontend/src/types/run.ts` | `Run` (camelCase mapped view), `RunStatus = "running" \| "stopped"`, `mapRun(dto)` adapter. |
| 3 | Data hook | `frontend/src/hooks/useRun.ts` | `useQuery(["run", runId], getRun)` + `useMutation` cancel/fork. Returns `{ run, status, isLoading, isError, error, cancel, isCancelling, fork, isForking }`. No SSE in V1. |
| 4 | QuestionDisplay organism | `frontend/src/components/organisms/QuestionDisplay.tsx` | Pure presentational. Token classes (`var(--text-primary/secondary)`), not raw greys. |
| 5 | ResearchingBanner organism | `frontend/src/components/organisms/ResearchingBanner.tsx` | C3 indicator: `Spinner` + "Researching…" copy. Used while `status === "running"`. |
| 6 | StopReasonCard organism | `frontend/src/components/organisms/StopReasonCard.tsx` | Maps all 7 `StopReason` enum values → title/description/variant (microcopy from BRD §4.8). Honest stops show `honest_explanation` placeholder ("event detail available in BRD-10"). |
| 7 | ActionBar organism | `frontend/src/components/organisms/ActionBar.tsx` | Live dot when running, Cancel button (red, calls `onCancel`), Fork button disabled with tooltip in V1. |
| 8 | CenterPanelView organism | `frontend/src/components/organisms/CenterPanelView.tsx` | Composes Question + Researching/Stop + ActionBar. Accepts `run`, `status`, callbacks. No hook imports. |
| 9 | Container | `frontend/src/pages/CenterPanelContainer.tsx` | Reads `:runId` from router, calls `useRun`, renders `templates/CenterPanel` with `CenterPanelView` in body and `ActionBar` in header slot. Handles C1 loading + load error. |
| 10 | Wire RunPage | `frontend/src/pages/RunPage.tsx` | Replace placeholder body with `<CenterPanelContainer />`. |
| 11 | Organism barrel | `frontend/src/components/organisms/index.ts` | Export new organisms. |
| 12 | Tests | colocated `*.test.tsx` per component, `useRun.test.tsx`, container test with MSW | Vitest + RTL + jest-axe. MSW only where API is hit (`useRun`, container). ≥ 80% coverage per L-002. |

## 3. Acceptance Criteria Mapping

| AC | Coverage in V1 |
|---|---|
| AC-01 Question displays correctly (C2) | ✅ `QuestionDisplay` + tests |
| AC-02 Answer streams live (C6) | ❌ Deferred to BRD-10 — documented in §1. Plan note: when BRD-10 lands, `useRun` adds `useRunStream` and `CenterPanelView` mounts `AnswerDisplay`. |
| AC-03 Cancel button stops research (RF-08) | ✅ `ActionBar` cancel → `useRun.cancel` → `POST /api/runs/{id}/cancel` → query invalidates → status flips to "stopped" |
| AC-04 Confidence formula min(S,J) (RF-12) | ❌ Deferred to BRD-10 — same reason as AC-02. |

The two deferred ACs are tracked in `decisions-history.md` (D-013) so the Reviewer scores against the plan, not the BRD ideal (per L-003).

## 4. Out of Scope (this BRD)

- Live event streaming (SSE) — BRD-10
- `AnswerDisplay`, markdown/citation rendering — BRD-10 + BRD-15
- `ConfidenceCard` and `ConfidenceMismatch` UI — BRD-10
- Fork point picker UI — BRD-15
- Trust flag banner / low confidence warning — BRD-10
- React-markdown / react-syntax-highlighter dependencies are **not** added in this BRD.

## 5. Tech Notes

- **Token policy:** organisms use `var(--*)` semantic tokens (BRD-11 §1) — no `bg-gray-50` hex/Tailwind greys for surfaces. Status colors via `var(--semantic-success/warning/error/info)`.
- **`exactOptionalPropertyTypes`:** any forwarded optional prop must be typed `T | undefined` (L-006).
- **Auth:** mutations require `X-Username` + `X-Token` headers (L-007); reuse `lib/auth.ts` helper. `GET /api/runs/{id}` is public.
- **TanStack Query keys:** `["run", runId]` (singular) — distinct from `["runs"]` used by `useRunHistory`. Cancel/fork invalidate `["run", runId]` and `["runs"]`.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Reviewer scores against BRD-13 ideal instead of plan | This document is explicit per L-003. Cite §1 / §3 in the review request. |
| `confidence_threshold` / `output_format` ever rename | Adapter `mapRun` is the single source of mapping; unit-test it. |
| Cancel race (user clicks while query still loading) | Button disabled until `run` resolved; `isCancelling` flag disables during request. |
