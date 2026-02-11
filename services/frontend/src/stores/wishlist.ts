/**
 * Wishlist store - offline-first using PouchDB.
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
  subscribeToWishlists,
  findById,
  upsert,
  softDelete,
  triggerSync,
  createId,
  type WishlistDoc,
} from '@/services/pouchdb';
import { useAuthStore } from '@/stores/auth';
import type {
  Wishlist,
  WishlistCreate,
  WishlistUpdate,
} from '@/types/wishlist';

export const useWishlistStore = defineStore('wishlist', () => {
  const authStore = useAuthStore();
  const isOnline = useOnline();
  const { t } = useI18n();

  const wishlists = ref<Wishlist[]>([]);
  const currentWishlist = ref<Wishlist | null>(null);
  const total = ref(0);
  const isLoading = ref(false);
  const isInitialized = ref(false);

  let unsubscribe: (() => void) | null = null;

  /**
   * Convert PouchDB doc to Wishlist type for API compatibility.
   */
  function docToWishlist(doc: WishlistDoc): Wishlist {
    return {
      id: doc._id,
      user_id: doc.owner_id,
      name: doc.name,
      description: doc.description || null,
      is_public: doc.is_public,
      icon: doc.icon || 'card_giftcard',
      icon_color: doc.icon_color || 'primary',
      created_at: doc.created_at,
      updated_at: doc.updated_at,
    };
  }

  /**
   * Initialize PouchDB subscription for wishlists.
   * Called when user logs in.
   */
  async function initializeStore(): Promise<void> {
    const userId = authStore.userId;
    if (isInitialized.value || !userId) return;

    isLoading.value = true;
    try {
      // Initialize database
      getDatabase();

      // Subscribe to wishlist changes
      unsubscribe = subscribeToWishlists(userId, (docs) => {
        wishlists.value = docs.map(docToWishlist);
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
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
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
    // Data is now loaded reactively via PouchDB subscription
  }

  /**
   * Fetch a single wishlist by ID from PouchDB.
   */
  async function fetchWishlist(id: string): Promise<void> {
    isLoading.value = true;
    try {
      const doc = await findById<WishlistDoc>(id);
      currentWishlist.value = doc ? docToWishlist(doc) : null;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Create a new wishlist in PouchDB.
   * Syncs to server via API when online.
   */
  async function createWishlist(data: WishlistCreate): Promise<Wishlist> {
    const userId = authStore.userId;
    if (!userId) {
      throw new Error('User not authenticated');
    }

    isLoading.value = true;
    try {
      const now = new Date().toISOString();
      const newDoc: Omit<WishlistDoc, '_rev'> = {
        _id: createId('wishlist'),
        type: 'wishlist',
        owner_id: userId,
        name: data.name,
        description: data.description || null,
        is_public: data.is_public || false,
        icon: data.icon || 'card_giftcard',
        icon_color: data.icon_color || 'primary',
        created_at: now,
        updated_at: now,
        access: [userId],
      };

      const saved = await upsert(newDoc as WishlistDoc);

      // Trigger sync if online
      if (isOnline.value && authStore.getAccessToken()) {
        triggerSync().catch(console.error);
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

      return docToWishlist(saved);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Update a wishlist in PouchDB.
   */
  async function updateWishlist(id: string, data: WishlistUpdate): Promise<Wishlist> {
    isLoading.value = true;
    try {
      const doc = await findById<WishlistDoc>(id);
      if (!doc) {
        throw new Error('Wishlist not found');
      }

      const updated = await upsert({
        ...doc,
        ...data,
        updated_at: new Date().toISOString(),
      });

      // Update currentWishlist if it's the same
      if (currentWishlist.value?.id === id) {
        currentWishlist.value = docToWishlist(updated);
      }

      // Trigger sync if online
      if (isOnline.value && authStore.getAccessToken()) {
        triggerSync().catch(console.error);
      }

      return docToWishlist(updated);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Soft-delete a wishlist in PouchDB.
   */
  async function deleteWishlist(id: string): Promise<void> {
    isLoading.value = true;
    try {
      await softDelete(id);

      // Clear current wishlist if it's the deleted one
      if (currentWishlist.value?.id === id) {
        currentWishlist.value = null;
      }

      // Trigger sync if online
      if (isOnline.value && authStore.getAccessToken()) {
        triggerSync().catch(console.error);
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
