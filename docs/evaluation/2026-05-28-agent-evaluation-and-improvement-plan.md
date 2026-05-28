# Evaluation Report & Improvement Plan — Novum Research Agent

**Date:** 2026-05-28
**Evaluator:** Automated audit (Copilot, expert evaluator role)
**Sample:** 8 production runs executed against the scenario battery in
[docs/q-for-testing.md](../q-for-testing.md).
**Evidence source:** Live Postgres event log via MCP (`runs` + `events` tables).
**Code source-of-truth:** `backend/app/` (not the documentation).

---

## 0. Executive Summary

| Metric | Value |
|---|---|
| Runs analysed | 8 / 8 |
| Average wall-clock | 106 s |
| Average events per run | 31 |
| `judge_confirmed` terminations | 6 |
| `stopped_by_budget` terminations | 2 (Q4 fasting, Q7 memory) |
| Distinct `answer_kind` values produced | 4 (`direct`, `weighted`, `tradeoff`, `scenario`, plus 2 NULL) |
| Runs whose payload populated the kind-specific shape (`candidates` / `scenarios` / `criteria`) | **0 / 6** |
| Total identified gaps | **17** (5 critical, 7 high, 5 medium) |
| Single most impactful fix | **Persist & render the synthesizer's structured payload** (`candidates`, `scenarios`, `criteria`) — currently dropped on the floor |
| Most problematic area | **Output formatting**: every answer is rendered as flat prose paragraphs regardless of `answer_kind` |

The agent's **research mechanics work** (classifier routes correctly in 7/8, ReAct fires in DEEP, sources are heterogeneous, citations are present, lanes terminate honestly). The **rendering and depth contract is broken**: the structured payload the synthesizer is asked to produce is discarded between `tasks/draft.py` and the `Stopped` event, and the DEEP lane uses the FAST 2-sentence prompt for its final answer. That is why every output, regardless of question depth, looks the same.

---

## 1. Run Inventory (raw evidence)

| # | Question | Lane | `answer_kind` | Stop reason | Confidence | Dur (s) | Events |
|---|---|---|---|---|---|---|---|
| 1 | Capital of Japan? | **fast → escalated to standard** | `direct` | judge_confirmed | 0.92 | 51 | 18 |
| 2 | PostgreSQL vs MongoDB for small SaaS | standard | `weighted` | judge_confirmed | 0.72 | 80 | 23 |
| 3 | Best programming language? | standard | `tradeoff` | judge_confirmed | 0.78 | 97 | 29 |
| 4 | Is intermittent fasting healthy? | deep | **null** | stopped_by_budget | **null → UI shows 0 %** | 158 | 41 |
| 5 | Long-term risks of AI-generated code | standard | `scenario` | judge_confirmed | 0.62 | 144 | 34 |
| 6 | EDA vs synchronous microservices for high-scale AI | standard | `weighted` | judge_confirmed | 0.72 | 137 | 28 |
| 7 | Most promising approach for long-term agent memory | deep | **null** | stopped_by_budget | **null → UI shows 0 %** | 84 | 53 |
| 8 | Will AI replace mid-level engineers in 10 years? | standard | `scenario` | judge_confirmed | 0.72 | 154 | 34 |

Notable absences across **all 8 runs**: zero `MetaStopVerdict`, zero `AdversarialObjectionsGenerated`, zero `PlanGapsDetected`, zero `NoProgressDetected`, zero `EchoChamberDetected`, zero `DraftSynthesized`. The structured renderer's `answer_structured_data.blocks` only contains `paragraph` blocks — never `KeyValueBlock`, `StepsBlock`, `MarkdownBlock` with tables, or `KeyPointsBlock`. The synthesizer's `candidates`/`scenarios`/`criteria` payloads are absent from the persisted `Stopped` event in every single run.

---

## 2. Current Research Model (verified against source code)

