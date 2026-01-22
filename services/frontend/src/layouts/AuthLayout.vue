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
  max-width: 400px
  padding: 24px
</style>
