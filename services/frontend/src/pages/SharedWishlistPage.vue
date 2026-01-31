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
    <template v-else-if="wishlistInfo">
      <!-- Header -->
      <div class="row items-center justify-between q-mb-md">
        <div class="col row items-center no-wrap">
          <q-btn flat dense icon="arrow_back" aria-label="Go back" @click="goBack" class="q-mr-md" />
          <q-icon :name="wishlistInfo.icon || 'card_giftcard'" size="28px" color="primary" class="q-mr-sm" />
          <span class="text-h5">{{ wishlistInfo.title }}</span>
        </div>
      </div>

      <!-- Owner info -->
      <div class="row items-center q-mb-md">
        <q-avatar size="40px" class="q-mr-sm">
          <img v-if="wishlistInfo.owner.avatar_base64" :src="wishlistInfo.owner.avatar_base64" />
          <q-icon v-else name="person" />
        </q-avatar>
        <div>
          <span class="text-body2 text-grey-7">
            {{ $t('sharing.sharedBy', { name: wishlistInfo.owner.name }) }}
          </span>
        </div>
      </div>

      <!-- Description -->
      <p v-if="wishlistInfo.description" class="text-body2 text-grey-7 q-mb-md">
        {{ wishlistInfo.description }}
      </p>

      <!-- Items section -->
      <div class="q-mt-lg">
        <div class="row items-center justify-between q-mb-md">
          <h2 class="text-h6 q-ma-none">{{ $t('items.title') }}</h2>
          <q-badge color="primary" outline>
            {{ displayItems.length }} {{ $t('items.title').toLowerCase() }}
          </q-badge>
        </div>

        <!-- Empty state -->
        <div
          v-if="displayItems.length === 0"
          class="flex flex-center column q-pa-xl"
        >
          <q-icon name="inbox" size="64px" color="grey-5" />
          <p class="text-h6 text-grey-7 q-mt-md">{{ $t('sharing.emptyWishlist') }}</p>
        </div>

        <!-- Items list -->
        <div v-else class="q-gutter-md">
          <SharedItemCard
            v-for="item in displayItems"
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar, LocalStorage } from 'quasar';
import { useI18n } from 'vue-i18n';
import { api } from '@/boot/axios';
import { useAuthStore } from '@/stores/auth';
import SharedItemCard from '@/components/items/SharedItemCard.vue';
import {
  triggerSync,
  subscribeToItems,
  subscribeToMarks,
  getItems,
  getMarks,
  extractId,
} from '@/services/pouchdb';
import type { ItemDoc, MarkDoc } from '@/services/pouchdb';
import type { SharedWishlistResponse, SharedItem, MarkResponse } from '@/types/share';

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();
const authStore = useAuthStore();

const token = computed(() => route.params.token as string);

const isLoading = ref(true);
const wishlistInfo = ref<SharedWishlistResponse['wishlist'] | null>(null);
const permissions = ref<string[]>([]);
const markingItemId = ref<string | null>(null);

// PouchDB reactive data
const pouchItems = ref<ItemDoc[]>([]);
const pouchMarks = ref<MarkDoc[]>([]);
let unsubscribeItems: (() => void) | null = null;
let unsubscribeMarks: (() => void) | null = null;

const canMark = computed(() => permissions.value.includes('mark'));

// Compute display items from PouchDB data with mark info
const displayItems = computed<SharedItem[]>(() => {
  const userId = authStore.user?.id;

  return pouchItems.value
    .filter(item => !item._deleted)
    .map(item => {
      const itemId = item._id;
      const itemMarks = pouchMarks.value.filter(m => m.item_id === itemId && !m._deleted);

      const totalMarked = itemMarks.reduce((sum, m) => sum + (m.quantity || 1), 0);
      const myMark = itemMarks.find(m => m.marked_by === userId);
      const myMarkQuantity = myMark?.quantity || 0;

      return {
        id: itemId,
        title: item.title,
        description: item.description || null,
        url: item.url || null,
        price_amount: item.price_amount || null,
        price_currency: item.price_currency || null,
        image_base64: item.image_base64 || null,
        quantity: item.quantity || 1,
        marked_quantity: totalMarked,
        my_mark_quantity: myMarkQuantity,
        available_quantity: Math.max(0, (item.quantity || 1) - totalMarked),
      };
    })
    .sort((a, b) => {
      // Sort by available quantity (available first), then by title
      if (a.available_quantity > 0 && b.available_quantity === 0) return -1;
      if (a.available_quantity === 0 && b.available_quantity > 0) return 1;
      return a.title.localeCompare(b.title);
    });
});