| Aspect | Where it lives | What it does today |
|---|---|---|
| Classifier | `backend/app/agent/tasks/classify.py` | One LLM call → emits `QuestionType`, `complexity_hint`, `temporal_sensitivity`. Working. |
| Lane router | `backend/app/agent/lane_router.py::select_lane` | Pure function. FAST iff `trivial + factual/definitional + static + !ambiguity`. DEEP iff `complexity=deep` OR `(causal|state_of_art) + !trivial`. STANDARD otherwise. |
| Answer-kind selector | `backend/app/agent/tasks/select_answer_kind.py` | Maps `QuestionType` → `AnswerKind`. `SUBJECTIVE_OPINION → TRADEOFF` (never `BEST_EFFORT`, even when ambiguity fires). |
| FAST lane | `backend/app/agent/lanes/fast.py` | One parallel search, synthesise with `FAST_SYNTH_PROMPT` (1-2 sentences), mini-judge. Escalates to STANDARD if `S_effective < 0.85` OR `mini_judge.ok == False`. `S_effective = min(1.0, n_evidence / 6)` so 6 results are required for floor. |
| STANDARD lane | `backend/app/agent/orchestrator.py` + `tasks/draft.py` | Plan → sub-claims → parallel search → analyse → `build_synthesizer_prompt(answer_kind=…)` → judge. Re-decomposition and deep-fetch code paths exist but **never fired in the 8 runs**. |
| DEEP lane | `backend/app/agent/lanes/deep.py` | Hypotheses → ReAct loop (max 8 steps) → synthesise. **Uses `FAST_SYNTH_PROMPT` for the final answer** (lines 256 & 308), so DEEP answers are also instructed to be "2-3 sentences". |
| Synthesizer prompt builder | `backend/app/llm/prompts.py::build_synthesizer_prompt` | Has six kind-specific templates (DIRECT, WEIGHTED, SCENARIO, TRADEOFF, ETHICAL_REDIRECT, BEST_EFFORT) that **require** populating `candidates`/`scenarios`/`criteria`. Called only from STANDARD lane. |
| Synthesizer model | `Pydantic SynthesizedAnswer` (`backend/app/llm/models.py`) | Validates that the kind-specific field is populated. **However…** see §3.1 below. |
| Renderer | `backend/app/output/structured.py::StructuredRenderer.build_data` | Receives only `answer_content: str` (the `prose` field). Guesses structure from the text. Has **no access** to `SynthesizedAnswer.candidates`, `scenarios`, `criteria`. |
| Meta-judge (BRD-26 VoC + Adversarial Completeness) | **Not implemented.** Grep for `MetaStopVerdict`, `VoCVerdict`, `meta_judge`, `ValueOfContinuation` returns zero matches in `backend/app/`. |
| `stop_rationale` builder | `backend/app/agent/orchestrator.py` lines 729-790 | DEEP path branches on `state.selected_lane == Lane.DEEP`. Q4 (fasting) had 6 ReAct observations but the persisted rationale said `"Reached search limit (0 rounds)"` → suggests `selected_lane` is not set correctly at stop time for at least one DEEP path. |

---

## 3. Per-Run Evaluation

The scoring rubric: Severity 1 = cosmetic, 5 = breaks the contract with the user.

### Run 1 — "What is the capital of Japan?"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Speed (RF: stop quickly) | Single source, < 15 s | 51 s, 3 ToolCalled, FAST → escalated to STANDARD | Mini-judge rejected a trivially-correct answer → wasted ×3 time | **4** |
| Format | Short factual paragraph | One paragraph "La capital de Japón es Tokio…" + 4 sources | OK | 1 |
| Confidence | ≥ 0.9 | 0.92 | OK | — |

**Root cause of the escalation:** `_FAST_S_THRESHOLD = 0.85` combined with `S = min(1, n/6)` demands ≥ 5.1 results from a single combined search. When Wikipedia + Tavily returned 6 items the floor was barely met; the mini-judge then independently rejected (likely citation-format strictness) and triggered the STANDARD pipeline for a question every encyclopedia answers in one word.

### Run 2 — "PostgreSQL vs MongoDB for small SaaS"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Format | Comparison table or side-by-side criteria (scenario expects criteria/notes) | `answer_kind: weighted` + **one paragraph**; `candidates: null` | The synthesizer's `candidates` payload is missing — there is no per-option score table | **5** |
| Tradeoff coverage | Multi-dimensional (consistency, schema flex, ops, cost, ACID) | Mentions ACID, multi-tenant, cost, schema flexibility — content is there but inside prose, not structured | Content OK, container wrong | 4 |
| Context dependency | Should say "depends on workload" up-front | "PostgreSQL es la opción superior para la mayoría…" — assertive verdict, mentions MongoDB strengths last | Mild — answer favours one side too strongly | 2 |

### Run 3 — "What is the best programming language?"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Ambiguity flagging | Lead with "the question is ambiguous because…" | `AmbiguityDetected` event fires, but the answer launches into a ranked comparison (Python / JS / C++) | Ambiguity is detected by the resolver but discarded by `select_answer_kind` (subjective_opinion → TRADEOFF, never BEST_EFFORT) | **5** |
| Multi-dimensional evaluation | Performance, productivity, ecosystem, learning curve, scalability | Mentioned in prose; no structured criteria table | `criteria: null` despite `answer_kind: tradeoff` | **5** |
| Avoid absolute answers | No single "best" | Says "Python domina… JavaScript es insustituible… C/C++ lideran" — closer to a ranked top-3 than ambiguity acknowledgement | 3 |

