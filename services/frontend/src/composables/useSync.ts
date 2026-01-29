/**
 * Composable for tracking sync status and triggering synchronization.
 * Uses PouchDB for local storage with backend API sync.
 */

import { ref, computed, onMounted, shallowRef } from 'vue';
import { useOnline } from '@vueuse/core';
import {
  getDatabase,
  destroyDatabase,
  startSync,
  stopSync,
  triggerSync as pouchTriggerSync,
  type SyncStatus,
} from '@/services/pouchdb';
import { useAuthStore } from '@/stores/auth';

export type { SyncStatus };

const db = shallowRef<PouchDB.Database | null>(null);
const isInitialized = ref(false);
const isSyncing = ref(false);
const syncError = ref<string | null>(null);
const syncStatus = ref<SyncStatus>('idle');

/**
 * Initialize PouchDB and setup sync.
 */
async function initializeSync(): Promise<void> {
  if (isInitialized.value) return;

  const authStore = useAuthStore();
  if (!authStore.isAuthenticated) return;

  const userId = authStore.userId;
  const token = authStore.getAccessToken();

  if (!userId || !token) return;

  try {
    db.value = getDatabase();

    // Start sync with backend API
    startSync(userId, token, {
      onStatusChange: (status) => {
        syncStatus.value = status;
        isSyncing.value = status === 'syncing';
        if (status === 'idle') {
          syncError.value = null;
        }
      },
      onError: (error) => {
        console.error('Sync error:', error);
        syncError.value = error.message || 'Sync error';
      },
      onChange: (change) => {
        console.debug('Sync change:', change.id);
      },
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
  stopSync();

  if (db.value) {
    await destroyDatabase();
    db.value = null;
  }

  isInitialized.value = false;
  isSyncing.value = false;
  syncError.value = null;
  syncStatus.value = 'idle';
}

export function useSync() {
  const isOnline = useOnline();
  const authStore = useAuthStore();

  const status = computed<SyncStatus>(() => {
    if (!isOnline.value) return 'offline';
    if (syncError.value) return 'error';
    return syncStatus.value;
  });

  /**
   * Manually trigger a sync.
   */
  async function triggerSync(): Promise<void> {
    const token = authStore.getAccessToken();
    if (!isOnline.value || !token) return;

    syncError.value = null;
    try {
      await pouchTriggerSync(token);
    } catch (error) {
      console.error('Manual sync failed:', error);
      syncError.value = (error as Error).message || 'Sync failed';
    }
  }

  /**
   * Get the database instance.
   */
  function getDb(): PouchDB.Database | null {
    return db.value;
  }

  onMounted(async () => {
    if (authStore.isAuthenticated) {
      await initializeSync();
    }
  });

  return {
    isOnline,
    isInitialized: computed(() => isInitialized.value),
    isSyncing: computed(() => isSyncing.value),
    syncError: computed(() => syncError.value),
    pendingCount: computed(() => 0), // Not tracked with API-based sync
    status,
    triggerSync,
    initializeSync,
    cleanupSync,
    getDb,
  };
}

// Export for use outside composables
export { initializeSync, cleanupSync };
