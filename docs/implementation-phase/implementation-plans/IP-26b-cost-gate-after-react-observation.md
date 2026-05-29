# Implementation Plan — IP-26b: Cost-gate para slice 3b' (`after_react_observation`)

**Plan ID:** IP-26b
**Parent BRD:** [BRD-26 §4.13](../brds/BRD-26-agentic-stopping-meta-judge.md)
**Parent IP:** [IP-26](IP-26-agentic-stopping-meta-judge.md) (Phase D dejó este hook *deferred*)
**Date:** 2026-05-28
**Author:** Plan Agent
**Complexity:** S (1 helper + 3 settings + 1 RunState field + wiring en `run_react_loop`)
**Estimated Effort:** ~1 pair-session (≤ 100 LOC producción + tests)
**Iteration:** 1
**Assumes shipped:** IP-26 fases A–E (META_JUDGE role, `maybe_run_meta_judge`, STANDARD `after_judge` y DEEP `after_cove` wired, telemetría base).

---

## 1. Plan summary

Cerrar el slice 3b' del BRD-26: habilitar el hook `after_react_observation`
dentro de `run_react_loop`, **gateado** por un predicado de coste que garantiza
≤ `max_meta_judge_calls_per_run` invocaciones del meta-juez por run DEEP
(default `4`), independientemente de cuántos pasos ReAct se ejecuten.

El hook existe en la `Literal` `MetaJudgeHook` (ya enumerado en
`app/agent/meta_judge_hook.py`) pero **nunca se invoca**: el ReAct loop sólo
termina por `max_react_steps`, `hypothesis_decisively_supported`,
`hypotheses_all_refuted` o `FinishAction`. Esta es la razón documentada de la
nota *"deferred pending cost gate"* en
[advanced-ai-research.md](../../understanding-phase/advanced-ai-research.md) §561.

### Ámbito

| Capa | Cambio |
|---|---|
| **Config** | 3 settings nuevos: `meta_judge_after_react_enabled`, `meta_judge_react_warmup_steps`, `max_meta_judge_calls_per_run`. |
| **RunState** | 1 campo nuevo: `meta_judge_calls: int = 0` (additive, schema-compatible per `extra="allow"`). |
| **Hook helper** | 1 función nueva `_cost_gate_after_react_ok(state, settings) -> bool` en `app/agent/react/loop.py` (privada al módulo). |
| **Hook helper** | 1 función `_synthetic_signal_from_react(state) -> object` que construye el duck-typed `judge_signal` que `maybe_run_meta_judge` espera. |
| **Hook wiring** | Llamada a `await maybe_run_meta_judge(state, emit, judge_signal, hook="after_react_observation")` justo tras `emit(AgentObservationEvent)` y **antes** de `evaluate_react_intra_loop`. |
| **Counter** | Incrementar `state.meta_judge_calls` en `meta_judge_hook.maybe_run_meta_judge` para que el cap sea O(1). |
| **Telemetría** | Etiqueta `hook ∈ {after_judge, after_cove, after_react_observation}` en la métrica `meta_judge_calls_per_run`. |
| **FE** | Ninguno. Los 3 event types ya están exportados desde IP-26 Phase E; sólo cambia el `hook` value, que es `Literal` open en el TS generado. |

### Reglas arquitectónicas respetadas

1. **Seam intacto.** No introduce un cuarto seam; reusa el helper `maybe_run_meta_judge` ya existente.
2. **`StopReason` enum sin cambios.** Outcomes mapean a los 3 que ya devuelve `maybe_run_meta_judge`:
   - `stop_best_effort` → break loop, propaga `StopReason.STOPPED_BY_BUDGET`.
   - `confirm` → break loop, propaga `StopReason.JUDGE_CONFIRMED`.
   - `continue` | `skipped` → fall-through al `evaluate_react_intra_loop` actual.
3. **`final_confidence = min(S_effective, J)`** intacto. El `expected_delta_s` sigue siendo decisión, no confidence (FR-26-08).
4. **Append-only.** Cero migraciones; los eventos `MetaStopVerdictEvent`/`AdversarialObjectionsGeneratedEvent` ya existen desde IP-26 Phase A.
5. **Determinismo de read.** El hook persiste el `MetaStopVerdictEvent` igual que los otros hooks; replay no re-invoca (RF-08, AC-09).
6. **Single-server.** Cero infra; solo `+0..1` `llm.call` extra por ReAct step, con cap duro.
7. **Hard cap `max_react_steps=8`** sigue siendo floor absoluto (FR-26-07).
8. **Language policy.** Identifiers, log messages, settings keys en inglés.
9. **Sin sub-agente / sin acceso a sources / sin nuevas dependencias.**

### Símbolos reales referenciados (verificados sobre `main`)

