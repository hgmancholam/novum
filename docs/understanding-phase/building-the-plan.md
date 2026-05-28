# Estrategias de razonamiento para Research Agents

> Comparativa técnica para elegir el método óptimo de investigación en un LLM agent.

---

## Contexto del problema

Cuando un agente recibe una pregunta de investigación, debe decidir **cómo descomponerla, ejecutarla y verificarla**. No existe una estrategia universalmente óptima — el trade-off siempre es entre efectividad, costo en llamadas LLM y latencia.

---

## Comparativa de estrategias

### 1. Decomposition / Plan-and-Solve

**Flujo:** Romper la pregunta en sub-claims independientes → ejecutar búsquedas en paralelo → sintetizar.

| Métrica | Valor |
|---|---|
| Efectividad | 65 / 100 |
| Costo LLM | Bajo (1–2 llamadas) |
| Latencia | Baja |
| Riesgo de alucinación | Medio |

**Ventajas:**
- Sub-claims se pueden ejecutar en paralelo → latencia baja
- Pipeline predecible y fácil de debuggear
- Bajo costo por query

**Desventajas:**
- No hay mecanismo de detección de errores en sub-claims
- Si una búsqueda devuelve un resultado incorrecto, el error se propaga al output final sin cuestionamiento
- No se adapta si el resultado de una búsqueda cambia el plan

**Cuándo usarlo:** Preguntas estructuradas y bien definidas donde las sub-claims son independientes entre sí.

---

### 2. ReAct (Reason → Act → Observe)

**Flujo:** Razonar el siguiente paso → ejecutar una acción (tool call) → observar el resultado → razonar de nuevo → repetir hasta tener suficiente contexto.

| Métrica | Valor |
|---|---|
| Efectividad | 82 / 100 |
| Costo LLM | Medio (3–6 llamadas típicas) |
| Latencia | Media |
| Riesgo de alucinación | Bajo |

**Ventajas:**
- Adaptativo: puede cambiar el plan a mitad de ejecución
- Cada observación informa el siguiente paso
- Estándar de facto para tool-use agents (LangChain, LlamaIndex, CrewAI lo usan por defecto)
- Self-correcting: si una búsqueda falla, el modelo lo detecta y reformula

**Desventajas:**
- Secuencial por naturaleza → latencia acumulada
- El número de llamadas LLM no está acotado
- Puede entrar en loops si el modelo no detecta que ya tiene suficiente información

**Cuándo usarlo:** Motor principal de ejecución para la mayoría de research queries. Es el estándar recomendado.

---

### 3. Chain-of-Verification (CoVe) ⭐ Top pick para calidad

**Flujo:** Generar un borrador de respuesta → el LLM genera preguntas de verificación sobre ese borrador → ejecutar búsquedas específicas para responder esas preguntas → re-draft si se detectan inconsistencias.

| Métrica | Valor |
|---|---|
| Efectividad | 90 / 100 |
| Costo LLM | Medio-alto (+1 ciclo completo) |
| Latencia | Media |
| Riesgo de alucinación | Muy bajo |

**Ventajas:**
- Diseñado específicamente para reducir alucinaciones en outputs de research
- Las preguntas de verificación son más precisas que una re-búsqueda genérica
- El modelo actúa como su propio fact-checker
- Se puede aplicar selectivamente solo al draft final (no en cada paso)

**Desventajas:**
- Añade una ronda completa de LLM + búsquedas al pipeline
- La calidad de las preguntas de verificación depende del quality del prompt

**Cuándo usarlo:** Como paso final de verificación sobre el draft, especialmente cuando el output es crítico o factual.

**Ejemplo de implementación:**
```
1. Draft: "La inflación en Colombia en 2024 fue del 5.2%"
2. Preguntas de verificación generadas:
   - "¿Cuál fue la tasa de inflación exacta en Colombia en 2024?"
   - "¿Este dato es del DANE o del Banco de la República?"
3. Búsquedas específicas para cada pregunta
4. Si hay contradicción → re-draft con los datos correctos
```

---

### 4. Self-Ask

**Flujo:** El LLM se hace sub-preguntas iterativas, responde cada una, y usa esas respuestas para llegar a la respuesta final.

| Métrica | Valor |
|---|---|
| Efectividad | 70 / 100 |
| Costo LLM | Bajo |
| Latencia | Baja |
| Riesgo de alucinación | Medio |

**Ventajas:**
- Simple de implementar
- Bueno para descomponer preguntas multi-hop ("¿Quién es el CEO de la empresa que adquirió X?")
- Bajo costo

**Desventajas:**
- No usa herramientas externas en su forma pura
- Menos robusto que ReAct para queries que requieren búsquedas reales
- Limitado por el conocimiento interno del modelo

**Cuándo usarlo:** Como clasificador/router antes de decidir si se aplica un pipeline más costoso. También para preguntas de razonamiento encadenado simples.

---

### 5. Tree-of-Thoughts (ToT)

**Flujo:** Generar múltiples hipótesis o caminos de razonamiento → evaluar cada uno → podar los que tienen menor probabilidad → profundizar en los mejores.

| Métrica | Valor |
|---|---|
| Efectividad | 85 / 100 |
| Costo LLM | Alto (N × M llamadas, donde N=ramas, M=profundidad) |
| Latencia | Alta |
| Riesgo de alucinación | Bajo |

**Ventajas:**
- Excelente para preguntas con múltiples hipótesis plausibles
- Puede explorar caminos no obvios
- Buen resultado en benchmarks de razonamiento complejo

**Desventajas:**
- Costo cuadrático con el número de ramas
- Over-kill para la mayoría de research queries en producción
- Difícil de controlar el número de llamadas LLM

**Cuándo usarlo:** Preguntas de razonamiento muy complejo con múltiples hipótesis competidoras. Raramente justificado en producción como método principal.

---

### 6. Abductive Hypothesis

**Flujo:** Dado un conjunto de observaciones o evidencia, generar las hipótesis más plausibles que explicarían esa evidencia → investigar cada hipótesis → seleccionar la mejor explicación.

| Métrica | Valor |
|---|---|
| Efectividad | 78 / 100 |
| Costo LLM | Medio |
| Latencia | Media |
| Riesgo de alucinación | Medio-bajo |