### Run 4 — "Is intermittent fasting healthy?"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Contradiction detection | Explicit contradictions between studies | Single nuanced paragraph; `contradictions_detected` not surfaced; no `Contradiction*` events | The judge ran 0 times (no `JudgeRuled` event in DEEP lane on this run); ReAct went 6 steps → budget | **4** |
| Stop transparency | "We stopped because…" honest rationale | `stop_rationale.summary = "Reached search limit (0 rounds)"` — but the lane is DEEP and ran 6 ReAct steps | **Bug**: DEEP lane reports wrong budget signal | **5** |
| Confidence display | A best-effort confidence or "not measured" | `confidence: null` → UI shows "**0 %**" with "Research Limit Reached" badge → looks like a failure | **5** |
| Format | Conditional / cohort-based recommendation | Prose-only, no per-population breakdown | Missed an opportunity to structure | 3 |

### Run 5 — "Long-term risks of AI-generated code in enterprise systems"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Separate evidence vs speculation | Explicit distinction | Quotes specific numbers ("62 %", "20 %", "~35 %") with citations — solid | OK | 1 |
| Format for `scenario` | Multiple scenarios with probability bands & drivers | `answer_kind: scenario` + **3 plain paragraphs**, `scenarios: null` | **No scenario branches rendered** | **5** |
| Acknowledge gaps | Long-term data is limited | Not stated; reads as confident | Missing "long-term evidence is still emerging" | 3 |
| Confidence | Should be moderate (0.5-0.7) given sparse long-term data | 0.62 | OK | — |

### Run 6 — "EDA vs synchronous microservices for high-scale AI"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Multi-factor evaluation | Scalability + latency + reliability + ops + observability + cost + team maturity | Mentions scalability, latency, ops complexity, observability; misses cost + team maturity explicitly | Partial coverage | 3 |
| Non-binary answer | "Depends on workload", possibly hybrid | "EDA es la opción claramente dominante" + 1 sentence on hybrid at the end | **Binary in tone**, violates scenario's "answer should NOT be binary" | **4** |
| Format | Per-factor matrix or weighted candidates | `answer_kind: weighted` + one paragraph, `candidates: null` | Same kind-payload bug as Run 2 | **5** |

### Run 7 — "Most promising approach for long-term memory in autonomous AI agents"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Compare vector / graph / episodic / hybrid | Side-by-side comparison | Mentions hierarchical, RAG, vector DB, graph — but in 2 paragraphs only | Comparison flattened into prose | **4** |
| Detect unresolved problems | List of open research questions | Not surfaced | Missing | 3 |
| Dynamic stopping decision | Should be defendable | Stopped at `max_react_steps=8` with `confidence: null` | Hit the hard cap, no meta-judge to negotiate | **4** |
| Format | DEEP question → richest output expected | **2 short paragraphs** — same length as the trivial Q1 answer | DEEP lane uses `FAST_SYNTH_PROMPT` (2-3 sentences) — **structural bug** | **5** |
| Confidence display | Best-effort score | UI shows "**0 %**" | Same as Run 4 | **5** |

### Run 8 — "Will AI replace mid-level engineers in 10 years?"

| Criterion | Expected | Obtained | Gap | Sev |
|---|---|---|---|---|
| Multi-domain synthesis | Tech + economics + regulation + history of displacement | Tech + economics + some history; regulation barely mentioned | Decent breadth | 2 |
| Multiple scenarios | At least 2 (replace / augment / hybrid) with explicit probabilities | One main scenario in 3 paragraphs; `scenarios: null` | **No scenario branches rendered** | **5** |
| Explicit uncertainty | Confidence + assumptions | Confidence shown (72 %), assumptions implicit | Partial | 3 |
| Contradictions between experts | E.g. Zuckerberg vs Goldman vs BCG | Mentions Zuck "espera tener IA…" alongside Goldman/BCG — does not flag the tension | Should call it a contradiction | 3 |

---

## 4. Aggregated Gap Map

