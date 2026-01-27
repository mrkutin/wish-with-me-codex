<template>
  <q-page padding>
    <q-pull-to-refresh @refresh="handleRefresh">
    <!-- Loading skeleton -->
    <div v-if="isLoading">
      <!-- Header skeleton -->
      <div class="row items-center q-mb-md">
        <q-skeleton type="QBtn" width="40px" height="40px" class="q-mr-md" />
        <q-skeleton type="text" width="200px" class="text-h5" />
      </div>
      <!-- Owner info skeleton -->
      <div class="row items-center q-mb-md">
        <q-skeleton type="QAvatar" size="40px" class="q-mr-sm" />
        <q-skeleton type="text" width="150px" />
      </div>
      <!-- Description skeleton -->
      <q-skeleton type="text" width="100%" class="q-mb-md" />
      <!-- Items section skeleton -->
      <div class="q-mt-lg">
        <div class="row items-center justify-between q-mb-md">
          <q-skeleton type="text" width="80px" class="text-h6" />
          <q-skeleton type="QBadge" width="60px" />
        </div>
        <!-- Item cards skeleton -->
        <div class="q-gutter-md">
          <q-card v-for="n in 3" :key="n">
            <q-card-section horizontal>
              <q-skeleton type="rect" width="100px" height="100px" />
              <q-card-section class="col">
                <q-skeleton type="text" width="70%" class="text-subtitle1" />
                <q-skeleton type="text" width="100%" class="q-mt-sm" />
                <q-skeleton type="text" width="30%" class="q-mt-sm" />
              </q-card-section>
            </q-card-section>
          </q-card>
        </div>
      </div>
    </div>

    <!-- Content -->
    <template v-else-if="sharedWishlist">
      <!-- Header -->
      <div class="row items-center justify-between q-mb-md">
        <div class="col row items-center no-wrap">
          <q-btn flat dense icon="arrow_back" aria-label="Go back" @click="goBack" class="q-mr-md" />
          <q-icon :name="sharedWishlist.wishlist.icon || 'card_giftcard'" size="28px" color="primary" class="q-mr-sm" />
          <span class="text-h5">{{ sharedWishlist.wishlist.title }}</span>
        </div>
      </div>

      <!-- Owner info -->
      <div class="row items-center q-mb-md">
        <q-avatar size="40px" class="q-mr-sm">
          <img v-if="sharedWishlist.wishlist.owner.avatar_base64" :src="sharedWishlist.wishlist.owner.avatar_base64" />
          <q-icon v-else name="person" />
        </q-avatar>
        <div>
          <span class="text-body2 text-grey-7">
            {{ $t('sharing.sharedBy', { name: sharedWishlist.wishlist.owner.name }) }}
          </span>
        </div>
      </div>

      <!-- Description -->
      <p v-if="sharedWishlist.wishlist.description" class="text-body2 text-grey-7 q-mb-md">
        {{ sharedWishlist.wishlist.description }}
      </p>

      <!-- Items section -->
      <div class="q-mt-lg">
        <div class="row items-center justify-between q-mb-md">
          <h2 class="text-h6 q-ma-none">{{ $t('items.title') }}</h2>
          <q-badge color="primary" outline>
            {{ sharedWishlist.items.length }} {{ $t('items.title').toLowerCase() }}
          </q-badge>
        </div>

        <!-- Empty state -->
        <div
          v-if="sharedWishlist.items.length === 0"
          class="flex flex-center column q-pa-xl"
        >
          <q-icon name="inbox" size="64px" color="grey-5" />
          <p class="text-h6 text-grey-7 q-mt-md">{{ $t('sharing.emptyWishlist') }}</p>
        </div>

        <!-- Items list -->
        <div v-else class="q-gutter-md">
          <SharedItemCard
            v-for="item in sharedWishlist.items"
            :key="item.id"
            :item="item"
            :can-mark="canMark"
            :is-marking="markingItemId === item.id"
            @mark="markItem"
            @unmark="unmarkItem"
          />
        </div>
      </div>
    </template>

    <!-- Not found -->
    <div v-else class="flex flex-center column q-pa-xl">
      <q-icon name="error_outline" size="64px" color="grey-5" />
      <p class="text-h6 text-grey-7 q-mt-md">{{ $t('sharing.linkNotFound') }}</p>
    </div>
    </q-pull-to-refresh>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar, LocalStorage } from 'quasar';
import { useI18n } from 'vue-i18n';
import { api } from '@/boot/axios';
import { useAuthStore } from '@/stores/auth';
import SharedItemCard from '@/components/items/SharedItemCard.vue';
import type { SharedWishlistResponse, SharedItem, MarkResponse } from '@/types/share';

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();
const authStore = useAuthStore();

const token = computed(() => route.params.token as string);

