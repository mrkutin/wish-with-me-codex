"""OAuth service for social authentication."""

import base64
import hashlib
import hmac
import logging
import secrets
import time
from typing import Literal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.config import settings
from app.models.user import SocialAccount, User
from app.oauth.providers import get_oauth_client, parse_user_info, is_provider_configured
from app.oauth.schemas import OAuthProvider, OAuthUserInfo
from app.schemas.auth import AuthResponse
from app.schemas.user import UserCreate, UserResponse
from app.security import (
    DEFAULT_AVATAR_BASE64,
    create_access_token,
    create_refresh_token,
    hash_token,
)
from app.services.user import UserService

logger = logging.getLogger(__name__)


MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB max


async def _download_avatar(url: str) -> str | None:
    """Download avatar from URL and return as base64 data URI.

    Args:
        url: The avatar URL to download.

    Returns:
        Base64 data URI string, or None if download fails.
    """
    # Only allow HTTPS URLs for security (SSRF protection)
    if not url.startswith("https://"):
        logger.warning(f"Avatar URL not HTTPS, skipping: {url}")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, max_redirects=3) as client:
            response = await client.get(url)
            if response.status_code == 200:
                # Check content size to prevent memory exhaustion
                if len(response.content) > MAX_AVATAR_SIZE:
                    logger.warning(f"Avatar too large from {url}: {len(response.content)} bytes")
                    return None

                content_type = response.headers.get("content-type", "image/jpeg")
                # Strip any charset or other parameters from content type
                if ";" in content_type:
                    content_type = content_type.split(";")[0].strip()

                # Validate content type is an image
                if not content_type.startswith("image/"):
                    logger.warning(f"Avatar not an image type: {content_type}")
                    return None

                b64 = base64.b64encode(response.content).decode()
                return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to download avatar from {url}: {e}")
    return None