**Ventajas:**
- Ideal cuando la pregunta es exploratoria o ambigua
- Genera un plan de investigación más rico que Decomposition
- Se complementa muy bien con CoVe para validar hipótesis

**Desventajas:**
- No es un estándar implementado en frameworks populares (hay que construirlo custom)
- Calidad depende de cuán bien el modelo genera hipótesis alternativas

**Cuándo usarlo:** Preguntas exploratorias del tipo "¿por qué está pasando X?" o "¿cuáles son las posibles causas de Y?". Usarlo como paso previo al ReAct loop.

---

### 7. Debate / Multi-agent

**Flujo:** Dos instancias LLM (o más) argumentan posturas opuestas sobre la misma pregunta → una instancia arbitradora evalúa los argumentos → síntesis final.

| Métrica | Valor |
|---|---|
| Efectividad | 88 / 100 |
| Costo LLM | Muy alto (2–3x más llamadas) |
| Latencia | Alta |
| Riesgo de alucinación | Muy bajo |

**Ventajas:**
- Alta calidad para preguntas complejas con perspectivas múltiples
- El proceso de debate fuerza a justificar afirmaciones
- Muy bajo riesgo de alucinaciones que pasen sin cuestionamiento

**Desventajas:**
- 2–3x más llamadas LLM por query
- Complejidad de implementación alta
- Raramente justificado para research factual (mejor para análisis de política, ética, decisiones estratégicas)

**Cuándo usarlo:** Análisis complejos con múltiples perspectivas válidas. No recomendado como método general en producción.

---

### 8. Claim Decomposition + Retrieval + CoVe ⭐ Método actual (Giovanny)

> Conocido en literatura como **RARR** (Retrieval and Revision) o **Decompose-then-Verify**. No es un paper único sino un patrón emergente documentado en sistemas como FActScore y FactChecking pipelines.

**Flujo:**
1. Recibir la pregunta
2. LLM descompone en sub-claims independientes y verificables
3. Para cada sub-claim: búsqueda + análisis del resultado (en paralelo)
4. Síntesis de todos los resultados en un draft
5. CoVe sobre el draft final: generar preguntas de verificación → búsquedas → re-draft si hay contradicción

```
Pregunta
   │
   ▼
Decomposition ──► sub-claim 1 ──► search → análisis ──┐
                  sub-claim 2 ──► search → análisis ──┤
                  sub-claim N ──► search → análisis ──┘
                                                       │
                                               Síntesis (draft)
                                                       │
                                                      CoVe
                                                       │
                                               Output verificado
```

| Métrica | Valor |
|---|---|
| Efectividad | 87 / 100 |
| Costo LLM | Medio (decomposición + N búsquedas + CoVe) |
| Latencia | Media-baja (sub-claims en paralelo) |
| Riesgo de alucinación | Bajo |

**Ventajas:**
- Paralelizable: todas las sub-claims se pueden buscar concurrentemente → mejor latencia que ReAct
- La descomposición upfront produce un plan explícito y auditable (se puede logguear, evaluar, debuggear)
- CoVe al final captura errores que la descomposición no detectó
- Más barato que ReAct+CoVe porque no tiene el overhead del loop iterativo en la fase de ejecución
- Las sub-claims son unidades pequeñas y específicas → búsquedas más precisas que una query genérica

**Desventajas:**
- La descomposición es estática: si durante la búsqueda de sub-claim 2 aparece información que debería modificar sub-claim 3, el plan no se actualiza (a diferencia de ReAct)
- Si la descomposición inicial es mala (sub-claims mal definidas o incompletas), todo el pipeline sufre — no hay corrección de rumbo en medio
- Dependencia en la calidad del paso de decomposición: un LLM más débil aquí degrada todo lo demás
- CoVe al final puede no ser suficiente si el error viene de una sub-claim completamente omitida (no verificas lo que no sabes que falta)

**Gap vs ReAct:** ReAct puede descubrir que necesita buscar algo que no estaba en el plan original. Tu método no puede — el plan se fija al inicio.

**Gap vs CoVe puro:** CoVe solo verifica el draft, no asegura cobertura temática. Tu método es más robusto porque la descomposición fuerza cobertura sistemática de la pregunta original.

**Mejora sugerida — Dynamic Re-decomposition:**
```python
# Después de analizar los resultados de cada sub-claim,
# añadir un paso que evalúe si surgieron gaps no previstos
gaps = llm.identify_gaps(original_question, sub_claims, results)
if gaps:
    new_sub_claims = llm.decompose(gaps)
    results += parallel_search(new_sub_claims)
# Luego síntesis + CoVe normalmente
```
Esto añade una sola ronda extra de LLM call pero cierra el gap principal del método.

**Cuándo es el método óptimo:** Preguntas factuales estructuradas donde la cobertura temática importa más que la adaptabilidad. Mejor que ReAct cuando las sub-claims son bien definidas y paralelizables. Peor que ReAct cuando la pregunta es ambigua o la información de una búsqueda debe influir en las siguientes.

**Posición en el espectro:**
```
Decomposition puro ──────────────────────── ReAct puro
(estático, sin verificación)        (adaptativo, secuencial)
                        ▲
              Tu método actual
         (estático + verificación final)
```

---

## Tabla resumen

| Estrategia | Efectividad | Costo | Latencia | Hallucination | Uso recomendado |
|---|---|---|---|---|---|
| Decomposition puro | 65 | Bajo | Baja | Medio | Queries estructuradas simples, sin verificación |
| Self-Ask | 70 | Bajo | Baja | Medio | Router / clasificador de queries |
| Abductive Hypothesis | 78 | Medio | Media | Medio-bajo | Preguntas exploratorias o ambiguas |
| ReAct | 82 | Medio | Media | Bajo | Motor principal adaptativo |
| **Decomp + Retrieval + CoVe** *(actual)* | **87** | **Medio** | **Media-baja** | **Bajo** | **Preguntas factuales con cobertura sistemática** |
| Debate / Multi-agent | 88 | Muy alto | Alta | Muy bajo | Análisis con múltiples perspectivas |
| Tree-of-Thoughts | 85 | Alto | Alta | Bajo | Razonamiento con hipótesis múltiples |
| **CoVe** | **90** | **Medio+** | **Media** | **Muy bajo** | **Verificación del output final** |

