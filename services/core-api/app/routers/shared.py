"""Shared wishlist access endpoints."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser, OptionalCurrentUser
from app.models.share import ShareLinkType
from app.schemas.share import (
    MarkCreate,
    MarkResponse,
    OwnerPublicProfile,
    SharedItemResponse,
    SharedWishlistInfo,
    SharedWishlistPreview,
    SharedWishlistResponse,
)
from app.services.mark import MarkService
from app.services.share import ShareService

router = APIRouter(prefix="/api/v1/shared", tags=["shared"])


@router.get(
    "/{token}/preview",
    response_model=SharedWishlistPreview,
)
async def preview_shared_wishlist(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SharedWishlistPreview:
    """Preview a shared wishlist (unauthenticated)."""
    share_service = ShareService(db)

    share_link = await share_service.get_share_link_by_token(token)
    if share_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    if not share_service.is_link_valid(share_link):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link has expired",
        )

    wishlist = share_link.wishlist
    if wishlist.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Count active items
    item_count = sum(1 for item in wishlist.items if item.deleted_at is None)

    # Get owner name (abbreviated for privacy)
    owner_name = wishlist.user.name
    if len(owner_name) > 10:
        owner_name = owner_name[:10] + "."

    return SharedWishlistPreview(
        wishlist={
            "title": wishlist.name,
            "owner_name": owner_name,
            "item_count": item_count,
        },
        requires_auth=True,
        auth_redirect=f"/login?share_token={token}",
    )


@router.get(
    "/{token}",
    response_model=SharedWishlistResponse,
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Share link not found or expired"},
    },
)
async def get_shared_wishlist(
    token: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SharedWishlistResponse:
    """Access a shared wishlist (authenticated)."""
    share_service = ShareService(db)
    mark_service = MarkService(db)

    share_link = await share_service.get_share_link_by_token(token)
    if share_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    if not share_service.is_link_valid(share_link):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link has expired",
        )

    wishlist = share_link.wishlist
    if wishlist.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Increment access count
    await share_service.increment_access_count(share_link)

    # Get owner info
    owner = wishlist.user
    owner_profile = OwnerPublicProfile(
        id=owner.id,
        name=owner.name,
        avatar_base64=owner.avatar_base64,
    )

    # Get active items
    active_items = [item for item in wishlist.items if item.deleted_at is None]

    # Batch fetch user marks to avoid N+1 query
    item_ids = [item.id for item in active_items]
    user_marks = await mark_service.get_user_marks_for_items(item_ids, current_user.id)

    # Build items list
    items = []
    for item in active_items:
        my_mark = user_marks.get(item.id, 0)
        available = item.quantity - item.marked_quantity

        items.append(SharedItemResponse(
            id=item.id,
            title=item.title,
            description=item.description,
            price_amount=str(item.price) if item.price else None,
            price_currency=item.currency,
            image_base64=item.image_base64,
            quantity=item.quantity,
            marked_quantity=item.marked_quantity,
            available_quantity=available,
            my_mark_quantity=my_mark,
        ))

    # Count active items
    item_count = len(items)

    # Determine permissions
    permissions = ["view"]
    if share_link.link_type == ShareLinkType.MARK:
        permissions.append("mark")

    return SharedWishlistResponse(
        wishlist=SharedWishlistInfo(
            id=wishlist.id,
            title=wishlist.name,
            description=wishlist.description,
            owner=owner_profile,
            item_count=item_count,
        ),
        items=items,
        permissions=permissions,
    )


@router.post(
    "/{token}/items/{item_id}/mark",
    response_model=MarkResponse,
    responses={
        400: {"description": "Invalid quantity"},
        403: {"description": "Cannot mark own wishlist or no permission"},
        404: {"description": "Share link or item not found"},
    },
)
async def mark_item(
    token: str,
    item_id: UUID,
    data: MarkCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MarkResponse:
    """Mark an item in a shared wishlist."""
    share_service = ShareService(db)
    mark_service = MarkService(db)

    share_link = await share_service.get_share_link_by_token(token)
    if share_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    if not share_service.is_link_valid(share_link):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link has expired",
        )

    # Check permission to mark
    if share_link.link_type != ShareLinkType.MARK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This share link does not allow marking",
        )

    wishlist = share_link.wishlist
    if wishlist.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Cannot mark own wishlist items
    if wishlist.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot mark items on your own wishlist",
        )

    # Find the item
    item = None
    for i in wishlist.items:
        if i.id == item_id and i.deleted_at is None:
            item = i
            break

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    try:
        my_qty, total_qty, available_qty = await mark_service.mark_item(
            item=item,
            user_id=current_user.id,
            quantity=data.quantity,
            owner_id=wishlist.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return MarkResponse(
        item_id=item_id,
        my_mark_quantity=my_qty,
        total_marked_quantity=total_qty,
        available_quantity=available_qty,
    )


@router.delete(
    "/{token}/items/{item_id}/mark",
    response_model=MarkResponse,
    responses={
        403: {"description": "Cannot unmark from own wishlist or no permission"},
        404: {"description": "Share link or item not found"},
    },
)
async def unmark_item(
    token: str,
    item_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MarkResponse:
    """Unmark an item in a shared wishlist."""
    share_service = ShareService(db)
    mark_service = MarkService(db)

    share_link = await share_service.get_share_link_by_token(token)
    if share_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    if not share_service.is_link_valid(share_link):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link has expired",
        )

    # Check permission to mark (unmark requires same permission)
    if share_link.link_type != ShareLinkType.MARK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This share link does not allow marking",
        )

    wishlist = share_link.wishlist
    if wishlist.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Cannot unmark own wishlist items
    if wishlist.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot unmark items on your own wishlist",
        )

    # Find the item
    item = None
    for i in wishlist.items:
        if i.id == item_id and i.deleted_at is None:
            item = i
            break

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    my_qty, total_qty, available_qty = await mark_service.unmark_item(
        item=item,
        user_id=current_user.id,
        owner_id=wishlist.user_id,
    )

    return MarkResponse(
        item_id=item_id,
        my_mark_quantity=my_qty,
        total_marked_quantity=total_qty,
        available_quantity=available_qty,
    )
