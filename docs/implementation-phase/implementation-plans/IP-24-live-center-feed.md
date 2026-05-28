# Implementation Plan — IP-24: Live Center Feed (Claude-style)

**Plan ID:** IP-24
**Parent BRD:** BRD-24 (TBD — not yet authored; this IP is the technical seed)
**Parent User Stories:** US-24-1 (TBD)
**Date:** 2026-05-27
**Author:** Plan Agent
**Complexity:** M (frontend-only refactor + new organism + atoms/molecules)
**Estimated Effort:** M (≈ 4–5 h pair-session, split across 8 phases — many parallelizable)
**Iteration:** 1

---

## 1. Plan summary

Replace the tiny `ResearchingBanner` in the center panel with a Claude-style **live feed**: vertical rail, icon per event type, natural-language step copy ("Searching the web", "Let me check…", "Done"), `ToolCalled` grouped with its consecutive `EvidenceAdded` children into one card with inline source rows (favicon + title + right-aligned domain). The right `TracePanel` stays in parallel but gains a `localStorage`-persisted collapse/expand toggle. The final answer animates in token-by-token (frontend-only typewriter, no backend streaming) with adaptive speed and click-to-skip. **Frontend-only** — no backend, schema, or event changes; every payload field needed by the feed already exists.

### Scope summary

| Phase | Concern | Files (new + modified) |
|---|---|---|
| 0 | Design tokens + microcopy | `index.css`, `microcopy.ts`, `eventLabels.ts` |
| 1 | Atoms | `FeedRail`, `FeedStepIcon`, `SourceLinkRow`, `CollapseToggleButton`, `BlinkingCursor` |
| 2 | Molecules | `FeedStep`, `SearchStepCard`, `PlanStepCard`, `JudgeVerdictCard` |
| 3 | Organism + grouping lib | `RunFeed`, `lib/feedGrouping.ts` |
| 3.5 | Typewriter hook | `lib/useTypewriter.ts`, `StructuredAnswer`, `StructuredBlocks` |
| 4 | Center integration | `CenterPanelView`, `CenterPanelContainer` |
| 5 | Right panel collapse | `selectionStore`, `TracePanel` template |
| 6 | Tests | 12 new test files + 3 modified |
| 7 | Docs + memory bank | `ui-prototype.md`, `decisions-history.md` |

### Architecture rules respected

1. **Atomic-design layering** — every new component lives at its correct tier (atoms → molecules → organisms); ESLint `import/no-restricted-paths` already enforces this.
2. **No backend changes** — Architecture rule #2 (planner / storage / LLM provider not pluggable) untouched. Event payloads already expose `ToolCalled.query`, `EvidenceAdded.source_url|source_title|polarity|authority_tier`, `JudgeRuled.final_confidence|rationale`, `PlanCreated.sub_claims`, `Stopped.answer_prose|stop_reason`.
3. **No schema or event-type changes** — RF-03 (event log append-only) untouched.
4. **Type contract FE↔BE** — uses existing `RunStreamEvent` shape from `frontend/src/types/events.ts`; no `scripts/export_types.py` rerun needed.
5. **Language policy** — feed microcopy in English; final answer keeps user-language behaviour (driven by backend prompt, not by frontend).

---

## 2. Phase breakdown

> **Convention.** Each task is numbered `T-24-<phase>-<NN>`, tagged `[fe-tokens] / [fe-atom] / [fe-molecule] / [fe-organism] / [fe-page] / [fe-lib] / [test] / [doc]`, sized at ≤ ~80 LOC delta where practical.

### 2.1 Phase 0 — Tokens + microcopy *(parallelizable with Phase 1)*

#### 2.1.1 — Goal

Provide the design vocabulary every later phase consumes: CSS custom properties for the rail/active/external-action colors, microcopy constants for natural-language step descriptions, optional `getEventNarrative(type, payload)` helper.