---

## Propuesta de mejora para Novum: pipeline de 3 carriles

### Hallazgos verificados en el código (base real de la propuesta)

Antes de proponer cualquier cambio, se inspeccionó el código y las variables de entorno activos en producción. Los hallazgos son:

**Configuración real de modelos (provider: GitHub Models + pool de 4 PATs):**

| Rol | Modelo | Familia |
|---|---|---|
| Classifier | `meta/Llama-4-Scout-17B-16E-Instruct` | Meta Llama 4 |
| Planner | `deepseek/DeepSeek-V3-0324` | DeepSeek |
| Synthesizer | `openai/gpt-5` | OpenAI |
| Judge | `deepseek/DeepSeek-V3-0324` | DeepSeek |

El judge NO es Haiku — es DeepSeek, mismo modelo que el planner. El synthesizer es `gpt-5` (familia distinta), lo que sí proporciona independencia parcial entre síntesis y juicio. Los providers alternativos (OpenAI `gpt-5.4`, Anthropic `claude-sonnet-4-6`, Google `gemini-2.5-flash`) están configurados con API keys y el sistema ya soporta routing por rol vía env vars (`anthropic_model_judge`, `google_model_classifier`, etc.).

**Causa raíz de los 8 minutos — serial search (`app/agent/tasks/search.py`):**

El loop `execute_search_round` es completamente serial:

```python
# Código actual — serial encubierto
for claim in state.pending_claims()[:_MAX_CLAIMS_PER_ROUND]:  # ← secuencial
    for source_type in cascade:
        results = await source.search(query, ...)  # ← await bloqueante
```

Con `_MAX_CLAIMS_PER_ROUND = 5` y cada claim tomando Tavily (3–8s) + Wikipedia (1–3s) en cascada: **5 claims × 5–11s = 25–55s por ronda**. Con `max_rounds = 20`, el worst case es 1.800s. Incluso en el caso típico de 3–4 rondas: **75–220s solo en búsquedas**, sin contar LLM calls. Eso explica los 8 minutos.

**`honest_contradiction` / `honest_unanswerable` — eliminados intencionalmente:**

El enum `StopReason` tiene exactamente 4 valores: `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`. Los tres `honest_*` fueron eliminados en WP-3 como parte del refactor "always answer" — la ambigüedad y contradicción ahora se expresan como `AnswerKind.best_effort` dentro de `judge_confirmed`. No se debe reactivarlos.

---

Novum hoy corre un único pipeline lineal (Classify → Plan → Critique → Search → Analyze → Synthesize → Judge → optional Deep-fetch → Stop). El `complexity_hint` ajusta *budgets* pero **no cambia las etapas**. Esta propuesta convierte ese hint en **tres carriles arquitectónicamente distintos**, cada uno con su propia política de parada, manteniendo:

- El event log append-only (RF-03) — cada carril emite los mismos tipos de evento; solo cambia la secuencia.
- Determinabilidad de lectura (RF-08) — toda decisión de ruteo y todo stop quedan persistidos.
- Los 3 seams (`Source`, `StoppingSignal`, `OutputRenderer`) intactos.
- El judge como verificador independiente (modelo de familia distinta al synthesizer: DeepSeek vs gpt-5).

### Cómo se decide el carril (Self-Ask = el classifier actual)

**Definición operativa para este documento:** *Self-Ask* es **la tarea que determina la complejidad de la pregunta**, es decir, el paso que en Novum hoy se llama `CLASSIFYING` y que emite el evento `QuestionClassified`. Cubre las fases 1.1, 1.2 y 1.3 de `advanced-ai-research.md` y se ejecuta en **una sola llamada LLM estructurada** (no hay router LLM adicional).

La salida de Self-Ask son tres dimensiones, ya existentes en producción:

- `question_type` (1.1) — `direct`, `definitional`, `comparative`, `weighted`, `causal`, `scenario`, `best_effort`, `state_of_art`, `predictive_future`
- `complexity_hint` (1.2) — `trivial`, `standard`, `deep`
- `temporal_sensitivity` (1.3) — `static`, `slow_changing`, `volatile`, `real_time`

Con esas tres dimensiones ya en mano, **la selección del carril es lógica determinística** (sin nueva llamada LLM): se evalúa en el orquestador justo después de `CLASSIFYING`, antes de `PLANNING`, según la siguiente tabla:

| Carril | Condición |
|---|---|
| **FAST** | `complexity_hint == trivial` Y `question_type ∈ {direct, definitional}` Y `temporal_sensitivity != real_time` |
| **DEEP** | `complexity_hint == deep` Y (`question_type ∈ {causal, scenario, predictive_future, best_effort}` O ambigüedad detectada por el resolver § 1.5) |
| **STANDARD** | resto (caso por defecto — donde cae el grueso del tráfico) |

El resultado se emite como `RouteSelected` (evento nuevo, additive) con `lane`, `reason` y las tres dimensiones de Self-Ask que lo justifican. Esto preserva auditabilidad y replay sin añadir llamadas LLM al hot path: Self-Ask sigue siendo **una sola llamada LLM** y el ruteo es post-procesamiento determinístico de su salida.

### Diagrama

```
                        ┌────────────────────────────────────┐
                        │             Self-Ask               │
                        │         (CLASSIFYING fase)         │
                        │         1 LLM call → emite         │
                        │  QuestionClassified (1.1+1.2+1.3)  │
                        └─────────────────┬──────────────────┘
                                          │
                                          ▼
                        ┌────────────────────────────────────┐
                        │           RouteSelected            │  ← lógica determinística
                        │   (sobre la salida de Self-Ask)    │
                        └─────────────────┬──────────────────┘
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
       Carril FAST                  Carril STANDARD                 Carril DEEP
       (ver §FAST)                  (ver §STANDARD)                 (ver §DEEP)
            │                             │                             │
            └─────────────────────────────┴─────────────────────────────┘
                                          │
                                          ▼
                        ┌────────────────────────────────────┐
                        │       Stopping evaluator           │  ← política común
                        │       (signals + judge)            │
                        └─────────────────┬──────────────────┘
                                          ▼
                                       Stopped
```

