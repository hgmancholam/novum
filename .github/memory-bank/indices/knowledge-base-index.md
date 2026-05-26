# Knowledge Base Index

> Central index of all knowledge artifacts in the Novum project.
> Updated automatically by agents after each task.

**Last Updated:** 2026-05-26
**Updated By:** System Initialization

---

## Business Requirements Documents (BRDs)

| ID | Title | Date | Status | Location |
|----|-------|------|--------|----------|
| - | No BRDs created yet | - | - | - |

---

## User Stories

| ID | Title | BRD Reference | Status | Location |
|----|-------|---------------|--------|----------|
| - | No user stories created yet | - | - | - |

---

## Implementation Plans

| ID | User Story | Date | Status | Location |
|----|------------|------|--------|----------|
| - | No plans created yet | - | - | - |

---

## Code Reviews

| ID | User Story | Iteration | Score | Status | Location |
|----|------------|-----------|-------|--------|----------|
| - | No reviews completed yet | - | - | - | - |

---

## Key Architectural Components

| Component | Type | Location | Description |
|-----------|------|----------|-------------|
| FastAPI App | Backend | `backend/app/main.py` | Main application entry point |
| React App | Frontend | `frontend/src/App.tsx` | Frontend entry point |
| Event Models | Backend | `backend/app/models/events.py` | Event-sourcing models |
| API Client | Frontend | `frontend/src/lib/api.ts` | HTTP client wrapper |

---

## Database Entities (RF-05)

| Entity | Table | Columns | Description |
|--------|-------|---------|-------------|
| User | `users` | `id`, `username` (unique), `token_hash`, `created_at` | Lightweight identity |
| Run | `runs` | `id`, `owner_username` FK, `question`, `user_context`, `output_format`, `confidence_threshold`, `question_type`, `stop_reason`, `parent_run_id`, `forked_at_event_id` | Research run tracking |
| Event | `events` | `id`, `run_id` FK, `parent_event_id` FK, `step_index`, `type`, `payload JSONB`, `created_at` | Append-only event log |

---

## API Endpoints (Planned — RF-08, RF-09)

| Method | Endpoint | Description | RF |
|--------|----------|-------------|-----|
| POST | `/api/runs` | Create new run | RF-01 |
| GET | `/api/runs` | List recent runs | RF-09 |
| GET | `/api/runs/{id}` | Get run details | RF-02 |
| GET | `/api/runs/{id}/events` | Stream run events (SSE) | RF-08 |
| POST | `/api/runs/{id}/resume` | Resume stopped/errored run | RF-11 |
| POST | `/api/runs/{id}/fork` | Fork run from event | RF-03 |
| POST | `/api/runs/{id}/cancel` | Cancel in-progress run | RF-08 |

---

## Event Types (~17 — RF-03, RF-04, RF-11, RF-14, RF-15)

| Event | Purpose | Forkable |
|-------|---------|----------|
| `QuestionAsked` | Initial question | No |
| `PlanCreated` | Sub-claim decomposition | Yes |
| `PlanCritiqued` | Plan quality check | No |
| `PlanRevised` | Plan update | No |
| `ToolCalled` | Search invocation | No |
| `EvidenceAdded` | Evidence with polarity | No |
| `ClaimCovered` | Sub-claim satisfied | No |
| `ClaimUncoverable` | Sub-claim failed | No |
| `SourceFailed` | Tool failure | No |
| `AmbiguityDetected` | Question ambiguity | Yes |
| `ContradictionDetected` | Source conflict | Yes |
| `JudgeRuled` | Judge evaluation | Yes |
| `ConfidenceMismatch` | S/J divergence flag | No |
| `AgentErrored` | LLM failure | No |
| `ResumedAfterError` | Recovery event | No |
| `ResumedAfterCancel` | Recovery event | No |
| `Stopped` | Terminal event | Yes |

---

## Stop Reasons (RF-02 — 7 enum values)

| Value | Terminal Type | Description |
|-------|---------------|-------------|
| `judge_confirmed` | Success | Answer approved by judge |
| `honest_unanswerable` | Honest | Insufficient evidence |
| `honest_contradiction` | Honest | Irreconcilable conflict |
| `honest_ambiguous` | Honest | Question ambiguity |
| `stopped_by_budget` | Safety | Budget exhausted |
| `user_cancelled` | User | Manual cancellation |
| `errored` | Error | Unrecoverable failure |

---

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| Tech Stack | Technology decisions | `docs/technical-phase/tech-stack.md` |
| Architecture | System design | `docs/technical-phase/architecture.md` |
| Infrastructure | Deployment config | `docs/technical-phase/infrastructure.md` |
| Requirements | Business requirements | `docs/understanding-phase/requirement-understanding.md` |

---

## Agent Configurations

| Agent | Purpose | Location |
|-------|---------|----------|
| Orchestrator | Workflow coordination | `.github/agents/orchestrator.agent.md` |
| BSA | Requirements analysis | `.github/agents/bsa.agent.md` |
| Coder | Implementation | `.github/agents/coder.agent.md` |
| Reviewer | Code review | `.github/agents/reviewer.agent.md` |

---

## Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| GitHub MCP | GitHub integration | `.github/prompts/skills/github-mcp/` |
| UX Frontend | UI/UX best practices | `.github/prompts/skills/ux-frontend/` |
| Database | PostgreSQL operations | `.github/prompts/skills/database/` |
| Implementation Plan | Planning tasks | `.github/prompts/skills/implementation-plan/` |
| Unit Test Backend | Python testing | `.github/prompts/skills/unit-test-backend/` |
| Unit Test Frontend | React testing | `.github/prompts/skills/unit-test-frontend/` |
| Memory Protocol | Knowledge management | `.github/prompts/skills/memory-protocol/` |

---

## Quick Links

- [Workflow Definition](.github/workflow.yaml)
- [Workflow Diagram](.github/workflow.md)
- [Copilot Instructions](.github/copilot-instructions.md)
- [Project Context](shared/project-context.md)
- [Lessons Learned](logs/lessons-learned.md)
- [Decisions History](logs/decisions-history.md)
