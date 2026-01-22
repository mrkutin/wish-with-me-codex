<template>
  <q-page class="flex flex-center">
    <div class="text-center">
      <div class="text-h1 text-primary q-mb-md">404</div>
      <p class="text-h5 text-grey-7 q-mb-lg">{{ $t('errors.notFound') }}</p>
      <q-btn
        color="primary"
        :label="$t('common.back')"
        @click="$router.push('/')"
      />
    </div>
  </q-page>
</template>

<script setup lang="ts">
// 404 Page
</script>
