# IP-13 iter 2: Center Panel — UX Completion

**Source BRD:** [BRD-13-center-panel.md](../brds/BRD-13-center-panel.md)
**Previous iteration:** [IP-13](IP-13-center-panel.md) (minimal, 9.6/10)
**Status:** In progress
**Date:** 2026-05-26
**Author:** Orchestrator (re-run from F2 per user request)

---

## 1. Why iter 2

Iter 1 shipped the BRD-13 skeleton (Question + ResearchingBanner + StopReasonCard), but the route surface still has **blind spots** that block the core user flow:

| Blind spot | User impact | Source |
|---|---|---|
| **No way to start a research from the UI** | `HomePage` shows a static welcome, no `QuestionForm`. POST `/api/runs` is unreachable without console. | UI prototype §3.2 C1/C2 |
| Terminal runs read as "no answer" | `judge_confirmed` looks identical to `honest_unanswerable` at a glance — no pre-attentive recognition. | §3.2.5 `OutcomeBar` missing |
| No run metadata visible | User cannot see when the run started, how long it took, which format/threshold was chosen. | §7.5 / §7.6 / §3.2.4 |
| No Resume affordance | RF-11 explicitly says `errored` and `user_cancelled` are resumable; backend exposes `POST /runs/{id}/resume`; UI has no button. | §3.1 C9, C10 |
| 404 leaves user stranded | A wrong `:runId` shows the generic load-error card with the backend's raw message, no link home. | §3.1 C13 |
| User has no idea what Novum will/won't answer | RF-06 disclosure missing; first-run users get no suggestion chips. | §3.2 C1, §7.3, §7.7 |
| Live run shows only a spinner | No elapsed-time, no owner-vs-viewer distinction, no `ShareLinkButton`-equivalent affordance. | §3.1 C4/C5 |

Iter 2 closes these gaps **without** waiting on BRD-10 (SSE) — it works against the existing `RunResponse` plus the create/cancel/resume mutations already exposed by `RunService`.

## 2. Scope

### In scope (this iteration)
- Frontend only. No backend changes.
- States covered: **C1, C2, C3, C4, C6 (header+meta), C9 Resume, C10 Resume, C13**.
- New: create-run flow (`HomePage` → `RunPage`), elapsed-time clock, run metadata strip, outcome bar, type disclosure, suggestion chips for first-run, resume affordance, 404 page.

### Deferred (still BRD-10 / BRD-14 / BRD-15)
- Live event stream → mini-feed (C4/C5 body content beyond elapsed time)
- AnswerRenderer (prose / structured) → BRD-10 + BRD-16
- ConfidenceMeter / TrustSummary metrics that require events (sources cited, coverage, contradictions) → BRD-10
- Fork picker → BRD-15
- Diff mode C12 → BRD-15 / V2

`TrustSummary` ships **partially** in iter 2: line 1 (badge variant) and line "started X · format Y · threshold Z · duration" derived from `RunResponse`. Event-derived lines (sources, sub-claims, contradictions) are deferred and rendered as `"—"` placeholders with `data-testid` hooks so BRD-10 can fill them in.

## 3. Task breakdown

