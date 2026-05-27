# Implementation Plan: IP-16 — Output Format Renderers

**Plan ID:** IP-16  
**BRD Reference:** BRD-16 (Output Format Renderers)  
**Complexity:** M (Medium)  
**Profile:** quality_profiles.M (audit_f2 min_score=8/max_iter=1; review min_score=9/max_iter=3)  
**Created:** 2026-05-27  
**Author:** Orchestrator  
**Status:** Draft (pending F2 Auditor approval)

---

## 1. Scope

Implement the `OutputRenderer` plugin seam (RF-10) for the Novum backend and wire up the frontend display of rendered answers. Covers:

- Backend: `OutputRenderer` protocol + `ProseRenderer` + `StructuredRenderer` + `RendererRegistry` + `/api/formats` discovery endpoint
- Backend integration: orchestrator calls renderer at answer-stop time
- Frontend: `FormatSelector` molecule + `StructuredAnswer` organism + CenterPanel wiring to display answer from SSE `Stopped` event
- Unit tests for all new code (≥ 80% coverage)

Out of scope per BRD-16 §10: Table, Timeline, custom format templates.

---

## 2. RF Coverage

| RF | Requirement | Coverage by this plan |
|----|-------------|----------------------|
| RF-10 | Output format selection (Prose / Structured) | Complete — seam + renderers + frontend selector + answer display |

---

## 3. Pre-conditions

| Item | State |
|------|-------|
| `OutputFormat` enum in `backend/app/domain/enums.py` | ✅ Already exists (`prose` / `structured`) |
| `RunCreate.output_format` in `backend/app/domain/run.py` | ✅ Already exists |
| `StoppedEvent.answer_prose` in `backend/app/domain/events.py` | ✅ Already exists |
| `RunState.output_format` in `backend/app/agent/run_state.py` | ✅ Already exists |
| Frontend `OutputFormat` type in `frontend/src/types/events.ts` | ✅ Already exists |
| Frontend `QuestionForm` has format toggle (hardcoded) | ✅ Already exists |
| `backend/app/seams/output.py` | ❌ Missing — Task 1 |
| `backend/app/output/` package | ❌ Missing — Tasks 2–5 |
| `backend/app/routes/formats.py` | ❌ Missing — Task 6 |
| `frontend/src/components/molecules/FormatSelector.tsx` | ❌ Missing — Task 8 |
| `frontend/src/components/organisms/StructuredAnswer.tsx` | ❌ Missing — Task 9 |
| Answer display in CenterPanelView | ❌ Missing — Task 10 |

---

## 4. Task Breakdown

### Task 1 — Backend: OutputRenderer Seam Protocol
**File:** `backend/app/seams/output.py`  
**Effort:** 0.5 h  

Create the `OutputRenderer` protocol with:
- `RenderContext(BaseModel)` — question, answer_content, sources, confidence, stop_reason
- `RenderedOutput(BaseModel)` — format, content, metadata dict
- `OutputRenderer(Protocol)` — `format_name`, `display_name` properties + `render(context)` method

Follow the exact signature in BRD-16 §4.3. Add `@runtime_checkable`.

**Dependencies:** None  
**Tests:** Covered by Task 7

---

### Task 2 — Backend: ProseRenderer
**File:** `backend/app/output/prose.py`  
**Effort:** 0.5 h  

Implement `ProseRenderer`:
- Passes `answer_content` through unchanged
- Appends numbered sources list (`### Sources`) if `context.sources` is non-empty
- Returns `RenderedOutput(format="prose", content=..., metadata={word_count, source_count})`

**Dependencies:** Task 1

---

### Task 3 — Backend: StructuredRenderer
**File:** `backend/app/output/structured.py`  
**Effort:** 0.5 h  

Implement `StructuredRenderer`:
- Calls `_structure_content()` to convert prose to structured markdown (detects existing headers/bullets)
- Appends confidence section with `stop_reason` display text
- Appends sources section
- Returns `RenderedOutput(format="structured", content=..., metadata={sections, source_count})`

`_format_stop_reason()` maps **all 7 current `StopReason` enum values** to human-readable text.

> **Note (enum status 2026-05-27):** `honest_unanswerable`, `honest_contradiction`, and `honest_ambiguous` are scheduled for removal at WP-3 but remain active in the enum. Renderers MUST handle them to avoid fallback to raw enum strings in production. The mapping is kept exhaustive for safety.

