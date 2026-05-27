# Audit BRD Skill

## Description
Checklist-driven audit of a Business Requirements Document (BRD) against the project's functional requirements (RF-01…RF-16) and authoritative documents in `docs/understanding-phase/` and `docs/technical-phase/`.

## When to Use
- The BSA agent has produced or revised a BRD in `docs/implementation-phase/brds/`.
- Inside the **F1: ANALYZE** sub-loop (step F1.S5).

## Inputs
- The BRD file under audit.
- The originating requirement statement.
- The full RF catalogue in `docs/understanding-phase/requirement-understanding.md`.
- Any prior audit report for the same BRD (`docs/implementation-phase/audits/AUDIT-BRD-*.md`).

## Checklist

### 1. Requirements Coverage (30%)
- [ ] Every RF affected by the requirement is **cited by number** (RF-01…RF-16) in the BRD.
- [ ] For each cited RF, the BRD states **how** it is satisfied.
- [ ] No RF is silently dropped (if one is intentionally out of scope, it is listed under "Out of Scope" with justification).
- [ ] Stop reasons referenced (when applicable) match the 7 enum values (RF-02).
- [ ] Confidence references match the `min(S, J)` formula (RF-12).

### 2. Acceptance Criteria Completeness (20%)
- [ ] Each business goal has measurable success criteria (SMART).
- [ ] Each acceptance criterion is testable (binary pass/fail or numeric threshold).
- [ ] Edge cases are listed (not only happy path).
- [ ] Out-of-scope is explicit.

### 3. Blind-Path Absence (25%)
- [ ] Every described user journey reaches a terminal state.
- [ ] Every error condition has either recovery or a terminal `stop_reason`.
- [ ] No "user-left-without-feedback" scenarios — every state has a visible UI representation referenced in `ui-prototype.md`.
- [ ] Cancellation is addressed (RF-08) where applicable.
- [ ] Budget exhaustion is addressed (RF-01·F) where applicable.

### 4. Traceability (15%)
- [ ] BRD ID follows naming convention.
- [ ] BRD links to the originating requirement.
- [ ] BRD lists the User Stories that will derive from it.
- [ ] Stakeholders are identified.

### 5. Consistency with Authoritative Docs (10%)
- [ ] No contradiction with `requirement-understanding.md`.
- [ ] No contradiction with `architecture.md` (8 rules).
- [ ] No contradiction with `tech-stack.md` (no introduction of banned tech).
- [ ] No contradiction with `ai-services.md` (LLM/search constraints).
- [ ] No contradiction with `ui-prototype.md` (states, microcopy, tokens).

## Scoring Rule

Compute the weighted score per the Auditor's scoring table. Round to one decimal.

| Score | Verdict |
|---|---|
| ≥ 9.0 | APPROVED |
| 7.0 – 8.9 | NEEDS REVISION |
| < 7.0 | MAJOR GAPS |

## Output
A markdown report saved to `docs/implementation-phase/audits/AUDIT-BRD-XX-{iter}-{date}.md` using the Auditor report template.

## Common Failure Patterns (auto-deduct)
- BRD does not cite a single RF number → Requirements Coverage capped at 4/10.
- Acceptance criteria written as opinions ("should be fast") with no metric → Acceptance Criteria capped at 5/10.
- Any error path missing → Blind-Path Absence reduced by 2 points per occurrence.
- No link to user stories or originating requirement → Traceability capped at 5/10.
