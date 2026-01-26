import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';

import ru from '@/i18n/ru';
import en from '@/i18n/en';

export type MessageSchema = typeof ru;
export type SupportedLocale = 'ru' | 'en';

const LOCALE_STORAGE_KEY = 'wishwithme_locale';
const SUPPORTED_LOCALES: SupportedLocale[] = ['ru', 'en'];
const DEFAULT_LOCALE: SupportedLocale = 'ru';

/**
 * Detect browser language and map to supported locale.
 * Returns 'ru' for Russian, 'en' for everything else.
 */
function detectBrowserLocale(): SupportedLocale {
  // navigator.userLanguage is IE-specific, use type assertion for compatibility
  const browserLang = navigator.language || (navigator as { userLanguage?: string }).userLanguage || '';
  const langCode = browserLang.split('-')[0].toLowerCase();

  if (langCode === 'ru') {
    return 'ru';
  }
  return 'en';
}

/**
 * Get the initial locale: saved preference > browser detection > default.
 */
function getInitialLocale(): SupportedLocale {
  // Check localStorage for saved preference
  try {
    const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (saved && SUPPORTED_LOCALES.includes(saved as SupportedLocale)) {
      return saved as SupportedLocale;
    }
  } catch {
    // localStorage may not be available
  }

  // Detect from browser
  return detectBrowserLocale();
}

/**
 * Save locale preference to localStorage.
 */
export function saveLocale(locale: SupportedLocale): void {
  try {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // localStorage may not be available
  }
}

const i18n = createI18n<[MessageSchema], SupportedLocale>({
  locale: getInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  legacy: false,
  messages: {
    ru,
    en,
  },
});

export default boot(({ app }) => {
  app.use(i18n);
});

export { i18n, SUPPORTED_LOCALES };
