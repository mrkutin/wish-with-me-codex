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
        <div v-if="connectedAccounts.length === 0" class="text-grey">
          No connected accounts
        </div>
        <q-list v-else>
          <q-item v-for="account in connectedAccounts" :key="account.provider">
            <q-item-section avatar>
              <q-icon :name="getProviderIcon(account.provider)" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ account.provider }}</q-item-label>
              <q-item-label caption>{{ account.email }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '@/boot/axios';
import type { ConnectedAccount } from '@/types/user';

const { locale } = useI18n({ useScope: 'global' });
const connectedAccounts = ref<ConnectedAccount[]>([]);

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

function getProviderIcon(provider: string): string {
  const icons: Record<string, string> = {
    google: 'mdi-google',
    apple: 'mdi-apple',
    yandex: 'mdi-alpha-y-box',
    sber: 'mdi-bank',
  };
  return icons[provider] || 'mdi-account';
}

async function fetchConnectedAccounts() {
  try {
    const response = await api.get<{ accounts: ConnectedAccount[] }>(
      '/api/v1/users/me/connected-accounts'
    );
    connectedAccounts.value = response.data.accounts;
  } catch {
    // Handle error
  }
}

onMounted(fetchConnectedAccounts);
</script>
