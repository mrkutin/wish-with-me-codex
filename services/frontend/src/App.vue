<template>
  <router-view />
</template>

<script setup lang="ts">
import { useRealtimeSync } from '@/composables/useRealtimeSync';

// Initialize SSE connection for real-time updates
// This connects when user is authenticated and online
useRealtimeSync();
</script>
