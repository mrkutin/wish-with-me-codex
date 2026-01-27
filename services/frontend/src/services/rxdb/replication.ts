/**
 * RxDB replication setup for syncing with backend.
 */

import { replicateRxCollection, type RxReplicationState } from 'rxdb/plugins/replication';
import { Subject } from 'rxjs';
import { api } from '@/boot/axios';
import type { WishWithMeDatabase, WishlistDoc, ItemDoc, MarkDoc } from './index';

// Global reference for SSE to trigger syncs
let currentReplicationState: ReplicationState | null = null;

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
    waitForLeadership: false, // Disabled to ensure replication runs in every tab

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
    waitForLeadership: false, // Disabled to ensure replication runs in every tab

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
    waitForLeadership: false, // Disabled to ensure replication runs in every tab

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

  const state: ReplicationState = {
    wishlists: wishlistReplication,
    items: itemReplication,
    marks: markReplication,
    pullStream$,
    triggerPull: () => {
      console.log('[RxDB] triggerPull called');
      // Call reSync() directly on each replication state
      // This is the documented method to trigger immediate checkpoint iteration
      console.log('[RxDB] Calling reSync() on wishlists...');
      wishlistReplication.reSync();
      console.log('[RxDB] Calling reSync() on items...');
      itemReplication.reSync();
      console.log('[RxDB] Calling reSync() on marks...');
      markReplication.reSync();
      console.log('[RxDB] reSync() called on all replications');
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
