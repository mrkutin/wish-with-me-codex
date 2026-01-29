"""Security utilities for authentication."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    The token is compatible with CouchDB JWT authentication.
    For CouchDB user IDs (format: "user:uuid"), the full ID is stored in sub.
    For UUID-only user IDs (PostgreSQL), just the UUID string is stored.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Support both UUID and string user IDs (for CouchDB "user:uuid" format)
    sub = str(user_id)

    to_encode: dict[str, Any] = {
        "sub": sub,
        "exp": expire,
        "iat": now,
        "jti": secrets.token_hex(16),
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def create_refresh_token() -> str:
    """Create a secure random refresh token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_refresh_token_expiry() -> datetime:
    """Get the expiry datetime for a new refresh token."""
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


# Default avatar as base64 (user silhouette placeholder)
DEFAULT_AVATAR_BASE64 = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciI"
    "HdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PGNpcmNsZSBje"
    "D0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiM2MzY2ZjEiLz48Y2lyY2xlIGN4PSI1MCIgY3k9"
    "IjM2IiByPSIxNiIgZmlsbD0id2hpdGUiLz48cGF0aCBkPSJNNTAgNTZjLTE4IDAtMzIgMTAtMzI"
    "gMjJ2MjJoNjR2LTIyYzAtMTItMTQtMjItMzItMjJ6IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPgo="
)
