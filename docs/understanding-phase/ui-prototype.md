# UI Prototype — Novum

> Companion to `requirement-understanding.md`. Defines the visual and interaction surface of the V1 build. Reading order: §1 (stack and aesthetic) → §2 (layout) → §3 (state inventory per panel) → §4 (routes) → §5 (RF coverage) → §6 (non-goals) → §7 (microcopy) → §8 (atomic-design architecture) → §9 (technical UI decisions) → §10 (defense).
>
> ## Binding precedence (READ FIRST)
>
> [`ui-design.md`](./ui-design.md) is the **MANDATORY** visual contract for every page, modal and component. The Slate Aurora language defined there — animated background orbs, glass surfaces, canonical button recipes, headline gradient text, `fadeUp + stagger` scroll-reveal, pill chips, top-bar glass header — is **non-negotiable** and applies to the **entire application**, not just the public landing.
>
> When a state description, layout sketch, microcopy block or atomic-design note in this file contradicts `ui-design.md`, **`ui-design.md` wins**. The §11 *Pattern lock-in* table in `ui-design.md` is the single source of truth for irreplaceable patterns; reviewers MUST reject PRs that diverge from it.
>
> This file owns: layout (§2), panel states (§3), routes (§4), microcopy (§7), atomic-design architecture (§8), technical decisions (§9). It does **not** own visual identity.

The build target is **L2 — UI with product intent**: layout, hierarchy and consistency cared for, but no design-system bloat, no dark-mode toggle to flip. Motion is restricted to the Slate Aurora budget (`ui-design.md` §5): micro-interactions confirm input, background orbs and gradient text reinforce the brand, and `fadeUp + stagger` reveals content as it enters the viewport. UI is treated as the surface of the trust contract — if a trace cannot be read, the system does not exist for the user.

---

## 1. Stack and design system

### 1.1 Technical stack

| Layer | Choice |
|---|---|
| Framework | React 19 + Vite |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS v4 (no `tailwind.config.js`, no PostCSS, plugin via `@tailwindcss/vite`) |
| Base components | shadcn/ui (Radix UI) |
| Animation | Motion (Framer Motion v12, `motion/react`) |
| Icons | Lucide React |
| Markdown | `react-markdown` + `react-syntax-highlighter` |
| Class utilities | `clsx` + `tailwind-merge` |
| State (client) | Zustand (lightweight, no Redux) |
| HTTP | Native `fetch` + a thin `lib/api.ts` wrapper |
| SSE | Native `EventSource` wrapped in `lib/sse.ts` |

### 1.2 Aesthetic — Slate Aurora (dark, premium, gradient-backed) — **MANDATORY**

> **The visual design language (colors, typography, depth, motion, interactive treatments) lives in [`ui-design.md`](./ui-design.md). That document is binding for every screen in the app — public, authenticated, modal, embedded.** This section is a summary; if it ever drifts from `ui-design.md`, the design file wins.

The Slate Aurora identity is composed of seven mandatory ingredients that MUST coexist on every full-viewport route:

1. **Fixed `--bg-gradient`** on `<body>` (indigo top-center + violet bottom-right + slate base) — never solid black, never plain slate.
2. **Animated `BackgroundOrbs`** layer (indigo + violet + amber, drifting on 14/18/16 s loops) — see `ui-design.md` §2.9. `AppShell` paints it once for authenticated pages; standalone pages render `<BackgroundOrbs />` directly.
3. **Glass surfaces** for every container that lifts off the gradient (panels, modals, cards, rows, chips, badges, buttons) — see `ui-design.md` §6.6. Solid fills on interactive surfaces are forbidden.
4. **Canonical button recipes** (§6.1.1) — the `Button` atom emits the verbatim CTA classes from `HowWeWorkPage`. Inline reinventions are blocked in review.
5. **Headline gradient text** (`from-(--accent) via-fuchsia-400 to-(--warm)`) — reserved for hero `<h1>` highlight and confirmed-answer confidence value.
6. **`fadeUp + stagger` scroll-reveal** for every section below the fold — see `ui-design.md` §5.3.
7. **Warm amber for trust signals only** (confirmed answers, headline confidence, `judge_confirmed` badge). No amber elsewhere.

Minimalist, refined, generous whitespace, clear typographic hierarchy, soft micro-interactions. **No** decorative illustrations.

> **Theme toggle (BRD-28, IP-28):** as of 2026-05-29 a user-controlled light/dark toggle ships in the global `AppShell` TopBar. Default is **`dark`** (Slate Aurora) — the seven mandatory ingredients above remain the canonical look and feel of the product. The light theme is a derived palette (see §1.2.1 below) intended for high-glare environments; it is opt-in and persisted in `localStorage["novum:theme"]`. No `prefers-color-scheme` auto-switch in V1.

### 1.2.1 Slate Aurora — Daylight variant (light theme)

When `<html data-theme="light">`, the following tokens override the defaults; all unlisted tokens (semantic, accent base, feed, radii, easing) are unchanged across themes. Verbatim values are owned by BRD-28 §4.8 — keep this table in sync if BRD-28 evolves.

| Token | Light value | Notes |
|---|---|---|
| `--bg-primary` | `#f8fafc` | Light slate, never pure white |
| `--bg-secondary` | `#f1f5f9` | |
| `--bg-tertiary` | `#e2e8f0` | |
| `--bg-elevated` | `#ffffff` | Modal / popover surface |
| `--bg-gradient` | indigo @10 % + violet @6 % + `linear-gradient(180deg, #f8fafc, #eef2f7)` | Same orb composition, washed for daylight |
| `--glass-bg` | `rgba(15, 23, 42, 0.04)` | Dark slate at low opacity — glass on light |
| `--glass-border` | `rgba(15, 23, 42, 0.10)` | |
| `--glass-hover` | `rgba(15, 23, 42, 0.07)` | |
| `--accent-soft` | `rgba(99, 102, 241, 0.10)` | Adjusted for light surfaces |
| `--accent-glow` | `rgba(99, 102, 241, 0.20)` | |
| `--warm-soft` | `rgba(251, 191, 36, 0.14)` | |
| `--warm-glow` | `rgba(251, 191, 36, 0.20)` | |
| `--text-primary` | `#0f172a` | |
| `--text-secondary` | `#334155` | |
| `--text-muted` | `#64748b` | |
| `--text-disabled` | `#94a3b8` | |
| `--overlay-scrim` | `rgba(15, 23, 42, 0.35)` | Modal backdrop |
| `--shadow-sm` / `-md` / `-lg` | Tinted with `rgba(15, 23, 42, ...)` instead of `rgba(0, 0, 0, ...)` | Softer on light surfaces |

The Tailwind v4 `dark:` modifier is bound to the same attribute via `@variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));` declared at the top of `index.css`, so existing `dark:*` utility classes (e.g. in `Toaster`, `UsernameModal`) continue to work without rewrites.

### 1.3 Color tokens — see [`ui-design.md` §2](./ui-design.md#2-color-system)

Authoritative tokens, gradient definition and semantic palette are defined in `ui-design.md` §2. Components **never** hardcode hex values — always reference tokens via `var(--token)` or Tailwind arbitrary-value syntax bound to the CSS variables.

Token families (full values in `ui-design.md` §2):

- `--bg-primary | --bg-secondary | --bg-tertiary | --bg-elevated` — slate surfaces
- `--bg-gradient` — fixed radial gradient applied to `<body>`
- `--glass-bg | --glass-border | --glass-hover` — glass surfaces
- `--accent | --accent-hover | --accent-soft | --accent-glow` — indigo (primary CTA)
- `--warm | --warm-soft | --warm-glow` — amber (trust highlight only)
- `--text-primary | --text-secondary | --text-muted | --text-disabled` — slate-tinted text
- `--semantic-success | --semantic-warning | --semantic-danger | --semantic-neutral | --semantic-error` — stop_reason palette (RF-02)
- `--overlay-scrim` — modal backdrop (tinted slate)
- `--radius-sm | --radius-md | --radius-lg | --radius-xl` — 8 / 12 / 16 / 24 px

### 1.4 Typography — see [`ui-design.md` §3](./ui-design.md#3-typography)

- **Primary:** `Inter` (variable, weights 300–700) with stylistic sets `cv02 cv03 cv04 cv11`. Fallback: `DM Sans`.
- **Mono:** `JetBrains Mono` for event payloads, code blocks in answers, and the JSON viewer.
- Type scale, line-heights and tracking values: `ui-design.md` §3.2.
- Negative letter-spacing on display/heading sizes for crisp dark headings.

### 1.5 Visual effects — see [`ui-design.md` §4 and §6](./ui-design.md#4-depth-and-elevation)

- **Glass is the standard surface treatment.** Every container that rises off the gradient — panels, modals, cards, rows, chips, badges **and buttons** — uses one of five glass utilities (`glass-subtle`, `glass`, `glass-strong`, `glass-primary`, `glass-danger`) backed by `backdrop-filter: blur(...) saturate(...)` over a translucent fill with a 1 px tinted border. The body gradient must remain visible through the chrome. Solid (non-glass) fills on interactive surfaces are forbidden. Full rules and selection guide: `ui-design.md` §6.6.
- The `<GlassSurface>` atom wraps the three neutral utilities (`glass-subtle | glass | glass-strong`) with `elevation` and `radius` props; prefer it for any wrapper component. Use raw utility classes only for in-place elements (chips, pills, inline buttons).
- **Three elevation shadows** + `--shadow-glow` (indigo) + `--shadow-warm` (amber, used once per confirmed run). Full definitions in `ui-design.md` §4.
- **No hard borders.** Always `var(--glass-border)` (or a tinted `--*-soft`) at 8–12% opacity.
- **`border-radius`** minimum 12 px on interactive elements; panels and modals use `--radius-xl` (24 px).

### 1.6 Animation policy (Motion) — see [`ui-design.md` §5](./ui-design.md#5-motion)

All animations route through `motion/react`. Durations strictly between **100 ms and 300 ms**, never above 400 ms (single exception: one-shot 600 ms warm pulse on the confirmed-answer card mount).

| Element | Animation | Duration |
|---|---|---|
| New event node in trace | `opacity 0→1`, `y 8→0`, `easeOut` | 200 ms |
| New row in history | same as above | 200 ms |
| Run-row hover | bg transition + lift to `--shadow-md` | 150 ms |
| Primary button hover | bg shift + `translateY(-1px)` + `--shadow-glow` | 150 ms |
| Primary button press | `translateY(0)` + `scale(0.98)` | 100 ms |
| Send button micro-bounce | `scale 1.05→0.95→1` (spring easing) | 80 ms |
| Modal enter | `opacity 0→1` + `scale 0.96→1` | 200 ms |
| `RunningIndicator` dots | CSS keyframes bounce, staggered 0 / 0.2 / 0.4 s | loop |
| Center panel state switch | crossfade 150 ms | — |
| Advanced controls reveal | `height auto` + fade | 200 ms |
| Stagger between sibling rows on initial load | 60 ms | — |
| Confirmed-answer card mount | fade + one-shot `--shadow-warm` pulse | 600 ms |

Easing tokens (`--ease-out`, `--ease-in-out`, `--ease-spring`) and `prefers-reduced-motion` handling: `ui-design.md` §5.1 and §5.2.

### 1.7 Custom scrollbar (global) — see [`ui-design.md` §6.6](./ui-design.md#6-interactive-treatments)

```css
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.15);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.25); }
```

### 1.8 Accessibility floor

- Focus ring: `outline: 2px solid var(--accent); outline-offset: 2px` on every focusable element.
- All interactive elements carry an `aria-label`.
- Trace container: `role="log"` + `aria-live="polite"`.
- WCAG AA contrast on all text against its background.
- Keyboard navigation works for: open new question form, submit form, expand/collapse event nodes, navigate history rows with arrow keys, close modals with `Esc`.

