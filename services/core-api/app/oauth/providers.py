"""OAuth provider configuration and registry."""

import logging
import time
from datetime import date, datetime
from typing import Any

import httpx
import jwt
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


def _generate_apple_client_secret() -> str | None:
    """Generate Apple client secret JWT.

    Apple requires a JWT signed with your private key as the client secret.
    The JWT is valid for up to 6 months.
    """
    if not all([
        settings.apple_team_id,
        settings.apple_key_id,
        settings.apple_private_key,
        settings.apple_client_id,
    ]):
        return None

    now = int(time.time())
    payload = {
        "iss": settings.apple_team_id,
        "iat": now,
        "exp": now + 86400 * 180,  # 180 days
        "aud": "https://appleid.apple.com",
        "sub": settings.apple_client_id,
    }

    headers = {
        "alg": "ES256",
        "kid": settings.apple_key_id,
    }

    return jwt.encode(
        payload,
        settings.apple_private_key,
        algorithm="ES256",
        headers=headers,
    )


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
                # Request birthday scope from People API
                "scope": "openid email profile https://www.googleapis.com/auth/user.birthday.read",
            },
        )
        _registered_providers.add("google")

    # Apple - Manual configuration
    if settings.apple_client_id and settings.apple_team_id:
        apple_secret = _generate_apple_client_secret()
        if apple_secret:
            oauth_registry.register(
                name="apple",
                client_id=settings.apple_client_id,
                client_secret=apple_secret,
                authorize_url="https://appleid.apple.com/auth/authorize",
                access_token_url="https://appleid.apple.com/auth/token",
                client_kwargs={
                    "scope": "name email",
                    "response_mode": "form_post",
                },
            )
            _registered_providers.add("apple")

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
                "scope": "login:email login:info login:avatar login:birthday",
            },
        )
        _registered_providers.add("yandex")

    # Sber ID - Manual configuration
    if settings.sber_client_id and settings.sber_client_secret:
        oauth_registry.register(
            name="sber",
            client_id=settings.sber_client_id,
            client_secret=settings.sber_client_secret,
            authorize_url="https://online.sberbank.ru/CSAFront/oidc/authorize",
            access_token_url="https://online.sberbank.ru/CSAFront/oidc/token",
            userinfo_endpoint="https://online.sberbank.ru/CSAFront/oidc/userinfo",
            client_kwargs={
                "scope": "openid name email",
            },
        )
        _registered_providers.add("sber")


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
    elif provider == OAuthProvider.APPLE:
        return _parse_apple_user(token, userinfo)
    elif provider == OAuthProvider.YANDEX:
        return _parse_yandex_user(token, userinfo)
    elif provider == OAuthProvider.SBER:
        return _parse_sber_user(token, userinfo)
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
            print(f"[DEBUG] People API response status: {response.status_code}", flush=True)
            print(f"[DEBUG] People API response body: {response.text[:500]}", flush=True)
            if response.status_code == 200:
                data = response.json()
                birthdays = data.get("birthdays", [])
                print(f"[DEBUG] Birthdays from API: {birthdays}", flush=True)
                for bday in birthdays:
                    bday_date = bday.get("date", {})
                    year = bday_date.get("year")
                    month = bday_date.get("month")
                    day = bday_date.get("day")
                    print(f"[DEBUG] Birthday date parts: year={year}, month={month}, day={day}", flush=True)
                    # Only return birthday if we have complete date including year
                    # Google may omit year for privacy - we skip those
                    if year and month and day:
                        return date(year, month, day)
                print("[DEBUG] Google birthday found but missing year, skipping", flush=True)
            elif response.status_code == 403:
                print("[DEBUG] User did not grant birthday permission to Google", flush=True)
            elif response.status_code == 401:
                print("[DEBUG] Google access token invalid for People API", flush=True)
            else:
                print(f"[DEBUG] Unexpected status from Google People API: {response.status_code}", flush=True)
    except httpx.RequestError as e:
        print(f"[DEBUG] Network error fetching Google birthday: {e}", flush=True)
    except (KeyError, ValueError, TypeError) as e:
        print(f"[DEBUG] Error parsing Google birthday response: {e}", flush=True)
    return None


