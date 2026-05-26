# Memory Protocol Skill

## Description
Defines the mandatory memory protocol for all agents. Manages reading, updating, and maintaining the shared knowledge base across the development workflow.

## When to Use
- Before starting ANY task (read context)
- After completing ANY task (update logs)
- When recording decisions or lessons learned
- When creating new knowledge base entries

## Memory Bank Structure

```
.github/memory-bank/
├── templates/                    # Document templates
│   ├── brd-template.md
│   ├── user-story-template.md
│   ├── implementation-plan-template.md
│   ├── review-report-template.md
│   └── decision-record-template.md
├── indices/                      # Knowledge base indices
│   └── knowledge-base-index.md
├── logs/                         # Historical logs
│   ├── decisions-history.md
│   └── lessons-learned.md
├── conventions/                  # Standards and conventions
│   └── naming-conventions.md
└── shared/                       # Shared documentation
    ├── project-context.md
    ├── project-structure.md
    └── architecture-summary.md
```

## Protocol Operations

### Before Every Task (MANDATORY)

```yaml
pre_task_read:
  required:
    - path: ".github/memory-bank/shared/project-context.md"
      purpose: "Understand current project state"
    - path: ".github/memory-bank/indices/knowledge-base-index.md"
      purpose: "Find relevant existing knowledge"
    - path: ".github/memory-bank/logs/lessons-learned.md"
      purpose: "Avoid repeating past mistakes"
  
  agent_specific:
    BSA:
      - ".github/memory-bank/templates/brd-template.md"
      - ".github/memory-bank/conventions/naming-conventions.md"
    Coder:
      - ".github/memory-bank/shared/architecture-summary.md"
      - ".github/memory-bank/conventions/naming-conventions.md"
    Reviewer:
      - ".github/memory-bank/shared/architecture-summary.md"
      - ".github/memory-bank/conventions/naming-conventions.md"
    Orchestrator:
      - ".github/memory-bank/templates/implementation-plan-template.md"
```

### After Every Task (MANDATORY)

```yaml
post_task_update:
  always_update:
    - path: ".github/memory-bank/logs/decisions-history.md"
      when: "Any decision was made"
      format: "decision_record"
    
    - path: ".github/memory-bank/indices/knowledge-base-index.md"
      when: "New artifacts were created"
      format: "index_entry"
  
  conditional_update:
    - path: ".github/memory-bank/logs/lessons-learned.md"
      when: "New insight or mistake discovered"
      format: "lesson_entry"
```

## File Formats

### Project Context (shared/project-context.md)
```markdown
# Novum Project Context

**Last Updated:** {date}
**Updated By:** {agent}

## Current State
- Phase: {design | development | testing | deployment}
- Sprint: {number}
- Active Features: {list}

## Recent Changes
| Date | Change | Agent |
|------|--------|-------|
| {date} | {description} | {agent} |

## Active Decisions
| ID | Decision | Status | Reference |
|----|----------|--------|-----------|
| D-001 | ... | Active | {link} |

## Blockers
- {blocker 1}
- {blocker 2}
```

### Knowledge Base Index (indices/knowledge-base-index.md)
```markdown
# Knowledge Base Index

## BRDs
| ID | Title | Date | Status |
|----|-------|------|--------|
| BRD-001 | ... | {date} | {status} |

## User Stories
| ID | Title | BRD | Status |
|----|-------|-----|--------|
| US-001 | ... | BRD-001 | {status} |

## Implementation Plans
| ID | User Story | Date | Status |
|----|------------|------|--------|
| PLAN-001 | US-001 | {date} | {status} |

## Code Reviews
| ID | User Story | Iteration | Score | Status |
|----|------------|-----------|-------|--------|
| REV-001 | US-001 | 1 | 8/10 | Revising |

## Key Components
| Component | Location | Description |
|-----------|----------|-------------|
| {name} | {path} | {description} |
```

