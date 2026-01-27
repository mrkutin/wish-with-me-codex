<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <q-page class="flex flex-center">
        <div class="auth-container">
          <div class="text-center q-mb-lg">
            <div class="text-h4 text-primary">{{ $t('common.appName') }}</div>
          </div>
          <router-view />
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
// Auth layout - centered content for login/register pages
</script>

<style lang="sass" scoped>
.auth-container
  width: 100%
  max-width: 420px
  padding: 16px

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
