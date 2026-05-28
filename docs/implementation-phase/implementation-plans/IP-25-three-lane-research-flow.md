# Implementation Plan — IP-25: Three-Lane Research Flow (FAST / STANDARD / DEEP)

**Plan ID:** IP-25
**Parent design doc:** [building-the-plan.md](../../understanding-phase/building-the-plan.md) — sección "Propuesta de mejora para Novum: pipeline de 3 carriles"
**Parent BRD:** BRD-25 (TBD)
**Date:** 2026-05-28
**Author:** Plan Agent
**Complexity:** XL (backend + agent FSM + new sub-FSM + 9 new event types + frontend trace updates)
**Estimated Effort:** ~7.5 pair-sessions, distribuidas en 7 fases (la fase 0 desbloquea las 8 minutos actuales; A-F son arquitectura)
**Iteration:** 1

---

## 1. Plan summary

Convertir el pipeline lineal actual de Novum en **tres carriles arquitectónicamente distintos** (FAST / STANDARD / DEEP) ruteados determinísticamente desde la salida del `CLASSIFYING` (Self-Ask). Cubre dos objetivos:

1. **Rendimiento (fase 0, crítica):** corregir el bucle serial en `execute_search_round` que es la causa real de los 8 minutos por query STANDARD. Reducir a ~2–3 minutos sin cambiar lógica de negocio.
2. **Arquitectura (fases A–F):** introducir los 3 carriles, cada uno con su composición de estrategias (Decomposition, ReAct, CoVe, Abductive), su política de parada con cortocircuitos de early-exit, y caps duros anti-loop.

### Ámbito

| Fase | Concern | Files (nuevos + modificados) |
|---|---|---|
| **0 (CRÍTICA)** | Paralelizar search + reformulation + echo chamber | `app/agent/tasks/search.py`, `app/confidence/structural.py`, `app/domain/events.py` |
| **A** | `RouteSelected` event + tabla de ruteo (telemetría) | `app/agent/lane_router.py` (NEW), `app/domain/enums.py`, `app/domain/events.py`, `app/agent/orchestrator.py` |
| **B** | Re-decomp dinámica STANDARD + `NoProgressSignal` ventana acumulada | `app/agent/tasks/replan.py` (NEW), `app/stopping/no_progress.py` (NEW), `app/agent/orchestrator.py` |
| **C** | Carril FAST con `LaneEscalated` | `app/agent/lanes/fast.py` (NEW), `app/agent/orchestrator.py` |
| **D** | Hipótesis abductiva en planner | `app/agent/tasks/hypotheses.py` (NEW), `app/llm/prompts.py` |
| **E** | Carril DEEP con ReAct loop + 7 nuevos events | `app/agent/lanes/deep.py` (NEW), `app/agent/react/` (NEW dir), `app/domain/events.py` |
| **F** | CoVe explícito en DEEP (sub-modo del judge) | `app/agent/tasks/cove.py` (NEW), `app/agent/lanes/deep.py` |

### Reglas arquitectónicas respetadas

1. **Los 3 seams intactos** — `Source`, `StoppingSignal`, `OutputRenderer` no cambian. ReAct usa `Source.fetch_full` existente; los checkpoints son nuevos `StoppingSignal` plugins.
2. **Event log append-only** (RF-03) — los 9 eventos nuevos son additive con `model_config=ConfigDict(extra="allow")`. Cero cambios destructivos.
3. **Enum `StopReason` no cambia** — sigue siendo `{judge_confirmed, stopped_by_budget, user_cancelled, errored}`. Finales honestos (contradicción, ambigüedad) se expresan vía `answer_kind=best_effort` + `stop_rationale` descriptivo dentro de `stopped_by_budget`.
4. **Confidence formula intacta** — `final_confidence = min(S_effective, J)` (RF-12) sigue siendo la única regla.
5. **Single-server / `uvicorn --workers 1`** (RF-05) — no introduce distribución; el ReAct loop es in-process.
6. **Type contract FE↔BE** — los 9 eventos nuevos se exportan a `frontend/src/types/events.ts` vía `scripts/export_types.py`.
7. **No LangGraph / LangChain / LlamaIndex** — el ReAct loop son ~120 LOC de Python custom sobre el seam `Source`.
8. **Language policy** — código, prompts internos, logs y `stop_rationale` en **inglés**; el output del usuario sigue la regla actual (español por default).

---

## 2. Phase 0 — Performance fix (CRÍTICA, bloqueante)

> **Esta fase NO depende de ninguna otra y debe implementarse primero.** Resuelve los 8 minutos actuales por sí sola sin tocar arquitectura.

### 2.1 Goal

Paralelizar `execute_search_round`, añadir reformulación de queries con baja relevancia, y añadir penalty por echo chamber en `C_diversity`.

