"""Tests for item endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.fixture
def item_data() -> dict:
    """Sample item creation data (manual)."""
    return {
        "title": "Programming in Python",
        "description": "Comprehensive Python programming book",
        "price": 49.99,
        "currency": "USD",
        "quantity": 1,
    }


@pytest.fixture
def url_item_data() -> dict:
    """Sample item creation data (from URL)."""
    return {
        "title": "Loading...",
        "source_url": "https://www.amazon.com/example-product",
    }


@pytest.fixture
def minimal_item_data() -> dict:
    """Minimal item creation data."""
    return {
        "title": "Simple Item",
    }


async def register_and_login(client: AsyncClient, user_data: dict) -> str:
    """Helper to register and login, returning access token."""
    response = await client.post("/api/v1/auth/register", json=user_data)
    return response.json()["access_token"]


async def create_wishlist(client: AsyncClient, token: str) -> str:
    """Helper to create a wishlist, returning wishlist ID."""
    response = await client.post(
        "/api/v1/wishlists",
        json={"name": "Test Wishlist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_item_success(client: AsyncClient, user_data: dict, item_data: dict):
    """Test successful item creation."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == item_data["title"]
    assert data["description"] == item_data["description"]
    assert float(data["price"]) == item_data["price"]
    assert data["currency"] == item_data["currency"]
    assert data["quantity"] == item_data["quantity"]
    assert data["status"] == "pending"
    assert "id" in data
    assert "wishlist_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_item_minimal(client: AsyncClient, user_data: dict, minimal_item_data: dict):
    """Test item creation with minimal data."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=minimal_item_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == minimal_item_data["title"]
    assert data["description"] is None
    assert data["price"] is None
    assert data["quantity"] == 1  # Default value


@pytest.mark.asyncio
async def test_create_item_with_url_triggers_resolver(client: AsyncClient, user_data: dict):
    """Test item creation with source_url triggers background resolver."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Mock the resolver client to prevent actual HTTP call
    with patch("app.routers.items.ItemResolverClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_client_class.return_value = mock_instance
        mock_instance.resolve_item.return_value = {
            "title": "Resolved Product Title",
            "description": "Resolved description",
            "price": 99.99,
            "currency": "USD",
            "image_base64": "data:image/png;base64,abc123",
            "source_url": "https://www.amazon.com/example-product",
            "metadata": {"source": "amazon"},
        }

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/items",
            json={
                "title": "Loading...",
                "source_url": "https://www.amazon.com/example-product",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["source_url"] == "https://www.amazon.com/example-product"
        # Status starts as pending, background task will update it
        assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_item_unauthorized(client: AsyncClient, user_data: dict, item_data: dict):
    """Test item creation without authentication fails."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Try without token
    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
    )
    assert response.status_code == 403  # FastAPI returns 403 when no auth token provided


@pytest.mark.asyncio
async def test_create_item_wrong_user(
    client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
):
    """Test creating item in another user's wishlist returns 403."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    wishlist_id = await create_wishlist(client, token1)

    # User 2 tries to add item to user 1's wishlist
    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_item_invalid_url(client: AsyncClient, user_data: dict):
    """Test item creation with invalid URL fails validation."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={
            "title": "Test",
            "source_url": "not-a-valid-url",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_items_empty(client: AsyncClient, user_data: dict):
    """Test listing items when none exist."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}/items",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_items_with_data(client: AsyncClient, user_data: dict, item_data: dict):
    """Test listing items returns created items."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create two items
    await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={"title": "Second Item"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}/items",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_items_pagination(client: AsyncClient, user_data: dict):
    """Test item pagination."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create 5 items
    for i in range(5):
        await client.post(
            f"/api/v1/wishlists/{wishlist_id}/items",
            json={"title": f"Item {i}"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Get first page
    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}/items?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_get_item_success(client: AsyncClient, user_data: dict, item_data: dict):
    """Test retrieving a single item."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create item
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create_response.json()["id"]

    # Get item
    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["title"] == item_data["title"]


@pytest.mark.asyncio
async def test_get_item_not_found(client: AsyncClient, user_data: dict):
    """Test retrieving nonexistent item returns 404."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}/items/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_item_success(client: AsyncClient, user_data: dict, item_data: dict):
    """Test updating an item."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create item
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create_response.json()["id"]

    # Update item
    update_data = {
        "title": "Updated Title",
        "price": 59.99,
        "quantity": 2,
    }
    response = await client.patch(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == update_data["title"]
    assert float(data["price"]) == update_data["price"]
    assert data["quantity"] == update_data["quantity"]


@pytest.mark.asyncio
async def test_update_item_unauthorized(
    client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
):
    """Test updating another user's item returns 403."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    wishlist_id = await create_wishlist(client, token1)

    # User 1 creates item
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token1}"},
    )
    item_id = create_response.json()["id"]

    # User 2 tries to update
    response = await client.patch(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}",
        json={"title": "Hacked"},
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_item_success(client: AsyncClient, user_data: dict, item_data: dict):
    """Test deleting an item (soft delete)."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create item
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create_response.json()["id"]

    # Delete item
    response = await client.delete(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify it's gone from list
    list_response = await client.get(
        f"/api/v1/wishlists/{wishlist_id}/items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_item_unauthorized(
    client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
):
    """Test deleting another user's item returns 403."""
    token1 = await register_and_login(client, user_data)
    token2 = await register_and_login(client, another_user_data)

    wishlist_id = await create_wishlist(client, token1)

    # User 1 creates item
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token1}"},
    )
    item_id = create_response.json()["id"]

    # User 2 tries to delete
    response = await client.delete(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_retry_resolve_success(client: AsyncClient, user_data: dict):
    """Test retrying item resolution."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create item with URL
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={
            "title": "Test Item",
            "source_url": "https://example.com/product",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create_response.json()["id"]

    # Mock resolver for retry
    with patch("app.routers.items.ItemResolverClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_client_class.return_value = mock_instance
        mock_instance.resolve_item.return_value = {
            "title": "Resolved Title",
            "description": "Resolved description",
            "price": 49.99,
            "currency": "USD",
            "image_base64": None,
            "source_url": "https://example.com/product",
            "metadata": {},
        }

        # Trigger resolve
        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/items/{item_id}/resolve",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        # Note: Status change happens asynchronously in background task
        # In test environment, background task may not complete before response


@pytest.mark.asyncio
async def test_retry_resolve_no_source_url(client: AsyncClient, user_data: dict, item_data: dict):
    """Test retrying resolution on item without source_url fails."""
    token = await register_and_login(client, user_data)
    wishlist_id = await create_wishlist(client, token)

    # Create item without URL
    create_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create_response.json()["id"]

    # Try to resolve
    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}/resolve",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


# Note: Unique title constraint tests are PostgreSQL-specific and don't work with SQLite
# The partial index (WHERE deleted_at IS NULL) is not enforced the same way in SQLite