### Decisions History (logs/decisions-history.md)
```markdown
# Decisions History

## D-{number}: {Title}

**Date:** {date}
**Agent:** {agent}
**Context:** {what prompted this decision}

### Decision
{What was decided}

### Rationale
{Why this was chosen}

### Alternatives Considered
- Alternative 1: {reason rejected}
- Alternative 2: {reason rejected}

### Impact
- {impact 1}
- {impact 2}

### References
- {link to relevant doc}

---
```

### Lessons Learned (logs/lessons-learned.md)
```markdown
# Lessons Learned

## L-{number}: {Title}

**Date:** {date}
**Agent:** {agent}
**Category:** {bug | performance | architecture | process}

### What Happened
{Description of the situation}

### Root Cause
{Why it happened}

### Lesson
{What we learned}

### Prevention
{How to avoid in the future}

### Applied To
- {where this lesson was applied}

---
```

### Naming Conventions (conventions/naming-conventions.md)
```markdown
# Naming Conventions

## Files

### Documentation
| Type | Pattern | Example |
|------|---------|---------|
| BRD | `BRD-{YYYY-MM-DD}-{feature}.md` | BRD-2026-05-26-auth.md |
| User Story | `US-{number}-{slug}.md` | US-001-create-session.md |
| Plan | `PLAN-{US}-{date}.md` | PLAN-US-001-2026-05-26.md |
| Review | `REVIEW-{US}-{iter}-{date}.md` | REVIEW-US-001-1-2026-05-26.md |

### Code
| Type | Convention | Example |
|------|------------|---------|
| Python modules | snake_case | `user_service.py` |
| Python classes | PascalCase | `UserService` |
| Python functions | snake_case | `create_user` |
| React components | PascalCase | `UserCard.tsx` |
| React hooks | camelCase, use prefix | `useUserStore` |
| TypeScript types | PascalCase | `UserResponse` |
| CSS classes | kebab-case (Tailwind) | `bg-primary` |

## Identifiers

### API
| Type | Convention | Example |
|------|------------|---------|
| Endpoints | kebab-case, plural nouns | `/api/user-sessions` |
| Query params | camelCase | `?includeEvents=true` |

### Database
| Type | Convention | Example |
|------|------------|---------|
| Tables | snake_case, plural | `user_sessions` |
| Columns | snake_case | `created_at` |
| Indexes | `idx_{table}_{columns}` | `idx_events_run_id` |

### Git
| Type | Convention | Example |
|------|------------|---------|
| Branch (feature) | `feature/{US}-{slug}` | `feature/us-001-session` |
| Branch (fix) | `fix/{issue}-{slug}` | `fix/123-null-check` |
| Commit | Conventional Commits | `feat(auth): add session` |
```

## Memory Operations API

### Read Operation
```typescript
// Conceptual API for reading memory
async function readMemory(path: string): Promise<string> {
  // Read file from .github/memory-bank/
  return await readFile(`.github/memory-bank/${path}`);
}

// Usage in agent
const context = await readMemory("shared/project-context.md");
const lessons = await readMemory("logs/lessons-learned.md");
```

### Update Operation
```typescript
// Conceptual API for updating memory
async function updateMemory(
  path: string,
  content: string,
  mode: "append" | "replace"
): Promise<void> {
  const fullPath = `.github/memory-bank/${path}`;
  
  if (mode === "append") {
    const existing = await readFile(fullPath);
    await writeFile(fullPath, `${existing}\n\n${content}`);
  } else {
    await writeFile(fullPath, content);
  }
}

// Usage in agent
await updateMemory(
  "logs/decisions-history.md",
  decisionRecord,
  "append"
);
```

## Compliance Check

Before completing any task, verify:

- [ ] Read project context
- [ ] Read relevant knowledge base entries
- [ ] Read lessons learned
- [ ] Updated decisions history (if applicable)
- [ ] Updated lessons learned (if applicable)
- [ ] Updated knowledge base index (if new artifacts)

## Integration with Workflow

```yaml
# In workflow.yaml
memory_protocol:
  mandatory_for_all_agents: true
  enforcement: strict
  audit_log: true
```
