# Code Review Report — CR-14-001 (Trace Panel)

**User Story / BRD:** BRD-14 (Trace Panel, right sidebar)
**Implementation Plan:** [IP-14-trace-panel.md](../implementation-plans/IP-14-trace-panel.md)
**Iteration (F3 ↔ F4):** 1 / 5
**Date:** 2026-05-26
**Reviewer:** Reviewer Agent

---

## Summary score

| Criterion | Score | Weight | Weighted |
|---|---:|---:|---:|
| Code Quality | 8.5 | 25 % | 2.125 |
| Test Coverage | 5.0 | 20 % | 1.000 |
| Architecture Compliance | 9.5 | 20 % | 1.900 |
| Documentation | 9.0 | 15 % | 1.350 |
| Security | 9.5 | 10 % | 0.950 |
| Performance | 8.5 | 10 % | 0.850 |
| **TOTAL** | | | **8.2 / 10** |

## Verdict

**CHANGES_REQUESTED** — score 8.2 < 9.0 gate. Coder iteration 2 required.

The implementation is architecturally excellent and matches the prototype's intent very closely, but two concrete test failures and two missing test files (for the only stateful pieces of the feature) keep it below the F4 quality gate.

---

## Per-criterion breakdown

### 1. Code Quality — 8.5 / 10

