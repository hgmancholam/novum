# UT-11: Frontend Setup & Layout Shell — Unit Tests

**BRD reference:** [BRD-11](../brds/BRD-11-frontend-layout.md)
**IP reference:** [IP-11](../implementation-plans/IP-11-frontend-layout.md)
**Author:** Coder Agent
**Date:** 2026-05-26
**Iteration:** 1

---

## 1. Scope

Co-located unit tests for the atoms, molecules, the `AppShell` template, and the `selectionStore` introduced by BRD-11. Higher-level pages remain placeholders in this BRD, so their tests are deferred.

## 2. Tooling

- **Vitest** (`environment: "jsdom"`, `globals: true`) — see [vitest.config.ts](../../../frontend/vitest.config.ts).
- **@testing-library/react** + **@testing-library/jest-dom**.
- **jest-axe** for a11y assertions (`expect(...).toHaveNoViolations()`).
- Global setup: [src/test/setup.ts](../../../frontend/src/test/setup.ts) (mocks `matchMedia` + `ResizeObserver`, registers jest-axe).
- Type augmentation: [src/test/jest-axe.d.ts](../../../frontend/src/test/jest-axe.d.ts).
- Commands: `npm test` (watch) and `npm run test -- --run` (CI).

## 3. Test inventory

| # | File | Component / module | Tests | Plan task |
|---|---|---|---|---|
| 1 | [Button.test.tsx](../../../frontend/src/components/atoms/Button.test.tsx) | `Button` atom | default render, 4 variants, 3 sizes, loading shows spinner + disables, `onClick` fires, disabled blocks click, loading blocks click, `forwardRef`, a11y | T18 |
| 2 | [Badge.test.tsx](../../../frontend/src/components/atoms/Badge.test.tsx) | `Badge` atom | renders children, each of 6 variants emits `data-variant`, distinct className per variant, custom `className` merge, a11y | T19 |
| 3 | [Spinner.test.tsx](../../../frontend/src/components/atoms/Spinner.test.tsx) | `Spinner` atom | `role="status"`, default + custom `aria-label`, 3 sizes apply class, custom `className`, a11y | T20 |
| 4 | [ConfidenceBar.test.tsx](../../../frontend/src/components/molecules/ConfidenceBar.test.tsx) | `ConfidenceBar` molecule | percentage rounding, default + custom label, `showLabel=false` hides label, passed flag flips at threshold boundary, value clamping, `aria-valuenow/min/max`, threshold marker rendered, a11y | T21 |
| 5 | [StatusBadge.test.tsx](../../../frontend/src/components/molecules/StatusBadge.test.tsx) | `StatusBadge` molecule | `running` → "Researching…" / info, each of 7 `StopReason` values maps to the canonical `ui-prototype.md` §7.4 label + variant, `errorReason` appended after "Errored —", non-errored ignores `errorReason`, fallback to Unknown, a11y | T22 |
| 6 | [AppShell.test.tsx](../../../frontend/src/components/templates/AppShell.test.tsx) | `AppShell` template | 3 slots render on desktop, tablet hides left + shows top-bar, mobile hides both panels, drawers open on store flags, overlay click closes, ESC closes, top-bar buttons open drawers, breakpoint exposed via `data-breakpoint`, a11y | T23 |
| 7 | [selectionStore.test.ts](../../../frontend/src/stores/selectionStore.test.ts) | `useSelectionStore` | initial state, `setSelectedRunId`, `setSelectedEventId`, `openLeftPanel/openRightPanel`, both toggles flip, `closePanels` resets | T24 |

## 4. Mapping to BRD-11 acceptance criteria

| BRD-11 AC | Covered by |
|---|---|
| **AC-01** — 3-panel layout renders on desktop | `AppShell.test.tsx`: "renders all three slots on desktop" |
| **AC-02** — left collapses to drawer on tablet/mobile | `AppShell.test.tsx`: "hides left panel and shows mobile top bar on tablet", "hides both side panels on mobile", "opens the left drawer when store flag is true (tablet)" |
| **AC-03** — drawers close via overlay and ESC | `AppShell.test.tsx`: "closes drawer when overlay is clicked", "closes drawer when Escape is pressed" |
| **§4.6 store contract** | `selectionStore.test.ts` (full suite) |
| **§3 design tokens (no hardcoded hex)** | Verified by code review; class assertions intentionally avoid hex to stay token-driven |
| **Atomic design layering** | Test paths follow atoms → molecules → templates → stores; pages remain placeholders |

## 5. Out of scope (deferred)

- Visual regression / Storybook snapshots — V2.
- Page-level integration tests (`HomePage`, `RunPage`, `DiffPage`) — they remain placeholders until BRD-12/13/14.
- E2E with Playwright — V2.

## 6. Running

```powershell
cd frontend
npm run test -- --run
```
