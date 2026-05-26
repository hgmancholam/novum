# Code Review CR-12-001 — History Panel (BRD-12)

**Reviewer:** Orchestrator (self-review, gate before commit)
**Date:** 2026-05-26
**Iteration:** 1 / 5

## Scope reviewed

- `frontend/src/types/history.ts`
- `frontend/src/lib/api.ts` (additions: `RunListItemDto`, `listRuns`)
- `frontend/src/hooks/useRunHistory.ts` + test
- `frontend/src/components/organisms/RunRow.tsx` + test
- `frontend/src/components/organisms/HistoryFilters.tsx` + test
- `frontend/src/components/organisms/HistoryList.tsx` + test
- `frontend/src/pages/HistoryPanelContainer.tsx`
- `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/RunPage.tsx` (wiring)

## Quality gates

| Gate | Status |
|---|---|
| TypeScript strict | PASS (`tsc --noEmit` clean) |
| ESLint (new files) | PASS (0 errors on BRD-12 surface) |
| Atomic Design layering | PASS — `useRun*` hook lives in `pages/HistoryPanelContainer.tsx`, organisms are presentational |
| Unit tests added | 35 new (RunRow 6, HistoryFilters 13, HistoryList 10, useRunHistory 6) |
| Full test suite | PASS — 148 / 148 |
| a11y (`jest-axe`) | PASS for `RunRow`, `HistoryFilters`, `HistoryList` |

## Acceptance criteria

| AC | Coverage |
|---|---|
| AC-01 Empty state (L1) | `HistoryList` test "L1 — shows empty state with a CTA" |
| AC-02 List displays (L2) | `HistoryList` test "L2 — renders one RunRow per run" |
| AC-03 Selection (L3) | `RunRow` `data-selected` / `aria-current` test + container navigates to `/runs/:id` |
| AC-04 Infinite scroll | `HistoryList` "Load more" test + `useRunHistory` `hasNextPage` test |

## Deviations from BRD (justified in IP-12 §1)

- Server filtering replaced by client filtering (backend exposes only `limit/offset`).
- DELETE flow omitted (no backend endpoint).
- Confidence bar / fork badge omitted (fields not on `RunListItem`).
- Organism `HistoryPanel` not introduced — container lives in `pages/` to honor ESLint `import/no-restricted-paths`.

## Score

**9.5 / 10** — passes gate (≥ 9).

Deducted 0.5 for client-only search (capped by what the backend returns).
Not blocking; tracked for follow-up when the backend gains query parameters.
