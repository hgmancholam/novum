# Code Review CR-13-001 — Center Panel (BRD-13)

**Reviewer:** Reviewer Agent
**Date:** 2026-05-26
**Iteration:** 1 / 5
**Source BRD:** [BRD-13-center-panel.md](../brds/BRD-13-center-panel.md)
**Source Plan:** [IP-13-center-panel.md](../implementation-plans/IP-13-center-panel.md)

> **Scoring basis (per L-003):** The plan IP-13 §1 explicitly defers AC-02 (live answer streaming) and AC-04 (confidence formula UI) to BRD-10, justified against the actual V1 backend surface (no events GET, no `AnswerDrafted` / `ConfidenceCalculated` events, snake_case `RunResponse`). This review scores against the **plan**, not the BRD ideal.

---

## 1. Scope reviewed

| File | Change |
|---|---|
| [frontend/src/lib/api.ts](../../../frontend/src/lib/api.ts) | Added `RunResponseDto`, `StopReasonDto`, `QuestionTypeDto`, `OutputFormatDto`, `getRun`, `cancelRun`, `forkRun` |
| [frontend/src/types/run.ts](../../../frontend/src/types/run.ts) + [run.test.ts](../../../frontend/src/types/run.test.ts) | `Run`, `RunStatus`, `mapRun`, `deriveStatus` |
| [frontend/src/hooks/useRun.ts](../../../frontend/src/hooks/useRun.ts) + [useRun.test.tsx](../../../frontend/src/hooks/useRun.test.tsx) | TanStack Query data hook with cancel/fork mutations |
| [frontend/src/components/organisms/QuestionDisplay.tsx](../../../frontend/src/components/organisms/QuestionDisplay.tsx) + test | C2 |
| [frontend/src/components/organisms/ResearchingBanner.tsx](../../../frontend/src/components/organisms/ResearchingBanner.tsx) + test | C3 |
| [frontend/src/components/organisms/StopReasonCard.tsx](../../../frontend/src/components/organisms/StopReasonCard.tsx) + test | C7 / C8 / C9 / C10 |
| [frontend/src/components/organisms/ActionBar.tsx](../../../frontend/src/components/organisms/ActionBar.tsx) + test | Cancel (RF-08), Fork (disabled placeholder) |
| [frontend/src/components/organisms/CenterPanelView.tsx](../../../frontend/src/components/organisms/CenterPanelView.tsx) + test | Composition |
| [frontend/src/components/organisms/index.ts](../../../frontend/src/components/organisms/index.ts) | Barrel exports |
| [frontend/src/pages/CenterPanelContainer.tsx](../../../frontend/src/pages/CenterPanelContainer.tsx) + test | Data owner |
| [frontend/src/pages/RunPage.tsx](../../../frontend/src/pages/RunPage.tsx) | Wires container into `AppShell.center` |

---

## 2. Quality gates

| Gate | Status |
|---|---|
| `npm run build` | PASS (reported by author) |
| `npm run typecheck` | PASS (reported by author) |
| `npx vitest run` (full suite) | **PASS — 219 / 219, 28 files** |
| BRD-13 test files (8 files, 40 tests) | **PASS — 40 / 40** |
| `jest-axe` a11y on every new organism | PASS |
| Atomic Design layering (ESLint `import/no-restricted-paths`) | PASS — `useRun` imported only by `pages/CenterPanelContainer.tsx` |
| Template/organism collision avoided | PASS — organism is `CenterPanelView`, geometry stays `templates/CenterPanel` |
| Token-only styling (no hex / Tailwind greys for surfaces) | PASS — all surfaces use `var(--text-*)`, `var(--bg-*)`, `var(--glass-*)`, `var(--semantic-*)` |
| Auth headers on mutations (L-007) | PASS — `cancelRun` / `forkRun` use `getAuthHeaders()`; GET is public |
| `exactOptionalPropertyTypes` (L-006) | PASS — optional props typed as `T \| undefined` |
| Language policy (English code) | PASS |

Coverage instrumentation is not installed (`@vitest/coverage-v8` missing), so I could not produce a numeric coverage report. The 40 tests exercise every conditional branch in each new file (all 7 `StopReason` values, both `RunStatus` values, loading / error / running / stopped / cancel-flip transitions, auth-header presence, undefined `runId` short-circuit, fork body payload), which is strong qualitative evidence of ≥ 80 % coverage on the new surface. **Not a blocker — recommended follow-up: add `@vitest/coverage-v8` to dev dependencies.**

---

## 3. Acceptance Criteria Mapping (against IP-13 §3)