### Composición por carril — cada paso es una estrategia identificable

Los tres carriles **no son estrategias puras**, son **pipelines compuestos**. Cada caja en los diagramas siguientes es una estrategia independiente de la tabla comparativa (§1–§8), encadenada con otras para cubrir cobertura, adaptabilidad y verificación. Esa composición **es** la robustez del modelo: cada estrategia compensa el gap de la siguiente.

#### Carril FAST — 3 estrategias en cadena

```
   ┌────────────────────────────────────┐
   │  [1] Búsqueda directa              │  ← estrategia: Decomposition puro (#1)
   │      Wikipedia + Tavily quick      │     simplificada a 1 sub-claim = la pregunta
   │      top-3 cada uno                │     Cubre: lookups factuales
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [2] Synthesizer corto             │  ← extensión propia de Novum
   │      Respuesta 1–2 frases          │     Cubre: shape del output (AnswerKind)
   │      con citas inline              │
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [3] Mini-judge schema             │  ← estrategia: CoVe degradado (#3)
   │      Valida citas + j_score        │     1 LLM call corta, no re-busca
   │      Si falla → escala a STANDARD  │     Cubre: detección de alucinación barata
   └─────────────────┬──────────────────┘
                     ▼
              Stopping evaluator
```

#### Carril STANDARD — 5 estrategias en cadena (núcleo del sistema)

```
   ┌────────────────────────────────────┐
   │  [1] Claim Decomposition           │  ← estrategia #1: Decomposition / Plan-and-Solve
   │      Plan + crítica del plan       │     Cubre: cobertura sistemática de la pregunta
   │      2–7 sub-claims                │     Gap que tiene: plan estático
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [2] Parallel Retrieval            │  ← extensión propia: 4 Sources heterogéneas
   │      Sub-claims en paralelo        │     (Tavily, Wikipedia, Semantic Scholar,
   │      por sub-claim:                │      OpenAlex) + tier de autoridad
   │      search + analyze + S parcial  │     Cubre: heterogeneidad de fuentes (RF-04)
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [3] Dynamic Re-decomposition 🆕   │  ← mejora #8 del documento
   │      "¿qué ángulos faltan?"        │     1 LLM call extra + búsquedas dirigidas
   │      1 ronda extra max             │     Cubre: gap del plan estático de [1]
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [4] Synthesis estructurada        │  ← extensión propia: AnswerKind ceiling
   │      Shape por question_type       │     Cubre: honestidad del output
   │      Citas inline                  │     (best_effort, scenario, weighted…)
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [5] CoVe vía Judge independiente  │  ← estrategia #3: CoVe
   │      Modelo distinto (Haiku)       │     implementada como verificador externo
   │      verdict + shallow_claims      │     Cubre: alucinación / cobertura insuficiente
   │      ↓ si shallow Y budget > 0     │
   │      Deep-fetch reactivo → re-judge│     Bucle reactivo: cierra gap del judge
   └─────────────────┬──────────────────┘
                     ▼
              Stopping evaluator
```

Las 5 estrategias se complementan: [1] da cobertura, [2] heterogeneidad, [3] cierra gaps no previstos, [4] honestidad del shape, [5] verificación cruzada + escalado reactivo. Quitar cualquiera de las 5 **abre un fallo concreto** que no detectarían las otras.

#### Carril DEEP — 3 estrategias en cadena (adaptativa)

```
   ┌────────────────────────────────────┐
   │  [1] Abductive Hypothesis          │  ← estrategia #6: Abductive Hypothesis
   │      2–4 hipótesis competidoras    │     Genera plan exploratorio rico
   │      cada una trackeable           │     Cubre: ambigüedad / causalidad
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [2] ReAct loop                    │  ← estrategia #2: ReAct
   │      Reason → Act → Observe        │     Adaptativo, secuencial
   │      acciones enum cerrado         │     Cubre: dependencias entre pasos
   │      cap = 8 steps                 │     Cubre: gap de [1] standard (plan estático)
   │      stopping intra-loop           │
   └─────────────────┬──────────────────┘
                     ▼
   ┌────────────────────────────────────┐
   │  [3] CoVe explícito                │  ← estrategia #3: CoVe (literal)
   │      3 preguntas de verificación   │     Re-busca por claim del draft
   │      mini-búsquedas + re-draft     │     Cubre: claims no garantizados por [1]
   │      (judge_mode = "cove")         │     (porque DEEP no tiene sub-claims upfront)
   └─────────────────┬──────────────────┘
                     ▼
              Stopping evaluator
```

#### Resumen de composición

| Carril | Estrategias compuestas | Robustez que dan |
|---|---|---|
| **FAST** | #1 (Decomposition) → Synth corto → #3 mini (CoVe degradado) | Latencia mínima + safety net por escalado |
| **STANDARD** | #1 (Decomposition) → Parallel Retrieval → mejora dinámica #8 → Synth estructurada → #3 (CoVe vía judge) + deep-fetch reactivo | **Cobertura + heterogeneidad + verificación cruzada + escalado reactivo** |
| **DEEP** | #6 (Abductive) → #2 (ReAct) → #3 (CoVe explícito) | Exploración adaptativa + verificación post-loop |

La robustez no viene de una estrategia "mágica" — viene de **encadenar estrategias cuyos gaps se cancelan mutuamente**.

#### Tabla de evaluación de resultados por carril

Efectividad en escala 0–100 (misma que la tabla comparativa). Las otras dimensiones están referidas al estado del sistema **con el fix de paralelismo de la fase 0 aplicado**.

