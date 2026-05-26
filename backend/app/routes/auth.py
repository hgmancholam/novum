"""Authentication endpoints (BRD-04 §4.5 / RF-05).

Routes:
- `POST /api/auth/register` — create identity, return one-time token.
- `POST /api/auth/verify`   — non-throwing token check, returns `{valid}`.
- `GET  /api/auth/users/{username}` — public profile.

Only `get_current_username` (in `app.dependencies`) raises 401;
`/verify` always answers 200 with `{valid: false}` on failure to avoid
turning it into an auth guard (IP-04 §5.3/§5.5).
"""

from __future__ import annotations

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
    """Body for `POST /api/auth/register`."""

    username: str = Field(..., min_length=3, max_length=50)


class RegisterResponse(BaseModel):
    """Response containing the newly created identity."""

    username: str
    token: str


class VerifyRequest(BaseModel):
    """Body for `POST /api/auth/verify`."""

    username: str
    token: str


class VerifyResponse(BaseModel):
    """Result of a verification request."""

    valid: bool


class UserResponse(BaseModel):
    """Public-profile payload."""

    username: str
    created_at: str


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: RegisterRequest, db: DbSession) -> RegisterResponse:
    """Create a new user identity. Token is returned exactly once."""
    service = AuthService(db)
    try:
        username, token = await service.register(data.username)
    except UsernameExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RegisterResponse(username=username, token=token)


@router.post("/verify", response_model=VerifyResponse)
async def verify(data: VerifyRequest, db: DbSession) -> VerifyResponse:
    """Non-throwing verify — answers `{valid: false}` on any failure."""
    service = AuthService(db)
    try:
        await service.verify(data.username, data.token)
    except InvalidTokenError:
        return VerifyResponse(valid=False)
    return VerifyResponse(valid=True)


@router.get("/users/{username}", response_model=UserResponse)
async def get_user(username: str, db: DbSession) -> UserResponse:
    """Public profile lookup."""
    service = AuthService(db)
    user = await service.get_user(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        username=user.username,
        created_at=user.created_at.isoformat(),
    )
