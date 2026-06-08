<!--
  CLAUDE.md — Claude Code project instructions for Novum.
  Copilot users: this file is not read by GitHub Copilot. See .github/copilot-instructions.md.
-->

# Novum — Claude Code Instructions

> Self-directing research agent that gathers evidence, resolves contradictions, and decides when it knows enough.
> Current repo state: **active implementation** (backend + frontend exist). All decisions live as Markdown under `docs/`.

---

## 1. Project Context

@.github/memory-bank/shared/project-context.md

---

## 2. Authoritative Documentation

Read these BEFORE proposing any change. They are binding.

| Topic | File |
|---|---|
| Requirements (RF-01…RF-16+) | `docs/understanding-phase/requirement-understanding.md` |
| Stopping policy | `docs/understanding-phase/stopping-signal-analysis.md` |
| Confidence calculation | `docs/understanding-phase/confidence-calculation.md` |
| Data flow diagrams | `docs/understanding-phase/data-flows-and-diagrams.md` |
| **UI prototype (MANDATORY for frontend)** | `docs/understanding-phase/ui-prototype.md` |
| **UI design system (MANDATORY — Slate Aurora)** | `docs/understanding-phase/ui-design.md` |
| Architecture (8 rules — never violate) | `docs/technical-phase/architecture.md` |
| Tech stack | `docs/technical-phase/tech-stack.md` |
| **AI services (MANDATORY for backend LLM/search)** | `docs/technical-phase/ai-services.md` |
| Infrastructure | `docs/technical-phase/infrastructure.md` |

When asked to change a decision, update the originating doc — do not silently diverge from it in code.

---

## 3. Stack at a Glance

@.github/memory-bank/shared/architecture-summary.md

### Symbol Index (auto-generated)

@.github/memory-bank/indices/codemap.md

### Explicitly NOT in V1
Docker, Redis, vector DB, LangGraph/LangChain/LlamaIndex, Celery/RQ, WebSockets, Sentry/Datadog/Prometheus, Nginx (Caddy instead), cookies (use `localStorage`), Storybook, i18n, multiple LLM providers. Do not suggest them unless explicitly asked.

---

## 4. Architectural Rules (do not violate without asking)

1. **Three plugin seams:** `Source`, `StoppingSignal`, `OutputRenderer`. New extensions go behind these protocols (`backend/app/seams/`).
2. **Three not-seams (V1):** the planner, the storage layer, and the LLM provider are **deliberately not pluggable**. Do not introduce abstractions for them.
3. **`stop_reason` is an enum, never free text.** All 4 terminal states map to enum values (RF-02, collapsed from 7 in the WP-3 "always answer" refactor, commit `6ec6f39`): `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`. Ambiguous/sparse/contradictory cases no longer short-circuit to a separate "honest stop" — they route through `AnswerKind` selection (`direct`, `weighted`, `scenario`, `tradeoff`, `ethical_redirect`, `best_effort`) inside `judge_confirmed`.
4. **Events are append-only.** Resume and fork append; they never mutate or delete. 45 event types.
5. **Schema evolution = `extra="allow"` + optional keys only.** Adding keys never breaks. Renaming or removing requires an explicit migration.
6. **UI surfaces every trust guarantee.** Hide nothing from RF §6-quater (RF-13).
7. **Type contract FE↔BE:** Pydantic → JSON Schema → `frontend/src/types/events.ts` via `scripts/export_types.py`. Never hand-edit the generated types.
8. **Confidence formula:** `final_confidence = min(S, J)` where S = structural score, J = judge score (RF-12).

---

## 5. Code Conventions

### Language Policy
All code artifacts in **English**: identifiers, comments, docstrings, log messages, exception messages, hardcoded fallback strings, LLM system prompts, migration descriptions. Runtime chat replies follow the user's language (Spanish by default). UI microcopy is always English — only the LLM-generated answer follows user language.

