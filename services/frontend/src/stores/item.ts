/**
 * Item store - offline-first using PouchDB.
 * All reads come from PouchDB with reactive change subscriptions.
 * All writes go to PouchDB and sync to server via API.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { useOnline } from '@vueuse/core';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import {
  getDatabase,
  subscribeToItems,
  findById,
  upsert,
  softDelete,
  triggerSync,
  createId,
  type ItemDoc,
  type WishlistDoc,
} from '@/services/pouchdb';
import { useAuthStore } from '@/stores/auth';
import type { Item, ItemCreate, ItemUpdate } from '@/types/item';

export const useItemStore = defineStore('item', () => {
  const authStore = useAuthStore();
  const isOnline = useOnline();
  const { t } = useI18n();

  const items = ref<Item[]>([]);
  const currentItem = ref<Item | null>(null);
  const currentWishlistId = ref<string | null>(null);
  const total = ref(0);
  const isLoading = ref(false);

  let unsubscribe: (() => void) | null = null;

  /**
   * Convert PouchDB doc to Item type for API compatibility.
   */
  function docToItem(doc: ItemDoc): Item {
    return {
      id: doc._id,
      wishlist_id: doc.wishlist_id,
      title: doc.title,
      description: doc.description || null,
      price: doc.price ? String(doc.price) : null,
      currency: doc.currency || null,
      quantity: doc.quantity,
      source_url: doc.source_url || null,
      image_url: doc.image_url || null,
      image_base64: doc.image_base64 || null,
      status: doc.status,
      created_at: doc.created_at,
      updated_at: doc.updated_at,
    };
  }

  /**
   * Subscribe to items for a specific wishlist.
   */
  async function subscribeToWishlistItems(wishlistId: string): Promise<void> {
    // Cleanup previous subscription
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
    currentWishlistId.value = wishlistId;

    // Initialize database
    getDatabase();

    // Subscribe to item changes
    unsubscribe = subscribeToItems(wishlistId, (docs) => {
      items.value = docs.map(docToItem);
      total.value = items.value.length;
      isLoading.value = false;
    });
  }

  /**
   * Fetch items for a wishlist - now uses PouchDB subscription.
   */
  async function fetchItems(wishlistId: string): Promise<void> {
    if (currentWishlistId.value !== wishlistId) {
      isLoading.value = true;
      await subscribeToWishlistItems(wishlistId);
    }
  }

  /**
   * Fetch a single item by ID from PouchDB.
   */
  async function fetchItem(wishlistId: string, itemId: string): Promise<void> {
    isLoading.value = true;
    try {
      const doc = await findById<ItemDoc>(itemId);
      currentItem.value = doc ? docToItem(doc) : null;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Create a new item in PouchDB.
   * Syncs to server via API when online.
   */
  async function createItem(wishlistId: string, data: ItemCreate): Promise<Item> {
    const userId = authStore.userId;
    if (!userId) {
      throw new Error('User not authenticated');
    }

    isLoading.value = true;
    try {
      // Get wishlist to inherit access array
      const wishlist = await findById<WishlistDoc>(wishlistId);
      const access = wishlist?.access || [userId];

      const now = new Date().toISOString();
      const newDoc: Omit<ItemDoc, '_rev'> = {
        _id: createId('item'),
        type: 'item',
        wishlist_id: wishlistId,
        owner_id: userId,
        title: data.title,
        description: data.description || null,
        price: data.price ? parseFloat(data.price) : null,
        currency: data.currency || null,
        quantity: data.quantity || 1,
        source_url: data.source_url || null,
        image_url: data.image_url || null,
        image_base64: data.image_base64 || null,
        status: data.source_url && !data.skip_resolution ? 'pending' : 'resolved',
        created_at: now,
        updated_at: now,
        access,
      };

      const saved = await upsert(newDoc as ItemDoc);

      // Trigger sync if online
      const token = authStore.getAccessToken();
      if (isOnline.value && token) {
        triggerSync(token).catch(console.error);
      } else {
        // Show offline notification
        Notify.create({
          message: t('offline.createdOffline'),
          caption: t('offline.createdOfflineCaption'),
          icon: 'cloud_off',
          color: 'info',
          timeout: 3000,
        });
      }

      return docToItem(saved);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Update an item in PouchDB.
   */
  async function updateItem(
    wishlistId: string,
    itemId: string,
    data: ItemUpdate
  ): Promise<Item> {
    isLoading.value = true;
    try {
      const doc = await findById<ItemDoc>(itemId);
      if (!doc) {
        throw new Error('Item not found');
      }

      const updated = await upsert({
        ...doc,
        ...data,
        price: data.price ? parseFloat(data.price) : doc.price,
        updated_at: new Date().toISOString(),
      });

      // Update currentItem if it's the same
      if (currentItem.value?.id === itemId) {
        currentItem.value = docToItem(updated);
      }

      // Trigger sync if online
      const token = authStore.getAccessToken();
      if (isOnline.value && token) {
        triggerSync(token).catch(console.error);
      }

      return docToItem(updated);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Soft-delete an item in PouchDB.
   */
  async function deleteItem(wishlistId: string, itemId: string): Promise<void> {
    isLoading.value = true;
    try {
      await softDelete(itemId);

      // Clear current item if it's the deleted one
      if (currentItem.value?.id === itemId) {
        currentItem.value = null;
      }

      // Trigger sync if online
      const token = authStore.getAccessToken();
      if (isOnline.value && token) {
        triggerSync(token).catch(console.error);
      }
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Retry resolving an item with URL.
   * This calls the API since resolution happens server-side.
   */
  async function retryResolve(wishlistId: string, itemId: string): Promise<Item> {
    isLoading.value = true;
    try {
      // Update status to pending locally to trigger server-side resolution
      const doc = await findById<ItemDoc>(itemId);
      if (doc) {
        await upsert({
          ...doc,
          status: 'pending',
          updated_at: new Date().toISOString(),
        });
      }

      // Trigger sync to push the pending status to server
      // Server will pick it up via changes watcher and resolve it
      const token = authStore.getAccessToken();
      if (isOnline.value && token) {
        await triggerSync(token);

        // Return current item state (will be updated when resolution completes)
        const updated = await findById<ItemDoc>(itemId);
        return updated ? docToItem(updated) : docToItem(doc!);
      } else {
        Notify.create({
          message: t('offline.youAreOffline'),
          caption: t('offline.willSyncWhenOnline'),
          icon: 'cloud_off',
          color: 'warning',
          timeout: 3000,
        });
        throw new Error('Cannot resolve item while offline');
      }
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Cleanup subscriptions.
   */
  function clearItems(): void {
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
    items.value = [];
    currentItem.value = null;
    currentWishlistId.value = null;
    total.value = 0;
  }

  return {
    items: computed(() => items.value),
    currentItem: computed(() => currentItem.value),
    total: computed(() => total.value),
    isLoading: computed(() => isLoading.value),
    fetchItems,
    fetchItem,
    createItem,
    updateItem,
    deleteItem,
    retryResolve,
    clearItems,
  };
});
