# Lessons Learned

> Repository of lessons learned during the Novum development.
> All agents must consult this before starting tasks and update after completing them.

**Last Updated:** 2026-05-27
**Total Lessons:** 10

> **Reaffirmed 2026-05-26:** L-002 (mandatory unit tests, backend + frontend) is an active, non-negotiable rule. See D-006 in `decisions-history.md`.
> **Reaffirmed 2026-05-26:** L-008 (mandatory API_URL prefix) is an active, non-negotiable rule for ALL frontend API calls.

---

## Recent Lessons

- **L-010:** Cancellation Tests in Single-Task Async FSMs Need a Yielding Emit Hook (2026-05-27)
- **L-009:** Vitest Fake Timers — `advanceTimersByTime` Already Moves `Date.now()`; Do Not Call `setSystemTime` Again (2026-05-27)
- **L-008:** Always Prefix Backend API Calls with `API_URL` — MANDATORY RULE (2026-05-26)
- **L-007:** Upgrading a Header-Only Auth Fixture Requires Touching All Downstream Route Tests (2026-05-26)
- **L-006:** `exactOptionalPropertyTypes` Requires `prop?: T | undefined` on Pass-Through Props (2026-05-26)
- **L-005:** SQLite Fallback for PG-Typed ORM Tests via `compiles`-hooks (2026-05-26)
- **L-004:** Disable the `pytest-postgresql` Plugin When Running DB-Free Suites Locally (2026-05-26)
- **L-003:** Static-Only Tests for DB Migrations are Acceptable for Iteration 1 (2026-05-26)
- **L-002:** Unit Tests are Mandatory per F3.S3 (2026-05-26)
- **L-001:** BRD Template for Spec-Driven Development (2026-05-26)

---

## L-010: Cancellation Tests in Single-Task Async FSMs Need a Yielding Emit Hook

**Date:** 2026-05-27
**Agent:** Coder (BRD-07 — `AgentOrchestrator`)
**Category:** Backend / Testing / Asyncio

### Situation
`AgentOrchestrator.cancel()` sets `self._cancelled = True`, checked at the top of each `run()` loop iteration. The intuitive test pattern — wrap `orch.run()` in `asyncio.create_task`, then call `orch.cancel()` from the outer task — does not work when every LLM call and source call is mocked with synchronous `AsyncMock`s that never `await`-yield. The whole `run()` coroutine executes in a single scheduling slot before the outer task can run, so the cancel flag is set after `Stopped` has already been emitted with `judge_confirmed`.

### Lesson
For unit tests of a single-task async FSM with mocked I/O, inject cancellation via the **event callback** instead of an external task. The callback is `await`-ed inside the loop body, so an `await asyncio.sleep(0)` there gives the test a deterministic yielding point:

```python
async def cancelling_emit(event: BaseEvent) -> None:
    captured.append(event)
    if isinstance(event, PlanCritiquedEvent):
        await asyncio.sleep(0)
        orch.cancel()

stop_reason = await orch.run()  # no outer task, no race
assert stop_reason is StopReason.USER_CANCELLED
```

This keeps the orchestrator's public API unchanged (`cancel()` still works the way the worker will use it in BRD-10) while making the cancellation path unit-testable without a real `asyncio.Task` race.

### Prevention
- For any future FSM with `_cancelled`-style cooperative cancellation, write the cancel test against the emit hook, not against an outer task.
- Document in the orchestrator docstring that the worker (BRD-10) is responsible for running the orchestrator in its own task — the cancel flag is correct, but the timing depends on a real event loop yielding on real I/O.

---

## L-009: Vitest Fake Timers — `advanceTimersByTime` Already Moves `Date.now()`; Do Not Call `setSystemTime` Again

**Date:** 2026-05-27
**Agent:** Coder (BRD-13 iter 2 — `ElapsedClock`)
**Category:** Frontend / Testing

### Situation
While testing a `setInterval`-driven `ElapsedClock`, the assertion `toHaveTextContent("3s")` reported the rendered value as `"6s"`. The test was:

```ts
vi.setSystemTime(new Date("00:00:00Z"));
render(<ElapsedClock startedAt="00:00:00Z" />);  // tick = 0
act(() => {
  vi.setSystemTime(new Date("00:00:03Z"));       // ← double-advance
  vi.advanceTimersByTime(3_000);                 // also advances Date
});
// expected 3s, got 6s
```

