# Frontend Specification

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Project Structure

```
/services/frontend/
├── .quasar/                      # Quasar build artifacts (gitignored)
├── public/
│   ├── favicon.ico
│   └── icons/                    # PWA icons (all sizes)
│       ├── icon-128x128.png
│       ├── icon-192x192.png
│       ├── icon-256x256.png
│       ├── icon-384x384.png
│       ├── icon-512x512.png
│       └── maskable-icon.png
├── src/
│   ├── App.vue                   # Root component
│   ├── index.template.html       # HTML template
│   │
│   ├── assets/
│   │   └── styles/
│   │       └── quasar.variables.sass
│   │
│   ├── boot/                     # Quasar boot files (plugins)
│   │   ├── axios.ts              # Axios configuration
│   │   ├── i18n.ts               # Vue-i18n setup
│   │   ├── pouchdb.ts            # PouchDB database init
│   │   └── auth.ts               # Auth initialization
│   │
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginForm.vue
│   │   │   ├── RegisterForm.vue
│   │   │   └── SocialLoginButtons.vue
│   │   ├── wishlist/
│   │   │   ├── WishlistCard.vue
│   │   │   ├── WishlistForm.vue
│   │   │   ├── WishlistList.vue
│   │   │   └── ShareDialog.vue
│   │   ├── item/
│   │   │   ├── ItemCard.vue
│   │   │   ├── ItemForm.vue
│   │   │   ├── ItemUrlInput.vue
│   │   │   ├── ItemResolvingState.vue
│   │   │   └── MarkButton.vue
│   │   ├── profile/
│   │   │   ├── ProfileForm.vue
│   │   │   ├── AvatarUpload.vue
│   │   │   └── SocialLinksForm.vue
│   │   ├── notifications/
│   │   │   ├── NotificationBell.vue
│   │   │   ├── NotificationList.vue
│   │   │   └── NotificationItem.vue
│   │   └── common/
│   │       ├── OfflineBanner.vue
│   │       ├── SyncStatus.vue
│   │       └── QRCodeDialog.vue
│   │
│   ├── composables/              # Vue 3 composables (hooks)
│   │   ├── useAuth.ts
│   │   ├── useWishlists.ts
│   │   ├── useItems.ts
│   │   ├── useSync.ts
│   │   ├── useOffline.ts
│   │   └── useNotifications.ts
│   │
│   ├── css/
│   │   ├── app.sass
│   │   └── quasar.variables.sass
│   │
│   ├── i18n/
│   │   ├── index.ts
│   │   ├── ru/
│   │   │   └── index.ts
│   │   └── en/
│   │       └── index.ts
│   │
│   ├── layouts/
│   │   ├── MainLayout.vue        # App shell with navigation
│   │   └── AuthLayout.vue        # Layout for login/register
│   │
│   ├── pages/
│   │   ├── IndexPage.vue         # Home/landing
│   │   ├── LoginPage.vue
│   │   ├── RegisterPage.vue
│   │   ├── PasswordResetPage.vue
│   │   ├── PasswordResetConfirmPage.vue
│   │   ├── OAuthCallbackPage.vue
│   │   ├── WishlistsPage.vue
│   │   ├── WishlistDetailPage.vue
│   │   ├── SharedWishlistPage.vue
│   │   ├── SharedPreviewPage.vue
│   │   ├── ProfilePage.vue
│   │   ├── SettingsPage.vue
│   │   ├── NotificationsPage.vue
│   │   └── ErrorNotFound.vue
│   │
│   ├── router/
│   │   ├── index.ts
│   │   └── routes.ts
│   │
│   ├── services/
│   │   ├── api/
│   │   │   ├── client.ts         # Axios instance
│   │   │   ├── auth.ts
│   │   │   └── share.ts
│   │   └── pouchdb/
│   │       ├── index.ts          # PouchDB database instance
│   │       ├── sync.ts           # Live sync with CouchDB
│   │       └── documents.ts      # Document CRUD helpers
│   │
│   ├── stores/                   # Pinia stores
│   │   ├── index.ts
│   │   ├── auth.ts
│   │   ├── sync.ts
│   │   └── notifications.ts
│   │
│   ├── types/
│   │   ├── documents.ts          # PouchDB document types
│   │   ├── api.ts
│   │   └── sync.ts
│   │
│   └── utils/
│       ├── constants.ts
│       ├── formatters.ts
│       ├── validators.ts
│       ├── imageUtils.ts
│       └── urlUtils.ts
│
├── src-pwa/                      # PWA-specific files
│   ├── custom-service-worker.ts  # Custom SW logic
│   ├── register-service-worker.ts
│   └── pwa-env.d.ts
│
├── .env.example
├── .env
├── package.json
├── quasar.config.js              # Quasar configuration (Webpack)
├── tsconfig.json
└── README.md
```

