# BRD-00: Project Setup & Folder Structure

**Document ID:** BRD-00
**Version:** 1.1
**Status:** ✅ Implemented
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 1 of 19
**Review:** [CR-00-001](../reviews/CR-00-001-project-setup.md) — Score 9.4/10 APPROVED

---

## 1. Executive Summary

Establish the foundational project structure for Novum, including monorepo organization, tooling configuration, and development environment setup. This BRD creates the skeleton that all subsequent BRDs build upon.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| — | Infrastructure foundation | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| — | All BRDs (01-18) |

---

## 4. Technical Specification

### 4.1 File Structure

```
novum/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Pydantic Settings
│   │   ├── database.py                # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── routes/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   ├── llm/
│   │   │   └── __init__.py
│   │   ├── sources/
│   │   │   └── __init__.py
│   │   ├── agent/
│   │   │   └── __init__.py
│   │   └── seams/
│   │       └── __init__.py
│   ├── alembic/
│   │   ├── versions/
│   │   │   └── .gitkeep
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── fixtures/
│   │       └── runs/
│   │           └── .gitkeep
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── vite-env.d.ts
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui components
│   │   │   │   └── .gitkeep
│   │   │   ├── atoms/
│   │   │   │   └── .gitkeep
│   │   │   ├── molecules/
│   │   │   │   └── .gitkeep
│   │   │   ├── organisms/
│   │   │   │   └── .gitkeep
│   │   │   └── templates/
│   │   │       └── .gitkeep
│   │   ├── pages/
│   │   │   └── .gitkeep
│   │   ├── lib/
│   │   │   ├── api.ts                 # HTTP client
│   │   │   ├── sse.ts                 # EventSource wrapper
│   │   │   ├── utils.ts               # cn() helper
│   │   │   └── constants.ts
│   │   ├── stores/
│   │   │   └── .gitkeep
│   │   ├── hooks/
│   │   │   └── .gitkeep
│   │   └── types/
│   │       └── events.ts              # Generated from backend
│   ├── public/
│   │   └── .gitkeep
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── eslint.config.js
│   ├── components.json               # shadcn/ui config
│   └── .env.example
├── scripts/
│   ├── export_types.py               # Pydantic → TypeScript
│   └── dev.ps1                        # Local dev runner
├── docs/
│   └── (existing documentation)
├── .github/
│   └── (existing agents, memory-bank)
├── .gitignore
├── README.md
└── .env.example
```

### 4.2 Backend Configuration

#### pyproject.toml
```toml
[project]
name = "novum-backend"
version = "0.1.0"
description = "Novum research agent backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "orjson>=3.10.0",
    "httpx[http2]>=0.28.0",
    "litellm>=1.55.0",
    "instructor>=1.7.0",
    "tiktoken>=0.8.0",
    "tenacity>=9.0.0",
    "tavily-python>=0.5.0",
    "wikipedia-api>=0.7.0",
    "sse-starlette>=2.2.0",
    "structlog>=24.4.0",
    "anyio>=4.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-httpx>=0.35.0",
    "pytest-postgresql>=6.1.0",
    "ruff>=0.8.0",
    "pyright>=1.1.390",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "TCH"]
ignore = ["E501"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
reportMissingImports = true
reportMissingTypeStubs = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### backend/app/config.py
```python
"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/novum"

    # LLM (provider-agnostic interface via litellm; V1 active provider = Anthropic Claude)
    anthropic_api_key: str
    # Optional fallback providers (wired but disabled in V1)
    github_token: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    llm_model_classifier: str = "anthropic/claude-haiku-4-5"
    llm_model_planner: str = "anthropic/claude-sonnet-4-6"
    llm_model_synthesizer: str = "anthropic/claude-sonnet-4-6"
    llm_model_judge: str = "anthropic/claude-sonnet-4-6"
    llm_model_meta_judge: str = "anthropic/claude-sonnet-4-6"

    # Search
    tavily_api_key: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # SSE
    sse_heartbeat_seconds: int = 15


