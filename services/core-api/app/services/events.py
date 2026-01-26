"""Server-Sent Events (SSE) channel manager for real-time updates.

Manages SSE connections per user and publishes events when data changes.
For single-instance deployment (Montreal), uses in-memory queues.
For multi-instance scaling, would need Redis pub/sub (future enhancement).
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class ServerEvent:
    """SSE event to send to client."""

    event: str
    data: dict

    def format(self) -> str:
        """Format as SSE message."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class EventChannelManager:
    """Manages SSE event channels for connected users.

    For single-instance deployment, uses in-memory queues.
    Each user can have one active SSE connection.
    """

    def __init__(self) -> None:
        self._channels: dict[UUID, asyncio.Queue[ServerEvent | None]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID) -> asyncio.Queue[ServerEvent | None]:
        """Register a new connection for user.

        If user already has a connection, the old one is signaled to close.
        """
        async with self._lock:
            # If user already connected, signal old connection to close
            if user_id in self._channels:
                try:
                    self._channels[user_id].put_nowait(None)
                except asyncio.QueueFull:
                    pass
                logger.info(f"SSE: Closing existing connection for user {user_id}")

            queue: asyncio.Queue[ServerEvent | None] = asyncio.Queue(maxsize=100)
            self._channels[user_id] = queue
            logger.info(
                f"SSE: User {user_id} connected, total connections: {len(self._channels)}"
            )
            return queue

    async def disconnect(self, user_id: UUID) -> None:
        """Remove user's connection."""
        async with self._lock:
            removed = self._channels.pop(user_id, None)
            if removed:
                logger.info(
                    f"SSE: User {user_id} disconnected, total connections: {len(self._channels)}"
                )
            else:
                logger.warning(f"SSE: Disconnect called but user {user_id} was not connected")

    async def publish(self, user_id: UUID, event: ServerEvent) -> bool:
        """Send event to specific user.

        Returns True if user was connected and event queued, False otherwise.
        """
        queue = self._channels.get(user_id)
        if queue:
            try:
                queue.put_nowait(event)
                return True
            except asyncio.QueueFull:
                logger.warning(f"Event queue full for user {user_id}, dropping event")
                return False
        return False

    async def publish_to_many(self, user_ids: list[UUID], event: ServerEvent) -> int:
        """Send event to multiple users.

        Returns count of users who received the event.
        """
        delivered = 0
        for user_id in user_ids:
            if await self.publish(user_id, event):
                delivered += 1
        return delivered

    def is_connected(self, user_id: UUID) -> bool:
        """Check if user has active SSE connection."""
        return user_id in self._channels

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._channels)


# Global singleton instance
event_manager = EventChannelManager()


# Convenience functions for publishing specific event types


async def publish_item_updated(
    user_id: UUID, item_id: UUID, wishlist_id: UUID
) -> bool:
    """Notify user that an item was updated."""
    return await event_manager.publish(
        user_id,
        ServerEvent(
            event="items:updated",
            data={"id": str(item_id), "wishlist_id": str(wishlist_id)},
        ),
    )


async def publish_item_resolved(
    user_id: UUID,
    item_id: UUID,
    wishlist_id: UUID,
    status: str,
    title: str | None = None,
) -> bool:
    """Notify user that item resolution completed."""
    is_connected = event_manager.is_connected(user_id)
    logger.info(
        f"Publishing items:resolved event: user={user_id}, "
        f"item={item_id}, status={status}, connected={is_connected}"
    )
    result = await event_manager.publish(
        user_id,
        ServerEvent(
            event="items:resolved",
            data={
                "id": str(item_id),
                "wishlist_id": str(wishlist_id),
                "status": status,
                "title": title,
            },
        ),
    )
    if not result:
        logger.warning(
            f"Failed to deliver items:resolved event: user={user_id}, "
            f"item={item_id} - user not connected to SSE"
        )
    return result


async def publish_wishlist_updated(user_id: UUID, wishlist_id: UUID) -> bool:
    """Notify user that a wishlist was updated."""
    return await event_manager.publish(
        user_id,
        ServerEvent(
            event="wishlists:updated",
            data={"id": str(wishlist_id)},
        ),
    )


async def publish_marks_updated(user_id: UUID, item_id: UUID) -> bool:
    """Notify user that marks on an item changed."""
    return await event_manager.publish(
        user_id,
        ServerEvent(
            event="marks:updated",
            data={"item_id": str(item_id)},
        ),
    )


def create_ping_event() -> ServerEvent:
    """Create a keepalive ping event."""
    return ServerEvent(
        event="sync:ping",
        data={"timestamp": datetime.now(timezone.utc).isoformat()},
    )
