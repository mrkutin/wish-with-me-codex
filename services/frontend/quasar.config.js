/* eslint-env node */
const { configure } = require('quasar/wrappers');
const path = require('path');

module.exports = configure((/* ctx */) => {
  return {
    boot: ['i18n', 'axios', 'auth'],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#sourcefiles
    sourceFiles: {
      rootComponent: 'src/App.vue',
      router: 'src/router/index',
      store: 'src/stores/index',
    },

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#aliases
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },

    css: ['app.sass'],

    extras: ['roboto-font', 'material-icons', 'mdi-v7'],

    build: {
      target: {
        browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node20',
      },
      vueRouterMode: 'history',
      env: {
        API_URL: process.env.API_URL || 'http://localhost:8000',
      },
      typescript: {
        strict: true,
        vueShim: true,
      },
      extendViteConf(viteConf) {
        viteConf.resolve = viteConf.resolve || {};
        viteConf.resolve.alias = {
          ...viteConf.resolve.alias,
          '@': path.resolve(__dirname, 'src'),
        };
      },
    },

    devServer: {
      open: true,
      port: 9000,
    },

    framework: {
      config: {
        brand: {
          primary: '#6366f1',
          secondary: '#26A69A',
          accent: '#9C27B0',
          dark: '#1d1d1d',
          positive: '#1a9f38',
          negative: '#C10015',
          info: '#31CCEC',
          warning: '#F2C037',
        },
        notify: {
          position: 'top',
          timeout: 3000,
        },
        loading: {
          spinnerColor: 'primary',
        },
      },
      plugins: [
        'Notify',
        'Dialog',
        'Loading',
        'LocalStorage',
        'SessionStorage',
        'BottomSheet',
      ],
    },

    animations: 'all',

    pwa: {
      workboxMode: 'generateSW',
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
      useCredentialsForManifestTag: false,
      extendGenerateSWOptions(cfg) {
        cfg.skipWaiting = true;
        cfg.clientsClaim = true;
        // Exclude /api/ paths from navigation fallback - let them pass through to server
        cfg.navigateFallbackDenylist = [/^\/api\//];
      },
      manifest: {
        name: 'Wish With Me',
        short_name: 'WishWithMe',
        description: 'Create and share wishlists with friends',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#ffffff',
        theme_color: '#6366f1',
        start_url: '/',
        icons: [
          {
            src: 'icons/icon-128x128.png',
            sizes: '128x128',
            type: 'image/png',
          },
          {
            src: 'icons/icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'icons/icon-256x256.png',
            sizes: '256x256',
            type: 'image/png',
          },
          {
            src: 'icons/icon-384x384.png',
            sizes: '384x384',
            type: 'image/png',
          },
          {
            src: 'icons/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
        ],
      },
    },
  };
});
