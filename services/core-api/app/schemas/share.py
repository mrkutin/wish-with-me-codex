"""Share-related Pydantic schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.share import ShareLinkType


class ShareLinkCreate(BaseModel):
    """Schema for creating a share link."""

    link_type: ShareLinkType = ShareLinkType.MARK
    expires_in_days: Annotated[int | None, Field(ge=1, le=365)] = None


class ShareLinkResponse(BaseModel):
    """Schema for share link response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wishlist_id: UUID
    token: str
    link_type: ShareLinkType
    expires_at: datetime | None
    access_count: int
    created_at: datetime
    share_url: str
    qr_code_base64: str | None = None


class ShareLinkListResponse(BaseModel):
    """Schema for list of share links."""

    items: list[ShareLinkResponse]


class OwnerPublicProfile(BaseModel):
    """Public profile info for wishlist owner."""

    id: UUID
    name: str
    avatar_base64: str


class SharedItemResponse(BaseModel):
    """Schema for item in a shared wishlist view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    price_amount: str | None = None
    price_currency: str | None = None
    image_base64: str | None
    quantity: int
    marked_quantity: int
    available_quantity: int
    my_mark_quantity: int = 0


class SharedWishlistInfo(BaseModel):
    """Basic info about a shared wishlist."""

    id: UUID
    title: str
    description: str | None
    owner: OwnerPublicProfile
    item_count: int


class SharedWishlistResponse(BaseModel):
    """Full response for shared wishlist access."""

    wishlist: SharedWishlistInfo
    items: list[SharedItemResponse]
    permissions: list[str]


class SharedWishlistPreview(BaseModel):
    """Preview response for unauthenticated users."""

    wishlist: dict  # title, owner_name, item_count
    requires_auth: bool = True
    auth_redirect: str


class MarkCreate(BaseModel):
    """Schema for marking an item."""

    quantity: Annotated[int, Field(ge=1)] = 1


class MarkResponse(BaseModel):
    """Response after marking/unmarking an item."""

    item_id: UUID
    my_mark_quantity: int
    total_marked_quantity: int
    available_quantity: int
