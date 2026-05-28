# Implementation Plan — IP-26: Agentic Stopping (Reflective Meta-Judge + Adversarial Completeness)

**Plan ID:** IP-26
**Parent BRD:** [BRD-26](../brds/BRD-26-agentic-stopping-meta-judge.md)
**Parent design doc:** [advanced-ai-research.md](../../understanding-phase/advanced-ai-research.md) §7 (stopping policy)
**Date:** 2026-05-28
**Author:** Plan Agent
**Complexity:** L (1 new LLM role + 3 events + 2 stopping signals + 2 orchestrator hooks + 1 conversion task)
**Estimated Effort:** ~3 pair-sessions, distribuidas en 5 fases (A foundations → E FE wiring)
**Iteration:** 2 (post-audit F2)
**Assumes shipped:** IP-25 todas las fases (3 carriles, ReAct loop, CoVe, hipótesis abductivas, `NoProgressSignal`, `LaneEscalated`).

**Audit changelog (iter 2):**
- C-1: nuevos prompts viven en `app/llm/meta_judge_prompts/` (paquete nuevo) — evita colisión con módulo existente `app/llm/prompts.py`.
- C-2: implementamos los envs **prescritos por el BRD** (`META_JUDGE_PROVIDER`, `META_JUDGE_MODEL_<provider>`) además del esquema existente; honran AC-11 verbatim.
- C-3 / M-2: el chequeo del happy path usa `judge_event.final_confidence` (ya `min(S_effective, J)` por construcción en `JudgeRuledEvent`), no `last_judge_confidence`.
- M-1: símbolo correcto `draft_best_effort_fallback` (sin guion bajo) en `app/agent/tasks/draft.py`.
- M-3: test de priorities cubre los 8 signals reales (Honest=10, Budget=20, NoProgress=30, Coverage=30, Agreement=35, Judge=40, VoC=45, AC=46).
- M-4 / m-2 / m-4 / m-5: nits aplicados en cada fase.

---

## 1. Plan summary

Convertir las tapas numéricas duras (`max_judge_attempts`, `max_react_steps`, `max_cove_rounds`) — hoy *criterio de decisión* de la terminación — en simples **pisos de seguridad**, y mover la *decisión* a un razonador LLM ligero (el "meta-juez") que se invoca después de cada punto de parada candidato y responde dos preguntas epistémicas:

1. **Value-of-Continuation (VoC)** — *¿una ronda más vale la pena?*
2. **Adversarial Completeness (AC)** — *¿qué objeciones de un revisor escéptico quedan sin responder?*

La salida de la AC se convierte, cuando existen objeciones `unanswered_needs_search`, en nuevos `SubClaim` dirigidos (STANDARD) o en `evaluate_hypothesis` targets (DEEP), forzando una continuación **dirigida** en lugar de exploratoria.

El BRD-26 es **aditivo puro**: 3 eventos nuevos, 2 signals nuevos, 1 rol LLM nuevo, 2 hooks en `orchestrator`. No toca: `StopReason` enum, fórmula `final_confidence = min(S_effective, J)` (RF-12), los 3 seams (`Source`, `StoppingSignal`, `OutputRenderer`), schema de events existentes, golden traces previas.

### Ámbito por fase

| Fase | Concern | Files (nuevos + modificados) |
|---|---|---|
| **A** | Domain types + LLM role + prompts | `app/domain/meta_stop.py` (NEW), `app/domain/events.py`, `app/domain/enums.py`, `app/llm/roles.py`, `app/llm/meta_judge_prompts/__init__.py` (NEW), `app/llm/meta_judge_prompts/voc.py` (NEW), `app/llm/meta_judge_prompts/adversarial.py` (NEW), `app/config.py` |
| **B** | Stopping signals (VoC + AC) + conversion task | `app/stopping/signals/meta_judge_voc.py` (NEW), `app/stopping/signals/meta_judge_adversarial.py` (NEW), `app/stopping/signals/__init__.py`, `app/agent/tasks/objections_to_subclaims.py` (NEW), `app/agent/run_state.py` (SubClaim.origin) |
| **C** | Orchestrator hook STANDARD `after_judge` + fallback prompt | `app/agent/orchestrator.py`, `app/llm/prompts.py` (extend existing fallback clause), `app/agent/tasks/draft.py` (pass `meta_judge_reason` through `draft_best_effort_fallback`), `app/agent/run_state.py` (meta-judge counters) |
| **D** | Orchestrator hooks DEEP (`after_react_observation`, `after_cove`) + hypothesis routing | `app/agent/lanes/deep.py`, `app/agent/react/loop.py`, `app/agent/tasks/cove.py`, `app/agent/tasks/objections_to_subclaims.py` |
| **E** | FE types export + trace renderer | `frontend/src/types/events.ts`, `frontend/src/lib/eventLabels.ts`, `frontend/src/components/organisms/TraceTimeline.tsx`, `frontend/src/components/organisms/RunFeed.tsx` |

### Reglas arquitectónicas respetadas

1. **Seams intactos.** Los dos nuevos signals son implementaciones del seam `StoppingSignal` existente (RF-01). No se introduce un cuarto seam.
2. **Event log append-only** (RF-03) — 3 eventos nuevos con `model_config=ConfigDict(extra="allow")`, todos opcionales. Una traza pre-BRD-26 replay byte-identical (AC-16 del BRD).
3. **`StopReason` enum sin cambios.** Stops honestos por VoC mapean a `STOPPED_BY_BUDGET` + `AnswerKind.BEST_EFFORT` + `stop_rationale` que cita `verdict.reason` (BRD §4.6, FR-26-10).
4. **`final_confidence = min(S_effective, J)`** sigue siendo la única fórmula (RF-12). El `expected_delta_s` del meta-juez es señal de decisión, no entra en confidence persistida (FR-26-08).
5. **Determinismo de read** (RF-08). Cada output del meta-juez se persiste en evento; replay nunca re-invoca `llm.call`. Fork antes del evento sí re-invoca — es la semántica intencional (BRD §4.11).
6. **Single-server / `uvicorn --workers 1`** (RF-05). El meta-juez es 1 (a veces 2) `llm.call` extra por checkpoint; cero infra nueva, cero migración Alembic.
7. **Hard caps siguen presentes.** `max_judge_attempts` sube a 5 (era 3 en `RunState` actual) **solamente porque** el VoC ahora corta antes en la mayoría de runs. El cap nunca decide; solo termina cuando el VoC ya dijo `continue` 5 veces seguidas (FR-26-07).
8. **Language policy.** Prompts, identifiers, `Objection.text`, `MetaStopVerdictEvent.verdict.reason` en **inglés**. La respuesta del synthesizer sigue al usuario (español por default) — el clause de fallback en `prompts.py` ya termina con *"Reply in the user's language."* (BRD §4.8).
9. **Type contract FE↔BE.** Los 3 eventos nuevos se exportan a `frontend/src/types/events.ts` vía `python scripts/export_types.py`. CI verifica diff vacío.

