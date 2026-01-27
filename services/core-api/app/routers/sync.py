"""Sync endpoints for RxDB replication."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, get_db
from app.dependencies import CurrentUser
from app.models.item import Item, ItemStatus
from app.models.mark import Mark
from app.models.wishlist import Wishlist
from app.routers.items import resolve_item_background
from app.schemas.sync import (
    ConflictDocument,
    PullResponse,
    PushRequest,
    PushResponse,
    SyncCheckpoint,
)
from app.services.events import (
    publish_item_updated,
    publish_marks_updated_to_many,
    publish_wishlist_updated,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

CollectionType = Literal["wishlists", "items", "marks"]


def _wishlist_to_sync_doc(wishlist: Wishlist) -> dict:
    """Convert wishlist model to sync document."""
    return {
        "id": str(wishlist.id),
        "user_id": str(wishlist.user_id),
        "name": wishlist.name,
        "description": wishlist.description,
        "is_public": wishlist.is_public,
        "icon": wishlist.icon,
        "created_at": wishlist.created_at.isoformat(),
        "updated_at": wishlist.updated_at.isoformat(),
        "_deleted": wishlist.deleted_at is not None,
    }


def _item_to_sync_doc(item: Item) -> dict:
    """Convert item model to sync document."""
    return {
        "id": str(item.id),
        "wishlist_id": str(item.wishlist_id),
        "title": item.title,
        "description": item.description,
        "price": str(item.price) if item.price else None,
        "currency": item.currency,
        "quantity": item.quantity,
        "source_url": item.source_url,
        "image_url": item.image_url,
        "image_base64": item.image_base64,
        "status": item.status.value,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "_deleted": item.deleted_at is not None,
    }


def _mark_to_sync_doc(mark: Mark, deleted: bool = False) -> dict:
    """Convert mark model to sync document."""
    return {
        "id": str(mark.id),
        "item_id": str(mark.item_id),
        "user_id": str(mark.user_id),
        "quantity": mark.quantity,
        "created_at": mark.created_at.isoformat(),
        "updated_at": mark.updated_at.isoformat(),
        "_deleted": deleted,
    }


@router.get(
    "/pull/{collection}",
    response_model=PullResponse,
)
async def pull_collection(
    collection: CollectionType,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    checkpoint_updated_at: Annotated[datetime | None, Query()] = None,
    checkpoint_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PullResponse:
    """Pull changes from server for RxDB replication.

    Uses checkpoint-based pagination for efficient sync.
    Returns documents updated after the checkpoint.
    """
    if collection == "wishlists":
        return await _pull_wishlists(
            db=db,
            user_id=current_user.id,
            checkpoint_updated_at=checkpoint_updated_at,
            checkpoint_id=checkpoint_id,
            limit=limit,
        )
    elif collection == "items":
        return await _pull_items(
            db=db,
            user_id=current_user.id,
            checkpoint_updated_at=checkpoint_updated_at,
            checkpoint_id=checkpoint_id,
            limit=limit,
        )
    elif collection == "marks":
        return await _pull_marks(
            db=db,
            user_id=current_user.id,
            checkpoint_updated_at=checkpoint_updated_at,
            checkpoint_id=checkpoint_id,
            limit=limit,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown collection: {collection}",
        )


async def _pull_wishlists(
    db: AsyncSession,
    user_id: UUID,
    checkpoint_updated_at: datetime | None,
    checkpoint_id: UUID | None,
    limit: int,
) -> PullResponse:
    """Pull wishlist changes."""
    query = select(Wishlist).where(Wishlist.user_id == user_id)

    # Apply checkpoint filter for pagination
    if checkpoint_updated_at and checkpoint_id:
        # Get documents updated after checkpoint or same time but with larger ID
        query = query.where(
            (Wishlist.updated_at > checkpoint_updated_at)
            | ((Wishlist.updated_at == checkpoint_updated_at) & (Wishlist.id > checkpoint_id))
        )
    elif checkpoint_updated_at:
        query = query.where(Wishlist.updated_at > checkpoint_updated_at)

    # Order by updated_at, then id for consistent pagination
    query = query.order_by(Wishlist.updated_at, Wishlist.id).limit(limit)

    result = await db.execute(query)
    wishlists = result.scalars().all()

    documents = [_wishlist_to_sync_doc(w) for w in wishlists]

    # Build checkpoint from last document
    checkpoint = None
    if wishlists:
        last = wishlists[-1]
        checkpoint = SyncCheckpoint(updated_at=last.updated_at, id=last.id)

    return PullResponse(documents=documents, checkpoint=checkpoint)


async def _pull_items(
    db: AsyncSession,
    user_id: UUID,
    checkpoint_updated_at: datetime | None,
    checkpoint_id: UUID | None,
    limit: int,
) -> PullResponse:
    """Pull item changes for user's wishlists."""
    # Get items from user's wishlists
    query = (
        select(Item)
        .join(Wishlist, Item.wishlist_id == Wishlist.id)
        .where(Wishlist.user_id == user_id)
    )

    # Apply checkpoint filter
    if checkpoint_updated_at and checkpoint_id:
        query = query.where(
            (Item.updated_at > checkpoint_updated_at)
            | ((Item.updated_at == checkpoint_updated_at) & (Item.id > checkpoint_id))
        )
    elif checkpoint_updated_at:
        query = query.where(Item.updated_at > checkpoint_updated_at)

    query = query.order_by(Item.updated_at, Item.id).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()

    documents = [_item_to_sync_doc(i) for i in items]

    checkpoint = None
    if items:
        last = items[-1]
        checkpoint = SyncCheckpoint(updated_at=last.updated_at, id=last.id)

    return PullResponse(documents=documents, checkpoint=checkpoint)


