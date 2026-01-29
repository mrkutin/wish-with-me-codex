"""CouchDB-based authentication endpoints."""

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.redis import RateLimiter
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_couchdb import CouchDBAuthService

router = APIRouter(prefix="/api/v2/auth", tags=["authentication-v2"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_device_info(request: Request) -> str | None:
    """Extract device info from request headers."""
    user_agent = request.headers.get("User-Agent")
    return user_agent[:255] if user_agent else None


async def check_rate_limit(
    request: Request,
    action: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    """Check rate limit for an action."""
    if not settings.rate_limit_enabled:
        return
    client_ip = get_client_ip(request)
    if await RateLimiter.is_rate_limited(
        f"{action}:{client_ip}",
        max_requests,
        window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email already registered"},
        429: {"description": "Too many requests"},
    },
)
async def register(
    data: RegisterRequest,
    request: Request,
) -> AuthResponse:
    """Register a new user with email and password (CouchDB backend)."""
    # Rate limit: 3 registrations per minute per IP
    await check_rate_limit(request, "register", max_requests=3, window_seconds=60)

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
        429: {"description": "Too many requests"},
    },
)
async def login(
    data: LoginRequest,
    request: Request,
) -> AuthResponse:
    """Login with email and password (CouchDB backend)."""
    # Rate limit: 5 login attempts per minute per IP
    await check_rate_limit(request, "login", max_requests=5, window_seconds=60)

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
