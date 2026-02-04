"""CouchDB-based authentication service."""

from datetime import datetime, timezone

from app.config import settings
from app.couchdb import CouchDBClient, DocumentNotFoundError, get_couchdb
from app.schemas.auth import AuthResponse, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.security import (
    DEFAULT_AVATAR_BASE64,
    create_access_token,
    create_refresh_token,
    get_refresh_token_expiry,
    hash_password,
    hash_token,
    verify_password,
)


class CouchDBAuthService:
    """Authentication service using CouchDB."""

    def __init__(self, db: CouchDBClient | None = None):
        self.db = db or get_couchdb()

    async def register(
        self,
        data: RegisterRequest,
        device_info: str | None = None,
    ) -> AuthResponse:
        """Register a new user and return auth tokens."""
        # Check if email is already taken
        existing_user = await self.db.get_user_by_email(data.email)
        if existing_user:
            raise ValueError("Email already registered")

        # Create user document
        user = await self.db.create_user(
            email=data.email,
            password_hash=hash_password(data.password),
            name=data.name,
            locale=data.locale or "en",
            avatar_base64=DEFAULT_AVATAR_BASE64,
        )

        user_id = user["_id"]

        # Generate tokens
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token()

        # Store refresh token in user document
        await self._store_refresh_token(user_id, refresh_token, device_info)

        return AuthResponse(
            user=self._user_to_response(user),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def login(
        self,
        email: str,
        password: str,
        device_info: str | None = None,
    ) -> AuthResponse | None:
        """Authenticate user and return auth tokens."""
        user = await self.db.get_user_by_email(email)

        # Prevent timing attacks
        if user is None:
            verify_password(password, hash_password("dummy-password-for-timing"))
            return None

        password_hash = user.get("password_hash")
        if not password_hash or not verify_password(password, password_hash):
            return None

        user_id = user["_id"]

        # Generate tokens
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token()

        # Store refresh token
        await self._store_refresh_token(user_id, refresh_token, device_info)

        return AuthResponse(
            user=self._user_to_response(user),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        device_info: str | None = None,
    ) -> TokenResponse | None:
        """Refresh access token using refresh token."""
        token_hash = hash_token(refresh_token)

        # Find user with this refresh token
        users = await self.db.find(
            {
                "type": "user",
                "refresh_tokens": {
                    "$elemMatch": {
                        "token_hash": token_hash,
                        "revoked": False,
                    }
                },
            }
        )

        if not users:
            return None

        user = users[0]
        user_id = user["_id"]
        now = datetime.now(timezone.utc)

        # Find and validate the token
        refresh_tokens = user.get("refresh_tokens", [])
        valid_token = None
        for rt in refresh_tokens:
            if rt["token_hash"] == token_hash and not rt["revoked"]:
                expires_at = datetime.fromisoformat(rt["expires_at"].replace("Z", "+00:00"))
                if expires_at > now:
                    valid_token = rt
                    break

        if not valid_token:
            return None

        # Revoke old token (token rotation)
        valid_token["revoked"] = True

        # Generate new tokens
        new_access_token = create_access_token(user_id)
        new_refresh_token = create_refresh_token()

        # Add new refresh token
        refresh_tokens.append({
            "token_hash": hash_token(new_refresh_token),
            "device_info": device_info,
            "expires_at": get_refresh_token_expiry().isoformat(),
            "revoked": False,
            "created_at": now.isoformat(),
        })

        # Clean up old/expired tokens
        refresh_tokens = [
            rt for rt in refresh_tokens
            if not rt["revoked"] or (
                datetime.fromisoformat(rt["expires_at"].replace("Z", "+00:00")) > now
            )
        ]

        # Update user document
        user["refresh_tokens"] = refresh_tokens
        user["updated_at"] = now.isoformat()
        await self.db.put(user)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def logout(self, user_id: str, refresh_token: str) -> bool:
        """Revoke refresh token on logout."""
        token_hash = hash_token(refresh_token)

        try:
            user = await self.db.get(user_id)
        except DocumentNotFoundError:
            return False

        refresh_tokens = user.get("refresh_tokens", [])
        token_found = False

        for rt in refresh_tokens:
            if rt["token_hash"] == token_hash and not rt["revoked"]:
                rt["revoked"] = True
                token_found = True
                break

        if not token_found:
            return False

        user["refresh_tokens"] = refresh_tokens
        user["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self.db.put(user)

        return True

    async def get_user_by_id(self, user_id: str) -> dict | None:
        """Get user by ID."""
        try:
            user = await self.db.get(user_id)
            if user.get("type") != "user":
                return None
            return user
        except DocumentNotFoundError:
            return None

    async def _store_refresh_token(
        self,
        user_id: str,
        token: str,
        device_info: str | None,
    ) -> None:
        """Store a new refresh token in the user document."""
        user = await self.db.get(user_id)
        now = datetime.now(timezone.utc)

        refresh_tokens = user.get("refresh_tokens", [])

        # Add new token
        refresh_tokens.append({
            "token_hash": hash_token(token),
            "device_info": device_info,
            "expires_at": get_refresh_token_expiry().isoformat(),
            "revoked": False,
            "created_at": now.isoformat(),
        })

        # Clean up old tokens (keep max 10 per user)
        # Remove expired and revoked tokens first
        refresh_tokens = [
            rt for rt in refresh_tokens
            if not rt["revoked"] and (
                datetime.fromisoformat(rt["expires_at"].replace("Z", "+00:00")) > now
            )
        ]
        # Keep only last 10
        if len(refresh_tokens) > 10:
            refresh_tokens = refresh_tokens[-10:]

        user["refresh_tokens"] = refresh_tokens
        user["updated_at"] = now.isoformat()
        await self.db.put(user)

    def _user_to_response(self, user: dict) -> UserResponse:
        """Convert CouchDB user document to UserResponse."""
        user_email = user.get("email") or f"{user['_id']}@unknown.oauth"
        user_name = user.get("name") or user_email.split("@")[0]

        return UserResponse(
            id=user["_id"],
            email=user_email,
            name=user_name,
            avatar_base64=user.get("avatar_base64"),
            bio=user.get("bio"),
            public_url_slug=user.get("public_url_slug"),
            locale=user.get("locale", "en"),
            created_at=user.get("created_at"),
            updated_at=user.get("updated_at"),
        )
