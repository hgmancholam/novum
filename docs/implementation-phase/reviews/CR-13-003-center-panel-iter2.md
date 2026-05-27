# Code Review CR-13-003 — Center Panel (Iteration 2, re-review)

**Source BRD:** [BRD-13-center-panel.md](../brds/BRD-13-center-panel.md)
**Implementation Plan:** [IP-13-center-panel-iter2.md](../implementation-plans/IP-13-center-panel-iter2.md)
**Predecessor reviews:** CR-13-001 (iter 1, 9.6/10 — approved) · [CR-13-002](CR-13-002-center-panel-iter2.md) (iter 2 first pass, 8.88/10 — returned)
**Fix decision record:** D-021
**Iteration:** 2 (2nd review of iter 2, F3↔F4 loop count **2 / 5**)
**Reviewer:** Reviewer Agent
**Date:** 2026-05-26

---

## 1. Score

| Criterion | Weight | Score | Weighted |
|---|---:|---:|---:|
| Code Quality (microcopy fidelity, readability, atomic design) | 25 % | 9.0 | 2.25 |
| Test Coverage (stability, jest-axe, full-suite green) | 20 % | 9.5 | 1.90 |
| Architecture Compliance (hook-in-pages, RF-11/13, plugin seams) | 20 % | 10.0 | 2.00 |
| Documentation (docstrings, deferred-decision honesty) | 15 % | 9.5 | 1.425 |
| Security (auth headers, error surfacing) | 10 % | 10.0 | 1.00 |
| Performance (interval scoping, render memoization) | 10 % | 9.5 | 0.95 |
| **TOTAL** | | | **9.53 / 10** |

**Threshold for approval:** ≥ 9.0/10.
**Verdict:** ✅ **APPROVED** — all four CR-13-002 blockers (M-1, M-2, S-1, S-2) are closed. Score improves from 8.88 → 9.53. Iteration 2/5 of the F3↔F4 loop.

---

## 2. Verification of CR-13-002 Fixes

### M-1 — `ElapsedClock` test stability ✅ PASS

**Files inspected:** [ElapsedClock.test.tsx](../../../frontend/src/components/molecules/ElapsedClock.test.tsx)

- The `setSystemTime + advanceTimersByTime` combination is **gone**. No `vi.setSystemTime` anywhere in the file.
- The 3 component tests (`renders elapsed time…`, `updates elapsed text when the now prop advances`, `does not tick when frozen`) all drive elapsed via `render` / `rerender` with explicit `now` `Date` instances — exactly the L-011 pattern recorded in the lessons log.
- A single `describe("ElapsedClock interval")` block retains `vi.useFakeTimers()` but asserts only that the text **changes** after `vi.advanceTimersByTime(2_000)` — not a specific elapsed value. This is the right trade-off: it preserves coverage of the internal `setInterval` registration without re-introducing the L-009 brittleness.