#### 2.1.2 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-0-01** | Add new tokens to `:root` in `frontend/src/index.css`: `--feed-rail: var(--glass-border)`, `--feed-rail-active: var(--accent)`, `--feed-search: #22d3ee` (cyan for external actions: Tool/Evidence/DeepFetch), `--feed-thinking: var(--accent)` (alias for internal: Plan/Judge). | `frontend/src/index.css` | XS | [fe-tokens] |
| **T-24-0-02** | Extend `frontend/src/lib/microcopy.ts` with: `FEED_LET_ME_SEARCH = "Let me search for {query}…"`, `FEED_LET_ME_FETCH = "Let me read this page…"`, `FEED_LET_ME_THINK = "Let me work this through…"`, `FEED_SEARCHED_WEB = "Searched the web"`, `FEED_FETCHED_PAGE = "Fetched the page"`, `FEED_RESULTS_COUNT(n) = "{n} results"` / `"1 result"`, `FEED_DONE = "Done"`, `FEED_TOGGLE_COLLAPSE = "Collapse reasoning"`, `FEED_TOGGLE_EXPAND = "Expand reasoning"`, `TRACE_PANEL_COLLAPSE = "Collapse trace"`, `TRACE_PANEL_EXPAND = "Expand trace"`, `ANSWER_SKIP_HINT = "Click to skip"`, `ANSWER_ANIMATE_TOGGLE = "Animate answer"`. All English (language policy). | `frontend/src/lib/microcopy.ts` | S | [fe-tokens] |
| **T-24-0-03** | Add `getEventNarrative(type: EventType, payload: Record<string, unknown>): string` to `frontend/src/lib/eventLabels.ts` returning a richer phrase than `EVENT_ACTIVITIES`: for `ToolCalled` → `Searched the web for "{query}"`; for `EvidenceAdded` → `Read "{source_title}" ({hostname})`; for `JudgeRuled` → `Judge verdict: confidence {final_confidence}`; for `Stopped` → `Wrapped up — {stop_reason}`. Fall back to `getEventActivity(type)` for any other type. Pure function; payload typed via `Record<string, unknown>` to avoid coupling. | `frontend/src/lib/eventLabels.ts` | S | [fe-lib] |

#### 2.1.3 — Test plan

| Test file | Test name | New / Modified |
|---|---|---|
| `frontend/src/lib/microcopy.test.ts` (existing) | `test_feed_microcopy_constants_present` | MODIFIED |
| `frontend/src/lib/eventLabels.test.ts` (existing) | `test_getEventNarrative_for_ToolCalled_includes_query`, `test_getEventNarrative_for_EvidenceAdded_includes_hostname`, `test_getEventNarrative_falls_back_to_activity_on_unknown_type` | MODIFIED |

### 2.2 Phase 1 — Atoms *(parallelizable with Phase 0)*

#### 2.2.1 — Goal

Five new presentational atoms with zero domain knowledge. Each ≤ ~60 LOC + co-located test.

#### 2.2.2 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-1-01** | `FeedRail` — vertical line drawn as `absolute left-[15px] top-0 bottom-0 w-px bg-[var(--feed-rail)]`. Props: `{ tone?: "neutral" \| "active", className?: string }`. When `tone === "active"`, swap `--feed-rail` for `--feed-rail-active`. Renders nothing else (the rail is just a positioned `div`). | `frontend/src/components/atoms/FeedRail.tsx` + `.test.tsx` | XS | [fe-atom] |
| **T-24-1-02** | `FeedStepIcon` — circular badge `w-8 h-8 rounded-full bg-[var(--bg-tertiary)] border` with Lucide icon centered. Props: `{ type: EventType, isActive?: boolean, className?: string }`. Reads icon and tone from `EVENT_VISUALS[type]` in `eventVisuals.ts`. When `isActive`, wrap the icon in a Motion `rotate` (or CSS `animate-spin` for the spinner-pulse). Tone drives `border-color` (e.g. `var(--feed-search)` for `info` external, `var(--accent)` for `decision`/`judge`). | `frontend/src/components/atoms/FeedStepIcon.tsx` + `.test.tsx` | S | [fe-atom] |
| **T-24-1-03** | `SourceLinkRow` — flex row: favicon (left, 16x16, from `https://www.google.com/s2/favicons?domain={hostname}` or fallback `Globe` icon), title (flex-1, truncate, click-target), hostname + `ExternalLink` icon (right-aligned, `text-[var(--text-muted)]`). Props: `{ url: string, title: string, sourceType?: "tavily" \| "wikipedia", className?: string }`. Renders as `<a target="_blank" rel="noopener noreferrer">`. Extract hostname via `new URL(url).hostname`; strip leading `www.`. | `frontend/src/components/atoms/SourceLinkRow.tsx` + `.test.tsx` | M | [fe-atom] |
| **T-24-1-04** | `CollapseToggleButton` — button with `ChevronRight` icon, Motion v12 `rotate` 0/90° based on `isCollapsed`. Props: `{ isCollapsed: boolean, onToggle: () => void, labelCollapse: string, labelExpand: string, className?: string }`. `aria-expanded={!isCollapsed}`, `aria-label={isCollapsed ? labelExpand : labelCollapse}`. Transition 200 ms. | `frontend/src/components/atoms/CollapseToggleButton.tsx` + `.test.tsx` | S | [fe-atom] |
| **T-24-1-05** | `BlinkingCursor` — `▌` glyph with CSS `@keyframes blink { 50% { opacity: 0 } }` at 1 s cadence. Props: `{ className?: string }`. `aria-hidden="true"`. Pure CSS, no JS state. | `frontend/src/components/atoms/BlinkingCursor.tsx` + `.test.tsx` | XS | [fe-atom] |
| **T-24-1-06** | Add all five exports to `frontend/src/components/atoms/index.ts`. | `frontend/src/components/atoms/index.ts` | XS | [fe-atom] |

