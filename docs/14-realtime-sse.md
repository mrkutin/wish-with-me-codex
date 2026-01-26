# Phase 6: Real-Time Updates via SSE

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Overview

### Problem

Currently, the frontend only learns about backend changes when it initiates a sync:
- Item resolution completes → User must refresh to see results
- Data modified by another device → Not visible until manual sync
- Backend processes complete → No immediate feedback

### Solution

Server-Sent Events (SSE) provide a lightweight, one-way stream from server to client. When backend data changes, the server pushes an event that triggers the frontend to pull updates via existing RxDB replication.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                                  │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ Item        │    │ Sync        │    │ SSE Endpoint            │ │
│  │ Resolver    │───▶│ Events      │───▶│ /api/v1/events/stream   │ │
│  │             │    │ Publisher   │    │                         │ │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘ │
│                                                     │               │
└─────────────────────────────────────────────────────┼───────────────┘
                                                      │ SSE stream
                                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (Vue)                                                     │
│                                                                     │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐│
│  │ useRealtimeSync         │    │ RxDB Replication                ││
│  │ composable              │───▶│ triggerPull()                   ││
│  │ (EventSource listener)  │    │                                 ││
│  └─────────────────────────┘    └────────────┬────────────────────┘│
│                                               │                     │
│                                               ▼                     │
│                                    ┌─────────────────────────┐     │
│                                    │ RxDB Subscriptions      │     │
│                                    │ → UI auto-updates       │     │
│                                    └─────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Event Types

| Event | Trigger | Data | Frontend Action |
|-------|---------|------|-----------------|
| `items:updated` | Item created/updated/resolved | `{id, wishlist_id}` | Pull items for wishlist |
| `items:resolved` | Item resolution complete | `{id, wishlist_id, status}` | Pull items, show notification |
| `wishlists:updated` | Wishlist created/updated | `{id}` | Pull wishlists |
| `marks:updated` | Mark added/removed | `{item_id}` | Pull marks (if viewer) |
| `sync:ping` | Keep-alive (every 30s) | `{timestamp}` | None (connection health) |

### Event Format

```
event: items:resolved
data: {"id":"abc123","wishlist_id":"xyz789","status":"resolved","title":"iPhone 15"}

event: sync:ping
data: {"timestamp":"2026-01-26T12:00:00Z"}
```

---

## 3. Backend Implementation

### 3.1 Event Channel Manager

```python
# /services/core-api/app/services/events.py

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID
from dataclasses import dataclass, asdict


@dataclass
class ServerEvent:
    """SSE event to send to client."""
    event: str
    data: dict

    def format(self) -> str:
        """Format as SSE message."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class EventChannelManager:
    """
    Manages SSE event channels for connected users.

    For single-instance deployment (Montreal), uses in-memory queues.
    For multi-instance, would need Redis pub/sub (future enhancement).
    """

    def __init__(self):
        self._channels: dict[UUID, asyncio.Queue[ServerEvent]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID) -> asyncio.Queue[ServerEvent]:
        """Register a new connection for user."""
        async with self._lock:
            # If user already connected, close old connection
            if user_id in self._channels:
                await self._channels[user_id].put(None)  # Signal close

            queue: asyncio.Queue[ServerEvent] = asyncio.Queue()
            self._channels[user_id] = queue
            return queue

    async def disconnect(self, user_id: UUID) -> None:
        """Remove user's connection."""
        async with self._lock:
            self._channels.pop(user_id, None)

    async def publish(self, user_id: UUID, event: ServerEvent) -> bool:
        """
        Send event to specific user.
        Returns True if user was connected, False otherwise.
        """
        queue = self._channels.get(user_id)
        if queue:
            await queue.put(event)
            return True
        return False

    async def publish_to_many(self, user_ids: list[UUID], event: ServerEvent) -> int:
        """Send event to multiple users. Returns count of delivered."""
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


# Global singleton
event_manager = EventChannelManager()


# Helper functions for publishing events
async def publish_item_updated(user_id: UUID, item_id: UUID, wishlist_id: UUID) -> None:
    """Notify user that an item was updated."""
    await event_manager.publish(
        user_id,
        ServerEvent(
            event="items:updated",
            data={"id": str(item_id), "wishlist_id": str(wishlist_id)}
        )
    )


async def publish_item_resolved(
    user_id: UUID,
    item_id: UUID,
    wishlist_id: UUID,
    status: str,
    title: str | None = None
) -> None:
    """Notify user that item resolution completed."""
    await event_manager.publish(
        user_id,
        ServerEvent(
            event="items:resolved",
            data={
                "id": str(item_id),
                "wishlist_id": str(wishlist_id),
                "status": status,
                "title": title
            }
        )
    )


async def publish_wishlist_updated(user_id: UUID, wishlist_id: UUID) -> None:
    """Notify user that a wishlist was updated."""
    await event_manager.publish(
        user_id,
        ServerEvent(
            event="wishlists:updated",
            data={"id": str(wishlist_id)}
        )
    )


async def publish_marks_updated(user_id: UUID, item_id: UUID) -> None:
    """Notify user that marks on an item changed."""
    await event_manager.publish(
        user_id,
        ServerEvent(
            event="marks:updated",
            data={"item_id": str(item_id)}
        )
    )
```

