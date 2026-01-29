/**
 * RxDB database setup for offline-first wishlist storage.
 */

import { createRxDatabase, addRxPlugin, type RxDatabase, type RxCollection } from 'rxdb';
import { getRxStorageDexie } from 'rxdb/plugins/storage-dexie';
import { RxDBDevModePlugin } from 'rxdb/plugins/dev-mode';
import { RxDBQueryBuilderPlugin } from 'rxdb/plugins/query-builder';
import { RxDBUpdatePlugin } from 'rxdb/plugins/update';
import { RxDBLeaderElectionPlugin } from 'rxdb/plugins/leader-election';

/**
 * Suppress RxDB premium marketing messages in console.
 * The message is logged on first bulkWrite(), so we need a permanent filter.
 */
const originalWarn = console.warn.bind(console);
console.warn = (...args: unknown[]) => {
  const msg = args.join(' ');
  if (msg.includes('Open Core RxStorage')) return;
  originalWarn(...args);
};

import {
  wishlistSchema,
  itemSchema,
  markSchema,
  type WishlistDoc,
  type ItemDoc,
  type MarkDoc,
} from './schemas';

// Add plugins
if (process.env.NODE_ENV === 'development') {
  addRxPlugin(RxDBDevModePlugin);
}
addRxPlugin(RxDBQueryBuilderPlugin);
addRxPlugin(RxDBUpdatePlugin);
addRxPlugin(RxDBLeaderElectionPlugin);

// Collection types
export type WishlistCollection = RxCollection<WishlistDoc>;
export type ItemCollection = RxCollection<ItemDoc>;
export type MarkCollection = RxCollection<MarkDoc>;

export type WishWithMeCollections = {
  wishlists: WishlistCollection;
  items: ItemCollection;
  marks: MarkCollection;
};

export type WishWithMeDatabase = RxDatabase<WishWithMeCollections>;

let dbInstance: WishWithMeDatabase | null = null;

/**
 * Get or create the RxDB database instance.
 */
export async function getDatabase(): Promise<WishWithMeDatabase> {
  if (dbInstance) {
    return dbInstance;
  }

  const db = await createRxDatabase<WishWithMeCollections>({
    name: 'wishwithme',
    storage: getRxStorageDexie(),
    multiInstance: true,
    eventReduce: true,
    ignoreDuplicate: true,
  });

  // Create collections
  await db.addCollections({
    wishlists: {
      schema: wishlistSchema,
    },
    items: {
      schema: itemSchema,
    },
    marks: {
      schema: markSchema,
    },
  });

  dbInstance = db;
  return db;
}

/**
 * Destroy the database instance (useful for logout).
 */
export async function destroyDatabase(): Promise<void> {
  if (dbInstance) {
    await dbInstance.destroy();
    dbInstance = null;
  }
}

/**
 * Clear all data from the database (useful for logout).
 */
export async function clearDatabase(): Promise<void> {
  if (dbInstance) {
    await dbInstance.wishlists.remove();
    await dbInstance.items.remove();
    await dbInstance.marks.remove();
  }
}

export { type WishlistDoc, type ItemDoc, type MarkDoc } from './schemas';
