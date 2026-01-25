"""Tests for the mark service (unit tests)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.models.item import Item
from app.models.mark import Mark
from app.models.user import User
from app.models.wishlist import Wishlist
from app.services.mark import MarkService


async def create_test_user(db: AsyncSession, email: str = "test@example.com") -> User:
    """Create a test user in the database."""
    user = User(
        id=uuid4(),
        email=email,
        password_hash="hashed_password",
        name="Test User",
        avatar_base64="data:image/png;base64,test",
    )
    db.add(user)
    await db.flush()
    return user


async def create_test_wishlist(db: AsyncSession, user: User) -> Wishlist:
    """Create a test wishlist in the database."""
    wishlist = Wishlist(
        id=uuid4(),
        user_id=user.id,
        name="Test Wishlist",
    )
    db.add(wishlist)
    await db.flush()
    return wishlist


async def create_test_item(
    db: AsyncSession, wishlist: Wishlist, quantity: int = 5
) -> Item:
    """Create a test item in the database."""
    item = Item(
        id=uuid4(),
        wishlist_id=wishlist.id,
        title="Test Item",
        quantity=quantity,
        marked_quantity=0,
    )
    db.add(item)
    await db.flush()
    return item


class TestMarkService:
    """Tests for MarkService."""

    @pytest.mark.asyncio
    async def test_mark_item_first_time(self, db_session: AsyncSession):
        """Test marking an item for the first time."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)
        my_qty, total_qty, available = await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=2,
            owner_id=owner.id,
        )

        assert my_qty == 2
        assert total_qty == 2
        assert available == 3
        assert item.marked_quantity == 2

    @pytest.mark.asyncio
    async def test_mark_item_update_existing(self, db_session: AsyncSession):
        """Test updating an existing mark."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # First mark
        await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=1,
            owner_id=owner.id,
        )

        # Update mark
        my_qty, total_qty, available = await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=3,
            owner_id=owner.id,
        )

        assert my_qty == 3
        assert total_qty == 3
        assert available == 2
        assert item.marked_quantity == 3

    @pytest.mark.asyncio
    async def test_mark_item_exceeds_available(self, db_session: AsyncSession):
        """Test marking more than available quantity raises error."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=3)

        mark_service = MarkService(db_session)

        with pytest.raises(ValueError) as exc_info:
            await mark_service.mark_item(
                item=item,
                user_id=marker.id,
                quantity=5,
                owner_id=owner.id,
            )

        assert "only 3 available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mark_item_multiple_users(self, db_session: AsyncSession):
        """Test multiple users marking the same item."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker1 = await create_test_user(db_session, "marker1@test.com")
        marker2 = await create_test_user(db_session, "marker2@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # Marker 1 marks 2
        my_qty1, total_qty1, available1 = await mark_service.mark_item(
            item=item,
            user_id=marker1.id,
            quantity=2,
            owner_id=owner.id,
        )

        assert my_qty1 == 2
        assert total_qty1 == 2
        assert available1 == 3

        # Marker 2 marks 2
        my_qty2, total_qty2, available2 = await mark_service.mark_item(
            item=item,
            user_id=marker2.id,
            quantity=2,
            owner_id=owner.id,
        )

        assert my_qty2 == 2
        assert total_qty2 == 4
        assert available2 == 1
        assert item.marked_quantity == 4

    @pytest.mark.asyncio
    async def test_mark_item_exceeds_after_other_marks(self, db_session: AsyncSession):
        """Test marking fails when other users have already marked most items."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker1 = await create_test_user(db_session, "marker1@test.com")
        marker2 = await create_test_user(db_session, "marker2@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=3)

        mark_service = MarkService(db_session)

        # Marker 1 marks 2
        await mark_service.mark_item(
            item=item,
            user_id=marker1.id,
            quantity=2,
            owner_id=owner.id,
        )

        # Marker 2 tries to mark 2 (only 1 available)
        with pytest.raises(ValueError) as exc_info:
            await mark_service.mark_item(
                item=item,
                user_id=marker2.id,
                quantity=2,
                owner_id=owner.id,
            )

        assert "only 1 available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unmark_item(self, db_session: AsyncSession):
        """Test unmarking an item."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # Mark first
        await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=2,
            owner_id=owner.id,
        )

        # Unmark
        my_qty, total_qty, available = await mark_service.unmark_item(
            item=item,
            user_id=marker.id,
            owner_id=owner.id,
        )

        assert my_qty == 0
        assert total_qty == 0
        assert available == 5
        assert item.marked_quantity == 0

    @pytest.mark.asyncio
    async def test_unmark_item_not_marked(self, db_session: AsyncSession):
        """Test unmarking an item that was never marked returns gracefully."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        my_qty, total_qty, available = await mark_service.unmark_item(
            item=item,
            user_id=marker.id,
            owner_id=owner.id,
        )

        assert my_qty == 0
        assert total_qty == 0
        assert available == 5

    @pytest.mark.asyncio
    async def test_unmark_preserves_other_marks(self, db_session: AsyncSession):
        """Test unmarking by one user preserves other users' marks."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker1 = await create_test_user(db_session, "marker1@test.com")
        marker2 = await create_test_user(db_session, "marker2@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # Both users mark
        await mark_service.mark_item(
            item=item,
            user_id=marker1.id,
            quantity=2,
            owner_id=owner.id,
        )
        await mark_service.mark_item(
            item=item,
            user_id=marker2.id,
            quantity=1,
            owner_id=owner.id,
        )

        # Marker 1 unmarks
        my_qty, total_qty, available = await mark_service.unmark_item(
            item=item,
            user_id=marker1.id,
            owner_id=owner.id,
        )

        assert my_qty == 0
        assert total_qty == 1  # Marker 2's mark remains
        assert available == 4
        assert item.marked_quantity == 1

    @pytest.mark.asyncio
    async def test_get_user_mark_quantity(self, db_session: AsyncSession):
        """Test getting user's mark quantity for an item."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # Before marking
        qty = await mark_service.get_user_mark_quantity(item.id, marker.id)
        assert qty == 0

        # After marking
        await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=3,
            owner_id=owner.id,
        )

        qty = await mark_service.get_user_mark_quantity(item.id, marker.id)
        assert qty == 3

    @pytest.mark.asyncio
    async def test_get_user_marks_for_items(self, db_session: AsyncSession):
        """Test batch fetching user marks for multiple items."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item1 = await create_test_item(db_session, wishlist, quantity=5)
        item2 = await create_test_item(db_session, wishlist, quantity=3)
        item3 = await create_test_item(db_session, wishlist, quantity=2)

        mark_service = MarkService(db_session)

        # Mark items 1 and 3
        await mark_service.mark_item(
            item=item1,
            user_id=marker.id,
            quantity=2,
            owner_id=owner.id,
        )
        await mark_service.mark_item(
            item=item3,
            user_id=marker.id,
            quantity=1,
            owner_id=owner.id,
        )

        marks = await mark_service.get_user_marks_for_items(
            [item1.id, item2.id, item3.id],
            marker.id,
        )

        assert marks[item1.id] == 2
        assert item2.id not in marks  # Not marked
        assert marks[item3.id] == 1

    @pytest.mark.asyncio
    async def test_get_user_marks_for_items_empty_list(self, db_session: AsyncSession):
        """Test batch fetching with empty item list."""
        marker = await create_test_user(db_session, "marker@test.com")

        mark_service = MarkService(db_session)
        marks = await mark_service.get_user_marks_for_items([], marker.id)

        assert marks == {}

    @pytest.mark.asyncio
    async def test_get_total_marked_quantity(self, db_session: AsyncSession):
        """Test getting total marked quantity for an item."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker1 = await create_test_user(db_session, "marker1@test.com")
        marker2 = await create_test_user(db_session, "marker2@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=10)

        mark_service = MarkService(db_session)

        # Before any marks
        total = await mark_service.get_total_marked_quantity(item.id)
        assert total == 0

        # After marks from two users
        await mark_service.mark_item(
            item=item,
            user_id=marker1.id,
            quantity=3,
            owner_id=owner.id,
        )
        await mark_service.mark_item(
            item=item,
            user_id=marker2.id,
            quantity=2,
            owner_id=owner.id,
        )

        total = await mark_service.get_total_marked_quantity(item.id)
        assert total == 5

    @pytest.mark.asyncio
    async def test_mark_item_all_available(self, db_session: AsyncSession):
        """Test marking all available items."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=3)

        mark_service = MarkService(db_session)

        my_qty, total_qty, available = await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=3,
            owner_id=owner.id,
        )

        assert my_qty == 3
        assert total_qty == 3
        assert available == 0
        assert item.marked_quantity == 3

    @pytest.mark.asyncio
    async def test_update_mark_reduces_quantity(self, db_session: AsyncSession):
        """Test reducing mark quantity via update."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker = await create_test_user(db_session, "marker@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # Mark 4
        await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=4,
            owner_id=owner.id,
        )

        # Reduce to 2
        my_qty, total_qty, available = await mark_service.mark_item(
            item=item,
            user_id=marker.id,
            quantity=2,
            owner_id=owner.id,
        )

        assert my_qty == 2
        assert total_qty == 2
        assert available == 3
        assert item.marked_quantity == 2

    @pytest.mark.asyncio
    async def test_update_mark_when_others_marked_in_between(
        self, db_session: AsyncSession
    ):
        """Test updating mark when another user marked in between."""
        owner = await create_test_user(db_session, "owner@test.com")
        marker1 = await create_test_user(db_session, "marker1@test.com")
        marker2 = await create_test_user(db_session, "marker2@test.com")
        wishlist = await create_test_wishlist(db_session, owner)
        item = await create_test_item(db_session, wishlist, quantity=5)

        mark_service = MarkService(db_session)

        # Marker 1 marks 2
        await mark_service.mark_item(
            item=item,
            user_id=marker1.id,
            quantity=2,
            owner_id=owner.id,
        )

        # Marker 2 marks 2
        await mark_service.mark_item(
            item=item,
            user_id=marker2.id,
            quantity=2,
            owner_id=owner.id,
        )

        # Marker 1 tries to increase to 3 (but only 1 more available)
        with pytest.raises(ValueError) as exc_info:
            await mark_service.mark_item(
                item=item,
                user_id=marker1.id,
                quantity=4,  # Wants 4, has 2, needs 2 more but only 1 available
                owner_id=owner.id,
            )

        # Should include that only 3 total available (2 they have + 1 free)
        assert "only 3 available" in str(exc_info.value)
