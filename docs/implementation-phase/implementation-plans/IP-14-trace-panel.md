# IP-14: Trace Panel (Right Sidebar)

**Source BRD:** [BRD-14-trace-panel.md](../brds/BRD-14-trace-panel.md)
**Authoritative UI spec:** [ui-prototype.md §3.3](../../understanding-phase/ui-prototype.md)
**Status:** Draft (F2)
**Date:** 2026-05-26
**Author:** Orchestrator

---

## 1. Why this plan deviates from BRD-14 (corrections)

The BRD-14 draft was written against a hypothetical event taxonomy that does not match the implemented backend. This plan reconciles it with the **source of truth** (architectural rule §7):

| BRD-14 (draft) | Corrected source | Resolution |
|---|---|---|
| `SearchStarted`, `SourceQueried`, `EvidenceCollected`, `AnswerDrafted`, `JudgeVerdict`, `ConfidenceCalculated`, `CriticFeedback`, `ResumeStarted`, `ForkCreated` | `frontend/src/types/events.ts` (auto-generated from Pydantic) | Use the real 19-type taxonomy: `QuestionAsked`, `PlanCreated`, `PlanCritiqued`, `PlanRevised`, `ToolCalled`, `EvidenceAdded`, `ClaimCovered`, `ClaimUncoverable`, `SourceFailed`, `AmbiguityDetected`, `ContradictionDetected`, `ContradictionResolved`, `UserContextChallenged`, `JudgeRuled`, `ConfidenceMismatch`, `AgentErrored`, `ResumedAfterError`, `ResumedAfterCancel`, `Stopped`. |
| Emoji icons (❓📋🔍 …) | `ui-prototype.md` §3.3 icon table + §1.9 iconography convention (Lucide only) | Use Lucide icons exclusively (`MessageSquare`, `Compass`, `Search`, `FileText`, `CheckCircle2`, `AlertTriangle`, `HelpCircle`, `XCircle`, `Gavel`, `MessageSquareWarning`, `ShieldCheck`, `AlertOctagon`, `RotateCw`, `Flag`). |
| `bg-blue-50`, `border-purple-200`, raw Tailwind palette | `ui-prototype.md` §1 design tokens + BRD-11 (token-only styling) | Only `--bg-*`, `--text-*`, `--semantic-*`, `--glass-*` CSS custom properties. |
| Single `T1 Empty` state | Prototype §3.3 splits into **T1a** (no run) and **T1b** (run started, awaiting events → render `PlanPreview` + first `QuestionAsked` node) | Implement both. |
| `T4 Diff view` (cross-run side-by-side `select` of any event) | Prototype §3.3 reclassifies: **T4 = inline expand of one event**; **T5 = cross-run diff via DiffView** (route `/diff/<a>/<b>`, owned by BRD-15) | T4 inline expand is in scope. **T5 cross-run diff is deferred to BRD-15** (matches BRD-15 §1 fork-resume scope). |
| Auto-scroll always-on (`scrollIntoView({behavior: "smooth"})`) | Prototype §3.3 — "auto-scroll **sticky-when-at-bottom**" | Track whether user is at bottom; only auto-scroll when sticky. Expose a `Jump to latest` pill when not sticky. |
| `JudgeRuled` rendered compact by default | Prototype §3.3 — "**`JudgeRuled` always renders expanded by default**" | Hard-code initial expanded state for `JudgeRuled`. |
| `isForkable(type)` UI hint, no behavior | Out of scope here — fork action and the `ForkButton` belong to BRD-15 | Reserve a `<ForkSlot>` placeholder on decision events but **do not** ship a working button. |

These corrections are mandatory; the originating BRD-14 will be updated in a follow-up (out of scope for F2).

---

## 2. Scope

### In scope (this iteration)
- States **T1a, T1b, T2, T3, T4**.
- Wiring on routes `/` (T1a) and `/runs/:runId` (T1b → T2 → T3, with T4 inline expand on any node).
- Data source: existing `useRunStream` hook (IP-10). No backend changes.
- Stop-trigger handling: when `Stopped`/`cancelled` arrives the timeline transitions T2 → T3 (frozen) and the header drops the "Live" indicator.

### Deferred
- **T5 cross-run diff** → BRD-15 (`/diff/<a>/<b>` route).
- **`ForkButton` behavior** → BRD-15. The decision-event slot reserved here just renders `null` for now.
- Event search, filtering, virtualization, export → V2 (BRD-14 §10 / §9 risks).
- `TraceSheet` mobile/tablet drawer variant → out of scope (template already exists; this plan only fills the desktop body).

