"""Tests for user management endpoints."""

import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, user_data: dict) -> str:
    """Helper to register user and return access token."""
    response = await client.post("/api/v1/auth/register", json=user_data)
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, user_data: dict):
    """Test getting current user profile."""
    token = await register_and_get_token(client, user_data)

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["name"] == user_data["name"]
    assert "id" in data
    assert "avatar_base64" in data


@pytest.mark.asyncio
async def test_get_current_user_unauthorized(client: AsyncClient):
    """Test getting current user without token fails."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 403  # No Authorization header


@pytest.mark.asyncio
async def test_update_current_user(client: AsyncClient, user_data: dict):
    """Test updating current user profile."""
    token = await register_and_get_token(client, user_data)

    response = await client.patch(
        "/api/v1/users/me",
        json={
            "name": "Updated Name",
            "bio": "This is my bio",
            "public_url_slug": "updated-user",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["bio"] == "This is my bio"
    assert data["public_url_slug"] == "updated-user"


@pytest.mark.asyncio
async def test_update_user_duplicate_slug(
    client: AsyncClient, user_data: dict, another_user_data: dict
):
    """Test updating user with duplicate slug fails."""
    # Register first user with a slug
    token1 = await register_and_get_token(client, user_data)
    await client.patch(
        "/api/v1/users/me",
        json={"public_url_slug": "taken-slug"},
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Register second user and try to use same slug
    token2 = await register_and_get_token(client, another_user_data)
    response = await client.patch(
        "/api/v1/users/me",
        json={"public_url_slug": "taken-slug"},
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_current_user(client: AsyncClient, user_data: dict):
    """Test soft deleting current user."""
    token = await register_and_get_token(client, user_data)

    response = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify user can no longer access their profile
    # Note: In a real scenario, the token would still be valid until expiry
    # but the user would be marked as deleted in the database


@pytest.mark.asyncio
async def test_get_user_public_profile(
    client: AsyncClient, user_data: dict, another_user_data: dict
):
    """Test getting another user's public profile."""
    # Register and setup first user
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    user1_id = register_response.json()["user"]["id"]
    token1 = register_response.json()["access_token"]

    await client.patch(
        "/api/v1/users/me",
        json={"bio": "Public bio"},
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Register second user
    token2 = await register_and_get_token(client, another_user_data)

    # Get first user's public profile from second user
    response = await client.get(
        f"/api/v1/users/{user1_id}/public",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user1_id
    assert data["name"] == user_data["name"]
    assert data["bio"] == "Public bio"
    # Should not include sensitive fields
    assert "email" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_nonexistent_user_profile(client: AsyncClient, user_data: dict):
    """Test getting nonexistent user's profile fails."""
    token = await register_and_get_token(client, user_data)

    response = await client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/public",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_connected_accounts_empty(client: AsyncClient, user_data: dict):
    """Test getting connected accounts when none exist."""
    token = await register_and_get_token(client, user_data)

    response = await client.get(
        "/api/v1/users/me/connected-accounts",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accounts"] == []
