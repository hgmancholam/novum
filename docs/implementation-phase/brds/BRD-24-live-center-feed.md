# BRD-24: Live Center Feed (Claude-style)

**Document ID:** BRD-24
**Version:** 1.0
**Status:** Draft (F1 — awaiting Auditor)
**Author:** BSA Agent
**Date:** 2026-05-27
**Implementation Order:** 24 of N
**Scope:** Frontend only. No backend, schema, or event-type changes.

---

## 1. Executive Summary

Replace the static `ResearchingBanner` in the center panel with a **live, narrative feed** in the style of Anthropic's Claude research mode: a vertical rail of typed steps that grows in real time as the run emits events, each step shown with a domain-tuned Lucide icon and natural-language copy ("Searching the web for *X*", "Let me check…", "Done"). Consecutive `ToolCalled` + `EvidenceAdded` events are **grouped** into a single card with inline source rows (favicon + title + right-aligned domain). The right `TracePanel` continues to render the full structured trace in parallel and gains a `localStorage`-persisted collapse/expand toggle so users can choose how much technical detail they see. The final answer animates token-by-token (frontend-only typewriter, click-to-skip, adaptive speed) once the `Stopped` event arrives.

The work is **frontend-only**: every payload field needed by the feed (`ToolCalled.query`, `EvidenceAdded.source_url|source_title|polarity|authority_tier`, `JudgeRuled.final_confidence|rationale`, `PlanCreated.sub_claims`, `Stopped.answer_prose|stop_reason`) already exists on the wire. No backend, no schema migration, no event-type addition, no `scripts/export_types.py` rerun.

Why this matters: today the center panel hides almost everything the agent does behind a spinner. RF-13 ("UI as trust surface") and RF-06-quater (every guarantee must be visible) are formally satisfied by the `TracePanel`, but the *center* — the surface most users actually look at — surfaces almost nothing. BRD-24 closes that gap: the trace panel keeps being the engineering surface; the center becomes the **conversation surface**, narrating what the agent is doing in the user's mental model (read web → read pages → think → conclude) without exposing internal vocabulary (`Tool`, `Evidence`, `Judge`).

The change is composed strictly within Atomic Design (atoms → molecules → organisms → templates → pages), enforced by the existing ESLint `import/no-restricted-paths` rule. No layer is skipped, no layer reaches up.

---

## 2. RF Traceability

| RF | Requirement | Coverage |
|---|---|---|
| RF-13 (UI as trust surface) | Surface every guarantee | **Extends** — the center panel now narrates the same trust surface the right `TracePanel` already exposes, but in user-facing prose ("Searched the web for X — 4 results") instead of engineering nouns. Nothing is hidden; the trace panel keeps the technical view. |
| RF-08 (read determinism) | Identical output on replay | **Preserved** — the typewriter animation is a presentation effect over the persisted `Stopped.answer_prose`; refreshing the page replays the same final text. The animation is skipped on the second view (`localStorage` flag `novum.answerAnimated.{runId}` set to `1`). |
| RF-03 (event log append-only) | No event mutation | **Preserved unchanged** — the feed is a derived view of the event stream; it never writes events. |
| RF-11 (SSE stream + resume) | `Last-Event-ID` resume | **Preserved unchanged** — the feed consumes the existing SSE stream via the existing `createSSEConnection` wrapper; no protocol change. |
| RF-02 (4-value `StopReason` enum) | Honest stops are successes | **Extends presentation** — the feed renders `Stopped.stop_reason` and `Stopped.stop_rationale` in natural language ("Wrapped up — best-effort answer because: …"). Enum values unchanged. |

**No RF amendments required.** All extensions are presentational.

> **Doc updates (separate PR, in scope of US-24-3):**
> - `ui-prototype.md` §3 — add panel states C14 (live-feed grouping) and L8 (panel collapse).
> - `ui-prototype.md` §7 (microcopy) — add `FEED_*` and `TRACE_PANEL_*` strings.

---

## 3. Dependencies

