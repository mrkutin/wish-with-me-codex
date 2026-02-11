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
    <template v-else-if="wishlistDoc">
      <!-- Header -->
      <div class="row items-center justify-between q-mb-md">
        <div class="col row items-center no-wrap">
          <q-btn flat dense icon="arrow_back" aria-label="Go back" @click="goBack" class="q-mr-md" />
          <q-icon :name="wishlistDoc.icon || 'card_giftcard'" size="28px" :color="wishlistDoc.icon_color || 'primary'" class="q-mr-sm" />
          <span class="text-h5">{{ wishlistDoc.name }}</span>
        </div>
      </div>

      <!-- Owner info -->
      <div class="row items-center q-mb-md">
        <q-avatar size="40px" class="q-mr-sm">
          <img v-if="ownerDoc?.avatar_base64" :src="ownerDoc.avatar_base64" />
          <q-icon v-else name="person" />
        </q-avatar>
        <div>
          <span class="text-body2 text-grey-7">
            {{ $t('sharing.sharedBy', { name: ownerDoc?.name || 'Unknown' }) }}
          </span>
        </div>
      </div>

      <!-- Description -->
      <p v-if="wishlistDoc.description" class="text-body2 text-grey-7 q-mb-md">
        {{ wishlistDoc.description }}
      </p>

      <!-- Items section -->
      <div class="q-mt-lg">
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
    <div v-else-if="!isLoading" class="flex flex-center column q-pa-xl">
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
import {
  triggerSync,
  subscribeToItems,
  subscribeToMarks,
  getItems,
  getMarks,
  getBookmarks,
  findById,
  upsert,
  createId,
  softDelete,
  onSyncComplete,
} from '@/services/pouchdb';
import type { ItemDoc, MarkDoc, WishlistDoc } from '@/services/pouchdb';
import type { SharedItem } from '@/types/share';

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

interface GrantAccessResponse {
  wishlist_id: string;
  permissions: string[];
}

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();
const authStore = useAuthStore();

const token = computed(() => route.params.token as string | undefined);
const routeWishlistId = computed(() => route.params.wishlistId as string | undefined);

const isLoading = ref(true);
const wishlistId = ref<string | null>(null);
const permissions = ref<string[]>([]);
const markingItemId = ref<string | null>(null);

// PouchDB reactive data
const wishlistDoc = ref<WishlistDoc | null>(null);
const ownerDoc = ref<{ name: string; avatar_base64?: string | null } | null>(null);
const pouchItems = ref<ItemDoc[]>([]);
const pouchMarks = ref<MarkDoc[]>([]);
let unsubscribeItems: (() => void) | null = null;
let unsubscribeMarks: (() => void) | null = null;
let unsubscribeSyncComplete: (() => void) | null = null;

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
        source_url: item.source_url || null,
        price_amount: item.price != null ? String(item.price) : null,
        price_currency: item.currency || null,
        image_base64: item.image_base64 || null,
        quantity: item.quantity || 1,
        marked_quantity: totalMarked,
        my_mark_quantity: myMarkQuantity,
        available_quantity: Math.max(0, (item.quantity || 1) - totalMarked),
      };
    });
});

function goBack() {
  router.push({ name: 'wishlists', query: { tab: 'shared' } });
}

async function handleRefresh(done: () => void) {
  try {
    if (authStore.token) {
      await triggerSync();
    }
    await loadFromPouchDB();
  } finally {
    done();
  }
}

// Initialize from bookmark (already have access, no API call needed)
async function initializeFromBookmark() {
  isLoading.value = true;
  try {
    // Get wishlist ID from route (format: just the UUID, need to add prefix)
    const wlId = routeWishlistId.value!.startsWith('wishlist:')
      ? routeWishlistId.value!
      : `wishlist:${routeWishlistId.value}`;
    wishlistId.value = wlId;

    // Find the bookmark to get permissions
    if (authStore.user) {
      const bookmarks = await getBookmarks(authStore.user.id);
      const bookmark = bookmarks.find(b => !b._deleted && b.wishlist_id === wlId);
      if (bookmark) {
        // Default permissions for bookmarked wishlists - assume mark permission
        // (the share link that created the bookmark determined permissions)
        permissions.value = ['view', 'mark'];
      }
    }

    // Load from PouchDB
    await loadFromPouchDB();

    // Check if user is owner - redirect to normal wishlist view
    if (wishlistDoc.value && authStore.user && wishlistDoc.value.owner_id === authStore.user.id) {
      const id = wishlistId.value.replace('wishlist:', '');
      router.replace({ name: 'wishlist-detail', params: { id } });
      return;
    }

    // Setup subscriptions for real-time updates
    setupSubscriptions();

  } catch (error) {
    console.error('[SharedWishlist] Error loading from bookmark:', error);
  } finally {
    isLoading.value = false;
  }
}

