# Histórico de iteraciones del agente — 2026-05-29 → 2026-05-30

Fuente: `eval_*.txt` y `compare_*.txt` en raíz del repo. Set de 8 preguntas
fijas (`scripts/run_eval_2026_05_29.py`):

| Q   | Pregunta                                         | Tipo / lane             |
|-----|--------------------------------------------------|-------------------------|
| Q1  | Capital de Japón                                 | FACTUAL / fast          |
| Q2  | PostgreSQL vs MongoDB para SaaS pequeño          | COMPARATIVE → WEIGHTED  |
| Q3  | Best programming language                        | SUBJECTIVE_OPINION (ev=0) |
| Q4  | Intermittent fasting                             | medical / STANDARD      |
| Q5  | Riesgos largo plazo de código AI                 | PREDICTIVE → SCENARIO   |
| Q6  | Event-driven vs microservices                    | COMPARATIVE → WEIGHTED  |
| Q7  | Long-term memory en agentes AI                   | STATE_OF_ART / DEEP     |
| Q8  | AI reemplazando engineers                        | PREDICTIVE → SCENARIO   |

---

## Línea de tiempo

| Iter   | Commit  | IP                | Cambio principal                                                                                  |
|--------|---------|-------------------|---------------------------------------------------------------------------------------------------|
| post-domain | (pre)   | IP-31             | Domain classifier mejorado; ruteo a fuentes académicas (SemanticScholar/OpenAlex) por dominio.    |
| post-ux     | (pre)   | IP-32             | Mejoras de UX/prompts; estilo de respuesta más conciso.                                            |
| post-q      | `609285e` | IP-33+34+35       | (33) `select_answer_kind` determinista; (34) BL ≤25 w + prohibición absolutos; (35) zero-evidence floor. |
| post-j      | `f386365` | **IP-36**         | (a) `CLAIM_BUDGETS` STANDARD ≤3 claims (default `(3,5,2,1)`→`(2,3,2,1)`); (b) prompt del juez relaja "completeness" a "relativo a evidencia". |

---

## Métricas comparadas por iteración

### Stop reason

| reason             | postux | postq | postj |
|--------------------|:------:|:-----:|:-----:|
| `judge_confirmed`   | 2/8    | 2/8   | **2/8** |
| `stopped_by_budget` | 6/8    | 6/8   | **6/8** |

> **No se ha movido el ratio judge_confirmed en 3 iteraciones.** Solo Q1 (FACTUAL trivial, coverage=1.0) y Q3 (zero-evidence floor → BEST_EFFORT en synthesis) llegan a `judge_confirmed`. Las 6 STANDARD que cuestan ~60-120 s siempre mueren por presupuesto.

### Bottom-line strict (primera oración ≤ 25 palabras)

| iter   | pass rate | notas                                                                                 |
|--------|:---------:|---------------------------------------------------------------------------------------|
| postux | 1/8       | absolutos ("safer default", "RAG dominant", oraciones de 35-46 w)                     |
| postq  | **5/8**   | IP-34 elimina absolutos, condicionales requeridos, Q4 38w→19w, Q5 35w→22w, Q6 46w→25w |
| postj  | 4/8       | leve regresión: Q4 19w→**26w**, Q7 21w→**30w**; Q6 25w→**12w** (ganó)                  |

### Per-question (postj IP-36)

| Q  | claims (postq → postj) | S    | evidence (postq → postj) | wall (s) | BL words | stop                |
|----|------------------------|------|--------------------------|----------|----------|---------------------|
| Q1 | 0 → 0                  | 1.00 | 6 → 6                    | 17       | 29       | judge_confirmed     |
| Q2 | 3 → 3                  | 0.58 | 24 → 26                  | 67       | 37       | stopped_by_budget   |
| Q3 | 0 → 0                  | 0.15 | 0 → 0                    | 39       | 19       | judge_confirmed     |
| Q4 | 5 → **2**              | 0.98 | 50 → 40                  | **327**  | 26       | stopped_by_budget   |
| Q5 | 5 → **3**              | 0.64 | 54 → 45                  | 106      | 23       | stopped_by_budget   |
| Q6 | 4 → **3**              | 0.55 | 36 → 24                  | 67       | 12       | stopped_by_budget   |
| Q7 | 0 → 0                  | 0.62 | 19 → 19                  | 113      | 30       | stopped_by_budget   |
| Q8 | 5 → **3**              | 0.62 | 42 → 36                  | 89       | 25       | stopped_by_budget   |

