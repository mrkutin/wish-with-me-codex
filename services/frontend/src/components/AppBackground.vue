<template>
  <div class="app-background" aria-hidden="true">
    <div class="app-background__gradient"></div>
    <div class="app-background__pattern"></div>
  </div>
</template>

<script setup lang="ts">
// Purely decorative component - no logic needed
</script>

<style scoped lang="sass">
.app-background
  position: fixed
  top: 0
  left: 0
  right: 0
  bottom: 0
  pointer-events: none
  z-index: -1

.app-background__gradient
  position: absolute
  inset: 0
  background: linear-gradient(180deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%)

.app-background__pattern
  position: absolute
  inset: 0
  opacity: var(--decoration-opacity)
  // SVG pattern with gift boxes, sparkles, ribbons, and bows
  // Pattern tile is 400x400px
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3C!-- Gift box 1 at (50, 80) ---%3E%3Cg transform='translate(50, 80) rotate(-15)'%3E%3Crect x='0' y='8' width='32' height='20' rx='2' fill='%23FB7185' fill-opacity='0.4'/%3E%3Crect x='-2' y='4' width='36' height='6' rx='1.5' fill='%23FB7185' fill-opacity='0.5'/%3E%3Crect x='14' y='4' width='4' height='24' fill='%23F43F5E' fill-opacity='0.6'/%3E%3Crect x='-2' y='6' width='36' height='3' fill='%23F43F5E' fill-opacity='0.6'/%3E%3C/g%3E%3C!-- Gift box 2 at (280, 200) ---%3E%3Cg transform='translate(280, 200) rotate(10)'%3E%3Crect x='0' y='6' width='24' height='15' rx='2' fill='%23FB7185' fill-opacity='0.35'/%3E%3Crect x='-1.5' y='3' width='27' height='4.5' rx='1' fill='%23FB7185' fill-opacity='0.45'/%3E%3Crect x='10' y='3' width='3' height='18' fill='%23F43F5E' fill-opacity='0.5'/%3E%3Crect x='-1.5' y='4.5' width='27' height='2' fill='%23F43F5E' fill-opacity='0.5'/%3E%3C/g%3E%3C!-- Gift box 3 at (340, 340) ---%3E%3Cg transform='translate(340, 340) rotate(-8)'%3E%3Crect x='0' y='5' width='20' height='13' rx='1.5' fill='%23FB7185' fill-opacity='0.3'/%3E%3Crect x='-1' y='2' width='22' height='4' rx='1' fill='%23FB7185' fill-opacity='0.4'/%3E%3Crect x='8' y='2' width='3' height='16' fill='%23F43F5E' fill-opacity='0.45'/%3E%3C/g%3E%3C!-- Sparkle 1 at (120, 40) ---%3E%3Cpath d='M128 40L129.5 46.5L136 48L129.5 49.5L128 56L126.5 49.5L120 48L126.5 46.5L128 40Z' fill='%23FBBF24' fill-opacity='0.7'/%3E%3C!-- Sparkle 2 at (320, 100) ---%3E%3Cpath d='M326 100L327 105L332 106L327 107L326 112L325 107L320 106L325 105L326 100Z' fill='%23FBBF24' fill-opacity='0.6'/%3E%3C!-- Sparkle 3 at (180, 280) ---%3E%3Cpath d='M187 280L188.2 286L194 287L188.2 288L187 294L185.8 288L180 287L185.8 286L187 280Z' fill='%23FBBF24' fill-opacity='0.65'/%3E%3C!-- Sparkle 4 at (60, 340) ---%3E%3Cpath d='M65 340L66 344L70 345L66 346L65 350L64 346L60 345L64 344L65 340Z' fill='%23FBBF24' fill-opacity='0.55'/%3E%3C!-- Sparkle 5 at (350, 320) ---%3E%3Cpath d='M358 320L359.5 326.5L366 328L359.5 329.5L358 336L356.5 329.5L350 328L356.5 326.5L358 320Z' fill='%23FBBF24' fill-opacity='0.7'/%3E%3C!-- Sparkle 6 at (220, 140) ---%3E%3Cpath d='M225 140L226 144L230 145L226 146L225 150L224 146L220 145L224 144L225 140Z' fill='%23FCD34D' fill-opacity='0.6'/%3E%3C!-- Ribbon curl at (220, 60) ---%3E%3Cpath d='M202 78C202 78 210 62 220 70C230 78 238 62 238 62' stroke='%23FB7185' stroke-width='2.5' stroke-linecap='round' fill='none' stroke-opacity='0.5'/%3E%3C!-- Ribbon curl at (80, 260) ---%3E%3Cpath d='M65 275C65 275 73 262 82 268C91 274 98 261 98 261' stroke='%23FB7185' stroke-width='2' stroke-linecap='round' fill='none' stroke-opacity='0.4'/%3E%3C!-- Bow at (150, 180) ---%3E%3Cg transform='translate(150, 180) rotate(5)'%3E%3Cellipse cx='-7' cy='0' rx='8' ry='6' fill='%23FB7185' fill-opacity='0.4'/%3E%3Cellipse cx='7' cy='0' rx='8' ry='6' fill='%23FB7185' fill-opacity='0.4'/%3E%3Ccircle cx='0' cy='0' r='3' fill='%23F43F5E' fill-opacity='0.55'/%3E%3Cpath d='M-3 3L-8 12M3 3L8 12' stroke='%23F43F5E' stroke-width='1.5' stroke-linecap='round' stroke-opacity='0.45'/%3E%3C/g%3E%3C!-- Small bow at (380, 60) ---%3E%3Cg transform='translate(380, 60) rotate(-10)'%3E%3Cellipse cx='-5' cy='0' rx='6' ry='4' fill='%23FB7185' fill-opacity='0.35'/%3E%3Cellipse cx='5' cy='0' rx='6' ry='4' fill='%23FB7185' fill-opacity='0.35'/%3E%3Ccircle cx='0' cy='0' r='2' fill='%23F43F5E' fill-opacity='0.5'/%3E%3C/g%3E%3C/svg%3E")
  background-size: 400px 400px
  background-repeat: repeat
</style>
