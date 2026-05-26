# Lessons Learned

> Repository of lessons learned during the Novum development.
> All agents must consult this before starting tasks and update after completing them.

**Last Updated:** 2026-05-26
**Total Lessons:** 1

---

## Recent Lessons

- **L-001:** BRD Template for Spec-Driven Development (2026-05-26)

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
