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
│   │   ├── rxdb.ts               # RxDB database init
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
│   │   │   ├── wishlists.ts
│   │   │   ├── items.ts
│   │   │   ├── share.ts
│   │   │   └── sync.ts
│   │   └── rxdb/
│   │       ├── index.ts          # RxDB database instance
│   │       ├── schemas/
│   │       │   ├── wishlist.ts   # Wishlist collection schema
│   │       │   ├── item.ts       # Item collection schema
│   │       │   └── syncMeta.ts   # Sync metadata schema
│   │       └── replication.ts    # Replication with PostgreSQL backend
│   │
│   ├── stores/                   # Pinia stores
│   │   ├── index.ts
│   │   ├── auth.ts
│   │   ├── wishlists.ts
│   │   ├── sync.ts
│   │   └── notifications.ts
│   │
│   ├── types/
│   │   ├── user.ts
│   │   ├── wishlist.ts
│   │   ├── item.ts
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
├── quasar.config.ts              # Quasar configuration
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
    "rxdb": "^15.25.0",
    "rxjs": "^7.8.0",
    "@vueuse/core": "^10.9.0",
    "@vueuse/rxjs": "^10.9.0",
    "date-fns": "^3.3.0",
    "qrcode": "^1.5.0"
  },
  "devDependencies": {
    "@quasar/app-vite": "^1.8.0",
    "@quasar/extras": "^1.16.0",
    "typescript": "^5.3.0",
    "@types/node": "^20.11.0",
    "@vue/test-utils": "^2.4.0",
    "vitest": "^1.2.0",
    "@vitest/coverage-v8": "^1.2.0",
    "happy-dom": "^13.0.0",
    "fake-indexeddb": "^5.0.0",
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

```typescript
// /services/frontend/quasar.config.ts

import { configure } from 'quasar/wrappers';

export default configure((/* ctx */) => {
  return {
    boot: ['i18n', 'axios', 'rxdb', 'auth'],

    css: ['app.sass'],

    extras: [
      'roboto-font',
      'material-icons',
      'mdi-v7'
    ],

    build: {
      target: {
        browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node20'
      },
      vueRouterMode: 'history',
      env: {
        API_URL: process.env.API_URL || 'https://api.wishwith.me',
      },
      typescript: {
        strict: true,
        vueShim: true
      }
    },

    devServer: {
      open: true
    },

    framework: {
      config: {
        brand: {
          primary: '#6366f1',
          secondary: '#26A69A',
          accent: '#9C27B0',
          dark: '#1d1d1d',
          positive: '#1a9f38',  // Darkened for WCAG contrast
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

## 5. RxDB Setup

### 5.1 Collection Schemas

```typescript
// /services/frontend/src/services/rxdb/schemas/wishlist.ts

import { RxJsonSchema } from 'rxdb';

export interface WishlistDocType {
  id: string;
  owner_id: string;
  title: string;
  description?: string;
  cover_image_base64?: string;
  item_count: number;
  created_at: string;
  updated_at: string;
  _deleted?: boolean;
}

export const wishlistSchema: RxJsonSchema<WishlistDocType> = {
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 36 },
    owner_id: { type: 'string', maxLength: 36 },
    title: { type: 'string', maxLength: 200 },
    description: { type: 'string' },
    cover_image_base64: { type: 'string' },
    item_count: { type: 'integer', minimum: 0, default: 0 },
    created_at: { type: 'string', format: 'date-time' },
    updated_at: { type: 'string', format: 'date-time' },
    _deleted: { type: 'boolean' }
  },
  required: ['id', 'owner_id', 'title', 'created_at', 'updated_at'],
  indexes: ['owner_id', 'updated_at']
};
```

```typescript
// /services/frontend/src/services/rxdb/schemas/item.ts

import { RxJsonSchema } from 'rxdb';

export type ItemStatus = 'pending' | 'resolving' | 'resolved' | 'failed' | 'manual';

