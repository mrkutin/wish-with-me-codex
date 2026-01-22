"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, user_data: dict):
    """Test successful user registration."""
    response = await client.post("/api/v1/auth/register", json=user_data)

    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == user_data["email"]
    assert data["user"]["name"] == user_data["name"]
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, user_data: dict):
    """Test registration with duplicate email fails."""
    # First registration
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201

    # Duplicate registration
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient, user_data: dict):
    """Test registration with invalid email fails."""
    user_data["email"] = "invalid-email"
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient, user_data: dict):
    """Test registration with short password fails."""
    user_data["password"] = "short"
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, user_data: dict):
    """Test successful login."""
    # Register first
    await client.post("/api/v1/auth/register", json=user_data)

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user_data: dict):
    """Test login with wrong password fails."""
    # Register first
    await client.post("/api/v1/auth/register", json=user_data)

    # Login with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": "wrongPassword"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with nonexistent user fails."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "somePassword"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, user_data: dict):
    """Test successful token refresh."""
    # Register and get tokens
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    refresh_token = register_response.json()["refresh_token"]

    # Refresh token
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token should be different (token rotation)
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    """Test refresh with invalid token fails."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, user_data: dict):
    """Test successful logout."""
    # Register and get tokens
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    data = register_response.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 204

    # Verify refresh token is revoked
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401
