/**
 * Unit tests for the useSync composable.
 * Tests sync initialization, triggering, cleanup, and status computation.
 *
 * Note: The useSync composable uses module-level state, so tests must
 * call cleanupSync() in afterEach to reset state between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ref } from 'vue';
import { setActivePinia, createPinia } from 'pinia';
import { useSync } from '../useSync';
import { useAuthStore } from '@/stores/auth';

// Mock @vueuse/core
const mockIsOnline = ref(true);
vi.mock('@vueuse/core', () => ({
  useOnline: () => mockIsOnline,
}));

// Mock PouchDB service
const mockGetDatabase = vi.fn();
const mockDestroyDatabase = vi.fn();
const mockStartSync = vi.fn();
const mockStopSync = vi.fn();
const mockPouchTriggerSync = vi.fn();

vi.mock('@/services/pouchdb', () => ({
  getDatabase: () => mockGetDatabase(),
  destroyDatabase: () => mockDestroyDatabase(),
  startSync: (...args: unknown[]) => mockStartSync(...args),
  stopSync: () => mockStopSync(),
  triggerSync: (...args: unknown[]) => mockPouchTriggerSync(...args),
}));

// Mock Quasar LocalStorage
vi.mock('quasar', () => ({
  LocalStorage: {
    getItem: vi.fn(),
    set: vi.fn(),
    remove: vi.fn(),
  },
}));

// Mock axios api
vi.mock('@/boot/axios', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('useSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();

    // Reset online status
    mockIsOnline.value = true;

    // Reset mock implementations
    mockGetDatabase.mockReturnValue({ name: 'test-db' });
    mockDestroyDatabase.mockResolvedValue(undefined);
    mockStartSync.mockImplementation(() => {});
    mockStopSync.mockImplementation(() => {});
    mockPouchTriggerSync.mockResolvedValue(undefined);
  });

  afterEach(async () => {
    // Reset the composable's module-level state by calling cleanupSync
    const { cleanupSync } = useSync();
    await cleanupSync();
    vi.restoreAllMocks();
  });

  describe('initializeSync', () => {
    it('should initialize DB and start sync when authenticated', async () => {
      // Setup authenticated state
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      const { initializeSync, isInitialized } = useSync();

      await initializeSync();

      expect(mockGetDatabase).toHaveBeenCalled();
      expect(mockStartSync).toHaveBeenCalledWith(
        'user:123',
        'mock-access-token',
        expect.objectContaining({
          onStatusChange: expect.any(Function),
          onError: expect.any(Function),
          onChange: expect.any(Function),
        })
      );
      expect(isInitialized.value).toBe(true);
    });

    it('should return early when unauthenticated', async () => {
      // Auth store starts unauthenticated by default
      const { initializeSync, isInitialized } = useSync();

      await initializeSync();

      expect(mockGetDatabase).not.toHaveBeenCalled();
      expect(mockStartSync).not.toHaveBeenCalled();
      expect(isInitialized.value).toBe(false);
    });

    it('should return early when userId is missing', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: null,
        accessToken: 'mock-access-token',
      });

      const { initializeSync, isInitialized } = useSync();

      await initializeSync();

      expect(mockGetDatabase).not.toHaveBeenCalled();
      expect(mockStartSync).not.toHaveBeenCalled();
      expect(isInitialized.value).toBe(false);
    });

    it('should return early when token is missing', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: null,
      });

      const { initializeSync, isInitialized } = useSync();

      await initializeSync();

      expect(mockGetDatabase).not.toHaveBeenCalled();
      expect(mockStartSync).not.toHaveBeenCalled();
      expect(isInitialized.value).toBe(false);
    });

    it('should not reinitialize if already initialized', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      const { initializeSync } = useSync();

      await initializeSync();
      // Clear mock counts to verify second call doesn't reinitialize
      mockGetDatabase.mockClear();
      mockStartSync.mockClear();

      await initializeSync(); // Second call

      // Should not be called again
      expect(mockGetDatabase).not.toHaveBeenCalled();
      expect(mockStartSync).not.toHaveBeenCalled();
    });

    it('should handle initialization errors gracefully', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      mockGetDatabase.mockImplementation(() => {
        throw new Error('Database creation failed');
      });

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { initializeSync, syncError } = useSync();

      await initializeSync();

      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to initialize sync:', expect.any(Error));
      expect(syncError.value).toBe('Failed to initialize offline storage');

      consoleErrorSpy.mockRestore();
    });
  });

  describe('triggerSync', () => {
    it('should call pouchTriggerSync with token', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      mockIsOnline.value = true;

      const { triggerSync } = useSync();

      await triggerSync();

      expect(mockPouchTriggerSync).toHaveBeenCalledWith('mock-access-token');
    });

    it('should return early when offline', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      mockIsOnline.value = false;

      const { triggerSync } = useSync();

      await triggerSync();

      expect(mockPouchTriggerSync).not.toHaveBeenCalled();
    });

    it('should return early when no token', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: null,
      });

      mockIsOnline.value = true;

      const { triggerSync } = useSync();

      await triggerSync();

      expect(mockPouchTriggerSync).not.toHaveBeenCalled();
    });

    it('should handle sync errors and set syncError', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      mockIsOnline.value = true;
      mockPouchTriggerSync.mockRejectedValue(new Error('Sync network error'));

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { triggerSync, syncError } = useSync();

      await triggerSync();

      expect(consoleErrorSpy).toHaveBeenCalledWith('Manual sync failed:', expect.any(Error));
      expect(syncError.value).toBe('Sync network error');

      consoleErrorSpy.mockRestore();
    });

    it('should clear syncError before attempting sync', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      mockIsOnline.value = true;
      vi.spyOn(console, 'error').mockImplementation(() => {});

      const { triggerSync, syncError } = useSync();

      // First sync fails
      mockPouchTriggerSync.mockRejectedValueOnce(new Error('First error'));
      await triggerSync();
      expect(syncError.value).toBe('First error');

      // Second sync succeeds - error should be cleared
      mockPouchTriggerSync.mockResolvedValueOnce(undefined);
      await triggerSync();
      expect(syncError.value).toBeNull();
    });
  });

  describe('cleanupSync', () => {
    it('should destroy database and reset state', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      const { initializeSync, cleanupSync, isInitialized, isSyncing, syncError } = useSync();

      // Initialize first
      await initializeSync();
      expect(isInitialized.value).toBe(true);

      // Then cleanup
      await cleanupSync();

      expect(mockStopSync).toHaveBeenCalled();
      expect(mockDestroyDatabase).toHaveBeenCalled();
      expect(isInitialized.value).toBe(false);
      expect(isSyncing.value).toBe(false);
      expect(syncError.value).toBeNull();
    });

    it('should stop sync even if not initialized', async () => {
      const { cleanupSync } = useSync();

      await cleanupSync();

      expect(mockStopSync).toHaveBeenCalled();
    });
  });

  describe('status computed', () => {
    it('should return "offline" when not online', () => {
      mockIsOnline.value = false;

      const { status } = useSync();

      expect(status.value).toBe('offline');
    });

    it('should return "error" when syncError exists', async () => {
      mockIsOnline.value = true;
      vi.spyOn(console, 'error').mockImplementation(() => {});

      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      mockPouchTriggerSync.mockRejectedValue(new Error('Sync failed'));

      const { status, triggerSync } = useSync();

      await triggerSync();

      expect(status.value).toBe('error');
    });

    it('should return "syncing" when isSyncing is true', async () => {
      mockIsOnline.value = true;

      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      // Capture the onStatusChange callback when startSync is called
      let capturedOnStatusChange: ((status: string) => void) | undefined;
      mockStartSync.mockImplementation((_userId, _token, options) => {
        capturedOnStatusChange = options?.onStatusChange;
      });

      const { initializeSync, status } = useSync();

      await initializeSync();

      // Simulate syncing status
      if (capturedOnStatusChange) {
        capturedOnStatusChange('syncing');
      }

      expect(status.value).toBe('syncing');
    });

    it('should return "idle" when idle and online', async () => {
      mockIsOnline.value = true;

      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      // Capture the onStatusChange callback
      let capturedOnStatusChange: ((status: string) => void) | undefined;
      mockStartSync.mockImplementation((_userId, _token, options) => {
        capturedOnStatusChange = options?.onStatusChange;
      });

      const { initializeSync, status } = useSync();

      await initializeSync();

      // Simulate idle status after sync completes
      if (capturedOnStatusChange) {
        capturedOnStatusChange('idle');
      }

      expect(status.value).toBe('idle');
    });

    it('should prioritize offline over error', async () => {
      mockIsOnline.value = true;
      vi.spyOn(console, 'error').mockImplementation(() => {});

      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      // First create an error state
      mockPouchTriggerSync.mockRejectedValueOnce(new Error('Some error'));
      const { triggerSync, status } = useSync();
      await triggerSync();

      // Now go offline
      mockIsOnline.value = false;

      // Offline should take precedence over error
      expect(status.value).toBe('offline');
    });
  });

  describe('sync callbacks', () => {
    it('should update isSyncing based on status changes', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      let capturedOnStatusChange: ((status: string) => void) | undefined;
      mockStartSync.mockImplementation((_userId, _token, options) => {
        capturedOnStatusChange = options?.onStatusChange;
      });

      const { initializeSync, isSyncing } = useSync();

      await initializeSync();

      // Initially idle (default)
      // Simulate syncing
      capturedOnStatusChange?.('syncing');
      expect(isSyncing.value).toBe(true);

      // Simulate idle
      capturedOnStatusChange?.('idle');
      expect(isSyncing.value).toBe(false);
    });

    it('should clear syncError when status becomes idle', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      vi.spyOn(console, 'error').mockImplementation(() => {});

      let capturedOnStatusChange: ((status: string) => void) | undefined;
      let capturedOnError: ((error: Error) => void) | undefined;
      mockStartSync.mockImplementation((_userId, _token, options) => {
        capturedOnStatusChange = options?.onStatusChange;
        capturedOnError = options?.onError;
      });

      const { initializeSync, syncError } = useSync();

      await initializeSync();

      // Simulate an error
      capturedOnError?.(new Error('Network error'));
      expect(syncError.value).toBe('Network error');

      // Simulate idle - should clear error
      capturedOnStatusChange?.('idle');
      expect(syncError.value).toBeNull();
    });

    it('should handle onError callback', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      let capturedOnError: ((error: Error) => void) | undefined;
      mockStartSync.mockImplementation((_userId, _token, options) => {
        capturedOnError = options?.onError;
      });

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { initializeSync, syncError } = useSync();

      await initializeSync();

      capturedOnError?.(new Error('Sync failed'));

      expect(consoleErrorSpy).toHaveBeenCalledWith('Sync error:', expect.any(Error));
      expect(syncError.value).toBe('Sync failed');

      consoleErrorSpy.mockRestore();
    });

    it('should handle error without message', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      let capturedOnError: ((error: Error) => void) | undefined;
      mockStartSync.mockImplementation((_userId, _token, options) => {
        capturedOnError = options?.onError;
      });

      vi.spyOn(console, 'error').mockImplementation(() => {});

      const { initializeSync, syncError } = useSync();

      await initializeSync();

      // Error without message
      const errorWithoutMessage = { name: 'Error' } as Error;
      capturedOnError?.(errorWithoutMessage);

      expect(syncError.value).toBe('Sync error');
    });
  });

  describe('getDb', () => {
    it('should return null when not initialized', async () => {
      // Ensure clean state by calling cleanupSync first
      const { cleanupSync, getDb } = useSync();
      await cleanupSync();

      expect(getDb()).toBeNull();
    });

    it('should return database after initialization', async () => {
      const authStore = useAuthStore();
      Object.assign(authStore, {
        user: { id: 'user:123', email: 'test@example.com', name: 'Test' },
        accessToken: 'mock-access-token',
      });

      const mockDb = { name: 'wishwithme' };
      mockGetDatabase.mockReturnValue(mockDb);

      const { initializeSync, getDb } = useSync();

      await initializeSync();

      expect(getDb()).toEqual(mockDb);
    });
  });

  describe('pendingCount', () => {
    it('should always return 0 (not tracked with API-based sync)', () => {
      const { pendingCount } = useSync();

      expect(pendingCount.value).toBe(0);
    });
  });
});