async def _pull_marks(
    db: AsyncSession,
    user_id: UUID,
    checkpoint_updated_at: datetime | None,
    checkpoint_id: UUID | None,
    limit: int,
) -> PullResponse:
    """Pull mark changes for the current user."""
    # Get marks created by this user
    query = select(Mark).where(Mark.user_id == user_id)

    # Apply checkpoint filter
    if checkpoint_updated_at and checkpoint_id:
        query = query.where(
            (Mark.updated_at > checkpoint_updated_at)
            | ((Mark.updated_at == checkpoint_updated_at) & (Mark.id > checkpoint_id))
        )
    elif checkpoint_updated_at:
        query = query.where(Mark.updated_at > checkpoint_updated_at)

    query = query.order_by(Mark.updated_at, Mark.id).limit(limit)

    result = await db.execute(query)
    marks = result.scalars().all()

    documents = [_mark_to_sync_doc(m) for m in marks]

    checkpoint = None
    if marks:
        last = marks[-1]
        checkpoint = SyncCheckpoint(updated_at=last.updated_at, id=last.id)

    return PullResponse(documents=documents, checkpoint=checkpoint)


@router.post(
    "/push/{collection}",
    response_model=PushResponse,
)
async def push_collection(
    collection: CollectionType,
    data: PushRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> PushResponse:
    """Push changes to server for RxDB replication.

    Uses Last-Write-Wins (LWW) conflict resolution based on updated_at.
    Returns conflicts if server has newer versions.
    """
    if collection == "wishlists":
        return await _push_wishlists(
            db=db,
            user_id=current_user.id,
            documents=data.documents,
        )
    elif collection == "items":
        return await _push_items(
            db=db,
            user_id=current_user.id,
            documents=data.documents,
            background_tasks=background_tasks,
        )
    elif collection == "marks":
        return await _push_marks(
            db=db,
            user_id=current_user.id,
            documents=data.documents,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown collection: {collection}",
        )


async def _push_wishlists(
    db: AsyncSession,
    user_id: UUID,
    documents: list[dict],
) -> PushResponse:
    """Push wishlist changes with LWW conflict resolution."""
    conflicts: list[ConflictDocument] = []
    updated_wishlist_ids: list[UUID] = []  # Track successful updates for SSE

    for doc in documents:
        try:
            doc_id = UUID(doc["id"])
            client_updated_at = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))

            # Find existing wishlist
            result = await db.execute(
                select(Wishlist).where(
                    Wishlist.id == doc_id,
                    Wishlist.user_id == user_id,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # LWW: Check if client version is newer
                if client_updated_at > existing.updated_at:
                    # Client wins - apply changes
                    if doc.get("_deleted"):
                        existing.deleted_at = datetime.now(timezone.utc)
                    else:
                        existing.name = doc["name"]
                        existing.description = doc.get("description")
                        existing.is_public = doc.get("is_public", False)
                        existing.icon = doc.get("icon", "card_giftcard")
                    existing.updated_at = client_updated_at
                    updated_wishlist_ids.append(doc_id)
                else:
                    # Server wins - return conflict
                    conflicts.append(
                        ConflictDocument(
                            document_id=doc_id,
                            error="Server has newer version",
                            server_document=_wishlist_to_sync_doc(existing),
                        )
                    )
            else:
                # New wishlist - only create if not deleted
                if not doc.get("_deleted"):
                    created_at = datetime.fromisoformat(
                        doc["created_at"].replace("Z", "+00:00")
                    )

                    # Use PostgreSQL upsert to handle concurrent inserts
                    stmt = pg_insert(Wishlist).values(
                        id=doc_id,
                        user_id=user_id,
                        name=doc["name"],
                        description=doc.get("description"),
                        is_public=doc.get("is_public", False),
                        icon=doc.get("icon", "card_giftcard"),
                        created_at=created_at,
                        updated_at=client_updated_at,
                    ).on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "name": doc["name"],
                            "description": doc.get("description"),
                            "is_public": doc.get("is_public", False),
                            "icon": doc.get("icon", "card_giftcard"),
                            "updated_at": client_updated_at,
                        },
                        where=Wishlist.updated_at < client_updated_at,
                    )
                    await db.execute(stmt)
                    updated_wishlist_ids.append(doc_id)

        except (KeyError, ValueError) as e:
            logger.warning(f"Invalid sync document: {e}")
            conflicts.append(
                ConflictDocument(
                    document_id=UUID(doc.get("id", "00000000-0000-0000-0000-000000000000")),
                    error=f"Invalid document: {str(e)}",
                )
            )

    await db.commit()

    # Publish SSE events for successful updates (for multi-tab/device sync)
    for wishlist_id in updated_wishlist_ids:
        await publish_wishlist_updated(user_id, wishlist_id)

    return PushResponse(conflicts=conflicts)