### 3.2 SSE Endpoint

```python
# /services/core-api/app/routers/events.py

import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.models import User
from app.services.events import event_manager, ServerEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/events", tags=["events"])

KEEPALIVE_INTERVAL = 30  # seconds


@router.get("/stream")
async def event_stream(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    SSE endpoint for real-time updates.

    Client connects and receives events when:
    - Items are updated/resolved
    - Wishlists are modified
    - Marks change (for viewers)

    Connection auto-closes when client disconnects.
    Keepalive ping sent every 30 seconds.
    """

    async def generate():
        queue = await event_manager.connect(user.id)
        logger.info(f"SSE connected: user={user.id}, total={event_manager.connection_count}")

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout for keepalive
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=KEEPALIVE_INTERVAL
                    )

                    if event is None:
                        # None signals connection should close (user reconnected elsewhere)
                        break

                    yield event.format()

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    ping = ServerEvent(
                        event="sync:ping",
                        data={"timestamp": datetime.utcnow().isoformat()}
                    )
                    yield ping.format()

        except asyncio.CancelledError:
            pass
        finally:
            await event_manager.disconnect(user.id)
            logger.info(f"SSE disconnected: user={user.id}, total={event_manager.connection_count}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/status")
async def connection_status(user: User = Depends(get_current_user)):
    """Check if user has active SSE connection."""
    return {
        "connected": event_manager.is_connected(user.id),
        "total_connections": event_manager.connection_count
    }
```

### 3.3 Integration Points

#### Item Resolution (items.py)

```python
# In resolve_item_background function, after successful resolution:

from app.services.events import publish_item_resolved

async def resolve_item_background(
    item_id: UUID,
    source_url: str,
    session_maker: async_sessionmaker[AsyncSession]
):
    async with session_maker() as db:
        # ... existing resolution logic ...

        # After successful resolution
        item = await db.get(Item, item_id)
        if item:
            wishlist = await db.get(Wishlist, item.wishlist_id)
            if wishlist:
                await publish_item_resolved(
                    user_id=wishlist.user_id,
                    item_id=item.id,
                    wishlist_id=item.wishlist_id,
                    status=item.status,
                    title=item.title
                )
```

#### Sync Push (sync.py)

```python
# After processing pushed documents:

from app.services.events import publish_item_updated, publish_wishlist_updated

# In _push_wishlists, after commit:
for doc in documents:
    await publish_wishlist_updated(user_id, UUID(doc["id"]))

# In _push_items, after commit:
for doc in documents:
    await publish_item_updated(user_id, UUID(doc["id"]), UUID(doc["wishlist_id"]))
```

### 3.4 Router Registration

```python
# /services/core-api/app/main.py

from app.routers import events

app.include_router(events.router)
```

---

## 4. Frontend Implementation

### 4.1 Realtime Sync Composable

