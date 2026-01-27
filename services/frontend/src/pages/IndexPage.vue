<template>
  <q-page class="index-page">
    <div class="hero-section">
      <!-- Decorative background -->
      <div class="hero-bg" aria-hidden="true"></div>

      <!-- Hero content -->
      <div class="hero-content">
        <h1 class="hero-title">{{ $t('common.appName') }}</h1>
        <p class="hero-subtitle">
          {{ $t('home.subtitle') || 'Create and share wishlists with friends and family' }}
        </p>

        <div class="hero-actions">
          <q-btn
            v-if="!authStore.isAuthenticated"
            color="primary"
            size="lg"
            :label="$t('auth.register')"
            :to="{ name: 'register' }"
            unelevated
            no-caps
            class="hero-btn-primary"
          />
          <q-btn
            v-if="!authStore.isAuthenticated"
            outline
            color="primary"
            size="lg"
            :label="$t('auth.login')"
            :to="{ name: 'login' }"
            no-caps
            class="hero-btn-secondary"
          />
          <q-btn
            v-if="authStore.isAuthenticated"
            color="primary"
            size="lg"
            :label="$t('wishlists.title')"
            :to="{ name: 'wishlists' }"
            unelevated
            no-caps
            class="hero-btn-primary"
          />
        </div>

        <!-- Features section -->
        <div v-if="!authStore.isAuthenticated" class="features-section">
          <div class="features-grid">
            <div class="feature-card">
              <div class="feature-icon">
                <q-icon name="checklist" size="32px" color="primary" />
              </div>
              <h3 class="feature-title">{{ $t('home.feature1Title') || 'Create Wishlists' }}</h3>
              <p class="feature-description">{{ $t('home.feature1Desc') || 'Organize your wishes into beautiful, shareable lists' }}</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">
                <q-icon name="share" size="32px" color="primary" />
              </div>
              <h3 class="feature-title">{{ $t('home.feature2Title') || 'Share Easily' }}</h3>
              <p class="feature-description">{{ $t('home.feature2Desc') || 'Share with friends and family via a simple link' }}</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">
                <q-icon name="cloud_off" size="32px" color="primary" />
              </div>
              <h3 class="feature-title">{{ $t('home.feature3Title') || 'Works Offline' }}</h3>
              <p class="feature-description">{{ $t('home.feature3Desc') || 'Access your wishlists anytime, even without internet' }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
</script>

<style scoped lang="sass">
.index-page
  min-height: 100vh
  background: transparent

.hero-section
  position: relative
  overflow: hidden
  min-height: calc(100vh - 56px)
  display: flex
  align-items: center
  justify-content: center

.hero-bg
  position: absolute
  inset: 0
  background: radial-gradient(ellipse at 50% 0%, rgba(99, 102, 241, 0.08) 0%, transparent 70%)
  pointer-events: none

.hero-content
  position: relative
  z-index: 1
  text-align: center
  padding: var(--space-8) var(--space-6)
  max-width: 800px
  margin: 0 auto

.hero-title
  font-size: var(--text-display)
  font-weight: 700
  letter-spacing: -0.03em
  line-height: 1.1
  margin: 0 0 var(--space-4) 0
  background: linear-gradient(135deg, #6366F1 0%, #4F46E5 50%, #7C3AED 100%)
  -webkit-background-clip: text
  -webkit-text-fill-color: transparent
  background-clip: text

.hero-subtitle
  font-size: var(--text-h4)
  color: var(--text-secondary)
  max-width: 480px
  margin: 0 auto var(--space-8)
  line-height: 1.6
  font-weight: 400

.hero-actions
  display: flex
  flex-wrap: wrap
  gap: var(--space-4)
  justify-content: center

.hero-btn-primary
  min-width: 160px
  font-size: 16px
  padding: 0 var(--space-8)

.hero-btn-secondary
  min-width: 160px
  font-size: 16px
  padding: 0 var(--space-8)

// Features section
.features-section
  margin-top: var(--space-16)
  padding-top: var(--space-8)
  border-top: 1px solid var(--border-subtle)

.features-grid
  display: grid
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))
  gap: var(--space-6)
  text-align: center

.feature-card
  padding: var(--space-6)
  border-radius: var(--radius-lg)
  background: var(--bg-secondary)
  border: 1px solid var(--border-subtle)
  transition: transform var(--duration-fast), box-shadow var(--duration-fast)

  &:hover
    transform: translateY(-2px)
    box-shadow: var(--shadow-md)

.feature-icon
  width: 64px
  height: 64px
  margin: 0 auto var(--space-4)
  display: flex
  align-items: center
  justify-content: center
  background: var(--primary-light)
  border-radius: var(--radius-lg)

.feature-title
  font-size: var(--text-h4)
  font-weight: 600
  margin: 0 0 var(--space-2) 0
  color: var(--text-primary)

.feature-description
  font-size: var(--text-body-sm)
  color: var(--text-secondary)
  margin: 0
  line-height: 1.5

// Dark mode adjustments
.body--dark
  .feature-icon
    background: rgba(99, 102, 241, 0.15)

// Responsive adjustments
@media (max-width: 599px)
  .hero-content
    padding: var(--space-6) var(--space-4)

  .hero-title
    font-size: 2rem

  .hero-subtitle
    font-size: 1rem

  .hero-actions
    flex-direction: column
    width: 100%

  .hero-btn-primary,
  .hero-btn-secondary
    width: 100%
    min-width: auto

  .features-grid
    grid-template-columns: 1fr
</style>
