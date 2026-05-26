# BRD Template (Spec-Driven Development)

> **Optimized for Copilot-assisted implementation**
> Last updated: 2026-05-26

---

## Template Structure

```markdown
# BRD-{NN}: {Feature Name}

**Document ID:** BRD-{NN}
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** {YYYY-MM-DD}
**Implementation Order:** {N} of {Total}

---

## 1. Executive Summary
Brief description of what this BRD delivers and why.

## 2. RF Traceability
| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-XX | Description | Partial/Complete |

## 3. Dependencies
| Depends On | Required For |
|------------|--------------|
| BRD-XX | BRD-YY |

---

## 4. Technical Specification

### 4.1 File Structure
\`\`\`
backend/
  app/
    {module}/
      __init__.py
      models.py
      routes.py
      service.py
frontend/
  src/
    components/
    pages/
\`\`\`

### 4.2 Database Schema
\`\`\`sql
-- Table definitions with exact column types
CREATE TABLE {table_name} (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ...
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_{table}_{column} ON {table}({column});
\`\`\`

### 4.3 Alembic Migration
\`\`\`python
"""
{description}

Revision ID: {auto}
Revises: {previous}
Create Date: {auto}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.create_table(
        '{table_name}',
        sa.Column('id', postgresql.UUID(), primary_key=True),
        ...
    )

def downgrade() -> None:
    op.drop_table('{table_name}')
\`\`\`

### 4.4 Pydantic Models
\`\`\`python
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID

class {Model}Base(BaseModel):
    """Base model with common fields."""
    model_config = ConfigDict(extra="allow")
    
class {Model}Create({Model}Base):
    """Request model for creation."""
    pass

class {Model}Response({Model}Base):
    """Response model with DB fields."""
    id: UUID
    created_at: datetime
\`\`\`

### 4.5 API Endpoints
| Method | Path | Request Body | Response | Description |
|--------|------|--------------|----------|-------------|
| GET | `/api/{resource}` | - | `List[{Model}Response]` | List all |
| POST | `/api/{resource}` | `{Model}Create` | `{Model}Response` | Create new |
| GET | `/api/{resource}/{id}` | - | `{Model}Response` | Get by ID |

### 4.6 React Components
| Component | Path | Props | State | Description |
|-----------|------|-------|-------|-------------|
| `{Name}` | `src/components/{path}` | `{props}` | `{state}` | Description |

### 4.7 UI Layout
\`\`\`
┌─────────────────────────────────────────────┐
│  Header / Navigation                        │
├──────────┬────────────────────┬─────────────┤
│  Left    │     Center         │    Right    │
│  Panel   │     Content        │    Panel    │
│          │                    │             │
└──────────┴────────────────────┴─────────────┘
\`\`\`

---

## 5. Acceptance Criteria

### AC-01: {Scenario Name}
\`\`\`gherkin
Given {initial context}
  And {additional context}
When {action taken}
Then {expected outcome}
  And {additional verification}
\`\`\`

### AC-02: {Error Scenario}
\`\`\`gherkin
Given {initial context}
When {invalid action}
Then {error handling}
\`\`\`

---

## 6. Implementation Checklist
- [ ] Database migration created — `backend/alembic/versions/{revision}.py`
- [ ] Pydantic models — `backend/app/{module}/models.py`
- [ ] API routes — `backend/app/{module}/routes.py`
- [ ] Service layer — `backend/app/{module}/service.py`
- [ ] React components — `frontend/src/components/{path}/`
- [ ] Unit tests backend — `backend/tests/{module}/`
- [ ] Unit tests frontend — `frontend/src/components/{path}/*.test.tsx`
- [ ] Integration test — `backend/tests/integration/`

## 7. Testing Strategy
| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit (BE) | pytest | `backend/app/{module}/` | ≥80% |
| Unit (FE) | Vitest | `frontend/src/components/` | ≥80% |
| Integration | pytest | `backend/tests/integration/` | Critical paths |
| E2E | Playwright | — | Deferred to V2 |

## 8. Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VAR_NAME` | Yes/No | `value` | Purpose |

## 9. Risks & Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Risk description | High/Med/Low | High/Med/Low | How to mitigate |

## 10. Out of Scope
- Feature X (covered in BRD-YY)
- Feature Y (deferred to V2)
\`\`\`

---

## Usage Notes

1. **Implementation Order** — Always respect the sequence number
2. **File paths** — Use exact paths; Copilot will create them
3. **Code blocks** — Include complete, copy-paste ready code
4. **Acceptance Criteria** — Use Gherkin format strictly
5. **Checklist** — Each item maps to a specific file

---

## Section Applicability by BRD Type

| Section | Infrastructure | Database | Backend | Frontend | Integration |
|---------|---------------|----------|---------|----------|-------------|
| 4.1 File Structure | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4.2 Database Schema | — | ✓ | — | — | — |
| 4.3 Alembic Migration | — | ✓ | — | — | — |
| 4.4 Pydantic Models | — | — | ✓ | — | — |
| 4.5 API Endpoints | — | — | ✓ | — | ✓ |
| 4.6 React Components | — | — | — | ✓ | — |
| 4.7 UI Layout | — | — | — | ✓ | — |
|----|------|--------|------------|------------|-------|
| R-01 | {risk} | High/Medium/Low | High/Medium/Low | {mitigation} | {owner} |
| R-02 | {risk} | High/Medium/Low | High/Medium/Low | {mitigation} | {owner} |

---

## 7. User Stories Summary

| Story ID | Title | Priority | Estimated Effort |
|----------|-------|----------|------------------|
| US-XXX | {title} | High/Medium/Low | S/M/L/XL |
| US-XXX | {title} | High/Medium/Low | S/M/L/XL |

---

## 8. Stakeholders

| Name | Role | Interest | Involvement |
|------|------|----------|-------------|
| {name} | {role} | {interest} | Consulted/Informed/Approver |

---

## 9. Appendix

### 9.1 Glossary

| Term | Definition |
|------|------------|
| {term} | {definition} |

### 9.2 References

- {Reference 1}
- {Reference 2}

### 9.3 Diagrams

{Include relevant diagrams, mockups, or wireframes}

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {date} | BSA Agent | Initial draft |