### Root Cause
`vi.advanceTimersByTime(ms)` already moves the fake clock forward by `ms` AND fires every timer whose deadline has passed during that window. Calling `setSystemTime(now + ms)` before `advanceTimersByTime(ms)` effectively jumps the clock twice: each interval tick calls `Date.now()`, which now returns `now + 2·ms`. The DOM ends up showing `2·ms` of elapsed time.

### Lesson
Use exactly one of the following per advance step:
- `vi.advanceTimersByTime(ms)` — moves the clock and fires timers (preferred for setInterval/setTimeout-driven UIs).
- `vi.setSystemTime(newDate)` — jumps the clock without firing timers (only when you want to observe an effect on the next render, not on the next tick).

Never call both back-to-back when measuring elapsed time. The fixture should use `advanceTimersByTime` exclusively.

### Prevention
- When writing fake-timer tests for clocks/animations, decide upfront: "does this assertion depend on timers firing?" If yes, only `advanceTimersByTime`.
- If a test needs a non-zero starting offset, call `setSystemTime` once **before** `render`, then drive elapsed time exclusively with `advanceTimersByTime`.

---

## L-008: Always Prefix Backend API Calls with `API_URL` — MANDATORY RULE

**Date:** 2026-05-26
**Agent:** All agents
**Category:** Frontend / Deployment

### Situation
`userStore.ts` called `fetch("/api/auth/register")` and `fetch("/api/auth/verify")` with a relative URL. In production (Vercel), these requests hit `https://novum-seven.vercel.app/api/...` instead of the real backend at `https://novum-prod.duckdns.org/api/...`, returning 404 or 405 errors. Other call sites (e.g. `lib/api.ts`, `lib/sse.ts`) correctly prefixed with `API_URL` and worked fine.

