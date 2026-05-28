# UI Design — Novum (Slate Aurora)

> ## Status: **MANDATORY · binding for every screen, every component, every PR**
>
> This document is the **single source of truth** for the visual identity of Novum. Every page — public, authenticated, modal, embedded — MUST implement the patterns defined here. The look-and-feel introduced on the public landing (`HowWeWorkPage` at `/`) is **not** marketing decoration: it is the canonical Slate Aurora language. Any prior visual decision, screenshot, sketch, or section in `ui-prototype.md` that contradicts this file is **superseded by this document**.
>
> **Non-negotiable rules** (reviewers MUST reject PRs that break any of these):
>
> 1. **Background** — every full-viewport surface renders the fixed `--bg-gradient` (§2.2) PLUS the animated `BackgroundOrbs` layer (§2.9). No solid `bg-black`, no flat `bg-(--bg-primary)` on full pages. Embedded panels inside `AppShell` may skip the orbs (the shell already paints them once for the viewport), but they MUST stay translucent so the gradient bleeds through.
> 2. **Surfaces** — every container that lifts off the gradient is glass (§6.6). Solid fills on interactive surfaces are forbidden.
> 3. **Buttons** — only the four variants in §6.1. The exact HowWeWork CTA recipes in §6.1.1 are the canonical primary/secondary patterns; the `Button` atom MUST emit them verbatim.
> 4. **Headline highlight** — the indigo → fuchsia → amber gradient text (§6.8) is reserved for the single hero phrase of a page and the confirmed-answer headline. Nowhere else.
> 5. **Scroll-reveal** — content blocks below the fold animate in via the `fadeUp + stagger` preset (§5.3). No custom one-off entrances.
> 6. **Tokens only** — components reference colors, shadows, radii and easings via `var(--token)` or `(--token)` Tailwind v4 syntax. Hardcoded hex / rgb values, `bg-gray-*`, `bg-slate-*`, `bg-black`, and inline shadows that don't map to a token are banned.
> 7. **Motion budget** — 100–300 ms except: orb drift (10–20 s loop), confirmed-answer warm pulse (one-shot 600 ms), `RunningIndicator` (loop). Everything else stays inside the budget.
> 8. **Reduced motion** — every animation defined here has a `prefers-reduced-motion` fallback (§5.2). No exceptions.
>
> Conflicts: **this file wins** over `ui-prototype.md` for anything visual. `ui-prototype.md` keeps ownership of layout (§2), panel states (§3), routes (§4), microcopy (§7), atomic-design architecture (§8), technical decisions (§9) — but if a §3 state description specifies a style that contradicts `ui-design.md`, the style here is canonical.

