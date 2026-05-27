# Knowledge Base Index

> Central index of all knowledge artifacts in the Novum project.
> Updated automatically by agents after each task.

**Last Updated:** 2026-05-26
**Updated By:** Orchestrator Agent (post IP-08 / REVIEW-IP-08-1 approved 10/10)

---

## Templates

| Template | Location | Updated | Description |
|----------|----------|---------|-------------|
| BRD Template (Spec-Driven) | `.github/memory-bank/templates/brd-template.md` | 2026-05-26 | Enhanced template for Copilot-assisted implementation |

---

## Conventions

| Convention | Location | Updated | Description |
|------------|----------|---------|-------------|
| Naming Conventions | `.github/memory-bank/conventions/naming-conventions.md` | 2026-05-26 | File, identifier, and slug naming rules across the project |
| Iconography | `.github/memory-bank/conventions/iconography.md` | 2026-05-26 | Brand mark + Lucide-only icon family rules. Binding from `ui-prototype.md` §1.9 |

---

## Implementation Plans

| ID | BRD Reference | Date | Status | Location |
|----|---------------|------|--------|----------|
| IP-00 | BRD-00 Project Setup | 2026-05-26 | Completed | [IP-00](../../../docs/implementation-phase/implementation-plans/IP-00-project-setup.md) |
| IP-01 | BRD-01 Database Schema | 2026-05-26 | Completed | [IP-01](../../../docs/implementation-phase/implementation-plans/IP-01-database-schema.md) |
| IP-02 | BRD-02 Domain Models | 2026-05-26 | Completed | [IP-02](../../../docs/implementation-phase/implementation-plans/IP-02-domain-models.md) |
| IP-03 | BRD-03 FastAPI Core & API Skeleton | 2026-05-26 | Completed | [IP-03](../../../docs/implementation-phase/implementation-plans/IP-03-fastapi-core.md) |
| IP-04 | BRD-04 User Identity | 2026-05-26 | Completed | [IP-04](../../../docs/implementation-phase/implementation-plans/IP-04-user-identity.md) |
| IP-05 | BRD-05 LLM Client Integration | 2026-05-26 | Completed | [IP-05](../../../docs/implementation-phase/implementation-plans/IP-05-llm-client.md) |
| IP-06 | BRD-06 Source Plugins (Tavily + Wikipedia) | 2026-05-26 | Completed | [IP-06](../../../docs/implementation-phase/implementation-plans/IP-06-source-plugins.md) |
| IP-07 | BRD-07 Agent FSM & Research Loop | 2026-05-27 | Completed | [IP-07](../../../docs/implementation-phase/implementation-plans/IP-07-agent-fsm.md) |
| IP-08 | BRD-08 Confidence Calculation Engine | 2026-05-26 | Completed | [IP-08](../../../docs/implementation-phase/implementation-plans/IP-08-confidence-calculation.md) |
| IP-11 | BRD-11 Frontend Setup & Layout Shell | 2026-05-26 | Completed | [IP-11](../../../docs/implementation-phase/implementation-plans/IP-11-frontend-layout.md) |
| IP-11-iter2 | BRD-11 / BRD-04 Auth Wiring | 2026-05-26 | Completed | [IP-11 iter 2](../../../docs/implementation-phase/implementation-plans/IP-11-frontend-layout-iter2.md) |
| IP-12 | BRD-12 History Panel | 2026-05-26 | Completed | [IP-12](../../../docs/implementation-phase/implementation-plans/IP-12-history-panel.md) |
| IP-13 | BRD-13 Center Panel | 2026-05-26 | Completed | [IP-13](../../../docs/implementation-phase/implementation-plans/IP-13-center-panel.md) |
| IP-13-iter2 | BRD-13 Center Panel — UX Completion | 2026-05-27 | Completed | [IP-13 iter 2](../../../docs/implementation-phase/implementation-plans/IP-13-center-panel-iter2.md) |
| IP-09 | BRD-09 Stopping Signal Policy | 2026-05-26 | Ready for Implementation (F2 approved 9.75/10) | [IP-09](../../../docs/implementation-phase/implementation-plans/IP-09-stopping-signals.md) |

---

## Business Requirements Documents (BRDs)

