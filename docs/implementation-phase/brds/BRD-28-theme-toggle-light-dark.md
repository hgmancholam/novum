# BRD-28: Theme Toggle (Light / Dark Mode)

**Document ID:** BRD-28
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-29
**Implementation Order:** 28 of N
**Assumes shipped:** BRD-11 (frontend layout), BRD-04 (user identity / `userStore`), ui-design.md "Slate Aurora" tokens.

---

## 1. Executive Summary

Novum today ships a single **dark** visual theme ("Slate Aurora") encoded as CSS custom properties on `:root` in `frontend/src/index.css`. The visual identity is intentional — the design system is built around dark glass surfaces with indigo/amber accents — but a non-trivial subset of users research in bright environments (daylight, projector demos, accessibility preferences) where a light surface is preferable. Forcing dark mode in those contexts produces glare, washed-out content, and an accessibility friction point that the UI prototype's trust-surface mandate (RF-13) does not justify.

BRD-28 introduces a **two-mode theme system** — `dark` (current Slate Aurora, **default**) and `light` (new, derived palette) — exposed through a single **`ThemeToggle`** control in the global header. The user's choice is persisted in `localStorage` under the key `novum:theme` (consistent with the repo's "no cookies" decision in copilot-instructions §2) and re-applied on every page load before first paint via a small inline boot script in `index.html` to prevent FOUC (flash-of-unstyled-content).

The implementation is **CSS-variable-only**: every existing token in `:root` gets a `light` counterpart inside a `:root[data-theme="light"]` block. Components that already use `var(--token)` switch automatically. Components that hardcode Tailwind utility colors (`bg-slate-900`, `text-white`, etc.) — there are some in `Toaster.tsx` using the `dark:` Tailwind modifier — must be audited and migrated to tokens or to the official Tailwind `dark:` mechanism wired to `data-theme="dark"` via Tailwind v4 `@variant dark (...)`.

The toggle itself is a simple two-state control (no "system" option in V1 — see §10 Out of Scope). The default for **new users and users with no `localStorage` entry is `dark`**, matching the current product identity and avoiding any regression for existing users.

This BRD is **frontend-only and additive**: no backend changes, no DB migrations, no new env vars, no API endpoints, no event types, no impact on the agent FSM, the three plugin seams, the LLM client, SSE, or `stop_reason` semantics. The work is bounded by §6 (single new molecule, one CSS block, one boot script, one `useTheme` hook, one persistence key).

Binding success metrics in §10. Expected outcome: zero new runtime dependencies, < 5 ms theme-apply latency (synchronous DOM attribute write), zero FOUC on cold loads, WCAG 2.1 AA contrast on every interactive element in both themes.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-13 (UI as trust surface) | Surface every trust-relevant signal honestly | **Preserved.** Theme is purely cosmetic; it does not alter any displayed evidence, confidence value, or `stop_reason`. All trust elements remain visible and legible in both modes. |
| RF-16 (graceful degradation) | App stays usable when something fails | **Preserved.** If `localStorage` is unavailable (private mode, quota exceeded), the toggle falls back to in-memory state and the default `dark` theme is used. |
| RF-05 (single-server) | No distributed state | **N/A.** Theme is a pure client-side preference and never touches the server. |

No RF amendments. No changes to the `stop_reason` enum. No changes to the confidence formula. No changes to event semantics.

---

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-11 (frontend layout) | The `ThemeToggle` molecule mounts in the global header slot. |
| ui-design.md (Slate Aurora) | The `light` palette is **derived** from the same token names; only values change. |

No dependents block on this BRD; it is independently shippable. BRD-27 (Service Health Bar) is unaffected — `StatusDot` colors must work in both modes (verified in AC-04).

---

## 4. Technical Specification

### 4.1 File Structure