### 1.9 Iconography — brand mark and icon system

> **Binding rule.** Every new icon — brand or functional — MUST follow `.github/memory-bank/conventions/iconography.md`. That document is the single source of truth for icon decisions (when to add, where it lives, naming, color, size, stroke, family). This §1.9 summarizes the rules and the brand mark; the memory-bank file is the enforceable convention referenced in code review.

Iconography is part of the trust contract: every glyph must map either to the brand or to a documented behavior. There is no decorative iconography in V1.

#### 1.9.1 Brand mark — *"three dots resolving into a line"*

The Novum mark renders the Baconian premise of `Novum Organum` visually: **three discrete observations (dots) align until they earn a single continuous conclusion (a bar)**. It is the same visual language as `RunningIndicator` (§1.6) — the user reads the same idea in the logo, in the live indicator, and in the event timeline.

```
viewBox 32×32 (monochrome, currentColor)
●  ●  ●  ▬▬▬
6  12 18  22..30   (cx / x · y baseline = 16)
```

- **Files:** `frontend/public/logo-mark.svg` (mark only), `frontend/public/logo.svg` (mark + Inter wordmark, viewBox 140×32), `frontend/public/favicon.svg` (mark on `--bg-primary` rounded square).
- **Atom:** `Logo` (`components/atoms/Logo.tsx`) renders the mark inline so it inherits `currentColor` and respects token-based theming. Props: `size` (default 24), `withWordmark` (default false), `title` (default *"Novum"*; empty string marks it decorative).
- **Color rule:** monochrome, always `currentColor`. **Never** colored with `--accent` — the accent is reserved for user actions, not for the brand.
- **Placements:** favicon, `LoginModal` header (M1 / M1-deep), `MobileTopBar` center label (next to the *"Novum"* wordmark text per §7.10), and the empty-history Skeleton header at very large viewports (V2 only — not required for V1).
- **No animated logo in V1.** A one-shot 600 ms splash animation (dots appearing sequentially, then the bar materializing) is documented as V2.

#### 1.9.2 Functional icon system — Lucide React, single family

All non-brand icons come from **Lucide React** (already declared in §1.1). No other icon family is allowed — no Heroicons, no Phosphor, no inline ad-hoc SVGs (except the `Logo` atom, which is the brand exception).

| Rule | Value |
|---|---|
| Family | Lucide React, one consistent family across the entire UI |
| Stroke width | `strokeWidth={1.5}` (matches Inter 400 stem weight) |
| Allowed sizes | 14 · 16 · 20 · 24 px (no intermediate values) |
| Color | `currentColor` driven by parent text token; never hardcoded hex |
| Semantic color | Only on icons that already carry result semantics (`StatusIcon`, `StopReasonBadge`, `OutcomeBar`), via `--semantic-*` tokens |
| Accent color | **Never** on icons unless the icon is the affordance of a user action |
| Animation | None, except `RunningIndicator` (loop), `Spinner` (loop), and the V2 splash logo (one-shot) |
| Decoration | Forbidden. If an icon does not back an event, a state, or an action documented in §3 or §7, it does not ship |

The event-to-icon map is fixed in §3.3. Two notes:
- `JudgeRuled` uses `Gavel` for now. `Scale` (balance) is a documented Baconian alternative — pick one and stick with it; do not mix across the trace.
- Stop reasons map through `StopReasonBadge`, not through standalone icons; the badge owns the `--semantic-*` token application.

#### 1.9.3 Generic `Icon` wrapper (optional convenience)

A future `Icon` atom may wrap Lucide to enforce size and stroke contractually:

```tsx
<Icon name="Compass" size={20} />
```

This is **not required in V1** — direct Lucide imports (`<Compass size={20} strokeWidth={1.5} />`) are equivalent and one less indirection. When `Icon` is introduced, every Lucide call site migrates in a single pass.

#### 1.9.4 Asset checklist (V1)

- [x] `frontend/public/logo-mark.svg`
- [x] `frontend/public/logo.svg`
- [x] `frontend/public/favicon.svg` (referenced from `index.html`)
- [x] `frontend/src/components/atoms/Logo.tsx` (+ test)
- [ ] PNG raster fallbacks 192/512 px (deferred — PWA is V2)
- [ ] Apple touch icon 180 px (deferred — V2)

The full convention (when to add a new icon, where it lives, naming) is in `.github/memory-bank/conventions/iconography.md`.

---

## 2. Layout

Three fixed panels at desktop width, **responsively collapsing** at narrower viewports. The desktop arrangement is the canonical one; tablet and mobile are derivations of it.

```
┌──────────────────┬──────────────────────────────┬─────────────────┐
│ HistoryPanel     │       CenterPanel            │   TracePanel    │
│ width: 260 px    │       flex: 1                │   width: 360 px │
│ glass            │       (run / form / diff)    │   glass         │
│                  │                              │                 │
│ [+ New research] │  ┌────────────────────────┐  │  · EventNode    │
│                  │  │ RunHeader              │  │    [fork ↗]     │
│ [Mine][All pub.] │  ├────────────────────────┤  │  · EventNode    │
│ ────────────────│  │                        │  │  · EventNode    │
│ RunRow           │  │  body (state-driven)   │  │    └ payload    │
│ RunRow           │  │                        │  │  · EventNode    │
│ RunRow           │  │                        │  │                 │
│ ────────────────│  │                        │  │                 │
│ @giovanny        │  └────────────────────────┘  │                 │
│ [logout]         │                              │                 │
└──────────────────┴──────────────────────────────┴─────────────────┘
```

- Root container: `height: 100dvh; overflow: hidden`.
- Internal scroll only inside: the history list, the center body, the trace timeline.
- Panel borders: `border-left/right: 1px solid var(--glass-border)`.
- **Responsive in V1.** Three breakpoints with three layouts:

| Breakpoint | Range | Layout |
|---|---|---|
| `desktop` | ≥ 1024 px | 3 panels visible (canonical). History 260 px, Trace 360 px, Center fluid. |
| `tablet` | 768–1023 px | History collapses to a drawer (toggle via top-bar hamburger). Center + Trace stay side-by-side: Trace 320 px, Center fluid. |
| `mobile` | < 768 px | Single-panel: only Center is visible. History and Trace each open as full-height `Sheet` drawers from left and right (shadcn `Sheet`). A persistent top-bar exposes both toggles. |

- Layout decision is owned by `useViewport()` hook + `AppShell`. Components below the shell are **viewport-agnostic** — they render the same regardless of breakpoint. Only `AppShell` rearranges them.
- **TopBar identity slot.** The `AppShell` TopBar renders on every breakpoint and includes an `IdentitySlot` molecule (anchored to the top-right). It surfaces a verifying spinner, a `Sign in` button when anonymous, or the username pill + `Logout` button when authenticated. Wired in IP-11 iter 2.
- Detailed responsive strategy (touch targets, animation, drawer behavior, table scrolling) is specified in §9.16.

---

## 3. State inventory

The three-panel layout has three independent state machines (history, center, trace) plus a small set of global overlays. Each state below has a unique id used in component contracts and tests.

### 3.1 Left — `HistoryPanel`

| Id | State | Trigger | Render |
|---|---|---|---|
| **L1** | Loading | Initial app mount | 6 skeleton `RunRow`s, shimmer animation |
| **L2** | Empty · Mine | Logged-in user has no runs of their own, toggle = `Mine` | Centered text: *"You haven't started any research yet."* + CTA *"See public runs"* (flips toggle) |
| **L3** | Empty · All public | System has no runs at all (fresh demo) | *"No public runs yet. Be the first."* |
| **L4** | Populated | Any runs visible | Vertical list of `RunRow`s, newest first. Header shows `HistoryToggle` + **`Compare` button** that enters multi-select explicitly. |
| **L5** | Multi-select · 1 picked | First checkbox tick **or** `Compare` button clicked | Header changes to: *"Select one more to compare"* + cancel link |
| **L6** | Multi-select · 2 picked | Second checkbox tick | Header: *"Compare these two →"* — clicking activates **C12** (diff mode) and updates URL to `/diff/<a>/<b>` |
| **L7** | Paginated | Server returned `has_more = true` | *"Load more"* button at list bottom; no infinite scroll |

**Decisions applied:**
- Status icons in `RunRow` — **4 only**: `▶` running · `✓` done (any honest stop or `judge_confirmed`) · `⚠` errored · `⊘` cancelled. The `stop_reason` text next to the icon disambiguates honest vs judge variants.
- Multi-select **preserves selection across toggle switches** (`Mine` ↔ `All public`).
- Clicking a row anywhere outside its checkbox navigates to that run (not enters select mode).

**Row anatomy (left to right):**
```
[ ✓ ]  React vs Vue for a team of 5...      @giovanny    judge_confirmed   2h ago    ⑂ 3
 ☐ status_icon  question_truncated_60_chars  owner       stop_reason       relative  forks
```

- The checkbox `☐` slides in on row hover; persistent only while in multi-select mode.
- Active run (the one currently open in CenterPanel): bg `rgba(255,255,255,0.08)` + left border `2px solid var(--accent)`.

### 3.2 Center — `CenterPanel`

| Id | State | Trigger | Render |
|---|---|---|---|
| **C1** | Empty form | No run in URL | `QuestionForm` (question textarea + optional context + `Advanced ▸`) + `TypeDisclosure` panel below. **First-run users only** (no `Mine` runs): a `SuggestionChips` row appears between `TypeDisclosure` and the form with 3 example questions — click fills the textarea but does not submit. |
| **C2** | Empty form · Advanced expanded | Click on `Advanced ▸` | Same as C1 + format selector (Structured/Prose) + threshold selector (Low 0.4 / Standard 0.6 / High 0.85 / Custom) |
| **C3** | Submitting | After `Start research` click, before first SSE event | Form disabled, overlay spinner, button shows *"Starting…"*. **Cancel available.** |
| **C4** | Running · owner | SSE connected, events arriving, current user owns run | `RunHeader` with `RunningIndicator` + **`ProgressIndicator`** (*"Researching · N of M sub-claims covered"* + bar driven by `C_coverage`) + **Cancel** button + **`ShareLinkButton`**. Body: mini-feed (last 5 events as one-liners with relative time). |
| **C5** | Running · viewer | Same as C4 but current user does not own run | Same layout as C4, **no Cancel button**, header shows *"Watching live"*. `ShareLinkButton` available. |
| **C6** | Terminal · judge_confirmed | `Stopped(judge_confirmed)` | Top of panel: 4 px `OutcomeBar` in `--semantic-success`. Header: green `StopReasonBadge`, `ConfidenceMeter` compact pill, `ShareLinkButton`. Body: **`TrustSummary` block at the very top** (confidence vs threshold, source count, contradictions resolved/unresolved, elapsed time, event count, cost), then `AnswerRenderer` (prose or structured per `output_format`). |
| **C7** | Terminal · honest stop | `Stopped(honest_unanswerable | honest_contradiction | honest_ambiguous)` | `OutcomeBar` in `--semantic-warning`. Header: amber badge. Body: `TrustSummary` (adapted variant — see §3.2.4) + type-specific `HonestStopExplainer` (interpretations list / contradiction positions / out-of-scope rationale) + contextual fork CTA (see §3.2.1). |
| **C8** | Terminal · budget | `Stopped(stopped_by_budget)` | `OutcomeBar` in `--semantic-warning`. Header: amber badge. Body: `TrustSummary` + `AnswerRenderer` with strong caveat banner *"Stopped on budget — answer is best-effort."* + CTA *"Fork to continue searching"*. |
| **C9** | Terminal · cancelled | `Stopped(user_cancelled)` | `OutcomeBar` in `--semantic-neutral`. Header: neutral badge. Body: warm message (§7.6) + partial-state snapshot + **two CTAs side-by-side: `Resume` (owner only) and `Fork to retry`**. |
| **C10** | Terminal · errored | `AgentErrored` followed by `Stopped(errored)` | `OutcomeBar` in `--semantic-danger`. Header: red badge with failure reason. **Resume** button (owner only) + `Fork from last decision`. Body: `ErrorState` (state at last successful event). |
| **C11** | Reconnecting | SSE drops during C4/C5 | Banner over current body: *"Connection lost — reconnecting…"* with retry attempt count. Existing content stays interactable. |
| **C12** | Diff mode | L6 fires `compare` | Replaces C1–C10 entirely. Three tabs: `Timeline` (default) / `Evidence` / `Outcome`. Close button (`✕`) reverts URL and state. |
| **C13** | Not found | URL `/runs/<bad_id>` returns 404 | Centered: *"Run not found"* + link back to home. |

