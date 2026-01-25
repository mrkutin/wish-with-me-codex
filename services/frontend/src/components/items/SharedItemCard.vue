<template>
  <q-card class="item-card">
    <div class="row no-wrap">
      <!-- Image -->
      <div class="col-auto">
        <q-img
          v-if="item.image_base64"
          :src="item.image_base64"
          :ratio="1"
          width="100px"
          class="rounded-borders"
        />
        <div
          v-else
          class="flex flex-center bg-grey-3 rounded-borders"
          style="width: 100px; height: 100px"
        >
          <q-icon name="image" size="40px" color="grey-6" />
        </div>
      </div>

      <!-- Content -->
      <div class="col q-pl-md">
        <q-card-section class="q-pa-sm">
          <div class="text-subtitle1">{{ item.title }}</div>
          <div v-if="item.description" class="text-body2 text-grey-7 q-mt-xs">
            {{ truncateText(item.description, 100) }}
          </div>

          <!-- Price and Quantity -->
          <div class="row items-center q-mt-sm q-gutter-md">
            <div v-if="item.price_amount" class="text-h6 text-primary">
              {{ formatPrice(item.price_amount, item.price_currency) }}
            </div>
            <div class="text-body2 text-grey-7">
              {{ $t('items.quantity') }}: {{ item.quantity }}
            </div>
          </div>

          <!-- Marked info -->
          <div class="q-mt-sm">
            <q-badge
              v-if="item.marked_quantity > 0"
              color="positive"
              outline
              class="q-mr-sm"
            >
              {{ $t('sharing.alreadyMarked', { count: item.marked_quantity }) }}
            </q-badge>
            <q-badge
              v-if="item.my_mark_quantity > 0"
              color="primary"
            >
              {{ $t('sharing.yourMark', { count: item.my_mark_quantity }) }}
            </q-badge>
          </div>

          <!-- Mark/Unmark buttons -->
          <div class="q-mt-md" v-if="canMark">
            <q-btn
              v-if="item.my_mark_quantity === 0 && item.available_quantity > 0"
              color="primary"
              :label="$t('sharing.markAsPurchased')"
              :loading="isMarking"
              :disable="isMarking"
              @click="$emit('mark', item)"
              size="sm"
            />
            <q-btn
              v-else-if="item.my_mark_quantity > 0"
              color="positive"
              outline
              :loading="isMarking"
              :disable="isMarking"
              @click="$emit('unmark', item)"
              size="sm"
            >
              <q-icon name="check" class="q-mr-xs" size="xs" />
              {{ $t('sharing.unmark') }}
            </q-btn>
            <q-btn
              v-else
              color="grey-5"
              flat
              disable
              :label="$t('sharing.fullyMarked')"
              size="sm"
            />
          </div>
        </q-card-section>
      </div>
    </div>
  </q-card>
</template>

<script setup lang="ts">
import type { SharedItem } from '@/types/share';

interface Props {
  item: SharedItem;
  canMark: boolean;
  isMarking: boolean;
}

defineProps<Props>();

defineEmits<{
  mark: [item: SharedItem];
  unmark: [item: SharedItem];
}>();

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

function formatPrice(price: string | null, currency: string | null): string {
  if (!price) return '';
  const numPrice = parseFloat(price);
  if (isNaN(numPrice)) return price;

  const currencyCode = currency || 'USD';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currencyCode,
    }).format(numPrice);
  } catch {
    return `${numPrice} ${currencyCode}`;
  }
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
