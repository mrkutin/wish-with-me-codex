import { ref, computed } from 'vue';
import { api } from '@/boot/axios';
import type { ConnectedAccount } from '@/types/user';

export type OAuthProvider = 'google' | 'apple' | 'yandex' | 'sber';

export interface OAuthProvidersResponse {
  providers: OAuthProvider[];
}

export interface ConnectedAccountsResponse {
  accounts: ConnectedAccount[];
  has_password: boolean;
}

const availableProviders = ref<OAuthProvider[]>([]);
const connectedAccounts = ref<ConnectedAccount[]>([]);
const hasPassword = ref(true);
const isLoading = ref(false);
const error = ref<string | null>(null);

export function useOAuth() {
  const canUnlinkAccount = computed(() => {
    // User can unlink if they have a password OR more than one social account
    return hasPassword.value || connectedAccounts.value.length > 1;
  });

  async function fetchAvailableProviders(): Promise<void> {
    try {
      const response = await api.get<OAuthProvidersResponse>('/api/v1/oauth/providers');
      availableProviders.value = response.data.providers;
    } catch {
      availableProviders.value = [];
    }
  }

  async function fetchConnectedAccounts(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await api.get<ConnectedAccountsResponse>('/api/v1/oauth/connected');
      connectedAccounts.value = response.data.accounts;
      hasPassword.value = response.data.has_password;
    } catch (err) {
      error.value = 'Failed to fetch connected accounts';
      connectedAccounts.value = [];
    } finally {
      isLoading.value = false;
    }
  }

  function initiateOAuthLogin(provider: OAuthProvider): void {
    // Redirect to backend OAuth authorize endpoint
    // The backend will redirect to the provider's auth page
    const baseUrl = import.meta.env.VITE_API_URL || '';
    window.location.href = `${baseUrl}/api/v1/oauth/${provider}/authorize`;
  }

  async function initiateOAuthLink(provider: OAuthProvider): Promise<void> {
    // Call authenticated endpoint to get the authorization URL
    // Then redirect to the OAuth provider
    try {
      const response = await api.post<{ authorization_url: string; state: string }>(
        `/api/v1/oauth/${provider}/link/initiate`
      );
      window.location.href = response.data.authorization_url;
    } catch (err) {
      error.value = 'Failed to initiate OAuth linking';
    }
  }

  async function unlinkAccount(provider: OAuthProvider): Promise<boolean> {
    isLoading.value = true;
    error.value = null;
    try {
      await api.delete(`/api/v1/oauth/${provider}/unlink`);
      await fetchConnectedAccounts();
      return true;
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      error.value = message || 'Failed to unlink account';
      return false;
    } finally {
      isLoading.value = false;
    }
  }

  function isProviderConnected(provider: OAuthProvider): boolean {
    return connectedAccounts.value.some((acc) => acc.provider === provider);
  }

  function getProviderDisplayName(provider: OAuthProvider): string {
    const names: Record<OAuthProvider, string> = {
      google: 'Google',
      apple: 'Apple',
      yandex: 'Yandex',
      sber: 'Sber ID',
    };
    return names[provider] || provider;
  }

  function getProviderIcon(provider: OAuthProvider): string {
    const icons: Record<OAuthProvider, string> = {
      google: 'mdi-google',
      apple: 'mdi-apple',
      yandex: 'mdi-alpha-y-box',
      sber: 'mdi-bank',
    };
    return icons[provider] || 'mdi-account';
  }

  function getProviderColor(provider: OAuthProvider): string {
    const colors: Record<OAuthProvider, string> = {
      google: '#4285F4',
      apple: '#000000',
      yandex: '#FC3F1D',
      sber: '#21A038',
    };
    return colors[provider] || '#666666';
  }

  return {
    availableProviders,
    connectedAccounts,
    hasPassword,
    isLoading,
    error,
    canUnlinkAccount,
    fetchAvailableProviders,
    fetchConnectedAccounts,
    initiateOAuthLogin,
    initiateOAuthLink,
    unlinkAccount,
    isProviderConnected,
    getProviderDisplayName,
    getProviderIcon,
    getProviderColor,
  };
}
