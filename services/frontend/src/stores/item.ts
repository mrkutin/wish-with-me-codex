/**
 * Item store - offline-first using RxDB.
 * All reads come from RxDB with reactive subscriptions.
 * All writes go to RxDB and sync to server via replication.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { useOnline } from '@vueuse/core';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { getDatabase, type WishWithMeDatabase, type ItemDoc } from '@/services/rxdb';
import { api } from '@/boot/axios';
import type { Subscription } from 'rxjs';
import type { Item, ItemCreate, ItemUpdate } from '@/types/item';

export const useItemStore = defineStore('item', () => {
  const isOnline = useOnline();
  const { t } = useI18n();

  const items = ref<Item[]>([]);
  const currentItem = ref<Item | null>(null);
  const currentWishlistId = ref<string | null>(null);
  const total = ref(0);
  const isLoading = ref(false);

  let subscription: Subscription | null = null;
  let db: WishWithMeDatabase | null = null;

  /**
   * Convert RxDB doc to Item type for API compatibility.
   */
  function docToItem(doc: ItemDoc): Item {
    return {
      id: doc.id,
      wishlist_id: doc.wishlist_id,
      title: doc.title,
      description: doc.description,
      price: doc.price,
      currency: doc.currency,
      quantity: doc.quantity,
      source_url: doc.source_url,
      image_url: doc.image_url,
      image_base64: doc.image_base64,
      status: doc.status,
      created_at: doc.created_at,
      updated_at: doc.updated_at,
    };
  }

  /**
   * Subscribe to items for a specific wishlist.
   */
  async function subscribeToWishlist(wishlistId: string): Promise<void> {
    // Cleanup previous subscription
    subscription?.unsubscribe();
    currentWishlistId.value = wishlistId;

    if (!db) {
      db = await getDatabase();
    }

    const query = db.items.find({
      selector: {
        wishlist_id: wishlistId,
        _deleted: { $ne: true },
      },
      sort: [{ created_at: 'desc' }],
    });

    subscription = query.$.subscribe((docs) => {
      items.value = docs.map((d) => docToItem(d.toJSON() as ItemDoc));
      total.value = items.value.length;
      isLoading.value = false;
    });
  }

  /**
   * Fetch items for a wishlist - now uses RxDB subscription.
   */
  async function fetchItems(wishlistId: string): Promise<void> {
    if (currentWishlistId.value !== wishlistId) {
      isLoading.value = true;
      await subscribeToWishlist(wishlistId);
    }
  }

  /**
   * Fetch a single item by ID from RxDB.
   */
  async function fetchItem(wishlistId: string, itemId: string): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const doc = await db.items.findOne(itemId).exec();
      currentItem.value = doc ? docToItem(doc.toJSON() as ItemDoc) : null;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Create a new item in RxDB.
   * Syncs to server via replication when online.
   */
  async function createItem(wishlistId: string, data: ItemCreate): Promise<Item> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const now = new Date().toISOString();
      const newDoc: ItemDoc = {
        id: crypto.randomUUID(),
        wishlist_id: wishlistId,
        title: data.title,
        description: data.description || null,
        price: data.price || null,
        currency: data.currency || null,
        quantity: data.quantity || 1,
        source_url: data.source_url || null,
        image_url: data.image_url || null,
        image_base64: data.image_base64 || null,
        status: data.source_url ? 'pending' : 'resolved',
        created_at: now,
        updated_at: now,
        _deleted: false,
      };

      await db.items.insert(newDoc);

      // Show offline notification
      if (!isOnline.value) {
        Notify.create({
          message: t('offline.createdOffline'),
          caption: t('offline.createdOfflineCaption'),
          icon: 'cloud_off',
          color: 'info',
          timeout: 3000,
        });
      }

      return docToItem(newDoc);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Update an item in RxDB.
   */
  async function updateItem(
    wishlistId: string,
    itemId: string,
    data: ItemUpdate
  ): Promise<Item> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const doc = await db.items.findOne(itemId).exec();
      if (!doc) {
        throw new Error('Item not found');
      }

      await doc.patch({
        ...data,
        updated_at: new Date().toISOString(),
      });

      const updated = doc.toJSON() as ItemDoc;

      // Update currentItem if it's the same
      if (currentItem.value?.id === itemId) {
        currentItem.value = docToItem(updated);
      }

      return docToItem(updated);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Soft-delete an item in RxDB.
   */
  async function deleteItem(wishlistId: string, itemId: string): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const doc = await db.items.findOne(itemId).exec();
      if (doc) {
        await doc.patch({
          _deleted: true,
          updated_at: new Date().toISOString(),
        });
      }

      // Clear current item if it's the deleted one
      if (currentItem.value?.id === itemId) {
        currentItem.value = null;
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
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      // Update status to resolving locally
      const doc = await db.items.findOne(itemId).exec();
      if (doc) {
        await doc.patch({
          status: 'resolving',
          updated_at: new Date().toISOString(),
        });
      }

      // Call API for actual resolution (requires server-side processing)
      if (isOnline.value) {
        const response = await api.post<Item>(
          `/api/v1/wishlists/${wishlistId}/items/${itemId}/resolve`
        );

        // Update local doc with resolved data
        if (doc) {
          await doc.patch({
            title: response.data.title,
            description: response.data.description,
            price: response.data.price,
            currency: response.data.currency,
            image_url: response.data.image_url,
            image_base64: response.data.image_base64,
            status: response.data.status,
            updated_at: response.data.updated_at,
          });
        }

        return response.data;
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
    subscription?.unsubscribe();
    subscription = null;
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