**Validation runs:**
- Isolated: `npx vitest run src/components/molecules/ElapsedClock.test.tsx` → **12 tests passed** in 56 ms.
- Full suite: `npx vitest run` → **39 files / 274 tests passed** (1 more than the 273 baseline because the original flaky case was split into two stable cases — matches D-021's note).

### M-2 — ESLint errors introduced by iter 2 ✅ PASS (scope), ⚠ SHOULD-FIX inherited

**Iter 2 in-scope files re-linted:** `src/pages/*` and `src/components/organisms/QuestionForm.tsx`.

- All 5 errors listed in [CR-13-002 §3.1 M-2](CR-13-002-center-panel-iter2.md) are cleared:
  - [NewRunContainer.tsx#L49](../../../frontend/src/pages/NewRunContainer.tsx#L49) — `void navigate(...)` ✅
  - [NewRunContainer.tsx#L69](../../../frontend/src/pages/NewRunContainer.tsx#L69) — sync `onSubmit={(payload) => { void handleSubmit(payload); }}` ✅
  - `NewRunContainer.test.tsx` `require-await` and `no-non-null-assertion` ✅
  - `CenterPanelContainer.test.tsx` `require-await` ✅
- Other lint errors flagged by the repo-wide `npx eslint .` run live in **pre-existing files explicitly scoped out** of CR-13-002: `lib/api.ts`, `lib/clipboard.ts`, `lib/format.ts`, `lib/sse.ts`, `hooks/useRun.ts`, `test/jest-axe.d.ts`. Not regressions of iter 2.

**Inherited warnings on [QuestionForm.tsx](../../../frontend/src/components/organisms/QuestionForm.tsx) — SHOULD FIX (next iteration), not MUST FIX:**

| Line | Rule | Drift |
|---:|---|---|
| 117 | `@typescript-eslint/no-deprecated` | `FormEvent` import is deprecated by the new `@types/react` typings; recommend `SyntheticEvent` or `SubmitEvent`. |
| 122 | `restrict-template-expressions` | `QUESTION_MIN` (number) in template literal. |
| 129 | `restrict-template-expressions` | `QUESTION_MAX` (number) in template literal. |
| 134 | `restrict-template-expressions` | `CONTEXT_MAX` (number) in template literal. |

These 4 errors were **not** flagged by CR-13-002. Per the re-review brief they are explicitly downgraded to **SHOULD FIX** (defer to a follow-up tidy-up pass; trivial — wrap the numeric constants with `String(...)` and swap `FormEvent` → `SubmitEvent`). They do **not** block approval.

### S-1 — `QuestionForm` microcopy aligned with §7.2 ✅ PASS

Cross-checked the 11 strings in `ui-prototype.md` §7.2 against [QuestionForm.tsx](../../../frontend/src/components/organisms/QuestionForm.tsx):

| §7.2 surface | Spec string | Code | Result |
|---|---|---|---|
| Question placeholder | `Ask Novum a question…` | L173 | ✅ |
| Context label | `Background context (optional)` | L213 | ✅ |
| Context placeholder | `Anything Novum should know up front. Not treated as evidence.` | L222 | ✅ |
| Advanced toggle (closed) | `Advanced ▸` | L256 | ✅ |
| Advanced toggle (open) | `Advanced ▾` | L256 | ✅ |
| Format legend | `Answer format` | L269 | ✅ |
| Format options | `Structured (recommended)` · `Prose` | L287 (ternary on `opt`) | ✅ |
| Threshold legend | `Confidence threshold` | L302 | ✅ |
| Threshold options | `Low (0.4)` · `Standard (0.6)` · `High (0.85)` · `Custom…` | `presetLabels` (L51–56) | ✅ (`\u2026` ≡ `…`) |
| Threshold tooltip | `Higher threshold = the agent searches longer and may honest-stop more often.` | L300 (`title=`) | ✅ |
| Submit button | `Start research` / `Starting…` | L386 | ✅ |
| Submit-disabled tooltip | `Type a question to start.` | L380–384 | ✅ |

Zero drift. Criterion 4 (verbatim spec match) of CR-13-002 is now satisfied.

### S-2 — `TrustSummary` line 1 per §7.7 ✅ PASS

[TrustSummary.tsx#L27–L50](../../../frontend/src/components/organisms/TrustSummary.tsx#L27-L50) implements `buildSummaryLine(run)` covering **all 7 `stop_reason` enum values plus the running case**, with the exact §7.7 glyphs and copy:

| `stop_reason` | §7.7 expected | Code |
|---|---|---|
| `judge_confirmed` | `✓ Judge confirmed · confidence <X> / threshold <Y>` | `✓ Judge confirmed · confidence — / threshold ${threshold}` ✅ |
| `honest_unanswerable` | `⚠ Honest stop · question is unanswerable` | exact match ✅ |
| `honest_contradiction` | `⚠ Honest stop · sources disagree` | exact match ✅ |
| `honest_ambiguous` | `⚠ Honest stop · question is ambiguous` | exact match ✅ |
| `stopped_by_budget` | `⚠ Stopped on budget · best-effort answer` | exact match ✅ |
| `user_cancelled` | `⊘ Cancelled · partial trace preserved` | exact match ✅ |
| `errored` | `⚠ Errored · <provider reason>` | `⚠ Errored · see details` ⚠ near-match (see below) |

**Minor drift on `errored`** — §7.7 expects `<provider reason>` interpolated. The code substitutes a generic `see details`. Acceptable for iter 2 because `RunResponse` does not yet carry an errored-reason field (BRD-10 will supply it via the event log) and "see details" preserves the warning glyph and the spec's intent. Document this as **N-1 (NICE TO HAVE)** for BRD-10 to fill in once `errored.message` is available; **not a blocker**.

The `<dl>` rows underneath (`Outcome`, `Threshold`, `Confidence`, `Iterations`, `Sources`, `Started`, `Stopped`) remain — RF-13 honesty preserved (every dimension surfaced, deferred values use `—` with `title="Available once the event log is wired (BRD-10)"`).

---

## 3. Acceptance Criteria Checklist (carry-forward)

| AC | CR-13-002 | CR-13-003 | Evidence |
|---|---|---|---|
| **AC-05** Home `/` starts a run; anon → login modal preserving draft; success → `/runs/:id`. | ✅ Pass | ✅ Pass | [NewRunContainer.tsx#L36-L52](../../../frontend/src/pages/NewRunContainer.tsx#L36-L52); `NewRunContainer.test.tsx` still green. |
| **AC-06** `TypeDisclosure` (5 ✓ + 3 ✗, RF-06) + 3 `SuggestionChips`; chip seeds textarea. | ✅ Pass | ✅ Pass | Unchanged from CR-13-002. |
| **AC-07** Resume button only on `errored` / `user_cancelled` (RF-11); errors inline. | ✅ Pass | ✅ Pass | `ActionBar.test.tsx` (10 cases) green. |
| **AC-08** 404 → `NotFoundCard`; other errors fall through. | ✅ Pass | ✅ Pass | Unchanged. |
| **AC-09** `OutcomeBar` + `RunHeader` + live `ElapsedClock`; all trust dimensions visible (RF-13). | ⚠ caveat (M-1) | ✅ Pass | M-1 closed — full-suite test now stable. |
| **AC-10** `TrustSummary` renders RF §6-quater rows; never hides a dimension. | ⚠ caveat (S-2) | ✅ Pass | S-2 closed — §7.7 line 1 + `<dl>` rows both present. |

**Net:** **6 / 6 pass, zero caveats** (vs. 6 / 6 with 2 caveats in CR-13-002).

---

## 4. Per-Criterion Notes

| Criterion (review request) | CR-13-002 | CR-13-003 |
|---|---|---|
| 1. Atomic-Design layering | ✅ | ✅ unchanged |
| 2. Type safety (strict + L-006) | ✅ | ✅ unchanged |
| 3. API client policy (L-008/L-007) | ✅ | ✅ unchanged |
| 4. Microcopy verbatim match | ⚠ S-1, S-2 | ✅ both closed |
| 5. Design tokens only | ✅ | ✅ unchanged |
| 6. RF-13 no dimension hidden | ✅ | ✅ unchanged |
| 7. RF-11 Resume gating | ✅ | ✅ unchanged |
| 8. Tests (≥ 80 %, jest-axe, MSW, no fake-timer pitfalls) | ⚠ M-1 | ✅ L-011 applied |
| 9. Language policy | ✅ | ✅ unchanged |

---

## 5. Issues (none blocking)

### 5.1 MUST FIX
*(none)*

### 5.2 SHOULD FIX (defer to a small follow-up pass, not blocking)

#### SF-1 — Lint clean-up on `QuestionForm.tsx`
[QuestionForm.tsx#L117](../../../frontend/src/components/organisms/QuestionForm.tsx#L117) `FormEvent` is deprecated by `@types/react`; switch to `SubmitEvent` (or `SyntheticEvent<HTMLFormElement>`) and wrap the three numeric template-literal interpolations on L122/L129/L134 with `String(...)` (or pre-compute the message). Trivial; pre-dates CR-13-002's flagged scope.

### 5.3 NICE TO HAVE

#### N-1 — Interpolate `errored` provider reason in `TrustSummary` line 1
Once BRD-10 wires the error-message field, replace `\u26a0 Errored \u00b7 see details` with `\u26a0 Errored \u00b7 ${run.errorReason}` to fully match §7.7.

#### N-2 — Old CR-13-002 N-1 / N-2 / N-3
Unchanged from CR-13-002 — `SuggestionChips` chip-vs-typing UX, `MetaRow` inner separator, `OutcomeBar` AT redundancy. All optional polish; defer freely.

---

## 6. Strengths Worth Highlighting

1. **L-011 (interval-driven component tests via `now` prop) is now memorialized as a reusable pattern.** The split into one prop-driven test plus one minimal interval test gives full coverage without the L-009 fake-timer hazard.
2. **`buildSummaryLine` keeps `stop_reason` enum coverage exhaustive.** The `switch` has explicit cases for all 7 enum values — if anyone later adds an 8th, `pyright`'s exhaustiveness check (TS in this case) will flag it. Good defensive coding.
3. **Microcopy fidelity is now spec-true.** No silent drift between `ui-prototype.md` §7.2/§7.7 and code — the only acceptable substitution (`errored` "see details") is honestly noted and tied to BRD-10.

---

## 7. Verdict

✅ **APPROVED** — score **9.53 / 10** (≥ 9.0 gate). The four CR-13-002 blockers are closed with clean implementations; no architectural regressions; full Vitest suite (274 tests) green; iter-2-introduced ESLint errors all resolved.

**F3↔F4 iteration count after this review: 2 / 5.**
**Orchestrator action:** advance BRD-13 iter 2 to **F5 (COMPLETE)**.

> The four inherited `QuestionForm.tsx` lint warnings and the `errored` provider-reason interpolation are tracked as **SHOULD FIX** and **NICE TO HAVE** respectively; both are appropriate for a small follow-up pass and do **not** delay completion.
