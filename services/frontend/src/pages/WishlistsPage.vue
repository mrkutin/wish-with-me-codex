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
        <!-- Loading skeleton -->
        <div v-if="wishlistStore.isLoading && wishlistStore.wishlists.length === 0" class="row q-col-gutter-md">
          <div v-for="n in 3" :key="n" class="col-12 col-sm-6 col-md-4">
            <q-card>
              <q-card-section>
                <q-skeleton type="text" width="60%" class="text-h6" />
                <q-skeleton type="text" width="100%" class="q-mt-sm" />
                <q-skeleton type="text" width="80%" />
              </q-card-section>
              <q-card-section>
                <q-skeleton type="text" width="40%" />
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- Empty state -->
        <div
          v-else-if="wishlistStore.wishlists.length === 0"
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
                    <div class="text-h6">{{ wishlist.name }}</div>
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
                  <div class="text-caption text-grey">
                    {{ formatDate(wishlist.created_at) }}
                  </div>
                </q-card-section>
              </q-card>
            </q-slide-item>
          </div>
        </div>
      </q-tab-panel>

      <!-- Shared With Me Tab -->
      <q-tab-panel name="shared" class="q-pa-none">
        <!-- Loading skeleton -->
        <div v-if="isLoadingBookmarks" class="row q-col-gutter-md">
          <div v-for="n in 3" :key="n" class="col-12 col-sm-6 col-md-4">
            <q-card>
              <q-card-section>
                <q-skeleton type="text" width="60%" class="text-h6" />
                <div class="row items-center q-mt-sm">
                  <q-skeleton type="QAvatar" size="24px" class="q-mr-sm" />
                  <q-skeleton type="text" width="40%" />
                </div>
              </q-card-section>
              <q-card-section>
                <q-skeleton type="text" width="30%" />
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- Empty state -->
        <div
          v-else-if="sharedBookmarks.length === 0"
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
            <q-card class="wishlist-card cursor-pointer" @click="openSharedWishlist(bookmark.share_token)">
              <q-card-section>
                <div class="row items-start justify-between">
                  <div class="text-h6">{{ bookmark.wishlist.title }}</div>
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
          <q-checkbox
            v-model="newWishlist.is_public"
            :label="$t('wishlists.isPublic')"
            class="q-mt-sm"
          />
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
          <q-checkbox
            v-model="editingWishlist.is_public"
            :label="$t('wishlists.isPublic')"
            class="q-mt-sm"
          />
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
import { ref, reactive, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useWishlistStore } from '@/stores/wishlist';
import { api } from '@/boot/axios';
import ShareDialog from '@/components/ShareDialog.vue';
import type { Wishlist } from '@/types/wishlist';
import type { SharedWishlistBookmark, SharedWishlistBookmarkListResponse } from '@/types/share';

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();
const wishlistStore = useWishlistStore();

const activeTab = ref('my');
const showCreateDialog = ref(false);
const showEditDialog = ref(false);
const showShareDialog = ref(false);
const sharingWishlist = ref<Wishlist | null>(null);
const sharedBookmarks = ref<SharedWishlistBookmark[]>([]);
const isLoadingBookmarks = ref(false);

const newWishlist = reactive({
  name: '',
  description: '',
  is_public: false,
});
const editingWishlist = reactive({
  id: '',
  name: '',
  description: '',
  is_public: false,
});

async function fetchBookmarks() {
  isLoadingBookmarks.value = true;
  try {
    const response = await api.get<SharedWishlistBookmarkListResponse>('/api/v1/shared/bookmarks');
    sharedBookmarks.value = response.data.items;
  } catch (error) {
    console.error('Failed to fetch bookmarks:', error);
  } finally {
    isLoadingBookmarks.value = false;
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
    });
    showCreateDialog.value = false;
    newWishlist.name = '';
    newWishlist.description = '';
    newWishlist.is_public = false;
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
  showEditDialog.value = true;
}

async function updateWishlist() {
  try {
    await wishlistStore.updateWishlist(editingWishlist.id, {
      name: editingWishlist.name,
      description: editingWishlist.description || null,
      is_public: editingWishlist.is_public,
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

function openSharedWishlist(token: string) {
  router.push({ name: 'shared-wishlist', params: { token } });
}

async function removeBookmark(bookmark: SharedWishlistBookmark) {
  $q.dialog({
    title: t('wishlists.removeBookmarkConfirm'),
    message: t('wishlists.removeBookmarkMessage', { name: bookmark.wishlist.title }),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await api.delete(`/api/v1/shared/bookmarks/${bookmark.wishlist_id}`);
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

// Sync URL and fetch bookmarks when tab changes
watch(activeTab, (newTab) => {
  // Update URL to reflect current tab
  const newQuery = newTab === 'shared' ? { tab: 'shared' } : {};
  router.replace({ query: newQuery });

  // Fetch bookmarks when switching to shared tab
  if (newTab === 'shared' && sharedBookmarks.value.length === 0) {
    fetchBookmarks();
  }
});

onMounted(() => {
  // Check for tab query parameter
  const tabParam = route.query.tab as string;
  if (tabParam === 'shared') {
    activeTab.value = 'shared';
    fetchBookmarks();
  }
  wishlistStore.fetchWishlists();
});
</script>

<style scoped lang="sass">
.wishlist-card
  transition: transform 0.2s, box-shadow 0.2s
  border: 1px solid var(--border-subtle)

  &:hover
    transform: translateY(-2px)
    box-shadow: var(--shadow-lg)

.dialog-card
  width: 100%
  min-width: 320px
  max-width: 450px

  @media (max-width: 599px)
    min-width: 90vw
    max-width: 95vw

// Dark mode
.body--dark .wishlist-card
  border-color: var(--border-default)
</style>