| ID | Title | Date | Status | Location |
|----|-------|------|--------|----------|
| BRD-00 | Project Setup & Folder Structure | 2026-05-26 | Draft | [BRD-00](../../../docs/implementation-phase/brds/BRD-00-project-setup.md) |
| BRD-01 | Database Schema & Alembic Migrations | 2026-05-26 | Implemented | [BRD-01](../../../docs/implementation-phase/brds/BRD-01-database-schema.md) |
| BRD-02 | Pydantic Domain Models & Event System | 2026-05-26 | Implemented | [BRD-02](../../../docs/implementation-phase/brds/BRD-02-domain-models.md) |
| BRD-03 | FastAPI Core & API Skeleton | 2026-05-26 | Implemented | [BRD-03](../../../docs/implementation-phase/brds/BRD-03-fastapi-core.md) |
| BRD-04 | User Identity (Lightweight Auth) | 2026-05-26 | Implemented | [BRD-04](../../../docs/implementation-phase/brds/BRD-04-user-identity.md) |
| BRD-05 | LLM Client Integration | 2026-05-26 | Implemented | [BRD-05](../../../docs/implementation-phase/brds/BRD-05-llm-client.md) |
| BRD-06 | Source Plugins (Tavily + Wikipedia) | 2026-05-26 | Implemented | [BRD-06](../../../docs/implementation-phase/brds/BRD-06-source-plugins.md) |
| BRD-07 | Agent FSM & Research Loop | 2026-05-27 | Implemented | [BRD-07](../../../docs/implementation-phase/brds/BRD-07-agent-fsm.md) |
| BRD-08 | Confidence Calculation Engine | 2026-05-26 | Implemented | [BRD-08](../../../docs/implementation-phase/brds/BRD-08-confidence-calculation.md) |
| BRD-09 | Stopping Signal Policy | 2026-05-26 | Draft | [BRD-09](../../../docs/implementation-phase/brds/BRD-09-stopping-signals.md) |
| BRD-10 | SSE Streaming & Resume | 2026-05-26 | Draft | [BRD-10](../../../docs/implementation-phase/brds/BRD-10-sse-streaming.md) |
| BRD-11 | Frontend Setup & Layout Shell | 2026-05-26 | Draft | [BRD-11](../../../docs/implementation-phase/brds/BRD-11-frontend-layout.md) |
| BRD-12 | History Panel (Left Sidebar) | 2026-05-26 | Draft | [BRD-12](../../../docs/implementation-phase/brds/BRD-12-history-panel.md) |
| BRD-13 | Center Panel (Question & Answer) | 2026-05-26 | Implemented | [BRD-13](../../../docs/implementation-phase/brds/BRD-13-center-panel.md) |
| BRD-14 | Trace Panel (Right Sidebar) | 2026-05-26 | Draft | [BRD-14](../../../docs/implementation-phase/brds/BRD-14-trace-panel.md) |
| BRD-15 | Fork & Resume from Events | 2026-05-26 | Draft | [BRD-15](../../../docs/implementation-phase/brds/BRD-15-fork-resume.md) |
| BRD-16 | Output Format Renderers | 2026-05-26 | Draft | [BRD-16](../../../docs/implementation-phase/brds/BRD-16-output-renderers.md) |
| BRD-17 | Testing Strategy & Calibration Eval | 2026-05-26 | Draft | [BRD-17](../../../docs/implementation-phase/brds/BRD-17-testing-strategy.md) |
| BRD-18 | Infrastructure & Deployment | 2026-05-26 | Draft | [BRD-18](../../../docs/implementation-phase/brds/BRD-18-infrastructure.md) |

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

| ID | BRD Reference | Iteration | Score | Status | Location |
|----|---------------|-----------|-------|--------|----------|
| CR-00-001 | BRD-00 Project Setup | 1 | 9.4/10 | Approved | [CR-00-001](../../../docs/implementation-phase/reviews/CR-00-001-project-setup.md) |
| CR-01-001 | BRD-01 Database Schema | 1 | 9.0/10 | Approved | [CR-01-001](../../../docs/implementation-phase/reviews/CR-01-001-database-schema.md) |
| CR-02-001 | BRD-02 Domain Models | 1 | 9.6/10 | Approved | [CR-02-001](../../../docs/implementation-phase/reviews/CR-02-001-domain-models.md) |
| CR-05-001 | BRD-05 LLM Client Integration | 1 | 9.5/10 | Approved | [CR-05-001](../../../docs/implementation-phase/reviews/CR-05-001-llm-client.md) |
| CR-06-001 | BRD-06 Source Plugins (Tavily + Wikipedia) | 1 | 9.4/10 | Approved | [CR-06-001](../../../docs/implementation-phase/reviews/CR-06-001-source-plugins.md) |
| CR-11-002 | BRD-11 / BRD-04 Auth Wiring (iter 2) | 1 | 9.6/10 | Approved | [CR-11-002](../../../docs/implementation-phase/reviews/CR-11-002-auth-wiring.md) |
| CR-13-001 | BRD-13 Center Panel | 1 | 9.6/10 | Approved | [CR-13-001](../../../docs/implementation-phase/reviews/CR-13-001-center-panel.md) |
| CR-13-002 | BRD-13 Center Panel (iter 2) | 1 | 8.88/10 | Returned to Coder | [CR-13-002](../../../docs/implementation-phase/reviews/CR-13-002-center-panel-iter2.md) |
| CR-13-003 | BRD-13 Center Panel (iter 2 — re-review) | 2 | 9.53/10 | Approved | [CR-13-003](../../../docs/implementation-phase/reviews/CR-13-003-center-panel-iter2.md) |
| CR-07-001 | BRD-07 Agent FSM & Research Loop | 1 | 9.4/10 | Approved | [CR-07-001](../../../docs/implementation-phase/reviews/CR-07-001-agent-fsm.md) |

