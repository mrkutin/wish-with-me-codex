"""Tests for wishlist endpoints."""

import asyncio
import pytest
from httpx import AsyncClient


@pytest.fixture
def wishlist_data() -> dict:
    """Sample wishlist creation data."""
    return {
        "name": "Birthday 2026",
        "description": "Gifts I'd love for my birthday",
        "is_public": True,
    }


@pytest.fixture
def minimal_wishlist_data() -> dict:
    """Minimal wishlist creation data."""
    return {
        "name": "Holiday Wishlist",
    }


async def register_and_login(client: AsyncClient, user_data: dict) -> str:
    """Helper to register and login, returning access token."""
    response = await client.post("/api/v1/auth/register", json=user_data)
    if response.status_code != 201:
        print(f"Registration failed: {response.status_code}, {response.json()}")
        raise Exception(f"Registration failed with status {response.status_code}")
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_wishlist_success(client: AsyncClient, user_data: dict, wishlist_data: dict):
    """Test successful wishlist creation."""
    token = await register_and_login(client, user_data)

    response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == wishlist_data["name"]
    assert data["description"] == wishlist_data["description"]
    assert data["is_public"] == wishlist_data["is_public"]
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_wishlist_minimal(client: AsyncClient, user_data: dict, minimal_wishlist_data: dict):
    """Test wishlist creation with minimal data."""
    token = await register_and_login(client, user_data)

    response = await client.post(
        "/api/v1/wishlists",
        json=minimal_wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == minimal_wishlist_data["name"]
    assert data["description"] is None
    assert data["is_public"] is False  # Default value


@pytest.mark.asyncio
async def test_create_wishlist_unauthorized(client: AsyncClient, wishlist_data: dict):
    """Test wishlist creation without authentication fails."""
    response = await client.post("/api/v1/wishlists", json=wishlist_data)
    assert response.status_code == 403  # FastAPI returns 403 when no auth token provided


@pytest.mark.asyncio
async def test_create_wishlist_invalid_data(client: AsyncClient, user_data: dict):
    """Test wishlist creation with invalid data fails."""
    token = await register_and_login(client, user_data)

    # Missing required field
    response = await client.post(
        "/api/v1/wishlists",
        json={"description": "No name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Name too long
    response = await client.post(
        "/api/v1/wishlists",
        json={"name": "a" * 101},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_wishlists_empty(client: AsyncClient, user_data: dict):
    """Test listing wishlists when none exist."""
    token = await register_and_login(client, user_data)

    response = await client.get(
        "/api/v1/wishlists",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["wishlists"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_wishlists_with_data(client: AsyncClient, user_data: dict, wishlist_data: dict):
    """Test listing wishlists returns created wishlists."""
    token = await register_and_login(client, user_data)

    # Create two wishlists
    await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    await asyncio.sleep(0.01)  # Small delay to ensure different timestamps
    await client.post(
        "/api/v1/wishlists",
        json={"name": "Second Wishlist"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/wishlists",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["wishlists"]) == 2
    assert data["total"] == 2
    # Verify both wishlists are present
    wishlist_names = {w["name"] for w in data["wishlists"]}
    assert wishlist_names == {"Second Wishlist", wishlist_data["name"]}


@pytest.mark.asyncio
async def test_list_wishlists_pagination(client: AsyncClient, user_data: dict):
    """Test wishlist pagination."""
    token = await register_and_login(client, user_data)

    # Create 5 wishlists
    for i in range(5):
        await client.post(
            "/api/v1/wishlists",
            json={"name": f"Wishlist {i}"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Get first page (limit=2)
    response = await client.get(
        "/api/v1/wishlists?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["wishlists"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Get second page
    response = await client.get(
        "/api/v1/wishlists?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["wishlists"]) == 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_list_wishlists_isolation(
    client: AsyncClient, user_data: dict, another_user_data: dict, wishlist_data: dict
):
    """Test users can only see their own wishlists."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    # User 1 creates wishlist
    await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token1}"},
    )

    # User 2 should see empty list
    response = await client.get(
        "/api/v1/wishlists",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_wishlist_success(client: AsyncClient, user_data: dict, wishlist_data: dict):
    """Test retrieving a single wishlist."""
    token = await register_and_login(client, user_data)

    # Create wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    wishlist_id = create_response.json()["id"]

    # Get wishlist
    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == wishlist_id
    assert data["name"] == wishlist_data["name"]


@pytest.mark.asyncio
async def test_get_wishlist_not_found(client: AsyncClient, user_data: dict):
    """Test retrieving nonexistent wishlist returns 404."""
    token = await register_and_login(client, user_data)

    response = await client.get(
        "/api/v1/wishlists/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_wishlist_unauthorized(client: AsyncClient, user_data: dict, another_user_data: dict, wishlist_data: dict):
    """Test retrieving another user's wishlist returns 403."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    # User 1 creates wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token1}"},
    )
    wishlist_id = create_response.json()["id"]

    # User 2 tries to access
    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_wishlist_success(client: AsyncClient, user_data: dict, wishlist_data: dict):
    """Test updating a wishlist."""
    token = await register_and_login(client, user_data)

    # Create wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    wishlist_id = create_response.json()["id"]

    # Update wishlist
    update_data = {
        "name": "Updated Name",
        "description": "Updated description",
        "is_public": False,
    }
    response = await client.patch(
        f"/api/v1/wishlists/{wishlist_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["description"] == update_data["description"]
    assert data["is_public"] == update_data["is_public"]


@pytest.mark.asyncio
async def test_update_wishlist_partial(client: AsyncClient, user_data: dict, wishlist_data: dict):
    """Test partial update of wishlist."""
    token = await register_and_login(client, user_data)

    # Create wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    wishlist_id = create_response.json()["id"]
    original_description = create_response.json()["description"]

    # Update only name
    response = await client.patch(
        f"/api/v1/wishlists/{wishlist_id}",
        json={"name": "New Name Only"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name Only"
    assert data["description"] == original_description  # Unchanged


@pytest.mark.asyncio
async def test_update_wishlist_unauthorized(client: AsyncClient, user_data: dict, another_user_data: dict, wishlist_data: dict):
    """Test updating another user's wishlist returns 403."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    # User 1 creates wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token1}"},
    )
    wishlist_id = create_response.json()["id"]

    # User 2 tries to update
    response = await client.patch(
        f"/api/v1/wishlists/{wishlist_id}",
        json={"name": "Hacked"},
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_wishlist_success(client: AsyncClient, user_data: dict, wishlist_data: dict):
    """Test deleting a wishlist (soft delete)."""
    token = await register_and_login(client, user_data)

    # Create wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    wishlist_id = create_response.json()["id"]

    # Delete wishlist
    response = await client.delete(
        f"/api/v1/wishlists/{wishlist_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify it's gone from list
    list_response = await client.get(
        "/api/v1/wishlists",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.json()["total"] == 0

    # Verify get returns 404
    get_response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_wishlist_unauthorized(client: AsyncClient, user_data: dict, another_user_data: dict, wishlist_data: dict):
    """Test deleting another user's wishlist returns 403."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    # User 1 creates wishlist
    create_response = await client.post(
        "/api/v1/wishlists",
        json=wishlist_data,
        headers={"Authorization": f"Bearer {token1}"},
    )
    wishlist_id = create_response.json()["id"]

    # User 2 tries to delete
    response = await client.delete(
        f"/api/v1/wishlists/{wishlist_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403

    # Verify wishlist still exists for user 1
    get_response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert get_response.status_code == 200
