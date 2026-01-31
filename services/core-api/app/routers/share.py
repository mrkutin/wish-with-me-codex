"""Share link management endpoints (CouchDB-based)."""

import base64
import io
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.couchdb import CouchDBClient, DocumentNotFoundError, get_couchdb
from app.dependencies import CurrentUserCouchDB
from app.schemas.share import (
    ShareLinkCreate,
    ShareLinkListResponse,
    ShareLinkResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wishlists", tags=["share"])


async def get_db() -> CouchDBClient:
    """Get CouchDB client dependency."""
    return get_couchdb()


def normalize_wishlist_id(wishlist_id: str) -> str:
    """Normalize wishlist ID to CouchDB format (wishlist:uuid)."""
    if wishlist_id.startswith("wishlist:"):
        return wishlist_id
    return f"wishlist:{wishlist_id}"


def generate_token(length: int = 32) -> str:
    """Generate a secure URL-safe token."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_qr_code(url: str) -> str | None:
    """Generate a QR code as base64-encoded PNG."""
    try:
        import qrcode
        from qrcode.image.pure import PyPNGImage

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(image_factory=PyPNGImage)
        buffer = io.BytesIO()
        img.save(buffer)
        buffer.seek(0)

        b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except ImportError:
        logger.warning("qrcode library not installed, skipping QR generation")
        return None
    except Exception as e:
        logger.error(f"QR code generation failed: {e}")
        return None


def get_share_url(token: str) -> str:
    """Get the public share URL for a token."""
    # TODO: Make this configurable
    return f"https://wishwith.me/s/{token}"


def extract_uuid(doc_id: str) -> UUID:
    """Extract UUID from CouchDB document ID (e.g., 'share:uuid')."""
    if ":" in doc_id:
        return UUID(doc_id.split(":", 1)[1])
    return UUID(doc_id)


def share_doc_to_response(doc: dict) -> ShareLinkResponse:
    """Convert CouchDB share document to response schema."""
    share_url = get_share_url(doc["token"])
    return ShareLinkResponse(
        id=extract_uuid(doc["_id"]),
        wishlist_id=extract_uuid(doc["wishlist_id"]),
        token=doc["token"],
        link_type=doc["link_type"],
        expires_at=datetime.fromisoformat(doc["expires_at"]) if doc.get("expires_at") else None,
        access_count=doc.get("access_count", 0),
        created_at=datetime.fromisoformat(doc["created_at"]),
        share_url=share_url,
        qr_code_base64=generate_qr_code(share_url),
    )


@router.get(
    "/{wishlist_id}/share",
    response_model=ShareLinkListResponse,
    responses={
        403: {"description": "Not the wishlist owner"},
        404: {"description": "Wishlist not found"},
    },
)
async def list_share_links(
    wishlist_id: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> ShareLinkListResponse:
    """List all share links for a wishlist (owner only)."""
    user_id = current_user["_id"]
    wishlist_doc_id = normalize_wishlist_id(wishlist_id)

    # Check wishlist exists and user is owner
    try:
        wishlist = await db.get(wishlist_doc_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if wishlist.get("owner_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the wishlist owner can manage share links",
        )

    # Find all share links for this wishlist
    shares = await db.find({
        "type": "share",
        "wishlist_id": wishlist_doc_id,
        "owner_id": user_id,
        "revoked": False,
    })

    # Filter out expired links
    now = datetime.now(timezone.utc)
    active_shares = []
    for share in shares:
        if share.get("expires_at"):
            expires = datetime.fromisoformat(share["expires_at"])
            if expires < now:
                continue
        active_shares.append(share_doc_to_response(share))

    return ShareLinkListResponse(items=active_shares)


@router.post(
    "/{wishlist_id}/share",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Not the wishlist owner"},
        404: {"description": "Wishlist not found"},
    },
)
async def create_share_link(
    wishlist_id: str,
    data: ShareLinkCreate,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> ShareLinkResponse:
    """Create a new share link for a wishlist (owner only)."""
    user_id = current_user["_id"]
    wishlist_doc_id = normalize_wishlist_id(wishlist_id)

    # Check wishlist exists and user is owner
    try:
        wishlist = await db.get(wishlist_doc_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found",
        )

    if wishlist.get("owner_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the wishlist owner can create share links",
        )

    # Generate token and calculate expiration
    token = generate_token()
    expires_at = None
    if data.expires_in_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)).isoformat()

    # Create share document
    share = await db.create_share(
        wishlist_id=wishlist_doc_id,
        owner_id=user_id,
        token=token,
        link_type=data.link_type.value,
        expires_at=expires_at,
    )

    return share_doc_to_response(share)


@router.delete(
    "/{wishlist_id}/share/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Not the wishlist owner"},
        404: {"description": "Share link not found"},
    },
)
async def revoke_share_link(
    wishlist_id: str,
    share_id: str,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> None:
    """Revoke a share link (owner only)."""
    user_id = current_user["_id"]
    # Normalize share_id - handle both 'share:uuid' and plain 'uuid'
    if share_id.startswith("share:"):
        share_doc_id = share_id
    else:
        share_doc_id = f"share:{share_id}"
    wishlist_doc_id = normalize_wishlist_id(wishlist_id)

    # Get share document
    try:
        share = await db.get(share_doc_id)
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    # Verify ownership
    if share.get("owner_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the wishlist owner can revoke share links",
        )

    # Verify it belongs to the right wishlist
    if share.get("wishlist_id") != wishlist_doc_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    # Revoke the share link (soft delete)
    share["revoked"] = True
    share["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.put(share)