| Depends On | Required For |
|---|---|
| Existing SSE infrastructure (BRD-10) | The feed consumes `RunStreamEvent` from `lib/sse.ts`. |
| Existing event types (BRD-02 + all subsequent) | Every payload field the feed reads (`query`, `source_url`, `source_title`, `polarity`, `authority_tier`, `final_confidence`, `rationale`, `sub_claims`, `answer_prose`, `stop_reason`, `stop_rationale`) already ships on the wire. |
| Atomic Design ESLint contract (BRD-11) | New components placed at the correct tier; CI fails any cross-tier import. |
| Design tokens (BRD-11 §1) | All new colors via CSS custom properties; no hardcoded hex. |
| Microcopy registry (`frontend/src/lib/microcopy.ts`) | All new strings centralized; English (language policy). |

**Does NOT depend on:** any backend change, any new event type, any schema migration, any LLM provider change.

---

## 4. Technical Specification

### 4.1 File Structure

```
frontend/
  src/
    index.css                              # MODIFY: +CSS custom properties for feed rail/active/external tones
    lib/
      microcopy.ts                         # MODIFY: +FEED_*, +TRACE_PANEL_*, +ANSWER_SKIP_HINT
      eventLabels.ts                       # MODIFY: +getEventNarrative(type, payload)
      feedGrouping.ts                      # NEW: groupConsecutiveEvents(events) -> FeedNode[]
      useTypewriter.ts                     # NEW: hook with adaptive speed + skip
    types/
      events.ts                            # UNCHANGED (verified by AC-16)
    components/
      atoms/
        FeedRail.tsx + .test.tsx           # NEW
        FeedStepIcon.tsx + .test.tsx       # NEW
        SourceLinkRow.tsx + .test.tsx      # NEW
        CollapseToggleButton.tsx + .test.tsx  # NEW
        BlinkingCursor.tsx + .test.tsx     # NEW
        index.ts                           # MODIFY: re-exports
      molecules/
        FeedStep.tsx + .test.tsx           # NEW
        SearchStepCard.tsx + .test.tsx     # NEW
        PlanStepCard.tsx + .test.tsx       # NEW
        JudgeVerdictCard.tsx + .test.tsx   # NEW
        index.ts                           # MODIFY: re-exports
      organisms/
        RunFeed.tsx + .test.tsx            # NEW: composes the molecules over an event stream
        StructuredAnswer.tsx + .test.tsx   # NEW: wraps StructuredBlocks with typewriter
        index.ts                           # MODIFY: re-exports
      templates/
        CenterPanelView.tsx                # MODIFY: replace ResearchingBanner with RunFeed
        TracePanel.tsx                     # MODIFY: collapse/expand toggle + persisted state
    containers/
      CenterPanelContainer.tsx             # MODIFY: pipe events into RunFeed; decide answer/feed split
    stores/
      selectionStore.ts                    # MODIFY: +tracePanelCollapsed: boolean (localStorage-backed)
```

### 4.2 Design tokens (new CSS custom properties)

Added to `:root` in `frontend/src/index.css`:

```css
--feed-rail:        var(--glass-border);  /* vertical rail */
--feed-rail-active: var(--accent);        /* rail segment behind the active step */
--feed-search:      #22d3ee;              /* cyan — external actions: Tool/Evidence/DeepFetch */
--feed-thinking:    var(--accent);        /* internal actions: Plan/Judge (aliases --accent for now) */
```

Rationale for cyan: external-world actions ("the agent reached *outside* the LLM") deserve a distinct color from internal reasoning steps. Cyan reads as "active networking" without competing with `--accent` (used for primary CTA and judge verdicts).

### 4.3 Microcopy (new strings, all English)

Added to `frontend/src/lib/microcopy.ts`:

```ts
export const FEED_LET_ME_SEARCH       = "Let me search for {query}…";
export const FEED_LET_ME_FETCH        = "Let me read this page…";
export const FEED_LET_ME_THINK        = "Let me work this through…";
export const FEED_SEARCHED_WEB        = "Searched the web";
export const FEED_FETCHED_PAGE        = "Fetched the page";
export const FEED_RESULTS_COUNT       = (n: number) => n === 1 ? "1 result" : `${n} results`;
export const FEED_DONE                = "Done";
export const FEED_TOGGLE_COLLAPSE     = "Collapse reasoning";
export const FEED_TOGGLE_EXPAND       = "Expand reasoning";
export const TRACE_PANEL_COLLAPSE     = "Collapse trace";
export const TRACE_PANEL_EXPAND       = "Expand trace";
export const ANSWER_SKIP_HINT         = "Click to skip";
export const ANSWER_ANIMATE_TOGGLE    = "Animate answer";
```

All strings are English per the language policy. The final synthesized answer continues to follow the backend's user-language rule (Spanish by default).

### 4.4 Grouping algorithm (`lib/feedGrouping.ts`)

Pure function `groupConsecutiveEvents(events: RunStreamEvent[]) -> FeedNode[]` where:

```ts
type FeedNode =
  | { kind: "search_group"; query: string; sources: SourceRow[]; deltaMs: number; toolEventId: string }
  | { kind: "single"; event: RunStreamEvent };
```

Rules:

1. A `ToolCalled` event opens a `search_group` node with `query` from its payload.
2. Every subsequent `EvidenceAdded` whose `tool_call_id` matches is appended as a `SourceRow` to the open group.
3. The group closes when (a) a non-`EvidenceAdded` event arrives, or (b) an `EvidenceAdded` arrives whose `tool_call_id` belongs to a different (still-open) group.
4. All other event types (`PlanCreated`, `PlanRevised`, `JudgeRuled`, `SubclaimUpdated`, `DeepFetchPerformed`, `RouteSelected`, `Stopped`, …) emit a `single` node.
5. The function is **pure** and deterministic — replaying the same `events[]` produces an identical `FeedNode[]`.

### 4.5 Typewriter (`lib/useTypewriter.ts`)

```ts
function useTypewriter(text: string, opts: {
  enabled: boolean;
  cps?: number;            // characters per second; default 80
  adaptive?: boolean;      // slow down 30% on code fences and headers; default true
  onSkip?: () => void;
}): { display: string; done: boolean; skip: () => void };
```

Behaviour:

- When `enabled === false`, returns `{ display: text, done: true }` immediately (used on replay and when user has already seen this answer).
- When `enabled === true`, advances one character per `1000/cps` ms via `requestAnimationFrame`.
- `adaptive=true` slows the cadence to 60 % inside fenced code blocks and Markdown headers (the user needs more time to parse them).
- `skip()` jumps to the full text and fires `onSkip`. The container wires `skip` to a click handler on the answer surface.
- On unmount, the animation cleans up (no orphan rAF callbacks).
- Sets `localStorage["novum.answerAnimated." + runId] = "1"` on completion so revisits skip the animation (RF-08 — read determinism: same text, no animation second time).

### 4.6 Component contracts

#### `RunFeed` (organism)

```ts
interface RunFeedProps {
  events: ReadonlyArray<RunStreamEvent>;
  status: "researching" | "stopped" | "cancelled";
  isCollapsed: boolean;
  onToggleCollapsed: () => void;
}
```

Renders an `<ol>` of `FeedStep`/`SearchStepCard`/`PlanStepCard`/`JudgeVerdictCard` molecules over the result of `groupConsecutiveEvents(events)`. The last non-stopped node carries `isActive=true` and shows a spinning icon. When `isCollapsed=true`, only the active node and the rail summary are visible. Motion v12 `layout` for additive growth — new steps fade in with `opacity 0 → 1` over 150 ms; no exit animations (the feed is append-only).

#### `StructuredAnswer` (organism)

```ts
interface StructuredAnswerProps {
  runId: string;
  answerProse: string;
  blocks: StructuredBlock[];          // existing type from US-21
  stopReason: StopReason;
  stopRationale: string | null;
  animate: boolean;
}
```

Composes `useTypewriter` with the existing `StructuredBlocks` renderer. When `animate=false` or `localStorage["novum.answerAnimated." + runId] === "1"`, renders instantly.