#### 2.2.3 — Test plan

| Test file | Asserts | New |
|---|---|---|
| `FeedRail.test.tsx` | renders `div` with correct CSS var per tone; `className` merge | NEW |
| `FeedStepIcon.test.tsx` | picks `EVENT_VISUALS[type].Icon`; adds spin class when `isActive`; tone-driven border color | NEW |
| `SourceLinkRow.test.tsx` | hostname extracted correctly; `target="_blank"` + `rel="noopener noreferrer"`; `www.` stripped; favicon fallback; jest-axe clean | NEW |
| `CollapseToggleButton.test.tsx` | `aria-expanded` flips; chevron rotation applied; click fires `onToggle` once | NEW |
| `BlinkingCursor.test.tsx` | renders `▌`; `aria-hidden="true"`; class includes `animate-blink` (or equivalent) | NEW |

### 2.3 Phase 2 — Molecules *(depends on Phase 1)*

#### 2.3.1 — Goal

Four molecule variants of a feed node, each specialized for one event family.

#### 2.3.2 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-2-01** | `FeedStep` — base molecule. Layout: `<li className="relative flex gap-3 pl-2 pb-3">` with `FeedStepIcon` (z-10 over the rail) + content column (title + optional summary + children slot) + optional right-aligned meta (`deltaMs` or timestamp). Props: `{ type: EventType, title: string, summary?: string, isActive?: boolean, isLast?: boolean, deltaMs?: number, children?: ReactNode, className?: string }`. Motion `fade-in` 150 ms on mount. | `frontend/src/components/molecules/FeedStep.tsx` + `.test.tsx` | M | [fe-molecule] |
| **T-24-2-02** | `SearchStepCard` — variant for grouped `ToolCalled` + children. Header: `FEED_SEARCHED_WEB` + `"{query}"` chip + `FEED_RESULTS_COUNT(n)` badge right-aligned. Body: collapsible `<ul>` of `SourceLinkRow` (default collapsed when `children.length > 3`, expanded otherwise). Uses internal state for collapse; controlled prop optional. Props: `{ query: string, sources: ReadonlyArray<{ url: string; title: string; sourceType?: "tavily" \| "wikipedia" }>, isActive?: boolean, deltaMs?: number, className?: string }`. Composes `FeedStep` (with `type="ToolCalled"`) wrapping the source list as children. | `frontend/src/components/molecules/SearchStepCard.tsx` + `.test.tsx` | M | [fe-molecule] |
| **T-24-2-03** | `PlanStepCard` — variant for `PlanCreated` / `PlanRevised`. Header: `"Drafted a plan"` (or `"Revised the plan"`) + complexity chip if present. Body: rationale (truncated to 2 lines, expandable), then bullet list of `sub_claims` with status icons (`CheckCircle2` covered / `Circle` pending / `MinusCircle` uncoverable) and text. Props: `{ rationale: string, subClaims: ReadonlyArray<{ id: string; text: string; status: "pending" \| "covered" \| "uncoverable" }>, complexityHint?: string, isActive?: boolean, deltaMs?: number, isRevision?: boolean }`. | `frontend/src/components/molecules/PlanStepCard.tsx` + `.test.tsx` | M | [fe-molecule] |
| **T-24-2-04** | `JudgeVerdictCard` — variant for `JudgeRuled`. Header: verdict pill (`"✓ Confirmed"` if `passed`, `"✗ Retry suggested"` otherwise) + `final_confidence` shown as a small bar (using existing `ConfidenceBar` molecule if available; otherwise inline `<div>` with width %). Body: rationale (always expanded for judge events per `EXPANDED_BY_DEFAULT`). Props: `{ passed: boolean, finalConfidence: number, threshold: number, rationale: string, deltaMs?: number }`. | `frontend/src/components/molecules/JudgeVerdictCard.tsx` + `.test.tsx` | M | [fe-molecule] |
| **T-24-2-05** | Add all four exports to `frontend/src/components/molecules/index.ts`. | `frontend/src/components/molecules/index.ts` | XS | [fe-molecule] |

