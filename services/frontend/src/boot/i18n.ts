import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';

import ru from '@/i18n/ru';
import en from '@/i18n/en';

export type MessageSchema = typeof ru;

const i18n = createI18n<[MessageSchema], 'ru' | 'en'>({
  locale: 'ru',
  fallbackLocale: 'en',
  legacy: false,
  messages: {
    ru,
    en,
  },
});

export default boot(({ app }) => {
  app.use(i18n);
});

export { i18n };
