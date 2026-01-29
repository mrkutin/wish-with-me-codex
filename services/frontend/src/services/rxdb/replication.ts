/**
 * RxDB replication setup for syncing with backend.
 */

import { replicateRxCollection, type RxReplicationState } from 'rxdb/plugins/replication';
import { ReplaySubject } from 'rxjs';
import { api } from '@/boot/axios';
import type { WishWithMeDatabase, WishlistDoc, ItemDoc, MarkDoc } from './index';

// Global reference for SSE to trigger syncs
let currentReplicationState: ReplicationState | null = null;
// Track if replications are active (not waiting for leadership)
let replicationsActive = false;

export interface ReplicationCheckpoint {
  updated_at: string;
  id: string;
}

interface PullResponse<T> {
  documents: T[];
  checkpoint: ReplicationCheckpoint | null;
}

interface ConflictInfo {
  document_id: string;
  error: string;
  server_document?: Record<string, unknown>;
}

interface PushResponse {
  conflicts: ConflictInfo[];
}

export interface ReplicationState {
  wishlists: RxReplicationState<WishlistDoc, ReplicationCheckpoint>;
  items: RxReplicationState<ItemDoc, ReplicationCheckpoint>;
  marks: RxReplicationState<MarkDoc, ReplicationCheckpoint>;
  pullStream$: ReplaySubject<'RESYNC' | void>;
  cancel: () => Promise<void>;
  triggerPull: () => void;
}

/**
 * Handle conflicts silently - no user notification needed.
 * Conflicts are resolved automatically via LWW (Last-Write-Wins).
 */
function notifyConflict(_conflicts: ConflictInfo[]): void {
  // Conflicts are handled silently - no notification to user
}

/**
 * Setup replication for all collections.
 */
