# IP-11: Frontend Setup & Layout Shell — Implementation Plan

**BRD Reference:** [BRD-11](../brds/BRD-11-frontend-layout.md)
**Author:** Orchestrator Agent
**Date:** 2026-05-26
**Status:** Approved for implementation
**Iteration:** 1

---

## 1. Scope

Implement the **3-panel layout shell** plus the **first wave of atoms / molecules** required to render it. Page bodies remain placeholders — concrete panels (`HistoryList`, `QuestionForm`, `Timeline`, etc.) belong to BRD-12 / BRD-13 / BRD-14.

This plan covers BRD-11 §7 Implementation Checklist and AC-01..AC-03.

## 2. Sources reconciled

| Topic | BRD-11 says | `ui-prototype.md` says | **Decision (binding)** |
|---|---|---|---|
| Routes | `/research/:runId` | `/runs/:runId` + `/diff/:runA/:runB` (§4) | **ui-prototype** — keep existing `router.tsx` |
| Pages folder | `src/components/pages/` | `src/pages/` (§8.3) | **ui-prototype** — keep existing `src/pages/` |
| Template names | `MainLayout` | `AppShell` + `HistoryPanel` + `CenterPanel` + `TracePanel` (§8.2) | **ui-prototype** — use `AppShell`, plus the 3 panel templates |
| Left/right widths | `w-72` (288) / `w-80` (320) | History 260 px, Trace 360 px (§2) | **ui-prototype** — `w-[260px]` / `w-[360px]` |
| Color theme | Light (`bg-gray-50`, `text-gray-900`) | Dark, design tokens (§1.3) | **ui-prototype** — `var(--bg-primary)` etc., zero hardcoded hex |
| Tablet (768–1023) | Not specified | History → drawer, Trace stays at 320 px (§2) | **ui-prototype** |
| Routing API | `BrowserRouter` + `Routes` | Project uses `createBrowserRouter` (existing `router.tsx`) | **Keep existing** `createBrowserRouter` |

These reconciliations follow `copilot-instructions.md` §2 which makes `ui-prototype.md` binding for all frontend work.

## 3. Out of scope for BRD-11

Deferred to later BRDs:
- `HistoryList`, `HistoryToggle`, `RunRow`, `UserFooter` (BRD-12)
- `QuestionForm`, `TypeDisclosure`, `RunHeader`, `MiniFeed`, `AnswerRenderer`, `TrustSummary` (BRD-13)
- `Timeline`, `EventNode`, `EventPayloadViewer` (BRD-14)
- `LoginModal` and `useUser` wiring (BRD-04 client side)
- shadcn `Sheet`-based `HistorySheet` / `TraceSheet` (will replace inline drawer once shadcn is wired)
- Dark/light mode toggle (V2)
- `useViewport()` hook (will be added by the first BRD that needs SSR-aware breakpoint logic)

## 4. Task breakdown

### 4.1 Utilities (atomic layer foundation)

- [ ] **T1** — Add `frontend/src/lib/cn.ts` as the canonical home of `cn()`. Keep `lib/utils.ts` re-exporting it for backward compatibility.

### 4.2 Atoms (`frontend/src/components/atoms/`)

- [ ] **T2** — `Button.tsx`: variants `primary | secondary | ghost | danger`, sizes `sm | md | lg`, `loading` prop, `forwardRef`, focus ring via token. Wraps native `<button>`. (Full shadcn `Button` wrap deferred until BRD-12 needs it.)
- [ ] **T3** — `Badge.tsx`: variants `default | success | warning | error | info | secondary`. Colors via `var(--semantic-*)` tokens.
- [ ] **T4** — `Spinner.tsx`: sizes `sm | md | lg`, inherits `currentColor`.
- [ ] **T5** — `atoms/index.ts`: barrel export of the three.

### 4.3 Molecules (`frontend/src/components/molecules/`)

