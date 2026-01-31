<template>
  <q-card class="item-card">
    <div class="row no-wrap">
      <!-- Image -->
      <div class="col-auto q-pa-sm">
        <div class="image-container">
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
            <!-- Simple mark button for single available quantity -->
            <template v-if="item.my_mark_quantity === 0 && item.available_quantity === 1">
              <q-btn
                color="primary"
                :label="$t('sharing.markAsPurchased')"
                :loading="isMarking"
                :disable="isMarking"
                @click="handleMark"
                size="sm"
              />
            </template>

            <!-- Quantity selector for multiple available items -->
            <template v-else-if="item.my_mark_quantity === 0 && item.available_quantity > 1">
              <div class="row items-center q-gutter-sm">
                <div class="quantity-selector row items-center no-wrap">
                  <q-btn
                    round
                    dense
                    flat
                    icon="remove"
                    size="sm"
                    :disable="selectedQuantity <= 1 || isMarking"
                    @click="decrementQuantity"
                  />
                  <q-input
                    v-model.number="selectedQuantity"
                    type="number"
                    dense
                    borderless
                    input-class="text-center"
                    style="width: 50px"
                    :min="1"
                    :max="item.available_quantity"
                    :disable="isMarking"
                    @update:model-value="clampQuantity"
                  />
                  <q-btn
                    round
                    dense
                    flat
                    icon="add"
                    size="sm"
                    :disable="selectedQuantity >= item.available_quantity || isMarking"
                    @click="incrementQuantity"
                  />
                </div>
                <span class="text-caption text-grey-7">
                  {{ $t('sharing.ofAvailable', { available: item.available_quantity }) }}
                </span>
                <q-btn
                  color="primary"
                  :label="$t('sharing.markQuantity', { count: selectedQuantity })"
                  :loading="isMarking"
                  :disable="isMarking"
                  @click="handleMark"
                  size="sm"
                />
              </div>
            </template>

            <!-- Already marked - show unmark button -->
            <template v-else-if="item.my_mark_quantity > 0">
              <q-btn
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
              <!-- Option to mark more if available -->
              <template v-if="item.available_quantity > 0">
                <div class="row items-center q-gutter-sm q-mt-sm">
                  <div class="quantity-selector row items-center no-wrap">
                    <q-btn
                      round
                      dense
                      flat
                      icon="remove"
                      size="sm"
                      :disable="selectedQuantity <= 1 || isMarking"
                      @click="decrementQuantity"
                    />
                    <q-input
                      v-model.number="selectedQuantity"
                      type="number"
                      dense
                      borderless
                      input-class="text-center"
                      style="width: 50px"
                      :min="1"
                      :max="item.available_quantity"
                      :disable="isMarking"
                      @update:model-value="clampQuantity"
                    />
                    <q-btn
                      round
                      dense
                      flat
                      icon="add"
                      size="sm"
                      :disable="selectedQuantity >= item.available_quantity || isMarking"
                      @click="incrementQuantity"
                    />
                  </div>
                  <span class="text-caption text-grey-7">
                    {{ $t('sharing.ofAvailable', { available: item.available_quantity }) }}
                  </span>
                  <q-btn
                    color="primary"
                    outline
                    :label="$t('sharing.markMore')"
                    :loading="isMarking"
                    :disable="isMarking"
                    @click="handleMark"
                    size="sm"
                  />
                </div>
              </template>
            </template>

            <!-- Fully marked -->
            <template v-else>
              <q-btn
                color="grey-5"
                flat
                disable
                :label="$t('sharing.fullyMarked')"
                size="sm"
              />
            </template>
          </div>
        </q-card-section>
      </div>
    </div>
  </q-card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import type { SharedItem } from '@/types/share';

interface Props {
  item: SharedItem;
  canMark: boolean;
  isMarking: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  mark: [item: SharedItem, quantity: number];
  unmark: [item: SharedItem];
}>();

const selectedQuantity = ref(1);

// Reset selected quantity when item changes or after marking
watch(() => props.item.available_quantity, () => {
  selectedQuantity.value = 1;
});

function incrementQuantity() {
  if (selectedQuantity.value < props.item.available_quantity) {
    selectedQuantity.value++;
  }
}

function decrementQuantity() {
  if (selectedQuantity.value > 1) {
    selectedQuantity.value--;
  }
}

function clampQuantity(value: number | null) {
  if (value === null || isNaN(value) || value < 1) {
    selectedQuantity.value = 1;
  } else if (value > props.item.available_quantity) {
    selectedQuantity.value = props.item.available_quantity;
  } else {
    selectedQuantity.value = Math.floor(value);
  }
}

function handleMark() {
  emit('mark', props.item, selectedQuantity.value);
  selectedQuantity.value = 1; // Reset after marking
}

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
  transition: box-shadow 0.15s ease-out, border-color 0.15s ease-out;
  border: 1px solid transparent;
}

.item-card:hover {
  box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05);
  border-color: rgba(79, 70, 229, 0.15);
}

.image-container {
  padding: 4px;
  background: #f5f5f5;
  border-radius: 8px;
}

.quantity-selector {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 2px;
}

.quantity-selector :deep(.q-field__control) {
  height: 28px;
}

.quantity-selector :deep(input) {
  padding: 0;
}
</style>
