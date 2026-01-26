/**
 * RxDB replication setup for syncing with backend.
 */

import { replicateRxCollection, type RxReplicationState } from 'rxdb/plugins/replication';
import { Subject } from 'rxjs';
import { api } from '@/boot/axios';
import type { WishWithMeDatabase, WishlistDoc, ItemDoc } from './index';

export interface ReplicationCheckpoint {
  updated_at: string;
  id: string;
}

interface PullResponse<T> {
  documents: T[];
  checkpoint: ReplicationCheckpoint | null;
}

interface PushResponse {
  conflicts: Array<{
    document_id: string;
    error: string;
    server_document?: Record<string, unknown>;
  }>;
}

export interface ReplicationState {
  wishlists: RxReplicationState<WishlistDoc, ReplicationCheckpoint>;
  items: RxReplicationState<ItemDoc, ReplicationCheckpoint>;
  pullStream$: Subject<void>;
  cancel: () => Promise<void>;
  triggerPull: () => void;
}

/**
 * Setup replication for all collections.
 */
export function setupReplication(db: WishWithMeDatabase): ReplicationState {
  const pullStream$ = new Subject<void>();

  // Wishlist replication
  const wishlistReplication = replicateRxCollection<WishlistDoc, ReplicationCheckpoint>({
    collection: db.wishlists,
    replicationIdentifier: 'wishlists-sync',
    deletedField: '_deleted',
    live: true,
    retryTime: 5000,
    waitForLeadership: true,

    push: {
      async handler(docs) {
        try {
          const response = await api.post<PushResponse>('/api/v1/sync/push/wishlists', {
            documents: docs.map((d) => d.newDocumentState),
          });
          return response.data.conflicts.map((c) => ({
            isError: true,
            documentId: c.document_id,
            writeRow: docs.find((d) => d.newDocumentState.id === c.document_id),
          }));
        } catch (error) {
          console.error('Wishlist push error:', error);
          throw error;
        }
      },
      batchSize: 10,
    },

    pull: {
      async handler(checkpoint, batchSize) {
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
    waitForLeadership: true,

    push: {
      async handler(docs) {
        try {
          const response = await api.post<PushResponse>('/api/v1/sync/push/items', {
            documents: docs.map((d) => d.newDocumentState),
          });
          return response.data.conflicts.map((c) => ({
            isError: true,
            documentId: c.document_id,
            writeRow: docs.find((d) => d.newDocumentState.id === c.document_id),
          }));
        } catch (error) {
          console.error('Item push error:', error);
          throw error;
        }
      },
      batchSize: 10,
    },

    pull: {
      async handler(checkpoint, batchSize) {
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

  // Trigger pull when coming back online
  const onlineHandler = () => pullStream$.next();
  if (typeof window !== 'undefined') {
    window.addEventListener('online', onlineHandler);
  }

  return {
    wishlists: wishlistReplication,
    items: itemReplication,
    pullStream$,
    triggerPull: () => pullStream$.next(),
    cancel: async () => {
      // Remove event listener on cleanup
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', onlineHandler);
      }
      await wishlistReplication.cancel();
      await itemReplication.cancel();
    },
  };
}