### 2.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-0-01** | Refactorizar `execute_search_round` para ejecutar las búsquedas por claim en paralelo con `asyncio.gather`. Extraer la lógica del bucle interno (cascada Tavily → Wikipedia por claim) a función privada `_search_one_claim(claim, cascade, days_filter, state) -> list[BaseEvent]`. La función debe NO mutar `state` (acumular eventos en lista local y retornarlos); la mutación de `state.add_evidence` y `state.failed_sources` se hace post-gather en el orden devuelto para preservar determinabilidad de replay. | `backend/app/agent/tasks/search.py` | M | [be-agent] |
| **T-25-0-02** | Añadir constante `_MIN_RELEVANCE_THRESHOLD = 0.3` y lógica en `_search_one_claim`: si **todos** los resultados de Tavily tienen `relevance_score < 0.3`, ejecutar una segunda búsqueda con query reformulada (`f"{claim.text} {state.question[:40]}"`). Emitir nuevo evento `QueryReformulatedEvent` con `original_query`, `reformulated_query`, `claim_id`, `reason="low_relevance"`. Una sola reformulación por claim, no loop. | `backend/app/agent/tasks/search.py`, `backend/app/domain/events.py` | M | [be-agent] [be-domain] |
| **T-25-0-03** | Añadir evento nuevo `QueryReformulatedEvent` en `events.py` con discriminator `event_type = "query_reformulated"` y campos `original_query: str`, `reformulated_query: str`, `target_claim_id: UUID`, `reason: Literal["low_relevance"]`. Añadir `EventType.QUERY_REFORMULATED` al enum en `enums.py`. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-0-04** | Añadir detector de echo chamber en `calculate_diversity` (o helper nuevo `_apply_echo_chamber_penalty`): si N ≥ 3 fuentes para el mismo claim tienen `source_published_date` no nulo y todas caen en una ventana de < 7 días Y `C_agreement == 1.0`, multiplicar `C_diversity *= 0.85`. Emitir `EchoChamberDetectedEvent` (nuevo) con `claim_id`, `n_sources`, `date_window_days`. | `backend/app/confidence/structural.py`, `backend/app/domain/events.py`, `backend/app/domain/enums.py` | M | [be-confidence] [be-domain] |
| **T-25-0-05** | Añadir evento `EchoChamberDetectedEvent` con `event_type = "echo_chamber_detected"`, `target_claim_id: UUID`, `n_sources: int`, `date_window_days: int`, `diversity_penalty_applied: float`. Añadir `EventType.ECHO_CHAMBER_DETECTED` al enum. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-0-06** | Regenerar `frontend/src/types/events.ts` ejecutando `python scripts/export_types.py` para incluir los 2 nuevos eventos. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 2.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_tasks_search.py` | `test_execute_search_round_runs_claims_in_parallel` — usar `asyncio.sleep` mockeado por source para verificar que el tiempo total ≈ max(per-claim), no sum | NEW |
| `tests/test_agent_tasks_search.py` | `test_execute_search_round_preserves_event_order_per_claim` — el orden de eventos dentro de cada claim sigue determinístico | NEW |
| `tests/test_agent_tasks_search.py` | `test_low_relevance_triggers_query_reformulation` — todos los results < 0.3 → segunda búsqueda con query reformulada + evento `QueryReformulated` | NEW |
| `tests/test_agent_tasks_search.py` | `test_high_relevance_skips_reformulation` — al menos un result ≥ 0.3 → no reformulación | NEW |
| `tests/test_confidence_structural.py` | `test_echo_chamber_penalty_applied_when_dates_cluster` — 3 fuentes mismo claim, fechas en 5 días → `C_diversity *= 0.85` + evento emitido | NEW |
| `tests/test_confidence_structural.py` | `test_echo_chamber_penalty_skipped_when_dates_spread` — fechas separadas > 7 días → sin penalty | NEW |
| `tests/test_domain_events.py` | `test_query_reformulated_event_serializes`, `test_echo_chamber_detected_event_serializes` | NEW |

### 2.4 Acceptance criteria

- Una query STANDARD con 5 sub-claims termina en ≤ 3 minutos (medida con `time` sobre `smoke_ip21.py` o equivalente).
- Todos los tests existentes de `search.py` y `confidence/` siguen pasando.
- `pyright strict` clean. `ruff` clean.
- Los 2 nuevos eventos aparecen en `frontend/src/types/events.ts` regenerado.

### 2.5 Impacto esperado

| Métrica | Antes | Después |
|---|---|---|
| Latencia búsqueda por ronda (5 claims) | 25–55s | 8–12s |
| Latencia total STANDARD (4 rondas) | 100–220s | 32–48s |
| Query reformuladas | 0% | ~10% de queries con resultados pobres |
| Detección de echo chamber | No existe | Emitido cuando aplica + UI puede mostrarlo |

---

## 3. Phase A — Route telemetry (RouteSelected event)

### 3.1 Goal

Emitir `RouteSelected` después de `CLASSIFYING` para medir en producción qué porcentaje de tráfico correspondería a cada carril, **sin cambiar el pipeline**. Telemetría pura.

### 3.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-A-01** | Crear `app/agent/lane_router.py` con función pura `select_lane(question_type, complexity_hint, temporal_sensitivity, ambiguity_detected) -> tuple[Lane, str]` que retorna `(Lane.FAST | Lane.STANDARD | Lane.DEEP, reason)`. Reglas en docstring. Tipo `Lane` es nuevo `StrEnum` en `enums.py`. | `backend/app/agent/lane_router.py`, `backend/app/domain/enums.py` | M | [be-agent] [be-domain] |
| **T-25-A-02** | Añadir `Lane` StrEnum en `enums.py` con valores `FAST = "fast"`, `STANDARD = "standard"`, `DEEP = "deep"`. | `backend/app/domain/enums.py` | XS | [be-domain] |
| **T-25-A-03** | Añadir `RouteSelectedEvent` en `events.py` con `event_type = "route_selected"`, `lane: Lane`, `reason: str`, `question_type: QuestionType`, `complexity_hint: ComplexityHint`, `temporal_sensitivity: TemporalSensitivity \| None`. Añadir `EventType.ROUTE_SELECTED`. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-A-04** | Forzar `complexity_hint=STANDARD` mínimo cuando `question_type == PREDICTIVE_FUTURE`. Lógica en `lane_router.select_lane`: `if qt == PREDICTIVE_FUTURE and hint == TRIVIAL: hint = STANDARD`. Documentar en docstring por qué (no existen predicciones triviales válidas). | `backend/app/agent/lane_router.py` | XS | [be-agent] |
| **T-25-A-05** | En `orchestrator.py` después de `_detect_question_type` y antes de `PLANNING`, llamar `lane = select_lane(...)` y emitir `RouteSelectedEvent`. Guardar `self.state.selected_lane = lane`. NO ramificar el pipeline aún — todos los carriles siguen ejecutando STANDARD. Esto es solo telemetría. | `backend/app/agent/orchestrator.py`, `backend/app/agent/run_state.py` | S | [be-agent] |
| **T-25-A-06** | Añadir `selected_lane: Lane | None = None` a `RunState`. | `backend/app/agent/run_state.py` | XS | [be-agent] |
| **T-25-A-07** | Regenerar `frontend/src/types/events.ts`. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 3.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_lane_router.py` | `test_fast_for_trivial_direct_static` — `(DIRECT, TRIVIAL, STATIC)` → `FAST` | NEW |
| `tests/test_agent_lane_router.py` | `test_deep_for_causal_complex` — `(CAUSAL, DEEP, *)` → `DEEP` | NEW |
| `tests/test_agent_lane_router.py` | `test_standard_default` — `(COMPARATIVE, STANDARD, VOLATILE)` → `STANDARD` | NEW |
| `tests/test_agent_lane_router.py` | `test_predictive_future_never_trivial` — `(PREDICTIVE_FUTURE, TRIVIAL, *)` → `STANDARD` (no FAST) | NEW |
| `tests/test_agent_lane_router.py` | `test_realtime_excludes_fast` — `(DEFINITIONAL, TRIVIAL, REALTIME)` → `STANDARD` | NEW |
| `tests/test_agent_orchestrator.py` | `test_route_selected_emitted_after_classify` — verificar evento emitido con dimensiones correctas | NEW |