```python
# Required mappings (architecture.md Rule 3 — stop_reason is enum, never free text)
mapping = {
    "judge_confirmed":      "✅ Verified",
    "honest_unanswerable": "⚠️ Insufficient Evidence",
    "honest_contradiction": "⚠️ Conflicting Sources",
    "honest_ambiguous":    "⚠️ Ambiguous Question",
    "stopped_by_budget":   "ℹ️ Research Limit Reached",
    "user_cancelled":      "🛑 Cancelled",
    "errored":             "❌ Error",
}
```

**Dependencies:** Task 1

---

### Task 4 — Backend: RendererRegistry
**File:** `backend/app/output/registry.py`  
**Effort:** 0.5 h  

Implement `RendererRegistry`:
- `__init__` calls `_register_defaults()` (Prose + Structured)
- `register(renderer)`, `get(format_name)`, `get_default()` (prose fallback), `list_formats()`
- Module-level singleton: `renderer_registry = RendererRegistry()`

**Dependencies:** Tasks 2, 3

---

### Task 5 — Backend: Package Init
**File:** `backend/app/output/__init__.py`  
**Effort:** 0.1 h  

Export `ProseRenderer`, `StructuredRenderer`, `renderer_registry`.

**Dependencies:** Tasks 2–4

---

### Task 6 — Backend: Formats Discovery Endpoint
**File:** `backend/app/routes/formats.py`  
**Effort:** 0.25 h  

```
GET /api/formats → {"formats": [{"name": "prose", "display": "Prose"}, ...]}
```

**File:** `backend/app/routes/__init__.py` (modification)  
Add `from app.routes.formats import router as formats_router` and include it in `api_router`.

**Dependencies:** Task 4

---

### Task 7 — Backend: Orchestrator Integration
**File:** `backend/app/agent/orchestrator.py` (modification)  
**Effort:** 0.5 h  

In `_stop()`, when `reason == StopReason.JUDGE_CONFIRMED` and `answer` is not None:
1. Build `sources: list[dict]` from `state.evidence` — deduplicate by `source_url`, map each `EvidenceItem` to `{"url": e.source_url, "title": e.source_title, "domain": ""}`. `state.draft_citations` is `list[str]` (raw URLs only from the LLM synthesizer) and does NOT contain titles — do NOT use it for RenderContext.sources.
2. Build `RenderContext(question=state.question, answer_content=answer, sources=sources, confidence=state.last_judge_confidence or 0.0, stop_reason=reason.value)`
3. Get renderer via `renderer_registry.get(self.state.output_format) or renderer_registry.get_default()`
4. Call `renderer.render(context)` → `rendered`
5. Use `rendered.content` instead of raw `answer` for `StoppedEvent.answer_prose`

**Pseudocode:**
```python
# Build sources from evidence (EvidenceItem has source_url, source_title)
seen: set[str] = set()
sources: list[dict] = []
for ev in self.state.evidence:
    if ev.source_url not in seen:
        seen.add(ev.source_url)
        sources.append({"url": ev.source_url, "title": ev.source_title, "domain": ""})
render_ctx = RenderContext(
    question=self.state.question,
    answer_content=answer,
    sources=sources,
    confidence=self.state.last_judge_confidence or 0.0,
    stop_reason=reason.value,
)
renderer = renderer_registry.get(self.state.output_format) or renderer_registry.get_default()
rendered = renderer.render(render_ctx)
answer = rendered.content  # use rendered content in StoppedEvent
```

**Important:** This is synchronous (renderers have no I/O). No async change needed.

**Dependencies:** Tasks 4, 5

---

### Task 8 — Frontend: FormatSelector Molecule
**File:** `frontend/src/components/molecules/FormatSelector.tsx`  
**Effort:** 0.5 h  

A standalone molecule that dynamically fetches formats from `/api/formats` using TanStack Query:
- Shows a loading skeleton while fetching
- Renders one button per format (active format highlighted with `var(--accent-*)` tokens per ui-prototype.md)
- `API_URL` from `@/lib/constants` (L-008 mandatory — **not** `import.meta.env.VITE_API_URL`)
- Uses `cn()` for conditional classes
- Exports `{ FormatSelector }` and adds to `frontend/src/components/molecules/index.ts`

**ESLint rule clarification:** The `frontend/eslint.config.js` `import/no-restricted-paths` rule only restricts imports of `useRun*` hooks in non-page layers (not all TanStack Query hooks). `useQuery` from `@tanstack/react-query` is permitted inside molecules. Therefore the BRD's design of placing `useQuery` inside `FormatSelector` (a molecule) is valid and does NOT violate any ESLint rule.

**AC covered:** AC-01

**Dependencies:** Task 6  
**Tests:** `FormatSelector.test.tsx` — MSW mock of `/api/formats`

---

