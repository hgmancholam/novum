# Code Review CR-13-002 — Center Panel (Iteration 2)

**Source BRD:** [BRD-13-center-panel.md](../brds/BRD-13-center-panel.md)
**Implementation Plan:** [IP-13-center-panel-iter2.md](../implementation-plans/IP-13-center-panel-iter2.md)
**Predecessor review:** CR-13-001 (iter 1 — 9.6/10, approved minimal)
**Iteration:** 2 (1st review of iter 2)
**Reviewer:** Reviewer Agent
**Date:** 2026-05-26
**Decision record:** D-018

---

## 1. Score

| Criterion | Weight | Score | Weighted |
|---|---:|---:|---:|
| Code Quality (atomic design, readability, microcopy fidelity) | 25 % | 8.0 | 2.00 |
| Test Coverage (presence, jest-axe, stability) | 20 % | 7.5 | 1.50 |
| Architecture Compliance (hook-in-pages, plugin seams, RF-11/13) | 20 % | 10.0 | 2.00 |
| Documentation (docstrings, deferred-decision honesty) | 15 % | 9.5 | 1.425 |
| Security (auth headers, error surfacing) | 10 % | 10.0 | 1.00 |
| Performance (interval scoping, render memoization) | 10 % | 9.5 | 0.95 |
| **TOTAL** | | | **8.88 / 10** |

**Threshold for approval:** ≥ 9.0/10.
**Verdict:** **Returned to Coder** — 2 MUST-FIX items (flaky test + ESLint errors) and microcopy drift block approval, but the scope is narrow (~30 min of work). No architectural rework needed.

---

## 2. Strengths

