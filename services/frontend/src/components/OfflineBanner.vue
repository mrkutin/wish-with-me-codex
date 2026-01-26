<script setup lang="ts">
/**
 * OfflineBanner - Shows only offline/online transition notifications.
 * Sync status is shown via the SyncStatus cloud icon in the navbar.
 */
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useOnline } from '@vueuse/core';

const isOnline = useOnline();

const showBanner = ref(false);
const bannerMessage = ref('');
const bannerIcon = ref('');
const bannerColor = ref('');

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

// Watch online status changes only
watch(isOnline, (online, prevOnline) => {
  if (!online && prevOnline) {
    // Just went offline - show persistent banner
    showTemporaryBanner('offline.youAreOffline', 'cloud_off', 'warning', 0);
  } else if (online && !prevOnline) {
    // Just came back online - brief notification then hide
    showTemporaryBanner('offline.backOnline', 'cloud_done', 'positive', 2000);
  }
});

onMounted(() => {
  // Show offline banner if starting offline
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
