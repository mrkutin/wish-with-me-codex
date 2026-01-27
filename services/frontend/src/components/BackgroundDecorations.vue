<template>
  <div class="background-decorations">
    <!-- Left side decorations -->
    <div class="decoration decoration-left-1">
      <q-icon name="card_giftcard" />
    </div>
    <div class="decoration decoration-left-2">
      <q-icon name="favorite_border" />
    </div>
    <div class="decoration decoration-left-3">
      <q-icon name="shopping_bag" />
    </div>

    <!-- Right side decorations -->
    <div class="decoration decoration-right-1">
      <q-icon name="inventory_2" />
    </div>
    <div class="decoration decoration-right-2">
      <q-icon name="favorite_border" />
    </div>
    <div class="decoration decoration-right-3">
      <q-icon name="card_giftcard" />
    </div>
  </div>
</template>

<script setup lang="ts">
// BackgroundDecorations - subtle gift/wishlist themed decorations
// Matching the old PWA design
</script>

<style scoped lang="sass">
.background-decorations
  position: fixed
  inset: 0
  overflow: hidden
  pointer-events: none
  z-index: 0
  max-width: 1800px
  margin: 0 auto

.decoration
  position: absolute
  color: var(--decoration-color)
  opacity: 1

  .q-icon
    font-size: 96px

// Left side
.decoration-left-1
  left: 2rem
  top: 15%
  transform: rotate(-12deg)

  .q-icon
    font-size: 96px

.decoration-left-2
  left: 3rem
  top: 45%
  transform: rotate(12deg)

  .q-icon
    font-size: 80px

.decoration-left-3
  left: 4rem
  bottom: 20%
  transform: rotate(-6deg)

  .q-icon
    font-size: 64px

// Right side
.decoration-right-1
  right: 2rem
  top: 20%
  transform: rotate(12deg)

  .q-icon
    font-size: 80px

.decoration-right-2
  right: 3rem
  top: 50%
  transform: rotate(-12deg)

  .q-icon
    font-size: 96px

.decoration-right-3
  right: 4rem
  bottom: 15%
  transform: rotate(6deg)

  .q-icon
    font-size: 64px

// Hide decorations on smaller screens where they would overlap content
@media (max-width: 1200px)
  .background-decorations
    display: none

// Dark mode - slightly reduce opacity
.body--dark
  .decoration
    opacity: 0.5
    color: #312E81
</style>
