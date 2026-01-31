/**
 * PouchDB database service for offline-first data storage.
 *
 * Architecture:
 * - PouchDB handles local storage and change detection (offline-first)
 * - Backend API handles sync with access control validation
 * - This is more secure than direct CouchDB replication since the backend
 *   validates access arrays and user permissions
 */

import PouchDB from 'pouchdb-browser';
import PouchDBFind from 'pouchdb-find';
import type {
  CouchDBDoc,
  WishlistDoc,
  ItemDoc,
  MarkDoc,
  BookmarkDoc,
  PouchDBFindOptions,
  PouchDBChange,
  SyncStatus,
} from './types';

// Register PouchDB plugins
PouchDB.plugin(PouchDBFind);

// Database name
const DB_NAME = 'wishwithme';

// Singleton database instance
let db: PouchDB.Database<CouchDBDoc> | null = null;

// Sync state
let syncStatus: SyncStatus = 'idle';
let syncAbortController: AbortController | null = null;
let syncIntervalId: ReturnType<typeof setInterval> | null = null;

// Sync callbacks
type SyncCallbacks = {
  onStatusChange?: (status: SyncStatus) => void;
  onChange?: (change: PouchDBChange) => void;
  onError?: (error: Error) => void;
};
let syncCallbacks: SyncCallbacks = {};

/**
 * Get or create the local PouchDB database.
 */
export function getDatabase(): PouchDB.Database<CouchDBDoc> {
  if (!db) {
    db = new PouchDB<CouchDBDoc>(DB_NAME, {
      auto_compaction: true,
    });
    console.log('[PouchDB] Database created:', DB_NAME);

    // Create indexes for efficient queries
    createIndexes(db);
  }
  return db;
}

/**
 * Create indexes for efficient Mango queries.
 */
async function createIndexes(database: PouchDB.Database<CouchDBDoc>): Promise<void> {
  const indexes = [
    { index: { fields: ['type'] } },
    { index: { fields: ['type', 'owner_id'] } },
    { index: { fields: ['type', 'wishlist_id'] } },
    { index: { fields: ['type', 'item_id'] } },
    { index: { fields: ['type', 'updated_at'] } },
    { index: { fields: ['type', 'created_at'] } },
  ];

  for (const idx of indexes) {
    try {
      await database.createIndex(idx);
    } catch (error) {
      // Index might already exist, that's fine
      console.debug('[PouchDB] Index creation:', idx.index.fields, error);
    }
  }
}

/**
 * Get the API base URL for sync endpoints.
 */
function getApiBaseUrl(): string {
  const hostname = window.location.hostname;

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }

  // Production - use api subdomain
  return `${window.location.protocol}//api.${hostname.replace(/^www\./, '')}`;
}

/**
 * Get current sync status.
 */
export function getSyncStatus(): SyncStatus {
  return syncStatus;
}

/**
 * Check if sync is currently running.
 */
export function isSyncing(): boolean {
  return syncStatus === 'syncing';
}

/**
 * Update sync status and notify callback.
 */
function setSyncStatus(status: SyncStatus): void {
  syncStatus = status;
  syncCallbacks.onStatusChange?.(status);
}

/**
 * Pull documents from the server.
 * Fetches all documents the user has access to.
 */
async function pullFromServer(
  token: string,
  collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks'>
): Promise<void> {
  const localDb = getDatabase();
  const baseUrl = getApiBaseUrl();

  for (const collection of collections) {
    try {
      const response = await fetch(`${baseUrl}/api/v2/sync/pull/${collection}`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        signal: syncAbortController?.signal,
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication expired');
        }
        throw new Error(`Pull failed: ${response.status}`);
      }

      const data = await response.json();
      const docs = data.documents || [];
      console.log(`[PouchDB] Received ${docs.length} ${collection} from server`);
      if (collection === 'items' && docs.length > 0) {
        console.log(`[PouchDB] First item:`, docs[0]._id, docs[0].title, 'wishlist_id:', docs[0].wishlist_id);
      }

      // Upsert each document to local database
      for (const doc of docs) {
        // Skip deleted documents from server (defense in depth)
        if (doc._deleted) {
          continue;
        }

        try {
          // Check if document exists locally
          let existingRev: string | undefined;
          let localDeleted = false;
          try {
            const existing = await localDb.get(doc._id);
            existingRev = existing._rev;
            localDeleted = existing._deleted === true;
          } catch {
            // Document doesn't exist locally
          }

          // Don't overwrite local deletion with server's non-deleted version
          // The local deletion should be pushed to server instead
          if (localDeleted) {
            continue;
          }

          await localDb.put({
            ...doc,
            _rev: existingRev,
          });

          // Notify about change
          syncCallbacks.onChange?.({
            id: doc._id,
            seq: 0,
            changes: [{ rev: doc._rev || '' }],
            doc,
            deleted: doc._deleted,
          });
        } catch (error) {
          console.warn(`[PouchDB] Failed to upsert ${doc._id}:`, error);
        }
      }

      console.log(`[PouchDB] Pulled ${docs.length} ${collection}`);
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        throw error;
      }
      console.error(`[PouchDB] Pull error for ${collection}:`, error);
      throw error;
    }
  }
}

