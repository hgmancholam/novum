@Orchestrator Ejecuta el workflow COMPLETO desde la Fase 2 hasta la Fase 5 para docs/implementation-phase/brds/BRD-22-complexity-aware-planning-and-experts.md en modo TOTALMENTE AUTÓNOMO.

═══════════════════════════════════════════════════════════════
MODO DE EJECUCIÓN: AUTÓNOMO — ZERO PREGUNTAS
═══════════════════════════════════════════════════════════════

REGLAS INNEGOCIABLES:
1. NO me hagas NINGUNA pregunta hasta que el workflow termine (éxito o escalamiento manual F6).
2. NO pidas confirmación entre fases, entre iteraciones, ni antes de delegar a subagentes.
3. NO pidas aprobación para crear/modificar archivos en `docs/implementation-phase/**` ni en `backend/**` ni en `frontend/**`.
4. NO pidas aprobación para ejecutar tests, linters, typecheckers, ni migraciones Alembic locales.
5. Asume "sí" a cualquier decisión reversible. Para decisiones IRREVERSIBLES (git push, merge, deploy, drop DB, rm -rf, force-push) → DETENTE y reporta al final.
6. Si encuentras ambigüedad en el BRD, resuélvela con la interpretación más alineada a:
   - RF-01…RF-16 (requirement-understanding.md)
   - docs/technical-phase/architecture.md
   - docs/technical-phase/ai-services.md
   - docs/understanding-phase/ui-prototype.md
   Documenta la decisión en el plan/decisions-history. NO preguntes.

═══════════════════════════════════════════════════════════════
FASES A EJECUTAR (workflow.yaml)
═══════════════════════════════════════════════════════════════

FASE 2 — Implementation Plan + Audit F2 (sub-loop, max 3 iter):
  - Genera el Implementation Plan completo (usa skill `implementation-plan`).
  - Invoca @Auditor con skill `audit-implementation-plan` (detección de blind paths).
  - Gate: score ≥ 9/10. Si < 9, itera automáticamente con el feedback (hasta 3 veces).
  - Output: docs/implementation-phase/implementation-plans/IP-22-*.md + docs/implementation-phase/audits/AUDIT-IP-22-*.md

FASE 3 — Implementación (Coder):
  - Implementa TODOS los tasks del plan en orden.
  - Aplica memory-bank/shared/project-context.md, conventions, y reglas §3 de copilot-instructions.
  - Respeta seams (Source/StoppingSignal/OutputRenderer), enum stop_reason, eventos append-only, schema extra="allow".
  - Si el plan toca tipos compartidos, regenera con `scripts/export_types.py`.

FASE 4 — Unit Tests + Review (sub-loop F3↔F4, max 5 iter):
  - Tests backend: pytest + pytest-asyncio (skill `unit-test-backend`). Coverage ≥ 80%.
  - Tests frontend (si aplica): Vitest + Testing Library + jest-axe (skill `unit-test-frontend`). Coverage ≥ 80%.
  - Ejecuta la suite COMPLETA localmente y deja la salida en la carpeta raíz como `pytest_ip22_iter<N>.txt` / `vitest_ip22_iter<N>.txt`.
  - Invoca @Reviewer. Gate: score ≥ 9/10. Si < 9, itera (max 5).
  - Output: docs/implementation-phase/unit-tests/UT-IP-22-*.md + docs/implementation-phase/reviews/REVIEW-IP-22-*.md

FASE 5 — Cierre:
  - Actualiza `.github/memory-bank/logs/decisions-history.md` y `lessons-learned.md`.
  - Actualiza `.github/memory-bank/indices/knowledge-base-index.md` con los nuevos artefactos.
  - NO hagas git commit, NO git push, NO PR — solo deja los cambios staged-ready.

═══════════════════════════════════════════════════════════════
PROTOCOLO DE MEMORIA (obligatorio antes/después de cada fase)
═══════════════════════════════════════════════════════════════
- Antes: lee project-context.md + knowledge-base-index.md + lessons-learned.md.
- Después: actualiza decisions-history.md y lessons-learned.md.

═══════════════════════════════════════════════════════════════
ESCALAMIENTO (F6) — únicas razones para detenerte y preguntarme
═══════════════════════════════════════════════════════════════
- Audit F2 sigue < 9/10 tras 3 iteraciones. Solucion: Avanza con el mejor plan generado, documenta la decisión, y reporta al final.
- Review F4 sigue < 9/10 tras 5 iteraciones. Solucion: Avanza con el mejor plan generado, documenta la decisión, y reporta al final.
- Falta una API key / secreto que no está en `.env` ni en `api_key_services.txt`.
- Conflicto real entre el BRD y un RF que no se puede resolver leyendo los docs. Solución: BRD-22-complexity-aware-planning-and-experts.md tiene la razon.

═══════════════════════════════════════════════════════════════
REPORTE FINAL (al terminar, en UN solo mensaje)
═══════════════════════════════════════════════════════════════
Incluye:
1. Score final F2 e iteraciones consumidas.
2. Score final F4 e iteraciones consumidas.
3. Lista de archivos creados/modificados (rutas relativas).
4. Resultado de tests (pass/fail, coverage backend, coverage frontend).
5. Decisiones autónomas tomadas ante ambigüedad (bullet list).
6. Próximo paso manual sugerido (commit message propuesto, no ejecutado).

EMPIEZA YA. No respondas con un plan previo — ejecuta.