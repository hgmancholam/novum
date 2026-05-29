# Implementation Plan — IP-28: Theme Toggle (Light / Dark Mode)

**Plan ID:** IP-28
**Parent BRD:** [BRD-28 v1.0](../brds/BRD-28-theme-toggle-light-dark.md)
**Parent User Stories:** _(to be drafted alongside this plan — `US-28-A` theme-tokens-and-boot, `US-28-B` theme-toggle-ui)_
**Date:** 2026-05-29
**Author:** Orchestrator Agent
**Estimated Effort:** S–M (≈3–4 h pair-session)
**Iteration:** 1

---

## 1. Summary

Introduce a two-mode visual theme (`dark` default, `light` opt-in) for the Novum SPA. The change is **frontend-only and CSS-variable-driven**: every existing Slate Aurora token defined on `:root` in `frontend/src/index.css` gains a counterpart inside a `:root[data-theme="light"]` block, so any component already consuming `var(--token)` switches automatically with zero refactor.

A pure helpers module (`lib/theme.ts`) handles `localStorage` read/write under the key `novum:theme` (wrapped in `try/catch` for private-mode / quota safety) and writes `document.documentElement.dataset.theme`. A new hook `useTheme()` exposes `{ theme, setTheme, toggle }` and synchronizes across tabs via the `storage` event. A new atom `ThemeToggleIcon` and molecule `ThemeToggle` render a `role="switch"` button that mounts in the existing top action bar of `AppShell` (next to `IdentitySlot`) — there is **no** `AppHeader` organism in the codebase, so BRD-28 §4.1's reference to `AppHeader.tsx` is corrected here to `templates/AppShell.tsx` (the actual top-bar owner, verified at `AppShell.tsx:163`).

A small synchronous boot script is injected into `index.html`'s `<head>` **before** the Vite module script to set `data-theme` from `localStorage` before first paint, eliminating FOUC. Tailwind v4's `dark:` modifier — currently used by `Toaster.tsx` (lines 48–52) — is rewired via `@variant dark (&:where([data-theme="dark"], [data-theme="dark"] *))` in `index.css` so existing utilities keep working under the new mechanism without a bulk rewrite.

**Additive only:** no backend changes, no env vars, no DB migration, no new API endpoints, no event types, no impact on the agent FSM, the three plugin seams, the LLM client, SSE, `stop_reason`, or `final_confidence`. The default for new users and users with no `localStorage` entry stays **`dark`** — zero regression for the current product identity.

RF traceability: **RF-13** (theme is cosmetic only — every trust signal stays visible and AA-contrasted in both modes), **RF-16** (storage failure falls back to in-memory + default), **RF-05** (N/A — purely client-side).

---

## 2. Prerequisites

- [x] BRD-28 v1.0 approved by F1 Auditor — locks default theme (`dark`), storage key (`novum:theme`), out-of-scope items (no system mode in V1).
- [x] Slate Aurora tokens already centralized on `:root` in `frontend/src/index.css` (verified, lines 7–80). All organisms below the top bar consume them via `var(--token)` or Tailwind v4 arbitrary tokens like `bg-(--bg-secondary)` — no major refactor needed.
- [x] Tailwind v4 + `@tailwindcss/vite` are configured per the user-memory rule `tailwind-v4-vite.md` — `@variant` directive is available.
- [x] `AppShell` template (`frontend/src/components/templates/AppShell.tsx`) already owns the top action bar (lines 163–189) where `IdentitySlot` and the "How do we work?" pill live. The `ThemeToggle` mounts there. **There is no `AppHeader` organism** — this corrects BRD-28 §4.1 / §4.6.
- [x] `useReducedMotion()` from `motion/react` is already used elsewhere (e.g. `ServiceStatusBar`); reuse for the icon cross-fade.
- [x] shadcn `Tooltip` is in deps (used by `StatusPill`) — reused for the toggle's hover label.
- [x] `lucide-react` provides `Sun` and `Moon` icons (already used across the app).
- [x] `jest-axe` is wired in `frontend/src/test/` (used by `ServiceStatusBar.test.tsx`, `UsernameModal.test.tsx`) — reused for AC-04 contrast checks.
- [x] An existing component already uses Tailwind's `dark:` modifier: `Toaster.tsx` lines 48–52. This is the **canonical regression target** for the `@variant dark` bridge (Phase 1 task 1.3 + Phase 3 task 3.6).
- [x] An existing test asserts the absence of `dark:bg-neutral-` in one organism (`UsernameModal.test.tsx:34`) — confirm that assertion stays green after the bridge is in place (it should; the bridge does not introduce new `dark:` utilities).

