# REVIEW-IP-23 Phase 3 — Authority Tiering (WP-3)

**Phase**: 3 (WP-3)
**Iteration**: 1
**Reviewer**: self-review (orchestrator)
**Date**: 2026-05-28

## Scope

Implements BRD-23 WP-3: classify each Source result into one of four
`AuthorityTier` buckets at search time, persist the tier on
`EvidenceAddedEvent`, fold it into the per-evidence multiplier inside
`C_coverage` and `C_diversity` (`C_agreement` and `C_no_conflict`
deliberately untouched per §15.3 Q3), surface the tier in the UI, and
amend `docs/understanding-phase/confidence-calculation.md`.

## Files changed (delta vs Phase 2)

### Backend (8)

1. `backend/app/domain/enums.py` — `AuthorityTier` enum (4 values).
2. `backend/app/domain/events.py` — `authority_tier` optional on
   `EvidenceAddedEvent` (extra="allow" preserves replay).
3. `backend/app/agent/run_state.py` — `EvidenceItem.authority_tier`
   (optional).
4. `backend/app/sources/authority.py` (new) — `classify_authority(url)`
   pure function with TLD + domain markers (gov, edu, peer-reviewed
   journals, established media, blogs/forums, etc.).
5. `backend/app/agent/tasks/search.py` — calls `classify_authority` on
   each result, threads through `EvidenceItem` and event payload.
6. `backend/app/config.py` — 4 multiplier knobs
   (`authority_multiplier_primary/reputable/general/low` =
   1.05 / 1.00 / 0.90 / 0.50).
7. `backend/app/confidence/structural.py` — `_authority_multiplier`
   (None → GENERAL, replay-safe); applied per-row in `C_coverage` (mean
   multiplier over supporting rows per claim) and per-domain in
   `C_diversity` (`base × mean_mult` of best-per-domain multipliers).
8. `backend/app/agent/runner.py::_fold_events` — reads `authority_tier`
   from EvidenceAdded dict, tolerates absence.

### Frontend (3)

9. `scripts/export_types.py` — `AuthorityTier` added to enum export.
10. `frontend/src/types/events.ts` — regenerated.
11. `frontend/src/components/molecules/AuthorityTierChip.tsx` (new) —
    chip molecule with severity-mapped variant.

### Docs (1)

12. `docs/understanding-phase/confidence-calculation.md` — Amendment
    2026-05-28: multiplier table, asymmetric design (only C_cov/C_div),
    RF-12 invariant preserved (`final_confidence = min(S_effective, J)`),
    replay tolerance rule (missing tier → GENERAL).

### Tests (5)

13. `backend/tests/test_sources_authority_tiers.py` (new) — 28 cases
    covering gov, edu, peer-reviewed, established media, blogs, forums,
    edge cases (subdomain matching with `(^|\.)` anchor — see L-016).
14. `backend/tests/test_confidence_authority_multiplier.py` (new) — 15
    cases for asymmetric multiplier application + replay tolerance.
15. `backend/tests/test_confidence_structural.py` (modified) — `_ev`
    factory now seeds `authority_tier=REPUTABLE_SECONDARY` so legacy
    baseline numerics (diversity 0.3/0.5/0.7/0.9/1.0) stay valid.
16. `backend/tests/test_confidence_calculator.py` (modified) — same
    factory adjustment in `_state_full`.
17. `backend/tests/test_agent_tasks_draft.py` (modified) — same factory
    adjustment in `_state`.
18. `frontend/src/components/molecules/AuthorityTierChip.test.tsx`
    (new) — 5 cases (one per tier + a11y violation check).

## Scoring rubric (0–10)

| Criterion | Score | Notes |
|---|---:|---|
| **Spec adherence** (BRD-23 §4.7, §15.3 Q3) | 10 | Multiplier applied only to C_cov & C_div; multipliers match config; RF-12 invariant preserved; amendment doc present. |
| **Architectural rules** | 10 | Append-only events; `extra="allow"`; replay-safe (missing tier → GENERAL); English-only; no new seam. |
| **Type safety / contracts** | 10 | Optional `AuthorityTier \| None`; FE↔BE types regenerated; pyright clean. |
| **Test coverage** | 10 | 43 new test cases + 9 baseline tests updated minimally (helper-factory only). Full backend suite: **732 passed**. Frontend: **476 passed** (+1 pre-existing unrelated UsernameModal fail). |
| **Backwards compatibility** | 10 | No required field added; pre-WP-3 traces fold cleanly (verified via runner._fold_events). |
| **Code style** | 9 | English-only; pure function for `classify_authority` (no side-effects); one minor: TLD marker tables documented only by constant names. |
| **Performance** | 10 | O(domain markers) per result; no new IO. |
| **Resilience** | 9 | Subdomain regex anchored with `(^|\.)` to avoid `gov.fake.com` false positives (L-016). |
| **UX** | 9 | Chip uses existing tokens & severity ramp; rendered next to source URL. |
| **Risk** | 9 | Multiplier silently lowers diversity for runs whose evidence rows omit a tier — but explicit GENERAL default is documented as the chosen replay-safe stance, and old tests were updated to opt-in. |

**Aggregate: 9.6/10 — APPROVED.**

## Autonomous decisions

1. **Baseline tests updated, not the production default.** The 9
   pre-WP-3 tests (`test_diversity_*`, `test_structural_full_state`,
   `test_calculate_returns_structural_components`,
   `test_evaluate_with_judge_passes_when_above_threshold`) were broken
   by the GENERAL default multiplier (0.9). Per the amendment doc, that
   default is **intentional**: replay must work for old traces without
   tier info. The minimal fix is to make baseline tests explicit about
   their assumption (`authority_tier=REPUTABLE_SECONDARY`, mult 1.0).
   Numerics preserved; intent of each test unchanged.
2. **`(^|\.)` anchor on subdomain regex.** A naïve `.gov` substring
   match flagged `gov.fake.com` as authoritative. Replaced with
   `(^|\.)gov($|\.)`. Captured as lesson L-016.
3. **No new seam for authority classification.** Per IP-23 §6, this is
   a pure helper in `app/sources/`. Keeps the 3-seams contract intact.

## Pre-existing failure (DEGRADED, out of scope)

`frontend/src/components/organisms/UsernameModal.test.tsx::renders the
dialog with token-based classes (no hardcoded colors)` continues to
fail on a `data-variant="strong"` vs expected `"default"` mismatch.
Component and test were NOT modified in this Phase. Tracked separately.

## Outputs

- `pytest_ip23_phase3_iter1.txt` — full backend suite: **732 passed in 110.95 s**.
- `vitest_ip23_phase3_iter1.txt` — full frontend suite: **476 passed | 1 failed (pre-existing UsernameModal)**.

## Verdict

**APPROVED 9.6/10** — proceed to Phase 4 (WP-2 Deep-Fetch).