async def _push_items(
    db: AsyncSession,
    user_id: UUID,
    documents: list[dict],
    background_tasks: BackgroundTasks,
) -> PushResponse:
    """Push item changes with LWW conflict resolution.

    Automatically triggers resolution for new items with source_url.
    """
    conflicts: list[ConflictDocument] = []
    items_to_resolve: list[tuple[UUID, str]] = []  # (item_id, source_url)
    updated_items: list[tuple[UUID, UUID]] = []  # (item_id, wishlist_id) for SSE

    # Get user's wishlist IDs for authorization
    wishlist_result = await db.execute(
        select(Wishlist.id).where(Wishlist.user_id == user_id)
    )
    user_wishlist_ids = {row[0] for row in wishlist_result.fetchall()}

    for doc in documents:
        try:
            doc_id = UUID(doc["id"])
            wishlist_id = UUID(doc["wishlist_id"])
            client_updated_at = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))

            # Authorization check
            if wishlist_id not in user_wishlist_ids:
                conflicts.append(
                    ConflictDocument(
                        document_id=doc_id,
                        error="Unauthorized: wishlist not owned by user",
                    )
                )
                continue

            # Find existing item
            result = await db.execute(
                select(Item).where(Item.id == doc_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Verify ownership
                if existing.wishlist_id not in user_wishlist_ids:
                    conflicts.append(
                        ConflictDocument(
                            document_id=doc_id,
                            error="Unauthorized: item not in user's wishlist",
                        )
                    )
                    continue

                # LWW: Check if client version is newer
                if client_updated_at > existing.updated_at:
                    if doc.get("_deleted"):
                        existing.deleted_at = datetime.now(timezone.utc)
                    else:
                        existing.title = doc["title"]
                        existing.description = doc.get("description")
                        if doc.get("price"):
                            existing.price = Decimal(doc["price"])
                        else:
                            existing.price = None
                        existing.currency = doc.get("currency")
                        existing.quantity = doc.get("quantity", 1)
                        existing.source_url = doc.get("source_url")
                        existing.image_url = doc.get("image_url")
                        existing.image_base64 = doc.get("image_base64")
                    existing.updated_at = client_updated_at
                    updated_items.append((doc_id, wishlist_id))
                else:
                    conflicts.append(
                        ConflictDocument(
                            document_id=doc_id,
                            error="Server has newer version",
                            server_document=_item_to_sync_doc(existing),
                        )
                    )
            else:
                # New item - only create if not deleted
                if not doc.get("_deleted"):
                    source_url = doc.get("source_url")
                    created_at = datetime.fromisoformat(
                        doc["created_at"].replace("Z", "+00:00")
                    )

                    # Use PostgreSQL upsert to handle concurrent inserts
                    # ON CONFLICT DO UPDATE only if client version is newer (LWW)
                    stmt = pg_insert(Item).values(
                        id=doc_id,
                        wishlist_id=wishlist_id,
                        title=doc["title"],
                        description=doc.get("description"),
                        price=Decimal(doc["price"]) if doc.get("price") else None,
                        currency=doc.get("currency"),
                        quantity=doc.get("quantity", 1),
                        source_url=source_url,
                        image_url=doc.get("image_url"),
                        image_base64=doc.get("image_base64"),
                        status=ItemStatus.PENDING if source_url else ItemStatus.RESOLVED,
                        created_at=created_at,
                        updated_at=client_updated_at,
                    ).on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "title": doc["title"],
                            "description": doc.get("description"),
                            "price": Decimal(doc["price"]) if doc.get("price") else None,
                            "currency": doc.get("currency"),
                            "quantity": doc.get("quantity", 1),
                            "source_url": source_url,
                            "image_url": doc.get("image_url"),
                            "image_base64": doc.get("image_base64"),
                            "updated_at": client_updated_at,
                        },
                        # Only update if client is newer (LWW)
                        where=Item.updated_at < client_updated_at,
                    )
                    try:
                        await db.execute(stmt)
                        updated_items.append((doc_id, wishlist_id))

                        # Track items that need resolution
                        if source_url:
                            items_to_resolve.append((doc_id, source_url))
                    except IntegrityError as e:
                        # Handle unique constraint violations (e.g., duplicate title in wishlist)
                        await db.rollback()
                        logger.warning(f"Item sync integrity error for {doc_id}: {e}")
                        conflicts.append(
                            ConflictDocument(
                                document_id=doc_id,
                                error="Duplicate item or constraint violation",
                            )
                        )

        except (KeyError, ValueError) as e:
            logger.warning(f"Invalid sync document: {e}")
            conflicts.append(
                ConflictDocument(
                    document_id=UUID(doc.get("id", "00000000-0000-0000-0000-000000000000")),
                    error=f"Invalid document: {str(e)}",
                )
            )

    await db.commit()

    # Publish SSE events for successful updates (for multi-tab/device sync)
    # Skip items that will be resolved (they'll get SSE events after resolution)
    items_to_resolve_ids = {item_id for item_id, _ in items_to_resolve}
    for item_id, wishlist_id in updated_items:
        if item_id not in items_to_resolve_ids:
            await publish_item_updated(user_id, item_id, wishlist_id)

    # Trigger resolution for new items with URLs (after commit so items exist)
    for item_id, source_url in items_to_resolve:
        logger.info(f"Scheduling resolution for synced item {item_id}")
        background_tasks.add_task(
            resolve_item_background,
            item_id=item_id,
            source_url=source_url,
            session_maker=async_session_maker,
        )

    return PushResponse(conflicts=conflicts)


