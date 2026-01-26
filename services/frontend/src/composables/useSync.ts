/**
 * Composable for tracking sync status and triggering synchronization.
 */

import { ref, computed, onMounted, onUnmounted, shallowRef } from 'vue';
import { useOnline } from '@vueuse/core';
import { getDatabase, destroyDatabase, type WishWithMeDatabase } from '@/services/rxdb';
import { setupReplication, type ReplicationState } from '@/services/rxdb/replication';
import { useAuthStore } from '@/stores/auth';

export type SyncStatus = 'idle' | 'syncing' | 'error' | 'offline';

const db = shallowRef<WishWithMeDatabase | null>(null);
const replication = shallowRef<ReplicationState | null>(null);
const isInitialized = ref(false);
const isSyncing = ref(false);
const syncError = ref<string | null>(null);
const pendingWishlists = ref(0);
const pendingItems = ref(0);

/**
 * Initialize RxDB and setup replication.
 */
async function initializeSync(): Promise<void> {
  if (isInitialized.value) return;

  const authStore = useAuthStore();
  if (!authStore.isAuthenticated) return;

  try {
    db.value = await getDatabase();
    replication.value = setupReplication(db.value);

    // Subscribe to sync errors
    replication.value.wishlists.error$.subscribe((err) => {
      console.error('Wishlist sync error:', err);
      syncError.value = err.message || 'Sync error';
    });

    replication.value.items.error$.subscribe((err) => {
      console.error('Item sync error:', err);
      syncError.value = err.message || 'Sync error';
    });

    // Track syncing state
    replication.value.wishlists.active$.subscribe((active) => {
      isSyncing.value = active;
      if (!active) {
        syncError.value = null;
      }
    });

    isInitialized.value = true;
  } catch (error) {
    console.error('Failed to initialize sync:', error);
    syncError.value = 'Failed to initialize offline storage';
  }
}

/**
 * Cleanup sync resources.
 */
async function cleanupSync(): Promise<void> {
  if (replication.value) {
    await replication.value.cancel();
    replication.value = null;
  }
  if (db.value) {
    await destroyDatabase();
    db.value = null;
  }
  isInitialized.value = false;
  isSyncing.value = false;
  syncError.value = null;
  pendingWishlists.value = 0;
  pendingItems.value = 0;
}

export function useSync() {
  const isOnline = useOnline();
  const authStore = useAuthStore();

  const status = computed<SyncStatus>(() => {
    if (!isOnline.value) return 'offline';
    if (syncError.value) return 'error';
    if (isSyncing.value) return 'syncing';
    return 'idle';
  });

  const pendingCount = computed(() => pendingWishlists.value + pendingItems.value);

  /**
   * Manually trigger a sync pull.
   */
  function triggerSync(): void {
    if (!isOnline.value || !replication.value) return;
    syncError.value = null;
    replication.value.triggerPull();
  }

  /**
   * Get the database instance.
   */
  function getDb(): WishWithMeDatabase | null {
    return db.value;
  }

  onMounted(async () => {
    if (authStore.isAuthenticated) {
      await initializeSync();
    }
  });

  onUnmounted(() => {
    // Don't cleanup on unmount - keep sync running
  });

  return {
    isOnline,
    isInitialized: computed(() => isInitialized.value),
    isSyncing: computed(() => isSyncing.value),
    syncError: computed(() => syncError.value),
    pendingCount,
    status,
    triggerSync,
    initializeSync,
    cleanupSync,
    getDb,
  };
}

// Export for use outside composables
export { initializeSync, cleanupSync };
