"""Shared wishlist bookmark model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.wishlist import Wishlist


class SharedWishlistBookmark(Base):
    """Bookmark for tracking user access to shared wishlists."""

    __tablename__ = "shared_wishlist_bookmarks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    wishlist_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    share_token: Mapped[str] = mapped_column(String(32), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="shared_bookmarks")
    wishlist: Mapped["Wishlist"] = relationship("Wishlist", back_populates="bookmarks")

    __table_args__ = (
        UniqueConstraint("user_id", "wishlist_id", name="uq_bookmark_user_wishlist"),
        {"comment": "Tracks user access to shared wishlists"},
    )

    def __repr__(self) -> str:
        return f"<SharedWishlistBookmark user={self.user_id} wishlist={self.wishlist_id}>"
