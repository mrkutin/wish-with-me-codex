"""Authentication service for login, registration, and token management."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User
from app.schemas.auth import AuthResponse, RegisterRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.security import (
    DEFAULT_AVATAR_BASE64,
    create_access_token,
    create_refresh_token,
    get_refresh_token_expiry,
    hash_password,
    hash_token,
    verify_password,
)
from app.services.user import UserService


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def register(
        self, data: RegisterRequest, device_info: str | None = None
    ) -> AuthResponse:
        """Register a new user and return auth tokens."""
        # Create user
        user_data = UserCreate(
            email=data.email,
            password=data.password,
            name=data.name,
            locale=data.locale,
            avatar_base64=DEFAULT_AVATAR_BASE64,
        )
        user = await self.user_service.create(user_data)

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token()

        # Store refresh token
        await self._store_refresh_token(user.id, refresh_token, device_info)

        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def login(
        self, email: str, password: str, device_info: str | None = None
    ) -> AuthResponse | None:
        """Authenticate user and return auth tokens."""
        user = await self.user_service.get_by_email(email)

        # Prevent timing attacks by always performing password verification
        # even when user doesn't exist or has no password
        if user is None or user.password_hash is None:
            # Perform dummy verification to maintain constant time
            verify_password(password, hash_password("dummy-password-for-timing"))
            return None

        if not verify_password(password, user.password_hash):
            return None

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token()

        # Store refresh token
        await self._store_refresh_token(user.id, refresh_token, device_info)

        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh_tokens(
        self, refresh_token: str, device_info: str | None = None
    ) -> TokenResponse | None:
        """Refresh access token using refresh token."""
        token_hash = hash_token(refresh_token)

        # Find and validate refresh token
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        stored_token = result.scalar_one_or_none()

        if stored_token is None:
            return None

        # Revoke old token (token rotation)
        stored_token.revoked = True

        # Generate new tokens
        new_access_token = create_access_token(stored_token.user_id)
        new_refresh_token = create_refresh_token()

        # Store new refresh token
        await self._store_refresh_token(
            stored_token.user_id, new_refresh_token, device_info
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def logout(self, user_id: UUID, refresh_token: str) -> bool:
        """Revoke refresh token on logout."""
        token_hash = hash_token(refresh_token)

        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == token_hash,
            )
        )
        stored_token = result.scalar_one_or_none()

        if stored_token is None:
            return False

        stored_token.revoked = True
        await self.db.flush()
        return True

    async def revoke_all_tokens(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user."""
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .values(revoked=True)
        )
        await self.db.flush()
        return result.rowcount

    async def _store_refresh_token(
        self, user_id: UUID, token: str, device_info: str | None
    ) -> RefreshToken:
        """Store a new refresh token in the database."""
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(token),
            device_info=device_info,
            expires_at=get_refresh_token_expiry(),
        )
        self.db.add(refresh_token)
        await self.db.flush()
        return refresh_token

    async def cleanup_expired_tokens(self) -> int:
        """Remove expired refresh tokens from the database."""
        result = await self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.expires_at < datetime.now(timezone.utc)
            )
        )
        await self.db.flush()
        return result.rowcount
