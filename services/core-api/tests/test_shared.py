"""Tests for shared wishlist access endpoints (/api/v1/shared)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.couchdb import CouchDBClient, DocumentNotFoundError
from app.main import app
from app.security import create_access_token


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_couchdb() -> MagicMock:
    """Create a mock CouchDB client."""
    mock = MagicMock(spec=CouchDBClient)
    mock.get = AsyncMock()
    mock.put = AsyncMock()
    mock.find = AsyncMock(return_value=[])
    mock.create_mark = AsyncMock()
    mock.update_access_arrays = AsyncMock()
    mock.generate_id = MagicMock(side_effect=lambda t: f"{t}:{uuid4()}")
    return mock


@pytest.fixture
def owner_user() -> dict[str, Any]:
    """Create an owner user document."""
    user_id = f"user:{uuid4()}"
    return {
        "_id": user_id,
        "type": "user",
        "email": "owner@example.com",
        "name": "Owner User",
        "avatar_base64": "data:image/png;base64,abc123",
        "locale": "en",
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def viewer_user() -> dict[str, Any]:
    """Create a viewer user document."""
    user_id = f"user:{uuid4()}"
    return {
        "_id": user_id,
        "type": "user",
        "email": "viewer@example.com",
        "name": "Viewer User",
        "locale": "en",
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def wishlist(owner_user: dict[str, Any]) -> dict[str, Any]:
    """Create a wishlist document."""
    wishlist_id = f"wishlist:{uuid4()}"
    return {
        "_id": wishlist_id,
        "_rev": "1-abc123",
        "type": "wishlist",
        "owner_id": owner_user["_id"],
        "name": "Birthday Wishlist",
        "description": "My birthday wishes",
        "icon": "gift",
        "access": [owner_user["_id"]],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def item(owner_user: dict[str, Any], wishlist: dict[str, Any]) -> dict[str, Any]:
    """Create an item document."""
    item_id = f"item:{uuid4()}"
    return {
        "_id": item_id,
        "_rev": "1-def456",
        "type": "item",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "title": "Nice Gift",
        "description": "A really nice gift",
        "price": 99.99,
        "currency": "USD",
        "quantity": 2,
        "source_url": "https://example.com/product",
        "image_base64": "data:image/png;base64,xyz789",
        "status": "resolved",
        "access": [owner_user["_id"]],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def share_link_mark(owner_user: dict[str, Any], wishlist: dict[str, Any]) -> dict[str, Any]:
    """Create a share link document with mark permissions."""
    share_id = f"share:{uuid4()}"
    return {
        "_id": share_id,
        "_rev": "1-ghi789",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "valid_mark_token_abc123",
        "link_type": "mark",
        "expires_at": None,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "access": [owner_user["_id"]],
    }


@pytest.fixture
def share_link_view(owner_user: dict[str, Any], wishlist: dict[str, Any]) -> dict[str, Any]:
    """Create a share link document with view-only permissions."""
    share_id = f"share:{uuid4()}"
    return {
        "_id": share_id,
        "_rev": "1-jkl012",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "valid_view_token_xyz789",
        "link_type": "view",
        "expires_at": None,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "access": [owner_user["_id"]],
    }


@pytest.fixture
def expired_share_link(owner_user: dict[str, Any], wishlist: dict[str, Any]) -> dict[str, Any]:
    """Create an expired share link document."""
    share_id = f"share:{uuid4()}"
    expired_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    return {
        "_id": share_id,
        "_rev": "1-mno345",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "expired_token_old123",
        "link_type": "mark",
        "expires_at": expired_at,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        "access": [owner_user["_id"]],
    }


@pytest.fixture
def bookmark(
    viewer_user: dict[str, Any],
    share_link_mark: dict[str, Any],
    wishlist: dict[str, Any],
) -> dict[str, Any]:
    """Create a bookmark document."""
    bookmark_id = f"bookmark:{uuid4()}"
    return {
        "_id": bookmark_id,
        "_rev": "1-pqr678",
        "type": "bookmark",
        "user_id": viewer_user["_id"],
        "share_id": share_link_mark["_id"],
        "wishlist_id": wishlist["_id"],
        "owner_name": "Owner User",
        "owner_avatar_base64": "data:image/png;base64,abc123",
        "wishlist_name": "Birthday Wishlist",
        "wishlist_icon": "gift",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_accessed_at": datetime.now(timezone.utc).isoformat(),
        "access": [viewer_user["_id"]],
    }


@pytest.fixture
def mark(
    viewer_user: dict[str, Any],
    owner_user: dict[str, Any],
    item: dict[str, Any],
    wishlist: dict[str, Any],
) -> dict[str, Any]:
    """Create a mark document."""
    mark_id = f"mark:{uuid4()}"
    return {
        "_id": mark_id,
        "_rev": "1-stu901",
        "type": "mark",
        "item_id": item["_id"],
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "marked_by": viewer_user["_id"],
        "quantity": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "access": [viewer_user["_id"]],  # Owner excluded (surprise mode)
    }


def create_auth_header(user: dict[str, Any]) -> dict[str, str]:
    """Create an Authorization header with a valid JWT token."""
    token = create_access_token(user["_id"])
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Tests: Preview Shared Wishlist (No Auth Required)
# =============================================================================


@pytest.mark.asyncio
async def test_preview_valid_token(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test previewing a shared wishlist with valid token returns preview."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [item],  # find items
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/shared/{share_link_mark['token']}/preview",
            )

    assert response.status_code == 200
    data = response.json()
    assert "wishlist" in data
    assert data["wishlist"]["title"] == "Birthday Wishlist"
    assert data["wishlist"]["owner_name"] == "Owner"  # First name only
    assert data["wishlist"]["item_count"] == 1
    assert data["requires_auth"] is True
    assert "auth_redirect" in data


@pytest.mark.asyncio
async def test_preview_invalid_token(
    mock_couchdb: MagicMock,
) -> None:
    """Test previewing with invalid token returns 404."""
    mock_couchdb.find.return_value = []  # No share found

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/shared/invalid_nonexistent_token/preview",
            )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_expired_token(
    mock_couchdb: MagicMock,
    expired_share_link: dict[str, Any],
) -> None:
    """Test previewing with expired token returns 404."""
    mock_couchdb.find.return_value = [expired_share_link]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/shared/{expired_share_link['token']}/preview",
            )

    assert response.status_code == 404
    assert "expired" in response.json()["detail"].lower()


# =============================================================================
# Tests: Grant Access
# =============================================================================


@pytest.mark.asyncio
async def test_grant_access_success(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
) -> None:
    """Test granting access adds user to access arrays."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [],  # find existing bookmarks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_mark['token']}/grant-access",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["wishlist_id"] == wishlist["_id"]
    assert "view" in data["permissions"]
    assert "mark" in data["permissions"]
    # Verify update_access_arrays was called
    mock_couchdb.update_access_arrays.assert_called_once()