### Símbolos reales referenciados (verificados sobre `main`)

- `app.agent.run_state.RunState.judge_attempts: int = 0`, `max_judge_attempts: int = 3` (línea 130). BRD-26 §4.6 los llama `judge_attempt_count` — el plan **usa los nombres reales**. La subida a default 5 se hace cambiando el valor por defecto.
- `app.agent.run_state.RunState.last_structural_confidence`, `last_judge_confidence` (líneas 132–133). `JudgeRuledEvent.final_confidence` (orchestrator.py L518) ya carga `min(S_effective, J)` — **es la fuente canónica** para el happy-path check, no `last_judge_confidence` aislado.
- `app.domain.enums.Lane` (FAST/STANDARD/DEEP), `LLMRole` (CLASSIFIER/PLANNER/SYNTHESIZER/JUDGE).
- `app.llm.client.llm.call(role, prompt, response_model=..., ...)` ya soporta `instructor` JSON mode (BRD §4.2 — Pydantic v2 con `ConfigDict(extra="allow")`).
- `app.llm.client.LLMProviderQuotaExhausted`, `InstructorRetryException` (ya importadas en `client.py`).
- `app.stopping.signals.no_progress.NoProgressSignal` con `priority=30`, contrato `StopSignalOutput`. Los nuevos signals siguen el mismo patrón. **Paisaje completo de prioridades en main:** Honest=10, Budget=20, NoProgress=30, Coverage=30, Agreement=35, Judge=40 (8 signals al añadir VoC=45 + AC=46).
- `app.agent.tasks.draft.draft_best_effort_fallback` (módulo-level, **sin** guion bajo) — orchestrator.py la importa en L574.
- `app.agent.lanes.fast.execute_fast_lane`, `app.agent.lanes.deep.execute_deep_lane`, `app.agent.react.loop.run_react_loop` — puntos de inserción para los hooks DEEP.
- `app.llm.prompts` **es un módulo (`prompts.py`), no un paquete**. Por eso los prompts nuevos van en `app/llm/meta_judge_prompts/` (paquete separado) — ver Phase A.

---

## 2. Phase A — Domain + LLM role + prompts

### 2.1 Goal

Aterrizar las piezas inertes (types, events, role enum, prompts) sin tocar todavía el orchestrator. Al final de esta fase, todo importa, todo compila con `pyright strict`, todo pasa tests, y nada se invoca.

### 2.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-26-A-01** | Crear `app/domain/meta_stop.py` con tres Pydantic models: `ValueOfContinuationVerdict { decision: Literal["stop","continue","stop_best_effort"], expected_delta_s: float (0..1), next_action_hypothesis: str \| None, reason: str }`, `Objection { text: str, status: Literal["answered_by_evidence","unanswered_needs_search","unanswered_no_search_possible"], evidence_ids_answering: list[UUID] = [], suggested_query: str \| None = None }`, `AdversarialCompletenessVerdict { objections: list[Objection], all_answered: bool }`. Validator `@field_validator("objections")` exige `len == 3`. `all_answered` validator deriva su valor de `objections` (no confiar en el LLM). Todos los modelos con `model_config = ConfigDict(extra="allow")`. | `backend/app/domain/meta_stop.py` | M | [be-domain] |
| **T-26-A-02** | Añadir 3 valores a `EventType` en `enums.py`: `META_STOP_VERDICT = "MetaStopVerdict"`, `ADVERSARIAL_OBJECTIONS_GENERATED = "AdversarialObjectionsGenerated"`, `DIRECTED_SUBCLAIMS_FROM_OBJECTIONS = "DirectedSubclaimsFromObjections"`. Mantener el comentario de grouping (BRD-26 §4.4). | `backend/app/domain/enums.py` | XS | [be-domain] |
| **T-26-A-03** | Añadir 3 eventos en `events.py`. `MetaStopVerdictEvent { lane: Lane, hook: Literal["after_judge","after_react_observation","after_cove"], verdict: ValueOfContinuationVerdict, confidence_at_check: float }`. `AdversarialObjectionsGeneratedEvent { lane: Lane, verdict: AdversarialCompletenessVerdict }`. `DirectedSubclaimsFromObjectionsEvent { source_objection_count: int, created_subclaim_ids: list[UUID] }`. Cada uno hereda de `BaseEvent`, tiene `type: Literal[...]` discriminado, y `model_config = ConfigDict(extra="allow")`. Registrar en el `EventUnion` discriminated union. | `backend/app/domain/events.py` | M | [be-domain] |
| **T-26-A-04** | Añadir `LLMRole.META_JUDGE = "meta_judge"` al StrEnum en `roles.py`. Añadir entrada en `ROLE_CONFIGS` con resolución por capas: (1) si `settings.meta_judge_provider` está definido, buscar `settings.meta_judge_models[settings.meta_judge_provider]` y construir tupla 1-element; (2) sino, copiar `ROLE_CONFIGS[LLMRole.JUDGE].models`. `temperature=0.0`, `max_tokens=1024`, `description="Agentic stopping meta-judge (BRD-26)"`. Esta resolución honra AC-11 verbatim y a la vez permite el default (sin envs) de caer en la familia JUDGE (FR-26-11). | `backend/app/llm/roles.py` | M | [be-llm] |
| **T-26-A-05** | Añadir a `Settings` en `app/config.py` los campos requeridos por **BRD-26 §4.3 / FR-26-11 / AC-11**: `meta_judge_provider: str \| None = Field(default=None, alias="META_JUDGE_PROVIDER")` + un dict serializado por env-pattern `META_JUDGE_MODEL_<provider>` parseado en `__init__` con `model_config(env_prefix="", populate_by_name=True)` (Pydantic Settings BaseSettings ya soporta `model_validator` para descubrir todos los envs que matchean el prefijo `META_JUDGE_MODEL_`). Defaults: cuando ambos son `None`, `LLMRole.META_JUDGE` cae al pool del `LLMRole.JUDGE` (DeepSeek-V3 en prod). Documentar en docstring que `META_JUDGE_PROVIDER=anthropic` + `META_JUDGE_MODEL_anthropic="claude-sonnet-4-6"` ruta a Anthropic (AC-11 verbatim). | `backend/app/config.py` | M | [be-config] |
| **T-26-A-06** | Crear **paquete nuevo** `app/llm/meta_judge_prompts/__init__.py` vacío. (No reusamos `app/llm/prompts.py` porque es un módulo de archivo único; convertirlo en paquete homónimo rompería imports `from app.llm.prompts import …`.) Crear `app/llm/meta_judge_prompts/voc.py` con la constante `VOC_SYSTEM_PROMPT: str` (texto del BRD §4.9 *Value-of-Continuation*) y función `build_voc_user_prompt(state: RunState, judge_verdict: JudgeRuledEvent) -> str` que serializa: original question, AnswerKind, lane, sub-claims con evidence count + tier mix, S_effective actual, J_score, rondas ejecutadas, rondas restantes, último judge verdict (approve/reject + reason). Todo en inglés. | `backend/app/llm/meta_judge_prompts/voc.py` | M | [be-llm] |
| **T-26-A-07** | Crear `app/llm/meta_judge_prompts/adversarial.py` con `AC_SYSTEM_PROMPT: str` (texto del BRD §4.9 *Adversarial Completeness*) y `build_ac_user_prompt(state, draft_answer, evidence_index) -> str`. El prompt obliga **exactamente 3** objeciones diferenciadas (no variaciones), `suggested_query` ≤ 6 tokens. Todo en inglés. | `backend/app/llm/meta_judge_prompts/adversarial.py` | M | [be-llm] |
| **T-26-A-08** | Añadir a `SubClaim` (en `app/agent/run_state.py` o donde esté el modelo) un campo nuevo opcional `origin: Literal["planner","redecomposition","adversarial_objection"] = "planner"`. Backfill con `"planner"` para sub-claims existentes (default). | `backend/app/agent/run_state.py` | XS | [be-agent] |
| **T-26-A-09** | Añadir a `RunState`: `meta_judge_calls: int = 0` (telemetría para NFR-26-01) y `max_judge_attempts: int = 5` (subir de 3 a 5; el VoC corta antes en la mayoría de runs — BRD §4.6 nota). Documentar el cambio en docstring del field. | `backend/app/agent/run_state.py` | XS | [be-agent] |

