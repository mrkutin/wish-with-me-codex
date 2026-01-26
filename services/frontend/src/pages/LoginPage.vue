<template>
  <div class="auth-page">
    <!-- Branding section for large desktop -->
    <div class="auth-branding">
      <div class="branding-content">
        <div class="branding-icon">
          <q-icon name="card_giftcard" size="64px" color="white" />
        </div>
        <h2 class="branding-title">Wish With Me</h2>
        <p class="branding-description">{{ $t('auth.brandingDescription') || 'Create wishlists, share with friends, and make gift-giving magical.' }}</p>
        <div class="branding-features">
          <div class="feature-item">
            <q-icon name="check_circle" size="20px" />
            <span>{{ $t('auth.featureOffline') || 'Works offline' }}</span>
          </div>
          <div class="feature-item">
            <q-icon name="check_circle" size="20px" />
            <span>{{ $t('auth.featureShare') || 'Easy sharing' }}</span>
          </div>
          <div class="feature-item">
            <q-icon name="check_circle" size="20px" />
            <span>{{ $t('auth.featureSync') || 'Syncs everywhere' }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="auth-card">
      <!-- Header -->
      <div class="auth-header">
        <h1 class="auth-title">{{ $t('auth.welcomeBack') || 'Welcome back' }}</h1>
        <p class="auth-subtitle">{{ $t('auth.loginSubtitle') || 'Sign in to continue to your wishlists' }}</p>
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
  padding: var(--space-6)
  background: var(--bg-primary)

  // Subtle gradient background
  &::before
    content: ''
    position: fixed
    inset: 0
    background: radial-gradient(ellipse at 50% 0%, rgba(99, 102, 241, 0.05) 0%, transparent 60%)
    pointer-events: none
    z-index: 0

  // Large desktop: two-column layout
  @media (min-width: 1200px)
    justify-content: flex-start
    align-items: stretch
    gap: 0
    padding: 0

// Branding section - hidden by default, shown on large desktop
.auth-branding
  display: none

  @media (min-width: 1200px)
    display: flex
    align-items: center
    justify-content: center
    flex-shrink: 0
    width: 45%
    min-height: 100vh
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark, #4338ca) 100%)
    position: relative
    overflow: hidden

    // Decorative circles
    &::before,
    &::after
      content: ''
      position: absolute
      border-radius: 50%
      background: rgba(255, 255, 255, 0.1)

    &::before
      width: 300px
      height: 300px
      top: -100px
      right: -100px

    &::after
      width: 200px
      height: 200px
      bottom: -50px
      left: -50px

.branding-content
  position: relative
  z-index: 1
  max-width: 400px
  padding: var(--space-12)
  color: white
  text-align: center

.branding-icon
  width: 100px
  height: 100px
  margin: 0 auto var(--space-6)
  background: rgba(255, 255, 255, 0.15)
  border-radius: var(--radius-xl)
  display: flex
  align-items: center
  justify-content: center

.branding-title
  font-size: 2.5rem
  font-weight: 700
  margin: 0 0 var(--space-4) 0
  letter-spacing: -0.02em

.branding-description
  font-size: 1.125rem
  opacity: 0.9
  margin: 0 0 var(--space-8) 0
  line-height: 1.6

.branding-features
  display: flex
  flex-direction: column
  gap: var(--space-3)
  text-align: left

.feature-item
  display: flex
  align-items: center
  gap: var(--space-3)
  font-size: 1rem
  opacity: 0.95

.auth-card
  position: relative
  z-index: 1
  width: 100%
  max-width: 400px
  // Fluid padding: 24px on mobile, scales up to 48px on desktop
  padding: clamp(var(--space-6), 4vw, var(--space-12))
  background: var(--bg-primary)
  border-radius: var(--radius-xl)
  box-shadow: var(--shadow-lg)
  border: 1px solid var(--border-subtle)

  // Mobile: full-width, no card styling
  @media (max-width: 599px)
    padding: var(--space-6)
    box-shadow: none
    border: none
    background: transparent

  // Tablet: 440px max-width, comfortable padding
  @media (min-width: 600px) and (max-width: 1023px)
    max-width: 440px
    padding: var(--space-8)

  // Desktop: 480px max-width, generous padding
  @media (min-width: 1024px) and (max-width: 1199px)
    max-width: 480px
    padding: var(--space-12)

  // Large desktop: form side of two-column layout
  @media (min-width: 1200px)
    max-width: none
    width: 55%
    min-height: 100vh
    display: flex
    flex-direction: column
    justify-content: center
    padding: var(--space-12) clamp(var(--space-12), 8vw, 160px)
    border-radius: 0
    box-shadow: none
    border: none

.auth-header
  text-align: center
  margin-bottom: clamp(var(--space-6), 4vw, var(--space-10))

  @media (min-width: 1200px)
    text-align: left
    max-width: 480px

.auth-title
  font-size: clamp(1.5rem, 4vw, var(--text-h1))
  font-weight: 700
  color: var(--text-primary)
  margin: 0 0 var(--space-2) 0
  letter-spacing: -0.02em

.auth-subtitle
  font-size: var(--text-body)
  color: var(--text-secondary)
  margin: 0

.auth-form
  display: flex
  flex-direction: column
  gap: var(--space-4)

  @media (min-width: 1200px)
    max-width: 480px

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

  @media (min-width: 1200px)
    max-width: 480px

.auth-footer
  text-align: center
  margin-top: var(--space-6)

  @media (min-width: 1200px)
    text-align: left
    max-width: 480px

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

  @media (min-width: 1200px)
    background: var(--bg-primary)
    border: none

.body--dark .auth-branding
  background: linear-gradient(135deg, var(--primary-dark, #4338ca) 0%, #312e81 100%)
</style>
