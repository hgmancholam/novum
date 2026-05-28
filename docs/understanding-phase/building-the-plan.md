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

## Recomendación: pipeline en capas

Para un research agent en producción, **ninguna estrategia sola es óptima**. La arquitectura recomendada es combinarlas en capas:

```
                          Pregunta de usuario
                                  │
                                  ▼
                        ┌───────────────────┐
                        │     Self-Ask      │  ← Clasificar: ¿simple, estándar o compleja?
                        │     (router)      │
                        └─────────┬─────────┘
                            complexity_hint 
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
         trivial               standard                deep
            │                     │                     │
            ▼                     ▼                     ▼
   ┌────────────────┐   ┌───────────────────┐   ┌───────────────────┐
   │   Búsqueda     │   │   Decomposition   │   │  Abductive (opt)  │  ← Si la pregunta es ambigua
   │    directa     │   │  sub-claims × N   │   │   Hipótesis →     │
   │                │   │ search + análisis │   └─────────┬─────────┘
   └────────┬───────┘   └─────────┬─────────┘             │
            │                     │                       ▼
            │                     │             ┌───────────────────┐
            │                     │             │    ReAct loop     │  ← Motor principal
            │                     │             │  Reason→Act→Obs   │
            │                     │             └─────────┬─────────┘
            │                     │                       │
            │                     └───────────┬───────────┘
            │                                 ▼
            │                       ┌───────────────────┐
            │                       │   CoVe (draft)    │  ← Verificación final
            │                       │  Draft → Check →  │
            │                       │     Re-draft      │
            │                       └─────────┬─────────┘
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                     Output verificado
```

### Implementación práctica

**Capa 1 — Routing (Self-Ask):**
```python
system_prompt = """
Analiza la pregunta y clasifícala en una de tres rutas:

- "trivial":   se responde con 1 sola búsqueda factual (definiciones, fechas,
               cifras puntuales, lookups directos). No requiere síntesis.
- "standard":  pregunta factual con varios componentes verificables que se
               pueden descomponer en sub-claims independientes y paralelos
               (comparativas, agregados, multi-entidad). NO es ambigua.
- "deep":      pregunta ambigua, exploratoria, multi-hop con dependencias
               entre pasos, o cuando el siguiente paso depende del resultado
               del anterior. Requiere razonamiento adaptativo.

Responde SOLO con JSON:
{"type": "trivial"|"standard"|"deep", "reason": "..."}
"""
```

**Capa 2a — Búsqueda directa (ruta `trivial`):**
```python
# Una sola llamada, sin verificación adicional
results = search_tool(question, top_k=3)
answer = llm.answer_from_snippets(question, results)
return answer  # va directo a Output verificado
```

**Capa 2b — Decomposition + Retrieval (ruta `standard`):**
```python
# 1. Descomponer en sub-claims independientes y verificables
sub_claims = llm.decompose(question)
# Ej: para "¿Cuál fue la inflación de Colombia y México en 2024?"
#  → ["inflación Colombia 2024", "inflación México 2024"]

# 2. Buscar + analizar cada sub-claim en paralelo
async def resolve(claim: str) -> ClaimResult:
    snippets = await search_tool(claim)
    return llm.analyze(claim, snippets)

results = await asyncio.gather(*(resolve(c) for c in sub_claims))

# 3. (Opcional) Re-decomposición dinámica: detectar gaps no previstos
gaps = llm.identify_gaps(question, sub_claims, results)
if gaps:
    extra = await asyncio.gather(*(resolve(c) for c in gaps))
    results += extra

# 4. Síntesis en draft → pasa a CoVe (Capa 3)
draft = llm.synthesize(question, results)
```

**Capa 2c — ReAct loop (ruta `deep`):**
```python
# Pseudocódigo — adaptativo, secuencial
while not done:
    thought = llm.think(question, history, observations)
    action = llm.decide_action(thought)  # search | fetch | calculate | finish
    observation = execute_tool(action)
    history.append((thought, action, observation))
    done = action.type == "finish"
draft = llm.draft_from_trace(history)
```

**Capa 3 — CoVe (sólo `standard` y `deep`):**
```python
# Verificación final sobre el draft
verification_questions = llm.generate_verification_questions(draft)
# Ej: ["¿Es correcto que X sucedió en 2023?", "¿La fuente de Y es confiable?"]

for question in verification_questions:
    evidence = search_tool(question)
    if contradicts(evidence, draft):
        draft = llm.redraft(draft, contradiction=evidence)

return draft  # Output verificado
```

### Costos por ruta

Llamadas LLM aproximadas y búsquedas por query, asumiendo `N` sub-claims típicos = 3 y `V` preguntas de verificación de CoVe = 3:

| Ruta | LLM calls | Búsquedas | Latencia | Cuándo |
|---|---|---|---|---|
| `trivial` | 2 (router + answer) | 1 | Baja | Lookups directos |
| `standard` | ~3 + N + V (router + decomp + N análisis + síntesis + CoVe) | N + V | Media-baja (sub-claims en paralelo) | Preguntas factuales descomponibles |
| `deep` | router + ciclo ReAct + V (CoVe) | variable | Media-alta | Ambiguo / multi-hop / dependiente |

### Ahorro de costos estimado

Distribución típica de tráfico y costo relativo vs. correr siempre el pipeline completo (`deep + CoVe`):

| Escenario | Sin router | Con Self-Ask router (3 rutas) |
|---|---|---|
| 50% queries trivial | 100% pasan por ReAct+CoVe | 50% van a búsqueda directa (~0.1x) |
| 35% queries standard | — | 35% pasan por Decomp + CoVe (~0.5x) |
| 15% queries deep | — | 15% pasan por ReAct+CoVe (1.0x) |
| Costo relativo | 1.0x | **~0.38x** |

---

## Conclusión

Tu método actual (**Decomp + Retrieval + CoVe**) es más sofisticado que un Decomposition puro — ya tienes la verificación final que la mayoría de implementaciones básicas omite. Su puntuación real es 87/100, no 65. En la arquitectura propuesta ocupa el carril **standard**, que será el camino más usado en producción.

El gap principal respecto a ReAct no es la verificación (eso ya lo tienes con CoVe), sino la **adaptabilidad del plan**. Si durante la búsqueda de sub-claim 2 aparece un ángulo que no habías contemplado, tu pipeline no lo incorpora. La mejora más directa es añadir un paso de **re-decomposición dinámica** después del análisis de resultados, antes de la síntesis (ya incluido en la Capa 2b).

La combinación óptima para escalar sería:

- **Self-Ask** como router de 3 vías (`trivial` / `standard` / `deep`) para no correr el pipeline completo en queries que no lo requieren
- **Búsqueda directa** para lookups factuales puntuales — sin CoVe, sin descomposición
- **Tu pipeline actual** (Decomp → Retrieval → Análisis → CoVe) como camino principal `standard`
- **Re-decomposición dinámica** como paso intermedio opcional dentro de `standard` para cerrar gaps
- **Abductive Hypothesis + ReAct + CoVe** como ruta `deep` para preguntas ambiguas o multi-hop adaptativas