@pytest.mark.asyncio
async def test_grant_access_already_has(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    bookmark: dict[str, Any],
) -> None:
    """Test granting access when user already has access updates bookmark."""
    # User already in granted_users
    share_with_user = share_link_mark.copy()
    share_with_user["granted_users"] = [viewer_user["_id"]]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_with_user],  # find share by token
        [bookmark],  # find existing bookmarks (one already exists)
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_mark['token']}/grant-access",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["wishlist_id"] == wishlist["_id"]


# =============================================================================
# Tests: Get Shared Wishlist
# =============================================================================


@pytest.mark.asyncio
async def test_get_shared_wishlist(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test getting a shared wishlist returns items and permissions."""
    share_with_user = share_link_mark.copy()
    share_with_user["granted_users"] = [viewer_user["_id"]]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_with_user],  # find share by token
        [],  # find existing bookmarks
        [item],  # find items
        [],  # find marks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/shared/{share_link_mark['token']}",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert "wishlist" in data
    assert "items" in data
    assert "permissions" in data
    assert data["wishlist"]["title"] == "Birthday Wishlist"
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Nice Gift"


@pytest.mark.asyncio
async def test_get_shared_wishlist_view_permissions(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_view: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test view-only share link returns only view permission."""
    share_with_user = share_link_view.copy()
    share_with_user["granted_users"] = [viewer_user["_id"]]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_with_user],  # find share by token
        [],  # find existing bookmarks
        [item],  # find items
        [],  # find marks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/shared/{share_link_view['token']}",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["permissions"] == ["view"]
    assert "mark" not in data["permissions"]


