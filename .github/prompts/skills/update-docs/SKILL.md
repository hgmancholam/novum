# Update Documentation Skill

## Description

Systematically identifies and updates stale documentation after a development task
completes. Covers two categories:

1. **Application docs** — `docs/` (requirements, architecture, implementation artifacts, eval)
2. **Agent/workflow docs** — `.github/agents/`, `.github/prompts/skills/`, `workflow.yaml`,
   `workflow.md`, `CLAUDE.md`, and the memory bank

Invoked automatically by the Orchestrator at **F5.S1** after implementation is approved.
Can also be called on demand via `/update-docs <task description>` in Claude Code,
or by any agent at the end of a task that produces doc-level changes.

---

## When to Use

| Trigger | Context |
|---------|---------|
| **F5.S1 — automatic** | Every approved implementation (Orchestrator calls at COMPLETE phase) |
| **`/update-docs <description>`** | On demand when docs lag behind recent changes |
| **After adding a skill or agent** | Ensure `workflow.yaml`, `CLAUDE.md`, `workflow.md` are all consistent |
| **After an eval hypothesis run** | Update `docs/evaluation/` iteration history and failure taxonomy |
| **After architectural decision** | Update `docs/technical-phase/architecture.md` + `architecture-summary.md` |

---

## Documentation Categories

### Category A — Application Docs (`docs/`)

| Path | Update when |
|------|-------------|
| `docs/understanding-phase/requirement-understanding.md` | RF-01…RF-16 changed; new requirement added |
| `docs/understanding-phase/stopping-signal-analysis.md` | Stopping policy changed; new `stop_reason` enum value |
| `docs/understanding-phase/confidence-calculation.md` | Confidence formula (`min(S,J)`) or thresholds changed |
| `docs/understanding-phase/ui-prototype.md` | UI state machine, microcopy, or panel states changed |
| `docs/understanding-phase/ui-design.md` | Slate Aurora patterns or design tokens changed |
| `docs/understanding-phase/data-flows-and-diagrams.md` | Data flow or event schema changed |
| `docs/technical-phase/architecture.md` | Architecture rules changed; new seam added |
| `docs/technical-phase/tech-stack.md` | New dependency added; existing tool replaced |
| `docs/technical-phase/ai-services.md` | LLM provider, model assignment, or search source changed |
| `docs/technical-phase/infrastructure.md` | Deployment, hosting, or infrastructure changed |
| `docs/implementation-phase/brds/BRD-XX.md` | Status changed (Draft → Approved → Implemented) |
| `docs/implementation-phase/user-stories/US-XX.md` | Status changed or Definition of Done completed |
| `docs/implementation-phase/implementation-plans/PLAN-US-XX.md` | Plan status updated |
| `docs/evaluation/iteration-history-*.md` | Eval iteration completed (EvalEngineer appends row) |
| `docs/evaluation/failure-taxonomy.md` | New failure category identified |
| `docs/evaluation/hypotheses/IP-XX.yaml` | Hypothesis outcome recorded |

### Category B — Agent/Workflow Docs (`.github/`)

| Path | Update when |
|------|-------------|
| `.github/agents/<name>.agent.md` | Agent responsibilities, steps, or outputs changed |
| `.github/prompts/skills/<name>/SKILL.md` | Skill behavior, triggers, or outputs changed |
| `.github/workflow.yaml` | New phase, step, skill, or agent added |
| `.github/workflow.md` | Diagram or step table becomes stale after yaml changes |
| `CLAUDE.md` | Skills table, entry points, model routing, or stack summary changed |

### Category C — Memory Bank (`.github/memory-bank/`) — always update

| Path | Update policy |
|------|---------------|
| `logs/decisions-history.md` | **Always** — append a new `## D-{N}` decision record |
| `logs/lessons-learned.md` | Append `## L-{N}` only when a non-obvious pattern was discovered |
| `indices/knowledge-base-index.md` | Add rows for every new artifact created |
| `shared/project-context.md` | Update §2 "Recent Changes" table and §7 "Active Decisions" |

---

## Update Protocol

### Step 1 — Context gathering (read first)

```
1. Read .github/memory-bank/logs/decisions-history.md (last 3 entries)
2. Read .github/memory-bank/indices/knowledge-base-index.md
3. Identify the completed task from the Orchestrator's context or from the
   skill's $ARGUMENTS (Claude Code) / prompt preamble (Copilot)
4. List all files modified during the task (git diff, or Orchestrator context)
```

### Step 2 — Determine stale docs

For each file touched by the task, map to documentation using the tables above.
A doc is stale when one or more of the following is true:
- A code path it describes was changed
- A threshold, enum value, or metric it defines was modified
- A phase, step, or agent flow was altered
- An artifact it tracks changed status
- A new artifact was created that the doc doesn't yet reference