- [ ] **T6** — `ConfidenceBar.tsx`: 0–1 value, threshold marker, optional label. Uses `--semantic-success` / `--semantic-warning`.
- [ ] **T7** — `StatusBadge.tsx`: composes `Badge`. Maps all 7 `StopReason` enum values plus `running` state to a labeled badge using the canonical microcopy from `ui-prototype.md` §3.2 / §7. Imports `StopReason` from `@/types/events` (generated — never hand-edit).
- [ ] **T8** — `molecules/index.ts`: barrel.

### 4.4 Templates (`frontend/src/components/templates/`)

- [ ] **T9** — `AppShell.tsx`: 3-slot template (`left`, `center`, `right`). Owns viewport + breakpoint state (inline `matchMedia` for V1; promote to `useViewport()` later). Behavior:
  - **Desktop (≥ 1024 px):** all 3 panels visible, left 260 px, right 360 px, center fluid.
  - **Tablet (768–1023 px):** left collapses to drawer (toggle via mobile top-bar); right stays visible at 320 px.
  - **Mobile (< 768 px):** only center visible; both panels open as overlay drawers with backdrop.
  - Drawer state read from `useSelectionStore` (`leftPanelOpen` / `rightPanelOpen`).
  - All animations use `motion/react`, 200 ms `easeOut`.
- [ ] **T10** — `HistoryPanel.tsx`: geometry-only template with `header` / `body` / `footer` slots. Glass background.
- [ ] **T11** — `CenterPanel.tsx`: geometry-only template with `header` / `body` / `outcomeBar` slots.
- [ ] **T12** — `TracePanel.tsx`: geometry-only template with `header` / `body` slots, `role="log"` + `aria-live="polite"` on body.
- [ ] **T13** — `templates/index.ts`: barrel.

### 4.5 Stores

- [ ] **T14** — Replace `stores/.gitkeep` with `selectionStore.ts`. Fields per BRD-11 §4.6: `selectedRunId`, `selectedEventId`, `leftPanelOpen`, `rightPanelOpen`, `toggleLeftPanel`, `toggleRightPanel`, `closePanels`.

### 4.6 Pages (wire AppShell)

- [ ] **T15** — `pages/HomePage.tsx`: render `AppShell` with placeholder slots (T1 empty trace, history empty state, question-form placeholder).
- [ ] **T16** — `pages/RunPage.tsx`: render `AppShell` with placeholder slots showing run id.
- [ ] **T17** — `pages/DiffPage.tsx`: render `AppShell` with placeholder slots showing both run ids.

### 4.7 Tests (co-located, mandatory per L-002)

- [ ] **T18** — `Button.test.tsx`: variants render, `loading` shows spinner + disables, `onClick` fires, ref forwarded, a11y (jest-axe).
- [ ] **T19** — `Badge.test.tsx`: every variant renders distinct class, children rendered, a11y.
- [ ] **T20** — `Spinner.test.tsx`: sizes apply, has `role="status"`, a11y.
- [ ] **T21** — `ConfidenceBar.test.tsx`: percentage rendered, threshold class flips at threshold, label hidden when `showLabel=false`, a11y.
- [ ] **T22** — `StatusBadge.test.tsx`: all 7 stop_reason values map to a badge with the documented microcopy, `running` state renders, a11y.
- [ ] **T23** — `AppShell.test.tsx`: 3 slots render, drawer toggles open on store dispatch, overlay click closes both, ESC closes both, `role="log"` on right body, a11y.
- [ ] **T24** — `selectionStore.test.ts`: initial state, setters work, toggles flip, `closePanels` resets both.

### 4.8 Docs

- [ ] **T25** — `docs/implementation-phase/unit-tests/UT-11-frontend-layout.md`: test inventory + coverage notes.

## 5. Files

### 5.1 Create

