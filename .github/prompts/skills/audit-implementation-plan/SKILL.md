# Audit Implementation Plan Skill

## Description
Checklist-driven audit of an Implementation Plan against the parent User Story, the BRD, and the project's functional requirements (RF-01…RF-16). Special focus on **blind-path detection** — guaranteeing that every described code path terminates, every error is handled, and the user is never left without feedback.

## When to Use
- The Orchestrator has produced or revised an Implementation Plan in `docs/implementation-phase/implementation-plans/`.
- Inside the **F2: PLAN** sub-loop (step F2.S3).

## Inputs
- The plan file under audit.
- The parent User Story (`docs/implementation-phase/user-stories/US-XX-*.md`).
- The parent BRD.
- Functional requirements (`docs/understanding-phase/requirement-understanding.md`).
- Data flows and diagrams (`docs/understanding-phase/data-flows-and-diagrams.md`) — **path-completeness invariant is binding**.
- UI prototype (`docs/understanding-phase/ui-prototype.md`) when plan touches UI.
- AI services (`docs/technical-phase/ai-services.md`) when plan touches LLM or search.
- Architecture (`docs/technical-phase/architecture.md`) — 8 rules.
- Any prior audit report for the same plan (`docs/implementation-phase/audits/AUDIT-PLAN-*.md`).

## Checklist

### 1. Requirements Coverage (30%)
- [ ] Every RF affected by the parent User Story is mapped to at least one task in the plan.
- [ ] Stop reasons enum is respected (RF-02) when plan touches the agent loop.
- [ ] Events are append-only (RF-03) — no plan task mutates or deletes events.
- [ ] Schema evolution uses `extra="allow"` or optional keys (architecture §5).
- [ ] Confidence formula `min(S, J)` is preserved (RF-12) if plan touches scoring.
- [ ] LLM calls go through `app/llm/client.py::call` (ai-services §1.3).
- [ ] Search plugins follow the `Source` seam (architecture §1).

### 2. Acceptance Criteria Completeness (20%)
- [ ] Every acceptance criterion of the parent User Story maps to at least one task.
- [ ] Every task lists which acceptance criterion it satisfies.
- [ ] Testing requirements are explicit (unit tests required per `testing-policy`).
- [ ] Coverage target ≥ 80% is stated.

### 3. Blind-Path Absence (25%) — **CRITICAL**

Apply the **Blind-Path Detection Checklist** from the Auditor agent. Verify for every step of the plan:

- [ ] **Path completeness** — every non-terminal task has a defined next step for every reachable outcome (success, retryable error, fatal error).
- [ ] **Error handling** — every LLM call, HTTP call, DB call, and SSE write has either retry, recovery, or a mapping to a terminal `stop_reason`.
- [ ] **User feedback continuity** — every long-running action emits at least one event the UI subscribes to; UI never shows an empty/frozen state.
- [ ] **Terminal reachability** — every flow reaches at least one of the 7 `stop_reason` values.
- [ ] **Cancellation honored** — every loop or long-running task respects `user_cancelled` (RF-08).
- [ ] **Resume coverage** — every error-terminal and cancel-terminal has a defined resume path (RF-08).
- [ ] **Budget cap** — every loop has a budget check that can emit `stopped_by_budget` (RF-01·F).
- [ ] **Concurrency** — single-writer-per-run invariant is preserved (no parallel writers).
- [ ] **Cross-reference with `data-flows-and-diagrams.md`** — no plan task contradicts an existing path in the canonical diagrams.

### 4. Traceability (15%)
- [ ] Plan ID follows naming convention.
- [ ] Plan links to parent User Story AND BRD.
- [ ] Each task lists: files touched, dependencies, effort estimate, RF mapping.
- [ ] Order of tasks is feasible (no forward dependency).

### 5. Consistency with Authoritative Docs (10%)
- [ ] No banned tech (Redis, Docker, LangGraph, Celery, WebSockets, vector DB, etc.) — see `tech-stack.md`.
- [ ] No violation of the 8 architectural rules.
- [ ] UI tasks reference exact states/microcopy from `ui-prototype.md`.

## Scoring Rule

Same weighted scoring as the Auditor agent. Round to one decimal.

| Score | Verdict |
|---|---|
| ≥ 9.0 | APPROVED |
| 7.0 – 8.9 | NEEDS REVISION |
| < 7.0 | MAJOR GAPS |

## Output
A markdown report saved to `docs/implementation-phase/audits/AUDIT-PLAN-US-XX-{iter}-{date}.md`.

## Common Failure Patterns (auto-deduct)
- One or more tasks introduce a state with no outgoing transition for a known outcome → Blind-Path Absence reduced by 3 points per occurrence.
- Any LLM call not routed through `app/llm/client.py::call` → Consistency = 0/10 (auto-fail criterion).
- Any new banned dependency → Consistency = 0/10 (auto-fail criterion).
- Missing budget check on a loop → Blind-Path Absence reduced by 4 points.
- Missing cancel handling on a long-running task → Blind-Path Absence reduced by 3 points.
- No mapping from acceptance criteria to tasks → Acceptance Criteria capped at 4/10.

## Audit Algorithm (pseudo-code)

```
1. Load plan, parent US, parent BRD, RFs, diagrams.
2. Build set RFs_required = union(parent_US.affected_RFs).
3. Build set RFs_covered = union(plan.tasks[*].cited_RFs).
4. coverage_gap = RFs_required - RFs_covered → reduce Requirements Coverage.
5. For each task t:
     - assert t.has_next_step_for_each_outcome → else blind-path finding.
     - assert t.error_handling defined for each external call → else finding.
     - assert t.cancellation_handled if t.is_long_running → else finding.
     - assert t.budget_check if t.is_loop → else finding.
     - assert t.tests defined → else acceptance-criteria deduction.
6. For each acceptance criterion ac in parent_US:
     - assert ∃ task t such that ac ∈ t.satisfies → else acceptance-criteria deduction.
7. Score each criterion, sum weighted, emit verdict and report.
```