#### 2.3.3 — Test plan

| Test file | Asserts | New |
|---|---|---|
| `FeedStep.test.tsx` | renders title + icon; spinner state when `isActive`; rail-relative positioning; jest-axe clean | NEW |
| `SearchStepCard.test.tsx` | header has query + count; collapsed by default with > 3 sources; expand reveals all `SourceLinkRow`s; jest-axe clean | NEW |
| `PlanStepCard.test.tsx` | each sub-claim status renders correct icon; rationale truncation + expand; revision vs creation header | NEW |
| `JudgeVerdictCard.test.tsx` | verdict pill flips with `passed`; confidence bar width matches `finalConfidence`; rationale visible | NEW |

### 2.4 Phase 3 — Organism `RunFeed` + grouping lib *(depends on Phase 2)*

#### 2.4.1 — Goal

The main orchestrator component. Pure-function event grouping in a separate lib so it can be tested without React.

#### 2.4.2 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-3-01** | `feedGrouping.ts` — pure `buildFeedSteps(events: readonly RunStreamEvent[]): readonly FeedStepData[]`. The discriminated union `FeedStepData` carries `{ kind: "search" \| "plan" \| "judge" \| "ambiguity" \| "contradiction" \| "done" \| "generic", payload, deltaMs?, isActive? }`. Algorithm: iterate; `ToolCalled` opens a `search` bucket; subsequent `EvidenceAdded` / `SourceFailed` / `DeepFetchPerformed` whose `target_claim_id` matches (or is empty) and that are not interrupted by `PlanCreated` / `PlanRevised` / `JudgeRuled` / `ContradictionDetected` / `AmbiguityDetected` / `Stopped` get appended; otherwise close the bucket. `PlanCreated`/`PlanRevised` → `plan`; `JudgeRuled` → `judge`; `ContradictionDetected` → `contradiction`; `AmbiguityDetected` → `ambiguity`; `Stopped` → `done`; everything else → `generic`. Compute `deltaMs` from `timestamp_ms` deltas. Mark the last step `isActive=true` only if `!isComplete` is passed (param). | `frontend/src/lib/feedGrouping.ts` + `.test.ts` | L | [fe-lib] |
| **T-24-3-02** | `RunFeed` organism. Props: `{ events: readonly RunStreamEvent[], isComplete: boolean, className?: string }`. Calls `buildFeedSteps(events, { isComplete })`, maps each `FeedStepData` to the corresponding molecule (`SearchStepCard` / `PlanStepCard` / `JudgeVerdictCard` / `FeedStep`). Wraps the list in a `<div className="relative">` containing a single `FeedRail` (tone `active` while `!isComplete`) and an `<ol className="flex flex-col">` of the steps. | `frontend/src/components/organisms/RunFeed.tsx` + `.test.tsx` | L | [fe-organism] |
| **T-24-3-03** | Sticky-bottom autoscroll: copy the pattern from `TraceTimeline.tsx` (sentinel `<div ref={bottomRef}/>` + `IntersectionObserver`; gracefully fall back to sticky=true if `IntersectionObserver === undefined` for tests). When `isComplete === true`, disable stickiness. Reuse `JumpToLatestPill` atom. | `frontend/src/components/organisms/RunFeed.tsx` | M | [fe-organism] |
| **T-24-3-04** | Feed collapse post-completion: when `isComplete && events.length > 0`, render a sticky header `"Reasoning trace ({steps.length} steps · {totalSeconds}s)"` + `CollapseToggleButton`. State persisted in `localStorage` key `novum_run_feed_collapsed` (default `true` after completion). Wrap the `<ol>` in a conditionally rendered div when expanded. | `frontend/src/components/organisms/RunFeed.tsx` | M | [fe-organism] |
| **T-24-3-05** | Add `RunFeed` export to `frontend/src/components/organisms/index.ts`. | `frontend/src/components/organisms/index.ts` | XS | [fe-organism] |

#### 2.4.3 — Test plan

