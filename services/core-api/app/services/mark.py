"""Mark service for managing item marks."""

import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.models.mark import Mark

logger = logging.getLogger(__name__)


class MarkService:
    """Service for managing marks on wishlist items."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_mark(self, item_id: UUID, user_id: UUID) -> Mark | None:
        """Get a mark by item and user."""
        result = await self.db.execute(
            select(Mark).where(
                Mark.item_id == item_id,
                Mark.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_mark_quantity(self, item_id: UUID, user_id: UUID) -> int:
        """Get the quantity marked by a specific user for an item."""
        mark = await self.get_mark(item_id, user_id)
        return mark.quantity if mark else 0

    async def get_user_marks_for_items(
        self, item_ids: list[UUID], user_id: UUID
    ) -> dict[UUID, int]:
        """Get user marks for multiple items in a single query.

        Returns:
            Dict mapping item_id to marked quantity (0 if not marked).
        """
        if not item_ids:
            return {}

        result = await self.db.execute(
            select(Mark.item_id, Mark.quantity).where(
                Mark.item_id.in_(item_ids),
                Mark.user_id == user_id,
            )
        )
        return {row.item_id: row.quantity for row in result.all()}

    async def get_total_marked_quantity(self, item_id: UUID) -> int:
        """Get total marked quantity for an item."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Mark.quantity), 0))
            .where(Mark.item_id == item_id)
        )
        return result.scalar() or 0

    async def mark_item(
        self,
        item: Item,
        user_id: UUID,
        quantity: int,
        owner_id: UUID,
    ) -> tuple[int, int, int]:
        """Mark an item.

        Uses row locking to prevent race conditions.

        Returns:
            Tuple of (my_mark_quantity, total_marked_quantity, available_quantity)
        """
        # Lock the item row to prevent concurrent updates
        result = await self.db.execute(
            select(Item)
            .where(Item.id == item.id)
            .with_for_update()
        )
        locked_item = result.scalar_one()

        # Check if user already has a mark (with lock)
        mark_result = await self.db.execute(
            select(Mark)
            .where(Mark.item_id == item.id, Mark.user_id == user_id)
            .with_for_update()
        )
        existing_mark = mark_result.scalar_one_or_none()

        # Calculate available quantity from locked item
        my_current = existing_mark.quantity if existing_mark else 0
        available = locked_item.quantity - (locked_item.marked_quantity - my_current)

        if quantity > available:
            raise ValueError(f"Cannot mark {quantity} items, only {available} available")

        if existing_mark:
            # Update existing mark
            existing_mark.quantity = quantity
        else:
            # Create new mark
            new_mark = Mark(
                item_id=item.id,
                user_id=user_id,
                quantity=quantity,
            )
            self.db.add(new_mark)

        # Update item's denormalized marked_quantity
        new_total = locked_item.marked_quantity - my_current + quantity
        locked_item.marked_quantity = new_total

        await self.db.flush()

        # Update the passed item reference to reflect the change
        item.marked_quantity = new_total

        return quantity, new_total, locked_item.quantity - new_total

    async def unmark_item(
        self,
        item: Item,
        user_id: UUID,
        owner_id: UUID,
    ) -> tuple[int, int, int]:
        """Unmark an item.

        Uses row locking to prevent race conditions.

        Returns:
            Tuple of (my_mark_quantity, total_marked_quantity, available_quantity)
        """
        # Lock the item row
        result = await self.db.execute(
            select(Item)
            .where(Item.id == item.id)
            .with_for_update()
        )
        locked_item = result.scalar_one()

        # Lock the mark row to prevent concurrent updates
        mark_result = await self.db.execute(
            select(Mark)
            .where(Mark.item_id == item.id, Mark.user_id == user_id)
            .with_for_update()
        )
        mark = mark_result.scalar_one_or_none()
        if not mark:
            # Nothing to unmark
            return 0, locked_item.marked_quantity, locked_item.quantity - locked_item.marked_quantity

        # Remove the mark
        quantity_removed = mark.quantity
        await self.db.delete(mark)

        # Update item's denormalized marked_quantity
        new_total = max(0, locked_item.marked_quantity - quantity_removed)
        locked_item.marked_quantity = new_total

        await self.db.flush()

        # Update the passed item reference
        item.marked_quantity = new_total

        return 0, new_total, locked_item.quantity - new_total
