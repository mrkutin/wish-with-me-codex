"""Tests for shared wishlist access endpoints (/api/v1/shared).

Note: Most shared wishlist operations are now handled via PouchDB sync.
This test file covers only the grant-access endpoint.
"""

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


def create_auth_header(user: dict[str, Any]) -> dict[str, str]:
    """Create an Authorization header with a valid JWT token."""
    token = create_access_token(user["_id"])
    return {"Authorization": f"Bearer {token}"}


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


@pytest.mark.asyncio
async def test_grant_access_view_only_permissions(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    viewer_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_view: dict[str, Any],
) -> None:
    """Test granting access with view-only link returns only view permission."""
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
        [share_link_view],  # find share by token
        [],  # find existing bookmarks
    ]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{share_link_view['token']}/grant-access",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["permissions"] == ["view"]
    assert "mark" not in data["permissions"]


@pytest.mark.asyncio
async def test_grant_access_invalid_token(
    mock_couchdb: MagicMock,
    viewer_user: dict[str, Any],
) -> None:
    """Test granting access with invalid token returns 404."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.return_value = []  # No share found

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/shared/invalid_nonexistent_token/grant-access",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_grant_access_expired_token(
    mock_couchdb: MagicMock,
    viewer_user: dict[str, Any],
    expired_share_link: dict[str, Any],
) -> None:
    """Test granting access with expired token returns 404."""
    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == viewer_user["_id"]:
            return viewer_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.find.return_value = [expired_share_link]

    with patch("app.routers.shared.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/shared/{expired_share_link['token']}/grant-access",
                headers=create_auth_header(viewer_user),
            )

    assert response.status_code == 404
    assert "expired" in response.json()["detail"].lower()