async def _push_marks(
    db: AsyncSession,
    user_id: UUID,
    documents: list[dict],
) -> PushResponse:
    """Push mark changes with LWW conflict resolution."""
    conflicts: list[ConflictDocument] = []
    updated_mark_item_ids: list[UUID] = []  # Track item IDs for SSE

    for doc in documents:
        try:
            doc_id = UUID(doc["id"])
            item_id = UUID(doc["item_id"])
            client_updated_at = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))

            # Find existing mark
            result = await db.execute(
                select(Mark).where(Mark.id == doc_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Verify ownership - only the mark creator can modify
                if existing.user_id != user_id:
                    conflicts.append(
                        ConflictDocument(
                            document_id=doc_id,
                            error="Unauthorized: mark not owned by user",
                        )
                    )
                    continue

                # LWW: Check if client version is newer
                if client_updated_at > existing.updated_at:
                    if doc.get("_deleted"):
                        # Delete the mark
                        await db.delete(existing)
                    else:
                        existing.quantity = doc.get("quantity", 1)
                        existing.updated_at = client_updated_at
                    updated_mark_item_ids.append(item_id)
                else:
                    conflicts.append(
                        ConflictDocument(
                            document_id=doc_id,
                            error="Server has newer version",
                            server_document=_mark_to_sync_doc(existing),
                        )
                    )
            else:
                # New mark - only create if not deleted
                if not doc.get("_deleted"):
                    created_at = datetime.fromisoformat(
                        doc["created_at"].replace("Z", "+00:00")
                    )

                    # Use PostgreSQL upsert to handle concurrent inserts
                    stmt = pg_insert(Mark).values(
                        id=doc_id,
                        item_id=item_id,
                        user_id=user_id,
                        quantity=doc.get("quantity", 1),
                        created_at=created_at,
                        updated_at=client_updated_at,
                    ).on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "quantity": doc.get("quantity", 1),
                            "updated_at": client_updated_at,
                        },
                        where=Mark.updated_at < client_updated_at,
                    )
                    await db.execute(stmt)
                    updated_mark_item_ids.append(item_id)

        except (KeyError, ValueError) as e:
            logger.warning(f"Invalid sync document: {e}")
            conflicts.append(
                ConflictDocument(
                    document_id=UUID(doc.get("id", "00000000-0000-0000-0000-000000000000")),
                    error=f"Invalid document: {str(e)}",
                )
            )

    await db.commit()

    # Publish SSE events to all users who have access to affected wishlists
    for mark_item_id in set(updated_mark_item_ids):  # Deduplicate
        # Get the item's wishlist and find all users to notify
        item_result = await db.execute(
            select(Item.wishlist_id).where(Item.id == mark_item_id)
        )
        wishlist_id = item_result.scalar_one_or_none()
        if not wishlist_id:
            continue

        # Get wishlist owner
        wishlist_result = await db.execute(
            select(Wishlist.user_id).where(Wishlist.id == wishlist_id)
        )
        owner_id = wishlist_result.scalar_one_or_none()

        # Get all users who have marks on items in this wishlist
        marks_result = await db.execute(
            select(Mark.user_id)
            .join(Item, Mark.item_id == Item.id)
            .where(Item.wishlist_id == wishlist_id)
            .distinct()
        )
        mark_user_ids = [row[0] for row in marks_result.fetchall()]

        # Combine owner + mark users, deduplicate
        all_user_ids = list(set([owner_id] + mark_user_ids) if owner_id else set(mark_user_ids))

        if all_user_ids:
            await publish_marks_updated_to_many(all_user_ids, mark_item_id)

    return PushResponse(conflicts=conflicts)
