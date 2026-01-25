"""Bookmark service for managing shared wishlist bookmarks."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bookmark import SharedWishlistBookmark
from app.models.wishlist import Wishlist


class BookmarkService:
    """Service for managing shared wishlist bookmarks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_bookmark(
        self,
        user_id: UUID,
        wishlist_id: UUID,
        share_token: str,
    ) -> SharedWishlistBookmark:
        """Save or update a bookmark when user accesses shared wishlist.

        Creates a new bookmark if not exists, otherwise updates last_accessed_at.
        """
        # Check if bookmark exists
        result = await self.db.execute(
            select(SharedWishlistBookmark).where(
                SharedWishlistBookmark.user_id == user_id,
                SharedWishlistBookmark.wishlist_id == wishlist_id,
            )
        )
        bookmark = result.scalar_one_or_none()

        if bookmark:
            # Update last accessed time and token (in case it changed)
            bookmark.last_accessed_at = datetime.now(timezone.utc)
            bookmark.share_token = share_token
        else:
            # Create new bookmark
            bookmark = SharedWishlistBookmark(
                user_id=user_id,
                wishlist_id=wishlist_id,
                share_token=share_token,
            )
            self.db.add(bookmark)

        await self.db.flush()
        return bookmark

    async def get_user_bookmarks(self, user_id: UUID) -> list[SharedWishlistBookmark]:
        """Get all bookmarks for a user, ordered by last accessed."""
        result = await self.db.execute(
            select(SharedWishlistBookmark)
            .options(
                selectinload(SharedWishlistBookmark.wishlist).selectinload(Wishlist.user),
                selectinload(SharedWishlistBookmark.wishlist).selectinload(Wishlist.items),
            )
            .where(SharedWishlistBookmark.user_id == user_id)
            .order_by(SharedWishlistBookmark.last_accessed_at.desc())
        )
        bookmarks = result.scalars().all()

        # Filter out bookmarks to deleted wishlists
        return [b for b in bookmarks if b.wishlist.deleted_at is None]

    async def remove_bookmark(self, user_id: UUID, wishlist_id: UUID) -> bool:
        """Remove a bookmark."""
        result = await self.db.execute(
            select(SharedWishlistBookmark).where(
                SharedWishlistBookmark.user_id == user_id,
                SharedWishlistBookmark.wishlist_id == wishlist_id,
            )
        )
        bookmark = result.scalar_one_or_none()

        if bookmark:
            await self.db.delete(bookmark)
            await self.db.flush()
            return True
        return False
