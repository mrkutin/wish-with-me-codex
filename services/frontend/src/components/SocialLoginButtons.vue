<template>
  <div class="social-login-buttons">
    <div v-if="availableProviders.length > 0" class="q-mb-md">
      <div class="text-center text-grey-7 q-mb-md">
        {{ $t('auth.orContinueWith') }}
      </div>
      <div class="row q-gutter-sm justify-center">
        <q-btn
          v-for="provider in availableProviders"
          :key="provider"
          outline
          :color="getButtonColor(provider)"
          :style="{ borderColor: getProviderColor(provider) }"
          @click="handleOAuthLogin(provider)"
          class="social-btn"
        >
          <q-icon :name="getProviderIcon(provider)" :style="{ color: getProviderColor(provider) }" class="q-mr-sm" />
          <span :style="{ color: getProviderColor(provider) }">{{ getProviderDisplayName(provider) }}</span>
        </q-btn>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useOAuth } from '@/composables/useOAuth';
import type { OAuthProvider } from '@/composables/useOAuth';

const {
  availableProviders,
  fetchAvailableProviders,
  initiateOAuthLogin,
  getProviderDisplayName,
  getProviderIcon,
  getProviderColor,
} = useOAuth();

function getButtonColor(provider: OAuthProvider): string {
  // Use grey for outline buttons
  return 'grey-4';
}

function handleOAuthLogin(provider: OAuthProvider): void {
  initiateOAuthLogin(provider);
}

onMounted(() => {
  fetchAvailableProviders();
});
</script>

<style scoped>
.social-login-buttons {
  width: 100%;
}

.social-btn {
  min-width: 140px;
}
</style>
