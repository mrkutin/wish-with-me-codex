<template>
  <q-page padding>
    <div class="row items-center justify-between q-mb-md">
      <h1 class="text-h5 q-ma-none">{{ $t('wishlists.title') }}</h1>
      <q-btn
        color="primary"
        icon="add"
        :label="$t('wishlists.create')"
        @click="showCreateDialog = true"
      />
    </div>

    <!-- Empty state -->
    <div
      v-if="wishlists.length === 0"
      class="flex flex-center column q-pa-xl"
    >
      <q-icon name="list" size="64px" color="grey-5" />
      <p class="text-h6 text-grey-7 q-mt-md">{{ $t('wishlists.empty') }}</p>
      <p class="text-body2 text-grey-6">{{ $t('wishlists.emptyHint') }}</p>
    </div>

    <!-- Wishlist grid -->
    <div v-else class="row q-col-gutter-md">
      <div
        v-for="wishlist in wishlists"
        :key="wishlist.id"
        class="col-12 col-sm-6 col-md-4"
      >
        <q-card class="wishlist-card cursor-pointer" @click="openWishlist(wishlist.id)">
          <q-card-section>
            <div class="text-h6">{{ wishlist.title }}</div>
            <div v-if="wishlist.description" class="text-body2 text-grey-7">
              {{ wishlist.description }}
            </div>
          </q-card-section>
          <q-card-section>
            <div class="text-caption text-grey">
              {{ $t('wishlists.items', { count: wishlist.item_count }) }}
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Create wishlist dialog -->
    <q-dialog v-model="showCreateDialog">
      <q-card style="min-width: 350px">
        <q-card-section>
          <div class="text-h6">{{ $t('wishlists.create') }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-input
            v-model="newWishlist.title"
            :label="$t('wishlists.name')"
            outlined
            autofocus
          />
          <q-input
            v-model="newWishlist.description"
            :label="$t('wishlists.description')"
            outlined
            type="textarea"
            class="q-mt-md"
          />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat :label="$t('common.cancel')" v-close-popup />
          <q-btn
            color="primary"
            :label="$t('common.create')"
            @click="createWishlist"
            :disable="!newWishlist.title"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/boot/axios';

interface Wishlist {
  id: string;
  title: string;
  description?: string;
  item_count: number;
}

const router = useRouter();
const wishlists = ref<Wishlist[]>([]);
const showCreateDialog = ref(false);
const newWishlist = reactive({
  title: '',
  description: '',
});

async function fetchWishlists() {
  try {
    const response = await api.get<{ items: Wishlist[] }>('/api/v1/wishlists');
    wishlists.value = response.data.items;
  } catch {
    // Handle error
  }
}

async function createWishlist() {
  try {
    const response = await api.post<Wishlist>('/api/v1/wishlists', {
      title: newWishlist.title,
      description: newWishlist.description || undefined,
    });
    wishlists.value.unshift(response.data);
    showCreateDialog.value = false;
    newWishlist.title = '';
    newWishlist.description = '';
  } catch {
    // Handle error
  }
}

function openWishlist(id: string) {
  router.push({ name: 'wishlist-detail', params: { id } });
}

onMounted(fetchWishlists);
</script>
