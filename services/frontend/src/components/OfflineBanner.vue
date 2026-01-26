<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useSync } from '@/composables/useSync';

const { isOnline, status, syncError } = useSync();

const showBanner = ref(false);
const bannerMessage = ref('');
const bannerIcon = ref('');
const bannerColor = ref('');

// Track previous online state to detect transitions
const wasOnline = ref(true);

// Auto-hide timer
let hideTimer: ReturnType<typeof setTimeout> | null = null;

function clearHideTimer() {
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
}

function showTemporaryBanner(message: string, icon: string, color: string, duration = 3000) {
  clearHideTimer();
  bannerMessage.value = message;
  bannerIcon.value = icon;
  bannerColor.value = color;
  showBanner.value = true;

  if (duration > 0) {
    hideTimer = setTimeout(() => {
      showBanner.value = false;
    }, duration);
  }
}

// Watch online status changes
watch(isOnline, (online, prevOnline) => {
  if (!online && prevOnline) {
    // Just went offline
    showTemporaryBanner('offline.youAreOffline', 'cloud_off', 'warning', 0);
  } else if (online && !prevOnline) {
    // Just came back online
    showTemporaryBanner('offline.backOnline', 'cloud_done', 'positive', 3000);
  }
  wasOnline.value = online;
});

// Watch sync status
watch(status, (newStatus) => {
  if (newStatus === 'syncing') {
    showTemporaryBanner('offline.syncing', 'sync', 'info', 0);
  } else if (newStatus === 'error') {
    showTemporaryBanner('offline.syncError', 'sync_problem', 'negative', 0);
  } else if (newStatus === 'idle' && showBanner.value && bannerIcon.value === 'sync') {
    // Sync completed
    showTemporaryBanner('offline.syncComplete', 'cloud_done', 'positive', 2000);
  }
});

// Watch sync errors
watch(syncError, (error) => {
  if (error) {
    showTemporaryBanner('offline.syncError', 'sync_problem', 'negative', 5000);
  }
});

onMounted(() => {
  wasOnline.value = isOnline.value;
  if (!isOnline.value) {
    showTemporaryBanner('offline.youAreOffline', 'cloud_off', 'warning', 0);
  }
});

onUnmounted(() => {
  clearHideTimer();
});
</script>

<template>
  <transition name="slide-down">
    <q-banner
      v-if="showBanner"
      :class="['offline-banner', `bg-${bannerColor}`]"
      dense
    >
      <template #avatar>
        <q-icon :name="bannerIcon" color="white" />
      </template>
      <span class="text-white">{{ $t(bannerMessage) }}</span>
      <template #action>
        <q-btn
          flat
          dense
          round
          icon="close"
          color="white"
          size="sm"
          @click="showBanner = false"
        />
      </template>
    </q-banner>
  </transition>
</template>

<style scoped lang="sass">
.offline-banner
  position: fixed
  top: 0
  left: 0
  right: 0
  z-index: 9999
  border-radius: 0

.slide-down-enter-active,
.slide-down-leave-active
  transition: transform 0.3s ease, opacity 0.3s ease

.slide-down-enter-from,
.slide-down-leave-to
  transform: translateY(-100%)
  opacity: 0
</style>