settings = Settings()
```

#### backend/app/main.py
```python
"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.database import engine


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown."""
    logger.info("starting_novum", host=settings.host, port=settings.port)
    yield
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Novum API",
    description="Self-directing research agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configured per-environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
```

#### backend/app/database.py
```python
"""Database engine and session configuration."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        yield session
```

#### backend/.env.example
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/novum

# LLM — V1 active provider: Anthropic Claude (interface is provider-agnostic via litellm)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
# Optional fallback providers (wired but disabled in V1 — leave unset unless re-enabling)
# GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# GOOGLE_API_KEY=xxxxxxxxxxxxxxxxxxxx

# Search
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

### 4.3 Frontend Configuration

#### package.json
```json
{
  "name": "novum-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.1.0",
    "zustand": "^5.0.0",
    "@tanstack/react-query": "^5.62.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.6.0",
    "lucide-react": "^0.468.0",
    "motion": "^12.0.0",
    "react-markdown": "^9.0.0",
    "react-syntax-highlighter": "^15.6.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/react-syntax-highlighter": "^15.5.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vite-tsconfig-paths": "^5.1.0",
    "vitest": "^2.1.0",
    "@testing-library/react": "^16.1.0",
    "@testing-library/jest-dom": "^6.6.0",
    "msw": "^2.7.0",
    "eslint": "^9.16.0",
    "@eslint/js": "^9.16.0",
    "typescript-eslint": "^8.18.0",
    "eslint-plugin-react-hooks": "^5.1.0"
  }
}
```

#### tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,

    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,

    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

#### vite.config.ts
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tailwindcss(), tsconfigPaths()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

#### src/index.css
```css
@import "tailwindcss";

/* Custom CSS variables for theming */
:root {
  --background: 0 0% 100%;
  --foreground: 240 10% 3.9%;
  --card: 0 0% 100%;
  --card-foreground: 240 10% 3.9%;
  --popover: 0 0% 100%;
  --popover-foreground: 240 10% 3.9%;
  --primary: 240 5.9% 10%;
  --primary-foreground: 0 0% 98%;
  --secondary: 240 4.8% 95.9%;
  --secondary-foreground: 240 5.9% 10%;
  --muted: 240 4.8% 95.9%;
  --muted-foreground: 240 3.8% 46.1%;
  --accent: 240 4.8% 95.9%;
  --accent-foreground: 240 5.9% 10%;
  --destructive: 0 84.2% 60.2%;
  --destructive-foreground: 0 0% 98%;
  --border: 240 5.9% 90%;
  --input: 240 5.9% 90%;
  --ring: 240 5.9% 10%;
  --radius: 0.5rem;
}

.dark {
  --background: 240 10% 3.9%;
  --foreground: 0 0% 98%;
  --card: 240 10% 3.9%;
  --card-foreground: 0 0% 98%;
  --popover: 240 10% 3.9%;
  --popover-foreground: 0 0% 98%;
  --primary: 0 0% 98%;
  --primary-foreground: 240 5.9% 10%;
  --secondary: 240 3.7% 15.9%;
  --secondary-foreground: 0 0% 98%;
  --muted: 240 3.7% 15.9%;
  --muted-foreground: 240 5% 64.9%;
  --accent: 240 3.7% 15.9%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 0 0% 98%;
  --border: 240 3.7% 15.9%;
  --input: 240 3.7% 15.9%;
  --ring: 240 4.9% 83.9%;
}

body {
  font-family: system-ui, -apple-system, sans-serif;
}
```

#### src/lib/utils.ts
```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

#### src/lib/constants.ts
```typescript
export const API_URL = import.meta.env.VITE_API_URL ?? "";
export const DEMO_SLOWDOWN = Number(import.meta.env.VITE_DEMO_SLOWDOWN ?? 1);
```

#### src/main.tsx
```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      retry: 1,
    },
  },
});

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
```

#### src/App.tsx
```typescript
import { BrowserRouter, Routes, Route } from "react-router-dom";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<div>Novum — Coming Soon</div>} />
      </Routes>
    </BrowserRouter>
  );
}
```

