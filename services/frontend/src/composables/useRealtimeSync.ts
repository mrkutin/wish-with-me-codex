/**
 * Composable for real-time sync via Server-Sent Events (SSE).
 *
 * Listens to SSE events from the backend and triggers PouchDB sync
 * when data changes (e.g., item resolution completes).
 */

import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useOnline } from '@vueuse/core';
import { useAuthStore } from '@/stores/auth';
import { triggerSync } from '@/services/pouchdb';
import { getApiBaseUrl } from '@/boot/axios';

interface SSEEventData {
  id?: string;
  wishlist_id?: string;
  item_id?: string;
  status?: string;
  title?: string;
  timestamp?: string;
}

const MAX_RECONNECT_DELAY = 30000; // 30 seconds max backoff
const BASE_RECONNECT_DELAY = 1000; // 1 second initial delay

export function useRealtimeSync() {
  const authStore = useAuthStore();
  const isOnline = useOnline();

  const isConnected = ref(false);
  const lastEventTime = ref<Date | null>(null);
  const reconnectAttempts = ref(0);

  let eventSource: EventSource | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  /**
   * Calculate reconnect delay with exponential backoff.
   */
  function getReconnectDelay(): number {
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.value),
      MAX_RECONNECT_DELAY
    );
    return delay;
  }

  /**
   * Trigger PouchDB sync to pull latest changes.
   */
  function triggerPull() {
    const token = authStore.getAccessToken();
    if (token) {
      console.log('[SSE] Triggering PouchDB sync...');
      triggerSync(token).catch((error) => {
        console.error('[SSE] Sync failed:', error);
      });
    } else {
      console.warn('[SSE] Cannot trigger sync - no access token');
    }
  }

  /**
   * Connect to SSE endpoint.
   */
  function connect() {
    if (!authStore.isAuthenticated || !isOnline.value) {
      return;
    }

    // Get access token for SSE authentication
    // EventSource doesn't support custom headers, so we pass token as query param
    const token = authStore.getAccessToken();
    if (!token) {
      console.warn('[SSE] No access token available');
      return;
    }

    // Close any existing connection
    disconnect();

    // Build SSE URL with token as query parameter
    // Use the same API base URL as axios to ensure consistency
    const baseUrl = getApiBaseUrl();
    const sseUrl = `${baseUrl}/api/v1/events/stream?token=${encodeURIComponent(token)}`;

    try {
      eventSource = new EventSource(sseUrl);

      eventSource.onopen = () => {
        console.log('[SSE] Connected');
        isConnected.value = true;
        reconnectAttempts.value = 0;
      };

      eventSource.onerror = async (error) => {
        // Only log errors when online (offline errors are expected and noisy)
        if (isOnline.value) {
          console.error('[SSE] Error:', error);
        }
        isConnected.value = false;

        // If offline, close the EventSource to stop its auto-reconnect attempts
        // This prevents the flood of ERR_NAME_NOT_RESOLVED errors
        if (!isOnline.value) {
          disconnect();
          return;
        }

        // Close the connection to stop auto-reconnect with stale token
        disconnect();

        // Only try to reconnect if still authenticated
        // If refresh token is invalid, the auth system will log out the user
        if (!authStore.isAuthenticated) {
          console.log('[SSE] Not authenticated, skipping reconnect');
          return;
        }

        // Schedule reconnect (token will be refreshed by axios interceptor if needed)
        scheduleReconnect();
      };

      // Handle item updates
      eventSource.addEventListener('items:updated', (event) => {
        try {
          const data: SSEEventData = JSON.parse(event.data);
          console.log('[SSE] items:updated:', data);
          lastEventTime.value = new Date();
          triggerPull();

          // Emit custom event for NotificationBell to listen to
          window.dispatchEvent(
            new CustomEvent('sse:items-updated', { detail: data })
          );
        } catch (e) {
          console.error('[SSE] Failed to parse items:updated:', e);
        }
      });

      // Handle item resolution completion
      eventSource.addEventListener('items:resolved', (event) => {
        try {
          const data: SSEEventData = JSON.parse(event.data);
          console.log('[SSE] items:resolved:', data);
          lastEventTime.value = new Date();
          triggerPull();

          // Emit custom event for NotificationBell to listen to
          window.dispatchEvent(
            new CustomEvent('sse:items-resolved', { detail: data })
          );
        } catch (e) {
          console.error('[SSE] Failed to parse items:resolved:', e);
        }
      });

      // Handle wishlist updates
      eventSource.addEventListener('wishlists:updated', (event) => {
        try {
          const data: SSEEventData = JSON.parse(event.data);
          console.log('[SSE] wishlists:updated:', data);
          lastEventTime.value = new Date();
          triggerPull();
        } catch (e) {
          console.error('[SSE] Failed to parse wishlists:updated:', e);
        }
      });

      // Handle mark updates
      eventSource.addEventListener('marks:updated', (event) => {
        try {
          const data: SSEEventData = JSON.parse(event.data);
          console.log('[SSE] marks:updated:', data);
          lastEventTime.value = new Date();
          triggerPull();

          // Emit custom event for shared wishlist pages to listen to
          window.dispatchEvent(
            new CustomEvent('sse:marks-updated', { detail: data })
          );
        } catch (e) {
          console.error('[SSE] Failed to parse marks:updated:', e);
        }
      });

      // Handle keepalive pings
      eventSource.addEventListener('sync:ping', (event) => {
        try {
          JSON.parse(event.data); // Validate but don't use
          lastEventTime.value = new Date();
          // Ping is just for keepalive, no action needed
        } catch (e) {
          console.error('[SSE] Failed to parse sync:ping:', e);
        }
      });
    } catch (error) {
      console.error('[SSE] Failed to create EventSource:', error);
      scheduleReconnect();
    }
  }

  /**
   * Disconnect from SSE.
   */
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

  /**
   * Schedule a reconnection attempt with exponential backoff.
   */
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

  // Auto-connect when authenticated
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

  // Connect on mount if already authenticated
  onMounted(() => {
    if (authStore.isAuthenticated && isOnline.value) {
      connect();
    }
  });

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    lastEventTime,
    reconnectAttempts,
    connect,
    disconnect,
  };
}