function goBack() {
  router.push({ name: 'wishlists', query: { tab: 'shared' } });
}

async function handleRefresh(done: () => void) {
  try {
    // Trigger sync to get latest data
    if (authStore.token) {
      await triggerSync(authStore.token);
    }
    await loadFromPouchDB();
  } finally {
    done();
  }
}

// Load initial data and grant access
async function initializeSharedWishlist() {
  isLoading.value = true;
  try {
    // This REST call grants access (adds user to access arrays) and returns initial data
    const response = await api.get<SharedWishlistResponse>(`/api/v1/shared/${token.value}`);

    // If current user is the owner, redirect to normal wishlist view
    if (authStore.user && response.data.wishlist.owner.id === authStore.user.id) {
      router.replace({ name: 'wishlist-detail', params: { id: response.data.wishlist.id } });
      return;
    }

    wishlistInfo.value = response.data.wishlist;
    permissions.value = response.data.permissions;

    // Trigger sync to pull the newly accessible documents
    if (authStore.token) {
      await triggerSync(authStore.token);
    }

    // Load from PouchDB and subscribe to changes
    await loadFromPouchDB();
    setupSubscriptions();

  } catch (error: any) {
    if (error.response?.status === 401) {
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

async function loadFromPouchDB() {
  if (!wishlistInfo.value) return;

  const wishlistId = `wishlist:${wishlistInfo.value.id}`;

  // Load items
  const items = await getItems(wishlistId);
  pouchItems.value = items;

  // Load marks for all items
  const itemIds = items.map(i => i._id);
  if (itemIds.length > 0) {
    const allMarks: MarkDoc[] = [];
    for (const itemId of itemIds) {
      const marks = await getMarks(itemId);
      allMarks.push(...marks);
    }
    pouchMarks.value = allMarks;
  }
}

function setupSubscriptions() {
  if (!wishlistInfo.value) return;

  const wishlistId = `wishlist:${wishlistInfo.value.id}`;

  // Subscribe to item changes
  unsubscribeItems = subscribeToItems(wishlistId, (items) => {
    pouchItems.value = items;
    // Re-fetch marks when items change (new items may have marks)
    loadMarksForItems(items.map(i => i._id));
  });

  // Subscribe to mark changes for current items
  const itemIds = pouchItems.value.map(i => i._id);
  if (itemIds.length > 0) {
    unsubscribeMarks = subscribeToMarks(itemIds, (marks) => {
      pouchMarks.value = marks;
    });
  }
}

async function loadMarksForItems(itemIds: string[]) {
  if (itemIds.length === 0) return;

  const allMarks: MarkDoc[] = [];
  for (const itemId of itemIds) {
    const marks = await getMarks(itemId);
    allMarks.push(...marks);
  }
  pouchMarks.value = allMarks;

  // Update marks subscription with new item IDs
  if (unsubscribeMarks) {
    unsubscribeMarks();
  }
  unsubscribeMarks = subscribeToMarks(itemIds, (marks) => {
    pouchMarks.value = marks;
  });
}

async function markItem(item: SharedItem, quantity: number = 1) {
  if (!canMark.value || markingItemId.value) return;

  markingItemId.value = item.id;
  try {
    await api.post<MarkResponse>(
      `/api/v1/shared/${token.value}/items/${item.id}/mark`,
      { quantity }
    );

    // Trigger sync to get the new mark
    if (authStore.token) {
      await triggerSync(authStore.token);
    }

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
    await api.delete<MarkResponse>(
      `/api/v1/shared/${token.value}/items/${item.id}/mark`
    );

    // Trigger sync to remove the mark
    if (authStore.token) {
      await triggerSync(authStore.token);
    }

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

function cleanup() {
  if (unsubscribeItems) {
    unsubscribeItems();
    unsubscribeItems = null;
  }
  if (unsubscribeMarks) {
    unsubscribeMarks();
    unsubscribeMarks = null;
  }
}

onMounted(async () => {
  if (!authStore.isAuthenticated) {
    LocalStorage.set(PENDING_SHARE_TOKEN_KEY, token.value);
    router.push({ name: 'login', query: { share_token: token.value } });
    return;
  }
  await initializeSharedWishlist();
});

onUnmounted(() => {
  cleanup();
});
</script>
