import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from '@/boot/axios';
import type { Item, ItemCreate, ItemUpdate, ItemListResponse } from '@/types/item';

export const useItemStore = defineStore('item', () => {
  const items = ref<Item[]>([]);
  const currentItem = ref<Item | null>(null);
  const total = ref(0);
  const isLoading = ref(false);

  async function fetchItems(
    wishlistId: string,
    limit = 50,
    offset = 0
  ): Promise<void> {
    isLoading.value = true;
    try {
      const response = await api.get<ItemListResponse>(
        `/api/v1/wishlists/${wishlistId}/items`,
        {
          params: { limit, offset },
        }
      );
      items.value = response.data.items;
      total.value = response.data.total;
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchItem(wishlistId: string, itemId: string): Promise<void> {
    isLoading.value = true;
    try {
      const response = await api.get<Item>(
        `/api/v1/wishlists/${wishlistId}/items/${itemId}`
      );
      currentItem.value = response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function createItem(
    wishlistId: string,
    data: ItemCreate
  ): Promise<Item> {
    isLoading.value = true;
    try {
      const response = await api.post<Item>(
        `/api/v1/wishlists/${wishlistId}/items`,
        data
      );
      items.value.unshift(response.data);
      total.value++;
      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function updateItem(
    wishlistId: string,
    itemId: string,
    data: ItemUpdate
  ): Promise<Item> {
    isLoading.value = true;
    try {
      const response = await api.patch<Item>(
        `/api/v1/wishlists/${wishlistId}/items/${itemId}`,
        data
      );

      // Update in list
      const index = items.value.findIndex((i) => i.id === itemId);
      if (index !== -1) {
        items.value[index] = response.data;
      }

      // Update current item if it's the same
      if (currentItem.value?.id === itemId) {
        currentItem.value = response.data;
      }

      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function deleteItem(wishlistId: string, itemId: string): Promise<void> {
    isLoading.value = true;
    try {
      await api.delete(`/api/v1/wishlists/${wishlistId}/items/${itemId}`);

      // Remove from list
      items.value = items.value.filter((i) => i.id !== itemId);
      total.value--;

      // Clear current item if it's the deleted one
      if (currentItem.value?.id === itemId) {
        currentItem.value = null;
      }
    } finally {
      isLoading.value = false;
    }
  }

  async function retryResolve(wishlistId: string, itemId: string): Promise<Item> {
    isLoading.value = true;
    try {
      const response = await api.post<Item>(
        `/api/v1/wishlists/${wishlistId}/items/${itemId}/resolve`
      );

      // Update in list
      const index = items.value.findIndex((i) => i.id === itemId);
      if (index !== -1) {
        items.value[index] = response.data;
      }

      // Update current item if it's the same
      if (currentItem.value?.id === itemId) {
        currentItem.value = response.data;
      }

      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  function clearItems(): void {
    items.value = [];
    currentItem.value = null;
    total.value = 0;
  }

  return {
    items,
    currentItem,
    total,
    isLoading,
    fetchItems,
    fetchItem,
    createItem,
    updateItem,
    deleteItem,
    retryResolve,
    clearItems,
  };
});
