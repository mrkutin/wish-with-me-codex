<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- Header -->
      <div class="auth-header">
        <h1 class="auth-title">{{ $t('auth.welcomeBack') }}</h1>
        <p class="auth-subtitle">{{ $t('auth.loginSubtitle') }}</p>
      </div>

      <!-- Form -->
      <q-form @submit="handleLogin" class="auth-form">
        <div class="form-fields">
          <q-input
            v-model="email"
            :label="$t('auth.email')"
            type="email"
            outlined
            :rules="[val => !!val || $t('validation.required'), val => /.+@.+\..+/.test(val) || $t('validation.email')]"
            autocomplete="email"
            class="form-field"
          />

          <q-input
            v-model="password"
            :label="$t('auth.password')"
            :type="showPassword ? 'text' : 'password'"
            outlined
            :rules="[val => !!val || $t('validation.required')]"
            autocomplete="current-password"
            class="form-field"
          >
            <template v-slot:append>
              <q-btn
                flat
                round
                dense
                :icon="showPassword ? 'visibility_off' : 'visibility'"
                :aria-label="showPassword ? $t('auth.hidePassword') : $t('auth.showPassword')"
                @click="showPassword = !showPassword"
                tabindex="-1"
              />
            </template>
          </q-input>
        </div>

        <!-- Error message -->
        <div v-if="error" class="error-message" role="alert" aria-live="polite">
          <q-icon name="error_outline" size="20px" />
          <span>{{ error }}</span>
        </div>

        <!-- Submit button -->
        <q-btn
          type="submit"
          color="primary"
          class="submit-btn"
          size="lg"
          :label="$t('auth.login')"
          :loading="authStore.isLoading"
          unelevated
          no-caps
        />
      </q-form>

      <!-- Social login -->
      <SocialLoginButtons class="social-section" />

      <!-- Footer link -->
      <div class="auth-footer">
        <span class="footer-text">{{ $t('auth.noAccount') }}</span>
        <router-link :to="{ name: 'register' }" class="footer-link">
          {{ $t('auth.register') }}
        </router-link>
      </div>
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

<style scoped lang="sass">
.auth-page
  min-height: 100vh
  display: flex
  align-items: center
  justify-content: center
  padding: var(--space-4)
  background: var(--bg-primary)

  // Subtle gradient background
  &::before
    content: ''
    position: fixed
    inset: 0
    background: radial-gradient(ellipse at 50% 0%, rgba(99, 102, 241, 0.05) 0%, transparent 60%)
    pointer-events: none
    z-index: 0

  @media (min-width: 600px)
    padding: var(--space-6)

.auth-card
  position: relative
  z-index: 1
  width: 100%
  max-width: 420px
  padding: var(--space-6)
  background: var(--bg-primary)
  border-radius: var(--radius-xl)
  box-shadow: var(--shadow-lg)
  border: 1px solid var(--border-subtle)

  // Mobile: full-width, no card styling
  @media (max-width: 599px)
    box-shadow: none
    border: none
    background: transparent

  // Tablet: comfortable sizing
  @media (min-width: 600px)
    max-width: 480px
    padding: var(--space-8)

  // Desktop: wider form
  @media (min-width: 1024px)
    max-width: 560px
    padding: var(--space-10)

  // Large desktop: generous sizing
  @media (min-width: 1440px)
    max-width: 640px
    padding: 48px

  // Very large desktop: even more generous
  @media (min-width: 1680px)
    max-width: 720px
    padding: 56px

.auth-header
  text-align: center
  margin-bottom: var(--space-8)

.auth-title
  font-size: var(--text-h2)
  font-weight: 700
  color: var(--text-primary)
  margin: 0 0 var(--space-2) 0
  letter-spacing: -0.02em

  @media (min-width: 600px)
    font-size: var(--text-h1)

.auth-subtitle
  font-size: var(--text-body)
  color: var(--text-secondary)
  margin: 0

.auth-form
  display: flex
  flex-direction: column
  gap: var(--space-4)

.form-fields
  display: flex
  flex-direction: column
  gap: var(--space-4)

.form-field
  margin-bottom: 0

.error-message
  display: flex
  align-items: center
  gap: var(--space-2)
  padding: var(--space-3) var(--space-4)
  background: rgba(220, 38, 38, 0.1)
  border-radius: var(--radius-md)
  color: #DC2626
  font-size: var(--text-body-sm)

.submit-btn
  width: 100%
  margin-top: var(--space-2)
  font-size: 16px

.social-section
  margin-top: var(--space-6)
  padding-top: var(--space-6)
  border-top: 1px solid var(--border-default)

.auth-footer
  text-align: center
  margin-top: var(--space-6)

.footer-text
  color: var(--text-secondary)
  margin-right: var(--space-1)

.footer-link
  color: var(--primary)
  font-weight: 500
  text-decoration: none
  transition: color var(--duration-fast)

  &:hover
    color: var(--primary-dark)

// Dark mode adjustments
.body--dark .auth-card
  background: var(--bg-secondary)
  border-color: var(--border-default)

  @media (max-width: 599px)
    background: transparent
    border: none
</style>
