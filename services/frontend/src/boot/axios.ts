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
 * In production, use the configured API_URL.
 * In development, use the same hostname as the current page but port 8000.
 */
function getApiBaseUrl(): string {
  // If API_URL is explicitly set (production), use it
  if (process.env.API_URL && process.env.API_URL !== 'http://localhost:8000') {
    return process.env.API_URL;
  }

  // In development, construct URL based on current hostname
  // This allows accessing from localhost, 127.0.0.1, or LAN IP
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  }

  // Fallback
  return process.env.API_URL || 'http://localhost:8000';
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

export { api };
