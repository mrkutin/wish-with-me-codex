<template>
  <q-page padding>
    <!-- Loading state -->
    <div v-if="wishlistStore.isLoading && !wishlistStore.currentWishlist" class="flex flex-center q-pa-xl">
      <q-spinner color="primary" size="50px" />
    </div>

    <!-- Wishlist found -->
    <div v-else-if="wishlistStore.currentWishlist">
      <!-- Header -->
      <div class="row items-center justify-between q-mb-md">
        <div class="col">
          <q-btn flat dense icon="arrow_back" @click="goBack" class="q-mr-md" />
          <span class="text-h5">{{ wishlistStore.currentWishlist.name }}</span>
        </div>
        <div>
          <q-btn
            flat
            dense
            round
            icon="more_vert"
          >
            <q-menu>
              <q-list style="min-width: 100px">
                <q-item clickable v-close-popup @click="editWishlist">
                  <q-item-section>{{ $t('common.edit') }}</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="confirmDelete">
                  <q-item-section class="text-negative">{{ $t('common.delete') }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </div>
      </div>

      <!-- Description -->
      <p v-if="wishlistStore.currentWishlist.description" class="text-body2 text-grey-7 q-mb-md">
        {{ wishlistStore.currentWishlist.description }}
      </p>

      <!-- Items section -->
      <div class="q-mt-lg">
        <div class="row items-center justify-between q-mb-md">
          <h2 class="text-h6 q-ma-none">{{ $t('items.title') }}</h2>
          <q-btn
            color="primary"
            icon="add"
            :label="$t('items.add')"
            @click="showAddDialog = true"
          />
        </div>

        <!-- Loading items -->
        <div v-if="itemStore.isLoading && itemStore.items.length === 0" class="flex flex-center q-pa-xl">
          <q-spinner color="primary" size="40px" />
        </div>

        <!-- Empty state -->
        <div
          v-else-if="itemStore.items.length === 0"
          class="flex flex-center column q-pa-xl"
        >
          <q-icon name="inbox" size="64px" color="grey-5" />
          <p class="text-h6 text-grey-7 q-mt-md">{{ $t('items.empty') }}</p>
          <p class="text-body2 text-grey-6">{{ $t('items.emptyHint') }}</p>
        </div>

        <!-- Items list -->
        <div v-else class="q-gutter-md">
          <ItemCard
            v-for="item in itemStore.items"
            :key="item.id"
            :item="item"
            @edit="editItem"
            @delete="confirmDeleteItem"
            @retry="retryResolve"
          />
        </div>
      </div>
    </div>

    <!-- Not found -->
    <div v-else class="flex flex-center column q-pa-xl">
      <q-icon name="error_outline" size="64px" color="grey-5" />
      <p class="text-h6 text-grey-7 q-mt-md">{{ $t('errors.notFound') }}</p>
    </div>

    <!-- Edit wishlist dialog -->
    <q-dialog v-model="showEditDialog">
      <q-card style="min-width: 350px">
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

    <!-- Add item dialog -->
    <AddItemDialog
      v-model="showAddDialog"
      :loading="itemStore.isLoading"
      @submit="createItem"
    />

    <!-- Edit item dialog -->
    <q-dialog v-model="showEditItemDialog">
      <q-card style="min-width: 400px">
        <q-card-section>
          <div class="text-h6">{{ $t('items.edit') }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-input
            v-model="editingItem.title"
            :label="$t('items.itemTitle')"
            outlined
            :rules="[(val) => !!val || $t('validation.required')]"
          />

          <q-input
            v-model="editingItem.description"
            :label="$t('items.description')"
            outlined
            type="textarea"
            rows="3"
            class="q-mt-md"
          />

          <div class="row q-col-gutter-md q-mt-sm">
            <div class="col-8">
              <q-input
                v-model.number="editingItem.price"
                :label="$t('items.price')"
                outlined
                type="number"
                step="0.01"
                min="0"
              >
                <template #prepend>
                  <q-icon name="attach_money" />
                </template>
              </q-input>
            </div>
            <div class="col-4">
              <q-input
                v-model="editingItem.currency"
                :label="$t('items.currency')"
                outlined
                maxlength="3"
              />
            </div>
          </div>

          <q-input
            v-model.number="editingItem.quantity"
            :label="$t('items.quantity')"
            outlined
            type="number"
            min="1"
            class="q-mt-md"
            :rules="[(val) => val >= 1 || $t('validation.minValue', { min: 1 })]"
          />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat :label="$t('common.cancel')" v-close-popup />
          <q-btn
            color="primary"
            :label="$t('common.save')"
            @click="updateItem"
            :disable="!editingItem.title"
            :loading="itemStore.isLoading"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useWishlistStore } from '@/stores/wishlist';
import { useItemStore } from '@/stores/item';
import ItemCard from '@/components/items/ItemCard.vue';
import AddItemDialog from '@/components/items/AddItemDialog.vue';
import type { Item, ItemCreate, ItemUpdate } from '@/types/item';

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();
const wishlistStore = useWishlistStore();
const itemStore = useItemStore();

const showEditDialog = ref(false);
const showAddDialog = ref(false);
const showEditItemDialog = ref(false);
const editingWishlist = reactive({
  id: '',
  name: '',
  description: '',
  is_public: false,
});
const editingItem = reactive<ItemUpdate & { id: string }>({
  id: '',
  title: '',
  description: '',
  price: null,
  currency: 'USD',
  quantity: 1,
});

function goBack() {
  router.push({ name: 'wishlists' });
}

function editWishlist() {
  if (!wishlistStore.currentWishlist) return;

  editingWishlist.id = wishlistStore.currentWishlist.id;
  editingWishlist.name = wishlistStore.currentWishlist.name;
  editingWishlist.description = wishlistStore.currentWishlist.description || '';
  editingWishlist.is_public = wishlistStore.currentWishlist.is_public;
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

function confirmDelete() {
  if (!wishlistStore.currentWishlist) return;

  $q.dialog({
    title: t('wishlists.deleteConfirm'),
    message: t('wishlists.deleteMessage', { name: wishlistStore.currentWishlist.name }),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await wishlistStore.deleteWishlist(wishlistStore.currentWishlist!.id);
      $q.notify({
        type: 'positive',
        message: t('wishlists.deleted'),
      });
      router.push({ name: 'wishlists' });
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: t('errors.deleteFailed'),
      });
    }
  });
}

