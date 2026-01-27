<template>
  <q-page class="settings-page">
    <div class="page-container">
      <h1 class="page-title">{{ $t('profile.settings') }}</h1>

      <!-- Language Settings -->
      <div class="settings-card">
        <div class="settings-section">
          <div class="section-title">{{ $t('profile.language') }}</div>
          <q-select
            v-model="currentLocale"
            :options="localeOptions"
            outlined
            emit-value
            map-options
            class="form-field"
          />
        </div>
      </div>

      <!-- Connected Accounts -->
      <div class="settings-card">
        <div class="settings-section">
          <div class="section-title">{{ $t('profile.connectedAccounts') }}</div>

          <div v-if="oauthError" class="error-message">
            <q-icon name="error_outline" size="20px" />
            <span>{{ oauthError }}</span>
          </div>

          <div class="accounts-list">
            <div v-for="provider in availableProviders" :key="provider" class="account-item">
              <div class="account-info">
                <q-icon :name="getProviderIcon(provider)" :style="{ color: getProviderColor(provider) }" size="24px" />
                <div class="account-details">
                  <div class="account-name">{{ getProviderDisplayName(provider) }}</div>
                  <div class="account-status" :class="{ connected: isProviderConnected(provider) }">
                    {{ getConnectedAccount(provider)?.email || (isProviderConnected(provider) ? $t('oauth.connected') : $t('oauth.notConnected')) }}
                  </div>
                </div>
              </div>
              <q-btn
                v-if="isProviderConnected(provider)"
                flat
                color="negative"
                :label="$t('oauth.disconnect')"
                :loading="isLoading"
                :disable="!canUnlinkAccount"
                @click="handleUnlink(provider)"
                no-caps
                class="account-btn"
              />
              <q-btn
                v-else
                flat
                color="primary"
                :label="$t('oauth.connect')"
                @click="handleLink(provider)"
                no-caps
                class="account-btn"
              />
            </div>
          </div>

          <div v-if="!canUnlinkAccount && connectedAccounts.length === 1" class="hint-text">
            {{ $t('oauth.cantUnlinkLast') }}
          </div>
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useOAuth } from '@/composables/useOAuth';
import { saveLocale, type SupportedLocale } from '@/boot/i18n';
import type { OAuthProvider } from '@/composables/useOAuth';
import type { ConnectedAccount } from '@/types/user';

const { locale } = useI18n({ useScope: 'global' });

const {
  availableProviders,
  connectedAccounts,
  isLoading,
  error: oauthError,
  canUnlinkAccount,
  fetchAvailableProviders,
  fetchConnectedAccounts,
  initiateOAuthLink,
  unlinkAccount,
  isProviderConnected,
  getProviderDisplayName,
  getProviderIcon,
  getProviderColor,
} = useOAuth();

const localeOptions = [
  { label: 'English', value: 'en' },
  { label: 'Русский', value: 'ru' },
];

const currentLocale = computed({
  get: () => locale.value,
  set: (val: string) => {
    locale.value = val;
    saveLocale(val as SupportedLocale);
  },
});

function getConnectedAccount(provider: OAuthProvider): ConnectedAccount | undefined {
  return connectedAccounts.value.find((acc) => acc.provider === provider);
}

async function handleLink(provider: OAuthProvider): Promise<void> {
  await initiateOAuthLink(provider);
}

async function handleUnlink(provider: OAuthProvider): Promise<void> {
  await unlinkAccount(provider);
}

onMounted(async () => {
  await Promise.all([fetchAvailableProviders(), fetchConnectedAccounts()]);
});
</script>

<style scoped lang="sass">
.settings-page
  min-height: 100%
  padding: var(--space-4)
  background: var(--bg-primary)

  @media (min-width: 600px)
    padding: var(--space-6)

.page-container
  max-width: 600px
  margin: 0 auto
  display: flex
  flex-direction: column
  gap: var(--space-6)

  @media (min-width: 1024px)
    max-width: 680px

  @media (min-width: 1440px)
    max-width: 720px

.page-title
  font-size: var(--text-h3)
  font-weight: 700
  color: var(--text-primary)
  margin: 0
  letter-spacing: -0.02em

  @media (min-width: 600px)
    font-size: var(--text-h2)

.settings-card
  background: var(--bg-primary)
  border-radius: var(--radius-xl)
  box-shadow: var(--shadow-lg)
  border: 1px solid var(--border-subtle)
  overflow: hidden
  position: relative

  // Gradient top border decoration
  &::before
    content: ''
    position: absolute
    top: 0
    left: 0
    right: 0
    height: 3px
    background: linear-gradient(90deg, var(--gift-coral-400) 0%, var(--gift-gold-400) 50%, var(--gift-coral-400) 100%)
    opacity: 0.6

.settings-section
  padding: var(--space-6)

  @media (min-width: 600px)
    padding: var(--space-8)

.section-title
  font-size: var(--text-body)
  font-weight: 600
  color: var(--text-primary)
  margin-bottom: var(--space-4)

.form-field
  margin-bottom: 0

.error-message
  display: flex
  align-items: center
  gap: var(--space-2)
  padding: var(--space-3) var(--space-4)
  background: rgba(220, 38, 38, 0.1)
  border-radius: var(--radius-md)
  color: #DC2626
  font-size: var(--text-body-sm)
  margin-bottom: var(--space-4)

.accounts-list
  display: flex
  flex-direction: column
  gap: var(--space-3)

.account-item
  display: flex
  align-items: center
  justify-content: space-between
  padding: var(--space-4)
  background: var(--bg-secondary)
  border-radius: var(--radius-lg)
  gap: var(--space-3)

.account-info
  display: flex
  align-items: center
  gap: var(--space-3)
  min-width: 0

.account-details
  min-width: 0

.account-name
  font-size: var(--text-body)
  font-weight: 500
  color: var(--text-primary)

.account-status
  font-size: var(--text-body-sm)
  color: var(--text-tertiary)

  &.connected
    color: var(--text-secondary)

.account-btn
  flex-shrink: 0

.hint-text
  font-size: var(--text-body-sm)
  color: var(--text-tertiary)
  margin-top: var(--space-4)

// Dark mode
.body--dark
  .settings-card
    background: var(--bg-secondary)
    border-color: var(--border-default)

  .account-item
    background: var(--bg-tertiary)
</style>
