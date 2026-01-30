"""FastAPI dependencies for authentication - CouchDB-based."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.couchdb import get_couchdb, DocumentNotFoundError
from app.security import decode_access_token

# HTTP Bearer scheme
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
    """Get the current authenticated user from CouchDB using JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")

        if user_id is None:
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


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_optional)],
) -> dict | None:
    """Get the current authenticated user from CouchDB if present."""
    if credentials is None:
        return None

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")

        if user_id is None:
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


# Type aliases for dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
OptionalCurrentUser = Annotated[dict | None, Depends(get_optional_current_user)]

# Legacy aliases for compatibility
CurrentUserCouchDB = CurrentUser
OptionalCurrentUserCouchDB = OptionalCurrentUser