| Test file | Asserts | New |
|---|---|---|
| `feedGrouping.test.ts` | (a) `ToolCalled` + 3× `EvidenceAdded` (same `target_claim_id`) → 1 `search` bucket with 3 children. (b) `ToolCalled` interrupted by `ContradictionDetected` → bucket closes, contradiction step opens. (c) Full sequence `PlanCreated` → `ToolCalled` → `EvidenceAdded` → `JudgeRuled` → `Stopped` → 5 steps in order with correct kinds. (d) `SourceFailed` appended to active bucket. (e) Orphan `EvidenceAdded` (no prior `ToolCalled`) → `generic` step. (f) `isComplete=false` → last step `isActive=true`; `isComplete=true` → no active. | NEW |
| `RunFeed.test.tsx` | renders correct molecule for each kind; sticky-bottom works with IntersectionObserver stub; `JumpToLatestPill` appears when sentinel out of view; collapse toggle persists key in localStorage; jest-axe clean | NEW |

### 2.5 Phase 3.5 — Typewriter on the final answer *(depends on Phase 3, parallelizable with Phase 4)*

#### 2.5.1 — Goal

Claude-style "is typing" visual on the final answer. **Frontend-only** — no backend streaming. Adaptive speed, click-to-skip, no re-animate on replay.

#### 2.5.2 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-3.5-01** | `useTypewriter` hook. Signature: `useTypewriter({ text: string, enabled: boolean, charsPerSecond?: number }): { displayed: string, isTyping: boolean, skip: () => void }`. Default `charsPerSecond`: `text.length < 500 ⇒ 60`, `< 1500 ⇒ 150`, `≥ 1500 ⇒ 250`. Implementation: `requestAnimationFrame` loop with delta-time accumulator (no `setInterval`); cleanup on unmount; respect `window.matchMedia("(prefers-reduced-motion: reduce)").matches` → force `enabled=false`. Listen to `document` `visibilitychange` → on hidden, call `skip()`. | `frontend/src/lib/useTypewriter.ts` + `.test.ts` | M | [fe-lib] |
| **T-24-3.5-02** | Update `StructuredAnswer` organism: new optional prop `animate?: boolean` (default `false`). When `animate`, pass `content` through `useTypewriter`; render `displayed` via `react-markdown`. Append `<BlinkingCursor/>` while `isTyping`. Wrap content in a div with click / `Escape` / `Space` handler → `skip()`. | `frontend/src/components/organisms/StructuredAnswer.tsx` (+ `.test.tsx` modified) | M | [fe-organism] |
| **T-24-3.5-03** | Update `StructuredBlocks` organism: same new prop `animate?: boolean`. Apply `useTypewriter` to the concatenated text of the first block only (rest revealed instantly after typewriter finishes; keeps complexity bounded). | `frontend/src/components/organisms/StructuredBlocks.tsx` (+ `.test.tsx` modified) | M | [fe-organism] |
| **T-24-3.5-04** | Persistence helper in `frontend/src/lib/answerAnimation.ts`: `hasAnswerBeenAnimated(runId): boolean` and `markAnswerAnimated(runId): void` reading/writing localStorage key `novum_answered_runs` (JSON array, capped at 500 entries — drop oldest). Plus global toggle `isAnimateAnswerEnabled(): boolean` reading `novum_animate_answer` (default `true`). | `frontend/src/lib/answerAnimation.ts` + `.test.ts` | S | [fe-lib] |
| **T-24-3.5-05** | Wire `animate` from `CenterPanelView` → `StructuredAnswer` / `StructuredBlocks`: `animate = isAnimateAnswerEnabled() && hasAnswer && !hasAnswerBeenAnimated(run.id)`; on typewriter `onComplete` (callback added to `useTypewriter` if needed), call `markAnswerAnimated(run.id)`. | `frontend/src/components/organisms/CenterPanelView.tsx` | S | [fe-organism] |

#### 2.5.3 — Test plan

| Test file | Asserts | New / Modified |
|---|---|---|
| `useTypewriter.test.ts` | `vi.useFakeTimers()` + `requestAnimationFrame` mock: progression at expected rate; `skip()` jumps to full text; reduced-motion → `enabled=false` immediately; `document.hidden=true` event fires `skip()` | NEW |
| `answerAnimation.test.ts` | `hasAnswerBeenAnimated` round-trip; cap at 500; global toggle default `true`; localStorage corruption recovery | NEW |
| `BlinkingCursor.test.tsx` | covered in Phase 1 | (already NEW) |
| `StructuredAnswer.test.tsx` | new test: with `animate=true`, only `displayed` substring renders initially; click triggers `skip()` ⇒ full text visible | MODIFIED |
| `StructuredBlocks.test.tsx` | same shape | MODIFIED |