### 3.4 Acceptance criteria

- `RouteSelectedEvent` aparece en el event log después de `QuestionClassified` y antes de `PlanCreated` en todas las runs.
- Telemetry: query SQL `SELECT payload->>'lane', COUNT(*) FROM events WHERE event_type='route_selected' GROUP BY 1` retorna distribución por carril.
- El pipeline existente sigue funcionando idéntico (todos los runs ejecutan el flujo STANDARD actual).

---

## 4. Phase B — Dynamic re-decomposition + NoProgressSignal

### 4.1 Goal

Cerrar el gap del plan estático en STANDARD: después de `ANALYZING`, una llamada extra al planner detecta ángulos no cubiertos y dispara una ronda extra de búsqueda dirigida. Añadir signal que evita iteración sin progreso.

### 4.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-B-01** | Crear `app/agent/tasks/replan.py` con `async def identify_plan_gaps(state: RunState) -> list[str]`: llama al planner con prompt nuevo (`PLAN_GAPS_PROMPT` en `prompts.py`) pasándole pregunta original, sub-claims actuales y resumen de evidencia. Retorna lista de gaps (strings cortos describiendo ángulos faltantes). Max 3 gaps. | `backend/app/agent/tasks/replan.py`, `backend/app/llm/prompts.py` | M | [be-agent] [be-llm] |
| **T-25-B-02** | Añadir `PlanGapsDetectedEvent` con `event_type = "plan_gaps_detected"`, `gaps: list[str]`, `extra_sub_claim_ids: list[UUID]`. Añadir `EventType.PLAN_GAPS_DETECTED`. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-B-03** | En `orchestrator._handle_analyzing` (o equivalente — verificar nombre exacto), después de computar S y antes de `_handle_synthesizing`, evaluar: si `state.redecomposition_count < state.max_redecomposition` (default 1) Y `S_raw < threshold + 0.10`, llamar `identify_plan_gaps`. Si retorna gaps no vacíos: añadir como nuevas `SubClaim` a `state.sub_claims`, emitir `PlanGapsDetectedEvent`, incrementar `redecomposition_count`, transition `ANALYZING → SEARCHING`. | `backend/app/agent/orchestrator.py`, `backend/app/agent/run_state.py` | M | [be-agent] |
| **T-25-B-04** | Añadir a `RunState`: `redecomposition_count: int = 0`, `max_redecomposition: int = 1`, `confidence_history: list[float] = []`. La última se actualiza después de cada `JudgeRuled` con `final_confidence`. | `backend/app/agent/run_state.py` | XS | [be-agent] |
| **T-25-B-05** | Crear `app/stopping/no_progress.py` con `class NoProgressSignal(StoppingSignal)`: `fires` si `len(state.confidence_history) >= 3` Y `state.confidence_history[-1] - state.confidence_history[-3] < 0.05`. Si dispara, retorna decisión que fuerza `SYNTHESIZING` con la evidencia actual (no termina la run directo; deja que synth + judge decidan el final). Emite `NoProgressDetectedEvent` con `delta_3rounds`, `current_confidence`. | `backend/app/stopping/no_progress.py`, `backend/app/domain/events.py`, `backend/app/domain/enums.py` | M | [be-stopping] [be-domain] |
| **T-25-B-06** | Registrar `NoProgressSignal` en `StoppingPolicy` con prioridad media (después de `BudgetExhausted` y `UserCancelled`, antes de los checkpoints específicos por carril). | `backend/app/stopping/__init__.py` o donde estén registrados los signals | XS | [be-stopping] |
| **T-25-B-07** | Añadir el nuevo evento `NoProgressDetectedEvent` con `delta_3rounds: float`, `current_confidence: float`. Añadir `EventType.NO_PROGRESS_DETECTED`. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-B-08** | Regenerar `frontend/src/types/events.ts`. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 4.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_tasks_replan.py` | `test_identify_plan_gaps_returns_list` — mock LLM call returning 2 gaps | NEW |
| `tests/test_agent_tasks_replan.py` | `test_identify_plan_gaps_caps_at_three` — LLM returns 5; only first 3 used | NEW |
| `tests/test_agent_orchestrator.py` | `test_redecomposition_triggers_once_when_s_low` — `S_raw=0.6` + budget left → re-decomp once | NEW |
| `tests/test_agent_orchestrator.py` | `test_redecomposition_skipped_when_s_high` — `S_raw=0.9` → skip re-decomp (puerta A del documento) | NEW |
| `tests/test_agent_orchestrator.py` | `test_redecomposition_skipped_when_budget_exhausted` | NEW |
| `tests/test_stopping_no_progress.py` | `test_fires_when_3_round_delta_below_threshold` | NEW |
| `tests/test_stopping_no_progress.py` | `test_does_not_fire_with_fewer_than_3_rounds` | NEW |
| `tests/test_stopping_no_progress.py` | `test_does_not_fire_when_delta_above_threshold` | NEW |

### 4.4 Acceptance criteria

- En queries STANDARD con `S_raw < 0.8` al final de ANALYZING, se emite `PlanGapsDetected` ≤ 1 vez por run.
- `NoProgressSignal` previene runs con > 3 rondas sin mejora real.
- Tasa de `stopped_by_budget` con `final_confidence` intermedia (0.5–0.7) baja en ≥ 30% en evaluación con fixtures.

---

## 5. Phase C — FAST lane

### 5.1 Goal

Implementar el carril FAST: 1 search (Wikipedia + Tavily) + synth corto + mini-judge schema. Si el mini-judge no aprueba, escalar a STANDARD vía `LaneEscalated`.

### 5.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-C-01** | Crear `app/agent/lanes/fast.py` con `async def execute_fast_lane(state: RunState) -> StopReason | Literal["escalate"]`. Lógica: (1) emite 1 `ToolCalled` con la pregunta original como query (sin sub-claims), corre Wikipedia + Tavily en paralelo, top-3 cada uno; (2) llama synth con prompt corto `FAST_SYNTH_PROMPT`; (3) llama mini-judge con prompt `FAST_MINI_JUDGE_PROMPT` que retorna `{ok: bool, j_score: float}`. Retorna `judge_confirmed` si `S_effective >= 0.85 AND mini_judge.ok`, sino retorna `"escalate"`. | `backend/app/agent/lanes/fast.py`, `backend/app/llm/prompts.py` | L | [be-agent] [be-llm] |
| **T-25-C-02** | Añadir `LaneEscalatedEvent` con `event_type = "lane_escalated"`, `from_lane: Lane`, `to_lane: Lane`, `reason: str`. Añadir `EventType.LANE_ESCALATED`. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-C-03** | En `orchestrator.run`, después de emit `RouteSelectedEvent`, ramificar: `if state.selected_lane == Lane.FAST: result = await execute_fast_lane(state); if result == "escalate": emit LaneEscalatedEvent, continue como STANDARD; else: await self._stop(result); return`. | `backend/app/agent/orchestrator.py` | M | [be-agent] |
| **T-25-C-04** | Añadir prompts `FAST_SYNTH_PROMPT` y `FAST_MINI_JUDGE_PROMPT` en `prompts.py`. El synth genera respuesta de 1–2 frases con citas inline. El mini-judge devuelve schema Pydantic `MiniJudgeVerdict {ok: bool, j_score: float, reason: str}`. | `backend/app/llm/prompts.py`, `backend/app/domain/judge.py` (o donde estén verdicts) | M | [be-llm] [be-domain] |
| **T-25-C-05** | Regenerar `frontend/src/types/events.ts`. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 5.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_lanes_fast.py` | `test_fast_lane_stops_when_mini_judge_ok` — mock high S + mini_judge.ok=True → judge_confirmed | NEW |
| `tests/test_agent_lanes_fast.py` | `test_fast_lane_escalates_when_mini_judge_rejects` — mini_judge.ok=False → returns "escalate" | NEW |
| `tests/test_agent_lanes_fast.py` | `test_fast_lane_escalates_when_s_below_threshold` — S < 0.85 → "escalate" | NEW |
| `tests/test_agent_orchestrator.py` | `test_fast_lane_runs_only_2_llm_calls_on_happy_path` — count `ToolCalled` + LLM mocks; expect 2 LLM calls (synth + mini-judge) | NEW |
| `tests/test_agent_orchestrator.py` | `test_lane_escalated_event_emitted_then_standard_runs` — verifica que tras escalado se ejecuta el flujo STANDARD completo | NEW |

