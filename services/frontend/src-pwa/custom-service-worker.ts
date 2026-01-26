/**
 * Custom service worker for Wish With Me PWA.
 * Uses Workbox for caching strategies.
 */

import { clientsClaim } from 'workbox-core';
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, NetworkOnly, CacheFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';

declare const self: ServiceWorkerGlobalScope & typeof globalThis;

self.skipWaiting();
clientsClaim();

// Precache static assets from build
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// API calls - Network First with fallback to cache
// Note: OAuth endpoints are excluded via navigateFallbackDenylist in quasar.config.js
registerRoute(
  ({ url }) =>
    url.pathname.startsWith('/api/') &&
    !url.pathname.includes('/oauth/') &&
    !url.pathname.startsWith('/api/v1/sync/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 60 * 60 * 24, // 24 hours
      }),
    ],
    networkTimeoutSeconds: 10,
  })
);

// Sync endpoints - Network Only (never cache sync data)
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/sync/'),
  new NetworkOnly()
);

// Static assets - Cache First
registerRoute(
  ({ request, url }) =>
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'font' ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js'),
  new CacheFirst({
    cacheName: 'static-cache',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
      }),
    ],
  })
);

// Images - Cache First with longer expiration
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'image-cache',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({
        maxEntries: 200,
        maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
      }),
    ],
  })
);

// Google Fonts - Stale While Revalidate
registerRoute(
  ({ url }) =>
    url.origin === 'https://fonts.googleapis.com' ||
    url.origin === 'https://fonts.gstatic.com',
  new StaleWhileRevalidate({
    cacheName: 'google-fonts-cache',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({
        maxEntries: 30,
        maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
      }),
    ],
  })
);

// Background sync event for offline changes
self.addEventListener('sync', (event) => {
  if (event.tag === 'wishlist-sync') {
    event.waitUntil(syncPendingChanges());
  }
});

async function syncPendingChanges(): Promise<void> {
  // RxDB handles most sync, this is for edge cases
  console.log('[SW] Background sync triggered');
}

// Handle messages from the app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
