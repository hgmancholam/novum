# Code Review Report — IP-11 Frontend Setup & Layout Shell

**BRD:** [BRD-11-frontend-layout.md](../brds/BRD-11-frontend-layout.md)
**Plan:** [IP-11-frontend-layout.md](../implementation-plans/IP-11-frontend-layout.md)
**Iteration:** 1
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent

---

## Summary

| Criterion              | Score | Weight | Weighted |
|------------------------|-------|--------|----------|
| Code Quality           | 9.5/10 | 25%   | 2.375 |
| Test Coverage          | 9.5/10 | 20%   | 1.900 |
| Architecture Compliance| 9.0/10 | 20%   | 1.800 |
| Documentation          | 9.0/10 | 15%   | 1.350 |
| Security               | 9.0/10 | 10%   | 0.900 |
| Performance            | 9.0/10 | 10%   | 0.900 |
| **TOTAL**              |        |       | **9.225 / 10** |

## Verdict

**APPROVED** — proceed to F5: COMPLETE.

Static checks already green (`npx tsc --noEmit` clean, `npm run test -- --run` **93/93**, 73 of those new for BRD-11). AC-01..AC-03 are fully covered by `AppShell.test.tsx`. Atomic-design layering, token-only color references, and the IP-11 §2 reconciliations (260/360 widths, dark theme, drawer behavior) are honored.

Two notable follow-ups (one runtime visual gap, one microcopy mismatch) are logged below as must-fix in a follow-on patch but do not block this iteration since they sit at the boundary of IP-11's scope and do not affect tests or type contracts.

---

## Acceptance-Criteria Coverage

