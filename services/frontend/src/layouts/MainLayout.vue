<template>
  <q-layout view="lHh Lpr lFf">
    <!-- Offline banner at very top -->
    <OfflineBanner />

    <q-header elevated>
      <q-toolbar>
        <q-btn
          flat
          dense
          round
          icon="menu"
          aria-label="Menu"
          @click="toggleLeftDrawer"
        />

        <q-toolbar-title>
          {{ $t('common.appName') }}
        </q-toolbar-title>

        <!-- Sync status indicator -->
        <SyncStatus v-if="authStore.isAuthenticated" class="q-mr-xs" />

        <NotificationBell v-if="authStore.isAuthenticated" class="q-mr-sm" />

        <q-btn
          v-if="authStore.isAuthenticated"
          flat
          dense
          no-caps
          class="q-px-sm"
          aria-label="Account menu"
          aria-haspopup="menu"
        >
          <q-avatar size="36px" class="q-mr-xs">
            <img v-if="authStore.user?.avatar_base64 && !isPlaceholderAvatar(authStore.user.avatar_base64)" :src="authStore.user.avatar_base64" alt="Avatar" />
            <q-icon v-else name="person" size="24px" />
          </q-avatar>
          <q-icon name="arrow_drop_down" size="20px" />
          <q-menu>
            <q-list style="min-width: 180px">
              <q-item clickable v-close-popup :to="{ name: 'profile' }">
                <q-item-section avatar>
                  <q-icon name="person" />
                </q-item-section>
                <q-item-section>{{ $t('profile.title') }}</q-item-section>
              </q-item>
              <q-item clickable v-close-popup :to="{ name: 'settings' }">
                <q-item-section avatar>
                  <q-icon name="settings" />
                </q-item-section>
                <q-item-section>{{ $t('profile.settings') }}</q-item-section>
              </q-item>
              <q-separator />
              <q-item clickable v-close-popup @click="handleLogout">
                <q-item-section avatar>
                  <q-icon name="logout" color="negative" />
                </q-item-section>
                <q-item-section class="text-negative">{{ $t('auth.logout') }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
        <q-btn
          v-else
          flat
          :label="$t('auth.login')"
          :to="{ name: 'login' }"
        />
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="leftDrawerOpen"
      show-if-above
      bordered
      class="column"
    >
      <q-list class="col">
        <q-item-label header>
          {{ $t('common.appName') }}
        </q-item-label>

        <q-item
          v-if="authStore.isAuthenticated"
          clickable
          :to="{ name: 'wishlists' }"
        >
          <q-item-section avatar>
            <q-icon name="list" />
          </q-item-section>
          <q-item-section>
            {{ $t('wishlists.title') }}
          </q-item-section>
        </q-item>

        <q-item
          v-if="authStore.isAuthenticated"
          clickable
          :to="{ name: 'profile' }"
        >
          <q-item-section avatar>
            <q-icon name="person" />
          </q-item-section>
          <q-item-section>
            {{ $t('profile.title') }}
          </q-item-section>
        </q-item>

        <q-item
          v-if="authStore.isAuthenticated"
          clickable
          :to="{ name: 'settings' }"
        >
          <q-item-section avatar>
            <q-icon name="settings" />
          </q-item-section>
          <q-item-section>
            {{ $t('profile.settings') }}
          </q-item-section>
        </q-item>
      </q-list>

      <!-- Logout at bottom of drawer -->
      <q-list v-if="authStore.isAuthenticated" class="q-mt-auto">
        <q-separator />
        <q-item clickable @click="handleLogout">
          <q-item-section avatar>
            <q-icon name="logout" color="negative" />
          </q-item-section>
          <q-item-section class="text-negative">
            {{ $t('auth.logout') }}
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>

    <!-- PWA install prompt -->
    <AppInstallPrompt />
  </q-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { initializeSync, cleanupSync } from '@/composables/useSync';
import NotificationBell from '@/components/NotificationBell.vue';
import OfflineBanner from '@/components/OfflineBanner.vue';
import SyncStatus from '@/components/SyncStatus.vue';
import AppInstallPrompt from '@/components/AppInstallPrompt.vue';

const authStore = useAuthStore();
const router = useRouter();
const leftDrawerOpen = ref(false);

function toggleLeftDrawer() {
  leftDrawerOpen.value = !leftDrawerOpen.value;
}

async function handleLogout() {
  // Cleanup sync before logout
  await cleanupSync();
  await authStore.logout();
  router.push({ name: 'login' });
}

// Initialize sync when authenticated
onMounted(() => {
  if (authStore.isAuthenticated) {
    initializeSync();
  }
});

// Watch for auth changes to init/cleanup sync
watch(() => authStore.isAuthenticated, async (isAuth) => {
  if (isAuth) {
    await initializeSync();
  } else {
    await cleanupSync();
  }
});

function isPlaceholderAvatar(avatar: string): boolean {
  // Check if avatar is the default placeholder SVG (contains "?" text element)
  return avatar.includes('PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiM2MzY2ZjEiLz48dGV4dCB4PSI1MCIgeT0iNTUiIGZvbnQtc2l6ZT0iNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+PzwvdGV4dD48L3N2Zz4=');
}
</script>