#### frontend/.env.example
```env
VITE_API_URL=http://localhost:8000
VITE_DEMO_SLOWDOWN=1
```

#### components.json (shadcn/ui)
```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/index.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

### 4.4 Root Configuration

#### .gitignore
```gitignore
# Dependencies
node_modules/
.venv/
__pycache__/

# Build
dist/
build/
*.egg-info/

# Environment
.env
.env.local
.env.*.local

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Test
.coverage
htmlcov/
.pytest_cache/

# Secrets
api_key_copilot.txt
```

---

## 5. Acceptance Criteria

### AC-01: Backend Starts Successfully
```gherkin
Given the backend virtual environment is created
  And dependencies are installed via uv
  And PostgreSQL is running locally
When I run "uvicorn app.main:app --reload"
Then the server starts on port 8000
  And GET /health returns {"status": "ok"}
```

### AC-02: Frontend Starts Successfully
```gherkin
Given dependencies are installed via npm install
When I run "npm run dev"
Then the Vite dev server starts on port 3000
  And the browser shows "Novum — Coming Soon"
```

### AC-03: Type Checking Passes
```gherkin
Given all configuration files are in place
When I run "pyright" in backend/
  And I run "npm run typecheck" in frontend/
Then both commands exit with code 0
  And no type errors are reported
```

### AC-04: Linting Passes
```gherkin
Given all configuration files are in place
When I run "ruff check ." in backend/
  And I run "npm run lint" in frontend/
Then both commands exit with code 0
```

---

## 6. Implementation Checklist

- [ ] Create `backend/` folder structure
- [ ] Create `backend/pyproject.toml`
- [ ] Create `backend/app/__init__.py`
- [ ] Create `backend/app/config.py`
- [ ] Create `backend/app/main.py`
- [ ] Create `backend/app/database.py`
- [ ] Create `backend/.env.example`
- [ ] Initialize Alembic: `alembic init alembic`
- [ ] Create `frontend/` folder structure
- [ ] Create `frontend/package.json`
- [ ] Create `frontend/tsconfig.json`
- [ ] Create `frontend/vite.config.ts`
- [ ] Create `frontend/src/index.css`
- [ ] Create `frontend/src/main.tsx`
- [ ] Create `frontend/src/App.tsx`
- [ ] Create `frontend/src/lib/utils.ts`
- [ ] Create `frontend/src/lib/constants.ts`
- [ ] Create `frontend/components.json`
- [ ] Create `frontend/.env.example`
- [ ] Create `scripts/export_types.py` (placeholder)
- [ ] Create root `.gitignore`
- [ ] Install backend deps: `uv sync`
- [ ] Install frontend deps: `npm install`
- [ ] Verify `uvicorn app.main:app` starts
- [ ] Verify `npm run dev` starts

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Smoke | Manual | Backend + Frontend startup | 100% |
| Lint | ruff, ESLint | All code | 100% |
| Types | pyright, tsc | All code | 100% |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | localhost | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key (V1 active LLM provider — all 5 roles) |
| `GITHUB_TOKEN` | No | — | Optional fallback (GitHub Models, wired-but-disabled in V1) |
| `OPENAI_API_KEY` | No | — | Optional fallback (OpenAI direct, wired-but-disabled in V1) |
| `GOOGLE_API_KEY` | No | — | Optional fallback (Google Gemini, wired-but-disabled in V1) |
| `TAVILY_API_KEY` | Yes | — | Tavily search API key |
| `VITE_API_URL` | No | `""` | Backend URL for frontend |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Dependency version conflicts | Med | Low | Pin exact versions in lock files |
| Python 3.12 not installed | High | Low | Document in README |
| Node 20+ not installed | High | Low | Document in README |

## 10. Out of Scope

- Database tables (BRD-01)
- Alembic migrations (BRD-01)
- API routes (BRD-03)
- React components (BRD-11+)
- Docker configuration (V2)
