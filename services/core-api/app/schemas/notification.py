"""Notification-related Pydantic schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    """Schema for notification response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    payload: dict
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Schema for notification list response."""

    items: list[NotificationResponse]
    unread_count: int
    total: int


class NotificationMarkReadRequest(BaseModel):
    """Schema for marking notifications as read."""

    notification_ids: Annotated[list[UUID], Field(min_length=1)]