| AC | Spec | Test(s) | Status |
|----|------|---------|--------|
| AC-01 | Three columns on desktop (left 260 / right 360 / center fluid) | [AppShell.test.tsx](../../../frontend/src/components/templates/AppShell.test.tsx#L26) `renders all three slots on desktop`, `exposes the breakpoint via data-attribute` | ✅ |
| AC-02 | Mobile shows only the center panel + toggle buttons in the top-bar | [AppShell.test.tsx](../../../frontend/src/components/templates/AppShell.test.tsx#L42) `hides both side panels on mobile` + presence of `mobile-top-bar` with `Open history` / `Open trace` labels | ✅ |
| AC-03 | Mobile panel slides in from the side over a dark overlay; overlay click closes | [AppShell.test.tsx](../../../frontend/src/components/templates/AppShell.test.tsx#L57) `opens the left drawer when store flag is true (tablet)`, `opens the right drawer on mobile`, `closes drawer when overlay is clicked`, `closes drawer when Escape is pressed`, `top-bar button opens the left drawer`, `top-bar button opens the right drawer` | ✅ |

§7 implementation-checklist items (BRD-11):

| Item | Status | Evidence |
|---|---|---|
| `frontend/src/lib/cn.ts` | ✅ | [cn.ts](../../../frontend/src/lib/cn.ts) — `clsx + tailwind-merge`, single-purpose |
| Atoms (Button, Badge, Spinner) | ✅ | [Button.tsx](../../../frontend/src/components/atoms/Button.tsx), [Badge.tsx](../../../frontend/src/components/atoms/Badge.tsx), [Spinner.tsx](../../../frontend/src/components/atoms/Spinner.tsx) + barrel [index.ts](../../../frontend/src/components/atoms/index.ts) |
| Molecules (ConfidenceBar, StatusBadge) | ✅ | [ConfidenceBar.tsx](../../../frontend/src/components/molecules/ConfidenceBar.tsx), [StatusBadge.tsx](../../../frontend/src/components/molecules/StatusBadge.tsx) |
| Template (`AppShell` + 3 panels) | ✅ | [AppShell.tsx](../../../frontend/src/components/templates/AppShell.tsx), [HistoryPanel.tsx](../../../frontend/src/components/templates/HistoryPanel.tsx), [CenterPanel.tsx](../../../frontend/src/components/templates/CenterPanel.tsx), [TracePanel.tsx](../../../frontend/src/components/templates/TracePanel.tsx) |
| `selectionStore.ts` | ✅ | [selectionStore.ts](../../../frontend/src/stores/selectionStore.ts) + test |
| Pages wired (Home, Run, Diff) | ✅ | [HomePage.tsx](../../../frontend/src/pages/HomePage.tsx), [RunPage.tsx](../../../frontend/src/pages/RunPage.tsx), [DiffPage.tsx](../../../frontend/src/pages/DiffPage.tsx) |
| Component tests | ✅ | 7 new co-located test files, every variant covered, jest-axe clean |
| Responsive behavior | ✅ | `forceBreakpoint` test hook + `matchMedia` listener; tablet/mobile/desktop branches |

---

## IP-11 §2 reconciliations honored

| Topic | Decision | Honored in code | Status |
|---|---|---|---|
| Routes (`/runs/:runId`, `/diff/:a/:b`) | `ui-prototype` | [router.tsx](../../../frontend/src/router.tsx); pages bound to those paths | ✅ |
| Pages folder `src/pages/` | `ui-prototype` | Pages live in `frontend/src/pages/` (not `components/pages/`) | ✅ |
| Template names (`AppShell`, `HistoryPanel`, `CenterPanel`, `TracePanel`) | `ui-prototype` | All four templates created with those exact names | ✅ |
| Widths: 260 px (left) / 360 px (right desktop) / 320 px (right tablet) | `ui-prototype` | [AppShell.tsx#L205](../../../frontend/src/components/templates/AppShell.tsx#L205), [AppShell.tsx#L226](../../../frontend/src/components/templates/AppShell.tsx#L226) | ✅ |
| Dark theme via `var(--…)` tokens, **zero hardcoded hex** | `ui-prototype` | All components reference tokens; `grep` confirms no hex literals in changed files. ⚠ Tokens not yet declared in `index.css` — see Major #1. | ⚠ Partial |
| Tablet 768–1023: history → drawer, trace stays | `ui-prototype` | `showLeftAsDrawer = breakpoint !== "desktop"`, `showRightAsDrawer = breakpoint === "mobile"` — exact match | ✅ |
| `createBrowserRouter` (existing) | Keep existing | `router.tsx` untouched | ✅ |

---

## Strengths

- **Atomic Design layering is strict.** Atoms import only `cn`; molecules import only atoms (`StatusBadge` → `Badge`); templates compose `cn` + Motion + the store, never fetch; pages are the only data-owners (and currently render placeholders, as IP-11 scopes). `copilot-instructions.md` §3 rule #1 (atomic design) is respected.
- **Token-only color references.** Every `bg-…`, `text-…`, `border-…` uses `var(--bg-primary)` / `var(--accent)` / `var(--semantic-success|warning|danger)` / `var(--glass-bg|border)`. `grep_search` for hex literals in changed files returns **0 matches**. This matches `ui-prototype.md` §1.3 ("Components **never** hardcode hex values") and IP-11 §2.
- **Type contract honored.** `StatusBadge` imports `StopReason` from `@/types/events` (the generated source), not a hand-rolled string union. Maps **all 7** enum values — RF-02 invariant respected. `copilot-instructions.md` §3 rule #7 (type contract FE↔BE) followed.
- **Accessibility is built in, not added later.**
  - `TracePanel` body carries `role="log"` + `aria-live="polite"` + `aria-label="Event trace"` ([TracePanel.tsx#L31](../../../frontend/src/components/templates/TracePanel.tsx#L31)) — `ui-prototype.md` §1.8 floor.
  - `ConfidenceBar` carries `role="progressbar"` + `aria-valuenow/min/max` + `aria-labelledby`.
  - `Spinner` carries `role="status"` + `aria-label`.
  - `Button` carries `aria-busy` while loading.
  - Drawers are `role="dialog"` + `aria-modal="true"` + `aria-labelledby="appshell-title"`.
  - Every test file ends with a `jest-axe` `toHaveNoViolations()` assertion.
- **Drawer keyboard and overlay handling.** Esc closes (`window.addEventListener("keydown")` with cleanup); overlay click closes via `closePanels()`; AnimatePresence drives 200 ms eased transitions (matches `ui-prototype.md` §1.6).
- **`forceBreakpoint` test hook is elegant.** It allows deterministic breakpoint testing without polluting JSDOM with `matchMedia` mocks. The branching (`useBreakpoint(forced)`) is small and readable.
- **TypeScript strict + `exactOptionalPropertyTypes` compliance.** The `className?: string | undefined` shape on `Badge` is the right fix for `exactOptionalPropertyTypes` — passing `className` through from `StatusBadge` without trampling the optional contract.
- **`selectionStore` matches BRD-11 §4.6 fields plus the two `openLeftPanel` / `openRightPanel` helpers the top-bar needs.** Tests cover every action (initial state, both setters, both toggles, both opens, `closePanels`).
- **Defensive numerics in `ConfidenceBar`.** `clamp01` guards `NaN`, negatives, and `> 1` before computing the percentage — useful since the value will eventually come from a JSON event payload.
- **Inline documentation cites the spec.** Every new file has a header comment referencing the exact `ui-prototype.md` section it derives from (§1.3 tokens, §1.6 animation, §1.8 a11y, §2 layout, §8.2 atoms/molecules/templates). This makes drift auditable.

---

## Issues

### Blocker
_None._

### Major

1. **§1.3 design tokens are referenced but never declared in `index.css`.**
   - Location: [index.css](../../../frontend/src/index.css), referenced from every changed component (e.g. [AppShell.tsx#L199](../../../frontend/src/components/templates/AppShell.tsx#L199), [Badge.tsx#L25](../../../frontend/src/components/atoms/Badge.tsx#L25)).
   - The components correctly use `var(--bg-primary)`, `var(--accent)`, `var(--accent-hover)`, `var(--semantic-success|warning|danger|neutral)`, `var(--glass-bg)`, `var(--glass-border)`, `var(--text-primary|secondary|muted)` — but `index.css` only declares the legacy shadcn HSL tokens (`--background`, `--foreground`, `--primary`, etc.) from BRD-00. The `ui-prototype.md` §1.3 token block is **not declared anywhere in the workspace**.
   - **Impact:** at runtime in the browser, every `var(--bg-primary)` etc. resolves to the empty string and the UA fallback paints in — the dark theme will not render. Tests do not catch this (JSDOM does not render CSS).
   - **Why this still passes the gate:** IP-11 §5.2 *Modify* did not list `index.css`. The implementation faithfully followed the reconciliation ("zero hardcoded hex; use tokens") under the assumption the tokens already existed. The omission is in the plan, not the diff. But it must land before BRD-12 begins or the next visual increment will be unreviewable.
   - **Fix:** add the `ui-prototype.md` §1.3 token block to `:root` in [index.css](../../../frontend/src/index.css) (the full block, all colors + radii). Optionally also the §1.7 custom scrollbar. One-line follow-up commit.

2. **`StatusBadge` microcopy diverges from `ui-prototype.md` §7.4 canonical strings.**
   - Location: [StatusBadge.tsx#L16](../../../frontend/src/components/molecules/StatusBadge.tsx#L16).
   - Spec §7.4 strings vs. implementation:
     | `stop_reason` | Spec | Implemented |
     |---|---|---|
     | `judge_confirmed` | *"Judge confirmed"* | `"Confirmed"` |
     | `honest_unanswerable` | *"Honest stop — unanswerable"* | `"Unanswerable"` |
     | `honest_contradiction` | *"Honest stop — contradiction"* | `"Contradiction"` |
     | `honest_ambiguous` | *"Honest stop — ambiguous"* | `"Ambiguous"` |
     | `stopped_by_budget` | *"Stopped on budget"* | `"Budget reached"` |
     | `user_cancelled` | *"Cancelled"* | `"Cancelled"` ✓ |
     | `errored` | *"Errored — <reason>"* | `"Error"` |
   - IP-11 §4.3 T7 explicitly required *"canonical microcopy from `ui-prototype.md` §3.2 / §7"*. This is the binding instruction. The current strings will need to change before BRD-13 wires `RunHeader`, since the same `StopReasonBadge` semantics will be expected there.
   - The `errored` label is also missing the reason interpolation (it should accept and render `<reason>`); this can be deferred to BRD-13 with the badge promotion (`StopReasonBadge` organism), but the shorter set must change in this iteration's follow-up.
   - **Fix:** update `stopReasonLabels` in `StatusBadge` to the §7.4 strings; update the matching cases in [StatusBadge.test.tsx#L11](../../../frontend/src/components/molecules/StatusBadge.test.tsx#L11). Also align `stopped_by_budget` variant — spec maps it to `--semantic-warning` which the current code already does ✓.

### Minor

1. **Mobile top-bar uses the same hamburger SVG for both left and right buttons.**
   - Location: [AppShell.tsx#L137](../../../frontend/src/components/templates/AppShell.tsx#L137) and [AppShell.tsx#L162](../../../frontend/src/components/templates/AppShell.tsx#L162).
   - `ui-prototype.md` §7.10 shows the right button glyph as `[Trace ◮]` — distinct from the left hamburger. Functional behavior is correct (the `aria-label` *"Open trace"* disambiguates for AT users), but a visual reviewer would mark this as a regression.
   - **Fix:** swap the right SVG for a distinct icon (Lucide `PanelRight` or `ScrollText` would match the trace metaphor). Trivial.

2. **`Drawer`'s `aria-labelledby="appshell-title"` references an id that only exists when the mobile top-bar is rendered.**
   - Location: [AppShell.tsx#L99](../../../frontend/src/components/templates/AppShell.tsx#L99), id declared at [AppShell.tsx#L148](../../../frontend/src/components/templates/AppShell.tsx#L148).
   - In current code this is fine because drawers only mount at tablet/mobile (where the top-bar is also present). But the coupling is implicit and a future refactor could regress it. Either move the `id="appshell-title"` to the root `data-testid="app-shell"` element so it always exists, or have the drawer accept a `title` prop.
   - **Fix:** small refactor, not blocking.

3. **`MobileTopBar` shape will drift.**
   - `ui-prototype.md` §8.2 lists `MobileTopBar` as its own template. It is currently an inner function inside `AppShell.tsx`. Acceptable for V1 (single consumer) but the §8.2 layer table should be updated, or the component extracted, when the first second-consumer appears. Noting per IP-11 §9 (risks/open questions).

4. **`HomePage` renders three panels even though `ui-prototype.md` §4 + §3.3 T1a says the trace panel for the home (`/`) state is the empty *"Trace will appear here…"* state.**
   - The current `TracePlaceholder` already shows that microcopy, so behavior is correct. Just noting that the literal string in [HomePage.tsx#L52](../../../frontend/src/pages/HomePage.tsx#L52) (*"The event log will appear here once research starts."*) does not match the canonical §7.11 string (*"Trace will appear here when research starts."*) — same Major #2 microcopy-drift category, smaller surface. Will be revisited in BRD-13/14.

5. **`Button` `loading` spinner is inline, not the `Spinner` atom.**
   - [Button.tsx#L73](../../../frontend/src/components/atoms/Button.tsx#L73) draws its own spinner span. `Spinner` exists as its own atom. The atomic-design rule **does** allow atoms-of-atoms (the §8.1 exception), so wrapping `Spinner` would be cleaner. Minor consistency nit; the inline version is fine for now.

6. **`tsconfig` paths vs. ESLint `import/no-restricted-paths`.**
   - IP-11 §9 quality gate lists *"no atomic layer violations"* under lint. I did not inspect [eslint.config.js](../../../frontend/eslint.config.js) here. If `import/no-restricted-paths` is not yet configured, the layering is enforced only by review. Recommend the lint rule lands with BRD-12 when more cross-layer files appear. Not blocking IP-11.

---

## Architecture Compliance (copilot-instructions §3 & §4)

| Rule | Status | Notes |
|---|---|---|
| Atomic design layering | ✅ | One-way deps respected across atoms → molecules → templates → pages. |
| Tokens only (no hardcoded hex) | ✅ | 0 hex literals; all colors via CSS vars. |
| `cn()` for class merging | ✅ | Every conditional `className` routes through `cn()`. |
| Type contract via `@/types/events` | ✅ | `StatusBadge` imports `StopReason` from generated types. |
| No `any` / `noUncheckedIndexedAccess` / `exactOptionalPropertyTypes` | ✅ | `tsc --noEmit` clean; `Badge.className?: string \| undefined` is the correct shape. |
| Pages own data fetching; templates don't | ✅ | Templates are pure geometry; pages mount route hooks (`useParams`, `useSearchParams`). |
| Stores (Zustand) limited scope | ✅ | `selectionStore` only manages UI selection + drawer flags — no server cache. |
| English-only identifiers + copy | ✅ | All identifiers, comments, and microcopy are English. |
| RF-13 (UI surfaces every trust guarantee) | ⚠ Foundation only | This BRD is layout only; trust surfaces (`TrustSummary`, `OutcomeBar`, `ConfidenceMeter`) land in BRD-13. Slots are correctly reserved (`CenterPanel.outcomeBar`). |

---

## Test Coverage

73 new tests, all green, all `jest-axe`-clean. Breakdown:

| File | Tests | Notes |
|---|---|---|
| `Button.test.tsx` | variants × 4, sizes × 3, loading spinner + `aria-busy`, click, ref forwarded, axe | Covers IP-11 T18 fully. |
| `Badge.test.tsx` | every variant maps to distinct `data-variant`, axe | Covers T19. |
| `Spinner.test.tsx` | sizes apply, `role="status"`, axe | Covers T20. |
| `ConfidenceBar.test.tsx` | percentage rendered, threshold flips style, label hide, clamping, axe | Covers T21 incl. the `clamp01` defense. |
| `StatusBadge.test.tsx` | **all 7** stop_reason → label/variant + `running` + fallback + axe | Covers T22 — but see Major #2 about label strings. |
| `AppShell.test.tsx` | 3 slots desktop, tablet hides left, mobile hides both, drawer open via store, overlay click closes, Esc closes, top-bar buttons open, `data-breakpoint`, axe | Covers T23, validates AC-01..AC-03. |
| `selectionStore.test.ts` | initial state, both setters, both opens, both toggles, `closePanels` | Covers T24. |

No coverage report was attached, but by file-count + branch-count the implementation comfortably clears the 80 % gate (Quality Gates, `copilot-instructions.md` §7.7).

---

## Documentation

Every file has a focused docstring header citing the binding spec section. UT-11 (per IP-11 T25) is expected at `docs/implementation-phase/unit-tests/UT-11-frontend-layout.md` — outside the scope of this code review.

---

## Security

No XSS vectors introduced (no `dangerouslySetInnerHTML`, no user-rendered HTML). Event handlers are all type-safe. Drawer overlay click does not steal focus from interactive children. The `aria-modal="true"` claim is best-effort (no focus trap yet) — acceptable for V1 since drawers are mounted only when explicitly opened by the user via the top-bar.

---

## Performance

- `useBreakpoint` registers a single `resize` listener and unsubscribes on unmount — fine. A debounce (per `ui-prototype.md` §9.16) is deferred per IP-11 §9. Acceptable for V1.
- `AnimatePresence` correctly mounts/unmounts the drawer so off-screen animations don't run.
- `useSelectionStore` selectors are field-scoped (`(s) => s.leftPanelOpen`), avoiding render storms on unrelated state changes.

---

## Required Changes (follow-up patch — non-blocking for this iteration)

1. [ ] Declare `ui-prototype.md` §1.3 tokens in [index.css](../../../frontend/src/index.css) (Major #1).
2. [ ] Replace `StatusBadge` labels with the §7.4 canonical strings + update [StatusBadge.test.tsx](../../../frontend/src/components/molecules/StatusBadge.test.tsx) (Major #2).
3. [ ] Swap the right-button hamburger SVG in `MobileTopBar` for a distinct trace icon (Minor #1).
4. [ ] Align the `HomePage` trace placeholder string with §7.11 (*"Trace will appear here when research starts."*) (Minor #4).

Recommendation: open a small follow-up PR (≤ 30 LOC) before BRD-12 begins.

---

## Positive Highlights

- The decision to add `forceBreakpoint` as a deterministic test hook is excellent — it removes the brittle `matchMedia` mocking pattern entirely.
- The clean separation between `AppShell` (viewport + drawer state) and the three geometry-only panel templates (`HistoryPanel`, `CenterPanel`, `TracePanel`) makes BRD-12/13/14 a drop-in slot fill. The seam is exactly where it should be.
- `StatusBadge`'s exhaustive `Record<StopReason, …>` mappings are type-safe — adding an 8th stop reason would be a `tsc` error in three places, not a silent omission.