| Ruta | Estrategias clave | Efectividad | Costo LLM | Latencia | Riesgo de alucinación | Tipo de pregunta óptimo |
|---|---|---|---|---|---|---|
| **FAST** | Decomp simplificado + mini-CoVe | **68** | Muy bajo (~2 calls) | **Muy baja (~15s)** | Medio (mini-judge cubre errores obvios; si falla escala a STANDARD) | `direct`, `definitional` + `trivial` |
| **FAST → STANDARD** (escalado) | ídem FAST + pipeline STANDARD completo | 90 | Bajo-medio | ~120s | Bajo | Cualquier trivial que el mini-judge rechace |
| **STANDARD** | Decomp paralelo + re-decomp dinámica + CoVe vía judge + deep-fetch | **90** | Medio (~8–10 calls) | **Media (~90–120s)** | **Bajo** (judge familia distinta + re-decomp cierra gaps) | `comparative`, `weighted`, `state_of_art`, `direct` complejo |
| **DEEP** | Abductive + ReAct (cap 8) + CoVe explícito | **87** | Alto (~18 calls) | Alta (~180–240s) | **Muy bajo** (CoVe claim-por-claim + tracking de hipótesis) | `causal`, `scenario`, `predictive_future`, `best_effort` ambüguo |
| **Pipeline actual (sin carriles, serial)** | Decomp + search serial + judge | 82 | Medio (~10 calls) | **Muy alta (~480s)** | Bajo-medio | Todos por igual |

> **Por qué DEEP puntua menos que STANDARD en efectividad (87 vs 90):** DEEP es más adaptativo pero paga latencia y complejidad. Para preguntas factuales estructuradas, la descomposición sistética + paralelismo de STANDARD supera la búsqueda secuencial de ReAct. DEEP gana donde STANDARD falla: preguntas donde el siguiente paso depende del anterior y no hay sub-claims independientes claros.

### Política de parada (común a los tres carriles)

Cada carril ejecuta su lógica y, al final de cada **ronda** (su unidad de progreso natural — ver más abajo), pasa por el mismo evaluador de stopping signals. Los dos disparadores mínimos exigidos:

1. **`HighConfidenceReached`** — `final_confidence = min(S_effective, J) ≥ confidence_threshold` con `J = approve`. Mapea a `stop_reason = judge_confirmed`.
2. **`HonestlyUnanswerable`** — alguno de:
   - El judge devuelve `verdict = reject` Y `max_judge_attempts` agotado → dispara `draft_best_effort_fallback`, mapea a `stop_reason = stopped_by_budget` con `answer_kind = best_effort`.
   - El evaluador detecta contradicción irreconciliable entre fuentes de tier `primary_authoritative` → `stop_reason = stopped_by_budget` con `answer_kind = best_effort` y `stop_rationale` describiendo la contradicción explícitamente.
   - El resolver de ambigüedad no puede determinar la pregunta incluso tras evidencia → `stop_reason = stopped_by_budget` con `answer_kind = best_effort`.

> **Nota sobre el enum `StopReason`:** tiene 4 valores en producción (`judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`). Los `honest_*` fueron eliminados en WP-3. La honestidad se expresa vía `answer_kind = best_effort` + `stop_rationale` descriptivo dentro de `stopped_by_budget`, no mediante enums separados.

Otros stops aceptables (sin cambios): `stopped_by_budget` con confianza intermedia, `user_cancelled`, `errored`.

**Regla maestra de parada por carril:**

| Carril | Unidad de "ronda" | Cuándo evalúa stopping |
|---|---|---|
| FAST | 1 sola pasada | Una vez, tras `mini_judge` |
| STANDARD | Una vuelta completa Search→Analyze→Synth→Judge | Tras cada `Judge` (igual que hoy) |
| DEEP | Cada step del ReAct loop O cada CoVe pass | Tras cada `AgentObservation` y tras cada re-draft del CoVe |

Esto cumple el requisito: **el agente sabe parar cuando supera el threshold de confianza, y sabe parar honestamente cuando ya no podrá responder**. Los signals son `StoppingSignal` plugins (RF-01), uniformes para los tres carriles.

#### Cortocircuitos de early-exit (evitar iteración innecesaria)

La regla anterior dice *cuándo evaluar*, pero no es suficiente para evitar el caso que importa: que el sistema **siga iterando aunque ya tenga la respuesta**. Para eso añadimos **checkpoints intra-carril** que cortocircuitan etapas posteriores cuando la evidencia ya es suficiente. Cada checkpoint es un `StoppingSignal` con prioridad alta, evaluado **antes** del siguiente paso costoso.

| Checkpoint | Carril | Dónde evalúa | Condición de corte | Qué etapas salta |
|---|---|---|---|---|
| `S_after_retrieval_high` | STANDARD | Tras [2] Parallel Retrieval, **antes** de [3] Re-decomposición | `S_raw ≥ 0.85` Y `n_sources ≥ 3` Y `C_no_conflict == 1.0` | Salta [3] Re-decomposición |
| `judge_first_pass_strong` | STANDARD | Tras [5] primer Judge, **antes** de deep-fetch | `judge.verdict == approve` Y `final_confidence ≥ threshold + 0.05` Y `shallow_claims == []` | Salta deep-fetch y re-judge |
| `hypothesis_decisively_supported` | DEEP | Dentro del ReAct loop, tras cada `AgentObservation` | 1 hipótesis con verdict `confirmed` Y `S_effective ≥ threshold` Y resto descartadas | Termina el loop sin completar `max_steps` |
| `hypotheses_all_refuted` | DEEP | Dentro del ReAct loop | Todas las hipótesis con verdict `refuted` con evidencia de tier `primary_authoritative` | Termina el loop → `honest_unanswerable` |
| `cove_no_contradictions` | DEEP | Tras primera vuelta de CoVe | 0 contradicciones detectadas Y `j_score ≥ threshold` | Salta re-draft de CoVe |
| `mini_judge_strong` | FAST | Tras [3] mini-judge | `S_effective ≥ 0.9` Y `mini_judge.ok` | (ya implícito — no escala a STANDARD) |

El **margen de seguridad** (`threshold + 0.05` en `judge_first_pass_strong`) es deliberado: solo cortocircuitamos cuando estamos *claramente* por encima del umbral, no marginalmente. Si la confianza queda en la zona ambigua (`[threshold, threshold + 0.05]`), corre el paso de verificación adicional — el costo extra vale la pena para no terminar en un score frontera.

#### Anti-loop: budgets duros además de los signals