### Python
- `ruff` + `pyright strict` clean. Use `match` statements for FSM transitions.
- Pydantic v2 models with discriminated unions for event types. `model_config = ConfigDict(extra="allow")` on event models.
- Async-first: every IO path is `async def`. Use `anyio.Lock` / `anyio.Event`, not bare `asyncio.Lock`.
- LLM calls go through `app/llm/client.py` (`llm.call`) — never call `litellm` or `httpx` directly from agent code.
- Retries via `tenacity` decorators with exponential backoff.
- **NEVER** embed iteration/ticket tags (`_ip##_`, `_pr##_`, `_wp##_`) in identifiers. See `naming-conventions.md`.

### TypeScript / React
- Strict TS. No `any`. Respect `noUncheckedIndexedAccess` — guard array/dict access.
- Atomic design: `atoms → molecules → organisms → templates → pages`. Only `pages/` fetches data.
- Co-locate component tests with **Vitest + Testing Library + jest-axe**. Mock APIs at the network with **MSW**.
- Use `cn()` (clsx + tailwind-merge) for conditional classes.
- **Slate Aurora is mandatory** for every screen. See `docs/understanding-phase/ui-design.md` §0.

### Tests
- Backend: `pytest` + `pytest-asyncio` + `pytest-postgresql`. Golden JSONL traces in `tests/fixtures/runs/`.
- Frontend: **Vitest** for everything. Register `afterEach(cleanup)` explicitly in `src/test/setup.ts` (L-033).
- Pre-commit: lint + typecheck (tests excluded).
- Coverage floor: ≥ 80% on touched files.

---

## 6. Environment Variables

Required:
```env
ANTHROPIC_API_KEY=<sk-ant-...>
TAVILY_API_KEY=<tvly-...>
```

Build-time (frontend):
```env
VITE_API_URL=https://<oracle-vm>.duckdns.org
VITE_DEMO_SLOWDOWN=1
```

Never commit secrets. `api_key_copilot.txt` and any `.env*` files must stay gitignored.

---

## 7. Agentic Development Architecture

This project uses an orchestrated agentic workflow. The formal definition lives in:
- **Workflow:** `@.github/workflow.yaml`
- **Workflow diagram:** `@.github/workflow.md`

### 7.1 Active Agents

@.github/agents/orchestrator.agent.md

---

@.github/agents/bsa.agent.md

---

@.github/agents/coder.agent.md

---

@.github/agents/reviewer.agent.md

---

@.github/agents/auditor.agent.md

---

@.github/agents/eval-engineer.agent.md

---

### 7.2 Skills

| Skill | Location |
|-------|----------|
| GitHub MCP | `@.github/prompts/skills/github-mcp/SKILL.md` |
| UX Frontend | `@.github/prompts/skills/ux-frontend/SKILL.md` |
| Database | `@.github/prompts/skills/database/SKILL.md` |
| Implementation Plan | `@.github/prompts/skills/implementation-plan/SKILL.md` |
| Audit BRD | `@.github/prompts/skills/audit-brd/SKILL.md` |
| Audit User Story | `@.github/prompts/skills/audit-user-story/SKILL.md` |
| Audit Implementation Plan | `@.github/prompts/skills/audit-implementation-plan/SKILL.md` |
| Unit Test Backend | `@.github/prompts/skills/unit-test-backend/SKILL.md` |
| Unit Test Frontend | `@.github/prompts/skills/unit-test-frontend/SKILL.md` |
| Eval Instrumentation | `@.github/prompts/skills/eval-instrumentation/SKILL.md` |
| Memory Protocol | `@.github/prompts/skills/memory-protocol/SKILL.md` |
| Update Documentation | `@.github/prompts/skills/update-docs/SKILL.md` |

---

### 7.3 Memory Protocol (MANDATORY for every agent role)

Before EVERY task, read:
1. `.github/memory-bank/shared/project-context.md`
2. `.github/memory-bank/indices/knowledge-base-index.md`
3. `.github/memory-bank/logs/lessons-learned.md`

After EVERY task, update:
1. `.github/memory-bank/logs/decisions-history.md`
2. `.github/memory-bank/logs/lessons-learned.md` (if new insights)
3. `.github/memory-bank/indices/knowledge-base-index.md` (if new artifacts)

---

### 7.4 Model Routing for Claude Code

