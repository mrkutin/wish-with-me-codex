import { boot } from 'quasar/wrappers';
import axios, { AxiosInstance } from 'axios';
import { useAuthStore } from '@/stores/auth';

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $axios: AxiosInstance;
    $api: AxiosInstance;
  }
}

/**
 * Get the API base URL.
 * - If accessing via IP address or localhost, construct URL dynamically (same IP, port 8000)
 * - If accessing via domain (like wishwith.me), use the configured API_URL
 * - This allows both direct IP access and production domain access to work correctly
 */
function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;

    // Check if hostname is an IP address (v4 or v6) or localhost
    const isIpAddress =
      /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname) ||
      hostname.includes(':') || // IPv6
      hostname === 'localhost';

    // If accessing via IP or localhost, construct URL dynamically
    if (isIpAddress) {
      return `${protocol}//${hostname}:8000`;
    }
  }

  // For domain access (production), use configured API_URL
  if (process.env.API_URL) {
    return process.env.API_URL;
  }

  // Fallback
  return 'http://localhost:8000';
}

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default boot(({ app, router }) => {
  // Request interceptor to add auth token
  api.interceptors.request.use(
    (config) => {
      const authStore = useAuthStore();
      if (authStore.accessToken) {
        config.headers.Authorization = `Bearer ${authStore.accessToken}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor for token refresh
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;
      const authStore = useAuthStore();

      // If 401 and we haven't tried refreshing yet
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          await authStore.refreshToken();
          originalRequest.headers.Authorization = `Bearer ${authStore.accessToken}`;
          return api(originalRequest);
        } catch {
          // Refresh failed, logout user
          await authStore.logout();
          router.push('/login');
          return Promise.reject(error);
        }
      }

      return Promise.reject(error);
    }
  );

  app.config.globalProperties.$axios = axios;
  app.config.globalProperties.$api = api;
});

export { api, getApiBaseUrl };
