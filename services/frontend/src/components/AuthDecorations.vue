<template>
  <div class="auth-decorations" aria-hidden="true">
    <!-- Floating gift boxes -->
    <svg class="floating-element floating-gift floating-gift-1" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="6" y="20" width="36" height="24" rx="3" fill="#FB7185" fill-opacity="0.4"/>
      <rect x="3" y="14" width="42" height="9" rx="2" fill="#FB7185" fill-opacity="0.5"/>
      <rect x="21" y="14" width="6" height="30" fill="#F43F5E" fill-opacity="0.6"/>
      <rect x="3" y="17" width="42" height="4" fill="#F43F5E" fill-opacity="0.6"/>
    </svg>

    <svg class="floating-element floating-gift floating-gift-2" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="5" y="17" width="30" height="20" rx="2.5" fill="#FB7185" fill-opacity="0.35"/>
      <rect x="2.5" y="12" width="35" height="7" rx="1.5" fill="#FB7185" fill-opacity="0.45"/>
      <rect x="17.5" y="12" width="5" height="25" fill="#F43F5E" fill-opacity="0.55"/>
      <rect x="2.5" y="14" width="35" height="3" fill="#F43F5E" fill-opacity="0.55"/>
    </svg>

    <svg class="floating-element floating-gift floating-gift-3" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="4.5" y="15" width="27" height="18" rx="2" fill="#FB7185" fill-opacity="0.3"/>
      <rect x="2.5" y="10.5" width="31" height="6.5" rx="1.5" fill="#FB7185" fill-opacity="0.4"/>
      <rect x="15.5" y="10.5" width="4.5" height="22.5" fill="#F43F5E" fill-opacity="0.5"/>
    </svg>

    <!-- Floating sparkles -->
    <svg class="floating-element floating-sparkle floating-sparkle-1" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L14 10L22 12L14 14L12 22L10 14L2 12L10 10L12 2Z" fill="#FBBF24" fill-opacity="0.8"/>
    </svg>

    <svg class="floating-element floating-sparkle floating-sparkle-2" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M10 1L11.5 8.5L19 10L11.5 11.5L10 19L8.5 11.5L1 10L8.5 8.5L10 1Z" fill="#FCD34D" fill-opacity="0.75"/>
    </svg>

    <svg class="floating-element floating-sparkle floating-sparkle-3" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M8 0L9.5 6.5L16 8L9.5 9.5L8 16L6.5 9.5L0 8L6.5 6.5L8 0Z" fill="#FBBF24" fill-opacity="0.7"/>
    </svg>

    <svg class="floating-element floating-sparkle floating-sparkle-4" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M7 0L8.2 5.8L14 7L8.2 8.2L7 14L5.8 8.2L0 7L5.8 5.8L7 0Z" fill="#FCD34D" fill-opacity="0.65"/>
    </svg>

    <!-- Centered warm glow -->
    <div class="auth-glow"></div>
  </div>
</template>

<script setup lang="ts">
// Purely decorative component - no logic needed
</script>

<style scoped lang="sass">
.auth-decorations
  position: absolute
  inset: 0
  overflow: hidden
  pointer-events: none
  z-index: 0

// Centered warm radial glow
.auth-glow
  position: absolute
  top: 30%
  left: 50%
  transform: translate(-50%, -50%)
  width: 150%
  height: 100%
  background: radial-gradient(ellipse 60% 50% at 50% 40%, var(--gift-peach-50) 0%, transparent 70%)
  opacity: 0.8

.body--dark .auth-glow
  background: radial-gradient(ellipse 60% 50% at 50% 40%, rgba(251, 113, 133, 0.05) 0%, transparent 70%)
  opacity: 0.6

.floating-element
  position: absolute
  opacity: 0.12

.body--dark .floating-element
  opacity: 0.06

// Floating gifts positioning
.floating-gift-1
  top: 8%
  left: 5%
  width: 60px
  animation: float 7s ease-in-out infinite

.floating-gift-2
  bottom: 15%
  right: 6%
  width: 50px
  animation: float 8s ease-in-out infinite
  animation-delay: -2.5s

.floating-gift-3
  top: 55%
  left: 8%
  width: 42px
  animation: float 9s ease-in-out infinite
  animation-delay: -4s

// Floating sparkles positioning
.floating-sparkle-1
  top: 15%
  right: 12%
  width: 28px
  animation: twinkle 4s ease-in-out infinite

.floating-sparkle-2
  bottom: 25%
  left: 12%
  width: 24px
  animation: twinkle 5s ease-in-out infinite
  animation-delay: -1.5s

.floating-sparkle-3
  top: 40%
  right: 8%
  width: 20px
  animation: twinkle 4.5s ease-in-out infinite
  animation-delay: -3s

.floating-sparkle-4
  bottom: 40%
  right: 18%
  width: 18px
  animation: twinkle 5.5s ease-in-out infinite
  animation-delay: -2s

// Animations
@keyframes float
  0%, 100%
    transform: translateY(0px) rotate(-3deg)
  50%
    transform: translateY(-12px) rotate(3deg)

@keyframes twinkle
  0%, 100%
    opacity: 0.12
    transform: scale(1)
  50%
    opacity: 0.2
    transform: scale(1.15)

.body--dark
  @keyframes twinkle
    0%, 100%
      opacity: 0.06
      transform: scale(1)
    50%
      opacity: 0.1
      transform: scale(1.15)

// Reduced motion
@media (prefers-reduced-motion: reduce)
  .floating-element
    animation: none !important

// Hide some elements on small screens
@media (max-width: 599px)
  .floating-gift-3,
  .floating-sparkle-3,
  .floating-sparkle-4
    display: none

  .floating-gift-1
    width: 45px
    top: 5%
    left: 3%

  .floating-gift-2
    width: 40px
    right: 3%

  .floating-sparkle-1,
  .floating-sparkle-2
    width: 20px
</style>
