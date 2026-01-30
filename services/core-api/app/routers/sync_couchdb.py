"""CouchDB-based sync endpoints for PouchDB clients.

Note: This is an API-based pull/push sync, not native CouchDB replication protocol.
The frontend's PouchDB uses these endpoints to sync data with the CouchDB backend.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.couchdb import CouchDBClient, ConflictError, DocumentNotFoundError, get_couchdb
from app.dependencies import CurrentUserCouchDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/sync", tags=["sync-v2"])

CollectionType = Literal["wishlists", "items", "marks"]


class SyncDocument(BaseModel):
    """A document being synced."""

    _id: str
    _rev: str | None = None
    type: str
    access: list[str] | None = None

    class Config:
        extra = "allow"


class PullResponse(BaseModel):
    """Response for pull operation."""

    documents: list[dict]


class PushRequest(BaseModel):
    """Request for push operation."""

    documents: list[dict]


class ConflictInfo(BaseModel):
    """Information about a conflict."""

    document_id: str
    error: str
    server_document: dict | None = None


class PushResponse(BaseModel):
    """Response for push operation."""

    conflicts: list[ConflictInfo]


async def get_db() -> CouchDBClient:
    """Get CouchDB client dependency."""
    return get_couchdb()


@router.get(
    "/pull/{collection}",
    response_model=PullResponse,
)
async def pull_collection(
    collection: CollectionType,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> PullResponse:
    """Pull all documents of a collection that the user has access to.

    Returns documents where the user's ID is in the access array.
    """
    user_id = current_user["_id"]

    # Map collection to document type
    type_map = {
        "wishlists": "wishlist",
        "items": "item",
        "marks": "mark",
    }
    doc_type = type_map[collection]

    # Find all documents of this type that user has access to
    # IMPORTANT: Exclude deleted documents to prevent phantom items reappearing
    selector = {
        "type": doc_type,
        "access": {"$elemMatch": {"$eq": user_id}},
        "_deleted": {"$ne": True},
    }

    # For marks, also exclude marks where user is the wishlist owner
    # (marks are hidden from wishlist owner in "surprise mode")
    if collection == "marks":
        selector["owner_id"] = {"$ne": user_id}

    try:
        # Note: CouchDB Mango with $elemMatch doesn't work well with indexes,
        # so we fetch without sort and sort in Python
        documents = await db.find(
            selector=selector,
            limit=1000,  # Reasonable limit for initial sync
        )
        # Sort by updated_at descending in Python
        documents.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
        return PullResponse(documents=documents)
    except Exception as e:
        logger.error(f"Pull error for {collection}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pull {collection}",
        )


@router.post(
    "/push/{collection}",
    response_model=PushResponse,
)
async def push_collection(
    collection: CollectionType,
    data: PushRequest,
    current_user: CurrentUserCouchDB,
    db: Annotated[CouchDBClient, Depends(get_db)],
) -> PushResponse:
    """Push documents to the server.

    Uses Last-Write-Wins (LWW) conflict resolution based on updated_at.
    Validates that user has access to each document.
    """
    user_id = current_user["_id"]
    conflicts: list[ConflictInfo] = []

    # Map collection to document type
    type_map = {
        "wishlists": "wishlist",
        "items": "item",
        "marks": "mark",
    }
    doc_type = type_map[collection]

    for doc in data.documents:
        try:
            doc_id = doc.get("_id")
            if not doc_id:
                conflicts.append(ConflictInfo(
                    document_id="unknown",
                    error="Document missing _id",
                ))
                continue

            # Validate document type
            if doc.get("type") != doc_type:
                conflicts.append(ConflictInfo(
                    document_id=doc_id,
                    error=f"Document type mismatch: expected {doc_type}",
                ))
                continue

            # Authorization check based on collection
            if collection == "wishlists":
                # User must be the owner
                if doc.get("owner_id") != user_id:
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Unauthorized: not the wishlist owner",
                    ))
                    continue
            elif collection == "items":
                # User must have access to the wishlist
                wishlist_id = doc.get("wishlist_id")
                if not wishlist_id:
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Item missing wishlist_id",
                    ))
                    continue
                try:
                    wishlist = await db.get(wishlist_id)
                    if user_id not in wishlist.get("access", []):
                        conflicts.append(ConflictInfo(
                            document_id=doc_id,
                            error="Unauthorized: no access to wishlist",
                        ))
                        continue
                except DocumentNotFoundError:
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Wishlist not found",
                    ))
                    continue
            elif collection == "marks":
                # User must be the one who marked it
                if doc.get("marked_by") != user_id:
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Unauthorized: not the mark owner",
                    ))
                    continue

            # Try to get existing document
            try:
                existing = await db.get(doc_id)

                # LWW: Check if client version is newer
                client_updated = doc.get("updated_at", "")
                server_updated = existing.get("updated_at", "")

                if client_updated <= server_updated:
                    # Server wins
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Server has newer version",
                        server_document=existing,
                    ))
                    continue

                # Client wins - update document
                doc["_rev"] = existing["_rev"]  # Use server's revision
                doc["updated_at"] = datetime.now(timezone.utc).isoformat()

                # Ensure access array is preserved
                if "access" not in doc:
                    doc["access"] = existing.get("access", [])

            except DocumentNotFoundError:
                # New document - ensure required fields
                doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                if "created_at" not in doc:
                    doc["created_at"] = doc["updated_at"]

                # Set access array based on document type
                if collection == "wishlists":
                    doc["access"] = [user_id]
                elif collection == "items":
                    # Inherit access from wishlist
                    try:
                        wishlist = await db.get(doc["wishlist_id"])
                        doc["access"] = wishlist.get("access", [user_id])
                    except DocumentNotFoundError:
                        doc["access"] = [user_id]
                elif collection == "marks":
                    # Marks are visible to all viewers except owner
                    try:
                        wishlist = await db.get(doc["wishlist_id"])
                        owner_id = wishlist.get("owner_id")
                        doc["access"] = [
                            uid for uid in wishlist.get("access", [])
                            if uid != owner_id
                        ]
                    except DocumentNotFoundError:
                        doc["access"] = [user_id]

            # Save document
            try:
                await db.put(doc)
            except ConflictError:
                # Race condition - refetch and return as conflict
                try:
                    server_doc = await db.get(doc_id)
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Concurrent modification",
                        server_document=server_doc,
                    ))
                except DocumentNotFoundError:
                    conflicts.append(ConflictInfo(
                        document_id=doc_id,
                        error="Document was deleted",
                    ))

        except Exception as e:
            logger.error(f"Push error for document {doc.get('_id', 'unknown')}: {e}")
            conflicts.append(ConflictInfo(
                document_id=doc.get("_id", "unknown"),
                error=str(e),
            ))

    return PushResponse(conflicts=conflicts)