```
frontend/
  index.html                                  # MODIFY: inline boot script (FOUC guard)
  src/
    index.css                                 # MODIFY: add :root[data-theme="light"] block
    hooks/
      useTheme.ts                             # NEW
      useTheme.test.ts                        # NEW
    components/
      atoms/
        ThemeToggleIcon.tsx                   # NEW (sun/moon icon, swaps on theme)
        ThemeToggleIcon.test.tsx              # NEW
      molecules/
        ThemeToggle.tsx                       # NEW (button wrapping atom)
        ThemeToggle.test.tsx                  # NEW
        Toaster.tsx                           # MODIFY: replace ad-hoc `dark:` utilities with tokens
      organisms/
        AppHeader.tsx                         # MODIFY: mount <ThemeToggle /> in trailing slot
    lib/
      theme.ts                                # NEW: pure helpers (read/write storage, apply DOM)
      theme.test.ts                           # NEW
```

No backend files. No new directories.

### 4.2 Database Schema
Not applicable — no persistence beyond client `localStorage`.

### 4.3 Alembic Migration
Not applicable.

### 4.4 Pydantic Models
Not applicable.

### 4.5 API Endpoints
Not applicable.

### 4.6 React Components

| Component | Path | Props | State | Description |
|-----------|------|-------|-------|-------------|
| `ThemeToggleIcon` | `atoms/ThemeToggleIcon.tsx` | `{ theme: "dark" \| "light" }` | none | Renders `Sun` (when current is `dark`, hinting "switch to light") or `Moon` (when current is `light`). Pure presentational. |
| `ThemeToggle` | `molecules/ThemeToggle.tsx` | none | uses `useTheme()` | Button (`role="switch"`, `aria-checked`) that flips theme and persists. Keyboard-activatable (`Space`, `Enter`). Tooltip "Switch to light/dark mode". |
| `AppHeader` (modify) | `organisms/AppHeader.tsx` | unchanged | unchanged | Adds `<ThemeToggle />` in the trailing actions slot, before user menu. |

### 4.6.1 `useTheme` hook contract

```typescript
export type Theme = "dark" | "light";

export interface UseThemeReturn {
  theme: Theme;
  setTheme: (next: Theme) => void;
  toggle: () => void;
}

export function useTheme(): UseThemeReturn;
```

- Initial value: read from `localStorage["novum:theme"]`. If absent or invalid → `"dark"`.
- `setTheme` and `toggle` both:
  1. Write the new value to `localStorage["novum:theme"]` (wrapped in try/catch — see §9 R-02).
  2. Set `document.documentElement.dataset.theme = next`.
  3. Update React state so subscribers re-render.
- Listens to `storage` events to sync across tabs (`window.addEventListener("storage", ...)`).
- Does **not** subscribe to `prefers-color-scheme` (Out of Scope in V1, see §10).

### 4.6.2 `lib/theme.ts` helpers

```typescript
export const THEME_STORAGE_KEY = "novum:theme" as const;
export const DEFAULT_THEME: Theme = "dark";

export function readStoredTheme(): Theme;            // safe, returns DEFAULT_THEME on failure
export function writeStoredTheme(theme: Theme): void; // safe, swallows quota errors
export function applyThemeToDocument(theme: Theme): void;
```

### 4.7 UI Layout

