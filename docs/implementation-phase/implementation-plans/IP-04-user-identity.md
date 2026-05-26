# Implementation Plan: BRD-04 User Identity (Lightweight Auth)

**Plan ID:** IP-04
**BRD Reference:** [BRD-04-user-identity.md](../brds/BRD-04-user-identity.md)
**Created:** 2026-05-26
**Status:** Ready for Coder
**Implementation Order:** 5 of 19

---

## 1. Overview

Implement RF-05 lightweight identity: username + random token, hashed with SHA-256. Adds `/api/auth/register|verify` and `/api/users/{username}` endpoints, upgrades the existing `get_current_username` dependency to verify the `X-Token` header against the stored hash, and provides the frontend `auth.ts` lib, `userStore` (Zustand), and `UsernameModal` organism.

**Source of truth:** BRD-04 §4 contains copy-paste-ready code. The Coder follows it verbatim unless tightened in §5 below.

**Non-goals (deferred):**
- Token rotation / regeneration — out of scope (BRD-04 §10).
- Authorization (who owns which run) — BRD-15.
- Authenticated SSE — BRD-10.
- Wiring `UsernameModal` into a page / app entry — BRD-11 already covers the layout; this BRD ships the modal + store only, ready to be mounted later.

---

## 2. Architectural Alignment

| Architecture rule | Compliance |
|---|---|
| English-only code artifacts | All identifiers, docstrings, error messages in English. |
| Pyright strict / Ruff clean | `from __future__ import annotations`, explicit return types, no `Any`. |
| Storage is a not-seam | `AuthService` depends directly on `AsyncSession`; no repository. |
| Single source for FastAPI deps | `get_current_username` lives **only** in `app/dependencies.py`; we extend, not duplicate. |
| Type contract FE↔BE | Pydantic models for request/response; mirrored in `frontend/src/lib/auth.ts` typings. |
| Frontend layering (atomic design) | `UsernameModal` is an **organism** (BRD-04 §4.1); `userStore` lives in `stores/`; raw fetch helper in `lib/`. |
| Constant-time token comparison | `secrets.compare_digest` (BRD-04 §4.3). |
| Token never stored plain | Only SHA-256 hash persisted in `users.token_hash`. |

**Pre-existing state (verified):**
- `backend/app/models/user.py` already defines `User(id, username, token_hash, created_at)` (BRD-02). ✓
- `backend/app/dependencies.py` already exposes `DbSession`, `CurrentUsername` from BRD-03 with a **header-only** placeholder. We tighten it. ✓
- `backend/app/routes/__init__.py` aggregates `health_router`, `runs_router`, `events_router`. We add `auth_router`. ✓
- `frontend/src/stores/` already contains `selectionStore.ts` (pattern reference). ✓
- `frontend/src/components/organisms/` exists. ✓

---

## 3. Implementation Sequence

### Phase 1 — Backend auth primitives (Steps 1–3)

| Step | Task | File | Priority |
|------|------|------|----------|
| 1 | Create `app/auth/__init__.py` (empty package marker). | [backend/app/auth/__init__.py](../../../backend/app/auth/__init__.py) | P0 |
| 2 | Implement `token.py` (`generate_token`, `hash_token`, `verify_token`) per BRD-04 §4.3. | [backend/app/auth/token.py](../../../backend/app/auth/token.py) | P0 |
| 3 | Implement `AuthService` per BRD-04 §4.4 with username validation, `UsernameExistsError`, `InvalidTokenError`. | [backend/app/services/auth_service.py](../../../backend/app/services/auth_service.py) | P0 |

### Phase 2 — Backend HTTP surface (Steps 4–6)

| Step | Task | File | Priority |
|------|------|------|----------|
| 4 | Implement `routes/auth.py` with `POST /api/auth/register`, `POST /api/auth/verify`, `GET /api/auth/users/{username}` per BRD-04 §4.5. | [backend/app/routes/auth.py](../../../backend/app/routes/auth.py) | P0 |
| 5 | Update `app/routes/__init__.py` to include `auth_router`. | [backend/app/routes/__init__.py](../../../backend/app/routes/__init__.py) | P0 |
| 6 | Update `app/dependencies.py`: `get_current_username` now requires `X-Username` **and** `X-Token`, verifies via `AuthService` (BRD-04 §4.6). | [backend/app/dependencies.py](../../../backend/app/dependencies.py) | P0 |

### Phase 3 — Frontend (Steps 7–9)

| Step | Task | File | Priority |
|------|------|------|----------|
| 7 | Create `lib/auth.ts` — localStorage helpers (`getStoredIdentity`, `storeIdentity`, `clearIdentity`, `getAuthHeaders`) per BRD-04 §4.7. | [frontend/src/lib/auth.ts](../../../frontend/src/lib/auth.ts) | P0 |
| 8 | Create `stores/userStore.ts` — Zustand store (`initialize`, `register`, `logout`) per BRD-04 §4.8. | [frontend/src/stores/userStore.ts](../../../frontend/src/stores/userStore.ts) | P0 |
| 9 | Create `components/organisms/UsernameModal.tsx` per BRD-04 §4.9. | [frontend/src/components/organisms/UsernameModal.tsx](../../../frontend/src/components/organisms/UsernameModal.tsx) | P0 |