- `app.config.Settings.meta_judge_enabled` (`config.py:145`), `meta_judge_min_delta_s` (`config.py:146`).
- `app.agent.run_state.RunState.react_step_count` (línea 119), `max_react_steps: int = 8` (línea 120).
- `app.agent.meta_judge_hook.maybe_run_meta_judge`, `MetaJudgeHook = Literal["after_judge", "after_cove", "after_react_observation"]`, `MetaJudgeOutcome = Literal["stop_best_effort", "confirm", "continue", "skipped"]`.
- `app.agent.react.loop.run_react_loop(state, emit, max_steps=8) -> StopReason | Literal["forced_synth"]`.
- `app.agent.react.loop._maybe_summarize_history(state, emit)` — invocar antes de `break` para no perder la summarization que el cap original ejecuta.
- `app.stopping.react_intra_loop.evaluate_react_intra_loop(state)` — el hook va **antes** de esta llamada para que el cost gate decida primero.
- `app.domain.events.AgentObservationEvent`, `MetaStopVerdictEvent` (ya existen).
- `app.domain.enums.StopReason.STOPPED_BY_BUDGET`, `JUDGE_CONFIRMED`.

---

## 2. Phase F — Cost-gated `after_react_observation` hook

### 2.1 Goal

Activar el slice con el flag `meta_judge_after_react_enabled` en `false` por
default. La activación en prod ocurre vía env var, no por código.

### 2.2 Task list

| # | Task | File(s) | Effort | Tag |
|---|------|---------|--------|-----|
| **T-26b-F-01** | Añadir 3 settings a `Settings` en `app/config.py` justo debajo de `meta_judge_min_delta_s` (línea 146): `meta_judge_after_react_enabled: bool = False`, `meta_judge_react_warmup_steps: int = 2`, `max_meta_judge_calls_per_run: int = 4`. Comentarios en inglés citando BRD-26 §4.13. | `backend/app/config.py` | XS | [be-config] |
| **T-26b-F-02** | Añadir `meta_judge_calls: int = 0` en `RunState` (junto a `react_step_count`, línea 119-120). Field additive — no migration. Verificar que `RunState.model_dump()` lo incluye sin romper tests existentes. | `backend/app/agent/run_state.py` | XS | [be-domain] |
| **T-26b-F-03** | En `app/agent/meta_judge_hook.py::maybe_run_meta_judge`, justo después de emitir `MetaStopVerdictEvent`, incrementar `state.meta_judge_calls += 1`. Único punto de incremento — todos los hooks (after_judge, after_cove, after_react_observation) pasan por aquí. | `backend/app/agent/meta_judge_hook.py` | XS | [be-agent] |
| **T-26b-F-04** | En `app/agent/react/loop.py`, añadir helper privado `_cost_gate_after_react_ok(state, settings) -> bool` que devuelve `True` sii todas las condiciones del BRD §4.13 se cumplen: `settings.meta_judge_enabled and settings.meta_judge_after_react_enabled and state.react_step_count >= settings.meta_judge_react_warmup_steps and state.meta_judge_calls < settings.max_meta_judge_calls_per_run`. Sin side-effects. | `backend/app/agent/react/loop.py` | S | [be-agent] |
| **T-26b-F-05** | En `app/agent/react/loop.py`, añadir helper privado `_synthetic_signal_from_react(state) -> _ReactJudgeSignal`. `_ReactJudgeSignal` es un `dataclass(frozen=True)` local al módulo con los 5 atributos que `maybe_run_meta_judge` espera (`passed: bool = False`, `structural_confidence: float`, `judge_confidence: float`, `final_confidence: float`, `rationale: str`). Valores: `structural_confidence = state.last_structural_confidence or 0.0`, `judge_confidence = state.last_judge_confidence or 0.0`, `final_confidence = min(structural_confidence, judge_confidence)`, `rationale = state.react_history[-1].observation[:280] if state.react_history else "no_observations_yet"`. | `backend/app/agent/react/loop.py` | S | [be-agent] |
| **T-26b-F-06** | En `run_react_loop`, justo después del bloque `await emit(AgentObservationEvent(...))` (paso 4) y **antes** del paso 5 (`state.react_history.append`), insertar la llamada al hook **gateada**. Importante: la inserción es **después** del append a `react_history` y del `state.react_step_count = step + 1` para que el counter ya esté actualizado y el rationale incluya la observación actual. Reordenar si necesario para preservar invariantes. Lógica: ```python\nif _cost_gate_after_react_ok(state, settings):\n    outcome = await maybe_run_meta_judge(\n        state, emit, _synthetic_signal_from_react(state),\n        hook="after_react_observation",\n    )\n    if outcome == "stop_best_effort":\n        await _maybe_summarize_history(state, emit)\n        return StopReason.STOPPED_BY_BUDGET\n    if outcome == "confirm":\n        await _maybe_summarize_history(state, emit)\n        return StopReason.JUDGE_CONFIRMED\n    # "continue" / "skipped" → fall through to intra-loop signals\n```. **No** modificar `state.react_step_count` cuando el hook corta — el cap absoluto se mantiene (BRD §4.7 invariante). | `backend/app/agent/react/loop.py` | M | [be-agent] |
| **T-26b-F-07** | Importar `from app.config import settings` y `from app.agent.meta_judge_hook import maybe_run_meta_judge` en `app/agent/react/loop.py`. Verificar que no hay cycles. | `backend/app/agent/react/loop.py` | XS | [be-agent] |
| **T-26b-F-08** | Extender `scripts/lane_telemetry.sql` (si existe) con breakdown por `hook` extraído de `MetaStopVerdictEvent.payload->>'hook'`. Si el script no existe en main, registrar como follow-up en el PR description (no bloquea merge). | `scripts/lane_telemetry.sql` | XS | [ops] |

