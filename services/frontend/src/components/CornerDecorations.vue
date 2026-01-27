<template>
  <div class="corner-decorations" aria-hidden="true">
    <!-- Top-left corner ribbon -->
    <svg class="corner-decoration corner-decoration--tl" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- Ribbon strands from corner -->
      <path d="M0 0C0 0 20 25 40 35C60 45 80 40 120 30" stroke="#FB7185" stroke-width="6" fill="none" stroke-linecap="round"/>
      <path d="M0 0C0 0 25 20 35 40C45 60 40 80 30 120" stroke="#FB7185" stroke-width="6" fill="none" stroke-linecap="round"/>
      <!-- Bow loops -->
      <ellipse cx="25" cy="18" rx="14" ry="9" fill="#FB7185" transform="rotate(-35 25 18)"/>
      <ellipse cx="18" cy="25" rx="9" ry="14" fill="#FB7185" transform="rotate(-35 18 25)"/>
      <!-- Bow center knot -->
      <circle cx="22" cy="22" r="5" fill="#F43F5E"/>
      <!-- Bow tails -->
      <path d="M18 28L8 50" stroke="#F43F5E" stroke-width="3" stroke-linecap="round"/>
      <path d="M28 18L50 8" stroke="#F43F5E" stroke-width="3" stroke-linecap="round"/>
    </svg>

    <!-- Bottom-right corner ribbon -->
    <svg class="corner-decoration corner-decoration--br" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- Ribbon strands -->
      <path d="M100 100C100 100 80 80 65 72C50 64 35 68 0 75" stroke="#FB7185" stroke-width="5" fill="none" stroke-linecap="round"/>
      <path d="M100 100C100 100 80 80 72 65C64 50 68 35 75 0" stroke="#FB7185" stroke-width="5" fill="none" stroke-linecap="round"/>
      <!-- Small bow -->
      <ellipse cx="78" cy="85" rx="10" ry="7" fill="#FB7185" transform="rotate(-45 78 85)"/>
      <ellipse cx="85" cy="78" rx="7" ry="10" fill="#FB7185" transform="rotate(-45 85 78)"/>
      <circle cx="82" cy="82" r="4" fill="#F43F5E"/>
    </svg>
  </div>
</template>

<script setup lang="ts">
// Purely decorative component - no logic needed
</script>

<style scoped lang="sass">
.corner-decorations
  pointer-events: none
  position: fixed
  inset: 0
  z-index: 0
  overflow: hidden

.corner-decoration
  position: absolute
  opacity: var(--decoration-opacity-strong)

.corner-decoration--tl
  top: 0
  left: 0
  width: 120px
  height: 120px

.corner-decoration--br
  bottom: 0
  right: 0
  width: 100px
  height: 100px

// Hide on very small screens to avoid clutter
@media (max-width: 400px)
  .corner-decoration--br
    display: none

  .corner-decoration--tl
    width: 80px
    height: 80px
</style>
