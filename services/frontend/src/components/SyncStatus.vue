<script setup lang="ts">
import { computed } from 'vue';
import { useSync, type SyncStatus as SyncStatusType } from '@/composables/useSync';

const { status, pendingCount, triggerSync, isOnline } = useSync();

const iconName = computed(() => {
  switch (status.value) {
    case 'offline':
      return 'cloud_off';
    case 'syncing':
      return 'cloud_sync';
    case 'error':
      return 'sync_problem';
    default:
      return pendingCount.value > 0 ? 'cloud_upload' : 'cloud_done';
  }
});

const iconColor = computed(() => {
  switch (status.value) {
    case 'offline':
      return 'grey-6';
    case 'syncing':
      return 'primary';
    case 'error':
      return 'negative';
    default:
      return pendingCount.value > 0 ? 'warning' : 'positive';
  }
});

const tooltipText = computed(() => {
  switch (status.value) {
    case 'offline':
      return 'offline.statusOffline';
    case 'syncing':
      return 'offline.statusSyncing';
    case 'error':
      return 'offline.statusError';
    default:
      return pendingCount.value > 0 ? 'offline.statusPending' : 'offline.statusSynced';
  }
});

const isAnimating = computed(() => status.value === 'syncing');

function handleClick() {
  if (isOnline.value && status.value !== 'syncing') {
    triggerSync();
  }
}
</script>

<template>
  <q-btn
    flat
    round
    dense
    :icon="iconName"
    :color="iconColor"
    :class="{ 'sync-spinning': isAnimating }"
    @click="handleClick"
  >
    <q-badge
      v-if="pendingCount > 0"
      color="warning"
      floating
      rounded
    >
      {{ pendingCount > 99 ? '99+' : pendingCount }}
    </q-badge>

    <q-tooltip>{{ $t(tooltipText) }}</q-tooltip>
  </q-btn>
</template>

<style scoped lang="sass">
.sync-spinning
  animation: spin 1.5s linear infinite

@keyframes spin
  from
    transform: rotate(0deg)
  to
    transform: rotate(360deg)
</style>