// Grant access via share token API call, then load from PouchDB
async function initializeFromShareToken() {
  isLoading.value = true;
  try {
    // Minimal API call to grant access (adds user to access arrays)
    const response = await api.post<GrantAccessResponse>(`/api/v1/shared/${token.value}/grant-access`);

    const wlId = response.data.wishlist_id;
    wishlistId.value = wlId;
    permissions.value = response.data.permissions;

    // Trigger sync to pull the newly accessible documents (including bookmark with owner info)
    if (authStore.token) {
      await triggerSync();
    }

    // Load from PouchDB (including owner info from bookmark)
    await loadFromPouchDB();

    // Check if user is owner - redirect to normal wishlist view
    // user.id is already in format "user:xxx" from CouchDB
    if (wishlistDoc.value && authStore.user && wishlistDoc.value.owner_id === authStore.user.id) {
      const id = wishlistId.value.replace('wishlist:', '');
      router.replace({ name: 'wishlist-detail', params: { id } });
      return;
    }

    // Redirect from share link to bookmark route
    // This prevents the link from being followed again (which could reset state)
    // and gives a cleaner URL for the user
    const wlIdForRoute = wishlistId.value.replace('wishlist:', '');
    router.replace({ name: 'bookmarked-wishlist', params: { wishlistId: wlIdForRoute } });

    // Setup subscriptions for real-time updates
    setupSubscriptions();

  } catch (error: any) {
    if (error.response?.status === 401) {
      LocalStorage.set(PENDING_SHARE_TOKEN_KEY, token.value!);
      router.push({ name: 'login', query: { share_token: token.value } });
      return;
    }
    if (error.response?.status === 404) {
      $q.notify({
        type: 'negative',
        message: t('sharing.linkNotFound'),
      });
    }
    // Don't show generic error - just show empty state
  } finally {
    isLoading.value = false;
  }
}

async function loadFromPouchDB() {
  if (!wishlistId.value) return;

  // Load wishlist
  const wl = await findById<WishlistDoc>(wishlistId.value);
  wishlistDoc.value = wl;

  // Load owner info from bookmark (cached there for offline-first access)
  // User documents are not synced to other users for privacy
  if (authStore.user) {
    // user.id is already in format "user:xxx" from CouchDB
    const bookmarks = await getBookmarks(authStore.user.id);
    const bookmark = bookmarks.find(b => !b._deleted && b.wishlist_id === wishlistId.value);
    if (bookmark?.owner_name) {
      ownerDoc.value = {
        name: bookmark.owner_name,
        avatar_base64: bookmark.owner_avatar_base64 || null,
      };
    }
  }

  // Load items
  const items = await getItems(wishlistId.value);
  pouchItems.value = items;

  // Load marks for all items
  await loadMarksForItems(items.map(i => i._id));
}

function setupSubscriptions() {
  if (!wishlistId.value) return;

  // Subscribe to item changes
  unsubscribeItems = subscribeToItems(wishlistId.value, (items) => {
    // Sort by created_at descending to match getItems() order
    items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
    pouchItems.value = items;
    // Re-fetch marks when items change
    loadMarksForItems(items.map(i => i._id));
  });

  // Subscribe to sync complete events to refresh data after background sync
  // This ensures deleted items are removed from UI when sync reconciliation runs
  unsubscribeSyncComplete = onSyncComplete(() => loadFromPouchDB());
}

async function loadMarksForItems(itemIds: string[]) {
  if (itemIds.length === 0) {
    pouchMarks.value = [];
    return;
  }

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
  if (!canMark.value || markingItemId.value || !authStore.user || !wishlistDoc.value) return;

  markingItemId.value = item.id;
  try {
    const now = new Date().toISOString();
    const userId = authStore.user.id;

    // Check if user already has a mark for this item
    const existingMark = pouchMarks.value.find(
      m => m.item_id === item.id && m.marked_by === userId && !m._deleted
    );

    if (existingMark) {
      // Update existing mark
      await upsert({
        ...existingMark,
        quantity: existingMark.quantity + quantity,
        updated_at: now,
      });
    } else {
      // Create new mark in PouchDB
      const markId = createId('mark');
      // Get all users who have access to this item (excluding owner for surprise mode)
      const itemDoc = pouchItems.value.find(i => i._id === item.id);
      const accessUsers = itemDoc?.access?.filter(u => u !== wishlistDoc.value?.owner_id) || [userId];

      const newMark = {
        _id: markId,
        type: 'mark',
        item_id: item.id,
        wishlist_id: wishlistId.value!,
        owner_id: wishlistDoc.value.owner_id,
        marked_by: userId,
        quantity,
        access: accessUsers,
        created_at: now,
        updated_at: now,
      } as MarkDoc;
      await upsert(newMark);
    }

    // Trigger sync
    if (authStore.token) {
      await triggerSync();
    }

    $q.notify({
      type: 'positive',
      message: t('sharing.markedSuccess'),
    });
  } catch (error: any) {
    console.error('[SharedWishlist] Mark error:', error);
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
  } finally {
    markingItemId.value = null;
  }
}

async function unmarkItem(item: SharedItem) {
  if (!canMark.value || markingItemId.value || !authStore.user) return;

  markingItemId.value = item.id;
  try {
    const userId = authStore.user.id;

    // Find user's mark for this item
    const existingMark = pouchMarks.value.find(
      m => m.item_id === item.id && m.marked_by === userId && !m._deleted
    );

    if (existingMark) {
      // Soft delete the mark
      await softDelete(existingMark._id);

      // Trigger sync
      if (authStore.token) {
        await triggerSync();
      }

      $q.notify({
        type: 'info',
        message: t('sharing.unmarkedSuccess'),
      });
    }
  } catch (error: any) {
    console.error('[SharedWishlist] Unmark error:', error);
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
  if (unsubscribeSyncComplete) {
    unsubscribeSyncComplete();
    unsubscribeSyncComplete = null;
  }
}

onMounted(async () => {
  if (!authStore.isAuthenticated) {
    if (token.value) {
      LocalStorage.set(PENDING_SHARE_TOKEN_KEY, token.value);
      router.push({ name: 'login', query: { share_token: token.value } });
    } else {
      router.push({ name: 'login' });
    }
    return;
  }

  // Choose initialization method based on route
  if (routeWishlistId.value) {
    // Accessed via bookmark - load directly from PouchDB
    await initializeFromBookmark();
  } else if (token.value) {
    // Accessed via share link - use API to grant access
    await initializeFromShareToken();
  } else {
    // Invalid route
    router.push({ name: 'wishlists' });
  }
});

onUnmounted(() => {
  cleanup();
});
</script>
