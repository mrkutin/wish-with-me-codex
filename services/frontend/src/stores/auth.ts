import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { LocalStorage } from 'quasar';
import { api } from '@/boot/axios';
import type { User } from '@/types/user';
import type { AuthResponse, TokenResponse, LoginRequest, RegisterRequest } from '@/types/api';

const REFRESH_TOKEN_KEY = 'refresh_token';

// API version to use (v2 = CouchDB, v1 = PostgreSQL legacy)
const API_VERSION = 'v2';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const accessToken = ref<string | null>(null);
  const refreshTokenValue = ref<string | null>(null);
  const isLoading = ref(false);

  const isAuthenticated = computed(() => !!user.value && !!accessToken.value);

  // Get user ID (handles both CouchDB _id and PostgreSQL id formats)
  const userId = computed(() => {
    if (!user.value) return null;
    // CouchDB uses _id, PostgreSQL uses id
    return (user.value as { _id?: string; id?: string })._id || user.value.id;
  });

  async function initializeAuth(): Promise<void> {
    const storedRefreshToken = LocalStorage.getItem<string>(REFRESH_TOKEN_KEY);
    if (storedRefreshToken) {
      refreshTokenValue.value = storedRefreshToken;
      try {
        await refreshToken();
      } catch {
        // Refresh failed, clear stored token
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
    // v2 returns user in auth response, but we can also fetch via /users/me
    // For now, keep using v1 endpoint until we create v2 users endpoint
    const response = await api.get<User>('/api/v1/users/me');
    user.value = response.data;
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
   * Used when we have tokens from URL params but no user data yet.
   */
  async function setTokensFromOAuth(tokens: {
    access_token: string;
    refresh_token: string;
  }): Promise<void> {
    accessToken.value = tokens.access_token;
    refreshTokenValue.value = tokens.refresh_token;
    LocalStorage.set(REFRESH_TOKEN_KEY, tokens.refresh_token);

    // Fetch user data with the access token
    await fetchCurrentUser();
  }

  function clearAuth(): void {
    user.value = null;
    accessToken.value = null;
    refreshTokenValue.value = null;
    LocalStorage.remove(REFRESH_TOKEN_KEY);
  }

  /**
   * Get the current access token.
   * Used by SSE composable since EventSource doesn't support headers.
   */
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
