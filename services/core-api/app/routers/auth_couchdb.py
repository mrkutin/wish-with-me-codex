"""CouchDB-based authentication endpoints."""

from fastapi import APIRouter, HTTPException, Request, status

from app.dependencies import CurrentUser
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_couchdb import CouchDBAuthService

router = APIRouter(prefix="/api/v2/auth", tags=["authentication-v2"])


def get_device_info(request: Request) -> str | None:
    """Extract device info from request headers."""
    user_agent = request.headers.get("User-Agent")
    return user_agent[:255] if user_agent else None


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email already registered"},
    },
)
async def register(
    data: RegisterRequest,
    request: Request,
) -> AuthResponse:
    """Register a new user with email and password (CouchDB backend)."""
    auth_service = CouchDBAuthService()
    device_info = get_device_info(request)

    try:
        return await auth_service.register(data, device_info)
    except ValueError as e:
        if "already registered" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        raise


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    data: LoginRequest,
    request: Request,
) -> AuthResponse:
    """Login with email and password (CouchDB backend)."""
    auth_service = CouchDBAuthService()
    device_info = get_device_info(request)

    result = await auth_service.login(data.email, data.password, device_info)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return result


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    data: RefreshTokenRequest,
    request: Request,
) -> TokenResponse:
    """Refresh access token using refresh token (CouchDB backend)."""
    auth_service = CouchDBAuthService()
    device_info = get_device_info(request)

    result = await auth_service.refresh_tokens(data.refresh_token, device_info)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return result


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    data: LogoutRequest,
    request: Request,
) -> None:
    """Logout and revoke refresh token (CouchDB backend).

    Note: This endpoint requires the refresh_token in the request body.
    For authenticated logout, include the access token in Authorization header.
    """
    # Extract user_id from access token if provided
    from app.security import decode_access_token
    from jose import JWTError

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )

    token = auth_header.split(" ")[1]
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    auth_service = CouchDBAuthService()
    await auth_service.logout(user_id, data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"description": "Not authenticated"},
    },
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user's information."""
    user_email = current_user.get("email") or f"{current_user['_id']}@unknown.oauth"
    user_name = current_user.get("name") or user_email.split("@")[0]

    return UserResponse(
        id=current_user["_id"],
        email=user_email,
        name=user_name,
        avatar_base64=current_user.get("avatar_base64"),
        bio=current_user.get("bio"),
        public_url_slug=current_user.get("public_url_slug"),
        locale=current_user.get("locale", "en"),
        birthday=current_user.get("birthday"),
        created_at=current_user.get("created_at"),
        updated_at=current_user.get("updated_at"),
    )
