<template>
  <q-page padding>
    <h1 class="text-h5 q-mb-md">{{ $t('profile.settings') }}</h1>

    <q-card>
      <q-card-section>
        <div class="text-subtitle1 q-mb-md">{{ $t('profile.language') }}</div>
        <q-select
          v-model="currentLocale"
          :options="localeOptions"
          outlined
          emit-value
          map-options
        />
      </q-card-section>

      <q-separator />

      <q-card-section>
        <div class="text-subtitle1 q-mb-md">{{ $t('profile.connectedAccounts') }}</div>

        <div v-if="oauthError" class="text-negative q-mb-md">
          {{ oauthError }}
        </div>

        <q-list separator>
          <q-item v-for="provider in availableProviders" :key="provider">
            <q-item-section avatar>
              <q-icon :name="getProviderIcon(provider)" :style="{ color: getProviderColor(provider) }" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ getProviderDisplayName(provider) }}</q-item-label>
              <q-item-label caption v-if="getConnectedAccount(provider)">
                {{ getConnectedAccount(provider)?.email || $t('oauth.connected') }}
              </q-item-label>
              <q-item-label caption v-else class="text-grey">
                {{ $t('oauth.notConnected') }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-btn
                v-if="isProviderConnected(provider)"
                flat
                color="negative"
                :label="$t('oauth.disconnect')"
                :loading="isLoading"
                :disable="!canUnlinkAccount"
                @click="handleUnlink(provider)"
              />
              <q-btn
                v-else
                flat
                color="primary"
                :label="$t('oauth.connect')"
                @click="handleLink(provider)"
              />
            </q-item-section>
          </q-item>
        </q-list>

        <div v-if="!canUnlinkAccount && connectedAccounts.length === 1" class="text-caption text-grey q-mt-md">
          {{ $t('oauth.cantUnlinkLast') }}
        </div>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useOAuth } from '@/composables/useOAuth';
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
