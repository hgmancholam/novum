# BRD-04: User Identity (Lightweight Auth)

**Document ID:** BRD-04
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 5 of 19

---

## 1. Executive Summary

Implement lightweight user identity per RF-05: username-only identity with localStorage token. No OAuth, no email, no password management. Users create an identity by choosing a username; a random token is generated and stored client-side.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-05 | Lightweight identity (username only) | Complete |
| RF-05 | Public commons (all runs public) | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-01, BRD-03 | BRD-07, BRD-11 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    routes/
      auth.py              # Auth endpoints
    services/
      auth_service.py      # Auth business logic
    auth/
      __init__.py
      token.py             # Token generation/hashing
frontend/
  src/
    lib/
      auth.ts              # Auth utilities
    stores/
      userStore.ts         # Zustand user store
    components/
      organisms/
        UsernameModal.tsx  # Username creation modal
```

### 4.2 API Endpoints

| Method | Path | Request Body | Response | Description |
|--------|------|--------------|----------|-------------|
| POST | `/api/auth/register` | `{username}` | `{username, token}` | Create identity |
| POST | `/api/auth/verify` | `{username, token}` | `{valid: bool}` | Verify token |
| GET | `/api/users/{username}` | — | `{username, created_at}` | Public profile |

### 4.3 Token Module

#### backend/app/auth/token.py

```python
"""Token generation and hashing utilities."""

import hashlib
import secrets


def generate_token() -> str:
    """Generate a cryptographically secure random token.
    
    Returns 32-byte hex string (64 characters).
    """
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256.
    
    Only the hash is stored in the database.
    The original token is returned to the user once.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    """Verify a token against its hash.
    
    Uses constant-time comparison to prevent timing attacks.
    """
    return secrets.compare_digest(hash_token(token), token_hash)
```

### 4.4 Auth Service

#### backend/app/services/auth_service.py

```python
"""Authentication service for user identity."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token import generate_token, hash_token, verify_token
from app.models import User


class UsernameExistsError(Exception):
    """Username already taken."""

    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Username '{username}' already exists")


class InvalidTokenError(Exception):
    """Token is invalid."""

    pass


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, username: str) -> tuple[str, str]:
        """Register a new user with a random token.
        
        Returns (username, token).
        Token is returned only once - store it client-side.
        """
        # Validate username
        username = username.strip().lower()
        if len(username) < 3 or len(username) > 50:
            raise ValueError("Username must be 3-50 characters")
        if not username.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, underscores, and hyphens")

        # Check if username exists
        existing = await self._get_user_by_username(username)
        if existing:
            raise UsernameExistsError(username)

        # Generate token
        token = generate_token()
        token_hash = hash_token(token)

        # Create user
        user = User(
            username=username,
            token_hash=token_hash,
        )
        self.db.add(user)
        await self.db.commit()

        return username, token

    async def verify(self, username: str, token: str) -> bool:
        """Verify a username/token pair.
        
        Returns True if valid, raises InvalidTokenError if not.
        """
        user = await self._get_user_by_username(username)
        if not user:
            raise InvalidTokenError()

        if not verify_token(token, user.token_hash):
            raise InvalidTokenError()

        return True

    async def get_user(self, username: str) -> Optional[User]:
        """Get public user info by username."""
        return await self._get_user_by_username(username)

    async def _get_user_by_username(self, username: str) -> Optional[User]:
        """Internal: fetch user by username."""
        query = select(User).where(User.username == username.lower())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
```

### 4.5 Auth Routes

#### backend/app/routes/auth.py

```python
"""Authentication endpoints (RF-05)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import DbSession
from app.services.auth_service import (
    AuthService,
    InvalidTokenError,
    UsernameExistsError,
)


router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    """Request to create a new identity."""

    username: str = Field(..., min_length=3, max_length=50)


class RegisterResponse(BaseModel):
    """Response with username and token."""

    username: str
    token: str


class VerifyRequest(BaseModel):
    """Request to verify a token."""

    username: str
    token: str


class VerifyResponse(BaseModel):
    """Response indicating validity."""

    valid: bool