### 2.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_domain_meta_stop.py` | `test_voc_verdict_serializes_round_trip` | NEW |
| `tests/test_domain_meta_stop.py` | `test_ac_verdict_requires_exactly_3_objections` — `len != 3` → `ValidationError` | NEW |
| `tests/test_domain_meta_stop.py` | `test_ac_verdict_all_answered_derived_from_objections` — LLM puede mentir; el validator lo recomputa | NEW |
| `tests/test_domain_meta_stop.py` | `test_objection_unanswered_needs_search_requires_query` (semántico, no schema; warning si falta) | NEW |
| `tests/test_domain_meta_stop.py` | `test_subclaim_origin_defaults_to_planner` — cargar dict JSON sin `origin` → instancia con `origin == "planner"` (cobertura schema-evolution para AC-16 sobre fixtures pre-BRD-26) | NEW |
| `tests/test_domain_events.py` | `test_meta_stop_verdict_event_serializes`, `test_adversarial_objections_event_serializes`, `test_directed_subclaims_event_serializes` | NEW |
| `tests/test_llm_roles.py` | `test_meta_judge_role_defaults_to_judge_pool` — sin envs → `ROLE_CONFIGS[META_JUDGE].models == ROLE_CONFIGS[JUDGE].models` | NEW |
| `tests/test_llm_roles.py` | `test_meta_judge_env_override_anthropic` — `META_JUDGE_PROVIDER=anthropic` + `META_JUDGE_MODEL_anthropic="claude-sonnet-4-6"` → `models == ("claude-sonnet-4-6",)` (BRD AC-11 verbatim) | NEW |
| `tests/test_meta_judge_voc.py` | `test_voc_prompt_includes_required_state_fields` (S_effective, lane, rounds, last judge verdict) — nombre alineado con BRD §8 | NEW |
| `tests/test_llm_prompts_meta_judge.py` | `test_ac_prompt_demands_three_objections_explicit` (string assertion sobre el system prompt) | NEW |

### 2.4 Acceptance criteria

- `ruff` + `pyright strict` limpios.
- `pytest backend/tests/test_domain_meta_stop.py backend/tests/test_domain_events.py backend/tests/test_llm_roles.py backend/tests/test_llm_prompts_meta_judge.py -q` → all green.
- `from app.domain.meta_stop import ValueOfContinuationVerdict, Objection, AdversarialCompletenessVerdict` funciona.
- `from app.llm.roles import LLMRole; LLMRole.META_JUDGE in ROLE_CONFIGS` → `True`.
- Ningún test existente regresiona (importa por nombre, no por enum reorder).
- `python scripts/export_types.py` produce los 3 events en `frontend/src/types/events.ts` (deferred al Phase E para commit en el mismo PR, pero ejecutable ya).

---

## 3. Phase B — Stopping signals + conversion task

### 3.1 Goal

Implementar los dos `StoppingSignal` plugins (puros, sin orchestrator) y la función pura `objections_to_subclaims`. Quedan disponibles para que la fase C los conecte.

