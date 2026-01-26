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
from uuid import UUID, uuid4

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
    Supports multiple connections per user (multiple devices).
    """

    def __init__(self) -> None:
        # user_id -> {connection_id -> queue}
        self._channels: dict[UUID, dict[str, asyncio.Queue[ServerEvent | None]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID) -> tuple[str, asyncio.Queue[ServerEvent | None]]:
        """Register a new connection for user.

        Returns (connection_id, queue) tuple.
        Supports multiple connections per user (multiple devices).
        """
        async with self._lock:
            connection_id = str(uuid4())
            queue: asyncio.Queue[ServerEvent | None] = asyncio.Queue(maxsize=100)

            if user_id not in self._channels:
                self._channels[user_id] = {}

            self._channels[user_id][connection_id] = queue
            total = sum(len(conns) for conns in self._channels.values())
            logger.info(
                f"SSE: User {user_id} connected (conn={connection_id[:8]}), "
                f"user has {len(self._channels[user_id])} connections, total: {total}"
            )
            return connection_id, queue

    async def disconnect(self, user_id: UUID, connection_id: str) -> None:
        """Remove a specific connection for user."""
        async with self._lock:
            user_connections = self._channels.get(user_id)
            if not user_connections:
                logger.debug(f"SSE: Disconnect called but user {user_id} has no connections")
                return

            removed = user_connections.pop(connection_id, None)
            if removed:
                # Clean up user entry if no more connections
                if not user_connections:
                    del self._channels[user_id]
                total = sum(len(conns) for conns in self._channels.values())
                logger.info(
                    f"SSE: User {user_id} disconnected (conn={connection_id[:8]}), total: {total}"
                )
            else:
                logger.debug(
                    f"SSE: Connection {connection_id[:8]} not found for user {user_id}"
                )

    async def publish(self, user_id: UUID, event: ServerEvent) -> bool:
        """Send event to all connections for a specific user.

        Returns True if at least one connection received the event.
        """
        user_connections = self._channels.get(user_id)
        if not user_connections:
            return False

        delivered = False
        for conn_id, queue in list(user_connections.items()):
            try:
                queue.put_nowait(event)
                delivered = True
            except asyncio.QueueFull:
                logger.warning(
                    f"Event queue full for user {user_id} conn {conn_id[:8]}, dropping event"
                )
        return delivered

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
        """Check if user has at least one active SSE connection."""
        return user_id in self._channels and len(self._channels[user_id]) > 0

    @property
    def connection_count(self) -> int:
        """Total number of active connections across all users."""
        return sum(len(conns) for conns in self._channels.values())


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
