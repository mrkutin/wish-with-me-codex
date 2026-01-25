<template>
  <q-page padding>
    <!-- Loading state -->
    <div v-if="isLoading" class="flex flex-center q-pa-xl">
      <q-spinner color="primary" size="50px" />
    </div>

    <!-- Content -->
    <template v-else-if="sharedWishlist">
      <!-- Header -->
      <div class="row items-center justify-between q-mb-md">
        <div class="col">
          <q-btn flat dense icon="arrow_back" @click="goBack" class="q-mr-md" />
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
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
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

async function fetchSharedWishlist() {
  isLoading.value = true;
  try {
    const response = await api.get<SharedWishlistResponse>(`/api/v1/shared/${token.value}`);
    sharedWishlist.value = response.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      // Redirect to login with share token
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

async function markItem(item: SharedItem) {
  if (!canMark.value || markingItemId.value) return;

  markingItemId.value = item.id;
  try {
    const response = await api.post<MarkResponse>(
      `/api/v1/shared/${token.value}/items/${item.id}/mark`,
      { quantity: 1 }
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

onMounted(() => {
  if (!authStore.isAuthenticated) {
    // Store share token so we can redirect back after login
    LocalStorage.set(PENDING_SHARE_TOKEN_KEY, token.value);
    router.push({ name: 'login', query: { share_token: token.value } });
    return;
  }
  fetchSharedWishlist();
});
</script>
