# IP-12: History Panel — Implementation Plan

**Source BRD:** [BRD-12-history-panel.md](../brds/BRD-12-history-panel.md)
**Status:** In progress
**Date:** 2026-05-26
**Author:** Orchestrator

---

## 1. Scope & Deviations from BRD-12

The BRD example code assumed features the backend does not implement. The plan adjusts to actual backend (BRD-03) without losing the BRD's acceptance criteria.

| BRD assumption | Actual backend (BRD-03) | Decision |
|---|---|---|
| `GET /api/runs?status&stop_reason&search&cursor` | `GET /api/runs?limit&offset` returns `RunListItem[]` | Use offset pagination. Filter `status` / `stopReason` / `search` **client-side** over the loaded pages. |
| `DELETE /api/runs/{id}` exists | No DELETE endpoint | Omit delete from V1 scope (BRD §10 lists bulk delete as out-of-scope; single delete follows). |
| `RunSummary { confidence, eventCount, isForked, forkedFromId, completedAt }` | `RunListItem { id, question, started_at, stopped_at, stop_reason }` | `RunSummary` adapts to available fields only. Confidence / fork badge omitted until the backend exposes them. |
| Organism `HistoryPanel` owns data fetching via `useRunHistory` | ESLint `import/no-restricted-paths` forbids organisms from importing `useRun*` | Organism `HistoryList` is **presentational**. `HomePage` / `RunPage` own the hook and pass data down. |
| Organism `HistoryPanel` replaces the panel chrome | A geometry-only `templates/HistoryPanel` already exists (BRD-11) | Reuse the template (header / body / footer slots). Render `HistoryList` inside `body`. |

Status derivation (client):
- `stop_reason == null` → `"running"`
- `stop_reason == "judge_confirmed"` → `"completed"`
- otherwise → `"stopped"`

## 2. Task Breakdown

| # | Task | File(s) | Notes |
|---|---|---|---|
| 1 | Define types | `frontend/src/types/history.ts` | `RunSummary`, `RunStatus`, `HistoryFilterValues` |
| 2 | API wrapper | `frontend/src/lib/api.ts` | Add `listRuns({ limit, offset })` returning `RunListItem[]` |
| 3 | Data hook | `frontend/src/hooks/useRunHistory.ts` | `useInfiniteQuery` over limit/offset. Maps `RunListItem` → `RunSummary`. `hasMore` = `page.length === limit`. |
| 4 | RunRow organism | `frontend/src/components/organisms/RunRow.tsx` | L3 selected, L4 hover. Uses `StatusBadge`, `formatRelative`, `truncate`. |
| 5 | HistoryFilters organism | `frontend/src/components/organisms/HistoryFilters.tsx` | Search + status pills + clear. Exports `hasActiveFilters`. |
| 6 | HistoryList organism | `frontend/src/components/organisms/HistoryList.tsx` | Presentational. Renders L1/L2/L3/L5/L6/L7. Receives `runs`, `filters`, `selectedRunId`, callbacks, query state. |
| 7 | Page wiring | `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/RunPage.tsx` | Own `useRunHistory`, local `filters` state, navigation handlers. Render inside `templates/HistoryPanel` body slot. |
| 8 | Tests | colocated `*.test.tsx` | Vitest + RTL + jest-axe. MSW where API is touched (hook test). |

## 3. Acceptance Criteria Mapping

| AC | Covered by |
|---|---|
| AC-01 Empty (L1) | `HistoryList` empty-state branch + tests |
| AC-02 List (L2) | `HistoryList` + `RunRow` tests |
| AC-03 Selection (L3) | `RunRow` `isSelected` + page `onSelect` navigates to `/runs/:id` |
| AC-04 Infinite scroll | `HistoryList` "Load more" button + `useRunHistory` infinite query |

## 4. Out of Scope (this BRD)

- Bulk delete, export, sort options (BRD §10)
- Single-run delete (no backend endpoint)
- Server-side filtering / search
- Confidence bar inside row (no field in `RunListItem`)
- Fork badge (no field in `RunListItem`)

## 5. Risks

| Risk | Mitigation |
|---|---|
| Client-only filtering misses results not yet paged in | "Load more" still works; acceptable for V1 single-server low volume. |
| Mapping `judge_confirmed` to `completed` vs other stops | Encoded in one place (`mapRun`) with unit tests. |
