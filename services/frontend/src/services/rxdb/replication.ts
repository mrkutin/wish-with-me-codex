/**
 * RxDB replication setup for syncing with backend.
 */

import { replicateRxCollection, type RxReplicationState } from 'rxdb/plugins/replication';
import { Subject } from 'rxjs';
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
  pullStream$: Subject<'RESYNC' | void>;
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
  // Use 'RESYNC' | void to allow emitting RESYNC flag for full sync
  const pullStream$ = new Subject<'RESYNC' | void>();

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
      console.log('[RxDB] triggerPull called, replicationsActive:', replicationsActive);
      // Log replication states for debugging
      console.log('[RxDB] Replication states:', {
        wishlists: {
          isStopped: wishlistReplication.isStopped(),
        },
        items: {
          isStopped: itemReplication.isStopped(),
        },
        marks: {
          isStopped: markReplication.isStopped(),
        },
      });

      // If replications aren't active yet (waiting for leadership), log warning
      if (!replicationsActive) {
        console.warn('[RxDB] Replications not yet active (waiting for leadership?). reSync may be queued.');
      }

      // Call reSync() directly on each replication state
      // This is the documented method to trigger immediate checkpoint iteration
      if (!wishlistReplication.isStopped()) {
        console.log('[RxDB] Calling reSync() on wishlists...');
        wishlistReplication.reSync();
      } else {
        console.warn('[RxDB] wishlists replication is stopped, skipping reSync');
      }

      if (!itemReplication.isStopped()) {
        console.log('[RxDB] Calling reSync() on items...');
        itemReplication.reSync();
      } else {
        console.warn('[RxDB] items replication is stopped, skipping reSync');
      }

      if (!markReplication.isStopped()) {
        console.log('[RxDB] Calling reSync() on marks...');
        markReplication.reSync();
      } else {
        console.warn('[RxDB] marks replication is stopped, skipping reSync');
      }

      console.log('[RxDB] reSync() called on all active replications');

      // Also emit on pullStream$ as backup trigger
      console.log('[RxDB] Emitting on pullStream$...');
      pullStream$.next();
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
