# Offline & Sync Strategy

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Architecture Overview

```
+-------------------------------------------------------------+
|  Browser                                                     |
|  +-----------------------------------------------------+    |
|  |  PouchDB (IndexedDB)                               |    |
|  |  - Native CouchDB sync protocol                    |    |
|  |  - Offline-first data storage                      |    |
|  |  - Live replication (real-time updates)            |    |
|  +------------------------+----------------------------+    |
+---------------------------+--------------------------------+
                            | Live sync (continuous)
                            v
+-------------------------------------------------------------+
|  Backend                                                     |
|  +-----------------------------------------------------+    |
|  |  CouchDB                                            |    |
|  |  - Document database                                |    |
|  |  - Native sync protocol                             |    |
|  |  - Conflict resolution via revisions                |    |
|  +-----------------------------------------------------+    |
+-------------------------------------------------------------+
```

**Key Benefits**:
- **Native sync protocol**: No custom HTTP endpoints needed
- **Real-time updates**: Live sync handles all changes automatically
- **Conflict resolution**: CouchDB revisions handle conflicts
- **Offline-first**: Full functionality without network

---

## 2. PouchDB Collections

All data is stored in a single PouchDB database with document types:

| Type | Purpose | Indexes |
|------|---------|---------|
| `user` | User profiles | `email` |
| `wishlist` | User's wishlists | `owner_id`, `access` |
| `item` | Wishlist items | `wishlist_id`, `status`, `access` |
| `mark` | Item marks (viewer only) | `item_id`, `marked_by` |
| `share` | Share links | `token`, `wishlist_id` |
| `notification` | User notifications | `user_id`, `read` |

---

## 3. Sync Protocol

### 3.1 Live Sync Setup

PouchDB syncs directly with CouchDB using native replication:

```typescript
// /services/frontend/src/services/pouchdb/sync.ts

import PouchDB from 'pouchdb-browser';

const localDB = new PouchDB('wishwithme_local');

const remoteDB = new PouchDB('https://api.wishwith.me/couchdb/wishwithme', {
  fetch: (url, opts) => {
    opts.headers.set('Authorization', `Bearer ${jwt}`);
    return fetch(url, opts);
  }
});

const sync = localDB.sync(remoteDB, {
  live: true,    // Continuous sync
  retry: true,   // Auto-reconnect on errors
  selector: {
    access: { $elemMatch: { $eq: userId } }  // Only user's documents
  }
});
```

### 3.2 Sync Events

```typescript
sync.on('change', (info) => {
  console.log('Sync change:', info.direction, info.change.docs.length);
  // UI auto-updates via PouchDB change listeners
});

sync.on('paused', (err) => {
  if (err) {
    console.error('Sync paused with error:', err);
  } else {
    console.log('Sync paused - up to date');
  }
});

sync.on('active', () => {
  console.log('Sync resumed');
});

sync.on('denied', (err) => {
  console.error('Sync denied (permission issue):', err);
});

sync.on('error', (err) => {
  console.error('Sync error:', err);
});
```

### 3.3 Filtered Replication

Users only sync documents they have access to:

```typescript
// Selector ensures only accessible documents sync
const sync = localDB.sync(remoteDB, {
  live: true,
  retry: true,
  selector: {
    access: { $elemMatch: { $eq: `user:${userId}` } }
  }
});
```

---

## 4. Conflict Resolution

### 4.1 CouchDB Revision System

CouchDB uses revisions (`_rev` field) for conflict detection:

```javascript
// Document with revision
{
  "_id": "wishlist:abc123",
  "_rev": "2-def456",  // Revision 2
  "title": "Birthday List",
  ...
}
```

### 4.2 Conflict Handling

When two users edit the same document offline:

1. Both create new revisions locally
2. On sync, CouchDB detects conflict
3. One revision becomes "winning" (deterministic)
4. Other revision stored as conflict
5. App can resolve conflicts explicitly

```typescript
// Check for conflicts
const doc = await localDB.get('wishlist:abc123', { conflicts: true });
if (doc._conflicts) {
  // Handle conflicts
  for (const rev of doc._conflicts) {
    const conflictDoc = await localDB.get('wishlist:abc123', { rev });
    // Merge or discard conflict
    await localDB.remove('wishlist:abc123', rev);
  }
}
```

### 4.3 Resolution Strategy: Last-Write-Wins

For simplicity, we use timestamp-based resolution:

```typescript
async function resolveConflict(docId: string) {
  const doc = await localDB.get(docId, { conflicts: true });
  if (!doc._conflicts?.length) return;

  // Get all versions
  const versions = [doc];
  for (const rev of doc._conflicts) {
    versions.push(await localDB.get(docId, { rev }));
  }

  // Sort by updated_at (newest first)
  versions.sort((a, b) =>
    new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  // Keep newest, delete others
  const winner = versions[0];
  for (const loser of versions.slice(1)) {
    await localDB.remove(docId, loser._rev);
  }
}
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

### 5.3 useSync Composable

```typescript
// /services/frontend/src/composables/useSync.ts

