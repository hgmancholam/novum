# Lessons Learned

> Repository of lessons learned during the Novum development.
> All agents must consult this before starting tasks and update after completing them.

**Last Updated:** 2026-05-26
**Total Lessons:** 3

---

## Recent Lessons

- **L-003:** Static-Only Tests for DB Migrations are Acceptable for Iteration 1 (2026-05-26)
- **L-002:** Unit Tests are Mandatory per F3.S3 (2026-05-26)
- **L-001:** BRD Template for Spec-Driven Development (2026-05-26)

---

## L-003: Static-Only Tests for DB Migrations are Acceptable for Iteration 1

**Date:** 2026-05-26
**Agent:** Reviewer
**Category:** Testing Strategy

### What Happened
BRD-01 review (CR-01-001) considered whether to penalize the Coder for shipping migration tests that only inspect the module source instead of executing `alembic upgrade head` against a live or `pytest-postgresql` database. AC-01 and AC-05 were therefore only verified structurally.

### Decision
Static-only verification is acceptable for iteration 1 **when the BRD itself defers runtime verification to a later phase**. BRD-01 §7 explicitly marks integration testing as BRD-02 territory and `alembic upgrade head` as a manual P1 step. Penalizing the Coder here would amount to enforcing a stricter standard than the spec.

### Rule of Thumb
- If the BRD's "Testing Strategy" section defers a test type, treat its absence as Minor (advisory), never Major.
- If the BRD requires a test type and it is missing, treat its absence as Major or Blocker.
- Cheap source-substring tests (e.g., "does `downgrade()` mention every `drop_table` in reverse order?") are a free win and should be requested as Minors.

### Prevention
Reviewers must read the BRD's `Testing Strategy` section before scoring `Test Coverage`. Do not import the stricter standards of later BRDs retroactively.

---

## L-002: Unit Tests are Mandatory per F3.S3

**Date:** 2026-05-26
**Agent:** Orchestrator
**Category:** Process & Workflow

### What Happened
BRD-00 implementation was marked complete without unit tests. Review CR-00-001 passed at 9.4/10 but user flagged missing tests.

### Root Cause
Workflow step F3.S3 (`generate_unit_tests`) was skipped. The Coder (Orchestrator acting as Coder) focused on file structure setup and forgot that **every BRD implementation must include unit tests**.

### Lesson Learned
**Unit tests are NOT optional.** Per `workflow.md`:
- **F3.S3** explicitly requires: "Create unit tests (backend/frontend)"
- **Quality Standards** mandate: "Test Coverage ≥80%"
- Even setup/infrastructure BRDs need smoke tests to validate tooling works

For BRD-00 specifically:
- Backend: `test_health.py` — validates FastAPI health endpoint
- Frontend: `format.test.ts`, `clipboard.test.ts` — validates utility functions

### Prevention
Before marking any implementation complete:
1. ✅ Verify F3.S3 was executed
2. ✅ Run `pytest` (backend) and `vitest` (frontend)
3. ✅ Confirm tests pass before review submission

### Applied To
- BRD-00: Added missing unit tests
- All future BRDs: F3.S3 is mandatory

---

## L-001: BRD Template for Spec-Driven Development

**Date:** 2026-05-26
**Agent:** BSA Agent
**Category:** Process & Workflow

### What Happened
Creating implementation specs for Novum project. Needed a BRD format that enables Copilot to implement directly from specifications without ambiguity.

### Root Cause
Standard BRD templates are too abstract for AI-assisted coding. Generic descriptions like "implement authentication" don't provide enough detail for automated implementation.

### Lesson Learned
BRDs optimized for Copilot need:
- **Implementation Order** field for sequencing
- **Exact file paths** in File Structure section
- **Copy-paste ready code blocks** (SQL, Python, TypeScript)
- **Alembic migration templates** included inline
- **UI ASCII mockups** for layout specs
- **Implementation Checklist** with specific file paths

### Prevention
Always use the enhanced BRD template at `.github/memory-bank/templates/brd-template.md` for all future specs.

### Applied To
- All 19 BRDs for Novum V1 implementation

---

## Categories

### Bugs & Debugging
_None yet._

### Performance
_None yet._

### Architecture
_None yet._

### Process & Workflow
_None yet._

### Testing
_None yet._

### Documentation
_None yet._

---

## Template

When adding a new lesson, use this format:

```markdown
## L-{number}: {Title}

**Date:** {YYYY-MM-DD}
**Agent:** {agent name}
**Category:** Bugs | Performance | Architecture | Process | Testing | Documentation

### What Happened
{Describe the situation that led to this lesson}

### Root Cause
{What was the underlying cause?}

### Lesson Learned
{What did we learn from this?}

### Prevention
{How do we prevent this in the future?}

### Applied To
- {Where was this lesson applied?}

---
```

---

## How to Add Lessons

1. Increment the lesson number (L-001, L-002, etc.)
2. Fill out the template completely
3. Update the "Total Lessons" count above
4. Add to the appropriate category section
5. Update the "Recent Lessons" section (keep last 5)

---

## Lesson Triggers

Add a lesson when:
- A bug takes more than 30 minutes to resolve
- A code review finds a significant issue
- An architectural decision needs to be revised
- A test fails unexpectedly
- A deployment fails
- A misunderstanding causes rework
- A better approach is discovered after implementation