/**
 * Push local changes to the server.
 * Gets documents modified since last push and sends them.
 */
async function pushToServer(
  token: string,
  collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks'>
): Promise<void> {
  const localDb = getDatabase();
  const baseUrl = getApiBaseUrl();

  // Map collection names to document types
  const typeMap: Record<string, string> = {
    wishlists: 'wishlist',
    items: 'item',
    marks: 'mark',
    bookmarks: 'bookmark',
  };

  for (const collection of collections) {
    try {
      // Get all local documents of this type INCLUDING deleted ones
      // IMPORTANT: allDocs() does NOT return deleted documents!
      // We must use the changes feed to get deleted docs
      const localDb = getDatabase();

      // Use changes feed to get ALL documents including deleted ones
      const changes = await localDb.changes({
        since: 0,
        include_docs: true,
      });

      // Deduplicate by doc ID (changes may have multiple entries per doc)
      // Keep only the latest entry for each document
      const docMap = new Map<string, CouchDBDoc>();
      for (const change of changes.results) {
        if (change.doc && change.doc.type === typeMap[collection]) {
          // Later entries overwrite earlier ones (they're more recent)
          docMap.set(change.id, change.doc as CouchDBDoc);
        }
      }
      const docs = Array.from(docMap.values());

      if (docs.length === 0) continue;

      // Send to server
      const response = await fetch(`${baseUrl}/api/v2/sync/push/${collection}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ documents: docs }),
        signal: syncAbortController?.signal,
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication expired');
        }
        throw new Error(`Push failed: ${response.status}`);
      }

      const result = await response.json();
      console.log(`[PouchDB] Pushed ${docs.length} ${collection}, conflicts:`, result.conflicts?.length || 0);

      // Handle conflicts by accepting server version
      for (const conflict of result.conflicts || []) {
        if (conflict.server_document) {
          try {
            const existing = await localDb.get(conflict.document_id);
            await localDb.put({
              ...conflict.server_document,
              _rev: existing._rev,
            });
          } catch {
            // Document might have been deleted
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        throw error;
      }
      console.error(`[PouchDB] Push error for ${collection}:`, error);
      throw error;
    }
  }
}

/**
 * Start sync with the backend API.
 * Uses polling for simplicity, can be enhanced with WebSocket later.
 */
export function startSync(
  userId: string,
  token: string,
  options?: {
    onStatusChange?: (status: SyncStatus) => void;
    onChange?: (change: PouchDBChange) => void;
    onError?: (error: Error) => void;
    interval?: number; // Poll interval in ms, default 30000
  }
): void {
  // Stop any existing sync
  stopSync();

  // Store callbacks
  syncCallbacks = {
    onStatusChange: options?.onStatusChange,
    onChange: options?.onChange,
    onError: options?.onError,
  };

  // Create abort controller for cancellation
  syncAbortController = new AbortController();

  const interval = options?.interval || 30000;
  const collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks'> = ['wishlists', 'items', 'marks', 'bookmarks'];

  // Initial sync
  const doSync = async () => {
    if (!navigator.onLine) {
      setSyncStatus('offline');
      return;
    }

    try {
      setSyncStatus('syncing');

      // Pull first, then push
      await pullFromServer(token, collections);
      await pushToServer(token, collections);

      setSyncStatus('idle');
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return; // Sync was cancelled
      }
      console.error('[PouchDB] Sync error:', error);
      setSyncStatus('error');
      syncCallbacks.onError?.(error as Error);
    }
  };

  // Do initial sync
  doSync();

  // Setup periodic sync
  syncIntervalId = setInterval(doSync, interval);

  // Listen for online/offline events
  window.addEventListener('online', doSync);
  window.addEventListener('offline', () => setSyncStatus('offline'));

  console.log('[PouchDB] Sync started for user:', userId);
}

// Track pending sync promise for waiting
let currentSyncPromise: Promise<void> | null = null;

/**
 * Wait for any in-progress sync to complete.
 */
async function waitForSyncComplete(): Promise<void> {
  if (currentSyncPromise) {
    try {
      await currentSyncPromise;
    } catch {
      // Ignore errors - we just want to wait for completion
    }
  }
}

/**
 * Trigger an immediate sync (e.g., after local write).
 * If a sync is already in progress, waits for it to complete then performs another sync.
 */
export async function triggerSync(token: string): Promise<void> {
  // If sync is already in progress, wait for it to complete first
  if (syncStatus === 'syncing') {
    console.log('[PouchDB] Sync in progress, waiting for completion...');
    await waitForSyncComplete();
    // After waiting, check again (another trigger might have started)
    if (syncStatus === 'syncing') {
      await waitForSyncComplete();
      return;
    }
  }

  const collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks'> = ['wishlists', 'items', 'marks', 'bookmarks'];

  const doSync = async () => {
    try {
      setSyncStatus('syncing');
      await pushToServer(token, collections);
      await pullFromServer(token, collections);
      setSyncStatus('idle');
    } catch (error) {
      console.error('[PouchDB] Trigger sync error:', error);
      setSyncStatus('error');
      syncCallbacks.onError?.(error as Error);
    }
  };

  // Store promise so other callers can wait for it
  currentSyncPromise = doSync();
  await currentSyncPromise;
  currentSyncPromise = null;
}

/**
 * Stop the sync process.
 */
export function stopSync(): void {
  // Cancel any in-flight requests
  if (syncAbortController) {
    syncAbortController.abort();
    syncAbortController = null;
  }

  // Clear interval
  if (syncIntervalId) {
    clearInterval(syncIntervalId);
    syncIntervalId = null;
  }

  // Remove event listeners
  window.removeEventListener('online', () => {});
  window.removeEventListener('offline', () => {});

  // Clear callbacks
  syncCallbacks = {};

  setSyncStatus('idle');
  console.log('[PouchDB] Sync stopped');
}

/**
 * Destroy the local database (for logout).
 */
export async function destroyDatabase(): Promise<void> {
  stopSync();
  if (db) {
    await db.destroy();
    db = null;
    console.log('[PouchDB] Database destroyed');
  }
}

/**
 * Clear all documents from the database without destroying it.
 */
export async function clearDatabase(): Promise<void> {
  const localDb = getDatabase();
  const allDocs = await localDb.allDocs();
  const toDelete = allDocs.rows.map((row) => ({
    _id: row.id,
    _rev: row.value.rev,
    _deleted: true,
  }));
  if (toDelete.length > 0) {
    await localDb.bulkDocs(toDelete as unknown as CouchDBDoc[]);
  }
  console.log('[PouchDB] Database cleared');
}

// ============================================
// Query helpers
// ============================================

/**
 * Find documents using Mango query.
 */
export async function find<T extends CouchDBDoc>(
  options: PouchDBFindOptions
): Promise<T[]> {
  const localDb = getDatabase();

  // Ensure _deleted filter is applied
  const selector = {
    ...options.selector,
    _deleted: options.selector._deleted ?? { $ne: true },
  };

  console.log('[PouchDB] find query:', JSON.stringify(selector));

  const result = await localDb.find({
    selector,
    sort: options.sort,
    limit: options.limit,
    skip: options.skip,
    fields: options.fields,
  });

  console.log('[PouchDB] find result:', result.docs.length, 'docs');

  return result.docs as T[];
}

/**
 * Find a single document by ID.
 */
export async function findById<T extends CouchDBDoc>(
  id: string
): Promise<T | null> {
  const localDb = getDatabase();
  try {
    const doc = await localDb.get(id);
    if (doc._deleted) return null;
    return doc as T;
  } catch (error) {
    if ((error as PouchDB.Core.Error).status === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Create or update a document.
 */
export async function upsert<T extends CouchDBDoc>(
  doc: Omit<T, '_rev'> & { _rev?: string }
): Promise<T> {
  const localDb = getDatabase();

  // Try to get existing document for revision
  let existingRev: string | undefined;
  try {
    const existing = await localDb.get(doc._id);
    existingRev = existing._rev;
  } catch {
    // Document doesn't exist, that's fine
  }

  const toSave = {
    ...doc,
    _rev: existingRev,
    updated_at: new Date().toISOString(),
  };

  const result = await localDb.put(toSave as CouchDBDoc);
  return { ...toSave, _rev: result.rev } as T;
}

/**
 * Soft delete a document.
 */
export async function softDelete(id: string): Promise<void> {
  const localDb = getDatabase();
  const doc = await localDb.get(id);
  await localDb.put({
    ...doc,
    _deleted: true,
    updated_at: new Date().toISOString(),
  });
}

/**
 * Subscribe to changes on a collection type.
 */
export function subscribeToChanges<T extends CouchDBDoc>(
  type: CouchDBDoc['type'],
  callback: (docs: T[]) => void,
  filter?: (doc: T) => boolean
): () => void {
  const localDb = getDatabase();

  // Initial load
  const loadDocs = async () => {
    const docs = await find<T>({ selector: { type } });
    const filtered = filter ? docs.filter(filter) : docs;
    callback(filtered);
  };

  // Load immediately
  loadDocs();

  // Subscribe to changes
  const changes = localDb
    .changes({
      since: 'now',
      live: true,
      include_docs: true,
    })
    .on('change', async (change) => {
      // Reload when any document of this type changes
      const doc = change.doc as T | undefined;
      if (doc?.type === type || change.deleted) {
        await loadDocs();
      }
    });

  // Return unsubscribe function
  return () => {
    changes.cancel();
  };
}

// ============================================
// Collection-specific helpers
// ============================================

/**
 * Get all wishlists for a user.
 */
export async function getWishlists(userId: string): Promise<WishlistDoc[]> {
  return find<WishlistDoc>({
    selector: {
      type: 'wishlist',
      owner_id: userId,
    },
    sort: [{ updated_at: 'desc' }],
  });
}

/**
 * Get wishlists shared with a user (not owned by them).
 */
export async function getSharedWishlists(userId: string): Promise<WishlistDoc[]> {
  const allWishlists = await find<WishlistDoc>({
    selector: {
      type: 'wishlist',
      access: { $elemMatch: { $eq: userId } },
    },
  });
  // Filter out owned wishlists
  return allWishlists.filter((w) => w.owner_id !== userId);
}

/**
 * Get items for a wishlist.
 */
export async function getItems(wishlistId: string): Promise<ItemDoc[]> {
  console.log('[PouchDB] getItems called with wishlistId:', wishlistId);
  const items = await find<ItemDoc>({
    selector: {
      type: 'item',
      wishlist_id: wishlistId,
    },
    sort: [{ created_at: 'desc' }],
  });
  console.log('[PouchDB] getItems result:', items.length, 'items found');
  return items;
}

/**
 * Get marks for an item.
 */
export async function getMarks(itemId: string): Promise<MarkDoc[]> {
  return find<MarkDoc>({
    selector: {
      type: 'mark',
      item_id: itemId,
    },
  });
}

/**
 * Get marks by a user.
 */
export async function getMarksByUser(userId: string): Promise<MarkDoc[]> {
  return find<MarkDoc>({
    selector: {
      type: 'mark',
      marked_by: userId,
    },
  });
}

/**
 * Subscribe to wishlists for a user.
 */
export function subscribeToWishlists(
  userId: string,
  callback: (wishlists: WishlistDoc[]) => void
): () => void {
  return subscribeToChanges<WishlistDoc>(
    'wishlist',
    callback,
    (doc) => doc.owner_id === userId
  );
}

/**
 * Subscribe to shared wishlists for a user.
 */
export function subscribeToSharedWishlists(
  userId: string,
  callback: (wishlists: WishlistDoc[]) => void
): () => void {
  return subscribeToChanges<WishlistDoc>(
    'wishlist',
    callback,
    (doc) => doc.owner_id !== userId && doc.access.includes(userId)
  );
}

/**
 * Subscribe to items for a wishlist.
 */
export function subscribeToItems(
  wishlistId: string,
  callback: (items: ItemDoc[]) => void
): () => void {
  return subscribeToChanges<ItemDoc>(
    'item',
    callback,
    (doc) => doc.wishlist_id === wishlistId
  );
}

/**
 * Subscribe to marks for items.
 */
export function subscribeToMarks(
  itemIds: string[],
  callback: (marks: MarkDoc[]) => void
): () => void {
  return subscribeToChanges<MarkDoc>(
    'mark',
    callback,
    (doc) => itemIds.includes(doc.item_id)
  );
}

/**
 * Get bookmarks for a user.
 */
export async function getBookmarks(userId: string): Promise<BookmarkDoc[]> {
  return find<BookmarkDoc>({
    selector: {
      type: 'bookmark',
      user_id: userId,
    },
  });
}

/**
 * Subscribe to bookmark changes for a user.
 */
export function subscribeToBookmarks(
  userId: string,
  callback: (bookmarks: BookmarkDoc[]) => void
): () => void {
  return subscribeToChanges<BookmarkDoc>(
    'bookmark',
    callback,
    (doc) => doc.user_id === userId
  );
}

// Export types and helpers
export { createId, extractId } from './types';
export type { CouchDBDoc, WishlistDoc, ItemDoc, MarkDoc, BookmarkDoc, PouchDBChange, SyncStatus };
