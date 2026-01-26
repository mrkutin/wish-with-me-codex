<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { LocalStorage } from 'quasar';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISSED_KEY = 'pwa-install-dismissed';
const DISMISS_DURATION = 7 * 24 * 60 * 60 * 1000; // 7 days

const showPrompt = ref(false);
const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null);
const isInstalling = ref(false);

function shouldShowPrompt(): boolean {
  // Check if already installed (standalone mode)
  if (window.matchMedia('(display-mode: standalone)').matches) {
    return false;
  }

  // Check if user dismissed recently
  const dismissedAt = LocalStorage.getItem<number>(DISMISSED_KEY);
  if (dismissedAt && Date.now() - dismissedAt < DISMISS_DURATION) {
    return false;
  }

  return true;
}

function handleBeforeInstallPrompt(event: Event) {
  // Prevent default mini-infobar
  event.preventDefault();

  // Store the event for later use
  deferredPrompt.value = event as BeforeInstallPromptEvent;

  // Show our custom prompt if appropriate
  if (shouldShowPrompt()) {
    showPrompt.value = true;
  }
}

async function installApp() {
  if (!deferredPrompt.value) return;

  isInstalling.value = true;

  try {
    // Show the browser install prompt
    await deferredPrompt.value.prompt();

    // Wait for user response
    const { outcome } = await deferredPrompt.value.userChoice;

    if (outcome === 'accepted') {
      showPrompt.value = false;
    }
  } finally {
    isInstalling.value = false;
    deferredPrompt.value = null;
  }
}

function dismissPrompt() {
  showPrompt.value = false;
  LocalStorage.set(DISMISSED_KEY, Date.now());
}

onMounted(() => {
  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

  // Handle app installed event
  window.addEventListener('appinstalled', () => {
    showPrompt.value = false;
    deferredPrompt.value = null;
  });
});

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
});
</script>

<template>
  <q-dialog v-model="showPrompt" position="bottom" seamless>
    <q-card class="install-prompt-card">
      <q-card-section class="row items-center no-wrap">
        <q-avatar size="48px" color="primary" text-color="white" icon="get_app" />
        <div class="q-ml-md">
          <div class="text-weight-bold">{{ $t('pwa.installTitle') }}</div>
          <div class="text-caption text-grey-6">{{ $t('pwa.installDescription') }}</div>
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn
          flat
          :label="$t('common.notNow')"
          color="grey"
          @click="dismissPrompt"
        />
        <q-btn
          unelevated
          :label="$t('pwa.install')"
          color="primary"
          :loading="isInstalling"
          @click="installApp"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped lang="sass">
.install-prompt-card
  width: 100%
  max-width: 400px
  margin: 16px
  border-radius: 12px
</style>
