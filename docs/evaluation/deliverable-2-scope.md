# Entregable 2 — Working Build · Alcance

> **Fuente del requerimiento:** [docs/understanding-phase/agent-challenge-candidate.html](../understanding-phase/agent-challenge-candidate.html)
> **Estado:** definición de alcance (qué debe entregarse, no cómo).
> **Fecha límite del reto:** ≤ 1 semana después de enviar el Entregable 1 (design doc).

---

## 1. Qué pide literalmente el reto

> *"The running system plus source code. Add a short note on anything that changed from your design doc and why it changed."*

Tres piezas obligatorias:

1. **Sistema corriendo** (URL accesible al evaluador).
2. **Código fuente** (repositorio).
3. **Nota corta de cambios** respecto al design doc.

Todo lo demás de este documento es soporte para que esas tres piezas se evalúen bien en la sesión de 35 min (15 demo + 20 pair).

---

## 2. Checklist del entregable

### 2.1 Sistema corriendo (obligatorio)

- [ ] Frontend desplegado (Vercel) con URL pública.
- [ ] Backend desplegado (Hetzner/Oracle + Caddy + DuckDNS) con URL pública HTTPS.
- [ ] Login funcional por `username` (sin password — RF de auth ligera).
- [ ] Al menos un usuario seed o instrucciones claras de cómo loguearse.
- [ ] Variables de entorno productivas configuradas: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `VITE_API_URL`. (`GITHUB_TOKEN` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` son opcionales — la interfaz LLM es agnóstica al proveedor pero V1 solo activa Anthropic Claude.)
- [ ] Health-check del backend respondiendo `200`.

### 2.2 Código fuente (obligatorio)

- [ ] Repositorio público en GitHub.
- [ ] `backend/`, `frontend/`, `docs/`, `scripts/` presentes.
- [ ] `README.md` raíz con:
  - Link al **design doc** (Entregable 1).
  - Link a la **demo desplegada**.
  - Sección **"How to run locally"** (backend + frontend, 2 comandos cada uno).
  - Sección **"How to read this repo"** (mapa de carpetas + qué leer primero).
- [ ] Tests pasando en CI (o instrucciones reproducibles para correrlos).
- [ ] `.env.example` en backend y frontend (sin secretos).

### 2.3 Nota de cambios vs. design doc (obligatorio)

Archivo: `docs/evaluation/changes-from-design-doc.md`

Formato mínimo:

```markdown
## Cambios respecto al design doc

| # | Cambio | Razón | Impacto |
|---|--------|-------|---------|
| 1 | ... | ... | ... |
```

Reglas:
- Sólo cambios materiales (no typos, no renombres).
- Una línea por cambio. Máximo 1 página.
- Si nada cambió, decirlo explícitamente con una frase.

---

## 3. Artefactos de soporte (recomendados, no obligatorios por el brief)

Estos no los pide el reto, pero **se usan en la sesión de 35 min** y conviene tenerlos listos para no improvisar:

### 3.1 Demo script — `docs/evaluation/demo-script.md`

- Guion para los 15 min de demo.
- 3 preguntas de ejemplo cubriendo los 4 must-have del reto:
  - Q1: pregunta clara → termina en `judge_confirmed`.
  - Q2: pregunta ambigua o sin fuentes → termina en `honest_ambiguous` u `honest_unanswerable`.
  - Q3: pregunta con contradicción → termina en `honest_contradiction` + demo de **fork** desde un evento intermedio.
- Por cada pregunta: qué señalar en pantalla (confidence estructural, judge score, stop_reason, timeline de eventos).

### 3.2 Trust tour — `docs/evaluation/trust-tour.md`

Mapeo explícito de cómo el build cumple los 4 must-have del brief:

| Must-have del reto | Dónde se ve en la UI | Dónde vive en el código |
|---|---|---|
| 01 — Decide cuándo parar | Badge `stop_reason` + panel de confianza | `backend/app/stopping/`, `backend/app/confidence/` |
| 02 — Run inspeccionable | Timeline de eventos, panel de fuentes, narrativa | `events` table + `routes/runs.py` |
| 03 — Re-examinar / re-intentar | Botón "fork from here" en cada evento | `routes/runs.py::fork`, append-only event log |
| 04 — Realidad sucia | Estados `honest_ambiguous` / `honest_contradiction` / `honest_unanswerable` visibles | enum `stop_reason` (7 valores) |

### 3.3 Extension guide para pair session — `docs/evaluation/extension-guide.md`

Los 3 seams del proyecto y un ejemplo de extensión en ≤ 10 líneas cada uno:

- `Source` — añadir una fuente nueva (ej. arXiv).
- `StoppingSignal` — añadir una nueva señal de parada (ej. "presupuesto de tokens").
- `OutputRenderer` — añadir un formato de salida (ej. Markdown con citas APA).

Objetivo: cuando en el minuto 15 nos pidan "añade X", abrimos este doc y mostramos el seam correcto.

---

## 4. Lo que NO va en este entregable

Para evitar over-engineering (el reto explícitamente penaliza el polish vacío):

- ❌ Storybook, i18n, dark mode toggle, animaciones decorativas.
- ❌ Métricas/observabilidad (Sentry, Datadog, Prometheus).
- ❌ Docker/k8s — el build corre directo con `uv` + `npm`.
- ❌ Activación en producción de proveedores LLM adicionales (Google Gemini, OpenAI directo, GitHub Models). La capa de interfaz ya los soporta vía litellm; V1 solo habilita Anthropic Claude.
- ❌ Tests E2E (Playwright) — sólo unitarios.
- ❌ Documentación nueva fuera de las 4 carpetas existentes (`understanding-phase`, `technical-phase`, `implementation-phase`, `evaluation`).

---

## 5. Definition of Done del Entregable 2

El entregable está listo cuando un evaluador externo, leyendo sólo el `README.md` raíz, puede en menos de 5 minutos:

1. Abrir la demo desplegada y correr una pregunta hasta ver un `stop_reason`.
2. Localizar el design doc.
3. Leer la nota de cambios.
4. Clonar y correr el repo localmente.

Si cualquiera de los 4 pasos requiere preguntarme algo, el entregable no está listo.

---

## 6. Riesgos abiertos (a resolver antes de enviar)

| # | Riesgo | Mitigación propuesta |
|---|--------|----------------------|
| R1 | Deploy del backend no está confirmado | Verificar URL pública + healthcheck antes de enviar |
| R2 | `ANTHROPIC_API_KEY` con cuota / crédito agotado durante la demo | Plan B: exportar `GITHUB_TOKEN` y repuntar roles a `openai/gpt-5` o `deepseek/DeepSeek-V3-0324` en `app/llm/models.py` (interfaz agnóstica). Adicional: cache de respuestas para las 3 preguntas del demo script. |
| R3 | La nota de cambios crece sin disciplina | Limitarla a 1 página, formato tabla |
| R4 | El evaluador pide extender algo fuera de los 3 seams | Tener clara la lista de **not-seams** (planner, storage, LLM provider — este último aislado tras la interfaz agnóstica `llm.call` con 4 providers soportados) y por qué |