When spawning subagents (using the `Agent` tool), map the workflow complexity tier to Claude Code model IDs:

| Tier | Claude Code model | Use for |
|------|------------------|---------|
| **fast** | `haiku` | Explore, BSA (M), Auditor (M), Reviewer (S) |
| **balanced** | `sonnet` | BSA (L), Auditor (L), Coder (all), Reviewer (M/L) |
| **deep** | `opus` | Escalation, deep architectural decisions |

Complexity × agent matrix (inherits from `workflow.yaml` `model_routing.matrix`):

| Agent | S | M | L |
|-------|---|---|---|
| Explore | haiku | haiku | haiku |
| BSA | skipped | haiku | sonnet |
| Auditor | skipped | haiku | sonnet |
| Coder | sonnet | sonnet | sonnet |
| Reviewer | haiku | sonnet | sonnet |
| EvalEngineer | skipped | sonnet | sonnet |

---

### 7.5 Workflow Entry Points (Claude Code usage)

Say any of the following to trigger the workflow:

| User phrase | Entry phase | What happens |
|------------|-------------|--------------|
| "Analyze requirement X" / "New feature: X" | F0.5 → F1 | Orchestrator triages, delegates to BSA |
| "Plan US-XX" / "Create implementation plan for…" | F0.5 → F2 | Orchestrator triages, creates plan directly |
| "Implement PLAN-US-XX" / "Code BRD-XX" | F0.5 → F3 | Orchestrator triages, delegates to Coder |
| "Review branch / PR / files in path" | F0.5 → F4 | Orchestrator triages, delegates to Reviewer |
| "Continue / resume US-XX" | F0.5 → last logged phase | Orchestrator reads memory bank, resumes |
| "/update-docs" / "Update docs for US-XX" | F5 (direct) | Orchestrator runs update-docs skill on the named task |

Triage (F0.5) **always runs first**. Output is always:
```yaml
triage:
  entry_phase: F1 | F2 | F3 | F4
  complexity:  S  | M  | L
  rationale:   "<1-2 lines>"
  override:    null | "<user-supplied reason>"
profile: quality_profiles[<level>]
models:  <resolved tier per agent>
```

---

### 7.6 Quality Gates (enforced by all agent roles)

| Gate | Threshold | Action |
|------|-----------|--------|
| Document Audit (F1 — BRD/US) | ≥ 9/10 (L), ≥ 8/10 (M) | Return to BSA; max 3 iters then F6 |
| Document Audit (F2 — Plan) | ≥ 9/10 (L), ≥ 8/10 (M) | Return to Orchestrator; max 3 iters then F6 |
| Eval Gate (F3.5) | PASS per hypothesis | Return to Coder; max 2 FAIL then F6 |
| Code Review (F4) | ≥ 9/10 (L/M), ≥ 8/10 (S) | Return to Coder; max 5 (L), 3 (M), 2 (S) iters |
| Test Coverage | ≥ 80% | Request additional tests |
| Lint + Typecheck | Clean | Block review submission |

---

### 7.7 Output Locations

| Artifact | Location |
|----------|----------|
| BRDs | `docs/implementation-phase/brds/` |
| User Stories | `docs/implementation-phase/user-stories/` |
| Implementation Plans | `docs/implementation-phase/implementation-plans/` |
| Audit Reports | `docs/implementation-phase/audits/` |
| Code Reviews | `docs/implementation-phase/reviews/` |
| Test Documentation | `docs/implementation-phase/unit-tests/` |
| Eval raw output | `eval_<tag>.txt` (repo root) |
| Eval scorecard | `compare_<tag>.{txt,json}` |
| Eval iteration history | `docs/evaluation/iteration-history-*.md` |
| Hypotheses | `docs/evaluation/hypotheses/IP-*.yaml` |

---

## 8. Naming Conventions

@.github/memory-bank/conventions/naming-conventions.md

---

## 9. Lessons Learned (Required reading before any task)

@.github/memory-bank/logs/lessons-learned.md

---

## 10. Reply Language

**Reply to the user in the same language he ased for**. All code, comments, docstrings, and log messages stay in English. UI microcopy is always English.
