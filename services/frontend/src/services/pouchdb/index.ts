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
  UserDoc,
  WishlistDoc,
  ItemDoc,
  MarkDoc,
  ShareDoc,
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
let currentSyncUserId: string | null = null; // Track current user for filtering

// Sync callbacks
type SyncCallbacks = {
  onStatusChange?: (status: SyncStatus) => void;
  onChange?: (change: PouchDBChange) => void;
  onError?: (error: Error) => void;
  onSyncComplete?: () => void;
};
let syncCallbacks: SyncCallbacks = {};

// Token management for sync - allows getting fresh tokens and refreshing on 401
type TokenManager = {
  getToken: () => string | null;
  refreshToken: () => Promise<void>;
};
let tokenManager: TokenManager | null = null;

// Global sync complete listeners for components to subscribe to
const syncCompleteListeners: Set<() => void> = new Set();

/**
 * Subscribe to sync completion events.
 * Returns unsubscribe function.
 */
export function onSyncComplete(callback: () => void): () => void {
  syncCompleteListeners.add(callback);
  return () => syncCompleteListeners.delete(callback);
}

/**
 * Notify all sync complete listeners.
 */
function notifySyncComplete(): void {
  syncCompleteListeners.forEach(cb => {
    try {
      cb();
    } catch (e) {
      console.error('[PouchDB] Sync complete listener error:', e);
    }
  });
}

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

    // Compact database to remove tombstones that can cause PouchDB-find issues
    // when deleted documents have missing fields
    db.compact().catch(err => console.debug('[PouchDB] Compact error:', err));
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
    // Compound indexes for sorted queries
    { index: { fields: ['type', 'wishlist_id', 'created_at'] } },  // getItems with sort
    { index: { fields: ['type', 'owner_id', 'updated_at'] } },     // getWishlists with sort
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

// Timeout for sync fetch requests (30 seconds)
const SYNC_FETCH_TIMEOUT_MS = 30000;

/**
 * Create an AbortSignal that combines a manual signal with a timeout.
 */
function createTimeoutSignal(manualSignal?: AbortSignal): AbortSignal {
  const timeoutController = new AbortController();
  const timer = setTimeout(() => timeoutController.abort(new Error('Sync fetch timeout')), SYNC_FETCH_TIMEOUT_MS);

  // If manual signal aborts, also abort the timeout controller
  if (manualSignal) {
    if (manualSignal.aborted) {
      clearTimeout(timer);
      timeoutController.abort(manualSignal.reason);
    } else {
      manualSignal.addEventListener('abort', () => {
        clearTimeout(timer);
        timeoutController.abort(manualSignal.reason);
      }, { once: true });
    }
  }

  // Clear timeout when the signal is used (request completes or aborts)
  timeoutController.signal.addEventListener('abort', () => clearTimeout(timer), { once: true });

  return timeoutController.signal;
}

/**
 * Perform a fetch with automatic token refresh, retry on 401, and timeout.
 * This handles the case where the token expires while the app is idle.
 */
