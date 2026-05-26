"""Authentication service (BRD-04 §4.4 / RF-05).

Owns username validation, registration, token verification, and public
profile lookup. The `User` ORM model is reused from `app.models` —
storage is a not-seam (see architecture rule §3).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token import generate_token, hash_token, verify_token
from app.models import User


class InvalidTokenError(Exception):
    """Raised when verification fails (unknown user OR wrong token).

    The same exception is used for both cases to avoid leaking which of
    the two failed (BRD-04 §4.4 / IP-04 §5.5).
    """


class AuthService:
    """User identity operations backed by `AsyncSession`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, username: str) -> tuple[str, str]:
        """Create or re-token a user and return `(username, plain_token)`.

        If the username does not exist it is created. If it already
        exists a new token is generated and the stored hash is replaced
        (token-regeneration / re-login flow). The plain token is
        returned exactly once; only its hash is persisted.
        Username is normalized (`strip().lower()`) here so all callers
        share the same validation rules.
        """
        username = username.strip().lower()
        if len(username) < 3 or len(username) > 50:
            raise ValueError("Username must be 3-50 characters")
        if not username.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Username may only contain letters, numbers, underscores, and hyphens"
            )

        token = generate_token()
        existing = await self._get_user_by_username(username)
        if existing is not None:
            existing.token_hash = hash_token(token)
        else:
            self.db.add(User(username=username, token_hash=hash_token(token)))
        await self.db.commit()

        return username, token

    async def verify(self, username: str, token: str) -> bool:
        """Verify `(username, token)`. Raise `InvalidTokenError` if bad.

        Returns True on success. Unknown user and wrong token raise the
        same exception so callers cannot distinguish the two cases.
        """
        user = await self._get_user_by_username(username)
        if user is None:
            raise InvalidTokenError()
        if not verify_token(token, user.token_hash):
            raise InvalidTokenError()
        return True

    async def get_user(self, username: str) -> User | None:
        """Return the public user record or None."""
        return await self._get_user_by_username(username)

    async def _get_user_by_username(self, username: str) -> User | None:
        query = select(User).where(User.username == username.lower())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