const isLoading = ref(true);
const sharedWishlist = ref<SharedWishlistResponse | null>(null);
const markingItemId = ref<string | null>(null);

const canMark = computed(() => {
  return sharedWishlist.value?.permissions.includes('mark') ?? false;
});

function goBack() {
  router.push({ name: 'wishlists', query: { tab: 'shared' } });
}

async function handleRefresh(done: () => void) {
  try {
    await fetchSharedWishlist();
  } finally {
    done();
  }
}

async function fetchSharedWishlist() {
  isLoading.value = true;
  try {
    const response = await api.get<SharedWishlistResponse>(`/api/v1/shared/${token.value}`);

    // If current user is the owner, redirect to normal wishlist view
    if (authStore.user && response.data.wishlist.owner.id === authStore.user.id) {
      router.replace({ name: 'wishlist-detail', params: { id: response.data.wishlist.id } });
      return;
    }

    sharedWishlist.value = response.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      // Store share token and redirect to login
      LocalStorage.set(PENDING_SHARE_TOKEN_KEY, token.value);
      router.push({ name: 'login', query: { share_token: token.value } });
      return;
    }
    if (error.response?.status === 404) {
      $q.notify({
        type: 'negative',
        message: t('sharing.linkNotFound'),
      });
    } else {
      $q.notify({
        type: 'negative',
        message: t('errors.generic'),
      });
    }
  } finally {
    isLoading.value = false;
  }
}

async function markItem(item: SharedItem, quantity: number = 1) {
  if (!canMark.value || markingItemId.value) return;

  markingItemId.value = item.id;
  try {
    const response = await api.post<MarkResponse>(
      `/api/v1/shared/${token.value}/items/${item.id}/mark`,
      { quantity }
    );

    // Update local state
    item.my_mark_quantity = response.data.my_mark_quantity;
    item.marked_quantity = response.data.total_marked_quantity;
    item.available_quantity = response.data.available_quantity;

    $q.notify({
      type: 'positive',
      message: t('sharing.markedSuccess'),
    });
  } catch (error: any) {
    if (error.response?.status === 400) {
      $q.notify({
        type: 'warning',
        message: t('sharing.quantityExceeds'),
      });
    } else if (error.response?.status === 403) {
      $q.notify({
        type: 'warning',
        message: t('sharing.cannotMarkOwn'),
      });
    } else {
      $q.notify({
        type: 'negative',
        message: t('errors.generic'),
      });
    }
  } finally {
    markingItemId.value = null;
  }
}

async function unmarkItem(item: SharedItem) {
  if (!canMark.value || markingItemId.value) return;

  markingItemId.value = item.id;
  try {
    const response = await api.delete<MarkResponse>(
      `/api/v1/shared/${token.value}/items/${item.id}/mark`
    );

    // Update local state
    item.my_mark_quantity = response.data.my_mark_quantity;
    item.marked_quantity = response.data.total_marked_quantity;
    item.available_quantity = response.data.available_quantity;

    $q.notify({
      type: 'info',
      message: t('sharing.unmarkedSuccess'),
    });
  } catch (error: any) {
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
  } finally {
    markingItemId.value = null;
  }
}

// Handle SSE marks:updated events for real-time sync
async function handleMarksUpdated(event: Event) {
  const customEvent = event as CustomEvent<{ item_id?: string }>;
  const itemId = customEvent.detail?.item_id;

  if (!sharedWishlist.value || !itemId) return;

  // Find the item in our list
  const item = sharedWishlist.value.items.find((i) => i.id === itemId);
  if (!item) return;

  console.log('[SharedWishlist] Updating item due to marks:updated:', itemId);

  try {
    // Fetch fresh data
    const response = await api.get<SharedWishlistResponse>(`/api/v1/shared/${token.value}`);
    const updatedItem = response.data.items.find((i) => i.id === itemId);

    if (updatedItem) {
      // Only update the mark-related fields of this specific item
      item.marked_quantity = updatedItem.marked_quantity;
      item.available_quantity = updatedItem.available_quantity;
      item.my_mark_quantity = updatedItem.my_mark_quantity;
    }
  } catch (error) {
    console.error('[SharedWishlist] Failed to update item:', error);
  }
}

onMounted(() => {
  if (!authStore.isAuthenticated) {
    // Store share token so we can redirect back after login
    LocalStorage.set(PENDING_SHARE_TOKEN_KEY, token.value);
    router.push({ name: 'login', query: { share_token: token.value } });
    return;
  }
  fetchSharedWishlist();

  // Listen for SSE marks:updated events
  window.addEventListener('sse:marks-updated', handleMarksUpdated);
});

onUnmounted(() => {
  window.removeEventListener('sse:marks-updated', handleMarksUpdated);
});
</script>
