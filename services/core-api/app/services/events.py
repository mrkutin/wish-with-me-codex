"""Server-Sent Events (SSE) channel manager for real-time updates.

Uses Redis pub/sub for cross-instance communication in multi-instance deployments.
Each instance maintains local SSE connections and subscribes to Redis for events.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.redis import get_redis

logger = logging.getLogger(__name__)

# Redis channel for SSE events
SSE_CHANNEL = "sse:events"


@dataclass
class ServerEvent:
    """SSE event to send to client."""

    event: str
    data: dict

    def format(self) -> str:
        """Format as SSE message."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"

    def to_redis(self, user_id: UUID) -> str:
        """Serialize for Redis pub/sub."""
        return json.dumps({
            "user_id": str(user_id),
            "event": self.event,
            "data": self.data,
        })

    @classmethod
    def from_redis(cls, message: str) -> tuple[UUID, "ServerEvent"]:
        """Deserialize from Redis pub/sub."""
        parsed = json.loads(message)
        return UUID(parsed["user_id"]), cls(
            event=parsed["event"],
            data=parsed["data"],
        )


class EventChannelManager:
    """Manages SSE event channels for connected users.

    Uses Redis pub/sub for cross-instance communication.
    Supports multiple connections per user (multiple devices).
    """

    def __init__(self) -> None:
        # user_id -> {connection_id -> queue}
        self._channels: dict[UUID, dict[str, asyncio.Queue[ServerEvent | None]]] = {}
        self._lock = asyncio.Lock()
        self._subscriber_task: asyncio.Task | None = None
        self._pubsub = None

    async def start_subscriber(self) -> None:
        """Start Redis subscriber for cross-instance events."""
        if self._subscriber_task is not None:
            return

        async def subscribe_loop():
            try:
                redis = await get_redis()
                self._pubsub = redis.pubsub()
                await self._pubsub.subscribe(SSE_CHANNEL)
                logger.info(f"SSE: Started Redis subscriber on channel {SSE_CHANNEL}")

                async for message in self._pubsub.listen():
                    if message["type"] == "message":
                        try:
                            user_id, event = ServerEvent.from_redis(message["data"])
                            logger.info(f"SSE: Received Redis message for user {user_id}, event {event.event}")
                            delivered = await self._deliver_local(user_id, event)
                            logger.info(f"SSE: Local delivery result for user {user_id}: {delivered}")
                        except Exception as e:
                            logger.exception(f"SSE: Failed to process Redis message: {e}")
            except asyncio.CancelledError:
                logger.info("SSE: Redis subscriber cancelled")
                raise
            except Exception as e:
                logger.exception(f"SSE: Redis subscriber error: {e}")

        self._subscriber_task = asyncio.create_task(subscribe_loop())

    async def stop_subscriber(self) -> None:
        """Stop Redis subscriber."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None

        if self._pubsub:
            await self._pubsub.unsubscribe(SSE_CHANNEL)
            await self._pubsub.close()
            self._pubsub = None

    async def connect(self, user_id: UUID) -> tuple[str, asyncio.Queue[ServerEvent | None]]:
        """Register a new connection for user.

        Returns (connection_id, queue) tuple.
        Supports multiple connections per user (multiple devices).
        """
        # Ensure subscriber is running
        await self.start_subscriber()

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

    async def _deliver_local(self, user_id: UUID, event: ServerEvent) -> bool:
        """Deliver event to local connections only (called from Redis subscriber)."""
        user_connections = self._channels.get(user_id)
        if not user_connections:
            logger.info(f"SSE: No local connections for user {user_id}, event {event.event} not delivered locally")
            return False

        delivered = False
        for conn_id, queue in list(user_connections.items()):
            try:
                queue.put_nowait(event)
                delivered = True
                logger.info(f"SSE: Delivered {event.event} to user {user_id} conn {conn_id[:8]}")
            except asyncio.QueueFull:
                logger.warning(
                    f"Event queue full for user {user_id} conn {conn_id[:8]}, dropping event"
                )
        return delivered

    async def publish(self, user_id: UUID, event: ServerEvent) -> bool:
        """Publish event via Redis for cross-instance delivery.

        Returns True if published successfully.
        """
        try:
            redis = await get_redis()
            await redis.publish(SSE_CHANNEL, event.to_redis(user_id))
            logger.info(f"SSE: Published {event.event} for user {user_id} to Redis channel {SSE_CHANNEL}")
            return True
        except Exception as e:
            logger.exception(f"SSE: Failed to publish to Redis: {e}")
            # Fallback to local delivery
            return await self._deliver_local(user_id, event)

    async def publish_to_many(self, user_ids: list[UUID], event: ServerEvent) -> int:
        """Publish event to multiple users via Redis.

        Returns count of publish attempts (not guaranteed deliveries).
        """
        published = 0
        for user_id in user_ids:
            if await self.publish(user_id, event):
                published += 1
        return published

    def is_connected(self, user_id: UUID) -> bool:
        """Check if user has at least one active SSE connection on this instance."""
        return user_id in self._channels and len(self._channels[user_id]) > 0

    @property
    def connection_count(self) -> int:
        """Total number of active connections on this instance."""
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
        f"item={item_id}, status={status}, local_connected={is_connected}"
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


async def publish_marks_updated_to_many(user_ids: list[UUID], item_id: UUID) -> int:
    """Notify multiple users that marks on an item changed.

    Returns count of publish attempts.
    """
    logger.info(
        f"Publishing marks:updated for item={item_id} to {len(user_ids)} users: "
        f"{[str(uid) for uid in user_ids]}"
    )

    event = ServerEvent(
        event="marks:updated",
        data={"item_id": str(item_id)},
    )
    published = await event_manager.publish_to_many(user_ids, event)
    logger.info(f"Published marks:updated to Redis for {published} users")
    return published


def create_ping_event() -> ServerEvent:
    """Create a keepalive ping event."""
    return ServerEvent(
        event="sync:ping",
        data={"timestamp": datetime.now(timezone.utc).isoformat()},
    )