### Root Cause
The store was implemented before `lib/api.ts` was established, so it used raw `fetch` with a relative path. Relative paths work in development (Vite's dev proxy) but break in production where frontend and backend are on different origins.

### Lesson — NON-NEGOTIABLE RULE
**Every HTTP or SSE call to the backend MUST be prefixed with `API_URL` from `@/lib/constants`.**

```typescript
// ✅ CORRECT
import { API_URL } from "@/lib/constants";
fetch(`${API_URL}/api/auth/register`, { ... });

// ❌ WRONG — breaks in production (Vercel ≠ backend host)
fetch("/api/auth/register", { ... });
```

### Enforcement
1. Prefer `lib/api.ts` methods (`api.get`, `api.post`, etc.) — they already include `API_URL`.
2. If raw `fetch` is unavoidable (e.g. Zustand stores before `api.ts` existed), import `API_URL` explicitly and prefix the path.
3. SSE connections use `lib/sse.ts::createSSEConnection()` — it already prefixes with `API_URL`.
4. **Never use relative paths like `/api/...` for backend calls in any frontend file.**

### Prevention
- Code review checklist: search for `fetch("/"` or `fetch('/` in `frontend/src/` — any match is a bug candidate.
- ESLint rule (future): `no-restricted-syntax` on raw `fetch` calls without `API_URL`.

---

---

## L-007: Upgrading a Header-Only Auth Fixture Requires Touching All Downstream Route Tests

**Date:** 2026-05-26
**Agent:** Coder (BRD-04)
**Category:** Testing / FastAPI dependencies

### Situation
BRD-03 protected routes were guarded by a placeholder `get_current_username` that only inspected `X-Username`. The shared `seeded_user` fixture inserted a `User` with a sentinel `token_hash = "x" * 64`. When BRD-04 upgraded the dependency to also require `X-Token`, every test that previously sent only `X-Username` started returning 401, even though the implementation under test was the new auth dependency.

### Lesson
When the production identity contract changes, the fixtures that simulate identity must change in lockstep. Specifically:
- Replace the synthetic ORM insert with a real `AuthService.register(...)` call so the persisted `token_hash` matches a plain token you can hand out.
- Expose a sibling fixture (`auth_headers`) that returns the full `{X-Username, X-Token}` dict; never let downstream tests reconstruct the header pair by hand.
- Do a workspace-wide rewrite of `headers={"X-Username": seeded_user}` → `headers=auth_headers` in one pass; partial updates produce noisy 401 failures that look like new bugs.

### Prevention
For any future BRD that tightens an auth dependency:
1. Update the shared fixture first.
2. Run the full suite — every 401 is a candidate for the rewrite.
3. Add an explicit `test_get_current_username_*` matrix (missing headers / wrong token / unknown user / valid pair) so the dependency's contract is asserted directly, not only via side effects of other tests.

---

## L-006: `exactOptionalPropertyTypes` Requires `prop?: T | undefined` on Pass-Through Props

**Date:** 2026-05-26
**Agent:** Coder (BRD-11)
**Category:** Frontend / TypeScript

### Situation
`tsconfig.json` enables `exactOptionalPropertyTypes`. With that flag, declaring `className?: string` means the prop may be **omitted** but cannot be **passed as `string | undefined`**. `StatusBadge` accepted an optional `className?: string` and forwarded it to `Badge`, which broke `tsc` even though tests passed.

### Lesson
For any wrapper component that forwards an optional prop coming from its own props, declare the receiving prop as `prop?: T | undefined` (explicit `undefined`). Plain `prop?: T` only works when callers always omit the prop.

### Action
Changed `BadgeProps.className` from `string` to `string | undefined`. Apply the same pattern proactively to all forwarded optional props (`label`, `aria-*`, refs) in future atoms/molecules.

---

## L-005: SQLite Fallback for PG-Typed ORM Tests via `compiles`-hooks

**Date:** 2026-05-26
**Agent:** Coder (BRD-03)
**Category:** Testing / SQLAlchemy

### Situation
BRD-03 services exercise the production ORM (`Run`, `Event`) which uses PG-specific column types: `JSONB`, `UUID`, `ENUM`. Running tests against SQLite via `aiosqlite` fails at table creation because SQLite has no native equivalents.

### Resolution
Register `sqlalchemy.ext.compiler.compiles` hooks **only in the test fixture** that downgrade `JSONB → JSON`, `UUID → CHAR(36)`, `ENUM → VARCHAR` for the `sqlite` dialect. Production models stay untouched (architecture rule: storage is a not-seam).

```python
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM

@compiles(JSONB, "sqlite")
def _jsonb_sqlite(_t, _c, **_kw): return "JSON"
# ...
```

Combined with `StaticPool` + a session-scoped in-memory engine, the entire BRD-03 suite (108 tests) runs DB-free in <2s.

### When to reuse
- Any future BRD that touches the ORM (BRD-05+, BRD-07, BRD-15) and needs unit/integration tests without Postgres.
- Place the hook in a shared `tests/conftest.py` fixture; do **not** import it from production code.

### Caveats
- This does not validate PG-specific behaviour (JSONB operators, ENUM constraints). Migration-level tests under `pytest-postgresql` remain the ground truth (per L-004, L-003).

---

## L-004: Disable the `pytest-postgresql` Plugin When Running DB-Free Suites Locally

**Date:** 2026-05-26
**Agent:** Coder
**Category:** Testing

### What Happened
While verifying BRD-02 (pure-Python domain tests, no DB touched), the entire pytest collection aborted with `ImportError: no pq wrapper available` originating from `pytest_postgresql.plugin`. The plugin transitively imports `psycopg`, which the local venv has installed without `psycopg_binary` and without a system libpq DLL on PATH.

### Root Cause
`pytest-postgresql` is auto-loaded via the `pytest11` entry point. It runs at *collection* time, before any test code, so unrelated test files (e.g. domain unit tests) cannot opt out individually.

### Lesson Learned
For test runs that do not need PostgreSQL, pass `-p no:postgresql` to pytest:
```
pytest -q -p no:postgresql
```
This disables only the postgres plugin and leaves `pytest-asyncio`, `pytest-httpx`, etc., intact.

### Prevention
- Use `-p no:postgresql` in CI jobs and local commands that target DB-free suites.
- Long-term fix (not in BRD-02 scope): install `psycopg[binary]` in the dev group, or pin `psycopg-binary>=3.x` explicitly so the plugin's transitive dependency resolves on Windows.

### Applied To
- BRD-02 verification commands.

---

## L-003: Static-Only Tests for DB Migrations are Acceptable for Iteration 1

**Date:** 2026-05-26
**Agent:** Reviewer
**Category:** Testing Strategy

### What Happened
BRD-01 review (CR-01-001) considered whether to penalize the Coder for shipping migration tests that only inspect the module source instead of executing `alembic upgrade head` against a live or `pytest-postgresql` database. AC-01 and AC-05 were therefore only verified structurally.

### Decision
Static-only verification is acceptable for iteration 1 **when the BRD itself defers runtime verification to a later phase**. BRD-01 §7 explicitly marks integration testing as BRD-02 territory and `alembic upgrade head` as a manual P1 step. Penalizing the Coder here would amount to enforcing a stricter standard than the spec.

### Rule of Thumb
- If the BRD's "Testing Strategy" section defers a test type, treat its absence as Minor (advisory), never Major.
- If the BRD requires a test type and it is missing, treat its absence as Major or Blocker.
- Cheap source-substring tests (e.g., "does `downgrade()` mention every `drop_table` in reverse order?") are a free win and should be requested as Minors.

### Prevention
Reviewers must read the BRD's `Testing Strategy` section before scoring `Test Coverage`. Do not import the stricter standards of later BRDs retroactively.

---

## L-002: Unit Tests are Mandatory per F3.S3

**Date:** 2026-05-26
**Agent:** Orchestrator
**Category:** Process & Workflow

### What Happened
BRD-00 implementation was marked complete without unit tests. Review CR-00-001 passed at 9.4/10 but user flagged missing tests.

### Root Cause
Workflow step F3.S3 (`generate_unit_tests`) was skipped. The Coder (Orchestrator acting as Coder) focused on file structure setup and forgot that **every BRD implementation must include unit tests**.

### Lesson Learned
**Unit tests are NOT optional.** Per `workflow.md`:
- **F3.S3** explicitly requires: "Create unit tests (backend/frontend)"
- **Quality Standards** mandate: "Test Coverage ≥80%"
- Even setup/infrastructure BRDs need smoke tests to validate tooling works

For BRD-00 specifically:
- Backend: `test_health.py` — validates FastAPI health endpoint
- Frontend: `format.test.ts`, `clipboard.test.ts` — validates utility functions

### Prevention
Before marking any implementation complete:
1. ✅ Verify F3.S3 was executed
2. ✅ Run `pytest` (backend) and `vitest` (frontend)
3. ✅ Confirm tests pass before review submission

### Applied To
- BRD-00: Added missing unit tests
- All future BRDs: F3.S3 is mandatory

---

## L-001: BRD Template for Spec-Driven Development

**Date:** 2026-05-26
**Agent:** BSA Agent
**Category:** Process & Workflow

### What Happened
Creating implementation specs for Novum project. Needed a BRD format that enables Copilot to implement directly from specifications without ambiguity.

### Root Cause
Standard BRD templates are too abstract for AI-assisted coding. Generic descriptions like "implement authentication" don't provide enough detail for automated implementation.

### Lesson Learned
BRDs optimized for Copilot need:
- **Implementation Order** field for sequencing
- **Exact file paths** in File Structure section
- **Copy-paste ready code blocks** (SQL, Python, TypeScript)
- **Alembic migration templates** included inline
- **UI ASCII mockups** for layout specs
- **Implementation Checklist** with specific file paths

### Prevention
Always use the enhanced BRD template at `.github/memory-bank/templates/brd-template.md` for all future specs.

### Applied To
- All 19 BRDs for Novum V1 implementation

---

## Categories

### Bugs & Debugging
_None yet._

### Performance
_None yet._

### Architecture
_None yet._

### Process & Workflow
_None yet._

### Testing
_None yet._

### Documentation
_None yet._

---

## Template

When adding a new lesson, use this format:

```markdown
## L-{number}: {Title}

**Date:** {YYYY-MM-DD}
**Agent:** {agent name}
**Category:** Bugs | Performance | Architecture | Process | Testing | Documentation

### What Happened
{Describe the situation that led to this lesson}

### Root Cause
{What was the underlying cause?}

### Lesson Learned
{What did we learn from this?}

### Prevention
{How do we prevent this in the future?}

### Applied To
- {Where was this lesson applied?}

---
```

---

## How to Add Lessons

1. Increment the lesson number (L-001, L-002, etc.)
2. Fill out the template completely
3. Update the "Total Lessons" count above
4. Add to the appropriate category section
5. Update the "Recent Lessons" section (keep last 5)

---

## Lesson Triggers

Add a lesson when:
- A bug takes more than 30 minutes to resolve
- A code review finds a significant issue
- An architectural decision needs to be revised
- A test fails unexpectedly
- A deployment fails
- A misunderstanding causes rework
- A better approach is discovered after implementation
