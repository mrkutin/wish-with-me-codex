"""OAuth service for social authentication - CouchDB-based."""

import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

import httpx
from starlette.requests import Request

from app.config import settings
from app.couchdb import get_couchdb, DocumentNotFoundError
from app.oauth.providers import get_oauth_client, parse_user_info, is_provider_configured
from app.oauth.schemas import OAuthProvider, OAuthUserInfo
from app.schemas.auth import AuthResponse
from app.schemas.user import UserResponse
from app.security import (
    DEFAULT_AVATAR_BASE64,
    create_access_token,
    create_refresh_token,
    hash_token,
    get_refresh_token_expiry,
)

logger = logging.getLogger(__name__)

MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB max


async def _download_avatar(url: str) -> str | None:
    """Download avatar from URL and return as base64 data URI."""
    if not url.startswith("https://"):
        logger.warning(f"Avatar URL not HTTPS, skipping: {url}")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, max_redirects=3) as client:
            response = await client.get(url)
            if response.status_code == 200:
                if len(response.content) > MAX_AVATAR_SIZE:
                    logger.warning(f"Avatar too large from {url}: {len(response.content)} bytes")
                    return None

                content_type = response.headers.get("content-type", "image/jpeg")
                if ";" in content_type:
                    content_type = content_type.split(";")[0].strip()

                if not content_type.startswith("image/"):
                    logger.warning(f"Avatar not an image type: {content_type}")
                    return None

                b64 = base64.b64encode(response.content).decode()
                return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to download avatar from {url}: {e}")
    return None