---

## 3. Architectural decisions

1. **Geometry vs content split.** `templates/TracePanel` (already exists) keeps owning geometry + `role="log"`/`aria-live="polite"`. Content is injected via its `header` and `body` slots from a new page-level container.
2. **New container `pages/TracePanelContainer.tsx`** owns the data hook (`useRunStream`). Per ESLint `import/no-restricted-paths`, only `pages/` may call data hooks. Organisms remain presentational.
3. **Atomic layering** strictly enforced:
   - **atoms**: `EventPayloadViewer` (JSON tree), `EventIcon` (Lucide wrapper keyed by event type), `JumpToLatestPill`.
   - **molecules**: `EventNode` (compact + expanded), `PlanPreview` (T1b numbered list), `TraceEmpty` (T1a text).
   - **organisms**: `TraceTimeline` (list, sticky-bottom auto-scroll, expansion state), `TraceHeader` (title + live indicator + event count).
   - **page container**: `TracePanelContainer` wires `useRunStream` to the template.
4. **State ownership.** `expandedEventIds: Set<string | number>` lives in `TraceTimeline` (the only stateful organism). The `Set` is keyed by `event.id` when present, otherwise by index. `JudgeRuled` events are seeded into the set on arrival.
5. **Sticky-when-at-bottom auto-scroll** implemented with a single `IntersectionObserver` on a sentinel `<div ref={bottomRef}/>`. When the sentinel is intersecting the viewport → sticky = true → auto-scroll new events into view. When not sticky and new events arrive → show `Jump to latest` pill.
6. **Icon + color mapping** lives in a single module `lib/eventVisuals.ts` (icon + semantic color token per event type). This is the only place the mapping exists; tests assert exhaustiveness against `EventType`.
7. **`useRunStream` reuse.** No new hook. The container subscribes only when `runId !== undefined`. On HomePage (T1a), the container is **not** mounted — `RunPage` passes the live container, `HomePage` passes a static `TraceEmpty` body.
8. **No new event types over the SSE wire.** Pure consumer of `useRunStream` output.

---

## 4. Task breakdown

| # | Layer | File | Purpose |
|---|---|---|---|
| 1 | lib | `frontend/src/lib/eventVisuals.ts` | Map `EventType → { Icon: LucideIcon; tone: "info" | "success" | "warn" | "danger" | "neutral" | "judge" | "decision" }`. Exhaustive switch typed against `EventType` union. |
| 2 | atom | `frontend/src/components/atoms/EventIcon.tsx` | Render a Lucide icon for a given event type using `eventVisuals.ts`. `aria-hidden`. Size prop. |
| 3 | atom | `frontend/src/components/atoms/EventPayloadViewer.tsx` | Colorized JSON tree, collapsible at the top-level keys. No external dep; recursive renderer with keyed entries; `<pre>`-style mono font; respects `--text-*` tokens. ≤ ~120 LOC. |
| 4 | atom | `frontend/src/components/atoms/JumpToLatestPill.tsx` | Floating button (semantic-info background, glass border) with chevron-down + "Jump to latest" label. Shown over the timeline when not sticky. |
| 5 | molecule | `frontend/src/components/molecules/EventNode.tsx` | Compact: icon + type + 1-line summary (derived per event type) + meta line (`step N · Δt ms`). Expanded: same header + `EventPayloadViewer` underneath. Optional `forkSlot?: ReactNode` rendered top-right (will be filled by BRD-15). Click toggles `onToggle(id)`. `aria-expanded` on the toggle button. |
| 6 | molecule | `frontend/src/components/molecules/PlanPreview.tsx` | T1b numbered list of agent steps (classify → plan → search → evaluate → judge → answer-or-honest-stop). Strings live verbatim from `ui-prototype.md` §3.3. |
| 7 | molecule | `frontend/src/components/molecules/TraceEmpty.tsx` | T1a muted text: *"Trace will appear here when research starts."* |
| 8 | organism | `frontend/src/components/organisms/TraceHeader.tsx` | Title "Trace" + event count subtitle + live indicator dot (`--semantic-success`, animate-pulse) when `isStreaming`. |
| 9 | organism | `frontend/src/components/organisms/TraceTimeline.tsx` | Owns `expandedEventIds: Set<string \| number>`, IntersectionObserver sentinel, sticky-bottom auto-scroll, seeds `JudgeRuled` expanded. Renders `EventNode[]`. Hosts `JumpToLatestPill` overlay. Mounts a `PlanPreview` above the list iff `events.length === 1 && events[0].type === "QuestionAsked"` (T1b). |
| 10 | page | `frontend/src/pages/TracePanelContainer.tsx` | `const { events, isComplete, isConnected } = useRunStream({ runId })`. Renders `templates/TracePanel` with `TraceHeader` in header slot and either `TraceTimeline` (events.length > 0) or `PlanPreview` placeholder (run loaded but no events yet) in body. |
| 11 | page | `frontend/src/pages/RunPage.tsx` | Replace the stub `TracePanel` body with `<TracePanelContainer />`. |
| 12 | page | `frontend/src/pages/HomePage.tsx` | Pass `<TraceEmpty />` as TracePanel body (T1a). No SSE subscription. |
| 13 | exports | `frontend/src/components/{atoms,molecules,organisms}/index.ts` | Re-export new components. |
| 14 | tests | `*.test.tsx` co-located with each component | Vitest + RTL + jest-axe. Coverage ≥ 80% (L-002). Use **prop-driven** elapsed/state assertions per L-011 — avoid fake timers where a prop suffices. |
| 15 | tests | `TracePanelContainer.test.tsx` | Mocks `useRunStream`; asserts T1b → T2 → T3 transitions and live-indicator toggling. |

