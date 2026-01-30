import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { LocalStorage } from 'quasar';
import { api } from '@/boot/axios';
import type { User } from '@/types/user';
import type { AuthResponse, TokenResponse, LoginRequest, RegisterRequest } from '@/types/api';

const REFRESH_TOKEN_KEY = 'refresh_token';

// API version - v2 uses CouchDB for all operations
const API_VERSION = 'v2';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const accessToken = ref<string | null>(null);
  const refreshTokenValue = ref<string | null>(null);
  const isLoading = ref(false);

  const isAuthenticated = computed(() => !!user.value && !!accessToken.value);

  // Get user ID (CouchDB uses _id)
  const userId = computed(() => {
    if (!user.value) return null;
    return (user.value as { _id?: string; id?: string })._id || user.value.id;
  });

  async function initializeAuth(): Promise<void> {
    const storedRefreshToken = LocalStorage.getItem<string>(REFRESH_TOKEN_KEY);
    if (storedRefreshToken) {
      refreshTokenValue.value = storedRefreshToken;
      try {
        await refreshToken();
      } catch {
        clearAuth();
      }
    }
  }

  async function login(email: string, password: string): Promise<void> {
    isLoading.value = true;
    try {
      const response = await api.post<AuthResponse>(`/api/${API_VERSION}/auth/login`, {
        email,
        password,
      } as LoginRequest);

      setAuth(response.data);
    } finally {
      isLoading.value = false;
    }
  }

  async function register(data: RegisterRequest): Promise<void> {
    isLoading.value = true;
    try {
      const response = await api.post<AuthResponse>(`/api/${API_VERSION}/auth/register`, data);
      setAuth(response.data);
    } finally {
      isLoading.value = false;
    }
  }

  async function refreshToken(): Promise<void> {
    if (!refreshTokenValue.value) {
      throw new Error('No refresh token');
    }

    const response = await api.post<TokenResponse>(`/api/${API_VERSION}/auth/refresh`, {
      refresh_token: refreshTokenValue.value,
    });

    accessToken.value = response.data.access_token;
    refreshTokenValue.value = response.data.refresh_token;
    LocalStorage.set(REFRESH_TOKEN_KEY, response.data.refresh_token);

    // Fetch user data if not already loaded
    if (!user.value) {
      await fetchCurrentUser();
    }
  }

  async function fetchCurrentUser(): Promise<void> {
    // User data is returned in auth response, but we can also fetch via sync
    // For now, user info is set from auth response
    // This function is kept for compatibility with OAuth callback
    const response = await api.get<TokenResponse>(`/api/${API_VERSION}/auth/refresh`, {
      params: { refresh_token: refreshTokenValue.value }
    });
    // User comes from auth response
  }

  async function logout(): Promise<void> {
    if (refreshTokenValue.value) {
      try {
        await api.post(`/api/${API_VERSION}/auth/logout`, {
          refresh_token: refreshTokenValue.value,
        });
      } catch {
        // Ignore logout errors
      }
    }
    clearAuth();
  }

  function setAuth(data: AuthResponse): void {
    user.value = data.user;
    accessToken.value = data.access_token;
    refreshTokenValue.value = data.refresh_token;
    LocalStorage.set(REFRESH_TOKEN_KEY, data.refresh_token);
  }

  /**
   * Set tokens from OAuth callback and fetch user data.
   * OAuth still uses v1 endpoint for provider integration.
   */
  async function setTokensFromOAuth(tokens: {
    access_token: string;
    refresh_token: string;
  }): Promise<void> {
    accessToken.value = tokens.access_token;
    refreshTokenValue.value = tokens.refresh_token;
    LocalStorage.set(REFRESH_TOKEN_KEY, tokens.refresh_token);

    // Refresh to get user data
    await refreshToken();
  }

  function clearAuth(): void {
    user.value = null;
    accessToken.value = null;
    refreshTokenValue.value = null;
    LocalStorage.remove(REFRESH_TOKEN_KEY);
  }

  function getAccessToken(): string | null {
    return accessToken.value;
  }

  return {
    user,
    userId,
    accessToken,
    isAuthenticated,
    isLoading,
    initializeAuth,
    login,
    register,
    refreshToken,
    logout,
    fetchCurrentUser,
    getAccessToken,
    setTokensFromOAuth,
  };
});