async def _parse_google_user(token: dict, userinfo: dict | None) -> OAuthUserInfo:
    """Parse Google user info."""
    # Google returns userinfo in the token response via OIDC
    info = userinfo or token.get("userinfo", {})

    # Debug: print token structure to understand where access_token is
    print(f"[DEBUG] Google token type: {type(token)}", flush=True)
    print(f"[DEBUG] Google token keys: {list(token.keys()) if hasattr(token, 'keys') else 'no keys method'}", flush=True)
    print(f"[DEBUG] Google token content: {dict(token) if hasattr(token, 'keys') else token}", flush=True)

    # Fetch birthday from People API if we have an access token
    # Authlib may return token as OAuth2Token object with dict-like access
    birthday = None
    access_token = token.get("access_token")
    if not access_token and hasattr(token, "access_token"):
        access_token = token.access_token
    if access_token:
        print(f"[DEBUG] Found access_token, fetching birthday from People API", flush=True)
        birthday = await _fetch_google_birthday(access_token)
        print(f"[DEBUG] Birthday result: {birthday}", flush=True)
    else:
        print(f"[DEBUG] No access_token found in token", flush=True)

    return OAuthUserInfo(
        provider=OAuthProvider.GOOGLE,
        provider_user_id=info.get("sub", ""),
        email=info.get("email"),
        name=info.get("name"),
        avatar_url=info.get("picture"),
        birthday=birthday,
        raw_data=info,
    )


def _parse_apple_user(token: dict, userinfo: dict | None) -> OAuthUserInfo:
    """Parse Apple user info.

    Note: Apple only returns name on the first authorization.
    The name is passed in the form_post user parameter.
    """
    # Decode ID token to get user info
    id_token = token.get("id_token", "")
    if id_token:
        try:
            # Decode without verification (we already verified during token exchange)
            payload = jwt.decode(id_token, options={"verify_signature": False})
        except Exception as e:
            logger.warning(f"Failed to decode Apple ID token: {e}")
            payload = {}
    else:
        payload = {}

    # User info might come from form post (only on first auth)
    user_data = userinfo or {}
    name_data = user_data.get("name", {})
    name = None
    if name_data:
        first = name_data.get("firstName", "")
        last = name_data.get("lastName", "")
        name = f"{first} {last}".strip() or None

    return OAuthUserInfo(
        provider=OAuthProvider.APPLE,
        provider_user_id=payload.get("sub", ""),
        email=payload.get("email"),
        name=name,
        avatar_url=None,  # Apple doesn't provide avatar
        raw_data={"id_token_payload": payload, "user": user_data},
    )


def _parse_yandex_user(token: dict, userinfo: dict | None) -> OAuthUserInfo:
    """Parse Yandex user info."""
    info = userinfo or {}

    # Build avatar URL if available
    avatar_url = None
    if info.get("default_avatar_id"):
        avatar_url = f"https://avatars.yandex.net/get-yapic/{info['default_avatar_id']}/islands-200"

    # Extract birthday if available
    birthday = None
    if info.get("birthday"):
        try:
            birthday = datetime.strptime(info["birthday"], "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Failed to parse Yandex birthday: {info['birthday']}")

    return OAuthUserInfo(
        provider=OAuthProvider.YANDEX,
        provider_user_id=info.get("id", ""),
        email=info.get("default_email"),
        name=info.get("real_name") or info.get("display_name"),
        avatar_url=avatar_url,
        birthday=birthday,
        raw_data=info,
    )


def _parse_sber_user(token: dict, userinfo: dict | None) -> OAuthUserInfo:
    """Parse Sber ID user info."""
    info = userinfo or {}

    # Sber returns name in separate fields
    name = None
    if info.get("given_name") or info.get("family_name"):
        name = f"{info.get('given_name', '')} {info.get('family_name', '')}".strip()

    return OAuthUserInfo(
        provider=OAuthProvider.SBER,
        provider_user_id=info.get("sub", ""),
        email=info.get("email"),
        name=name,
        avatar_url=None,  # Sber doesn't provide avatar in standard flow
        raw_data=info,
    )
