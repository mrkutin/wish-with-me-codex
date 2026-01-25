import { boot } from 'quasar/wrappers';
import { LocalStorage } from 'quasar';
import { useAuthStore } from '@/stores/auth';

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

export default boot(async ({ router }) => {
  const authStore = useAuthStore();

  // Try to restore session from storage
  await authStore.initializeAuth();

  // Navigation guard for protected routes
  router.beforeEach((to, from, next) => {
    const requiresAuth = to.matched.some((record) => record.meta.requiresAuth);
    const isAuthenticated = authStore.isAuthenticated;

    if (requiresAuth && !isAuthenticated) {
      // If redirecting from shared-wishlist page, store the token
      if (to.name === 'shared-wishlist' && to.params.token) {
        LocalStorage.set(PENDING_SHARE_TOKEN_KEY, to.params.token as string);
      }
      // Redirect to login with return URL
      next({
        path: '/login',
        query: { redirect: to.fullPath },
      });
    } else if (
      (to.path === '/login' || to.path === '/register') &&
      isAuthenticated
    ) {
      // Redirect authenticated users away from auth pages
      next('/wishlists');
    } else {
      next();
    }
  });
});
