<template>
  <q-card class="item-card">
    <div class="item-card-inner">
      <!-- Image -->
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
        <div class="item-header">
          <h3 class="item-title">{{ item.title }}</h3>
          <q-btn
            flat
            dense
            round
            icon="more_vert"
            size="sm"
            class="item-menu-btn"
            aria-label="Item options"
            aria-haspopup="menu"
            @click.stop
          >
            <q-menu anchor="top right" self="top right">
              <q-list class="item-menu">
                <q-item clickable v-close-popup @click="$emit('edit', item)">
                  <q-item-section avatar>
                    <q-icon name="edit" size="20px" />
                  </q-item-section>
                  <q-item-section>{{ $t('common.edit') }}</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="$emit('delete', item)" class="text-negative">
                  <q-item-section avatar>
                    <q-icon name="delete" size="20px" />
                  </q-item-section>
                  <q-item-section>{{ $t('common.delete') }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </div>

        <p v-if="item.description" class="item-description">
          {{ truncateText(item.description, 100) }}
        </p>

        <!-- Price and Quantity row -->
        <div class="item-meta">
          <span v-if="item.price !== null" class="item-price">
            {{ formatPrice(item.price, item.currency) }}
          </span>
          <span class="item-quantity">
            <q-icon name="inventory_2" size="16px" />
            {{ item.quantity }}
          </span>
        </div>

        <!-- Status Badge -->
        <div class="item-status">
          <q-badge
            v-if="item.status === 'pending' || item.status === 'resolving'"
            color="info"
            class="status-badge"
          >
            <q-spinner-dots size="12px" class="q-mr-xs" />
            {{ $t('items.resolving') }}
          </q-badge>
          <q-badge
            v-else-if="item.status === 'failed'"
            color="negative"
            class="status-badge"
          >
            <q-icon name="error" size="14px" class="q-mr-xs" />
            {{ $t('items.resolveFailed') }}
          </q-badge>
          <q-badge
            v-else-if="item.status === 'resolved'"
            color="positive"
            class="status-badge"
          >
            <q-icon name="check_circle" size="14px" class="q-mr-xs" />
            {{ $t('items.resolved') }}
          </q-badge>
        </div>

        <!-- Retry button for failed items -->
        <q-btn
          v-if="item.status === 'failed'"
          flat
          dense
          size="sm"
          color="primary"
          icon="refresh"
          :label="$t('items.retry')"
          class="retry-btn"
          @click="$emit('retry', item)"
        />

        <!-- Source URL link -->
        <a
          v-if="item.source_url"
          :href="item.source_url"
          target="_blank"
          rel="noopener noreferrer"
          class="item-source-link"
          @click.stop
        >
          <q-icon name="launch" size="14px" />
          <span>{{ $t('items.viewSource') }}</span>
        </a>
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

<style scoped lang="sass">
.item-card
  overflow: hidden
  border: 1px solid var(--border-subtle)
  transition: transform var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out)

  &:hover
    transform: translateY(-2px)
    box-shadow: var(--shadow-lg)

  &:active
    transform: translateY(0)

.item-card-inner
  display: flex
  gap: var(--space-4)
  padding: var(--space-4)

.item-image-container
  flex-shrink: 0
  width: 96px
  height: 96px

.item-image
  width: 100%
  height: 100%
  border-radius: var(--radius-md)
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

.item-header
  display: flex
  align-items: flex-start
  justify-content: space-between
  gap: var(--space-2)

.item-title
  font-size: var(--text-body)
  font-weight: 600
  color: var(--text-primary)
  margin: 0
  line-height: 1.4
  // Text overflow handling
  overflow: hidden
  text-overflow: ellipsis
  display: -webkit-box
  -webkit-line-clamp: 2
  -webkit-box-orient: vertical

.item-menu-btn
  flex-shrink: 0
  margin: -4px -4px 0 0
  color: var(--text-tertiary)

  &:hover
    color: var(--text-secondary)

.item-menu
  min-width: 140px

  .q-item
    min-height: 44px
    padding: var(--space-2) var(--space-4)

.item-description
  font-size: var(--text-body-sm)
  color: var(--text-secondary)
  margin: 0
  line-height: 1.5
  // Text overflow
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

.item-status
  margin-top: var(--space-1)

.status-badge
  font-size: 11px
  font-weight: 500
  padding: 4px 8px
  border-radius: var(--radius-sm)

.retry-btn
  align-self: flex-start
  margin-top: var(--space-1)

.item-source-link
  display: inline-flex
  align-items: center
  gap: var(--space-1)
  font-size: var(--text-caption)
  color: var(--text-tertiary)
  text-decoration: none
  transition: color var(--duration-fast)
  margin-top: var(--space-1)

  &:hover
    color: var(--primary)

// Dark mode adjustments
.body--dark
  .item-card
    border-color: var(--border-default)

  .item-image-placeholder
    background: var(--bg-tertiary)

// Responsive adjustments
@media (max-width: 599px)
  .item-card-inner
    gap: var(--space-3)
    padding: var(--space-3)

  .item-image-container
    width: 80px
    height: 80px
</style>