### Task 9 — Frontend: StructuredAnswer Organism
**File:** `frontend/src/components/organisms/StructuredAnswer.tsx`  
**Effort:** 0.5 h  

Organism that renders the final answer markdown:
- Accepts `content: string`, `outputFormat: OutputFormat`, `metadata?: { sections?: number; source_count?: number }`
- Uses `ReactMarkdown` for rendering
- Shows meta bar (sections, sources) if metadata is present
- Exports from `frontend/src/components/organisms/index.ts`

**AC covered:** AC-02, AC-03

**Dependencies:** None (pure presentational)  
**Tests:** `StructuredAnswer.test.tsx`

---

### Task 10 — Frontend: Wire Answer Display into CenterPanel
**Files:** 
- `frontend/src/pages/CenterPanelContainer.tsx` (modification)
- `frontend/src/components/organisms/CenterPanelView.tsx` (modification)

**Effort:** 1.0 h  

**CenterPanelContainer changes:**
1. Extract `answerProse` and `answerMetadata` from the SSE `events` array — look for the `Stopped` event (`e.type === "Stopped"`) and read `e.answer_prose`, `e.answer_sections`
2. Pass `answerProse` and `outputFormat` (from `run.outputFormat`) down to `CenterPanelView`

**CenterPanelView changes:**
1. Accept new optional props `answerProse?: string | null` and `outputFormat?: OutputFormat`
2. When `isTerminal && run.stopReason === "judge_confirmed" && answerProse`:
   - Render `<StructuredAnswer content={answerProse} outputFormat={outputFormat ?? "prose"} />` above `TrustSummary`

**AC covered:** AC-02, AC-03, AC-04

**Dependencies:** Task 9  
**Tests:** Update `CenterPanelView.test.tsx` and `CenterPanelContainer.test.tsx`

---

### Task 11 — Backend: Unit Tests
**File:** `backend/tests/test_output_renderers.py`  
**Effort:** 1.0 h  

Test matrix:

| Test | Description |
|------|-------------|
| `test_prose_renderer_no_sources` | Prose with empty sources — content unchanged, no sources section |
| `test_prose_renderer_with_sources` | Sources appended with numbered list |
| `test_prose_metadata` | `word_count` and `source_count` correct |
| `test_structured_renderer_plain_text` | Converts to "Key Points" bullet format |
| `test_structured_renderer_existing_headers` | Passes through content with existing `##` unchanged |
| `test_structured_renderer_confidence_section` | Confidence + stop_reason section appended |
| `test_structured_format_name` | Returns `"structured"` |
| `test_prose_format_name` | Returns `"prose"` |
| `test_registry_list_formats` | Returns 2 formats |
| `test_registry_get_default` | Returns prose renderer |
| `test_registry_get_by_name` | Returns correct renderer |
| `test_registry_unknown_format` | Returns None |

Additional:
- `test_formats_endpoint` — GET /api/formats returns 200 + JSON list

---

### Task 12 — Frontend: Unit Tests
**Files:**
- `frontend/src/components/molecules/FormatSelector.test.tsx`
- `frontend/src/components/organisms/StructuredAnswer.test.tsx`

**Effort:** 0.75 h  

| Test | File | Description |
|------|------|-------------|
| renders loading skeleton | FormatSelector | Shows skeleton while formats loading |
| renders format buttons from API | FormatSelector | MSW returns [prose, structured]; 2 buttons appear |
| calls onChange on click | FormatSelector | onChange called with correct format name |
| active format is highlighted | FormatSelector | active button has distinguished class |
| renders markdown content | StructuredAnswer | content rendered via ReactMarkdown |
| shows metadata bar | StructuredAnswer | sections + source_count displayed |
| no metadata bar if missing | StructuredAnswer | metadata omitted → no bar |

---

## 5. File Modification Checklist

### New Files
- [ ] `backend/app/seams/output.py`
- [ ] `backend/app/output/__init__.py`
- [ ] `backend/app/output/prose.py`
- [ ] `backend/app/output/structured.py`
- [ ] `backend/app/output/registry.py`
- [ ] `backend/app/routes/formats.py`
- [ ] `backend/tests/test_output_renderers.py`
- [ ] `frontend/src/components/molecules/FormatSelector.tsx`
- [ ] `frontend/src/components/molecules/FormatSelector.test.tsx`
- [ ] `frontend/src/components/organisms/StructuredAnswer.tsx`
- [ ] `frontend/src/components/organisms/StructuredAnswer.test.tsx`

