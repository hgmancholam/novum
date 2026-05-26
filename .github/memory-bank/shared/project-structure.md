# Novum Project Structure

> Reference for the project's file and folder organization.

**Last Updated:** 2026-05-26

---

## Current Structure

```
novum/
│
├── .github/                          # GitHub and Copilot configuration
│   ├── copilot-instructions.md       # Main Copilot instructions
│   ├── workflow.yaml                 # Agentic workflow definition
│   ├── workflow.md                   # Workflow diagram (Mermaid)
│   │
│   ├── agents/                       # Copilot agent definitions
│   │   ├── orchestrator.agent.md     # Workflow coordinator
│   │   ├── bsa.agent.md              # Business analyst
│   │   ├── coder.agent.md            # Implementation agent
│   │   └── reviewer.agent.md         # Code reviewer
│   │
│   ├── prompts/                      # Shared prompts and skills
│   │   └── skills/                   # Skill definitions
│   │       ├── github-mcp/
│   │       │   └── SKILL.md
│   │       ├── ux-frontend/
│   │       │   └── SKILL.md
│   │       ├── database/
│   │       │   └── SKILL.md
│   │       ├── implementation-plan/
│   │       │   └── SKILL.md
│   │       ├── unit-test-backend/
│   │       │   └── SKILL.md
│   │       ├── unit-test-frontend/
│   │       │   └── SKILL.md
│   │       └── memory-protocol/
│   │           └── SKILL.md
│   │
│   └── memory-bank/                  # Shared knowledge base
│       ├── templates/                # Document templates
│       │   ├── brd-template.md
│       │   ├── user-story-template.md
│       │   └── decision-record-template.md
│       ├── indices/                  # Knowledge indices
│       │   └── knowledge-base-index.md
│       ├── logs/                     # Historical logs
│       │   ├── decisions-history.md
│       │   └── lessons-learned.md
│       ├── conventions/              # Standards
│       │   └── naming-conventions.md
│       └── shared/                   # Shared documentation
│           ├── project-context.md
│           ├── project-structure.md
│           └── architecture-summary.md
│
├── docs/                             # Project documentation
│   ├── understanding-phase/          # Requirements analysis
│   │   ├── requirement-understanding.md
│   │   ├── stopping-signal-analysis.md
│   │   ├── data-flows-and-diagrams.md
│   │   ├── ui-prototype.md
│   │   ├── confidence-calculation.md
│   │   ├── research-method-selection.md
│   │   └── project-name.md
│   │
│   ├── technical-phase/              # Technical design
│   │   ├── architecture.md
│   │   ├── tech-stack.md
│   │   ├── infrastructure.md
│   │   ├── ai-services.md
│   │   └── server-backend-configuration.md
│   │
│   └── implementation-phase/         # Generated artifacts
│       ├── brds/                     # Business Requirements Docs
│       │   └── README.md
│       ├── user-stories/             # User Stories
│       │   └── README.md
│       ├── implementation-plans/     # Implementation Plans
│       │   └── README.md
│       ├── reviews/                  # Code Reviews
│       │   └── README.md
│       └── unit-tests/               # Test Documentation
│           └── README.md
│
├── backend/                          # Python/FastAPI backend (planned)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app entry
│   │   ├── config.py                 # Configuration
│   │   ├── models/                   # Pydantic/SQLAlchemy models
│   │   ├── api/                      # API routes
│   │   ├── services/                 # Business logic
│   │   ├── repositories/             # Data access
│   │   ├── llm/                      # LLM integration
│   │   ├── seams/                    # Plugin interfaces
│   │   └── utils/                    # Utilities
│   ├── alembic/                      # Database migrations
│   ├── tests/                        # Test suite
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/                         # React/Vite frontend (planned)
│   ├── src/
│   │   ├── components/               # Atomic design structure
│   │   │   ├── atoms/
│   │   │   ├── molecules/
│   │   │   ├── organisms/
│   │   │   ├── templates/
│   │   │   └── pages/
│   │   ├── lib/                      # Utilities
│   │   │   ├── api.ts
│   │   │   ├── sse.ts
│   │   │   └── utils.ts
│   │   ├── stores/                   # Zustand stores
│   │   ├── hooks/                    # Custom hooks
│   │   ├── types/                    # TypeScript types
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── scripts/                          # Utility scripts
│   ├── export_types.py               # Pydantic → TypeScript
│   └── metrics.py                    # KPI calculations
│
├── LICENSE
├── README.md
└── api_key_services.txt              # API key reference (gitignored)
```

---

## Key Locations

### For BSA Agent
- Create BRDs in: `docs/implementation-phase/brds/`
- Create User Stories in: `docs/implementation-phase/user-stories/`

### For Orchestrator
- Create Plans in: `docs/implementation-phase/implementation-plans/`
- Read workflow: `.github/workflow.yaml`

### For Coder
- Backend code: `backend/app/`
- Frontend code: `frontend/src/`
- Backend tests: `backend/tests/`
- Frontend tests: `frontend/src/**/*.test.tsx`

### For Reviewer
- Create Reviews in: `docs/implementation-phase/reviews/`
- Reference architecture: `docs/technical-phase/architecture.md`

### For All Agents
- Memory bank: `.github/memory-bank/`
- Project context: `.github/memory-bank/shared/project-context.md`
- Conventions: `.github/memory-bank/conventions/naming-conventions.md`

---

## File Naming Quick Reference

| Type | Pattern | Location |
|------|---------|----------|
| BRD | `BRD-{date}-{feature}.md` | `docs/implementation-phase/brds/` |
| User Story | `US-{number}-{slug}.md` | `docs/implementation-phase/user-stories/` |
| Plan | `PLAN-{US}-{date}.md` | `docs/implementation-phase/implementation-plans/` |
| Review | `REVIEW-{US}-{iter}-{date}.md` | `docs/implementation-phase/reviews/` |
| Agent | `{name}.agent.md` | `.github/prompts/` |
| Skill | `SKILL.md` | `.github/prompts/skills/{skill-name}/` |
