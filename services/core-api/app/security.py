import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, roles: list[str]) -> tuple[str, datetime]:
    expires_at = _utcnow() + timedelta(days=settings.access_token_ttl_days)
    payload = {
        "sub": subject,
        "roles": roles,
        "type": "access",
        "iss": settings.jwt_issuer,
        "exp": expires_at,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires_at


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    expires_at = _utcnow() + timedelta(days=settings.refresh_token_ttl_days)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "jti": jti,
        "type": "refresh",
        "iss": settings.jwt_issuer,
        "exp": expires_at,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, jti, expires_at


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)


def require_token_type(payload: dict, expected: str) -> None:
    if payload.get("type") != expected:
        raise JWTError("Invalid token type")
