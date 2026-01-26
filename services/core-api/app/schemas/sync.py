"""Sync-related Pydantic schemas for RxDB replication."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field


class SyncCheckpoint(BaseModel):
    """Checkpoint for sync pagination."""

    updated_at: datetime
    id: UUID


class WishlistSyncDocument(BaseModel):
    """Wishlist document for sync (RxDB compatible)."""

    id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    _deleted: bool = False


class ItemSyncDocument(BaseModel):
    """Item document for sync (RxDB compatible)."""

    id: UUID
    wishlist_id: UUID
    title: str
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    quantity: int = 1
    source_url: str | None = None
    image_url: str | None = None
    image_base64: str | None = None
    status: str  # pending, resolving, resolved, failed
    created_at: datetime
    updated_at: datetime
    _deleted: bool = False


class PullResponse(BaseModel):
    """Response for pull sync endpoint."""

    documents: list[dict[str, Any]]
    checkpoint: SyncCheckpoint | None = None


class PushRequest(BaseModel):
    """Request for push sync endpoint."""

    documents: Annotated[list[dict[str, Any]], Field(max_length=100)]


class ConflictDocument(BaseModel):
    """Conflict document returned when push fails."""

    document_id: UUID
    error: str
    server_document: dict[str, Any] | None = None


class PushResponse(BaseModel):
    """Response for push sync endpoint."""

    conflicts: list[ConflictDocument] = []
