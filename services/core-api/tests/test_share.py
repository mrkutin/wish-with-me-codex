"""Tests for share link management endpoints (/api/v1/wishlists/{id}/share)."""

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
    mock.create_share = AsyncMock()
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
        "locale": "en",
        "access": [user_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def other_user() -> dict[str, Any]:
    """Create another user document (not the owner)."""
    user_id = f"user:{uuid4()}"
    return {
        "_id": user_id,
        "type": "user",
        "email": "other@example.com",
        "name": "Other User",
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
        "_rev": "1-abc123",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "valid_share_token_abc123",
        "link_type": "mark",
        "expires_at": None,
        "access_count": 5,
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
        "_rev": "1-def456",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "view_only_token_xyz789",
        "link_type": "view",
        "expires_at": None,
        "access_count": 2,
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
        "_rev": "1-ghi789",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "expired_token",
        "link_type": "mark",
        "expires_at": expired_at,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        "access": [owner_user["_id"]],
    }


@pytest.fixture
def revoked_share_link(owner_user: dict[str, Any], wishlist: dict[str, Any]) -> dict[str, Any]:
    """Create a revoked share link document."""
    share_id = f"share:{uuid4()}"
    return {
        "_id": share_id,
        "_rev": "2-jkl012",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "revoked_token",
        "link_type": "mark",
        "expires_at": None,
        "access_count": 3,
        "revoked": True,
        "granted_users": ["user:someone"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "access": [owner_user["_id"]],
    }


def create_auth_header(user: dict[str, Any]) -> dict[str, str]:
    """Create an Authorization header with a valid JWT token."""
    token = create_access_token(user["_id"])
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Tests: Create Share Link
# =============================================================================


@pytest.mark.asyncio
async def test_create_share_success(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
) -> None:
    """Test creating a share link successfully generates token and share URL."""
    wishlist_uuid = wishlist["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == owner_user["_id"]:
            return owner_user
        if doc_id == wishlist["_id"]:
            return wishlist
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    created_share = {
        "_id": f"share:{uuid4()}",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "generated_token_123",
        "link_type": "mark",
        "expires_at": None,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mock_couchdb.create_share.return_value = created_share

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/wishlists/{wishlist_uuid}/share",
                headers=create_auth_header(owner_user),
                json={"link_type": "mark"},
            )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "token" in data
    assert "share_url" in data
    assert data["link_type"] == "mark"
    assert data["access_count"] == 0


@pytest.mark.asyncio
async def test_create_share_not_owner(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    other_user: dict[str, Any],
    wishlist: dict[str, Any],
) -> None:
    """Test creating a share link as non-owner returns 403."""
    wishlist_uuid = wishlist["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == other_user["_id"]:
            return other_user
        if doc_id == wishlist["_id"]:
            return wishlist
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/wishlists/{wishlist_uuid}/share",
                headers=create_auth_header(other_user),
                json={"link_type": "mark"},
            )

    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_share_with_expiry(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
) -> None:
    """Test creating a share link with expiration date."""
    wishlist_uuid = wishlist["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == owner_user["_id"]:
            return owner_user
        if doc_id == wishlist["_id"]:
            return wishlist
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    created_share = {
        "_id": f"share:{uuid4()}",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "expiring_token_456",
        "link_type": "mark",
        "expires_at": expires_at,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mock_couchdb.create_share.return_value = created_share

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/wishlists/{wishlist_uuid}/share",
                headers=create_auth_header(owner_user),
                json={"link_type": "mark", "expires_in_days": 7},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["expires_at"] is not None
    # Verify create_share was called with expires_at
    mock_couchdb.create_share.assert_called_once()


@pytest.mark.asyncio
async def test_create_share_type_view(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
) -> None:
    """Test creating a view-only share link."""
    wishlist_uuid = wishlist["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == owner_user["_id"]:
            return owner_user
        if doc_id == wishlist["_id"]:
            return wishlist
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    created_share = {
        "_id": f"share:{uuid4()}",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "view_token_789",
        "link_type": "view",
        "expires_at": None,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mock_couchdb.create_share.return_value = created_share

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/wishlists/{wishlist_uuid}/share",
                headers=create_auth_header(owner_user),
                json={"link_type": "view"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["link_type"] == "view"


@pytest.mark.asyncio
async def test_create_share_type_mark(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
) -> None:
    """Test creating a mark share link (default type)."""
    wishlist_uuid = wishlist["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == owner_user["_id"]:
            return owner_user
        if doc_id == wishlist["_id"]:
            return wishlist
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    created_share = {
        "_id": f"share:{uuid4()}",
        "type": "share",
        "wishlist_id": wishlist["_id"],
        "owner_id": owner_user["_id"],
        "token": "mark_token_abc",
        "link_type": "mark",
        "expires_at": None,
        "access_count": 0,
        "revoked": False,
        "granted_users": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mock_couchdb.create_share.return_value = created_share

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/wishlists/{wishlist_uuid}/share",
                headers=create_auth_header(owner_user),
                json={"link_type": "mark"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["link_type"] == "mark"


# =============================================================================
# Tests: Revoke Share Link
# =============================================================================


@pytest.mark.asyncio
async def test_revoke_share_success(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
) -> None:
    """Test revoking a share link performs soft delete."""
    wishlist_uuid = wishlist["_id"].split(":")[1]
    share_uuid = share_link_mark["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == owner_user["_id"]:
            return owner_user
        if doc_id == share_link_mark["_id"]:
            return share_link_mark.copy()
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get
    mock_couchdb.put.return_value = {"ok": True}

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/wishlists/{wishlist_uuid}/share/{share_uuid}",
                headers=create_auth_header(owner_user),
            )

    assert response.status_code == 204
    # Verify put was called with revoked=True
    mock_couchdb.put.assert_called_once()
    updated_doc = mock_couchdb.put.call_args[0][0]
    assert updated_doc["revoked"] is True
    assert "updated_at" in updated_doc


@pytest.mark.asyncio
async def test_revoke_share_not_owner(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    other_user: dict[str, Any],
    wishlist: dict[str, Any],
    share_link_mark: dict[str, Any],
) -> None:
    """Test revoking a share link as non-owner returns 403."""
    wishlist_uuid = wishlist["_id"].split(":")[1]
    share_uuid = share_link_mark["_id"].split(":")[1]

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == other_user["_id"]:
            return other_user
        if doc_id == share_link_mark["_id"]:
            return share_link_mark
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/wishlists/{wishlist_uuid}/share/{share_uuid}",
                headers=create_auth_header(other_user),
            )

    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_revoke_share_not_found(
    mock_couchdb: MagicMock,
    owner_user: dict[str, Any],
    wishlist: dict[str, Any],
) -> None:
    """Test revoking a non-existent share link returns 404."""
    wishlist_uuid = wishlist["_id"].split(":")[1]
    nonexistent_share_uuid = str(uuid4())

    async def mock_get(doc_id: str) -> dict[str, Any]:
        if doc_id == owner_user["_id"]:
            return owner_user
        raise DocumentNotFoundError(doc_id)

    mock_couchdb.get.side_effect = mock_get

    with patch("app.routers.share.get_couchdb", return_value=mock_couchdb), \
         patch("app.dependencies.get_couchdb", return_value=mock_couchdb):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                f"/api/v1/wishlists/{wishlist_uuid}/share/{nonexistent_share_uuid}",
                headers=create_auth_header(owner_user),
            )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
