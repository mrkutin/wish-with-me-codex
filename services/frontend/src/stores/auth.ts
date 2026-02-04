import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { LocalStorage } from 'quasar';
import { api } from '@/boot/axios';
import type { User } from '@/types/user';
import type { AuthResponse, TokenResponse, LoginRequest, RegisterRequest } from '@/types/api';
import { upsert, triggerSync, getCurrentUser as getPouchUser } from '@/services/pouchdb';
import type { UserDoc } from '@/services/pouchdb';

const REFRESH_TOKEN_KEY = 'refresh_token';

// API version - v2 uses CouchDB for all operations
const API_VERSION = 'v2';

// Refresh token 2 minutes before expiration to avoid 401 errors
const REFRESH_BUFFER_MS = 2 * 60 * 1000;

/**
 * Decode JWT payload without verification (client-side only).
 * Returns null if token is invalid.
 */
function decodeJwtPayload(token: string): { exp?: number } | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const accessToken = ref<string | null>(null);
  const refreshTokenValue = ref<string | null>(null);
  const isLoading = ref(false);

  // Timer for proactive token refresh
  let refreshTimerId: ReturnType<typeof setTimeout> | null = null;

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

  /**
   * Schedule proactive token refresh before expiration.
   */
  function scheduleTokenRefresh(token: string): void {
    // Clear any existing timer
    if (refreshTimerId) {
      clearTimeout(refreshTimerId);
      refreshTimerId = null;
    }

    const payload = decodeJwtPayload(token);
    if (!payload?.exp) return;

    // Calculate when to refresh (2 minutes before expiration)
    const expiresAt = payload.exp * 1000; // Convert to milliseconds
    const now = Date.now();
    const refreshIn = expiresAt - now - REFRESH_BUFFER_MS;

    if (refreshIn <= 0) {
      // Token already expired or about to expire, refresh immediately
      console.log('[Auth] Token expired or expiring soon, refreshing now');
      refreshToken().catch(() => clearAuth());
      return;
    }

    console.log(`[Auth] Scheduling token refresh in ${Math.round(refreshIn / 1000)}s`);
    refreshTimerId = setTimeout(async () => {
      try {
        console.log('[Auth] Proactive token refresh');
        await refreshToken();
      } catch (error) {
        console.error('[Auth] Proactive refresh failed:', error);
        clearAuth();
      }
    }, refreshIn);
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

    // Schedule next proactive refresh
    scheduleTokenRefresh(response.data.access_token);

    // Fetch user data if not already loaded
    if (!user.value) {
      await fetchCurrentUser();
    }
  }

  async function fetchCurrentUser(): Promise<void> {
    // Fetch user data from /me endpoint using access token
    const response = await api.get<User>(`/api/${API_VERSION}/auth/me`);
    user.value = response.data;

    // Also save to PouchDB for offline-first sync
    // Convert User to UserDoc format
    const userDoc: UserDoc = {
      _id: response.data.id,
      type: 'user',
      email: response.data.email,
      name: response.data.name,
      avatar_base64: response.data.avatar_base64 || null,
      bio: response.data.bio || null,
      public_url_slug: response.data.public_url_slug || null,
      locale: response.data.locale || 'en',
      birthday: response.data.birthday || null,
      access: [response.data.id],
      created_at: response.data.created_at || new Date().toISOString(),
      updated_at: response.data.updated_at || new Date().toISOString(),
    };
    try {
      await upsert<UserDoc>(userDoc);
    } catch (e) {
      console.warn('[Auth] Failed to save user to PouchDB:', e);
    }
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

    // Schedule proactive token refresh
    scheduleTokenRefresh(data.access_token);
  }

  /**
   * Set tokens from OAuth callback and fetch user data.
   * OAuth tokens are already valid - no need to refresh immediately.
   */
  async function setTokensFromOAuth(tokens: {
    access_token: string;
    refresh_token: string;
  }): Promise<void> {
    accessToken.value = tokens.access_token;
    refreshTokenValue.value = tokens.refresh_token;
    LocalStorage.set(REFRESH_TOKEN_KEY, tokens.refresh_token);

    // Schedule proactive token refresh
    scheduleTokenRefresh(tokens.access_token);

    // Fetch user data using the access token
    await fetchCurrentUser();
  }

  function clearAuth(): void {
    // Clear proactive refresh timer
    if (refreshTimerId) {
      clearTimeout(refreshTimerId);
      refreshTimerId = null;
    }

    user.value = null;
    accessToken.value = null;
    refreshTokenValue.value = null;
    LocalStorage.remove(REFRESH_TOKEN_KEY);
  }

  function getAccessToken(): string | null {
    return accessToken.value;
  }

  /**
   * Update user profile via PouchDB (offline-first).
   * Changes are synced to server on next sync cycle.
   */
  async function updateUser(updates: {
    name?: string;
    bio?: string | null;
    public_url_slug?: string | null;
    birthday?: string | null;
    avatar_base64?: string | null;
    locale?: string;
  }): Promise<void> {
    if (!user.value) {
      throw new Error('No user logged in');
    }

    const currentUserId = (user.value as { _id?: string; id?: string })._id || user.value.id;

    // Get current user doc from PouchDB
    let userDoc = await getPouchUser(currentUserId);
    if (!userDoc) {
      // Create user doc if it doesn't exist (shouldn't happen normally)
      userDoc = {
        _id: currentUserId,
        type: 'user',
        email: user.value.email,
        name: user.value.name,
        avatar_base64: user.value.avatar_base64 || null,
        bio: user.value.bio || null,
        public_url_slug: user.value.public_url_slug || null,
        locale: user.value.locale || 'en',
        birthday: user.value.birthday || null,
        access: [currentUserId],
        created_at: user.value.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    }

    // Apply updates
    const updatedDoc: UserDoc = {
      ...userDoc,
      ...updates,
      updated_at: new Date().toISOString(),
    };

    // Save to PouchDB
    await upsert<UserDoc>(updatedDoc);

    // Update local state immediately for responsive UI
    user.value = {
      ...user.value,
      ...updates,
      updated_at: updatedDoc.updated_at,
    } as User;

    // Trigger sync to push changes to server
    await triggerSync();
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
    updateUser,
  };
});
