"""Wishlist management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.wishlist import (
    WishlistCreate,
    WishlistListResponse,
    WishlistResponse,
    WishlistUpdate,
)
from app.services.wishlist import WishlistService

router = APIRouter(prefix="/api/v1/wishlists", tags=["wishlists"])


@router.post(
    "",
    response_model=WishlistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_wishlist(
    data: WishlistCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WishlistResponse:
    """Create a new wishlist for the current user."""
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.create(current_user.id, data)
    return WishlistResponse.model_validate(wishlist)


@router.get("", response_model=WishlistListResponse)
async def list_wishlists(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WishlistListResponse:
    """List wishlists for the current user with pagination."""
    wishlist_service = WishlistService(db)
    wishlists, total = await wishlist_service.list_user_wishlists(
        current_user.id, limit, offset
    )

    return WishlistListResponse(
        wishlists=[WishlistResponse.model_validate(w) for w in wishlists],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{wishlist_id}",
    response_model=WishlistResponse,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to access this wishlist"},
    },
)
async def get_wishlist(
    wishlist_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WishlistResponse:
    """Get a wishlist by ID."""
    wishlist_service = WishlistService(db)
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

    return WishlistResponse.model_validate(wishlist)


@router.patch(
    "/{wishlist_id}",
    response_model=WishlistResponse,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to modify this wishlist"},
    },
)
async def update_wishlist(
    wishlist_id: UUID,
    data: WishlistUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WishlistResponse:
    """Update a wishlist."""
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)

    if wishlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if not wishlist_service.is_owner(wishlist, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this wishlist",
        )

    updated_wishlist = await wishlist_service.update(wishlist, data)
    return WishlistResponse.model_validate(updated_wishlist)


@router.delete(
    "/{wishlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to delete this wishlist"},
    },
)
async def delete_wishlist(
    wishlist_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete a wishlist."""
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)

    if wishlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if not wishlist_service.is_owner(wishlist, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this wishlist",
        )

    await wishlist_service.soft_delete(wishlist)