**Estimated LOC** (excluding tests): ~600 LOC across 10 source files. Tests roughly 1× the source.

---

## 5. State machine implementation map

| Prototype state | Trigger | Render path |
|---|---|---|
| **T1a** | `HomePage` (no `runId`) | `HomePage` → `AppShell.right = <TracePanel body={<TraceEmpty/>} />`. No data hook mounted. |
| **T1b** | `RunPage`, `useRunStream` returned `events.length === 0` OR `events.length === 1 && events[0].type === "QuestionAsked"` | `TraceTimeline` renders `PlanPreview` (+ the single `QuestionAsked` node if present). |
| **T2** | `events.length ≥ 2` AND `!isComplete` | Full timeline, sticky-bottom auto-scroll, live indicator on. |
| **T3** | `isComplete === true` (terminal `Stopped`/`cancelled` arrived) | Same timeline; live indicator off; sticky-bottom disabled (no more events to follow). |
| **T4** | User clicks an `EventNode` | The node is toggled in `expandedEventIds`; expanded variant renders `EventPayloadViewer`. `JudgeRuled` already in the set on arrival. |
| **T5** | Out of scope | Deferred to BRD-15. |

---

## 6. Acceptance criteria mapping

| BRD-14 AC | Source state | This plan covers it |
|---|---|---|
| AC-01 Events display in chronological order (T2) | T2 | ✅ `TraceTimeline` renders `events` in arrival order with icon + type + summary per `EventNode`. |
| AC-02 Auto-scroll to latest | T2 | ✅ Sticky-bottom + IntersectionObserver. |
| AC-03 Event details expand (T3) | **T4** (corrected) | ✅ Click toggles `EventPayloadViewer`. |
| AC-04 Fork points highlighted | T3 + BRD-15 | ⚠️ `forkSlot` reserved on decision events; **button itself is BRD-15**. AC met as "highlight indicator visible"; full action deferred and noted in iter-2 of BRD-15. |

Additional ACs unlocked by the prototype correction:

| New AC (from prototype) | Plan |
|---|---|
| AC-05 T1b shows `PlanPreview` until ≥ 2 events arrived | `TraceTimeline` conditional. |
| AC-06 `JudgeRuled` arrives expanded by default | `TraceTimeline` seeds the id into `expandedEventIds`. |
| AC-07 Sticky-when-at-bottom auto-scroll (no surprise scroll-jacking) | `IntersectionObserver` sentinel; assertion: scroll up, new event arrives → sentinel not visible → no scroll change → `JumpToLatestPill` visible. |
| AC-08 Lucide-only icons, token-only colors | Lint: tests assert no `bg-(gray|blue|…)-\d` classes in the new components; visual mapping table exhaustive against `EventType`. |
| AC-09 Live indicator off in T3 | `TraceHeader` reads `isConnected && !isComplete`. |
| AC-10 Container only subscribes when `runId !== undefined` | Hook gated; HomePage uses `TraceEmpty`. |

---

## 7. RF coverage

