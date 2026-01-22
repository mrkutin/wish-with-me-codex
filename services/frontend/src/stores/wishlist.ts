import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from '@/boot/axios';
import type {
  Wishlist,
  WishlistCreate,
  WishlistUpdate,
  WishlistListResponse,
} from '@/types/wishlist';

export const useWishlistStore = defineStore('wishlist', () => {
  const wishlists = ref<Wishlist[]>([]);
  const currentWishlist = ref<Wishlist | null>(null);
  const total = ref(0);
  const isLoading = ref(false);

  async function fetchWishlists(limit = 20, offset = 0): Promise<void> {
    isLoading.value = true;
    try {
      const response = await api.get<WishlistListResponse>('/api/v1/wishlists', {
        params: { limit, offset },
      });
      wishlists.value = response.data.wishlists;
      total.value = response.data.total;
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchWishlist(id: string): Promise<void> {
    isLoading.value = true;
    try {
      const response = await api.get<Wishlist>(`/api/v1/wishlists/${id}`);
      currentWishlist.value = response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function createWishlist(data: WishlistCreate): Promise<Wishlist> {
    isLoading.value = true;
    try {
      const response = await api.post<Wishlist>('/api/v1/wishlists', data);
      wishlists.value.unshift(response.data);
      total.value++;
      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function updateWishlist(id: string, data: WishlistUpdate): Promise<Wishlist> {
    isLoading.value = true;
    try {
      const response = await api.patch<Wishlist>(`/api/v1/wishlists/${id}`, data);

      // Update in list
      const index = wishlists.value.findIndex((w) => w.id === id);
      if (index !== -1) {
        wishlists.value[index] = response.data;
      }

      // Update current wishlist if it's the same
      if (currentWishlist.value?.id === id) {
        currentWishlist.value = response.data;
      }

      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function deleteWishlist(id: string): Promise<void> {
    isLoading.value = true;
    try {
      await api.delete(`/api/v1/wishlists/${id}`);

      // Remove from list
      wishlists.value = wishlists.value.filter((w) => w.id !== id);
      total.value--;

      // Clear current wishlist if it's the deleted one
      if (currentWishlist.value?.id === id) {
        currentWishlist.value = null;
      }
    } finally {
      isLoading.value = false;
    }
  }

  function clearWishlists(): void {
    wishlists.value = [];
    currentWishlist.value = null;
    total.value = 0;
  }

  return {
    wishlists,
    currentWishlist,
    total,
    isLoading,
    fetchWishlists,
    fetchWishlist,
    createWishlist,
    updateWishlist,
    deleteWishlist,
    clearWishlists,
  };
});