| # | Gap | Runs affected | Severity |
|---|---|---|---|
| G1 | Kind-specific payload (`candidates`, `scenarios`, `criteria`) is **dropped between `tasks/draft.py` and the `Stopped` event** | 2, 3, 5, 6, 8 | **5** |
| G2 | `StructuredRenderer.build_data` only sees `answer_content` string; **cannot render kind-specific blocks** | 2, 3, 5, 6, 8 | **5** |
| G3 | **DEEP lane uses `FAST_SYNTH_PROMPT` (1-2 sentence)** for its final draft | 4, 7 | **5** |
| G4 | `stop_rationale` for DEEP-with-budget reports `"search limit (0 rounds)"` instead of `"ReAct step limit"` | 4 | **5** |
| G5 | `stopped_by_budget` confidence rendered as **"0 %"** instead of "not measured" / best-effort score | 4, 7 | **5** |
| G6 | `select_answer_kind` ignores `ambiguity_detected` — `SUBJECTIVE_OPINION` always → `TRADEOFF`, never `BEST_EFFORT` | 3 | 4 |
| G7 | FAST lane escalates trivial factual questions to STANDARD due to strict mini-judge | 1 | 4 |
| G8 | Meta-judge (BRD-26 VoC + Adversarial Completeness) **does not exist in code** | all DEEP + borderline STANDARD | 4 |
| G9 | `PlanGapsDetected`, `NoProgressDetected`, `EchoChamberDetected` never fire — thresholds too lax or paths not wired | 5, 6, 8 | 3 |
| G10 | Contradictions between sources/experts are detected by judge but not surfaced as a visible bullet in prose | 4, 8 | 3 |
| G11 | `weighted` answers come out **assertive ("X es la opción superior")** without surfacing the context-dependency clause | 2, 6 | 3 |
| G12 | `scenario` answers do not list explicit assumptions, drivers, or probability bands in the prose | 5, 8 | 3 |
| G13 | No `DraftSynthesized` event persisted (only `Stopped` carries the answer) — breaks the "every step is an event" guarantee | all | 2 |
| G14 | Total ReAct exploration in DEEP capped at 8 steps with no negotiation — too rigid for genuinely hard questions | 4, 7 | 2 |
| G15 | DEEP lane never invokes the kind-specific synth prompt → it has no `answer_kind` at all (`null` in `Stopped`) | 4, 7 | 4 |
| G16 | The `_FAST_S_THRESHOLD = 0.85` proxy is `min(1, n_evidence/6)` — coupling threshold to a count is brittle | 1 | 3 |
| G17 | "Best programming language" runs the full STANDARD pipeline (97 s) when an honest "this is ambiguous because…" reply should be < 20 s | 3 | 3 |

---

# PLAN DE MEJORA: Agente de Investigación AI

## RESUMEN EJECUTIVO

- **Gaps identificados:** 17 (5 críticos / 7 altos / 5 medios)
- **Área más problemática:** Formato y estructura del output (5 gaps críticos)
- **Mejora de mayor impacto / menor costo:** **Á1.1** — propagar `candidates`/`scenarios`/`criteria` desde `SynthesizedAnswer` hasta el `Stopped` event y consumirlos en `StructuredRenderer.build_data`. Una sola PR cierra G1+G2 y transforma 5/8 outputs.
- **Bug de honestidad más urgente:** **Á2.1** — corregir `stop_rationale` y `confidence` para `stopped_by_budget` en DEEP (G4+G5). Hoy el usuario ve "0 % — Research Limit Reached" cuando el agente sí produjo una respuesta defendible.

---

## ÁREA 1 — Formato estructurado (kind-specific payloads)

### Problemas identificados

| Run # | Escenario | Problema específico | Severidad | Evidencia |
|-------|-----------|---------------------|-----------|-----------|
| 2 | PostgreSQL vs MongoDB | `answer_kind: weighted` pero `answer_structured_data.blocks` solo tiene un `paragraph` | 5 | `Stopped.answer_structured_data` = `{blocks: [{type: "paragraph", text: "..."}]}` |
| 3 | Best programming language | `answer_kind: tradeoff` sin `criteria[]` ni tabla | 5 | mismo patrón |
| 5 | AI-generated code risks | `answer_kind: scenario` sin `scenarios[]` ni probability bands | 5 | mismo patrón |
| 6 | EDA vs microservices | `weighted` sin tabla de candidatos | 5 | mismo patrón |
| 8 | Replace mid-level engineers | `scenario` sin ramas | 5 | mismo patrón |

### Causa raíz

