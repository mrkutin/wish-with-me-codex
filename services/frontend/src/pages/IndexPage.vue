<template>
  <q-page class="flex flex-center">
    <div class="text-center">
      <div class="text-h3 text-primary q-mb-md">{{ $t('common.appName') }}</div>
      <p class="text-body1 text-grey-7 q-mb-lg">
        Create and share wishlists with friends and family
      </p>
      <div class="q-gutter-md">
        <q-btn
          v-if="!authStore.isAuthenticated"
          color="primary"
          size="lg"
          :label="$t('auth.register')"
          :to="{ name: 'register' }"
        />
        <q-btn
          v-if="!authStore.isAuthenticated"
          outline
          color="primary"
          size="lg"
          :label="$t('auth.login')"
          :to="{ name: 'login' }"
        />
        <q-btn
          v-if="authStore.isAuthenticated"
          color="primary"
          size="lg"
          :label="$t('wishlists.title')"
          :to="{ name: 'wishlists' }"
        />
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
</script>
