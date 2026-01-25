"""Tests for OAuth endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import SocialAccount, User
from app.oauth.schemas import OAuthProvider, OAuthUserInfo
from app.services.user import UserService


@pytest.fixture
def mock_oauth_user_info():
    """Sample OAuth user info."""
    return OAuthUserInfo(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-123456",
        email="oauth@example.com",
        name="OAuth User",
        avatar_url="https://example.com/avatar.jpg",
        raw_data={"sub": "google-123456"},
    )


@pytest.mark.asyncio
async def test_get_providers_empty(client: AsyncClient):
    """Test getting available providers when none configured."""
    response = await client.get("/api/v1/oauth/providers")

    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    # By default, no providers are configured in test environment
    assert isinstance(data["providers"], list)


@pytest.mark.asyncio
async def test_authorize_unconfigured_provider(client: AsyncClient):
    """Test OAuth authorize with unconfigured provider fails."""
    response = await client.get("/api/v1/oauth/google/authorize?redirect=false")

    assert response.status_code == 400
    assert "not configured" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_invalid_state(client: AsyncClient):
    """Test OAuth callback with invalid state redirects with error."""
    response = await client.get(
        "/api/v1/oauth/google/callback",
        params={"code": "auth-code", "state": "invalid-state"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "error=" in response.headers["location"]


@pytest.mark.asyncio
async def test_callback_provider_error(client: AsyncClient):
    """Test OAuth callback with provider error redirects with error."""
    response = await client.get(
        "/api/v1/oauth/google/callback",
        params={
            "code": "dummy-code",  # Still need code param even with error
            "error": "access_denied",
            "error_description": "User denied access",
            "state": "some-state",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "error=" in location


@pytest.mark.asyncio
async def test_get_connected_accounts_unauthenticated(client: AsyncClient):
    """Test getting connected accounts without auth fails."""
    response = await client.get("/api/v1/oauth/connected")

    # HTTPBearer returns 403 for missing credentials
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_connected_accounts_authenticated(
    client: AsyncClient, user_data: dict
):
    """Test getting connected accounts with auth succeeds."""
    # Register user
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    access_token = register_response.json()["access_token"]

    response = await client.get(
        "/api/v1/oauth/connected",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert "has_password" in data
    assert data["has_password"] is True
    assert data["accounts"] == []


@pytest.mark.asyncio
async def test_unlink_not_linked_provider(client: AsyncClient, user_data: dict):
    """Test unlinking a provider that's not linked fails."""
    # Register user
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    access_token = register_response.json()["access_token"]

    response = await client.delete(
        "/api/v1/oauth/google/unlink",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    assert "not linked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unlink_unauthenticated(client: AsyncClient):
    """Test unlinking without auth fails."""
    response = await client.delete("/api/v1/oauth/google/unlink")

    # HTTPBearer returns 403 for missing credentials
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_link_initiate_unauthenticated(client: AsyncClient):
    """Test initiating link flow without auth fails."""
    response = await client.post("/api/v1/oauth/google/link/initiate")

    # HTTPBearer returns 403 for missing credentials
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_link_initiate_unconfigured_provider(
    client: AsyncClient, user_data: dict
):
    """Test linking unconfigured provider fails."""
    # Register user
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    access_token = register_response.json()["access_token"]

    response = await client.post(
        "/api/v1/oauth/google/link/initiate",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    assert "not configured" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_service_unlink_safety_check(
    db_session: AsyncSession, mock_oauth_user_info: OAuthUserInfo
):
    """Test that unlinking fails if it's the only auth method."""
    from app.services.oauth import OAuthService

    # Create a user without password (OAuth-only)
    user_service = UserService(db_session)
    from app.schemas.user import UserCreate
    from app.security import DEFAULT_AVATAR_BASE64

    user = await user_service.create(
        UserCreate(
            email="oauthonly@example.com",
            password=None,
            name="OAuth Only User",
            locale="en",
            avatar_base64=DEFAULT_AVATAR_BASE64,
        )
    )

    # Add a social account
    social_account = SocialAccount(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE.value,
        provider_user_id="google-123",
        email="oauthonly@example.com",
    )
    db_session.add(social_account)
    await db_session.flush()
    await db_session.commit()

    # Try to unlink - should fail
    oauth_service = OAuthService(db_session)

    with pytest.raises(ValueError) as exc_info:
        await oauth_service.unlink_account(user.id, OAuthProvider.GOOGLE)

    assert "cannot unlink" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_oauth_service_link_account(
    db_session: AsyncSession, mock_oauth_user_info: OAuthUserInfo
):
    """Test linking OAuth account to existing user."""
    from app.services.oauth import OAuthService

    # Create a user with password
    user_service = UserService(db_session)
    from app.schemas.user import UserCreate
    from app.security import DEFAULT_AVATAR_BASE64

    user = await user_service.create(
        UserCreate(
            email="existing@example.com",
            password="securePassword123",
            name="Existing User",
            locale="en",
            avatar_base64=DEFAULT_AVATAR_BASE64,
        )
    )
    await db_session.commit()

    # Link OAuth account
    oauth_service = OAuthService(db_session)
    social_account = await oauth_service.link_account(user.id, mock_oauth_user_info)
    await db_session.commit()

    assert social_account.user_id == user.id
    assert social_account.provider == OAuthProvider.GOOGLE.value
    assert social_account.provider_user_id == "google-123456"
    assert social_account.email == "oauth@example.com"


@pytest.mark.asyncio
async def test_oauth_service_duplicate_link(
    db_session: AsyncSession, mock_oauth_user_info: OAuthUserInfo
):
    """Test linking same provider twice fails."""
    from app.services.oauth import OAuthService, DuplicateLinkError

    # Create a user with password
    user_service = UserService(db_session)
    from app.schemas.user import UserCreate
    from app.security import DEFAULT_AVATAR_BASE64

    user = await user_service.create(
        UserCreate(
            email="existing@example.com",
            password="securePassword123",
            name="Existing User",
            locale="en",
            avatar_base64=DEFAULT_AVATAR_BASE64,
        )
    )
    await db_session.commit()

    # Link OAuth account
    oauth_service = OAuthService(db_session)
    await oauth_service.link_account(user.id, mock_oauth_user_info)
    await db_session.commit()

    # Try to link again - should fail
    with pytest.raises(DuplicateLinkError):
        await oauth_service.link_account(user.id, mock_oauth_user_info)


@pytest.mark.asyncio
async def test_oauth_service_authenticate_new_user(
    db_session: AsyncSession, mock_oauth_user_info: OAuthUserInfo
):
    """Test OAuth creates new user when none exists."""
    from app.services.oauth import OAuthService

    oauth_service = OAuthService(db_session)
    auth_response, is_new = await oauth_service.authenticate_or_create(
        mock_oauth_user_info
    )
    await db_session.commit()

    assert is_new is True
    assert auth_response.user.email == "oauth@example.com"
    assert auth_response.user.name == "OAuth User"
    assert auth_response.access_token is not None
    assert auth_response.refresh_token is not None


@pytest.mark.asyncio
async def test_oauth_service_authenticate_existing_linked(
    db_session: AsyncSession, mock_oauth_user_info: OAuthUserInfo
):
    """Test OAuth logs in existing user with linked account."""
    from app.services.oauth import OAuthService

    oauth_service = OAuthService(db_session)

    # Create user via OAuth first time
    auth_response1, _ = await oauth_service.authenticate_or_create(mock_oauth_user_info)
    await db_session.commit()

    # Login again with same OAuth
    auth_response2, is_new = await oauth_service.authenticate_or_create(
        mock_oauth_user_info
    )
    await db_session.commit()

    assert is_new is False
    assert auth_response2.user.id == auth_response1.user.id


@pytest.mark.asyncio
async def test_oauth_service_email_conflict(
    db_session: AsyncSession, mock_oauth_user_info: OAuthUserInfo
):
    """Test OAuth with conflicting email raises error."""
    from app.services.oauth import OAuthService, EmailConflictError

    # Create a user with the same email but not linked
    user_service = UserService(db_session)
    from app.schemas.user import UserCreate
    from app.security import DEFAULT_AVATAR_BASE64

    await user_service.create(
        UserCreate(
            email="oauth@example.com",  # Same email as mock_oauth_user_info
            password="securePassword123",
            name="Existing User",
            locale="en",
            avatar_base64=DEFAULT_AVATAR_BASE64,
        )
    )
    await db_session.commit()

    # Try OAuth with same email - should raise conflict
    oauth_service = OAuthService(db_session)

    with pytest.raises(EmailConflictError) as exc_info:
        await oauth_service.authenticate_or_create(mock_oauth_user_info)

    assert exc_info.value.email == "oauth@example.com"
    assert exc_info.value.provider == OAuthProvider.GOOGLE


@pytest.mark.asyncio
async def test_oauth_state_generation_and_verification(db_session: AsyncSession):
    """Test OAuth state parameter generation and verification."""
    from app.services.oauth import OAuthService

    oauth_service = OAuthService(db_session)

    # Test login state
    login_state = oauth_service._generate_state("login")
    verified = oauth_service._verify_state(login_state)

    assert verified is not None
    assert verified["action"] == "login"
    assert verified["user_id"] is None

    # Test link state with user_id
    user_id = uuid4()
    link_state = oauth_service._generate_state("link", user_id)
    verified = oauth_service._verify_state(link_state)

    assert verified is not None
    assert verified["action"] == "link"
    assert verified["user_id"] == user_id


@pytest.mark.asyncio
async def test_oauth_state_tampering_detected(db_session: AsyncSession):
    """Test that tampered state is rejected."""
    from app.services.oauth import OAuthService

    oauth_service = OAuthService(db_session)

    state = oauth_service._generate_state("login")

    # Tamper with the state
    tampered_state = state[:-5] + "xxxxx"
    verified = oauth_service._verify_state(tampered_state)

    assert verified is None


@pytest.mark.asyncio
async def test_oauth_state_wrong_action_rejected(db_session: AsyncSession):
    """Test that state with wrong expected action is rejected."""
    from app.services.oauth import OAuthService

    oauth_service = OAuthService(db_session)

    login_state = oauth_service._generate_state("login")
    verified = oauth_service._verify_state(login_state, expected_action="link")

    assert verified is None
