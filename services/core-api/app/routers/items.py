"""Item management endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.item_resolver import ItemResolverClient, ItemResolverError
from app.database import async_session_maker, get_db
from app.dependencies import CurrentUser
from app.models.wishlist import Wishlist
from app.schemas.item import (
    ItemCreate,
    ItemListResponse,
    ItemResponse,
    ItemUpdate,
)
from app.services.events import publish_item_resolved
from app.services.item import ItemService
from app.services.wishlist import WishlistService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["items"])


async def get_owned_wishlist(
    wishlist_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Wishlist:
    """Dependency to validate wishlist ownership.

    Raises:
        HTTPException: 404 if wishlist not found, 403 if not authorized.

    Returns:
        Wishlist if user owns it.
    """
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

    return wishlist


@router.post(
    "/api/v1/wishlists/{wishlist_id}/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to modify this wishlist"},
    },
)
async def create_item(
    data: ItemCreate,
    wishlist: Annotated[Wishlist, Depends(get_owned_wishlist)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> ItemResponse:
    """Create a new item in a wishlist.

    If source_url is provided, automatically triggers resolution in the background.
    """
    item_service = ItemService(db)
    item = await item_service.create(wishlist.id, data)

    # Explicitly commit the transaction before scheduling background task
    # This ensures the item is visible to the background task's new session
    await db.commit()

    # Automatically trigger resolution if source_url is provided
    if item.source_url:
        background_tasks.add_task(
            resolve_item_background,
            item_id=item.id,
            source_url=item.source_url,
            session_maker=async_session_maker,
        )

    return ItemResponse.model_validate(item)


@router.get(
    "/api/v1/wishlists/{wishlist_id}/items",
    response_model=ItemListResponse,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized to access this wishlist"},
    },
)
async def list_items(
    wishlist: Annotated[Wishlist, Depends(get_owned_wishlist)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ItemListResponse:
    """List items in a wishlist with pagination."""
    item_service = ItemService(db)
    items, total = await item_service.list_wishlist_items(
        wishlist.id, limit, offset
    )

    return ItemListResponse(
        items=[ItemResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/v1/wishlists/{wishlist_id}/items/{item_id}",
    response_model=ItemResponse,
    responses={
        404: {"description": "Wishlist or item not found"},
        403: {"description": "Not authorized to access this wishlist"},
    },
)
async def get_item(
    item_id: UUID,
    wishlist: Annotated[Wishlist, Depends(get_owned_wishlist)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    """Get an item by ID."""
    item_service = ItemService(db)
    item = await item_service.get_by_id(item_id)

    if item is None or item.wishlist_id != wishlist.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return ItemResponse.model_validate(item)


@router.patch(
    "/api/v1/wishlists/{wishlist_id}/items/{item_id}",
    response_model=ItemResponse,
    responses={
        404: {"description": "Wishlist or item not found"},
        403: {"description": "Not authorized to modify this wishlist"},
    },
)
async def update_item(
    item_id: UUID,
    data: ItemUpdate,
    wishlist: Annotated[Wishlist, Depends(get_owned_wishlist)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    """Update an item."""
    item_service = ItemService(db)
    item = await item_service.get_by_id(item_id)

    if item is None or item.wishlist_id != wishlist.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    updated_item = await item_service.update(item, data)
    return ItemResponse.model_validate(updated_item)


@router.delete(
    "/api/v1/wishlists/{wishlist_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Wishlist or item not found"},
        403: {"description": "Not authorized to modify this wishlist"},
    },
)
async def delete_item(
    item_id: UUID,
    wishlist: Annotated[Wishlist, Depends(get_owned_wishlist)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete an item."""
    item_service = ItemService(db)
    item = await item_service.get_by_id(item_id)

    if item is None or item.wishlist_id != wishlist.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    await item_service.soft_delete(item)


async def resolve_item_background(
    item_id: UUID,
    source_url: str,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Background task to resolve item metadata from URL.

    Args:
        item_id: ID of the item to resolve
        source_url: URL to resolve
        session_maker: Async session maker for database access
    """
    resolver = ItemResolverClient()
    wishlist = None  # Initialize for exception handler scope

    async with session_maker() as session:
        try:
            item_service = ItemService(session)
            wishlist_service = WishlistService(session)
            item = await item_service.get_by_id(item_id)

            if item is None:
                logger.error(f"Item {item_id} not found for resolution")
                return

            # Get wishlist to know who to notify
            wishlist = await wishlist_service.get_by_id(item.wishlist_id)
            if wishlist is None:
                logger.error(f"Wishlist {item.wishlist_id} not found for item {item_id}")
                return

            # Mark as resolving
            await item_service.mark_resolving(item)
            await session.commit()

            # Call resolver service
            logger.info(f"Resolving item {item_id} from URL: {source_url}")
            resolver_data = await resolver.resolve_item(source_url)

            # Update item with resolved data
            await item_service.update_from_resolver(item, resolver_data)
            await session.commit()

            # Refresh to get latest state after commit (may expire attributes)
            await session.refresh(item)
            logger.info(f"Successfully resolved item {item_id}")

            # Publish SSE event to notify user
            await publish_item_resolved(
                user_id=wishlist.user_id,
                item_id=item.id,
                wishlist_id=item.wishlist_id,
                status=item.status.value if hasattr(item.status, 'value') else item.status,
                title=item.title,
            )

        except ItemResolverError as e:
            logger.error(f"Failed to resolve item {item_id}: {str(e)}")
            await item_service.mark_resolver_failed(item, str(e))
            await session.commit()

            # Notify about failure via SSE
            if wishlist:
                await publish_item_resolved(
                    user_id=wishlist.user_id,
                    item_id=item.id,
                    wishlist_id=item.wishlist_id,
                    status="failed",
                    title=item.title,
                )

        except Exception as e:
            logger.exception(f"Unexpected error resolving item {item_id}: {str(e)}")
            await item_service.mark_resolver_failed(
                item, f"Unexpected error: {str(e)}"
            )
            await session.commit()

            # Notify about failure via SSE
            if wishlist:
                await publish_item_resolved(
                    user_id=wishlist.user_id,
                    item_id=item.id,
                    wishlist_id=item.wishlist_id,
                    status="failed",
                    title=item.title,
                )


@router.post(
    "/api/v1/wishlists/{wishlist_id}/items/{item_id}/resolve",
    response_model=ItemResponse,
    responses={
        404: {"description": "Wishlist or item not found"},
        403: {"description": "Not authorized to modify this wishlist"},
        400: {"description": "Item has no source URL"},
    },
)
async def resolve_item(
    item_id: UUID,
    wishlist: Annotated[Wishlist, Depends(get_owned_wishlist)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> ItemResponse:
    """Trigger or retry resolution of an item from its source URL.

    This endpoint starts a background task to resolve item metadata.
    The item status will be updated to 'resolving', then either 'resolved' or 'failed'.
    """
    item_service = ItemService(db)
    item = await item_service.get_by_id(item_id)

    if item is None or item.wishlist_id != wishlist.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if not item.source_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item has no source URL to resolve",
        )

    # Add background task for resolution
    background_tasks.add_task(
        resolve_item_background,
        item_id=item.id,
        source_url=item.source_url,
        session_maker=async_session_maker,
    )

    return ItemResponse.model_validate(item)
