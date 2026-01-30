<template>
  <q-page class="flex flex-center">
    <div class="text-center">
      <q-spinner-dots color="primary" size="60px" v-if="isProcessing" />
      <div v-if="errorMessage" class="q-mt-md">
        <q-icon name="error" color="negative" size="60px" />
        <div class="text-h6 text-negative q-mt-md">{{ errorMessage }}</div>
        <q-btn
          :label="$t('auth.login')"
          color="primary"
          class="q-mt-lg"
          :to="loginRedirect"
        />
      </div>
      <div v-if="successMessage" class="q-mt-md">
        <q-icon name="check_circle" color="positive" size="60px" />
        <div class="text-h6 text-positive q-mt-md">{{ successMessage }}</div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useI18n } from 'vue-i18n';
import { LocalStorage } from 'quasar';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const { t } = useI18n();

const isProcessing = ref(true);
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const isEmailExistsError = ref(false);

// If email_exists error, redirect to settings after login so user can link account
const loginRedirect = computed(() => ({
  name: 'login',
  query: isEmailExistsError.value ? { redirect: '/settings' } : undefined,
}));

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

function getErrorMessage(error: string, email?: string, provider?: string): string {
  switch (error) {
    case 'email_exists':
      return t('oauth.emailConflict', { email: email || '', provider: provider || '' });
    case 'already_linked':
      return t('oauth.alreadyLinked', { provider: provider || '' });
    case 'auth_failed':
      return t('oauth.authFailed');
    case 'server_error':
      return t('errors.generic');
    default:
      return error || t('errors.generic');
  }
}

async function processCallback(): Promise<void> {
  const query = route.query;

  // Check for errors
  if (query.error) {
    const error = query.error as string;
    const email = query.email as string | undefined;
    const provider = query.provider as string | undefined;
    errorMessage.value = getErrorMessage(error, email, provider);
    isEmailExistsError.value = error === 'email_exists';
    isProcessing.value = false;
    return;
  }

  // Check for successful account linking
  if (query.linked) {
    const provider = query.linked as string;
    successMessage.value = t('oauth.accountLinked', { provider });
    isProcessing.value = false;
    // Redirect to settings after a short delay
    setTimeout(() => {
      router.push({ name: 'settings' });
    }, 1500);
    return;
  }

  // Check for tokens (successful login/register)
  const accessToken = query.access_token as string | undefined;
  const refreshToken = query.refresh_token as string | undefined;
  const expiresIn = query.expires_in as string | undefined;
  const isNewUser = query.new_user === 'true';

  if (accessToken && refreshToken) {
    // Initialize auth store with OAuth tokens directly
    try {
      // Use the access token directly instead of refreshing immediately
      await authStore.setTokensFromOAuth({
        access_token: accessToken,
        refresh_token: refreshToken,
      });

      if (isNewUser) {
        successMessage.value = t('oauth.accountCreated');
      } else {
        successMessage.value = t('oauth.loginSuccess');
      }
      isProcessing.value = false;

      // Check for pending share token and redirect accordingly
      const pendingShareToken = LocalStorage.getItem<string>(PENDING_SHARE_TOKEN_KEY);
      if (pendingShareToken) {
        LocalStorage.remove(PENDING_SHARE_TOKEN_KEY);
        setTimeout(() => {
          router.push({ name: 'shared-wishlist', params: { token: pendingShareToken } });
        }, 1000);
      } else {
        // Redirect to wishlists
        setTimeout(() => {
          router.push({ name: 'wishlists' });
        }, 1000);
      }
    } catch (err) {
      errorMessage.value = t('oauth.authFailed');
      isProcessing.value = false;
    }
    return;
  }

  // No recognized query params
  errorMessage.value = t('oauth.invalidCallback');
  isProcessing.value = false;
}

onMounted(() => {
  processCallback();
});
</script>
