"""Shared wishlist access endpoints (CouchDB-based).

Note: Most shared wishlist operations are now handled via PouchDB sync.
This router only contains the grant-access endpoint for establishing permissions.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.couchdb import CouchDBClient, DocumentNotFoundError, get_couchdb
from app.dependencies import CurrentUserCouchDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/shared", tags=["shared"])


async def get_db() -> CouchDBClient:
    """Get CouchDB client dependency."""
    return get_couchdb()


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

    # Get wishlist and owner info to store in bookmark (offline-first)
    wishlist = await db.get(wishlist_id)
    owner_name = "Unknown"
    owner_avatar = None
    try:
        owner = await db.get(wishlist["owner_id"])
        owner_name = owner.get("name") or "Unknown"
        owner_avatar = owner.get("avatar_base64")
    except DocumentNotFoundError:
        pass

    # Find existing bookmark for this wishlist
    all_user_bookmarks = await db.find({
        "type": "bookmark",
        "user_id": user_id,
    })
    user_bookmarks = [b for b in all_user_bookmarks if not b.get("_deleted")]

    existing_bookmark = None
    for bookmark in user_bookmarks:
        # First check if bookmark has wishlist_id directly (new format)
        if bookmark.get("wishlist_id") == wishlist_id:
            existing_bookmark = bookmark
            break
        # Fallback: check via share document (old format)
        try:
            bookmark_share = await db.get(bookmark["share_id"])
            if bookmark_share.get("wishlist_id") == wishlist_id:
                existing_bookmark = bookmark
                break
        except DocumentNotFoundError:
            continue

    if existing_bookmark:
        # Update existing bookmark to use the LAST share link followed
        existing_bookmark["share_id"] = share["_id"]
        existing_bookmark["wishlist_id"] = wishlist_id  # Store directly for easy lookup
        existing_bookmark["last_accessed_at"] = now
        # Update cached owner/wishlist info
        existing_bookmark["owner_name"] = owner_name
        existing_bookmark["owner_avatar_base64"] = owner_avatar
        existing_bookmark["wishlist_name"] = wishlist.get("name", "")
        existing_bookmark["wishlist_icon"] = wishlist.get("icon", "card_giftcard")
        existing_bookmark["updated_at"] = now
        await db.put(existing_bookmark)
    else:
        # Create new bookmark with cached owner/wishlist info
        bookmark_id = db.generate_id("bookmark")
        bookmark = {
            "_id": bookmark_id,
            "type": "bookmark",
            "user_id": user_id,
            "share_id": share["_id"],
            "wishlist_id": wishlist_id,  # Store directly for easy lookup
            "owner_name": owner_name,
            "owner_avatar_base64": owner_avatar,
            "wishlist_name": wishlist.get("name", ""),
            "wishlist_icon": wishlist.get("icon", "card_giftcard"),
            "created_at": now,
            "last_accessed_at": now,
            "access": [user_id],
        }
        await db.put(bookmark)


# =============================================================================
# Grant Access endpoint - minimal API for offline-first architecture
# =============================================================================

class GrantAccessResponse(BaseModel):
    """Minimal response for grant access - only returns IDs and permissions."""
    wishlist_id: str
    permissions: list[str]


@router.post(
    "/{token}/grant-access",
    response_model=GrantAccessResponse,
)
async def grant_access(
    token: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> GrantAccessResponse:
    """Grant access to a shared wishlist (minimal endpoint for offline-first).

    This endpoint:
    1. Validates the share token
    2. Adds user to access arrays
    3. Creates/updates bookmark (with cached owner/wishlist info for offline access)
    4. Returns only wishlist_id and permissions

    Data is then synced via PouchDB.
    """
    share = await get_share_by_token(db, token)
    user_id = current_user["_id"]

    # Grant access (updates access arrays, creates bookmark with owner info)
    await grant_access_to_user(db, share, user_id)

    # Determine permissions
    permissions = ["view"]
    if share.get("link_type") == "mark":
        permissions.append("mark")

    return GrantAccessResponse(
        wishlist_id=share["wishlist_id"],
        permissions=permissions,
    )