---

## 3. Task Breakdown

### Phase 1 — CSS tokens & boot

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 1.1 | Add the `light` token block to `index.css`. Insert **immediately after** the existing Novum `:root { ... }` block (ends ~line 80) and **before** the shadcn legacy `:root { ... }` block (starts ~line 85). Block contents exactly per BRD-28 §4.8 — surfaces, gradient, glass (dark slate at low opacity, NOT light slate — R-04), accent soft/glow, warm soft/glow, text, scrim, shadows. Semantic colors (`--semantic-*`) are intentionally **not** overridden (they already meet AA on both backgrounds per BRD §4.8 comment). The `--accent`, `--accent-hover`, `--warm`, `--feed-*`, `--radius-*`, `--ease-*` tokens are intentionally not overridden (palette-neutral). | `frontend/src/index.css` (MODIFY) | S | — | AC-02, AC-04; §4.8 |
| 1.2 | Add the Tailwind v4 `@variant dark` directive at the top of `index.css`, **right after** the `@import "tailwindcss";` line (must come after the import per Tailwind v4 cascade rules): `@variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));`. This rewires every existing `dark:` utility (Toaster, future code) so it activates on `data-theme="dark"` instead of the legacy `.dark` class. | `frontend/src/index.css` (MODIFY) | XS | 1.1 | §4.8 Toaster bridge, R-01 |
| 1.3 | **Decide and document** the fate of the legacy `.dark { ... }` shadcn block (lines ~102–120). Two acceptable outcomes:<br>**Option A (recommended)** — duplicate the block's contents under `:root[data-theme="dark"]` as well, so shadcn primitives that read `--background`, `--foreground`, etc. work without the `.dark` class being present (it never is — nothing in the app currently adds `class="dark"` to `<html>`). Then delete the now-redundant `.dark { ... }` block.<br>**Option B** — leave `.dark { ... }` untouched (dead code; harmless) and add the same overrides under `:root[data-theme="dark"]`.<br>Pick **A** unless audit-on-touch reveals a shadcn primitive that breaks. Record the choice in §6.2 of this plan after implementation. | `frontend/src/index.css` (MODIFY) | S | 1.1 | R-05; AC-02, AC-04 |
| 1.4 | Inject the FOUC-guard boot script into `frontend/index.html`. Insert **inside `<head>`, immediately before `<title>`** (so it runs before the title repaint and before the Vite module script). Body exactly per BRD-28 §4.9: synchronous IIFE, `try`/`catch`, validates value is `"light"` or `"dark"`, falls back to `"dark"`, writes `document.documentElement.dataset.theme`. Verify minified size < 1 KB (it is). | `frontend/index.html` (MODIFY) | XS | — | AC-01, AC-03, R-03 |

