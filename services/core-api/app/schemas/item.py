"""Item-related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.item import ItemStatus


class ItemBase(BaseModel):
    """Base item schema with common fields."""

    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str | None, Field(max_length=1000)] = None
    price: Annotated[Decimal | None, Field(ge=0, decimal_places=2, max_digits=10)] = None
    currency: Annotated[str | None, Field(min_length=3, max_length=3)] = None
    quantity: Annotated[int, Field(ge=1)] = 1
    source_url: Annotated[str | None, Field(max_length=2048, pattern=r"^https?://.*")] = None
    image_url: Annotated[str | None, Field(max_length=2048, pattern=r"^https?://.*")] = None
    image_base64: str | None = None


class ItemCreate(ItemBase):
    """Schema for item creation."""

    pass


class ItemUpdate(BaseModel):
    """Schema for updating item."""

    title: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    price: Annotated[Decimal | None, Field(ge=0, decimal_places=2, max_digits=10)] = None
    currency: Annotated[str | None, Field(min_length=3, max_length=3)] = None
    quantity: Annotated[int | None, Field(ge=1)] = None
    source_url: Annotated[str | None, Field(max_length=2048, pattern=r"^https?://.*")] = None
    image_url: Annotated[str | None, Field(max_length=2048, pattern=r"^https?://.*")] = None
    image_base64: str | None = None


class ItemResponse(ItemBase):
    """Schema for item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wishlist_id: UUID
    status: ItemStatus
    marked_quantity: int = 0  # Hidden from owner (surprise mode)
    resolver_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class ItemResponseForOwner(ItemBase):
    """Schema for item response for wishlist owner - marked_quantity hidden."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wishlist_id: UUID
    status: ItemStatus
    # marked_quantity is intentionally omitted for surprise mode
    resolver_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class ItemListResponse(BaseModel):
    """Schema for item list response with pagination."""

    items: list[ItemResponse]
    total: int
    limit: int
    offset: int