### Step 3 — Update in priority order

**Priority 1 — Generated indices (always, no exceptions)**
- If any `.py`, `.ts`, or `.tsx` file was created or modified during the task, run:
  ```bash
  python scripts/gen_codemap.py
  ```
  This regenerates `.github/memory-bank/indices/codemap.md` (the symbol index used by
  Claude Code and Copilot). Skip only if the task touched exclusively non-code files
  (docs, config, migrations).

**Priority 2 — Memory bank (always, no exceptions)**
- Append a new `## D-{N}` entry to `decisions-history.md` (D-{N} = next consecutive ID)
- Append `## L-{N}` entry to `lessons-learned.md` ONLY if a non-obvious pattern emerged
- Add new artifact rows to `knowledge-base-index.md` for each file created
- Update `project-context.md` §2 "Recent Changes" table (add row; keep last 5)

**Priority 3 — Implementation-phase status updates**
- Update `Status:` field in affected BRDs / user stories / plans to `Implemented` | `Approved`
- Tick off completed items in user story `Definition of Done` checklists

**Priority 4 — Technical facts**
- Update `docs/technical-phase/` docs (architecture, tech stack, AI services, infrastructure)
- Update `docs/understanding-phase/` docs (requirements, stopping policy, confidence, UI spec)
- Keep all RF cross-references (RF-01…RF-16) accurate — never invent or remove RF IDs

**Priority 5 — Agent/workflow meta-docs**
- Update agent `.md` files if their step flow, skills used, or outputs changed
- Update `workflow.yaml` skills section if a skill was added/removed
- Update `CLAUDE.md` §7.2 skills table and §7.5 entry points when stale
- Update `workflow.md` step tables and Mermaid diagrams when yaml changed

### In-place edit rules (non-negotiable)

- **In-place only** — never create `*-v2`, `*-revised`, or dated copies of existing docs
- **Append-only for logs** — never delete or overwrite existing entries in `decisions-history.md`,
  `lessons-learned.md`, or evaluation iteration history
- **Preserve trace IDs** — never renumber or rename RF-XX, BRD-XX, US-XX, PLAN-XX, D-{N}, L-{N}
- **English only** — all doc content must be in English (project language policy)
- **Never modify** `.github/copilot-instructions.md` — it is a frozen Copilot system prompt

### Step 4 — Validate completeness

Before declaring done, verify all boxes below:

- [ ] `codemap.md` regenerated if any `.py` / `.ts` / `.tsx` files were touched
- [ ] `decisions-history.md` has a new `## D-{N}` entry dated today
- [ ] `project-context.md` §2 "Recent Changes" table includes this task
- [ ] All new artifacts appear in `knowledge-base-index.md`
- [ ] BRD / US / Plan `Status:` fields match the actual state (not still `Draft` after approval)
- [ ] `workflow.yaml` skills section is consistent with files under `.github/prompts/skills/`
- [ ] `CLAUDE.md` §7.2 skills table matches the `workflow.yaml` skills section
- [ ] No doc section contradicts another doc on the same fact; if conflict found, resolve and note in `decisions-history.md`

### Step 5 — GitHub sync (if MCP available)

If the `github-mcp` skill (GitHub MCP) is active, push all updated doc files together:

```
commit message: "docs(<scope>): update docs after <task-description>"
files: list of all .md / .yaml files modified in Steps 1–4
```

**Never include** in the commit: `backend/.env`, `.env.*`, `*.pem`, `api_key*.txt`,
`.vscode/mcp.json`, or any file containing secrets or credentials.

---

## Output

Emit this block when the skill completes:

```yaml
update_docs_result:
  task: "<what was completed>"
  codemap_regenerated: true | false   # true if any .py/.ts/.tsx files were modified
  memory_bank_updated:
    decisions_history: true | false
    lessons_learned:   true | false   # true only if a new lesson was added
    knowledge_base_index: true | false
    project_context:   true | false
  application_docs_updated:
    - "<docs/... path>"               # list each updated file
  workflow_docs_updated:
    - "<.github/... path>"            # list each updated file; omit if none
  github_sync: true | false
  validation_passed: true | false
  notes: "<deferred updates, discrepancies found, or 'none'>"
```

---

## Constraints

| Constraint | Rule |
|------------|------|
| Frozen file | Never modify `.github/copilot-instructions.md` |
| Secret hygiene | Never write API keys, tokens, or passwords into any doc |
| Scope discipline | Only update docs that are genuinely stale — do not touch unrelated files |
| Single source of truth | When a doc contradicts the code, update the doc; note discrepancy in `decisions-history.md` |
| No new versioned copies | All updates are in-place edits to existing files |
| Append-only logs | Decisions history, lessons learned, and eval iteration history are append-only |