### 2.6 Phase 4 — Center integration *(depends on Phase 3)*

#### 2.6.1 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-4-01** | Add optional prop `events?: readonly RunStreamEvent[]` to `CenterPanelView`. Replace the entire `status === "running" ? <ResearchingBanner …/>` branch with `<RunFeed events={events ?? []} isComplete={status !== "running"}/>`. When `isTerminal && hasAnswer`, render `<RunFeed … isComplete/>` ABOVE `TrustSummary` + `StopReasonCard` + `StructuredAnswer`. Pass `animate` to `StructuredAnswer` per T-24-3.5-05. | `frontend/src/components/organisms/CenterPanelView.tsx` | M | [fe-organism] |
| **T-24-4-02** | Update `CenterPanelView.test.tsx`: expect `RunFeed` instead of `ResearchingBanner` during running; keep tests for terminal answer rendering. | `frontend/src/components/organisms/CenterPanelView.test.tsx` | S | [test] |
| **T-24-4-03** | `CenterPanelContainer.tsx`: pass `events` (already available from `useRunStream`) to `<CenterPanelView … events={events}/>`. | `frontend/src/pages/CenterPanelContainer.tsx` | XS | [fe-page] |

### 2.7 Phase 5 — TracePanel collapse *(parallelizable with Phase 4)*

#### 2.7.1 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-5-01** | Extend `selectionStore`: add `isTracePanelCollapsed: boolean` (default `false`), action `toggleTracePanelCollapsed(): void`. Initialize from `localStorage.getItem("novum_trace_panel_collapsed") === "1"`; persist on toggle. Mimic `auth.ts` localStorage pattern. | `frontend/src/stores/selectionStore.ts` | S | [fe-store] |
| **T-24-5-02** | Modify the right-panel template (`TracePanel.tsx` or `AppShell.tsx` if width is controlled there): when `isTracePanelCollapsed`, render a narrow rail (`w-10`) containing a vertical `CollapseToggleButton` + rotated `"Trace"` label; when expanded, render normal width with `CollapseToggleButton` at top-right. The toggle is independent of `rightPanelOpen` (close = hidden, collapse = minimized). | `frontend/src/components/templates/TracePanel.tsx` (or `AppShell.tsx`) | M | [fe-template] |

#### 2.7.2 — Test plan

| Test file | Asserts | New / Modified |
|---|---|---|
| `selectionStore.test.ts` | new toggle + localStorage round-trip (with localStorage stub) | MODIFIED |
| `TracePanel.test.tsx` (if it exists; otherwise add) | collapsed renders narrow rail; expanded renders normal width; toggle button click flips state | NEW or MODIFIED |

### 2.8 Phase 6 — Test sweep + a11y

#### 2.8.1 — Goal

Confirm aggregate coverage ≥ 80 % on all new files; jest-axe clean on every new component; ESLint atomic-design boundaries pass.

#### 2.8.2 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-6-01** | `npx vitest run --coverage` — confirm each new file ≥ 80 % statements / branches / lines. | (n/a) | XS | [test] |
| **T-24-6-02** | `npx eslint src` — 0 errors of `import/no-restricted-paths`. | (n/a) | XS | [test] |
| **T-24-6-03** | `npx tsc --noEmit` — 0 errors under `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`. | (n/a) | XS | [test] |

### 2.9 Phase 7 — Docs + memory bank

#### 2.9.1 — Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-24-7-01** | Update `docs/understanding-phase/ui-prototype.md` §3 (add C3' Live Feed state diagram) and §7 (new microcopy strings). | `docs/understanding-phase/ui-prototype.md` | S | [doc] |
| **T-24-7-02** | Add decision record to `.github/memory-bank/logs/decisions-history.md`: D-NN — "Live center feed (Claude-style) replaces ResearchingBanner; trace panel parallel and collapsible; final answer animated via frontend typewriter (no backend streaming)". | `.github/memory-bank/logs/decisions-history.md` | XS | [doc] |
| **T-24-7-03** | (Optional, post-coder) Author BRD-24 and US-24-1 retroactively from this IP so the artefact triplet is complete. Or accept that IP-24 stands alone (precedent: `PLAN-US-20-…`). | `docs/implementation-phase/brds/`, `docs/implementation-phase/user-stories/` | S | [doc] |

---

## 3. Files relevant

### Create