### 3.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-26-B-01** | Crear `app/stopping/signals/meta_judge_voc.py` con `class ValueOfContinuationSignal: name = "MetaJudgeVoC"; priority = 45` (entre `JudgeSignal` @ 40 y antes de cualquier hard-cap signal). Método principal `async def evaluate_with_state(state: RunState, hook: Literal["after_judge","after_react_observation","after_cove"]) -> tuple[ValueOfContinuationVerdict, MetaStopVerdictEvent]`. Internamente: (1) llama `llm.call(LLMRole.META_JUDGE, build_voc_user_prompt(state, last_judge), response_model=ValueOfContinuationVerdict)`; (2) aplica las 3 reglas de saneamiento (BRD §4.6 paso 3): si `next_action_hypothesis is None` → forzar `decision="stop_best_effort"`, si `expected_delta_s < 0.03` → forzar `decision="stop_best_effort"`; (3) construye `MetaStopVerdictEvent`; (4) incrementa `state.meta_judge_calls`. **No** muta `stop_reason` — eso es responsabilidad del orchestrator. Sigue el patrón de `NoProgressSignal.check_no_progress` (no-DEFER en `evaluate(StopContext)`, función helper que toma `RunState`). | `backend/app/stopping/signals/meta_judge_voc.py` | L | [be-stopping] |
| **T-26-B-02** | Crear `app/stopping/signals/meta_judge_adversarial.py::AdversarialCompletenessSignal { priority = 46 }` con `async def evaluate_with_state(state, draft) -> tuple[AdversarialCompletenessVerdict, AdversarialObjectionsGeneratedEvent]`. Llama `llm.call(LLMRole.META_JUDGE, build_ac_user_prompt(...), response_model=AdversarialCompletenessVerdict)`. Recomputa `all_answered = all(o.status == "answered_by_evidence" for o in objections)` (no confiar en LLM). Incrementa `state.meta_judge_calls`. | `backend/app/stopping/signals/meta_judge_adversarial.py` | M | [be-stopping] |
| **T-26-B-03** | En ambos signals: wrap `llm.call` con manejo de error específico. (a) `InstructorRetryException` (instructor agotó sus reintentos) → devolver fallback synthesized: `ValueOfContinuationVerdict(decision="stop_best_effort", expected_delta_s=0.0, next_action_hypothesis=None, reason="meta_judge_unparseable")`. (b) `LLMProviderQuotaExhausted` → fallback con `reason="meta_judge_quota_exhausted"`, **sin** retry (NFR-26-05). Loggar con structlog. **Pasar `max_retries=1` explícito a `llm.call` para `LLMRole.META_JUDGE`** (BRD AC-13: "one retry, then fall through") — el client ya acepta `max_retries`; documentar este override en docstring del signal. | `backend/app/stopping/signals/meta_judge_voc.py`, `backend/app/stopping/signals/meta_judge_adversarial.py` | M | [be-stopping] |
| **T-26-B-04** | Registrar ambos signals en `app/stopping/signals/__init__.py` (`__all__` + import). Mantener orden de `priority` consistente con el resto de signals: **Honest=10, Budget=20, NoProgress=30, Coverage=30, Agreement=35, Judge=40, VoC=45, AC=46** (8 signals en total post-merge). | `backend/app/stopping/signals/__init__.py` | XS | [be-stopping] |
| **T-26-B-05** | Crear `app/agent/tasks/objections_to_subclaims.py::def convert(objections: list[Objection], state: RunState) -> tuple[list[SubClaim], DirectedSubclaimsFromObjectionsEvent]`. Filtra por `status == "unanswered_needs_search"`. Para cada uno crea `SubClaim(id=uuid4(), text=obj.text, search_queries=[obj.suggested_query] if obj.suggested_query else [], origin="adversarial_objection")`. Devuelve la lista nueva + el evento poblado con `source_objection_count=len(objections)` y `created_subclaim_ids=[sc.id for sc in new]`. **No** muta `state` — la mutación la hace el caller (orchestrator). | `backend/app/agent/tasks/objections_to_subclaims.py` | M | [be-agent] |
| **T-26-B-06** | En la misma `objections_to_subclaims.py`, añadir `def route_objections_to_hypotheses(objections, state, *, token_overlap_threshold=0.5) -> tuple[list[Objection], list[tuple[UUID, Objection]]]` que separa las objeciones que matchean por overlap de tokens ≥ 0.5 con alguna `state.hypotheses[].text` cuyo verdict == "pending", devolviendo `(objeciones_residuales, [(hypothesis_id, objection), ...])`. Usado solo en DEEP (Phase D). Función pura, sin LLM call. Heurística simple: `len(tokens_a & tokens_b) / len(tokens_a | tokens_b)` (Jaccard) sobre tokens lowercased > 3 chars. | `backend/app/agent/tasks/objections_to_subclaims.py` | M | [be-agent] |

