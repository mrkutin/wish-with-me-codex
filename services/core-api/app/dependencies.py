"""FastAPI dependencies for authentication and common operations."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.redis import TokenBlocklist
from app.security import decode_access_token

# HTTP Bearer scheme
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if user_id_str is None:
            raise credentials_exception

        # Check if token is blocklisted
        if jti and await TokenBlocklist.is_blocked(jti):
            raise credentials_exception

        user_id = UUID(user_id_str)

    except (JWTError, ValueError):
        raise credentials_exception

    # Fetch user from database
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Get the current authenticated user if present, or None if not authenticated."""
    if credentials is None:
        return None

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if user_id_str is None:
            return None

        # Check if token is blocklisted
        if jti and await TokenBlocklist.is_blocked(jti):
            return None

        user_id = UUID(user_id_str)

    except (JWTError, ValueError):
        return None

    # Fetch user from database
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


# Type alias for dependency injection (PostgreSQL)
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]


# CouchDB-based user dependencies
async def get_current_user_couchdb(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
    """Get the current authenticated user from CouchDB using JWT token."""
    from app.couchdb import get_couchdb, DocumentNotFoundError

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if user_id is None:
            raise credentials_exception

        # Check if token is blocklisted
        if jti and await TokenBlocklist.is_blocked(jti):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Fetch user from CouchDB
    db = get_couchdb()
    try:
        user = await db.get(user_id)
        if user.get("type") != "user":
            raise credentials_exception
        return user
    except DocumentNotFoundError:
        raise credentials_exception


async def get_optional_current_user_couchdb(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_optional)],
) -> dict | None:
    """Get the current authenticated user from CouchDB if present."""
    from app.couchdb import get_couchdb, DocumentNotFoundError

    if credentials is None:
        return None

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if user_id is None:
            return None

        # Check if token is blocklisted
        if jti and await TokenBlocklist.is_blocked(jti):
            return None

    except JWTError:
        return None

    # Fetch user from CouchDB
    db = get_couchdb()
    try:
        user = await db.get(user_id)
        if user.get("type") != "user":
            return None
        return user
    except DocumentNotFoundError:
        return None


# Type alias for CouchDB dependency injection
CurrentUserCouchDB = Annotated[dict, Depends(get_current_user_couchdb)]
OptionalCurrentUserCouchDB = Annotated[dict | None, Depends(get_optional_current_user_couchdb)]