class UserResponse(BaseModel):
    """Public user profile."""

    username: str
    created_at: str


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    data: RegisterRequest,
    db: DbSession,
) -> RegisterResponse:
    """Create a new user identity (RF-05).
    
    The token is returned only once. Store it in localStorage.
    """
    service = AuthService(db)
    try:
        username, token = await service.register(data.username)
        return RegisterResponse(username=username, token=token)
    except UsernameExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    data: VerifyRequest,
    db: DbSession,
) -> VerifyResponse:
    """Verify a username/token pair."""
    service = AuthService(db)
    try:
        await service.verify(data.username, data.token)
        return VerifyResponse(valid=True)
    except InvalidTokenError:
        return VerifyResponse(valid=False)


@router.get("/users/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    db: DbSession,
) -> UserResponse:
    """Get public user profile."""
    service = AuthService(db)
    user = await service.get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        username=user.username,
        created_at=user.created_at.isoformat(),
    )
```

### 4.6 Updated Dependencies

#### backend/app/dependencies.py (updated)

```python
"""FastAPI dependencies for dependency injection."""

from typing import Annotated, AsyncIterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.services.auth_service import AuthService, InvalidTokenError


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session."""
    async with async_session_maker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_username(
    db: DbSession,
    x_username: Annotated[str | None, Header()] = None,
    x_token: Annotated[str | None, Header()] = None,
) -> str:
    """Extract and verify username from headers.
    
    Requires both X-Username and X-Token headers.
    """
    if not x_username or not x_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Username and X-Token headers required",
        )

    service = AuthService(db)
    try:
        await service.verify(x_username, x_token)
        return x_username
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


CurrentUsername = Annotated[str, Depends(get_current_username)]
```

### 4.7 Frontend Auth Utilities

#### frontend/src/lib/auth.ts

```typescript
/**
 * Authentication utilities for localStorage-based identity.
 */

const STORAGE_KEY_USERNAME = "novum_username";
const STORAGE_KEY_TOKEN = "novum_token";

export interface UserIdentity {
  username: string;
  token: string;
}

/**
 * Get stored identity from localStorage.
 */
export function getStoredIdentity(): UserIdentity | null {
  const username = localStorage.getItem(STORAGE_KEY_USERNAME);
  const token = localStorage.getItem(STORAGE_KEY_TOKEN);

  if (username && token) {
    return { username, token };
  }
  return null;
}

/**
 * Store identity in localStorage.
 */
export function storeIdentity(identity: UserIdentity): void {
  localStorage.setItem(STORAGE_KEY_USERNAME, identity.username);
  localStorage.setItem(STORAGE_KEY_TOKEN, identity.token);
}

/**
 * Clear stored identity.
 */
export function clearIdentity(): void {
  localStorage.removeItem(STORAGE_KEY_USERNAME);
  localStorage.removeItem(STORAGE_KEY_TOKEN);
}

/**
 * Get auth headers for API requests.
 */
export function getAuthHeaders(): Record<string, string> {
  const identity = getStoredIdentity();
  if (!identity) {
    return {};
  }
  return {
    "X-Username": identity.username,
    "X-Token": identity.token,
  };
}
```

### 4.8 Frontend User Store

#### frontend/src/stores/userStore.ts

```typescript
/**
 * Zustand store for user state.
 */

import { create } from "zustand";
import { getStoredIdentity, storeIdentity, clearIdentity, type UserIdentity } from "@/lib/auth";

interface UserState {
  // State
  user: UserIdentity | null;
  isVerifying: boolean;
  isAuthenticated: boolean;

  // Actions
  initialize: () => Promise<void>;
  register: (username: string) => Promise<void>;
  logout: () => void;
}

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  isVerifying: true,
  isAuthenticated: false,

  initialize: async () => {
    const stored = getStoredIdentity();
    if (!stored) {
      set({ user: null, isVerifying: false, isAuthenticated: false });
      return;
    }

    // Verify token with backend
    try {
      const response = await fetch("/api/auth/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(stored),
      });
      const data = await response.json();

      if (data.valid) {
        set({ user: stored, isVerifying: false, isAuthenticated: true });
      } else {
        clearIdentity();
        set({ user: null, isVerifying: false, isAuthenticated: false });
      }
    } catch {
      // Network error - assume valid for offline support
      set({ user: stored, isVerifying: false, isAuthenticated: true });
    }
  },

  register: async (username: string) => {
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Registration failed");
    }

    const data = await response.json();
    const identity: UserIdentity = {
      username: data.username,
      token: data.token,
    };

    storeIdentity(identity);
    set({ user: identity, isAuthenticated: true });
  },

  logout: () => {
    clearIdentity();
    set({ user: null, isAuthenticated: false });
  },
}));
```

### 4.9 Username Modal Component

#### frontend/src/components/organisms/UsernameModal.tsx

```typescript
/**
 * Modal for creating a new username identity.
 */

import { useState } from "react";
import { useUserStore } from "@/stores/userStore";

interface UsernameModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function UsernameModal({ isOpen, onClose }: UsernameModalProps) {
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const register = useUserStore((state) => state.register);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await register(username.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-neutral-900 rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-semibold mb-4">Choose a Username</h2>
        <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
          Your username is your identity. No email or password required.
        </p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter username (3-50 chars)"
            className="w-full px-3 py-2 border rounded-md mb-2 dark:bg-neutral-800 dark:border-neutral-700"
            minLength={3}
            maxLength={50}
            pattern="[a-zA-Z0-9_-]+"
            required
            disabled={isLoading}
          />

          {error && (
            <p className="text-red-500 text-sm mb-2">{error}</p>
          )}

          <div className="flex gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              disabled={isLoading || username.length < 3}
            >
              {isLoading ? "Creating..." : "Create Identity"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

---

## 5. Acceptance Criteria

### AC-01: Registration Creates User
```gherkin
Given no user with username "alice" exists
When I POST /api/auth/register with username="alice"
Then status 201 is returned
  And the response contains username="alice"
  And the response contains a 64-character hex token
  And a user record is created in the database
  And the token hash is stored (not the plain token)
```

### AC-02: Duplicate Username Rejected
```gherkin
Given user "alice" already exists
When I POST /api/auth/register with username="alice"
Then status 409 is returned
  And detail="Username already exists"
```

### AC-03: Token Verification Works
```gherkin
Given user "alice" registered with token "abc123..."
When I POST /api/auth/verify with username="alice" and correct token
Then valid=true is returned
When I POST /api/auth/verify with username="alice" and wrong token
Then valid=false is returned
```

### AC-04: Protected Routes Require Auth
```gherkin
Given user "alice" with valid token
When I GET /api/runs with X-Username and X-Token headers
Then the request succeeds
When I GET /api/runs without headers
Then status 401 is returned
When I GET /api/runs with invalid token
Then status 401 is returned
```

### AC-05: Frontend Stores Identity
```gherkin
Given the user creates username "alice"
When registration succeeds
Then localStorage contains novum_username="alice"
  And localStorage contains novum_token=<token>
  And subsequent API calls include auth headers
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/auth/__init__.py`
- [ ] Create `backend/app/auth/token.py`
- [ ] Create `backend/app/services/auth_service.py`
- [ ] Create `backend/app/routes/auth.py`
- [ ] Update `backend/app/routes/__init__.py` with auth router
- [ ] Update `backend/app/dependencies.py` with token verification
- [ ] Create `frontend/src/lib/auth.ts`
- [ ] Create `frontend/src/stores/userStore.ts`
- [ ] Create `frontend/src/components/organisms/UsernameModal.tsx`
- [ ] Write unit tests for token.py
- [ ] Write unit tests for auth_service.py
- [ ] Write integration tests for auth routes
- [ ] Write frontend tests for userStore

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | token.py, auth_service.py | 100% |
| Integration | pytest | Auth routes | 100% |
| Component | Vitest | UsernameModal, userStore | 100% |

## 8. Environment Variables

_None additional. Token generation uses Python secrets module._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Token theft from localStorage | High | Medium | Token is per-device; user can regenerate |
| Timing attack on verification | Low | Low | Use secrets.compare_digest |
| Username squatting | Low | Medium | Document: no ownership guarantees |

## 10. Out of Scope

- Password-based auth
- OAuth integration
- Email verification
- Account recovery
- Multi-device sync
- Session management