```
┌──────────────────────────────────────────────────────────────┐
│  [Novum logo]    [page title]            [☀/☾] [User ▾]      │  ← header
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ... unchanged page content ...                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The toggle is a 32×32 px button matching the existing header action sizing. Icon swaps with a 200 ms cross-fade (`var(--ease-out)`). No layout shift on toggle.

### 4.8 CSS token strategy

Add a second block to `index.css` immediately after the existing `:root { ... }` Novum block:

```css
:root[data-theme="light"] {
  /* Surfaces — light slate, never pure white */
  --bg-primary:   #f8fafc;
  --bg-secondary: #f1f5f9;
  --bg-tertiary:  #e2e8f0;
  --bg-elevated:  #ffffff;

  --bg-gradient:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(99, 102, 241, 0.10), transparent 70%),
    radial-gradient(ellipse 60% 50% at 85% 100%, rgba(168, 85, 247, 0.06), transparent 70%),
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);

  --glass-bg:     rgba(15, 23, 42, 0.04);
  --glass-border: rgba(15, 23, 42, 0.10);
  --glass-hover:  rgba(15, 23, 42, 0.07);

  /* Accent kept; soft/glow adjusted for light backgrounds */
  --accent-soft:  rgba(99, 102, 241, 0.10);
  --accent-glow:  rgba(99, 102, 241, 0.20);

  --warm-soft:    rgba(251, 191, 36, 0.14);
  --warm-glow:    rgba(251, 191, 36, 0.20);

  --text-primary:   #0f172a;
  --text-secondary: #334155;
  --text-muted:     #64748b;
  --text-disabled:  #94a3b8;

  /* Semantic colors stay identical — they already meet AA on both backgrounds */

  --overlay-scrim: rgba(15, 23, 42, 0.35);

  --shadow-sm:   0 1px 2px rgba(15, 23, 42, 0.08);
  --shadow-md:   0 4px 12px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-lg:   0 12px 32px rgba(15, 23, 42, 0.12), 0 4px 8px rgba(15, 23, 42, 0.06);
}
```

The existing `.dark { ... }` block (shadcn/ui legacy tokens, lines ~102–120 of `index.css`) keeps its current role for shadcn primitives. To re-use Tailwind's `dark:` modifier with `data-theme`, configure Tailwind v4 in `index.css` with:

```css
@variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));
```

This lets existing `dark:bg-...` utilities (e.g. in `Toaster.tsx`) keep working under the new theming scheme without rewriting them all in one shot. Migration to pure tokens is deferred (§10).

### 4.9 Boot script (FOUC guard)

Add to `index.html` `<head>` **before** the Vite module script:

```html
<script>
  (function () {
    try {
      var t = localStorage.getItem("novum:theme");
      if (t !== "light" && t !== "dark") t = "dark";
      document.documentElement.dataset.theme = t;
    } catch (_) {
      document.documentElement.dataset.theme = "dark";
    }
  })();
</script>
```

Synchronous, < 1 KB, no dependencies. Runs before React mounts.

---

## 5. Acceptance Criteria

### AC-01: Default theme is dark for new users

```gherkin
Given a user opens the app for the first time
  And localStorage does not contain "novum:theme"
When the page finishes loading
Then document.documentElement.dataset.theme is "dark"
  And the ThemeToggle button shows the Sun icon
  And no flash of a light-themed surface is visible at any point
```

### AC-02: Toggling persists and applies immediately

```gherkin
Given the current theme is "dark"
When the user clicks the ThemeToggle
Then document.documentElement.dataset.theme becomes "light"
  And localStorage["novum:theme"] is "light"
  And the page background uses var(--bg-primary) light value within one animation frame
  And the ThemeToggle's aria-checked attribute reflects the new state
```

### AC-03: Choice survives reload

```gherkin
Given the user selected "light" in a previous session
When the user reloads the page
Then the page renders in light mode on first paint
  And no flash of dark surface is visible
```

### AC-04: Both themes meet WCAG 2.1 AA contrast

```gherkin
Given the LandingPage, RunPage, and HistoryPage are rendered
When jest-axe runs against the DOM in dark mode
Then no contrast violations are reported
When the theme is switched to light mode and jest-axe runs again
Then no contrast violations are reported
```

### AC-05: Cross-tab synchronization

```gherkin
Given the app is open in two browser tabs both in "dark" mode
When the user toggles to "light" in tab A
Then tab B updates to "light" within 100 ms
  And no data refetch is triggered in tab B
```

### AC-06: Storage failure does not break the app

```gherkin
Given localStorage.setItem throws QuotaExceededError
When the user clicks the ThemeToggle
Then the theme still changes visually within the current tab
  And no uncaught exception reaches the React error boundary
  And on next reload the theme falls back to the default "dark"
```

### AC-07: Keyboard accessibility

```gherkin
Given the ThemeToggle is focused via Tab navigation
When the user presses Space or Enter
Then the theme toggles
  And focus remains on the button
  And a visible focus ring is rendered using --accent
