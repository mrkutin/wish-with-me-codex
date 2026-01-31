"""Shared wishlist access endpoints (CouchDB-based)."""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.couchdb import CouchDBClient, DocumentNotFoundError, get_couchdb
from app.dependencies import CurrentUserCouchDB, OptionalCurrentUser
from app.schemas.share import (
    MarkCreate,
    MarkResponse,
    OwnerPublicProfile,
    SharedItemResponse,
    SharedWishlistBookmarkListResponse,
    SharedWishlistBookmarkResponse,
    SharedWishlistInfo,
    SharedWishlistPreview,
    SharedWishlistResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/shared", tags=["shared"])


async def get_db() -> CouchDBClient:
    """Get CouchDB client dependency."""
    return get_couchdb()


def extract_uuid(doc_id: str) -> UUID:
    """Extract UUID from CouchDB document ID (e.g., 'wishlist:uuid')."""
    if ":" in doc_id:
        return UUID(doc_id.split(":", 1)[1])
    return UUID(doc_id)


async def get_share_by_token(db: CouchDBClient, token: str) -> dict:
    """Get share document by token, validating it's active."""
    shares = await db.find({
        "type": "share",
        "token": token,
        "revoked": False,
    })

    if not shares:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or expired",
        )

    share = shares[0]

    # Check expiration
    if share.get("expires_at"):
        expires = datetime.fromisoformat(share["expires_at"])
        if expires < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share link has expired",
            )

    return share


async def grant_access_to_user(db: CouchDBClient, share: dict, user_id: str) -> None:
    """Grant a user access to the shared wishlist and its items."""
    # Add user to granted_users if not already there
    granted = share.get("granted_users", [])
    now = datetime.now(timezone.utc).isoformat()

    if user_id not in granted:
        granted.append(user_id)
        share["granted_users"] = granted
        share["access_count"] = share.get("access_count", 0) + 1
        share["updated_at"] = now
        await db.put(share)

        # Add user to wishlist and items access arrays
        await db.update_access_arrays(share["wishlist_id"], user_id, action="add")

    # Auto-create or update bookmark for "Shared with me" tab
    # Important: Only ONE bookmark per wishlist (not per share link)
    # Always use the LAST link's permissions (update share_id to current share)
    wishlist_id = share["wishlist_id"]

    # Find existing bookmark for this wishlist
    all_user_bookmarks = await db.find({
        "type": "bookmark",
        "user_id": user_id,
    })
    user_bookmarks = [b for b in all_user_bookmarks if not b.get("_deleted")]

    existing_bookmark = None
    for bookmark in user_bookmarks:
        try:
            bookmark_share = await db.get(bookmark["share_id"])
            if bookmark_share.get("wishlist_id") == wishlist_id:
                existing_bookmark = bookmark
                break
        except DocumentNotFoundError:
            # Share was deleted - check if bookmark has wishlist_id directly
            continue

    if existing_bookmark:
        # Update existing bookmark to use the LAST share link followed
        existing_bookmark["share_id"] = share["_id"]
        existing_bookmark["last_accessed_at"] = now
        await db.put(existing_bookmark)
        logger.info(f"Updated bookmark {existing_bookmark['_id']} to share {share['_id']}")
    else:
        # Create new bookmark
        bookmark_id = db.generate_id("bookmark")
        bookmark = {
            "_id": bookmark_id,
            "type": "bookmark",
            "user_id": user_id,
            "share_id": share["_id"],
            "created_at": now,
            "last_accessed_at": now,
            "access": [user_id],
        }
        await db.put(bookmark)
        logger.info(f"Created bookmark {bookmark_id} for share {share['_id']}")


# =============================================================================
# Bookmarks endpoint - MUST be defined BEFORE /{token} routes!
# =============================================================================