#### 3.2.0 Live Run Feed (IP-24)

**C3' — Live Run Feed states**: The center body in C4/C5/C6–C10 renders a `RunFeed` organism (Claude-style feed) that replaces the legacy `ResearchingBanner`. Three states:

| Sub-state | When | Render |
|---|---|---|
| **C3'-running** | `isComplete=false`, events streaming | Vertical feed with `FeedRail` (active tone), live-updating event cards (`SearchStepCard`, `PlanStepCard`, `JudgeVerdictCard`, generic `FeedStep`). `ToolCalled` groups consecutive `EvidenceAdded` / `SourceFailed` / `DeepFetchPerformed` with matching `target_claim_id` into one `SearchStepCard` with inline source rows (favicon + title + hostname). Last step marked active (spinner). Sticky-bottom autoscroll with `JumpToLatestPill` when user scrolls up. No collapse toggle. |
| **C3'-completed-collapsed** | `isComplete=true`, default post-run | Feed collapses behind a sticky header: *"Reasoning trace ({N} steps · {elapsed}s)"* + `CollapseToggleButton`. Toggle state persisted in `localStorage` key `novum_run_feed_collapsed` (default `true`). Click toggle → expands to C3'-completed-expanded. Renders above `TrustSummary` + answer in C6–C10. |
| **C3'-completed-expanded** | `isComplete=true`, user expanded | Full feed visible (same render as C3'-running but frozen, rail neutral tone, no active step). Collapse toggle at top. Renders above answer. |

**localStorage keys introduced (IP-24):**
- `novum_run_feed_collapsed` (string `"0"` / `"1"`, default `"1"` after completion)
- `novum_trace_panel_collapsed` (string `"0"` / `"1"`, default `"0"`)
- `novum_answered_runs` (JSON array of run IDs, capped at 500, tracks which runs have had answer animated)
- `novum_animate_answer` (string `"0"` / `"1"`, global toggle, default `"1"`)

**Answer animation (IP-24):** When `isComplete && hasAnswer && !hasAnswerBeenAnimated(runId) && isAnimateAnswerEnabled()`, the final answer animates in character-by-character via frontend-only `useTypewriter` hook. Adaptive speed: 60 cps (< 500 chars), 150 cps (500–1500), 250 cps (≥ 1500). Skip on click / Esc / Space / scroll / `document.hidden` / `prefers-reduced-motion`. `BlinkingCursor` appended while typing. No re-animate on replay.

#### 3.2.1 Contextual fork CTAs in C7

| Sub-reason | CTA text | Form pre-fill on fork |
|---|---|---|
| `honest_unanswerable` · `confidence_below_threshold` | *"Fork with lower threshold"* | Threshold selector pre-set one step down |
| `honest_unanswerable` · question type 6/7/8 (predictive/opinion/personal) | (no CTA — terminal by design) | — |
| `honest_unanswerable` · sources exhausted | *"Fork with refined question"* | Question textarea pre-filled and focused |
| `honest_ambiguous` | *"Fork with refined question"* | Question textarea pre-filled, detected interpretations shown as suggestion chips below the textarea |
| `honest_contradiction` | *"Fork to dig deeper"* | Question pre-filled, context pre-filled with *"Investigate this contradiction: [position A] vs [position B]."* |

#### 3.2.2 Running body — mini-feed (decision applied)

The center body in C4/C5 shows a **rolling mini-feed of the last 5 events**, each one-line: `[icon] [type] [one-line summary] [Δt]`. Examples:

- `🔎 ToolCalled · web_search("React vs Vue 2026 production teams") · 0.4s`
- `📄 EvidenceAdded · 3 chunks from stackoverflow.com · 1.2s`
- `🧭 PlanCreated · 4 sub-claims to cover · 0.8s`

The **full trace** lives in the right panel (T2). The mini-feed gives the user a sense of progress without forcing them to read the technical timeline.

#### 3.2.3 `ConfidenceMeter` in C6 (decision applied)

The header shows a compact pill: `confidence 0.87 / threshold 0.60 ✓`. Clicking it expands a small panel below the header (within CenterPanel, not in the trace) with four horizontal bars:

```
Final confidence       ████████░░  0.87
Structural score (S)   █████████░  0.91
  Claim coverage       ██████████  1.00
  Source agreement     ████████░░  0.85
  Source diversity     ███████░░░  0.75
  No-conflict          ██████████  1.00
Judge confidence (J)   ████████░░  0.87
```

The same data is also viewable by expanding the `JudgeRuled` event in the right-panel trace — that location is canonical (event payload is the source of truth), the meter is a convenience surface.

#### 3.2.4 `TrustSummary` block (decision applied)

A "nutrition label" of the run, rendered at the top of the body in **every terminal state** (C6–C10). The point: the user must know whether to trust the result **before reading the answer**.

Variant rendered per `stop_reason`:

```
[C6 · judge_confirmed]
┌──────────────────────────────────────────────────────┐
│  ✓ Judge confirmed · confidence 0.87 / threshold 0.60         │
│  7 sources cited · 4 sub-claims covered                        │
│  0 unresolved contradictions · 1 resolved                     │
│  42s · 23 events                                              │
└───────────────────────────────────────────────────────┘
```

```
[C7 · honest_contradiction]
┌──────────────────────────────────────────────────────┐
│  ⚠ Honest stop · sources disagree                              │
│  5 sources cited across 2 positions                           │
│  1 unresolved contradiction · 2 resolution attempts made      │
│  38s · 21 events                                              │
└───────────────────────────────────────────────────────┘
```

```
[C10 · errored]
┌──────────────────────────────────────────────────────┐
│  ⚠ Errored · provider rate_limit                                │
│  3 sources cited · 2/4 sub-claims covered when error hit       │
│  19s · 12 events                                              │
└───────────────────────────────────────────────────────┘
```

**Cost line** is included from V1 but starts as a coarse estimate (sum of LLM tokens × published rate). Source citations count = distinct sources in `EvidenceAdded` payloads. The data feeding `TrustSummary` is derived client-side from the event log — no extra back-end endpoint required.

#### 3.2.5 `OutcomeBar` (decision applied)

A 4 px high colored strip across the very top of `CenterPanel`, rendered only on terminal states (C6–C10). Color tokens map to `stop_reason` exactly like `StopReasonBadge`. The point is **pre-attentive recognition**: the reviewer's eye registers the outcome before parsing any text. Implementation is a single styled `Atom` (`OutcomeBar`).

### 3.3 Right — `TracePanel`

| Id | State | Trigger | Render |
|---|---|---|---|
| **T1a** | Empty · no run | C1/C2 active (no run loaded) | *"Trace will appear here when research starts."* in muted text |
| **T1b** | Awaiting events | Run started, `QuestionAsked` received but no `PlanCreated` yet | `PlanPreview` molecule shows a numbered list of what Novum will do next (classify → plan → search → evaluate → judge → answer-or-honest-stop) + first `EventNode` (`QuestionAsked`) at the bottom. Replaced by T2 as soon as more events arrive. |
| **T2** | Streaming | C4/C5 active, ≥2 events present | Vertical timeline of `EventNode`s, newest at bottom. Auto-scroll **sticky-when-at-bottom** (stops auto-scrolling if user manually scrolled up). New nodes animate in (see §1.6). |
| **T3** | Frozen (terminal) | C6–C10 active | Same timeline, no new events arriving. All `EventNode`s frozen; decision-events show `ForkButton`, mechanical events do not. |
| **T4** | Event expanded | Click on any `EventNode` | Node expands inline to show full payload via `EventPayloadViewer` (JSON, colorized, collapsible by key). Click again or anywhere outside collapses. |
| **T5** | Diff mode | C12 active | Two-column event diff (left run vs right run). Aligned by `step_index` where possible, gaps shown as faded markers. |
| **T1d** | Cost breakdown tab | User clicks the `TotalCostChip` in the run header **or** selects the "Cost" tab in the trace tab strip | `TraceCostPanel` organism: header with `$total` + token total + provider count; body with `CostBreakdownBar` (stacked bar per provider) and `CostBreakdownTable` (rows: provider · kind · model · calls · tokens · USD · % of total). Live-patched on every `CostIncurred` SSE frame via `useRunCosts(runId)`. Loading skeleton on first paint; error state with a retry button on REST failure. Empty state when the ledger has no entries yet. See RF-20 and [BRD-29](../implementation-phase/brds/BRD-29-cost-and-token-tracking.md). |

**Decisions applied:**
- **No filters in V1.** All events show. The expand/collapse mechanism manages visual density.
- **`JudgeRuled` always renders expanded by default.** Every other event renders compact by default. Rationale: judge is the trust-bearing event; everything else is supporting infrastructure.
- **Auto-scroll is sticky-when-at-bottom.** Reading historical events in T2 should not snap you to the latest.

**`EventNode` anatomy:**

Compact (default):
```
┌─────────────────────────────────────────────────────────┐
│ 🧭  PlanCreated · 4 sub-claims                  [fork↗] │
│     0.8s · step 2                                       │
└─────────────────────────────────────────────────────────┘
```

