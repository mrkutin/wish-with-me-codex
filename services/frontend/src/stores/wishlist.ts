/**
 * Wishlist store - offline-first using RxDB.
 * All reads come from RxDB with reactive subscriptions.
 * All writes go to RxDB and sync to server via replication.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { useOnline } from '@vueuse/core';
import { Notify } from 'quasar';
import { getDatabase, type WishWithMeDatabase, type WishlistDoc } from '@/services/rxdb';
import { useAuthStore } from '@/stores/auth';
import type { Subscription } from 'rxjs';
import type {
  Wishlist,
  WishlistCreate,
  WishlistUpdate,
} from '@/types/wishlist';

export const useWishlistStore = defineStore('wishlist', () => {
  const authStore = useAuthStore();
  const isOnline = useOnline();

  const wishlists = ref<Wishlist[]>([]);
  const currentWishlist = ref<Wishlist | null>(null);
  const total = ref(0);
  const isLoading = ref(false);
  const isInitialized = ref(false);

  let subscription: Subscription | null = null;
  let db: WishWithMeDatabase | null = null;

  /**
   * Convert RxDB doc to Wishlist type for API compatibility.
   */
  function docToWishlist(doc: WishlistDoc): Wishlist {
    return {
      id: doc.id,
      user_id: doc.user_id,
      name: doc.name,
      description: doc.description,
      is_public: doc.is_public,
      created_at: doc.created_at,
      updated_at: doc.updated_at,
    };
  }

  /**
   * Initialize RxDB subscription for wishlists.
   * Called when user logs in.
   */
  async function initializeStore(): Promise<void> {
    if (isInitialized.value || !authStore.user?.id) return;

    isLoading.value = true;
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
        wishlists.value = docs.map((d) => docToWishlist(d.toJSON() as WishlistDoc));
        total.value = wishlists.value.length;
        isLoading.value = false;
      });

      isInitialized.value = true;
    } catch (error) {
      console.error('Failed to initialize wishlist store:', error);
      isLoading.value = false;
    }
  }

  /**
   * Cleanup store on logout.
   */
  function cleanup(): void {
    subscription?.unsubscribe();
    subscription = null;
    db = null;
    wishlists.value = [];
    currentWishlist.value = null;
    total.value = 0;
    isInitialized.value = false;
  }

  /**
   * Legacy method for compatibility - now auto-subscribes.
   */
  async function fetchWishlists(): Promise<void> {
    if (!isInitialized.value) {
      await initializeStore();
    }
    // Data is now loaded reactively via RxDB subscription
  }

  /**
   * Fetch a single wishlist by ID from RxDB.
   */
  async function fetchWishlist(id: string): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const doc = await db.wishlists.findOne(id).exec();
      currentWishlist.value = doc ? docToWishlist(doc.toJSON() as WishlistDoc) : null;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Create a new wishlist in RxDB.
   * Syncs to server via replication when online.
   */
  async function createWishlist(data: WishlistCreate): Promise<Wishlist> {
    if (!db) {
      db = await getDatabase();
    }
    if (!authStore.user) {
      throw new Error('User not authenticated');
    }

    isLoading.value = true;
    try {
      const now = new Date().toISOString();
      const newDoc: WishlistDoc = {
        id: crypto.randomUUID(),
        user_id: authStore.user.id,
        name: data.name,
        description: data.description || null,
        is_public: data.is_public || false,
        created_at: now,
        updated_at: now,
        _deleted: false,
      };

      await db.wishlists.insert(newDoc);

      // Show offline notification
      if (!isOnline.value) {
        Notify.create({
          message: 'Saved offline',
          caption: 'Will sync when back online',
          icon: 'cloud_off',
          color: 'info',
          timeout: 3000,
        });
      }

      return docToWishlist(newDoc);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Update a wishlist in RxDB.
   */
  async function updateWishlist(id: string, data: WishlistUpdate): Promise<Wishlist> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const doc = await db.wishlists.findOne(id).exec();
      if (!doc) {
        throw new Error('Wishlist not found');
      }

      await doc.patch({
        ...data,
        updated_at: new Date().toISOString(),
      });

      const updated = doc.toJSON() as WishlistDoc;

      // Update currentWishlist if it's the same
      if (currentWishlist.value?.id === id) {
        currentWishlist.value = docToWishlist(updated);
      }

      return docToWishlist(updated);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Soft-delete a wishlist in RxDB.
   */
  async function deleteWishlist(id: string): Promise<void> {
    if (!db) {
      db = await getDatabase();
    }

    isLoading.value = true;
    try {
      const doc = await db.wishlists.findOne(id).exec();
      if (doc) {
        await doc.patch({
          _deleted: true,
          updated_at: new Date().toISOString(),
        });
      }

      // Clear current wishlist if it's the deleted one
      if (currentWishlist.value?.id === id) {
        currentWishlist.value = null;
      }
    } finally {
      isLoading.value = false;
    }
  }

  function clearWishlists(): void {
    cleanup();
  }

  return {
    wishlists: computed(() => wishlists.value),
    currentWishlist: computed(() => currentWishlist.value),
    total: computed(() => total.value),
    isLoading: computed(() => isLoading.value),
    isInitialized: computed(() => isInitialized.value),
    initializeStore,
    cleanup,
    fetchWishlists,
    fetchWishlist,
    createWishlist,
    updateWishlist,
    deleteWishlist,
    clearWishlists,
  };
});
