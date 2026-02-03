/**
 * Unit tests for the wishlist store.
 * Tests wishlist CRUD operations with offline-first PouchDB architecture.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useWishlistStore } from '../wishlist';
import { useAuthStore } from '../auth';
import type { WishlistDoc } from '@/services/pouchdb/types';
import {
  createMockWishlistDoc,
  createMockUser,
  resetIdCounter,
} from '@/test/fixtures';

// Mock Quasar Notify
const mockNotifyCreate = vi.fn();
vi.mock('quasar', () => ({
  Notify: {
    create: vi.fn((opts) => mockNotifyCreate(opts)),
  },
}));

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: vi.fn((key: string) => key),
  }),
}));

// Mock @vueuse/core useOnline
const mockIsOnline = vi.fn(() => true);
vi.mock('@vueuse/core', () => ({
  useOnline: () => ({
    value: mockIsOnline(),
  }),
}));

// Mock PouchDB service
const mockUnsubscribe = vi.fn();
const mockSubscribeToWishlists = vi.fn(() => mockUnsubscribe);
const mockGetDatabase = vi.fn();
const mockFindById = vi.fn();
const mockUpsert = vi.fn();
const mockSoftDelete = vi.fn();
const mockTriggerSync = vi.fn();
const mockCreateId = vi.fn((type: string) => `${type}:test-uuid-123`);

vi.mock('@/services/pouchdb', () => ({
  getDatabase: () => mockGetDatabase(),
  subscribeToWishlists: (userId: string, callback: (docs: WishlistDoc[]) => void) =>
    mockSubscribeToWishlists(userId, callback),
  findById: (id: string) => mockFindById(id),
  upsert: (doc: WishlistDoc) => mockUpsert(doc),
  softDelete: (id: string) => mockSoftDelete(id),
  triggerSync: (token: string) => mockTriggerSync(token),
  createId: (type: string) => mockCreateId(type),
}));

// Mock auth store
vi.mock('@/stores/auth', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...(actual as object),
    useAuthStore: vi.fn(),
  };
});

describe('useWishlistStore', () => {
  const mockUser = createMockUser({ id: 'user:test-123' });
  let mockAuthStore: {
    userId: string | null;
    getAccessToken: () => string | null;
  };

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    resetIdCounter();

    // Setup default auth store mock
    mockAuthStore = {
      userId: mockUser.id,
      getAccessToken: vi.fn(() => 'test-access-token'),
    };
    vi.mocked(useAuthStore).mockReturnValue(mockAuthStore as ReturnType<typeof useAuthStore>);

    // Default online state
    mockIsOnline.mockReturnValue(true);

    // Default mock implementations - reset to safe defaults
    mockGetDatabase.mockReturnValue({}); // Reset getDatabase to not throw
    mockSubscribeToWishlists.mockImplementation(() => mockUnsubscribe);
    mockUpsert.mockImplementation(async (doc) => ({ ...doc, _rev: '1-mock' }));
    mockFindById.mockResolvedValue(null);
    mockSoftDelete.mockResolvedValue(undefined);
    mockTriggerSync.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initializeStore', () => {
    it('should create PouchDB subscription when user is authenticated', async () => {
      const store = useWishlistStore();

      await store.initializeStore();

      expect(mockGetDatabase).toHaveBeenCalled();
      expect(mockSubscribeToWishlists).toHaveBeenCalledWith(
        mockUser.id,
        expect.any(Function)
      );
      expect(store.isInitialized).toBe(true);
    });

    it('should not initialize when user is not authenticated', async () => {
      mockAuthStore.userId = null;

      const store = useWishlistStore();

      await store.initializeStore();

      expect(mockGetDatabase).not.toHaveBeenCalled();
      expect(mockSubscribeToWishlists).not.toHaveBeenCalled();
      expect(store.isInitialized).toBe(false);
    });

    it('should not re-initialize when already initialized', async () => {
      const store = useWishlistStore();

      await store.initializeStore();
      await store.initializeStore();

      expect(mockSubscribeToWishlists).toHaveBeenCalledTimes(1);
    });

    it('should handle initialization errors gracefully', async () => {
      mockGetDatabase.mockImplementation(() => {
        throw new Error('Database error');
      });

      const store = useWishlistStore();

      // Should not throw
      await store.initializeStore();

      expect(store.isInitialized).toBe(false);
      expect(store.isLoading).toBe(false);
    });
  });

  describe('createWishlist', () => {
    it('should create wishlist document and trigger sync when online', async () => {
      const store = useWishlistStore();

      const result = await store.createWishlist({
        name: 'Birthday Wishlist',
        description: 'My birthday wishes',
        icon: 'cake',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'wishlist:test-uuid-123',
          type: 'wishlist',
          owner_id: mockUser.id,
          name: 'Birthday Wishlist',
          description: 'My birthday wishes',
          icon: 'cake',
          is_public: false,
          access: [mockUser.id],
        })
      );
      // triggerSync no longer takes arguments - it uses the token manager internally
      expect(mockTriggerSync).toHaveBeenCalled();
      expect(result.name).toBe('Birthday Wishlist');
      expect(result.id).toBe('wishlist:test-uuid-123');
    });

    it('should use default values when optional fields not provided', async () => {
      const store = useWishlistStore();

      await store.createWishlist({
        name: 'Simple Wishlist',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Simple Wishlist',
          description: null,
          icon: 'card_giftcard',
          is_public: false,
        })
      );
    });

    it('should throw error when user is not authenticated', async () => {
      mockAuthStore.userId = null;

      const store = useWishlistStore();

      await expect(
        store.createWishlist({ name: 'Test' })
      ).rejects.toThrow('User not authenticated');

      expect(mockUpsert).not.toHaveBeenCalled();
    });

    it('should show offline notification and not sync when offline', async () => {
      mockIsOnline.mockReturnValue(false);

      const store = useWishlistStore();

      await store.createWishlist({ name: 'Offline Wishlist' });

      expect(mockUpsert).toHaveBeenCalled();
      expect(mockTriggerSync).not.toHaveBeenCalled();
      expect(mockNotifyCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'offline.createdOffline',
          icon: 'cloud_off',
        })
      );
    });

    it('should not sync when access token is not available', async () => {
      mockAuthStore.getAccessToken = vi.fn(() => null);

      const store = useWishlistStore();

      await store.createWishlist({ name: 'No Token Wishlist' });

      expect(mockUpsert).toHaveBeenCalled();
      expect(mockTriggerSync).not.toHaveBeenCalled();
    });
  });

  describe('updateWishlist', () => {
    it('should modify existing wishlist document', async () => {
      const existingDoc = createMockWishlistDoc({
        id: 'wishlist:existing-123',
        name: 'Old Name',
        description: 'Old description',
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(existingDoc);

      const store = useWishlistStore();

      const result = await store.updateWishlist('wishlist:existing-123', {
        name: 'New Name',
        description: 'New description',
      });

      expect(mockFindById).toHaveBeenCalledWith('wishlist:existing-123');
      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'wishlist:existing-123',
          name: 'New Name',
          description: 'New description',
        })
      );
      expect(mockTriggerSync).toHaveBeenCalled();
      expect(result.name).toBe('New Name');
    });

    it('should throw error when wishlist does not exist', async () => {
      mockFindById.mockResolvedValue(null);

      const store = useWishlistStore();

      await expect(
        store.updateWishlist('wishlist:nonexistent', { name: 'New Name' })
      ).rejects.toThrow('Wishlist not found');

      expect(mockUpsert).not.toHaveBeenCalled();
    });

    it('should update currentWishlist when updating the same wishlist', async () => {
      const existingDoc = createMockWishlistDoc({
        id: 'wishlist:current-123',
        name: 'Current Wishlist',
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(existingDoc);

      const store = useWishlistStore();

      // Set current wishlist first
      await store.fetchWishlist('wishlist:current-123');
      expect(store.currentWishlist?.name).toBe('Current Wishlist');

      // Update should also update currentWishlist
      mockUpsert.mockResolvedValue({ ...existingDoc, name: 'Updated Name' });
      await store.updateWishlist('wishlist:current-123', { name: 'Updated Name' });

      expect(store.currentWishlist?.name).toBe('Updated Name');
    });

    it('should update updated_at timestamp', async () => {
      const existingDoc = createMockWishlistDoc({
        id: 'wishlist:test',
        owner_id: mockUser.id,
        updated_at: '2024-01-01T00:00:00Z',
      });
      mockFindById.mockResolvedValue(existingDoc);

      const store = useWishlistStore();
      const beforeUpdate = new Date().toISOString();

      await store.updateWishlist('wishlist:test', { name: 'Updated' });

      const upsertCall = mockUpsert.mock.calls[0][0];
      expect(new Date(upsertCall.updated_at).getTime()).toBeGreaterThanOrEqual(
        new Date(beforeUpdate).getTime()
      );
    });
  });

  describe('deleteWishlist', () => {
    it('should soft delete wishlist with _deleted flag', async () => {
      const store = useWishlistStore();

      await store.deleteWishlist('wishlist:to-delete');

      expect(mockSoftDelete).toHaveBeenCalledWith('wishlist:to-delete');
      expect(mockTriggerSync).toHaveBeenCalled();
    });

    it('should clear currentWishlist when deleting the current one', async () => {
      const existingDoc = createMockWishlistDoc({
        id: 'wishlist:current',
        name: 'Current',
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(existingDoc);

      const store = useWishlistStore();

      // Set current wishlist
      await store.fetchWishlist('wishlist:current');
      expect(store.currentWishlist).not.toBeNull();

      // Delete it
      await store.deleteWishlist('wishlist:current');

      expect(store.currentWishlist).toBeNull();
    });

    it('should not clear currentWishlist when deleting a different wishlist', async () => {
      const currentDoc = createMockWishlistDoc({
        id: 'wishlist:current',
        name: 'Current',
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(currentDoc);

      const store = useWishlistStore();

      // Set current wishlist
      await store.fetchWishlist('wishlist:current');
      expect(store.currentWishlist).not.toBeNull();

      // Delete a different wishlist
      await store.deleteWishlist('wishlist:other');

      expect(store.currentWishlist).not.toBeNull();
    });
  });

  describe('fetchWishlist', () => {
    it('should fetch wishlist by ID and set currentWishlist', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: 'wishlist:fetch-test',
        name: 'Fetched Wishlist',
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useWishlistStore();

      await store.fetchWishlist('wishlist:fetch-test');

      expect(mockFindById).toHaveBeenCalledWith('wishlist:fetch-test');
      expect(store.currentWishlist).toEqual(
        expect.objectContaining({
          id: 'wishlist:fetch-test',
          name: 'Fetched Wishlist',
        })
      );
    });

    it('should set currentWishlist to null when wishlist not found', async () => {
      mockFindById.mockResolvedValue(null);

      const store = useWishlistStore();

      await store.fetchWishlist('wishlist:nonexistent');

      expect(store.currentWishlist).toBeNull();
    });

    it('should set isLoading during fetch', async () => {
      let resolveFind: (value: WishlistDoc | null) => void;
      mockFindById.mockReturnValue(
        new Promise((resolve) => {
          resolveFind = resolve;
        })
      );

      const store = useWishlistStore();
      const fetchPromise = store.fetchWishlist('wishlist:test');

      expect(store.isLoading).toBe(true);

      resolveFind!(createMockWishlistDoc({ id: 'wishlist:test', owner_id: mockUser.id }));
      await fetchPromise;

      expect(store.isLoading).toBe(false);
    });
  });

  describe('cleanup', () => {
    it('should unsubscribe and clear all state', async () => {
      const store = useWishlistStore();

      // Initialize to setup subscription
      await store.initializeStore();

      // Manually set some state
      const wishlistDoc = createMockWishlistDoc({
        id: 'wishlist:test',
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);
      await store.fetchWishlist('wishlist:test');

      // Cleanup
      store.cleanup();

      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(store.wishlists).toEqual([]);
      expect(store.currentWishlist).toBeNull();
      expect(store.total).toBe(0);
      expect(store.isInitialized).toBe(false);
    });

    it('should handle cleanup when not initialized', () => {
      const store = useWishlistStore();

      // Should not throw
      store.cleanup();

      expect(mockUnsubscribe).not.toHaveBeenCalled();
    });
  });

  describe('docToWishlist mapping', () => {
    it('should correctly map PouchDB doc to Wishlist type', async () => {
      const doc = createMockWishlistDoc({
        id: 'wishlist:map-test',
        owner_id: 'user:owner-123',
        name: 'Test Wishlist',
        description: 'Test description',
        is_public: true,
        icon: 'star',
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T12:00:00Z',
      });
      mockFindById.mockResolvedValue(doc);

      const store = useWishlistStore();
      await store.fetchWishlist('wishlist:map-test');

      expect(store.currentWishlist).toEqual({
        id: 'wishlist:map-test',
        user_id: 'user:owner-123',
        name: 'Test Wishlist',
        description: 'Test description',
        is_public: true,
        icon: 'star',
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T12:00:00Z',
      });
    });

    it('should use default icon when not provided', async () => {
      const doc = createMockWishlistDoc({
        id: 'wishlist:no-icon',
        owner_id: mockUser.id,
      });
      // Remove icon from doc
      delete (doc as Partial<WishlistDoc>).icon;
      mockFindById.mockResolvedValue(doc);

      const store = useWishlistStore();
      await store.fetchWishlist('wishlist:no-icon');

      expect(store.currentWishlist?.icon).toBe('card_giftcard');
    });

    it('should handle null description', async () => {
      const doc = createMockWishlistDoc({
        id: 'wishlist:no-desc',
        owner_id: mockUser.id,
        description: null,
      });
      mockFindById.mockResolvedValue(doc);

      const store = useWishlistStore();
      await store.fetchWishlist('wishlist:no-desc');

      expect(store.currentWishlist?.description).toBeNull();
    });
  });

  describe('wishlists reactive to PouchDB changes', () => {
    it('should update wishlists when subscription callback is called', async () => {
      let subscriptionCallback: ((docs: WishlistDoc[]) => void) | null = null;

      mockSubscribeToWishlists.mockImplementation((userId, callback) => {
        subscriptionCallback = callback;
        return mockUnsubscribe;
      });

      const store = useWishlistStore();
      await store.initializeStore();

      expect(subscriptionCallback).not.toBeNull();

      // Simulate PouchDB change
      const wishlists = [
        createMockWishlistDoc({ id: 'wishlist:1', name: 'First', owner_id: mockUser.id }),
        createMockWishlistDoc({ id: 'wishlist:2', name: 'Second', owner_id: mockUser.id }),
      ];
      subscriptionCallback!(wishlists);

      expect(store.wishlists).toHaveLength(2);
      expect(store.wishlists[0].name).toBe('First');
      expect(store.wishlists[1].name).toBe('Second');
      expect(store.total).toBe(2);
    });

    it('should update total when wishlists change', async () => {
      let subscriptionCallback: ((docs: WishlistDoc[]) => void) | null = null;

      mockSubscribeToWishlists.mockImplementation((userId, callback) => {
        subscriptionCallback = callback;
        return mockUnsubscribe;
      });

      const store = useWishlistStore();
      await store.initializeStore();

      // Start with 2 wishlists
      subscriptionCallback!([
        createMockWishlistDoc({ id: 'wishlist:1', owner_id: mockUser.id }),
        createMockWishlistDoc({ id: 'wishlist:2', owner_id: mockUser.id }),
      ]);
      expect(store.total).toBe(2);

      // Update to 3 wishlists
      subscriptionCallback!([
        createMockWishlistDoc({ id: 'wishlist:1', owner_id: mockUser.id }),
        createMockWishlistDoc({ id: 'wishlist:2', owner_id: mockUser.id }),
        createMockWishlistDoc({ id: 'wishlist:3', owner_id: mockUser.id }),
      ]);
      expect(store.total).toBe(3);
    });

    it('should set isLoading to false after subscription callback', async () => {
      let subscriptionCallback: ((docs: WishlistDoc[]) => void) | null = null;

      mockSubscribeToWishlists.mockImplementation((userId, callback) => {
        subscriptionCallback = callback;
        return mockUnsubscribe;
      });

      const store = useWishlistStore();
      await store.initializeStore();

      // isLoading should still be true until callback fires
      expect(store.isLoading).toBe(true);

      // Fire callback
      subscriptionCallback!([]);

      expect(store.isLoading).toBe(false);
    });
  });

  describe('clearWishlists', () => {
    it('should call cleanup', async () => {
      const store = useWishlistStore();
      await store.initializeStore();

      store.clearWishlists();

      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(store.isInitialized).toBe(false);
    });
  });

  describe('fetchWishlists', () => {
    it('should initialize store if not initialized', async () => {
      const store = useWishlistStore();

      expect(store.isInitialized).toBe(false);

      await store.fetchWishlists();

      expect(mockSubscribeToWishlists).toHaveBeenCalled();
      expect(store.isInitialized).toBe(true);
    });

    it('should not re-initialize if already initialized', async () => {
      const store = useWishlistStore();

      await store.initializeStore();
      vi.clearAllMocks();

      await store.fetchWishlists();

      expect(mockSubscribeToWishlists).not.toHaveBeenCalled();
    });
  });
});
