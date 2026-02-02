/**
 * Unit tests for the item store.
 * Tests item CRUD operations with offline-first PouchDB architecture.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useItemStore } from '../item';
import { useAuthStore } from '../auth';
import type { ItemDoc, WishlistDoc } from '@/services/pouchdb/types';
import {
  createMockItemDoc,
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
const mockSubscribeToItems = vi.fn(() => mockUnsubscribe);
const mockGetDatabase = vi.fn();
const mockFindById = vi.fn();
const mockUpsert = vi.fn();
const mockSoftDelete = vi.fn();
const mockTriggerSync = vi.fn();
const mockCreateId = vi.fn((type: string) => `${type}:test-uuid-456`);

vi.mock('@/services/pouchdb', () => ({
  getDatabase: () => mockGetDatabase(),
  subscribeToItems: (wishlistId: string, callback: (docs: ItemDoc[]) => void) =>
    mockSubscribeToItems(wishlistId, callback),
  findById: (id: string) => mockFindById(id),
  upsert: (doc: ItemDoc) => mockUpsert(doc),
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

describe('useItemStore', () => {
  const mockUser = createMockUser({ id: 'user:test-123' });
  const testWishlistId = 'wishlist:test-wishlist';
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

    // Default mock implementations
    mockUpsert.mockImplementation(async (doc) => ({ ...doc, _rev: '1-mock' }));
    mockFindById.mockResolvedValue(null);
    mockSoftDelete.mockResolvedValue(undefined);
    mockTriggerSync.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('createItem', () => {
    it('should create item with URL and set status to pending', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
        access: [mockUser.id, 'user:shared-user'],
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      const result = await store.createItem(testWishlistId, {
        title: 'Product from URL',
        source_url: 'https://example.com/product/123',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'item:test-uuid-456',
          type: 'item',
          wishlist_id: testWishlistId,
          owner_id: mockUser.id,
          title: 'Product from URL',
          source_url: 'https://example.com/product/123',
          status: 'pending',
        })
      );
      expect(result.status).toBe('pending');
    });

    it('should create manual item with skip_resolution and set status to resolved', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      const result = await store.createItem(testWishlistId, {
        title: 'Manual Item',
        description: 'Manually added',
        source_url: 'https://example.com/product',
        skip_resolution: true,
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Manual Item',
          status: 'resolved',
          source_url: 'https://example.com/product',
        })
      );
      expect(result.status).toBe('resolved');
    });

    it('should create item without URL and set status to resolved', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      const result = await store.createItem(testWishlistId, {
        title: 'Manual Item Without URL',
        price: '1500',
        currency: 'RUB',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Manual Item Without URL',
          status: 'resolved',
          source_url: null,
        })
      );
      expect(result.status).toBe('resolved');
    });

    it('should inherit wishlist access array', async () => {
      const sharedAccess = [mockUser.id, 'user:friend-1', 'user:friend-2'];
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
        access: sharedAccess,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      await store.createItem(testWishlistId, {
        title: 'Shared Item',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          access: sharedAccess,
        })
      );
    });

    it('should use user ID as fallback when wishlist not found', async () => {
      mockFindById.mockResolvedValue(null);

      const store = useItemStore();

      await store.createItem(testWishlistId, {
        title: 'Item without wishlist',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          access: [mockUser.id],
        })
      );
    });

    it('should throw error when user is not authenticated', async () => {
      mockAuthStore.userId = null;

      const store = useItemStore();

      await expect(
        store.createItem(testWishlistId, { title: 'Test' })
      ).rejects.toThrow('User not authenticated');

      expect(mockUpsert).not.toHaveBeenCalled();
    });

    it('should convert price string to number', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      await store.createItem(testWishlistId, {
        title: 'Priced Item',
        price: '1500.50',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          price: 1500.5,
        })
      );
    });

    it('should trigger sync when online', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      await store.createItem(testWishlistId, { title: 'Online Item' });

      expect(mockTriggerSync).toHaveBeenCalledWith('test-access-token');
    });

    it('should show offline notification when offline', async () => {
      mockIsOnline.mockReturnValue(false);
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      await store.createItem(testWishlistId, { title: 'Offline Item' });

      expect(mockTriggerSync).not.toHaveBeenCalled();
      expect(mockNotifyCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'offline.createdOffline',
          icon: 'cloud_off',
        })
      );
    });
  });

  describe('updateItem', () => {
    it('should modify existing item and handle price conversion', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:existing-123',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        title: 'Old Title',
        price: 1000,
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      const result = await store.updateItem(testWishlistId, 'item:existing-123', {
        title: 'New Title',
        price: '2500.99',
      });

      expect(mockFindById).toHaveBeenCalledWith('item:existing-123');
      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'item:existing-123',
          title: 'New Title',
          price: 2500.99,
        })
      );
      expect(result.title).toBe('New Title');
    });

    it('should preserve original price when not provided in update', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:keep-price',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        price: 5000,
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      await store.updateItem(testWishlistId, 'item:keep-price', {
        title: 'Updated Title',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          price: 5000, // Original price preserved
        })
      );
    });

    it('should throw error when item does not exist', async () => {
      mockFindById.mockResolvedValue(null);

      const store = useItemStore();

      await expect(
        store.updateItem(testWishlistId, 'item:nonexistent', { title: 'New' })
      ).rejects.toThrow('Item not found');

      expect(mockUpsert).not.toHaveBeenCalled();
    });

    it('should update currentItem when updating the same item', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:current',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        title: 'Current Item',
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      // Fetch item first
      await store.fetchItem(testWishlistId, 'item:current');
      expect(store.currentItem?.title).toBe('Current Item');

      // Update should update currentItem
      mockUpsert.mockResolvedValue({ ...existingItem, title: 'Updated' });
      await store.updateItem(testWishlistId, 'item:current', { title: 'Updated' });

      expect(store.currentItem?.title).toBe('Updated');
    });

    it('should update updated_at timestamp', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:test',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        updated_at: '2024-01-01T00:00:00Z',
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();
      const beforeUpdate = new Date().toISOString();

      await store.updateItem(testWishlistId, 'item:test', { title: 'Updated' });

      const upsertCall = mockUpsert.mock.calls[0][0];
      expect(new Date(upsertCall.updated_at).getTime()).toBeGreaterThanOrEqual(
        new Date(beforeUpdate).getTime()
      );
    });
  });

  describe('deleteItem', () => {
    it('should soft delete item', async () => {
      const store = useItemStore();

      await store.deleteItem(testWishlistId, 'item:to-delete');

      expect(mockSoftDelete).toHaveBeenCalledWith('item:to-delete');
      expect(mockTriggerSync).toHaveBeenCalled();
    });

    it('should clear currentItem when deleting the current one', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:current',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      // Set current item
      await store.fetchItem(testWishlistId, 'item:current');
      expect(store.currentItem).not.toBeNull();

      // Delete it
      await store.deleteItem(testWishlistId, 'item:current');

      expect(store.currentItem).toBeNull();
    });

    it('should not clear currentItem when deleting a different item', async () => {
      const currentItem = createMockItemDoc({
        id: 'item:current',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(currentItem);

      const store = useItemStore();

      // Set current item
      await store.fetchItem(testWishlistId, 'item:current');
      expect(store.currentItem).not.toBeNull();

      // Delete a different item
      await store.deleteItem(testWishlistId, 'item:other');

      expect(store.currentItem).not.toBeNull();
    });
  });

  describe('retryResolve', () => {
    it('should set status to pending and trigger sync', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:retry',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        status: 'error',
        source_url: 'https://example.com/product',
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      await store.retryResolve(testWishlistId, 'item:retry');

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'item:retry',
          status: 'pending',
        })
      );
      expect(mockTriggerSync).toHaveBeenCalledWith('test-access-token');
    });

    it('should throw error when offline', async () => {
      mockIsOnline.mockReturnValue(false);
      const existingItem = createMockItemDoc({
        id: 'item:retry-offline',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        status: 'error',
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      await expect(
        store.retryResolve(testWishlistId, 'item:retry-offline')
      ).rejects.toThrow('Cannot resolve item while offline');

      expect(mockNotifyCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'offline.youAreOffline',
          icon: 'cloud_off',
          color: 'warning',
        })
      );
    });

    it('should throw error when no access token', async () => {
      mockAuthStore.getAccessToken = vi.fn(() => null);
      const existingItem = createMockItemDoc({
        id: 'item:retry-no-token',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        status: 'error',
      });
      mockFindById.mockResolvedValue(existingItem);

      const store = useItemStore();

      await expect(
        store.retryResolve(testWishlistId, 'item:retry-no-token')
      ).rejects.toThrow('Cannot resolve item while offline');
    });

    it('should return updated item after successful retry', async () => {
      const existingItem = createMockItemDoc({
        id: 'item:retry-success',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        status: 'error',
        title: 'Original Title',
      });

      // First call returns existing item, second call (after sync) returns updated
      mockFindById
        .mockResolvedValueOnce(existingItem)
        .mockResolvedValueOnce({ ...existingItem, status: 'pending' });

      const store = useItemStore();

      const result = await store.retryResolve(testWishlistId, 'item:retry-success');

      expect(result.status).toBe('pending');
    });
  });

  describe('subscribeToWishlistItems', () => {
    it('should clean up previous subscription when switching wishlists', async () => {
      const store = useItemStore();

      // Subscribe to first wishlist
      await store.fetchItems('wishlist:first');
      expect(mockSubscribeToItems).toHaveBeenCalledWith(
        'wishlist:first',
        expect.any(Function)
      );

      // Subscribe to second wishlist
      await store.fetchItems('wishlist:second');

      // Previous subscription should be cancelled
      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(mockSubscribeToItems).toHaveBeenCalledWith(
        'wishlist:second',
        expect.any(Function)
      );
    });

    it('should update currentWishlistId when subscribing', async () => {
      const store = useItemStore();

      await store.fetchItems('wishlist:new');

      // Access internal state via items subscription behavior
      expect(mockSubscribeToItems).toHaveBeenCalledWith(
        'wishlist:new',
        expect.any(Function)
      );
    });
  });

  describe('fetchItems', () => {
    it('should switch subscription when wishlist ID changes', async () => {
      const store = useItemStore();

      await store.fetchItems('wishlist:first');
      vi.clearAllMocks();

      await store.fetchItems('wishlist:second');

      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(mockSubscribeToItems).toHaveBeenCalledWith(
        'wishlist:second',
        expect.any(Function)
      );
    });

    it('should not re-subscribe when fetching same wishlist', async () => {
      const store = useItemStore();

      await store.fetchItems('wishlist:same');
      vi.clearAllMocks();

      // Fetch same wishlist again
      await store.fetchItems('wishlist:same');

      // Should not create new subscription
      expect(mockSubscribeToItems).not.toHaveBeenCalled();
    });

    it('should set isLoading when switching wishlists', async () => {
      const store = useItemStore();

      // Set up a slow subscription
      let subscriptionCallback: ((docs: ItemDoc[]) => void) | null = null;
      mockSubscribeToItems.mockImplementation((wishlistId, callback) => {
        subscriptionCallback = callback;
        return mockUnsubscribe;
      });

      const fetchPromise = store.fetchItems('wishlist:new');

      expect(store.isLoading).toBe(true);

      // Simulate subscription callback
      subscriptionCallback!([]);
      await fetchPromise;

      expect(store.isLoading).toBe(false);
    });
  });

  describe('docToItem price conversion', () => {
    it('should convert number price to string', async () => {
      const itemDoc = createMockItemDoc({
        id: 'item:price-test',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        price: 1500.5,
      });
      mockFindById.mockResolvedValue(itemDoc);

      const store = useItemStore();
      await store.fetchItem(testWishlistId, 'item:price-test');

      expect(store.currentItem?.price).toBe('1500.5');
    });

    it('should handle null price', async () => {
      const itemDoc = createMockItemDoc({
        id: 'item:no-price',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        price: null,
      });
      mockFindById.mockResolvedValue(itemDoc);

      const store = useItemStore();
      await store.fetchItem(testWishlistId, 'item:no-price');

      expect(store.currentItem?.price).toBeNull();
    });

    it('should handle zero price', async () => {
      const itemDoc = createMockItemDoc({
        id: 'item:zero-price',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        price: 0,
      });
      mockFindById.mockResolvedValue(itemDoc);

      const store = useItemStore();
      await store.fetchItem(testWishlistId, 'item:zero-price');

      // 0 is falsy, so should be null
      expect(store.currentItem?.price).toBeNull();
    });

    it('should correctly map all ItemDoc fields to Item type', async () => {
      const itemDoc = createMockItemDoc({
        id: 'item:full-mapping',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        title: 'Full Item',
        description: 'Full description',
        price: 2500,
        currency: 'USD',
        quantity: 2,
        source_url: 'https://example.com/product',
        image_url: 'https://example.com/image.jpg',
        image_base64: 'data:image/png;base64,abc123',
        status: 'resolved',
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T12:00:00Z',
      });
      mockFindById.mockResolvedValue(itemDoc);

      const store = useItemStore();
      await store.fetchItem(testWishlistId, 'item:full-mapping');

      expect(store.currentItem).toEqual({
        id: 'item:full-mapping',
        wishlist_id: testWishlistId,
        title: 'Full Item',
        description: 'Full description',
        price: '2500',
        currency: 'USD',
        quantity: 2,
        source_url: 'https://example.com/product',
        image_url: 'https://example.com/image.jpg',
        image_base64: 'data:image/png;base64,abc123',
        status: 'resolved',
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T12:00:00Z',
      });
    });
  });

  describe('clearItems', () => {
    it('should unsubscribe and clear all state', async () => {
      const store = useItemStore();

      // Subscribe to items
      await store.fetchItems(testWishlistId);

      // Set current item
      const itemDoc = createMockItemDoc({
        id: 'item:test',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(itemDoc);
      await store.fetchItem(testWishlistId, 'item:test');

      // Clear
      store.clearItems();

      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(store.items).toEqual([]);
      expect(store.currentItem).toBeNull();
      expect(store.total).toBe(0);
    });

    it('should handle clearItems when not subscribed', () => {
      const store = useItemStore();

      // Should not throw
      store.clearItems();

      expect(mockUnsubscribe).not.toHaveBeenCalled();
    });
  });

  describe('items reactive to PouchDB changes', () => {
    it('should update items when subscription callback is called', async () => {
      let subscriptionCallback: ((docs: ItemDoc[]) => void) | null = null;

      mockSubscribeToItems.mockImplementation((wishlistId, callback) => {
        subscriptionCallback = callback;
        return mockUnsubscribe;
      });

      const store = useItemStore();
      await store.fetchItems(testWishlistId);

      expect(subscriptionCallback).not.toBeNull();

      // Simulate PouchDB change
      const items = [
        createMockItemDoc({
          id: 'item:1',
          title: 'First Item',
          wishlist_id: testWishlistId,
          owner_id: mockUser.id,
        }),
        createMockItemDoc({
          id: 'item:2',
          title: 'Second Item',
          wishlist_id: testWishlistId,
          owner_id: mockUser.id,
        }),
      ];
      subscriptionCallback!(items);

      expect(store.items).toHaveLength(2);
      expect(store.items[0].title).toBe('First Item');
      expect(store.items[1].title).toBe('Second Item');
      expect(store.total).toBe(2);
    });

    it('should update total when items change', async () => {
      let subscriptionCallback: ((docs: ItemDoc[]) => void) | null = null;

      mockSubscribeToItems.mockImplementation((wishlistId, callback) => {
        subscriptionCallback = callback;
        return mockUnsubscribe;
      });

      const store = useItemStore();
      await store.fetchItems(testWishlistId);

      // Start with 2 items
      subscriptionCallback!([
        createMockItemDoc({ id: 'item:1', wishlist_id: testWishlistId, owner_id: mockUser.id }),
        createMockItemDoc({ id: 'item:2', wishlist_id: testWishlistId, owner_id: mockUser.id }),
      ]);
      expect(store.total).toBe(2);

      // Update to 5 items
      subscriptionCallback!([
        createMockItemDoc({ id: 'item:1', wishlist_id: testWishlistId, owner_id: mockUser.id }),
        createMockItemDoc({ id: 'item:2', wishlist_id: testWishlistId, owner_id: mockUser.id }),
        createMockItemDoc({ id: 'item:3', wishlist_id: testWishlistId, owner_id: mockUser.id }),
        createMockItemDoc({ id: 'item:4', wishlist_id: testWishlistId, owner_id: mockUser.id }),
        createMockItemDoc({ id: 'item:5', wishlist_id: testWishlistId, owner_id: mockUser.id }),
      ]);
      expect(store.total).toBe(5);
    });
  });

  describe('fetchItem', () => {
    it('should fetch item by ID and set currentItem', async () => {
      const itemDoc = createMockItemDoc({
        id: 'item:fetch-test',
        wishlist_id: testWishlistId,
        owner_id: mockUser.id,
        title: 'Fetched Item',
      });
      mockFindById.mockResolvedValue(itemDoc);

      const store = useItemStore();

      await store.fetchItem(testWishlistId, 'item:fetch-test');

      expect(mockFindById).toHaveBeenCalledWith('item:fetch-test');
      expect(store.currentItem).toEqual(
        expect.objectContaining({
          id: 'item:fetch-test',
          title: 'Fetched Item',
        })
      );
    });

    it('should set currentItem to null when item not found', async () => {
      mockFindById.mockResolvedValue(null);

      const store = useItemStore();

      await store.fetchItem(testWishlistId, 'item:nonexistent');

      expect(store.currentItem).toBeNull();
    });

    it('should set isLoading during fetch', async () => {
      let resolveFind: (value: ItemDoc | null) => void;
      mockFindById.mockReturnValue(
        new Promise((resolve) => {
          resolveFind = resolve;
        })
      );

      const store = useItemStore();
      const fetchPromise = store.fetchItem(testWishlistId, 'item:test');

      expect(store.isLoading).toBe(true);

      resolveFind!(
        createMockItemDoc({
          id: 'item:test',
          wishlist_id: testWishlistId,
          owner_id: mockUser.id,
        })
      );
      await fetchPromise;

      expect(store.isLoading).toBe(false);
    });
  });

  describe('create item with all optional fields', () => {
    it('should handle all optional fields correctly', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      await store.createItem(testWishlistId, {
        title: 'Full Item',
        description: 'Full description',
        price: '1999.99',
        currency: 'EUR',
        quantity: 3,
        source_url: 'https://example.com/product',
        image_url: 'https://example.com/image.jpg',
        image_base64: 'data:image/png;base64,xyz',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Full Item',
          description: 'Full description',
          price: 1999.99,
          currency: 'EUR',
          quantity: 3,
          source_url: 'https://example.com/product',
          image_url: 'https://example.com/image.jpg',
          image_base64: 'data:image/png;base64,xyz',
          status: 'pending', // Has source_url and no skip_resolution
        })
      );
    });

    it('should use default quantity of 1', async () => {
      const wishlistDoc = createMockWishlistDoc({
        id: testWishlistId,
        owner_id: mockUser.id,
      });
      mockFindById.mockResolvedValue(wishlistDoc);

      const store = useItemStore();

      await store.createItem(testWishlistId, {
        title: 'Default Quantity Item',
      });

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          quantity: 1,
        })
      );
    });
  });
});