1. **Atomic-Design layering is intact.** `useRun`/`useCreateRun` are only consumed by `pages/*` ([NewRunContainer.tsx#L24](../../../frontend/src/pages/NewRunContainer.tsx#L24-L31), [CenterPanelContainer.tsx#L21-L24](../../../frontend/src/pages/CenterPanelContainer.tsx#L21-L24)). Organisms (`QuestionForm`, `RunHeader`, `TrustSummary`, `NotFoundCard`) are pure presentational. ESLint `import/no-restricted-paths` keeps this honest.

2. **API client policy (L-008) followed by construction.** `createRun` and `resumeRun` go through `api.post` with `getAuthHeaders()` ([api.ts#L172-L208](../../../frontend/src/lib/api.ts#L172-L208)). No raw `fetch("/api/…")` anywhere.

3. **`exactOptionalPropertyTypes` (L-006) correctly applied** on every new optional prop:
   - [OutcomeBar.tsx#L31-L34](../../../frontend/src/components/atoms/OutcomeBar.tsx#L31-L34)
   - [ElapsedClock.tsx#L18-L23](../../../frontend/src/components/molecules/ElapsedClock.tsx#L18-L23)
   - [MetaRow.tsx#L11-L17](../../../frontend/src/components/molecules/MetaRow.tsx#L11-L17)
   - [ActionBar.tsx#L19-L30](../../../frontend/src/components/organisms/ActionBar.tsx#L19-L30)
   - [RunHeader.tsx#L8-L13](../../../frontend/src/components/organisms/RunHeader.tsx#L8-L13)

4. **RF-11 correctly enforced.** `RESUMABLE` set in [ActionBar.tsx#L32-L35](../../../frontend/src/components/organisms/ActionBar.tsx#L32-L35) limits the Resume button to `errored` and `user_cancelled`. `showResume` returns `false` for terminal states and while running. Verified by [ActionBar.test.tsx](../../../frontend/src/components/organisms/ActionBar.test.tsx) (10 cases including a11y).

5. **RF-13 honored — no trust dimension hidden.** `TrustSummary` renders all dimensions (Outcome, Threshold, Confidence, Iterations, Sources, Started, Stopped). Pending values use a `—` placeholder with an explicit `title="Pending event log (BRD-10)"` so the user sees *what is missing* and *why*. See [TrustSummary.tsx#L42-L106](../../../frontend/src/components/organisms/TrustSummary.tsx#L42-L106).

6. **OutcomeBar variant table matches §3.2.5 verbatim** for all 7 enum values ([OutcomeBar.tsx#L12-L20](../../../frontend/src/components/atoms/OutcomeBar.tsx#L12-L20)). `aria-hidden="true"` + `role="presentation"` is correct for a decorative strip.

7. **NotFoundCard wired before the generic error path** ([CenterPanelContainer.tsx#L42-L44](../../../frontend/src/pages/CenterPanelContainer.tsx#L42-L44)). `isNotFound` is computed from `ApiClientError.status === 404` in [useRun.ts#L128-L129](../../../frontend/src/hooks/useRun.ts#L128-L129) — clean.

8. **Design-token discipline.** Zero hex codes, zero Tailwind grey-/slate-* in any file under `src/components/` or `src/pages/`. All colors via `var(--…)`.

9. **Auth-gate UX.** `NewRunContainer` preserves the question draft when an anonymous user submits, then opens the login modal ([NewRunContainer.tsx#L36-L42](../../../frontend/src/pages/NewRunContainer.tsx#L36-L42)) — matches §3.2 C2 spec.

10. **Resume errors surfaced inline.** `resumeError.message` is rendered with `role="alert"` next to the panel ([CenterPanelContainer.tsx#L95-L101](../../../frontend/src/pages/CenterPanelContainer.tsx#L95-L101)) — user sees backend rejection without a toast dependency.

11. **Test breadth.** 39 test files / 273 cases; new files: `OutcomeBar`, `ElapsedClock`, `MetaRow`, `TypeDisclosure`, `SuggestionChips`, `QuestionForm`, `RunHeader`, `TrustSummary`, `NotFoundCard`, `NewRunContainer`, `useCreateRun`. Every new component has at least one `jest-axe` assertion.

---

## 3. Issues

### 3.1 MUST FIX (block approval)

#### M-1 — `ElapsedClock` test is flaky in full-suite runs (L-009)

**File:** [ElapsedClock.test.tsx#L40-L47](../../../frontend/src/components/molecules/ElapsedClock.test.tsx#L40-L47)
**Symptom:**
```
FAIL  src/components/molecules/ElapsedClock.test.tsx > ticks every second while not frozen
Expected: "3s"   Received: "6s"
```
Passes in isolation (`vitest run ElapsedClock.test.tsx`), fails when the full suite runs. This is the L-009 fake-timer pitfall already documented in memory.

**Root cause hypothesis:** `vi.useFakeTimers()` interacts poorly with `Date.now()` being read inside `setInterval` after another worker’s system-time mutation bleeds through (or the React-scheduler timer is double-counted). The test received exactly 2× the expected elapsed (3 s → 6 s), suggesting interval fired both at +1 s and +0.5 s ticks or that an extra render captured a later `Date.now()`.

**Fix options (any one):**
- Use `vi.setSystemTime` + advance by absolute time before each assertion (`vi.setSystemTime(t0); render(); vi.setSystemTime(t0 + 3000); vi.runOnlyPendingTimers();`).
- Inject `now` prop in the test (the component already accepts it — see [ElapsedClock.tsx#L19-L20](../../../frontend/src/components/molecules/ElapsedClock.tsx#L19-L20)) and avoid timer advancement entirely.
- Add `vi.clearAllTimers()` in `beforeEach`.

**Why this blocks merge:** the test fails on CI as part of the full run. Per `testing-policy` memory note, "Do not mark a task complete until tests pass locally."

#### M-2 — ESLint errors introduced by iter 2

Five new lint errors block clean CI:

| File | Line | Rule | Suggested fix |
|---|---:|---|---|
| `pages/NewRunContainer.tsx` | 49 | `@typescript-eslint/no-floating-promises` | `navigate(...)` returns a Promise in RR v7; wrap with `void navigate(...)`. |
| `pages/NewRunContainer.tsx` | 69 | `@typescript-eslint/no-misused-promises` | `onSubmit={(v) => { void handleSubmit(v); }}` instead of passing the async fn directly. |
| `pages/NewRunContainer.test.tsx` | 91 | `require-await` | Remove `async` from the handler with no `await`. |
| `pages/NewRunContainer.test.tsx` | 121 | `no-non-null-assertion` | Replace `foo!` with an explicit guard. |
| `pages/CenterPanelContainer.test.tsx` | 67 | `require-await` | Remove `async` from the handler. |

(Other lint errors in `lib/clipboard.ts`, `lib/format.ts`, `lib/sse.ts`, `test/jest-axe.d.ts` are pre-existing and out of scope for CR-13-002.)

### 3.2 SHOULD FIX (recommend before merge)

#### S-1 — `QuestionForm` microcopy drifts from §7.2

Criterion 4 (verbatim match) is breached. Differences observed in [QuestionForm.tsx](../../../frontend/src/components/organisms/QuestionForm.tsx):

| Surface | Spec (§7.2) | Code |
|---|---|---|
| Context placeholder | *"Anything Novum should know up front. Not treated as evidence."* | *"Anything Novum should know (audience, constraints, scope)…"* |
| Context textarea label | *"Background context (optional)"* | (no `<label>`; only the toggle button text *"Add context (optional) ▸"*) |
| Format selector legend | *"Answer format"* | *"Output format"* |
| Format option | *"Structured (recommended)"* | *"Structured"* |
| Threshold preset label | *"Custom…"* | *"Custom"* |
| Threshold tooltip | *"Higher threshold = the agent searches longer and may honest-stop more often."* | missing |
| Submit-disabled tooltip | *"Type a question to start."* | missing |

These are pure-string changes (no logic changes) and should land before merge to keep the spec as single source of truth.

#### S-2 — `TrustSummary` line 1 shape does not match §7.7

Iter 2 correctly defers metrics to BRD-10, but §7.7 prescribes a **specific line-1 string per stop_reason** that this iteration *could* render today from the `RunResponse` alone. For example:
- `judge_confirmed` → *"✓ Judge confirmed · confidence — / threshold 0.60"*
- `honest_unanswerable` → *"⚠ Honest stop · question is unanswerable"*

The current implementation renders a generic `dl` with one row per dimension and uses `StopReasonCard` titles instead. This is a shape regression that BRD-10 will then need to refactor rather than just plug in numbers. Recommend rendering line 1 verbatim per §7.7 with `—` placeholders where confidence/elapsed are not yet computed.

#### S-3 — `useEffect` dep-array warning suppressed in `QuestionForm`

[QuestionForm.tsx#L87-L100](../../../frontend/src/components/organisms/QuestionForm.tsx#L87-L100) uses `eslint-disable-next-line react-hooks/exhaustive-deps`. The intent ("only overwrite when empty") is defensible, but a cleaner pattern is to make the parent fully control the textarea (`value` + `onChange` props) — that would eliminate the effect entirely and the disable comment with it. Defer to next iteration if time-boxed.

### 3.3 NICE TO HAVE

#### N-1 — `SuggestionChips` silently no-ops when textarea already has text

If the user types something, then clicks a chip, the chip *appears* to fail (because the `initialQuestion` effect guards on `question === ""`). Consider one of:
- swap to a controlled prop pattern so the chip always wins,
- add a visual confirmation toast,
- disable the chip when `draft !== ""`.

#### N-2 — `MetaRow` mixes `·` separators inside each chip

[MetaRow.tsx#L52-L75](../../../frontend/src/components/molecules/MetaRow.tsx#L52-L75) renders `<span aria-hidden="true">·</span>` *inside* each chip. Visually the chips already have border+padding, so the inner `·` reads as decorative noise. Drop the inner separators or move them between chips.

#### N-3 — `OutcomeBar` could announce variant for AT users

`role="presentation" aria-hidden="true"` is appropriate for the colored strip itself, but the `RunHeader` does not include the human-readable outcome text in an `aria-live` region. The `StopReasonCard` covers this on terminal states; just confirming the redundancy is intentional.

---

## 4. Acceptance Criteria Checklist

| AC | Result | Evidence |
|---|---|---|
| **AC-05** Home `/` starts a run from `QuestionForm`; anonymous opens login modal preserving draft; success navigates to `/runs/:id`. | ✅ **Pass** | [NewRunContainer.tsx#L36-L52](../../../frontend/src/pages/NewRunContainer.tsx#L36-L52); test "submits the question and navigates to /runs/:id on success". |
| **AC-06** `TypeDisclosure` (5 supported + 3 rejected, RF-06) + `SuggestionChips` (3 examples); picking a chip seeds textarea without submitting. | ✅ **Pass** | [TypeDisclosure.tsx#L17-L29](../../../frontend/src/components/molecules/TypeDisclosure.tsx#L17-L29), [SuggestionChips.tsx#L13-L17](../../../frontend/src/components/molecules/SuggestionChips.tsx#L13-L17); test "seeds the textarea when a suggestion is picked". |
| **AC-07** `ActionBar` shows Resume only when `stop_reason ∈ {errored, user_cancelled}` (RF-11), wired to `useRun.resume()`, errors surfaced inline. | ✅ **Pass** | [ActionBar.tsx#L32-L35,L82-L95](../../../frontend/src/components/organisms/ActionBar.tsx#L32-L35); [CenterPanelContainer.tsx#L95-L101](../../../frontend/src/pages/CenterPanelContainer.tsx#L95-L101). |
| **AC-08** 404 from `GET /api/runs/:id` renders `NotFoundCard` (C13 microcopy); other errors keep the existing path. | ✅ **Pass** | [useRun.ts#L128-L129](../../../frontend/src/hooks/useRun.ts#L128-L129) + [CenterPanelContainer.tsx#L42-L44](../../../frontend/src/pages/CenterPanelContainer.tsx#L42-L44); test "renders NotFoundCard on 404". |
| **AC-09** `OutcomeBar` varies by `stop_reason`; `RunHeader` shows `StatusBadge` + `MetaRow` chips + live `ElapsedClock`. All trust dimensions visible (RF-13). | ⚠ **Pass with caveat** | All elements present ([CenterPanelView.tsx#L34-L51](../../../frontend/src/components/organisms/CenterPanelView.tsx#L34-L51), [RunHeader.tsx#L17-L48](../../../frontend/src/components/organisms/RunHeader.tsx#L17-L48)). **Caveat:** `ElapsedClock` tick test is flaky in full-suite runs (M-1). Behaviour is correct in isolation. |
| **AC-10** `TrustSummary` renders RF §6-quater rows; Confidence/Iterations/Sources use `—` placeholders with explicit "pending event log (BRD-10)" copy — never hides a dimension. | ⚠ **Pass with caveat** | All dimensions present with honest placeholders ([TrustSummary.tsx#L72-L106](../../../frontend/src/components/organisms/TrustSummary.tsx#L72-L106)). **Caveat:** line shape diverges from §7.7 (S-2) — functional RF-13 requirement met, microcopy fidelity not. |

**Net AC outcome:** 6 / 6 pass. 2 of them carry caveats that are scoped to M-1 and S-2 above.

---

## 5. Per-Criterion Notes

| Criterion (review request) | Verdict |
|---|---|
| 1. Atomic-Design layering | ✅ ESLint `import/no-restricted-paths` enforced; verified manually for all new files. |
| 2. Type safety (strict + L-006) | ✅ All pass-through optional props typed `T \| undefined`. |
| 3. API client policy (L-008/L-007) | ✅ All new fetches via `lib/api.ts`; mutations send `getAuthHeaders()`. |
| 4. Microcopy verbatim match | ⚠ `TypeDisclosure`, `SuggestionChips`, `NotFoundCard`, `Resume` button OK. `QuestionForm` (S-1) and `TrustSummary` line 1 (S-2) drift. |
| 5. Design tokens only | ✅ Zero hex / Tailwind greys. |
| 6. RF-13 no dimension hidden | ✅ Honest placeholders with tooltips citing BRD-10. |
| 7. RF-11 Resume gating | ✅ `RESUMABLE = {errored, user_cancelled}` only. |
| 8. Tests (≥80 %, jest-axe, MSW, no fake-timer pitfalls) | ⚠ Coverage and a11y OK; **fake-timer pitfall hit** in `ElapsedClock` (M-1). |
| 9. Language policy | ✅ All code/comments/docstrings in English. |

---

## 6. Required Changes (to clear approval)

In priority order:

1. **[M-1]** Stabilize `ElapsedClock > ticks every second while not frozen`. Recommend the `now`-prop injection path since the component already supports it.
2. **[M-2]** Resolve the 5 ESLint errors in `NewRunContainer.tsx`, `NewRunContainer.test.tsx`, `CenterPanelContainer.test.tsx`.
3. **[S-1]** Align `QuestionForm` microcopy with §7.2 (7 strings listed above).
4. **[S-2]** Render `TrustSummary` line 1 verbatim per §7.7 with `—` placeholders, keeping the deferred-metric rows for BRD-10.

S-3 and the NICE-TO-HAVE items may be deferred without blocking merge.

---

## 7. Verdict

**Returned to Coder** — score **8.88 / 10**, below the **9.0** approval threshold. Iteration count: **1 / 5**. Scope of remediation is narrow (≈ 30–45 min) and does not require any architectural rework. Re-submit as CR-13-003 once the four required items above are addressed.

> Positive signal: the architectural compliance (10/10), security (10/10) and RF-11/RF-13 enforcement are exemplary. The blocking issues are surface-level (test stability, lint, microcopy) — easy to close in one short pass.
