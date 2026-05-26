"""Token generation and hashing utilities (BRD-04 §4.3).

Tokens are 32-byte random hex strings (64 chars). Only their SHA-256
hash is persisted in `users.token_hash`. Verification uses a constant-
time comparison to avoid timing leaks.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_token() -> str:
    """Return a 64-char hex token (32 random bytes)."""
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of `token`."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    """Constant-time verify `token` against a stored SHA-256 hash."""
    return secrets.compare_digest(hash_token(token), token_hash)
