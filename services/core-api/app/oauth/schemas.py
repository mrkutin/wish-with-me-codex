"""OAuth schemas and enums."""

from datetime import date
from enum import Enum
from pydantic import BaseModel, EmailStr, field_validator


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    YANDEX = "yandex"


class OAuthUserInfo(BaseModel):
    """Normalized user info from OAuth provider."""

    provider: OAuthProvider
    provider_user_id: str
    email: str | None = None  # Use str instead of EmailStr to avoid validation errors

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        """Normalize email - convert empty strings to None."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.strip().lower()
        return v
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