| RF | How this plan exposes it |
|---|---|
| **RF-02** (full inspectability) | Every event from the log is rendered; payload viewer surfaces the raw JSON; nothing is hidden. |
| **RF-08** (live streaming + cancellation) | Consumes `useRunStream`; live indicator + Stopped/cancelled → T3 terminal. |
| **RF-13** (UI as trust contract) | Trace panel is the visible surface for the trust guarantees; matches §3.3 prototype. |
| **RF-03** (fork from decision points) | Slot reserved; full RF-03 surface ships in BRD-15. |

---

## 8. Tests (mandatory per L-002)

Co-located Vitest + Testing Library + jest-axe. MSW not required (container is tested with a mocked `useRunStream` import).

| File | Key assertions |
|---|---|
| `lib/eventVisuals.test.ts` | Exhaustive: every `EventType` resolves to an icon + tone; no duplicate fallthroughs. |
| `atoms/EventIcon.test.tsx` | Renders the right Lucide for a sample of event types; `aria-hidden`. |
| `atoms/EventPayloadViewer.test.tsx` | Renders primitives, arrays, nested objects; collapses by top-level key; a11y violations = 0. |
| `atoms/JumpToLatestPill.test.tsx` | Calls `onClick`; `aria-label`. |
| `molecules/EventNode.test.tsx` | Compact vs expanded; `aria-expanded` flips on click; `forkSlot` renders when provided. |
| `molecules/PlanPreview.test.tsx` | Renders all 6 prototype steps. |
| `molecules/TraceEmpty.test.tsx` | Renders the exact §3.3 microcopy string. |
| `organisms/TraceHeader.test.tsx` | Live dot shown only when `isStreaming === true`. |
| `organisms/TraceTimeline.test.tsx` | T1b condition; `JudgeRuled` arrives pre-expanded; toggle expands/collapses arbitrary node; sticky-bottom: simulate `IntersectionObserver` with a stubbed entry (use the project's existing IO polyfill pattern from history tests). |
| `pages/TracePanelContainer.test.tsx` | Mock `useRunStream` to drive `events`/`isComplete`/`isConnected`; assert T1a (no `runId`) not mounted, T1b/T2/T3 transitions. |
| `pages/RunPage` (extend existing) | TracePanel right slot now contains `TraceTimeline` not the stub paragraph. |
| `pages/HomePage` (extend existing) | TracePanel right slot contains `TraceEmpty`. |

**Coverage gate:** ≥ 80% lines + branches on every new file.

---

## 9. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `IntersectionObserver` flake in jsdom | Med | Med | Use the same stub pattern already used by history panel tests; assert via the timeline's exposed `data-sticky` attribute instead of measuring scroll. |
| Large JSON payloads slow `EventPayloadViewer` | Low | Low | Top-level collapsible-by-default; if a value > 5 KB stringified, render a "(N KB hidden, click to expand)" placeholder. |
| Lucide bundle size | Low | Low | Tree-shaken named imports only (already the project's pattern in `iconography.md`). |
| Mis-key `expandedEventIds` when events lack `id` | Med | Med | Key = `event.id ?? "idx:" + index`. Tests cover the no-id branch. |
| BRD-14 emoji+raw-color table is mis-applied | High if not flagged | High | Section 1 explicitly invalidates that table; lint test asserts no raw tailwind palette in trace components. |
| Sticky-scroll fights smooth-scroll on rapid bursts | Low | Low | Use `behavior: "instant"` when ≥ 3 events arrive within 200 ms. |
| Duplicate event ids across resume/fork | Low (V1) | Low | Set key falls back to index; resume appends, never edits (RF rule §3.4). |

---

## 10. Out of scope (explicit)

- T5 cross-run diff (`/diff/<a>/<b>`) → BRD-15.
- Functional `ForkButton` → BRD-15.
- Event filter / search / export → V2.
- Mobile `TraceSheet` drawer wiring → out of scope; template already exists, no behavior to add this iter.
- Editing or amending BRD-14 itself (the corrections in §1 are applied here; a follow-up doc PR will sync the BRD).

---

## 11. Definition of done

- All 10 new source files + 12 test files green under `npm run test -- --coverage`.
- `npm run lint`, `npm run typecheck` clean (strict, no `any`).
- `RunPage` shows the live trace; `HomePage` shows T1a placeholder.
- Reviewer score ≥ 9/10 (F4 quality gate).
- Memory bank updated: `decisions-history`, `knowledge-base-index`, and `lessons-learned` if new patterns emerged.