### 5.4 Acceptance criteria

- Una query trivial (ej. `"¿capital de Japón?"`) corre por FAST y termina en ≤ 15s.
- Si FAST no convence (`mini_judge.ok=False`), `LaneEscalatedEvent` emitido y STANDARD ejecuta normalmente.
- Cero regresión en queries que hoy son STANDARD/DEEP.

---

## 6. Phase D — Abductive hypotheses in planner

### 6.1 Goal

Para `AnswerKind ∈ {best_effort, scenario}` o `question_type ∈ {causal, predictive_future}`, el planner emite 2–4 hipótesis competidoras además de las sub-claims. Esto enriquece tanto STANDARD (mejor `best_effort`) como DEEP (input para ReAct).

### 6.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-D-01** | Crear `app/agent/tasks/hypotheses.py` con `async def generate_hypotheses(state: RunState) -> list[Hypothesis]`. Llama planner con `HYPOTHESES_PROMPT`. Retorna 2–4 `Hypothesis` (id UUID, text, priority float). | `backend/app/agent/tasks/hypotheses.py`, `backend/app/llm/prompts.py` | M | [be-agent] [be-llm] |
| **T-25-D-02** | Definir `Hypothesis` Pydantic model en `app/domain/hypothesis.py` (nuevo archivo) con `id: UUID`, `text: str`, `priority: float`, `verdict: Literal["pending", "confirmed", "refuted"] = "pending"`, `evidence_ids: list[UUID] = []`. | `backend/app/domain/hypothesis.py` | S | [be-domain] |
| **T-25-D-03** | Añadir `HypothesesGeneratedEvent` con `event_type = "hypotheses_generated"`, `hypotheses: list[Hypothesis]`. Añadir `EventType.HYPOTHESES_GENERATED`. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-D-04** | En `orchestrator._handle_planning` (o equivalente), después de `create_plan` y `critique_plan`, si `state.question_type in {CAUSAL, SCENARIO, PREDICTIVE_FUTURE, BEST_EFFORT}` O `state.selected_lane == Lane.DEEP`, llamar `generate_hypotheses` y emitir evento. Guardar `state.hypotheses = result`. | `backend/app/agent/orchestrator.py`, `backend/app/agent/run_state.py` | M | [be-agent] |
| **T-25-D-05** | Añadir `hypotheses: list[Hypothesis] = []` a `RunState`. | `backend/app/agent/run_state.py` | XS | [be-agent] |
| **T-25-D-06** | Modificar el prompt del synthesizer en caso `AnswerKind.scenario` para que use `state.hypotheses` como esqueleto: cada hipótesis confirmada se vuelve un escenario etiquetado con su `j_score`. | `backend/app/llm/prompts.py`, `backend/app/agent/tasks/synthesize.py` (o equivalente) | M | [be-llm] [be-agent] |
| **T-25-D-07** | Regenerar `frontend/src/types/events.ts`. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 6.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_tasks_hypotheses.py` | `test_generate_hypotheses_returns_2_to_4` | NEW |
| `tests/test_agent_tasks_hypotheses.py` | `test_hypotheses_have_unique_ids` | NEW |
| `tests/test_agent_orchestrator.py` | `test_hypotheses_generated_for_causal_question` | NEW |
| `tests/test_agent_orchestrator.py` | `test_hypotheses_skipped_for_direct_factual` | NEW |
| `tests/test_agent_tasks_synthesize.py` | `test_scenario_synth_uses_hypotheses_as_skeleton` | NEW |

### 6.4 Acceptance criteria

- `HypothesesGeneratedEvent` aparece para todas las runs con `question_type ∈ {causal, scenario, predictive_future, best_effort}`.
- Los outputs `AnswerKind=scenario` muestran 2–4 escenarios diferenciados con su confianza individual.

---

## 7. Phase E — DEEP lane with ReAct loop

> **Pre-requisito:** medir 1 semana en producción los datos de `RouteSelected` post-fase A. Si `lane=DEEP` aporta < 10% del tráfico, postergar esta fase y concentrar esfuerzo en mejorar STANDARD.

### 7.1 Goal

Implementar el carril DEEP: hipótesis abductiva + ReAct loop con cap de 8 steps + acciones enum-cerrado + 5 eventos nuevos para trazabilidad.

### 7.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-E-01** | Crear directorio `backend/app/agent/react/` con `__init__.py`, `loop.py`, `actions.py`, `prompts.py`, `history.py`. | `backend/app/agent/react/` | XS | [be-agent] |
| **T-25-E-02** | Definir en `react/actions.py` el enum cerrado `AgentActionType = Literal["search", "deep_fetch", "evaluate_hypothesis", "finish"]` y los modelos Pydantic `SearchAction { query: str, source_hint: SourceType | None }`, `DeepFetchAction { url: str }`, `EvaluateHypothesisAction { hypothesis_id: UUID, verdict: Literal["confirmed", "refuted"] }`, `FinishAction { reason: str }`. Discriminated union `AgentActionUnion` con `type` como discriminator. | `backend/app/agent/react/actions.py` | M | [be-agent] |
| **T-25-E-03** | Implementar `react/loop.py::async def run_react_loop(state, max_steps=8) -> StopReason | Literal["forced_synth"]`. Bucle: por cada step, (a) `Thought` LLM call con prompt `REACT_THOUGHT_PROMPT` que ve history + hypotheses; (b) `Action` LLM call con structured output `AgentActionUnion`; (c) `execute_action` despacha al seam `Source` o actualiza `state.hypotheses`; (d) emite los 3 eventos (`AgentThought`, `AgentAction`, `AgentObservation`); (e) evalúa stopping intra-loop (ver T-25-E-06). Acciones inválidas → step no cuenta + reprompt. | `backend/app/agent/react/loop.py`, `backend/app/agent/react/prompts.py` | XL | [be-agent] [be-llm] |
| **T-25-E-04** | Implementar `react/history.py::summarize_history_if_needed(history, max_tokens=15000) -> History` — si tokens > 15k, llama al synthesizer con tarea de summarization sobre `history[:-4]` y mantiene últimos 4 verbatim. | `backend/app/agent/react/history.py` | M | [be-agent] |
| **T-25-E-05** | Añadir 5 eventos nuevos: `AgentThoughtEvent { step: int, thought: str }`, `AgentActionEvent { step: int, action_type: AgentActionType, args: dict }`, `AgentObservationEvent { step: int, result_summary: str, tokens: int }`, `HypothesisEvaluatedEvent { hypothesis_id: UUID, verdict: str, evidence_ids: list[UUID] }`, `HistorySummarizedEvent { steps_summarized: int, summary_tokens: int }`. Añadir los 5 al `EventType` enum. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | M | [be-domain] |
| **T-25-E-06** | Crear `app/stopping/react_intra_loop.py` con 4 signals: `HypothesisConfirmedSignal` (≥1 hypothesis con verdict=confirmed Y S ≥ threshold), `AllHypothesesRefutedSignal`, `ReactStepCapSignal` (step ≥ max_steps), y `ReactContradictionSignal` (2+ confirmed con evidencia tier primary_authoritative mutuamente excluyente). Cada uno dispara una decisión específica (`judge_confirmed` para el primero, `stopped_by_budget`+best_effort para los otros). | `backend/app/stopping/react_intra_loop.py` | L | [be-stopping] |
| **T-25-E-07** | Crear `app/agent/lanes/deep.py::async def execute_deep_lane(state)`. Flujo: (1) genera hipótesis si no existen (reusa T-25-D-01); (2) corre `run_react_loop`; (3) `SYNTHESIZE` con history como contexto; (4) judge; (5) si `cove_enabled` → CoVe (fase F). Retorna `StopReason`. | `backend/app/agent/lanes/deep.py` | L | [be-agent] |
| **T-25-E-08** | En `orchestrator.run`, ramificar a `execute_deep_lane` cuando `state.selected_lane == Lane.DEEP`. | `backend/app/agent/orchestrator.py` | S | [be-agent] |
| **T-25-E-09** | Añadir a `RunState`: `react_history: list[ReactStep] = []`, `react_step_count: int = 0`, `max_react_steps: int = 8`. `ReactStep` es Pydantic `{ step: int, thought: str, action: AgentActionUnion, observation: str }`. | `backend/app/agent/run_state.py`, `backend/app/agent/react/loop.py` | S | [be-agent] |
| **T-25-E-10** | Regenerar `frontend/src/types/events.ts`. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 7.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_react_loop.py` | `test_loop_terminates_on_hypothesis_confirmed` | NEW |
| `tests/test_agent_react_loop.py` | `test_loop_terminates_on_all_refuted` | NEW |
| `tests/test_agent_react_loop.py` | `test_loop_caps_at_max_steps` | NEW |
| `tests/test_agent_react_loop.py` | `test_invalid_action_does_not_count_step` | NEW |
| `tests/test_agent_react_loop.py` | `test_history_summarized_when_tokens_exceed_15k` | NEW |
| `tests/test_agent_react_loop.py` | `test_all_events_emitted_per_step` — Thought + Action + Observation por step | NEW |
| `tests/test_agent_lanes_deep.py` | `test_deep_lane_happy_path_judge_confirmed` | NEW |
| `tests/test_agent_lanes_deep.py` | `test_deep_lane_falls_back_to_best_effort_on_cap` | NEW |
| `tests/test_stopping_react_intra_loop.py` | 4 tests, uno por signal | NEW |