| Path | Tier |
|---|---|
| `frontend/src/components/atoms/FeedRail.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/FeedStepIcon.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/SourceLinkRow.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/CollapseToggleButton.tsx` + `.test.tsx` | atom |
| `frontend/src/components/atoms/BlinkingCursor.tsx` + `.test.tsx` | atom |
| `frontend/src/components/molecules/FeedStep.tsx` + `.test.tsx` | molecule |
| `frontend/src/components/molecules/SearchStepCard.tsx` + `.test.tsx` | molecule |
| `frontend/src/components/molecules/PlanStepCard.tsx` + `.test.tsx` | molecule |
| `frontend/src/components/molecules/JudgeVerdictCard.tsx` + `.test.tsx` | molecule |
| `frontend/src/components/organisms/RunFeed.tsx` + `.test.tsx` | organism |
| `frontend/src/lib/feedGrouping.ts` + `.test.ts` | lib |
| `frontend/src/lib/useTypewriter.ts` + `.test.ts` | lib |
| `frontend/src/lib/answerAnimation.ts` + `.test.ts` | lib |

### Modify

| Path | Reason |
|---|---|
| `frontend/src/index.css` | new tokens (Phase 0) |
| `frontend/src/lib/microcopy.ts` | new feed strings (Phase 0) |
| `frontend/src/lib/eventLabels.ts` | `getEventNarrative` helper |
| `frontend/src/stores/selectionStore.ts` | `isTracePanelCollapsed` + persistence |
| `frontend/src/components/organisms/CenterPanelView.tsx` | mount `RunFeed`, wire `animate` |
| `frontend/src/components/organisms/CenterPanelView.test.tsx` | expect `RunFeed` |
| `frontend/src/components/organisms/StructuredAnswer.tsx` + `.test.tsx` | `animate` prop |
| `frontend/src/components/organisms/StructuredBlocks.tsx` + `.test.tsx` | `animate` prop |
| `frontend/src/pages/CenterPanelContainer.tsx` | pass `events` |
| `frontend/src/components/templates/TracePanel.tsx` (or `AppShell.tsx`) | collapsed mode |
| `frontend/src/components/atoms/index.ts`, `molecules/index.ts`, `organisms/index.ts` | exports |

### Reuse without modification

- `frontend/src/lib/eventVisuals.ts` — `EVENT_VISUALS`, `EventTone`, `EXPANDED_BY_DEFAULT`
- `frontend/src/components/atoms/JumpToLatestPill.tsx` — sticky-bottom UX
- `frontend/src/lib/hooks/useRunStream` (or wherever it lives) — events source
- All event payload types in `frontend/src/types/events.ts` (auto-generated)

### Do not touch

- `frontend/src/components/organisms/TraceTimeline.tsx` and its container — keeps its role as raw-JSON debug view in the right panel
- `frontend/src/components/organisms/ResearchingBanner.tsx` — unreferenced after Phase 4 but kept alive; cleanup in a follow-up PR
- Backend (all event payloads already carry the needed fields)

---

## 4. Verification

1. **Unit + coverage:** `cd frontend && npx vitest run --coverage` — all tests green, ≥ 80 % on every new file.
2. **Lint:** `cd frontend && npx eslint src` — 0 errors (especially `import/no-restricted-paths`).
3. **Types:** `cd frontend && npx tsc --noEmit` — 0 errors with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
4. **A11y:** `jest-axe` clean on every new component + on updated `StructuredAnswer`/`StructuredBlocks`.
5. **Manual smoke (local):**
   - `npm run dev` (frontend) + backend with `provider=tavily` and a valid `TAVILY_API_KEY`.
   - Ask: *"Could AI systems realistically replace mid-level software engineers within the next 10 years?"* (from `docs/q-for-testing.md` §8).
   - Expected feed sequence visible in the center: `FeedStep` "Reading your question" → `PlanStepCard` with sub-claims → `SearchStepCard` "Searched the web · N results" with right-aligned hostnames → optionally `ContradictionDetected` → `JudgeVerdictCard` with confidence bar → `FeedStep` "Done".
   - Scroll up → `JumpToLatestPill` appears; click → snaps back to bottom.
   - After completion: feed collapses; toggle expands; reload → collapsed state persisted.
   - Final answer types in character-by-character with `BlinkingCursor`; click anywhere on the answer → skips to full text.
   - Right `TracePanel`: click collapse toggle → narrows to `w-10` with rotated label; reload → still collapsed.
6. **Prod deploy:** push to `main`, `systemctl restart novum`, `health=200`, repeat the smoke above on `https://novum-prod.duckdns.org`.

---

## 5. Decisions (locked in this iteration)