async function createItem(data: ItemCreate) {
  const wishlistId = route.params.id as string;
  try {
    await itemStore.createItem(wishlistId, data);
    showAddDialog.value = false;
    $q.notify({
      type: 'positive',
      message: t('items.created'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.createFailed'),
    });
  }
}

function editItem(item: Item) {
  editingItem.id = item.id;
  editingItem.title = item.title;
  editingItem.description = item.description || '';
  editingItem.price = item.price;
  editingItem.currency = item.currency || 'USD';
  editingItem.quantity = item.quantity;
  showEditItemDialog.value = true;
}

async function updateItem() {
  const wishlistId = route.params.id as string;
  try {
    const updateData: ItemUpdate = {
      title: editingItem.title,
      description: editingItem.description || null,
      price: editingItem.price,
      currency: editingItem.currency,
      quantity: editingItem.quantity,
    };

    await itemStore.updateItem(wishlistId, editingItem.id, updateData);
    showEditItemDialog.value = false;
    $q.notify({
      type: 'positive',
      message: t('items.updated'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.updateFailed'),
    });
  }
}

function confirmDeleteItem(item: Item) {
  $q.dialog({
    title: t('items.deleteConfirm'),
    message: t('items.deleteMessage', { title: item.title }),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    const wishlistId = route.params.id as string;
    try {
      await itemStore.deleteItem(wishlistId, item.id);
      $q.notify({
        type: 'positive',
        message: t('items.deleted'),
      });
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: t('errors.deleteFailed'),
      });
    }
  });
}

async function retryResolve(item: Item) {
  const wishlistId = route.params.id as string;
  try {
    await itemStore.retryResolve(wishlistId, item.id);
    $q.notify({
      type: 'info',
      message: t('items.resolving'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('items.retryFailed'),
    });
  }
}

onMounted(async () => {
  const id = route.params.id as string;
  if (id) {
    try {
      await Promise.all([
        wishlistStore.fetchWishlist(id),
        itemStore.fetchItems(id),
      ]);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    }
  }
});

onUnmounted(() => {
  itemStore.clearItems();
});
</script>
