# Audit Report — BRD-20 / US-20-A / US-20-B

<!-- STATUS HEADER — overwritten on every iteration -->
**Artifact:** BRD-20 + US-20-A + US-20-B (audited together; single F1 batch)
**Phase:** F1 (ANALYZE)
**Auditor:** Auditor Agent
**Latest Iteration:** 2
**Latest Date:** 2026-05-27
**Latest Score:** 9.83/10
**Latest Verdict:** ✅ APPROVED
**Iteration Log:**

| Iter | Date | Score | Verdict |
|---|---|---|---|
| 1 | 2026-05-27 | 7.45 | ⚠️ NEEDS REVISION |
| 2 | 2026-05-27 | 9.83 | ✅ APPROVED |

---

## Iter 1 — 2026-05-27

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 7/10 | 30% | 2.10 |
| Acceptance Criteria Completeness | 7/10 | 20% | 1.40 |
| Blind-Path Absence | 7.5/10 | 25% | 1.875 |
| Traceability | 9/10 | 15% | 1.35 |
| Consistency w/ docs | 7/10 | 10% | 0.70 |
| **TOTAL** | | | **7.45/10** |

### 2. Verdict

⚠️ **NEEDS REVISION (7-8)** — Return to BSA with the feedback list in §5. Three blocking issues (one critical, two major) and three minor consistency items must be applied in place to the existing BRD-20 / US-20-A / US-20-B files. Audit iteration counter `audit_iter_F1` advances to **2**.

### 3. Requirements Coverage Matrix

