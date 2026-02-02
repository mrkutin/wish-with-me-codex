"""OAuth provider configuration and registry."""

import logging
from datetime import date, datetime

import httpx
from authlib.integrations.starlette_client import OAuth

from app.config import settings
from app.oauth.schemas import OAuthProvider, OAuthUserInfo

logger = logging.getLogger(__name__)

# Google People API endpoint for birthday
GOOGLE_PEOPLE_API_URL = "https://people.googleapis.com/v1/people/me"

# Create OAuth registry
oauth_registry = OAuth()

# Track which providers are registered
_registered_providers: set[str] = set()


def _register_providers() -> None:
    """Register all OAuth providers with the registry."""
    # Google - OIDC auto-discovery
    if settings.google_client_id and settings.google_client_secret:
        oauth_registry.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile",
            },
        )
        _registered_providers.add("google")

    # Yandex - Manual configuration
    if settings.yandex_client_id and settings.yandex_client_secret:
        oauth_registry.register(
            name="yandex",
            client_id=settings.yandex_client_id,
            client_secret=settings.yandex_client_secret,
            authorize_url="https://oauth.yandex.ru/authorize",
            access_token_url="https://oauth.yandex.ru/token",
            userinfo_endpoint="https://login.yandex.ru/info",
            client_kwargs={
                "scope": "login:email login:info login:avatar",
            },
        )
        _registered_providers.add("yandex")


# Register providers on module load
_register_providers()


def get_oauth_client(provider: OAuthProvider):
    """Get OAuth client for a provider.

    Args:
        provider: The OAuth provider enum value.

    Returns:
        The OAuth client if configured, None otherwise.

    Raises:
        ValueError: If provider is not configured.
    """
    if provider.value not in _registered_providers:
        raise ValueError(f"OAuth provider '{provider.value}' is not configured")
    return oauth_registry.create_client(provider.value)


def is_provider_configured(provider: OAuthProvider) -> bool:
    """Check if an OAuth provider is configured."""
    return provider.value in _registered_providers


def get_configured_providers() -> list[OAuthProvider]:
    """Get list of configured OAuth providers."""
    configured = []
    for provider in OAuthProvider:
        if is_provider_configured(provider):
            configured.append(provider)
    return configured


async def parse_user_info(provider: OAuthProvider, token: dict, userinfo: dict | None = None) -> OAuthUserInfo:
    """Parse user info from OAuth provider response.

    Args:
        provider: The OAuth provider.
        token: The token response from the provider.
        userinfo: Optional userinfo response (for providers that don't include it in token).

    Returns:
        Normalized user info.
    """
    if provider == OAuthProvider.GOOGLE:
        return await _parse_google_user(token, userinfo)
    elif provider == OAuthProvider.YANDEX:
        return _parse_yandex_user(token, userinfo)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _fetch_google_birthday(access_token: str) -> date | None:
    """Fetch birthday from Google People API.

    Args:
        access_token: The OAuth access token.

    Returns:
        Birthday date or None if not available or year not provided.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                GOOGLE_PEOPLE_API_URL,
                params={"personFields": "birthdays"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                birthdays = data.get("birthdays", [])
                for bday in birthdays:
                    bday_date = bday.get("date", {})
                    year = bday_date.get("year")
                    month = bday_date.get("month")
                    day = bday_date.get("day")
                    # Only return birthday if we have complete date including year
                    # Google may omit year for privacy - we skip those
                    if year and month and day:
                        return date(year, month, day)
                logger.debug("Google birthday found but missing year, skipping")
            elif response.status_code == 403:
                logger.debug("User did not grant birthday permission to Google")
            elif response.status_code == 401:
                logger.warning("Google access token invalid for People API")
            else:
                logger.warning(f"Unexpected status from Google People API: {response.status_code}")
    except httpx.RequestError as e:
        logger.warning(f"Network error fetching Google birthday: {e}")
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Error parsing Google birthday response: {e}")
    return None


async def _parse_google_user(token: dict, userinfo: dict | None) -> OAuthUserInfo:
    """Parse Google user info."""
    # Google returns userinfo in the token response via OIDC
    info = userinfo or token.get("userinfo", {})

    # Birthday requires user.birthday.read scope which needs Google verification
    # Skip birthday fetch - use basic profile scopes only
    birthday = None

    return OAuthUserInfo(
        provider=OAuthProvider.GOOGLE,
        provider_user_id=info.get("sub", ""),
        email=info.get("email"),
        name=info.get("name"),
        avatar_url=info.get("picture"),
        birthday=birthday,
        raw_data=info,
    )


def _parse_yandex_user(token: dict, userinfo: dict | None) -> OAuthUserInfo:
    """Parse Yandex user info."""
    info = userinfo or {}

    # Build avatar URL if available
    avatar_url = None
    if info.get("default_avatar_id"):
        avatar_url = f"https://avatars.yandex.net/get-yapic/{info['default_avatar_id']}/islands-200"

    # Birthday requires login:birthday scope which may trigger verification warning
    # Skip birthday - use basic profile scopes only
    birthday = None

    return OAuthUserInfo(
        provider=OAuthProvider.YANDEX,
        provider_user_id=info.get("id", ""),
        email=info.get("default_email"),
        name=info.get("real_name") or info.get("display_name"),
        avatar_url=avatar_url,
        birthday=birthday,
        raw_data=info,
    )