export interface ItemDocType {
  id: string;
  wishlist_id: string;
  source_url?: string;
  title: string;
  description?: string;
  price_amount?: number;
  price_currency?: string;
  image_url?: string;
  image_base64?: string;
  quantity: number;
  marked_quantity: number;
  status: ItemStatus;
  resolution_error?: Record<string, unknown>;
  sort_order: number;
  created_at: string;
  updated_at: string;
  _deleted?: boolean;
}

export const itemSchema: RxJsonSchema<ItemDocType> = {
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 36 },
    wishlist_id: { type: 'string', maxLength: 36 },
    source_url: { type: 'string' },
    title: { type: 'string', maxLength: 500 },
    description: { type: 'string' },
    price_amount: { type: 'number' },
    price_currency: { type: 'string', maxLength: 3 },
    image_url: { type: 'string' },
    image_base64: { type: 'string' },
    quantity: { type: 'integer', minimum: 1, default: 1 },
    marked_quantity: { type: 'integer', minimum: 0, default: 0 },
    status: { type: 'string', enum: ['pending', 'resolving', 'resolved', 'failed', 'manual'] },
    resolution_error: { type: 'object' },
    sort_order: { type: 'integer', default: 0 },
    created_at: { type: 'string', format: 'date-time' },
    updated_at: { type: 'string', format: 'date-time' },
    _deleted: { type: 'boolean' }
  },
  required: ['id', 'wishlist_id', 'title', 'quantity', 'status', 'created_at', 'updated_at'],
  indexes: ['wishlist_id', 'status', 'updated_at']
};
```

### 5.2 Database Initialization

```typescript
// /services/frontend/src/services/rxdb/index.ts

import {
  createRxDatabase,
  RxDatabase,
  RxCollection,
  addRxPlugin
} from 'rxdb';
import { getRxStorageDexie } from 'rxdb/plugins/storage-dexie';
import { RxDBDevModePlugin } from 'rxdb/plugins/dev-mode';
import { RxDBQueryBuilderPlugin } from 'rxdb/plugins/query-builder';
import { RxDBUpdatePlugin } from 'rxdb/plugins/update';
import { RxDBLeaderElectionPlugin } from 'rxdb/plugins/leader-election';

import { wishlistSchema, WishlistDocType } from './schemas/wishlist';
import { itemSchema, ItemDocType } from './schemas/item';

// Add plugins
if (import.meta.env.DEV) {
  addRxPlugin(RxDBDevModePlugin);
}
addRxPlugin(RxDBQueryBuilderPlugin);
addRxPlugin(RxDBUpdatePlugin);
addRxPlugin(RxDBLeaderElectionPlugin);

// Type definitions
export type WishlistCollection = RxCollection<WishlistDocType>;
export type ItemCollection = RxCollection<ItemDocType>;

export interface DatabaseCollections {
  wishlists: WishlistCollection;
  items: ItemCollection;
}

export type WishWithMeDatabase = RxDatabase<DatabaseCollections>;

let dbPromise: Promise<WishWithMeDatabase> | null = null;

export async function getDatabase(): Promise<WishWithMeDatabase> {
  if (dbPromise) return dbPromise;

  dbPromise = createRxDatabase<DatabaseCollections>({
    name: 'wishwithme',
    storage: getRxStorageDexie(),
    multiInstance: true,
    eventReduce: true,
    cleanupPolicy: {
      minimumDeletedTime: 1000 * 60 * 60 * 24 * 7,
      minimumCollectionAge: 1000 * 60,
      runEach: 1000 * 60 * 5,
      awaitReplicationsInSync: true,
      waitForLeadership: true
    }
  }).then(async (db) => {
    await db.addCollections({
      wishlists: { schema: wishlistSchema },
      items: { schema: itemSchema }
    });
    return db;
  });

  return dbPromise;
}

export let db: WishWithMeDatabase;

export async function initDatabase(): Promise<WishWithMeDatabase> {
  db = await getDatabase();
  return db;
}
```

---

## 6. Vue Composables

### 6.1 useItems

```typescript
// /services/frontend/src/composables/useItems.ts

import { computed } from 'vue';
import { useObservable } from '@vueuse/rxjs';
import { useOnline } from '@vueuse/core';
import { db } from '@/services/rxdb';
import type { ItemDocType } from '@/services/rxdb/schemas/item';

