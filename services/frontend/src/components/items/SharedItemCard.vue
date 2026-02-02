<template>
  <q-card class="item-card">
    <div class="item-card-inner">
      <!-- Image (unified with ItemCard) -->
      <div class="item-image-container">
        <q-img
          v-if="item.image_base64"
          :src="item.image_base64"
          :alt="item.title"
          :ratio="1"
          class="item-image"
        />
        <div
          v-else
          class="item-image-placeholder"
          aria-hidden="true"
        >
          <q-icon name="image" size="32px" />
        </div>
      </div>

      <!-- Content -->
      <div class="item-content">
        <h3 class="item-title">{{ item.title }}</h3>

        <p v-if="item.description" class="item-description">
          {{ truncateText(item.description, 100) }}
        </p>

        <!-- Price and Quantity row -->
        <div class="item-meta">
          <span v-if="item.price_amount" class="item-price">
            {{ formatPrice(item.price_amount, item.price_currency) }}
          </span>
          <span class="item-quantity">
            <q-icon name="inventory_2" size="16px" />
            {{ item.quantity }}
          </span>
        </div>

        <!-- Marking status (simplified - no redundancy) -->
        <div class="item-marks" v-if="item.marked_quantity > 0">
          <!-- User has marked this item -->
          <q-badge
            v-if="item.my_mark_quantity > 0"
            color="positive"
            class="mark-badge"
          >
            <q-icon name="check_circle" size="14px" class="q-mr-xs" />
            {{ $t('sharing.youMarkedThis') }}
          </q-badge>
          <!-- Others have marked (only show if user hasn't marked) -->
          <q-badge
            v-else
            color="positive"
            outline
            class="mark-badge"
          >
            {{ $t('sharing.alreadyMarked', { count: item.marked_quantity }) }}
          </q-badge>
        </div>

        <!-- Action buttons -->
        <div class="item-actions" v-if="canMark">
          <!-- Available to mark (single or multiple) -->
          <template v-if="item.my_mark_quantity === 0 && item.available_quantity > 0">
            <!-- Quantity selector for multiple items -->
            <div v-if="item.available_quantity > 1" class="quantity-row">
              <div class="quantity-selector">
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
            </div>
            <q-btn
              color="primary"
              icon="check"
              :label="item.available_quantity > 1 ? $t('sharing.markQuantity', { count: selectedQuantity }) : $t('sharing.markAsPurchased')"
              :loading="isMarking"
              :disable="isMarking"
              class="action-button"
              @click="handleMark"
            />
          </template>

          <!-- User has marked - show unmark option -->
          <template v-else-if="item.my_mark_quantity > 0">
            <div class="button-row">
              <q-btn
                v-if="item.source_url"
                color="primary"
                icon="shopping_cart"
                :label="$t('sharing.buyItem')"
                :href="item.source_url"
                target="_blank"
                class="action-button"
              />
              <q-btn
                color="grey-7"
                outline
                icon="undo"
                :label="$t('sharing.unmark')"
                :loading="isMarking"
                :disable="isMarking"
                class="action-button"
                @click="$emit('unmark', item)"
              />
            </div>
            <!-- Option to mark more if available -->
            <template v-if="item.available_quantity > 0">
              <div class="quantity-row q-mt-sm">
                <div class="quantity-selector">
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
              </div>
              <q-btn
                color="primary"
                outline
                icon="add"
                :label="$t('sharing.markMore')"
                :loading="isMarking"
                :disable="isMarking"
                class="action-button"
                @click="handleMark"
              />
            </template>
          </template>

          <!-- Fully marked by others -->
          <template v-else>
            <q-btn
              color="grey-5"
              outline
              disable
              icon="check"
              :label="$t('sharing.fullyMarked')"
              class="action-button"
            />
          </template>
        </div>
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

<style scoped lang="sass">
// Unified card styles (same as ItemCard)
.item-card
  overflow: hidden
  background-color: var(--bg-primary)
  border: 1px solid var(--border-subtle)
  border-radius: var(--radius-lg)
  box-shadow: var(--shadow-sm)
  transition: box-shadow var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out)

  &:hover
    box-shadow: var(--shadow-lg)
    border-color: rgba(79, 70, 229, 0.15)

  &:active
    box-shadow: var(--shadow-md)

.item-card-inner
  display: flex
  gap: var(--space-4)
  padding: var(--space-4)

.item-image-container
  flex-shrink: 0
  width: 112px
  height: 112px
  padding: var(--space-2)
  border-radius: var(--radius-md)

.item-image
  width: 100%
  height: 100%
  border-radius: var(--radius-sm)
  object-fit: cover

.item-image-placeholder
  width: 100%
  height: 100%
  display: flex
  align-items: center
  justify-content: center
  background: var(--bg-tertiary)
  border-radius: var(--radius-md)
  color: var(--text-tertiary)

.item-content
  flex: 1
  min-width: 0
  display: flex
  flex-direction: column
  gap: var(--space-2)

.item-title
  font-size: var(--text-body)
  font-weight: 600
  color: var(--text-primary)
  margin: 0
  line-height: 1.4
  overflow: hidden
  text-overflow: ellipsis
  display: -webkit-box
  -webkit-line-clamp: 2
  -webkit-box-orient: vertical

.item-description
  font-size: var(--text-body-sm)
  color: var(--text-secondary)
  margin: 0
  line-height: 1.5
  overflow: hidden
  text-overflow: ellipsis
  display: -webkit-box
  -webkit-line-clamp: 2
  -webkit-box-orient: vertical

.item-meta
  display: flex
  align-items: center
  gap: var(--space-4)
  margin-top: var(--space-1)

.item-price
  font-size: var(--text-body)
  font-weight: 600
  color: var(--primary)
  font-feature-settings: 'tnum' 1

.item-quantity
  display: flex
  align-items: center
  gap: var(--space-1)
  font-size: var(--text-body-sm)
  color: var(--text-secondary)

.item-marks
  margin-top: var(--space-2)

.mark-badge
  font-size: 12px
  font-weight: 500
  padding: 6px 10px
  border-radius: var(--radius-sm)

.item-actions
  display: flex
  flex-direction: column
  gap: var(--space-2)
  margin-top: var(--space-3)

.action-button
  align-self: flex-start
  min-width: 140px

.button-row
  display: flex
  flex-wrap: wrap
  gap: var(--space-2)

.quantity-row
  display: flex
  align-items: center
  gap: var(--space-3)
  flex-wrap: wrap

.quantity-selector
  display: flex
  align-items: center
  border: 1px solid var(--border-default)
  border-radius: var(--radius-sm)
  padding: 2px

  :deep(.q-field__control)
    height: 28px

  :deep(input)
    padding: 0

// Dark mode adjustments
.body--dark
  .item-card
    background-color: var(--bg-secondary)
    border-color: var(--border-default)

    &:hover
      border-color: rgba(99, 102, 241, 0.3)

  .item-image-placeholder
    background: var(--bg-tertiary)

  .quantity-selector
    border-color: var(--border-default)

// Responsive adjustments
@media (max-width: 599px)
  .item-card-inner
    gap: var(--space-3)
    padding: var(--space-3)

  .item-image-container
    width: 80px
    height: 80px

  .action-button
    min-width: 120px
    width: 100%
</style>