| RF | Covered? | Where | Notes |
|---|---|---|---|
| RF-05 (Cross-session persistence — owner controls own runs) | ⚠️ Partial | [BRD-20 §2](../brds/BRD-20-delete-run-and-pagination.md), §11 #2 | Delete is correctly owner-scoped (403 path). The `GET /api/runs` list is **explicitly left OPEN** in §11 #2, and §4.5 keeps a `username \| None` signature that preserves the current cross-user behavior. RF-05 cannot be marked "owner controls own runs" while listing leaks other users' runs. See finding **F-1**. |
| RF-09 (History panel discovery & pagination) | ✅ Complete | [BRD-20 §4.4, §4.5, §5 AC-07/08/09](../brds/BRD-20-delete-run-and-pagination.md); [US-20-B Scenarios 1-3, 7, 8](../user-stories/US-20-B-history-pagination.md) | Keyset over `(started_at DESC, id DESC)`, opaque cursor, "More" gesture. Stable under inserts and deletes between pages. |
| RF-13 (UI as trust contract — visible affordance + animated removal) | ⚠️ Partial | [BRD-20 §4.7, §5 AC-03/AC-10](../brds/BRD-20-delete-run-and-pagination.md); [US-20-A Scenarios 1, 3, 8](../user-stories/US-20-A-delete-finished-run.md) | Hover affordance + exit animation + error rollback are spelled out. Missing: side-effect when the **currently selected** run is deleted (see **F-2**), and the post-deletion empty state (see **F-3**). RF-13 demands every visible state be defined. |
| RF-03 (Re-examinable runs — fork lineage on delete) | ✅ Complete | [BRD-20 §4.2, §5 AC-06, §11 #1](../brds/BRD-20-delete-run-and-pagination.md); [US-20-A Scenario 7](../user-stories/US-20-A-delete-finished-run.md) | `ON DELETE SET NULL` documented; user-visible "no fork badge" is stated. |

**RFs out of scope for this artifact** (not audited): RF-01, RF-02, RF-04, RF-06, RF-07, RF-08, RF-10, RF-11, RF-12, RF-14, RF-15, RF-16. They are correctly owned by other BRDs.

### 4. Blind-Path Findings

#### F-1 — Owner scoping of `GET /api/runs` is unresolved (**CRITICAL**)
- **Location:** [BRD-20 §4.5 "API Endpoints"](../brds/BRD-20-delete-run-and-pagination.md) and [BRD-20 §11 #2 "List scope — OPEN"](../brds/BRD-20-delete-run-and-pagination.md).
- **Type:** `missing_transition` (the spec encodes both behaviors simultaneously — `username | None`).
- **Affected RF:** RF-05.
- **Severity:** Critical.
- **Why this blocks audit:** the BSA's own §11 flags this as OPEN at iter-1. RF-05 says the owner controls *their* persisted runs; a global list is inconsistent with an owner-scoped delete and would let user A see (but not delete) user B's runs in the panel. The only consumer is the frontend, which is updated atomically with the rest of this BRD — no compatibility tax for closing it now. The user's question in the audit brief explicitly asks to resolve this here.
- **Fix recommendation:** Lock the decision **inside BRD-20**, do not split into a new BRD:
  1. In §4.5, change the signature to `list_runs_keyset(username: str, limit, cursor)` (drop the `None` case) and add `WHERE owner_username = :username` to the SQL contract.
  2. In §2, upgrade RF-05 coverage from "Partial" to "Complete" with the rationale "list is now symmetric with delete".
  3. In §5, add an acceptance criterion **AC-12 (Owner-scoped list)** — see exact Gherkin in §5 below.
  4. Add a row to §11 #2 marking it **RESOLVED**.
  5. Mirror **AC-12** as **Scenario 9** in US-20-B.

#### F-2 — No defined transition when the currently selected run is deleted (**MAJOR**)
- **Location:** [US-20-A Scenario 3](../user-stories/US-20-A-delete-finished-run.md); [BRD-20 §4.7 "UI Layout"](../brds/BRD-20-delete-run-and-pagination.md).
- **Type:** `missing_transition` + `no_user_feedback`.
- **Affected RF:** RF-13.
- **Severity:** Major.
- **Why this blocks audit:** if the user deletes the run that is currently displayed in the center panel, the BRD/US do not say what the center panel becomes. The card disappears from the history list, but the run viewer below it is left rendering a now-deleted run, which can re-fire SSE / re-fetch a 404 and produce a broken intermediate state. This is exactly the kind of "blind path" the auditor checklist item #1 forbids.
- **Fix recommendation:** in **US-20-A**, add a new Gherkin scenario (suggested **Scenario 9**) covering the selected-run case:
  ```gherkin
  Given the user has run R selected in the center panel
    And R is finished and visible in the history panel
  When the user deletes R from its history card
  Then the center panel returns to the L1 empty state (per BRD-12 state machine)
    And the selectionStore.selectedRunId is cleared
    And no further SSE/fetch requests target R.id
  ```
  In **BRD-20 §4.6 "React Components"**, add a one-line note to `useDeleteRun`: *"on successful mutation, if the deleted id matches `selectionStore.selectedRunId`, clear it."*

#### F-3 — Empty state after the last run is deleted is not defined (**MAJOR**)
- **Location:** [US-20-B Scenario 4](../user-stories/US-20-B-history-pagination.md) only covers empty-at-mount, not empty-after-deletion.
- **Type:** `missing_transition`.
- **Affected RF:** RF-13.
- **Severity:** Major.
- **Why this blocks audit:** the path "user has 1 run → user deletes it" must converge on the same L1 empty state as "user has 0 runs at mount". Without an explicit AC, the optimistic mutation may leave the panel in an empty-list-without-empty-message state (just a blank container), which is a `no_user_feedback` violation of RF-13.
- **Fix recommendation:** add a new Gherkin scenario to **US-20-A** (suggested **Scenario 10**):
  ```gherkin
  Given the panel shows exactly one finished run R owned by me
  When I delete R successfully
  Then the panel renders the L1 empty state from BRD-12
    And no "More" button is rendered
    And no cards are rendered
  ```

#### F-4 — Microcopy strings not cross-referenced to UI prototype §7 (**MINOR**)
- **Location:** BRD-20 §4.5 (error detail bodies) and §4.7 (button labels); US-20-A Scenarios 5 and 8; US-20-B Scenario 5.
- **Type:** `consistency_with_authoritative_docs`.
- **Affected RF:** RF-13 (microcopy is part of the trust contract).
- **Severity:** Minor.
- **Strings introduced:** `"More"`, `"Loading…"`, `"Delete run"` (aria-label / title), `"Cannot delete a run that is still in progress. Cancel it first."` (409), `"Run is not owned by the current user."` (403), `"Run not found: <id>"` (404), `"Invalid cursor"` (400), and the unspecified error toast text on AC-10 / Scenario 8.
- **Fix recommendation:** in BRD-20 §4.5 and §4.7, either (a) cite the exact subsection of `docs/understanding-phase/ui-prototype.md §7` that already defines each string, or (b) add a new subsection §14.3 "New microcopy (proposed addition to ui-prototype §7)" listing the strings verbatim so the binding source can be updated in a follow-up. Also pin the **exact** error-toast string for AC-10 / Scenario 8 (currently "an error message is surfaced" is vague — `no_user_feedback` risk).

#### F-5 — `GET /api/runs` 401 path is not specified (**MINOR**)
- **Location:** [BRD-20 §4.5 status-code table](../brds/BRD-20-delete-run-and-pagination.md).
- **Type:** `unhandled_error`.
- **Affected RF:** RF-05.
- **Severity:** Minor (becomes Critical only if F-1 is rejected).
- **Fix recommendation:** once owner-scoping is locked (F-1), the status-code table for `GET /api/runs` must list **401** when `X-Username` is missing/unknown, with body `{"detail": "Authentication required."}` (or cite the existing BRD-04 middleware behavior).

#### F-6 — `next_cursor` semantics on the last non-empty page (**INFORMATIONAL**)
- **Location:** BRD-20 §4.4.
- **Type:** `consistency_with_authoritative_docs`.
- **Severity:** Informational.
- **Note:** the contract clearly says `next_cursor: str | None`, but neither the BRD nor the US states explicitly whether `next_cursor` is `null` when `has_more=false` on a **non-empty** last page (e.g. 35 runs → page 2 returns 15 items, `has_more=false`). Recommend a one-line clarification in §4.4: *"When `has_more` is false, `next_cursor` is always `null`, regardless of whether the page is empty."*

### 5. Required Changes (apply IN PLACE — no `-v2` files)

> All edits target the existing files. Do not create new artifacts.

1. **[CRITICAL — F-1] Lock owner-scoping of `GET /api/runs` in BRD-20.** Edit [BRD-20 §4.5](../brds/BRD-20-delete-run-and-pagination.md) to drop the `username | None` option and add `WHERE owner_username = :username`. Edit §2 to upgrade RF-05 to "Complete". Edit §11 #2 to mark **RESOLVED** with the rationale "symmetry with delete; only consumer is the frontend, updated atomically". Add **AC-12** to §5:
   ```gherkin
   Given user "alice" owns 5 finished runs and user "bob" owns 3 finished runs
   When alice sends GET /api/runs with header X-Username: alice
   Then the response contains exactly 5 items
     And none of the items reference a run owned by bob
   ```
   Mirror this as **Scenario 9** in US-20-B.

2. **[MAJOR — F-2] Add a Gherkin scenario for "selected run is deleted" in US-20-A** (see exact text in §4 / F-2 above) and append a one-line note in BRD-20 §4.6 instructing `useDeleteRun` to clear `selectionStore.selectedRunId` when the deleted id matches.

3. **[MAJOR — F-3] Add a Gherkin scenario for "delete the last visible run → L1 empty state" in US-20-A** (see exact text in §4 / F-3 above).

4. **[MINOR — F-4] Cross-reference or declare microcopy.** Edit BRD-20 §4.5 and §4.7 to either cite `docs/understanding-phase/ui-prototype.md §7` for each user-visible string, or add a new §14.3 listing them verbatim as proposed additions. Pin the exact error-toast string for AC-10 (BRD §5) and Scenario 8 (US-20-A) — replace "error message is surfaced" with the literal copy.

5. **[MINOR — F-5] Document the 401 path for `GET /api/runs`** in BRD-20 §4.5 (after F-1 is applied).

6. **[INFORMATIONAL — F-6] Clarify `next_cursor` semantics on the last non-empty page** in BRD-20 §4.4 (one-line note).

### 6. Positive Highlights

- **Excellent traceability.** §2 RF table, §3 Dependencies, §4.1 File-by-file plan, §10 Out of Scope, §11 explicit Open Decisions — the BRD is one of the most navigable in the suite.
- **Strong server-side defense.** Owner check **before** terminal-state check (avoids existence leak via 409) is correctly motivated in §4.5 and mirrored in US-20-A "Technical Notes".
- **Keyset pagination is the right call** and is correctly motivated in §11 #4. The `(started_at, id)` tie-break is stated; US-20-B Scenario 7 and 8 prove the contract holds under concurrent inserts and deletes.
- **Fork orphaning policy is fully wired.** Schema-level `ON DELETE SET NULL` is referenced with a precise file/line (`backend/app/models/run.py:100`), the SQL is shown, and the user-visible "no fork badge" is captured in US-20-A Scenario 7.
- **SSE race anticipated.** §9 Risks correctly proposes `connection_manager.close(run_id)` after delete commit; US-20-A "Technical Notes" repeats it. This pre-empts a real blind path.
- **Breaking change handled honestly.** §9 risk row + §10 single-consumer rationale + atomic frontend update is the cleanest possible answer for a pre-launch V1.
- **Language policy respected.** All artifacts are in English; the only Spanish fragment is a verbatim quote of the original user requirement in §11 #1, which is correct.

### 7. Next Step

- Verdict **NEEDS REVISION**. Return artifacts to **BSA** with the six required changes above.
- `audit_iter_F1` advances to **2**. Maximum is 3 before F6 escalation.
- All changes are surgical and apply IN PLACE to existing files. No new BRD, no new US, no new audit file on the next pass — the iter-2 section will be appended to **this** report.

---

## Iter 2 — 2026-05-27

### 0. Resolution of Iter 1 findings

| Prior change | Status | Evidence |
|---|---|---|
| F-1 [CRITICAL] Lock owner-scoping of `GET /api/runs` | ✅ done | [BRD-20 §4.5](../brds/BRD-20-delete-run-and-pagination.md) — signature `list_runs_keyset(username: str, ...)` (no `None` overload), SQL `WHERE owner_username = :username`; §2 RF-05 upgraded to **Complete**; §11 #2 marked **RESOLVED**; §5 **AC-12** added; mirrored as US-20-B Scenario 9 |
| F-2 [MAJOR] Gherkin for deleted-while-selected | ✅ done | [US-20-A Scenario 9](../user-stories/US-20-A-delete-finished-run.md) added verbatim per recommendation; [BRD-20 §4.6 `useDeleteRun` row](../brds/BRD-20-delete-run-and-pagination.md) extended to clear `selectionStore.selectedRunId` |
| F-3 [MAJOR] Gherkin for deleting last visible run → L1 empty state | ✅ done | [US-20-A Scenario 10](../user-stories/US-20-A-delete-finished-run.md) added verbatim |
| F-4 [MINOR] Microcopy cross-references + literal toast strings | ✅ done | New [BRD-20 §14.3 Microcopy additions](../brds/BRD-20-delete-run-and-pagination.md) lists all 10 strings verbatim; §4.5 / §4.7 cite it; AC-10 toast string `"Couldn't delete the run. Please try again."` pinned; US-20-A Scenario 8 and US-20-B Scenario 5 reference the literals |
| F-5 [MINOR] 401 path for `GET /api/runs` | ✅ done | BRD-20 §4.5 GET error model now lists 401 with body `"Authentication required."` |
| F-6 [INFO] `next_cursor=null` when `has_more=false` | ✅ done | BRD-20 §4.4 clarification note added: *"when `has_more` is `false`, `next_cursor` is **always** `null`, regardless of whether the page returned items"* |

All six iter-1 changes applied **in place** (no new files). v1.1 history row recorded in §14.2.

### 1. Score Summary

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Requirements Coverage | 10/10 | 30% | 3.00 |
| Acceptance Criteria Completeness | 10/10 | 20% | 2.00 |
| Blind-Path Absence | 9.5/10 | 25% | 2.375 |
| Traceability | 10/10 | 15% | 1.50 |
| Consistency w/ docs | 9.5/10 | 10% | 0.95 |
| **TOTAL** | | | **9.83/10** |

### 2. Verdict

✅ **APPROVED (≥ 9)** — All blocking findings from iter 1 are resolved. RF-05 / RF-09 / RF-13 / RF-03 are now fully covered within the artifact's scope. Proceed to **F2 (PLAN)**.

### 3. Requirements Coverage Matrix

| RF | Covered? | Where | Notes |
|---|---|---|---|
| RF-05 (Cross-session persistence — owner controls own runs) | ✅ Complete | [BRD-20 §2, §4.5, §5 AC-05/AC-12, §11 #2](../brds/BRD-20-delete-run-and-pagination.md); [US-20-B Scenario 9](../user-stories/US-20-B-history-pagination.md) | List and delete are now symmetric (owner-scoped). 401 path documented. |
| RF-09 (History panel discovery & pagination) | ✅ Complete | BRD-20 §4.4 / §4.5 / §5 AC-07/08/09; US-20-B Scenarios 1–3, 7, 8 | Unchanged from iter 1. `next_cursor=null` invariant now explicit (§4.4). |
| RF-13 (UI as trust contract) | ✅ Complete | BRD-20 §4.7, §5 AC-03/AC-10, §14.3; US-20-A Scenarios 1, 3, 8, 9, 10 | Selected-run reset and post-deletion empty state are now wired (Scenarios 9, 10). Microcopy literals pinned in §14.3. |
| RF-03 (Re-examinable runs — fork lineage handling) | ✅ Complete | BRD-20 §4.2, §5 AC-06, §11 #1; US-20-A Scenario 7 | Unchanged from iter 1. |

### 4. Blind-Path Findings

None blocking. Two minor informational notes for the implementation phase (no score impact, no required change):

- **N-1 (informational)** — §14.3 declares the microcopy literals as *proposed additions* to `ui-prototype.md §7.12`. The follow-up sync to `ui-prototype.md` is out of scope for this BRD but should be tracked so the binding source matches the code. Not a defect of BRD-20.
- **N-2 (informational)** — US-20-A Scenario 9 correctly clears `selectionStore.selectedRunId` and stops further SSE/fetch. The implementation should also ensure `connection_manager.close(run_id)` (already required by BRD-20 §9 Risks and the Technical Notes) fires before the optimistic cache mutation triggers any re-render that could re-open the stream. This is an implementation-time concern for F3, not a spec gap.

### 5. Required Changes

None. Artifact is APPROVED.

### 6. Positive Highlights

- **Iter 1 feedback applied surgically and in place.** All six items resolved in a single pass with no scope creep — version bumped to 1.1, §14.2 records the change set, no orphan files.
- **§14.3 microcopy table is exemplary.** Ten strings pinned verbatim with surface, literal, and consumer — eliminates ambiguity for the coder and the reviewer; also flags the `"More" supersedes "Load more"` discrepancy honestly instead of hiding it.
- **Selected-run reset is wired end-to-end** (US-20-A Scenario 9 + BRD-20 §4.6 `useDeleteRun` note + US-20-A Technical Notes). No blind path between the optimistic delete and the center panel.
- **Owner-scoped list is now SQL-level enforced** (`WHERE owner_username = :username` in §4.5) rather than route-level, which is the correct defense-in-depth posture.
- **§11 #2 RESOLVED rationale is precise** ("symmetric with delete; only consumer updated atomically; no compatibility tax") and matches the iter-1 recommendation verbatim.
- **`next_cursor` invariant is now contract-grade**: *always null when `has_more=false`, regardless of page emptiness* — removes a real client-side foot-gun.

### 7. Next Step

- Verdict **APPROVED**. Hand off to **Orchestrator** for F2 (PLAN) — produce `PLAN-US-20-A` and `PLAN-US-20-B` implementation plans.
- `audit_iter_F1` finalized at **2** (under the limit of 3). F2 starts a fresh `audit_iter_F2 = 1`.
- Reminder for the implementation phase: track the `ui-prototype.md §7.12` sync (per §14.3) as a follow-up doc-only PR.

