"""Pydantic schemas for API validation."""

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserPublicProfile,
    SocialLinks,
)
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    RefreshTokenRequest,
    AuthResponse,
)
from app.schemas.wishlist import (
    WishlistCreate,
    WishlistUpdate,
    WishlistResponse,
    WishlistListResponse,
)
from app.schemas.item import (
    ItemCreate,
    ItemUpdate,
    ItemResponse,
    ItemResponseForOwner,
    ItemListResponse,
)
from app.schemas.share import (
    ShareLinkCreate,
    ShareLinkResponse,
    ShareLinkListResponse,
    SharedWishlistResponse,
    SharedWishlistPreview,
    SharedItemResponse,
    MarkCreate,
    MarkResponse,
)
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
)

__all__ = [
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserPublicProfile",
    "SocialLinks",
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "AuthResponse",
    "WishlistCreate",
    "WishlistUpdate",
    "WishlistResponse",
    "WishlistListResponse",
    "ItemCreate",
    "ItemUpdate",
    "ItemResponse",
    "ItemResponseForOwner",
    "ItemListResponse",
    "ShareLinkCreate",
    "ShareLinkResponse",
    "ShareLinkListResponse",
    "SharedWishlistResponse",
    "SharedWishlistPreview",
    "SharedItemResponse",
    "MarkCreate",
    "MarkResponse",
    "NotificationResponse",
    "NotificationListResponse",
    "NotificationMarkReadRequest",
]
