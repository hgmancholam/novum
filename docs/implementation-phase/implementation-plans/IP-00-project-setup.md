# Implementation Plan: BRD-00 Project Setup

**Plan ID:** IP-00
**BRD Reference:** BRD-00-project-setup.md
**GitHub Issue:** [#1](https://github.com/hgmancholam/novum/issues/1)
**Created:** 2026-05-26
**Status:** In Progress

---

## 1. Overview

Implement the foundational project structure for Novum, creating the complete folder hierarchy, configuration files, and initial source files for both backend (Python/FastAPI) and frontend (React/Vite).

## 2. Implementation Sequence

### Phase 1: Backend Structure (Steps 1-8)

| Step | Task | Files to Create | Priority |
|------|------|-----------------|----------|
| 1 | Create backend folder structure | `backend/app/`, subdirectories | P0 |
| 2 | Create pyproject.toml | `backend/pyproject.toml` | P0 |
| 3 | Create config module | `backend/app/config.py` | P0 |
| 4 | Create main entry point | `backend/app/main.py` | P0 |
| 5 | Create database module | `backend/app/database.py` | P0 |
| 6 | Create __init__.py files | All `__init__.py` | P0 |
| 7 | Create .env.example | `backend/.env.example` | P0 |
| 8 | Initialize Alembic | `backend/alembic/` structure | P0 |

### Phase 2: Frontend Structure (Steps 9-16)

| Step | Task | Files to Create | Priority |
|------|------|-----------------|----------|
| 9 | Create frontend folder structure | `frontend/src/`, subdirectories | P0 |
| 10 | Create package.json | `frontend/package.json` | P0 |
| 11 | Create TypeScript configs | `tsconfig.json`, `tsconfig.node.json` | P0 |
| 12 | Create Vite config | `frontend/vite.config.ts` | P0 |
| 13 | Create main CSS with Tailwind v4 | `frontend/src/index.css` | P0 |
| 14 | Create React entry points | `main.tsx`, `App.tsx` | P0 |
| 15 | Create lib utilities | `utils.ts`, `constants.ts`, `api.ts`, `sse.ts` | P0 |
| 16 | Create shadcn/ui config | `components.json` | P0 |

### Phase 3: Root & Scripts (Steps 17-19)

| Step | Task | Files to Create | Priority |
|------|------|-----------------|----------|
| 17 | Update root .gitignore | `.gitignore` | P0 |
| 18 | Create type export script | `scripts/export_types.py` | P1 |
| 19 | Create dev runner script | `scripts/dev.ps1` | P1 |

## 3. Verification Criteria

### Backend Verification
- [ ] `cd backend && uv sync` completes without errors
- [ ] `pyright` passes with no errors
- [ ] `ruff check .` passes
- [ ] `uvicorn app.main:app` starts successfully
- [ ] `GET /health` returns `{"status": "ok"}`

### Frontend Verification
- [ ] `cd frontend && npm install` completes
- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] `npm run dev` starts Vite server on port 3000

## 4. Dependencies

- **Python 3.12** (must be installed)
- **Node.js 20+** (must be installed)
- **uv** (Python package manager)
- **PostgreSQL 16** (for database connection test)

## 5. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Tailwind v4 plugin syntax errors | Use `@import "tailwindcss"` per docs, NO `@tailwind` directives |
| Path alias resolution | Use `vite-tsconfig-paths` plugin |
| SQLAlchemy async driver | Ensure `asyncpg` in dependencies |

## 6. Estimated Time

- **Backend setup:** ~15 minutes
- **Frontend setup:** ~15 minutes
- **Verification:** ~10 minutes
- **Total:** ~40 minutes

---

*Created by Orchestrator Agent*
