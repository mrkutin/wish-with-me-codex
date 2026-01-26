<template>
  <q-card class="item-card">
    <div class="row no-wrap">
      <!-- Image -->
      <div class="col-auto">
        <q-img
          v-if="item.image_base64"
          :src="item.image_base64"
          :alt="item.title"
          :ratio="1"
          width="100px"
          class="rounded-borders"
        />
        <div
          v-else
          class="flex flex-center bg-grey-3 rounded-borders"
          style="width: 100px; height: 100px"
          aria-hidden="true"
        >
          <q-icon name="image" size="40px" color="grey-6" />
        </div>
      </div>

      <!-- Content -->
      <div class="col q-pl-md">
        <q-card-section class="q-pa-sm">
          <div class="row items-start justify-between">
            <div class="col">
              <div class="text-subtitle1">{{ item.title }}</div>
              <div v-if="item.description" class="text-body2 text-grey-7 q-mt-xs">
                {{ truncateText(item.description, 100) }}
              </div>
            </div>
            <q-btn
              flat
              dense
              round
              icon="more_vert"
              size="sm"
              aria-label="Item options"
              aria-haspopup="menu"
              @click.stop
            >
              <q-menu>
                <q-list style="min-width: 100px">
                  <q-item clickable v-close-popup @click="$emit('edit', item)">
                    <q-item-section>{{ $t('common.edit') }}</q-item-section>
                  </q-item>
                  <q-item clickable v-close-popup @click="$emit('delete', item)">
                    <q-item-section class="text-negative">{{ $t('common.delete') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </div>

          <!-- Price and Quantity -->
          <div class="row items-center q-mt-sm q-gutter-md">
            <div v-if="item.price !== null" class="text-h6 text-primary">
              {{ formatPrice(item.price, item.currency) }}
            </div>
            <div class="text-body2 text-grey-7">
              {{ $t('items.quantity') }}: {{ item.quantity }}
            </div>
          </div>

          <!-- Status Badge -->
          <div class="q-mt-sm">
            <q-badge
              v-if="item.status === 'pending' || item.status === 'resolving'"
              color="info"
              class="q-px-sm"
            >
              <q-spinner-dots size="xs" class="q-mr-xs" />
              {{ $t('items.resolving') }}
            </q-badge>
            <q-badge
              v-else-if="item.status === 'failed'"
              color="negative"
              class="q-px-sm"
            >
              <q-icon name="error" size="xs" class="q-mr-xs" />
              {{ $t('items.resolveFailed') }}
            </q-badge>
            <q-badge
              v-else-if="item.status === 'resolved'"
              color="positive"
              class="q-px-sm"
            >
              <q-icon name="check_circle" size="xs" class="q-mr-xs" />
              {{ $t('items.resolved') }}
            </q-badge>
          </div>

          <!-- Retry button for failed items -->
          <div v-if="item.status === 'failed'" class="q-mt-sm">
            <q-btn
              flat
              dense
              size="sm"
              color="primary"
              icon="refresh"
              :label="$t('items.retry')"
              @click="$emit('retry', item)"
            />
          </div>

          <!-- Source URL link -->
          <div v-if="item.source_url" class="q-mt-sm">
            <a
              :href="item.source_url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-caption text-grey-7"
              @click.stop
            >
              <q-icon name="launch" size="xs" class="q-mr-xs" />
              {{ $t('items.viewSource') }}
            </a>
          </div>
        </q-card-section>
      </div>
    </div>
  </q-card>
</template>

<script setup lang="ts">
import type { Item } from '@/types/item';

interface Props {
  item: Item;
}

defineProps<Props>();

defineEmits<{
  edit: [item: Item];
  delete: [item: Item];
  retry: [item: Item];
}>();

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

function formatPrice(price: number, currency: string | null): string {
  const currencyCode = currency || 'USD';
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currencyCode,
  }).format(price);
}
</script>

<style scoped>
.item-card {
  transition: transform 0.2s;
}

.item-card:hover {
  transform: translateY(-2px);
}
</style>