| # | Decision | Source |
|---|---|---|
| **D1** | `ToolCalled` groups consecutive `EvidenceAdded`, `SourceFailed`, and `DeepFetchPerformed` events with matching (or empty) `target_claim_id` until interrupted by a different family or by `ToolCalled` again. | User confirmed |
| **D2** | After completion, the feed stays above the answer, **collapsed by default**, with header `"Reasoning trace (N steps · Xs)"`. Answer renders below, expanded. | User confirmed |
| **D3** | Right `TracePanel` stays in parallel (not hidden) and gains a collapse toggle that narrows it to `w-10`. State persisted in `localStorage` key `novum_trace_panel_collapsed`. Close vs collapse are independent. | User confirmed |
| **D4** | Feed microcopy in English (per `/memories/language-policy.md`); final answer keeps user language (driven by backend prompt). | Language policy |
| **D5** | Motion v12 used for chevron rotation (200 ms), `FeedStep` fade-in on mount (150 ms), spinner on the active icon. | Plan default |
| **D6** | New token `--feed-search: #22d3ee` (cyan) distinguishes external actions (Tool/Evidence/DeepFetch) from internal (`--accent` for Plan/Judge). Other tones reuse the existing `EVENT_VISUALS` mapping. | Plan default |
| **D7** | Final-answer animation = **frontend-only typewriter** (no backend streaming). Adaptive speed (60/150/250 chars/s by length). Skip on click / `Esc` / `Space` / `scroll`. Auto-skip on `document.hidden` and `prefers-reduced-motion`. No re-animate on replay (`localStorage` key `novum_answered_runs`). Global toggle `novum_animate_answer` (default `true`). Real backend token streaming deferred to a future BRD. | User confirmed |

---

## 6. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `buildFeedSteps` mis-groups events when `target_claim_id` is missing on legacy/resumed runs. | Med | Default: include the evidence in the active search bucket. Fallback: orphan `EvidenceAdded` renders as `generic`. Covered by `feedGrouping.test.ts` cases (e) and (f). |
| Typewriter visibly slow on long answers (> 3000 chars). | Med | Adaptive `charsPerSecond` (250 above 1500 chars); click anywhere → instant skip; `prefers-reduced-motion` users skip entirely. |
| `IntersectionObserver` absent in old Vitest/jsdom — sticky-bottom breaks tests. | Low | Reuse the existing stub pattern from `TraceTimeline.test.tsx` (graceful fallback to sticky=true). |
| Right-panel collapse breaks responsive layout on small viewports. | Low | Only collapse when viewport ≥ md breakpoint; on smaller, fall back to the existing `rightPanelOpen=false` close behavior. Defer responsive polish if out of scope. |
| `ResearchingBanner` removal breaks tests we don't know about. | Low | Keep the file alive (don't delete); just stop referencing from `CenterPanelView`. Cleanup in a follow-up PR. |
| `react-markdown` rendering partial markdown during typewriter shows raw `*` / `#` glyphs briefly. | Low | Acceptable — Claude has the same artefact. Optional follow-up: detect open code-fences and pause typewriter until the closing fence is in `text`. |

---

## 7. Rollback strategy

The whole IP-24 is feature-flagged implicitly by the `events` prop on `CenterPanelView`: omitting it (or passing `[]`) makes `RunFeed` render empty and the rest of the UI behaves as before BRD-24. Per-component rollback paths:

1. **Phase 4 revert** (1-file revert in `CenterPanelView.tsx`) → restores `ResearchingBanner` immediately. All other code stays compiled and tested.
2. **Phase 5 revert** (`selectionStore` toggle removed + `TracePanel` collapsed branch removed) → trace panel reverts to always-full-width.
3. **Phase 3.5 revert** (`animate` prop removed) → answer appears instantly. Hook + helper survive harmlessly.
4. **Phases 0-3 are additive** — atoms/molecules/organism not referenced by anything else; can stay in the tree unused without UI impact.

No backend rollback. No DB migration. No event schema changes.

---

## 8. Further considerations (deferred to future BRDs)

1. **Real backend token streaming** of the synthesizer output (new `AnswerTokenStreamed` event + `litellm` `stream=True` + replay handling). Big scope; deferred.
2. **Streaming partial planner output** so the user sees the plan being drafted live. Optional polish.
3. **Source favicon caching** to avoid `s2/favicons` rate limits at scale. Probably never needed for a single-user prototype.
4. **Mobile responsive layout** for the new feed and collapsed trace panel (current scope assumes md+).

---

**End of IP-24.**
