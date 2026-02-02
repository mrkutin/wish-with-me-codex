<template>
  <q-page padding>
    <q-pull-to-refresh @refresh="handleRefresh">
    <div class="row items-center justify-between q-mb-md">
      <h1 class="text-h5 q-ma-none">{{ $t('wishlists.title') }}</h1>
      <q-btn
        v-if="activeTab === 'my'"
        color="primary"
        icon="add"
        :label="$t('wishlists.create')"
        @click="showCreateDialog = true"
      />
    </div>

    <!-- Tabs -->
    <q-tabs
      v-model="activeTab"
      dense
      class="text-grey"
      active-color="primary"
      indicator-color="primary"
      align="left"
      narrow-indicator
    >
      <q-tab name="my" :label="$t('wishlists.myWishlists')" />
      <q-tab name="shared" :label="$t('wishlists.sharedWithMe')" />
    </q-tabs>

    <q-separator class="q-mb-md" />

    <!-- My Wishlists Tab -->
    <q-tab-panels v-model="activeTab" animated>
      <q-tab-panel name="my" class="q-pa-none">
        <!-- Empty state -->
        <div
          v-if="wishlistStore.wishlists.length === 0"
          class="flex flex-center column q-pa-xl"
        >
          <q-icon name="list" size="64px" color="grey-5" />
          <p class="text-h6 text-grey-7 q-mt-md">{{ $t('wishlists.empty') }}</p>
          <p class="text-body2 text-grey-6">{{ $t('wishlists.emptyHint') }}</p>
        </div>

        <!-- Wishlist grid -->
        <div v-else class="row q-col-gutter-md">
          <div
            v-for="wishlist in wishlistStore.wishlists"
            :key="wishlist.id"
            class="col-12 col-sm-6 col-md-4"
          >
            <q-slide-item
              @left="({ reset }) => onSwipeLeft(wishlist, reset)"
              @right="({ reset }) => onSwipeRight(wishlist, reset)"
              left-color="primary"
              right-color="negative"
            >
              <template v-slot:left>
                <q-icon name="share" />
              </template>
              <template v-slot:right>
                <q-icon name="delete" />
              </template>
              <q-card class="wishlist-card cursor-pointer" @click="openWishlist(wishlist.id)">
                <q-card-section>
                  <div class="row items-start justify-between">
                    <div class="row items-center no-wrap">
                      <q-icon :name="wishlist.icon || 'card_giftcard'" size="24px" color="primary" class="q-mr-sm" />
                      <div class="text-h6">{{ wishlist.name }}</div>
                    </div>
                    <q-btn
                      flat
                      dense
                      round
                      icon="more_vert"
                      aria-label="Wishlist options"
                      aria-haspopup="menu"
                      @click.stop="showMenu(wishlist)"
                    >
                      <q-menu>
                        <q-list style="min-width: 100px">
                          <q-item clickable v-close-popup @click="shareWishlist(wishlist)">
                            <q-item-section avatar>
                              <q-icon name="share" />
                            </q-item-section>
                            <q-item-section>{{ $t('sharing.share') }}</q-item-section>
                          </q-item>
                          <q-item clickable v-close-popup @click="editWishlist(wishlist)">
                            <q-item-section avatar>
                              <q-icon name="edit" />
                            </q-item-section>
                            <q-item-section>{{ $t('common.edit') }}</q-item-section>
                          </q-item>
                          <q-separator />
                          <q-item clickable v-close-popup @click="confirmDelete(wishlist)">
                            <q-item-section avatar>
                              <q-icon name="delete" color="negative" />
                            </q-item-section>
                            <q-item-section class="text-negative">{{ $t('common.delete') }}</q-item-section>
                          </q-item>
                        </q-list>
                      </q-menu>
                    </q-btn>
                  </div>
                  <div v-if="wishlist.description" class="text-body2 text-grey-7 q-mt-sm">
                    {{ wishlist.description }}
                  </div>
                </q-card-section>
                <q-card-section>
                  <div class="row items-center justify-between">
                    <div class="text-caption text-grey">
                      {{ formatDate(wishlist.created_at) }}
                    </div>
                    <q-badge color="primary" outline>
                      {{ itemCounts[wishlist.id] || 0 }} {{ $t('items.title').toLowerCase() }}
                    </q-badge>
                  </div>
                </q-card-section>
              </q-card>
            </q-slide-item>
          </div>
        </div>
      </q-tab-panel>

      <!-- Shared With Me Tab -->
      <q-tab-panel name="shared" class="q-pa-none">
        <!-- Empty state -->
        <div
          v-if="sharedBookmarks.length === 0"
          class="flex flex-center column q-pa-xl"
        >
          <q-icon name="people" size="64px" color="grey-5" />
          <p class="text-h6 text-grey-7 q-mt-md">{{ $t('wishlists.noSharedWishlists') }}</p>
          <p class="text-body2 text-grey-6">{{ $t('wishlists.noSharedWishlistsHint') }}</p>
        </div>

        <!-- Shared wishlists grid -->
        <div v-else class="row q-col-gutter-md">
          <div
            v-for="bookmark in sharedBookmarks"
            :key="bookmark.id"
            class="col-12 col-sm-6 col-md-4"
          >
            <q-card class="wishlist-card cursor-pointer" @click="openSharedWishlist(bookmark.wishlist_id)">
              <q-card-section>
                <div class="row items-start justify-between">
                  <div class="row items-center no-wrap">
                    <q-icon :name="bookmark.wishlist.icon || 'card_giftcard'" size="24px" color="primary" class="q-mr-md" />
                    <div class="text-h6">{{ bookmark.wishlist.title }}</div>
                  </div>
                  <q-btn
                    flat
                    dense
                    round
                    icon="more_vert"
                    @click.stop
                  >
                    <q-menu>
                      <q-list style="min-width: 100px">
                        <q-item clickable v-close-popup @click="removeBookmark(bookmark)">
                          <q-item-section avatar>
                            <q-icon name="bookmark_remove" color="negative" />
                          </q-item-section>
                          <q-item-section class="text-negative">{{ $t('wishlists.removeBookmark') }}</q-item-section>
                        </q-item>
                      </q-list>
                    </q-menu>
                  </q-btn>
                </div>
                <div v-if="bookmark.wishlist.description" class="text-body2 text-grey-7 q-mt-sm">
                  {{ bookmark.wishlist.description }}
                </div>
              </q-card-section>
              <q-card-section>
                <div class="row items-center q-gutter-sm">
                  <q-avatar size="24px">
                    <img v-if="bookmark.wishlist.owner.avatar_base64" :src="bookmark.wishlist.owner.avatar_base64" />
                    <q-icon v-else name="person" />
                  </q-avatar>
                  <span class="text-caption text-grey">
                    {{ bookmark.wishlist.owner.name }}
                  </span>
                  <q-space />
                  <q-badge color="primary" outline>
                    {{ bookmark.wishlist.item_count }} {{ $t('items.title').toLowerCase() }}
                  </q-badge>
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>
      </q-tab-panel>
    </q-tab-panels>
    </q-pull-to-refresh>

    <!-- Create wishlist dialog -->
    <q-dialog v-model="showCreateDialog">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="text-h6">{{ $t('wishlists.create') }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-input
            v-model="newWishlist.name"
            :label="$t('wishlists.name')"
            outlined
            autofocus
            :rules="[(val) => !!val || $t('validation.required')]"
          />
          <q-input
            v-model="newWishlist.description"
            :label="$t('wishlists.description')"
            outlined
            type="textarea"
            rows="3"
            class="q-mt-md"
          />

          <!-- Icon picker -->
          <div class="q-mt-md">
            <div class="text-caption q-mb-sm">{{ $t('wishlists.chooseIcon') }}</div>
            <div class="row q-gutter-sm">
              <q-btn
                v-for="icon in iconOptions"
                :key="icon.value"
                :icon="icon.value"
                :color="newWishlist.icon === icon.value ? 'primary' : 'grey-5'"
                round
                flat
                size="md"
                @click="newWishlist.icon = icon.value"
              />
            </div>
          </div>

        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat :label="$t('common.cancel')" v-close-popup />
          <q-btn
            color="primary"
            :label="$t('common.create')"
            @click="createWishlist"
            :disable="!newWishlist.name"
            :loading="wishlistStore.isLoading"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Share dialog -->
    <ShareDialog
      v-model="showShareDialog"
      :wishlist-id="sharingWishlist?.id || ''"
      :wishlist-name="sharingWishlist?.name || ''"
    />

    <!-- Edit wishlist dialog -->
    <q-dialog v-model="showEditDialog">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="text-h6">{{ $t('wishlists.edit') }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-input
            v-model="editingWishlist.name"
            :label="$t('wishlists.name')"
            outlined
            :rules="[(val) => !!val || $t('validation.required')]"
          />
          <q-input
            v-model="editingWishlist.description"
            :label="$t('wishlists.description')"
            outlined
            type="textarea"
            rows="3"
            class="q-mt-md"
          />

          <!-- Icon picker -->
          <div class="q-mt-md">
            <div class="text-caption q-mb-sm">{{ $t('wishlists.chooseIcon') }}</div>
            <div class="row q-gutter-sm">
              <q-btn
                v-for="icon in iconOptions"
                :key="icon.value"
                :icon="icon.value"
                :color="editingWishlist.icon === icon.value ? 'primary' : 'grey-5'"
                round
                flat
                size="md"
                @click="editingWishlist.icon = icon.value"
              />
            </div>
          </div>

        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat :label="$t('common.cancel')" v-close-popup />
          <q-btn
            color="primary"
            :label="$t('common.save')"
            @click="updateWishlist"
            :disable="!editingWishlist.name"
            :loading="wishlistStore.isLoading"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useWishlistStore } from '@/stores/wishlist';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/boot/axios';
import { triggerSync, subscribeToBookmarks, getItemCounts } from '@/services/pouchdb';
import ShareDialog from '@/components/ShareDialog.vue';
import type { Wishlist } from '@/types/wishlist';
import type { SharedWishlistBookmark, SharedWishlistBookmarkListResponse } from '@/types/share';

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();
const wishlistStore = useWishlistStore();
const authStore = useAuthStore();

const activeTab = ref('my');
const showCreateDialog = ref(false);
const showEditDialog = ref(false);
const showShareDialog = ref(false);
const sharingWishlist = ref<Wishlist | null>(null);
const sharedBookmarks = ref<SharedWishlistBookmark[]>([]);
const isLoadingBookmarks = ref(false);
const itemCounts = ref<Record<string, number>>({});
let unsubscribeBookmarks: (() => void) | null = null;

const iconOptions = [
  { value: 'card_giftcard', label: 'Gift' },
  { value: 'checklist', label: 'Checklist' },
  { value: 'celebration', label: 'Celebration' },
  { value: 'cake', label: 'Birthday' },
  { value: 'favorite', label: 'Favorite' },
  { value: 'star', label: 'Star' },
  { value: 'redeem', label: 'Redeem' },
  { value: 'shopping_bag', label: 'Shopping' },
  { value: 'home', label: 'Home' },
  { value: 'flight', label: 'Travel' },
  { value: 'child_care', label: 'Kids' },
  { value: 'pets', label: 'Pets' },
];

const newWishlist = reactive({
  name: '',
  description: '',
  is_public: false,
  icon: 'card_giftcard',
});
const editingWishlist = reactive({
  id: '',
  name: '',
  description: '',
  is_public: false,
  icon: 'card_giftcard',
});

async function fetchItemCounts() {
  const wishlistIds = wishlistStore.wishlists.map(w => w.id);
  if (wishlistIds.length > 0) {
    itemCounts.value = await getItemCounts(wishlistIds);
  }
}

async function fetchBookmarks(silent = false) {
  if (!silent) {
    isLoadingBookmarks.value = true;
  }
  try {
    // Trigger sync first to get latest bookmarks from server
    if (authStore.token) {
      await triggerSync(authStore.token);
    }
    // Fetch enriched bookmark list via REST (includes wishlist details, owner, item count)
    const response = await api.get<SharedWishlistBookmarkListResponse>('/api/v1/shared/bookmarks');
    sharedBookmarks.value = response.data.items;
  } catch (error) {
    if (!silent) {
      console.error('Failed to fetch bookmarks:', error);
    }
  } finally {
    if (!silent) {
      isLoadingBookmarks.value = false;
    }
  }
}

function setupBookmarkSubscription() {
  if (unsubscribeBookmarks || !authStore.user) return;

  // Subscribe to bookmark changes via PouchDB
  unsubscribeBookmarks = subscribeToBookmarks(authStore.user.id, () => {
    // When bookmarks change locally, refresh the list from REST API
    // (REST provides enriched data with wishlist details)
    fetchBookmarks(true);
  });
}

function cleanupBookmarkSubscription() {
  if (unsubscribeBookmarks) {
    unsubscribeBookmarks();
    unsubscribeBookmarks = null;
  }
}

async function handleRefresh(done: () => void) {
  try {
    if (activeTab.value === 'my') {
      await wishlistStore.fetchWishlists();
    } else {
      await fetchBookmarks();
    }
  } finally {
    done();
  }
}

async function createWishlist() {
  try {
    await wishlistStore.createWishlist({
      name: newWishlist.name,
      description: newWishlist.description || null,
      is_public: newWishlist.is_public,
      icon: newWishlist.icon,
    });
    showCreateDialog.value = false;
    newWishlist.name = '';
    newWishlist.description = '';
    newWishlist.is_public = false;
    newWishlist.icon = 'card_giftcard';
    $q.notify({
      type: 'positive',
      message: t('wishlists.created'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.createFailed'),
    });
  }
}

function editWishlist(wishlist: Wishlist) {
  editingWishlist.id = wishlist.id;
  editingWishlist.name = wishlist.name;
  editingWishlist.description = wishlist.description || '';
  editingWishlist.is_public = wishlist.is_public;
  editingWishlist.icon = wishlist.icon || 'card_giftcard';
  showEditDialog.value = true;
}

async function updateWishlist() {
  try {
    await wishlistStore.updateWishlist(editingWishlist.id, {
      name: editingWishlist.name,
      description: editingWishlist.description || null,
      is_public: editingWishlist.is_public,
      icon: editingWishlist.icon,
    });
    showEditDialog.value = false;
    $q.notify({
      type: 'positive',
      message: t('wishlists.updated'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.updateFailed'),
    });
  }
}

function confirmDelete(wishlist: Wishlist) {
  $q.dialog({
    title: t('wishlists.deleteConfirm'),
    message: t('wishlists.deleteMessage', { name: wishlist.name }),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await wishlistStore.deleteWishlist(wishlist.id);
      $q.notify({
        type: 'positive',
        message: t('wishlists.deleted'),
      });
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: t('errors.deleteFailed'),
      });
    }
  });
}