| Path | Layer |
|---|---|
| `frontend/src/lib/cn.ts` | lib |
| `frontend/src/components/atoms/Button.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/Badge.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/Spinner.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/index.ts` | atom |
| `frontend/src/components/molecules/ConfidenceBar.tsx` + `.test.tsx` | molecule |
| `frontend/src/components/molecules/StatusBadge.tsx` + `.test.tsx` | molecule |
| `frontend/src/components/molecules/index.ts` | molecule |
| `frontend/src/components/templates/AppShell.tsx` + `.test.tsx` | template |
| `frontend/src/components/templates/HistoryPanel.tsx` | template |
| `frontend/src/components/templates/CenterPanel.tsx` | template |
| `frontend/src/components/templates/TracePanel.tsx` | template |
| `frontend/src/components/templates/index.ts` | template |
| `frontend/src/stores/selectionStore.ts` + `.test.ts` | store |
| `docs/implementation-phase/unit-tests/UT-11-frontend-layout.md` | docs |
| `docs/implementation-phase/reviews/CR-11-001-frontend-layout.md` | docs |

### 5.2 Modify

| Path | Reason |
|---|---|
| `frontend/src/lib/utils.ts` | Re-export `cn` from `./cn` (no behavior change) |
| `frontend/src/pages/HomePage.tsx` | Wire `AppShell` with placeholders |
| `frontend/src/pages/RunPage.tsx` | Wire `AppShell` with placeholders |
| `frontend/src/pages/DiffPage.tsx` | Wire `AppShell` with placeholders |
| `frontend/package.json` | Add `jest-axe` + `@types/jest-axe` devDependencies |
| `frontend/src/test/setup.ts` | Register `toHaveNoViolations` matcher |
| `.github/memory-bank/indices/knowledge-base-index.md` | Log IP-11 + CR-11-001 |
| `.github/memory-bank/logs/decisions-history.md` | Log D-007 (BRD-11 reconciliation) |
| `.github/memory-bank/logs/lessons-learned.md` | Add L-005 if any new lessons emerge |

## 6. Dependencies between tasks

```
T1 (cn) ──► T2,T3,T4 (atoms) ──► T5 (barrel) ──► T6,T7 (molecules) ──► T8 (barrel)
                                                       │
                                                       ▼
                                        T9–T12 (templates) ◄── T14 (store)
                                                       │
                                                       ▼
                                        T13 (barrel) ──► T15,T16,T17 (pages)

Tests T18–T24 follow their respective source tasks. T25 (docs) follows all.
```

## 7. Acceptance criteria mapping

| AC | Validated by |
|---|---|
| **AC-01** Three columns on desktop | `AppShell.test.tsx` — renders all 3 slots with viewport ≥ 1024 px (mocked `matchMedia`) |
| **AC-02** Mobile shows center only | `AppShell.test.tsx` — < 768 px viewport: left/right hidden by default, toggle buttons present in top bar |
| **AC-03** Mobile panels slide out | `AppShell.test.tsx` — clicking left toggle sets `leftPanelOpen=true`, overlay appears, overlay click closes |

Plus the BRD-11 checklist items (§7) all map 1:1 to T1..T17.

## 8. Quality gates

| Gate | Target |
|---|---|
| Review score | ≥ 9/10 |
| Test coverage | ≥ 80 % on changed files |
| `npm run typecheck` | clean |
| `npm run lint` | clean (no `@typescript-eslint/no-explicit-any`, no atomic layer violations) |
| `npm test` | all green |
| jest-axe violations | 0 on every rendered component |

## 9. Risks / open questions

- **shadcn primitives not wired yet.** Atoms (`Button`, `Badge`, `Spinner`) are implemented as plain components for BRD-11 and will be migrated to wrap `components/ui/*` once shadcn is installed (BRD-12). The atom API is stable so the migration is internal.
- **`useViewport()` hook deferred.** `AppShell` reads `window.matchMedia` directly with a `useEffect` listener for now. Will be promoted to `hooks/useViewport.ts` (debounced 150 ms per ui-prototype §9.16) when a second consumer appears.
- No blockers requiring user input.

## 10. Validation commands

```powershell
cd frontend
npm install            # only if jest-axe was added since last install
npm run typecheck
npm run lint
npm test -- --run
```
