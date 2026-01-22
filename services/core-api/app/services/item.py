"""Item service for item management operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item, ItemStatus
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    """Service for item management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, item_id: UUID) -> Item | None:
        """Get an item by ID."""
        result = await self.db.execute(
            select(Item).where(Item.id == item_id, Item.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_wishlist_items(
        self, wishlist_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[Item], int]:
        """List items for a wishlist with pagination.

        Returns:
            Tuple of (items, total_count)
        """
        # Get paginated items
        result = await self.db.execute(
            select(Item)
            .where(Item.wishlist_id == wishlist_id, Item.deleted_at.is_(None))
            .order_by(Item.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(result.scalars().all())

        # Get total count
        count_result = await self.db.execute(
            select(func.count())
            .select_from(Item)
            .where(Item.wishlist_id == wishlist_id, Item.deleted_at.is_(None))
        )
        total = count_result.scalar_one()

        return items, total

    async def create(self, wishlist_id: UUID, data: ItemCreate) -> Item:
        """Create a new item."""
        item = Item(
            wishlist_id=wishlist_id,
            title=data.title,
            description=data.description,
            price=data.price,
            currency=data.currency,
            quantity=data.quantity,
            source_url=data.source_url,
            image_url=data.image_url,
            status=ItemStatus.PENDING,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def update(self, item: Item, data: ItemUpdate) -> Item:
        """Update an item."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(item, field, value)

        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def soft_delete(self, item: Item) -> None:
        """Soft delete an item."""
        item.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def mark_resolving(self, item: Item) -> None:
        """Mark an item as currently being resolved."""
        item.status = ItemStatus.RESOLVING
        await self.db.flush()
        await self.db.refresh(item)

    async def update_from_resolver(
        self, item: Item, resolver_data: dict
    ) -> Item:
        """Update item with data from resolver service.

        Args:
            item: The item to update
            resolver_data: Data from resolver containing title, description, price, etc.

        Returns:
            Updated item with RESOLVED status
        """
        # Update fields from resolver
        if resolver_data.get("title"):
            item.title = resolver_data["title"]
        if resolver_data.get("description"):
            item.description = resolver_data["description"]
        if resolver_data.get("price") is not None:
            item.price = resolver_data["price"]
        if resolver_data.get("currency"):
            item.currency = resolver_data["currency"]
        if resolver_data.get("image_base64"):
            item.image_base64 = resolver_data["image_base64"]
        if resolver_data.get("source_url"):
            # Update source_url from resolver (canonical URL)
            item.source_url = resolver_data["source_url"]

        # Store full metadata
        item.resolver_metadata = resolver_data.get("metadata", {})
        item.status = ItemStatus.RESOLVED

        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def mark_resolver_failed(self, item: Item, error: str) -> None:
        """Mark an item as failed to resolve.

        Args:
            item: The item that failed to resolve
            error: Error message from resolver
        """
        item.status = ItemStatus.FAILED
        item.resolver_metadata = {
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.flush()
        await self.db.refresh(item)