class OAuthService:
    """Service for OAuth authentication operations - CouchDB-based."""

    def __init__(self):
        self.db = get_couchdb()

    # Allowed callback URL schemes for mobile clients
    ALLOWED_CALLBACK_SCHEMES = {"https", "wishwithme"}

    def _generate_state(
        self,
        action: Literal["login", "link"],
        user_id: str | None = None,
        callback_url: str | None = None,
    ) -> str:
        """Generate a signed state parameter for OAuth."""
        nonce = secrets.token_urlsafe(16)
        timestamp = int(time.time())
        user_id_str = user_id or ""
        callback_b64 = base64.urlsafe_b64encode(callback_url.encode()).decode() if callback_url else ""

        payload = f"{nonce}:{action}:{user_id_str}:{timestamp}:{callback_b64}"
        secret = settings.oauth_state_secret or settings.jwt_secret_key
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]

        return f"{payload}:{signature}"

    def _verify_state(self, state: str, expected_action: Literal["login", "link"] | None = None) -> dict | None:
        """Verify and parse OAuth state parameter."""
        try:
            parts = state.split(":")
            # Support both old 5-part and new 6-part format
            if len(parts) == 5:
                nonce, action, user_id_str, timestamp_str, signature = parts
                callback_b64 = ""
            elif len(parts) == 6:
                nonce, action, user_id_str, timestamp_str, callback_b64, signature = parts
            else:
                return None

            payload = f"{nonce}:{action}:{user_id_str}:{timestamp_str}:{callback_b64}"
            # Also check old format for backward compatibility
            payload_old = f"{nonce}:{action}:{user_id_str}:{timestamp_str}"

            secret = settings.oauth_state_secret or settings.jwt_secret_key
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()[:32]
            expected_signature_old = hmac.new(
                secret.encode(),
                payload_old.encode(),
                hashlib.sha256,
            ).hexdigest()[:32]

            if not (hmac.compare_digest(signature, expected_signature) or
                    (len(parts) == 5 and hmac.compare_digest(signature, expected_signature_old))):
                return None

            timestamp = int(timestamp_str)
            if time.time() - timestamp > 900:
                return None

            if expected_action and action != expected_action:
                return None

            # Decode callback URL if present
            callback_url = None
            if callback_b64:
                try:
                    decoded = base64.urlsafe_b64decode(callback_b64).decode()
                    # Validate scheme
                    from urllib.parse import urlparse
                    parsed = urlparse(decoded)
                    if parsed.scheme in self.ALLOWED_CALLBACK_SCHEMES:
                        callback_url = decoded
                except Exception:
                    pass

            return {
                "action": action,
                "user_id": user_id_str if user_id_str else None,
                "callback_url": callback_url,
            }

        except (ValueError, AttributeError):
            return None

    async def get_authorization_url(
        self,
        request: Request,
        provider: OAuthProvider,
        action: Literal["login", "link"] = "login",
        user_id: str | None = None,
        callback_url: str | None = None,
    ) -> tuple[str, str]:
        """Generate OAuth authorization URL."""
        if action == "link" and user_id is None:
            raise ValueError("user_id is required for link action")

        if not is_provider_configured(provider):
            raise ValueError(f"OAuth provider '{provider.value}' is not configured")

        client = get_oauth_client(provider)
        state = self._generate_state(action, user_id, callback_url=callback_url)

        redirect_uri = f"{settings.api_base_url}/api/v1/oauth/{provider.value}/callback"

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
        """Exchange authorization code for tokens and user info."""
        state_data = self._verify_state(state)
        if state_data is None:
            raise ValueError("Invalid or expired OAuth state")

        if not is_provider_configured(provider):
            raise ValueError(f"OAuth provider '{provider.value}' is not configured")

        client = get_oauth_client(provider)
        redirect_uri = f"{settings.api_base_url}/api/v1/oauth/{provider.value}/callback"

        token = await client.fetch_access_token(
            code=code,
            redirect_uri=redirect_uri,
        )

        logger.debug(f"OAuth token response keys: {list(token.keys()) if token else 'None'}")

        userinfo = None
        if provider in (OAuthProvider.GOOGLE, OAuthProvider.YANDEX):
            try:
                userinfo = await client.userinfo(token=token)
                logger.debug(f"OAuth userinfo keys: {list(userinfo.keys()) if userinfo else 'None'}")
            except KeyError as e:
                # authlib may raise KeyError if token structure is unexpected
                logger.warning(f"Failed to fetch userinfo, will use token claims: {e}")
                # For Google OIDC, userinfo is embedded in the token response
                userinfo = token.get("userinfo") or {}
            except Exception as e:
                logger.warning(f"Userinfo endpoint failed: {type(e).__name__}: {e}")
                userinfo = token.get("userinfo") or {}

        user_info = await parse_user_info(provider, token, userinfo)
        return user_info, state_data

    async def get_social_account(
        self,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> dict | None:
        """Get a social account by provider and provider user ID from CouchDB."""
        try:
            results = await self.db.find({
                "type": "social_account",
                "provider": provider.value,
                "provider_user_id": provider_user_id,
            })
            if results:
                return results[0]
        except Exception as e:
            logger.error(f"Error finding social account: {e}")
        return None

    async def get_user_social_accounts(self, user_id: str) -> list[dict]:
        """Get all social accounts for a user from CouchDB."""
        try:
            return await self.db.find({
                "type": "social_account",
                "user_id": user_id,
            })
        except Exception as e:
            logger.error(f"Error finding user social accounts: {e}")
            return []

    async def authenticate_or_create(
        self,
        user_info: OAuthUserInfo,
        device_info: str | None = None,
    ) -> tuple[AuthResponse, bool]:
        """Authenticate user via OAuth or create new account in CouchDB."""
        # Check if social account already exists
        social_account = await self.get_social_account(
            user_info.provider,
            user_info.provider_user_id,
        )

        if social_account:
            # Existing user with linked account - login
            user_id = social_account["user_id"]
            try:
                user = await self.db.get(user_id)
            except DocumentNotFoundError:
                raise ValueError("User account not found")

            # Update social account with latest OAuth info
            social_account["email"] = user_info.email
            social_account["profile_data"] = {
                "name": user_info.name,
                "avatar_url": user_info.avatar_url,
                "birthday": user_info.birthday.isoformat() if user_info.birthday else None,
                "raw": user_info.raw_data,
            }
            social_account["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self.db.put(social_account)

            # Update user profile from OAuth data if needed
            user_updated = False
            if user_info.name and user_info.name != user.get("name"):
                user["name"] = user_info.name
                user_updated = True

            if user_info.avatar_url and user.get("avatar_base64") == DEFAULT_AVATAR_BASE64:
                downloaded = await _download_avatar(user_info.avatar_url)
                if downloaded:
                    user["avatar_base64"] = downloaded
                    user_updated = True

            if user_info.birthday and not user.get("birthday"):
                user["birthday"] = user_info.birthday.isoformat()
                user_updated = True

            if user_updated:
                user["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self.db.put(user)
                # Re-fetch to get the latest _rev for subsequent saves
                user = await self.db.get(user["_id"])

            auth_response = await self._create_auth_response(user, device_info)
            return auth_response, False

        # Check if email is already used
        if user_info.email:
            existing_users = await self.db.find({
                "type": "user",
                "email": user_info.email.lower(),
            })
            if existing_users:
                # Email exists - auto-link OAuth account and login
                # This is safe because Google/Yandex verify email ownership
                user = existing_users[0]
                logger.info(f"Auto-linking {user_info.provider.value} to existing user {user['_id']}")

                # Create the social account link
                await self._create_social_account(user["_id"], user_info)

                # Update user profile from OAuth if beneficial
                user_updated = False
                if user_info.name and not user.get("name"):
                    user["name"] = user_info.name
                    user_updated = True

                if user_info.avatar_url and user.get("avatar_base64") == DEFAULT_AVATAR_BASE64:
                    downloaded = await _download_avatar(user_info.avatar_url)
                    if downloaded:
                        user["avatar_base64"] = downloaded
                        user_updated = True

                if user_info.birthday and not user.get("birthday"):
                    user["birthday"] = user_info.birthday.isoformat()
                    user_updated = True

                if user_updated:
                    user["updated_at"] = datetime.now(timezone.utc).isoformat()
                    await self.db.put(user)
                    # Re-fetch to get the latest _rev for subsequent saves
                    user = await self.db.get(user["_id"])

                auth_response = await self._create_auth_response(user, device_info)
                return auth_response, False

        # Create new user
        user = await self._create_oauth_user(user_info)

        # Link social account
        await self._create_social_account(user["_id"], user_info)

        auth_response = await self._create_auth_response(user, device_info)
        return auth_response, True

    async def link_account(
        self,
        user_id: str,
        user_info: OAuthUserInfo,
    ) -> dict:
        """Link an OAuth account to an existing user in CouchDB."""
        existing = await self.get_social_account(
            user_info.provider,
            user_info.provider_user_id,
        )
        if existing:
            if existing["user_id"] == user_id:
                raise DuplicateLinkError(provider=user_info.provider)
            raise ValueError("This account is already linked to another user")

        user_accounts = await self.get_user_social_accounts(user_id)
        for account in user_accounts:
            if account["provider"] == user_info.provider.value:
                raise DuplicateLinkError(provider=user_info.provider)

        return await self._create_social_account(user_id, user_info)

    async def unlink_account(
        self,
        user_id: str,
        provider: OAuthProvider,
    ) -> bool:
        """Unlink an OAuth account from a user in CouchDB."""
        try:
            user = await self.db.get(user_id)
        except DocumentNotFoundError:
            raise ValueError("User not found")

        user_accounts = await self.get_user_social_accounts(user_id)
        account_to_remove = None
        for account in user_accounts:
            if account["provider"] == provider.value:
                account_to_remove = account
                break

        if not account_to_remove:
            raise ProviderNotLinkedError(provider=provider)

        has_password = user.get("password_hash") is not None
        other_social_count = len(user_accounts) - 1

        if not has_password and other_social_count == 0:
            raise ValueError(
                "Cannot unlink the only authentication method. "
                "Please set a password or link another account first."
            )

        await self.db.delete(account_to_remove["_id"], account_to_remove["_rev"])
        return True

    async def _create_oauth_user(self, user_info: OAuthUserInfo, locale: str = "en") -> dict:
        """Create a new user from OAuth info in CouchDB."""
        avatar = DEFAULT_AVATAR_BASE64
        if user_info.avatar_url:
            downloaded = await _download_avatar(user_info.avatar_url)
            if downloaded:
                avatar = downloaded

        now = datetime.now(timezone.utc).isoformat()
        user_id = str(uuid4())

        user = {
            "_id": user_id,
            "type": "user",
            "email": (user_info.email or f"{user_info.provider_user_id}@{user_info.provider.value}.oauth").lower(),
            "name": user_info.name or user_info.email or "User",
            "avatar_base64": avatar,
            "bio": None,
            "locale": locale,
            "birthday": user_info.birthday.isoformat() if user_info.birthday else None,
            "created_at": now,
            "updated_at": now,
            "refresh_tokens": [],
        }

        await self.db.put(user)
        return await self.db.get(user_id)

    async def _create_social_account(
        self,
        user_id: str,
        user_info: OAuthUserInfo,
    ) -> dict:
        """Create a social account linking in CouchDB."""
        now = datetime.now(timezone.utc).isoformat()
        account_id = f"social:{user_info.provider.value}:{user_info.provider_user_id}"

        social_account = {
            "_id": account_id,
            "type": "social_account",
            "user_id": user_id,
            "provider": user_info.provider.value,
            "provider_user_id": user_info.provider_user_id,
            "email": user_info.email,
            "profile_data": {
                "name": user_info.name,
                "avatar_url": user_info.avatar_url,
                "birthday": user_info.birthday.isoformat() if user_info.birthday else None,
                "raw": user_info.raw_data,
            },
            "created_at": now,
            "updated_at": now,
        }

        await self.db.put(social_account)
        return await self.db.get(account_id)

    async def _create_auth_response(
        self,
        user: dict,
        device_info: str | None,
    ) -> AuthResponse:
        """Create auth response with tokens stored in CouchDB."""
        user_id = user["_id"]
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token()

        # Store refresh token in user document
        now = datetime.now(timezone.utc).isoformat()
        refresh_tokens = user.get("refresh_tokens", [])
        refresh_tokens.append({
            "token_hash": hash_token(refresh_token),
            "device_info": device_info,
            "expires_at": get_refresh_token_expiry().isoformat(),
            "revoked": False,
            "created_at": now,
        })

        # Keep only last 10 non-revoked tokens
        refresh_tokens = [rt for rt in refresh_tokens if not rt.get("revoked")][-10:]
        user["refresh_tokens"] = refresh_tokens
        user["updated_at"] = now
        await self.db.put(user)

        # Use .get() for email and name to handle legacy users without these fields
        user_email = user.get("email") or f"{user['_id']}@unknown.oauth"
        user_name = user.get("name") or user_email.split("@")[0]

        return AuthResponse(
            user=UserResponse(
                id=user["_id"],
                email=user_email,
                name=user_name,
                avatar_base64=user.get("avatar_base64"),
                bio=user.get("bio"),
                public_url_slug=user.get("public_url_slug"),
                locale=user.get("locale", "en"),
                created_at=user.get("created_at"),
                updated_at=user.get("updated_at"),
            ),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )


class EmailConflictError(Exception):
    """Raised when OAuth email conflicts with existing user."""

    def __init__(self, email: str, user_id: str, provider: OAuthProvider):
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
