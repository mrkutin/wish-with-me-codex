# Offline & Sync Strategy

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │  RxDB (IndexedDB)                               │    │
│  │  - Reactive queries (auto-updating UI)          │    │
│  │  - Offline-first data storage                   │    │
│  │  - Built-in replication protocol                │    │
│  └───────────────────┬─────────────────────────────┘    │
└──────────────────────┼──────────────────────────────────┘
                       │ HTTP replication
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                      │
│  ┌─────────────────────────────────────────────────┐    │
│  │  PostgreSQL                                     │    │
│  │  - ACID transactions                            │    │
│  │  - Relational integrity                         │    │
│  │  - Complex queries                              │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 2. RxDB Collections

| Collection | Purpose | Indexes |
|------------|---------|---------|
| `wishlists` | User's wishlists | `owner_id`, `updated_at` |
| `items` | Wishlist items | `wishlist_id`, `status`, `updated_at` |
| `marks` | Item marks (viewer only) | `item_id`, `user_id` |

---

## 3. Replication Protocol

### 3.1 Pull Endpoint

```
GET /api/v1/sync/pull/{collection}
  ?checkpoint_updated_at=2026-01-21T10:00:00Z
  &checkpoint_id=uuid
  &limit=50

Response:
{
  "documents": [...],
  "checkpoint": {
    "updated_at": "2026-01-21T11:00:00Z",
    "id": "uuid"
  }
}
```

### 3.2 Push Endpoint

```
POST /api/v1/sync/push/{collection}

Body:
{
  "documents": [
    { "id": "uuid", "title": "Updated", "updated_at": "...", "_deleted": false }
  ]
}

Response:
{
  "conflicts": []
}
```

### 3.3 Replication Setup

```typescript
// /services/frontend/src/services/rxdb/replication.ts

import { replicateRxCollection } from 'rxdb/plugins/replication';
import { Subject } from 'rxjs';
import type { WishWithMeDatabase } from './index';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/services/api/client';

interface ReplicationCheckpoint {
  updated_at: string;
  id: string;
}

export function setupReplication(db: WishWithMeDatabase) {
  const authStore = useAuthStore();
  const pullStream$ = new Subject<void>();

  const wishlistReplication = replicateRxCollection<any, ReplicationCheckpoint>({
    collection: db.wishlists,
    replicationIdentifier: 'wishlists-sync',
    deletedField: '_deleted',
    live: true,
    retryTime: 5000,
    waitForLeadership: true,

    push: {
      async handler(docs) {
        const response = await api.post('/api/v1/sync/push/wishlists', {
          documents: docs.map(d => d.newDocumentState)
        });
        return response.data.conflicts || [];
      },
      batchSize: 10
    },

    pull: {
      async handler(checkpoint, batchSize) {
        const response = await api.get('/api/v1/sync/pull/wishlists', {
          params: {
            checkpoint_updated_at: checkpoint?.updated_at,
            checkpoint_id: checkpoint?.id,
            limit: batchSize
          }
        });
        return {
          documents: response.data.documents,
          checkpoint: response.data.checkpoint
        };
      },
      batchSize: 50,
      stream$: pullStream$.asObservable()
    }
  });

  // Trigger pull when coming online
  window.addEventListener('online', () => pullStream$.next());

  return {
    wishlistReplication,
    triggerPull: () => pullStream$.next(),
    cancel: () => wishlistReplication.cancel()
  };
}
```

---

## 4. Conflict Resolution

### 4.1 Strategy: Last-Write-Wins (LWW)

```typescript
// Conflict resolution based on updated_at
const resolveConflict = (clientDoc: any, serverDoc: any) => {
  const clientTime = new Date(clientDoc.updated_at).getTime();
  const serverTime = new Date(serverDoc.updated_at).getTime();

  return clientTime > serverTime ? clientDoc : serverDoc;
};
```

### 4.2 Conflict Notification

When a conflict is resolved, notify the user:

```typescript
Notify.create({
  message: 'Некоторые изменения были обновлены',
  caption: 'На сервере найдена более новая версия',
  icon: 'sync_problem',
  color: 'warning'
});
```

---

## 5. Offline Indicators

### 5.1 OfflineBanner Component

| State | Message (RU) | Message (EN) | Color |
|-------|--------------|--------------|-------|
| Offline | Нет подключения | You're offline | warning |
| Syncing | Синхронизация... | Syncing... | info |
| Sync error | Ошибка синхронизации | Couldn't sync | negative |
| Back online | Подключение восстановлено | Back online! | positive |

### 5.2 SyncStatus Component (Header)

| State | Icon | Badge |
|-------|------|-------|
| Synced | `cloud-check` | None |
| Pending | `cloud-arrow-up` | Count |
| Syncing | `cloud` (animated) | None |
| Error | `cloud-x` | `!` |

### 5.3 Composable

```typescript
// /services/frontend/src/composables/useSync.ts

import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useOnline } from '@vueuse/core';

export function useSync() {
  const isOnline = useOnline();
  const isSyncing = ref(false);
  const pendingCount = ref(0);
  const syncError = ref<string | null>(null);

  async function triggerSync() {
    if (!isOnline.value) return;
    syncError.value = null;
    // Trigger replication pull
  }

  return {
    isOnline,
    isSyncing: computed(() => isSyncing.value),
    pendingCount: computed(() => pendingCount.value),
    syncError: computed(() => syncError.value),
    triggerSync
  };
}
```

---

## 6. Service Worker

```typescript
// /services/frontend/src-pwa/custom-service-worker.ts

import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, CacheFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';

declare const self: ServiceWorkerGlobalScope;

// Precache static assets
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// API calls - Network First
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 60 * 60 * 24
      })
    ]
  })
);

// Images - Cache First
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'image-cache',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 200,
        maxAgeSeconds: 60 * 60 * 24 * 30
      })
    ]
  })
);

// Background sync event
self.addEventListener('sync', (event) => {
  if (event.tag === 'wishlist-sync') {
    event.waitUntil(syncPendingChanges());
  }
});

async function syncPendingChanges() {
  // RxDB handles most sync, this is for edge cases
  console.log('Background sync triggered');
}
```

---

## 7. Offline Action Feedback

When user performs action while offline:

```typescript
// After creating wishlist offline
Notify.create({
  message: 'Список создан',
  caption: 'Синхронизируется при подключении',
  icon: 'cloud_off',
  color: 'info'
});

// After coming back online
Notify.create({
  message: 'Все изменения сохранены',
  icon: 'cloud_done',
  color: 'positive',
  timeout: 2000
});
```
