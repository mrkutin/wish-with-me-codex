"""Tests for share link CRUD endpoints."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


@pytest.fixture
def wishlist_data() -> dict:
    """Sample wishlist creation data."""
    return {
        "name": "Birthday 2026",
        "description": "Gifts I'd love for my birthday",
    }


async def register_and_login(client: AsyncClient, user_data: dict) -> str:
    """Helper to register and login, returning access token."""
    response = await client.post("/api/v1/auth/register", json=user_data)
    if response.status_code != 201:
        raise Exception(f"Registration failed with status {response.status_code}")
    return response.json()["access_token"]


async def create_wishlist(client: AsyncClient, token: str, name: str = "Test Wishlist") -> str:
    """Helper to create a wishlist, returning wishlist ID."""
    response = await client.post(
        "/api/v1/wishlists",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


class TestCreateShareLink:
    """Tests for share link creation."""

    @pytest.mark.asyncio
    async def test_create_mark_type_share_link(
        self, client: AsyncClient, user_data: dict, wishlist_data: dict
    ):
        """Test creating a share link with mark permission."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["wishlist_id"] == wishlist_id
        assert data["link_type"] == "mark"
        assert data["expires_at"] is None
        assert data["access_count"] == 0
        assert "id" in data
        assert "token" in data
        assert "share_url" in data
        assert "qr_code_base64" in data
        assert data["share_url"].endswith(f"/s/{data['token']}")

    @pytest.mark.asyncio
    async def test_create_view_only_share_link(
        self, client: AsyncClient, user_data: dict, wishlist_data: dict
    ):
        """Test creating a view-only share link."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "view"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["link_type"] == "view"

    @pytest.mark.asyncio
    async def test_create_share_link_with_expiry(
        self, client: AsyncClient, user_data: dict
    ):
        """Test creating a share link with expiration."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark", "expires_in_days": 7},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None
        # Verify expiry is approximately 7 days from now
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        expected = datetime.now(timezone.utc) + timedelta(days=7)
        assert abs((expires_at - expected).total_seconds()) < 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_create_share_link_default_type(
        self, client: AsyncClient, user_data: dict
    ):
        """Test default share link type is mark."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["link_type"] == "mark"

    @pytest.mark.asyncio
    async def test_create_share_link_nonexistent_wishlist(
        self, client: AsyncClient, user_data: dict
    ):
        """Test creating share link for nonexistent wishlist returns 404."""
        token = await register_and_login(client, user_data)

        response = await client.post(
            "/api/v1/wishlists/00000000-0000-0000-0000-000000000000/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_share_link_unauthorized(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test creating share link on another user's wishlist returns 403."""
        token1 = await register_and_login(client, user_data)
        token2 = await register_and_login(client, another_user_data)
        wishlist_id = await create_wishlist(client, token1)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token2}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_share_link_no_auth(
        self, client: AsyncClient, user_data: dict
    ):
        """Test creating share link without authentication fails."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_multiple_share_links(
        self, client: AsyncClient, user_data: dict
    ):
        """Test creating multiple share links for same wishlist."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        # Create first link
        response1 = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 201

        # Create second link
        response2 = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "view"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 201

        # Tokens should be different
        assert response1.json()["token"] != response2.json()["token"]