### 3.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_returns_stop_when_judge_approved_and_threshold` (mock `llm.call` → VoC stop) | NEW |
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_forces_stop_best_effort_when_no_action` (LLM devuelve `continue` + `next_action_hypothesis=None` → output saneado a `stop_best_effort`) | NEW |
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_forces_stop_best_effort_when_delta_below_floor` (LLM devuelve `continue` + `expected_delta_s=0.01`) | NEW |
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_unparseable_falls_back` (`InstructorRetryException` → reason `meta_judge_unparseable`) | NEW |
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_max_retries_one_then_fallback` — mock `llm.call` para verificar `max_retries=1` se pasa explícitamente; segundo output malformado → fallback (cubre AC-13 literalmente) | NEW |
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_quota_exhausted_no_retry` (raise `LLMProviderQuotaExhausted`; assert single call, fallback reason) | NEW |
| `tests/test_stopping_meta_judge_voc.py` | `test_voc_signal_emits_event_with_lane_and_hook` | NEW |
| `tests/test_stopping_meta_judge_adversarial.py` | `test_ac_signal_returns_3_objections` | NEW |
| `tests/test_stopping_meta_judge_adversarial.py` | `test_ac_signal_all_answered_derived_not_trusted_from_llm` (LLM dice `all_answered=True` pero hay objeción `unanswered` → recomputado `False`) | NEW |
| `tests/test_stopping_meta_judge_adversarial.py` | `test_ac_signal_unparseable_falls_back` | NEW |
| `tests/test_stopping_meta_judge_priority.py` | `test_signal_priorities_strict_ordering_all_eight` — enumera los 8 signals reales (`HonestStopSignal`=10, `BudgetExhaustedSignal`=20, `NoProgressSignal`=30, `CoverageSignal`=30, `AgreementSignal`=35, `JudgeSignal`=40, `ValueOfContinuationSignal`=45, `AdversarialCompletenessSignal`=46) y assert que `sorted(signals, key=priority)` produce ese orden. Documenta el tie-break Coverage=30 vs NoProgress=30 (orden de registro estable). | NEW |
| `tests/test_objections_to_subclaims.py` | `test_convert_only_unanswered_needs_search` | NEW |
| `tests/test_objections_to_subclaims.py` | `test_convert_uses_suggested_query_when_present` | NEW |
| `tests/test_objections_to_subclaims.py` | `test_convert_emits_event_with_correct_counts` | NEW |
| `tests/test_objections_to_subclaims.py` | `test_route_objections_to_hypotheses_jaccard_overlap` — overlap > 0.5 → match | NEW |
| `tests/test_objections_to_subclaims.py` | `test_route_objections_jaccard_at_threshold_matches` — overlap == 0.5 → match (frontera inclusiva) | NEW |
| `tests/test_objections_to_subclaims.py` | `test_route_objections_jaccard_below_threshold_no_match` — overlap == 0.49 → cae a `convert` | NEW |
| `tests/test_objections_to_subclaims.py` | `test_route_objections_all_hypotheses_resolved_falls_through` — 0 hipótesis `pending` → todas las objeciones residuales | NEW |
| `tests/test_objections_to_subclaims.py` | `test_route_objections_skips_resolved_hypotheses` (verdict != "pending") | NEW |

### 3.4 Acceptance criteria

- Los dos signals son importables desde `app.stopping.signals` y exponen `priority` correcto.
- Mocking de `llm.call` permite testear las 4 ramas del VoC (stop / continue / stop_best_effort / fallback) sin red.
- `objections_to_subclaims.convert` es pura (no muta `state`) — verificado por test que pasa un `RunState` clon y compara igualdad post-call.
- `pyright strict` + `ruff` limpios.

---

## 4. Phase C — Orchestrator STANDARD `after_judge` hook

### 4.1 Goal

Conectar VoC + AC en el orchestrator del carril STANDARD, justo después de `_handle_judging`, **antes** del check actual de `judge_attempts >= max_judge_attempts`. Añadir el clause de FALLBACK MODE al synthesizer cuando termina por `stop_best_effort`. El símbolo del fallback se llama `draft_best_effort_fallback` (módulo-level en `app/agent/tasks/draft.py`, sin guion bajo) y ya es importado por el orchestrator en L574.

### 4.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-26-C-01** | En `orchestrator.py`, refactor mínimo de `_handle_judging`: separar (a) el judge call propiamente dicho y (b) la decisión "continúa o termina". Extraer (b) a método nuevo `_after_judge_meta_decision(judge_event: JudgeRuledEvent) -> AgentState | None` que retorna el próximo estado o `None` si ya pasó a SYNTHESIZING/terminó. | `backend/app/agent/orchestrator.py` | M | [be-agent] |
| **T-26-C-02** | Implementar `_after_judge_meta_decision` siguiendo BRD §4.6 al pie de la letra. **El threshold check usa `judge_event.final_confidence`** (que ya es `min(S_effective, J)` por construcción en `JudgeRuledEvent`, orchestrator.py L518) — NUNCA `state.last_judge_confidence` aislado, porque eso ignoraría la S y violaría RF-12 / FR-26-08. (1) **Happy path** — si `judge_event.verdict == APPROVE AND judge_event.final_confidence >= state.confidence_threshold` → `judge_confirmed`, no invocar meta-juez. (2) Invocar `ValueOfContinuationSignal.evaluate_with_state(state, hook="after_judge")`, persistir el `MetaStopVerdictEvent` vía `self.emit`. (3) Despachar por `verdict.decision`: `stop` → `judge_confirmed` si `judge_event.final_confidence >= state.confidence_threshold` sino `draft_best_effort_fallback(meta_judge_reason=verdict.reason)`; `stop_best_effort` → `draft_best_effort_fallback(meta_judge_reason=verdict.reason)`; `continue` con `expected_delta_s >= 0.03` → invocar `AdversarialCompletenessSignal`, persistir evento; si `all_answered` → `judge_confirmed`; sino → `objections_to_subclaims.convert`, append a `state.sub_claims`, emit `DirectedSubclaimsFromObjectionsEvent`, `state.judge_attempts += 1`, si `judge_attempts >= max_judge_attempts` → `draft_best_effort_fallback(meta_judge_reason="hard_cap_reached_after_meta_judge_continue")`, sino → `transition_to(ANALYZING)`. | `backend/app/agent/orchestrator.py` | XL | [be-agent] |
| **T-26-C-03** | Reemplazar el bloque actual que evalúa `judge_attempts >= max_judge_attempts` directamente con la llamada a `_after_judge_meta_decision`. El cap sigue siendo el floor: si el meta-juez dice `continue` pero `judge_attempts >= max_judge_attempts`, gana el cap (FR-26-07). | `backend/app/agent/orchestrator.py` | S | [be-agent] |
| **T-26-C-04** | Añadir parámetro `meta_judge_reason: str \| None = None` a `draft_best_effort_fallback` en `app/agent/tasks/draft.py` (módulo-level, sin guion bajo). Cuando esté presente, inyectar el clause `FALLBACK_MODE_CLAUSE_META_JUDGE` (T-26-C-05) en el prompt del synthesizer además del clause base BRD-23 §9.2. Pasar `meta_judge_reason=verdict.reason` desde todas las call sites del orchestrator que terminen por VoC. | `backend/app/agent/tasks/draft.py`, `backend/app/agent/orchestrator.py` | M | [be-agent] |
| **T-26-C-05** | En `app/llm/prompts.py` (el archivo del synthesizer), añadir constante `FALLBACK_MODE_CLAUSE_META_JUDGE: str` con el texto literal del BRD §4.8. Inyectarla en el prompt del synthesizer cuando se llama desde el fallback. La existente BRD-23 §9.2 fallback clause se mantiene; este es un override cuando `meta_judge_reason is not None`. | `backend/app/llm/prompts.py`, `backend/app/agent/tasks/draft.py` | M | [be-llm] [be-agent] |
| **T-26-C-06** | En el `Stopped` event que cierra el run vía VoC `stop_best_effort`: asegurar `stop_reason = STOPPED_BY_BUDGET`, `answer_kind = AnswerKind.BEST_EFFORT`, `stop_rationale` que cita verbatim `verdict.reason` del meta-juez (FR-26-10). Ya hay infraestructura `StopRationale` en orchestrator (línea 729) — añadir branch para esta causa. | `backend/app/agent/orchestrator.py` | S | [be-agent] |

### 4.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_orchestrator_meta_stop_flow.py` | `test_happy_path_skips_meta_judge` — judge approve + `final_confidence >= threshold` → 0 META_STOP_VERDICT events | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_happy_path_not_taken_when_j_high_but_s_low` — J=0.85, S_effective=0.55 → meta-juez SÍ se invoca (regresión para C-3 del audit; cubre RF-12 / FR-26-08) | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_voc_stop_terminates_judge_confirmed_above_threshold` | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_voc_stop_terminates_best_effort_below_threshold` | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_voc_stop_best_effort_goes_through_fallback` — verifica `stop_reason=STOPPED_BY_BUDGET`, `answer_kind=BEST_EFFORT`, `stop_rationale` contiene `verdict.reason` | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_voc_continue_below_delta_floor_treated_as_stop_best_effort` (AC-03) | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_ac_all_answered_terminates_judge_confirmed_even_below_threshold` (AC-06) | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_ac_unanswered_creates_directed_subclaims_and_re_searches` (AC-05) — verifica nuevo `SubClaim.origin=="adversarial_objection"` aparece en `state.sub_claims` | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_hard_cap_wins_over_voc_continue` (AC-07) — `judge_attempts == max_judge_attempts` y VoC sigue diciendo `continue` → fallback | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_meta_judge_event_carries_confidence_at_check` | NEW |
| `tests/test_orchestrator_meta_stop_flow.py` | `test_final_confidence_formula_unchanged_after_meta_judge` (AC-08) — replay del run; assert `final_confidence == min(S_effective, J)`, `expected_delta_s` no aparece en el cómputo | NEW |
| `tests/test_meta_judge_replay_determinism.py` | `test_resume_with_meta_judge_events_invokes_zero_llm_calls` (AC-09) — `_fold_events` reconstruye sin invocar `llm.call` | NEW |
| `tests/test_meta_judge_replay_determinism.py` | `test_golden_traces_pre_brd26_replay_byte_identical` (AC-16) — todas las trazas en `tests/fixtures/runs/` pre-BRD-26 replay sin cambios | NEW |

### 4.4 Acceptance criteria

- Un run STANDARD sintético con judge rechazado emite exactamente 1 `MetaStopVerdictEvent(hook="after_judge")` por ronda no-happy-path.
- FAST happy-path runs siguen emitiendo 0 eventos meta-juez (FR-26-12).
- Todos los tests existentes de `test_agent_orchestrator_*.py` siguen verdes (sin regresiones por el refactor de `_handle_judging`).
- `pyright strict` + `ruff` limpios.

---

## 5. Phase D — DEEP hooks (`after_react_observation` + `after_cove`) + hypothesis routing

### 5.1 Goal

Insertar el meta-juez en los dos puntos de decisión del carril DEEP: tras cada `AgentObservation` dentro de `run_react_loop`, y tras el pase de CoVe. Cuando AC produce objeciones que matchean (Jaccard ≥ 0.5) con hipótesis `pending`, rutearlas al ReAct loop como `evaluate_hypothesis` targets en vez de crear nuevos `SubClaim`.

### 5.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-26-D-01** | En `app/agent/react/loop.py::run_react_loop`, después de emitir cada `AgentObservationEvent`, llamar a `ValueOfContinuationSignal.evaluate_with_state(state, hook="after_react_observation")`. Despacho: `stop` con threshold ok → break loop, retorna el outcome existente de "forced synth" del loop (verificar el tipo de retorno real de `run_react_loop` antes de implementar; el plan **no** introduce strings nuevos — reusa el outcome que ya usa el cap por `max_react_steps`); `stop_best_effort` → break loop, retorna `StopReason.STOPPED_BY_BUDGET` con `meta_judge_reason` propagado vía atributo en el outcome; `continue` + `expected_delta_s >= 0.03` → AC pass (siguiente task). El cap `max_react_steps` sigue siendo floor; cuando el meta-juez dice `stop` mid-loop, **NO** se incrementa `react_step_count` (BRD §4.7). | `backend/app/agent/react/loop.py` | L | [be-agent] |
| **T-26-D-02** | En `run_react_loop`, cuando VoC dice `continue` + delta OK, invocar `AdversarialCompletenessSignal`. Si `all_answered` → break loop, transita a SYNTHESIZING (decisión análoga a `judge_confirmed`); sino → llamar `route_objections_to_hypotheses` primero (T-26-B-06); las objeciones ruteadas se inyectan como acciones `evaluate_hypothesis(hypothesis_id, target=objection.text)` en el siguiente step; las residuales pasan por `objections_to_subclaims.convert` y se añaden a `state.sub_claims`. | `backend/app/agent/react/loop.py` | XL | [be-agent] |
| **T-26-D-03** | En `app/agent/lanes/deep.py::execute_deep_lane`, después del bloque CoVe (`cove_redraft` o aceptación), insertar hook `after_cove`: invocar VoC; mismo despacho que C-02 pero sin la rama "judge_confirmed by happy path" (CoVe no aprueba; el judge se llama después). | `backend/app/agent/lanes/deep.py` | M | [be-agent] |
| **T-26-D-04** | Asegurar que los `MetaStopVerdictEvent` en DEEP llevan `lane=Lane.DEEP` y el `hook` correcto (`after_react_observation` o `after_cove`). | `backend/app/agent/react/loop.py`, `backend/app/agent/lanes/deep.py` | XS | [be-agent] |
| **T-26-D-05** | Cuando DEEP termina vía VoC `stop_best_effort`, propagar `meta_judge_reason` al synthesizer del DEEP draft path (igual que C-04, C-05, C-06). | `backend/app/agent/lanes/deep.py`, `backend/app/agent/tasks/cove.py` | M | [be-agent] |

### 5.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_react_loop_meta_judge.py` | `test_voc_stop_mid_loop_does_not_advance_step_count` (BRD §4.7) | NEW |
| `tests/test_react_loop_meta_judge.py` | `test_voc_continue_invokes_ac_when_delta_above_floor` | NEW |
| `tests/test_react_loop_meta_judge.py` | `test_ac_objections_route_to_pending_hypotheses` — Jaccard match → siguiente step ejecuta `evaluate_hypothesis` con el target de la objection | NEW |
| `tests/test_react_loop_meta_judge.py` | `test_ac_unmatched_objections_become_subclaims` | NEW |
| `tests/test_react_loop_meta_judge.py` | `test_max_react_steps_cap_wins_over_voc_continue` | NEW |
| `tests/test_react_loop_meta_judge.py` | `test_meta_judge_event_lane_is_deep` | NEW |
| `tests/test_agent_lanes_deep.py` | `test_cove_meta_judge_hook_fires_after_redraft_decision` (NEW test in existing file) | EXTEND |
| `tests/test_agent_lanes_deep.py` | `test_cove_meta_judge_stop_best_effort_uses_fallback_clause` | EXTEND |
| `tests/test_agent_lanes_fast_no_meta_judge.py` | `test_fast_lane_never_emits_meta_judge_events` (AC-12, BRD FR-26-12) — archivo dedicado por requerimiento BRD §8 | NEW |