### Phase 2 — Logic layer

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 2.1 | Create `frontend/src/lib/theme.ts`. Exports exactly per BRD-28 §4.6.2:<br>```ts<br>export type Theme = "dark" \| "light";<br>export const THEME_STORAGE_KEY = "novum:theme" as const;<br>export const DEFAULT_THEME: Theme = "dark";<br>export function isTheme(v: unknown): v is Theme;<br>export function readStoredTheme(): Theme;<br>export function writeStoredTheme(theme: Theme): void;<br>export function applyThemeToDocument(theme: Theme): void;<br>```<br>Implementation rules:<br>• `readStoredTheme` wraps `localStorage.getItem` in `try/catch` and validates with `isTheme`; any failure → `DEFAULT_THEME`.<br>• `writeStoredTheme` wraps `localStorage.setItem` in `try/catch` and **silently swallows** `QuotaExceededError` / `SecurityError` (AC-06, R-02). No logging — this path is hot.<br>• `applyThemeToDocument` is SSR-safe: early-return when `typeof document === "undefined"`.<br>• `isTheme` uses a literal-union guard, **never** `[key: string]: unknown` (user-memory `typescript-react-props.md`). | `frontend/src/lib/theme.ts` (NEW) | S | — | AC-01..AC-03, AC-06; R-02 |
| 2.2 | Create `frontend/src/hooks/useTheme.ts`. Public API exactly per BRD-28 §4.6.1:<br>```ts<br>export interface UseThemeReturn {<br>  theme: Theme;<br>  setTheme: (next: Theme) => void;<br>  toggle: () => void;<br>}<br>export function useTheme(): UseThemeReturn;<br>```<br>Implementation:<br>• `useState<Theme>(() => readStoredTheme())` for initial value (the boot script in 1.4 has already applied it to the DOM; this just mirrors it in React state).<br>• `setTheme(next)` → `writeStoredTheme(next)`; `applyThemeToDocument(next)`; `setState(next)`.<br>• `toggle()` → `setTheme(theme === "dark" ? "light" : "dark")` (via the functional updater pattern to avoid stale closures).<br>• `useEffect` subscribes to `window.addEventListener("storage", ...)`: when `e.key === THEME_STORAGE_KEY` and `isTheme(e.newValue)`, call `applyThemeToDocument(e.newValue)` and `setState(e.newValue)` — satisfies AC-05 (cross-tab sync).<br>• **Does NOT** subscribe to `matchMedia("(prefers-color-scheme: dark)")` — out of scope (§10).<br>• SSR-safe: gate `window` access behind `typeof window !== "undefined"`.<br>The hook does **not** memoize the return object; React's referential stability for primitive `theme` is enough, and stable callbacks are provided by `useCallback`. | `frontend/src/hooks/useTheme.ts` (NEW) | S | 2.1 | AC-02, AC-05, AC-06 |