class TestListShareLinks:
    """Tests for listing share links."""

    @pytest.mark.asyncio
    async def test_list_share_links_empty(
        self, client: AsyncClient, user_data: dict
    ):
        """Test listing share links when none exist."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.get(
            f"/api/v1/wishlists/{wishlist_id}/share",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_share_links_with_data(
        self, client: AsyncClient, user_data: dict
    ):
        """Test listing share links returns created links."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        # Create two share links
        await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "view"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            f"/api/v1/wishlists/{wishlist_id}/share",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        link_types = {link["link_type"] for link in data["items"]}
        assert link_types == {"mark", "view"}

    @pytest.mark.asyncio
    async def test_list_share_links_excludes_revoked(
        self, client: AsyncClient, user_data: dict
    ):
        """Test listing share links excludes revoked links."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        # Create and then revoke a share link
        create_response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )
        share_id = create_response.json()["id"]

        await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/share/{share_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Create another active link
        await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "view"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            f"/api/v1/wishlists/{wishlist_id}/share",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["link_type"] == "view"

    @pytest.mark.asyncio
    async def test_list_share_links_nonexistent_wishlist(
        self, client: AsyncClient, user_data: dict
    ):
        """Test listing share links for nonexistent wishlist returns 404."""
        token = await register_and_login(client, user_data)

        response = await client.get(
            "/api/v1/wishlists/00000000-0000-0000-0000-000000000000/share",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_share_links_unauthorized(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test listing share links on another user's wishlist returns 403."""
        token1 = await register_and_login(client, user_data)
        token2 = await register_and_login(client, another_user_data)
        wishlist_id = await create_wishlist(client, token1)

        response = await client.get(
            f"/api/v1/wishlists/{wishlist_id}/share",
            headers={"Authorization": f"Bearer {token2}"},
        )

        assert response.status_code == 403


class TestRevokeShareLink:
    """Tests for revoking share links."""

    @pytest.mark.asyncio
    async def test_revoke_share_link_success(
        self, client: AsyncClient, user_data: dict
    ):
        """Test successfully revoking a share link."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        # Create a share link
        create_response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )
        share_id = create_response.json()["id"]

        # Revoke it
        response = await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/share/{share_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204

        # Verify it's not in the list
        list_response = await client.get(
            f"/api/v1/wishlists/{wishlist_id}/share",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.json()["items"] == []

    @pytest.mark.asyncio
    async def test_revoke_share_link_not_found(
        self, client: AsyncClient, user_data: dict
    ):
        """Test revoking nonexistent share link returns 404."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/share/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_share_link_wrong_wishlist(
        self, client: AsyncClient, user_data: dict
    ):
        """Test revoking share link with wrong wishlist ID returns 404."""
        token = await register_and_login(client, user_data)
        wishlist_id1 = await create_wishlist(client, token, "Wishlist 1")
        wishlist_id2 = await create_wishlist(client, token, "Wishlist 2")

        # Create share link for wishlist 1
        create_response = await client.post(
            f"/api/v1/wishlists/{wishlist_id1}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token}"},
        )
        share_id = create_response.json()["id"]

        # Try to revoke using wishlist 2's path
        response = await client.delete(
            f"/api/v1/wishlists/{wishlist_id2}/share/{share_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_share_link_unauthorized(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test revoking share link on another user's wishlist returns 403."""
        token1 = await register_and_login(client, user_data)
        token2 = await register_and_login(client, another_user_data)
        wishlist_id = await create_wishlist(client, token1)

        # Create share link as user 1
        create_response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        share_id = create_response.json()["id"]

        # Try to revoke as user 2
        response = await client.delete(
            f"/api/v1/wishlists/{wishlist_id}/share/{share_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_revoke_share_link_nonexistent_wishlist(
        self, client: AsyncClient, user_data: dict
    ):
        """Test revoking share link on nonexistent wishlist returns 404."""
        token = await register_and_login(client, user_data)

        response = await client.delete(
            "/api/v1/wishlists/00000000-0000-0000-0000-000000000000/share/00000000-0000-0000-0000-000000000001",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404


class TestShareLinkValidation:
    """Tests for share link validation edge cases."""

    @pytest.mark.asyncio
    async def test_create_share_link_invalid_expiry(
        self, client: AsyncClient, user_data: dict
    ):
        """Test creating share link with invalid expiry days fails."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        # Expiry too small
        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark", "expires_in_days": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

        # Expiry too large
        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "mark", "expires_in_days": 400},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_share_link_invalid_type(
        self, client: AsyncClient, user_data: dict
    ):
        """Test creating share link with invalid link type fails."""
        token = await register_and_login(client, user_data)
        wishlist_id = await create_wishlist(client, token)

        response = await client.post(
            f"/api/v1/wishlists/{wishlist_id}/share",
            json={"link_type": "invalid_type"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422