### Phase 4 — Tests (Steps 10–13) — mandatory per L-002

| Step | Task | File | Priority |
|------|------|------|----------|
| 10 | Unit tests for `token.py` (`generate_token` length/uniqueness, `hash_token` determinism, `verify_token` accept/reject + constant-time). | [backend/tests/test_auth_token.py](../../../backend/tests/test_auth_token.py) | P0 |
| 11 | Service + integration tests for `AuthService` and routes (register happy path / 409 duplicate / 400 invalid; verify ok / wrong token / unknown user; user profile 200 / 404). Use the SQLite fixture pattern from L-005. | [backend/tests/test_auth_service.py](../../../backend/tests/test_auth_service.py), [backend/tests/test_routes_auth.py](../../../backend/tests/test_routes_auth.py) | P0 |
| 12 | Update / add a test asserting `get_current_username` returns 401 without headers, 401 with wrong token, 200 with valid pair. May extend `tests/test_routes_runs.py` fixtures. | [backend/tests/test_dependencies.py](../../../backend/tests/test_dependencies.py) | P0 |
| 13 | Vitest tests for `lib/auth.ts` (localStorage round-trip, header helper, clear), `userStore` (initialize valid/invalid/no-storage, register success/error, logout) using `vi.spyOn(globalThis, "fetch")`. | [frontend/src/lib/auth.test.ts](../../../frontend/src/lib/auth.test.ts), [frontend/src/stores/userStore.test.ts](../../../frontend/src/stores/userStore.test.ts) | P0 |

---

## 4. Acceptance Criteria Mapping

| AC (BRD-04 §5) | Verifying test |
|---|---|
| AC-01 Registration Creates User | `test_routes_auth.py::test_register_success` |
| AC-02 Duplicate Username Rejected | `test_routes_auth.py::test_register_duplicate_returns_409` |
| AC-03 Token Verification Works | `test_routes_auth.py::test_verify_*` |
| AC-04 Protected Routes Require Auth | `test_dependencies.py::test_get_current_username_*` |
| AC-05 Frontend Stores Identity | `lib/auth.test.ts` + `userStore.test.ts::register_*` |

---

## 5. Implementation Notes / Tightenings

1. **Existing `User` model already matches BRD-04.** Do **not** re-declare it; import from `app.models`.
2. **Username normalization is in the service**, not the route, to keep validation centralized (BRD-04 §4.4 `username.strip().lower()`).
3. **`POST /api/auth/verify` never throws on invalid credentials** — it returns `{valid: false}`. Only `get_current_username` raises 401, because route guards must short-circuit.
4. **`get_user` endpoint path:** BRD-04 §4.2 documents `/api/users/{username}` but §4.5's router is prefixed `/api/auth` — keep §4.5's prefix (`/api/auth/users/{username}`). Update BRD-04 §4.2 in the BRD only if the user requests it; do not introduce a second router for this BRD.
5. **`InvalidTokenError`** must be raised for both "unknown user" and "wrong token" so verification leaks zero info (timing + message symmetry). The route still maps both to `{valid: false}` (200), not 401.
6. **Frontend modal styling:** BRD-04 §4.9 ships Tailwind classes that reference `bg-primary text-primary-foreground` — these tokens come from BRD-11. They already exist; do not redefine.
7. **`isVerifying` initial value in `userStore`** is `true` because `initialize()` is async; tests must wait for `initialize()` to resolve before asserting `isAuthenticated`.
8. **Network test isolation:** use `vi.spyOn(globalThis, "fetch")` (not MSW) for `userStore` tests to keep BRD-04 self-contained; MSW arrives in a later BRD.
9. **English-only.** Modal microcopy stays in English ("Choose a Username", "Create Identity", "Cancel"). Per L-001 language policy: user-facing strings here are static atoms; the runtime LLM reply (Spanish-by-default) does not apply.
10. **Token storage type guarantee.** `getStoredIdentity` returns `UserIdentity | null` — under `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` callers must guard the null case (see L-006).

---

## 6. Risks

| Risk | Mitigation |
|------|------------|
| Test suite still on SQLite (per L-005) — `User.token_hash` String(64) and `users.id` UUID must materialize. | The existing `compiles`-hooks (`UUID → CHAR(36)`) cover this; no fixture change required. |
| `get_current_username` change breaks BRD-03 tests that pass only `X-Username`. | Update affected tests in step 12 to also send `X-Token`, registering a fixture user in setup. |
| `userStore.initialize` network error path silently authenticates — by design (offline support, BRD-04 §4.8). Document this in the test. | Add an explicit test `initialize_network_error_keeps_stored_identity`. |

---

## 7. Definition of Done

- All 13 steps complete.
- `pyright --strict` and `ruff check` clean on changed files.
- `pytest backend/tests/ -q` green.
- `vitest run` green.
- BRD-04 §6 checklist fully ticked.
- Reviewer score ≥ 9/10.