---

## 2. Dependencies

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "quasar": "^2.14.0",
    "pinia": "^2.1.0",
    "vue-router": "^4.3.0",
    "vue-i18n": "^9.10.0",
    "axios": "^1.6.0",
    "pouchdb-browser": "^8.0.0",
    "pouchdb-find": "^8.0.0",
    "@vueuse/core": "^10.9.0",
    "date-fns": "^3.3.0",
    "qrcode": "^1.5.0",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "@quasar/app-webpack": "^3.12.0",
    "@quasar/extras": "^1.16.0",
    "typescript": "^5.3.0",
    "@types/node": "^20.11.0",
    "@types/pouchdb-browser": "^6.1.0",
    "@types/pouchdb-find": "^7.3.0",
    "@vue/test-utils": "^2.4.0",
    "vitest": "^1.2.0",
    "@vitest/coverage-v8": "^1.2.0",
    "happy-dom": "^13.0.0",
    "workbox-build": "^7.0.0",
    "workbox-core": "^7.0.0",
    "workbox-precaching": "^7.0.0",
    "workbox-routing": "^7.0.0",
    "workbox-strategies": "^7.0.0"
  }
}
```

---

## 3. Quasar Configuration

```javascript
// /services/frontend/quasar.config.js

const { configure } = require('quasar/wrappers');

