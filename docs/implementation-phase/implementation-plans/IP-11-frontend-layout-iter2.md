# IP-11 (Iteration 2): Auth Wiring into the Layout Shell

**BRD Reference:** [BRD-11](../brds/BRD-11-frontend-layout.md) (+ client side of [BRD-04](../brds/BRD-04-user-identity.md))
**Author:** Orchestrator Agent
**Date:** 2026-05-26
**Status:** Approved for implementation
**Iteration:** 2 (follow-up to [IP-11 iter 1](./IP-11-frontend-layout.md))

---

## 1. Why a second iteration

Iteration 1 shipped `AppShell` + atoms + templates but **explicitly deferred**:

> `LoginModal` and `useUser` wiring (BRD-04 client side) — IP-11 iter 1 §3

IP-04 iter 1 in turn shipped `UsernameModal` + `userStore` but **also explicitly deferred** mounting them:

> Wiring `UsernameModal` into a page / app entry — BRD-11 already covers the layout; this BRD ships the modal + store only, ready to be mounted later. — IP-04 §3

Net effect on the deployed app (https://novum-seven.vercel.app/): **no path to login exists in the UI**. There is no `initialize()` call on boot, no trigger to open the modal, no identity indicator in the shell, no logout. This iteration closes that gap.

The auth wiring belongs in IP-11 (not a new BRD) because the shell — `AppShell`, its TopBar, its global overlays — is owned by BRD-11.

## 2. Scope

In scope:

1. Mount `UsernameModal` once, globally, above the router so every route sees it.
2. Drive boot-time verification: call `useUserStore.getState().initialize()` exactly once at app startup.
3. Auto-open the modal when `!isVerifying && !isAuthenticated`; never auto-open while `isVerifying`.
4. Promote the existing mobile-only `MobileTopBar` in `AppShell` to a **desktop TopBar** as well, so identity is visible on every viewport. Add an identity slot:
   - Authenticated: username pill + Logout action.
   - Unauthenticated: `Sign in` button that opens the modal.
5. Re-skin `UsernameModal` to design tokens (it currently uses hardcoded `bg-white dark:bg-neutral-900`, `text-neutral-*`, `border` defaults — violates ui-prototype §1.3 "zero hardcoded hex"). Behavior unchanged.
6. Co-located tests for everything above. jest-axe on all rendered components.

Out of scope (deferred, with rationale):

- Server-injected username/token in API calls — owned by [`lib/api.ts`](../../frontend/src/lib/api.ts) work in BRD-12/13. This iteration only handles UI wiring of identity.
- Token recovery / re-issue flow — not in BRD-04.
- Dark/light toggle — V2.
- Persisting `lastSeenUsername` for nicer modal copy — V2.

## 3. Sources reconciled

| Topic | BRD-04 says | BRD-11 / ui-prototype say | **Decision (binding)** |
|---|---|---|---|
| Modal mount point | "ready to be mounted later" (§4.9) | M1 modal lives above the AppShell (ui-prototype §3.2) | Mount **once** in `main.tsx` as a sibling of `<RouterProvider>` so it is route-independent. |
| Auto-open trigger | Not specified | M1 opens on first visit (ui-prototype §3.2) | Open when `!isVerifying && !isAuthenticated`. Modal owns its own `isOpen` derived from the store. |
| Identity location | "no header chrome required" (BRD-04 §4.9) | TopBar identity slot (ui-prototype §2 + §3.2) | TopBar slot. Visible on desktop too (not only mobile as in iter 1). |
| Modal styling | shadcn primitives (BRD-04 §4.9) | Design tokens (`var(--bg-*)`, `var(--text-*)`), no hardcoded hex (§1.3) | Use tokens **now**; shadcn migration deferred to BRD-12 (consistent with iter 1 §9). |
| `initialize()` location | Not specified | — | `main.tsx` `useEffect` inside a tiny `<AppBoot>` component that wraps `RouterProvider`. Single call, StrictMode-safe via a module-level guard. |
| StrictMode double-mount | — | React 19 double-invokes effects in dev | Guard `initialize()` behind a module-level `initStarted` flag. |

## 4. Task breakdown

### 4.1 Boot wiring

- [ ] **T1** — `frontend/src/main.tsx`: introduce `<AppBoot>` wrapper that
  - on mount, calls `useUserStore.getState().initialize()` exactly once (module-level guard),
  - renders `{children}` and `<UsernameModalContainer />` as siblings.
  Wrap the existing `<RouterProvider>` in `<AppBoot>`.

### 4.2 Global modal container

- [ ] **T2** — `frontend/src/components/organisms/UsernameModalContainer.tsx`: subscribes to `useUserStore` and renders `<UsernameModal isOpen={!isVerifying && !isAuthenticated} onClose={…} />`. `onClose` is a no-op when unauthenticated (the modal stays open until the user registers — there is no "guest" mode in V1). Export from `organisms/index.ts`.

### 4.3 TopBar promotion

- [ ] **T3** — Refactor `AppShell.tsx`: extract `MobileTopBar` into a new `TopBar` rendered **on every breakpoint**. Hamburger/PanelRight buttons remain visible only when the corresponding panel is drawerized (i.e. only on tablet/mobile). Desktop renders the same TopBar but without those toggles.
- [ ] **T4** — Add `IdentitySlot` molecule to the TopBar right-edge:
  - Authenticated → username pill (`<Badge variant="secondary">{username}</Badge>`) + `Logout` ghost `Button` (`size="sm"`).
  - Unauthenticated and not verifying → `Sign in` primary `Button` (`size="sm"`) that calls `openLoginModal()` (see T5).
  - Verifying → `Spinner` `size="sm"`.

### 4.4 Modal open state

- [ ] **T5** — Add a tiny `useLoginModal()` hook in `frontend/src/hooks/useLoginModal.ts` exposing `{isOpen, open, close}`. Backed by a one-key module-level signal (`zustand` create or simple `useSyncExternalStore`). This lets the `Sign in` button in the TopBar force-open the modal even when the auto-open condition is false (e.g., after a logout). `UsernameModalContainer` ORs the auto-open condition with this hook's `isOpen`.

### 4.5 Modal token re-skin

- [ ] **T6** — Rewrite `UsernameModal.tsx` JSX classes to use design tokens only:
  - dialog backdrop: `bg-[var(--overlay-scrim)]` (add token if missing — see T7)
  - dialog surface: `bg-[var(--bg-secondary)]`, `border border-[var(--glass-border)]`
  - title: `text-[var(--text-primary)]`
  - description: `text-[var(--text-secondary)]`
  - input: `bg-[var(--bg-primary)]`, `border-[var(--glass-border)]`, `text-[var(--text-primary)]`, `focus-visible:ring-[var(--accent)]`
  - error: `text-[var(--semantic-error)]`
  - Cancel: `<Button variant="ghost" size="md">`; Submit: `<Button variant="primary" size="md" loading={isLoading}>` (reuse atoms from iter 1)
  Behavior, props and ARIA unchanged.
- [ ] **T7** — Add `--overlay-scrim: rgba(0,0,0,0.5);` to `frontend/src/index.css` `:root` if not already defined. Document in `ui-prototype.md §1.1` (token table) via the doc update task T15.

### 4.6 Logout flow

- [ ] **T8** — TopBar `Logout` button calls `useUserStore.getState().logout()`. Modal re-appears automatically on the next render via the auto-open condition. No navigation change required (deterministic per RF-08).

### 4.7 Tests (co-located, mandatory per L-002)

- [ ] **T9** — `UsernameModalContainer.test.tsx`:
  - hidden while `isVerifying`,
  - shown after `initialize` resolves with no stored identity,
  - hidden after a successful `register`,
  - shown again after `logout`,
  - shown when `useLoginModal().open()` is called even if authenticated (covers Sign-in re-trigger edge case after logout),
  - a11y (jest-axe).
- [ ] **T10** — `UsernameModal.test.tsx` (extend existing if present, otherwise create):
  - renders with token-based classes (assert via `getComputedStyle` presence of `--bg-secondary` via class string match, not numeric color),
  - submit calls `register`,
  - error message rendered on rejection,
  - `loading` disables submit,
  - a11y.
- [ ] **T11** — `AppShell.test.tsx` (extend iter 1):
  - TopBar renders on `desktop` breakpoint,
  - `IdentitySlot` shows Spinner while `isVerifying`,
  - shows `Sign in` button when unauthenticated and not verifying,
  - shows username pill + Logout when authenticated,
  - `Logout` click clears store and re-opens modal,
  - a11y.
- [ ] **T12** — `useLoginModal.test.ts`: open/close transitions, shared state across consumers.
- [ ] **T13** — `main.tsx` smoke test (`main.test.tsx`): render via `<AppBoot>{<div/>}</AppBoot>` and assert `initialize` is called exactly once across two consecutive mounts (StrictMode guard). Mock `useUserStore.getState`.

### 4.8 Docs

- [ ] **T14** — `docs/implementation-phase/unit-tests/UT-11-frontend-layout-iter2.md`: append-only test inventory for the new files.
- [ ] **T15** — Update `docs/understanding-phase/ui-prototype.md` §1.1 (Color tokens): add `--overlay-scrim` row. Update §2/§3.2 to show the TopBar `IdentitySlot` on desktop (small diff).
- [ ] **T16** — Append a row to `docs/implementation-phase/implementation-plans/README.md` for iter 2 if that index exists.
- [ ] **T17** — `.github/memory-bank/logs/decisions-history.md`: log D-00X — "Auth wiring closed via IP-11 iter 2 (not a new BRD)".

## 5. Files

### 5.1 Create

| Path | Layer |
|---|---|
| `frontend/src/components/organisms/UsernameModalContainer.tsx` + `.test.tsx` | organism |
| `frontend/src/components/molecules/IdentitySlot.tsx` + `.test.tsx` | molecule |
| `frontend/src/hooks/useLoginModal.ts` + `.test.ts` | hook |
| `frontend/src/main.test.tsx` | smoke test |
| `docs/implementation-phase/unit-tests/UT-11-frontend-layout-iter2.md` | docs |
| `docs/implementation-phase/reviews/CR-11-002-auth-wiring.md` | docs (created by Reviewer) |

### 5.2 Modify

| Path | Reason |
|---|---|
| `frontend/src/main.tsx` | Introduce `<AppBoot>` wrapper; call `initialize()` once |
| `frontend/src/components/templates/AppShell.tsx` | Promote TopBar to all breakpoints, add `IdentitySlot` |
| `frontend/src/components/templates/AppShell.test.tsx` | Tests for new TopBar behavior |
| `frontend/src/components/organisms/UsernameModal.tsx` | Token-only classes; use atoms `Button`/`Spinner` |
| `frontend/src/components/organisms/index.ts` | Export `UsernameModalContainer` |
| `frontend/src/components/molecules/index.ts` | Export `IdentitySlot` |
| `frontend/src/index.css` | Add `--overlay-scrim` token if missing |
| `docs/understanding-phase/ui-prototype.md` | §1.1 token table; §2/§3.2 TopBar identity slot |
| `.github/memory-bank/logs/decisions-history.md` | Log decision |
| `.github/memory-bank/indices/knowledge-base-index.md` | Index iter 2 docs |

### 5.3 Untouched (intentionally)

- `userStore.ts` — already correct (BRD-04 §4.8).
- `auth_service.py`, `routes/auth.py`, `auth/token.py` — backend unchanged.
- Routes / pages — no auth gating in V1; `GET /api/runs/:id` stays public per RF-05 (and per the iter 1 review note "intentionally unauthenticated").

## 6. Dependencies between tasks

```
T7 (token) ──► T6 (modal re-skin) ──► T10 (modal tests)
                       │
                       ▼
T5 (useLoginModal) ──► T2 (Container) ──► T9 (Container tests)
                       │                       │
                       ▼                       │
T4 (IdentitySlot) ──► T3 (AppShell TopBar) ──► T11 (AppShell tests)
                       │
                       ▼
T1 (main.tsx + AppBoot) ──► T13 (main smoke test)
                       │
                       ▼
T8 (logout wiring) covered by T11.

T14–T17 (docs) follow all code tasks.
```

## 7. Acceptance criteria mapping

New ACs added for iter 2 (extend BRD-11 §6):

| AC | Validated by |
|---|---|
| **AC-04** First-visit user is presented with the identity modal | `UsernameModalContainer.test.tsx` — `initialize` resolves with no stored identity → modal visible |
| **AC-05** Returning verified user is not prompted | `UsernameModalContainer.test.tsx` — `initialize` resolves valid → modal hidden |
| **AC-06** Username is visible in the shell on every breakpoint | `AppShell.test.tsx` — TopBar `IdentitySlot` renders on desktop, tablet, mobile |
| **AC-07** Logout clears identity and re-opens the modal | `AppShell.test.tsx` — Logout click → store cleared, modal re-appears |
| **AC-08** `initialize` runs exactly once per app load | `main.test.tsx` — two StrictMode mounts → one call |
| **AC-09** Modal uses design tokens only (no hardcoded color) | `UsernameModal.test.tsx` — class string assertions; lint rule (future) |

Original AC-01..AC-03 remain validated by iter 1 tests; the AppShell refactor must not regress them.

## 8. Quality gates

| Gate | Target |
|---|---|
| Review score | ≥ 9/10 |
| Test coverage | ≥ 80 % on changed files, **100 % on `UsernameModalContainer` and `useLoginModal`** (small files, no excuse) |
| `npm run typecheck` | clean |
| `npm run lint` | clean (no `any`, no hardcoded hex in modified files) |
| `npm test` | all green (iter 1 tests must still pass) |
| jest-axe violations | 0 |
| Deployed smoke (Vercel preview) | M1 modal visible on `/`, dismissed after registering, persists across reload |

## 9. Risks / open questions

- **StrictMode double-init in dev.** Mitigated by the module-level `initStarted` guard in `<AppBoot>`. T13 explicitly asserts the single-call contract.
- **Closing the modal while unauthenticated.** Intentionally a no-op in V1 — there is no guest mode. The Cancel button is hidden when `!isAuthenticated`. (BRD-04 §4.9 leaves dismissal undefined; we choose the strict reading.)
- **Offline `initialize` quirk.** The store treats network errors as "assume valid" (BRD-04 §4.8). This means a brand-new visitor in airplane mode with no stored identity still sees the modal (correct — no stored identity ⇒ unauthenticated). No change required.
- **shadcn `Dialog` migration.** Deferred to BRD-12 along with the rest of the shadcn migration; the `UsernameModal` API will not change.

## 10. Validation commands

```powershell
cd frontend
npm install            # only if dev deps changed (no new ones expected)
npm run typecheck
npm run lint
npm test -- --run
npm run build          # ensure production bundle still builds
```

Manual smoke (post-deploy):

1. Open the Vercel preview URL in an incognito window → modal appears.
2. Register `testuser` → modal closes, TopBar shows `testuser` + Logout.
3. Reload → no modal (verified via `localStorage`).
4. Click Logout → modal re-appears, `localStorage.novum_user` is gone.
5. Resize to mobile → TopBar still shows identity slot.