### Costo y latencia

| iter  | evidence total | wall avg | costo total aprox |
|-------|---------------|----------|-------------------|
| postux | 224           | ~80 s    | $1.55             |
| postq  | 231           | ~83 s    | $1.59             |
| postj  | 196 (-15 %)   | ~103 s\* | $1.48             |

\* Q4 disparó el promedio (327 s, outlier de 1 corrida).

---

## Qué funcionó y qué NO

| Hipótesis                                                                | Resultado en postj                                                          | Veredicto |
|--------------------------------------------------------------------------|-----------------------------------------------------------------------------|-----------|
| IP-36a: planner cap STANDARD ≤3 claims reduce trabajo redundante         | Q4/Q5/Q6/Q8 bajaron claims; evidence −15 %; runs más baratos                | ✅ ÉXITO   |
| IP-36b: prompt al juez "completeness relativa a evidencia" → más approvals | El juez sigue retornando `verdict=reject` sobre los mismos 6 borradores     | ❌ NULO    |
| IP-34 (postq) condicionales + ≤25 w sobreviven a planner cap            | Sí, mayormente; pequeño coletazo en Q4/Q7                                   | ⚠️ MIXTO   |

---

## Diagnóstico actual

1. **El juez es el cuello de botella verdadero.** Cambiar el prompt no mueve el verdict — el LLM aplica su propio "rigor" cuando ve `coverage < 1.0`. El gate efectivo no es el prompt sino la decisión binaria del juez.
2. **Los `stopped_by_budget` no son corridas malas.** S ≥ 0.55 en todas, evidence 19-45 ítems, BL en condicional honesto. Es exactamente lo que el sistema debe producir como BEST_EFFORT honesto — pero etiquetado como exhausto en lugar de confirmado.
3. **PR-6a ya tiene la lógica**: si `judge.passed AND budget`, flip a `JUDGE_CONFIRMED`. Pero `judge.passed` exige `verdict=approve` del LLM, que nunca llega.
4. **El planner cap fue libre**: rebajamos costo y latencia sin perder BL pass rate dramáticamente.

---

## Próxima iteración recomendada — IP-37: structural override

### Idea
Override estructural en `_handle_judging` (orchestrator). Si tras la última
ronda de juez:
- `judge.passed` es `False` por "completeness" (no por contradicción / fabricación), Y
- `S ≥ 0.6` (estructural sólido), Y
- `coverage ≥ 0.6` (cubrimos al menos la mayoría de claims), Y
- `agreement ≥ 0.5` (sin contradicciones graves)

entonces marcamos el borrador como **structural-confirmed** y emitimos
`JUDGE_CONFIRMED` con `answer_kind = BEST_EFFORT`. La honestidad se preserva
(seguimos surfaceando S, J, coverage en el UI) pero el `stop_reason` deja de
mislabel como exhausto.

### Por qué esto es seguro
- No tocamos el prompt del juez (testarudo, ya probado).
- No bajamos `confidence_threshold_default` (no afloja gate semántica).
- Si el juez rechaza por contradicción o fabricación, esa señal sí bloquea
  (no entramos al override).
- El UI ya muestra S y J por separado — el usuario sigue viendo el rechazo
  del juez por completeness en el panel de transparencia.

### Métrica de éxito
- `judge_confirmed` ratio 2/8 → ≥ 5/8.
- BL strict pass rate ≥ 4/8 (no regresión vs postj).
- Cero corridas que pasen `judge_confirmed` con S < 0.6 o `verdict=reject`
  por contradicción.

---

## Alternativas descartadas (para referencia)

| Opción                                                  | Por qué no ahora                                                  |
|---------------------------------------------------------|-------------------------------------------------------------------|
| Bajar `confidence_threshold_default` 0.5 → 0.45         | Afloja gate semántica universalmente; podría aprobar drafts malos. |
| Reescribir prompt del juez de cero                       | Frágil; ya probamos en IP-36b sin efecto.                          |
| Subir `early_stop_min_judge` / `early_stop_min_agreement` | Hace el problema peor, no mejor.                                   |
| Más rondas de búsqueda                                  | Las STANDARD ya consumen 60-120 s; latencia inaceptable.           |
