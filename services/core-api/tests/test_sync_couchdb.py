"""Tests for CouchDB-based sync endpoints.

Tests cover:
- Pull operations: access control, surprise mode, filtering
- Push operations: authorization, LWW conflict resolution, type validation
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.couchdb import CouchDBClient, ConflictError, DocumentNotFoundError
from app.main import app
from app.security import create_access_token


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def user_id() -> str:
    """Generate a test user ID."""
    return f"user:{uuid4()}"


@pytest.fixture
def another_user_id() -> str:
    """Generate another test user ID."""
    return f"user:{uuid4()}"


@pytest.fixture
def third_user_id() -> str:
    """Generate a third test user ID."""
    return f"user:{uuid4()}"


@pytest.fixture
def user_doc(user_id: str) -> dict[str, Any]:
    """Create a test user document."""
    return {
        "_id": user_id,
        "_rev": "1-abc",
        "type": "user",
        "email": "test@example.com",
        "name": "Test User",
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def another_user_doc(another_user_id: str) -> dict[str, Any]:
    """Create another test user document."""
    return {
        "_id": another_user_id,
        "_rev": "1-def",
        "type": "user",
        "email": "another@example.com",
        "name": "Another User",
        "access": [another_user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def auth_token(user_id: str) -> str:
    """Create a valid auth token for the test user."""
    return create_access_token(user_id)


@pytest.fixture
def another_auth_token(another_user_id: str) -> str:
    """Create a valid auth token for another user."""
    return create_access_token(another_user_id)


@pytest.fixture
def wishlist_id() -> str:
    """Generate a wishlist ID."""
    return f"wishlist:{uuid4()}"


@pytest.fixture
def another_wishlist_id() -> str:
    """Generate another wishlist ID."""
    return f"wishlist:{uuid4()}"


@pytest.fixture
def item_id() -> str:
    """Generate an item ID."""
    return f"item:{uuid4()}"


@pytest.fixture
def mark_id() -> str:
    """Generate a mark ID."""
    return f"mark:{uuid4()}"


@pytest.fixture
def bookmark_id() -> str:
    """Generate a bookmark ID."""
    return f"bookmark:{uuid4()}"


@pytest.fixture
def wishlist_doc(wishlist_id: str, user_id: str) -> dict[str, Any]:
    """Create a test wishlist document."""
    return {
        "_id": wishlist_id,
        "_rev": "1-wishlist",
        "type": "wishlist",
        "owner_id": user_id,
        "name": "Test Wishlist",
        "description": "Test description",
        "icon": "gift",
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def shared_wishlist_doc(
    another_wishlist_id: str,
    user_id: str,
    another_user_id: str,
) -> dict[str, Any]:
    """Create a wishlist shared between two users."""
    return {
        "_id": another_wishlist_id,
        "_rev": "1-sharedwishlist",
        "type": "wishlist",
        "owner_id": another_user_id,
        "name": "Shared Wishlist",
        "description": "Shared with test user",
        "icon": "star",
        "access": [another_user_id, user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def item_doc(item_id: str, wishlist_id: str, user_id: str) -> dict[str, Any]:
    """Create a test item document."""
    return {
        "_id": item_id,
        "_rev": "1-item",
        "type": "item",
        "wishlist_id": wishlist_id,
        "owner_id": user_id,
        "title": "Test Item",
        "description": "Test item description",
        "price": 100.00,
        "currency": "USD",
        "status": "resolved",
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mark_doc(
    mark_id: str,
    item_id: str,
    wishlist_id: str,
    user_id: str,
    another_user_id: str,
) -> dict[str, Any]:
    """Create a test mark document (by another_user on user's item)."""
    return {
        "_id": mark_id,
        "_rev": "1-mark",
        "type": "mark",
        "item_id": item_id,
        "wishlist_id": wishlist_id,
        "owner_id": user_id,  # Wishlist owner
        "marked_by": another_user_id,  # Who marked it
        "quantity": 1,
        "access": [another_user_id],  # Excludes owner (surprise mode)
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def bookmark_doc(bookmark_id: str, wishlist_id: str, user_id: str) -> dict[str, Any]:
    """Create a test bookmark document."""
    return {
        "_id": bookmark_id,
        "_rev": "1-bookmark",
        "type": "bookmark",
        "wishlist_id": wishlist_id,
        "owner_id": user_id,
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def deleted_wishlist_doc(user_id: str) -> dict[str, Any]:
    """Create a deleted wishlist document."""
    deleted_id = f"wishlist:{uuid4()}"
    return {
        "_id": deleted_id,
        "_rev": "2-deleted",
        "type": "wishlist",
        "owner_id": user_id,
        "name": "Deleted Wishlist",
        "access": [user_id],
        "_deleted": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_couchdb() -> MagicMock:
    """Create a mock CouchDB client."""
    return MagicMock(spec=CouchDBClient)


@pytest_asyncio.fixture
async def client_with_mock_db(
    mock_couchdb: MagicMock,
    user_doc: dict[str, Any],
) -> AsyncGenerator[tuple[AsyncClient, MagicMock], None]:
    """Create test HTTP client with mocked CouchDB."""

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == user_doc["_id"]:
            return user_doc
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get = AsyncMock(side_effect=mock_get)
    mock_couchdb.find = AsyncMock(return_value=[])
    mock_couchdb.put = AsyncMock(return_value={"ok": True, "rev": "2-new"})

    with patch("app.routers.sync_couchdb.get_couchdb", return_value=mock_couchdb):
        with patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                yield ac, mock_couchdb


# =============================================================================
# PULL ENDPOINT TESTS
# =============================================================================


class TestPullEndpoint:
    """Tests for GET /api/v2/sync/pull/{collection}."""

    # -------------------------------------------------------------------------
    # Test 1: Pull wishlists returns only user-accessible documents
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_wishlists_returns_user_accessible(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """Only wishlists where user is in access array are returned."""
        client, mock_db = client_with_mock_db

        # Another user's wishlist (not accessible)
        other_wishlist = {
            "_id": f"wishlist:{uuid4()}",
            "type": "wishlist",
            "owner_id": f"user:{uuid4()}",
            "name": "Other Wishlist",
            "access": [f"user:{uuid4()}"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock find to return only user's wishlist
        mock_db.find = AsyncMock(return_value=[wishlist_doc])

        response = await client.get(
            "/api/v2/sync/pull/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) == 1
        assert data["documents"][0]["_id"] == wishlist_doc["_id"]

        # Verify the selector used in find
        mock_db.find.assert_called_once()
        call_args = mock_db.find.call_args
        selector = call_args.kwargs.get("selector") or call_args[0][0]
        assert selector["type"] == "wishlist"
        assert selector["access"]["$elemMatch"]["$eq"] == user_id

    # -------------------------------------------------------------------------
    # Test 2: Pull items returns only user-accessible items
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_items_returns_user_accessible(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        item_doc: dict[str, Any],
    ):
        """Only items where user is in access array are returned."""
        client, mock_db = client_with_mock_db
        mock_db.find = AsyncMock(return_value=[item_doc])

        response = await client.get(
            "/api/v2/sync/pull/items",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["_id"] == item_doc["_id"]

        # Verify selector
        call_args = mock_db.find.call_args
        selector = call_args.kwargs.get("selector") or call_args[0][0]
        assert selector["type"] == "item"

    # -------------------------------------------------------------------------
    # Test 3: Pull marks excludes owner's marks (surprise mode)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_marks_excludes_owner_marks(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        another_user_id: str,
        mark_doc: dict[str, Any],
    ):
        """Marks where user is the wishlist owner should not be returned."""
        client, mock_db = client_with_mock_db

        # Mark on user's own wishlist (should be excluded)
        own_mark = {
            "_id": f"mark:{uuid4()}",
            "type": "mark",
            "owner_id": user_id,  # User is owner
            "marked_by": another_user_id,
            "access": [another_user_id],  # User not in access anyway
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mark on another user's wishlist (visible to current user)
        visible_mark = {
            "_id": f"mark:{uuid4()}",
            "type": "mark",
            "owner_id": another_user_id,  # Not the current user
            "marked_by": user_id,
            "access": [user_id],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_db.find = AsyncMock(return_value=[visible_mark])

        response = await client.get(
            "/api/v2/sync/pull/marks",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Only the visible mark should be returned
        assert len(data["documents"]) == 1
        assert data["documents"][0]["owner_id"] != user_id

        # Verify the selector includes owner_id != user_id
        call_args = mock_db.find.call_args
        selector = call_args.kwargs.get("selector") or call_args[0][0]
        assert selector["owner_id"] == {"$ne": user_id}

    # -------------------------------------------------------------------------
    # Test 4: Pull bookmarks returns only user-owned bookmarks
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_bookmarks_returns_user_owned(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        bookmark_doc: dict[str, Any],
    ):
        """Only bookmarks where user is in access array are returned."""
        client, mock_db = client_with_mock_db
        mock_db.find = AsyncMock(return_value=[bookmark_doc])

        response = await client.get(
            "/api/v2/sync/pull/bookmarks",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["owner_id"] == user_id

    # -------------------------------------------------------------------------
    # Test 5: Pull without authentication returns 401
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_unauthenticated(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
    ):
        """Unauthenticated requests should return 401."""
        client, _ = client_with_mock_db

        response = await client.get("/api/v2/sync/pull/wishlists")

        assert response.status_code == 401  # HTTPBearer returns 401 when no token

    # -------------------------------------------------------------------------
    # Test 6: Pull invalid collection returns 422
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_invalid_collection(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
    ):
        """Invalid collection name should return 422."""
        client, _ = client_with_mock_db

        response = await client.get(
            "/api/v2/sync/pull/invalid_collection",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Test 7: Pull empty collection returns empty array
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_empty_collection(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
    ):
        """Empty collection should return empty documents array."""
        client, mock_db = client_with_mock_db
        mock_db.find = AsyncMock(return_value=[])

        response = await client.get(
            "/api/v2/sync/pull/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []

    # -------------------------------------------------------------------------
    # Test 8: Pull excludes deleted documents
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_pull_excludes_deleted(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        wishlist_doc: dict[str, Any],
        deleted_wishlist_doc: dict[str, Any],
    ):
        """Deleted documents should be filtered out from results."""
        client, mock_db = client_with_mock_db

        # Return both active and deleted wishlists
        mock_db.find = AsyncMock(return_value=[wishlist_doc, deleted_wishlist_doc])

        response = await client.get(
            "/api/v2/sync/pull/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Only non-deleted should be returned
        assert len(data["documents"]) == 1
        assert data["documents"][0]["_id"] == wishlist_doc["_id"]
        assert "_deleted" not in data["documents"][0] or not data["documents"][0].get(
            "_deleted"
        )


# =============================================================================
# PUSH ENDPOINT TESTS
# =============================================================================


class TestPushEndpoint:
    """Tests for POST /api/v2/sync/push/{collection}."""

    # -------------------------------------------------------------------------
    # Test 9: Push wishlists creates new document
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_wishlists_create_new(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """New wishlist should be created successfully."""
        client, mock_db = client_with_mock_db

        new_wishlist_id = f"wishlist:{uuid4()}"
        new_wishlist = {
            "_id": new_wishlist_id,
            "type": "wishlist",
            "owner_id": user_id,
            "name": "New Wishlist",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Document doesn't exist
        async def mock_get(doc_id: str) -> dict[str, Any]:
            from app.couchdb import DocumentNotFoundError

            if doc_id == user_id:
                return {
                    "_id": user_id,
                    "type": "user",
                    "email": "test@example.com",
                }
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [new_wishlist]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conflicts"] == []
        mock_db.put.assert_called()

    # -------------------------------------------------------------------------
    # Test 10: Push wishlists updates existing document
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_wishlists_update_existing(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """Existing wishlist should be updated when client has newer version."""
        client, mock_db = client_with_mock_db

        # Server has older version
        old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        wishlist_doc["updated_at"] = old_time

        # Client has newer version
        updated_wishlist = {
            **wishlist_doc,
            "name": "Updated Name",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_doc["_id"]:
                return wishlist_doc
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [updated_wishlist]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conflicts"] == []

    # -------------------------------------------------------------------------
    # Test 11: Push wishlists by non-owner returns conflict
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_wishlists_not_owner(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        another_user_id: str,
    ):
        """Non-owner should not be able to push wishlist updates."""
        client, mock_db = client_with_mock_db

        # Wishlist owned by another user
        other_wishlist = {
            "_id": f"wishlist:{uuid4()}",
            "type": "wishlist",
            "owner_id": another_user_id,  # Different owner
            "name": "Not My Wishlist",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [other_wishlist]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "not the wishlist owner" in data["conflicts"][0]["error"].lower()

    # -------------------------------------------------------------------------
    # Test 12: Push items creates new item
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_items_create_new(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """New item should be created when user has wishlist access."""
        client, mock_db = client_with_mock_db

        new_item = {
            "_id": f"item:{uuid4()}",
            "type": "item",
            "wishlist_id": wishlist_doc["_id"],
            "owner_id": user_id,
            "title": "New Item",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_doc["_id"]:
                return wishlist_doc
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/items",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [new_item]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conflicts"] == []

    # -------------------------------------------------------------------------
    # Test 13: Push items without wishlist access returns conflict
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_items_no_wishlist_access(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        another_user_id: str,
    ):
        """Item push should fail when user has no access to wishlist."""
        client, mock_db = client_with_mock_db

        # Wishlist user doesn't have access to
        inaccessible_wishlist = {
            "_id": f"wishlist:{uuid4()}",
            "type": "wishlist",
            "owner_id": another_user_id,
            "access": [another_user_id],  # User not in access
        }

        new_item = {
            "_id": f"item:{uuid4()}",
            "type": "item",
            "wishlist_id": inaccessible_wishlist["_id"],
            "title": "New Item",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == inaccessible_wishlist["_id"]:
                return inaccessible_wishlist
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/items",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [new_item]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "no access to wishlist" in data["conflicts"][0]["error"].lower()

    # -------------------------------------------------------------------------
    # Test 14: Push marks creates new mark
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_marks_create_new(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        item_id: str,
        wishlist_id: str,
        another_user_id: str,
    ):
        """New mark should be created when user is the marker."""
        client, mock_db = client_with_mock_db

        new_mark = {
            "_id": f"mark:{uuid4()}",
            "type": "mark",
            "item_id": item_id,
            "wishlist_id": wishlist_id,
            "owner_id": another_user_id,  # Wishlist owner
            "marked_by": user_id,  # Current user is marking
            "quantity": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Wishlist for access inheritance
        wishlist = {
            "_id": wishlist_id,
            "type": "wishlist",
            "owner_id": another_user_id,
            "access": [another_user_id, user_id],
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_id:
                return wishlist
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/marks",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [new_mark]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conflicts"] == []

    # -------------------------------------------------------------------------
    # Test 15: Push marks by non-marker returns conflict
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_marks_not_marker(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        another_user_id: str,
    ):
        """Mark push should fail when user is not the one who marked."""
        client, mock_db = client_with_mock_db

        mark_by_other = {
            "_id": f"mark:{uuid4()}",
            "type": "mark",
            "marked_by": another_user_id,  # Different user marked it
            "quantity": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            "/api/v2/sync/push/marks",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [mark_by_other]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "not the mark owner" in data["conflicts"][0]["error"].lower()

    # -------------------------------------------------------------------------
    # Test 16: Push bookmarks creates new bookmark
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_bookmarks_create_new(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_id: str,
    ):
        """New bookmark should be created successfully."""
        client, mock_db = client_with_mock_db

        new_bookmark = {
            "_id": f"bookmark:{uuid4()}",
            "type": "bookmark",
            "wishlist_id": wishlist_id,
            "owner_id": user_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/bookmarks",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [new_bookmark]},
        )

        assert response.status_code == 200
        data = response.json()
        # Note: bookmarks don't have special authorization in current code
        # They use access array check implicitly

    # -------------------------------------------------------------------------
    # Test 17: Push bookmarks by non-owner - no explicit check in code
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_bookmarks_not_owner(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        another_user_id: str,
    ):
        """Bookmark push by non-owner - current code doesn't check owner."""
        client, mock_db = client_with_mock_db

        # Note: The current sync_couchdb.py doesn't have explicit owner check for bookmarks
        # This test documents current behavior
        other_bookmark = {
            "_id": f"bookmark:{uuid4()}",
            "type": "bookmark",
            "owner_id": another_user_id,  # Different owner
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/bookmarks",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [other_bookmark]},
        )

        # Current implementation doesn't check bookmark ownership
        # Document the actual behavior - this may be intentional or a gap
        assert response.status_code == 200
        # Note: If owner check is added in future, this test should verify conflict

    # -------------------------------------------------------------------------
    # Test 18: Push with newer client timestamp wins (LWW)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_lww_client_wins(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """Client with newer updated_at should win over server."""
        client, mock_db = client_with_mock_db

        # Server has old timestamp
        server_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        wishlist_doc["updated_at"] = server_time

        # Client has newer timestamp
        client_time = datetime.now(timezone.utc).isoformat()
        updated_doc = {
            **wishlist_doc,
            "name": "Client Updated",
            "updated_at": client_time,
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_doc["_id"]:
                return wishlist_doc
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [updated_doc]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conflicts"] == []
        # Document should be put with server's _rev
        mock_db.put.assert_called()

    # -------------------------------------------------------------------------
    # Test 19: Push with older client timestamp loses (LWW - server wins)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_lww_server_wins(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """Server with newer updated_at should win - conflict returned."""
        client, mock_db = client_with_mock_db

        # Server has newer timestamp
        server_time = datetime.now(timezone.utc).isoformat()
        wishlist_doc["updated_at"] = server_time

        # Client has old timestamp
        client_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        outdated_doc = {
            **wishlist_doc,
            "name": "Old Client Version",
            "updated_at": client_time,
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_doc["_id"]:
                return wishlist_doc
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [outdated_doc]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "newer version" in data["conflicts"][0]["error"].lower()
        assert data["conflicts"][0]["server_document"] is not None

    # -------------------------------------------------------------------------
    # Test 20: Delete operations win over LWW
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_delete_wins_over_lww(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """Delete should succeed even if client has older timestamp."""
        client, mock_db = client_with_mock_db

        # Server has newer timestamp
        server_time = datetime.now(timezone.utc).isoformat()
        wishlist_doc["updated_at"] = server_time

        # Client is deleting with old timestamp (should still work)
        client_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        delete_doc = {
            **wishlist_doc,
            "_deleted": True,
            "updated_at": client_time,
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_doc["_id"]:
                return wishlist_doc
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [delete_doc]},
        )

        assert response.status_code == 200
        data = response.json()
        # Delete should succeed even with older timestamp
        assert data["conflicts"] == []

    # -------------------------------------------------------------------------
    # Test 21: Push without authentication returns 401
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_unauthenticated(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
    ):
        """Unauthenticated push should return 401/403."""
        client, _ = client_with_mock_db

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            json={"documents": []},
        )

        assert response.status_code == 401  # HTTPBearer returns 401 when no token

    # -------------------------------------------------------------------------
    # Test 22: Push with type mismatch returns conflict
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_type_mismatch(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """Document with wrong type should return conflict."""
        client, mock_db = client_with_mock_db

        # Pushing an item to wishlists endpoint
        wrong_type_doc = {
            "_id": f"item:{uuid4()}",
            "type": "item",  # Wrong type for /wishlists endpoint
            "title": "Wrong Type",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [wrong_type_doc]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "type mismatch" in data["conflicts"][0]["error"].lower()

    # -------------------------------------------------------------------------
    # Test 23: Concurrent modification handled gracefully
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_push_concurrent_modification(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
        wishlist_doc: dict[str, Any],
    ):
        """Concurrent modification (CouchDB conflict) should be handled."""
        client, mock_db = client_with_mock_db

        # Server has older version initially
        old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        wishlist_doc["updated_at"] = old_time

        # Updated document
        updated_doc = {
            **wishlist_doc,
            "name": "Updated",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Track call count for get
        get_call_count = 0

        async def mock_get(doc_id: str) -> dict[str, Any]:
            nonlocal get_call_count
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            if doc_id == wishlist_doc["_id"]:
                get_call_count += 1
                if get_call_count == 1:
                    return wishlist_doc
                # On retry after conflict, return updated doc
                return {**wishlist_doc, "name": "Someone else updated"}
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        # Simulate CouchDB conflict on put
        mock_db.put = AsyncMock(side_effect=ConflictError(wishlist_doc["_id"]))

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [updated_doc]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "concurrent" in data["conflicts"][0]["error"].lower()


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for sync endpoints."""

    @pytest.mark.asyncio
    async def test_push_document_missing_id(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
    ):
        """Document without _id should return conflict."""
        client, _ = client_with_mock_db

        doc_without_id = {
            "type": "wishlist",
            "name": "No ID",
        }

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [doc_without_id]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "missing _id" in data["conflicts"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_push_item_missing_wishlist_id(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """Item without wishlist_id should return conflict."""
        client, _ = client_with_mock_db

        item_without_wishlist = {
            "_id": f"item:{uuid4()}",
            "type": "item",
            "title": "No Wishlist",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            "/api/v2/sync/push/items",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [item_without_wishlist]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "wishlist_id" in data["conflicts"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_push_item_wishlist_not_found(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """Item referencing non-existent wishlist should return conflict."""
        client, mock_db = client_with_mock_db

        nonexistent_wishlist_id = f"wishlist:{uuid4()}"
        item = {
            "_id": f"item:{uuid4()}",
            "type": "item",
            "wishlist_id": nonexistent_wishlist_id,
            "title": "Orphan Item",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/items",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [item]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicts"]) == 1
        assert "not found" in data["conflicts"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_push_multiple_documents(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """Multiple documents should be processed individually."""
        client, mock_db = client_with_mock_db

        # One valid, one invalid
        valid_wishlist = {
            "_id": f"wishlist:{uuid4()}",
            "type": "wishlist",
            "owner_id": user_id,
            "name": "Valid",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        invalid_wishlist = {
            "_id": f"wishlist:{uuid4()}",
            "type": "wishlist",
            "owner_id": f"user:{uuid4()}",  # Wrong owner
            "name": "Invalid",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [valid_wishlist, invalid_wishlist]},
        )

        assert response.status_code == 200
        data = response.json()
        # Only one conflict (the invalid one)
        assert len(data["conflicts"]) == 1
        assert data["conflicts"][0]["document_id"] == invalid_wishlist["_id"]

    @pytest.mark.asyncio
    async def test_push_deleted_doc_not_on_server(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """Pushing deleted document that doesn't exist on server should be skipped."""
        client, mock_db = client_with_mock_db

        deleted_doc = {
            "_id": f"wishlist:{uuid4()}",
            "type": "wishlist",
            "owner_id": user_id,
            "_deleted": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async def mock_get(doc_id: str) -> dict[str, Any]:
            if doc_id == user_id:
                return {"_id": user_id, "type": "user"}
            raise DocumentNotFoundError(doc_id)

        mock_db.get = AsyncMock(side_effect=mock_get)

        response = await client.post(
            "/api/v2/sync/push/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"documents": [deleted_doc]},
        )

        assert response.status_code == 200
        data = response.json()
        # No conflicts - deleted doc that doesn't exist is skipped
        assert data["conflicts"] == []
        # put should not be called (document skipped)
        mock_db.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_pull_sorts_by_updated_at_descending(
        self,
        client_with_mock_db: tuple[AsyncClient, MagicMock],
        auth_token: str,
        user_id: str,
    ):
        """Pull results should be sorted by updated_at descending."""
        client, mock_db = client_with_mock_db

        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=7)).isoformat()
        mid_time = (now - timedelta(days=3)).isoformat()
        new_time = now.isoformat()

        wishlists = [
            {"_id": "wishlist:old", "type": "wishlist", "updated_at": old_time},
            {"_id": "wishlist:new", "type": "wishlist", "updated_at": new_time},
            {"_id": "wishlist:mid", "type": "wishlist", "updated_at": mid_time},
        ]

        mock_db.find = AsyncMock(return_value=wishlists)

        response = await client.get(
            "/api/v2/sync/pull/wishlists",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        docs = data["documents"]
        assert len(docs) == 3
        # Should be sorted newest first
        assert docs[0]["_id"] == "wishlist:new"
        assert docs[1]["_id"] == "wishlist:mid"
        assert docs[2]["_id"] == "wishlist:old"
