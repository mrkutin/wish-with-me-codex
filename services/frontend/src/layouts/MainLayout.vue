<template>
  <q-layout view="lHh Lpr lFf" class="main-layout">
    <!-- Skip link for keyboard navigation -->
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <!-- Offline banner at very top -->
    <OfflineBanner />

    <q-header class="main-header" elevated>
      <q-toolbar class="main-toolbar">
        <q-btn
          flat
          dense
          round
          icon="menu"
          aria-label="Menu"
          class="drawer-toggle"
          @click="toggleLeftDrawer"
        />

        <q-toolbar-title class="app-title">
          <router-link :to="{ name: 'home' }" class="app-title-link">
            <q-icon name="card_giftcard" size="24px" class="app-logo-icon" />
            <span>{{ $t('common.appName') }}</span>
          </router-link>
        </q-toolbar-title>

        <!-- Sync status indicator -->
        <SyncStatus v-if="authStore.isAuthenticated" class="toolbar-item" />

        <q-btn
          v-if="authStore.isAuthenticated"
          flat
          dense
          no-caps
          class="user-menu-btn"
          aria-label="Account menu"
          aria-haspopup="menu"
        >
          <q-avatar size="32px" class="user-avatar">
            <img v-if="authStore.user?.avatar_base64 && !isPlaceholderAvatar(authStore.user.avatar_base64)" :src="authStore.user.avatar_base64" alt="Avatar" />
            <q-icon v-else name="person" size="20px" />
          </q-avatar>
          <q-icon name="arrow_drop_down" size="20px" class="q-ml-xs" />
          <q-menu anchor="top right" self="top right" class="user-menu">
            <q-list>
              <q-item clickable v-close-popup :to="{ name: 'profile' }">
                <q-item-section avatar>
                  <q-icon name="person" size="20px" color="primary" />
                </q-item-section>
                <q-item-section>{{ $t('profile.title') }}</q-item-section>
              </q-item>
              <q-item clickable v-close-popup :to="{ name: 'settings' }">
                <q-item-section avatar>
                  <q-icon name="settings" size="20px" color="primary" />
                </q-item-section>
                <q-item-section>{{ $t('profile.settings') }}</q-item-section>
              </q-item>
              <q-separator />
              <q-item clickable v-close-popup @click="handleLogout" class="logout-item">
                <q-item-section avatar>
                  <q-icon name="logout" size="20px" color="negative" />
                </q-item-section>
                <q-item-section class="text-negative">{{ $t('auth.logout') }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
        <q-btn
          v-else
          flat
          no-caps
          :label="$t('auth.login')"
          :to="{ name: 'login' }"
          class="login-btn"
        />
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="leftDrawerOpen"
      show-if-above
      bordered
      class="main-drawer"
    >
      <div class="drawer-content">
        <q-list class="drawer-nav">
          <q-item-label header class="drawer-header">
            <router-link :to="{ name: 'home' }" class="drawer-header-link">
              <q-icon name="card_giftcard" size="24px" class="drawer-logo-icon" />
              <span>{{ $t('common.appName') }}</span>
            </router-link>
          </q-item-label>

          <q-item
            v-if="authStore.isAuthenticated"
            clickable
            :to="{ name: 'wishlists' }"
            class="nav-item"
            active-class="nav-item--active"
          >
            <q-item-section avatar>
              <q-icon name="checklist" size="24px" color="primary" />
            </q-item-section>
            <q-item-section>
              {{ $t('wishlists.title') }}
            </q-item-section>
          </q-item>

          <q-item
            v-if="authStore.isAuthenticated"
            clickable
            :to="{ name: 'profile' }"
            class="nav-item"
            active-class="nav-item--active"
          >
            <q-item-section avatar>
              <q-icon name="person" size="24px" color="primary" />
            </q-item-section>
            <q-item-section>
              {{ $t('profile.title') }}
            </q-item-section>
          </q-item>

          <q-item
            v-if="authStore.isAuthenticated"
            clickable
            :to="{ name: 'settings' }"
            class="nav-item"
            active-class="nav-item--active"
          >
            <q-item-section avatar>
              <q-icon name="settings" size="24px" color="primary" />
            </q-item-section>
            <q-item-section>
              {{ $t('profile.settings') }}
            </q-item-section>
          </q-item>
        </q-list>

        <!-- Logout at bottom of drawer -->
        <q-list v-if="authStore.isAuthenticated" class="drawer-footer">
          <q-separator />
          <q-item clickable @click="handleLogout" class="nav-item logout-item">
            <q-item-section avatar>
              <q-icon name="logout" size="24px" color="negative" />
            </q-item-section>
            <q-item-section class="text-negative">
              {{ $t('auth.logout') }}
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </q-drawer>

    <q-page-container class="page-container-main">
      <div class="page-layout-wrapper">
        <BackgroundDecorations />
        <main id="main-content" class="main-content">
          <router-view />
        </main>
      </div>
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
import OfflineBanner from '@/components/OfflineBanner.vue';
import SyncStatus from '@/components/SyncStatus.vue';
import AppInstallPrompt from '@/components/AppInstallPrompt.vue';
import BackgroundDecorations from '@/components/BackgroundDecorations.vue';

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

// Watch for auth changes to cleanup sync on logout
// Note: initializeSync is handled by useSync composable in SyncStatus component
watch(() => authStore.isAuthenticated, async (isAuth) => {
  if (!isAuth) {
    await cleanupSync();
  }
});

function isPlaceholderAvatar(avatar: string): boolean {
  // Check if avatar is the default placeholder SVG (contains "?" text element)
  return avatar.includes('PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiM2MzY2ZjEiLz48dGV4dCB4PSI1MCIgeT0iNTUiIGZvbnQtc2l6ZT0iNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+PzwvdGV4dD48L3N2Zz4=');
}
</script>

<style scoped lang="sass">
.main-header
  background: var(--bg-primary)
  color: var(--text-primary)
  border-bottom: 1px solid var(--border-default)

.main-toolbar
  min-height: 56px
  padding: 0 var(--space-4)
  max-width: 1440px
  margin: 0 auto
  width: 100%

.drawer-toggle
  color: var(--text-secondary)

  &:hover
    color: var(--text-primary)

.app-title
  font-weight: 700
  font-size: var(--text-h4)
  letter-spacing: -0.01em

.app-title-link
  display: flex
  align-items: center
  gap: var(--space-2)
  color: var(--primary)
  text-decoration: none

  &:hover
    opacity: 0.8

.app-logo-icon
  color: var(--primary)

.toolbar-item
  margin-right: var(--space-2)

.user-menu-btn
  padding: var(--space-1) var(--space-2)
  border-radius: var(--radius-full)

  &:hover
    background: var(--bg-tertiary)

.user-avatar
  background: rgba(79, 70, 229, 0.1)
  color: var(--primary)
  border: none
  box-shadow: none

.user-menu
  min-width: 200px
  margin-top: var(--space-2)

  .q-item
    min-height: 48px
    padding: var(--space-2) var(--space-4)
    border-radius: var(--radius-md)
    margin: var(--space-1) var(--space-2)

.login-btn
  font-weight: 500
  color: var(--primary)

.main-drawer
  background: var(--bg-primary)
  border-right-color: var(--border-default)

.drawer-content
  display: flex
  flex-direction: column
  height: 100%

.drawer-header
  font-weight: 700
  font-size: var(--text-h4)
  padding: var(--space-6) var(--space-4) var(--space-4)

.drawer-header-link
  display: flex
  align-items: center
  gap: var(--space-2)
  color: var(--primary)
  text-decoration: none

  &:hover
    opacity: 0.8

.drawer-logo-icon
  color: var(--primary)

.drawer-nav
  flex: 1

.nav-item
  min-height: 48px
  padding: var(--space-2) var(--space-4)
  margin: var(--space-1) var(--space-2)
  border-radius: var(--radius-md)
  color: var(--text-secondary)
  transition: background-color var(--duration-fast), color var(--duration-fast)

  &:hover
    background: var(--bg-tertiary)
    color: var(--text-primary)

  &--active
    background: rgba(79, 70, 229, 0.1)
    color: var(--primary)

    .q-icon
      color: var(--primary)

.drawer-footer
  margin-top: auto
  padding-bottom: var(--space-2)

.logout-item
  &:hover
    background: rgba(220, 38, 38, 0.08)

.page-container-main
  background: var(--bg-secondary)

.page-layout-wrapper
  position: relative
  min-height: 100vh
  background: var(--bg-secondary)

.main-content
  position: relative
  z-index: 10

.skip-link
  position: absolute
  top: -50px
  left: var(--space-4)
  background: var(--primary)
  color: white
  padding: var(--space-2) var(--space-4)
  z-index: 9999
  text-decoration: none
  border-radius: var(--radius-md)
  font-weight: 500
  transition: top var(--duration-normal)

  &:focus
    top: var(--space-4)
    outline: 2px solid white
    outline-offset: 2px

// Dark mode adjustments
.body--dark
  .main-header
    background: var(--bg-secondary)
    border-bottom-color: var(--border-default)

  .main-drawer
    background: var(--bg-secondary)

  .user-avatar
    background: rgba(79, 70, 229, 0.2)
</style>
