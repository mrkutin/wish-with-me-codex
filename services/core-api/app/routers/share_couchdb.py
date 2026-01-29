"""CouchDB-based share link management endpoints."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.couchdb import CouchDBClient, DocumentNotFoundError, get_couchdb
from app.dependencies import CurrentUserCouchDB

router = APIRouter(prefix="/api/v2/wishlists", tags=["share-v2"])


class ShareLinkCreateRequest(BaseModel):
    """Request to create a share link."""

    link_type: str = "mark"  # "view" or "mark"
    expires_in_days: Annotated[int | None, Field(ge=1, le=365)] = None


class ShareLinkResponse(BaseModel):
    """Response for a share link."""

    id: str
    wishlist_id: str
    token: str
    link_type: str
    expires_at: str | None
    access_count: int
    created_at: str
    share_url: str


class ShareLinkListResponse(BaseModel):
    """List of share links."""

    items: list[ShareLinkResponse]


class ShareAccessRequest(BaseModel):
    """Request to access a shared wishlist."""

    # No fields needed - user ID comes from auth


class ShareAccessResponse(BaseModel):
    """Response after accessing a shared wishlist."""

    wishlist_id: str
    wishlist_name: str
    owner_name: str
    permissions: list[str]


def generate_share_token() -> str:
    """Generate a secure random share token."""
    return secrets.token_urlsafe(24)[:32]


def get_share_url(token: str) -> str:
    """Get the share URL for a token."""
    from app.config import settings

    base_url = settings.api_base_url.replace("api.", "")
    return f"{base_url}/s/{token}"


async def get_db() -> CouchDBClient:
    """Get CouchDB client dependency."""
    return get_couchdb()


@router.get(
    "/{wishlist_id}/share",
    response_model=ShareLinkListResponse,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized"},
    },
)
async def list_share_links(
    wishlist_id: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> ShareLinkListResponse:
    """List all share links for a wishlist."""
    # Get wishlist
    try:
        wishlist = await db.get(wishlist_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Check ownership
    if wishlist.get("owner_id") != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this wishlist",
        )

    # Find share links for this wishlist
    shares = await db.find({
        "type": "share",
        "wishlist_id": wishlist_id,
        "revoked": False,
    })

    items = [
        ShareLinkResponse(
            id=share["_id"],
            wishlist_id=share["wishlist_id"],
            token=share["token"],
            link_type=share["link_type"],
            expires_at=share.get("expires_at"),
            access_count=share.get("access_count", 0),
            created_at=share["created_at"],
            share_url=get_share_url(share["token"]),
        )
        for share in shares
    ]

    return ShareLinkListResponse(items=items)


@router.post(
    "/{wishlist_id}/share",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Wishlist not found"},
        403: {"description": "Not authorized"},
    },
)
async def create_share_link(
    wishlist_id: str,
    data: ShareLinkCreateRequest,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> ShareLinkResponse:
    """Create a new share link for a wishlist."""
    # Get wishlist
    try:
        wishlist = await db.get(wishlist_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Check ownership
    if wishlist.get("owner_id") != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to share this wishlist",
        )

    # Generate token
    token = generate_share_token()

    # Calculate expiry
    expires_at = None
    if data.expires_in_days:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)
        ).isoformat()

    # Create share document
    share = await db.create_share(
        wishlist_id=wishlist_id,
        owner_id=current_user["_id"],
        token=token,
        link_type=data.link_type,
        expires_at=expires_at,
    )

    return ShareLinkResponse(
        id=share["_id"],
        wishlist_id=share["wishlist_id"],
        token=share["token"],
        link_type=share["link_type"],
        expires_at=share.get("expires_at"),
        access_count=share.get("access_count", 0),
        created_at=share["created_at"],
        share_url=get_share_url(share["token"]),
    )


@router.delete(
    "/{wishlist_id}/share/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Share link not found"},
        403: {"description": "Not authorized"},
    },
)
async def revoke_share_link(
    wishlist_id: str,
    share_id: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> None:
    """Revoke a share link and remove granted users from access arrays."""
    # Get wishlist
    try:
        wishlist = await db.get(wishlist_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    # Check ownership
    if wishlist.get("owner_id") != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this share link",
        )

    # Get share link
    try:
        share = await db.get(share_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    if share.get("wishlist_id") != wishlist_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    # Get list of granted users before revoking
    granted_users = share.get("granted_users", [])

    # Revoke the share link
    now = datetime.now(timezone.utc).isoformat()
    share["revoked"] = True
    share["revoked_at"] = now
    share["updated_at"] = now
    await db.put(share)

    # Remove granted users from access arrays
    for user_id in granted_users:
        await db.update_access_arrays(wishlist_id, user_id, action="remove")


@router.post(
    "/shared/{token}/access",
    response_model=ShareAccessResponse,
    responses={
        404: {"description": "Share link not found or expired"},
        401: {"description": "Authentication required"},
    },
)
async def access_shared_wishlist(
    token: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> ShareAccessResponse:
    """Access a shared wishlist and add user to access arrays.

    This endpoint is called when a user clicks on a share link.
    It adds the user to the wishlist's access arrays so they can sync it.
    """
    # Find share by token using view
    result = await db.view(
        "app",
        "shares_by_token",
        key=token,
        include_docs=True,
        limit=1,
    )

    rows = result.get("rows", [])
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or expired",
        )

    share = rows[0]["doc"]

    # Check if expired
    if share.get("expires_at"):
        expires_at = datetime.fromisoformat(
            share["expires_at"].replace("Z", "+00:00")
        )
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share link has expired",
            )

    # Check if revoked
    if share.get("revoked"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link has been revoked",
        )

    wishlist_id = share["wishlist_id"]
    user_id = current_user["_id"]
    owner_id = share["owner_id"]

    # Don't add owner to their own access arrays
    if user_id == owner_id:
        # Just return the wishlist info
        wishlist = await db.get(wishlist_id)
        owner = await db.get(owner_id)
        return ShareAccessResponse(
            wishlist_id=wishlist_id,
            wishlist_name=wishlist.get("name", ""),
            owner_name=owner.get("name", ""),
            permissions=["view", "mark"] if share["link_type"] == "mark" else ["view"],
        )

    # Add user to access arrays
    await db.update_access_arrays(wishlist_id, user_id, action="add")

    # Update share document
    now = datetime.now(timezone.utc).isoformat()
    granted_users = share.get("granted_users", [])
    if user_id not in granted_users:
        granted_users.append(user_id)
    share["granted_users"] = granted_users
    share["access_count"] = share.get("access_count", 0) + 1
    share["updated_at"] = now
    await db.put(share)

    # Get wishlist and owner info
    wishlist = await db.get(wishlist_id)
    owner = await db.get(owner_id)

    return ShareAccessResponse(
        wishlist_id=wishlist_id,
        wishlist_name=wishlist.get("name", ""),
        owner_name=owner.get("name", ""),
        permissions=["view", "mark"] if share["link_type"] == "mark" else ["view"],
    )


@router.get(
    "/shared/{token}",
    responses={
        404: {"description": "Share link not found or expired"},
    },
)
async def get_shared_wishlist_preview(
    token: str,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> dict:
    """Get preview info for a shared wishlist (no auth required)."""
    # Find share by token
    result = await db.view(
        "app",
        "shares_by_token",
        key=token,
        include_docs=True,
        limit=1,
    )

    rows = result.get("rows", [])
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or expired",
        )

    share = rows[0]["doc"]

    # Check if expired or revoked
    if share.get("revoked"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link has been revoked",
        )

    if share.get("expires_at"):
        expires_at = datetime.fromisoformat(
            share["expires_at"].replace("Z", "+00:00")
        )
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share link has expired",
            )

    # Get wishlist and owner
    wishlist = await db.get(share["wishlist_id"])
    owner = await db.get(share["owner_id"])

    # Count items
    items = await db.find(
        {"type": "item", "wishlist_id": share["wishlist_id"]},
        fields=["_id"],
    )

    return {
        "wishlist": {
            "id": wishlist["_id"],
            "name": wishlist.get("name", ""),
            "description": wishlist.get("description"),
            "icon": wishlist.get("icon", "🎁"),
            "owner_name": owner.get("name", ""),
            "item_count": len(items),
        },
        "link_type": share["link_type"],
        "requires_auth": True,
    }