Expanded (after click):
```
┌─────────────────────────────────────────────────────────┐
│ 🧭  PlanCreated · 4 sub-claims                  [fork↗] │
│     0.8s · step 2                                       │
│ ─────────────────────────────────────────────────────── │
│ {                                                       │
│   "question_type": "comparative",                       │
│   "claims": [                                           │
│     "performance characteristics",                      │
│     "ecosystem maturity",                               │
│     "team learning curve",                              │
│     "production case studies"                           │
│   ],                                                    │
│   ...                                                   │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

Icon-by-event mapping (Lucide):

| Event | Icon |
|---|---|
| `QuestionAsked` | `MessageSquare` |
| `PlanCreated` | `Compass` |
| `ToolCalled` | `Search` |
| `EvidenceAdded` | `FileText` |
| `ClaimCovered` | `CheckCircle2` |
| `ContradictionDetected` | `AlertTriangle` |
| `AmbiguityDetected` | `HelpCircle` |
| `SourceFailed` | `XCircle` |
| `JudgeRuled` | `Gavel` |
| `UserContextChallenged` | `MessageSquareWarning` |
| `ContradictionResolved` | `ShieldCheck` |
| `AgentErrored` | `AlertOctagon` |
| `ResumedAfterError` | `RotateCw` |
| `ResumedAfterCancel` | `RotateCw` |
| `Stopped` | `Flag` |

### 3.4 Global modals and overlays

| Id | Modal | Trigger | Render |
|---|---|---|---|
| **M1** | Login | No valid token at app load **and** not on a deep-link route | Full-viewport modal, blocking. Single input (username), single button (*"Continue"*). Glass card on a darkened backdrop. |
| **M1-deep** | Login · non-blocking | No valid token **and** user landed on `/runs/<id>` or `/diff/<a>/<b>` | Same modal, **dismissible** (`✕`), with a *"Continue as guest"* button. Guest can read the run; the **Fork** button is disabled with tooltip *"Log in to fork this run."* |

**Decisions applied:**
- **No confirm modal on Cancel.** Direct action; the cancelled run is still forkable **and resumable by its owner** (see RF-08 / RF-11 update).
- **No confirm modal on Fork.** Fork navigates directly to a new form pre-filled with the parent's question / context / format / threshold (any of which the user can edit before clicking `Start research`). A banner at the top of the form reads *"Forking from run_<id> · step <n>."*
- **`ForkContextCard` accompanies the form on fork.** A collapsible card above the textareas shows the originating event's contents (the plan that was created, the judge's ruling, the contradiction positions, etc.) so the user knows what they are departing from. Default state: expanded for `JudgeRuled` and `PlanCreated` forks, collapsed for `Stopped` forks (already summarized by the badges in the parent run header).

---

## 4. Routes

| Route | Active state | Notes |
|---|---|---|
| `/` | C1 + L (Mine, default) + T1 | Home. If no token: M1 blocking. |
| `/runs/<run_id>` | C4–C10 (depending on run status) + L + T2/T3 | Deep-linkable. Public — no token required. If no token: M1-deep non-blocking. |
| `/runs/<run_id>?fork=<event_id>` | C1 pre-filled from fork point + L + T3 (parent run, faded) | URL-parametrized fork. Refresh-safe. |
| `/diff/<run_a>/<run_b>` | C12 + L (with both rows highlighted) + T5 | Shareable. Public read; fork on either side requires login. |

**Decision applied:** Fork uses `?fork=<event_id>` query param, not transient client state. Refreshing preserves the fork context.

---

## 5. RF coverage matrix

Every requirement in `requirement-understanding.md` has a UI surface. Anything not in this table is **not** exposed to the user in V1 (back-end only).

| RF | Where it lives in the UI |
|---|---|
| **RF-01** layered stopping policy | `StopReasonBadge` in `RunHeader` (C6–C10) · `JudgeRuled` expanded in trace (T3) · `ConfidenceMeter` in C6 |
| **RF-02** Level-3 inspectability + diff viewer | Entire `TracePanel` (T2–T5) · `EventPayloadViewer` on click · `DiffView` (C12 + T5) · read-determinism via cached event log on GET `/runs/<id>` |
| **RF-03** fork from decision points | `ForkButton` inline on decision `EventNode`s only (T3) · `?fork=<event_id>` URL · pre-filled form banner |
| **RF-04** ambiguity / contradiction / source failure | C7 (honest stop variants) · `AmbiguityDetected` / `ContradictionDetected` / `SourceFailed` event icons in trace · contextual fork CTAs (§3.2.1) |
| **RF-05** lightweight identity + public commons | M1 / M1-deep · `UserFooter` (logout) · `Mine` / `All public` toggle (L) · owner attribution in every `RunRow` and `RunHeader` |
| **RF-06** supported question types disclosure | `TypeDisclosure` panel inside `EmptyCenterState` (C1) — always visible, not behind a click. First-run-only `SuggestionChips` reinforce the supported types with one example each. |
| **RF-07** optional user context | Context textarea inside `QuestionForm` (C1), 1000-char cap, character counter, visible at top of `RunHeader` (collapsible) on terminal runs |
| **RF-08** live streaming + cancel + recoverable cancel | `RunningIndicator` + `ProgressIndicator` + mini-feed (C4/C5) · `EventNode`s streaming into T2 · Cancel button in `RunHeader` (owner only) · C11 reconnect banner · `Resume` button in C9 (owner only) · `ResumedAfterCancel` event in trace · `ShareLinkButton` for live + terminal runs |
| **RF-09** run discovery (URL + recent runs) | `HistoryPanel` (L) · `CompareButton` for diff discoverability · deep-link routes (§4) · *"Load more"* pagination (L7) |
| **RF-10** user-selectable answer format | `AdvancedControls` in `QuestionForm` (C2) · `AnswerRenderer` switches between prose/structured · format visible in `RunHeader` and as a metadata-diff in C12 · sticky TL;DR for structured |
| **RF-11** agent-side error handling + recoverable cancel | C10 + red `StopReasonBadge` + Resume button (owner) · `AgentErrored` / `ResumedAfterError` events visible in trace · Resume mechanism extended to `user_cancelled` (C9) with `ResumedAfterCancel` event |
| **RF-12** user-set confidence threshold | `AdvancedControls` (C2) · threshold visible in `RunHeader`, `ConfidenceMeter`, and `TrustSummary` · inherited but editable on fork (with context shown in `ForkContextCard`) |
| **confidence-calculation** | `ConfidenceMeter` in C6 · `TrustSummary` line 1 · `JudgeRuled` expanded payload in T3 (canonical) |
| **UX onboarding (P0–3)** | `SuggestionChips` on first run · `PlanPreview` in T1b · `TrustSummary` post-run · `OutcomeBar` for pre-attentive outcome recognition |

---

## 6. Explicit V1 UI non-goals

The equivalent of the trust contract, applied to UX. Each entry is a **deliberate** choice, not an oversight.

- **Responsive in V1** (mobile / tablet / desktop) — see §2 and §9.16. No native apps; browser only. No landscape-only lock; orientation is free.
- **No light mode.** Dark only. Toggle is V2.
- **No theme customization.** Single design system.
- **No full-text search in history.** The recent-runs list plus deep-link URL covers the demo path. Search is V2.
- **No infinite scroll.** Explicit *"Load more"* button.
- **No notifications, no toasts** except two narrowly scoped cases: the SSE reconnect banner (C11) and the *"Link copied"* confirmation after `ShareLinkButton` (2 s, inline near the button). Failures and outcomes are visible state, not transient popups.
- **No token-by-token streaming of the final answer.** Answer renders complete when `Stopped` event arrives. Event-level SSE is what streams.
- **No model selector in the UI.** The agent manages synthesizer and judge models internally.
- **No "regenerate" button.** The equivalent is Fork from a decision point.
- **No like / dislike on answers.** Auditable research is not graded by emoji.
- **Suggestion chips appear only on the very first run** (when the user has zero runs in `Mine`). They are an onboarding affordance, not a permanent feature. Once the user has any prior run, the empty form shows only the `TypeDisclosure` panel.
- **No avatar uploads, no user profiles.** Username is text only.
- **No export to PDF / Word / Notion.** V2, implemented via Seam 3.
- **No accessibility beyond WCAG AA + keyboard navigation.** Screen-reader optimization, reduced-motion preference, and high-contrast theme are V2.
- **No internationalization.** English UI only. Multi-language is V3 (and tied to multi-language source support).
- **No keyboard shortcuts beyond:** `Enter` to submit, `Shift+Enter` for newline, `Esc` to close modals, arrow keys to navigate history rows. `Cmd+K` palette and friends are V2.

---

## 7. Microcopy — critical strings

Every user-facing string that maps to a documented behavior. Centralized so the back-end and the UI cannot drift.

### 7.1 Login

| Surface | String |
|---|---|
| M1 / M1-deep title | *"Welcome to Novum"* |
| M1 subtitle | *"A research agent that earns its conclusions — and tells you when it cannot. Claim a username to start. No password, no email."* |
| M1-deep subtitle | *"You can browse runs as a guest. Log in to fork or start your own."* |
| Username placeholder | *"username"* |
| Continue button | *"Continue"* |
| Guest button (M1-deep) | *"Continue as guest"* |

### 7.2 Question form (`QuestionForm`)

| Surface | String |
|---|---|
| Question textarea placeholder | *"Ask Novum a question…"* |
| Context textarea label | *"Background context (optional)"* |
| Context placeholder | *"Anything Novum should know up front. Not treated as evidence."* |
| Context counter | *"<n> / 1000"* — turns amber at 900, red at 1000 |
| Advanced toggle (collapsed) | *"Advanced ▸"* |
| Advanced toggle (expanded) | *"Advanced ▾"* |
| Format selector label | *"Answer format"* |
| Format options | *"Structured (recommended)"* · *"Prose"* |
| Threshold selector label | *"Confidence threshold"* |
| Threshold options | *"Low (0.4)"* · *"Standard (0.6)"* · *"High (0.85)"* · *"Custom…"* |
| Threshold tooltip | *"Higher threshold = the agent searches longer and may honest-stop more often."* |
| Submit button | *"Start research"* — *"Starting…"* during C3 |
| Submit disabled tooltip (empty question) | *"Type a question to start."* |

### 7.3 Type disclosure (`TypeDisclosure`)

```
What Novum answers:
  ✓ Factual           e.g. "When was Tekton Labs founded?"
  ✓ Comparative       e.g. "React vs Vue for a team of 5."
  ✓ Definitional      e.g. "What is event sourcing?"
  ✓ State-of-the-art  e.g. "Best framework for LLM agents in 2026?"
  ✓ Causal            e.g. "Why did Rust gain traction in systems?"

What Novum will not answer (it will tell you why):
  ✗ Predictive        future events Novum cannot verify
  ✗ Opinion           subjective preferences
  ✗ Personal data     individuals' private information