### 4.7 `TracePanel` collapse

`selectionStore` gains:

```ts
tracePanelCollapsed: boolean;
setTracePanelCollapsed: (collapsed: boolean) => void;
```

Persisted to `localStorage["novum.tracePanelCollapsed"]` (boolean, default `false` — trust surface is open by default). The `TracePanel` template renders:

- When `collapsed=false`: full trace (today's behaviour).
- When `collapsed=true`: a thin vertical strip (40 px wide) with the `CollapseToggleButton` and a small "N steps" badge derived from `events.length`.

The collapse state is **per-device, not per-run** — users who hide the trace stay hidden across runs until they reopen it.

### 4.8 What does NOT change

- `frontend/src/types/events.ts` (verified by AC-16 — no diff after `python scripts/export_types.py`).
- Any backend file.
- Any database schema.
- Any SSE protocol message shape.
- Any URL or route.
- The right-panel `TracePanel` content rendering (only its collapse chrome).

---

## 5. Functional Requirements

| FR | Description | Verification |
|---|---|---|
| FR-24-01 | While a run is in progress (status = `researching`), the center panel renders a `RunFeed` that updates in real time as SSE events arrive. | AC-01 |
| FR-24-02 | `ToolCalled` and its consecutive `EvidenceAdded` children render as a single `SearchStepCard` with the query in the header, the result count in a badge, and one `SourceLinkRow` per source. | AC-02 |
| FR-24-03 | Each source row shows favicon (with `Globe` fallback), title (truncated), and right-aligned hostname (`www.` stripped). Clicking the row opens the source in a new tab (`target="_blank" rel="noopener noreferrer"`). | AC-03 |
| FR-24-04 | `PlanCreated` and `PlanRevised` render as `PlanStepCard` with a rationale (truncated to 2 lines, expandable) and a bullet list of sub-claims with status icons. | AC-04 |
| FR-24-05 | `JudgeRuled` renders as `JudgeVerdictCard` with a pass/fail pill, a confidence bar (width = `final_confidence × 100 %`), the threshold, and the rationale (always expanded). | AC-05 |
| FR-24-06 | The currently-running step shows a spinning icon and its rail segment is colored with `--feed-rail-active`; all completed steps show their final icon and the rail returns to `--feed-rail`. | AC-06 |
| FR-24-07 | When `Stopped` arrives, a `FeedStep` with `FEED_DONE` is appended; the final answer renders inside `StructuredAnswer`. | AC-07 |
| FR-24-08 | On first view of a run's final answer, the answer animates token-by-token at ~80 cps; the animation is interruptible by clicking the answer (`ANSWER_SKIP_HINT` tooltip on hover). | AC-08 |
| FR-24-09 | On any subsequent view of the same run, the answer renders instantly (RF-08 read determinism). | AC-09 |
| FR-24-10 | The `TracePanel` has a collapse/expand toggle in its header that persists across page loads in `localStorage`. | AC-10 |
| FR-24-11 | The collapse state of the `TracePanel` is per-device, not per-run. | AC-11 |
| FR-24-12 | The center feed has its own collapse/expand toggle (`FEED_TOGGLE_COLLAPSE` / `FEED_TOGGLE_EXPAND`) that hides intermediate steps and shows only the active step + a summary count. | AC-12 |
| FR-24-13 | All new components pass `jest-axe` accessibility checks (no violations at WCAG AA). | AC-13 |
| FR-24-14 | The feed correctly groups even when SSE events arrive out of order — `groupConsecutiveEvents` is order-tolerant within a single render (groups are keyed by `tool_call_id`, not by arrival index). | AC-14 |
| FR-24-15 | Cancelled runs (`status = "cancelled"`) render a final `FeedStep` with `EVENT_VISUALS["UserCancelled"]` and stop the active spinner. | AC-15 |
| FR-24-16 | `frontend/src/types/events.ts` does not change. | AC-16 |

---

## 6. Non-Functional Requirements

| NFR | Requirement | Verification |
|---|---|---|
| NFR-24-01 | The feed remains responsive (no frame drops > 16 ms) up to 200 events on a mid-range laptop. | Manual perf check + React Profiler. |
| NFR-24-02 | All new strings are English. The user-facing final answer continues to follow the backend's language rule. | Manual grep + i18n review. |
| NFR-24-03 | All new components are typed strictly (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`). No `any`. | `tsc --noEmit` clean. |
| NFR-24-04 | All new components use `cn()` (clsx + tailwind-merge) for conditional classes; no string concatenation for class names. | Code review. |
| NFR-24-05 | Atomic Design layering is respected — only `pages/` (or `containers/`) fetches data; molecules never import organisms; atoms never import molecules. | ESLint `import/no-restricted-paths` clean. |
| NFR-24-06 | No new runtime dependency added to `package.json`. (Reuses Motion v12, Lucide React, `clsx + tailwind-merge`, `react-markdown + react-syntax-highlighter`.) | `git diff package.json` empty. |
| NFR-24-07 | All new code is tested with Vitest + Testing Library + jest-axe; ≥ 80 % coverage on the new files. | `vitest --coverage`. |

---

## 7. Acceptance Criteria

| AC | Statement |
|---|---|
| AC-01 | Component test on `RunFeed`: feeding a sequence of events emits the corresponding feed nodes in the DOM as `<li>` items inside an `<ol>`. |
| AC-02 | Component test: a `ToolCalled` followed by 3 `EvidenceAdded` (same `tool_call_id`) renders one `SearchStepCard`, header text contains the query, badge shows `"3 results"`. |
| AC-03 | Component test on `SourceLinkRow`: `https://www.wikipedia.org/wiki/Foo` displays hostname `wikipedia.org` and `target="_blank" rel="noopener noreferrer"` is set. jest-axe clean. |
| AC-04 | Component test on `PlanStepCard`: sub-claim status `covered → CheckCircle2`, `pending → Circle`, `uncoverable → MinusCircle`. Revision header differs from creation header. |
| AC-05 | Component test on `JudgeVerdictCard`: `passed=true` shows ✓ pill; confidence bar width = `final_confidence × 100`%. |
| AC-06 | Component test on `RunFeed`: with status `researching` and 4 events, the 4th node has `isActive=true` and renders a spinning icon. |
| AC-07 | Component test: `Stopped` event causes the feed to append a `FEED_DONE` step and renders `StructuredAnswer` below the feed. |
| AC-08 | Component test on `StructuredAnswer`: when `animate=true` and no `localStorage` flag is set, `useTypewriter` is invoked with `enabled=true`; clicking the surface fires `skip()` and the full text appears. |
| AC-09 | Component test: when `localStorage["novum.answerAnimated." + runId] === "1"`, `useTypewriter` is invoked with `enabled=false`; text appears instantly. |
| AC-10 | Component test on `TracePanel`: clicking the collapse toggle persists `selectionStore.tracePanelCollapsed=true` and writes `localStorage["novum.tracePanelCollapsed"]`. |
| AC-11 | Component test: reloading the page restores the previous collapse state without any per-run context. |
| AC-12 | Component test on `RunFeed`: with `isCollapsed=true`, only the active node is visible; the others are hidden but still in the DOM (so resume is instantaneous). |
| AC-13 | jest-axe assertion in every new `.test.tsx` — 0 violations. |
| AC-14 | Unit test on `groupConsecutiveEvents`: shuffling the order of an `EvidenceAdded` and an unrelated `JudgeRuled` between two `ToolCalled` groups still produces correct, separate groups keyed by `tool_call_id`. |
| AC-15 | Component test: `status="cancelled"` stops the active spinner and appends a cancellation step. |
| AC-16 | CI check: `python scripts/export_types.py` produces empty diff after this change. |

---

## 8. Test Plan (binding)

| Test file | Scope | New / Modified |
|---|---|---|
| `frontend/src/lib/microcopy.test.ts` | Verify `FEED_*` / `TRACE_PANEL_*` constants present and English | MODIFIED |
| `frontend/src/lib/eventLabels.test.ts` | `getEventNarrative` per event type | MODIFIED |
| `frontend/src/lib/feedGrouping.test.ts` | Grouping algorithm + order tolerance | NEW |
| `frontend/src/lib/useTypewriter.test.ts` | Adaptive cps + skip + localStorage flag | NEW |
| `frontend/src/components/atoms/*.test.tsx` (5 files) | Each atom in isolation + jest-axe | NEW |
| `frontend/src/components/molecules/*.test.tsx` (4 files) | Each molecule + jest-axe | NEW |
| `frontend/src/components/organisms/RunFeed.test.tsx` | Composition + grouping + active step + collapse | NEW |
| `frontend/src/components/organisms/StructuredAnswer.test.tsx` | Typewriter wiring + replay determinism | NEW |
| `frontend/src/components/templates/TracePanel.test.tsx` | Collapse toggle + persistence | MODIFIED |

Coverage gate ≥ 80 % on all new files.

---

## 9. Out of Scope

| Item | Reason |
|---|---|
| Backend event-type changes | Every payload field needed is already on the wire. |
| Streaming the final answer token-by-token from the backend | The typewriter is a presentation effect; backend streaming would violate RF-08 (read determinism on resume). |
| Per-run trace-panel collapse state | The collapse preference is about user trust comfort, not about a specific run. |
| Internationalization of the new microcopy | i18n is explicitly excluded from V1 (copilot-instructions.md §2). |
| Storybook stories for the new components | Storybook is excluded from V1. |

---

## 10. Success Metrics

| Metric | Baseline | Target |
|---|---|---|
| Time-to-first-meaningful-paint of the center panel after `RunStarted` | ~2 s (banner only) | **≤ 200 ms** (first feed step renders as soon as the first event arrives) |
| User-reported "I understand what the agent is doing" (manual qualitative review of 10 runs) | Low (banner is opaque) | **High** (steps narrate the action) |
| `TracePanel` collapse usage | n/a | Measurable in `localStorage` audit; not a hard target |
| Feed render performance with 200 events | n/a | **No frame > 16 ms** in React Profiler |
| Replay determinism | 100 % | **100 %** (final answer identical on every reload; AC-09) |
| Regression on existing flows | none expected | 0 failed test in existing test suite |

---

## 11. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Grouping algorithm misclassifies events when SSE delivers out-of-order | Low | Medium | `tool_call_id`-keyed grouping (AC-14) is order-tolerant; unit test on shuffled fixture. |
| Typewriter feels slow on long answers | Medium | Low | Adaptive cps (80 baseline, 60 % inside code/headers) + click-to-skip + `ANSWER_ANIMATE_TOGGLE` user setting (future iteration). |
| Atomic-Design layering accidentally broken by a hurried import | Low | Medium | ESLint `import/no-restricted-paths` fails CI. |
| Favicon endpoint fails (Google s2 down) | Low | Low | `SourceLinkRow` falls back to `Globe` Lucide icon (AC-03 fallback branch). |
| Hidden steps in collapsed mode break screen readers | Medium | High | Hidden steps remain in the DOM with `aria-hidden="false"` but `tabindex="-1"`; jest-axe assertion (AC-13) enforces 0 violations. |
| Animation skip interferes with user clicks on links inside the answer | Medium | Medium | `useTypewriter.skip()` only fires when `done === false`; once done, clicks pass through to links normally. |
| Animation re-fires on resume causing UX dissonance | High if unhandled | Medium | `localStorage["novum.answerAnimated." + runId]` flag (AC-09). |

---

## 12. References

- IP-24 implementation plan: [IP-24](../implementation-plans/IP-24-live-center-feed.md)
- UI prototype (binding for all frontend work): [ui-prototype.md](../../understanding-phase/ui-prototype.md)
- Atomic Design enforcement: BRD-11
- SSE infrastructure: BRD-10
- Event types (read by the feed): BRD-02, BRD-22, BRD-23
- Requirements catalogue: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
