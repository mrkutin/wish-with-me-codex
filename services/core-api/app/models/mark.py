"""Mark-related SQLAlchemy models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.user import User


class Mark(Base):
    """Mark representing a user's intent to purchase an item."""

    __tablename__ = "marks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    item_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="marks")
    user: Mapped["User"] = relationship("User", back_populates="marks")

    __table_args__ = (
        UniqueConstraint("item_id", "user_id", name="uq_mark_item_user"),
        CheckConstraint("quantity > 0", name="check_mark_quantity_positive"),
        {"comment": "User marks on wishlist items"},
    )

    def __repr__(self) -> str:
        return f"<Mark item={self.item_id} user={self.user_id} qty={self.quantity}>"
