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
// BackgroundDecorations - matching old PWA design exactly
// Icons positioned on left and right sides with light indigo color
</script>

<style scoped lang="sass">
.background-decorations
  position: absolute
  inset: 0
  overflow: hidden
  pointer-events: none
  max-width: 1800px
  margin: 0 auto

.decoration
  position: absolute
  color: #EEF2FF

// Left side - matching old PWA positions exactly
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

// Right side - matching old PWA positions exactly
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

// Dark mode
.body--dark
  .decoration
    color: #312E81
</style>