```typescript
// /services/frontend/src/composables/useRealtimeSync.ts

import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useOnline } from '@vueuse/core';
import { useAuthStore } from '@/stores/auth';
import { getReplicationState } from '@/services/rxdb/replication';

interface SSEEvent {
  id?: string;
  wishlist_id?: string;
  item_id?: string;
  status?: string;
  title?: string;
  timestamp?: string;
}

export function useRealtimeSync() {
  const authStore = useAuthStore();
  const isOnline = useOnline();

  const isConnected = ref(false);
  const lastEventTime = ref<Date | null>(null);
  const reconnectAttempts = ref(0);

  let eventSource: EventSource | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  const MAX_RECONNECT_DELAY = 30000; // 30 seconds
  const BASE_RECONNECT_DELAY = 1000; // 1 second

  function getReconnectDelay(): number {
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s, 30s, ...
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.value),
      MAX_RECONNECT_DELAY
    );
    return delay;
  }

  function connect() {
    if (!authStore.isAuthenticated || !isOnline.value) {
      return;
    }

    // Close existing connection
    disconnect();

    const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    eventSource = new EventSource(`${baseUrl}/api/v1/events/stream`, {
      withCredentials: true
    });

    eventSource.onopen = () => {
      console.log('[SSE] Connected');
      isConnected.value = true;
      reconnectAttempts.value = 0;
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Error:', error);
      isConnected.value = false;

      // EventSource auto-reconnects, but we track state
      if (eventSource?.readyState === EventSource.CLOSED) {
        scheduleReconnect();
      }
    };

    // Item updated - trigger pull for items
    eventSource.addEventListener('items:updated', (event) => {
      const data: SSEEvent = JSON.parse(event.data);
      console.log('[SSE] items:updated:', data);
      lastEventTime.value = new Date();
      triggerItemsPull(data.wishlist_id);
    });

    // Item resolved - trigger pull and optionally notify
    eventSource.addEventListener('items:resolved', (event) => {
      const data: SSEEvent = JSON.parse(event.data);
      console.log('[SSE] items:resolved:', data);
      lastEventTime.value = new Date();
      triggerItemsPull(data.wishlist_id);

      // Could show notification for resolution
      // if (data.status === 'resolved' && data.title) {
      //   showItemResolvedNotification(data.title);
      // }
    });

    // Wishlist updated - trigger pull for wishlists
    eventSource.addEventListener('wishlists:updated', (event) => {
      const data: SSEEvent = JSON.parse(event.data);
      console.log('[SSE] wishlists:updated:', data);
      lastEventTime.value = new Date();
      triggerWishlistsPull();
    });

    // Marks updated - trigger pull for marks
    eventSource.addEventListener('marks:updated', (event) => {
      const data: SSEEvent = JSON.parse(event.data);
      console.log('[SSE] marks:updated:', data);
      lastEventTime.value = new Date();
      triggerMarksPull();
    });

    // Keepalive ping - just update timestamp
    eventSource.addEventListener('sync:ping', (event) => {
      const data: SSEEvent = JSON.parse(event.data);
      lastEventTime.value = new Date();
    });
  }

  function disconnect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    isConnected.value = false;
  }

  function scheduleReconnect() {
    if (reconnectTimeout) return;

    const delay = getReconnectDelay();
    reconnectAttempts.value++;

    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.value})`);

    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null;
      if (isOnline.value && authStore.isAuthenticated) {
        connect();
      }
    }, delay);
  }

  async function triggerItemsPull(wishlistId?: string) {
    const replication = getReplicationState();
    if (replication?.items) {
      await replication.items.reSync();
    }
  }

  async function triggerWishlistsPull() {
    const replication = getReplicationState();
    if (replication?.wishlists) {
      await replication.wishlists.reSync();
    }
  }

  async function triggerMarksPull() {
    const replication = getReplicationState();
    if (replication?.marks) {
      await replication.marks.reSync();
    }
  }

  // Auto-connect when authenticated and online
  watch(
    () => authStore.isAuthenticated,
    (authenticated) => {
      if (authenticated && isOnline.value) {
        connect();
      } else {
        disconnect();
      }
    }
  );

  // Reconnect when coming back online
  watch(isOnline, (online) => {
    if (online && authStore.isAuthenticated) {
      connect();
    } else {
      disconnect();
    }
  });

  onMounted(() => {
    if (authStore.isAuthenticated && isOnline.value) {
      connect();
    }
  });

  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    lastEventTime,
    reconnectAttempts,
    connect,
    disconnect
  };
}
```

### 4.2 Replication State Access

```typescript
// /services/frontend/src/services/rxdb/replication.ts

// Add export for accessing replication state
let replicationState: {
  wishlists: RxReplicationState<any, any> | null;
  items: RxReplicationState<any, any> | null;
  marks: RxReplicationState<any, any> | null;
} | null = null;

export function getReplicationState() {
  return replicationState;
}

// In setupReplication function:
export function setupReplication(db: WishWithMeDatabase) {
  // ... existing setup ...

  replicationState = {
    wishlists: wishlistReplication,
    items: itemReplication,
    marks: markReplication
  };

  return {
    // ... existing return ...
    getState: () => replicationState
  };
}
```

### 4.3 App Integration

```typescript
// /services/frontend/src/App.vue

<script setup lang="ts">
import { useRealtimeSync } from '@/composables/useRealtimeSync';

// Initialize SSE connection when app loads
const { isConnected } = useRealtimeSync();
</script>
```

### 4.4 Optional: Connection Status in UI

```vue
<!-- /services/frontend/src/components/SyncStatus.vue -->
<!-- Add SSE status to existing sync indicator -->

<script setup lang="ts">
import { useRealtimeSync } from '@/composables/useRealtimeSync';

const { isConnected: sseConnected } = useRealtimeSync();
</script>

<template>
  <q-icon
    :name="sseConnected ? 'cloud_done' : 'cloud_off'"
    :color="sseConnected ? 'positive' : 'grey'"
  >
    <q-tooltip>
      {{ sseConnected ? $t('sync.realtime') : $t('sync.polling') }}
    </q-tooltip>
  </q-icon>
