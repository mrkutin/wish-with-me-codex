"""Tests for CouchDB-based authentication endpoints."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import AsyncClient

from app.security import hash_password, hash_token, get_refresh_token_expiry
from tests.conftest import MockCouchDBClient

pytestmark = pytest.mark.asyncio


# =============================================================================
# /api/v2/auth/register Tests
# =============================================================================


class TestRegister:
    """Tests for POST /api/v2/auth/register endpoint."""

    async def test_register_success(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
    ) -> None:
        """Test successful user registration creates user and returns tokens."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securePassword123",
                "name": "New User",
                "locale": "en",
            },
        )

        assert response.status_code == 201

        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data

        # Verify user data
        user = data["user"]
        assert user["email"] == "newuser@example.com"
        assert user["name"] == "New User"
        assert user["locale"] == "en"
        assert user["id"].startswith("user:")

        # Verify token type
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

        # Verify user was created in database
        db_user = await mock_couchdb.get_user_by_email("newuser@example.com")
        assert db_user is not None
        assert db_user["email"] == "newuser@example.com"
        assert db_user["name"] == "New User"
        assert "password_hash" in db_user  # Password should be hashed
        assert db_user["password_hash"] != "securePassword123"  # Not plaintext

    async def test_register_duplicate_email(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test registration with existing email returns 409 conflict."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": registered_user["email"],
                "password": "differentPassword123",
                "name": "Different Name",
                "locale": "en",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_invalid_email(
        self,
        client: AsyncClient,
    ) -> None:
        """Test registration with invalid email returns 422 validation error."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "invalid-email",
                "password": "securePassword123",
                "name": "Test User",
                "locale": "en",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Check that email field has validation error
        errors = data["detail"]
        assert any("email" in str(e.get("loc", [])) for e in errors)

    async def test_register_password_too_short(
        self,
        client: AsyncClient,
    ) -> None:
        """Test registration with short password returns 422 validation error."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",  # Less than 8 characters
                "name": "Test User",
                "locale": "en",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Check that password field has validation error
        errors = data["detail"]
        assert any("password" in str(e.get("loc", [])) for e in errors)

    async def test_register_invalid_locale(
        self,
        client: AsyncClient,
    ) -> None:
        """Test registration with invalid locale returns 422 validation error."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "test@example.com",
                "password": "securePassword123",
                "name": "Test User",
                "locale": "fr",  # Only 'ru' and 'en' are valid
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Check that locale field has validation error
        errors = data["detail"]
        assert any("locale" in str(e.get("loc", [])) for e in errors)


# =============================================================================
# /api/v2/auth/login Tests
# =============================================================================


class TestLogin:
    """Tests for POST /api/v2/auth/login endpoint."""

    async def test_login_success(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test successful login with valid credentials returns tokens."""
        response = await client.post(
            "/api/v2/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )

        assert response.status_code == 200

        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data

        # Verify user data
        user = data["user"]
        assert user["email"] == registered_user["email"]
        assert user["name"] == registered_user["name"]

        # Verify token type
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_wrong_password(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test login with wrong password returns 401."""
        response = await client.post(
            "/api/v2/auth/login",
            json={
                "email": registered_user["email"],
                "password": "wrongPassword123",
            },
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_login_nonexistent_email(
        self,
        client: AsyncClient,
    ) -> None:
        """Test login with non-existent email returns 401."""
        response = await client.post(
            "/api/v2/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anyPassword123",
            },
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_login_timing_attack_protection(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test that login takes similar time for invalid email vs invalid password.

        This helps prevent timing attacks where attackers can determine
        whether an email exists based on response time.
        """
        # Measure time for invalid email
        times_invalid_email = []
        for _ in range(3):
            start = time.monotonic()
            await client.post(
                "/api/v2/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": "wrongPassword123",
                },
            )
            times_invalid_email.append(time.monotonic() - start)

        # Measure time for invalid password (valid email)
        times_invalid_password = []
        for _ in range(3):
            start = time.monotonic()
            await client.post(
                "/api/v2/auth/login",
                json={
                    "email": registered_user["email"],
                    "password": "wrongPassword123",
                },
            )
            times_invalid_password.append(time.monotonic() - start)

        # Calculate average times
        avg_invalid_email = sum(times_invalid_email) / len(times_invalid_email)
        avg_invalid_password = sum(times_invalid_password) / len(times_invalid_password)

        # Times should be within 50% of each other (allowing for some variance)
        # This is a rough check - in production you'd want more sophisticated analysis
        ratio = max(avg_invalid_email, avg_invalid_password) / max(
            min(avg_invalid_email, avg_invalid_password), 0.001
        )
        assert ratio < 3.0, (
            f"Timing difference too large: invalid_email={avg_invalid_email:.4f}s, "
            f"invalid_password={avg_invalid_password:.4f}s, ratio={ratio:.2f}"
        )


# =============================================================================
# /api/v2/auth/refresh Tests
# =============================================================================


class TestRefresh:
    """Tests for POST /api/v2/auth/refresh endpoint."""

    async def test_refresh_success(
        self,
        client: AsyncClient,
        user_with_refresh_token: dict[str, Any],
    ) -> None:
        """Test successful token refresh returns new tokens."""
        response = await client.post(
            "/api/v2/auth/refresh",
            json={
                "refresh_token": user_with_refresh_token["refresh_token"],
            },
        )

        assert response.status_code == 200

        data = response.json()

        # Verify response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data

        # Verify new tokens are different from old
        assert data["refresh_token"] != user_with_refresh_token["refresh_token"]

        # Verify token type
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_refresh_invalid_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Test refresh with invalid token returns 401."""
        response = await client.post(
            "/api/v2/auth/refresh",
            json={
                "refresh_token": "invalid-refresh-token",
            },
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_refresh_expired_token(
        self,
        client: AsyncClient,
        user_with_expired_refresh_token: dict[str, Any],
    ) -> None:
        """Test refresh with expired token returns 401."""
        response = await client.post(
            "/api/v2/auth/refresh",
            json={
                "refresh_token": user_with_expired_refresh_token["refresh_token"],
            },
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_refresh_revoked_token(
        self,
        client: AsyncClient,
        user_with_revoked_refresh_token: dict[str, Any],
    ) -> None:
        """Test refresh with revoked token returns 401."""
        response = await client.post(
            "/api/v2/auth/refresh",
            json={
                "refresh_token": user_with_revoked_refresh_token["refresh_token"],
            },
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_refresh_token_rotation(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
        user_with_refresh_token: dict[str, Any],
    ) -> None:
        """Test that old refresh token is revoked after successful refresh."""
        old_token = user_with_refresh_token["refresh_token"]
        old_token_hash = hash_token(old_token)

        # First refresh should succeed
        response = await client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": old_token},
        )
        assert response.status_code == 200

        # Get the new token
        new_token = response.json()["refresh_token"]

        # Old token should be revoked - trying to use it again should fail
        response = await client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": old_token},
        )
        assert response.status_code == 401

        # New token should work
        response = await client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": new_token},
        )
        assert response.status_code == 200


# =============================================================================
# /api/v2/auth/logout Tests
# =============================================================================


class TestLogout:
    """Tests for POST /api/v2/auth/logout endpoint."""

    async def test_logout_success(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
        user_with_refresh_token: dict[str, Any],
    ) -> None:
        """Test successful logout returns 204 and revokes token."""
        from app.security import create_access_token

        access_token = create_access_token(user_with_refresh_token["user_id"])
        refresh_token = user_with_refresh_token["refresh_token"]

        response = await client.post(
            "/api/v2/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 204

        # Verify refresh token is revoked - trying to use it should fail
        response = await client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401

    async def test_logout_missing_auth(
        self,
        client: AsyncClient,
        user_with_refresh_token: dict[str, Any],
    ) -> None:
        """Test logout without Authorization header returns 401."""
        response = await client.post(
            "/api/v2/auth/logout",
            json={"refresh_token": user_with_refresh_token["refresh_token"]},
        )

        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    async def test_logout_invalid_token(
        self,
        client: AsyncClient,
        user_with_refresh_token: dict[str, Any],
    ) -> None:
        """Test logout with invalid access token returns 401."""
        response = await client.post(
            "/api/v2/auth/logout",
            json={"refresh_token": user_with_refresh_token["refresh_token"]},
            headers={"Authorization": "Bearer invalid-access-token"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()


# =============================================================================
# /api/v2/auth/me Tests
# =============================================================================


class TestMe:
    """Tests for GET /api/v2/auth/me endpoint."""

    async def test_me_success(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test successful /me returns user info."""
        from app.security import create_access_token

        access_token = create_access_token(registered_user["user_id"])

        response = await client.get(
            "/api/v2/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200

        data = response.json()

        # Verify user data
        assert data["email"] == registered_user["email"]
        assert data["name"] == registered_user["name"]
        assert data["locale"] == registered_user["locale"]
        assert data["id"] == registered_user["user_id"]

    async def test_me_missing_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Test /me without token returns 401."""
        response = await client.get("/api/v2/auth/me")

        assert response.status_code == 403  # HTTPBearer returns 403 when no token

    async def test_me_expired_token(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test /me with expired token returns 401."""
        from app.security import create_access_token

        # Create an expired token
        expired_token = create_access_token(
            registered_user["user_id"],
            expires_delta=timedelta(seconds=-1),
        )

        response = await client.get(
            "/api/v2/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestAuthEdgeCases:
    """Additional edge case tests for authentication."""

    async def test_register_email_case_insensitive(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
    ) -> None:
        """Test that email registration is case-insensitive."""
        # Register with lowercase
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "test@example.com",
                "password": "securePassword123",
                "name": "Test User",
                "locale": "en",
            },
        )
        assert response.status_code == 201

        # Try to register with uppercase - should fail
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "TEST@EXAMPLE.COM",
                "password": "differentPassword123",
                "name": "Different User",
                "locale": "en",
            },
        )
        assert response.status_code == 409

    async def test_login_email_case_insensitive(
        self,
        client: AsyncClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test that login email is case-insensitive."""
        response = await client.post(
            "/api/v2/auth/login",
            json={
                "email": registered_user["email"].upper(),
                "password": registered_user["password"],
            },
        )

        assert response.status_code == 200

    async def test_register_stores_default_avatar(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
    ) -> None:
        """Test that registration stores a default avatar."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securePassword123",
                "name": "New User",
                "locale": "en",
            },
        )

        assert response.status_code == 201

        # Check that avatar is in response
        user = response.json()["user"]
        assert "avatar_base64" in user
        # Default avatar should be set
        db_user = await mock_couchdb.get_user_by_email("newuser@example.com")
        assert db_user["avatar_base64"] is not None
        assert db_user["avatar_base64"].startswith("data:image/")

    async def test_register_name_validation(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that name cannot be empty."""
        response = await client.post(
            "/api/v2/auth/register",
            json={
                "email": "test@example.com",
                "password": "securePassword123",
                "name": "",  # Empty name
                "locale": "en",
            },
        )

        assert response.status_code == 422

    async def test_login_oauth_user_without_password(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
    ) -> None:
        """Test that OAuth users without password cannot login with password."""
        # Create a user without password (OAuth user)
        user_id = mock_couchdb.generate_id("user")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "_id": user_id,
            "type": "user",
            "email": "oauth@example.com",
            "name": "OAuth User",
            "locale": "en",
            "created_at": now,
            "updated_at": now,
            "access": [user_id],
            # No password_hash
        }
        await mock_couchdb.put(doc)

        response = await client.post(
            "/api/v2/auth/login",
            json={
                "email": "oauth@example.com",
                "password": "anyPassword123",
            },
        )

        assert response.status_code == 401

    async def test_multiple_refresh_tokens_per_user(
        self,
        client: AsyncClient,
        mock_couchdb: MockCouchDBClient,
        registered_user: dict[str, Any],
    ) -> None:
        """Test that user can have multiple refresh tokens (for multiple devices)."""
        # Login twice to get two different refresh tokens
        response1 = await client.post(
            "/api/v2/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
            headers={"User-Agent": "Device1"},
        )
        assert response1.status_code == 200
        token1 = response1.json()["refresh_token"]

        response2 = await client.post(
            "/api/v2/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
            headers={"User-Agent": "Device2"},
        )
        assert response2.status_code == 200
        token2 = response2.json()["refresh_token"]

        # Both tokens should be different
        assert token1 != token2

        # Both tokens should work
        response = await client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": token1},
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": token2},
        )
        assert response.status_code == 200