import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useOnline } from '@vueuse/core';
import { getSyncStatus, startSync, stopSync } from '@/services/pouchdb/sync';

export function useSync() {
  const isOnline = useOnline();
  const isSyncing = ref(false);
  const syncError = ref<Error | null>(null);
  const lastSync = ref<Date | null>(null);

  function updateStatus() {
    const status = getSyncStatus();
    isSyncing.value = status.isActive && !status.isPaused;
    syncError.value = status.error;
    lastSync.value = status.lastSync;
  }

  onMounted(() => {
    startSync();
    const interval = setInterval(updateStatus, 1000);
    return () => clearInterval(interval);
  });

  return {
    isOnline,
    isSyncing: computed(() => isSyncing.value),
    syncError: computed(() => syncError.value),
    lastSync: computed(() => lastSync.value)
  };
}
```

---

## 6. Service Worker

### 6.1 Important: CouchDB & OAuth Compatibility

The service worker's navigation fallback **must exclude `/couchdb/` and `/api/` paths**:

```javascript
// quasar.config.js
extendGenerateSWOptions(cfg) {
  cfg.navigateFallbackDenylist = [/^\/api\//, /^\/couchdb\//];
}
```

Without this, the service worker would intercept CouchDB sync requests.

### 6.2 Custom Service Worker

```typescript
// /services/frontend/src-pwa/custom-service-worker.ts

import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, CacheFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';

declare const self: ServiceWorkerGlobalScope;

// Precache static assets
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// API calls - Network First (not CouchDB - that's handled by PouchDB)
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/') && !url.pathname.includes('/couchdb/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    plugins: [
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

// After coming back online and sync completes
Notify.create({
  message: 'Все изменения сохранены',
  icon: 'cloud_done',
  color: 'positive',
  timeout: 2000
});
```

---

## 8. Real-Time Updates

### How PouchDB Live Sync Provides Real-Time Updates

Unlike SSE or WebSockets, PouchDB live sync is built into the database layer:

```
User A creates item locally
        |
        v
PouchDB syncs to CouchDB
        |
        v
CouchDB sends change to User B's PouchDB
        |
        v
User B's PouchDB triggers change event
        |
        v
Vue component re-renders
```

**Benefits over SSE**:
- No separate real-time connection to maintain
- Works with offline-first architecture
- Automatic reconnection built-in
- Bi-directional (both push and pull)

### Reactive Queries with PouchDB Changes

```typescript
// In Vue composable
const db = getDatabase();

// Watch for changes to items in this wishlist
db.changes({
  since: 'now',
  live: true,
  include_docs: true,
  selector: {
    type: 'item',
    wishlist_id: wishlistId
  }
}).on('change', (change) => {
  // Refetch items when any change occurs
  fetchItems();
});
```

---

## 9. Data Flow Diagrams

### 9.1 Create Item Flow (Online)

```
User adds item
      |
      v
Save to PouchDB (immediate)
      |
      v
UI updates instantly
      |
      v (background)
PouchDB syncs to CouchDB
      |
      v
Item resolver watches _changes
      |
      v
Resolver updates item in CouchDB
      |
      v
CouchDB syncs back to PouchDB
      |
      v
UI shows resolved item
```

### 9.2 Create Item Flow (Offline)

```
User adds item
      |
      v
Save to PouchDB (immediate)
      |
      v
UI updates instantly
      |
      v
[Network unavailable - sync queued]
      |
      v
User goes online
      |
      v
PouchDB auto-syncs to CouchDB
      |
      v
Item resolver processes item
      |
      v
Resolved item syncs back
```

---

## 10. Best Practices

### 10.1 Always Work with Local Database

```typescript
// GOOD: Write to local, sync handles the rest
await localDB.put(doc);

// BAD: Don't call API for data changes
await api.post('/wishlists', data);  // Not needed with CouchDB
```

### 10.2 Use Change Listeners for Reactivity

```typescript
// GOOD: Listen for changes
db.changes({ live: true, since: 'now' })
  .on('change', () => refetchData());

// BAD: Don't poll for changes
setInterval(() => refetchData(), 5000);
```

### 10.3 Handle Sync Errors Gracefully

```typescript
sync.on('error', (err) => {
  if (err.status === 401) {
    // Token expired, re-authenticate
    authStore.refreshToken();
  } else {
    // Show error to user
    showSyncError(err);
  }
});
```

### 10.4 Clean Up On Logout

```typescript
async function logout() {
  stopSync();           // Stop live sync
  await localDB.destroy();  // Delete local data
  // ... clear auth state
}
```
