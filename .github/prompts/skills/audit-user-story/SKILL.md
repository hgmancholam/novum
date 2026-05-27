# Audit User Story Skill

## Description
Checklist-driven audit of a User Story against the INVEST criteria, Gherkin acceptance-criteria completeness, and traceability to its parent BRD and to the affected RFs.

## When to Use
- The BSA agent has produced or revised User Stories in `docs/implementation-phase/user-stories/`.
- Inside the **F1: ANALYZE** sub-loop (step F1.S5).

## Inputs
- The User Story file under audit.
- The parent BRD (`docs/implementation-phase/brds/BRD-XX-*.md`).
- Functional requirements (`docs/understanding-phase/requirement-understanding.md`).
- UI prototype (`docs/understanding-phase/ui-prototype.md`) — when story has UI impact.
- Any prior audit report for the same story (`docs/implementation-phase/audits/AUDIT-US-*.md`).

## Scope Discipline (MANDATORY)

- Audit ONLY the acceptance criteria declared by `US-XX` and the BRD sections it explicitly links to.
- Do NOT flag missing behavior that belongs to a sibling User Story or to a later iteration.
- `RFs_in_scope` = RFs cited by the story + RFs cited by the parent BRD for the slice this story owns.
- Anything outside this set is OUT OF SCOPE — informational at most, never a Required Change.

## In-Place Revision Rule (MANDATORY)

- All Required Changes MUST be phrased as in-place edits to the existing User Story file (e.g. "In `US-XX-...md`, add an acceptance criterion covering …").
- The BSA must apply changes to the **same** `US-XX-<slug>.md` across every audit iteration. No `-v2`, no new date, no new slug.
- If a revised User Story appears under a different filename, treat it as a process violation and report it under §4 of the audit report.

## Audit Report File (Single File, In-Place)

- Output path: `docs/implementation-phase/audits/AUDIT-US-XX.md` (no date, no iter suffix).
- On iter 1 → **create** the file with the Status Header + `## Iter 1 — {date}` section.
- On iter 2 / 3 → **open** the existing file and **append** a `## Iter N — {date}` section that begins with a *Resolution of Iter N-1 findings* table. Refresh the Status Header at the top. Never overwrite or delete prior Iter sections.

## Checklist

### 1. Requirements Coverage (30%)
- [ ] Story cites every RF it touches.
- [ ] If story affects a stop_reason path, the 7-enum values are respected (RF-02).
- [ ] If story affects events, append-only invariant is respected (RF-03).
- [ ] If story affects UI, states and microcopy reference `ui-prototype.md` §3 / §7.

### 2. Acceptance Criteria Completeness (20%)
- [ ] Story uses **Gherkin** (Given / When / Then) for each criterion.
- [ ] Happy path is covered.
- [ ] At least one **failure** scenario is covered.
- [ ] At least one **edge case** is covered (empty input, timeout, partial state, cancel).
- [ ] Each criterion is testable (no opinions, no "should be intuitive").

### 3. Blind-Path Absence (25%)
- [ ] Story covers what happens on **error** for every external call.
- [ ] Story covers what the **user sees** during loading, partial, and terminal states.
- [ ] Story covers **cancellation** (RF-08) if it triggers a long-running action.
- [ ] Story does not assume a state that has no transition into it.
- [ ] Story does not produce a state that has no transition out of it (unless terminal).

### 4. Traceability (15%)
- [ ] Story ID follows naming convention.
- [ ] Story is linked to a parent BRD.
- [ ] Story lists the components/files it will likely touch (informational only).
- [ ] **INVEST** properties hold:
  - **I**ndependent — minimal coupling with other in-flight stories
  - **N**egotiable — written as intent, not as solution
  - **V**aluable — explicit user/business value
  - **E**stimable — scope is clear enough to size
  - **S**mall — fits a single iteration
  - **T**estable — every AC is verifiable

### 5. Consistency with Authoritative Docs (10%)
- [ ] No contradiction with parent BRD.
- [ ] No contradiction with architectural rules.
- [ ] No new tech introduced outside `tech-stack.md`.

## Scoring Rule

Same weighted scoring as the Auditor agent. Round to one decimal.

| Score | Verdict |
|---|---|
| ≥ 9.0 | APPROVED |
| 7.0 – 8.9 | NEEDS REVISION |
| < 7.0 | MAJOR GAPS |

## Output
A markdown report saved to `docs/implementation-phase/audits/AUDIT-US-XX.md` (single file per User Story, edited in place; one `## Iter N` section appended per audit iteration).

## Common Failure Patterns (auto-deduct)
- Acceptance criteria not in Gherkin → Acceptance Criteria capped at 5/10.
- Only happy path covered → Blind-Path Absence reduced by 3 points.
- No parent BRD link → Traceability capped at 4/10.
- Story implies a banned technology → Consistency = 0/10 (auto-fail criterion).