### Phase 3 — UI components

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 3.1 | Create the atom `ThemeToggleIcon` (`atoms/ThemeToggleIcon.tsx`). Props: `{ theme: Theme }` extending `SVGAttributes<SVGSVGElement>` (per user-memory `typescript-react-props.md` — **never** `[key: string]: unknown`). Renders:<br>• `<AnimatePresence mode="wait" initial={false}>` (from `motion/react`) wrapping either `<motion.span key="sun">` or `<motion.span key="moon">` based on `theme`.<br>• When `theme === "dark"` → render `<Sun />` (lucide) — hint = "click to switch to light".<br>• When `theme === "light"` → render `<Moon />` (lucide).<br>• Cross-fade: `initial={{ opacity: 0, rotate: -90 }}`, `animate={{ opacity: 1, rotate: 0 }}`, `exit={{ opacity: 0, rotate: 90 }}`, `transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}` (matches `--ease-out`).<br>• Gate the rotate behind `useReducedMotion()` — when reduced, only opacity is animated.<br>• Icon size: `h-4 w-4`, `strokeWidth={1.75}`, `aria-hidden="true"` (the parent button supplies the accessible label). | `frontend/src/components/atoms/ThemeToggleIcon.tsx` (NEW), `ThemeToggleIcon.test.tsx` (NEW) | S | — | §4.6, §4.7 |
| 3.2 | Create the molecule `ThemeToggle` (`molecules/ThemeToggle.tsx`). No props (uses `useTheme()` internally). Structure:<br>```tsx<br><Tooltip><br>  <TooltipTrigger asChild><br>    <button<br>      type="button"<br>      role="switch"<br>      aria-checked={theme === "light"}<br>      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}<br>      onClick={toggle}<br>      className={cn(<br>        "inline-flex h-9 w-9 items-center justify-center rounded-md",<br>        "text-(--text-primary) transition-colors",<br>        "hover:bg-(--glass-bg)",<br>        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--accent)"<br>      )}<br>    ><br>      <ThemeToggleIcon theme={theme} /><br>    </button><br>  </TooltipTrigger><br>  <TooltipContent>{theme === "dark" ? "Light mode" : "Dark mode"}</TooltipContent><br></Tooltip><br>```<br>Sizing (`h-9 w-9`) matches the sibling trace-toggle button at `AppShell.tsx:183`. Tooltip `delayDuration={200}` matches `StatusPill`. **Strings in English** per the language policy in user memory. | `frontend/src/components/molecules/ThemeToggle.tsx` (NEW), `ThemeToggle.test.tsx` (NEW) | S | 2.2, 3.1 | AC-02, AC-07 |
| 3.3 | Re-export `ThemeToggle` from `frontend/src/components/molecules/index.ts` so it can be imported via the barrel like its siblings (`IdentitySlot`, `StatusPill`, …). | `frontend/src/components/molecules/index.ts` (MODIFY) | XS | 3.2 | conventions |
| 3.4 | Mount `<ThemeToggle />` in `AppShell`'s top action bar. Open `frontend/src/components/templates/AppShell.tsx`, locate the inner container at line ~163 (`<div className="flex items-center gap-2">`), and insert `<ThemeToggle />` **immediately before** `<IdentitySlot />` (line 177). Order in the row becomes: `[How do we work?]  [ThemeToggle]  [IdentitySlot]  [Open trace?]`. Update the import line at the top to add `ThemeToggle` to the existing `IdentitySlot` barrel import (Task 3.3 makes this a one-line change). | `frontend/src/components/templates/AppShell.tsx` (MODIFY) | XS | 3.3 | AC-01 placement |
| 3.5 | **`Toaster.tsx` audit & visual smoke.** Read `frontend/src/components/molecules/Toaster.tsx` lines 48–52 (the only file using `dark:` modifiers today). After Task 1.2 the bridge means `dark:bg-red-950/80` now activates when `[data-theme="dark"]` is set. **Manually verify** in dev (`npm run dev`): trigger a toast in dark mode → confirm dark styling; toggle to light → confirm the non-`dark:` classes (`bg-red-50`, `bg-white`, etc.) take over. **No code changes** to `Toaster.tsx` are required if the bridge works — deferred bulk migration is explicit Out-of-Scope (§10). If a regression is observed, the minimal fix is to swap the affected utility for a token (e.g. `bg-(--semantic-danger)/12`) on that single line. | `frontend/src/components/molecules/Toaster.tsx` (NO-OP unless regression) | XS–S | 1.2 | R-01 |
| 3.6 | ESLint sanity: confirm `import/no-restricted-paths` still passes (atoms don't import molecules, molecules don't import organisms, etc.). Run `npm run lint`. The new files respect the layering: `ThemeToggleIcon` (atom) imports only from `motion/react` + `lucide-react`; `ThemeToggle` (molecule) imports `ThemeToggleIcon` atom + `useTheme` hook + shadcn `Tooltip` (ui). | n/a | XS | 3.4 | atomic-layering rule |

### Phase 4 — Tests

