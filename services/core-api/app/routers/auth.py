"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.redis import RateLimiter
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


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


async def check_rate_limit(request: Request, action: str, max_requests: int, window_seconds: int) -> None:
    """Check rate limit for an action and raise exception if exceeded."""
    if not settings.rate_limit_enabled:
        return
    client_ip = get_client_ip(request)
    if await RateLimiter.is_rate_limited(f"{action}:{client_ip}", max_requests, window_seconds):
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Register a new user with email and password."""
    # Rate limit: 3 registrations per minute per IP
    await check_rate_limit(request, "register", max_requests=3, window_seconds=60)

    user_service = UserService(db)

    # Check if email is already taken
    if await user_service.is_email_taken(data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    auth_service = AuthService(db)
    device_info = get_device_info(request)

    return await auth_service.register(data, device_info)


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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Login with email and password."""
    # Rate limit: 5 login attempts per minute per IP
    await check_rate_limit(request, "login", max_requests=5, window_seconds=60)

    auth_service = AuthService(db)
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)
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
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Logout and revoke refresh token."""
    auth_service = AuthService(db)
    await auth_service.logout(current_user.id, data.refresh_token)
