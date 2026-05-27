# UI Design — Novum (Slate Aurora)

> **Visual design language for Novum V1.** This document is the **single source of truth** for color, typography, depth, motion and interactive treatments. It supersedes the original §1.2–§1.6 of `ui-prototype.md` (which now references this file).
>
> `ui-prototype.md` keeps ownership of: layout (§2), panel states (§3), routes (§4), microcopy (§7), atomic-design architecture (§8), technical decisions (§9).
> `ui-design.md` (this file) owns: the **look and feel** that every component must implement.

Reading order: §1 (philosophy) → §2 (color system) → §3 (typography) → §4 (depth and elevation) → §5 (motion) → §6 (interactive treatments) → §7 (accessibility floor) → §8 (do / don't).

---

## 1. Design philosophy

The target is **L2 — UI with product intent**, refined toward a *Tailwind Labs × Linear × Raycast* dark aesthetic.

| Principle | What it means for Novum |
|---|---|
| **No black, only deep slate** | Pure black (`#000`) is the cheapest dark UI smell. Backgrounds are slate with a blue tint, layered with a fixed radial gradient so the surface feels alive. |
| **Depth through light, not borders** | Hierarchy comes from layered surfaces, soft shadows and subtle glow — not from hairline borders everywhere. Borders exist only on glass surfaces and at 8–12% opacity. |
| **Warm accent on cool base** | The base palette is cool (blue-slate). The accent (indigo) is vibrant, and a single **warm token** (amber) is reserved for highlighting trust-critical content (confirmed answers, key confidence values). |
| **Micro-interaction over animation** | Buttons lift 1 px on hover, gain a glow, scale 0.98 on press. No keyframe animation longer than 300 ms. Motion exists to confirm input, never to entertain. |
| **Generous whitespace** | Inherited from `ui-prototype.md` §1.2. Density reduced one notch vs the original spec to let the gradient and shadows breathe. |
| **The trace is the hero** | Every visual decision must keep the trace timeline (RF-13) legible and scannable. Chrome recedes; evidence stands out. |

> Inspiration sources: [refactoringui.com](https://refactoringui.com) (background gradient, type hierarchy), [linear.app](https://linear.app) (slate palette, micro-interactions), [vercel.com/geist](https://vercel.com/geist) (Inter typography), [Radix Colors](https://www.radix-ui.com/colors) (slate + indigo scales).

---

## 2. Color system

All colors live as CSS custom properties on `:root` in `frontend/src/index.css`. Components never hardcode hex.

### 2.1 Surfaces (backgrounds)

```css
--bg-primary:   #0b1120;   /* slate-950 with a blue tint — base canvas */
--bg-secondary: #111827;   /* slate-900 — secondary panels, history rows */
--bg-tertiary:  #1e293b;   /* slate-800 — input fields, inactive surfaces */
--bg-elevated:  #273449;   /* surface for cards lifted above the gradient */
```

### 2.2 Background gradient (the key change vs the old palette)

The `<body>` background is **never a solid color**. It is a fixed, attached layered gradient:

```css
--bg-gradient:
  radial-gradient(ellipse 80% 50% at 50% -10%, rgba(99, 102, 241, 0.18), transparent 70%),
  radial-gradient(ellipse 60% 50% at 85% 100%, rgba(168, 85, 247, 0.10), transparent 70%),
  linear-gradient(180deg, #0b1120 0%, #0a0f1c 100%);

body {
  background: var(--bg-gradient);
  background-attachment: fixed;
}
```

Two soft orbs (indigo at top-center, violet at bottom-right) create depth without distracting. The gradient is **fixed**, so scrolling does not move it.

### 2.3 Glass surfaces

```css
--glass-bg:     rgba(148, 163, 184, 0.06);   /* slate-400 @ 6% */
--glass-border: rgba(148, 163, 184, 0.12);
--glass-hover:  rgba(148, 163, 184, 0.10);
```

Applied to the three panels, modals, and cards lifted from the gradient. Always combined with `backdrop-filter: blur(20px) saturate(180%)`.

### 2.4 Accent — Indigo (primary action color)

```css
--accent:        #6366f1;   /* indigo-500 — primary CTAs, links, focus rings */
--accent-hover:  #818cf8;   /* indigo-400 — hover state */
--accent-soft:   rgba(99, 102, 241, 0.12);   /* tinted background fills */
--accent-glow:   rgba(99, 102, 241, 0.35);   /* shadow-glow on hover */
```

### 2.5 Warm secondary — Amber (trust highlight)

Reserved for **trust-critical UI** only: confirmed-answer header, headline confidence value, judge-confirmed stop badge. Using it elsewhere dilutes its meaning.

```css
--warm:        #fbbf24;   /* amber-400 */
--warm-soft:   rgba(251, 191, 36, 0.12);
--warm-glow:   rgba(251, 191, 36, 0.30);
```

### 2.6 Text

```css
--text-primary:   #f8fafc;   /* slate-50 — headings, primary body */
--text-secondary: #cbd5e1;   /* slate-300 — secondary body, labels */
--text-muted:     #64748b;   /* slate-500 — timestamps, metadata */
--text-disabled:  #475569;   /* slate-600 — disabled controls */
```

Replaces the old neutral-gray secondary (`#86868b`) which had identical hue to the background and zero perceived contrast.

### 2.7 Semantic (stop reasons — RF-02)

One color per stop_reason family. **Never free text.**

```css
--semantic-success: #10b981;   /* judge_confirmed */
--semantic-warning: #f59e0b;   /* honest_unanswerable, honest_contradiction,
                                  honest_ambiguous, stopped_by_budget */
--semantic-danger:  #ef4444;   /* errored */
--semantic-neutral: #64748b;   /* user_cancelled */
--semantic-error:   #ef4444;   /* inline form errors (alias of danger) */
```

### 2.8 Overlays

```css
--overlay-scrim: rgba(8, 12, 24, 0.65);   /* modal backdrop — tinted, not gray */
```

---

## 3. Typography

### 3.1 Font family

```css
font-family: "Inter", "DM Sans", system-ui, -apple-system, sans-serif;
font-feature-settings: "cv02", "cv03", "cv04", "cv11";   /* Inter stylistic sets */
-webkit-font-smoothing: antialiased;
```

- **Primary:** `Inter` (Google Fonts, variable, weights 300–700). Inter ships with stylistic sets that improve numerals and ambiguous glyphs (`I` vs `l`, `0`).
- **Fallback:** `DM Sans` (kept for graceful degradation).
- **Mono:** `JetBrains Mono` for event payloads, code blocks in answers, JSON viewer.

### 3.2 Type scale

| Use | Size / line-height | Weight | Tracking |
|---|---|---|---|
| Display (hero, run question) | 32 px / 1.15 | 600 | -0.02em |
| H1 | 24 px / 1.25 | 600 | -0.015em |
| H2 | 18 px / 1.35 | 500 | -0.01em |
| H3 / panel header | 15 px / 1.45 | 600 | -0.005em |
| Body | 15 px / 1.6 | 400 | 0 |
| Small / history row | 13 px / 1.5 | 400 | 0 |
| Caption / timestamp | 11 px / 1.4 | 500 | +0.02em (uppercase) |
| Mono (event payload) | 13 px / 1.55 | 400 | 0 |

Negative tracking on display/heading sizes (`-0.02em` to `-0.005em`) is the *refactoringui* signature for crisp dark headings.

### 3.3 Text on gradient

When text sits directly on `--bg-gradient` (no card), use `--text-primary` only. Secondary text always sits inside a glass surface — never directly on the gradient.

---

## 4. Depth and elevation

The old spec had a single shadow. The new system uses **three elevation levels** plus a **glow** for accents.

```css
--shadow-sm:    0 1px 2px rgba(0, 0, 0, 0.4);
--shadow-md:    0 4px 12px rgba(0, 0, 0, 0.35),
                0 1px 2px rgba(0, 0, 0, 0.2);
--shadow-lg:    0 12px 32px rgba(0, 0, 0, 0.5),
                0 4px 8px rgba(0, 0, 0, 0.3);
--shadow-glow:  0 0 0 1px var(--accent-soft),
                0 8px 24px var(--accent-glow);
--shadow-warm:  0 0 0 1px var(--warm-soft),
                0 8px 24px var(--warm-glow);
```

| Level | Used for |
|---|---|
| `--shadow-sm` | Pressed states, inline chips |
| `--shadow-md` | Default buttons, cards lifted from the gradient |
| `--shadow-lg` | Modals, popovers, the answer card on confirmed runs |
| `--shadow-glow` | Primary button hover, focused input, active selection |
| `--shadow-warm` | Confirmed-answer card highlight (used once per run) |

### 4.1 Radii

Unchanged from `ui-prototype.md` §1.3, restated here:

```css
--radius-sm: 8px;   /* chips, badges */
--radius-md: 12px;  /* buttons, inputs */
--radius-lg: 16px;  /* cards, history rows */
--radius-xl: 24px;  /* panels, modals */
```

---

## 5. Motion

All motion routes through `motion/react`. Durations strictly between **100 ms and 300 ms**, never above 400 ms. The full table from `ui-prototype.md` §1.6 still applies, with these refinements:

| Element | Old behavior | New behavior |
|---|---|---|
| Primary button hover | bg color change | bg color change + `translateY(-1px)` + `--shadow-glow` |
| Primary button press | `scale 0.97` | `translateY(0)` + `scale(0.98)` |
| Card / row hover | bg change only | bg change + `--shadow-md` rise |
| Send button micro-bounce | scale 1.05→0.95→1 | unchanged |
| Focused input | outline ring | `border-color: var(--accent)` + `--shadow-glow` |
| Modal enter | opacity + scale | unchanged |
| Confirmed-answer card mount | fade only | fade + `--shadow-warm` pulse over 600 ms (one-shot) |

### 5.1 Easing tokens

```css
--ease-out:    cubic-bezier(0.16, 1, 0.3, 1);   /* default for entrances and hovers */
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);  /* state transitions, modal */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* send button bounce only */
```

### 5.2 Reduced motion

`@media (prefers-reduced-motion: reduce)` collapses all durations to 0 and disables `translateY` micro-lifts. Glow shadows remain (static decoration only).

---

## 6. Interactive treatments

### 6.1 Buttons (atoms/Button.tsx)

| Variant | Background | Border | Hover | Press |
|---|---|---|---|---|
| `primary` | `linear-gradient(180deg, var(--accent-hover) 0%, var(--accent) 100%)` | — | `translateY(-1px)` + `--shadow-glow` | `translateY(0)` + `scale(0.98)` |
| `secondary` | `var(--glass-bg)` + `backdrop-blur(20px)` | `1px solid var(--glass-border)` | `var(--glass-hover)` + border opacity 0.20 | `scale(0.98)` |
| `ghost` | transparent | — | `var(--glass-bg)` | `scale(0.98)` |
| `danger` | `linear-gradient(180deg, #f87171, var(--semantic-danger))` | — | `--shadow-lg` (red tint) | `scale(0.98)` |
| `warm` *(new)* | `linear-gradient(180deg, #fcd34d, var(--warm))` | — | `--shadow-warm` | `scale(0.98)` |

All buttons share:
- `transition: background-color 150ms, transform 150ms, box-shadow 200ms var(--ease-out)`.
- Focus ring: `outline: 2px solid var(--accent); outline-offset: 2px`.
- Loading spinner replaces icon, never resizes the button.

### 6.2 Inputs

- Idle: `bg: var(--bg-tertiary)`, `border: 1px solid var(--glass-border)`.
- Hover: `border-color: rgba(148, 163, 184, 0.20)`.
- Focus: `border-color: var(--accent)` + `box-shadow: 0 0 0 3px var(--accent-soft)`.
- Error: `border-color: var(--semantic-error)` + `box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15)`.
- Placeholder: `color: var(--text-muted)`.

### 6.3 Cards and rows

- Default sits **on the gradient** with `--glass-bg` + `--glass-border` + `--shadow-md`.
- Hover (on interactive rows): `bg: var(--glass-hover)` + lift to `--shadow-lg`.
- Selected: `border-color: var(--accent)` + `--shadow-glow`.

### 6.4 Badges and chips

- Background: `--accent-soft` (or matching `--*-soft` for semantic variants).
- Text: full-saturation token (`--accent`, `--semantic-success`, …).
- Border: none.
- Radius: `--radius-sm`.

### 6.5 Modal

- Backdrop: `--overlay-scrim` (tinted slate, not gray) with `backdrop-filter: blur(8px)`.
- Surface: `--bg-elevated` + `--glass-border` + `--shadow-lg`.
- Radius: `--radius-xl`.

### 6.6 Scrollbar (global)

Updated to match the slate palette:

```css
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.15);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.25); }
```

---

## 7. Accessibility floor

Inherits everything from `ui-prototype.md` §1.8, with these additions:

- All glow effects (`--shadow-glow`, `--shadow-warm`) are **decorative only**. State is never communicated by glow alone — also by border-color, label, or icon.
- WCAG AA contrast verified for every text token against every surface token (`--text-primary` and `--text-secondary` clear AA against `--bg-primary`, `--bg-secondary`, `--bg-tertiary`, `--bg-elevated`, and the gradient).
- `prefers-reduced-motion` honored as in §5.2.
- Focus rings always use `--accent` against `--bg-primary` for guaranteed contrast (ratio > 4.5:1).

---

## 8. Do / don't

| Do | Don't |
|---|---|
| Use `--bg-gradient` on `<body>` only. | Apply the gradient to individual panels — it ruins the parallax-like depth. |
| Use `--warm` for confirmed answers and headline confidence only. | Use `--warm` on every success state — it loses meaning. |
| Layer surfaces with shadow, not borders. | Add 1 px borders to separate every section. |
| Use negative letter-spacing on display/heading sizes. | Use negative tracking on body text — it hurts readability. |
| Reference tokens via `var(--token)` or Tailwind arbitrary values (`bg-[var(--accent)]`). | Hardcode hex values anywhere in components. |
| Keep glow effects subtle (alpha ≤ 0.35). | Stack multiple glows on one element — it looks like a video game. |
| Use `Inter` with stylistic sets `cv02 cv03 cv04 cv11`. | Mix `Inter` with another sans-serif on the same page. |
| Honor `prefers-reduced-motion`. | Use any animation longer than 300 ms (except the one-shot 600 ms warm pulse on the confirmed-answer card). |

---

## 9. Implementation checklist (for the refactor)

When applying this design language to existing code:

1. Replace `:root` block in [`frontend/src/index.css`](../../frontend/src/index.css) with the tokens from §2, §3, §4.
2. Update `body` background to `var(--bg-gradient)` with `background-attachment: fixed`.
3. Refactor [`frontend/src/components/atoms/Button.tsx`](../../frontend/src/components/atoms/Button.tsx) per §6.1.
4. Refactor input atom(s) per §6.2.
5. Audit all components for hardcoded hex / `bg-black` / `bg-gray-*` Tailwind classes — replace with token-bound arbitrary values.
6. Verify the answer card and confidence value use `--warm` per §2.5 and §6.1.
7. Run `npm run test` to ensure no contrast or token-name regressions.
8. Take before/after screenshots of: home, run page (running), run page (confirmed), history, modal.

---

## 10. Relationship to other documents

- **Governs:** color, type, depth, motion and interactive treatments referenced throughout `ui-prototype.md` §3 (panel states), §7 (microcopy renders with these styles), §8 (atomic components implement these treatments).
- **Does NOT govern:** layout proportions, state machines, microcopy strings, atomic-design boundaries, technical decisions on data fetching — those remain in `ui-prototype.md`.
- **Supersedes:** `ui-prototype.md` §1.2 (aesthetic statement), §1.3 (color tokens), §1.4 (typography), §1.5 (visual effects), §1.6 (animation policy — additive refinements only), §1.7 (scrollbar). Those sections in `ui-prototype.md` now point here.