### 7.4 Acceptance criteria

- Queries `complexity=deep` + `causal/scenario` ejecutan el ReAct loop.
- El loop nunca excede `max_react_steps=8` (verificado por test de invariante).
- Cada step persiste en event log → replay completo posible.
- Tasa de `judge_confirmed` para queries causales sube ≥ 25% vs. pipeline actual (medido sobre fixtures de evaluación).

---

## 8. Phase F — Explicit CoVe in DEEP

### 8.1 Goal

Después de `SYNTHESIZING` en DEEP, ejecutar CoVe real: el sintetizador genera 3 preguntas de verificación sobre el draft; el judge (modelo distinto, DeepSeek-V3) las verifica mediante mini-búsquedas. Si hay contradicción y `cove_rounds < max_cove_rounds`, re-draft.

### 8.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-25-F-01** | Crear `app/agent/tasks/cove.py` con: `async def generate_verification_questions(draft, role=SYNTHESIZER) -> list[str]` (3 preguntas, prompt nuevo `COVE_QUESTIONS_PROMPT`); `async def verify_question(question, draft, role=JUDGE) -> CoveVerdict` (busca evidencia con seam Source, mide consistencia con el draft, retorna `{contradicts: bool, evidence: str}`). | `backend/app/agent/tasks/cove.py`, `backend/app/llm/prompts.py` | L | [be-agent] [be-llm] |
| **T-25-F-02** | Añadir `VerificationQuestionsGeneratedEvent { questions: list[str] }` y `CoveContradictionDetectedEvent { question: str, contradicting_evidence: str }`. Añadir entradas al `EventType` enum. | `backend/app/domain/events.py`, `backend/app/domain/enums.py` | S | [be-domain] |
| **T-25-F-03** | En `execute_deep_lane`, después de `SYNTHESIZING` y antes del judge final, ejecutar CoVe: (a) emit `VerificationQuestionsGeneratedEvent`; (b) por cada pregunta llamar `verify_question`; (c) si N ≥ 1 contradicen Y `state.cove_rounds < max_cove_rounds` (default 1) → re-draft con context de contradicciones, incrementar `cove_rounds`; (d) sino → aceptar draft. | `backend/app/agent/lanes/deep.py`, `backend/app/agent/run_state.py` | M | [be-agent] |
| **T-25-F-04** | Añadir a `RunState`: `cove_rounds: int = 0`, `max_cove_rounds: int = 1`. | `backend/app/agent/run_state.py` | XS | [be-agent] |
| **T-25-F-05** | Regenerar `frontend/src/types/events.ts`. | `frontend/src/types/events.ts` | XS | [fe-types] |