---

## Unit Test Inventories

| ID | Plan Reference | Date | Location |
|----|----------------|------|----------|
| UT-11-iter2 | IP-11 iter 2 — Auth Wiring | 2026-05-26 | [UT-11 iter 2](../../../docs/implementation-phase/unit-tests/UT-11-frontend-layout-iter2.md) |

---

## Key Architectural Components

| Component | Type | Location | Description | Status |
|-----------|------|----------|-------------|--------|
| FastAPI App | Backend | `backend/app/main.py` | Main application entry point | ✅ Created |
| Config | Backend | `backend/app/config.py` | Pydantic settings | ✅ Created |
| Database | Backend | `backend/app/database.py` | SQLAlchemy async engine | ✅ Created |
| Alembic | Backend | `backend/alembic/` | Database migrations | ✅ Created |
| React App | Frontend | `frontend/src/App.tsx` | Frontend entry point | ✅ Created |
| API Client | Frontend | `frontend/src/lib/api.ts` | HTTP client wrapper | ✅ Created |
| SSE Client | Frontend | `frontend/src/lib/sse.ts` | EventSource wrapper | ✅ Created |
| Event Types | Frontend | `frontend/src/types/events.ts` | TypeScript types (placeholder) | ✅ Created |
| Domain Enums | Backend | `backend/app/domain/enums.py` | StopReason, QuestionType, OutputFormat, EventType, EvidencePolarity, SourceType | ✅ BRD-02 |
| Event Models | Backend | `backend/app/domain/events.py` | 19 Pydantic event classes + discriminated union + `EVENT_TYPE_MAP` + `FORKABLE_EVENTS` | ✅ BRD-02 |
| Run DTOs | Backend | `backend/app/domain/run.py` | `RunCreate`, `RunResponse`, `RunListItem`, `RunForkRequest` | ✅ BRD-02 |
| Confidence DTOs | Backend | `backend/app/domain/confidence.py` | `StructuralConfidence` (weighted score), `ConfidenceResult` | ✅ BRD-02 |
| Type Exporter | Scripts | `scripts/export_types.py` | Pydantic → TypeScript generator | ✅ BRD-02 |
| Event Types (TS) | Frontend | `frontend/src/types/events.ts` | Auto-generated enums + JSON schema | ✅ BRD-02 |
| ORM Models | Backend | `backend/app/models/{base,user,run,event}.py` | SQLAlchemy 2.0 async ORM | ✅ BRD-01 |
| Initial Migration | Backend | `backend/alembic/versions/001_initial_schema.py` | users + runs + events + enums | ✅ BRD-01 |
| `Source` Seam | Backend | `backend/app/seams/source.py` | `Protocol` + `SourceResult` + `SourceError` (plugin seam #1 of 3) | ✅ BRD-06 |
| Source Base | Backend | `backend/app/sources/base.py` | `BaseSource` mixin with content truncation helper | ✅ BRD-06 |
| Tavily Source | Backend | `backend/app/sources/tavily.py` | Web search via `tavily-python`, `search_depth="advanced"` | ✅ BRD-06 |
| Wikipedia Source | Backend | `backend/app/sources/wikipedia.py` | Sync client wrapped with `anyio.to_thread.run_sync` | ✅ BRD-06 |
| Source Registry | Backend | `backend/app/sources/registry.py` | `SourceRegistry` keyed by `SourceType`, module-level `get_source` | ✅ BRD-06 |
| Agent States | Backend | `backend/app/agent/states.py` | `AgentState` enum + `TRANSITIONS` map + `TERMINAL_STATES` (single source of truth for FSM edges) | ✅ BRD-07 |
| Run State | Backend | `backend/app/agent/run_state.py` | `RunState` Pydantic model (ephemeral) + `EvidenceItem` (in-memory mirror of `EvidenceAddedEvent`) | ✅ BRD-07 |
| Agent Orchestrator | Backend | `backend/app/agent/orchestrator.py` | `AgentOrchestrator` FSM driver — emits events via async callback, no persistence | ✅ BRD-07 |
| Agent Tasks | Backend | `backend/app/agent/tasks/{classify,plan,search,analyze,draft}.py` | LLM-backed steps: RF-06 classifier, RF-14 plan critic, search cascade, coverage analysis, synthesizer + judge + RF-15 disconfirmation | ✅ BRD-07 |
| Critique Output | Backend | `backend/app/llm/models.py::CritiqueOutput` | Pydantic structured output for plan critic step (additive to BRD-05 surface) | ✅ BRD-07 |

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