### 5.4 Acceptance criteria

- DEEP runs con hipótesis `pending` y objeción matcheada → 0 `SubClaim` nuevos, 1 `evaluate_hypothesis` ruteado.
- FAST runs (incluso escalados desde FAST a STANDARD) → 0 `MetaStopVerdictEvent` desde la porción FAST (la STANDARD sí emite).
- `max_react_steps=8` sigue siendo invariante absoluto; test de invariante pasa.

---

## 6. Phase E — FE types export + trace renderer

### 6.1 Goal

Exportar los 3 eventos al frontend y renderizarlos en el trace panel (RF-13 trust surface). Sin lógica de negocio nueva — sólo UI.

### 6.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-26-E-01** | Ejecutar `python scripts/export_types.py`. Verificar diff: aparecen `MetaStopVerdictEvent`, `AdversarialObjectionsGeneratedEvent`, `DirectedSubclaimsFromObjectionsEvent` en `frontend/src/types/events.ts`. Commit en el mismo PR. CI check verifica que un re-run produce diff vacío (AC-15). | `frontend/src/types/events.ts` | XS | [fe-types] |
| **T-26-E-02** | En `frontend/src/lib/eventLabels.ts`, añadir labels para los 3 eventos: `MetaStopVerdict: "Meta-judge verdict"`, `AdversarialObjectionsGenerated: "Skeptic objections"`, `DirectedSubclaimsFromObjections: "Directed follow-ups from objections"`. Añadir entries en `getEventNarrative` con narrativas concisas que citen `verdict.reason` o el conteo de objeciones answered/unanswered. | `frontend/src/lib/eventLabels.ts` | M | [fe-ui] |
| **T-26-E-03** | En `TraceTimeline.tsx`, añadir 3 nuevos casos en `summaryOf` y `EVENT_VISUALS` (o equivalente): (a) `MetaStopVerdict` → badge con `decision` + `expected_delta_s`; collapsible con `reason` y `next_action_hypothesis`; (b) `AdversarialObjectionsGenerated` → lista numerada de las 3 objeciones con chip color-coded por `status` (verde=answered, ámbar=needs_search, gris=no_search_possible); (c) `DirectedSubclaimsFromObjections` → nota inline "N follow-ups created from skeptic objections". | `frontend/src/components/organisms/TraceTimeline.tsx` | L | [fe-ui] |
| **T-26-E-04** | En `RunFeed.tsx::mapStepToView`, branch para `MetaStopVerdict` en el live feed: ícono balanza + label "Meta-judge: {decision}". `AdversarialObjections` colapsado por default. | `frontend/src/components/organisms/RunFeed.tsx` | M | [fe-ui] |
| **T-26-E-05** | Tests Vitest para los 3 eventos en `TraceTimeline.test.tsx`, `eventLabels.test.ts`, `RunFeed.test.tsx` (snapshot + assertion sobre microcopy literal). | `frontend/src/components/organisms/TraceTimeline.test.tsx`, `frontend/src/lib/eventLabels.test.ts` | M | [fe-test] |