@pytest.mark.asyncio
async def test_get_shared_wishlist_mark_permissions(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test mark share link returns view and mark permissions."""
    share_with_user = share_link_mark.copy()
    share_with_user["granted_users"] = [viewer_user["_id"]]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_with_user],  # find share by token
        [],  # find existing bookmarks
        [item],  # find items
        [],  # find marks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/shared/{share_link_mark['token']}",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert "view" in data["permissions"]
    assert "mark" in data["permissions"]


# =============================================================================
# Tests: Mark Item
# =============================================================================


@pytest.mark.asyncio
async def test_mark_item_success(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test marking an item creates mark and updates quantities."""
    item_uuid = item["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == item["_id"]:
            return item
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [],  # find existing marks for this item
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_mark['token']}/items/{item_uuid}/mark",
                headers=create_auth_header(viewer_user),
                json={"quantity": 1},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == item_uuid
    assert data["my_mark_quantity"] == 1
    assert data["total_marked_quantity"] == 1
    assert data["available_quantity"] == 1  # 2 total - 1 marked
    # Verify create_mark was called
    mock_couchdb.create_mark.assert_called_once()


@pytest.mark.asyncio
async def test_mark_item_view_only(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_view: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test marking an item with view-only link returns 403."""
    item_uuid = item["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.return_value = [share_link_view]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_view['token']}/items/{item_uuid}/mark",
                headers=create_auth_header(viewer_user),
                json={"quantity": 1},
            )

    assert response.status_code == 403
    assert "doesn't allow marking" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mark_item_not_found(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    share_link_mark: dict[str, Any],
) -> None:
    """Test marking a non-existent item returns 404."""
    nonexistent_item_uuid = str(uuid4())

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.return_value = [share_link_mark]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_mark['token']}/items/{nonexistent_item_uuid}/mark",
                headers=create_auth_header(viewer_user),
                json={"quantity": 1},
            )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mark_item_no_availability(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
    mark: dict[str, Any],
) -> None:
    """Test marking an item with no available quantity returns 409."""
    item_uuid = item["_id"].split(":")[1]
    # Item has quantity 2, and there's already a mark for 2
    existing_mark = mark.copy()
    existing_mark["quantity"] = 2
    existing_mark["marked_by"] = f"user:{uuid4()}"  # Different user

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == item["_id"]:
            return item
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [existing_mark],  # find existing marks (all items marked)
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_mark['token']}/items/{item_uuid}/mark",
                headers=create_auth_header(viewer_user),
                json={"quantity": 1},
            )

    assert response.status_code == 409
    assert "available" in response.json()["detail"].lower()


# =============================================================================
# Tests: Unmark Item
# =============================================================================


@pytest.mark.asyncio
async def test_unmark_item_success(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
    mark: dict[str, Any],
) -> None:
    """Test unmarking an item removes the mark."""
    item_uuid = item["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == item["_id"]:
            return item
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [mark],  # find existing marks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/shared/{share_link_mark['token']}/items/{item_uuid}/mark",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == item_uuid
    assert data["my_mark_quantity"] == 0
    assert data["total_marked_quantity"] == 0
    assert data["available_quantity"] == 2  # All available now
    # Verify put was called with _deleted=True
    mock_couchdb.put.assert_called()
    updated_mark = mock_couchdb.put.call_args[0][0]
    assert updated_mark["_deleted"] is True


@pytest.mark.asyncio
async def test_unmark_item_no_existing_mark(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test unmarking an item that user hasn't marked returns 404."""
    item_uuid = item["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == item["_id"]:
            return item
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [],  # no existing marks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/shared/{share_link_mark['token']}/items/{item_uuid}/mark",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 404
    assert "haven't marked" in response.json()["detail"].lower()


# =============================================================================
# Tests: Bookmarks
# =============================================================================


@pytest.mark.asyncio
async def test_bookmarks_list(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
    bookmark: dict[str, Any],
    item: dict[str, Any],
) -> None:
    """Test listing bookmarks returns user's bookmarked wishlists."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        if doc_id == bookmark["share_id"]:
            return share_link_mark
        if doc_id == wishlist["_id"]:
            return wishlist
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [bookmark],  # find bookmarks for user
        [item],  # find items for wishlist
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/shared/bookmarks",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["share_token"] == share_link_mark["token"]
    assert data["items"][0]["wishlist"]["title"] == "Birthday Wishlist"


@pytest.mark.asyncio
async def test_create_bookmark(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    share_link_mark: dict[str, Any],
) -> None:
    """Test creating a bookmark for a shared wishlist."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [],  # no existing bookmarks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_mark['token']}/bookmark",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Bookmark created"
    # Verify put was called to create bookmark
    mock_couchdb.put.assert_called_once()
    created_bookmark = mock_couchdb.put.call_args[0][0]
    assert created_bookmark["type"] == "bookmark"
    assert created_bookmark["user_id"] == viewer_user["_id"]


@pytest.mark.asyncio
async def test_delete_bookmark(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    share_link_mark: dict[str, Any],
    bookmark: dict[str, Any],
) -> None:
    """Test deleting a bookmark removes it (soft delete)."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [bookmark],  # find existing bookmark
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/shared/{share_link_mark['token']}/bookmark",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 204
    # Verify put was called with _deleted=True
    mock_couchdb.put.assert_called_once()
    deleted_bookmark = mock_couchdb.put.call_args[0][0]
    assert deleted_bookmark["_deleted"] is True


@pytest.mark.asyncio
async def test_delete_bookmark_not_found(
    mock_couchdb: MagicMock,
    viewer_user: dict[str, Any],
    share_link_mark: dict[str, Any],
) -> None:
    """Test deleting a non-existent bookmark returns 404."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.side_effect = [
        [share_link_mark],  # find share by token
        [],  # no existing bookmark
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/shared/{share_link_mark['token']}/bookmark",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
