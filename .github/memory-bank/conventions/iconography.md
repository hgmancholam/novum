# Iconography convention — Novum frontend

> **Binding rule** referenced from `docs/understanding-phase/ui-prototype.md` §1.9.
> Every new icon — brand or functional — MUST follow this document. No exceptions.

**Last Updated:** 2026-05-26

---

## 1. Mindset (why iconography exists in Novum)

The product is `Novum Organum` made software: **discrete evidence accumulates until it earns a continuous conclusion**. Iconography is one of the surfaces of that contract — it must:

1. **Earn its place.** An icon ships only if it backs a documented event, state, or user action (per `ui-prototype.md` §3 / §7). Decorative icons are forbidden.
2. **Tell the user when to trust and when to stop.** Stop reasons, contradictions, ambiguity, and honest stops are first-class — their icons must read pre-attentively (semantic color tokens) without forcing the user to read text first.
3. **Stay restrained.** Apple-inspired, monochrome by default, no gradients, no shadows on glyphs, no illustrations. Restraint is the brand.
4. **Match the typography stem.** Stroke weight follows DM Sans 400 — `strokeWidth={1.5}` on every functional icon. Anything thicker looks loud; anything thinner looks fragile.

---

## 2. Brand mark — non-negotiables

| Aspect | Rule |
|---|---|
| Concept | Three dots resolving into a bar — induction made visual |
| Atom | `frontend/src/components/atoms/Logo.tsx` is the **only** sanctioned brand surface |
| Files | `public/logo-mark.svg`, `public/logo.svg` (with wordmark), `public/favicon.svg` |
| Color | `currentColor` only. **Never** `--accent` (accent is reserved for user actions) |
| Animation | None in V1. A 600 ms one-shot splash is V2 |
| Placements | Favicon · `LoginModal` (M1/M1-deep) · `MobileTopBar` next to wordmark · nowhere else |
| Mutation | Geometry edits require a doc PR updating `ui-prototype.md` §1.9.1 in the same commit |

If a designer wants to "modernize" or "warm up" the mark with gradients, color, or motion: refuse. The mark is a constraint, like the trust contract.

---

## 3. Functional icon family — Lucide React, single source

**One family across the whole UI.** Mixing icon families is a build-time concern.

| Rule | Value |
|---|---|
| Family | `lucide-react` (declared in `frontend/package.json`) |
| Stroke | `strokeWidth={1.5}` |
| Sizes | `14 · 16 · 20 · 24` px only |
| Color | `currentColor` by default; `--semantic-*` only when the icon already carries result semantics |
| Accent | Allowed only when the icon **is** the user-action affordance (e.g. submit, fork, copy) |
| Animation | Only for `RunningIndicator` (loop) and `Spinner` (loop) |
| Inline SVG | Forbidden everywhere except the `Logo` atom |
| Emoji | Forbidden in production UI (allowed only in ASCII wireframes inside docs) |

Forbidden by example:
- `<svg viewBox="0 0 24 24">…</svg>` written inline inside a component (use Lucide instead).
- Importing `@heroicons/react`, `@phosphor-icons/react`, `react-icons`, or any other icon family.
- A `🚀` or `🔎` in JSX (use `Rocket` or `Search` from Lucide).
- Hex color on an icon's `stroke` or `fill` (use a token).

---

## 4. When you need a NEW icon

Follow this checklist before writing any code:

1. **Justify it.** Which event, state, or action in `ui-prototype.md` §3 / §7 does it back? If you cannot cite a section, the icon is decorative — drop it.
2. **Pick from Lucide.** Search [lucide.dev/icons](https://lucide.dev/icons). Prefer **abstract / geometric** glyphs over literal ones (e.g. `Compass` over `Map`, `Scale` over `Gavel` when balance matters).
3. **Respect the event map.** If you are adding an event type, register its icon in `ui-prototype.md` §3.3 in the same PR — do not let the map drift.
4. **Stick to the size grid.** 14 (inline text), 16 (default), 20 (header / button), 24 (modal / hero). Custom sizes are rejected at review.
5. **Use `strokeWidth={1.5}`.** Anything else gets a comment in review asking why.
6. **Token-color it.** Default is `currentColor` inheriting from the parent text class (`text-(--text-primary)` etc.). Only escalate to `--semantic-*` when the icon already encodes a result.
7. **Document it.** If the icon is reused 3+ times across components, lift it to a named atom (e.g. `EventIcon`, `StatusIcon`) and update the §8.2 atom list in `ui-prototype.md`.

---

## 5. When you need a NEW brand asset

(e.g. social card, dark-bg variant, OG image, apple-touch-icon)

1. Start from `logo-mark.svg`. Do not redraw geometry.
2. Keep the same 32×32 internal viewBox; outer padding / framing is the only thing allowed to change.
3. Allowed background tokens for framed variants: `--bg-primary` (default), `--bg-secondary`, transparent. Anything else needs a doc update.
4. Add the file to `frontend/public/`, reference it from `index.html` or the relevant manifest, and append it to the checklist in `ui-prototype.md` §1.9.4.

---

## 6. Review gate

A PR that touches iconography is rejected if:

- It imports any icon family other than `lucide-react`.
- It introduces inline `<svg>` outside the `Logo` atom.
- It hardcodes a hex value on stroke or fill.
- It animates an icon outside the two whitelisted cases (`RunningIndicator`, `Spinner`).
- It uses `--accent` on a non-interactive icon.
- It adds a brand variant without updating `ui-prototype.md` §1.9.
- It uses an emoji in a JSX render path.

This is enforceable by code review today; an ESLint rule banning inline SVG + non-Lucide imports outside `Logo.tsx` is planned (see §8.4 of `ui-prototype.md`).