Los cortocircuitos cubren el caso "ya tengo suficiente". Para el caso opuesto — "estoy iterando sin converger" — todos los carriles tienen **caps duros que no dependen de la confianza**:

| Cap | Valor por defecto | Aplica a | Qué hace al alcanzarse |
|---|---|---|---|
| `max_redecomposition` | 1 (`standard`), 2 (`deep`) | STANDARD | Forzar synthesis con la evidencia actual |
| `max_judge_attempts` | 2 (`standard`), 3 (`deep`) | STANDARD, DEEP | `draft_best_effort_fallback` |
| `max_deep_fetch_per_run` | 2 (`standard`), 3 (`deep`) | STANDARD, DEEP | Aceptar evidencia shallow |
| `max_react_steps` | 8 | DEEP | Forzar `Synthesize` con history actual |
| `max_cove_rounds` | 1 | DEEP | Aceptar draft sin más verificación |
| `max_tokens_total` | derivado de `complexity_hint` (§1.2) | todos | Trigger `BudgetExhaustedSignal` |
| `max_seconds_wall_clock` | 60 / 180 / 300 | todos | Mismo signal |

Los caps **no** son fallback de emergencia: son parte del contrato del carril. `stopped_by_budget` con `final_confidence` reportada es una salida normal y honesta, no un error.

#### Detector de no-convergencia (delta-confidence)

Caso particular peligroso: el carril DEEP entra en un loop donde **la confianza no sube** entre iteraciones (el agente busca, observa, pero ninguna observación mueve la aguja). Esto puede ocurrir si el modelo se obsesiona con un ángulo agotado.

Mecanismo:

```
después de cada AgentObservation (DEEP) o cada Judge (STANDARD):
    delta_S = S_effective_actual - S_effective_anterior
    if delta_S < 0.02 durante 3 rondas/steps consecutivos:
        emite NoProgressDetected
        → fuerza Synthesize con evidencia actual
        → si final_confidence < threshold → best_effort_fallback
```

Es un `StoppingSignal` adicional (`NoProgressSignal`) con prioridad media. No mata la run, la **fuerza a converger** a su mejor draft disponible. Evita el escenario "20 minutos sin progreso" que el usuario ve como bug.

#### Resumen visual del control de iteración

```
Cada checkpoint pregunta lo mismo en 3 momentos distintos:

  "¿la confianza ya es suficiente?"        →  cortocircuito + judge_confirmed
  "¿la confianza no sube hace N rondas?"   →  NoProgressDetected → forzar synth
  "¿alcancé el cap duro?"                  →  best_effort_fallback / stopped_by_budget
```

Las tres puertas son **complementarias**: la primera evita trabajo innecesario, la segunda evita estancamiento, la tercera garantiza terminación. **Un run nunca puede iterar indefinidamente** porque los caps duros son el suelo absoluto, pero en la mayoría de queries el sistema parará mucho antes vía cortocircuito.

---

### Carril FAST — preguntas factuales puntuales

**Para qué**: definiciones, datos puntuales, lookups (`"¿capital de Japón?"`, `"¿qué es CRISPR?"`).

**Flujo:**
1. **1 search** combinado (Wikipedia + Tavily sin `search_depth="advanced"`, top-3 cada uno).
2. **Synthesizer corto** — respuesta de 1–2 frases sobre snippets, con citas inline.
3. **Mini-judge estructurado** (no es el judge LLM completo — es validación schema + LLM call corta):
   - ¿Las citas existen? ¿Soportan el claim? ¿Hay contradicción evidente entre las dos fuentes?
   - Devuelve `{ok: bool, j_score: float}`.
4. **Stopping evaluator**:
   - `S_effective ≥ 0.85` Y `mini_judge.ok` → `judge_confirmed`.
   - Si no → **escala a STANDARD** (emite `LaneEscalated` y arranca decomposición). No es failure: es upgrade transparente.

**Saltos respecto al pipeline actual**: sin `CRITIQUING`, sin sub-claims, sin deep-fetch, sin re-decomposición, sin judge Haiku completo. Reduce el costo de queries triviales de ~10–15 llamadas LLM a 2.

**Coste objetivo**: 2 LLM calls + 2 searches.

---

### Carril STANDARD — preguntas factuales descomponibles (carril por defecto)

**Para qué**: comparativas, multi-entidad, agregados, state-of-art con cobertura sistemática (`"compara EDA vs microservicios síncronos"`, `"inflación de Colombia y México 2024"`).

**Flujo** (es básicamente el pipeline actual + un paso nuevo):
1. **Decomposition** en 2–7 sub-claims (existente).
2. **Plan critique** (existente — sigue activo).
3. **Búsqueda paralela** por sub-claim, con routing por `temporal_sensitivity` y tier de autoridad (existente).
4. **Analyze** + cómputo de `S_effective` (existente).
5. **🆕 Re-decomposición dinámica (1 ronda, opt-out con flag)**:
   - Nueva llamada al planner: *"¿qué ángulos relevantes no están cubiertos por las sub-claims dada la evidencia recolectada?"*
   - Si devuelve ≥ 1 gap → emite `PlanGapsDetected`, ejecuta una ronda extra de búsqueda dirigida solo para los gaps, reanaliza.
   - Cap fijo: 1 ronda extra por run (configurable, default 1).
6. **Synthesize** (existente).
7. **Judge Haiku** (existente).
8. **Stopping evaluator**:
   - `judge.verdict == approve` Y `final_confidence ≥ threshold` → `judge_confirmed`.
   - `judge.verdict == reject` Y hay `supported_but_shallow_claim_ids` Y budget de deep-fetch > 0 → escala a deep-fetch (existente), vuelve a step 4.
   - `judge.verdict == reject` Y `max_judge_attempts` agotado → `best_effort_fallback` (existente).
   - Budget total exhausto en cualquier punto → `stopped_by_budget` con la mejor evidencia disponible.

**Lo que añade vs. hoy**: solo el paso 5. Cierra el gap principal vs. ReAct (plan estático) sin meter loops.

**Coste objetivo**: ~3 + N + 1 (re-decomp) + 1 (judge) LLM calls. Marginal sobre el actual.

---

