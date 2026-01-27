"""Wishlist service for wishlist management operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wishlist import Wishlist
from app.schemas.wishlist import WishlistCreate, WishlistUpdate


class WishlistService:
    """Service for wishlist management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, wishlist_id: UUID) -> Wishlist | None:
        """Get a wishlist by ID."""
        result = await self.db.execute(
            select(Wishlist).where(
                Wishlist.id == wishlist_id, Wishlist.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list_user_wishlists(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[Wishlist], int]:
        """List wishlists for a user with pagination.

        Returns:
            Tuple of (wishlists, total_count)
        """
        # Get paginated wishlists
        result = await self.db.execute(
            select(Wishlist)
            .where(Wishlist.user_id == user_id, Wishlist.deleted_at.is_(None))
            .order_by(Wishlist.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        wishlists = list(result.scalars().all())

        # Get total count
        count_result = await self.db.execute(
            select(func.count())
            .select_from(Wishlist)
            .where(Wishlist.user_id == user_id, Wishlist.deleted_at.is_(None))
        )
        total = count_result.scalar_one()

        return wishlists, total

    async def create(self, user_id: UUID, data: WishlistCreate) -> Wishlist:
        """Create a new wishlist."""
        wishlist = Wishlist(
            user_id=user_id,
            name=data.name,
            description=data.description,
            is_public=data.is_public,
            icon=data.icon,
        )
        self.db.add(wishlist)
        await self.db.flush()
        await self.db.refresh(wishlist)
        return wishlist

    async def update(self, wishlist: Wishlist, data: WishlistUpdate) -> Wishlist:
        """Update a wishlist."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(wishlist, field, value)

        await self.db.flush()
        await self.db.refresh(wishlist)
        return wishlist

    async def soft_delete(self, wishlist: Wishlist) -> None:
        """Soft delete a wishlist."""
        wishlist.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    def is_owner(self, wishlist: Wishlist, user_id: UUID) -> bool:
        """Check if a user owns a wishlist."""
        return wishlist.user_id == user_id
