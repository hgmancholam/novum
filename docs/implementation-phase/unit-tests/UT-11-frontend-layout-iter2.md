# UT-11 (Iteration 2): Auth Wiring Test Inventory

**Plan Reference:** [IP-11 iter 2](../implementation-plans/IP-11-frontend-layout-iter2.md)
**Date:** 2026-05-26

## Test Files

| File | Tests | Purpose |
|---|---|---|
| `frontend/src/hooks/useLoginModal.test.ts` | 4 | Open/close transitions, shared state across consumers (T12) |
| `frontend/src/components/organisms/UsernameModalContainer.test.tsx` | 6 | Auto-open contract, logout re-open, manual open via `useLoginModal`, a11y (T9) |
| `frontend/src/components/organisms/UsernameModal.test.tsx` | 8 | Token-only classes, no hardcoded colors, register success/error, Cancel visibility rules, a11y (T10) |
| `frontend/src/components/templates/AppShell.test.tsx` | +6 (iter-2 subsuite) | TopBar on every breakpoint, IdentitySlot states, Logout wiring, a11y (T11) |
| `frontend/src/main.test.tsx` | 2 | `<AppBoot>` calls `initialize` exactly once across two mounts; renders children + container (T13) |

## Coverage Targets

- ≥ 80 % on changed files.
- **100 %** on `UsernameModalContainer.tsx` and `useLoginModal.ts` (small files, no excuse).

## Acceptance Criteria Mapped

| AC (from IP-11 iter 2 §7) | Test |
|---|---|
| AC-04 First-visit user sees identity modal | `UsernameModalContainer.test.tsx::is shown after initialize resolves` |
| AC-05 Returning verified user is not prompted | `UsernameModalContainer.test.tsx::is hidden after a successful register` |
| AC-06 Username visible in shell on every breakpoint | `AppShell.test.tsx::renders the IdentitySlot on tablet and mobile too` |
| AC-07 Logout clears identity and re-opens the modal | `AppShell.test.tsx::clears the store when Logout is clicked` + container test for logout transition |
| AC-08 `initialize` runs exactly once per app load | `main.test.tsx::calls useUserStore.initialize exactly once across two mounts` |
| AC-09 Modal uses design tokens only | `UsernameModal.test.tsx::renders the dialog with token-based classes` |