| # | Task | File(s) | Effort | Depends on | Satisfies |
|---|------|---------|--------|------------|-----------|
| 4.1 | `lib/theme.test.ts` — pure-logic tests, no DOM render needed.<br>• `isTheme` accepts `"dark"`/`"light"`, rejects `""`, `"system"`, `null`, `42`.<br>• `readStoredTheme`: returns `"light"` when storage has `"light"`; returns `DEFAULT_THEME` when storage is empty / has an invalid value / `getItem` throws.<br>• `writeStoredTheme`: writes to storage; does NOT throw when `setItem` throws `QuotaExceededError` (mock `Storage.prototype.setItem` to throw).<br>• `applyThemeToDocument`: sets `document.documentElement.dataset.theme`; no-op when `document` is undefined (use `vi.stubGlobal`). | `frontend/src/lib/theme.test.ts` (NEW) | S | 2.1 | AC-01, AC-06; R-02 |
| 4.2 | `hooks/useTheme.test.ts` — `renderHook` from `@testing-library/react`.<br>• Default: with empty `localStorage`, initial `theme` is `"dark"`; `document.documentElement.dataset.theme` is `"dark"` after first `act`.<br>• `toggle()`: flips dark → light, persists to storage, updates DOM (AC-02).<br>• `setTheme("light")` then re-render: `theme === "light"`.<br>• Cross-tab sync (AC-05): fire `new StorageEvent("storage", { key: "novum:theme", newValue: "light" })` on `window`; `result.current.theme` becomes `"light"` within a single `act`. Also assert: ignoring events with `key !== "novum:theme"` and events with invalid `newValue`.<br>• Storage-failure (AC-06): monkeypatch `localStorage.setItem` to throw; `toggle()` still updates `result.current.theme` and the DOM; no exception bubbles. | `frontend/src/hooks/useTheme.test.ts` (NEW) | M | 2.2 | AC-02, AC-05, AC-06 |
| 4.3 | `atoms/ThemeToggleIcon.test.tsx` — render with each theme; assert the right lucide icon is in the tree (look up by `data-lucide` or `<title>` if available, otherwise by class `lucide-sun` / `lucide-moon`). With `prefers-reduced-motion: reduce` (mock `matchMedia`), assert no `rotate` style is applied on the animated wrapper. | `frontend/src/components/atoms/ThemeToggleIcon.test.tsx` (NEW) | S | 3.1 | §4.6 |
| 4.4 | `molecules/ThemeToggle.test.tsx` — render inside a `<TooltipProvider>`.<br>• Has `role="switch"`; `aria-checked="false"` when theme is dark; `aria-checked="true"` after click (AC-02).<br>• `aria-label` reads `"Switch to light mode"` initially, `"Switch to dark mode"` after click.<br>• Keyboard: focus the button, press `Enter` → theme toggles. Same for `Space` (AC-07).<br>• `localStorage["novum:theme"]` updates to `"light"` after click.<br>• jest-axe: zero violations in both theme states (mount twice — once per theme — to cover both label strings). | `frontend/src/components/molecules/ThemeToggle.test.tsx` (NEW) | M | 3.2 | AC-02, AC-04, AC-07 |
| 4.5 | `templates/AppShell.test.tsx` — extend the existing file (do **not** create a new one). Add **one** assertion to the existing desktop-layout test: `expect(screen.getByRole("switch", { name: /switch to (light|dark) mode/i })).toBeInTheDocument();`. Add a second tiny test "AppShell — theme toggle persists choice across re-mount" that:<br>1. Renders `<AppShell>`, clicks the switch, asserts `localStorage["novum:theme"] === "light"`.<br>2. Unmounts and re-renders. Asserts the boot path (`useTheme` reading storage) reports `aria-checked="true"`. | `frontend/src/components/templates/AppShell.test.tsx` (MODIFY) | S | 3.4 | AC-01, AC-03 |
| 4.6 | Contrast regression (AC-04). Add an `it.each(["dark", "light"])(...)` block to `pages/HomePage` and `pages/NewRunContainer` test files (`HomePage.test.tsx` exists? if not, defer to whichever page test currently mounts the most surface — `NewRunContainer.test.tsx` is a strong candidate, verified at `pages/NewRunContainer.test.tsx`). For each theme: `document.documentElement.dataset.theme = theme`; render; `expect(await axe(container)).toHaveNoViolations()`. Reset `dataset.theme` in `afterEach`. **Two pages × two themes = four axe runs total** — keeps the suite under the existing axe budget. | `frontend/src/pages/NewRunContainer.test.tsx` (MODIFY) and at most one more page test (MODIFY) | M | 1.1, 1.3 | AC-04 |
| 4.7 | Confirm `git diff backend/` is empty after Phases 1–4 (`backend` is excluded from this BRD). Confirm `git diff frontend/src/types/` is empty (no schema export — there is no backend change). | n/a | XS | end | scope check |

