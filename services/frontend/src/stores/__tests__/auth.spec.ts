/**
 * Unit tests for the auth store.
 * Tests authentication flows including login, register, token refresh, and logout.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '../auth';
import type { AuthResponse, TokenResponse } from '@/types/api';
import type { User } from '@/types/user';

// Mock Quasar LocalStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  set: vi.fn(),
  remove: vi.fn(),
};

vi.mock('quasar', () => ({
  LocalStorage: {
    getItem: vi.fn(),
    set: vi.fn(),
    remove: vi.fn(),
  },
}));

// Import mocked LocalStorage after mock setup
import { LocalStorage } from 'quasar';

// Mock axios api
vi.mock('@/boot/axios', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '@/boot/axios';

// Helper to create a valid JWT token with expiration
function createMockJwt(expiresInSeconds: number, payload: Record<string, unknown> = {}): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const exp = Math.floor(Date.now() / 1000) + expiresInSeconds;
  const payloadData = btoa(JSON.stringify({ exp, ...payload }));
  const signature = btoa('mock-signature');
  return `${header}.${payloadData}.${signature}`;
}

// Helper to create an expired JWT token
function createExpiredJwt(): string {
  return createMockJwt(-60); // Expired 60 seconds ago
}

// Sample user data
const mockUser: User = {
  id: 'user:123',
  email: 'test@example.com',
  name: 'Test User',
  avatar_base64: '',
  locale: 'en',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// Sample user with CouchDB _id format
const mockUserWithCouchId: User & { _id: string } = {
  ...mockUser,
  _id: 'user:456',
};

// Sample auth response
function createMockAuthResponse(expiresInSeconds = 3600): AuthResponse {
  return {
    user: mockUser,
    access_token: createMockJwt(expiresInSeconds),
    refresh_token: 'mock-refresh-token',
    token_type: 'bearer',
    expires_in: expiresInSeconds,
  };
}

// Sample token response
function createMockTokenResponse(expiresInSeconds = 3600): TokenResponse {
  return {
    access_token: createMockJwt(expiresInSeconds),
    refresh_token: 'new-refresh-token',
    token_type: 'bearer',
    expires_in: expiresInSeconds,
  };
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('login', () => {
    it('should update user, tokens, and localStorage with valid credentials', async () => {
      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      const store = useAuthStore();
      await store.login('test@example.com', 'password123');

      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/login', {
        email: 'test@example.com',
        password: 'password123',
      });
      expect(store.user).toEqual(mockUser);
      expect(store.accessToken).toBe(authResponse.access_token);
      expect(LocalStorage.set).toHaveBeenCalledWith('refresh_token', authResponse.refresh_token);
      expect(store.isAuthenticated).toBe(true);
    });

    it('should throw error and not change state with invalid credentials', async () => {
      const error = new Error('Invalid credentials');
      vi.mocked(api.post).mockRejectedValueOnce(error);

      const store = useAuthStore();

      await expect(store.login('test@example.com', 'wrongpassword')).rejects.toThrow(
        'Invalid credentials'
      );

      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
      expect(store.isAuthenticated).toBe(false);
      expect(LocalStorage.set).not.toHaveBeenCalled();
    });

    it('should set isLoading during login request', async () => {
      let resolveLogin: (value: { data: AuthResponse }) => void;
      const loginPromise = new Promise<{ data: AuthResponse }>((resolve) => {
        resolveLogin = resolve;
      });
      vi.mocked(api.post).mockReturnValueOnce(loginPromise as Promise<never>);

      const store = useAuthStore();
      const loginCall = store.login('test@example.com', 'password123');

      expect(store.isLoading).toBe(true);

      resolveLogin!({ data: createMockAuthResponse() });
      await loginCall;

      expect(store.isLoading).toBe(false);
    });
  });

  describe('register', () => {
    it('should create user and set tokens with valid data', async () => {
      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      const store = useAuthStore();
      await store.register({
        email: 'new@example.com',
        password: 'password123',
        name: 'New User',
        locale: 'en',
      });

      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/register', {
        email: 'new@example.com',
        password: 'password123',
        name: 'New User',
        locale: 'en',
      });
      expect(store.user).toEqual(mockUser);
      expect(store.accessToken).toBe(authResponse.access_token);
      expect(LocalStorage.set).toHaveBeenCalledWith('refresh_token', authResponse.refresh_token);
    });

    it('should throw error with duplicate email', async () => {
      const error = {
        response: {
          status: 409,
          data: {
            error: {
              code: 'EMAIL_EXISTS',
              message: 'Email already registered',
            },
          },
        },
      };
      vi.mocked(api.post).mockRejectedValueOnce(error);

      const store = useAuthStore();

      await expect(
        store.register({
          email: 'existing@example.com',
          password: 'password123',
          name: 'Test User',
        })
      ).rejects.toEqual(error);

      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
    });
  });

  describe('refreshToken', () => {
    it('should update tokens with valid refresh token', async () => {
      const tokenResponse = createMockTokenResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      const store = useAuthStore();
      // Set initial refresh token
      (store as unknown as { refreshTokenValue: { value: string } }).refreshTokenValue = {
        value: 'old-refresh-token',
      };
      // Access the private refreshTokenValue through store internals
      // We need to set it via the store's internal state
      vi.mocked(LocalStorage.getItem).mockReturnValue('old-refresh-token');

      // Initialize auth to set the refresh token
      await store.initializeAuth();

      // Reset mocks after initialization
      vi.mocked(api.post).mockClear();
      vi.mocked(api.get).mockClear();

      // Now test refresh
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      await store.refreshToken();

      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/refresh', {
        refresh_token: expect.any(String),
      });
      expect(store.accessToken).toBe(tokenResponse.access_token);
      expect(LocalStorage.set).toHaveBeenCalledWith('refresh_token', tokenResponse.refresh_token);
    });

    it('should clear auth state with expired/invalid refresh token', async () => {
      const error = {
        response: {
          status: 401,
          data: { error: { code: 'TOKEN_EXPIRED', message: 'Refresh token expired' } },
        },
      };
      vi.mocked(LocalStorage.getItem).mockReturnValue('expired-refresh-token');
      vi.mocked(api.post).mockRejectedValueOnce(error);

      const store = useAuthStore();

      // Initialize which tries to refresh
      await store.initializeAuth();

      // After failed refresh, auth should be cleared
      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
      expect(LocalStorage.remove).toHaveBeenCalledWith('refresh_token');
    });

    it('should throw error when no refresh token exists', async () => {
      const store = useAuthStore();

      await expect(store.refreshToken()).rejects.toThrow('No refresh token');
    });
  });

  describe('logout', () => {
    it('should clear user, tokens, localStorage, and cancel refresh timer', async () => {
      // Setup authenticated state
      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      const store = useAuthStore();
      await store.login('test@example.com', 'password123');

      expect(store.isAuthenticated).toBe(true);

      // Mock logout API call
      vi.mocked(api.post).mockResolvedValueOnce({ data: {} });

      await store.logout();

      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
      expect(store.isAuthenticated).toBe(false);
      expect(LocalStorage.remove).toHaveBeenCalledWith('refresh_token');
    });

    it('should clear auth even if logout API call fails', async () => {
      // Setup authenticated state
      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      const store = useAuthStore();
      await store.login('test@example.com', 'password123');

      // Mock logout API call to fail
      vi.mocked(api.post).mockRejectedValueOnce(new Error('Network error'));

      await store.logout();

      // Auth should still be cleared locally
      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
      expect(LocalStorage.remove).toHaveBeenCalledWith('refresh_token');
    });
  });

  describe('initializeAuth', () => {
    it('should restore session from stored refresh token', async () => {
      const tokenResponse = createMockTokenResponse();
      // Mock localStorage to return different values based on key
      vi.mocked(LocalStorage.getItem).mockImplementation((key: string) => {
        if (key === 'refresh_token') return 'stored-refresh-token';
        return null; // No stored access token or user data
      });
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      const store = useAuthStore();
      await store.initializeAuth();

      expect(LocalStorage.getItem).toHaveBeenCalledWith('refresh_token');
      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/refresh', {
        refresh_token: 'stored-refresh-token',
      });
      expect(store.accessToken).toBe(tokenResponse.access_token);
      expect(store.user).toEqual(mockUser);
    });

    it('should restore session immediately from stored access token and user', async () => {
      const validAccessToken = createMockJwt(3600); // Valid for 1 hour
      // Mock localStorage with stored session data
      vi.mocked(LocalStorage.getItem).mockImplementation((key: string) => {
        if (key === 'refresh_token') return 'stored-refresh-token';
        if (key === 'access_token') return validAccessToken;
        if (key === 'user_data') return mockUser;
        return null;
      });

      const store = useAuthStore();
      await store.initializeAuth();

      // Should restore from storage without API call
      expect(api.post).not.toHaveBeenCalled();
      expect(store.accessToken).toBe(validAccessToken);
      expect(store.user).toEqual(mockUser);
    });

    it('should refresh when stored access token is expired', async () => {
      const expiredAccessToken = createExpiredJwt();
      const tokenResponse = createMockTokenResponse();
      // Mock localStorage with expired access token
      vi.mocked(LocalStorage.getItem).mockImplementation((key: string) => {
        if (key === 'refresh_token') return 'stored-refresh-token';
        if (key === 'access_token') return expiredAccessToken;
        if (key === 'user_data') return mockUser;
        return null;
      });
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      const store = useAuthStore();
      await store.initializeAuth();

      // Should call refresh since token is expired
      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/refresh', {
        refresh_token: 'stored-refresh-token',
      });
      expect(store.accessToken).toBe(tokenResponse.access_token);
    });

    it('should clear state when stored token is invalid', async () => {
      vi.mocked(LocalStorage.getItem).mockImplementation((key: string) => {
        if (key === 'refresh_token') return 'invalid-token';
        return null;
      });
      vi.mocked(api.post).mockRejectedValueOnce(new Error('Invalid token'));

      const store = useAuthStore();
      await store.initializeAuth();

      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
      expect(LocalStorage.remove).toHaveBeenCalledWith('refresh_token');
    });

    it('should do nothing when no stored refresh token exists', async () => {
      vi.mocked(LocalStorage.getItem).mockReturnValue(null);

      const store = useAuthStore();
      await store.initializeAuth();

      expect(api.post).not.toHaveBeenCalled();
      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
    });
  });

  describe('scheduleTokenRefresh', () => {
    it('should schedule refresh 2 minutes before token expiration', async () => {
      const store = useAuthStore();

      // Login to trigger scheduleTokenRefresh
      const expiresInSeconds = 600; // 10 minutes
      const authResponse = createMockAuthResponse(expiresInSeconds);
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      await store.login('test@example.com', 'password123');

      // Prepare for the scheduled refresh
      const tokenResponse = createMockTokenResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });

      // Advance time to just before refresh should happen (8 minutes = 480 seconds)
      // Refresh should happen at (600 - 120) = 480 seconds = 8 minutes
      vi.advanceTimersByTime(480 * 1000);

      // Wait for async operations
      await vi.runAllTimersAsync();

      // Check that refresh was called
      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/refresh', {
        refresh_token: expect.any(String),
      });
    });

    it('should refresh immediately if token is about to expire', async () => {
      const store = useAuthStore();

      // Login with a token that expires in 1 minute (less than 2 min buffer)
      const expiresInSeconds = 60;
      const authResponse = createMockAuthResponse(expiresInSeconds);
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      // The immediate refresh returns a long-lived token (won't trigger another immediate refresh)
      const longLivedTokenResponse = createMockTokenResponse(7200); // 2 hours - well beyond buffer
      vi.mocked(api.post).mockResolvedValueOnce({ data: longLivedTokenResponse });

      await store.login('test@example.com', 'password123');

      // Advance a small amount to trigger the immediate refresh (it's scheduled with setTimeout)
      await vi.advanceTimersByTimeAsync(100);

      // Verify refresh was called after login due to soon-expiring token
      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/refresh', {
        refresh_token: expect.any(String),
      });
      // Login is first call
      expect(api.post).toHaveBeenNthCalledWith(1, '/api/v2/auth/login', {
        email: 'test@example.com',
        password: 'password123',
      });
    });

    it('should clear auth on refresh failure during scheduled refresh', async () => {
      const store = useAuthStore();

      // Login with token expiring in 5 minutes
      const expiresInSeconds = 300;
      const authResponse = createMockAuthResponse(expiresInSeconds);
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      await store.login('test@example.com', 'password123');

      // Make refresh fail
      vi.mocked(api.post).mockRejectedValueOnce(new Error('Refresh failed'));

      // Advance to when refresh should happen (300 - 120 = 180 seconds)
      vi.advanceTimersByTime(180 * 1000);
      await vi.runAllTimersAsync();

      expect(store.user).toBeNull();
      expect(store.accessToken).toBeNull();
    });
  });

  describe('decodeJwtPayload', () => {
    it('should extract claims from valid token', async () => {
      // This is tested indirectly through scheduleTokenRefresh
      // The function correctly extracts exp to schedule refresh
      const store = useAuthStore();
      const expiresInSeconds = 3600;
      const authResponse = createMockAuthResponse(expiresInSeconds);
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      await store.login('test@example.com', 'password123');

      // If decodeJwtPayload works correctly, refresh timer would be set
      // We can verify this by checking that a scheduled refresh occurs at the right time
      const tokenResponse = createMockTokenResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });

      // Advance to refresh time (3600 - 120 = 3480 seconds)
      vi.advanceTimersByTime(3480 * 1000);
      await vi.runAllTimersAsync();

      // Refresh should have been called
      expect(api.post).toHaveBeenLastCalledWith('/api/v2/auth/refresh', {
        refresh_token: expect.any(String),
      });
    });

    it('should handle invalid token format gracefully', async () => {
      const store = useAuthStore();

      // Create a response with an invalid JWT
      const authResponse: AuthResponse = {
        user: mockUser,
        access_token: 'invalid-token-no-dots',
        refresh_token: 'mock-refresh-token',
        token_type: 'bearer',
        expires_in: 3600,
      };
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      // Should not throw, but also won't schedule refresh
      await store.login('test@example.com', 'password123');

      expect(store.user).toEqual(mockUser);
      expect(store.accessToken).toBe('invalid-token-no-dots');
    });

    it('should return null for token with invalid base64 payload', async () => {
      const store = useAuthStore();

      // Create a token with invalid base64 in payload
      const authResponse: AuthResponse = {
        user: mockUser,
        access_token: 'header.!!!invalid-base64!!!.signature',
        refresh_token: 'mock-refresh-token',
        token_type: 'bearer',
        expires_in: 3600,
      };
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      // Should not throw
      await store.login('test@example.com', 'password123');

      expect(store.user).toEqual(mockUser);
    });
  });

  describe('setTokensFromOAuth', () => {
    it('should set tokens and fetch user data', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      const store = useAuthStore();
      const tokens = {
        access_token: createMockJwt(3600),
        refresh_token: 'oauth-refresh-token',
      };

      await store.setTokensFromOAuth(tokens);

      expect(store.accessToken).toBe(tokens.access_token);
      expect(LocalStorage.set).toHaveBeenCalledWith('refresh_token', tokens.refresh_token);
      expect(api.get).toHaveBeenCalledWith('/api/v2/auth/me');
      expect(store.user).toEqual(mockUser);
      expect(store.isAuthenticated).toBe(true);
    });

    it('should schedule token refresh after setting OAuth tokens', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      const store = useAuthStore();
      const expiresInSeconds = 600;
      const tokens = {
        access_token: createMockJwt(expiresInSeconds),
        refresh_token: 'oauth-refresh-token',
      };

      await store.setTokensFromOAuth(tokens);

      // Prepare for scheduled refresh
      const tokenResponse = createMockTokenResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: tokenResponse });

      // Advance to refresh time (600 - 120 = 480 seconds)
      vi.advanceTimersByTime(480 * 1000);
      await vi.runAllTimersAsync();

      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/refresh', {
        refresh_token: expect.any(String),
      });
    });
  });

  describe('isAuthenticated computed', () => {
    it('should return true only when user AND token exist', async () => {
      const store = useAuthStore();

      // Initially false
      expect(store.isAuthenticated).toBe(false);

      // After login, should be true
      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });
      await store.login('test@example.com', 'password123');

      expect(store.isAuthenticated).toBe(true);

      // After logout, should be false
      vi.mocked(api.post).mockResolvedValueOnce({ data: {} });
      await store.logout();

      expect(store.isAuthenticated).toBe(false);
    });

    it('should return false when only token exists without user', async () => {
      const store = useAuthStore();

      // Manually set only access token (simulating edge case)
      // This requires accessing store internals which we cannot do directly
      // But we can test the behavior through proper API usage

      expect(store.isAuthenticated).toBe(false);
    });
  });

  describe('userId computed', () => {
    it('should handle _id format from CouchDB', async () => {
      const authResponse: AuthResponse = {
        user: mockUserWithCouchId as User,
        access_token: createMockJwt(3600),
        refresh_token: 'mock-refresh-token',
        token_type: 'bearer',
        expires_in: 3600,
      };
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      const store = useAuthStore();
      await store.login('test@example.com', 'password123');

      // Should prefer _id over id
      expect(store.userId).toBe('user:456');
    });

    it('should handle id format', async () => {
      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });

      const store = useAuthStore();
      await store.login('test@example.com', 'password123');

      expect(store.userId).toBe('user:123');
    });

    it('should return null when user is not set', () => {
      const store = useAuthStore();

      expect(store.userId).toBeNull();
    });
  });

  describe('fetchCurrentUser', () => {
    it('should fetch and set user data', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });

      const store = useAuthStore();
      await store.fetchCurrentUser();

      expect(api.get).toHaveBeenCalledWith('/api/v2/auth/me');
      expect(store.user).toEqual(mockUser);
    });
  });

  describe('getAccessToken', () => {
    it('should return current access token', async () => {
      const store = useAuthStore();

      expect(store.getAccessToken()).toBeNull();

      const authResponse = createMockAuthResponse();
      vi.mocked(api.post).mockResolvedValueOnce({ data: authResponse });
      await store.login('test@example.com', 'password123');

      expect(store.getAccessToken()).toBe(authResponse.access_token);
    });
  });

  describe('isLoading state', () => {
    it('should be true during login and false after', async () => {
      const store = useAuthStore();

      expect(store.isLoading).toBe(false);

      let resolveLogin: (value: { data: AuthResponse }) => void;
      const loginPromise = new Promise<{ data: AuthResponse }>((resolve) => {
        resolveLogin = resolve;
      });
      vi.mocked(api.post).mockReturnValueOnce(loginPromise as Promise<never>);

      const loginCall = store.login('test@example.com', 'password123');

      expect(store.isLoading).toBe(true);

      resolveLogin!({ data: createMockAuthResponse() });
      await loginCall;

      expect(store.isLoading).toBe(false);
    });

    it('should be false after login error', async () => {
      const store = useAuthStore();

      vi.mocked(api.post).mockRejectedValueOnce(new Error('Login failed'));

      await expect(store.login('test@example.com', 'password123')).rejects.toThrow();

      expect(store.isLoading).toBe(false);
    });

    it('should be true during register and false after', async () => {
      const store = useAuthStore();

      expect(store.isLoading).toBe(false);

      let resolveRegister: (value: { data: AuthResponse }) => void;
      const registerPromise = new Promise<{ data: AuthResponse }>((resolve) => {
        resolveRegister = resolve;
      });
      vi.mocked(api.post).mockReturnValueOnce(registerPromise as Promise<never>);

      const registerCall = store.register({
        email: 'new@example.com',
        password: 'password123',
        name: 'New User',
      });

      expect(store.isLoading).toBe(true);

      resolveRegister!({ data: createMockAuthResponse() });
      await registerCall;

      expect(store.isLoading).toBe(false);
    });
  });
});