| AC | Plan status | Evidence |
|---|---|---|
| AC-01 Question displays (C2) | ✅ in-scope | `QuestionDisplay` + 2 tests; `CenterPanelView` test asserts heading content |
| AC-02 Answer streams live (C6) | ❌ deferred to BRD-10 (IP §1) | Out of scope — correctly omitted |
| AC-03 Cancel stops research (RF-08) | ✅ in-scope | `ActionBar` cancel → `useRun.cancel` → POST `/api/runs/{id}/cancel` with `X-Username` + `X-Token`; container test asserts banner → stop-reason flip |
| AC-04 Confidence `min(S,J)` (RF-12) | ❌ deferred to BRD-10 (IP §1) | Out of scope — correctly omitted |

UI-prototype states C1, C2, C3, C7, C8, C9, C10 are all covered as the plan promised. C4/C5/C6/C11/C12/C13 are correctly deferred.

---

## 4. Strengths

- **Plan/code alignment is excellent.** Every task in IP §2 (#1–#12) maps to a concrete file; nothing was silently expanded or skipped.
- **Clean separation of concerns.** Organisms are pure presentational, the `useRun` hook is isolated to `pages/`, and the geometry template is untouched. The naming `CenterPanelView` vs `templates/CenterPanel` avoids the collision flagged in IP §1.
- **All 7 `stop_reason` enum values handled** in `stopReasonConfig` (RF-02 compliance), driven by a typed `Record<StopReason, ReasonEntry>` so adding a new value is a compile-time obligation.
- **Token discipline is strict.** `StopReasonCard` even uses `color-mix(in srgb, …)` against `var(--bg-secondary)` instead of a hardcoded tint — exactly the pattern UI-prototype §1 prescribes.
- **`deriveStatus` is correctly conservative.** The "stopped without reason" edge case (`stopped_at` set, `stop_reason` null) is covered by both a unit test and a `CenterPanelView` test, and the UI degrades gracefully (question only, no card).
- **a11y baseline.** Every organism has a `jest-axe` violation-free assertion; `StopReasonCard` runs the axe check across all 7 variants.
- **Auth attached at the boundary.** `lib/api.ts` is the only place reading `getAuthHeaders()`; the hook is auth-agnostic.

---

## 5. Issues

### Blockers
*None.*

### Major
*None.*

### Minor

1. **`ResearchingBanner` announces the label twice to screen readers.**
   [ResearchingBanner.tsx#L24](../../../frontend/src/components/organisms/ResearchingBanner.tsx#L24) passes `label="Researching…"` to `<Spinner>` (which becomes its `aria-label` / inner status text) and then renders a visible `<span>{label}</span>` immediately after. The wrapper is also `role="status" aria-live="polite"`. Net effect: a polite live region may announce "Researching… Researching…". Either drop the `label` prop on the `<Spinner>` (so the spinner is decorative) or mark the visible `<span>` with `aria-hidden="true"`. Tests would still pass with `getAllByText`.

2. **`ActionBar` Fork button receives props it cannot exercise.**
   [ActionBar.tsx#L67-L74](../../../frontend/src/components/organisms/ActionBar.tsx#L67) forwards `onClick={onFork}` and `loading={isForking}` to a permanently `disabled` button. Functional, but the props are dead code in V1. Acceptable as forward-compat for BRD-15; consider a `// BRD-15: enabled when trace picker lands` one-liner to signal intent.

### Nits

3. **`useRun.ts` queryKey sentinel.** [useRun.ts#L51](../../../frontend/src/hooks/useRun.ts#L51) uses `["run", "__noop__"]` when `runId === undefined`. Works because `enabled` short-circuits the fetch, but the sentinel pollutes the query cache namespace. A defensible alternative is `queryKey: ["run", runId ?? null]` with a narrow type. Cosmetic.

4. **`CenterPanelContainer` has a redundant error check.** [CenterPanelContainer.tsx#L38-L40](../../../frontend/src/pages/CenterPanelContainer.tsx#L38) checks `isError` inside the loading branch and again at line 60. Reachable, just slightly belt-and-braces. Reads fine.

5. **`UseQueryOptions` explicit annotation in `useRun`.** TanStack Query can infer the generics here; the explicit `UseQueryOptions<RunResponseDto, Error, Run>` is harmless but adds noise. Style.

6. **Coverage tooling missing.** `@vitest/coverage-v8` is not installed, so `vitest run --coverage` fails with `MISSING DEPENDENCY`. Quantitative coverage cannot be enforced in CI today. Track as repo follow-up (independent of BRD-13).

---

## 6. Per-file notes

| File | Verdict | Notes |
|---|---|---|
| `lib/api.ts` | ✅ | DTOs are correctly snake-case; type unions match `domain/enums.py`. Auth headers spread last so callers can override only intentionally. |
| `types/run.ts` | ✅ | `mapRun` is the single mapping point (IP §6 risk mitigation). Re-exporting `RunResponseDto` is harmless and convenient. |
| `hooks/useRun.ts` | ✅ (with nit #3, #5) | Status derivation lives in `types/run.ts` and is reused via `deriveStatus` — good. Invalidates both `["run", id]` and `["runs"]` on success — correct for BRD-12 list sync. |
| `organisms/QuestionDisplay.tsx` | ✅ | Minimal, presentational, semantic `<h1>`. |
| `organisms/ResearchingBanner.tsx` | ✅ (with minor #1) | Token-clean. The double-announcement is the only weakness. |
| `organisms/StopReasonCard.tsx` | ✅ | Best file in the change set. Microcopy faithfully matches BRD-13 §4.8. Variant-driven styling via `color-mix` is precisely what UI-prototype §1 wants. |
| `organisms/ActionBar.tsx` | ✅ (with minor #2) | Cancel disabled-when-not-running and disabled-when-cancelling are both tested. `data-testid="live-dot"` exposes the affordance for future trace tests. |
| `organisms/CenterPanelView.tsx` | ✅ | Composes cleanly; explicit `null` for the no-reason-but-stopped branch is correct. |
| `organisms/index.ts` | ✅ | Exports both runtime and type symbols consistently with the BRD-12 pattern. |
| `pages/CenterPanelContainer.tsx` | ✅ (with nit #4) | Renders the existing `templates/CenterPanel` slots correctly. Uses `<StopReasonCard reason="errored" />` for load failures — clever reuse. |
| `pages/RunPage.tsx` | ✅ | Single-line wiring. `TracePanel` stub kept untouched. |

---

## 7. Test coverage assessment

| Suite | Tests | Branches covered |
|---|---|---|
| `types/run.test.ts` | 4 | `mapRun` field renames, `deriveStatus` all 3 paths |
| `hooks/useRun.test.tsx` | 7 | running, stopped, fetch error, loading state, undefined `runId` short-circuit, cancel + auth headers, fork + body payload |
| `QuestionDisplay.test.tsx` | 2 | render + axe |
| `ResearchingBanner.test.tsx` | 3 | default label, custom label, axe |
| `StopReasonCard.test.tsx` | 9 | all 7 reasons × (title+desc+variant), explanation slot, axe per variant |
| `ActionBar.test.tsx` | 7 | running enables cancel, cancelling disables, stopped disables, undefined disables, Fork disabled with tooltip, Live/Stopped indicator, axe |
| `CenterPanelView.test.tsx` | 3 | running → banner, stopped+reason → card, stopped+no reason → empty |
| `CenterPanelContainer.test.tsx` | 5 | C1 loading, running render, terminal render, load error → errored card, cancel-flip integration |
| **Total** | **40** | All conditional branches in the new code. |

Empirically ≥ 80 % statement coverage on the BRD-13 surface; cannot certify numerically until `@vitest/coverage-v8` is added.

---

## 8. Architectural & compliance checks

| Rule | Status |
|---|---|
| 3 plugin seams untouched | ✅ — no `Source` / `StoppingSignal` / `OutputRenderer` changes |
| Events append-only (RF-03) | N/A — frontend read path only |
| Stop reasons are the 7 enum values (RF-02) | ✅ — `stopReasonConfig` exhaustively typed |
| Confidence `min(S, J)` (RF-12) | N/A this BRD — deferred to BRD-10 per IP §1 |
| No Redis / distributed primitives (RF-05) | ✅ |
| FE↔BE type contract | ✅ — DTOs typed manually but unions match `domain/enums.py`; reconciliation with `scripts/export_types.py` is a separate task |
| UI-prototype §1 tokens, §3 panel states, §7 microcopy | ✅ — verified |
| Atomic design (`atoms → molecules → organisms → templates → pages`) | ✅ — only `pages/` fetches data |
| English in all code artifacts | ✅ |

---

## 9. Score

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Code Quality | 9.5/10 | 25 % | 2.375 |
| Test Coverage | 9.5/10 | 20 % | 1.900 |
| Architecture Compliance | 10/10 | 20 % | 2.000 |
| Documentation | 9/10 | 15 % | 1.350 |
| Security | 10/10 | 10 % | 1.000 |
| Performance | 10/10 | 10 % | 1.000 |
| **TOTAL** | | | **9.6 / 10** |

Deductions:
- −0.5 Code Quality: `ResearchingBanner` double-announcement (minor #1) and Fork-button dead props (minor #2).
- −0.5 Test Coverage: cannot produce numeric coverage; `@vitest/coverage-v8` not installed (nit #6).
- −1.0 Documentation: per-file headers cite BRD/IP sections but not RF numbers; no inline comment near the `__noop__` sentinel explaining the choice.

---

## 10. Decision

**✅ APPROVE** — score 9.6 ≥ 9.0 gate. Proceed to F5 (complete).

The two deferred ACs (AC-02, AC-04) are explicitly tracked in IP-13 §1/§3 and D-013, satisfying L-003. Recommend the follow-ups in §5 (minors and coverage tooling) be folded into BRD-10 work rather than blocking this gate.

---

## 11. Required changes

*None.* The minors and nits in §5 are non-blocking; either fold them into BRD-10 or open a small follow-up issue for the a11y duplicate-announcement and the coverage tooling.
