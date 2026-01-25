"""Tests for shared wishlist access endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def item_data() -> dict:
    """Sample item creation data."""
    return {
        "title": "Test Item",
        "description": "A test item description",
        "price": 29.99,
        "currency": "USD",
        "quantity": 3,
    }


async def register_and_login(client: AsyncClient, user_data: dict) -> tuple[str, str]:
    """Helper to register and login, returning (access_token, user_id)."""
    response = await client.post("/api/v1/auth/register", json=user_data)
    if response.status_code != 201:
        raise Exception(f"Registration failed with status {response.status_code}")
    data = response.json()
    return data["access_token"], data["user"]["id"]


async def create_wishlist(client: AsyncClient, token: str, name: str = "Test Wishlist") -> str:
    """Helper to create a wishlist, returning wishlist ID."""
    response = await client.post(
        "/api/v1/wishlists",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


async def create_item(client: AsyncClient, token: str, wishlist_id: str, item_data: dict) -> str:
    """Helper to create an item, returning item ID."""
    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json=item_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


async def create_share_link(
    client: AsyncClient, token: str, wishlist_id: str, link_type: str = "mark"
) -> str:
    """Helper to create a share link, returning the share token."""
    response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/share",
        json={"link_type": link_type},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["token"]


class TestSharedWishlistPreview:
    """Tests for unauthenticated preview of shared wishlists."""

    @pytest.mark.asyncio
    async def test_preview_shared_wishlist(
        self, client: AsyncClient, user_data: dict, item_data: dict
    ):
        """Test previewing a shared wishlist without authentication."""
        token, _ = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token, "My Birthday List")
        await create_item(client, token, wishlist_id, item_data)
        await create_item(client, token, wishlist_id, {"title": "Second Item"})
        share_token = await create_share_link(client, token, wishlist_id)

        response = await client.get(f"/api/v1/shared/{share_token}/preview")

        assert response.status_code == 200
        data = response.json()
        assert data["requires_auth"] is True
        assert f"share_token={share_token}" in data["auth_redirect"]
        assert data["wishlist"]["title"] == "My Birthday List"
        assert data["wishlist"]["item_count"] == 2
        assert "owner_name" in data["wishlist"]

    @pytest.mark.asyncio
    async def test_preview_invalid_token(self, client: AsyncClient):
        """Test preview with invalid token returns 404."""
        response = await client.get("/api/v1/shared/invalid_token_12345/preview")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_revoked_link(
        self, client: AsyncClient, user_data: dict
    ):
        """Test preview with revoked link returns 404."""
        token, _ = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        # Create and revoke share link
        create_response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )
        share_data = create_response.json()
        share_token = share_data["token"]
        share_id = share_data["id"]

        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/share/{share_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(f"/api/v1/shared/{share_token}/preview")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_deleted_wishlist(
        self, client: AsyncClient, user_data: dict
    ):
        """Test preview when wishlist is deleted returns 404."""
        token, _ = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)
        share_token = await create_share_link(client, token, wishlist_id)

        # Delete the wishlist
        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(f"/api/v1/shared/{share_token}/preview")
        assert response.status_code == 404


class TestGetSharedWishlist:
    """Tests for authenticated access to shared wishlists."""

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_mark_permission(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test accessing a shared wishlist with mark permission."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token, "Birthday Wishlist")
        await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["wishlist"]["title"] == "Birthday Wishlist"
        assert data["wishlist"]["item_count"] == 1
        assert "view" in data["permissions"]
        assert "mark" in data["permissions"]
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == item_data["title"]
        assert data["items"][0]["quantity"] == item_data["quantity"]
        assert data["items"][0]["available_quantity"] == item_data["quantity"]
        assert data["items"][0]["my_mark_quantity"] == 0

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_view_only(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test accessing a view-only shared wishlist."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "view")

        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["permissions"] == ["view"]
        assert "mark" not in data["permissions"]

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_invalid_token(
        self, client: AsyncClient, user_data: dict
    ):
        """Test accessing with invalid token returns 404."""
        token, _ = await register_and_login(client, user_data)

        response = await client.get(
            "/api/v1/shared/invalid_token_12345",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_no_auth(
        self, client: AsyncClient, user_data: dict
    ):
        """Test accessing shared wishlist without authentication returns 403."""
        owner_token, _ = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        response = await client.get(f"/api/v1/shared/{share_token}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_revoked(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test accessing a revoked share link returns 404."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        create_response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        share_data = create_response.json()
        share_token = share_data["token"]
        share_id = share_data["id"]

        # Revoke the link
        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/share/{share_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_deleted(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test accessing share link for deleted wishlist returns 404."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Delete the wishlist
        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_owner_accessing_own_share_link(
        self, client: AsyncClient, user_data: dict, item_data: dict
    ):
        """Test owner can access their own shared wishlist via share link."""
        owner_token, _ = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, owner_token)
        await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        # Owner should be able to view via share link
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_access_shared_wishlist_excludes_deleted_items(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test shared wishlist view excludes deleted items."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item1_id = await create_item(client, owner_token, wishlist_id, item_data)
        await create_item(client, owner_token, wishlist_id, {"title": "Item 2"})
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Delete the first item
        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/items/{item1_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Item 2"
        assert data["wishlist"]["item_count"] == 1

    @pytest.mark.asyncio
    async def test_access_increments_access_count(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test accessing shared wishlist increments access count."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Access the shared wishlist twice
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Check access count via share links list
        list_response = await client.get(
            f"/api/v1/wishlists/{wishlist_id}/share",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        links = list_response.json()["items"]
        assert len(links) == 1
        assert links[0]["access_count"] == 2


class TestMarkItem:
    """Tests for marking items in shared wishlists."""

    @pytest.mark.asyncio
    async def test_mark_item_success(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test successfully marking an item."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == item_id
        assert data["my_mark_quantity"] == 1
        assert data["total_marked_quantity"] == 1
        assert data["available_quantity"] == item_data["quantity"] - 1

    @pytest.mark.asyncio
    async def test_mark_item_multiple_quantity(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test marking multiple quantities of an item."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 2},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["my_mark_quantity"] == 2
        assert data["total_marked_quantity"] == 2
        assert data["available_quantity"] == item_data["quantity"] - 2

    @pytest.mark.asyncio
    async def test_mark_item_update_existing(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test updating an existing mark increases quantity."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Mark once
        await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Mark again with different quantity
        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 2},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["my_mark_quantity"] == 2
        assert data["total_marked_quantity"] == 2

    @pytest.mark.asyncio
    async def test_mark_item_exceeds_quantity(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test marking more than available quantity fails."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": item_data["quantity"] + 1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 400
        assert "available" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_mark_item_owner_cannot_mark_own(
        self, client: AsyncClient, user_data: dict, item_data: dict
    ):
        """Test owner cannot mark items on their own wishlist."""
        owner_token, _ = await register_and_login(client, user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert response.status_code == 403
        assert "own wishlist" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_mark_item_view_only_link(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test marking via view-only link fails."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "view")

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 403
        assert "does not allow marking" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_mark_item_invalid_token(
        self, client: AsyncClient, user_data: dict
    ):
        """Test marking with invalid token returns 404."""
        token, _ = await register_and_login(client, user_data)

        response = await client.post(
            "/api/v1/shared/invalid_token/items/00000000-0000-0000-0000-000000000000/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_item_not_found(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test marking nonexistent item returns 404."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/00000000-0000-0000-0000-000000000000/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_item_deleted_item(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test marking deleted item returns 404."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Delete the item
        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/items/{item_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_item_invalid_quantity(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test marking with zero or negative quantity fails validation."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Zero quantity
        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 0},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 422

        # Negative quantity
        response = await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": -1},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 422


class TestUnmarkItem:
    """Tests for unmarking items in shared wishlists."""

    @pytest.mark.asyncio
    async def test_unmark_item_success(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test successfully unmarking an item."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Mark first
        await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 2},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Unmark
        response = await client.delete(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == item_id
        assert data["my_mark_quantity"] == 0
        assert data["total_marked_quantity"] == 0
        assert data["available_quantity"] == item_data["quantity"]

    @pytest.mark.asyncio
    async def test_unmark_item_not_marked(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test unmarking an item that wasn't marked returns gracefully."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.delete(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["my_mark_quantity"] == 0
        assert data["total_marked_quantity"] == 0

    @pytest.mark.asyncio
    async def test_unmark_item_owner_cannot_unmark_own(
        self, client: AsyncClient, user_data: dict, item_data: dict
    ):
        """Test owner cannot unmark items on their own wishlist."""
        owner_token, _ = await register_and_login(client, user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        response = await client.delete(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unmark_item_view_only_link(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test unmarking via view-only link fails."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "view")

        response = await client.delete(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unmark_preserves_other_marks(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test unmarking by one user preserves marks by another user."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer1_token, _ = await register_and_login(client, another_user_data)

        # Create a third user
        third_user_data = {
            "email": "third@example.com",
            "password": "thirdPassword789",
            "name": "Third User",
            "locale": "en",
        }
        viewer2_token, _ = await register_and_login(client, third_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Viewer 1 marks
        await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer1_token}"},
        )

        # Viewer 2 marks
        await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 1},
            headers={"Authorization": f"Bearer {viewer2_token}"},
        )

        # Viewer 1 unmarks
        response = await client.delete(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            headers={"Authorization": f"Bearer {viewer1_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["my_mark_quantity"] == 0
        assert data["total_marked_quantity"] == 1  # Viewer 2's mark remains
        assert data["available_quantity"] == item_data["quantity"] - 1


class TestSharedWishlistItemView:
    """Tests for item information in shared wishlist responses."""

    @pytest.mark.asyncio
    async def test_shared_wishlist_shows_mark_quantities(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test shared wishlist shows correct mark quantities."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        item_id = await create_item(client, owner_token, wishlist_id, item_data)
        share_token = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Mark the item
        await client.post(
            f"/api/v1/shared/{share_token}/items/{item_id}/mark",
            json={"quantity": 2},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Get the shared wishlist
        response = await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        item = data["items"][0]
        assert item["quantity"] == item_data["quantity"]
        assert item["marked_quantity"] == 2
        assert item["available_quantity"] == item_data["quantity"] - 2
        assert item["my_mark_quantity"] == 2
