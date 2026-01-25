"""Notification service for managing in-app notifications."""

import logging
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing in-app notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        user_id: UUID,
        notification_type: NotificationType,
        payload: dict,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            payload=payload,
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def list_notifications(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int, int]:
        """List notifications for a user.

        Returns:
            Tuple of (notifications, unread_count, total_count)
        """
        # Base query
        query = select(Notification).where(Notification.user_id == user_id)

        if unread_only:
            query = query.where(Notification.read == False)  # noqa: E712

        # Get total count
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get unread count
        unread_query = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.read == False,  # noqa: E712
        )
        unread_result = await self.db.execute(unread_query)
        unread_count = unread_result.scalar() or 0

        # Get paginated notifications
        query = query.order_by(Notification.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        notifications = list(result.scalars().all())

        return notifications, unread_count, total

    async def mark_as_read(self, notification_ids: list[UUID], user_id: UUID) -> int:
        """Mark notifications as read.

        Returns:
            Number of notifications marked as read.
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id.in_(notification_ids),
                Notification.user_id == user_id,
                Notification.read == False,  # noqa: E712
            )
            .values(read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all notifications as read for a user.

        Returns:
            Number of notifications marked as read.
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read == False,  # noqa: E712
            )
            .values(read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        result = await self.db.execute(
            select(func.count()).where(
                Notification.user_id == user_id,
                Notification.read == False,  # noqa: E712
            )
        )
        return result.scalar() or 0


async def notify_item_resolved(
    db: AsyncSession,
    user_id: UUID,
    wishlist_id: UUID,
    item_id: UUID,
    item_title: str,
) -> Notification:
    """Send notification when an item is resolved."""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=user_id,
        notification_type=NotificationType.ITEM_RESOLVED,
        payload={
            "wishlist_id": str(wishlist_id),
            "item_id": str(item_id),
            "item_title": item_title,
        },
    )


async def notify_item_resolution_failed(
    db: AsyncSession,
    user_id: UUID,
    wishlist_id: UUID,
    item_id: UUID,
    item_title: str,
    error: str | None = None,
) -> Notification:
    """Send notification when item resolution fails."""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=user_id,
        notification_type=NotificationType.ITEM_RESOLUTION_FAILED,
        payload={
            "wishlist_id": str(wishlist_id),
            "item_id": str(item_id),
            "item_title": item_title,
            "error": error,
        },
    )