export function useItems(wishlistId: string) {
  const isOnline = useOnline();

  const items = useObservable(
    db.items
      .find({
        selector: {
          wishlist_id: wishlistId,
          _deleted: { $ne: true }
        },
        sort: [{ sort_order: 'asc' }]
      })
      .$,
    { initialValue: [] as ItemDocType[] }
  );

  async function createItem(data: Partial<ItemDocType>): Promise<ItemDocType> {
    const now = new Date().toISOString();
    const item: ItemDocType = {
      id: crypto.randomUUID(),
      wishlist_id: wishlistId,
      title: data.title || 'Loading...',
      description: data.description,
      price_amount: data.price_amount,
      price_currency: data.price_currency,
      source_url: data.source_url,
      image_base64: data.image_base64,
      status: data.source_url ? 'pending' : 'manual',
      quantity: data.quantity ?? 1,
      marked_quantity: 0,
      sort_order: items.value.length,
      created_at: now,
      updated_at: now
    };
    const doc = await db.items.insert(item);
    return doc.toJSON();
  }

  async function updateItem(id: string, updates: Partial<ItemDocType>) {
    const doc = await db.items.findOne(id).exec();
    if (doc) {
      await doc.patch({ ...updates, updated_at: new Date().toISOString() });
    }
  }

  async function deleteItem(id: string) {
    const doc = await db.items.findOne(id).exec();
    if (doc) {
      await doc.patch({ _deleted: true, updated_at: new Date().toISOString() });
    }
  }

  return {
    items: computed(() => items.value),
    isOnline,
    createItem,
    updateItem,
    deleteItem
  };
}
```

### 6.2 useWishlists

```typescript
// /services/frontend/src/composables/useWishlists.ts

import { computed } from 'vue';
import { useObservable } from '@vueuse/rxjs';
import { db } from '@/services/rxdb';
import { useAuthStore } from '@/stores/auth';
import type { WishlistDocType } from '@/services/rxdb/schemas/wishlist';

export function useWishlists() {
  const authStore = useAuthStore();

  const wishlists = useObservable(
    db.wishlists
      .find({
        selector: {
          owner_id: authStore.user?.id,
          _deleted: { $ne: true }
        },
        sort: [{ updated_at: 'desc' }]
      })
      .$,
    { initialValue: [] as WishlistDocType[] }
  );

  async function createWishlist(data: { title: string; description?: string }) {
    const now = new Date().toISOString();
    const wishlist: WishlistDocType = {
      id: crypto.randomUUID(),
      owner_id: authStore.user!.id,
      title: data.title,
      description: data.description,
      item_count: 0,
      created_at: now,
      updated_at: now
    };
    await db.wishlists.insert(wishlist);
    return wishlist;
  }

  async function deleteWishlist(id: string) {
    const doc = await db.wishlists.findOne(id).exec();
    if (doc) {
      await doc.patch({ _deleted: true, updated_at: new Date().toISOString() });
      const items = await db.items.find({ selector: { wishlist_id: id } }).exec();
      await Promise.all(
        items.map(item => item.patch({ _deleted: true, updated_at: new Date().toISOString() }))
      );
    }
  }

  return {
    wishlists: computed(() => wishlists.value),
    createWishlist,
    deleteWishlist
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

interface User {
  id: string;
  email: string;
  name: string;
  avatar_base64: string;
  locale: string;
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const accessToken = ref<string | null>(null);
  const isAuthenticated = computed(() => !!user.value);

  async function login(email: string, password: string) {
    const response = await api.post('/api/v1/auth/login', { email, password });
    user.value = response.data.user;
    accessToken.value = response.data.access_token;
  }

  async function logout() {
    await api.post('/api/v1/auth/logout');
    user.value = null;
    accessToken.value = null;
  }

  async function refreshToken() {
    const response = await api.post('/api/v1/auth/refresh');
    accessToken.value = response.data.access_token;
  }

  return {
    user,
    accessToken,
    isAuthenticated,
    login,
    logout,
    refreshToken
  };
});
```

---

## 8. Dockerfile

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
ENV API_URL=${API_URL}
RUN quasar build -m pwa

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist/spa /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```
