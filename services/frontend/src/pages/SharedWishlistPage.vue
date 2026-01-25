<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { api } from '@/boot/axios';
import { useAuthStore } from '@/stores/auth';
import type { SharedWishlistResponse, SharedItem, MarkResponse } from '@/types/share';

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
      router.push({ name: 'home' });
      return;
    }
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
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

function formatPrice(amount: string | null, currency: string | null): string {
  if (!amount) return '';
  const numAmount = parseFloat(amount);
  if (isNaN(numAmount)) return amount;

  const currencySymbols: Record<string, string> = {
    RUB: '\u20BD',
    USD: '$',
    EUR: '\u20AC',
  };
  const symbol = currency ? currencySymbols[currency] || currency : '';
  return `${numAmount.toLocaleString()} ${symbol}`.trim();
}

onMounted(() => {
  if (!authStore.isAuthenticated) {
    router.push({ name: 'login', query: { share_token: token.value } });
    return;
  }
  fetchSharedWishlist();
});
</script>

<template>
  <q-page padding>
    <!-- Loading state -->
    <div v-if="isLoading" class="flex flex-center q-pa-xl">
      <q-spinner color="primary" size="50px" />
    </div>

    <!-- Content -->
    <template v-else-if="sharedWishlist">
      <!-- Header -->
      <div class="row items-center q-mb-lg">
        <q-avatar size="48px" class="q-mr-md">
          <img :src="sharedWishlist.wishlist.owner.avatar_base64" />
        </q-avatar>
        <div class="col">
          <h5 class="q-ma-none">{{ sharedWishlist.wishlist.title }}</h5>
          <p class="text-grey-7 q-mb-none">
            {{ $t('sharing.sharedBy', { name: sharedWishlist.wishlist.owner.name }) }}
          </p>
        </div>
      </div>

      <!-- Description -->
      <p v-if="sharedWishlist.wishlist.description" class="text-body1 q-mb-lg">
        {{ sharedWishlist.wishlist.description }}
      </p>

      <!-- Items -->
      <div v-if="sharedWishlist.items.length > 0" class="row q-col-gutter-md">
        <div
          v-for="item in sharedWishlist.items"
          :key="item.id"
          class="col-12 col-sm-6 col-md-4"
        >
          <q-card class="shared-item-card">
            <!-- Image -->
            <q-img
              v-if="item.image_base64"
              :src="item.image_base64"
              :ratio="1"
              class="item-image"
            />
            <div v-else class="item-image-placeholder flex flex-center">
              <q-icon name="image" size="64px" color="grey-4" />
            </div>

            <q-card-section>
              <div class="text-h6 ellipsis-2-lines">{{ item.title }}</div>
              <div v-if="item.description" class="text-body2 text-grey-7 q-mt-xs ellipsis-2-lines">
                {{ item.description }}
              </div>
            </q-card-section>

            <q-card-section class="q-pt-none">
              <!-- Price -->
              <div v-if="item.price_amount" class="text-subtitle1 text-primary q-mb-sm">
                {{ formatPrice(item.price_amount, item.price_currency) }}
              </div>

              <!-- Quantity info -->
              <div class="text-body2 text-grey-7 q-mb-md">
                <span v-if="item.quantity > 1">
                  {{ $t('sharing.wantedQuantity', { count: item.quantity }) }}
                </span>
                <span v-if="item.marked_quantity > 0" class="q-ml-sm">
                  <q-badge color="positive" outline>
                    {{ $t('sharing.alreadyMarked', { count: item.marked_quantity }) }}
                  </q-badge>
                </span>
              </div>

              <!-- Mark button -->
              <template v-if="canMark">
                <q-btn
                  v-if="item.my_mark_quantity === 0 && item.available_quantity > 0"
                  color="primary"
                  :label="$t('sharing.markAsPurchased')"
                  :loading="markingItemId === item.id"
                  :disable="markingItemId !== null"
                  @click="markItem(item)"
                  class="full-width"
                />
                <q-btn
                  v-else-if="item.my_mark_quantity > 0"
                  color="positive"
                  outline
                  :loading="markingItemId === item.id"
                  :disable="markingItemId !== null"
                  @click="unmarkItem(item)"
                  class="full-width"
                >
                  <q-icon name="check" class="q-mr-sm" />
                  {{ $t('sharing.youMarked', { count: item.my_mark_quantity }) }}
                </q-btn>
                <q-btn
                  v-else
                  color="grey-5"
                  flat
                  disable
                  :label="$t('sharing.fullyMarked')"
                  class="full-width"
                />
              </template>
            </q-card-section>
          </q-card>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="flex flex-center column q-pa-xl">
        <q-icon name="inbox" size="64px" color="grey-5" />
        <p class="text-h6 text-grey-7 q-mt-md">{{ $t('sharing.emptyWishlist') }}</p>
      </div>
    </template>
  </q-page>
</template>

<style scoped lang="scss">
.shared-item-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.item-image {
  height: 200px;
}

.item-image-placeholder {
  height: 200px;
  background-color: #f5f5f5;
}

.ellipsis-2-lines {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
