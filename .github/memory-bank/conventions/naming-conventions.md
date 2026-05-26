# Naming Conventions

> Standard naming conventions for all Novum project artifacts.
> All agents must follow these conventions.

**Last Updated:** 2026-05-26

---

## Documentation Files

### Business Documents

| Type | Pattern | Example |
|------|---------|---------|
| BRD | `BRD-{YYYY-MM-DD}-{feature-slug}.md` | `BRD-2026-05-26-user-authentication.md` |
| User Story | `US-{number}-{slug}.md` | `US-001-create-user-session.md` |
| Implementation Plan | `PLAN-{US-number}-{date}.md` | `PLAN-US-001-2026-05-26.md` |
| Review Report | `REVIEW-{US-number}-{iter}-{date}.md` | `REVIEW-US-001-1-2026-05-26.md` |
| Decision Record | `D-{number}` (inline in decisions-history.md) | `D-001` |
| Lesson Learned | `L-{number}` (inline in lessons-learned.md) | `L-001` |

### Slugs
- Lowercase
- Hyphen-separated
- No special characters
- Max 30 characters
- Descriptive but concise

---

## Code Identifiers

### Python (Backend)

| Type | Convention | Example |
|------|------------|---------|
| Modules | `snake_case` | `user_service.py` |
| Classes | `PascalCase` | `UserService`, `RunRepository` |
| Functions | `snake_case` | `create_user`, `get_run_by_id` |
| Methods | `snake_case` | `process_event`, `validate_input` |
| Variables | `snake_case` | `user_count`, `is_active` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Type Variables | `PascalCase` with `T` suffix | `EventT`, `ModelT` |
| Private | `_snake_case` prefix | `_internal_method` |
| Pydantic Models | `PascalCase` | `UserCreate`, `RunResponse` |
| Enums | `PascalCase` (class), `SCREAMING_SNAKE_CASE` (values) | `Status.PENDING` |

### TypeScript (Frontend)

| Type | Convention | Example |
|------|------------|---------|
| Files (components) | `PascalCase.tsx` | `UserCard.tsx` |
| Files (utils) | `camelCase.ts` | `formatDate.ts` |
| Files (types) | `camelCase.ts` or `PascalCase.ts` | `types.ts`, `User.ts` |
| Components | `PascalCase` | `UserCard`, `RunList` |
| Functions | `camelCase` | `formatDate`, `handleClick` |
| Variables | `camelCase` | `userName`, `isLoading` |
| Constants | `SCREAMING_SNAKE_CASE` or `camelCase` | `API_URL`, `defaultConfig` |
| Types/Interfaces | `PascalCase` | `User`, `RunEvent` |
| Hooks | `camelCase` with `use` prefix | `useUser`, `useRunEvents` |
| Context | `PascalCase` with `Context` suffix | `UserContext` |
| Enums | `PascalCase` | `Status.Pending` |

### CSS/Tailwind

| Type | Convention | Example |
|------|------------|---------|
| Tailwind classes | `kebab-case` | `bg-primary`, `text-sm` |
| Custom CSS classes | `kebab-case` | `custom-button` |
| CSS variables | `--kebab-case` | `--primary-color` |

---

## API Conventions

### Endpoints

| Type | Convention | Example |
|------|------------|---------|
| Resources | `kebab-case`, plural | `/api/user-sessions` |
| Actions | Verb prefix when needed | `/api/runs/{id}/resume` |
| Query params | `camelCase` | `?includeEvents=true` |
| Path params | `{camelCase}` | `/api/runs/{runId}` |

### HTTP Methods

| Method | Purpose | Example |
|--------|---------|---------|
| GET | Retrieve | `GET /api/runs` |
| POST | Create | `POST /api/runs` |
| PUT | Replace | `PUT /api/runs/{id}` |
| PATCH | Partial update | `PATCH /api/runs/{id}` |
| DELETE | Remove | `DELETE /api/runs/{id}` |

---

## Database Conventions

### Tables

| Type | Convention | Example |
|------|------------|---------|
| Table names | `snake_case`, plural | `user_sessions` |
| Column names | `snake_case` | `created_at`, `user_id` |
| Primary keys | `id` | `id UUID` |
| Foreign keys | `{table}_id` | `user_id`, `run_id` |
| Timestamps | `{action}_at` | `created_at`, `updated_at` |
| Boolean | `is_{condition}` or `has_{thing}` | `is_active`, `has_error` |

### Indexes

| Type | Convention | Example |
|------|------------|---------|
| Index | `idx_{table}_{column(s)}` | `idx_events_run_id` |
| Unique | `uq_{table}_{column(s)}` | `uq_users_email` |
| Foreign key | `fk_{table}_{ref_table}` | `fk_runs_users` |

---

## Git Conventions

### Branches

| Type | Convention | Example |
|------|------------|---------|
| Feature | `feature/{US-number}-{slug}` | `feature/us-001-user-session` |
| Bug fix | `fix/{issue-number}-{slug}` | `fix/123-null-pointer` |
| Hotfix | `hotfix/{slug}` | `hotfix/auth-bypass` |
| Release | `release/{version}` | `release/v1.0.0` |

### Commits (Conventional Commits)

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code change, no feature/fix |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `chore` | Build, tooling, etc. |

Examples:
- `feat(auth): add user session creation`
- `fix(api): handle null response from LLM`
- `docs(readme): update installation steps`
- `test(runs): add unit tests for repository`

### Tags

| Type | Convention | Example |
|------|------------|---------|
| Release | `v{major}.{minor}.{patch}` | `v1.0.0` |
| Pre-release | `v{version}-{stage}.{number}` | `v1.0.0-beta.1` |

---

## Environment Variables

| Convention | Example |
|------------|---------|
| `SCREAMING_SNAKE_CASE` | `DATABASE_URL` |
| Prefix by service | `TAVILY_API_KEY`, `GITHUB_TOKEN` |
| Boolean | `ENABLE_DEBUG`, `USE_SSL` |

---

## Identifiers to Avoid

- Single letter variables (except loop counters `i`, `j`, `k`)
- Abbreviations (unless widely known: `id`, `url`, `api`)
- Hungarian notation (`strName`, `intCount`)
- Generic names (`data`, `temp`, `result`, `value`, `item`)
- Reserved words as identifiers
