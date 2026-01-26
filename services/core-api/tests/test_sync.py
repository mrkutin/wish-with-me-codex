"""Tests for sync endpoints (RxDB replication)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth_headers(client: AsyncClient, user_data: dict) -> dict:
    """Register user and return auth headers."""
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def another_auth_headers(client: AsyncClient, another_user_data: dict) -> dict:
    """Register another user and return auth headers."""
    response = await client.post("/api/v1/auth/register", json=another_user_data)
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def wishlist_id(client: AsyncClient, auth_headers: dict) -> str:
    """Create a wishlist and return its ID."""
    response = await client.post(
        "/api/v1/wishlists",
        json={"name": "Test Wishlist", "description": "Test description"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
async def item_id(client: AsyncClient, auth_headers: dict, wishlist_id: str) -> str:
    """Create an item and return its ID."""
    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={"title": "Test Item", "quantity": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestSyncPullWishlists:
    """Tests for GET /api/v1/sync/pull/wishlists."""

    @pytest.mark.asyncio
    async def test_pull_empty(self, client: AsyncClient, auth_headers: dict):
        """Test pull with no wishlists."""
        response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []
        assert data["checkpoint"] is None

    @pytest.mark.asyncio
    async def test_pull_with_wishlists(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str
    ):
        """Test pull returns user's wishlists."""
        response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["id"] == wishlist_id
        assert data["documents"][0]["_deleted"] is False
        assert data["checkpoint"] is not None

    @pytest.mark.asyncio
    async def test_pull_with_checkpoint(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str
    ):
        """Test pull with checkpoint returns only newer documents."""
        # First pull to get checkpoint
        response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=auth_headers,
        )
        checkpoint = response.json()["checkpoint"]

        # Create another wishlist
        await client.post(
            "/api/v1/wishlists",
            json={"name": "New Wishlist"},
            headers=auth_headers,
        )

        # Pull with checkpoint
        response = await client.get(
            "/api/v1/sync/pull/wishlists",
            params={
                "checkpoint_updated_at": checkpoint["updated_at"],
                "checkpoint_id": checkpoint["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["name"] == "New Wishlist"

    @pytest.mark.asyncio
    async def test_pull_excludes_other_users(
        self,
        client: AsyncClient,
        auth_headers: dict,
        another_auth_headers: dict,
        wishlist_id: str,
    ):
        """Test pull doesn't return other users' wishlists."""
        response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=another_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0

    @pytest.mark.asyncio
    async def test_pull_requires_auth(self, client: AsyncClient):
        """Test pull requires authentication."""
        response = await client.get("/api/v1/sync/pull/wishlists")
        assert response.status_code == 401


class TestSyncPushWishlists:
    """Tests for POST /api/v1/sync/push/wishlists."""

    @pytest.mark.asyncio
    async def test_push_new_wishlist(self, client: AsyncClient, auth_headers: dict):
        """Test pushing a new wishlist."""
        new_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/wishlists",
            json={
                "documents": [
                    {
                        "id": new_id,
                        "name": "Pushed Wishlist",
                        "description": "Created offline",
                        "is_public": False,
                        "created_at": now,
                        "updated_at": now,
                        "_deleted": False,
                    }
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["conflicts"] == []

        # Verify wishlist was created
        pull_response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=auth_headers,
        )
        documents = pull_response.json()["documents"]
        assert any(d["id"] == new_id for d in documents)

    @pytest.mark.asyncio
    async def test_push_update_existing(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str
    ):
        """Test updating existing wishlist via push."""
        # Get current timestamp (slightly in the future to ensure we win LWW)
        future_time = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/wishlists",
            json={
                "documents": [
                    {
                        "id": wishlist_id,
                        "name": "Updated Name",
                        "description": "Updated offline",
                        "is_public": False,
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "updated_at": future_time,
                        "_deleted": False,
                    }
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["conflicts"] == []

        # Verify update
        pull_response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=auth_headers,
        )
        doc = next(
            d for d in pull_response.json()["documents"] if d["id"] == wishlist_id
        )
        assert doc["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_push_lww_conflict(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str
    ):
        """Test LWW conflict resolution - server wins if newer."""
        # Push with old timestamp (server should win)
        old_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/wishlists",
            json={
                "documents": [
                    {
                        "id": wishlist_id,
                        "name": "Old Update",
                        "description": None,
                        "is_public": False,
                        "created_at": old_time,
                        "updated_at": old_time,
                        "_deleted": False,
                    }
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Should have conflict because server has newer version
        assert len(data["conflicts"]) == 1
        assert data["conflicts"][0]["document_id"] == wishlist_id
        assert "newer" in data["conflicts"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_push_delete(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str
    ):
        """Test deleting wishlist via push."""
        future_time = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/wishlists",
            json={
                "documents": [
                    {
                        "id": wishlist_id,
                        "name": "Test Wishlist",
                        "description": None,
                        "is_public": False,
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "updated_at": future_time,
                        "_deleted": True,
                    }
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["conflicts"] == []

        # Verify deletion
        pull_response = await client.get(
            "/api/v1/sync/pull/wishlists",
            headers=auth_headers,
        )
        doc = next(
            d for d in pull_response.json()["documents"] if d["id"] == wishlist_id
        )
        assert doc["_deleted"] is True

    @pytest.mark.asyncio
    async def test_push_requires_auth(self, client: AsyncClient):
        """Test push requires authentication."""
        response = await client.post(
            "/api/v1/sync/push/wishlists",
            json={"documents": []},
        )
        assert response.status_code == 401


class TestSyncPullItems:
    """Tests for GET /api/v1/sync/pull/items."""

    @pytest.mark.asyncio
    async def test_pull_items(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str, item_id: str
    ):
        """Test pull returns items from user's wishlists."""
        response = await client.get(
            "/api/v1/sync/pull/items",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["id"] == item_id
        assert data["documents"][0]["wishlist_id"] == wishlist_id

    @pytest.mark.asyncio
    async def test_pull_items_excludes_other_users(
        self,
        client: AsyncClient,
        auth_headers: dict,
        another_auth_headers: dict,
        wishlist_id: str,
        item_id: str,
    ):
        """Test pull doesn't return items from other users' wishlists."""
        response = await client.get(
            "/api/v1/sync/pull/items",
            headers=another_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0


class TestSyncPushItems:
    """Tests for POST /api/v1/sync/push/items."""

    @pytest.mark.asyncio
    async def test_push_new_item(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str
    ):
        """Test pushing a new item."""
        new_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/items",
            json={
                "documents": [
                    {
                        "id": new_id,
                        "wishlist_id": wishlist_id,
                        "title": "Pushed Item",
                        "description": "Created offline",
                        "price": "99.99",
                        "currency": "USD",
                        "quantity": 2,
                        "status": "pending",
                        "created_at": now,
                        "updated_at": now,
                        "_deleted": False,
                    }
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["conflicts"] == []

        # Verify item was created
        pull_response = await client.get(
            "/api/v1/sync/pull/items",
            headers=auth_headers,
        )
        documents = pull_response.json()["documents"]
        pushed_item = next((d for d in documents if d["id"] == new_id), None)
        assert pushed_item is not None
        assert pushed_item["title"] == "Pushed Item"
        assert pushed_item["price"] == "99.99"

    @pytest.mark.asyncio
    async def test_push_item_to_other_user_wishlist(
        self,
        client: AsyncClient,
        auth_headers: dict,
        another_auth_headers: dict,
        wishlist_id: str,
    ):
        """Test can't push item to another user's wishlist."""
        new_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/items",
            json={
                "documents": [
                    {
                        "id": new_id,
                        "wishlist_id": wishlist_id,  # belongs to first user
                        "title": "Malicious Item",
                        "quantity": 1,
                        "status": "pending",
                        "created_at": now,
                        "updated_at": now,
                        "_deleted": False,
                    }
                ]
            },
            headers=another_auth_headers,  # different user
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "unauthorized" in data["conflicts"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_push_item_lww_conflict(
        self, client: AsyncClient, auth_headers: dict, wishlist_id: str, item_id: str
    ):
        """Test LWW conflict for item updates."""
        old_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()

        response = await client.post(
            "/api/v1/sync/push/items",
            json={
                "documents": [
                    {
                        "id": item_id,
                        "wishlist_id": wishlist_id,
                        "title": "Old Update",
                        "quantity": 1,
                        "status": "pending",
                        "created_at": old_time,
                        "updated_at": old_time,
                        "_deleted": False,
                    }
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "newer" in data["conflicts"][0]["error"].lower()


class TestSyncInvalidCollection:
    """Tests for invalid collection names."""

    @pytest.mark.asyncio
    async def test_pull_invalid_collection(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test pull with invalid collection name."""
        response = await client.get(
            "/api/v1/sync/pull/invalid",
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_push_invalid_collection(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test push with invalid collection name."""
        response = await client.post(
            "/api/v1/sync/push/invalid",
            json={"documents": []},
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error
