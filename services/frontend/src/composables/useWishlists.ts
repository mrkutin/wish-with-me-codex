/**
 * Composable for offline-first wishlist data access via RxDB.
 * All reads come from RxDB with reactive subscriptions.
 * Changes are written to RxDB and replicated to server when online.
 */

import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useOnline } from '@vueuse/core';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { getDatabase, type WishWithMeDatabase, type WishlistDoc } from '@/services/rxdb';
import { useAuthStore } from '@/stores/auth';
import type { Subscription } from 'rxjs';

export function useWishlists() {
  const authStore = useAuthStore();
  const isOnline = useOnline();
  const { t } = useI18n();

  const wishlists = ref<WishlistDoc[]>([]);
  const isLoading = ref(true);
  let subscription: Subscription | null = null;
  let db: WishWithMeDatabase | null = null;

  async function init(): Promise<void> {
    if (!authStore.user?.id) return;

    try {
      db = await getDatabase();

      // Subscribe to reactive RxDB query
      const query = db.wishlists.find({
        selector: {
          user_id: authStore.user.id,
          _deleted: { $ne: true },
        },
        sort: [{ updated_at: 'desc' }],
      });

      subscription = query.$.subscribe((docs) => {
        wishlists.value = docs.map((d) => d.toJSON() as WishlistDoc);
        isLoading.value = false;
      });
    } catch (error) {
      console.error('Failed to initialize wishlists:', error);
      isLoading.value = false;
    }
  }

  async function createWishlist(data: {
    name: string;
    description?: string;
    is_public?: boolean;
  }): Promise<WishlistDoc | null> {
    if (!authStore.user) return null;

    if (!db) {
      db = await getDatabase();
    }

    const now = new Date().toISOString();
    const newWishlist: WishlistDoc = {
      id: crypto.randomUUID(),
      user_id: authStore.user.id,
      name: data.name,
      description: data.description || null,
      is_public: data.is_public || false,
      created_at: now,
      updated_at: now,
      _deleted: false,
    };

    await db.wishlists.insert(newWishlist);

    // Show offline notification if offline
    if (!isOnline.value) {
      Notify.create({
        message: t('offline.createdOffline'),
        caption: t('offline.createdOfflineCaption'),
        icon: 'cloud_off',
        color: 'info',
      });
    }

    return newWishlist;
  }

  async function updateWishlist(
    id: string,
    data: Partial<Pick<WishlistDoc, 'name' | 'description' | 'is_public'>>
  ): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    const doc = await db.wishlists.findOne(id).exec();
    if (doc) {
      await doc.patch({
        ...data,
        updated_at: new Date().toISOString(),
      });
    }
  }

  async function deleteWishlist(id: string): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    const doc = await db.wishlists.findOne(id).exec();
    if (doc) {
      await doc.patch({
        _deleted: true,
        updated_at: new Date().toISOString(),
      });
    }
  }

  async function getWishlist(id: string): Promise<WishlistDoc | null> {
    if (!db) {
      db = await getDatabase();
    }
    const doc = await db.wishlists.findOne(id).exec();
    return doc ? (doc.toJSON() as WishlistDoc) : null;
  }

  onMounted(() => {
    init();
  });

  onUnmounted(() => {
    subscription?.unsubscribe();
  });

  return {
    wishlists: computed(() => wishlists.value),
    isLoading: computed(() => isLoading.value),
    isOnline,
    createWishlist,
    updateWishlist,
    deleteWishlist,
    getWishlist,
    refresh: init,
  };
}
