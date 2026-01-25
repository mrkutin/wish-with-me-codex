"""Wishlist-related SQLAlchemy models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.bookmark import SharedWishlistBookmark
    from app.models.item import Item
    from app.models.share import ShareLink
    from app.models.user import User


class Wishlist(Base):
    """Wishlist model."""

    __tablename__ = "wishlists"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="wishlists")
    items: Mapped[list["Item"]] = relationship(
        "Item", back_populates="wishlist", cascade="all, delete-orphan"
    )
    share_links: Mapped[list["ShareLink"]] = relationship(
        "ShareLink", back_populates="wishlist", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list["SharedWishlistBookmark"]] = relationship(
        "SharedWishlistBookmark", back_populates="wishlist", cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        """Check if wishlist is active (not deleted)."""
        return self.deleted_at is None

    def __repr__(self) -> str:
        return f"<Wishlist {self.name}>"