| # | Layer | File | Purpose |
|---|---|---|---|
| 1 | api | `lib/api.ts` | Add `createRun(payload)`, `resumeRun(id)`. Re-use `getAuthHeaders`. |
| 2 | hook | `hooks/useCreateRun.ts` | `useMutation<RunResponseDto, Error, RunCreatePayload>` → invalidates `["runs"]`. |
| 3 | hook | `hooks/useRun.ts` | Add `resume()`, `isResuming`, `resumeError`. Detect 404 (ApiClientError 404) → expose `isNotFound`. |
| 4 | atom | `components/atoms/OutcomeBar.tsx` | 4 px strip, color from `stopReason` → `--semantic-*`. |
| 5 | molecule | `components/molecules/MetaRow.tsx` | Inline chips: relative-start · duration · format · threshold. |
| 6 | molecule | `components/molecules/TypeDisclosure.tsx` | RF-06 supported/rejected lists (§7.3 copy). |
| 7 | molecule | `components/molecules/SuggestionChips.tsx` | 3 chips → onPick(question). |
| 8 | molecule | `components/molecules/ElapsedClock.tsx` | Ticks every 1 s, formats `Xs` / `Xm Ys`. |
| 9 | organism | `components/organisms/QuestionForm.tsx` | Question textarea + collapsible context (RF-07) + Advanced disclosure (format + threshold) per §7.2. Submits via `useCreateRun`, navigates to `/runs/:id` on success. Auth gate: opens `useLoginModal` if anonymous. |
| 10 | organism | `components/organisms/RunHeader.tsx` | `StatusBadge` + `MetaRow` + `ElapsedClock` when running. |
| 11 | organism | `components/organisms/TrustSummary.tsx` | Partial v1: title line + metrics placeholder lines per §7.7. |
| 12 | organism | `components/organisms/ResearchingBanner.tsx` | Add `startedAt` prop → render `ElapsedClock`. |
| 13 | organism | `components/organisms/ActionBar.tsx` | Add `onResume`, `isResuming`. Show Resume when `stopReason ∈ {errored, user_cancelled}`. |
| 14 | organism | `components/organisms/CenterPanelView.tsx` | Compose `OutcomeBar` (terminal) + `RunHeader` + `Question` + (Researching | TrustSummary + StopReasonCard). |
| 15 | organism | `components/organisms/NotFoundCard.tsx` | C13 — "Run not found" + link to `/`. |
| 16 | page | `pages/CenterPanelContainer.tsx` | Wire 404 (renders `NotFoundCard`) + resume mutation. |
| 17 | page | `pages/HomePage.tsx` | Replace placeholder body with `<NewRunContainer />` → `QuestionForm` + `TypeDisclosure` + `SuggestionChips` (when zero `Mine` runs). |
| 18 | page | `pages/NewRunContainer.tsx` | Page-level data owner for the create flow. Reads `useUserStore` + `useRunHistory` (for first-run detection) + `useCreateRun`. |
| 19 | tests | `*.test.tsx` co-located | Vitest + RTL + jest-axe + MSW. ≥ 80% coverage per L-002. |

## 4. Acceptance criteria coverage (after iter 2)

| AC | Status |
|---|---|
| AC-01 Question displays correctly (C2) | ✅ (iter 1) |
| AC-02 Answer streams live (C6) | ❌ deferred to BRD-10 — same as iter 1. |
| AC-03 Cancel stops research (RF-08) | ✅ (iter 1) |
| AC-04 Confidence formula min(S,J) (RF-12) | ❌ deferred to BRD-10. |
| **iter 2 — AC-05** Start research from `/` | ✅ `QuestionForm` |
| **iter 2 — AC-06** Resume errored/cancelled run | ✅ `ActionBar.Resume` |
| **iter 2 — AC-07** 404 routes do not strand user | ✅ `NotFoundCard` |
| **iter 2 — AC-08** Outcome readable pre-attentively | ✅ `OutcomeBar` |
| **iter 2 — AC-09** Run metadata visible | ✅ `MetaRow` + `ElapsedClock` |
| **iter 2 — AC-10** First-run gets question suggestions (RF-06 onboarding) | ✅ `TypeDisclosure` + `SuggestionChips` |

## 5. Tech notes

- **Atomic-design seam** stays intact: organisms remain presentational, page containers own data hooks (ESLint enforces it).
- **`API_URL` prefix** (L-008): every new fetch uses `lib/api.ts` so the rule is enforced by construction.
- **`exactOptionalPropertyTypes`** (L-006): forwarded optional props typed `T | undefined`.
- **Auth headers** on mutations (L-007): reuse `getAuthHeaders`. `QuestionForm` opens login modal if anonymous instead of failing 401.
- **Token-only styling** (BRD-11 §1): `--semantic-*` for outcome colors. No raw hex / Tailwind greys.
- **Microcopy** comes from `ui-prototype.md` §7 verbatim.

## 6. Risks

| Risk | Mitigation |
|---|---|
| `ElapsedClock` re-renders waste CPU | `setInterval(1000)` only mounted while `status === "running"`; component memoized; only the seconds text re-renders. |
| Question form double-submit | Button disabled while `isPending`; navigation happens onSuccess. |
| Resume race (user clicks twice) | Mutation deduped + button disabled while `isPending`. |
| First-run detection flickers | `useRunHistory().isLoading` masks `SuggestionChips` until known; once decided, sticky for the page lifetime. |
