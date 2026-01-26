import { register } from 'register-service-worker';
import { Notify } from 'quasar';

// Event for app to listen to service worker updates
export const swUpdateEvent = new CustomEvent('swUpdated', { detail: null });

register(process.env.SERVICE_WORKER_FILE, {
  ready(registration) {
    console.log('[SW] Service worker is active.');

    // Listen for messages from service worker
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'SW_UPDATED') {
        window.dispatchEvent(swUpdateEvent);
      }
    });
  },

  registered(registration) {
    console.log('[SW] Service worker has been registered.');

    // Check for updates periodically (every 15 minutes)
    setInterval(() => {
      registration.update();
    }, 15 * 60 * 1000);
  },

  cached() {
    console.log('[SW] Content has been cached for offline use.');
    Notify.create({
      message: 'App ready for offline use',
      icon: 'cloud_done',
      color: 'positive',
      timeout: 3000,
    });
  },

  updatefound() {
    console.log('[SW] New content is downloading.');
  },

  updated(registration) {
    console.log('[SW] New content is available.');

    // Store registration for later use
    (window as Window & { swRegistration?: ServiceWorkerRegistration }).swRegistration =
      registration;

    // Dispatch custom event for app to handle
    window.dispatchEvent(new CustomEvent('swUpdated', { detail: registration }));
  },

  offline() {
    console.log('[SW] No internet connection. App is running in offline mode.');
  },

  error(err) {
    console.error('[SW] Error during service worker registration:', err);
  },
});
