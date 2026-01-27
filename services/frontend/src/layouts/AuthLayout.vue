<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container class="auth-page-container">
      <div class="page-layout-wrapper">
        <BackgroundDecorations />
        <q-page class="flex flex-center auth-page">
          <div class="auth-container">
            <div class="text-center q-mb-lg">
              <router-link :to="{ name: 'index' }" class="auth-logo-link">
                <div class="text-h4 text-primary">{{ $t('common.appName') }}</div>
              </router-link>
            </div>
            <router-view />
          </div>
        </q-page>
      </div>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import BackgroundDecorations from '@/components/BackgroundDecorations.vue';
// Auth layout - centered content for login/register pages
</script>

<style lang="sass" scoped>
.auth-page-container
  background: var(--bg-secondary)

.page-layout-wrapper
  position: relative
  min-height: 100vh
  background: var(--bg-secondary)

.auth-page
  position: relative
  z-index: 10

.auth-logo-link
  text-decoration: none

  &:hover
    opacity: 0.8

.auth-container
  width: 100%
  max-width: 420px
  padding: 16px
  position: relative
  z-index: 10

  @media (min-width: 600px)
    max-width: 500px
    padding: 24px

  @media (min-width: 1024px)
    max-width: 580px

  @media (min-width: 1440px)
    max-width: 680px

  @media (min-width: 1680px)
    max-width: 780px
</style>
