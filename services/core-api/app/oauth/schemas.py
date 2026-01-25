"""OAuth schemas and enums."""

from datetime import date
from enum import Enum
from pydantic import BaseModel, EmailStr


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    APPLE = "apple"
    YANDEX = "yandex"
    SBER = "sber"


class OAuthUserInfo(BaseModel):
    """Normalized user info from OAuth provider."""

    provider: OAuthProvider
    provider_user_id: str
    email: EmailStr | None = None
    name: str | None = None
    avatar_url: str | None = None
    birthday: date | None = None
    raw_data: dict | None = None


class OAuthAuthorizeResponse(BaseModel):
    """Response for OAuth authorization URL."""

    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Request for OAuth callback."""

    code: str
    state: str


class OAuthLinkRequest(BaseModel):
    """Request to link OAuth account."""

    code: str
    state: str


class ConnectedAccountResponse(BaseModel):
    """Response for a connected OAuth account."""

    provider: str
    email: str | None = None
    connected_at: str


class OAuthError(BaseModel):
    """OAuth error response."""

    error: str
    error_description: str | None = None