### 8.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_agent_tasks_cove.py` | `test_generate_verification_questions_returns_3` | NEW |
| `tests/test_agent_tasks_cove.py` | `test_verify_question_returns_no_contradiction_when_evidence_supports` | NEW |
| `tests/test_agent_tasks_cove.py` | `test_verify_question_detects_contradiction` | NEW |
| `tests/test_agent_lanes_deep.py` | `test_cove_redraft_when_contradiction_within_budget` | NEW |
| `tests/test_agent_lanes_deep.py` | `test_cove_accepts_draft_when_budget_exhausted` | NEW |
| `tests/test_agent_lanes_deep.py` | `test_cove_uses_synthesizer_for_questions_judge_for_verification` — assert distintos role en LLM mocks | NEW |

### 8.4 Acceptance criteria

- En DEEP, CoVe siempre se ejecuta una vez después del primer draft.
- Las preguntas las genera `SYNTHESIZER` y la verificación la hace `JUDGE` (familias distintas — gpt-5 vs DeepSeek-V3) → independencia real.
- Re-draft ocurre máximo `max_cove_rounds=1` veces.

---

## 9. Cross-cutting work

### 9.1 Frontend trace panel updates

Los 9 nuevos eventos deben renderizarse en el trace panel (RF-13 trust surface) y opcionalmente en el live feed del center panel:

