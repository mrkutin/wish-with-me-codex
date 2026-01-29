/* eslint-env node */
const { configure } = require('quasar/wrappers');
const path = require('path');

module.exports = configure((/* ctx */) => {
  return {
    supportTS: true,

    boot: ['i18n', 'axios', 'auth'],

    css: ['app.sass'],

    extras: ['roboto-font', 'material-icons', 'mdi-v7'],

    build: {
      vueRouterMode: 'history',
      env: {
        API_URL: process.env.API_URL || 'http://localhost:8000',
      },
      // Webpack config for PouchDB compatibility
      extendWebpack(cfg) {
        // Node.js polyfills for PouchDB
        cfg.resolve = cfg.resolve || {};
        cfg.resolve.fallback = cfg.resolve.fallback || {};
        cfg.resolve.fallback.events = require.resolve('events');

        // Add TypeScript extensions for module resolution
        cfg.resolve.extensions = cfg.resolve.extensions || [];
        if (!cfg.resolve.extensions.includes('.ts')) {
          cfg.resolve.extensions.push('.ts', '.tsx');
        }
      },
      chainWebpack(chain) {
        // Set up aliases for Quasar's generated files
        chain.resolve.alias
          .set('app', path.resolve(__dirname))
          .set('src', path.resolve(__dirname, 'src'))
          .set('@', path.resolve(__dirname, 'src'))
          .set('boot', path.resolve(__dirname, 'src/boot'))
          .set('components', path.resolve(__dirname, 'src/components'))
          .set('layouts', path.resolve(__dirname, 'src/layouts'))
          .set('pages', path.resolve(__dirname, 'src/pages'))
          .set('assets', path.resolve(__dirname, 'src/assets'))
          .set('stores', path.resolve(__dirname, 'src/stores'));

        // Define global for PouchDB
        chain.plugin('define').tap((args) => {
          args[0]['global'] = 'window';
          return args;
        });
      },
    },

    devServer: {
      open: true,
      port: 9000,
    },

    framework: {
      config: {
        brand: {
          primary: '#4F46E5',
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
      workboxMode: 'injectManifest',
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
      useCredentialsForManifestTag: false,
      manifest: {
        name: 'Wish With Me — Create & Share Wishlists',
        short_name: 'Wish With Me',
        description: 'Create wishlists, share with friends, get perfect gifts! Free wishlist app that works offline.',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#ffffff',
        theme_color: '#4F46E5',
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