Reading order: §1 (philosophy) → §2 (color system) → §3 (typography) → §4 (depth and elevation) → §5 (motion) → §6 (interactive treatments) → §7 (accessibility floor) → §8 (do / don't) → §11 (pattern lock-in).

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
| **Glass is the standard surface** | Every container that rises off the gradient — panels, modals, cards, rows, chips, badges and **buttons** — uses one of the four glass utilities (§6.7). Solid `bg-*` fills are forbidden for new components; the gradient must remain visible through the chrome. |

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

### 2.9 Animated background orbs (`BackgroundOrbs`) — **MANDATORY page-level layer**

The fixed `--bg-gradient` (§2.2) is the *base*; the live aesthetic only emerges when the **animated orbs layer** sits above it. This layer is the visual signature of Novum and is **required on every full-viewport route** (public landing, `/run`, `/runs/:id`, `/diff/...`, error pages). The `AppShell` template renders it once for authenticated pages; standalone pages (like `HowWeWorkPage`) include the `BackgroundOrbs` atom directly.

**Composition** (three orbs, fixed-positioned, `pointer-events-none`, `z-0`):

| Orb | Color (rgba) | Approx position | Approx size | Animation |
|---|---|---|---|---|
| Indigo (primary) | `rgba(99,102,241,0.28)` | top-center, slightly above viewport | 640 × 640 px | `y: [0, 18, 0]` over 14 s, `easeInOut`, infinite |
| Violet (secondary) | `rgba(168,85,247,0.18)` | upper-right, slightly off-screen | 420 × 420 px | `y: [0, -22, 0]` over 18 s, `easeInOut`, infinite |
| Amber (trust) | `rgba(251,191,36,0.10)` | bottom-left | 380 × 380 px | `y: [0, 14, 0]` over 16 s, `easeInOut`, infinite |

**Rendering rules:**

- Each orb is a `motion.div` with `radial-gradient(closest-side, <rgba>, transparent 70%)` and `filter: blur(20–28px)`.
- All three orbs are wrapped in a single `aria-hidden` container with `pointer-events-none fixed inset-0 z-0 overflow-hidden`.
- Animations honor `useReducedMotion()` — when true, omit the `animate` prop entirely (orbs remain visible but static).
- The amber orb's opacity may NOT be raised above 0.10. Amber is reserved for trust signals (§2.5); the background hint is intentionally subtle.

**Canonical implementation:** the `BackgroundOrbs` atom lives in `frontend/src/components/atoms/BackgroundOrbs.tsx` (extracted from `HowWeWorkPage`). Every page-level component imports and renders it at the top of its tree, right before the foreground `z-10` content.

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

### 5.3 Scroll-reveal preset (`fadeUp` + `stagger`) — **MANDATORY for any content below the fold**

Any section that enters the viewport on scroll (cards grid, feature row, anatomy diagram, closing CTA) MUST animate in via this exact pair of variants. No custom one-off entrances.

```ts
import { type Variants } from "motion/react";

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] },
  }),
};

export const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};
```

**Usage contract:**

- The section wrapper uses `initial="hidden"`, `whileInView="visible"`, `viewport={{ once: true, amount: 0.2 }}`, `variants={stagger}`.
- Each child uses `variants={fadeUp}` and an optional `custom={i}` (its index) for the staggered delay.
- The hero section is the only exception: it uses `animate="visible"` (immediate) instead of `whileInView` because it's always above the fold.
- Easing `[0.16, 1, 0.3, 1]` is `--ease-out` — never substitute.
- Reduced motion: `motion/react` handles the override automatically when `useReducedMotion()` is respected at the page root; no per-section guard required.

**Canonical exports:** `frontend/src/lib/motion.ts` exports `fadeUp` and `stagger`. Every page-level and section-level component imports from there.

---

## 6. Interactive treatments

### 6.1 Buttons (atoms/Button.tsx) — **all variants are glass**

Buttons share the same chrome as every other lifted surface: a translucent fill, a 20 px backdrop blur and a 1 px tinted border (§6.7). Hierarchy comes from the **tint**, not from chrome. The body gradient remains partially visible through every button — that visual continuity is the whole point of the rule.

| Variant | Glass utility | Tint | Text | Hover | Press |
|---|---|---|---|---|---|
| `primary` | `glass-primary` | `--accent` @ 80% | `white` | `bg → --accent-hover` + `--shadow-glow` | `scale(0.97)` |
| `secondary` | `glass` | neutral slate @ 6% | `--text-primary` | `bg → --glass-hover` | `scale(0.98)` |
| `ghost` | *(none — transparent)* | — | `--text-primary` | acquires `glass-subtle` on hover (`blur(12px) saturate(150%)` + `bg --glass-bg`) | `scale(0.98)` |
| `danger` | `glass-danger` | `--semantic-danger` @ 22% | `--text-primary` | `bg → --semantic-danger @ 32%` + red glow | `scale(0.97)` |

All buttons share:
- `transition: background-color 150ms, transform 150ms, box-shadow 200ms var(--ease-out)`.
- Focus ring: `outline: 2px solid var(--accent); outline-offset: 2px`.
- Loading spinner replaces icon, never resizes the button.
- Solid (non-glass) button fills are forbidden — if a future variant needs a solid CTA, it must still keep the backdrop blur and the 1 px tinted border.

### 6.1.1 Canonical CTA recipes — **the only allowed primary/secondary patterns**

The `Button` atom (`atoms/Button.tsx`) MUST emit the exact Tailwind v4 token-bound classes below, lifted verbatim from the `HowWeWorkPage` hero (which is now the reference implementation). Pages and organisms render `<Button variant="primary">` / `<Button variant="secondary">` — they do NOT recreate these classes inline.

**Primary CTA** (every `Start research`, `Open Novum`, `Continue`, `Resume`, `Fork`):

```tsx
className={cn(
  "group inline-flex items-center gap-2 rounded-xl",
  "bg-(--accent) px-5 py-2.5 text-sm font-medium text-white",
  "shadow-(--shadow-glow)",
  "transition-transform duration-200 ease-out",
  "hover:bg-(--accent-hover) hover:-translate-y-0.5",
  "hover:shadow-[0_12px_28px_var(--accent-glow)]",
  "active:translate-y-0 active:scale-[0.98]",
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--accent) focus-visible:outline-offset-2",
)}
```

**Secondary CTA** (every `Compare strategies`, `See public runs`, `Cancel`, `Continue as guest`):

```tsx
className={cn(
  "inline-flex items-center gap-2 rounded-xl",
  "border border-(--glass-border) bg-(--glass-bg) backdrop-blur-xl",
  "px-5 py-2.5 text-sm text-(--text-secondary)",
  "transition-colors duration-150 ease-out",
  "hover:bg-(--glass-hover) hover:text-(--text-primary)",
  "active:scale-[0.98]",
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--accent) focus-visible:outline-offset-2",
)}
```

**Mandatory tokens** (do NOT substitute):

| Property | Token |
|---|---|
| Radius | `rounded-xl` (= `--radius-lg`, 16 px) |
| Padding | `px-5 py-2.5` |
| Font | `text-sm font-medium` (primary), `text-sm` (secondary) |
| Hover lift | `-translate-y-0.5` (primary only) |
| Press | `active:scale-[0.98]` |
| Glow on hover | `shadow-[0_12px_28px_var(--accent-glow)]` |

Compact / icon-only variants (e.g. row actions in `RunFeed`) keep the same color/shadow tokens but may use `rounded-lg` + `px-3 py-1.5`. They MUST still pass through the `Button` atom.

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

### 6.6 Glass utility hierarchy — **the standard**

Five glass utilities live in [`frontend/src/index.css`](../../frontend/src/index.css) and the `<GlassSurface>` atom in [`frontend/src/components/atoms/GlassSurface.tsx`](../../frontend/src/components/atoms/GlassSurface.tsx) wraps the three neutral ones (`glass-subtle`, `glass`, `glass-strong`) with elevation + radius props.

| Utility | When to use | Blur / saturate | Background | Border |
|---|---|---|---|---|
| `glass-subtle` | Chips, badges, inline pills, secondary sections inside a card | 12 px / 150% | `--glass-bg` @ 50% | `--glass-border` @ 60% |
| `glass` | Default — panels, cards, rows, secondary buttons | 20 px / 180% | `--glass-bg` | `--glass-border` |
| `glass-strong` | Modals and dialogs that must read against the scrim | 28 px / 200% | `--bg-elevated` @ 85% | `--glass-border` @ 220% + inset highlight + outer shadow |
| `glass-primary` | Primary buttons and CTA surfaces | 20 px / 180% | `--accent` @ 80% | `--accent` @ 50% |
| `glass-danger` | Destructive buttons | 20 px / 180% | `--semantic-danger` @ 22% | `--semantic-danger` @ 55% |

**Rules** (enforced in review):

1. **Prefer `<GlassSurface>`** for any element that wraps content (panels, modals, cards). Use raw utilities only when adding a wrapper component would be overkill (chips, pills, inline labels, buttons).
2. **Glass only works over varied content.** The body gradient counts; a flat panel background does not. Never apply a glass utility on top of another solid color — the blur becomes invisible.
3. **Never stack two glass utilities** on the same element. Pick one.
4. **Borders are always glass-tinted** (`--glass-border` or `--*-soft`), never opaque slate or hex.
5. **Solid fills on interactive surfaces are forbidden.** Buttons, rows and chips must be glass. Static text and timestamps may sit directly on the gradient.

### 6.7 Scrollbar (global)

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

### 6.8 Headline gradient text — **reserved highlight**

The indigo → fuchsia → amber gradient is the **single most recognizable visual asset of Novum**. It is reserved for exactly two uses; anywhere else it is forbidden.

**Allowed locations** (whitelist):

1. The single highlighted phrase inside the **hero `<h1>`** of a page (e.g. *"…knows **when to stop**."* on `/`).
2. The **headline confidence value** on the confirmed-answer card (C6, `judge_confirmed`).

**Canonical class:**

```tsx
className="bg-linear-to-r from-(--accent) via-fuchsia-400 to-(--warm) bg-clip-text text-transparent"
```

**Rules:**

- Maximum **one occurrence per viewport**. Two gradient phrases on the same screen dilute the brand.
- Apply only to inline text (a `<span>` inside an `<h1>` / `<h2>` / large numeric). Never to whole paragraphs, never to body copy, never to buttons.
- `fuchsia-400` is the only Tailwind named color allowed in production CSS — it sits between `--accent` (indigo) and `--warm` (amber) on the spectrum and has no token because it is exclusively a gradient stop.
- Reduced motion does not affect gradient text (it's static).

### 6.9 Pill chip and link badge

Small, glass-backed pills are the canonical pattern for: section eyebrows (e.g. *"How Novum thinks"* in the hero), top-bar secondary links (e.g. *"Open Novum"*), and metadata chips (relative time, source count). They share one recipe with two size variants.

**Eyebrow / link variant** (default):

```tsx
className={cn(
  "inline-flex items-center gap-2 rounded-full",
  "border border-(--glass-border) bg-(--glass-bg) backdrop-blur",
  "px-3 py-1 text-xs text-(--text-secondary)",
  "transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)",
)}
```

**Compact metadata variant** (`RunRow` timestamps, source counters):

```tsx
className={cn(
  "inline-flex items-center gap-1 rounded-md",
  "bg-(--accent-soft) px-2 py-0.5 text-[11px] font-medium text-(--accent)",
)}
```

Semantic variants (`StopReasonBadge`, success/warning/danger chips) swap `--accent-soft` / `--accent` for the matching `--semantic-*-soft` / `--semantic-*` pair. Borders remain glass-tinted, never opaque.

### 6.10 Top bar / sticky header

Every full-width header (public nav, `AppShell` TopBar, modal headers wider than 480 px) follows the same glass-strong recipe:

```tsx
className={cn(
  "relative z-20 border-b border-(--glass-border)",
  "bg-(--bg-secondary)/60 backdrop-blur-xl",
)}
```

**Rules:**

- `bg-(--bg-secondary)/60` is the canonical opacity — 60 % so the gradient still bleeds through.
- Height: `h-14` (56 px) on desktop, `h-12` on mobile.
- Inner content uses the same max-width as the page body (`max-w-6xl` for marketing, `w-full` for shell).
- Only the primary brand link and a single secondary action (pill badge — §6.9) live in the top bar. No tertiary clutter.

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

---

## 11. Pattern lock-in (irreplaceable patterns)

The following patterns are **not negotiable**. They identify Novum visually and may not be removed, renamed, replaced with a "cleaner alternative", or A/B-tested away. A reviewer MUST block any PR that touches them without an accompanying documented exception agreed in `decisions-history.md`.

| # | Pattern | Canonical source | Where it MUST appear | Forbidden alternatives |
|---|---|---|---|---|
| 1 | **Animated background orbs** (indigo + violet + amber, drifting) | §2.9, `atoms/BackgroundOrbs.tsx`, `HowWeWorkPage` lines 84–117 | Every full-viewport route; `AppShell` paints it once for authenticated shell pages | Solid `bg-(--bg-primary)`, static gradient only, CSS-only `@keyframes`, removing the amber orb, raising amber opacity > 0.10 |
| 2 | **Fixed `--bg-gradient` on `<body>`** | §2.2 | `index.css` `body` rule, no override allowed | `background-attachment: scroll`, swapping the linear base, adding a third orb to the gradient |
| 3 | **Glass surface system** (5 utilities, §6.6) | §6.6, `index.css` `.glass*` rules, `atoms/GlassSurface.tsx` | Every panel, modal, card, row, chip, badge, button | Solid `bg-(--bg-tertiary)` cards, `bg-white/5` ad-hoc, double-stacked glass |
| 4 | **Canonical button recipes** | §6.1.1 | The `Button` atom — every CTA in the app | Inline reinventions, `bg-indigo-500`, `hover:bg-indigo-600`, custom shadows not derived from `--shadow-glow`/`--accent-glow` |
| 5 | **Headline gradient text** (`from-(--accent) via-fuchsia-400 to-(--warm)`) | §6.8 | Hero `<h1>` highlight on `/` and `/how-we-work`; confirmed-answer confidence value | Applying to body copy, buttons, or more than one phrase per viewport |
| 6 | **Pill chip / link badge** | §6.9 | Section eyebrows, top-bar secondary links, metadata chips | Square chips with hard borders, opaque slate fills, `bg-gray-*` |
| 7 | **Top-bar glass header** (`bg-(--bg-secondary)/60 backdrop-blur-xl`) | §6.10 | `AppShell` TopBar, public nav, wide modal headers | Solid backgrounds, removing `backdrop-blur-xl`, opacity > 80 % |
| 8 | **`fadeUp + stagger` scroll-reveal** | §5.3, `lib/motion.ts` | Every section below the fold | Custom `whileInView` variants, opacity-only fades, `y` distances other than 24 px, durations other than 0.55 s |
| 9 | **Lucide-only iconography, `strokeWidth={1.5}`** | `ui-prototype.md` §1.9.2 | Every non-brand icon | Heroicons, Phosphor, custom SVGs (except the brand `Logo` atom) |
| 10 | **Warm amber for trust signals only** | §2.5 | Confirmed-answer card, headline confidence, `judge_confirmed` badge | Amber on running spinners, hover states, generic success toasts |
| 11 | **Slate Aurora token names** (`--accent`, `--warm`, `--glass-*`, `--shadow-glow`, `--ease-out`, …) | §2, §4, §5.1 | All component styles | Renaming, aliasing, hardcoding the resolved values |
| 12 | **Reduced-motion fallbacks** | §5.2 | Every motion preset, including the orbs | Animations without a `useReducedMotion()` guard |

### 11.1 How to add a new pattern

If a new screen needs a treatment not covered here, the procedure is:

1. Open a PR that **adds the pattern as a new row in this table** AND ships a reference implementation in an atom/molecule.
2. The PR description cites the RF and the user-visible behavior the pattern serves.
3. After merge, every subsequent screen MUST consume the new atom/molecule — no copy-paste reinventions.

The lock-in table is the contract. If a pattern is not in it, it does not exist. If it is in it, it cannot be replaced.

### 11.2 Override clause

Any prior text in this document, in `ui-prototype.md`, in component docstrings, or in `.github/memory-bank/**` that conflicts with §11 is **superseded by §11**. Reviewers must reject PRs whose code aligns with the older text. The mandatory preamble at the top of this file restates the same precedence rule.