module.exports = configure(function (/* ctx */) {
  return {
    boot: ['i18n', 'axios', 'pouchdb', 'auth'],

    css: ['app.sass'],

    extras: [
      'roboto-font',
      'material-icons',
      'mdi-v7'
    ],

    build: {
      vueRouterMode: 'history',
      env: {
        API_URL: process.env.API_URL || 'https://api.wishwith.me',
        COUCHDB_URL: process.env.COUCHDB_URL || 'https://api.wishwith.me/couchdb',
      },
    },

    devServer: {
      open: true,
      port: 9000
    },

    framework: {
      config: {
        brand: {
          primary: '#6366f1',
          secondary: '#26A69A',
          accent: '#9C27B0',
          dark: '#1d1d1d',
          positive: '#1a9f38',
          negative: '#C10015',
          info: '#31CCEC',
          warning: '#F2C037'
        },
        notify: {
          position: 'top',
          timeout: 3000
        },
        loading: {
          spinnerColor: 'primary'
        }
      },
      plugins: [
        'Notify',
        'Dialog',
        'Loading',
        'LocalStorage',
        'SessionStorage',
        'BottomSheet'
      ]
    },

    animations: 'all',

    pwa: {
      workboxMode: 'injectManifest',
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
      useCredentialsForManifestTag: false,
      extendGenerateSWOptions(cfg) {
        cfg.skipWaiting = true;
        cfg.clientsClaim = true;
        // Exclude /api/ from navigation fallback for OAuth redirects
        cfg.navigateFallbackDenylist = [/^\/api\//, /^\/couchdb\//];
      },
      manifest: {
        name: 'Wish With Me',
        short_name: 'WishWithMe',
        description: 'Create and share wishlists with friends',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#ffffff',
        theme_color: '#6366f1',
        start_url: '/',
        icons: [
          { src: 'icons/icon-128x128.png', sizes: '128x128', type: 'image/png' },
          { src: 'icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-256x256.png', sizes: '256x256', type: 'image/png' },
          { src: 'icons/icon-384x384.png', sizes: '384x384', type: 'image/png' },
          { src: 'icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/maskable-icon.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
        ]
      }
    }
  };
});
```

---

## 4. Router Configuration

```typescript
// /services/frontend/src/router/routes.ts

import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', name: 'home', component: () => import('pages/IndexPage.vue') },
      {
        path: 'wishlists',
        name: 'wishlists',
        component: () => import('pages/WishlistsPage.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'wishlists/:id',
        name: 'wishlist-detail',
        component: () => import('pages/WishlistDetailPage.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('pages/ProfilePage.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('pages/SettingsPage.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'notifications',
        name: 'notifications',
        component: () => import('pages/NotificationsPage.vue'),
        meta: { requiresAuth: true }
      },
    ]
  },
  {
    path: '/',
    component: () => import('layouts/AuthLayout.vue'),
    children: [
      { path: 'login', name: 'login', component: () => import('pages/LoginPage.vue') },
      { path: 'register', name: 'register', component: () => import('pages/RegisterPage.vue') },
      { path: 'password-reset', name: 'password-reset', component: () => import('pages/PasswordResetPage.vue') },
      { path: 'password-reset/:token', name: 'password-reset-confirm', component: () => import('pages/PasswordResetConfirmPage.vue') },
      { path: 'auth/callback/:provider', name: 'oauth-callback', component: () => import('pages/OAuthCallbackPage.vue') },
    ]
  },
  {
    path: '/s/:token',
    name: 'shared-wishlist',
    component: () => import('pages/SharedWishlistPage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/s/:token/preview',
    name: 'shared-preview',
    component: () => import('pages/SharedPreviewPage.vue')
  },
  {
    path: '/u/:slug',
    name: 'public-profile',
    component: () => import('pages/PublicProfilePage.vue')
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue')
  }
];

export default routes;
```

---

## 5. PouchDB Setup

### 5.1 Database Service

```typescript
// /services/frontend/src/services/pouchdb/index.ts

import PouchDB from 'pouchdb-browser';
import PouchDBFind from 'pouchdb-find';

PouchDB.plugin(PouchDBFind);

let localDB: PouchDB.Database | null = null;

export function getDatabase(): PouchDB.Database {
  if (!localDB) {
    throw new Error('Database not initialized. Call initDatabase first.');
  }
  return localDB;
}

export async function initDatabase(): Promise<PouchDB.Database> {
  if (localDB) {
    return localDB;
  }

  localDB = new PouchDB('wishwithme_local');

  // Create indexes for common queries
  await localDB.createIndex({
    index: { fields: ['type', 'access'] }
  });

  await localDB.createIndex({
    index: { fields: ['type', 'wishlist_id', 'sort_order'] }
  });

  await localDB.createIndex({
    index: { fields: ['type', 'status'] }
  });

  return localDB;
}

export async function destroyDatabase(): Promise<void> {
  if (localDB) {
    await localDB.destroy();
    localDB = null;
  }
}
```

### 5.2 Sync Service

```typescript
// /services/frontend/src/services/pouchdb/sync.ts

import PouchDB from 'pouchdb-browser';
import { getDatabase } from './index';
import { useAuthStore } from '@/stores/auth';

let syncHandler: PouchDB.Replication.Sync<{}> | null = null;

export interface SyncStatus {
  isActive: boolean;
  isPaused: boolean;
  lastSync: Date | null;
  error: Error | null;
}

const syncStatus: SyncStatus = {
  isActive: false,
  isPaused: false,
  lastSync: null,
  error: null
};

export function getSyncStatus(): SyncStatus {
  return { ...syncStatus };
}

export async function startSync(): Promise<void> {
  const authStore = useAuthStore();

  if (!authStore.isAuthenticated || !authStore.token) {
    console.log('[Sync] Not authenticated, skipping sync');
    return;
  }

  if (syncHandler) {
    console.log('[Sync] Already running');
    return;
  }

  const localDB = getDatabase();
  const couchdbUrl = process.env.COUCHDB_URL || 'https://api.wishwith.me/couchdb';
  const userId = authStore.user?.id;

  const remoteDB = new PouchDB(`${couchdbUrl}/wishwithme`, {
    fetch: (url, opts) => {
      (opts!.headers as Headers).set('Authorization', `Bearer ${authStore.token}`);
      return fetch(url, opts);
    }
  });

  // Live sync with filtered replication
  syncHandler = localDB.sync(remoteDB, {
    live: true,
    retry: true,
    // Only sync documents the user has access to
    selector: {
      access: { $elemMatch: { $eq: userId } }
    }
  });

  syncHandler.on('change', (info) => {
    console.log('[Sync] Change:', info.direction, info.change.docs.length, 'docs');
    syncStatus.lastSync = new Date();
    syncStatus.error = null;
  });

  syncHandler.on('paused', (err) => {
    syncStatus.isPaused = true;
    if (err) {
      console.error('[Sync] Paused with error:', err);
      syncStatus.error = err;
    }
  });

  syncHandler.on('active', () => {
    syncStatus.isActive = true;
    syncStatus.isPaused = false;
    console.log('[Sync] Active');
  });

  syncHandler.on('denied', (err) => {
    console.error('[Sync] Denied:', err);
    syncStatus.error = err;
  });

  syncHandler.on('complete', (info) => {
    console.log('[Sync] Complete:', info);
    syncStatus.isActive = false;
  });

  syncHandler.on('error', (err) => {
    console.error('[Sync] Error:', err);
    syncStatus.error = err;
    syncStatus.isActive = false;
  });

  syncStatus.isActive = true;
  console.log('[Sync] Started live sync');
}

export function stopSync(): void {
  if (syncHandler) {
    syncHandler.cancel();
    syncHandler = null;
    syncStatus.isActive = false;
    syncStatus.isPaused = false;
    console.log('[Sync] Stopped');
  }
}
```

### 5.3 Document Helpers

```typescript
// /services/frontend/src/services/pouchdb/documents.ts

import { getDatabase } from './index';
import { v4 as uuidv4 } from 'uuid';
import type { Wishlist, Item, Mark } from '@/types/documents';

// Wishlist operations
export async function createWishlist(
  userId: string,
  data: { title: string; description?: string; icon?: string }
): Promise<Wishlist> {
  const db = getDatabase();
  const now = new Date().toISOString();

  const doc: Wishlist = {
    _id: `wishlist:${uuidv4()}`,
    type: 'wishlist',
    owner_id: userId,
    title: data.title,
    description: data.description || '',
    icon: data.icon || '',
    item_count: 0,
    created_at: now,
    updated_at: now,
    deleted_at: null,
    access: [userId]
  };

  await db.put(doc);
  return doc;
}

export async function getWishlists(userId: string): Promise<Wishlist[]> {
  const db = getDatabase();
  const result = await db.find({
    selector: {
      type: 'wishlist',
      access: { $elemMatch: { $eq: userId } },
      deleted_at: { $eq: null }
    },
    sort: [{ updated_at: 'desc' }]
  });
  return result.docs as Wishlist[];
}

export async function updateWishlist(
  id: string,
  updates: Partial<Wishlist>
): Promise<Wishlist> {
  const db = getDatabase();
  const doc = await db.get(id) as Wishlist;

  const updated = {
    ...doc,
    ...updates,
    updated_at: new Date().toISOString()
  };

  await db.put(updated);
  return updated;
}

export async function deleteWishlist(id: string): Promise<void> {
  const db = getDatabase();
  const doc = await db.get(id) as Wishlist;

  await db.put({
    ...doc,
    deleted_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  });
}

// Item operations
export async function createItem(
  userId: string,
  wishlistId: string,
  data: Partial<Item>
): Promise<Item> {
  const db = getDatabase();
  const now = new Date().toISOString();

  // Get wishlist to copy access array
  const wishlist = await db.get(wishlistId) as Wishlist;

  // Count existing items for sort order
  const existingItems = await db.find({
    selector: {
      type: 'item',
      wishlist_id: wishlistId,
      deleted_at: { $eq: null }
    }
  });

  const doc: Item = {
    _id: `item:${uuidv4()}`,
    type: 'item',
    wishlist_id: wishlistId,
    owner_id: userId,
    title: data.title || 'Loading...',
    description: data.description || null,
    price_amount: data.price_amount || null,
    price_currency: data.price_currency || null,
    source_url: data.source_url || null,
    image_url: null,
    image_base64: data.image_base64 || null,
    status: data.source_url ? 'pending' : 'manual',
    quantity: data.quantity ?? 1,
    marked_quantity: 0,
    resolution_error: null,
    sort_order: existingItems.docs.length,
    created_at: now,
    updated_at: now,
    deleted_at: null,
    access: wishlist.access
  };

  await db.put(doc);

  // Update wishlist item_count
  await updateWishlist(wishlistId, {
    item_count: wishlist.item_count + 1
  });

  return doc;
}

export async function getItems(wishlistId: string): Promise<Item[]> {
  const db = getDatabase();
  const result = await db.find({
    selector: {
      type: 'item',
      wishlist_id: wishlistId,
      deleted_at: { $eq: null }
    },
    sort: [{ sort_order: 'asc' }]
  });
  return result.docs as Item[];
}

export async function updateItem(
  id: string,
  updates: Partial<Item>
): Promise<Item> {
  const db = getDatabase();
  const doc = await db.get(id) as Item;

  const updated = {
    ...doc,
    ...updates,
    updated_at: new Date().toISOString()
  };

  await db.put(updated);
  return updated;
}

export async function deleteItem(id: string): Promise<void> {
  const db = getDatabase();
  const doc = await db.get(id) as Item;

  await db.put({
    ...doc,
    deleted_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  });

  // Update wishlist item_count
  const wishlist = await db.get(doc.wishlist_id) as Wishlist;
  await updateWishlist(doc.wishlist_id, {
    item_count: Math.max(0, wishlist.item_count - 1)
  });
}

// Mark operations (for viewers)
export async function createMark(
  viewerId: string,
  item: Item,
  wishlist: Wishlist,
  quantity: number
): Promise<Mark> {
  const db = getDatabase();
  const now = new Date().toISOString();

  // Access includes all viewers EXCEPT owner (surprise mode)
  const viewerAccess = wishlist.access.filter(id => id !== wishlist.owner_id);

  const doc: Mark = {
    _id: `mark:${uuidv4()}`,
    type: 'mark',
    item_id: item._id,
    wishlist_id: wishlist._id,
    owner_id: wishlist.owner_id,
    marked_by: viewerId,
    quantity,
    created_at: now,
    updated_at: now,
    access: viewerAccess
  };

  await db.put(doc);

  // Update item marked_quantity
  await updateItem(item._id, {
    marked_quantity: item.marked_quantity + quantity
  });

  return doc;
}

export async function getMarks(itemId: string): Promise<Mark[]> {
  const db = getDatabase();
  const result = await db.find({
    selector: {
      type: 'mark',
      item_id: itemId
    }
  });
  return result.docs as Mark[];
}
```

---

## 6. Vue Composables

### 6.1 useWishlists

```typescript
// /services/frontend/src/composables/useWishlists.ts

import { ref, onMounted, onUnmounted, computed } from 'vue';
import { getDatabase } from '@/services/pouchdb';
import { createWishlist, getWishlists, deleteWishlist } from '@/services/pouchdb/documents';
import { useAuthStore } from '@/stores/auth';
import type { Wishlist } from '@/types/documents';

export function useWishlists() {
  const authStore = useAuthStore();
  const wishlists = ref<Wishlist[]>([]);
  const loading = ref(true);
  const error = ref<Error | null>(null);

  let changesHandler: PouchDB.Core.Changes<{}> | null = null;

  async function fetchWishlists() {
    if (!authStore.user) return;

    try {
      wishlists.value = await getWishlists(authStore.user.id);
    } catch (err) {
      error.value = err as Error;
    }
  }

  async function create(data: { title: string; description?: string }) {
    if (!authStore.user) throw new Error('Not authenticated');

    const wishlist = await createWishlist(authStore.user.id, data);
    await fetchWishlists();
    return wishlist;
  }

  async function remove(id: string) {
    await deleteWishlist(id);
    await fetchWishlists();
  }

  onMounted(async () => {
    try {
      await fetchWishlists();

      // Watch for changes (live updates from sync)
      const db = getDatabase();
      changesHandler = db.changes({
        since: 'now',
        live: true,
        include_docs: true,
        selector: { type: 'wishlist' }
      }).on('change', () => {
        fetchWishlists();
      });
    } catch (err) {
      error.value = err as Error;
    } finally {
      loading.value = false;
    }
  });

  onUnmounted(() => {
    if (changesHandler) {
      changesHandler.cancel();
    }
  });

  return {
    wishlists: computed(() => wishlists.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    create,
    remove,
    refetch: fetchWishlists
  };
}
```

### 6.2 useItems

```typescript
// /services/frontend/src/composables/useItems.ts

import { ref, onMounted, onUnmounted, computed } from 'vue';
import { getDatabase } from '@/services/pouchdb';
import { createItem, getItems, updateItem, deleteItem } from '@/services/pouchdb/documents';
import { useAuthStore } from '@/stores/auth';
import type { Item } from '@/types/documents';

export function useItems(wishlistId: string) {
  const authStore = useAuthStore();
  const items = ref<Item[]>([]);
  const loading = ref(true);
  const error = ref<Error | null>(null);

  let changesHandler: PouchDB.Core.Changes<{}> | null = null;

  async function fetchItems() {
    try {
      items.value = await getItems(wishlistId);
    } catch (err) {
      error.value = err as Error;
    }
  }

  async function create(data: Partial<Item>) {
    if (!authStore.user) throw new Error('Not authenticated');

    const item = await createItem(authStore.user.id, wishlistId, data);
    await fetchItems();
    return item;
  }

  async function update(id: string, updates: Partial<Item>) {
    const item = await updateItem(id, updates);
    await fetchItems();
    return item;
  }

  async function remove(id: string) {
    await deleteItem(id);
    await fetchItems();
  }

  onMounted(async () => {
    try {
      await fetchItems();

      // Watch for changes (live updates from sync)
      const db = getDatabase();
      changesHandler = db.changes({
        since: 'now',
        live: true,
        include_docs: true,
        selector: { type: 'item', wishlist_id: wishlistId }
      }).on('change', () => {
        fetchItems();
      });
    } catch (err) {
      error.value = err as Error;
    } finally {
      loading.value = false;
    }
  });

  onUnmounted(() => {
    if (changesHandler) {
      changesHandler.cancel();
    }
  });

  return {
    items: computed(() => items.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    create,
    update,
    remove,
    refetch: fetchItems
  };
}
```

### 6.3 useSync

```typescript
// /services/frontend/src/composables/useSync.ts

import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useOnline } from '@vueuse/core';
import { startSync, stopSync, getSyncStatus } from '@/services/pouchdb/sync';
import { useAuthStore } from '@/stores/auth';

export function useSync() {
  const authStore = useAuthStore();
  const isOnline = useOnline();

  const isSyncing = ref(false);
  const lastSync = ref<Date | null>(null);
  const syncError = ref<Error | null>(null);

  let pollInterval: ReturnType<typeof setInterval> | null = null;

  function updateStatus() {
    const status = getSyncStatus();
    isSyncing.value = status.isActive && !status.isPaused;
    lastSync.value = status.lastSync;
    syncError.value = status.error;
  }

  // Start/stop sync based on auth state
  watch(
    () => authStore.isAuthenticated,
    (authenticated) => {
      if (authenticated && isOnline.value) {
        startSync();
      } else {
        stopSync();
      }
    }
  );

  // Start/stop sync based on online state
  watch(isOnline, (online) => {
    if (online && authStore.isAuthenticated) {
      startSync();
    }
    // Note: PouchDB handles offline gracefully, no need to stop
  });

  onMounted(() => {
    if (authStore.isAuthenticated && isOnline.value) {
      startSync();
    }

    // Poll sync status periodically
    pollInterval = setInterval(updateStatus, 1000);
  });

  onUnmounted(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
  });

  return {
    isOnline,
    isSyncing: computed(() => isSyncing.value),
    lastSync: computed(() => lastSync.value),
    syncError: computed(() => syncError.value)
  };
}
```

---

## 7. Pinia Store Example

```typescript
// /services/frontend/src/stores/auth.ts

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { api } from '@/services/api/client';
import { initDatabase, destroyDatabase } from '@/services/pouchdb';
import { startSync, stopSync } from '@/services/pouchdb/sync';

interface User {
  id: string;
  email: string;
  name: string;
  avatar_base64: string;
  locale: string;
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const token = ref<string | null>(null);
  const isAuthenticated = computed(() => !!user.value && !!token.value);

  async function login(email: string, password: string) {
    const response = await api.post('/api/v1/auth/login', { email, password });
    user.value = response.data.user;
    token.value = response.data.access_token;

    // Initialize PouchDB and start sync
    await initDatabase();
    startSync();
  }

  async function register(data: { email: string; password: string; name: string }) {
    const response = await api.post('/api/v1/auth/register', data);
    user.value = response.data.user;
    token.value = response.data.access_token;

    // Initialize PouchDB and start sync
    await initDatabase();
    startSync();
  }

  async function logout() {
    // Stop sync and destroy local database
    stopSync();
    await destroyDatabase();

    // Clear state
    user.value = null;
    token.value = null;

    await api.post('/api/v1/auth/logout');
  }

  async function refreshToken() {
    const response = await api.post('/api/v1/auth/refresh');
    token.value = response.data.access_token;
  }

  // Restore session on app load
  async function restore() {
    const storedToken = localStorage.getItem('token');
    if (storedToken) {
      token.value = storedToken;
      try {
        const response = await api.get('/api/v1/users/me');
        user.value = response.data;
        await initDatabase();
        startSync();
      } catch {
        // Token invalid, clear state
        token.value = null;
        localStorage.removeItem('token');
      }
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    login,
    register,
    logout,
    refreshToken,
    restore
  };
});
```

---

## 8. PWA Service Worker & OAuth

### 8.1 The Problem

PWA service workers use a **navigation fallback** strategy that serves `index.html` for all navigation requests. This enables SPA routing but breaks OAuth redirect flows that navigate to backend `/api/` endpoints.

### 8.2 The Solution

Configure `navigateFallbackDenylist` in the Workbox service worker to exclude `/api/` and `/couchdb/` paths:

```javascript
// quasar.config.js - pwa section
extendGenerateSWOptions(cfg) {
  cfg.skipWaiting = true;
  cfg.clientsClaim = true;
  // Exclude /api/ and /couchdb/ from navigation fallback
  cfg.navigateFallbackDenylist = [/^\/api\//, /^\/couchdb\//];
},
```

### 8.3 How OAuth Flow Works

```
1. User clicks "Login with Google" button
2. Frontend redirects to: /api/v1/oauth/google/authorize
3. Backend returns 302 redirect to Google OAuth consent screen
4. User authorizes on Google
5. Google redirects to: /api/v1/oauth/google/callback?code=...
6. Backend exchanges code for tokens
7. Backend redirects to: /auth/callback?access_token=...
8. Frontend AuthCallbackPage processes tokens
```

---

## 9. Dockerfile

```dockerfile
# /services/frontend/Dockerfile

# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

RUN npm install -g @quasar/cli

COPY package*.json ./
RUN npm ci

COPY . .

ARG API_URL=https://api.wishwith.me
ARG COUCHDB_URL=https://api.wishwith.me/couchdb
ENV API_URL=${API_URL}
ENV COUCHDB_URL=${COUCHDB_URL}
RUN quasar build -m pwa

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist/pwa /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```