@router.get(
    "/bookmarks",
    response_model=SharedWishlistBookmarkListResponse,
)
async def list_bookmarks(
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> SharedWishlistBookmarkListResponse:
    """List all bookmarked shared wishlists for the current user."""
    user_id = current_user["_id"]
    logger.info(f"Fetching bookmarks for user: {user_id}")

    # Find all bookmarks for this user (filter _deleted in Python)
    all_bookmarks = await db.find({
        "type": "bookmark",
        "user_id": user_id,
    })
    bookmarks = [b for b in all_bookmarks if not b.get("_deleted")]
    logger.info(f"Found {len(bookmarks)} bookmarks for user {user_id}")

    items = []
    for bookmark in bookmarks:
        try:
            # Get the share document
            share = await db.get(bookmark["share_id"])
            if share.get("revoked") or share.get("_deleted"):
                continue

            # Check expiration
            if share.get("expires_at"):
                expires = datetime.fromisoformat(share["expires_at"])
                if expires < datetime.now(timezone.utc):
                    continue

            # Get wishlist
            wishlist = await db.get(share["wishlist_id"])
            if wishlist.get("_deleted"):
                continue

            # Get owner
            try:
                owner = await db.get(wishlist["owner_id"])
                owner_profile = OwnerPublicProfile(
                    id=extract_uuid(owner["_id"]),
                    name=owner.get("name", "Unknown"),
                    avatar_base64=owner.get("avatar_base64"),
                )
            except DocumentNotFoundError:
                owner_profile = OwnerPublicProfile(
                    id=extract_uuid(wishlist["owner_id"]),
                    name="Unknown",
                    avatar_base64=None,
                )

            # Count items (filter _deleted in Python)
            all_wishlist_items = await db.find({
                "type": "item",
                "wishlist_id": share["wishlist_id"],
            })
            wishlist_items = [i for i in all_wishlist_items if not i.get("_deleted")]

            items.append(SharedWishlistBookmarkResponse(
                id=extract_uuid(bookmark["_id"]),
                wishlist_id=extract_uuid(share["wishlist_id"]),
                share_token=share["token"],
                last_accessed_at=datetime.fromisoformat(bookmark.get("last_accessed_at", bookmark["created_at"])),
                wishlist=SharedWishlistInfo(
                    id=extract_uuid(wishlist["_id"]),
                    title=wishlist.get("title", ""),
                    description=wishlist.get("description"),
                    icon=wishlist.get("icon", "card_giftcard"),
                    owner=owner_profile,
                    item_count=len(wishlist_items),
                ),
            ))
        except DocumentNotFoundError:
            # Share or wishlist was deleted, skip this bookmark
            continue

    return SharedWishlistBookmarkListResponse(items=items)


# =============================================================================
# Token-based routes
# =============================================================================

@router.get(
    "/{token}/preview",
    response_model=SharedWishlistPreview,
)
async def preview_shared_wishlist(
    token: str,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> SharedWishlistPreview:
    """Preview a shared wishlist (no authentication required)."""
    share = await get_share_by_token(db, token)

    # Get wishlist
    try:
        wishlist = await db.get(share["wishlist_id"])
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Get owner info
    try:
        owner = await db.get(wishlist["owner_id"])
        # Show only first name for privacy
        owner_name = owner.get("name", "Someone").split()[0]
    except DocumentNotFoundError:
        owner_name = "Someone"

    # Count items
    all_items = await db.find({
        "type": "item",
        "wishlist_id": share["wishlist_id"],
    })
    items = [i for i in all_items if not i.get("_deleted")]

    return SharedWishlistPreview(
        wishlist={
            "title": wishlist.get("title", "Wishlist"),
            "owner_name": owner_name,
            "item_count": len(items),
        },
        requires_auth=True,
        auth_redirect=f"/login?share_token={token}",
    )


@router.get(
    "/{token}",
    response_model=SharedWishlistResponse,
)
async def get_shared_wishlist(
    token: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> SharedWishlistResponse:
    """Access a shared wishlist (authentication required)."""
    user_id = current_user["_id"]
    share = await get_share_by_token(db, token)

    # Grant access to user if not already granted
    await grant_access_to_user(db, share, user_id)

    # Get wishlist
    try:
        wishlist = await db.get(share["wishlist_id"])
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Get owner info
    try:
        owner = await db.get(wishlist["owner_id"])
        owner_profile = OwnerPublicProfile(
            id=extract_uuid(owner["_id"]),
            name=owner.get("name", "Unknown"),
            avatar_base64=owner.get("avatar_base64"),
        )
    except DocumentNotFoundError:
        owner_profile = OwnerPublicProfile(
            id=extract_uuid(wishlist["owner_id"]),
            name="Unknown",
            avatar_base64=None,
        )

    # Get items
    logger.info(f"Fetching items for wishlist_id: {share['wishlist_id']}")
    all_items = await db.find({
        "type": "item",
        "wishlist_id": share["wishlist_id"],
    })
    logger.info(f"Found {len(all_items)} total items for wishlist {share['wishlist_id']}")
    # Filter out deleted items in Python (CouchDB Mango can be unreliable with _deleted)
    items = [item for item in all_items if not item.get("_deleted")]
    logger.info(f"After filtering deleted: {len(items)} items")

    # Get all marks for these items
    item_ids = [item["_id"] for item in items]
    all_marks = await db.find({
        "type": "mark",
        "item_id": {"$in": item_ids},
    }) if item_ids else []
    marks = [m for m in all_marks if not m.get("_deleted")]

    # Build marks lookup: item_id -> list of marks
    marks_by_item: dict[str, list[dict]] = {}
    for mark in marks:
        item_id = mark["item_id"]
        if item_id not in marks_by_item:
            marks_by_item[item_id] = []
        marks_by_item[item_id].append(mark)

    # Build item responses
    item_responses = []
    for item in items:
        item_marks = marks_by_item.get(item["_id"], [])
        total_marked = sum(m.get("quantity", 1) for m in item_marks)
        my_marked = sum(
            m.get("quantity", 1) for m in item_marks
            if m.get("marked_by") == user_id
        )
        quantity = item.get("quantity", 1)

        item_responses.append(SharedItemResponse(
            id=extract_uuid(item["_id"]),
            title=item.get("title", ""),
            description=item.get("description"),
            price_amount=str(item["price"]) if item.get("price") else None,
            price_currency=item.get("currency"),
            image_base64=item.get("image_base64"),
            quantity=quantity,
            marked_quantity=total_marked,
            available_quantity=max(0, quantity - total_marked),
            my_mark_quantity=my_marked,
        ))

    # Determine permissions based on link type
    permissions = ["view"]
    if share.get("link_type") == "mark":
        permissions.append("mark")

    return SharedWishlistResponse(
        wishlist=SharedWishlistInfo(
            id=extract_uuid(wishlist["_id"]),
            title=wishlist.get("title", ""),
            description=wishlist.get("description"),
            icon=wishlist.get("icon", "card_giftcard"),
            owner=owner_profile,
            item_count=len(items),
        ),
        items=item_responses,
        permissions=permissions,
    )


@router.post(
    "/{token}/items/{item_id}/mark",
    response_model=MarkResponse,
    responses={
        403: {"description": "No permission to mark items"},
        404: {"description": "Item not found"},
        409: {"description": "Not enough available quantity"},
    },
)
async def mark_item(
    token: str,
    item_id: UUID,
    data: MarkCreate,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> MarkResponse:
    """Mark an item as taken/reserved."""
    user_id = current_user["_id"]
    share = await get_share_by_token(db, token)

    # Check permission
    if share.get("link_type") != "mark":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This share link doesn't allow marking items",
        )

    # Get item
    item_doc_id = f"item:{item_id}"
    try:
        item = await db.get(item_doc_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    # Verify item belongs to the shared wishlist
    if item.get("wishlist_id") != share["wishlist_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in this wishlist",
        )

    # Get wishlist for access array
    wishlist = await db.get(share["wishlist_id"])
    owner_id = wishlist.get("owner_id")

    # Get existing marks for this item (filter _deleted in Python)
    all_marks = await db.find({
        "type": "mark",
        "item_id": item_doc_id,
    })
    marks = [m for m in all_marks if not m.get("_deleted")]

    total_marked = sum(m.get("quantity", 1) for m in marks)
    my_existing_mark = next(
        (m for m in marks if m.get("marked_by") == user_id),
        None
    )
    my_marked = my_existing_mark.get("quantity", 0) if my_existing_mark else 0

    quantity = item.get("quantity", 1)
    available = quantity - total_marked

    # Check if enough available
    if data.quantity > available + my_marked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {available} items available",
        )

    # Update or create mark
    new_my_quantity = my_marked + data.quantity
    if new_my_quantity > quantity:
        new_my_quantity = quantity

    if my_existing_mark:
        # Update existing mark
        my_existing_mark["quantity"] = new_my_quantity
        my_existing_mark["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.put(my_existing_mark)
    else:
        # Create new mark - access excludes owner (surprise mode)
        mark_access = [
            uid for uid in wishlist.get("access", [])
            if uid != owner_id
        ]
        await db.create_mark(
            item_id=item_doc_id,
            wishlist_id=share["wishlist_id"],
            owner_id=owner_id,
            marked_by=user_id,
            quantity=data.quantity,
            viewer_access=mark_access,
        )

    # Recalculate totals
    new_total_marked = total_marked - my_marked + new_my_quantity
    new_available = quantity - new_total_marked

    return MarkResponse(
        item_id=item_id,
        my_mark_quantity=new_my_quantity,
        total_marked_quantity=new_total_marked,
        available_quantity=max(0, new_available),
    )


@router.delete(
    "/{token}/items/{item_id}/mark",
    response_model=MarkResponse,
    responses={
        404: {"description": "Item or mark not found"},
    },
)
async def unmark_item(
    token: str,
    item_id: UUID,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> MarkResponse:
    """Remove mark from an item."""
    user_id = current_user["_id"]
    share = await get_share_by_token(db, token)

    # Get item
    item_doc_id = f"item:{item_id}"
    try:
        item = await db.get(item_doc_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    # Verify item belongs to the shared wishlist
    if item.get("wishlist_id") != share["wishlist_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in this wishlist",
        )

    # Get existing marks for this item (filter _deleted in Python)
    all_marks = await db.find({
        "type": "mark",
        "item_id": item_doc_id,
    })
    marks = [m for m in all_marks if not m.get("_deleted")]

    my_mark = next(
        (m for m in marks if m.get("marked_by") == user_id),
        None
    )

    if not my_mark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You haven't marked this item",
        )

    # Soft delete the mark
    my_mark["_deleted"] = True
    my_mark["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.put(my_mark)

    # Recalculate totals
    total_marked = sum(m.get("quantity", 1) for m in marks if m["_id"] != my_mark["_id"])
    quantity = item.get("quantity", 1)

    return MarkResponse(
        item_id=item_id,
        my_mark_quantity=0,
        total_marked_quantity=total_marked,
        available_quantity=max(0, quantity - total_marked),
    )


# =============================================================================
# Additional bookmark management endpoints
# =============================================================================

@router.post(
    "/{token}/bookmark",
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark(
    token: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> dict:
    """Bookmark a shared wishlist."""
    user_id = current_user["_id"]
    share = await get_share_by_token(db, token)

    # Check if bookmark already exists (filter _deleted in Python)
    all_existing = await db.find({
        "type": "bookmark",
        "user_id": user_id,
        "share_id": share["_id"],
    })
    existing = [b for b in all_existing if not b.get("_deleted")]

    if existing:
        # Update last_accessed_at
        bookmark = existing[0]
        bookmark["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
        await db.put(bookmark)
        return {"message": "Bookmark updated"}

    # Create new bookmark
    now = datetime.now(timezone.utc).isoformat()
    bookmark_id = db.generate_id("bookmark")
    bookmark = {
        "_id": bookmark_id,
        "type": "bookmark",
        "user_id": user_id,
        "share_id": share["_id"],
        "created_at": now,
        "last_accessed_at": now,
        "access": [user_id],  # Only this user can see their bookmark
    }
    await db.put(bookmark)

    return {"message": "Bookmark created"}


@router.delete(
    "/{token}/bookmark",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_bookmark(
    token: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> None:
    """Remove a bookmark."""
    user_id = current_user["_id"]
    share = await get_share_by_token(db, token)

    # Find the bookmark (filter _deleted in Python)
    all_bookmarks = await db.find({
        "type": "bookmark",
        "user_id": user_id,
        "share_id": share["_id"],
    })
    bookmarks = [b for b in all_bookmarks if not b.get("_deleted")]

    if not bookmarks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found",
        )

    # Soft delete
    bookmark = bookmarks[0]
    bookmark["_deleted"] = True
    bookmark["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.put(bookmark)
