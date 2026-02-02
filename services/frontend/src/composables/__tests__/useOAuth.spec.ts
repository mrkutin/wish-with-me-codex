/**
 * Unit tests for the useOAuth composable.
 * Tests OAuth provider management, account linking/unlinking, and UI helpers.
 *
 * Note: The useOAuth composable uses module-level state, so tests must
 * reset the shared state in beforeEach to prevent state bleeding between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useOAuth, type OAuthProvider } from '../useOAuth';
import type { ConnectedAccount } from '@/types/user';

// Mock axios api
const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
};

const mockGetApiBaseUrl = vi.fn(() => 'http://localhost:8000');

vi.mock('@/boot/axios', () => ({
  api: {
    get: (...args: unknown[]) => mockApi.get(...args),
    post: (...args: unknown[]) => mockApi.post(...args),
    delete: (...args: unknown[]) => mockApi.delete(...args),
  },
  getApiBaseUrl: () => mockGetApiBaseUrl(),
}));

// Store original window.location
const originalLocation = window.location;

describe('useOAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Reset window.location mock
    Object.defineProperty(window, 'location', {
      value: {
        href: 'http://localhost:9000/',
        hostname: 'localhost',
        protocol: 'http:',
        origin: 'http://localhost:9000',
        pathname: '/',
        search: '',
        hash: '',
      },
      writable: true,
      configurable: true,
    });

    // Reset the composable's module-level state
    const {
      availableProviders,
      connectedAccounts,
      hasPassword,
      isLoading,
      error,
    } = useOAuth();

    availableProviders.value = [];
    connectedAccounts.value = [];
    hasPassword.value = true;
    isLoading.value = false;
    error.value = null;
  });

  afterEach(() => {
    // Restore original location
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  describe('fetchAvailableProviders', () => {
    it('should populate availableProviders array on success', async () => {
      const mockProviders: OAuthProvider[] = ['google', 'yandex', 'apple'];
      mockApi.get.mockResolvedValueOnce({
        data: { providers: mockProviders },
      });

      const { fetchAvailableProviders, availableProviders } = useOAuth();

      await fetchAvailableProviders();

      expect(mockApi.get).toHaveBeenCalledWith('/api/v1/oauth/providers');
      expect(availableProviders.value).toEqual(mockProviders);
    });

    it('should set empty array on error', async () => {
      mockApi.get.mockRejectedValueOnce(new Error('Network error'));

      const { fetchAvailableProviders, availableProviders } = useOAuth();

      // First set some providers to verify they get cleared
      availableProviders.value = ['google'];

      await fetchAvailableProviders();

      expect(availableProviders.value).toEqual([]);
    });

    it('should handle empty providers response', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: { providers: [] },
      });

      const { fetchAvailableProviders, availableProviders } = useOAuth();

      await fetchAvailableProviders();

      expect(availableProviders.value).toEqual([]);
    });
  });

  describe('fetchConnectedAccounts', () => {
    it('should populate accounts and hasPassword on success', async () => {
      const mockAccounts: ConnectedAccount[] = [
        { provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' },
        { provider: 'yandex', email: 'test@yandex.ru', connected_at: '2024-01-02T00:00:00Z' },
      ];

      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: mockAccounts,
          has_password: true,
        },
      });

      const { fetchConnectedAccounts, connectedAccounts, hasPassword, isLoading, error } =
        useOAuth();

      const fetchPromise = fetchConnectedAccounts();

      // Should be loading
      expect(isLoading.value).toBe(true);

      await fetchPromise;

      expect(mockApi.get).toHaveBeenCalledWith('/api/v1/oauth/connected');
      expect(connectedAccounts.value).toEqual(mockAccounts);
      expect(hasPassword.value).toBe(true);
      expect(isLoading.value).toBe(false);
      expect(error.value).toBeNull();
    });

    it('should set hasPassword to false when user has no password', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [{ provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' }],
          has_password: false,
        },
      });

      const { fetchConnectedAccounts, hasPassword } = useOAuth();

      await fetchConnectedAccounts();

      expect(hasPassword.value).toBe(false);
    });

    it('should set error and clear accounts on failure', async () => {
      mockApi.get.mockRejectedValueOnce(new Error('Unauthorized'));

      const { fetchConnectedAccounts, connectedAccounts, error, isLoading } = useOAuth();

      // Pre-populate to verify clearing
      connectedAccounts.value = [{ provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' }];

      await fetchConnectedAccounts();

      expect(error.value).toBe('Failed to fetch connected accounts');
      expect(connectedAccounts.value).toEqual([]);
      expect(isLoading.value).toBe(false);
    });
  });

  describe('initiateOAuthLogin', () => {
    it('should redirect to OAuth URL for google', () => {
      mockGetApiBaseUrl.mockReturnValue('http://localhost:8000');

      const { initiateOAuthLogin } = useOAuth();

      initiateOAuthLogin('google');

      expect(window.location.href).toBe('http://localhost:8000/api/v1/oauth/google/authorize');
    });

    it('should redirect to OAuth URL for yandex', () => {
      mockGetApiBaseUrl.mockReturnValue('https://api.wishwith.me');

      const { initiateOAuthLogin } = useOAuth();

      initiateOAuthLogin('yandex');

      expect(window.location.href).toBe('https://api.wishwith.me/api/v1/oauth/yandex/authorize');
    });

    it('should redirect to OAuth URL for apple', () => {
      mockGetApiBaseUrl.mockReturnValue('https://api.wishwith.me');

      const { initiateOAuthLogin } = useOAuth();

      initiateOAuthLogin('apple');

      expect(window.location.href).toBe('https://api.wishwith.me/api/v1/oauth/apple/authorize');
    });

    it('should redirect to OAuth URL for sber', () => {
      mockGetApiBaseUrl.mockReturnValue('https://api.wishwith.me');

      const { initiateOAuthLogin } = useOAuth();

      initiateOAuthLogin('sber');

      expect(window.location.href).toBe('https://api.wishwith.me/api/v1/oauth/sber/authorize');
    });
  });

  describe('initiateOAuthLink', () => {
    it('should call API and redirect to authorization URL', async () => {
      const authorizationUrl = 'https://accounts.google.com/o/oauth2/auth?client_id=...';
      mockApi.post.mockResolvedValueOnce({
        data: {
          authorization_url: authorizationUrl,
          state: 'random-state-string',
        },
      });

      const { initiateOAuthLink, error } = useOAuth();

      await initiateOAuthLink('google');

      expect(mockApi.post).toHaveBeenCalledWith('/api/v1/oauth/google/link/initiate');
      expect(window.location.href).toBe(authorizationUrl);
      expect(error.value).toBeNull();
    });

    it('should set error on API failure', async () => {
      mockApi.post.mockRejectedValueOnce(new Error('Already linked'));

      const { initiateOAuthLink, error } = useOAuth();

      await initiateOAuthLink('google');

      expect(error.value).toBe('Failed to initiate OAuth linking');
      // Should not redirect
      expect(window.location.href).not.toContain('accounts.google.com');
    });
  });

  describe('unlinkAccount', () => {
    it('should call API and refresh accounts on success', async () => {
      mockApi.delete.mockResolvedValueOnce({ data: {} });
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [],
          has_password: true,
        },
      });

      const { unlinkAccount, connectedAccounts, isLoading, error } = useOAuth();

      // Pre-populate
      connectedAccounts.value = [{ provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' }];

      const result = await unlinkAccount('google');

      expect(result).toBe(true);
      expect(mockApi.delete).toHaveBeenCalledWith('/api/v1/oauth/google/unlink');
      expect(mockApi.get).toHaveBeenCalledWith('/api/v1/oauth/connected');
      expect(isLoading.value).toBe(false);
      expect(error.value).toBeNull();
    });

    it('should set error message on failure', async () => {
      mockApi.delete.mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Cannot unlink last authentication method',
          },
        },
      });

      const { unlinkAccount, error, isLoading } = useOAuth();

      const result = await unlinkAccount('google');

      expect(result).toBe(false);
      expect(error.value).toBe('Cannot unlink last authentication method');
      expect(isLoading.value).toBe(false);
    });

    it('should use default error message when no detail provided', async () => {
      mockApi.delete.mockRejectedValueOnce(new Error('Network error'));

      const { unlinkAccount, error } = useOAuth();

      const result = await unlinkAccount('google');

      expect(result).toBe(false);
      expect(error.value).toBe('Failed to unlink account');
    });

    it('should set isLoading during the operation', async () => {
      let resolveDelete: () => void;
      const deletePromise = new Promise<{ data: object }>((resolve) => {
        resolveDelete = () => resolve({ data: {} });
      });
      mockApi.delete.mockReturnValueOnce(deletePromise);
      mockApi.get.mockResolvedValueOnce({
        data: { accounts: [], has_password: true },
      });

      const { unlinkAccount, isLoading } = useOAuth();

      const unlinkPromise = unlinkAccount('google');

      expect(isLoading.value).toBe(true);

      resolveDelete!();
      await unlinkPromise;

      expect(isLoading.value).toBe(false);
    });
  });

  describe('canUnlinkAccount', () => {
    it('should return true when user has password', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [{ provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' }],
          has_password: true,
        },
      });

      const { fetchConnectedAccounts, canUnlinkAccount } = useOAuth();

      await fetchConnectedAccounts();

      expect(canUnlinkAccount.value).toBe(true);
    });

    it('should return true when user has multiple accounts (no password)', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [
            { provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' },
            { provider: 'yandex', email: 'test@yandex.ru', connected_at: '2024-01-02T00:00:00Z' },
          ],
          has_password: false,
        },
      });

      const { fetchConnectedAccounts, canUnlinkAccount } = useOAuth();

      await fetchConnectedAccounts();

      expect(canUnlinkAccount.value).toBe(true);
    });

    it('should return false when user has no password and only one account', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [{ provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' }],
          has_password: false,
        },
      });

      const { fetchConnectedAccounts, canUnlinkAccount } = useOAuth();

      await fetchConnectedAccounts();

      expect(canUnlinkAccount.value).toBe(false);
    });

    it('should return true when hasPassword is true (default state with no accounts)', () => {
      const { canUnlinkAccount, hasPassword, connectedAccounts } = useOAuth();

      // Verify default state
      expect(hasPassword.value).toBe(true);
      expect(connectedAccounts.value).toEqual([]);

      // hasPassword = true OR accounts.length > 1
      // Since hasPassword is true, canUnlinkAccount should be true
      expect(canUnlinkAccount.value).toBe(true);
    });
  });

  describe('isProviderConnected', () => {
    it('should return true for connected provider', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [
            { provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' },
          ],
          has_password: true,
        },
      });

      const { fetchConnectedAccounts, isProviderConnected } = useOAuth();

      await fetchConnectedAccounts();

      expect(isProviderConnected('google')).toBe(true);
    });

    it('should return false for unconnected provider', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [
            { provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' },
          ],
          has_password: true,
        },
      });

      const { fetchConnectedAccounts, isProviderConnected } = useOAuth();

      await fetchConnectedAccounts();

      expect(isProviderConnected('yandex')).toBe(false);
      expect(isProviderConnected('apple')).toBe(false);
      expect(isProviderConnected('sber')).toBe(false);
    });

    it('should check array correctly with multiple accounts', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          accounts: [
            { provider: 'google', email: 'test@gmail.com', connected_at: '2024-01-01T00:00:00Z' },
            { provider: 'yandex', email: 'test@yandex.ru', connected_at: '2024-01-02T00:00:00Z' },
          ],
          has_password: true,
        },
      });

      const { fetchConnectedAccounts, isProviderConnected } = useOAuth();

      await fetchConnectedAccounts();

      expect(isProviderConnected('google')).toBe(true);
      expect(isProviderConnected('yandex')).toBe(true);
      expect(isProviderConnected('apple')).toBe(false);
    });
  });

  describe('getProviderDisplayName', () => {
    it('should return correct name for google', () => {
      const { getProviderDisplayName } = useOAuth();

      expect(getProviderDisplayName('google')).toBe('Google');
    });

    it('should return correct name for apple', () => {
      const { getProviderDisplayName } = useOAuth();

      expect(getProviderDisplayName('apple')).toBe('Apple');
    });

    it('should return correct name for yandex', () => {
      const { getProviderDisplayName } = useOAuth();

      expect(getProviderDisplayName('yandex')).toBe('Yandex');
    });

    it('should return correct name for sber', () => {
      const { getProviderDisplayName } = useOAuth();

      expect(getProviderDisplayName('sber')).toBe('Sber ID');
    });

    it('should return provider name for unknown provider', () => {
      const { getProviderDisplayName } = useOAuth();

      // Type assertion for testing edge case
      expect(getProviderDisplayName('unknown' as OAuthProvider)).toBe('unknown');
    });
  });

  describe('getProviderIcon', () => {
    it('should return correct icon for google', () => {
      const { getProviderIcon } = useOAuth();

      expect(getProviderIcon('google')).toBe('mdi-google');
    });

    it('should return correct icon for apple', () => {
      const { getProviderIcon } = useOAuth();

      expect(getProviderIcon('apple')).toBe('mdi-apple');
    });

    it('should return correct icon for yandex', () => {
      const { getProviderIcon } = useOAuth();

      expect(getProviderIcon('yandex')).toBe('mdi-alpha-y-box');
    });

    it('should return correct icon for sber', () => {
      const { getProviderIcon } = useOAuth();

      expect(getProviderIcon('sber')).toBe('mdi-bank');
    });

    it('should return default icon for unknown provider', () => {
      const { getProviderIcon } = useOAuth();

      // Type assertion for testing edge case
      expect(getProviderIcon('unknown' as OAuthProvider)).toBe('mdi-account');
    });
  });

  describe('getProviderColor', () => {
    it('should return correct color for google', () => {
      const { getProviderColor } = useOAuth();

      expect(getProviderColor('google')).toBe('#4285F4');
    });

    it('should return correct color for apple', () => {
      const { getProviderColor } = useOAuth();

      expect(getProviderColor('apple')).toBe('#000000');
    });

    it('should return correct color for yandex', () => {
      const { getProviderColor } = useOAuth();

      expect(getProviderColor('yandex')).toBe('#FC3F1D');
    });

    it('should return correct color for sber', () => {
      const { getProviderColor } = useOAuth();

      expect(getProviderColor('sber')).toBe('#21A038');
    });

    it('should return default color for unknown provider', () => {
      const { getProviderColor } = useOAuth();

      // Type assertion for testing edge case
      expect(getProviderColor('unknown' as OAuthProvider)).toBe('#666666');
    });
  });

  describe('reactive state', () => {
    it('should expose isLoading ref', () => {
      const { isLoading } = useOAuth();

      expect(isLoading.value).toBe(false);
    });

    it('should expose error ref', () => {
      const { error } = useOAuth();

      expect(error.value).toBeNull();
    });

    it('should expose availableProviders ref', () => {
      const { availableProviders } = useOAuth();

      expect(Array.isArray(availableProviders.value)).toBe(true);
    });

    it('should expose connectedAccounts ref', () => {
      const { connectedAccounts } = useOAuth();

      expect(Array.isArray(connectedAccounts.value)).toBe(true);
    });

    it('should expose hasPassword ref', () => {
      const { hasPassword } = useOAuth();

      expect(typeof hasPassword.value).toBe('boolean');
    });
  });

  describe('error handling', () => {
    it('should clear error before fetching connected accounts', async () => {
      const { fetchConnectedAccounts, error } = useOAuth();

      // First call fails
      mockApi.get.mockRejectedValueOnce(new Error('First error'));
      await fetchConnectedAccounts();
      expect(error.value).toBe('Failed to fetch connected accounts');

      // Second call succeeds - error should be cleared
      mockApi.get.mockResolvedValueOnce({
        data: { accounts: [], has_password: true },
      });
      await fetchConnectedAccounts();
      expect(error.value).toBeNull();
    });

    it('should clear error before unlinking account', async () => {
      const { unlinkAccount, error } = useOAuth();

      // First call fails
      mockApi.delete.mockRejectedValueOnce(new Error('First error'));
      await unlinkAccount('google');
      expect(error.value).toBe('Failed to unlink account');

      // Second call succeeds
      mockApi.delete.mockResolvedValueOnce({ data: {} });
      mockApi.get.mockResolvedValueOnce({
        data: { accounts: [], has_password: true },
      });
      await unlinkAccount('yandex');
      expect(error.value).toBeNull();
    });
  });
});