Positive:
- File-header docstrings on every new module; comments only where the WHY is non-obvious.
- Strict types throughout; no `any`; `noUncheckedIndexedAccess` respected (e.g. `items[0]?.type` in [TraceTimeline.tsx](../../../frontend/src/components/organisms/TraceTimeline.tsx#L200)).
- Clean separation of pure helpers (`keyOf`, `summaryOf`, `metaLine`, `formatPrimitive`).
- `EVENT_VISUALS` typed as `Record<EventType, EventVisual>` so any missing arm fails the compiler — strongest possible exhaustiveness guarantee.
- `getEventVisual` provides a tested fallback for synthetic SSE frames such as `"cancelled"` ([eventVisuals.ts#L72-L78](../../../frontend/src/lib/eventVisuals.ts#L72-L78)).

Issues:
- **[BUG]** [EventPayloadViewer.tsx#L165-L180](../../../frontend/src/components/atoms/EventPayloadViewer.tsx#L165-L180) — when `value={}` the `isObject` branch is taken but `Object.entries({}).map(...)` yields an empty array, so nothing is rendered. The dedicated `ObjectValue` empty-state (`"{}"`) is only reachable for nested empties, never the root. This is a real runtime issue that surfaces any time an event arrives with an empty payload object, and is the cause of the failing unit test.
- **[A11y risk, non-blocking now]** [EventNode.tsx#L75-L110](../../../frontend/src/components/molecules/EventNode.tsx#L75-L110) — the toggle `<button>` wraps the entire row including a `<span data-testid="event-fork-slot">`. In V1 this slot is `null`, so it is fine; once BRD-15 ships a real `ForkButton` inside that slot we will have a `<button>` nested in a `<button>`, which is invalid HTML and an a11y violation. Recommend converting the outer interactive element to a `<div>` with `role="button"` + `onKeyDown` (or splitting the toggle into a chevron sub-button) before BRD-15.
- `EventPayloadViewer` renders `<div>` blocks inside `<pre>` ([L156-L188](../../../frontend/src/components/atoms/EventPayloadViewer.tsx#L156-L188)). Browsers tolerate it but `<pre>` is phrasing content; an inner `<div className="font-mono">` would be more correct.
- Tone tokens `info`, `judge` and `decision` all resolve to `var(--accent)` ([eventVisuals.ts#L87-L94](../../../frontend/src/lib/eventVisuals.ts#L87-L94)) — semantically distinct categories collapsed to one color. Acceptable for V1 but worth a `// TODO(ui-prototype §1)` note so it is not lost.

### 2. Test Coverage — 5.0 / 10

This is the dominant reason the score is below 9. IP-14 §4 task #14 and §8 explicitly require co-located tests on **every** new file, and L-002 requires ≥ 80 % coverage.

- **Missing entirely** — `frontend/src/components/organisms/TraceTimeline.test.tsx`. This is the most behavior-rich file in the change set: it owns expansion state, IntersectionObserver-driven sticky-bottom auto-scroll, the `JudgeRuled`-pre-expanded seeding (AC-06), T1b conditional (AC-05) and the `JumpToLatestPill` overlay (AC-07). None of these behaviors are unit-tested.
- **Missing entirely** — `frontend/src/pages/TracePanelContainer.test.tsx`. Required by IP-14 §4 task #15 (mock `useRunStream`, assert T1b → T2 → T3 transitions and live-indicator toggling).
- **Failing** — `EventPayloadViewer.test.tsx > "renders an empty object placeholder"` (1 failure). Caused by the empty-object bug above; the test is correct.
- **Failing** — `EventNode.test.tsx > "has no accessibility violations"`. The `<li>` is rendered without an `<ol>`/`<ul>` ancestor in the test harness, so the axe `listitem` rule reports a violation. Runtime usage inside `TraceTimeline` does wrap it in `<ol>`, so this is a test-setup defect rather than a product bug. Fix by wrapping the render in `<ol>{...}</ol>` (or rendering through `TraceTimeline`).

Positive on what is present:
- `eventVisuals.test.ts` is exhaustive against the 19-member `EventType` union and pins `EXPANDED_BY_DEFAULT.size === 1` (`JudgeRuled` only) — exactly what the plan asked for ([eventVisuals.test.ts#L65-L70](../../../frontend/src/lib/eventVisuals.test.ts#L65-L70)).
- Atoms and molecules have a11y assertions and prop-driven behavior assertions (no fake timers, per L-011).

### 3. Architecture Compliance — 9.5 / 10

- **Atomic layering enforced.** Data hook `useRunStream` is only called in [TracePanelContainer.tsx#L22-L26](../../../frontend/src/pages/TracePanelContainer.tsx#L22-L26), inside `pages/`, satisfying the `import/no-restricted-paths` rule from `eslint.config.js` and `.github/copilot-instructions.md` §3.
- **Geometry vs content split honored.** `templates/TracePanel` is used unchanged; only its `header`/`body` slots are populated. Matches IP-14 §3.1.
- **Single source of truth for icon/tone mapping.** `lib/eventVisuals.ts` is consumed by `EventIcon` only; no duplicate switches elsewhere — verified via repository search.
- **Mount points correct.** `<TracePanelContainer />` is mounted from [RunPage.tsx#L17](../../../frontend/src/pages/RunPage.tsx#L17) (`/runs/:runId`) and **not** from `HomePage.tsx`, which passes `<TraceEmpty />` directly ([HomePage.tsx#L25](../../../frontend/src/pages/HomePage.tsx#L25)). This satisfies AC-10 and the T1a vs T1b/T2/T3 split.
- **No new event types over the SSE wire** — pure consumer, confirmed.
- **Tokens-only styling.** No raw Tailwind palette (`bg-blue-50`, `text-gray-700`, …) anywhere in the new components — verified by regex search across all eight new files. Every color goes through `var(--…)` tokens.
- Minor: `TraceTimeline` does not reset `expandedKeys` when `events` reference changes due to a new `runId`. Practically the `runId` change unmounts the timeline (the container's body switches), so this is not a real bug today, but if the timeline is ever lifted to a parent that survives `runId` changes the seed set could leak. Worth a comment.

### 4. Documentation — 9.0 / 10

- Every new file has a top-level JSDoc describing scope, owners and references to the plan / prototype sections.
- Public props interfaces are exported and annotated.
- Microcopy constants (`TRACE_EMPTY_MESSAGE`, `PLAN_PREVIEW_STEPS`) are exported, so tests and downstream code share a single string. Verbatim with `ui-prototype.md` §7.
- No README / index entry mentions the new components — minor. The `components/{atoms,molecules,organisms}/index.ts` re-exports are listed in §4 task 13; I did not verify they were updated.

### 5. Security — 9.5 / 10

- `EventPayloadViewer` renders via text nodes only (`{text}`, `JSON.stringify(...)`) — no `dangerouslySetInnerHTML`, no markdown evaluation. JSON injection cannot create DOM.
- No new network calls.
- No secrets / tokens in source.

### 6. Performance — 8.5 / 10

- `items` derivation memoized on `events` ([TraceTimeline.tsx#L94-L116](../../../frontend/src/components/organisms/TraceTimeline.tsx#L94-L116)).
- `IntersectionObserver` set up once with stable refs.
- `EventPayloadViewer` short-circuits values whose JSON is > 5 KB into a placeholder, addressing the §9 risk row.
- Possible re-render storm on `events` array identity change — each frame creates a new `items` array. Acceptable at the expected event volumes (< 100), but virtualization is correctly listed as V2 in §10.

---

## Blocking issues (must fix to reach ≥ 9)

1. **Fix `EventPayloadViewer` empty-object rendering bug** — render `{}` (and continue to render `[]` correctly) when `value` is an empty object. Currently the top-level branch maps over `Object.entries({})` and produces no output. File: [EventPayloadViewer.tsx#L165-L188](../../../frontend/src/components/atoms/EventPayloadViewer.tsx#L165-L188). This unblocks the failing unit test as a side effect.
2. **Resolve `EventNode` a11y test failure** — fix the test harness (render the `<EventNode>` inside an `<ol>` wrapper, or switch the component to a context-free element). Pure test-setup change; no product behavior changes.
3. **Add `frontend/src/components/organisms/TraceTimeline.test.tsx`** covering: T1b conditional (PlanPreview shown when `events.length === 0` or only `QuestionAsked`); `JudgeRuled` arrives pre-expanded; toggling expands/collapses other nodes; sticky-bottom via stubbed IntersectionObserver; `JumpToLatestPill` shown only when `!sticky && !isComplete`. Required by IP-14 §4 task #14 and §8.
4. **Add `frontend/src/pages/TracePanelContainer.test.tsx`** covering: T1a (no `runId`) does not subscribe and renders `TraceEmpty`; T1b/T2/T3 transitions driven by a mocked `useRunStream`; live indicator off once `isComplete` flips. Required by IP-14 §4 task #15 and §8.
5. **Maintain ≥ 80 % line + branch coverage on every new file** (L-002 quality gate) and re-run `npx vitest run --coverage` before re-submitting.
6. **All tests must pass** under `npx vitest run` (0 failures) before re-review.

## Non-blocking suggestions

- Consider switching the outer `<button>` in `EventNode` to `<div role="button" tabIndex={0}>` (with `onKeyDown`) **before BRD-15** lands so the future `ForkButton` does not produce a nested-button violation.
- Replace the `<div>`-in-`<pre>` nesting in `EventPayloadViewer` with a styled `<div className="font-mono whitespace-pre-wrap">` to keep the HTML strictly valid.
- Add a `// TODO(ui-prototype §1)` next to `TONE_COLOR` noting that `info`, `judge` and `decision` currently collapse to `--accent`; revisit when distinct tone tokens are introduced.
- In `TraceTimeline`, reset `expandedKeys` when an upstream `runId` change is signaled (defensive — not needed today since the timeline unmounts).
- Update the `components/{atoms,molecules,organisms}/index.ts` barrel files if not already done (IP-14 §4 task #13).

## Compliance verification (selected ACs)

| AC | Verified? | Notes |
|---|---|---|
| AC-01 chronological order (T2) | ✅ | `items.map` preserves arrival order. |
| AC-02 sticky auto-scroll | ⚠️ untested | Implementation matches plan; no unit test asserts it. |
| AC-03 inline expand (T4) | ✅ at code level | Tested in `EventNode.test.tsx`; integration in `TraceTimeline` untested. |
| AC-04 fork points highlighted | ✅ | `data-decision="true"` set; button deferred to BRD-15 as planned. |
| AC-05 T1b PlanPreview gating | ⚠️ untested | Logic present in `TraceTimeline`; no test. |
| AC-06 `JudgeRuled` arrives expanded | ⚠️ untested | Seeded via `EXPANDED_BY_DEFAULT`; no `TraceTimeline` test asserts it end-to-end. |
| AC-07 sticky-when-at-bottom + Jump pill | ⚠️ untested | IO sentinel implemented; no test. |
| AC-08 Lucide-only + tokens-only | ✅ | Verified by regex search across all 8 new components. |
| AC-09 live indicator off in T3 | ✅ | `isStreaming = isConnected && !isComplete` in container. |
| AC-10 container only subscribes with `runId` | ✅ | `enabled: runId !== undefined && runId.length > 0`. |

---

## Positive highlights

- The exhaustive `EVENT_VISUALS` map keyed on the auto-generated `EventType` union is the right way to guarantee BRD §1 corrections cannot regress. The matching unit test pins all 19 members.
- `TracePanelContainer` is a textbook example of the atomic-design / data-in-pages discipline from `.github/copilot-instructions.md` §3.
- Microcopy strings are externalized as named exports (`TRACE_EMPTY_MESSAGE`, `PLAN_PREVIEW_STEPS`) and match `ui-prototype.md` §7 verbatim.
- The `data-sticky` / `data-complete` attributes on `TraceTimeline` are a deliberate test affordance and will make the missing tests easy to write.

---

## Required iteration plan (handoff to Coder)

1. Patch `EventPayloadViewer` empty-object branch + keep its test green.
2. Wrap `EventNode` test in `<ol>` (or switch markup) to clear the axe violation.
3. Write `TraceTimeline.test.tsx` per the assertions enumerated above.
4. Write `TracePanelContainer.test.tsx` mocking `useRunStream`.
5. Re-run `npx vitest run --coverage`, `npx tsc --noEmit`, `npx eslint .` — all must be green and coverage ≥ 80 % on each new file.

Next gate: F4 iteration 2 of 5.