class OAuthService:
    """Service for OAuth authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    def _generate_state(self, action: Literal["login", "link"], user_id: UUID | None = None) -> str:
        """Generate a signed state parameter for OAuth.

        The state includes:
        - Random nonce for CSRF protection
        - Action type (login or link)
        - Optional user_id for link action
        - Timestamp for expiration
        - HMAC signature
        """
        nonce = secrets.token_urlsafe(16)
        timestamp = int(time.time())
        user_id_str = str(user_id) if user_id else ""

        # Create state payload
        payload = f"{nonce}:{action}:{user_id_str}:{timestamp}"

        # Sign with secret (use 32 hex chars = 128 bits for adequate security)
        secret = settings.oauth_state_secret or settings.jwt_secret_key
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]

        return f"{payload}:{signature}"

    def _verify_state(self, state: str, expected_action: Literal["login", "link"] | None = None) -> dict | None:
        """Verify and parse OAuth state parameter.

        Returns:
            Dict with action, user_id (if link), or None if invalid.
        """
        try:
            parts = state.split(":")
            if len(parts) != 5:
                return None

            nonce, action, user_id_str, timestamp_str, signature = parts

            # Reconstruct payload for verification
            payload = f"{nonce}:{action}:{user_id_str}:{timestamp_str}"

            # Verify signature
            secret = settings.oauth_state_secret or settings.jwt_secret_key
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()[:32]

            if not hmac.compare_digest(signature, expected_signature):
                return None

            # Check expiration (15 minutes)
            timestamp = int(timestamp_str)
            if time.time() - timestamp > 900:
                return None

            # Verify action if expected
            if expected_action and action != expected_action:
                return None

            return {
                "action": action,
                "user_id": UUID(user_id_str) if user_id_str else None,
            }

        except (ValueError, AttributeError):
            return None

    async def get_authorization_url(
        self,
        request: Request,
        provider: OAuthProvider,
        action: Literal["login", "link"] = "login",
        user_id: UUID | None = None,
    ) -> tuple[str, str]:
        """Generate OAuth authorization URL.

        Args:
            request: The Starlette request (needed for redirect URI).
            provider: The OAuth provider.
            action: Whether this is for login or account linking.
            user_id: Required if action is "link".

        Returns:
            Tuple of (authorization_url, state).

        Raises:
            ValueError: If provider is not configured or action is link without user_id.
        """
        if action == "link" and user_id is None:
            raise ValueError("user_id is required for link action")

        if not is_provider_configured(provider):
            raise ValueError(f"OAuth provider '{provider.value}' is not configured")

        client = get_oauth_client(provider)
        state = self._generate_state(action, user_id)

        # Build redirect URI for callback using configured API base URL
        # This ensures HTTPS is used even when running behind a reverse proxy
        redirect_uri = f"{settings.api_base_url}/api/v1/oauth/{provider.value}/callback"

        # Get authorization URL
        authorization_endpoint = await client.create_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
        )

        return authorization_endpoint["url"], state

    async def exchange_code(
        self,
        request: Request,
        provider: OAuthProvider,
        code: str,
        state: str,
    ) -> tuple[OAuthUserInfo, dict]:
        """Exchange authorization code for tokens and user info.

        Args:
            request: The Starlette request.
            provider: The OAuth provider.
            code: The authorization code.
            state: The state parameter.

        Returns:
            Tuple of (user_info, state_data).

        Raises:
            ValueError: If state is invalid or provider not configured.
        """
        state_data = self._verify_state(state)
        if state_data is None:
            raise ValueError("Invalid or expired OAuth state")

        if not is_provider_configured(provider):
            raise ValueError(f"OAuth provider '{provider.value}' is not configured")

        client = get_oauth_client(provider)

        # Build redirect URI (must match authorization request)
        redirect_uri = f"{settings.api_base_url}/api/v1/oauth/{provider.value}/callback"

        # Exchange code for token
        token = await client.fetch_access_token(
            code=code,
            redirect_uri=redirect_uri,
        )

        # Get user info (some providers include it in token, others need separate call)
        userinfo = None
        if provider in (OAuthProvider.GOOGLE, OAuthProvider.YANDEX):
            # These providers support userinfo endpoint
            userinfo = await client.userinfo(token=token)

        user_info = await parse_user_info(provider, token, userinfo)
        return user_info, state_data

    async def get_social_account(
        self,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> SocialAccount | None:
        """Get a social account by provider and provider user ID."""
        result = await self.db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.user))
            .where(
                SocialAccount.provider == provider.value,
                SocialAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_social_accounts(self, user_id: UUID) -> list[SocialAccount]:
        """Get all social accounts for a user."""
        result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    async def authenticate_or_create(
        self,
        user_info: OAuthUserInfo,
        device_info: str | None = None,
    ) -> tuple[AuthResponse, bool]:
        """Authenticate user via OAuth or create new account.

        This handles:
        1. Existing user with linked social account -> login
        2. Existing user with same email -> return conflict info
        3. New user -> create account and link social

        Args:
            user_info: Normalized user info from OAuth provider.
            device_info: Optional device info for refresh token.

        Returns:
            Tuple of (auth_response, is_new_user).

        Raises:
            EmailConflictError: If email is already used by another account.
        """
        # Check if social account already exists
        social_account = await self.get_social_account(
            user_info.provider,
            user_info.provider_user_id,
        )

        if social_account:
            # Existing user with linked account - login
            user = social_account.user
            if user.deleted_at is not None:
                raise ValueError("User account has been deleted")

            # Update social account email if changed
            if user_info.email and social_account.email != user_info.email:
                social_account.email = user_info.email

            # Update social account profile_data with latest OAuth info
            social_account.profile_data = {
                "name": user_info.name,
                "avatar_url": user_info.avatar_url,
                "birthday": user_info.birthday.isoformat() if user_info.birthday else None,
                "raw": user_info.raw_data,
            }

            # Update user profile from OAuth data if missing or placeholder
            user_updated = False

            # Update name from OAuth if provided and different
            if user_info.name and user_info.name != user.name:
                user.name = user_info.name
                user_updated = True
                logger.info(f"Updated name for user {user.id} from OAuth")

            # Update avatar if user has placeholder or no real avatar
            if user_info.avatar_url:
                # Check if user still has the default placeholder avatar (exact match)
                is_placeholder = user.avatar_base64 == DEFAULT_AVATAR_BASE64
                if is_placeholder:
                    downloaded = await _download_avatar(user_info.avatar_url)
                    if downloaded:
                        user.avatar_base64 = downloaded
                        user_updated = True
                        logger.info(f"Updated avatar for user {user.id} from OAuth")

            # Update birthday if user doesn't have one but OAuth provides it
            if user_info.birthday and not user.birthday:
                user.birthday = user_info.birthday
                user_updated = True
                logger.info(f"Updated birthday for user {user.id} from OAuth")

            if user_updated:
                await self.db.flush()
                await self.db.refresh(user)

            auth_response = await self._create_auth_response(user, device_info)
            return auth_response, False

        # Check if email is already used
        if user_info.email:
            existing_user = await self.user_service.get_by_email(user_info.email)
            if existing_user:
                raise EmailConflictError(
                    email=user_info.email,
                    user_id=existing_user.id,
                    provider=user_info.provider,
                )

        # Create new user
        user = await self._create_oauth_user(user_info)

        # Link social account
        await self._create_social_account(user.id, user_info)

        auth_response = await self._create_auth_response(user, device_info)
        return auth_response, True

    async def link_account(
        self,
        user_id: UUID,
        user_info: OAuthUserInfo,
    ) -> SocialAccount:
        """Link an OAuth account to an existing user.

        Args:
            user_id: The user ID to link to.
            user_info: The OAuth user info.

        Returns:
            The created social account.

        Raises:
            ValueError: If account is already linked to another user.
            DuplicateLinkError: If user already has this provider linked.
        """
        # Check if this social account is already linked
        existing = await self.get_social_account(
            user_info.provider,
            user_info.provider_user_id,
        )
        if existing:
            if existing.user_id == user_id:
                raise DuplicateLinkError(provider=user_info.provider)
            raise ValueError("This account is already linked to another user")

        # Check if user already has this provider linked
        user_accounts = await self.get_user_social_accounts(user_id)
        for account in user_accounts:
            if account.provider == user_info.provider.value:
                raise DuplicateLinkError(provider=user_info.provider)

        return await self._create_social_account(user_id, user_info)

    async def unlink_account(
        self,
        user_id: UUID,
        provider: OAuthProvider,
    ) -> bool:
        """Unlink an OAuth account from a user.

        Args:
            user_id: The user ID.
            provider: The provider to unlink.

        Returns:
            True if unlinked successfully.

        Raises:
            ValueError: If this is the only auth method and user has no password.
            ProviderNotLinkedError: If provider is not linked.
        """
        # Get user with social accounts
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.social_accounts))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # Find the account to unlink
        account_to_remove = None
        for account in user.social_accounts:
            if account.provider == provider.value:
                account_to_remove = account
                break

        if not account_to_remove:
            raise ProviderNotLinkedError(provider=provider)

        # Safety check: ensure user has another auth method
        has_password = user.password_hash is not None
        other_social_count = len(user.social_accounts) - 1

        if not has_password and other_social_count == 0:
            raise ValueError(
                "Cannot unlink the only authentication method. "
                "Please set a password or link another account first."
            )

        # Remove the social account
        await self.db.delete(account_to_remove)
        await self.db.flush()

        return True

    async def _create_oauth_user(self, user_info: OAuthUserInfo, locale: str = "en") -> User:
        """Create a new user from OAuth info."""
        # Try to download avatar from OAuth provider
        avatar = DEFAULT_AVATAR_BASE64
        if user_info.avatar_url:
            downloaded = await _download_avatar(user_info.avatar_url)
            if downloaded:
                avatar = downloaded

        user_data = UserCreate(
            email=user_info.email or f"{user_info.provider_user_id}@{user_info.provider.value}.oauth",
            password=None,  # OAuth users don't have passwords initially
            name=user_info.name or user_info.email or "User",
            locale=locale,
            avatar_base64=avatar,
            birthday=user_info.birthday,
        )
        return await self.user_service.create(user_data)

    async def _create_social_account(
        self,
        user_id: UUID,
        user_info: OAuthUserInfo,
    ) -> SocialAccount:
        """Create a social account linking."""
        social_account = SocialAccount(
            user_id=user_id,
            provider=user_info.provider.value,
            provider_user_id=user_info.provider_user_id,
            email=user_info.email,
            profile_data={
                "name": user_info.name,
                "avatar_url": user_info.avatar_url,
                "birthday": user_info.birthday.isoformat() if user_info.birthday else None,
                "raw": user_info.raw_data,
            },
        )
        self.db.add(social_account)
        await self.db.flush()
        await self.db.refresh(social_account)
        return social_account

    async def _create_auth_response(
        self,
        user: User,
        device_info: str | None,
    ) -> AuthResponse:
        """Create auth response with tokens."""
        from app.models.user import RefreshToken
        from app.security import get_refresh_token_expiry

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token()

        # Store refresh token
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            device_info=device_info,
            expires_at=get_refresh_token_expiry(),
        )
        self.db.add(token_record)
        await self.db.flush()

        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )


class EmailConflictError(Exception):
    """Raised when OAuth email conflicts with existing user."""

    def __init__(self, email: str, user_id: UUID, provider: OAuthProvider):
        self.email = email
        self.user_id = user_id
        self.provider = provider
        super().__init__(f"Email {email} is already registered")


class DuplicateLinkError(Exception):
    """Raised when user already has this provider linked."""

    def __init__(self, provider: OAuthProvider):
        self.provider = provider
        super().__init__(f"Provider {provider.value} is already linked")


class ProviderNotLinkedError(Exception):
    """Raised when trying to unlink a provider that isn't linked."""

    def __init__(self, provider: OAuthProvider):
        self.provider = provider
        super().__init__(f"Provider {provider.value} is not linked")