### 6.3 Acceptance criteria

- `python scripts/export_types.py` produce diff vacío en una segunda corrida (CI gate, AC-15).
- Vitest verde para los 3 archivos de test nuevos.
- `npm run typecheck` y `npm run lint` limpios.
- Manual smoke: una run STANDARD con judge rechazado muestra el `MetaStopVerdict` y `AdversarialObjections` en el trace panel.

---

## 7. Cross-cutting work

### 7.1 Golden traces

Crear dos fixtures nuevas en `backend/tests/fixtures/runs/`:

- `2026-05-28-meta-judge-saturation.jsonl` — STANDARD volatile, VoC corta en ronda 1 con `stop_best_effort`.
- `2026-05-28-meta-judge-objection-driven.jsonl` — STANDARD, AC produce 1 `unanswered_needs_search`, ronda dirigida encuentra evidencia, judge approve.

Ambos consumidos por `test_meta_judge_replay_determinism.py` (Phase C).

### 7.2 Telemetría

- `meta_judge_calls_per_run` (NFR-26-01) — campo `state.meta_judge_calls` ya añadido en T-26-A-09; emitir métrica vía structlog en `Stopped` event handler.
- Alerta en SQL telemetry script (extiende `scripts/lane_telemetry.sql`): `WHERE meta_judge_calls > max_judge_attempts * 1.5` → indicio de runaway.

### 7.3 Memory bank updates

Después de cada fase registrar en `.github/memory-bank/logs/decisions-history.md`. **Reservar los IDs (consultar el último `D-XXX` en main antes de mergear Phase A)** para evitar colisiones:

- **D-{next}** (Phase A) — *"`META_JUDGE` role honra el esquema env del BRD (`META_JUDGE_PROVIDER` + `META_JUDGE_MODEL_<provider>`) y a la vez cae al pool del JUDGE cuando no hay envs; resolución en `ROLE_CONFIGS[META_JUDGE]`."*
- **D-{next+1}** (Phase A) — *"`max_judge_attempts` sube de 3 a 5 con la introducción del meta-juez como criterio primario de stop."*
- **D-{next+2}** (Phase A) — *"Nuevos prompts viven en paquete `app/llm/meta_judge_prompts/` para no colisionar con el módulo `app/llm/prompts.py`."*
- **D-{next+3}** (Phase B) — *"Recomputamos `all_answered` server-side en vez de confiar en el LLM (defensa-en-profundidad)."*
- **D-{next+4}** (Phase C) — *"Happy-path threshold usa `judge_event.final_confidence` (`= min(S, J)`), nunca `last_judge_confidence` aislado, para no violar RF-12."*
- **D-{next+5}** (Phase D) — *"Hypothesis routing usa Jaccard sobre tokens > 3 chars con umbral inclusivo ≥ 0.5 — heurística sin embeddings, alineada con la regla 'no-vector-DB en V1'."*