### Modified Files
- [ ] `backend/app/routes/__init__.py` — add formats router
- [ ] `backend/app/agent/orchestrator.py` — call renderer in `_stop()`
- [ ] `frontend/src/components/molecules/index.ts` — export FormatSelector
- [ ] `frontend/src/components/organisms/index.ts` — export StructuredAnswer
- [ ] `frontend/src/pages/CenterPanelContainer.tsx` — extract answer from SSE Stopped event
- [ ] `frontend/src/components/organisms/CenterPanelView.tsx` — accept + render answerProse

---

## 6. Dependencies & Order

```
Task 1 (seam protocol)
  → Task 2 (prose)  → Task 4 (registry) → Task 5 (init) → Task 6 (endpoint) → Task 7 (orchestrator integration)
  → Task 3 (structured) ↗                                                       ↓
                                                                             Task 11 (BE tests)

Task 8 (FormatSelector) — depends on Task 6 (backend endpoint running)
Task 9 (StructuredAnswer) — no dependency
Task 10 (wire CenterPanel) — depends on Task 9
Task 12 (FE tests) — depends on Tasks 8, 9
```

Recommended execution order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 11 → 8 → 9 → 10 → 12

---

## 7. Testing Requirements

| Scope | Tool | Target | Threshold |
|-------|------|--------|-----------|
| Backend renderers | pytest | `test_output_renderers.py` | 100% coverage on output/ |
| Backend endpoint | pytest | `test_output_renderers.py::test_formats_endpoint` | — |
| Frontend molecule | Vitest + RTL + MSW | `FormatSelector.test.tsx` | — |
| Frontend organism | Vitest + RTL | `StructuredAnswer.test.tsx` | — |
| Regression | pytest + vitest | All existing tests | Must pass (0 regressions) |

Coverage floor: ≥ 80% backend and frontend.

---

## 8. Architecture Constraints

| Constraint | Source | Application |
|------------|--------|-------------|
| Rendering is synchronous (no LLM) | BRD-16 §4.3 | `render()` is a regular `def`, not `async def` |
| Three plugin seams | architecture.md §Rule 1 | `output.py` follows same pattern as `source.py` / `stopping.py` |
| `stop_reason` is enum, never free text | architecture.md §Rule 3 | `_format_stop_reason` maps from enum values |
| Events are append-only | architecture.md §Rule 4 | `StoppedEvent.answer_prose` updated with rendered content; event not mutated after emit |
| API_URL mandatory | L-008 | `FormatSelector` imports from `@/lib/constants`, not `import.meta.env` |
| No axios | tech-stack.md | Use native `fetch` in `FormatSelector` |
| Atomic design seam | ESLint enforced | `FormatSelector` in molecules (no page-level hooks inside), `StructuredAnswer` in organisms |

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `FormatSelector` in `molecules/` violates ESLint "no data hooks in molecules" | ~~Medium~~ CLOSED | None | ESLint rule only restricts `useRun*` hooks, not `useQuery`. Verified in `eslint.config.js` §9.1 |
| `answer_prose` arrives as `null` in `StoppedEvent` for non-`judge_confirmed` stops | Low | Certain | Guard: only render `StructuredAnswer` when `stopReason === "judge_confirmed"` |
| Renderer called on empty draft_answer | Low | Low | Guard in orchestrator: `if answer:` before render |
| StructuredRenderer paragraph split produces empty bullets | Low | Low | Filter empty paragraphs in `_structure_content` |
| `draft_citations` is `list[str]` not `list[dict]` | Medium | RESOLVED | Task 7 uses `state.evidence` (EvidenceItem with source_url + source_title) instead of `draft_citations` |
| `honest_*` stop_reason values removed from enum | Low | RESOLVED | Values still in enum (WP-3 removal scheduled); `_format_stop_reason` handles all 7 for safety |

### 9.1 — ESLint Rule Verification (FormatSelector)

The `frontend/eslint.config.js` `import/no-restricted-paths` rule restricts only `./src/hooks/useRun*` from being imported into molecules/organisms/templates. `useQuery` from `@tanstack/react-query` is NOT restricted. Therefore:

- `FormatSelector.tsx` in `molecules/` CAN use `useQuery` directly.
- No workaround (props-only pattern, separate hook, container) is needed.
- Risk is **closed** — no ESLint violation.

---

## 10. Acceptance Criteria Traceability

| AC | Tasks Covering It |
|----|-----------------|
| AC-01: Format selector visible (Prose + Structured default) | Task 8, Task 10 |
| AC-02: Prose format renders narrative + sources | Tasks 2, 7, 9, 10 |
| AC-03: Structured format has Key Points + confidence + sources | Tasks 3, 7, 9, 10 |
| AC-04: Format stored with run (view later in same format) | Pre-condition (format already stored in DB via RunCreate); Task 10 reads `run.outputFormat` |