### Phase 5 — Docs & memory bank

| # | Task | File(s) | Effort | Depends on |
|---|------|---------|--------|------------|
| 5.1 | Register IP-28, `ThemeToggle` molecule, `ThemeToggleIcon` atom, `useTheme` hook, `lib/theme.ts`, and the new `:root[data-theme="light"]` token block in the knowledge-base index. | `.github/memory-bank/indices/knowledge-base-index.md` | S | end |
| 5.2 | Append a decision entry: (a) `dark` chosen as default to match Slate Aurora identity and avoid regression; (b) `data-theme` attribute on `<html>` chosen over `class="dark"` so the same attribute drives both Tailwind utilities (via `@variant dark`) and Novum CSS-variable overrides; (c) no `prefers-color-scheme` auto mode in V1 (BRD §10); (d) FOUC guard kept inline-synchronous to remain < 1 KB and avoid a render-blocking JS module. | `.github/memory-bank/logs/decisions-history.md` | S | end |
| 5.3 | If the `Toaster.tsx` audit (Task 3.5) reveals a regression and a token swap is needed, record the pattern in lessons-learned (Tailwind v4 `@variant dark` bridges most cases but fails for X). Otherwise skip. | `.github/memory-bank/logs/lessons-learned.md` (optional) | XS | 3.5 |
| 5.4 | Update [ui-design.md](../../understanding-phase/ui-design.md) (or its equivalent — verify the actual filename; the repo's tech doc map lists `ui-prototype.md` §1) to document the **light** palette under a new §2.x. This is **binding** per the repo rule "update the originating doc — don't silently diverge from it in code". Mirror the BRD-28 §4.8 table verbatim, with a one-paragraph rationale ("Slate Aurora — Daylight variant"). | `docs/understanding-phase/ui-prototype.md` (MODIFY) | S | 1.1 |

---

## 4. File Modifications

### New files
```
frontend/src/lib/theme.ts
frontend/src/lib/theme.test.ts
frontend/src/hooks/useTheme.ts
frontend/src/hooks/useTheme.test.ts
frontend/src/components/atoms/ThemeToggleIcon.tsx
frontend/src/components/atoms/ThemeToggleIcon.test.tsx
frontend/src/components/molecules/ThemeToggle.tsx
frontend/src/components/molecules/ThemeToggle.test.tsx
docs/implementation-phase/implementation-plans/IP-28-theme-toggle-light-dark.md   (this file)
```

### Modified files
```
frontend/index.html                                          (FOUC boot script)
frontend/src/index.css                                       (light tokens + @variant dark)
frontend/src/components/molecules/index.ts                   (barrel export)
frontend/src/components/templates/AppShell.tsx               (mount toggle next to IdentitySlot)
frontend/src/components/templates/AppShell.test.tsx          (one assertion + one persistence test)
frontend/src/pages/NewRunContainer.test.tsx                  (AC-04 axe loop, plus possibly one more page test)
docs/understanding-phase/ui-prototype.md                     (light palette section)
.github/memory-bank/indices/knowledge-base-index.md
.github/memory-bank/logs/decisions-history.md
```

### Conditionally modified
```
frontend/src/components/molecules/Toaster.tsx                (only if Task 3.5 finds a regression)
frontend/src/index.css                                       (Option A in Task 1.3 deletes the legacy .dark block)
```

### Out of scope (do not touch)
```
backend/**                                                   (zero changes)
frontend/src/types/**                                        (no schema regen)
scripts/export_types.py                                      (not invoked)
```

---

## 5. Sequencing & Dependencies

```
Phase 1 (CSS + boot)
  ├── 1.1 light tokens ──┐
  ├── 1.2 @variant dark ─┤
  ├── 1.3 .dark block ───┤
  └── 1.4 index.html ─────┴──> Phase 2 (lib + hook)
                                ├── 2.1 lib/theme.ts ──┐
                                └── 2.2 useTheme ──────┴──> Phase 3 (UI)
                                                            ├── 3.1 atom ──┐
                                                            ├── 3.2 molecule ┤
                                                            ├── 3.3 barrel ─┤
                                                            ├── 3.4 mount ──┤
                                                            ├── 3.5 audit ──┤
                                                            └── 3.6 lint ────┴──> Phase 4 (tests) ──> Phase 5 (docs)
```

Phases 1 and 2 can run in parallel by two pair-programmers; Phase 3 needs both. Phases 1, 2, 3 must all complete before Phase 4's axe loop (4.6) is meaningful.

---

## 6. Acceptance Criteria Coverage

| BRD AC | Covered by |
|--------|-----------|
| AC-01 default theme is dark | 1.4 boot, 2.1 `DEFAULT_THEME`, 4.1, 4.5 |
| AC-02 toggle persists & applies | 2.1, 2.2, 3.2, 4.1, 4.2, 4.4 |
| AC-03 choice survives reload | 1.4 boot, 4.5 persistence test |
| AC-04 WCAG AA both themes | 1.1 token block, 4.4 toggle axe, 4.6 page axe |
| AC-05 cross-tab sync | 2.2 storage listener, 4.2 storage-event test |
| AC-06 storage failure resilience | 2.1 try/catch, 4.1, 4.2 |
| AC-07 keyboard accessibility | 3.2 native `<button>` + focus ring, 4.4 keyboard test |

Every BRD-28 AC maps to ≥ 1 implementation task **and** ≥ 1 test. No AC is left to manual QA only.

---

## 7. Risk Re-Assessment (vs BRD-28 §9)

| ID | BRD risk | Plan-time view | Residual action |
|----|----------|----------------|-----------------|
| R-01 hardcoded colors | Surveyed: only `Toaster.tsx` (5 lines) uses `dark:`. `UsernameModal.test.tsx:34` explicitly forbids `dark:bg-neutral-`. No raw `#xxxxxx` in components (spot-checked). | Bridge via `@variant dark` (1.2) + audit (3.5). No mass rewrite. |
| R-02 storage unavailable | Covered end-to-end. | Tasks 2.1 + 4.1 + 4.2. |
| R-03 FOUC | Boot script inline + synchronous + < 1 KB. | Task 1.4 + AC-01/AC-03 manual smoke. |
| R-04 glass surfaces in light mode | Light `--glass-bg` uses dark slate at 4 % (not light slate) — verified to be readable against white surfaces. | Task 1.1 implements exactly that. |
| R-05 shadcn `.dark` conflict | Task 1.3 explicitly chooses between Option A (delete) and Option B (keep harmless). | Decision recorded in 5.2. |

No new risks identified at plan time.

---

## 8. Out of Scope (re-confirmed)

Identical to BRD-28 §10 — repeated here for the Coder's convenience:

- No `prefers-color-scheme` auto mode.
- No server-side theme persistence (no `users.theme`, no API).
- No high-contrast / color-blind modes.
- No View Transitions API.
- No bulk migration of every `dark:` utility (bridge handles it).
- No marketing-site / external-docs theming.

---

## 9. Definition of Done

- [ ] All Phase 1–5 checklist items complete.
- [ ] `npm run lint` clean (frontend).
- [ ] `npm run typecheck` clean (frontend).
- [ ] `npm test` clean — every new test file green; pre-existing tests still green.
- [ ] Coverage on new files ≥ 80 % (per copilot-instructions §7.7). `lib/theme.ts` and `hooks/useTheme.ts` target ≥ 90 % (pure logic).
- [ ] `git diff backend/` is empty.
- [ ] BRD-28 ACs 1–7 verified — six by automated tests, one (AC-03 visual no-FOUC) by manual reload smoke captured in a 5-second screen recording attached to the PR.
- [ ] `docs/understanding-phase/ui-prototype.md` updated with the light palette (5.4).
- [ ] Memory bank entries created (5.1, 5.2).

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-29 | Orchestrator Agent | Initial plan (awaiting F2 Auditor) |
