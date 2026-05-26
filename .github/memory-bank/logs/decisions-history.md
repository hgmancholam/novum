# Decisions History

> Chronological log of all decisions made during the Novum development.
> Each decision follows the decision record template.

**Last Updated:** 2026-05-26
**Total Decisions:** 3

---

## Recent Decisions

## D-003: BRD-01 Database Schema — Review APPROVED (9.0/10)

**Date:** 2026-05-26
**Agent:** Reviewer
**Category:** Review
**Status:** Approved

### Context
Iteration 1 review of BRD-01 (PostgreSQL schema + Alembic migration + ORM models). Coder declared 7 intentional deviations from BRD §4.4 code blocks (all typing/SQLAlchemy 2.0 idiomatic improvements). 16 unit tests passed in 0.15 s.

### Decision
APPROVED at exactly 9.0/10 weighted score. Zero Blockers, zero Majors. Two Minors filed for follow-up in BRD-02:
- Add a downgrade-ordering static test to close the AC-05 gap.
- Tighten `Mapped[str | None]` enum columns to `Literal[...]` or `Enum` when domain models land.

### Consequences
- Proceed to BRD-02 (Pydantic domain models & event types).
- The Coder's `text()` wrapping of every `server_default` and explicit `postgresql.UUID(as_uuid=True)` become the project standard.
- The `pgcrypto` extension creation (added by Coder, missing from BRD §4.3) is acknowledged as a substantive correctness fix.

### Artifacts Created
- Review report: [CR-01-001-database-schema.md](../../../docs/implementation-phase/reviews/CR-01-001-database-schema.md)

---

## D-002: BRD-00 Implementation — Project Setup

**Date:** 2026-05-26
**Agent:** Orchestrator
**Category:** Implementation
**Status:** Completed

### Context
First implementation in the Novum project. Needed to establish the complete folder structure and tooling configuration for both backend (Python/FastAPI) and frontend (React/Vite).

### Decision
Implement BRD-00 as the foundation for all subsequent BRDs:
- Backend: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic
- Frontend: React 19 + Vite + Tailwind v4 (plugin, no config)
- Full atomic design structure for components

### Consequences
- All subsequent BRDs can build on this foundation
- Tailwind v4 uses `@import "tailwindcss"` (not v3 directives)
- Path aliases configured via `vite-tsconfig-paths`
- Agent tooling updated to include full toolset for subagents

### Artifacts Created
- `backend/` complete structure (pyproject.toml, app/, alembic/, tests/)
- `frontend/` complete structure (package.json, src/, components/, lib/)
- `scripts/` (dev.ps1, export_types.py)
- Implementation plan: `docs/implementation-phase/implementation-plans/IP-00-project-setup.md`

---

## D-001: Spec-Driven Development with Comprehensive BRDs

**Date:** 2026-05-26
**Agent:** BSA
**Category:** Process
**Status:** Accepted

### Context
The project needed detailed specifications to enable AI-assisted implementation with GitHub Copilot. Traditional BRDs were too high-level and didn't include the technical details needed for copy-paste implementation.

### Decision
Create 19 comprehensive BRDs (BRD-00 to BRD-18) in strict implementation order with:
- Complete file structures with paths
- Copy-paste ready code blocks
- Alembic migrations
- Pydantic models
- React components
- Acceptance criteria in Gherkin format
- Implementation checklists

### Consequences
- Development will follow strict sequence
- Each BRD is self-contained for implementation
- Code can be directly copied from BRDs
- Reduces ambiguity and decision-making during coding

### Artifacts Created
- 19 BRDs in `docs/implementation-phase/brds/`
- Updated knowledge base index
- Enhanced BRD template in memory bank

---

## Decision Categories

### Architecture Decisions
_None yet._

### Technology Decisions
_None yet._

### Process Decisions
- D-001: Spec-Driven Development with Comprehensive BRDs

### Design Decisions
_None yet._

---

## Template

When adding a new decision, use this format:

```markdown
## D-{number}: {Title}

**Date:** {YYYY-MM-DD}
**Agent:** {agent name}
**Category:** Architecture | Technology | Process | Design
**Status:** Accepted

### Context
{Why was this decision needed?}

### Decision
{What was decided?}

### Rationale
{Why was this the best choice?}

### Consequences
- {Positive/negative consequence}

### References
- {Link to related document}

---
```

---

## How to Add Decisions

1. Increment the decision number (D-001, D-002, etc.)
2. Fill out the template completely
3. Update the "Total Decisions" count above
4. Add to the appropriate category section
5. Update the "Recent Decisions" section (keep last 5)