async function fetchWithTokenRefresh(
  url: string,
  options: RequestInit,
  signal?: AbortSignal
): Promise<Response> {
  if (!tokenManager) {
    throw new Error('Token manager not initialized');
  }

  const token = tokenManager.getToken();
  if (!token) {
    throw new Error('No access token available');
  }

  const fetchSignal = createTimeoutSignal(signal);

  // First attempt with current token
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
    signal: fetchSignal,
  });

  // If 401, try to refresh token and retry once
  if (response.status === 401) {
    console.log('[PouchDB] Got 401, attempting token refresh and retry');
    try {
      await tokenManager.refreshToken();
      const newToken = tokenManager.getToken();
      if (!newToken) {
        throw new Error('Authentication expired');
      }

      const retrySignal = createTimeoutSignal(signal);

      // Retry with new token
      const retryResponse = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${newToken}`,
        },
        signal: retrySignal,
      });

      return retryResponse;
    } catch (refreshError) {
      console.error('[PouchDB] Token refresh failed:', refreshError);
      throw new Error('Authentication expired');
    }
  }

  return response;
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

// Track document IDs that failed to push (for reconciliation skip)
// These are documents that had conflicts without a server_document response
let failedPushDocIds: Set<string> = new Set();

/**
 * Pull documents from the server.
 * Fetches all documents the user has access to.
 * Uses reconciliation: server is source of truth, local docs not in server response are deleted.
 * Only reconciles documents that were included in the push batch (pushedDocIds).
 * Documents not in the push batch are preserved — they may have been created locally
 * after the push phase read the changes feed, and haven't been synced yet.
 */
async function pullFromServer(
  collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks' | 'users' | 'shares'>,
  pushedDocIds: Map<string, Set<string>>
): Promise<void> {
  const localDb = getDatabase();
  const baseUrl = getApiBaseUrl();

  // Map collection to document type
  const typeMap: Record<string, string> = {
    wishlists: 'wishlist',
    items: 'item',
    marks: 'mark',
    bookmarks: 'bookmark',
    users: 'user',
    shares: 'share',
  };

  // Fetch all collections in parallel instead of sequentially.
  // This reduces pull latency from 6 round-trips to 1 (network-wise).
  const fetchResults = await Promise.all(
    collections.map(async (collection) => {
      const response = await fetchWithTokenRefresh(
        `${baseUrl}/api/v2/sync/pull/${collection}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        },
        syncAbortController?.signal
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication expired');
        }
        throw new Error(`Pull failed for ${collection}: ${response.status}`);
      }

      const data = await response.json();
      return { collection, serverDocs: (data.documents || []) as CouchDBDoc[] };
    })
  );

  // Process upserts and reconciliation for each collection
  for (const { collection, serverDocs } of fetchResults) {
    try {
      // Build set of IDs from server (non-deleted docs user has access to)
      const serverDocIds = new Set(serverDocs.map((d: CouchDBDoc) => d._id));

      // Upsert documents from server
      for (const doc of serverDocs) {
        try {
          let existingRev: string | undefined;
          try {
            const existing = await localDb.get(doc._id);
            existingRev = existing._rev;
          } catch {
            // Document doesn't exist locally
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
            deleted: false,
          });
        } catch (error) {
          console.warn(`[PouchDB] Failed to upsert ${doc._id}:`, error);
        }
      }

      // Reconciliation: find local docs not in server response and mark as deleted
      // This handles items deleted by other users (e.g., wishlist owner)
      // EXCEPTION: Skip documents that failed to push (preserve local changes)
      const docType = typeMap[collection];
      try {
        const localResult = await localDb.find({
          selector: {
            $and: [
              { type: docType },
              {
                $or: [
                  { _deleted: { $exists: false } },
                  { _deleted: false },
                ],
              },
            ],
          },
        });

        const collectionPushedIds = pushedDocIds.get(collection);
        for (const localDoc of localResult.docs) {
          if (!serverDocIds.has(localDoc._id)) {
            // Skip if this doc wasn't in the push batch — it was created locally
            // after push read the changes feed and hasn't been synced yet
            if (!collectionPushedIds?.has(localDoc._id)) {
              continue;
            }
            // Skip if this doc failed to push - preserve local changes
            if (failedPushDocIds.has(localDoc._id)) {
              console.log(`[PouchDB] Preserving ${localDoc._id} - failed to push, will retry later`);
              continue;
            }
            // This doc exists locally but not on server - it was deleted or access revoked
            try {
              await localDb.put({
                ...localDoc,
                _deleted: true,
                updated_at: new Date().toISOString(),
              });
              // Notify about deletion
              syncCallbacks.onChange?.({
                id: localDoc._id,
                seq: 0,
                changes: [{ rev: localDoc._rev || '' }],
                doc: localDoc,
                deleted: true,
              });
            } catch (error) {
              console.warn(`[PouchDB] Failed to delete ${localDoc._id}:`, error);
            }
          }
        }
      } catch (error) {
        console.warn(`[PouchDB] Reconciliation query failed for ${collection}:`, error);
      }

      console.log(`[PouchDB] Pulled and reconciled ${serverDocs.length} ${collection}`);
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
 * Returns a map of collection -> Set<docId> that were included in the push batch.
 * Tracks documents that fail to push for reconciliation skip.
 */
async function pushToServer(
  collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks' | 'users' | 'shares'>
): Promise<Map<string, Set<string>>> {
  const pushedDocIds = new Map<string, Set<string>>();
  // Clear failed push tracking at start of new push cycle
  failedPushDocIds = new Set();

  const localDb = getDatabase();
  const baseUrl = getApiBaseUrl();

  // Map collection names to document types
  const typeMap: Record<string, string> = {
    wishlists: 'wishlist',
    items: 'item',
    marks: 'mark',
    bookmarks: 'bookmark',
    users: 'user',
    shares: 'share',
  };

  // Read the changes feed ONCE and group documents by type.
  // Previously this was read 6 times (once per collection) — O(6M) instead of O(M).
  const changes = await localDb.changes({
    since: 0,
    include_docs: true,
  });

  const docsByType = new Map<string, Map<string, CouchDBDoc>>();
  for (const collection of collections) {
    docsByType.set(typeMap[collection], new Map());
  }
  for (const change of changes.results) {
    if (change.doc && change.doc.type) {
      const typeMap2 = docsByType.get(change.doc.type);
      if (typeMap2) {
        // Later entries overwrite earlier ones (they're more recent)
        typeMap2.set(change.id, change.doc as CouchDBDoc);
      }
    }
  }

  for (const collection of collections) {
    try {
      let docs = Array.from(docsByType.get(typeMap[collection])?.values() || []);

      // Filter documents to only include those owned by the current user
      // This prevents pushing documents received from other users during pull
      if (currentSyncUserId) {
        if (collection === 'marks') {
          docs = docs.filter(doc => (doc as MarkDoc).marked_by === currentSyncUserId);
        } else if (collection === 'bookmarks') {
          docs = docs.filter(doc => (doc as BookmarkDoc).user_id === currentSyncUserId);
        } else if (collection === 'users') {
          docs = docs.filter(doc => doc._id === currentSyncUserId);
        } else if (collection === 'shares') {
          docs = docs.filter(doc => (doc as ShareDoc).owner_id === currentSyncUserId);
        }
      }

      // Record which doc IDs are in this push batch
      pushedDocIds.set(collection, new Set(docs.map(d => d._id)));

      if (docs.length === 0) continue;

      // Send to server
      const response = await fetchWithTokenRefresh(
        `${baseUrl}/api/v2/sync/push/${collection}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ documents: docs }),
        },
        syncAbortController?.signal
      );

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
          // Server has a version - accept it
          try {
            const existing = await localDb.get(conflict.document_id);
            await localDb.put({
              ...conflict.server_document,
              _rev: existing._rev,
            });
          } catch {
            // Document might have been deleted
          }
        } else {
          // No server document - track this for reconciliation skip
          // This document should NOT be deleted during pull reconciliation
          // because the server rejected it but doesn't have an alternative version
          failedPushDocIds.add(conflict.document_id);
          console.log(`[PouchDB] Document ${conflict.document_id} failed to push (${conflict.error}), preserving local copy`);
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

  return pushedDocIds;
}

/**
 * Start sync with the backend API.
 * Uses polling for simplicity, can be enhanced with WebSocket later.
 *
 * @param userId - The current user ID for filtering documents
 * @param getToken - Function to get fresh access token
 * @param refreshToken - Function to refresh the token when expired
 * @param options - Sync options
 */
export function startSync(
  userId: string,
  getToken: () => string | null,
  refreshToken: () => Promise<void>,
  options?: {
    onStatusChange?: (status: SyncStatus) => void;
    onChange?: (change: PouchDBChange) => void;
    onError?: (error: Error) => void;
    interval?: number; // Poll interval in ms, default 30000
  }
): void {
  // Stop any existing sync
  stopSync();

  // Store user ID for filtering during push
  currentSyncUserId = userId;

  // Store token manager for fetching fresh tokens and refreshing on 401
  tokenManager = { getToken, refreshToken };

  // Store callbacks
  syncCallbacks = {
    onStatusChange: options?.onStatusChange,
    onChange: options?.onChange,
    onError: options?.onError,
  };

  // Create abort controller for cancellation
  syncAbortController = new AbortController();

  const interval = options?.interval || 30000;
  const collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks' | 'users' | 'shares'> = ['wishlists', 'items', 'marks', 'bookmarks', 'users', 'shares'];

  // Lock to prevent overlapping sync operations
  let isSyncRunning = false;

  // Initial sync
  const doSync = async () => {
    if (isSyncRunning) {
      console.debug('[PouchDB] Sync already running, skipping');
      return;
    }

    if (!navigator.onLine) {
      setSyncStatus('offline');
      return;
    }

    // Check if we have a valid token before starting sync
    if (!tokenManager?.getToken()) {
      console.log('[PouchDB] No token available, skipping sync');
      return;
    }

    isSyncRunning = true;
    try {
      setSyncStatus('syncing');

      // Push first, then pull - ensures local changes are sent before
      // reconciliation logic in pull can delete local-only documents
      const pushedDocIds = await pushToServer(collections);
      await pullFromServer(collections, pushedDocIds);

      setSyncStatus('idle');
      notifySyncComplete();
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return; // Sync was cancelled
      }
      console.error('[PouchDB] Sync error:', error);
      setSyncStatus('error');
      syncCallbacks.onError?.(error as Error);
    } finally {
      isSyncRunning = false;
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

// Debounce state for triggerSync
const SYNC_DEBOUNCE_MS = 1000; // Coalesce calls within 1 second
let debouncedSyncTimer: ReturnType<typeof setTimeout> | null = null;
let debouncedSyncPromise: Promise<void> | null = null;
let debouncedSyncResolvers: Array<() => void> = [];
let debouncedSyncRejecters: Array<(error: Error) => void> = [];

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
 * Execute the actual sync operation.
 */
async function executeSync(): Promise<void> {
  // If sync is already in progress, wait for it to complete first
  if (syncStatus === 'syncing') {
    await waitForSyncComplete();
    // After waiting, check again (another trigger might have started)
    if (syncStatus === 'syncing') {
      await waitForSyncComplete();
      return;
    }
  }

  // Check if we have a token manager and valid token
  if (!tokenManager?.getToken()) {
    console.log('[PouchDB] No token available, skipping triggered sync');
    return;
  }

  const collections: Array<'wishlists' | 'items' | 'marks' | 'bookmarks' | 'users' | 'shares'> = ['wishlists', 'items', 'marks', 'bookmarks', 'users', 'shares'];

  const doSync = async () => {
    try {
      setSyncStatus('syncing');
      const pushedDocIds = await pushToServer(collections);
      await pullFromServer(collections, pushedDocIds);
      setSyncStatus('idle');
      notifySyncComplete();
    } catch (error) {
      console.error('[PouchDB] Trigger sync error:', error);
      setSyncStatus('error');
      syncCallbacks.onError?.(error as Error);
      throw error;
    }
  };

  // Store promise so other callers can wait for it
  currentSyncPromise = doSync();
  await currentSyncPromise;
  currentSyncPromise = null;
}

/**
 * Trigger a sync with debouncing.
 * Multiple calls within SYNC_DEBOUNCE_MS are coalesced into a single sync.
 * All callers receive the same promise that resolves when sync completes.
 */
export function triggerSync(): Promise<void> {
  // If there's already a debounced sync waiting, return its promise
  if (debouncedSyncPromise) {
    return debouncedSyncPromise;
  }

  // Create a new promise that all callers within the debounce window will share
  debouncedSyncPromise = new Promise<void>((resolve, reject) => {
    debouncedSyncResolvers.push(resolve);
    debouncedSyncRejecters.push(reject);
  });

  // Clear any existing timer
  if (debouncedSyncTimer) {
    clearTimeout(debouncedSyncTimer);
  }

  // Set up debounced execution
  debouncedSyncTimer = setTimeout(async () => {
    const resolvers = debouncedSyncResolvers;
    const rejecters = debouncedSyncRejecters;

    // Reset state before executing
    debouncedSyncTimer = null;
    debouncedSyncPromise = null;
    debouncedSyncResolvers = [];
    debouncedSyncRejecters = [];

    try {
      await executeSync();
      // Resolve all waiting promises
      resolvers.forEach(resolve => resolve());
    } catch (error) {
      // Reject all waiting promises
      rejecters.forEach(reject => reject(error as Error));
    }
  }, SYNC_DEBOUNCE_MS);

  return debouncedSyncPromise;
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

  // Clear callbacks and token manager
  syncCallbacks = {};
  tokenManager = null;

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

  // Build selector - use $or to properly handle _deleted field
  // This matches docs where _deleted doesn't exist OR is explicitly false
  const baseSelector = options.selector;
  const selector = options.selector._deleted !== undefined
    ? baseSelector
    : {
        $and: [
          baseSelector,
          {
            $or: [
              { _deleted: { $exists: false } },
              { _deleted: false },
            ],
          },
        ],
      };

  try {
    const result = await localDb.find({
      selector,
      sort: options.sort,
      limit: options.limit,
      skip: options.skip,
      fields: options.fields,
    });

    // Filter out any undefined or incomplete documents that might slip through
    return (result.docs as T[]).filter(doc => doc && doc._id);
  } catch (error) {
    // PouchDB-find can crash when evaluating selectors on tombstone documents
    // that have missing fields. When this happens, compact and retry once.
    if (error instanceof TypeError && String(error).includes('Cannot read properties of undefined')) {
      console.debug('[PouchDB] Find error on tombstone, compacting and retrying');
      try {
        await localDb.compact();
        const result = await localDb.find({
          selector,
          sort: options.sort,
          limit: options.limit,
          skip: options.skip,
          fields: options.fields,
        });
        return (result.docs as T[]).filter(doc => doc && doc._id);
      } catch (retryError) {
        // Retry also failed - return empty array and let sync continue
        console.debug('[PouchDB] Find retry failed, returning empty result');
        return [];
      }
    }
    throw error;
  }
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
  const wishlists = await find<WishlistDoc>({
    selector: {
      type: 'wishlist',
      owner_id: userId,
    },
    // Note: Sort in JavaScript to avoid PouchDB index issues
  });
  // Sort by updated_at descending in JavaScript
  wishlists.sort((a, b) => {
    const dateA = a.updated_at || '';
    const dateB = b.updated_at || '';
    return dateB.localeCompare(dateA);
  });
  return wishlists;
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
  const items = await find<ItemDoc>({
    selector: {
      type: 'item',
      wishlist_id: wishlistId,
    },
  });
  // Sort by created_at descending in JavaScript (avoids PouchDB index issues)
  items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
  return items;
}

/**
 * Get item counts for multiple wishlists.
 * Returns a map of wishlist_id -> item count.
 */
export async function getItemCounts(wishlistIds: string[]): Promise<Record<string, number>> {
  if (wishlistIds.length === 0) {
    return {};
  }

  const items = await find<ItemDoc>({
    selector: {
      type: 'item',
      wishlist_id: { $in: wishlistIds },
    },
  });

  const counts: Record<string, number> = {};
  for (const id of wishlistIds) {
    counts[id] = 0;
  }
  for (const item of items) {
    if (item.wishlist_id && counts[item.wishlist_id] !== undefined) {
      counts[item.wishlist_id]++;
    }
  }
  return counts;
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
    (doc) => doc?.owner_id === userId
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
    (doc) => doc?.owner_id !== userId && doc?.access?.includes(userId) === true
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
    (doc) => doc?.wishlist_id === wishlistId
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
    (doc) => doc?.item_id != null && itemIds.includes(doc.item_id)
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
    (doc) => doc?.user_id === userId
  );
}

// ============================================
// Share helpers
// ============================================

/**
 * Get shares for a wishlist owned by the user.
 */
export async function getShares(wishlistId: string, userId: string): Promise<ShareDoc[]> {
  return find<ShareDoc>({
    selector: {
      type: 'share',
      wishlist_id: wishlistId,
      owner_id: userId,
      revoked: { $ne: true },
    },
  });
}

/**
 * Get all shares owned by a user.
 */
export async function getSharesByUser(userId: string): Promise<ShareDoc[]> {
  return find<ShareDoc>({
    selector: {
      type: 'share',
      owner_id: userId,
      revoked: { $ne: true },
    },
  });
}

/**
 * Subscribe to share changes for a wishlist.
 */
export function subscribeToShares(
  wishlistId: string,
  userId: string,
  callback: (shares: ShareDoc[]) => void
): () => void {
  return subscribeToChanges<ShareDoc>(
    'share',
    callback,
    (doc) => doc?.wishlist_id === wishlistId && doc?.owner_id === userId && doc?.revoked !== true
  );
}

// ============================================
// User helpers
// ============================================

/**
 * Get the current user document from PouchDB.
 */
export async function getCurrentUser(userId: string): Promise<UserDoc | null> {
  return findById<UserDoc>(userId);
}

/**
 * Update the current user document in PouchDB.
 * This will be synced to the server on the next sync cycle.
 */
export async function updateCurrentUser(
  userId: string,
  updates: Partial<Pick<UserDoc, 'name' | 'bio' | 'public_url_slug' | 'birthday' | 'avatar_base64' | 'locale'>>
): Promise<UserDoc> {
  const existing = await findById<UserDoc>(userId);
  if (!existing) {
    throw new Error('User document not found');
  }

  const updated: UserDoc = {
    ...existing,
    ...updates,
    updated_at: new Date().toISOString(),
  };

  return upsert<UserDoc>(updated);
}

/**
 * Subscribe to the current user document changes.
 */
export function subscribeToCurrentUser(
  userId: string,
  callback: (user: UserDoc | null) => void
): () => void {
  return subscribeToChanges<UserDoc>(
    'user',
    (docs) => callback(docs[0] || null),
    (doc) => doc?._id === userId
  );
}

// Export types and helpers
export { createId, extractId } from './types';
export type { CouchDBDoc, UserDoc, WishlistDoc, ItemDoc, MarkDoc, ShareDoc, BookmarkDoc, PouchDBChange, SyncStatus };