### 7.4 Doc updates (PR separado, no parte de este IP)

Como nota el BRD §2: `advanced-ai-research.md` §7 necesita un §7.6 nuevo describiendo VoC + AC; `stopping-signal-analysis.md` necesita meta-juez en la tabla de prioridades. **Estos doc updates NO bloquean la implementación**, pero deben listarse en el PR description del IP-26.

---

## 8. Sequencing & rollout

1. **Phase A** primero, end-to-end mergeable solo (cero comportamiento nuevo, solo símbolos disponibles).
2. **Phase B** segundo, también mergeable solo (signals importables, no invocados).
3. **Phase C** activa el comportamiento en STANDARD. Tras merge, observar `meta_judge_calls_per_run` y `stop_rationale` distribution durante 48h en prod antes de C-promote-DEEP.
4. **Phase D** activa DEEP. Más sensible (más calls/run). Si NFR-26-01 se viola, rollback de Phase D dejando A/B/C activos.
5. **Phase E** (FE) puede hacerse en paralelo con C/D una vez que los tipos están exportados.

Cada fase es una PR atómica, con todos sus tests verdes y `pyright strict` + `ruff` limpios.

---

## 9. Success metrics (tracking post-rollout)

Re-itera los del BRD §10 — el plan no añade objetivos nuevos. La telemetría queda lista en T-26-A-09 + 7.2.

| Metric | Target |
|---|---|
| STANDARD p50 saturated | ≤ 90 s (−25 % vs IP-25 baseline) |
| `judge_confirmed` rate en borderline | ≥ 70 % (+15 pp) |
| `stopped_by_budget` con reason epistémica (no cap) | ≥ 60 % |
| Mean `meta_judge_calls_per_run` (STANDARD) | ≤ 3 |
| Replay determinism (golden traces) | 100 % |

---

## 10. Files inventory

**Nuevos (10 producción + 11 test + 2 fixtures = 23):**

Producción:
- `backend/app/domain/meta_stop.py`
- `backend/app/llm/meta_judge_prompts/__init__.py`
- `backend/app/llm/meta_judge_prompts/voc.py`
- `backend/app/llm/meta_judge_prompts/adversarial.py`
- `backend/app/stopping/signals/meta_judge_voc.py`
- `backend/app/stopping/signals/meta_judge_adversarial.py`
- `backend/app/agent/tasks/objections_to_subclaims.py`

Tests:
- `backend/tests/test_domain_meta_stop.py`
- `backend/tests/test_meta_judge_voc.py` (alineado con BRD §8)
- `backend/tests/test_meta_judge_adversarial.py` (alineado con BRD §8)
- `backend/tests/test_stopping_meta_judge_voc.py`
- `backend/tests/test_stopping_meta_judge_adversarial.py`
- `backend/tests/test_stopping_meta_judge_priority.py`
- `backend/tests/test_objections_to_subclaims.py`
- `backend/tests/test_orchestrator_meta_stop_flow.py` (alineado con BRD §8)
- `backend/tests/test_meta_judge_replay_determinism.py`
- `backend/tests/test_react_loop_meta_judge.py`
- `backend/tests/test_agent_lanes_fast_no_meta_judge.py` (alineado con BRD §8)

Fixtures:
- `backend/tests/fixtures/runs/2026-05-28-meta-judge-saturation.jsonl`
- `backend/tests/fixtures/runs/2026-05-28-meta-judge-objection-driven.jsonl`

**Modificados (15):**

- `backend/app/domain/enums.py` (+3 EventType)
- `backend/app/domain/events.py` (+3 event classes + union update)
- `backend/app/llm/roles.py` (+META_JUDGE entry)
- `backend/app/llm/prompts.py` (+`FALLBACK_MODE_CLAUSE_META_JUDGE` constant)
- `backend/app/config.py` (+`META_JUDGE_PROVIDER`/`META_JUDGE_MODEL_<provider>` envs per BRD AC-11)
- `backend/app/agent/run_state.py` (+`meta_judge_calls`, +`SubClaim.origin`, `max_judge_attempts` default 3→5)
- `backend/app/agent/orchestrator.py` (refactor `_handle_judging`, new `_after_judge_meta_decision`, `Stopped` rationale branch)
- `backend/app/agent/tasks/draft.py` (`draft_best_effort_fallback` acepta `meta_judge_reason`)
- `backend/app/agent/lanes/deep.py` (after_cove hook)
- `backend/app/agent/react/loop.py` (after_react_observation hook + AC routing)
- `backend/app/agent/tasks/cove.py` (propagate `meta_judge_reason` on fallback)
- `backend/app/stopping/signals/__init__.py` (register VoC + AC)
- `backend/tests/test_agent_lanes_deep.py` (+2 tests)
- `backend/tests/test_domain_events.py` (+3 serialization tests)
- `backend/tests/test_llm_roles.py` (+2 META_JUDGE tests)
- `frontend/src/types/events.ts` (regenerated)
- `frontend/src/lib/eventLabels.ts` (+3 labels)
- `frontend/src/components/organisms/TraceTimeline.tsx` (+3 cases)
- `frontend/src/components/organisms/RunFeed.tsx` (+1 branch)
- `frontend/src/components/organisms/TraceTimeline.test.tsx` (+3 tests)
- `frontend/src/lib/eventLabels.test.ts` (+3 tests)

**Documentación de soporte (PR separado, fuera de scope del IP):**

- `docs/understanding-phase/advanced-ai-research.md` (§7.6 nuevo)
- `docs/understanding-phase/stopping-signal-analysis.md` (tabla de prioridades)

---

## 11. References

- BRD-26: [BRD-26-agentic-stopping-meta-judge.md](../brds/BRD-26-agentic-stopping-meta-judge.md)
- IP-25 (parent flow): [IP-25-three-lane-research-flow.md](IP-25-three-lane-research-flow.md)
- Research narrative: [advanced-ai-research.md](../../understanding-phase/advanced-ai-research.md)
- Confidence formula (unchanged): [confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- Requirements: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