### 2.3 Test plan

| Test file | Test name | Status |
|---|---|---|
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_gate_blocks_when_global_flag_disabled` — `meta_judge_enabled=False, meta_judge_after_react_enabled=True` → 0 `MetaStopVerdictEvent` con `hook="after_react_observation"`. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_gate_blocks_when_slice_flag_disabled` (default state) — `meta_judge_enabled=True, meta_judge_after_react_enabled=False` → 0 emisiones del hook, otros hooks no afectados. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_gate_blocks_during_warmup` — `react_step_count < 2` → no llama meta-juez. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_gate_blocks_when_cap_reached` — `state.meta_judge_calls == max_meta_judge_calls_per_run` → no llama. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_cap_is_shared_across_hooks` — un run con 2 calls `after_judge` y `after_cove` previas + cap=4 → quedan 2 cupos para `after_react_observation`. Verifica con `len([e for e in events if e.type=='meta_stop_verdict' and e.hook=='after_react_observation']) <= 2`. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_worst_case_8_step_run_emits_at_most_max_calls` — mock VoC siempre `continue`, `max_react_steps=8`, cap=4 → exactamente 4 emisiones totales (incluyendo hooks no-react). | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_voc_stop_best_effort_breaks_loop_with_stopped_by_budget` — mock VoC `stop_best_effort` en step 3 → `run_react_loop` retorna `StopReason.STOPPED_BY_BUDGET`, `react_step_count == 3` (no avanza por el cut). | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_voc_confirm_breaks_loop_with_judge_confirmed` — mock pipeline VoC `continue` + AC `all_answered=True` → `StopReason.JUDGE_CONFIRMED`, summarize_history llamado. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_voc_continue_falls_through_to_intra_loop_signals` — VoC `continue` + AC no terminal → el loop sigue al `evaluate_react_intra_loop` existente. | NEW |
| `tests/test_react_loop_meta_judge_cost_gate.py` | `test_synthetic_signal_uses_last_observation_as_rationale` — assertion sobre el `MetaJudgeContext.last_judge_rationale` capturado por el spy del LLM. | NEW |
| `tests/test_meta_judge_hook.py` | `test_meta_judge_calls_counter_increments_once_per_emission` (EXTEND) — invocar `maybe_run_meta_judge` con 3 hooks distintos → `state.meta_judge_calls == 3`. | EXTEND |
| `tests/test_agent_lanes_fast_no_meta_judge.py` | `test_fast_never_emits_after_react_observation` (EXTEND, AC-12) — FAST lane no debe emitir `hook="after_react_observation"` bajo ninguna config. | EXTEND |
| `tests/test_config.py` | `test_meta_judge_cost_gate_defaults` — `after_react_enabled is False`, `warmup_steps == 2`, `max_calls_per_run == 4`. | EXTEND |
| `tests/test_run_state.py` | `test_meta_judge_calls_default_zero` y `test_meta_judge_calls_in_model_dump`. | EXTEND |

Coverage gate ≥ 80 % para los helpers nuevos (`_cost_gate_after_react_ok`, `_synthetic_signal_from_react`).

### 2.4 Acceptance criteria

- **AC-26b-01** — Con defaults (`meta_judge_after_react_enabled=False`), un run DEEP de 8 pasos emite **cero** `MetaStopVerdictEvent` con `hook="after_react_observation"`. Otros hooks no afectados.
- **AC-26b-02** — Con `meta_judge_enabled=True, meta_judge_after_react_enabled=True, max_meta_judge_calls_per_run=4`, un run DEEP sintético con VoC siempre `continue` emite ≤ 4 `MetaStopVerdictEvent` **totales** (suma de los 3 hooks), no por hook.
- **AC-26b-03** — `state.meta_judge_calls` se incrementa exactamente una vez por `MetaStopVerdictEvent` emitido, sin importar el hook.
- **AC-26b-04** — VoC `stop_best_effort` mid-loop → `run_react_loop` retorna `StopReason.STOPPED_BY_BUDGET` y `state.react_step_count` no avanza más allá del step donde se cortó.
- **AC-26b-05** — VoC `continue` + AC `all_answered=True` mid-loop → `run_react_loop` retorna `StopReason.JUDGE_CONFIRMED` y `_maybe_summarize_history` se invoca antes del return.
- **AC-26b-06** — `max_react_steps=8` sigue siendo invariante absoluto: incluso con el hook activo y VoC siempre `continue` + AC `all_answered=False`, el loop nunca ejecuta un step 9.
- **AC-26b-07** — Golden traces pre-IP-26b (cuando el flag estaba `False` o no existía) replay byte-identical (RF-08, BRD AC-16).
- **AC-26b-08** — `pyright strict` y `ruff` limpios. `npm run typecheck` sigue verde sin regenerar `frontend/src/types/events.ts` (el set de `hook` literal ya incluye el valor desde IP-26 Phase A).
- **AC-26b-09** — Telemetría: query SQL `SELECT payload->>'hook' AS hook, COUNT(*) FROM events WHERE type='meta_stop_verdict' GROUP BY hook` retorna las 3 etiquetas distintas tras activar el flag en una run DEEP.

---

## 3. Rollout

Slice 3b' se activa por env vars, no por código. Procedimiento:

1. **Merge del PR** con `meta_judge_after_react_enabled=False` (default). Cero cambio de comportamiento en prod.
2. **Shadow window (20 runs DEEP en staging)** con `meta_judge_after_react_enabled=True, max_meta_judge_calls_per_run=4`. Observar `meta_judge_calls_per_run` mean — debe quedar ≤ 3.
3. **Flip en prod** vía env var (`META_JUDGE_AFTER_REACT_ENABLED=true`) + `systemctl restart novum`. Observar 48 h.
4. **Rollback** si NFR-26-01 se viola: flip env var a `false`, restart. Cero migración a deshacer.

Defaults concretos en `.env` (a copiar al server cuando se decida activar):

```env
META_JUDGE_AFTER_REACT_ENABLED=true
META_JUDGE_REACT_WARMUP_STEPS=2
MAX_META_JUDGE_CALLS_PER_RUN=4
```

---

## 4. Files inventory

**Nuevos (1 test):**

- `backend/tests/test_react_loop_meta_judge_cost_gate.py`

**Modificados (6 producción + 4 test):**

Producción:
- `backend/app/config.py` (+3 settings)
- `backend/app/agent/run_state.py` (+`meta_judge_calls: int = 0`)
- `backend/app/agent/meta_judge_hook.py` (+`state.meta_judge_calls += 1`)
- `backend/app/agent/react/loop.py` (+2 helpers, +hook wiring, +2 imports)
- `scripts/lane_telemetry.sql` (opcional, breakdown por hook)

Tests:
- `backend/tests/test_meta_judge_hook.py` (+1 test)
- `backend/tests/test_agent_lanes_fast_no_meta_judge.py` (+1 test)
- `backend/tests/test_config.py` (+1 test)
- `backend/tests/test_run_state.py` (+2 tests)

---

## 5. Memory bank updates

Después del merge registrar en `.github/memory-bank/logs/decisions-history.md`
(reservar IDs consultando el último `D-XXX` en main):

- **D-{next}** — *"Cost gate de `after_react_observation` (slice 3b') usa
  cap **compartido** `max_meta_judge_calls_per_run=4` para los 3 hooks, no
  un cap independiente por hook. Razón: simplicidad operacional y cota
  total predecible."*
- **D-{next+1}** — *"Helper `_synthetic_signal_from_react` construye el
  `judge_signal` duck-typed desde `state.last_structural_confidence` /
  `last_judge_confidence` y la última observación. `final_confidence =
  min(S, J)` se computa local, sin tocar persistencia (RF-12 intacto)."*
- **D-{next+2}** — *"Slice 3b' arranca con `meta_judge_after_react_enabled=False`
  en prod; activación vía env var tras 20-run shadow window."*

---

## 6. References

- BRD-26 §4.13: [BRD-26 — Cost gate for after_react_observation](../brds/BRD-26-agentic-stopping-meta-judge.md#413-cost-gate-for-after_react_observation-slice-3b--design-deferred)
- Parent IP: [IP-26](IP-26-agentic-stopping-meta-judge.md)
- Deferred note: [advanced-ai-research.md §561](../../understanding-phase/advanced-ai-research.md)
- Confidence formula (unchanged): [confidence-calculation.md](../../understanding-phase/confidence-calculation.md)
- Requirements: [requirement-understanding.md](../../understanding-phase/requirement-understanding.md)