</template>
```

---

## 5. Nginx Configuration

SSE requires disabling buffering. Update nginx config:

```nginx
# /etc/nginx/sites-available/wishwithme

location /api/v1/events/stream {
    proxy_pass http://core-api:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;  # 24 hours
    chunked_transfer_encoding off;
}
```

---

## 6. i18n Translations

### English (en/index.ts)

```typescript
sync: {
  // ... existing ...
  realtime: 'Real-time sync active',
  polling: 'Periodic sync',
  reconnecting: 'Reconnecting...',
}
```

### Russian (ru/index.ts)

```typescript
sync: {
  // ... existing ...
  realtime: 'Синхронизация в реальном времени',
  polling: 'Периодическая синхронизация',
  reconnecting: 'Переподключение...',
}
```

---

## 7. Testing

### 7.1 Backend Tests

```python
# /services/core-api/tests/test_events.py

import pytest
from httpx import AsyncClient
from app.services.events import event_manager, ServerEvent

@pytest.mark.asyncio
async def test_event_channel_connect_disconnect():
    """Test user can connect and disconnect from event channel."""
    user_id = uuid4()

    queue = await event_manager.connect(user_id)
    assert event_manager.is_connected(user_id)

    await event_manager.disconnect(user_id)
    assert not event_manager.is_connected(user_id)

@pytest.mark.asyncio
async def test_event_publish():
    """Test events are delivered to connected users."""
    user_id = uuid4()

    queue = await event_manager.connect(user_id)

    event = ServerEvent(event="test", data={"foo": "bar"})
    delivered = await event_manager.publish(user_id, event)

    assert delivered
    received = await queue.get()
    assert received.event == "test"
    assert received.data == {"foo": "bar"}

@pytest.mark.asyncio
async def test_sse_endpoint(client: AsyncClient, auth_headers):
    """Test SSE endpoint streams events."""
    # This requires special handling for streaming responses
    pass
```

### 7.2 Manual Testing

```bash
# Test SSE endpoint with curl
curl -N -H "Cookie: session=..." https://api.wishwith.me/api/v1/events/stream

# Should see:
# event: sync:ping
# data: {"timestamp":"2026-01-26T12:00:00Z"}
#
# (after item resolution)
# event: items:resolved
# data: {"id":"abc","wishlist_id":"xyz","status":"resolved","title":"iPhone"}
```

### 7.3 Integration Test

1. Open app in browser, login
2. Open Network tab, filter by EventStream
3. Verify SSE connection established
4. Add item by URL in another tab or device
5. Watch original tab - item should resolve without refresh
6. Check Console for `[SSE] items:resolved` logs

---

## 8. Scaling Considerations

### Current (Single Instance - Montreal)

In-memory `EventChannelManager` works fine:
- One FastAPI instance
- All users connect to same instance
- Events delivered directly via memory queue

### Future (Multi-Instance)

When scaling to multiple backend instances:

1. **Redis Pub/Sub**
```python
# Replace in-memory queue with Redis pub/sub
import aioredis

class RedisEventChannelManager:
    async def publish(self, user_id: UUID, event: ServerEvent):
        await redis.publish(f"events:{user_id}", event.format())

    async def subscribe(self, user_id: UUID):
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"events:{user_id}")
        async for message in pubsub.listen():
            yield message
```

2. **Sticky Sessions**
Alternative: Use load balancer sticky sessions so user always hits same instance.

---

## 9. Deliverables Checklist

### Backend
- [ ] `app/services/events.py` - EventChannelManager
- [ ] `app/routers/events.py` - SSE endpoint
- [ ] Integration in `items.py` - publish on resolve
- [ ] Integration in `sync.py` - publish on push
- [ ] Router registration in `main.py`
- [ ] Unit tests for event manager

### Frontend
- [ ] `composables/useRealtimeSync.ts` - EventSource composable
- [ ] Update `services/rxdb/replication.ts` - expose reSync
- [ ] Integration in `App.vue` - initialize SSE
- [ ] Optional: SSE status in `SyncStatus.vue`
- [ ] i18n translations (en, ru)

### Infrastructure
- [ ] Nginx SSE configuration
- [ ] Test on Montreal server

### Documentation
- [ ] Update `docs/08-phases.md` with Phase 6 items
- [ ] Update `docs/05-offline-sync.md` with SSE reference

---

## 10. Success Criteria

1. **Real-time item resolution**: User adds item by URL → resolution completes → item updates in UI without refresh
2. **Cross-device sync**: User edits on device A → appears on device B within seconds
3. **Connection resilience**: Network drops → reconnects automatically when online
4. **Graceful degradation**: SSE unavailable → app still works via manual sync
5. **No duplicate connections**: User opens multiple tabs → single SSE connection per user