### Carril DEEP — preguntas ambiguas, causales, exploratorias o multi-hop

**Para qué**: `"¿por qué falló X?"`, `"¿qué pasaría si Y?"`, preguntas donde el siguiente paso depende del resultado anterior, ambigüedad estructural detectada por el resolver.

**Flujo:**

#### 3.1. Generación de hipótesis (abductive)
Antes del loop, el planner emite **2–4 hipótesis competidoras** que podrían explicar la pregunta (evento nuevo `HypothesesGenerated`). Cada hipótesis es trackeable y se convierte en objetivo del ReAct loop. Para `AnswerKind=scenario` cada hipótesis ya mapea a un escenario del output final.

#### 3.2. ReAct loop con guardrails duros

```python
# Esquema (no implementación)
async def react_loop(state, max_steps=8):
    history = []
    for step in range(max_steps):
        thought = await llm.think(state, history)           # event: AgentThought
        action  = await llm.decide_action(thought)          # event: AgentAction
        obs     = await execute_action(action)              # event: AgentObservation
        history.append((thought, action, obs))

        # Stopping evaluator INTRA-LOOP (clave)
        signal = await stopping_evaluator.check(state, history, step)
        if signal is not None:
            return signal                # judge_confirmed / honest_unanswerable / budget
    return BudgetExhausted()              # cap → best_effort_fallback
```

**Acciones permitidas (enum cerrado, no free-form):**
- `search(query, source_hint?)` — usa el seam `Source` existente.
- `deep_fetch(url)` — usa `Source.fetch_full`.
- `evaluate_hypothesis(hypothesis_id, verdict)` — registra confirmación/descarte de una hipótesis.
- `finish(reason)` — termina explícitamente con razón.

Cualquier otra acción → rechazada y se le pide al modelo que reformule (sin contar contra el step).

**Stopping intra-loop** evalúa en cada `AgentObservation`:
- `S_effective ≥ threshold` Y al menos 1 hipótesis con verdict `confirmed` → `judge_confirmed` (sin esperar a `finish`).
- Todas las hipótesis con verdict `refuted` → `stopped_by_budget` con `answer_kind=best_effort` (el sistema describe que investigó todas las hipótesis y ninguna se sostiene).
- 2+ hipótesis con verdicts `confirmed` y evidencia mutuamente excluyente de tier `primary_authoritative` → `stopped_by_budget` con `answer_kind=best_effort` y `stop_rationale` explicando la contradicción encontrada.
- Step counter ≥ `max_steps` → `stopped_by_budget` → `draft_best_effort_fallback`.

> **Nota:** `honest_contradiction` y `honest_unanswerable` no existen en el enum actual `StopReason` — fueron eliminados en WP-3. Todos los finales honestos se expresan como `stopped_by_budget` con `answer_kind=best_effort` y un `stop_rationale` descriptivo. El enum no cambia.

#### 3.3. CoVe explícito sobre el draft de ReAct

Aquí sí adoptamos CoVe **literal** (no solo el judge): tras `Synthesize`, una llamada extra genera 3 preguntas de verificación apuntando a los claims del draft, lanza mini-búsquedas dirigidas, re-draftea si hay contradicción. Razón: el draft de DEEP no viene de sub-claims pre-verificadas, así que la cobertura claim-por-claim no está garantizada por construcción.

CoVe reusa la fase `JUDGING` con un sub-modo (`judge_mode = "cove"`), no es una etapa FSM nueva.

**Coste objetivo**: variable, cap duro por `max_steps × 2` LLM calls + CoVe.

---

### Tabla de carriles

| Carril | Trigger | Política de parada | Verificación | Ahorro vs. hoy | Costo vs. carril DEEP |
|---|---|---|---|---|---|
| **FAST** | `trivial` + `direct`/`definitional` + `≠ real_time` | `S ≥ 0.85` Y mini-judge ok, si no escala a STANDARD | Mini-judge schema + LLM corto | **~75% menos LLM calls** en queries triviales | ~0.10x |
| **STANDARD** | resto | Judge `approve` con threshold + deep-fetch reactivo + best-effort fallback | Judge (DeepSeek-V3, familia distinta al synthesizer gpt-5) + re-decomp dinámica + echo chamber detection + query reformulation | igual + 1–2 LLM calls extra | ~0.45x |
| **DEEP** | `deep` + `causal/scenario/predictive_future/best_effort` o ambigüedad | Stopping intra-ReAct + CoVe + step cap | CoVe explícito + judge | – | 1.0x |

### Garantías invariantes (los 3 carriles las cumplen)

1. **Evento de ruteo persistido** (`RouteSelected`) → replay determinístico.
2. **El mismo enum `stop_reason`** describe el final en los tres → UI no cambia.
3. **`final_confidence` se computa igual** (`min(S_effective, J)`) → comparable entre carriles.
4. **Budgets respetados** → ningún carril puede correr sin cota.
5. **Best-effort fallback existe en los tres** → nunca se devuelve "error" cuando hay evidencia parcial honesta.

### Eventos nuevos (todos additive, schema-compatible)

| Evento | Carril | Payload mínimo |
|---|---|---|
| `RouteSelected` | todos | `lane`, `reason`, `question_type`, `complexity_hint`, `temporal_sensitivity` |
| `LaneEscalated` | FAST → STANDARD | `from_lane`, `to_lane`, `reason` |
| `PlanGapsDetected` | STANDARD | `gaps[]`, `extra_sub_claims[]` |
| `HypothesesGenerated` | DEEP | `hypotheses[]` con `id`, `text`, `priority` |
| `AgentThought` | DEEP | `step`, `thought` |
| `AgentAction` | DEEP | `step`, `action_type`, `args` |
| `AgentObservation` | DEEP | `step`, `result_summary`, `tokens` |
| `HypothesisEvaluated` | DEEP | `hypothesis_id`, `verdict`, `evidence_ids[]` |
| `VerificationQuestionsGenerated` | DEEP | `questions[]` (CoVe) |

Cero cambios destructivos en eventos existentes — solo extensiones.

---

### Distribución esperada y ahorro

**Impacto del fix de paralelismo serial (independiente de los carriles):**