```

When a question is rejected on submit, the rejection banner reads:
*"This looks like a <type> question. Novum honest-stops on those — see why above."*

### 7.4 Stop reason badges

| `stop_reason` | Badge label | Color token |
|---|---|---|
| `judge_confirmed` | *"Judge confirmed"* | `--semantic-success` |
| `honest_unanswerable` | *"Honest stop — unanswerable"* | `--semantic-warning` |
| `honest_contradiction` | *"Honest stop — contradiction"* | `--semantic-warning` |
| `honest_ambiguous` | *"Honest stop — ambiguous"* | `--semantic-warning` |
| `stopped_by_budget` | *"Stopped on budget"* | `--semantic-warning` |
| `user_cancelled` | *"Cancelled"* | `--semantic-neutral` |
| `errored` | *"Errored — <reason>"* | `--semantic-danger` |

### 7.5 Live run

| Surface | String |
|---|---|
| `RunningIndicator` label | *"Researching…"* |
| Cancel button | *"Cancel"* — confirms inline by changing to *"Stopping…"* until `Stopped(user_cancelled)` arrives |
| Watching badge (C5) | *"Watching live"* |
| Reconnect banner (C11) | *"Connection lost — reconnecting… (attempt <n>)"* |

### 7.6 Terminal runs

| State | Body header / banner |
|---|---|
| C8 budget caveat | *"Stopped on budget — this answer is best-effort. Fork to keep searching."* |
| C9 cancel snapshot | *"This run was cancelled. The partial trace and evidence are preserved. Resume from where you left off, or fork to try a different approach."* |
| C9 Resume button | *"Resume"* — *"Resuming…"* while the new SSE attaches (owner only) |
| C10 error | *"Something went wrong: <reason>. Your event log is intact — you can resume."* |
| C10 Resume button | *"Resume"* — *"Resuming…"* while the new SSE attaches |
| C7 ambiguous (intro) | *"Novum found multiple ways to read this question:"* (followed by bulleted interpretations) |
| C7 contradiction (intro) | *"Sources disagree. Here are the positions Novum found:"* |

### 7.7 New molecules / organisms (P0–P1 UX additions)

| Surface | String |
|---|---|
| `ProgressIndicator` (C4/C5) | *"Researching · <covered> of <total> sub-claims covered · <elapsed>s"*. If `<total>` not yet known (pre-`PlanCreated`): *"Researching · planning… · <elapsed>s"*. |
| `TrustSummary` line 1 (C6) | *"✓ Judge confirmed · confidence <X> / threshold <Y>"* |
| `TrustSummary` line 1 (C7 unanswerable) | *"⚠ Honest stop · question is unanswerable"* |
| `TrustSummary` line 1 (C7 contradiction) | *"⚠ Honest stop · sources disagree"* |
| `TrustSummary` line 1 (C7 ambiguous) | *"⚠ Honest stop · question is ambiguous"* |
| `TrustSummary` line 1 (C8) | *"⚠ Stopped on budget · best-effort answer"* |
| `TrustSummary` line 1 (C9) | *"⊘ Cancelled · partial trace preserved"* |
| `TrustSummary` line 1 (C10) | *"⚠ Errored · <provider reason>"* |
| `TrustSummary` metrics line | *"<N> sources cited · <covered>/<total> sub-claims covered"* |
| `TrustSummary` contradictions line | *"<unresolved> unresolved contradictions · <resolved> resolved"* (line is omitted when both are 0) |
| `TrustSummary` footer line | *"<elapsed>s · <event_count> events"* (cost omitted in V1 if not yet wired) |
| `SuggestionChips` heading (first run only) | *"Try one of these:"* |
| `SuggestionChips` content | 3 chips, one each for definitional / comparative / state-of-the-art. Defaults: *"What is event sourcing?"* · *"React vs Vue for a team of 5"* · *"Best framework for LLM agents in 2026"*. |
| `PlanPreview` (T1b) | *"Novum will:"* followed by an ordered list: *"1. Classify the question type · 2. Plan sub-claims to cover · 3. Search the web and Wikipedia · 4. Check source agreement and contradictions · 5. Have a judge verify sufficiency · 6. Answer — or honest-stop if it cannot."* + footer: *"Events will appear below as they happen."* |
| `ShareLinkButton` tooltip | *"Copy link to this run"* |
| `ShareLinkButton` confirmation | inline toast next to the button for 2 s: *"Link copied"* |
| `CompareButton` label | *"Compare"* |
| `CompareButton` tooltip | *"Compare two runs side by side"* |
| `ForkContextCard` header | *"Forking from <event_type> at step <n>"* with collapse `▾` / expand `▸` |
| `ForkContextCard` body (per event_type) | `PlanCreated`: shows the plan's claims list · `JudgeRuled`: shows `sufficient`, `confidence`, `S`, `J`, and the judge's one-line rationale · `ContradictionDetected`: shows the two positions and their sources · `AmbiguityDetected`: shows the detected interpretations · `Stopped`: shows `stop_reason` and the final summary |
| Relative time formatter (`lib/format.ts`) | < 60s *"just now"* · < 60m *"<n>m ago"* · < 24h *"<n>h ago"* · < 7d *"<n>d ago"* · same year *"MMM D"* · else *"MMM D, YYYY"*. Tooltip shows ISO 8601 absolute. |

### 7.7' Live Run Feed microcopy (IP-24)

| Surface | String |
|---|---|
| `FEED_LET_ME_SEARCH` | *"Let me search for {query}…"* |
| `FEED_LET_ME_FETCH` | *"Let me read this page…"* |
| `FEED_LET_ME_THINK` | *"Let me work this through…"* |
| `FEED_SEARCHED_WEB` | *"Searched the web"* |
| `FEED_FETCHED_PAGE` | *"Fetched the page"* |
| `FEED_DONE` | *"Done"* |
| `FEED_RESULTS_COUNT(n)` | `n === 1 ? "1 result" : "${n} results"` (function) |
| `FEED_TOGGLE_COLLAPSE` | *"Collapse reasoning"* |
| `FEED_TOGGLE_EXPAND` | *"Expand reasoning"* |
| `TRACE_PANEL_COLLAPSE` | *"Collapse trace"* |
| `TRACE_PANEL_EXPAND` | *"Expand trace"* |
| `ANSWER_SKIP_HINT` | *"Click to skip"* (shown during typewriter animation) |
| `ANSWER_ANIMATE_TOGGLE` | *"Animate answer"* (global toggle label) |

### 7.8 Sticky TL;DR (structured answers, C6)

When `output_format = structured`, the **TL;DR section** of the rendered answer becomes a sticky element inside the scrollable answer body: it pins to the top of the body container while the user scrolls through Body / Claims table / Caveats. The pinned variant is one line shorter (collapses subtitle if any). Releases sticky on scroll-up beyond its natural position.

### 7.9 Compare button strings

When `CompareButton` is clicked (L4 → L5):
- The `RunRow` checkboxes become persistently visible (no longer hover-only).
- The header reads: *"Pick two runs to compare"* with cancel link.
- After one pick: same as L5 microcopy.
- After two picks: same as L6 microcopy.

### 7.10 Responsive top-bar (mobile / tablet)

Below `desktop` breakpoint, `AppShell` injects a 48 px sticky top-bar above `CenterPanel` (and replaces the in-panel headers that used to live inside the side panels). It contains:

```
[☰ History]   Novum            [Trace ◮]
```

- **Left button** (`MobileMenuButton`): opens the `HistorySheet` drawer (history panel content, slides from left). 44 × 44 px tap target.
- **Center label**: app name. Doubles as a tap-to-scroll-top affordance for the center body.
- **Right button** (`TraceToggleButton`): opens the `TraceSheet` drawer (trace panel content, slides from right). Hidden when the current center state has no trace to show (L1–L3 home, M1 login). 44 × 44 px tap target.
- Both drawers use shadcn `Sheet`. Body content inside the drawer is **the exact same component tree** as the desktop panel — just remounted into a `Sheet` container. Closing the drawer keeps state (scroll position, multi-select) via `selectionStore`.
- The top-bar is **not rendered at desktop** breakpoint. There is no visual difference there.

### 7.11 Trace

| Surface | String |
|---|---|
| T1 empty | *"Trace will appear here when research starts."* |
| `ForkButton` label | *"Fork from here"* |
| `ForkButton` disabled tooltip (guest) | *"Log in to fork this run."* |
| Expand event hint | first event shows *"Click any step for full details"* (dismissible) |
| Auto-scroll paused indicator | small pill at bottom-right of trace: *"Jump to latest ↓"* — appears when sticky-at-bottom is broken |

### 7.12 History

| Surface | String |
|---|---|
| Toggle labels | *"Mine"* · *"All public"* |
| Empty Mine (L2) | *"You haven't started any research yet."* + button *"See public runs"* |
| Empty All public (L3) | *"No public runs yet. Be the first."* |
| Multi-select intro (L5) | *"Select one more to compare."* |
| Multi-select ready (L6) | *"Compare these two →"* |
| Cancel multi-select | *"Cancel selection"* |
| Load more (L7) | *"Load more"* |

### 7.13 Diff mode

| Tab | Shows |
|---|---|
| `Timeline` | Side-by-side event sequence, aligned by `step_index`, with `+` / `−` / `≠` markers |
| `Evidence` | Set diff of sources cited, with deltas (chunks added / removed / shared) |
| `Outcome` | Final answer A vs B, stop reasons, confidence numbers — semantic diff, not character diff |

---

## 8. Component architecture · Atomic Design (mandatory)

The frontend is built strictly under **Atomic Design** as defined by Brad Frost. This is a **build mandate**, not a guideline — every component must be assigned to exactly one of the five layers, and the dependency direction is enforced one-way. Violating the layering rules is a build-time concern (lint rule + folder boundaries), not a code-review opinion.

### 8.1 The five layers and their rules

| Layer | Purpose | Allowed dependencies | Owns data? | Examples |
|---|---|---|---|---|
| **Atoms** | Smallest indivisible visual or interactive primitive. A button, an input, a label, an icon, a single badge. | Only `ui/` (shadcn) primitives and design tokens. **Never** another component from any layer. | No | `Button`, `Input`, `Badge`, `StatusIcon`, `EventIcon` |
| **Molecules** | A small functional group of atoms that has a single, clear purpose. A labeled input, a toggle pair, a meter bar with a label. | Atoms + tokens. **Never** organisms, templates, pages. | No | `HistoryToggle`, `ConfidenceBar`, `CharCounter`, `MiniFeedItem` |
| **Organisms** | A complex, self-contained UI section. A form, a header, a list row, a modal body. | Atoms + molecules + hooks for self-contained state. **Never** templates, pages, or other organisms. | Local only (UI state — not server data) | `QuestionForm`, `TypeDisclosure`, `RunHeader`, `EventNode`, `RunRow`, `AnswerRenderer`, `DiffView`, `LoginModal` |
| **Templates** | Page-level layout skeletons with named slots. Define the geometry of the page, not its content. | Organisms + atoms + layout primitives. **Never** fetch data, never know about routes. | No | `AppShell` (the 3-panel layout), `HistoryPanel`, `CenterPanel`, `TracePanel` |
| **Pages** | Route-level components. Wire data (via hooks/stores) into templates and organisms. | Anything below + hooks + stores + routing. | **Yes** — this is the only layer allowed to fetch and own server data | `HomePage`, `RunPage`, `DiffPage` |

**Hard rules:**

1. **Strict downward dependency.** A component can only import from layers strictly below it. Atoms cannot import molecules; molecules cannot import organisms; templates cannot import pages. **No exceptions.**
2. **No data fetching outside pages.** Hooks like `useRun`, `useRunHistory`, `useEventStream`, `useUser` are called **only** in pages. Pages pass the resulting data down as props. Organisms and below remain pure presentation + local UI state.
3. **No business logic in templates.** Templates only arrange organisms in slots.
4. **No same-layer composition** except for atoms inside atoms (e.g. an `IconButton` atom may compose an `Icon` atom). Molecules don't compose molecules; organisms don't compose organisms — if that need appears, the larger thing is a template or a page.
5. **`shadcn/ui` lives in `components/ui/` and counts as the atom-primitive layer.** Anything we wrap from `ui/` becomes one of our atoms with our naming and our tokens.

### 8.2 Component classification (every named component)

Every component referenced anywhere in §3–§7 of this document has an exact layer assignment. Anything outside this table cannot be built without first deciding its layer.

#### Atoms

| Component | Notes |
|---|---|
| `Button` | Wraps shadcn `Button`. Variants: primary / secondary / ghost / danger / icon. |
| `IconButton` | Atom-of-atoms exception: composes `Icon`. |
| `Input` | Single-line text. |
| `Textarea` | Auto-resize behavior lives here. Used by `QuestionForm` and the context textarea. |
| `Checkbox` | Used in history multi-select. |
| `Label` | Form label primitive. |
| `Tooltip` | Wraps shadcn `Tooltip`. |
| `Icon` | Generic Lucide wrapper with size/color tokens. |
| `StatusIcon` | The 4-state run status icon (`▶ / ✓ / ⚠ / ⊘`). |
| `EventIcon` | Maps each event type to its Lucide icon (per §3.3 table). |
| `Badge` | Pill primitive. Variant-driven colors via tokens. |
| `StopReasonBadge` | A `Badge` configured for stop_reason semantics. |
| `Spinner` | Loading spinner. |
| `Dot` | Single animated dot used by `RunningIndicator`. |
| `Skeleton` | Shimmer block for L1 / loading states. |
| `Pill` | Smaller than `Badge`, used for `Mine`/`All public` toggle options. |
| `ForkButton` | A specialized button atom — semantic to the domain but indivisible. |
| `KeyboardHint` | Inline `<kbd>` element for shortcut hints. |
| `OutcomeBar` | 4 px colored strip at top of `CenterPanel` on terminal states. Color via token; nothing else. |
| `SuggestionChip` | Single clickable pill that fills the question textarea on click. |
| `CompareButton` | Styled `Button` variant living in the history header. |
| `TotalCostChip` | Clickable chip in `RunHeader` showing `$total · N tokens` for the run. Click opens trace tab `T1d`. Loading skeleton on first paint. Driven by `useRunCosts(runId)`. See RF-20. |
| `CostBarSegment` | One colored segment of the stacked bar inside `CostBreakdownBar`. Color via the provider-color token map (no new design tokens — reuses `--accent`, `--accent-soft`, `--semantic-*`). |

#### Molecules

| Component | Composed of | Purpose |
|---|---|---|
| `HistoryToggle` | 2× `Pill` | `Mine` / `All public` switch in HistoryPanel header. |
| `RunningIndicator` | 3× `Dot` + `Label` | The "Researching…" 3-dot indicator. |
| `ConfidenceBar` | `Label` + bar primitive + `Badge` | One row of the breakdown meter. Five of these compose `ConfidenceMeter`. |
| `CharCounter` | `Label` | Live `<n> / 1000` counter for context textarea. Colorizes at thresholds. |
| `FormatSelector` | `Label` + `Button`s | Structured / Prose chooser. |
| `ThresholdSelector` | `Label` + `Button`s + `Input` (for Custom) | Low / Standard / High / Custom chooser. |
| `MiniFeedItem` | `EventIcon` + `Label` + relative-time text | One row of the running mini-feed. |
| `RunRowMeta` | `StatusIcon` + owner + `StopReasonBadge` + time + fork count | The right-aligned metadata strip inside a `RunRow`. |
| `ConnectionStatus` | `Dot` + `Label` | Small connection state pill in `RunHeader`. |
| `EmptyStateMessage` | `Icon` + `Label` + optional `Button` | Reused in L2, L3, T1a, C13. |
| `ProgressIndicator` | `Label` + bar primitive + `Label` | *"Researching · N of M sub-claims covered"* + horizontal progress bar. Driven by `C_coverage` from the live event stream. |
| `SuggestionChips` | row of 3 `SuggestionChip` atoms | First-run-only onboarding row. Hidden after the user has any prior run. |
| `PlanPreview` | `Label` + `Icon` + ordered list | T1b state — narrative description of what Novum will do, shown post-`QuestionAsked` and pre-`PlanCreated`. |
| `ShareLinkButton` | `IconButton` + inline toast region | Copies the current run URL on click. Shows *"Link copied"* inline for 2 s. |
| `CostBreakdownBar` | many `CostBarSegment` + provider legend | Stacked horizontal bar in `TraceCostPanel` (T1d) — one segment per `(provider, kind)`, widths proportional to `cost_usd`. |
| `CostBreakdownTable` | table primitives + `Badge` | Tabular view in `TraceCostPanel` (T1d): rows = `(provider, kind, model)`, columns = calls / tokens / USD / % of total. Empty state when ledger has no entries. |

#### Organisms

| Component | Composed of | Purpose / location |
|---|---|---|
| `LoginModal` | atoms + `EmptyStateMessage` | M1 / M1-deep |
| `UserFooter` | `Icon` + username + `Button` (logout) | Bottom of HistoryPanel |
| `RunRow` | `Checkbox` + truncated question + `RunRowMeta` | One entry in the history list |
| `HistoryList` | many `RunRow` + `Skeleton` + `EmptyStateMessage` + Load-more `Button` | Body of HistoryPanel |
| `QuestionForm` | `Textarea` × 2 + `CharCounter` + `Button` + `AdvancedControls` (mol or org? — **organism**, see below) | The form in C1/C2 |
| `AdvancedControls` | `FormatSelector` + `ThresholdSelector` + reveal animation | Collapsible section of the form. **Organism**, not molecule, because it owns its own reveal state. |
| `TypeDisclosure` | atoms + a small data file | The visible-by-default panel listing 5 supported + 3 unsupported types |
| `RunHeader` | `StopReasonBadge` + question text + `ConfidenceMeter` (compact) + Cancel/Resume `Button` + `ConnectionStatus` + `TotalCostChip` (RF-20) | Top of CenterPanel during/after a run |
| `MiniFeed` | up to 5× `MiniFeedItem` + auto-scroll behavior | Body of C4/C5 |
| `AnswerRenderer` | Markdown renderer + `StopReasonBadge` + (for structured) sectioned blocks | Body of C6/C8 |
| `ConfidenceMeter` | 5× `ConfidenceBar` (compact = first one only) | Expandable in `RunHeader`, also referenced inside `EventPayloadViewer` for `JudgeRuled` |
| `EventNode` | `EventIcon` + meta line + `ForkButton` + collapsible `EventPayloadViewer` | One item in the trace timeline |
| `EventPayloadViewer` | custom JSON renderer (atoms internally) + Copy `Button` | Expanded payload inside an `EventNode` |
| `Timeline` | many `EventNode` + sticky-at-bottom auto-scroll + `Jump-to-latest` pill | Body of TracePanel in T2/T3 |
| `TimelineDiff` | two `Timeline`s aligned by `step_index` + diff markers | The Timeline tab inside `DiffView` |
| `EvidenceDiff` | set-diff renderer | The Evidence tab inside `DiffView` |
| `OutcomeDiff` | side-by-side answer + metadata diff | The Outcome tab inside `DiffView` |
| `TraceCostPanel` | `TotalCostChip` (large) + `CostBreakdownBar` + `CostBreakdownTable` + loading/error/empty states | Body of `TracePanel` tab T1d. Mounts `useRunCosts(runId)`. See RF-20. |
| `DiffView` | tab bar + one of `TimelineDiff` / `EvidenceDiff` / `OutcomeDiff` | C12 |
| `HonestStopExplainer` | layout for interpretations / contradictions / out-of-scope content + contextual fork CTA | Body of C7 |
| `ErrorState` | failure reason + Resume `Button` + last-known-state snapshot | Body of C10 |
| `TrustSummary` | atoms + tokens + computed metrics from the event log | Renders at the top of every terminal-state body (C6–C10) as the "nutrition label" of the run. Variant rendered per `stop_reason` (see §3.2.4). |
| `ForkContextCard` | collapsible card + per-event-type renderer | Sits above the textareas inside `QuestionForm` when the form is rendered in fork mode. Shows the originating event's contents so the user understands what they are departing from. |

#### Templates

| Component | Slots | Purpose |
|---|---|---|
| `AppShell` | `left`, `center`, `right` | The root layout. Owns the viewport and the panel widths at desktop. **Below 1024 px**, renders the responsive top-bar and mounts `left` / `right` slot contents into `HistorySheet` / `TraceSheet` drawers instead of side panels. Renders any modals via portal. |
| `HistoryPanel` | header slot, body slot, footer slot | Geometry of the left panel at desktop. At tablet/mobile its contents are re-mounted inside `HistorySheet`. Does not know what runs are. |
| `CenterPanel` | header slot, body slot, optional `OutcomeBar` slot | Geometry of the center. Always visible at every breakpoint. Does not know if it is showing a form, a run, or a diff. |
| `TracePanel` | header slot, body slot | Geometry of the right panel at desktop. At tablet/mobile its contents are re-mounted inside `TraceSheet`. |
| `HistorySheet` | (wraps `HistoryPanel` slots) | shadcn `Sheet` from the left. Used at tablet + mobile to host history content. |
| `TraceSheet` | (wraps `TracePanel` slots) | shadcn `Sheet` from the right. Used at tablet + mobile to host trace content. |
| `MobileTopBar` | left button slot, label slot, right button slot | 48 px sticky bar above `CenterPanel` at tablet + mobile. Hosts the two drawer toggles. Not rendered at desktop. |

#### Pages

| Page | Route | Owns | Renders |
|---|---|---|---|
| `HomePage` | `/` | `useUser`, `useRunHistory` | `AppShell` → `HistoryPanel` (with `HistoryToggle`, `HistoryList`, `UserFooter`) · `CenterPanel` (with `QuestionForm` + `TypeDisclosure`) · `TracePanel` (T1 empty state) |
| `RunPage` | `/runs/<run_id>` and `/runs/<run_id>?fork=<event_id>` | `useUser`, `useRun(run_id)`, `useEventStream(run_id)`, `useRunHistory` | Same `AppShell`, center varies per run state (C3–C11), trace shows T2/T3 |
| `DiffPage` | `/diff/<a>/<b>` | `useUser`, `useRun(a)`, `useRun(b)`, `useRunHistory` | Same `AppShell`, center renders `DiffView` (C12), trace renders `TimelineDiff` (T5) |

The login modal is a singleton owned by `AppShell` — it observes `useUser` and renders itself when needed. Pages do not "render" the login modal.

### 8.3 Folder structure (mirrors the atomic layers)

```
src/
├── components/
│   ├── ui/                       // shadcn/ui generated — atom primitives layer
│   ├── atoms/
│   │   ├── Button.tsx
│   │   ├── IconButton.tsx
│   │   ├── Input.tsx
│   │   ├── Textarea.tsx
│   │   ├── Checkbox.tsx
│   │   ├── Label.tsx
│   │   ├── Tooltip.tsx
│   │   ├── Icon.tsx
│   │   ├── StatusIcon.tsx
│   │   ├── EventIcon.tsx
│   │   ├── Badge.tsx
│   │   ├── StopReasonBadge.tsx
│   │   ├── Spinner.tsx
│   │   ├── Dot.tsx
│   │   ├── Skeleton.tsx
│   │   ├── Pill.tsx
│   │   ├── ForkButton.tsx
│   │   ├── KeyboardHint.tsx
│   │   ├── OutcomeBar.tsx
│   │   ├── SuggestionChip.tsx
│   │   └── CompareButton.tsx
│   ├── molecules/
│   │   ├── HistoryToggle.tsx
│   │   ├── RunningIndicator.tsx
│   │   ├── ProgressIndicator.tsx
│   │   ├── ConfidenceBar.tsx
│   │   ├── CharCounter.tsx
│   │   ├── FormatSelector.tsx
│   │   ├── ThresholdSelector.tsx
│   │   ├── MiniFeedItem.tsx
│   │   ├── RunRowMeta.tsx
│   │   ├── ConnectionStatus.tsx
│   │   ├── EmptyStateMessage.tsx
│   │   ├── SuggestionChips.tsx
│   │   ├── PlanPreview.tsx
│   │   └── ShareLinkButton.tsx
│   ├── organisms/
│   │   ├── LoginModal.tsx
│   │   ├── UserFooter.tsx
│   │   ├── RunRow.tsx
│   │   ├── HistoryList.tsx
│   │   ├── QuestionForm.tsx
│   │   ├── AdvancedControls.tsx
│   │   ├── TypeDisclosure.tsx
│   │   ├── RunHeader.tsx
│   │   ├── MiniFeed.tsx
│   │   ├── AnswerRenderer.tsx
│   │   ├── ConfidenceMeter.tsx
│   │   ├── TrustSummary.tsx
│   │   ├── ForkContextCard.tsx
│   │   ├── EventNode.tsx
│   │   ├── EventPayloadViewer.tsx
│   │   ├── Timeline.tsx
│   │   ├── HonestStopExplainer.tsx
│   │   ├── ErrorState.tsx
│   │   ├── DiffView.tsx
│   │   ├── TimelineDiff.tsx
│   │   ├── EvidenceDiff.tsx
│   │   └── OutcomeDiff.tsx
│   └── templates/
│       ├── AppShell.tsx
│       ├── HistoryPanel.tsx
│       ├── CenterPanel.tsx
│       ├── TracePanel.tsx
│       ├── HistorySheet.tsx       // mobile/tablet drawer wrapper
│       ├── TraceSheet.tsx         // mobile/tablet drawer wrapper
│       └── MobileTopBar.tsx       // 48 px sticky bar < 1024 px
├── pages/
│   ├── HomePage.tsx
│   ├── RunPage.tsx
│   └── DiffPage.tsx
├── hooks/
│   ├── useRun.ts                 // load + manage one run
│   ├── useEventStream.ts         // SSE wrapper, idempotent by event.id
│   ├── useRunHistory.ts          // Mine vs All public + pagination
│   ├── useUser.ts                // identity + token persistence
│   ├── useAutoScroll.ts          // sticky-when-at-bottom
│   ├── useMultiSelect.ts
│   ├── useViewport.ts            // breakpoint detection (mobile/tablet/desktop), debounced 150 ms
│   └── useRunMetrics.ts          // derives TrustSummary metrics from event log
├── store/
│   ├── userStore.ts              // Zustand
│   └── selectionStore.ts         // multi-select cross-toggle
├── lib/
│   ├── api.ts
│   ├── sse.ts
│   ├── format.ts                 // relative time (see §9), truncate, etc.
│   └── clipboard.ts              // copy URL helper for ShareLinkButton
├── types/
│   ├── events.ts                 // event payload types (mirrors back-end)
│   ├── run.ts
│   └── user.ts
├── styles/
│   └── globals.css               // CSS variables + reset + scrollbar
├── router.tsx                    // route → page mapping
└── main.tsx                      // app entry
```

### 8.4 Enforcement

The layering rules are not honor-system. They are enforced by:

1. **ESLint `import/no-restricted-paths`** rule, declared in `.eslintrc`. Each layer declares its allowed `from` zones. Violations break the build.
2. **Folder-as-boundary convention.** Every component lives in exactly one of `atoms/`, `molecules/`, `organisms/`, `templates/`, `pages/`. No `shared/`, no `common/`, no `utils/components/`. If something does not fit a layer, the layer assignment is wrong.
3. **One component per file.** Filename matches export name. No barrel files that re-export across layers.
4. **Storybook (optional in V1, mandatory in V2).** Each atom and molecule gets a story. Organisms get a story with mocked props. This is the substrate of any future component-library extraction.

### 8.5 Why this is a build mandate, not a preference

This is the section where the pair session will probe hardest, so the reasoning is on the record:

- **The pair session adds a requirement.** Adding it cleanly means knowing exactly which layer the new piece belongs to. Atomic Design pre-answers *"where does this live?"* — without it, every new requirement is an architectural conversation.
- **Inspectability is the product.** A jumbled component tree contradicts that posture. The trace UI is auditable; the code that renders it should be auditable too.
- **The 4–6 hour budget rewards predictability.** Hesitating on file placement burns hours. The five-layer taxonomy collapses that decision to a glance.
- **Refactor cost stays linear.** The backend already runs on Postgres in V1; when V2 changes the schema (e.g. adds snapshots), only `hooks/` and `lib/api.ts` change — every layer above is insulated. Same when V2 introduces real auth: only `useUser`, `LoginModal`, and `pages/` touch identity logic.
- **It is a Solutions Director artifact.** Saying *"the frontend follows Atomic Design, here is the lint rule that enforces it"* is the architectural equivalent of the trust contract: a constraint visible from the outside.

---

## 9. Technical UI decisions

These are the technical contracts the frontend commits to. Each one is small but consequential: data fetching shape, persistence keys, SSE protocol, global error handling, performance budget, testing minimum, and explicit deferrals. Anything not listed here is implementation detail.

### 9.1 Data fetching · TanStack Query (React Query)

All server reads route through **TanStack Query**. No `fetch` inside organisms, no `useEffect`-based fetches outside `hooks/`.

**Why this and not SWR or raw fetch:**
- The cache + invalidation model fits the SSE-driven world exactly: when `Stopped` arrives, the hook invalidates `["runs", "list"]` and the history refetches automatically.
- Dedupe is free — guarantees a deep-linked `/runs/<id>` doesn't double-fetch when the user clicks the same row in history.
- Devtools accelerate the pair session: I can show cache state on screen if a question goes deep on "what does the client know vs the server".

**Query key conventions:**
```
["user", "me"]
["runs", "list", { scope: "mine" | "all_public", cursor: string | null }]
["runs", "detail", runId]
["runs", "events", runId]                  // events fetched at load before SSE attaches
```

**Mutation keys:**
```
["runs", "create"]                            // POST /runs
["runs", "cancel", runId]
["runs", "resume", runId]
["runs", "fork", runId, eventId]
["user", "login"]
```

**Invalidation triggers:**
| Event | Invalidates |
|---|---|
| SSE `Stopped` received | `["runs", "list"]` · `["runs", "detail", runId]` |
| Successful `create` mutation | `["runs", "list", { scope: "mine" }]` |
| Successful `fork` mutation | `["runs", "list", { scope: "mine" }]` |
| `login` success | every cache key (full reset, simplest) |
| `logout` | every cache key |

**Stale times:**
- `["user", "me"]`: `Infinity` (only invalidated by login/logout).
- `["runs", "list", ...]`: 30 s — short enough that a quick fork shows up, long enough to dedupe rapid navigations.
- `["runs", "detail", ...]`: `Infinity` for terminal runs (read-deterministic per RF-02), 0 for running runs (let SSE drive).
- `["runs", "events", ...]`: same rule as detail.

### 9.2 Client-side persistence · `localStorage` only

No cookies in V1. Token theft is a non-threat because anyone can claim any username already (documented non-guarantee in the trust contract).

| Key | Type | Purpose | Survives logout? |
|---|---|---|---|
| `novum.token` | string (opaque) | RF-05 persistent identity | No — cleared on logout |
| `novum.username` | string | Optimistic display before `["user", "me"]` resolves | No — cleared on logout |
| `novum.history_toggle` | `"mine" \| "all_public"` | Last selected history scope | **Yes** — survives logout (per-device pref) |
| `novum.advanced_open` | boolean | Whether `AdvancedControls` was last expanded | **Yes** — survives logout |

**Deliberately NOT persisted:**
- `novum.last_format` — forces user to make a conscious choice when they need non-default. Avoids "why is my output prose? I never picked prose."
- `novum.last_threshold` — same rationale, plus higher safety (a user shouldn't unintentionally lower rigor).
- Any pagination cursor, scroll position, or selection state — multi-select is intentionally session-only.

**Read shape:** wrapped in a `usePersistedState<T>(key)` hook with a Zod schema for safety on malformed values.

### 9.3 SSE protocol

Given the run-duration target (< 90 s, RF-08 + the latency KPI in §6-bis of the requirements doc), event idempotency by `event.id` (RF-02), and the single-server scope (RF-05), this protocol is deliberately simple. Heavyweight reconnect machinery would be over-engineering.

**Connection lifecycle:**
1. Client opens `EventSource` to `GET /runs/<run_id>/stream`.
2. Server immediately replays any events the client has not seen yet (based on `Last-Event-ID` header if present, otherwise from event 0).
3. Server keeps the connection open and pushes new events as they happen.
4. When the run reaches a terminal `Stopped` event, the server **closes the stream cleanly** (no `__end__` sentinel). The client treats `readyState === CLOSED` after a `Stopped` event as the normal exit path.
5. If the run is already terminal when the client connects, the server replays the full event log then closes.

**Why server-closes-after-`Stopped` (option a) and not a `__end__` sentinel (option b):**
- The `Stopped` event is already the canonical terminal signal in the event log. Adding a second one is duplicated state.
- Browser `EventSource` distinguishes "server closed cleanly" from "network dropped" via `readyState`. We use that signal directly.
- Reconnect logic stays correct: if the client sees `readyState === CLOSED` **and** the last received event was `Stopped`, do nothing. Otherwise, reconnect.

**Reconnect strategy:**
| Property | Value |
|---|---|
| Trigger | `readyState === CLOSED` AND last event was not `Stopped` |
| Backoff | Exponential: 1 s → 2 s → 4 s → 8 s → 16 s |
| Max attempts | 5 |
| Resume mechanism | Client sends `Last-Event-ID` header (W3C standard). Server resumes from the next event. |
| UI surface during reconnect | C11 banner *"Connection lost — reconnecting… (attempt n/5)"* |
| UI surface after exhaustion | Banner becomes *"Could not reconnect. The run may still be running — refresh to retry."* with manual retry button. **The run is not marked errored client-side** — only the server can decide that. |

**Heartbeat:**
- Server sends a comment-line heartbeat (`: keepalive\n\n`) every **15 s** to defeat proxies and detect zombie connections.
- Client treats absence of any data for **30 s** as a dropped connection and triggers reconnect.
- Heartbeats are not events and are not visible in the trace.

**Idempotency:**
- Every event carries `event.id` (UUID v4 or monotonic int — back-end decision).
- Client maintains a `Set<event.id>` for the current run. Duplicates from a replayed window are dropped on the client side too as defense-in-depth.

**Why this is right for the context:**
> *"Runs are short, single-server, idempotent by event id, and the event log is the source of truth. The simplest correct SSE protocol is: stream until `Stopped`, then close; reconnect with `Last-Event-ID` if the close was unexpected. Anything beyond that is solving problems we don't have."*

### 9.4 Global error states (non-run)

The in-run error states (C10, C11) cover failures of the agent and the SSE. These are the **other** failure modes — failures of the front-end's own HTTP calls and environment.

| Trigger | Surface | Component |
|---|---|---|
| HTTP 5xx on `GET /runs/<id>` | Center renders C13-like screen, message: *"Could not load this run. Retry."* with retry button | `CenterPanel` body |
| HTTP 5xx on `GET /runs` (list) | Persistent banner above `HistoryList`: *"Could not load runs. [Retry]"* | `HistoryPanel` |
| HTTP 5xx on `POST /runs` (create) | Inline error inside `QuestionForm`, below submit button: *"Could not start research: <reason>. Try again."* | `QuestionForm` |
| HTTP 5xx on Fork / Cancel / Resume | Inline error in the originating component, no toast | Per-component |
| HTTP 401 anywhere (token rejected) | Full TanStack Query cache reset → redirect to M1 with note: *"Your session expired. Log in again."* | `AppShell` |
| HTTP 403 (trying to mutate a run you don't own) | Inline error: *"You can only modify runs you started."* | Per-component |
| HTTP 404 on `/runs/<id>` | C13 *"Run not found."* | `CenterPanel` body |
| `navigator.onLine === false` | Top-of-viewport banner: *"You're offline. Reconnect to continue."* — non-dismissible while offline | `AppShell` |
| Unhandled JS error | React error boundary at `AppShell` level — *"Something broke. Reload to continue."* with reload button | `AppShell` |

**General principle:** errors are **inline where they happened**, not floating toasts. The only persistent banners are connectivity (offline / SSE reconnecting) and history-load failure. No transient toasts in V1 — they hide state.

### 9.5 Performance budget

Declared as targets, not premature optimization. Implementation only kicks in when measurement shows the target is at risk.

| Metric | Target | When to act |
|---|---|---|
| Bundle size (gzipped) | ≤ 250 KB | Above 200 KB → audit imports, lazy-load `react-syntax-highlighter` |
| LCP (localhost demo) | < 1.5 s | Above 2 s → audit blocking work in `HomePage` |
| TTI (localhost demo) | < 2 s | Same as LCP |
| CLS | < 0.05 | Skeletons must match real-content height |
| `HistoryList` render time | < 50 ms for 50 rows | If exceeded → react-window |
| `Timeline` render time | < 100 ms for 50 events | If exceeded → react-window |

**Virtualization triggers (declared, not implemented in V1):**
- `HistoryList` virtualizes when row count > **100**.
- `Timeline` virtualizes when event count > **200**.
- Neither is expected to fire in the demo. Documented so the design defends "we know where the seam is."

### 9.6 Testing strategy

The Atomic Design layering enables a tiered testing pyramid that maps onto the file structure.

| Layer | What we test | Tool | V1 scope |
|---|---|---|---|
| Atoms | Render with each variant prop, axe-core accessibility check | Vitest + Testing Library + `jest-axe` | Smoke test for the 4 highest-visibility atoms: `Button`, `StopReasonBadge`, `ForkButton`, `Badge` |
| Molecules | Interaction (click, hover, keyboard) | Vitest + Testing Library | Smoke test for `HistoryToggle`, `ConfidenceBar` |
| Organisms | Behavior under realistic props (loading, success, error) | Vitest + Testing Library + MSW for API mocks | Tests for `RunHeader`, `EventNode`, `QuestionForm`, `LoginModal` — the 4 organisms with branching state |
| Pages | ⏳ **V2** — Playwright happy-path deferred | Playwright (post-MVP) | Originally: *"log in → ask comparative question → see `judge_confirmed` answer → fork from `JudgeRuled`"*. V1 covers this via manual smoke. |
| Visual regression | n/a in V1 | Chromatic (V2) | Deferred |

**V1 testing budget:** ~1 hour total. The point is to prove the code is auditable, not to chase coverage numbers. Reviewers will look at *what is tested* more than *how much*.

### 9.7 Internationalization · hardcoded English in V1

All user-facing strings are hardcoded English in V1. No `t()` wrapper, no JSON dictionary.

**Documented as deuda explícita.** V2 migration path:
1. Extract every literal in `microcopy` (§7) into `src/i18n/en.json`.
2. Introduce `react-i18next` provider in `AppShell`.
3. Replace literals with `t("key")`.
4. Add language switcher (probably a new molecule).

Reasoning: V1 is 4–6 hours; that hour belongs to the agent loop, not to a provider configuration. The strings are already centralized in §7 of this doc, so the V2 extraction is a 1-hour mechanical exercise.

### 9.8 Edge case caps (input validation)

| Surface | Cap | Behavior on overflow |
|---|---|---|
| Question textarea | 500 characters | Char counter goes red at 500, submit disabled at 501 |
| Context textarea | 1000 characters (per RF-07) | Char counter red at 1000, submit disabled at 1001 |
| Username | regex `^[a-zA-Z0-9_-]{2,32}$` | Inline validation error in M1 |
| `RunRow` question truncation | 60 chars + ellipsis | Full question available in tooltip |
| `EventPayloadViewer` JSON depth | No cap | If a payload is huge, the viewer is collapsible by key |
| `MiniFeed` items kept | Last 5 always | Older items removed (still in full trace) |

### 9.9 Wireframes · ASCII only in V1

The ASCII layouts embedded in §2 and §3 of this document **are** the wireframes. No Figma, no Excalidraw, no separate artifact. Reasoning:
- ASCII renders inside the same Markdown the reviewers read.
- The reviewers' attention is on the system, not the wireframes — anything more polished risks signaling priority misalignment.
- Implementation directly references the layouts in this doc, so there is no source-of-truth split.

### 9.10 Tooling and DX configuration (deferred to repo bootstrap)

These are decisions that belong to a future `ARCHITECTURE.md` written when the repository is initialized, not to this UI spec. Calling them out so they are not forgotten:

- **ESLint** with `eslint-plugin-import` + `import/no-restricted-paths` rule enforcing the atomic layering from §8.
- **Prettier** with project defaults (printWidth 100, single quotes, no semicolons — to be confirmed at repo init).
- **Husky** pre-commit hook running `lint` + `typecheck`. No tests in pre-commit (too slow).
- **TypeScript** strictness: `"strict": true`, `"noUncheckedIndexedAccess": true`, `"exactOptionalPropertyTypes": true`.
- **Path aliases** via `vite-tsconfig-paths` so atomic-layer imports read clean: `@/atoms/Button`, `@/organisms/RunHeader`, etc.
- **Storybook** deferred to V2 per §8.4.

### 9.11 Small visual deferrals (settled by feel at implementation)

Low-stakes choices. Listed so they're not forgotten, not so they're decided now.

- Exact pixel widths of the panels between 1024–1440 px. Likely fluid with `min(360px, 25vw)` style constraints.
- Whether `EventPayloadViewer` uses a third-party JSON viewer or a custom one. Default: custom, ~80 LOC, full control over styling and copy-on-click.
- Whether `MiniFeed` retains exactly 5 events or fades older ones with a height cap. Decided in implementation by feel.
- Animation easing curves beyond `easeOut`. Default `cubic-bezier(0.4, 0, 0.2, 1)` (Material-standard).
- Whether `ConfidenceMeter` bars use color or stay monochrome. Default: monochrome, with the final-confidence bar in `--accent`. Color invites premature semantic readings.

### 9.12 Relative-time formatting (`lib/format.ts`)

A single function `formatRelative(date: Date | string, now = new Date()): string` is the only allowed way to render a timestamp in the UI. Centralized so the rule is uniform across `RunRow`, `RunHeader`, `EventNode`, and `TrustSummary`.

| Δ (`now − date`) | Output |
|---|---|
| < 60 s | *"just now"* |
| < 60 m | *"<n>m ago"* |
| < 24 h | *"<n>h ago"* |
| < 7 d | *"<n>d ago"* |
| ≥ 7 d, same calendar year as `now` | *"MMM D"* (e.g. *"Mar 14"*) |
| different calendar year | *"MMM D, YYYY"* (e.g. *"Mar 14, 2024"*) |

The rendered string is always wrapped in a `<Tooltip>` whose content is the ISO 8601 absolute timestamp (`2025-03-14T09:42:11Z`). Auditability requires the exact time be one keyboard-focus away.

### 9.13 Sticky TL;DR (structured answers)

When the rendered answer is `output_format = structured`, the **TL;DR** section of `AnswerRenderer` becomes `position: sticky; top: 0` inside the scrollable answer container. This is the only sticky element inside C6. Plain-prose answers are not affected. Implementation: 1 CSS class + 1 conditional on `output_format`.

### 9.14 OutcomeBar visual rule

`OutcomeBar` is a 4 px-tall solid color strip at the very top of `CenterPanel` rendered on every terminal state (C6–C10). It uses the same `--semantic-*` token as the `StopReasonBadge`, so the outcome is recognizable peripherally before the user reads any text. Not animated; not interactive. Hidden on non-terminal states.

### 9.15 Demo-mode slowdown environment variable

`VITE_DEMO_SLOWDOWN` is a build-time / runtime numeric env var (default `1`). When > 1, the client deliberately delays the rendering of each incoming SSE event by `(N − 1) × natural_inter_event_delay`, so a 2-second run on a fast back-end demos as 4 seconds with `VITE_DEMO_SLOWDOWN=2`. Useful when the reviewer's demo machine is too fast to read the live trace. Wired only into `useEventStream.ts` (single place). Not surfaced anywhere in the UI — purely a developer / demo affordance, documented in `README.md`. Stripped at build time in production builds (Vite's `import.meta.env.PROD` gate).

### 9.16 Responsive strategy (V1)

Responsive is a V1 requirement, not an afterthought. The whole component tree is viewport-agnostic; only `AppShell` knows about breakpoints.

**Breakpoints** (Tailwind v4 defaults, used as semantic names — not as media queries spread across components):

| Name | Range | Trigger class | Source of truth |
|---|---|---|---|
| `mobile` | < 768 px | (none / default) | `useViewport().breakpoint === "mobile"` |
| `tablet` | 768–1023 px | `md:` | `useViewport().breakpoint === "tablet"` |
| `desktop` | ≥ 1024 px | `lg:` | `useViewport().breakpoint === "desktop"` |

`useViewport()` listens to `window.resize` with a 150 ms debounce and re-emits a stable string discriminant. Components below `AppShell` **should not** read it; if a child needs responsive behavior, lift the decision to `AppShell` and pass it as a prop or a slot variant. This keeps atomic-design layers (§8) clean.

**Layout rules per breakpoint:**

| Surface | Mobile | Tablet | Desktop |
|---|---|---|---|
| `HistoryPanel` | `HistorySheet` drawer (left), trigger in top-bar | `HistorySheet` drawer (left), trigger in top-bar | inline, 260 px |
| `CenterPanel` | full viewport width, 100% of `<main>` | flex: 1, ~Center+Trace = full | flex: 1 |
| `TracePanel` | `TraceSheet` drawer (right), trigger in top-bar | inline, 320 px | inline, 360 px |
| `MobileTopBar` | visible, 48 px sticky | visible, 48 px sticky | not rendered |
| Modals (`LoginModal`, fork dialog) | full-screen sheet from bottom | centered modal, max 90vw | centered modal, fixed widths |

**Touch target rule.** At `mobile` and `tablet`, every interactive element must satisfy a minimum 44 × 44 px tap area (Apple HIG, WCAG 2.5.5 AAA). Achieved via a `touch-friendly` Tailwind variant applied to `Button`, `IconButton`, `RunRow`, `Checkbox`, `Pill`, `SuggestionChip`, `ForkButton`, `CompareButton`. Hit area can extend beyond the visual bounds with `padding` + `relative` + `::before` overlays where the visual stays compact (e.g. `Checkbox`).

**Tables and wide content.** The structured-answer `Claims table` (C6), `EvidenceDiff` and `OutcomeDiff` (C12) are the only intrinsically wide surfaces. At mobile + tablet they are wrapped in a horizontal-scroll container with a soft fade on the right edge to signal overflow, and a `KeyboardHint` *"swipe →"* line below at mobile only.

**Sticky TL;DR (§9.13)** keeps the same behavior at every breakpoint — the answer's TL;DR pins to the top of the answer body, which on mobile is the same scroll container as the center body.

**Sheet behavior.** Both drawers (`HistorySheet`, `TraceSheet`) use shadcn `Sheet` with `side="left"` and `side="right"`. Opening one closes the other (mutually exclusive). Backdrop tap closes. `Esc` key closes. State is **ephemeral** (not persisted across reloads) — the user re-opens the drawer they want on each visit. Scroll position inside the drawer is preserved while it remains mounted in the session.

**Animation reduced-motion.** Drawer slide animations honor `prefers-reduced-motion: reduce` and degrade to instant open/close.

**Implementation cost.** Estimated **~6–8 h** on top of the desktop build: `useViewport` (~30 LOC), `MobileTopBar` (~60 LOC), two `Sheet` wrappers (~40 LOC each), the touch-target Tailwind variant (~20 LOC), table horizontal-scroll wrappers (~30 LOC), real-device QA on iOS Safari + Android Chrome (~2 h). Folded into the V1 build budget.

**What is still V2** (responsive does not change these):
- Native apps.
- Offline mode.
- PWA install / home-screen icon.
- Mobile-specific gestures beyond tap + horizontal scroll (no swipe-to-fork, no pinch-to-zoom on the trace).
- Landscape-optimized split views on phone.

---

## 10. One-paragraph defense for the pair session

> *"V1 ships three panels because the product is a research inspector, not a chat. The center is where the run happens; the right is where you audit it; the left is where you find it again or compare it. Every visible piece maps to a documented requirement — the type disclosure is RF-06, the fork button on decision events is RF-03, the confidence meter is the user-facing surface of the confidence calculation document, the badge in the run header is the first-class stop reason of RF-02. Polish was constrained to L2: layout, hierarchy, restraint. No mobile, no light mode, no notifications, no avatars. The single line a designer would push back on — 'where are the suggestion chips?' — was deliberately replaced by the type disclosure, because surfacing what the system will not answer is part of knowing when to stop."*
