/**
 * Composable for offline-first item data access via RxDB.
 * All reads come from RxDB with reactive subscriptions.
 * Changes are written to RxDB and replicated to server when online.
 */

import { ref, computed, onMounted, onUnmounted, watch, type Ref } from 'vue';
import { useOnline } from '@vueuse/core';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { getDatabase, type WishWithMeDatabase, type ItemDoc } from '@/services/rxdb';
import type { Subscription } from 'rxjs';

export function useItems(wishlistId: string | Ref<string> | (() => string)) {
  const isOnline = useOnline();
  const { t } = useI18n();

  const items = ref<ItemDoc[]>([]);
  const isLoading = ref(true);
  let subscription: Subscription | null = null;
  let db: WishWithMeDatabase | null = null;

  const getWishlistId = (): string => {
    if (typeof wishlistId === 'function') {
      return wishlistId();
    }
    if (typeof wishlistId === 'object' && 'value' in wishlistId) {
      return wishlistId.value;
    }
    return wishlistId;
  };

  async function init(): Promise<void> {
    const wId = getWishlistId();
    if (!wId) return;

    // Cleanup previous subscription
    subscription?.unsubscribe();

    try {
      db = await getDatabase();

      const query = db.items.find({
        selector: {
          wishlist_id: wId,
          _deleted: { $ne: true },
        },
        sort: [{ created_at: 'desc' }],
      });

      subscription = query.$.subscribe((docs) => {
        items.value = docs.map((d) => d.toJSON() as ItemDoc);
        isLoading.value = false;
      });
    } catch (error) {
      console.error('Failed to initialize items:', error);
      isLoading.value = false;
    }
  }

  async function createItem(data: {
    title: string;
    description?: string;
    price?: string;
    currency?: string;
    quantity?: number;
    source_url?: string;
    image_url?: string;
    image_base64?: string;
  }): Promise<ItemDoc> {
    const wId = getWishlistId();
    if (!db) {
      db = await getDatabase();
    }

    const now = new Date().toISOString();
    const newItem: ItemDoc = {
      id: crypto.randomUUID(),
      wishlist_id: wId,
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

    await db.items.insert(newItem);

    if (!isOnline.value) {
      Notify.create({
        message: t('offline.createdOffline'),
        caption: t('offline.createdOfflineCaption'),
        icon: 'cloud_off',
        color: 'info',
      });
    }

    return newItem;
  }

  async function updateItem(
    id: string,
    data: Partial<
      Pick<
        ItemDoc,
        | 'title'
        | 'description'
        | 'price'
        | 'currency'
        | 'quantity'
        | 'source_url'
        | 'image_url'
        | 'image_base64'
        | 'status'
      >
    >
  ): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    const doc = await db.items.findOne(id).exec();
    if (doc) {
      await doc.patch({
        ...data,
        updated_at: new Date().toISOString(),
      });
    }
  }

  async function deleteItem(id: string): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    const doc = await db.items.findOne(id).exec();
    if (doc) {
      await doc.patch({
        _deleted: true,
        updated_at: new Date().toISOString(),
      });
    }
  }

  async function getItem(id: string): Promise<ItemDoc | null> {
    if (!db) {
      db = await getDatabase();
    }
    const doc = await db.items.findOne(id).exec();
    return doc ? (doc.toJSON() as ItemDoc) : null;
  }

  onMounted(() => {
    init();
  });

  onUnmounted(() => {
    subscription?.unsubscribe();
  });

  // Watch for wishlist ID changes if it's reactive
  if (typeof wishlistId === 'function') {
    watch(() => wishlistId(), () => {
      isLoading.value = true;
      init();
    });
  } else if (typeof wishlistId === 'object' && 'value' in wishlistId) {
    watch(wishlistId, () => {
      isLoading.value = true;
      init();
    });
  }

  return {
    items: computed(() => items.value),
    isLoading: computed(() => isLoading.value),
    isOnline,
    createItem,
    updateItem,
    deleteItem,
    getItem,
    refresh: init,
  };
}