| Evento | Carril | Visualización mínima |
|---|---|---|
| `RouteSelected` | todos | Badge con lane name + reason en collapse |
| `LaneEscalated` | FAST→STANDARD | Inline note "Escaló a STANDARD: {reason}" |
| `PlanGapsDetected` | STANDARD | Lista de gaps + extra sub-claims |
| `HypothesesGenerated` | DEEP / scenario | Cards con cada hipótesis (text + priority) |
| `AgentThought/Action/Observation` | DEEP | Step counter + collapsible content per step |
| `HypothesisEvaluated` | DEEP | Tick/cross sobre la hipótesis correspondiente |
| `VerificationQuestionsGenerated` | DEEP | Lista numerada de las 3 preguntas |
| `EchoChamberDetected` | todos | Warning chip "Posible echo chamber: N fuentes en {window}d" |
| `QueryReformulated` | todos | Pequeña nota gris bajo el `ToolCalled` original |
| `NoProgressDetected` | todos | Warning chip "Sin progreso por 3 rondas" |

Esto vive en el frontend bajo `RunFeed` (organism IP-24) y `TracePanel`. Cada evento nuevo necesita su entry en `EVENT_VISUALS` y `getEventNarrative`. Task `T-25-CC-01` (XL): añadir las 9 entradas + sus tests Vitest. Fuera del scope de Copilot backend; programar en sprint separado o paralelo.

### 9.2 SQL telemetry helpers

Crear `scripts/lane_telemetry.sql` con las queries del documento (`building-the-plan.md` § "Pre-requisito: medir antes de E") para que el equipo pueda medir distribución por carril, tasas de escalado, latencias, etc.

### 9.3 Memory bank updates

Después de cada fase, registrar en `.github/memory-bank/logs/decisions-history.md` con formato existente:
- `D-XXX` ID
- Fecha
- Decisión técnica clave (ej. "Lane routing como lógica determinística, no LLM call extra")
- Tradeoffs evaluados
- Status

Y en `lessons-learned.md` si surgen problemas comunes (ej. paralelismo + transacciones DB).

---

## 10. Sequencing & dependencies

```
Phase 0 (CRÍTICA) ───────────► merge antes que cualquier otra
                                       │
       ┌───────────────────────────────┴────────────────────────────────┐
       │                                                                 │
       ▼                                                                 │
Phase A (Telemetry, 0.5 sesión)                                          │
       │                                                                 │
       ├──── medir 1 semana en producción ──────────────────────┐        │
       │                                                        │        │
       ▼                                                        │        │
Phase B (Re-decomp + NoProgress, 1 sesión)                      │        │
       │                                                        │        │
       ▼                                                        │        │
Phase C (FAST lane, 1 sesión) ◄─── Phase D (Hypotheses, 0.5)    │        │
       │                                                        │        │
       │                                  ┌─────────────────────┘        │
       │                                  │ Gate: si DEEP < 10% → STOP   │
       │                                  ▼                              │
       │                            Phase E (DEEP, 3 sesiones)           │
       │                                  │                              │
       │                                  ▼                              │
       │                            Phase F (CoVe, 1 sesión)             │
       │                                  │                              │
       └──────────────────────────────────┴──────────────────────────────┘
                                          │
                                          ▼
                              Cross-cutting (UI + docs)
```

