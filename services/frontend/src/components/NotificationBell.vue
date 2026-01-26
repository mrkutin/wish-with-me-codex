<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '@/boot/axios';
import { useAuthStore } from '@/stores/auth';
import type { Notification, NotificationListResponse } from '@/types/notification';

const { t } = useI18n();
const authStore = useAuthStore();

const notifications = ref<Notification[]>([]);
const unreadCount = ref(0);
const isLoading = ref(false);
const showMenu = ref(false);

let pollInterval: ReturnType<typeof setInterval> | null = null;

// Debounce SSE-triggered refreshes to avoid multiple rapid API calls
let sseRefreshTimeout: ReturnType<typeof setTimeout> | null = null;
const SSE_REFRESH_DEBOUNCE_MS = 500;

async function fetchNotifications() {
  if (!authStore.isAuthenticated) return;

  try {
    const response = await api.get<NotificationListResponse>('/api/v1/notifications', {
      params: { limit: 10 },
    });
    notifications.value = response.data.items;
    unreadCount.value = response.data.unread_count;
  } catch (error) {
    // Silently fail - notifications are non-critical
    console.error('Failed to fetch notifications:', error);
  }
}

async function markAsRead(notificationIds: string[]) {
  if (notificationIds.length === 0) return;

  try {
    await api.post('/api/v1/notifications/read', {
      notification_ids: notificationIds,
    });
    // Update local state
    notifications.value.forEach(n => {
      if (notificationIds.includes(n.id)) {
        n.read = true;
      }
    });
    unreadCount.value = Math.max(0, unreadCount.value - notificationIds.length);
  } catch (error) {
    console.error('Failed to mark notifications as read:', error);
  }
}

async function markAllAsRead() {
  try {
    await api.post('/api/v1/notifications/read-all');
    notifications.value.forEach(n => (n.read = true));
    unreadCount.value = 0;
  } catch (error) {
    console.error('Failed to mark all notifications as read:', error);
  }
}

function handleMenuOpen() {
  showMenu.value = true;
  // Mark visible unread notifications as read after a delay
  setTimeout(() => {
    const unreadIds = notifications.value
      .filter(n => !n.read)
      .map(n => n.id);
    if (unreadIds.length > 0) {
      markAsRead(unreadIds);
    }
  }, 2000);
}

function getNotificationIcon(type: string): string {
  switch (type) {
    case 'wishlist_shared':
      return 'share';
    case 'wishlist_accessed':
      return 'visibility';
    case 'item_marked':
      return 'check_circle';
    case 'item_unmarked':
      return 'remove_circle';
    case 'item_resolved':
      return 'done_all';
    case 'item_resolution_failed':
      return 'error';
    default:
      return 'notifications';
  }
}

function getNotificationColor(type: string): string {
  switch (type) {
    case 'wishlist_shared':
      return 'primary';
    case 'wishlist_accessed':
      return 'info';
    case 'item_marked':
      return 'positive';
    case 'item_unmarked':
      return 'warning';
    case 'item_resolved':
      return 'positive';
    case 'item_resolution_failed':
      return 'negative';
    default:
      return 'grey';
  }
}

function getNotificationText(notification: Notification): string {
  const payload = notification.payload;
  switch (notification.type) {
    case 'item_resolved':
      return t('notifications.itemResolved', { title: payload.item_title || 'Item' });
    case 'item_resolution_failed':
      return t('notifications.itemFailed', { title: payload.item_title || 'Item' });
    case 'item_marked':
      return t('notifications.itemMarked', { title: payload.item_title || 'Item' });
    case 'item_unmarked':
      return t('notifications.itemUnmarked', { title: payload.item_title || 'Item' });
    case 'wishlist_shared':
      return t('notifications.wishlistShared', { title: payload.wishlist_title || 'Wishlist' });
    case 'wishlist_accessed':
      return t('notifications.wishlistAccessed', {
        viewer: payload.viewer_name || 'Someone',
        title: payload.wishlist_title || 'Wishlist',
      });
    default:
      return t('notifications.generic');
  }
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return t('notifications.justNow');
  if (diffMins < 60) return t('notifications.minutesAgo', { count: diffMins });
  if (diffHours < 24) return t('notifications.hoursAgo', { count: diffHours });
  if (diffDays < 7) return t('notifications.daysAgo', { count: diffDays });

  return date.toLocaleDateString();
}

/**
 * Handle SSE events by debouncing notification refetches.
 * This prevents multiple rapid API calls when several events arrive quickly.
 */
function handleSSEEvent() {
  if (sseRefreshTimeout) {
    clearTimeout(sseRefreshTimeout);
  }
  sseRefreshTimeout = setTimeout(() => {
    console.log('[NotificationBell] Refreshing notifications after SSE event');
    fetchNotifications();
  }, SSE_REFRESH_DEBOUNCE_MS);
}

// SSE event handlers
function onItemsResolved() {
  handleSSEEvent();
}

function onItemsUpdated() {
  handleSSEEvent();
}

function onMarksUpdated() {
  handleSSEEvent();
}

onMounted(() => {
  if (authStore.isAuthenticated) {
    fetchNotifications();
    // Poll for new notifications every 60 seconds (fallback)
    pollInterval = setInterval(fetchNotifications, 60000);

    // Listen to SSE events for real-time updates
    window.addEventListener('sse:items-resolved', onItemsResolved);
    window.addEventListener('sse:items-updated', onItemsUpdated);
    window.addEventListener('sse:marks-updated', onMarksUpdated);
  }
});

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
  if (sseRefreshTimeout) {
    clearTimeout(sseRefreshTimeout);
  }

  // Clean up SSE event listeners
  window.removeEventListener('sse:items-resolved', onItemsResolved);
  window.removeEventListener('sse:items-updated', onItemsUpdated);
  window.removeEventListener('sse:marks-updated', onMarksUpdated);
});
</script>

<template>
  <q-btn flat round dense icon="notifications" @click="handleMenuOpen">
    <q-badge v-if="unreadCount > 0" color="negative" floating>
      {{ unreadCount > 99 ? '99+' : unreadCount }}
    </q-badge>

    <q-menu v-model="showMenu" anchor="bottom right" self="top right" :max-width="'350px'">
      <q-list style="min-width: 300px;">
        <q-item-label header class="row items-center justify-between">
          <span>{{ $t('notifications.title') }}</span>
          <q-btn
            v-if="unreadCount > 0"
            flat
            dense
            size="sm"
            color="primary"
            :label="$t('notifications.markAllRead')"
            @click="markAllAsRead"
          />
        </q-item-label>

        <q-separator />

        <template v-if="notifications.length > 0">
          <q-item
            v-for="notification in notifications"
            :key="notification.id"
            clickable
            v-close-popup
            :class="{ 'bg-grey-2': !notification.read }"
          >
            <q-item-section avatar>
              <q-icon
                :name="getNotificationIcon(notification.type)"
                :color="getNotificationColor(notification.type)"
              />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ getNotificationText(notification) }}</q-item-label>
              <q-item-label caption>{{ formatTime(notification.created_at) }}</q-item-label>
            </q-item-section>
            <q-item-section v-if="!notification.read" side>
              <q-badge color="primary" rounded />
            </q-item-section>
          </q-item>
        </template>

        <q-item v-else class="text-center text-grey-6">
          <q-item-section>
            <q-item-label>{{ $t('notifications.noNotifications') }}</q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>
