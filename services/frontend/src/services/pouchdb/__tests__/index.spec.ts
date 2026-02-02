/**
 * Unit tests for PouchDB service.
 * Tests offline-first data storage and sync functionality.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { WishlistDoc } from '../types';

// Use vi.hoisted to ensure mocks are available before module imports
const mocks = vi.hoisted(() => {
  const mockChangesEmitter = {
    on: vi.fn().mockReturnThis(),
    cancel: vi.fn(),
  };

  return {
    mockPut: vi.fn(),
    mockGet: vi.fn(),
    mockFind: vi.fn(),
    mockAllDocs: vi.fn(),
    mockChanges: vi.fn().mockReturnValue({
      ...mockChangesEmitter,
      results: [],
    }),
    mockDestroy: vi.fn(),
    mockCompact: vi.fn(),
    mockCreateIndex: vi.fn(),
    mockBulkDocs: vi.fn(),
    mockChangesEmitter,
    mockFetch: vi.fn(),
  };
});

// Mock PouchDB before importing the module
vi.mock('pouchdb-browser', () => {
  const MockPouchDB = vi.fn().mockImplementation(() => ({
    put: mocks.mockPut,
    get: mocks.mockGet,
    find: mocks.mockFind,
    allDocs: mocks.mockAllDocs,
    changes: mocks.mockChanges,
    destroy: mocks.mockDestroy,
    compact: mocks.mockCompact,
    createIndex: mocks.mockCreateIndex,
    bulkDocs: mocks.mockBulkDocs,
  }));
  MockPouchDB.plugin = vi.fn();
  return { default: MockPouchDB };
});

vi.mock('pouchdb-find', () => ({
  default: {},
}));

// Mock fetch for sync operations
vi.stubGlobal('fetch', mocks.mockFetch);

describe('PouchDB Service', () => {
  // Use dynamic import to get fresh module state
  let pouchdbService: typeof import('../index');

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Reset navigator.onLine
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true });

    // Reset mock implementations
    mocks.mockPut.mockResolvedValue({ ok: true, rev: '1-abc' });
    mocks.mockGet.mockRejectedValue({ status: 404 });
    mocks.mockFind.mockResolvedValue({ docs: [] });
    mocks.mockAllDocs.mockResolvedValue({ rows: [] });
    mocks.mockDestroy.mockResolvedValue({ ok: true });
    mocks.mockCreateIndex.mockResolvedValue({ result: 'created' });
    mocks.mockCompact.mockResolvedValue(undefined);
    mocks.mockBulkDocs.mockResolvedValue([]);

    // Reset changes mock with results property
    mocks.mockChanges.mockReturnValue({
      ...mocks.mockChangesEmitter,
      results: [],
    });

    // Reset changes emitter
    mocks.mockChangesEmitter.on.mockClear();
    mocks.mockChangesEmitter.cancel.mockClear();
    mocks.mockChangesEmitter.on.mockReturnThis();

    // Reset fetch mock
    mocks.mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ documents: [] }),
    });

    // Reset module to get fresh singleton state
    vi.resetModules();
    pouchdbService = await import('../index');
  });

  afterEach(() => {
    vi.useRealTimers();
    // Clean up sync state
    pouchdbService.stopSync();
  });

  describe('getDatabase', () => {
    it('creates singleton and returns same instance', () => {
      const db1 = pouchdbService.getDatabase();
      const db2 = pouchdbService.getDatabase();

      // Should return the same instance (both have same methods)
      expect(db1).toBe(db2);
    });

    it('creates indexes on first database access', () => {
      pouchdbService.getDatabase();

      // Should create multiple indexes
      expect(mocks.mockCreateIndex).toHaveBeenCalled();
    });
  });

  describe('createIndexes', () => {
    it('creates all required indexes', () => {
      // getDatabase triggers createIndexes
      pouchdbService.getDatabase();

      // Verify indexes are created
      expect(mocks.mockCreateIndex).toHaveBeenCalled();
    });
  });

  describe('find', () => {
    it('excludes deleted documents by default', async () => {
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'wishlist:1', type: 'wishlist', name: 'Test' },
        ],
      });

      await pouchdbService.find({ selector: { type: 'wishlist' } });

      // Should wrap selector with _deleted exclusion
      expect(mocks.mockFind).toHaveBeenCalledWith(
        expect.objectContaining({
          selector: expect.objectContaining({
            $and: expect.arrayContaining([
              { type: 'wishlist' },
              expect.objectContaining({
                $or: [
                  { _deleted: { $exists: false } },
                  { _deleted: false },
                ],
              }),
            ]),
          }),
        })
      );
    });

    it('handles tombstone errors by compacting and retrying', async () => {
      const tombstoneError = new TypeError("Cannot read properties of undefined (reading 'x')");

      mocks.mockFind
        .mockRejectedValueOnce(tombstoneError)
        .mockResolvedValueOnce({ docs: [{ _id: 'wishlist:1', type: 'wishlist' }] });

      const result = await pouchdbService.find({ selector: { type: 'wishlist' } });

      // Should compact database
      expect(mocks.mockCompact).toHaveBeenCalled();

      // Should retry find
      expect(mocks.mockFind).toHaveBeenCalledTimes(2);

      // Should return results
      expect(result).toHaveLength(1);
    });

    it('returns empty array when retry also fails', async () => {
      const tombstoneError = new TypeError("Cannot read properties of undefined (reading 'x')");

      mocks.mockFind
        .mockRejectedValueOnce(tombstoneError)
        .mockRejectedValueOnce(tombstoneError);

      const result = await pouchdbService.find({ selector: { type: 'wishlist' } });

      expect(result).toEqual([]);
    });

    it('filters out incomplete documents', async () => {
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'wishlist:1', type: 'wishlist' },
          undefined,
          null,
          { type: 'wishlist' }, // Missing _id
        ],
      });

      const result = await pouchdbService.find({ selector: { type: 'wishlist' } });

      expect(result).toHaveLength(1);
      expect(result[0]._id).toBe('wishlist:1');
    });
  });

  describe('findById', () => {
    it('returns null for deleted document', async () => {
      mocks.mockGet.mockResolvedValue({
        _id: 'wishlist:1',
        _rev: '1-abc',
        _deleted: true,
        type: 'wishlist',
      });

      const result = await pouchdbService.findById('wishlist:1');

      expect(result).toBeNull();
    });

    it('returns null for 404 error', async () => {
      mocks.mockGet.mockRejectedValue({ status: 404 });

      const result = await pouchdbService.findById('wishlist:nonexistent');

      expect(result).toBeNull();
    });

    it('returns document when found', async () => {
      const doc = {
        _id: 'wishlist:1',
        _rev: '1-abc',
        type: 'wishlist',
        name: 'Test',
      };
      mocks.mockGet.mockResolvedValue(doc);

      const result = await pouchdbService.findById('wishlist:1');

      expect(result).toEqual(doc);
    });

    it('throws for non-404 errors', async () => {
      mocks.mockGet.mockRejectedValue({ status: 500, message: 'Server error' });

      await expect(pouchdbService.findById('wishlist:1')).rejects.toEqual({
        status: 500,
        message: 'Server error',
      });
    });
  });

  describe('upsert', () => {
    it('creates new document with _rev', async () => {
      mocks.mockGet.mockRejectedValue({ status: 404 });
      mocks.mockPut.mockResolvedValue({ ok: true, rev: '1-new' });

      const doc = {
        _id: 'wishlist:1',
        type: 'wishlist' as const,
        name: 'New Wishlist',
        owner_id: 'user:1',
        access: ['user:1'],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        icon: 'gift',
        is_public: false,
      };

      const result = await pouchdbService.upsert(doc);

      expect(mocks.mockPut).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'wishlist:1',
          _rev: undefined, // No existing revision
          name: 'New Wishlist',
        })
      );
      expect(result._rev).toBe('1-new');
    });

    it('updates existing document with existing _rev', async () => {
      mocks.mockGet.mockResolvedValue({ _id: 'wishlist:1', _rev: '1-old' });
      mocks.mockPut.mockResolvedValue({ ok: true, rev: '2-updated' });

      const doc = {
        _id: 'wishlist:1',
        type: 'wishlist' as const,
        name: 'Updated Wishlist',
        owner_id: 'user:1',
        access: ['user:1'],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        icon: 'gift',
        is_public: false,
      };

      const result = await pouchdbService.upsert(doc);

      expect(mocks.mockPut).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'wishlist:1',
          _rev: '1-old', // Uses existing revision
        })
      );
      expect(result._rev).toBe('2-updated');
    });

    it('sets updated_at timestamp', async () => {
      const now = new Date('2024-06-15T12:00:00Z');
      vi.setSystemTime(now);

      mocks.mockGet.mockRejectedValue({ status: 404 });
      mocks.mockPut.mockResolvedValue({ ok: true, rev: '1-new' });

      const doc = {
        _id: 'wishlist:1',
        type: 'wishlist' as const,
        name: 'Test',
        owner_id: 'user:1',
        access: ['user:1'],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        icon: 'gift',
        is_public: false,
      };

      await pouchdbService.upsert(doc);

      expect(mocks.mockPut).toHaveBeenCalledWith(
        expect.objectContaining({
          updated_at: '2024-06-15T12:00:00.000Z',
        })
      );
    });
  });

  describe('softDelete', () => {
    it('sets _deleted flag on document', async () => {
      const existingDoc = {
        _id: 'wishlist:1',
        _rev: '1-abc',
        type: 'wishlist',
        name: 'Test',
      };
      mocks.mockGet.mockResolvedValue(existingDoc);
      mocks.mockPut.mockResolvedValue({ ok: true, rev: '2-deleted' });

      await pouchdbService.softDelete('wishlist:1');

      expect(mocks.mockPut).toHaveBeenCalledWith(
        expect.objectContaining({
          _id: 'wishlist:1',
          _rev: '1-abc',
          _deleted: true,
        })
      );
    });

    it('updates timestamp when soft deleting', async () => {
      const now = new Date('2024-06-15T12:00:00Z');
      vi.setSystemTime(now);

      mocks.mockGet.mockResolvedValue({ _id: 'wishlist:1', _rev: '1-abc' });
      mocks.mockPut.mockResolvedValue({ ok: true, rev: '2-deleted' });

      await pouchdbService.softDelete('wishlist:1');

      expect(mocks.mockPut).toHaveBeenCalledWith(
        expect.objectContaining({
          updated_at: '2024-06-15T12:00:00.000Z',
        })
      );
    });
  });

  describe('subscribeToChanges', () => {
    it('fires callback on changes', async () => {
      const callback = vi.fn();
      mocks.mockFind.mockResolvedValue({
        docs: [{ _id: 'wishlist:1', type: 'wishlist', name: 'Test' }],
      });

      const unsubscribe = pouchdbService.subscribeToChanges('wishlist', callback);

      // Wait for initial load
      await vi.runAllTimersAsync();

      // Initial load should trigger callback
      expect(callback).toHaveBeenCalledWith([
        expect.objectContaining({ _id: 'wishlist:1' }),
      ]);

      // Simulate a change event
      const changeHandler = mocks.mockChangesEmitter.on.mock.calls.find(
        (call: [string, unknown]) => call[0] === 'change'
      )?.[1] as ((change: { doc?: { _id: string; type: string } }) => Promise<void>) | undefined;

      if (changeHandler) {
        await changeHandler({
          doc: { _id: 'wishlist:2', type: 'wishlist' },
        });
        await vi.runAllTimersAsync();

        // Should reload docs
        expect(mocks.mockFind.mock.calls.length).toBeGreaterThan(1);
      }

      // Clean up
      unsubscribe();
      expect(mocks.mockChangesEmitter.cancel).toHaveBeenCalled();
    });

    it('applies filter function', async () => {
      const callback = vi.fn();
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'wishlist:1', type: 'wishlist', owner_id: 'user:1' },
          { _id: 'wishlist:2', type: 'wishlist', owner_id: 'user:2' },
        ],
      });

      const unsubscribe = pouchdbService.subscribeToChanges(
        'wishlist',
        callback,
        (doc: WishlistDoc) => doc.owner_id === 'user:1'
      );

      await vi.runAllTimersAsync();

      expect(callback).toHaveBeenCalledWith([
        expect.objectContaining({ _id: 'wishlist:1', owner_id: 'user:1' }),
      ]);

      unsubscribe();
    });
  });

  describe('pullFromServer', () => {
    it('deletes local docs not in server response (reconciliation)', async () => {
      // Setup: local has doc that server doesn't return
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'wishlist:local-only', _rev: '1-abc', type: 'wishlist', owner_id: 'user:1' },
        ],
      });

      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            documents: [
              // Server only returns different doc
              { _id: 'wishlist:server', type: 'wishlist', owner_id: 'user:1' },
            ],
          }),
      });

      mocks.mockGet
        .mockRejectedValueOnce({ status: 404 }) // For server doc (new)
        .mockResolvedValueOnce({ _id: 'wishlist:local-only', _rev: '1-abc' }); // For deletion

      // Trigger sync
      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      // Should have attempted to delete the local-only document
      const putCalls = mocks.mockPut.mock.calls;
      const deleteCall = putCalls.find((call: [{ _deleted?: boolean }]) => call[0]._deleted === true);
      expect(deleteCall).toBeDefined();
    });

    it('preserves failed push docs during reconciliation', async () => {
      // This tests that documents which failed to push are not deleted during pull
      // Setup: push will fail for a document
      mocks.mockChanges.mockReturnValue({
        ...mocks.mockChangesEmitter,
        results: [
          {
            id: 'wishlist:failed',
            doc: {
              _id: 'wishlist:failed',
              type: 'wishlist',
              owner_id: 'user:1',
            },
          },
        ],
      });

      // Push returns conflict without server_document
      mocks.mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              conflicts: [
                {
                  document_id: 'wishlist:failed',
                  error: 'access_denied',
                  // No server_document - this doc should be preserved
                },
              ],
            }),
        })
        .mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ documents: [], conflicts: [] }),
        });

      // Local find returns the failed doc
      mocks.mockFind.mockResolvedValue({
        docs: [{ _id: 'wishlist:failed', _rev: '1-abc', type: 'wishlist', owner_id: 'user:1' }],
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      // The failed doc should NOT be deleted
      const deleteCalls = mocks.mockPut.mock.calls.filter((call: [{ _deleted?: boolean }]) => call[0]._deleted === true);
      const failedDocDeleted = deleteCalls.some((call: [{ _id?: string }]) => call[0]._id === 'wishlist:failed');
      expect(failedDocDeleted).toBe(false);
    });
  });

  describe('pushToServer', () => {
    it('sends all local docs including deleted', async () => {
      // Changes feed returns both active and deleted docs
      mocks.mockChanges.mockReturnValue({
        ...mocks.mockChangesEmitter,
        results: [
          {
            id: 'wishlist:active',
            doc: { _id: 'wishlist:active', type: 'wishlist', owner_id: 'user:1' },
          },
          {
            id: 'wishlist:deleted',
            doc: { _id: 'wishlist:deleted', type: 'wishlist', _deleted: true, owner_id: 'user:1' },
          },
        ],
      });

      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      // Should have made push request with documents
      const pushCalls = mocks.mockFetch.mock.calls.filter(
        (call: [string, { method?: string }]) => call[0].includes('/push/') && call[1].method === 'POST'
      );
      expect(pushCalls.length).toBeGreaterThan(0);
    });

    it('handles conflicts by accepting server version', async () => {
      mocks.mockChanges.mockReturnValue({
        ...mocks.mockChangesEmitter,
        results: [
          {
            id: 'wishlist:conflict',
            doc: { _id: 'wishlist:conflict', type: 'wishlist', name: 'Local', owner_id: 'user:1' },
          },
        ],
      });

      // Server returns conflict with its version
      mocks.mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              conflicts: [
                {
                  document_id: 'wishlist:conflict',
                  error: 'conflict',
                  server_document: {
                    _id: 'wishlist:conflict',
                    type: 'wishlist',
                    name: 'Server Version',
                  },
                },
              ],
            }),
        })
        .mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ documents: [], conflicts: [] }),
        });

      // Existing doc for conflict resolution
      mocks.mockGet.mockResolvedValue({
        _id: 'wishlist:conflict',
        _rev: '1-local',
        type: 'wishlist',
        name: 'Local',
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      // Should update local with server version
      const serverUpdateCall = mocks.mockPut.mock.calls.find(
        (call: [{ name?: string }]) => call[0].name === 'Server Version'
      );
      expect(serverUpdateCall).toBeDefined();
    });
  });

  describe('triggerSync', () => {
    it('waits for in-progress sync', async () => {
      // Start a sync that takes some time
      let resolvePush: () => void = () => {};
      const pushPromise = new Promise<void>((resolve) => {
        resolvePush = resolve;
      });

      mocks.mockFetch.mockImplementation(() => pushPromise.then(() => ({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      })));

      // Start initial sync
      pouchdbService.startSync('user:1', 'token', { interval: 60000 });

      // Try to trigger another sync while first is running
      const triggerPromise = pouchdbService.triggerSync('token');

      // Status should be syncing
      expect(pouchdbService.getSyncStatus()).toBe('syncing');

      // Resolve the in-progress sync
      resolvePush();
      await vi.runAllTimersAsync();

      // Wait for trigger to complete
      await triggerPromise;

      expect(pouchdbService.getSyncStatus()).not.toBe('syncing');
    });
  });

  describe('startSync', () => {
    it('polling interval works', async () => {
      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 5000 });

      // Initial sync
      await vi.runAllTimersAsync();
      const initialCalls = mocks.mockFetch.mock.calls.length;

      // Fast-forward by interval
      vi.advanceTimersByTime(5000);
      await vi.runAllTimersAsync();

      // Should have made additional calls
      expect(mocks.mockFetch.mock.calls.length).toBeGreaterThan(initialCalls);
    });

    it('calls status change callback', async () => {
      const statusCallback = vi.fn();

      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', {
        onStatusChange: statusCallback,
        interval: 60000,
      });

      await vi.runAllTimersAsync();

      // Should have called with 'syncing' then 'idle'
      expect(statusCallback).toHaveBeenCalledWith('syncing');
      expect(statusCallback).toHaveBeenCalledWith('idle');
    });

    it('handles offline status', async () => {
      Object.defineProperty(navigator, 'onLine', { value: false });

      const statusCallback = vi.fn();

      pouchdbService.startSync('user:1', 'test-token', {
        onStatusChange: statusCallback,
        interval: 60000,
      });

      await vi.runAllTimersAsync();

      expect(statusCallback).toHaveBeenCalledWith('offline');
    });
  });

  describe('stopSync', () => {
    it('cancels requests and interval', async () => {
      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 5000 });
      await vi.runAllTimersAsync();

      const callsBeforeStop = mocks.mockFetch.mock.calls.length;

      pouchdbService.stopSync();

      // Fast-forward by multiple intervals
      vi.advanceTimersByTime(15000);
      await vi.runAllTimersAsync();

      // Should not have made additional calls
      expect(mocks.mockFetch.mock.calls.length).toBe(callsBeforeStop);
    });

    it('sets status to idle', async () => {
      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      pouchdbService.stopSync();

      expect(pouchdbService.getSyncStatus()).toBe('idle');
    });
  });

  describe('destroyDatabase', () => {
    it('stops sync and destroys database', async () => {
      // Get database first to create it
      pouchdbService.getDatabase();

      await pouchdbService.destroyDatabase();

      expect(mocks.mockDestroy).toHaveBeenCalled();
    });
  });

  describe('getWishlists', () => {
    it('returns wishlists sorted by updated_at descending', async () => {
      mocks.mockFind.mockResolvedValue({
        docs: [
          {
            _id: 'wishlist:1',
            type: 'wishlist',
            owner_id: 'user:1',
            name: 'Older',
            updated_at: '2024-01-01T00:00:00Z',
          },
          {
            _id: 'wishlist:2',
            type: 'wishlist',
            owner_id: 'user:1',
            name: 'Newer',
            updated_at: '2024-06-01T00:00:00Z',
          },
          {
            _id: 'wishlist:3',
            type: 'wishlist',
            owner_id: 'user:1',
            name: 'Middle',
            updated_at: '2024-03-01T00:00:00Z',
          },
        ],
      });

      const result = await pouchdbService.getWishlists('user:1');

      expect(result[0].name).toBe('Newer');
      expect(result[1].name).toBe('Middle');
      expect(result[2].name).toBe('Older');
    });

    it('queries by owner_id', async () => {
      mocks.mockFind.mockResolvedValue({ docs: [] });

      await pouchdbService.getWishlists('user:123');

      expect(mocks.mockFind).toHaveBeenCalledWith(
        expect.objectContaining({
          selector: expect.objectContaining({
            $and: expect.arrayContaining([
              expect.objectContaining({
                type: 'wishlist',
                owner_id: 'user:123',
              }),
            ]),
          }),
        })
      );
    });
  });

  describe('getItemCounts', () => {
    it('aggregates item counts correctly', async () => {
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'item:1', type: 'item', wishlist_id: 'wishlist:a' },
          { _id: 'item:2', type: 'item', wishlist_id: 'wishlist:a' },
          { _id: 'item:3', type: 'item', wishlist_id: 'wishlist:b' },
          { _id: 'item:4', type: 'item', wishlist_id: 'wishlist:a' },
        ],
      });

      const result = await pouchdbService.getItemCounts(['wishlist:a', 'wishlist:b', 'wishlist:c']);

      expect(result).toEqual({
        'wishlist:a': 3,
        'wishlist:b': 1,
        'wishlist:c': 0,
      });
    });

    it('returns empty object for empty input', async () => {
      const result = await pouchdbService.getItemCounts([]);

      expect(result).toEqual({});
      expect(mocks.mockFind).not.toHaveBeenCalled();
    });
  });

  describe('onSyncComplete', () => {
    it('notifies all registered listeners', async () => {
      const listener1 = vi.fn();
      const listener2 = vi.fn();

      const unsubscribe1 = pouchdbService.onSyncComplete(listener1);
      const unsubscribe2 = pouchdbService.onSyncComplete(listener2);

      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      expect(listener1).toHaveBeenCalled();
      expect(listener2).toHaveBeenCalled();

      // Clean up
      unsubscribe1();
      unsubscribe2();
    });

    it('unsubscribe removes listener', async () => {
      const listener = vi.fn();

      const unsubscribe = pouchdbService.onSyncComplete(listener);
      unsubscribe();

      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      expect(listener).not.toHaveBeenCalled();
    });

    it('handles listener errors gracefully', async () => {
      const errorListener = vi.fn().mockImplementation(() => {
        throw new Error('Listener error');
      });
      const goodListener = vi.fn();

      const unsubscribe1 = pouchdbService.onSyncComplete(errorListener);
      const unsubscribe2 = pouchdbService.onSyncComplete(goodListener);

      mocks.mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ documents: [], conflicts: [] }),
      });

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });
      await vi.runAllTimersAsync();

      // Good listener should still be called despite error in first
      expect(goodListener).toHaveBeenCalled();

      unsubscribe1();
      unsubscribe2();
    });
  });

  describe('getSyncStatus', () => {
    it('returns current sync status', () => {
      expect(pouchdbService.getSyncStatus()).toBe('idle');
    });
  });

  describe('isSyncing', () => {
    it('returns true when syncing', async () => {
      // Setup fetch to hang
      mocks.mockFetch.mockImplementation(() => new Promise(() => {}));

      pouchdbService.startSync('user:1', 'test-token', { interval: 60000 });

      // Give time for sync to start
      await vi.advanceTimersByTimeAsync(100);

      expect(pouchdbService.isSyncing()).toBe(true);
    });

    it('returns false when idle', () => {
      expect(pouchdbService.isSyncing()).toBe(false);
    });
  });

  describe('clearDatabase', () => {
    it('marks all documents as deleted', async () => {
      mocks.mockAllDocs.mockResolvedValue({
        rows: [
          { id: 'wishlist:1', value: { rev: '1-a' } },
          { id: 'item:1', value: { rev: '1-b' } },
        ],
      });

      await pouchdbService.clearDatabase();

      expect(mocks.mockBulkDocs).toHaveBeenCalledWith([
        { _id: 'wishlist:1', _rev: '1-a', _deleted: true },
        { _id: 'item:1', _rev: '1-b', _deleted: true },
      ]);
    });

    it('handles empty database', async () => {
      mocks.mockAllDocs.mockResolvedValue({ rows: [] });

      await pouchdbService.clearDatabase();

      expect(mocks.mockBulkDocs).not.toHaveBeenCalled();
    });
  });

  describe('getItems', () => {
    it('returns items sorted by created_at descending', async () => {
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'item:1', type: 'item', wishlist_id: 'wishlist:1', created_at: '2024-01-01T00:00:00Z' },
          { _id: 'item:2', type: 'item', wishlist_id: 'wishlist:1', created_at: '2024-06-01T00:00:00Z' },
          { _id: 'item:3', type: 'item', wishlist_id: 'wishlist:1', created_at: '2024-03-01T00:00:00Z' },
        ],
      });

      const result = await pouchdbService.getItems('wishlist:1');

      expect(result[0]._id).toBe('item:2'); // Newest first
      expect(result[1]._id).toBe('item:3');
      expect(result[2]._id).toBe('item:1'); // Oldest last
    });
  });

  describe('getMarks', () => {
    it('queries marks by item_id', async () => {
      mocks.mockFind.mockResolvedValue({ docs: [] });

      await pouchdbService.getMarks('item:123');

      expect(mocks.mockFind).toHaveBeenCalledWith(
        expect.objectContaining({
          selector: expect.objectContaining({
            $and: expect.arrayContaining([
              expect.objectContaining({
                type: 'mark',
                item_id: 'item:123',
              }),
            ]),
          }),
        })
      );
    });
  });

  describe('getMarksByUser', () => {
    it('queries marks by marked_by', async () => {
      mocks.mockFind.mockResolvedValue({ docs: [] });

      await pouchdbService.getMarksByUser('user:456');

      expect(mocks.mockFind).toHaveBeenCalledWith(
        expect.objectContaining({
          selector: expect.objectContaining({
            $and: expect.arrayContaining([
              expect.objectContaining({
                type: 'mark',
                marked_by: 'user:456',
              }),
            ]),
          }),
        })
      );
    });
  });

  describe('getBookmarks', () => {
    it('queries bookmarks by user_id', async () => {
      mocks.mockFind.mockResolvedValue({ docs: [] });

      await pouchdbService.getBookmarks('user:789');

      expect(mocks.mockFind).toHaveBeenCalledWith(
        expect.objectContaining({
          selector: expect.objectContaining({
            $and: expect.arrayContaining([
              expect.objectContaining({
                type: 'bookmark',
                user_id: 'user:789',
              }),
            ]),
          }),
        })
      );
    });
  });

  describe('getSharedWishlists', () => {
    it('returns wishlists where user has access but is not owner', async () => {
      mocks.mockFind.mockResolvedValue({
        docs: [
          { _id: 'wishlist:1', type: 'wishlist', owner_id: 'user:1', access: ['user:1', 'user:2'] },
          { _id: 'wishlist:2', type: 'wishlist', owner_id: 'user:2', access: ['user:2'] },
          { _id: 'wishlist:3', type: 'wishlist', owner_id: 'user:3', access: ['user:2', 'user:3'] },
        ],
      });

      const result = await pouchdbService.getSharedWishlists('user:2');

      // Should only include wishlists not owned by user:2
      expect(result).toHaveLength(2);
      expect(result.map((w) => w._id)).toContain('wishlist:1');
      expect(result.map((w) => w._id)).toContain('wishlist:3');
      expect(result.map((w) => w._id)).not.toContain('wishlist:2');
    });
  });
});
