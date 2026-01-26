<template>
  <div>
    <q-form @submit="handleLogin" class="q-gutter-md">
      <q-input
        v-model="email"
        :label="$t('auth.email')"
        type="email"
        outlined
        :rules="[val => !!val || $t('validation.required'), val => /.+@.+\..+/.test(val) || $t('validation.email')]"
      />

      <q-input
        v-model="password"
        :label="$t('auth.password')"
        :type="showPassword ? 'text' : 'password'"
        outlined
        :rules="[val => !!val || $t('validation.required')]"
      >
        <template v-slot:append>
          <q-btn
            flat
            round
            dense
            :icon="showPassword ? 'visibility_off' : 'visibility'"
            :aria-label="showPassword ? 'Hide password' : 'Show password'"
            @click="showPassword = !showPassword"
          />
        </template>
      </q-input>

      <div v-if="error" class="text-negative text-center" role="alert" aria-live="polite">
        {{ error }}
      </div>

      <q-btn
        type="submit"
        color="primary"
        class="full-width"
        size="lg"
        :label="$t('auth.login')"
        :loading="authStore.isLoading"
      />
    </q-form>

    <SocialLoginButtons class="q-mt-lg" />

    <div class="text-center q-mt-lg">
      <router-link :to="{ name: 'register' }" class="text-primary">
        {{ $t('auth.noAccount') }} {{ $t('auth.register') }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useI18n } from 'vue-i18n';
import { LocalStorage } from 'quasar';
import SocialLoginButtons from '@/components/SocialLoginButtons.vue';

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const { t } = useI18n();

const email = ref('');
const password = ref('');
const showPassword = ref(false);
const error = ref('');

// Store share token from query param if present
onMounted(() => {
  const shareToken = route.query.share_token as string;
  if (shareToken) {
    LocalStorage.set(PENDING_SHARE_TOKEN_KEY, shareToken);
  }
});

function isValidRedirect(url: string): boolean {
  // Only allow relative paths starting with /
  if (!url || !url.startsWith('/')) {
    return false;
  }
  // Prevent protocol-relative URLs like //evil.com
  if (url.startsWith('//')) {
    return false;
  }
  return true;
}

async function handleLogin() {
  error.value = '';
  try {
    await authStore.login(email.value, password.value);

    // Check for pending share token first
    const pendingShareToken = LocalStorage.getItem<string>(PENDING_SHARE_TOKEN_KEY);
    if (pendingShareToken) {
      LocalStorage.remove(PENDING_SHARE_TOKEN_KEY);
      router.push({ name: 'shared-wishlist', params: { token: pendingShareToken } });
      return;
    }

    const redirect = route.query.redirect as string;
    // Validate redirect to prevent open redirect vulnerability
    router.push(isValidRedirect(redirect) ? redirect : { name: 'wishlists' });
  } catch (err: unknown) {
    error.value = t('auth.invalidCredentials');
  }
}
</script>