```

---

## 6. Implementation Checklist

- [ ] CSS tokens — extend `frontend/src/index.css` with `:root[data-theme="light"]` block and `@variant dark (...)` directive
- [ ] Boot script — inject FOUC guard into `frontend/index.html`
- [ ] Theme helpers — `frontend/src/lib/theme.ts` + tests
- [ ] `useTheme` hook — `frontend/src/hooks/useTheme.ts` + tests
- [ ] `ThemeToggleIcon` atom — `frontend/src/components/atoms/ThemeToggleIcon.tsx` + tests
- [ ] `ThemeToggle` molecule — `frontend/src/components/molecules/ThemeToggle.tsx` + tests (a11y via jest-axe)
- [ ] Mount in header — modify `frontend/src/components/organisms/AppHeader.tsx`
- [ ] Toaster audit — verify the existing `dark:` utilities behave correctly under the new `@variant dark` rule (one regression test added to `Toaster.test.tsx`)
- [ ] Visual smoke — render LandingPage / RunPage / HistoryPage in both themes; capture screenshots manually for review
- [ ] No backend changes — confirm `git diff backend/` is empty

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (FE) | Vitest | `lib/theme.ts`, `hooks/useTheme.ts` | ≥ 90% (pure logic) |
| Component (FE) | Vitest + Testing Library | `ThemeToggle`, `ThemeToggleIcon` | ≥ 80% |
| Accessibility (FE) | jest-axe | LandingPage, RunPage, HistoryPage in **both themes** | Zero violations |
| Cross-tab | Vitest (mock `storage` event) | `useTheme` | Sync within 100 ms |
| Unit (BE) | — | — | N/A (no backend changes) |
| E2E | Playwright | — | Deferred to V2 |

Coverage gate per copilot-instructions §7.7: ≥ 80%.

## 8. Environment Variables

None. The feature has no backend, no build-time configuration, no runtime flag.

## 9. Risks & Mitigations

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-01 | Hardcoded colors in existing components (e.g. `Toaster.tsx`, `GlassSurface`) render incorrectly in light mode | Medium | High | Audit step in checklist; `@variant dark (...)` lets `dark:` utilities keep working as a bridge; visual smoke before merge. |
| R-02 | `localStorage` unavailable (private mode, Safari ITP, quota) | Low | Low | All storage access wrapped in `try/catch`; fallback to in-memory state + `DEFAULT_THEME`. Covered by AC-06. |
| R-03 | FOUC on slow connections if boot script is deferred | Medium | Low | Boot script is **inline and synchronous** in `<head>`, before any `<script type="module">`. Covered by AC-01/AC-03. |
| R-04 | Glass surfaces (`--glass-*`) look poor on light backgrounds at the same opacity | Medium | Medium | Light-mode `--glass-bg` uses dark slate at low opacity instead of light slate — verified visually before merge. |
| R-05 | shadcn/ui `.dark` legacy block conflicts with new `data-theme` mechanism | Low | Medium | Both can coexist: `.dark` class is no longer applied; shadcn primitives that depend on it must be migrated or have their tokens duplicated under `data-theme="dark"`. Audited per component on touch. |

## 10. Out of Scope (V1)

- **"System" / auto mode** following `prefers-color-scheme` — deferred. V1 ships only explicit `dark` / `light` with `dark` default.
- **Per-page or per-user server-side theme persistence** — V1 is client-only. No `users.theme` column, no API.
- **High-contrast or color-blind modes** — separate concern (a future BRD-XX on accessibility themes).
- **Animated theme transition** beyond the icon cross-fade (e.g. View Transitions API) — deferred to avoid scope creep.
- **Bulk migration of every `dark:` utility to CSS tokens** — opportunistic, on-touch only. The `@variant dark` bridge keeps the codebase working in the meantime.
- **Theming the marketing site / external docs** — out of frontend SPA scope.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-29 | BSA Agent | Initial draft |
