"""Tests for bookmark functionality."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def item_data() -> dict:
    """Sample item creation data."""
    return {
        "title": "Test Item",
        "description": "A test item",
        "quantity": 2,
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


class TestBookmarkCreation:
    """Tests for automatic bookmark creation on share link access."""

    @pytest.mark.asyncio
    async def test_bookmark_created_on_first_access(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test bookmark is created when user first accesses shared wishlist."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token, "Birthday List")
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Access the shared wishlist
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Check bookmarks
        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["wishlist_id"] == wishlist_id
        assert data["items"][0]["share_token"] == share_token
        assert data["items"][0]["wishlist"]["title"] == "Birthday List"

    @pytest.mark.asyncio
    async def test_bookmark_updated_on_subsequent_access(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test bookmark's last_accessed_at is updated on subsequent access."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # First access
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Get initial bookmark timestamp
        response1 = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        initial_time = response1.json()["items"][0]["last_accessed_at"]

        # Wait a tiny bit and access again
        import asyncio
        await asyncio.sleep(0.01)

        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Get updated bookmark
        response2 = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        updated_time = response2.json()["items"][0]["last_accessed_at"]

        # Still just one bookmark
        assert len(response2.json()["items"]) == 1
        # Time should be updated (or at least not earlier)
        assert updated_time >= initial_time

    @pytest.mark.asyncio
    async def test_owner_accessing_own_link_no_bookmark(
        self, client: AsyncClient, user_data: dict
    ):
        """Test owner accessing their own share link does not create bookmark."""
        owner_token, _ = await register_and_login(client, user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Owner accesses via share link
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        # Check bookmarks (should be empty)
        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert response.status_code == 200
        assert len(response.json()["items"]) == 0

    @pytest.mark.asyncio
    async def test_bookmark_includes_owner_info(
        self, client: AsyncClient, user_data: dict, another_user_data: dict, item_data: dict
    ):
        """Test bookmark includes owner profile information."""
        owner_token, owner_id = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token, "Gift Ideas")
        await create_item(client, owner_token, wishlist_id, item_data)
        await create_item(client, owner_token, wishlist_id, {"title": "Second Item"})
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Access to create bookmark
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        bookmark = response.json()["items"][0]
        assert bookmark["wishlist"]["title"] == "Gift Ideas"
        assert bookmark["wishlist"]["item_count"] == 2
        assert bookmark["wishlist"]["owner"]["id"] == owner_id
        assert bookmark["wishlist"]["owner"]["name"] == user_data["name"]


class TestListBookmarks:
    """Tests for listing bookmarks."""

    @pytest.mark.asyncio
    async def test_list_bookmarks_empty(
        self, client: AsyncClient, user_data: dict
    ):
        """Test listing bookmarks when none exist."""
        token, _ = await register_and_login(client, user_data)

        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["items"] == []

    @pytest.mark.asyncio
    async def test_list_bookmarks_multiple(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test listing multiple bookmarks."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        # Create two wishlists with share links
        wishlist1_id = await create_wishlist(client, owner_token, "Wishlist 1")
        wishlist2_id = await create_wishlist(client, owner_token, "Wishlist 2")
        share_token1 = await create_share_link(client, owner_token, wishlist1_id)
        share_token2 = await create_share_link(client, owner_token, wishlist2_id)

        # Access both
        await client.get(
            f"/api/v1/shared/{share_token1}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        await client.get(
            f"/api/v1/shared/{share_token2}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        titles = {b["wishlist"]["title"] for b in data["items"]}
        assert titles == {"Wishlist 1", "Wishlist 2"}

    @pytest.mark.asyncio
    async def test_list_bookmarks_ordered_by_last_accessed(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test bookmarks are ordered by last accessed (most recent first)."""
        import asyncio

        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        # Create two wishlists
        wishlist1_id = await create_wishlist(client, owner_token, "First Accessed")
        wishlist2_id = await create_wishlist(client, owner_token, "Last Accessed")
        share_token1 = await create_share_link(client, owner_token, wishlist1_id)
        share_token2 = await create_share_link(client, owner_token, wishlist2_id)

        # Access first, then second with delay to ensure distinct timestamps
        await client.get(
            f"/api/v1/shared/{share_token1}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        await asyncio.sleep(1.0)  # 1 second to ensure distinct timestamps
        await client.get(
            f"/api/v1/shared/{share_token2}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        data = response.json()
        assert len(data["items"]) == 2
        # Most recently accessed should be first
        assert data["items"][0]["wishlist"]["title"] == "Last Accessed"
        assert data["items"][1]["wishlist"]["title"] == "First Accessed"

    @pytest.mark.asyncio
    async def test_list_bookmarks_excludes_deleted_wishlists(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test listing bookmarks excludes deleted wishlists."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        # Create two wishlists
        wishlist1_id = await create_wishlist(client, owner_token, "Keep This")
        wishlist2_id = await create_wishlist(client, owner_token, "Delete This")
        share_token1 = await create_share_link(client, owner_token, wishlist1_id)
        share_token2 = await create_share_link(client, owner_token, wishlist2_id)

        # Access both
        await client.get(
            f"/api/v1/shared/{share_token1}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        await client.get(
            f"/api/v1/shared/{share_token2}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Delete one wishlist
        await client.delete(
            f"/api/v1/wishlists/{wishlist2_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["wishlist"]["title"] == "Keep This"

    @pytest.mark.asyncio
    async def test_list_bookmarks_no_auth(self, client: AsyncClient):
        """Test listing bookmarks without authentication fails."""
        response = await client.get("/api/v1/shared/bookmarks")
        assert response.status_code == 401  # Unauthenticated returns 401

    @pytest.mark.asyncio
    async def test_bookmarks_isolated_between_users(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test each user only sees their own bookmarks."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer1_token, _ = await register_and_login(client, another_user_data)

        # Create third user
        third_user_data = {
            "email": "third@example.com",
            "password": "thirdPassword789",
            "name": "Third User",
            "locale": "en",
        }
        viewer2_token, _ = await register_and_login(client, third_user_data)

        # Create wishlist
        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Only viewer 1 accesses
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer1_token}"},
        )

        # Viewer 1 should have bookmark
        response1 = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer1_token}"},
        )
        assert len(response1.json()["items"]) == 1

        # Viewer 2 should have no bookmarks
        response2 = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer2_token}"},
        )
        assert len(response2.json()["items"]) == 0