**Reglas de orden:**
1. **Fase 0 va primera, siempre.** Sin paralelismo, las demás fases no se notan.
2. **Fase A tras Fase 0.** Necesitamos telemetría para decidir si vale Fase E.
3. **Fase B no depende de A** (la re-decomp sirve sin saber qué carril) pero tiene más sentido después.
4. **Fase C y D son paralelas.** Ninguna depende de la otra.
5. **Fase E depende de A + D.** Necesita el ruteo y las hipótesis abductivas.
6. **Fase F depende de E.** CoVe se ejecuta en el carril DEEP.

---

## 11. Quality gates per phase

| Gate | Threshold | Verificación |
|---|---|---|
| Tests unitarios | ≥ 80% cobertura líneas afectadas | `pytest --cov` por módulo nuevo |
| `pyright strict` | clean | CI |
| `ruff` | clean | CI |
| Tests existentes | 0 regresiones | full suite |
| Replay determinístico | 100% runs replayables | golden trace tests existentes en `tests/fixtures/runs/` extendidos con casos nuevos |
| Type contract FE↔BE | 0 drift | `scripts/export_types.py` corre y produce diff vacío |
| Smoke test E2E | una query por carril termina exitosamente | `scripts/smoke_ip25.py` (NEW, similar a `smoke_ip21.py`) |
| Latencia STANDARD | ≤ 3 min en p50 sobre golden traces | benchmark script |

---

## 12. Risks & mitigations

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Paralelizar search rompe order-dependence en `state.add_evidence` | Media | Alto (events fuera de orden → replay roto) | T-25-0-01 explícitamente acumula eventos en lista local y los aplica en orden post-gather |
| Re-decomposición agota budget en queries ya borderline | Baja | Medio | Cap fijo `max_redecomposition=1` + skip cuando `S_raw ≥ 0.85` |
| ReAct loop entra en bucles | Media | Alto | Cap duro `max_react_steps=8` + `NoProgressSignal` + acción enum cerrado |
| Mini-judge en FAST aprueba respuestas malas | Media | Medio | Threshold conservador (`S ≥ 0.85`) + escalado a STANDARD como safety net |
| CoVe en DEEP nunca termina | Baja | Medio | `max_cove_rounds=1` |
| El judge LLM sigue siendo DeepSeek (no independencia perfecta vs synthesizer gpt-5) | Media | Bajo (ya hay independencia de familia) | Aceptable en V1 post-V1; mejorar a Claude Sonnet con flip de env `judge_provider=anthropic` cuando se requiera mayor independencia |
| Context window overflow en ReAct con steps largos | Media | Alto | T-25-E-04: summarization automática cuando `tokens > 15k` |
| Frontend renderiza eventos nuevos como "unknown" | Alta si no se actualiza | Bajo (visual) | Cross-cutting T-25-CC-01 en sprint paralelo |

---

## 13. Out-of-scope

- **Cambiar de provider LLM** (Groq, Cerebras, OpenAI directo). No requerido — el código ya soporta routing per-role via env. Decisión separada.
- **Vector DB / embeddings semánticos** — fuera de scope, ver `building-the-plan.md` § "What Novum Does NOT Do".
- **Long-term memory across runs** — RF-08 mantiene cada run aislada.
- **Multi-agent debate** — la propuesta original lo descartó.
- **Tree-of-Thoughts** — descartado por costo cuadrático.

---

## 14. References

- Design doc: [building-the-plan.md](../../understanding-phase/building-the-plan.md)
- Current flow: [advanced-ai-research.md](../../understanding-phase/advanced-ai-research.md)
- Confidence: [confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- Stopping: [stopping-signal-analysis.md](../../understanding-phase/stopping-signal-analysis.md)
- Architecture: [architecture.md](../../technical-phase/architecture.md)
- Requirements: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
- Previous IPs: [IP-23](IP-23-research-quality-improvements.md), [IP-24](IP-24-live-center-feed.md)

---

## 15. Definition of Done

- [ ] Fase 0 mergeada y medible: query STANDARD termina en ≤ 3 min en p50.
- [ ] `RouteSelected` se emite en 100% de runs nuevos.
- [ ] Re-decomp activa cuando aplica; emite `PlanGapsDetected` ≤ 1 vez por run.
- [ ] FAST funciona para queries triviales en ≤ 15s; escalado funciona cuando falla.
- [ ] Hipótesis se generan para `causal/scenario/predictive_future/best_effort`.
- [ ] DEEP corre el ReAct loop para queries elegibles (si Fase E aprobada por telemetría).
- [ ] CoVe explícito ejecuta una ronda de verificación en DEEP (si Fase F aprobada).
- [ ] Los 11 eventos nuevos están en `events.py`, `enums.py`, exportados a `frontend/src/types/events.ts`.
- [ ] Coverage ≥ 80% por módulo nuevo. Suite completa pasa.
- [ ] `decisions-history.md` y `lessons-learned.md` actualizados.
- [ ] Smoke E2E pasa con una query por carril.
