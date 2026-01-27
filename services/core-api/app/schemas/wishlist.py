"""Wishlist-related Pydantic schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WishlistBase(BaseModel):
    """Base wishlist schema with common fields."""

    name: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str | None, Field(max_length=500)] = None
    is_public: bool = False
    icon: Annotated[str, Field(max_length=50)] = "card_giftcard"


class WishlistCreate(WishlistBase):
    """Schema for wishlist creation."""

    pass


class WishlistUpdate(BaseModel):
    """Schema for updating wishlist."""

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    description: Annotated[str | None, Field(max_length=500)] = None
    is_public: bool | None = None
    icon: Annotated[str | None, Field(max_length=50)] = None


class WishlistResponse(WishlistBase):
    """Schema for wishlist response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class WishlistListResponse(BaseModel):
    """Schema for wishlist list response with pagination."""

    wishlists: list[WishlistResponse]
    total: int
    limit: int
    offset: int
