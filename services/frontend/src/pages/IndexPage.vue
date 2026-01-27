<template>
  <q-page class="landing-page">
    <!-- Hero Section -->
    <section class="hero-section">
      <div class="hero-container">
        <div class="hero-content">
          <h1 class="hero-title">{{ $t('home.heroTitle') }}</h1>
          <p class="hero-subtitle">{{ $t('home.heroSubtitle') }}</p>
          <q-btn
            color="primary"
            size="lg"
            :label="$t('home.createWishlist')"
            :to="authStore.isAuthenticated ? { name: 'wishlists' } : { name: 'register' }"
            unelevated
            no-caps
            class="hero-cta"
          />
        </div>
        <div class="hero-illustration">
          <div class="hero-phone">
            <div class="phone-screen">
              <div class="phone-header">
                <q-icon name="card_giftcard" size="24px" color="primary" />
                <span>Wish With Me</span>
              </div>
              <div class="phone-wishlist">
                <div class="wishlist-card-mini">
                  <q-icon name="checklist" size="20px" color="primary" />
                  <span>Birthday Wishlist</span>
                </div>
                <div class="wishlist-card-mini">
                  <q-icon name="celebration" size="20px" color="primary" />
                  <span>New Year Gifts</span>
                </div>
              </div>
            </div>
          </div>
          <div class="floating-gift gift-1">
            <q-icon name="card_giftcard" size="48px" />
          </div>
          <div class="floating-gift gift-2">
            <q-icon name="redeem" size="36px" />
          </div>
          <div class="floating-gift gift-3">
            <q-icon name="favorite" size="28px" />
          </div>
        </div>
      </div>
    </section>

    <!-- How It Works Section -->
    <section class="how-it-works-section">
      <div class="section-container">
        <h2 class="section-title">{{ $t('home.howItWorks') }}</h2>
        <div class="steps-grid">
          <div class="step-card">
            <div class="step-illustration">
              <div class="step-icon-wrapper">
                <q-icon name="add_circle" size="48px" color="primary" />
              </div>
            </div>
            <div class="step-badge">{{ $t('common.create').toUpperCase() }} 1</div>
            <h3 class="step-title">{{ $t('home.step1Title') }}</h3>
            <p class="step-desc">{{ $t('home.step1Desc') }}</p>
          </div>
          <div class="step-card">
            <div class="step-illustration">
              <div class="step-icon-wrapper">
                <q-icon name="share" size="48px" color="primary" />
              </div>
            </div>
            <div class="step-badge">{{ $t('common.create').toUpperCase() }} 2</div>
            <h3 class="step-title">{{ $t('home.step2Title') }}</h3>
            <p class="step-desc">{{ $t('home.step2Desc') }}</p>
          </div>
          <div class="step-card">
            <div class="step-illustration">
              <div class="step-icon-wrapper">
                <q-icon name="celebration" size="48px" color="primary" />
              </div>
            </div>
            <div class="step-badge">{{ $t('common.create').toUpperCase() }} 3</div>
            <h3 class="step-title">{{ $t('home.step3Title') }}</h3>
            <p class="step-desc">{{ $t('home.step3Desc') }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Benefit 1: Get what you want -->
    <section class="benefit-section benefit-light">
      <div class="benefit-container">
        <div class="benefit-content">
          <h2 class="benefit-title">{{ $t('home.benefit1Title') }}</h2>
          <p class="benefit-desc">{{ $t('home.benefit1Desc') }}</p>
          <q-btn
            color="primary"
            size="lg"
            :label="$t('home.benefit1Cta')"
            :to="authStore.isAuthenticated ? { name: 'wishlists' } : { name: 'register' }"
            unelevated
            no-caps
            class="benefit-cta"
          />
        </div>
        <div class="benefit-illustration">
          <div class="gift-box-illustration">
            <q-icon name="redeem" size="120px" color="primary" />
          </div>
        </div>
      </div>
    </section>

    <!-- Benefit 2: Help friends -->
    <section class="benefit-section">
      <div class="benefit-container benefit-reverse">
        <div class="benefit-content">
          <h2 class="benefit-title">{{ $t('home.benefit2Title') }}</h2>
          <p class="benefit-desc">{{ $t('home.benefit2Desc') }}</p>
        </div>
        <div class="benefit-illustration">
          <div class="chat-bubbles">
            <div class="chat-bubble chat-question">
              <q-icon name="help_outline" size="20px" />
              <span>What to give?</span>
            </div>
            <div class="chat-bubble chat-answer">
              <q-icon name="link" size="20px" />
              <span>Here's my wishlist!</span>
            </div>
            <div class="chat-bubble chat-happy">
              <q-icon name="favorite" size="20px" />
              <span>Perfect!</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Benefit 3: All in one place -->
    <section class="benefit-section benefit-green">
      <div class="benefit-container">
        <div class="benefit-content benefit-content-centered">
          <h2 class="benefit-title">{{ $t('home.benefit3Title') }}</h2>
          <p class="benefit-desc">{{ $t('home.benefit3Desc') }}</p>
          <q-btn
            color="primary"
            size="lg"
            :label="$t('home.finalCta')"
            :to="authStore.isAuthenticated ? { name: 'wishlists' } : { name: 'register' }"
            unelevated
            no-caps
            class="benefit-cta"
          />
        </div>
        <div class="wishlists-showcase">
          <div class="showcase-card">
            <div class="showcase-emoji">&#127873;</div>
            <span>Birthday</span>
          </div>
          <div class="showcase-card">
            <div class="showcase-emoji">&#127876;</div>
            <span>New Year</span>
          </div>
          <div class="showcase-card">
            <div class="showcase-emoji">&#127968;</div>
            <span>Housewarming</span>
          </div>
          <div class="showcase-card">
            <div class="showcase-emoji">&#128144;</div>
            <span>Wedding</span>
          </div>
        </div>
      </div>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
</script>

<style scoped lang="sass">
.landing-page
  background: transparent

// Hero Section
.hero-section
  padding: var(--space-16) var(--space-6) var(--space-12)
  min-height: calc(100vh - 56px)
  display: flex
  align-items: center

  @media (max-width: 768px)
    padding: var(--space-8) var(--space-4)
    min-height: auto

.hero-container
  max-width: 1200px
  margin: 0 auto
  display: grid
  grid-template-columns: 1fr 1fr
  gap: var(--space-12)
  align-items: center

  @media (max-width: 900px)
    grid-template-columns: 1fr
    text-align: center
    gap: var(--space-8)

.hero-content
  @media (max-width: 900px)
    order: 1

.hero-title
  font-size: 2.75rem
  font-weight: 700
  line-height: 1.2
  margin: 0 0 var(--space-6) 0
  color: var(--text-primary)

  @media (max-width: 768px)
    font-size: 1.75rem

.hero-subtitle
  font-size: 1.25rem
  color: var(--text-secondary)
  margin: 0 0 var(--space-8) 0
  line-height: 1.6

  @media (max-width: 768px)
    font-size: 1rem

.hero-cta
  font-size: 1.125rem
  padding: var(--space-4) var(--space-8)
  border-radius: var(--radius-lg)

  @media (max-width: 900px)
    width: 100%
    max-width: 300px

.hero-illustration
  position: relative
  display: flex
  justify-content: center
  align-items: center
  min-height: 400px

  @media (max-width: 900px)
    order: 2
    min-height: 300px

.hero-phone
  width: 260px
  height: 400px
  background: white
  border-radius: 32px
  box-shadow: var(--shadow-xl)
  overflow: hidden
  border: 8px solid #1a1a1a
  position: relative

  @media (max-width: 768px)
    width: 200px
    height: 320px

.phone-screen
  padding: var(--space-4)
  background: var(--bg-secondary)
  height: 100%

.phone-header
  display: flex
  align-items: center
  gap: var(--space-2)
  padding: var(--space-2)
  font-weight: 600
  color: var(--primary)
  font-size: 0.875rem

.phone-wishlist
  margin-top: var(--space-4)
  display: flex
  flex-direction: column
  gap: var(--space-3)

.wishlist-card-mini
  display: flex
  align-items: center
  gap: var(--space-2)
  padding: var(--space-3)
  background: white
  border-radius: var(--radius-md)
  box-shadow: var(--shadow-sm)
  font-size: 0.875rem

.floating-gift
  position: absolute
  background: white
  border-radius: 50%
  padding: var(--space-3)
  box-shadow: var(--shadow-lg)
  color: var(--primary)

.gift-1
  top: 10%
  right: 5%
  animation: float 3s ease-in-out infinite

.gift-2
  bottom: 20%
  left: 5%
  animation: float 3s ease-in-out infinite 0.5s

.gift-3
  top: 40%
  left: 0%
  animation: float 3s ease-in-out infinite 1s

@keyframes float
  0%, 100%
    transform: translateY(0)
  50%
    transform: translateY(-10px)

// How It Works Section
.how-it-works-section
  padding: var(--space-16) var(--space-6)
  background: white

.section-container
  max-width: 1200px
  margin: 0 auto

.section-title
  font-size: 2rem
  font-weight: 700
  text-align: center
  margin: 0 0 var(--space-12) 0
  color: var(--text-primary)

  @media (max-width: 768px)
    font-size: 1.5rem
    margin-bottom: var(--space-8)

.steps-grid
  display: grid
  grid-template-columns: repeat(3, 1fr)
  gap: var(--space-8)

  @media (max-width: 900px)
    grid-template-columns: 1fr
    gap: var(--space-6)

.step-card
  text-align: center
  padding: var(--space-6)
  background: var(--bg-secondary)
  border-radius: var(--radius-xl)
  border: 1px solid var(--border-subtle)

.step-illustration
  margin-bottom: var(--space-4)

.step-icon-wrapper
  width: 100px
  height: 100px
  margin: 0 auto
  background: rgba(79, 70, 229, 0.1)
  border-radius: var(--radius-xl)
  display: flex
  align-items: center
  justify-content: center

.step-badge
  display: inline-block
  font-size: 0.75rem
  font-weight: 600
  color: var(--text-tertiary)
  margin-bottom: var(--space-2)
  letter-spacing: 0.05em

.step-title
  font-size: 1.25rem
  font-weight: 600
  margin: 0 0 var(--space-2) 0
  color: var(--text-primary)

.step-desc
  font-size: 0.9375rem
  color: var(--text-secondary)
  margin: 0
  line-height: 1.5

// Benefit Sections
.benefit-section
  padding: var(--space-16) var(--space-6)

.benefit-light
  background: rgba(79, 70, 229, 0.05)

.benefit-green
  background: rgba(34, 197, 94, 0.08)

.benefit-container
  max-width: 1100px
  margin: 0 auto
  display: grid
  grid-template-columns: 1fr 1fr
  gap: var(--space-12)
  align-items: center

  @media (max-width: 900px)
    grid-template-columns: 1fr
    gap: var(--space-8)
    text-align: center

.benefit-reverse
  @media (min-width: 901px)
    direction: rtl
    > *
      direction: ltr

.benefit-content
  @media (max-width: 900px)
    order: 1

.benefit-content-centered
  @media (min-width: 901px)
    grid-column: 1 / -1
    text-align: center
    max-width: 700px
    margin: 0 auto

.benefit-title
  font-size: 2rem
  font-weight: 700
  margin: 0 0 var(--space-4) 0
  color: var(--text-primary)

  @media (max-width: 768px)
    font-size: 1.5rem

.benefit-desc
  font-size: 1.125rem
  color: var(--text-secondary)
  margin: 0 0 var(--space-6) 0
  line-height: 1.6

  @media (max-width: 768px)
    font-size: 1rem

.benefit-cta
  font-size: 1rem
  padding: var(--space-3) var(--space-6)
  border-radius: var(--radius-lg)

.benefit-illustration
  display: flex
  justify-content: center
  align-items: center

  @media (max-width: 900px)
    order: 2

.gift-box-illustration
  width: 200px
  height: 200px
  background: rgba(79, 70, 229, 0.1)
  border-radius: 50%
  display: flex
  align-items: center
  justify-content: center

// Chat bubbles animation
.chat-bubbles
  display: flex
  flex-direction: column
  gap: var(--space-3)
  width: 100%
  max-width: 300px

.chat-bubble
  display: flex
  align-items: center
  gap: var(--space-2)
  padding: var(--space-3) var(--space-4)
  border-radius: var(--radius-lg)
  font-size: 0.9375rem
  animation: slideIn 0.5s ease-out

.chat-question
  background: #e5e7eb
  color: var(--text-primary)
  align-self: flex-start

.chat-answer
  background: var(--primary)
  color: white
  align-self: flex-end
  animation-delay: 0.3s

.chat-happy
  background: #22c55e
  color: white
  align-self: flex-start
  animation-delay: 0.6s

@keyframes slideIn
  from
    opacity: 0
    transform: translateY(10px)
  to
    opacity: 1
    transform: translateY(0)

// Wishlists showcase
.wishlists-showcase
  display: flex
  flex-wrap: wrap
  gap: var(--space-4)
  justify-content: center
  margin-top: var(--space-8)

.showcase-card
  background: white
  padding: var(--space-4) var(--space-6)
  border-radius: var(--radius-lg)
  box-shadow: var(--shadow-md)
  display: flex
  flex-direction: column
  align-items: center
  gap: var(--space-2)
  min-width: 120px
  transition: transform var(--duration-fast)

  &:hover
    transform: translateY(-4px)

.showcase-emoji
  font-size: 2rem

// Dark mode
.body--dark
  .hero-phone
    border-color: #333

  .phone-screen
    background: var(--bg-tertiary)

  .wishlist-card-mini
    background: var(--bg-secondary)

  .floating-gift
    background: var(--bg-secondary)

  .how-it-works-section
    background: var(--bg-secondary)

  .step-card
    background: var(--bg-tertiary)

  .chat-question
    background: var(--bg-tertiary)

  .showcase-card
    background: var(--bg-secondary)
</style>