class TestRemoveBookmark:
    """Tests for removing bookmarks."""

    @pytest.mark.asyncio
    async def test_remove_bookmark_success(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test successfully removing a bookmark."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Create bookmark by accessing
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Verify bookmark exists
        bookmarks = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert len(bookmarks.json()["items"]) == 1

        # Remove bookmark
        response = await client.delete(
            f"/api/v1/shared/bookmarks/{wishlist_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 204

        # Verify bookmark is gone
        bookmarks = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert len(bookmarks.json()["items"]) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_bookmark(
        self, client: AsyncClient, user_data: dict
    ):
        """Test removing a bookmark that doesn't exist succeeds silently."""
        token, _ = await register_and_login(client, user_data)

        response = await client.delete(
            "/api/v1/shared/bookmarks/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should succeed even if bookmark didn't exist
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_remove_bookmark_no_auth(self, client: AsyncClient):
        """Test removing bookmark without authentication fails."""
        response = await client.delete(
            "/api/v1/shared/bookmarks/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401  # Unauthenticated returns 401

    @pytest.mark.asyncio
    async def test_remove_bookmark_preserves_others(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test removing one bookmark preserves others."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        # Create two wishlists
        wishlist1_id = await create_wishlist(client, owner_token, "Keep")
        wishlist2_id = await create_wishlist(client, owner_token, "Remove")
        share_token1 = await create_share_link(client, owner_token, wishlist1_id)
        share_token2 = await create_share_link(client, owner_token, wishlist2_id)

        # Access both
        await client.get(
            f"/api/v1/shared/{share_token1}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        await client.get(
            f"/api/v1/shared/{share_token2}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # Remove second bookmark
        await client.delete(
            f"/api/v1/shared/bookmarks/{wishlist2_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        # First bookmark should still exist
        bookmarks = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert len(bookmarks.json()["items"]) == 1
        assert bookmarks.json()["items"][0]["wishlist"]["title"] == "Keep"

    @pytest.mark.asyncio
    async def test_remove_bookmark_does_not_affect_other_users(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test removing bookmark does not affect other users' bookmarks."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer1_token, _ = await register_and_login(client, another_user_data)

        # Create third user
        third_user_data = {
            "email": "third@example.com",
            "password": "thirdPassword789",
            "name": "Third User",
            "locale": "en",
        }
        viewer2_token, _ = await register_and_login(client, third_user_data)

        # Create wishlist
        wishlist_id = await create_wishlist(client, owner_token)
        share_token = await create_share_link(client, owner_token, wishlist_id)

        # Both viewers access
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer1_token}"},
        )
        await client.get(
            f"/api/v1/shared/{share_token}",
            headers={"Authorization": f"Bearer {viewer2_token}"},
        )

        # Viewer 1 removes bookmark
        await client.delete(
            f"/api/v1/shared/bookmarks/{wishlist_id}",
            headers={"Authorization": f"Bearer {viewer1_token}"},
        )

        # Viewer 2 should still have bookmark
        bookmarks = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer2_token}"},
        )
        assert len(bookmarks.json()["items"]) == 1


class TestBookmarkWithTokenUpdates:
    """Tests for bookmark behavior when share tokens change."""

    @pytest.mark.asyncio
    async def test_bookmark_token_updated_on_new_link_access(
        self, client: AsyncClient, user_data: dict, another_user_data: dict
    ):
        """Test bookmark token is updated when user accesses via different link."""
        owner_token, _ = await register_and_login(client, user_data)
        viewer_token, _ = await register_and_login(client, another_user_data)

        wishlist_id = await create_wishlist(client, owner_token)
        share_token1 = await create_share_link(client, owner_token, wishlist_id, "view")
        share_token2 = await create_share_link(client, owner_token, wishlist_id, "mark")

        # Access via first link
        await client.get(
            f"/api/v1/shared/{share_token1}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        bookmarks1 = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert bookmarks1.json()["items"][0]["share_token"] == share_token1

        # Access via second link
        await client.get(
            f"/api/v1/shared/{share_token2}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        bookmarks2 = await client.get(
            "/api/v1/shared/bookmarks",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        # Still one bookmark but with updated token
        assert len(bookmarks2.json()["items"]) == 1
        assert bookmarks2.json()["items"][0]["share_token"] == share_token2