`build_synthesizer_prompt` (`backend/app/llm/prompts.py`) **instruye** al LLM a producir un `SynthesizedAnswer` con los campos `candidates`/`scenarios`/`criteria` poblados según el `AnswerKind`, y el `model_validator` los **valida**. Pero en [backend/app/agent/tasks/draft.py](../../backend/app/agent/tasks/draft.py#L228) sólo se persiste `result.prose`:

```python
# Success — populate state and return
state.draft_answer = result.prose          # ← solo el texto
state.draft_citations = list(result.citations)
state.draft_sections = [ ... ]              # parsed from prose, no payload
```

Aguas abajo, [orchestrator.py::_stop](../../backend/app/agent/orchestrator.py#L686) construye el `RenderContext` con `answer_content=self.state.draft_answer` (un string). El `StructuredRenderer.build_data` (líneas 70-130 de structured.py) sólo conoce ese string y adivina la estructura con regex de markdown. Resultado: el JSON tipado que el LLM entregó se descarta y la UI sólo recibe párrafos.

### Mejoras específicas

#### Mejora 1.1 — Persistir el `SynthesizedAnswer` completo en `RunState`

- **Qué cambiar:** añadir un campo `state.draft_payload: SynthesizedAnswer | None` (no solo `draft_answer: str`).
- **Dónde:** [backend/app/agent/run_state.py](../../backend/app/agent/run_state.py) y [backend/app/agent/tasks/draft.py](../../backend/app/agent/tasks/draft.py) (la asignación de `state.draft_answer = result.prose`).
- **Snippet actual** (draft.py:228):
  ```python
  state.draft_answer = result.prose
  state.draft_citations = list(result.citations)
  ```
- **Snippet propuesto:**
  ```python
  state.draft_answer = result.prose
  state.draft_payload = result   # full SynthesizedAnswer with kind-specific fields
  state.draft_citations = list(result.citations)
  ```

#### Mejora 1.2 — Pasar el payload tipado al `RenderContext`

- **Qué cambiar:** extender `RenderContext` (`backend/app/seams/output.py`) con un campo opcional `synth_payload: SynthesizedAnswer | None = None`.
- **Dónde:** definición del dataclass + el sitio donde se construye en `orchestrator.py::_stop` (~línea 686).
- **Snippet propuesto:** en `_stop`:
  ```python
  render_ctx = RenderContext(
      question=self.state.question,
      answer_content=answer,
      sources=sources,
      confidence=self.state.last_judge_confidence or 0.0,
      stop_reason=reason.value,
      synth_payload=self.state.draft_payload,
  )
  ```

#### Mejora 1.3 — Renderizar bloques tipados según `AnswerKind`

- **Qué cambiar:** en `StructuredRenderer.build_data`, **antes** del fallback de regex, consumir `synth_payload`:
  - `AnswerKind.WEIGHTED` → emitir un `KeyValueBlock` (o nuevo `WeightedTableBlock`) con `label`, `score`, `rationale` por cada `candidate`.
  - `AnswerKind.SCENARIO` → emitir un `KeyPointsBlock` con `label (probability_band)` + `summary` por cada `scenario`, más un sub-bloque de `drivers`.
  - `AnswerKind.TRADEOFF` → emitir un `KeyValueBlock` con `name`, `weight`, `notes`.
  - `AnswerKind.BEST_EFFORT` → mostrar `interpretation` + `alternative_interpretations` como un bloque destacado **al inicio**.
- **Dónde:** [backend/app/output/structured.py](../../backend/app/output/structured.py) método `build_data` (líneas 80-130). Insertar nuevo bloque condicional entre la línea "if not text" y el procesamiento de mermaid.
- **Snippet propuesto:**
  ```python
  def build_data(self, context: RenderContext) -> StructuredAnswerData:
      text = (context.answer_content or "").strip()
      summary = self._extract_summary(text)
      blocks: list[StructuredBlock] = []

      # NEW: render the kind-specific payload first
      payload = getattr(context, "synth_payload", None)
      if payload is not None and payload.answer_kind is not None:
          blocks.extend(self._render_kind_blocks(payload))

      # Then the prose follows as before
      ...
  ```
- **Cobertura:** definir bloques tipados nuevos en `backend/app/domain/structured.py` (`WeightedTableBlock`, `ScenarioBlock`, `TradeoffMatrixBlock`) y exportarlos por `JSON Schema` para que `scripts/export_types.py` los regenere en `frontend/src/types/events.ts`.

#### Mejora 1.4 — Forzar el contrato kind-specific en el prompt (defensa en profundidad)

El validador Pydantic ya rechaza un `weighted` sin `candidates`. Pero los runs sugieren que el LLM lo está cumpliendo (no hay `LLMContractError` ni reintentos visibles) — el problema es que el payload **no se guarda**. Tras 1.1-1.3, añadir un test de integración:

- **Dónde:** `backend/tests/test_agent_output_payload_persistence.py` (nuevo).
- **Qué:** ejecutar un mock de STANDARD con `question_type=COMPARATIVE`, validar que el `Stopped` event persiste `answer_structured_data.blocks[0].type in {"weighted_table", "key_value"}`.

**Esfuerzo estimado:** mediano. **Impacto:** transforma 5/8 outputs.

---

## ÁREA 2 — Stopping honesto y rationale correcto

### Problemas identificados

| Run # | Escenario | Problema específico | Severidad | Evidencia |
|-------|-----------|---------------------|-----------|-----------|
| 4 | Intermittent fasting | `stop_rationale.summary = "Reached search limit (0 rounds)"` en un run DEEP con 6 ReAct steps | 5 | `Stopped.stop_rationale` literal en BD |
| 4, 7 | fasting + memory | UI muestra **"0 %"** y badge `Research Limit Reached`, cuando hay respuesta defendible | 5 | `confidence: null` en `Stopped.stop_rationale` |

### Causa raíz

`orchestrator.py::_stop` (líneas 747-770) discrimina la rama DEEP con `if self.state.selected_lane == Lane.DEEP`. Para Run 4 ese flag no estaba en DEEP al momento del stop (probablemente reseteado o no asignado tras un retorno temprano del lane handler) → cae en el `else` y reporta `search_count = 0`. Adicionalmente, cuando `last_judge_confidence is None`, el frontend convierte `null → 0` antes de mostrar el porcentaje.

### Mejoras específicas

#### Mejora 2.1 — Source-of-truth para el budget signal

- **Qué cambiar:** en lugar de inferir el tipo de budget desde `selected_lane`, propagar **explícitamente** desde el lane handler la razón concreta (`ReactStepsBudgetReached`, `SearchRoundsBudgetReached`, `JudgeAttemptsBudgetReached`) como atributo de `RunState` antes de invocar `_stop`.
- **Dónde:** [backend/app/agent/lanes/deep.py](../../backend/app/agent/lanes/deep.py) (cuando `react_result == "forced_synth"`) y `STANDARD` orchestrator.
- **Snippet propuesto:** añadir `state.budget_exhausted_kind: Literal["react_steps","search_rounds","judge_attempts"] | None`, fijarlo donde dispara el límite, y leerlo en `_stop` en lugar del `if/elif` actual basado en lane.

#### Mejora 2.2 — Mostrar confianza estructural cuando no hay judge

- **Qué cambiar:** cuando `last_judge_confidence is None` pero el run produjo evidencia, persistir `stop_rationale.confidence = state.last_structural_confidence` (S) y un flag `confidence_kind: "structural" | "judge"` para que la UI muestre algo honesto (p.ej. "Confianza estructural 0.58 · juez no confirmado").
- **Dónde:** `orchestrator.py::_stop` líneas 770-790 + `StopRationale` model en `backend/app/llm/models.py` o `domain/events.py`.

#### Mejora 2.3 — Frontend: distinguir "no medido" de "0 %"

- **Qué cambiar:** en el renderer de la confianza (frontend `StructuredAnswer.tsx` o equivalente), cuando `confidence is null`, mostrar `"—"` o `"No verificado"` en vez de `0 %`.
- **Dónde:** buscar el lugar que hoy produce `**0%**` (probablemente en `frontend/src/features/run/...`). El mismo `structured.py::render` líneas 47-49 ya lo formatea como `{context.confidence:.0%}` — añadir branching en el renderer.

**Esfuerzo estimado:** bajo. **Impacto:** elimina la falsa percepción de fallo en runs DEEP que sí entregaron contenido.

---

## ÁREA 3 — DEEP lane debe sintetizar profundamente

### Problemas identificados

| Run # | Escenario | Problema específico | Severidad | Evidencia |
|-------|-----------|---------------------|-----------|-----------|
| 4 | Fasting | Respuesta DEEP = 2 párrafos cortos | 5 | `Stopped.answer_prose` |
| 7 | Long-term memory | Respuesta DEEP = 2 párrafos cortos | 5 | `Stopped.answer_prose` |

### Causa raíz

[backend/app/agent/lanes/deep.py:256-281](../../backend/app/agent/lanes/deep.py#L256) y `:308-330` usan `FAST_SYNTH_PROMPT` ("concise 1-2 sentence answer") como prompt del synthesizer DEEP, en lugar de `build_synthesizer_prompt(answer_kind=…)`. Resultado: aunque el agente exploró 8 ReAct steps y reunió 14 evidence items, la instrucción al synthesizer pide brevedad de FAST. Además, no se asigna `answer_kind`, por eso Q4 y Q7 muestran `answer_kind: null`.

### Mejoras específicas

#### Mejora 3.1 — DEEP usa el builder kind-specific

- **Qué cambiar:** sustituir las dos invocaciones a `FAST_SYNTH_PROMPT.format(...)` por `build_synthesizer_prompt(question, evidence, answer_kind, user_language="es", hypotheses=...)`.
- **Dónde:** `backend/app/agent/lanes/deep.py::_synthesize_with_react_history` y `_synthesize_with_contradictions`.
- **`answer_kind` seleccionado para DEEP:** invocar `select_answer_kind` con `state.question_type`, `structural_confidence` derivada de la ReAct history, `coverage` derivada de `hypotheses_confirmed/total`, `agreement = 0.5 if contradictions else 0.8`. Para `state_of_art` el mapping debería ser `SCENARIO` (con cada hipótesis confirmada como una rama).

#### Mejora 3.2 — DEEP emite `DraftSynthesized` antes de `Stopped`

- **Qué cambiar:** después de generar `draft`, llamar `await self.emit(DraftSynthesizedEvent(answer_kind=..., prose=draft.prose, ...))`. Restaura la auditabilidad (RF-03) hoy ausente en los 8 runs.
- **Dónde:** `deep.py` (los dos sitios) y revisar STANDARD también — el grep mostró 0 `DraftSynthesized` events en los 8 runs.

**Esfuerzo estimado:** medio. **Impacto:** soluciona los dos casos donde el agente "trabaja mucho y entrega poco".

---

## ÁREA 4 — Ambigüedad real → `BEST_EFFORT`, no `TRADEOFF`

### Problema

Run 3 ("best programming language"): `AmbiguityDetected` se emite, pero `select_answer_kind` mapea `SUBJECTIVE_OPINION → TRADEOFF` y produce una respuesta tipo ranking. El escenario espera **liderar** con "the question is ambiguous because…".

### Causa raíz

[backend/app/agent/tasks/select_answer_kind.py](../../backend/app/agent/tasks/select_answer_kind.py) no consume `ambiguity_flag` para `SUBJECTIVE_OPINION`. El comentario explícitamente dice "subjective_opinion → TRADEOFF".

### Mejora 4.1

- **Qué cambiar:** introducir override:
  ```python
  if inputs.question_type == QuestionType.SUBJECTIVE_OPINION and inputs.ambiguity_flag:
      return AnswerKind.BEST_EFFORT
  ```
- **Dónde:** `select_answer_kind.py` función `select_answer_kind`.
- **Efecto:** el synthesizer entonces poblará `interpretation` + `alternative_interpretations` + un `prose` que **lidera** con "la pregunta carece de contexto porque…".

### Mejora 4.2 — Short-circuit en STANDARD cuando `BEST_EFFORT` por ambigüedad

- **Qué cambiar:** cuando ambigüedad se detecta antes de planear, saltar `PLANNING → SEARCHING → ANALYZING` completo y pasar directo a synthesis `BEST_EFFORT` con 0 evidence (o búsqueda mínima para opciones). Hoy Q3 gastó 97 s y 4 tool calls para responder algo que no requiere búsqueda.
- **Dónde:** `orchestrator.py` después del `AmbiguityDetected` event.

---

## ÁREA 5 — FAST lane menos pesimista

### Problema

Q1 (capital de Japón) escaló a STANDARD pese a tener `S = 1.0`. Probablemente la mini-judge rechazó por motivo conservador.

### Mejora 5.1

- **Qué cambiar:** desacoplar el threshold de escalación. Si `S_effective >= 0.85` **y** el judge devuelve `j_score >= 0.7` (no solo `ok=True`), aceptar. Hoy `mini_judge_result.ok` es un booleano sin matiz.
- **Dónde:** [backend/app/agent/lanes/fast.py:210](../../backend/app/agent/lanes/fast.py#L210).
- **Snippet propuesto:**
  ```python
  if mini_judge_result.ok or mini_judge_result.j_score >= 0.85:
      state.draft_answer = synth_result.prose
      ...
      return StopReason.JUDGE_CONFIRMED
  ```

### Mejora 5.2 — Mejorar el proxy de `S_effective`

- **Qué cambiar:** `min(1, n_evidence/6)` premia cantidad sobre calidad. Cambiar a `min(1, sum(authority_multiplier * relevance) / 4)`.
- **Dónde:** `fast.py:142`.

---

## ÁREA 6 — Meta-judge BRD-26 (Value of Continuation + Adversarial Completeness)

### Problema

Está documentado en [BRD-26](../implementation-phase/brds/BRD-26-agentic-stopping-meta-judge.md) y mencionado como Phase 7.5 de [advanced-ai-research.md](../understanding-phase/advanced-ai-research.md), pero `grep MetaStopVerdict|VoC|meta_judge backend/app/` devuelve **cero matches**. Los 8 runs lo confirman: ningún `MetaStopVerdict` event.

### Impacto

- Run 4 (fasting) y Run 7 (memory) cortan en hard cap sin oportunidad de "¿una ronda más vale la pena?".
- Sin AC, los runs no detectan que su propio borrador tiene objeciones obvias sin responder.

### Mejora 6.1

- **Qué cambiar:** implementar los dos signals como `StoppingSignal` plugins.
- **Dónde:** `backend/app/stopping/signals/meta_judge_voc.py` y `meta_judge_adversarial.py` (nuevos).
- **Prompts:** crear `META_JUDGE_VOC_PROMPT` y `META_JUDGE_ADVERSARIAL_PROMPT` en `prompts.py`.
- **Modelos Pydantic:** `ValueOfContinuationVerdict { decision, expected_delta_s, next_action_hypothesis, reason }` y `AdversarialObjectionsResult { objections: list[{kind, text, evidence_ids?, suggested_query?}] }`.
- **Hook points:** STANDARD `after_judge` (antes de evaluar `max_judge_attempts`); DEEP `after_react_observation` y `after_cove`.
- **Event types:** `MetaStopVerdict`, `AdversarialObjectionsGenerated`, `DirectedSubclaimsFromObjections` — registrar en `domain/events.py` con `extra="allow"`.

**Esfuerzo estimado:** alto (un IP completo). **Impacto:** transforma `stopped_by_budget` silenciosos en stops defendibles con razón citada.

---

## ÁREA 7 — Surfacing de contradicciones y supuestos

### Mejora 7.1

- **Qué cambiar:** cuando el judge devuelve `contradictions_detected` no vacío, **inyectar** un bloque `KeyPointsBlock(title="Contradicciones detectadas", items=[...])` en el output, antes de los sources. Hoy esa info se queda en el evento `JudgeRuled` y nunca llega al usuario.
- **Dónde:** `structured.py::build_data` consumiendo `context.judge_verdict` (añadir al `RenderContext`).

### Mejora 7.2

- **Qué cambiar:** en el `SCENARIO_SYNTH_PROMPT` (`prompts.py` líneas ~273-282), añadir requisito: "Cada `ScenarioBranch` DEBE incluir `drivers` (≥ 2) y `assumptions` (≥ 1). Si no puedes nombrarlos, no inventes el escenario."
- **Efecto:** Q5 y Q8 (los dos scenarios) ganarían supuestos explícitos.

---

## ÁREA 8 — Señales de progreso (PlanGaps, NoProgress, EchoChamber)

### Problema

Ningún `PlanGapsDetected` / `NoProgressDetected` / `EchoChamberDetected` event fue emitido en los 8 runs. Las señales existen en código (presumiblemente bajo `backend/app/stopping/signals/` y `app/agent/tasks/`), pero los umbrales jamás se cruzan.

### Mejora 8.1 — Reducir el umbral de echo chamber

- Hoy requiere ≥ 3 fuentes en 7 días + `C_agreement == 1.0`. Considerar **`C_agreement >= 0.9`** y ventana de 14 días para que dispare en runs con noticias replicadas.

### Mejora 8.2 — Re-decomposition para runs borderline

- Forzar al menos una ronda de `identify_plan_gaps` cuando `S_raw < threshold + 0.10` AND `redecomposition_count == 0`. Hoy el código existe pero la condición no se cumple en los 8 runs (todos cierran con `S` mayor al umbral o por DEEP).

---

## Roadmap sugerido (orden por ROI)

| Fase | Áreas | Razón |
|---|---|---|
| **PR-1** (quick win) | 2.1 + 2.2 + 2.3 | Corrige bug de honestidad (rationale + confidence). Cambios localizados. |
| **PR-2** (alto impacto) | 1.1 + 1.2 + 1.3 + 1.4 | Activa todo el contrato kind-specific. Transforma 5/8 outputs. |
| **PR-3** | 3.1 + 3.2 | DEEP por fin produce respuestas DEEP. |
| **PR-4** | 4.1 + 4.2 + 5.1 + 5.2 | Pulido del routing (ambigüedad real, FAST menos pesimista). |
| **PR-5** | 7.1 + 7.2 + 8.1 + 8.2 | Surfacing de contradicciones, supuestos y señales de progreso. |
| **IP nuevo** | 6.1 (meta-judge completo) | El más costoso. Hacer al final cuando los anteriores estabilicen. |

---

## Anexo A — Comandos de verificación

```sql
-- Verificar que tras PR-2 los payloads ya se persisten
SELECT run_id, payload->'answer_kind', jsonb_array_length(payload->'answer_structured_data'->'blocks')
FROM events
WHERE type = 'Stopped'
ORDER BY created_at DESC LIMIT 20;

-- Verificar que tras PR-1 ningún DEEP-budget reporta "search limit"
SELECT payload->'stop_rationale'->>'summary'
FROM events
WHERE type = 'Stopped' AND payload->>'stop_reason' = 'stopped_by_budget';

-- Verificar que tras IP-meta-judge hay MetaStopVerdict
SELECT COUNT(*) FROM events WHERE type = 'MetaStopVerdict';
```

## Anexo B — Métricas a vigilar

| Métrica | Antes (8 runs) | Objetivo post-PR-2 |
|---|---|---|
| % runs con `answer_structured_data.blocks` no-paragraph | 0 % | ≥ 70 % |
| % `weighted`/`scenario`/`tradeoff` con payload kind-specific poblado | 0 % | ≥ 95 % |
| Avg confianza en `stopped_by_budget` (no null) | 0 % | ≥ 0.55 (estructural) |
| Tiempo wall-clock FAST exitoso | 51 s (escaló) | ≤ 15 s |
| Runs DEEP con `answer_kind != null` | 0 / 2 | 2 / 2 |