El búcle `execute_search_round` serial es hoy la causa principal de latencia. Paralelizarlo con `asyncio.gather` es una corrección que aplica **antes** de implementar los carriles y que reduce la latencia de búsqueda 3–4× por sí sola:

| Escenario | Latencia de búsqueda por ronda (5 claims) | Latencia total (4 rondas típicas) |
|---|---|---|
| Hoy (serial) | 25–55s | 100–220s |
| Con `asyncio.gather` (paralelo) | 8–12s | 32–48s |
| **Ahorro absoluto** | **−17 a −43s** | **−68 a −172s** |

Esto solo ya recorta los 8 minutos actuales a ~2–3 minutos en STANDARD sin cambiar ninguna otra lógica.

**Ahorro adicional con los 3 carriles (sobre la base paralela):**

Asumiendo una distribución realista para Novum (no la del documento original, que asumía 50% trivial):

| Carril | Tráfico estimado | Costo por run (LLM calls) | Latencia típica (con paralelo) |
|---|---|---|---|
| FAST | 20% | ~2 | ~15s |
| STANDARD | 65% | ~8–10 | ~90–120s |
| DEEP | 15% | ~18 | ~180–240s |
| **Pipeline actual (sin carriles, sin paralelo)** | 100% | ~10 | **~480s (8 min)** |
| **Pipeline actual (sin carriles, con paralelo)** | 100% | ~10 | ~150–180s |
| **3 carriles + paralelo** | 100% ponderado | ~8.3 | **~110–130s mediana** |

El valor real de los carriles **no es solo costo** — es:
- **FAST**: 15s en vez de 150s para queries triviales.
- **STANDARD + re-decomposición**: cierra el gap de cobertura sin ReAct; +echo chamber detection.
- **DEEP**: hace posibles preguntas causales/exploratorias que hoy terminan en `stopped_by_budget` con `final_confidence < 0.6`.

---

### Orden de implementación

| Fase | Cambios | Sesiones | Riesgo | Impacto directo |
|---|---|---|---|---|
| **0 — CRÍTICO** | Paralelizar `execute_search_round` con `asyncio.gather` + query reformulation en baja relevancia + echo chamber penalty en `C_diversity` | 1 | Bajo — bugfix, no cambia la lógica de negocio | **−60–70% latencia de búsqueda** |
| **A** | `RouteSelected` event + tabla de ruteo determinística (telemetría — mide distribución real de tráfico sin cambiar el pipeline) | 0.5 | Bajo — solo evento nuevo | Visibilidad de qué carril se usaría |
| **B** | Re-decomposición dinámica en STANDARD (`PlanGapsDetected`, 1 ronda) + `NoProgressSignal` con ventana acumulada de 3 rondas | 1 | Bajo — aditivo | +cobertura temática, −iteraciones innecesarias |
| **C** | Carril FAST con `LaneEscalated` como safety net | 1 | Bajo — escalado a STANDARD si falla | −75% costo en queries triviales |
| **D** | Hipótesis abductiva (`HypothesesGenerated`) en planner para `best_effort`/`causal` aunque sigan en STANDARD | 0.5 | Bajo — solo prompt + evento | +riqueza en outputs ambiguos |
| **E** | Carril DEEP con ReAct loop + 7 nuevos events + cap duro | 3 | Medio — nueva sub-FSM con tests | Habilita preguntas causales/exploratorias |
| **F** | CoVe explícito (SYNTHESIZER genera preguntas, JUDGE verifica) como sub-modo del judge en DEEP | 1 | Bajo si E está estable | +accuracy en draft de DEEP |

Total: ~7.5 sesiones. **La fase 0 es obligatoria antes de todo lo demás** — es la que resuelve los 8 minutos. Las fases A–F son mejoras de calidad y arquitectura.

### Pre-requisito: medir antes de E

Antes de implementar el carril DEEP, ejecuta A+B+C+D en producción durante ≥ 1 semana e instrumenta:

```sql
SELECT
  payload->>'lane' AS lane,
  payload->>'stop_reason' AS stop_reason,
  AVG((payload->>'final_confidence')::float) AS avg_conf,
  COUNT(*) AS runs
FROM events
WHERE event_type IN ('RouteSelected', 'Stopped')
GROUP BY 1, 2
ORDER BY 1, 2;
```

Si `lane = DEEP` aporta < 10% del tráfico **o** los runs `STANDARD` con `final_confidence < threshold` son < 15%, el carril DEEP no se justifica todavía — concentra esfuerzo en mejorar STANDARD. Si > 20%, E es la mejora correcta.

---

## Conclusión

Esta propuesta convierte el `complexity_hint` actual de un simple modulador de budgets en **tres pipelines arquitectónicamente distintos**, cada uno optimizado para su clase de pregunta, todos compartiendo la misma política de parada honesta (`confidence ≥ threshold` Ó `cannot answer` reconocido explícitamente).

Lo importante:

- **Reutiliza Self-Ask** (= el classifier actual, fases 1.1 + 1.2 + 1.3) → cero llamadas LLM extra en el ruteo: la decisión del carril es lógica determinística sobre el `QuestionClassified` que Self-Ask ya emite.
- **Aditivo respecto al event log** → replay y determinabilidad intactos.
- **Mantiene el judge independiente** (DeepSeek-V3 vs gpt-5 en synthesizer — familias distintas).
- **Cierra el gap real** del pipeline actual (plan estático) por dos caminos diferentes: re-decomposición en STANDARD, ReAct en DEEP — sin frameworks externos, ambos con cap duro de iteraciones.
- **Para honestamente** vía `stopped_by_budget` con `answer_kind=best_effort` y `stop_rationale` descriptivo cuando la evidencia es contradictoria o insuficiente — usando el enum de 4 valores que existe en producción, no stop_reasons eliminados.
- **Fix de rendimiento primero (fase 0):** el paralelismo de búsquedas es una corrección urgente independiente de la arquitectura de carriles — reduce los 8 minutos actuales a ~2–3 minutos por sí solo.

El orden de implementación está diseñado para que cada fase aporte valor por sí sola y para que la decisión de invertir en el carril DEEP (que es la pieza más costosa) se tome **con datos** de producción, no a ciegas.