export function setupReplication(db: WishWithMeDatabase): ReplicationState {
  // Store database instance for direct sync operations
  setDatabaseForDirectSync(db);

  // Use ReplaySubject to buffer the last event - this ensures RESYNC events
  // are not lost if emitted before RxDB subscribes (which happens after leadership)
  const pullStream$ = new ReplaySubject<'RESYNC' | void>(1);

  // Log leadership status for debugging
  // @ts-expect-error - RxDBLeaderElectionPlugin adds these methods
  if (typeof db.isLeader === 'function') {
    // @ts-expect-error - RxDBLeaderElectionPlugin adds these methods
    console.log('[RxDB] Initial leadership status:', db.isLeader());
    // @ts-expect-error - RxDBLeaderElectionPlugin adds these methods
    db.waitForLeadership().then(() => {
      console.log('[RxDB] This tab is now the LEADER');
    });
  } else {
    console.warn('[RxDB] Leader election plugin not available');
  }

  // Wishlist replication
  const wishlistReplication = replicateRxCollection<WishlistDoc, ReplicationCheckpoint>({
    collection: db.wishlists,
    replicationIdentifier: 'wishlists-sync',
    deletedField: '_deleted',
    live: true,
    retryTime: 5000,
    waitForLeadership: true, // Only leader tab runs replication to prevent duplicates

    push: {
      async handler(docs) {
        try {
          // Filter out docs without newDocumentState (shouldn't happen, but safety check)
          const validDocs = docs.filter((d) => d.newDocumentState != null);
          if (validDocs.length === 0) return [];

          const response = await api.post<PushResponse>('/api/v1/sync/push/wishlists', {
            documents: validDocs.map((d) => d.newDocumentState),
          });
          // Notify user about conflicts (server wins)
          notifyConflict(response.data.conflicts);
          // Filter out conflicts where we can't find the matching doc in this batch
          return response.data.conflicts
            .map((c) => {
              const writeRow = docs.find((d) => d.newDocumentState?.id === c.document_id);
              if (!writeRow) return null;
              return {
                isError: true,
                documentId: c.document_id,
                writeRow,
              };
            })
            .filter((c): c is NonNullable<typeof c> => c !== null);
        } catch (error) {
          console.error('Wishlist push error:', error);
          throw error;
        }
      },
      batchSize: 10,
    },

    pull: {
      async handler(checkpoint, batchSize) {
        console.log('[RxDB] Wishlists pull handler called, checkpoint:', checkpoint);
        try {
          const params: Record<string, string | number> = {
            limit: batchSize,
          };
          if (checkpoint?.updated_at) {
            params.checkpoint_updated_at = checkpoint.updated_at;
          }
          if (checkpoint?.id) {
            params.checkpoint_id = checkpoint.id;
          }

          const response = await api.get<PullResponse<WishlistDoc>>(
            '/api/v1/sync/pull/wishlists',
            { params }
          );
          console.log('[RxDB] Wishlists pull response:', response.data.documents.length, 'docs');

          return {
            documents: response.data.documents,
            checkpoint: response.data.checkpoint || undefined,
          };
        } catch (error) {
          console.error('Wishlist pull error:', error);
          throw error;
        }
      },
      batchSize: 50,
      stream$: pullStream$.asObservable(),
    },
  });

  // Item replication
  const itemReplication = replicateRxCollection<ItemDoc, ReplicationCheckpoint>({
    collection: db.items,
    replicationIdentifier: 'items-sync',
    deletedField: '_deleted',
    live: true,
    retryTime: 5000,
    waitForLeadership: true, // Only leader tab runs replication to prevent duplicates

    push: {
      async handler(docs) {
        try {
          // Filter out docs without newDocumentState (shouldn't happen, but safety check)
          const validDocs = docs.filter((d) => d.newDocumentState != null);
          if (validDocs.length === 0) return [];

          const response = await api.post<PushResponse>('/api/v1/sync/push/items', {
            documents: validDocs.map((d) => d.newDocumentState),
          });
          // Notify user about conflicts (server wins)
          notifyConflict(response.data.conflicts);
          // Filter out conflicts where we can't find the matching doc in this batch
          return response.data.conflicts
            .map((c) => {
              const writeRow = docs.find((d) => d.newDocumentState?.id === c.document_id);
              if (!writeRow) return null;
              return {
                isError: true,
                documentId: c.document_id,
                writeRow,
              };
            })
            .filter((c): c is NonNullable<typeof c> => c !== null);
        } catch (error) {
          console.error('Item push error:', error);
          throw error;
        }
      },
      batchSize: 10,
    },

    pull: {
      async handler(checkpoint, batchSize) {
        console.log('[RxDB] Items pull handler called, checkpoint:', checkpoint);
        try {
          const params: Record<string, string | number> = {
            limit: batchSize,
          };
          if (checkpoint?.updated_at) {
            params.checkpoint_updated_at = checkpoint.updated_at;
          }
          if (checkpoint?.id) {
            params.checkpoint_id = checkpoint.id;
          }

          const response = await api.get<PullResponse<ItemDoc>>('/api/v1/sync/pull/items', {
            params,
          });
          console.log('[RxDB] Items pull response:', response.data.documents.length, 'docs');

          return {
            documents: response.data.documents,
            checkpoint: response.data.checkpoint || undefined,
          };
        } catch (error) {
          console.error('Item pull error:', error);
          throw error;
        }
      },
      batchSize: 50,
      stream$: pullStream$.asObservable(),
    },
  });

  // Mark replication
  const markReplication = replicateRxCollection<MarkDoc, ReplicationCheckpoint>({
    collection: db.marks,
    replicationIdentifier: 'marks-sync',
    deletedField: '_deleted',
    live: true,
    retryTime: 5000,
    waitForLeadership: true, // Only leader tab runs replication to prevent duplicates

    push: {
      async handler(docs) {
        try {
          // Filter out docs without newDocumentState (shouldn't happen, but safety check)
          const validDocs = docs.filter((d) => d.newDocumentState != null);
          if (validDocs.length === 0) return [];

          const response = await api.post<PushResponse>('/api/v1/sync/push/marks', {
            documents: validDocs.map((d) => d.newDocumentState),
          });
          // Notify user about conflicts (server wins)
          notifyConflict(response.data.conflicts);
          // Filter out conflicts where we can't find the matching doc in this batch
          return response.data.conflicts
            .map((c) => {
              const writeRow = docs.find((d) => d.newDocumentState?.id === c.document_id);
              if (!writeRow) return null;
              return {
                isError: true,
                documentId: c.document_id,
                writeRow,
              };
            })
            .filter((c): c is NonNullable<typeof c> => c !== null);
        } catch (error) {
          console.error('Mark push error:', error);
          throw error;
        }
      },
      batchSize: 10,
    },

    pull: {
      async handler(checkpoint, batchSize) {
        console.log('[RxDB] Marks pull handler called, checkpoint:', checkpoint);
        try {
          const params: Record<string, string | number> = {
            limit: batchSize,
          };
          if (checkpoint?.updated_at) {
            params.checkpoint_updated_at = checkpoint.updated_at;
          }
          if (checkpoint?.id) {
            params.checkpoint_id = checkpoint.id;
          }

          const response = await api.get<PullResponse<MarkDoc>>('/api/v1/sync/pull/marks', {
            params,
          });
          console.log('[RxDB] Marks pull response:', response.data.documents.length, 'docs');

          return {
            documents: response.data.documents,
            checkpoint: response.data.checkpoint || undefined,
          };
        } catch (error) {
          console.error('Mark pull error:', error);
          throw error;
        }
      },
      batchSize: 50,
      stream$: pullStream$.asObservable(),
    },
  });

  // Trigger pull when coming back online
  const onlineHandler = () => pullStream$.next();
  if (typeof window !== 'undefined') {
    window.addEventListener('online', onlineHandler);
  }

  // Debug: log when pull handler is called
  pullStream$.subscribe((event) => {
    console.log('[RxDB] pullStream$ event received:', event);
  });

  // Track when replications become active (not waiting for leadership)
  // Subscribe to active$ observables to know when replications are ready
  wishlistReplication.active$.subscribe((active) => {
    console.log('[RxDB] wishlists replication active:', active);
  });
  itemReplication.active$.subscribe((active) => {
    console.log('[RxDB] items replication active:', active);
    if (active) replicationsActive = true;
  });
  markReplication.active$.subscribe((active) => {
    console.log('[RxDB] marks replication active:', active);
  });

  // Log errors
  wishlistReplication.error$.subscribe((err) => {
    console.error('[RxDB] wishlists replication error:', err);
  });
  itemReplication.error$.subscribe((err) => {
    console.error('[RxDB] items replication error:', err);
  });
  markReplication.error$.subscribe((err) => {
    console.error('[RxDB] marks replication error:', err);
  });

  const state: ReplicationState = {
    wishlists: wishlistReplication,
    items: itemReplication,
    marks: markReplication,
    pullStream$,
    triggerPull: () => {
      console.log('[RxDB] triggerPull called');

      // Use direct sync to bypass RxDB's complex replication mechanism
      // This directly fetches items from the server and upserts them into RxDB
      const database = getDatabaseForDirectSync();
      if (database) {
        directSyncItems(database).catch((error) => {
          console.error('[RxDB] directSyncItems failed:', error);
        });
      } else {
        console.warn('[RxDB] Database not available for direct sync');
      }
    },
    cancel: async () => {
      // Remove event listener on cleanup
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', onlineHandler);
      }
      currentReplicationState = null;
      await wishlistReplication.cancel();
      await itemReplication.cancel();
      await markReplication.cancel();
    },
  };

  // Store globally for SSE access
  currentReplicationState = state;

  return state;
}