function showMenu(wishlist: Wishlist) {
  // Menu handled by q-menu in template
}

function shareWishlist(wishlist: Wishlist) {
  sharingWishlist.value = wishlist;
  showShareDialog.value = true;
}

function onSwipeLeft(wishlist: Wishlist, reset: () => void) {
  reset();
  shareWishlist(wishlist);
}

function onSwipeRight(wishlist: Wishlist, reset: () => void) {
  reset();
  confirmDelete(wishlist);
}

function openWishlist(id: string) {
  router.push({ name: 'wishlist-detail', params: { id } });
}

function openSharedWishlist(wishlistId: string) {
  // Navigate using wishlist ID (bookmark route), not share token
  const id = wishlistId.replace('wishlist:', '');
  router.push({ name: 'bookmarked-wishlist', params: { wishlistId: id } });
}

async function removeBookmark(bookmark: SharedWishlistBookmark) {
  $q.dialog({
    title: t('wishlists.removeBookmarkConfirm'),
    message: t('wishlists.removeBookmarkMessage', { name: bookmark.wishlist.title }),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await api.delete(`/api/v1/shared/${bookmark.share_token}/bookmark`);
      sharedBookmarks.value = sharedBookmarks.value.filter(b => b.id !== bookmark.id);
      $q.notify({
        type: 'info',
        message: t('wishlists.bookmarkRemoved'),
      });
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: t('errors.generic'),
      });
    }
  });
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

// Update item counts when wishlists change
watch(() => wishlistStore.wishlists, () => {
  fetchItemCounts();
}, { deep: true });

// Sync URL and fetch bookmarks when tab changes
watch(activeTab, (newTab) => {
  // Update URL to reflect current tab
  const newQuery = newTab === 'shared' ? { tab: 'shared' } : {};
  router.replace({ query: newQuery });

  // Fetch bookmarks when switching to shared tab
  if (newTab === 'shared') {
    fetchBookmarks();
  }
});

onMounted(async () => {
  // Setup PouchDB subscription for real-time bookmark updates
  setupBookmarkSubscription();

  // Check for tab query parameter
  const tabParam = route.query.tab as string;
  if (tabParam === 'shared') {
    activeTab.value = 'shared';
    fetchBookmarks();
  }
  await wishlistStore.fetchWishlists();
  await fetchItemCounts();
});

onUnmounted(() => {
  cleanupBookmarkSubscription();
});
</script>

<style scoped lang="sass">
.dialog-card
  width: 100%
  min-width: 320px
  max-width: 450px

  @media (max-width: 599px)
    min-width: 90vw
    max-width: 95vw
</style>
