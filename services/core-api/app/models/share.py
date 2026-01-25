"""Share-related SQLAlchemy models."""

import enum
import secrets
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.wishlist import Wishlist


class ShareLinkType(str, enum.Enum):
    """Type of share link access."""

    VIEW = "view"
    MARK = "mark"


class ShareLink(Base):
    """Share link for a wishlist."""

    __tablename__ = "share_links"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    wishlist_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    link_type: Mapped[ShareLinkType] = mapped_column(
        Enum(ShareLinkType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ShareLinkType.MARK,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    wishlist: Mapped["Wishlist"] = relationship("Wishlist", back_populates="share_links")

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for the share link."""
        return secrets.token_urlsafe(24)[:32]

    @property
    def is_valid(self) -> bool:
        """Check if share link is valid (not revoked and not expired)."""
        if self.revoked:
            return False
        if self.expires_at is not None:
            from datetime import timezone
            return self.expires_at > datetime.now(timezone.utc)
        return True

    def __repr__(self) -> str:
        return f"<ShareLink {self.token}>"