/**
 * Get the current replication state.
 * Used by SSE composable to trigger syncs.
 */
export function getReplicationState(): ReplicationState | null {
  return currentReplicationState;
}

/**
 * Directly fetch and upsert items from the server.
 * This bypasses RxDB's complex replication mechanism and directly updates the local database.
 * Use this when SSE events arrive to ensure immediate UI updates.
 */
export async function directSyncItems(db: WishWithMeDatabase): Promise<void> {
  console.log('[RxDB] directSyncItems called');
  try {
    // Fetch recent items from the server (no checkpoint = get recent items)
    const response = await api.get<PullResponse<ItemDoc>>('/api/v1/sync/pull/items', {
      params: { limit: 100 },
    });

    const documents = response.data.documents;
    console.log('[RxDB] directSyncItems fetched', documents.length, 'items');

    if (documents.length === 0) {
      return;
    }

    // Directly upsert each document into RxDB
    for (const doc of documents) {
      try {
        // Check if document exists
        const existing = await db.items.findOne(doc.id).exec();
        if (existing) {
          // Update existing document using incrementalPatch
          await existing.incrementalPatch({
            title: doc.title,
            description: doc.description,
            price: doc.price,
            currency: doc.currency,
            quantity: doc.quantity,
            source_url: doc.source_url,
            image_url: doc.image_url,
            image_base64: doc.image_base64,
            status: doc.status,
            updated_at: doc.updated_at,
            _deleted: doc._deleted,
          });
        } else {
          // Insert new document
          await db.items.insert(doc);
        }
      } catch (docError) {
        console.error('[RxDB] Error upserting item:', doc.id, docError);
      }
    }

    console.log('[RxDB] directSyncItems completed');
  } catch (error) {
    console.error('[RxDB] directSyncItems error:', error);
  }
}

/**
 * Get the database instance for direct sync operations.
 */
let dbInstance: WishWithMeDatabase | null = null;

export function setDatabaseForDirectSync(db: WishWithMeDatabase): void {
  dbInstance = db;
}

export function getDatabaseForDirectSync(): WishWithMeDatabase | null {
  return dbInstance;
}
