"""Share link management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.share import (
    ShareLinkCreate,
    ShareLinkResponse,
    ShareLinkListResponse,
)
from app.services.share import ShareService
from app.services.wishlist import WishlistService

router = APIRouter(prefix="/api/v1/wishlists", tags=["share"])


@router.get(
    "/{wishlist_id}/share",
    response_model=ShareLinkListResponse,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to access this wishlist"},
    },
)
async def list_share_links(
    wishlist_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareLinkListResponse:
    """List all share links for a wishlist."""
    wishlist_service = WishlistService(db)
    share_service = ShareService(db)

    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if wishlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if not wishlist_service.is_owner(wishlist, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this wishlist",
        )

    links = await share_service.list_share_links(wishlist_id)
    return ShareLinkListResponse(items=links)


@router.post(
    "/{wishlist_id}/share",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to share this wishlist"},
    },
)
async def create_share_link(
    wishlist_id: UUID,
    data: ShareLinkCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareLinkResponse:
    """Create a new share link for a wishlist."""
    wishlist_service = WishlistService(db)
    share_service = ShareService(db)

    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if wishlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if not wishlist_service.is_owner(wishlist, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to share this wishlist",
        )

    link = await share_service.create_share_link(wishlist_id, data)
    return link


@router.delete(
    "/{wishlist_id}/share/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Share link not found"},
        403: {"description": "Not authorized to revoke this share link"},
    },
)
async def revoke_share_link(
    wishlist_id: UUID,
    share_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Revoke a share link."""
    wishlist_service = WishlistService(db)
    share_service = ShareService(db)

    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if wishlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if not wishlist_service.is_owner(wishlist, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this share link",
        )

    share_link = await share_service.get_share_link(share_id)
    if share_link is None or share_link.wishlist_id != wishlist_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    await share_service.revoke_share_link(share_link)
