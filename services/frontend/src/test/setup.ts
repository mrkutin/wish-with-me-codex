/**
 * Vitest setup file for Vue/Quasar test environment.
 *
 * This file sets up global mocks for:
 * - Quasar components and plugins
 * - vue-i18n translation functions
 * - vue-router navigation
 * - PouchDB database operations
 * - axios/api HTTP calls
 */

import { vi, beforeEach, afterEach } from 'vitest';
import { config } from '@vue/test-utils';
import { ref, reactive } from 'vue';

// ============================================
// Browser API Mocks
// ============================================

// Mock crypto.randomUUID for consistent IDs in tests
Object.defineProperty(globalThis, 'crypto', {
  value: {
    randomUUID: vi.fn(() => '00000000-0000-0000-0000-000000000000'),
    getRandomValues: vi.fn((arr: Uint8Array) => {
      for (let i = 0; i < arr.length; i++) {
        arr[i] = Math.floor(Math.random() * 256);
      }
      return arr;
    }),
  },
});

// Mock navigator.onLine
Object.defineProperty(navigator, 'onLine', {
  writable: true,
  value: true,
});

// Mock window.location
Object.defineProperty(window, 'location', {
  value: {
    hostname: 'localhost',
    protocol: 'http:',
    href: 'http://localhost:9000/',
    origin: 'http://localhost:9000',
    pathname: '/',
    search: '',
    hash: '',
  },
  writable: true,
});

// Mock console methods to reduce noise during tests
vi.spyOn(console, 'log').mockImplementation(() => {});
vi.spyOn(console, 'debug').mockImplementation(() => {});
vi.spyOn(console, 'warn').mockImplementation(() => {});

// ============================================
// Quasar Component Stubs
// ============================================

const quasarComponentStubs = {
  QBtn: {
    name: 'QBtn',
    template: '<button :class="$attrs.class" :disabled="$attrs.disable" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['label', 'color', 'disable', 'loading', 'icon', 'flat', 'outline', 'rounded', 'dense', 'size', 'type'],
  },
  QInput: {
    name: 'QInput',
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" :placeholder="placeholder" :disabled="disable" />',
    props: ['modelValue', 'label', 'placeholder', 'type', 'disable', 'readonly', 'rules', 'error', 'errorMessage', 'hint', 'dense', 'outlined', 'filled'],
    emits: ['update:modelValue'],
  },
  QDialog: {
    name: 'QDialog',
    template: '<div v-if="modelValue" class="q-dialog" data-testid="q-dialog"><slot /></div>',
    props: ['modelValue', 'persistent', 'maximized', 'fullWidth', 'fullHeight', 'position'],
    emits: ['update:modelValue', 'show', 'hide'],
  },
  QCard: {
    name: 'QCard',
    template: '<div class="q-card"><slot /></div>',
    props: ['flat', 'bordered', 'square', 'dark'],
  },
  QCardSection: {
    name: 'QCardSection',
    template: '<div class="q-card__section"><slot /></div>',
    props: ['horizontal'],
  },
  QCardActions: {
    name: 'QCardActions',
    template: '<div class="q-card__actions"><slot /></div>',
    props: ['align', 'vertical'],
  },
  QForm: {
    name: 'QForm',
    template: '<form @submit.prevent="$emit(\'submit\', $event)"><slot /></form>',
    emits: ['submit', 'reset', 'validation-success', 'validation-error'],
  },
  QIcon: {
    name: 'QIcon',
    template: '<span class="q-icon" :data-name="name">{{ name }}</span>',
    props: ['name', 'color', 'size', 'left', 'right'],
  },
  QList: {
    name: 'QList',
    template: '<div class="q-list"><slot /></div>',
    props: ['bordered', 'separator', 'padding', 'dense'],
  },
  QItem: {
    name: 'QItem',
    template: '<div class="q-item" @click="$emit(\'click\', $event)"><slot /></div>',
    props: ['clickable', 'disable', 'active', 'dense', 'to'],
    emits: ['click'],
  },
  QItemSection: {
    name: 'QItemSection',
    template: '<div class="q-item__section"><slot /></div>',
    props: ['avatar', 'thumbnail', 'side', 'top', 'noWrap'],
  },
  QItemLabel: {
    name: 'QItemLabel',
    template: '<div class="q-item__label"><slot /></div>',
    props: ['overline', 'caption', 'header', 'lines'],
  },
  QSpinner: {
    name: 'QSpinner',
    template: '<div class="q-spinner" data-testid="q-spinner" />',
    props: ['size', 'color', 'thickness'],
  },
  QAvatar: {
    name: 'QAvatar',
    template: '<div class="q-avatar"><slot /></div>',
    props: ['size', 'fontSize', 'color', 'textColor', 'icon', 'square', 'rounded'],
  },
  QImg: {
    name: 'QImg',
    template: '<img :src="src" :alt="alt" class="q-img" />',
    props: ['src', 'alt', 'width', 'height', 'ratio', 'fit', 'position', 'loading', 'noSpinner'],
  },
  QSeparator: {
    name: 'QSeparator',
    template: '<hr class="q-separator" />',
    props: ['spaced', 'inset', 'vertical', 'color', 'dark'],
  },
  QBadge: {
    name: 'QBadge',
    template: '<span class="q-badge"><slot /></span>',
    props: ['color', 'textColor', 'floating', 'transparent', 'multiLine', 'label', 'align', 'outline', 'rounded'],
  },
  QChip: {
    name: 'QChip',
    template: '<span class="q-chip" @click="$emit(\'click\', $event)"><slot /></span>',
    props: ['icon', 'iconRight', 'iconRemove', 'iconSelected', 'label', 'color', 'textColor', 'dense', 'size', 'outline', 'square', 'clickable', 'removable', 'disable', 'selected', 'tabindex'],
    emits: ['click', 'remove', 'update:selected'],
  },
  QMenu: {
    name: 'QMenu',
    template: '<div v-if="modelValue" class="q-menu"><slot /></div>',
    props: ['modelValue', 'target', 'anchor', 'self', 'offset', 'noParentEvent', 'touchPosition', 'persistent', 'autoClose', 'separate-close-popup', 'square', 'noRefocus', 'noFocus', 'fit', 'cover', 'maxHeight', 'maxWidth'],
    emits: ['update:modelValue', 'show', 'before-show', 'hide', 'before-hide'],
  },
  QSelect: {
    name: 'QSelect',
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
    props: ['modelValue', 'options', 'label', 'dense', 'outlined', 'filled', 'disable', 'readonly', 'multiple', 'emitValue', 'mapOptions', 'optionLabel', 'optionValue', 'optionDisable'],
    emits: ['update:modelValue', 'filter', 'input-value'],
  },
  QToolbar: {
    name: 'QToolbar',
    template: '<div class="q-toolbar"><slot /></div>',
    props: ['inset'],
  },
  QToolbarTitle: {
    name: 'QToolbarTitle',
    template: '<div class="q-toolbar__title"><slot /></div>',
    props: ['shrink'],
  },
  QPage: {
    name: 'QPage',
    template: '<main class="q-page"><slot /></main>',
    props: ['padding', 'styleFn'],
  },
  QPageContainer: {
    name: 'QPageContainer',
    template: '<div class="q-page-container"><slot /></div>',
  },
  QLayout: {
    name: 'QLayout',
    template: '<div class="q-layout"><slot /></div>',
    props: ['view', 'container'],
  },
  QHeader: {
    name: 'QHeader',
    template: '<header class="q-header"><slot /></header>',
    props: ['reveal', 'revealOffset', 'bordered', 'elevated', 'heightHint'],
  },
  QFooter: {
    name: 'QFooter',
    template: '<footer class="q-footer"><slot /></footer>',
    props: ['reveal', 'bordered', 'elevated', 'heightHint'],
  },
  QDrawer: {
    name: 'QDrawer',
    template: '<aside v-if="modelValue" class="q-drawer"><slot /></aside>',
    props: ['modelValue', 'side', 'overlay', 'width', 'mini', 'miniToOverlay', 'miniWidth', 'breakpoint', 'behavior', 'bordered', 'elevated', 'persistent', 'showIfAbove', 'noSwipeOpen', 'noSwipeClose', 'noSwipeBackdrop'],
    emits: ['update:modelValue', 'show', 'hide', 'on-layout', 'mini-state'],
  },
  QScrollArea: {
    name: 'QScrollArea',
    template: '<div class="q-scroll-area"><slot /></div>',
    props: ['thumbStyle', 'barStyle', 'contentStyle', 'contentActiveStyle', 'delay', 'visible', 'horizontal', 'tabindex'],
  },
  QSpace: {
    name: 'QSpace',
    template: '<div class="q-space" />',
  },
  QTab: {
    name: 'QTab',
    template: '<div class="q-tab" @click="$emit(\'click\', $event)"><slot /></div>',
    props: ['name', 'icon', 'label', 'alert', 'alertIcon', 'disable', 'noCaps', 'tabindex', 'ripple'],
    emits: ['click'],
  },
  QTabs: {
    name: 'QTabs',
    template: '<div class="q-tabs"><slot /></div>',
    props: ['modelValue', 'vertical', 'outside-arrows', 'mobile-arrows', 'align', 'breakpoint', 'shrink', 'stretch', 'activeColor', 'activeBgColor', 'indicatorColor', 'contentClass', 'leftIcon', 'rightIcon', 'dense', 'inlineLabel', 'noCaps', 'narrow-indicator', 'switchIndicator'],
    emits: ['update:modelValue'],
  },
  QTabPanel: {
    name: 'QTabPanel',
    template: '<div class="q-tab-panel"><slot /></div>',
    props: ['name', 'disable'],
  },
  QTabPanels: {
    name: 'QTabPanels',
    template: '<div class="q-tab-panels"><slot /></div>',
    props: ['modelValue', 'keepAlive', 'keepAliveInclude', 'keepAliveExclude', 'keepAliveMax', 'animated', 'infinite', 'swipeable', 'vertical', 'transitionPrev', 'transitionNext', 'transitionDuration'],
    emits: ['update:modelValue', 'before-transition', 'transition'],
  },
  QToggle: {
    name: 'QToggle',
    template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    props: ['modelValue', 'label', 'leftLabel', 'color', 'keepColor', 'dark', 'dense', 'disable', 'tabindex', 'val', 'trueValue', 'falseValue', 'indeterminateValue', 'toggleOrder', 'toggleIndeterminate', 'checkedIcon', 'uncheckedIcon', 'indeterminateIcon', 'size', 'iconColor'],
    emits: ['update:modelValue'],
  },
  QCheckbox: {
    name: 'QCheckbox',
    template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    props: ['modelValue', 'label', 'leftLabel', 'color', 'keepColor', 'dark', 'dense', 'disable', 'tabindex', 'val', 'trueValue', 'falseValue', 'indeterminateValue', 'toggleOrder', 'toggleIndeterminate', 'checkedIcon', 'uncheckedIcon', 'indeterminateIcon', 'size'],
    emits: ['update:modelValue'],
  },
  QRadio: {
    name: 'QRadio',
    template: '<input type="radio" :checked="modelValue === val" @change="$emit(\'update:modelValue\', val)" />',
    props: ['modelValue', 'val', 'label', 'leftLabel', 'color', 'keepColor', 'dark', 'dense', 'disable', 'tabindex', 'checkedIcon', 'uncheckedIcon', 'size'],
    emits: ['update:modelValue'],
  },
  QFile: {
    name: 'QFile',
    template: '<input type="file" @change="$emit(\'update:modelValue\', $event.target.files)" />',
    props: ['modelValue', 'accept', 'capture', 'maxFileSize', 'maxTotalSize', 'maxFiles', 'filter', 'label', 'dense', 'outlined', 'filled', 'disable', 'readonly', 'multiple', 'append', 'displayValue', 'useChips', 'counter', 'counterLabel'],
    emits: ['update:modelValue', 'rejected'],
  },
  QTooltip: {
    name: 'QTooltip',
    template: '<div class="q-tooltip"><slot /></div>',
    props: ['modelValue', 'maxHeight', 'maxWidth', 'anchor', 'self', 'offset', 'scrollTarget', 'delay', 'hideDelay', 'persistent', 'noParentEvent', 'transitionShow', 'transitionHide', 'transitionDuration'],
    emits: ['update:modelValue', 'show', 'before-show', 'hide', 'before-hide'],
  },
  QPopupProxy: {
    name: 'QPopupProxy',
    template: '<div class="q-popup-proxy"><slot /></div>',
    props: ['modelValue', 'breakpoint', 'target', 'noParentEvent', 'contextMenu'],
    emits: ['update:modelValue', 'show', 'before-show', 'hide', 'before-hide'],
  },
  QExpansionItem: {
    name: 'QExpansionItem',
    template: '<div class="q-expansion-item"><slot /></div>',
    props: ['modelValue', 'icon', 'expandIcon', 'expandedIcon', 'expandIconClass', 'toggleAriaLabel', 'label', 'labelLines', 'caption', 'captionLines', 'dark', 'dense', 'duration', 'headerInsetLevel', 'contentInsetLevel', 'expandSeparator', 'defaultOpened', 'hideExpandIcon', 'expandIconToggle', 'switchToggleSide', 'denseToggle', 'group', 'popup', 'headerStyle', 'headerClass'],
    emits: ['update:modelValue', 'show', 'before-show', 'hide', 'before-hide', 'after-show', 'after-hide'],
  },
  QStepper: {
    name: 'QStepper',
    template: '<div class="q-stepper"><slot /></div>',
    props: ['modelValue', 'keepAlive', 'keepAliveInclude', 'keepAliveExclude', 'keepAliveMax', 'animated', 'infinite', 'swipeable', 'vertical', 'transitionPrev', 'transitionNext', 'transitionDuration', 'dark', 'flat', 'bordered', 'alternativeLabels', 'headerNav', 'contracted', 'headerClass', 'inactiveColor', 'inactiveIcon', 'doneIcon', 'doneColor', 'activeIcon', 'activeColor', 'errorIcon', 'errorColor'],
    emits: ['update:modelValue', 'before-transition', 'transition'],
  },
  QStep: {
    name: 'QStep',
    template: '<div class="q-step"><slot /></div>',
    props: ['name', 'disable', 'icon', 'color', 'title', 'caption', 'prefix', 'doneIcon', 'doneColor', 'activeIcon', 'activeColor', 'errorIcon', 'errorColor', 'headerNav', 'done', 'error'],
  },
  QStepperNavigation: {
    name: 'QStepperNavigation',
    template: '<div class="q-stepper__nav"><slot /></div>',
  },
  QBanner: {
    name: 'QBanner',
    template: '<div class="q-banner"><slot /></div>',
    props: ['inlineActions', 'dense', 'rounded', 'dark'],
  },
  QCircularProgress: {
    name: 'QCircularProgress',
    template: '<div class="q-circular-progress" />',
    props: ['value', 'min', 'max', 'color', 'centerColor', 'trackColor', 'fontSize', 'rounded', 'thickness', 'angle', 'indeterminate', 'showValue', 'reverse', 'instantFeedback', 'animationSpeed', 'size'],
  },
  QLinearProgress: {
    name: 'QLinearProgress',
    template: '<div class="q-linear-progress" />',
    props: ['value', 'buffer', 'color', 'trackColor', 'dark', 'reverse', 'stripe', 'indeterminate', 'query', 'rounded', 'animationSpeed', 'instantFeedback', 'size'],
  },
  QInnerLoading: {
    name: 'QInnerLoading',
    template: '<div v-if="showing" class="q-inner-loading"><slot /></div>',
    props: ['showing', 'color', 'size', 'dark', 'transitionShow', 'transitionHide', 'transitionDuration', 'label', 'labelClass', 'labelStyle'],
  },
  QSlideTransition: {
    name: 'QSlideTransition',
    template: '<div class="q-slide-transition"><slot /></div>',
    props: ['appear', 'duration'],
  },
  QIntersection: {
    name: 'QIntersection',
    template: '<div class="q-intersection"><slot /></div>',
    props: ['tag', 'once', 'ssrPrerender', 'root', 'margin', 'threshold', 'transition', 'transitionDuration', 'disable'],
    emits: ['visibility'],
  },
  QResponsive: {
    name: 'QResponsive',
    template: '<div class="q-responsive"><slot /></div>',
    props: ['ratio'],
  },
  QNoSsr: {
    name: 'QNoSsr',
    template: '<div class="q-no-ssr"><slot /></div>',
    props: ['tag', 'placeholder'],
  },
  QFab: {
    name: 'QFab',
    template: '<div class="q-fab"><slot /></div>',
    props: ['modelValue', 'icon', 'activeIcon', 'hideIcon', 'hideLabel', 'direction', 'vertical-actions-align', 'persistent', 'type', 'outline', 'push', 'flat', 'unelevated', 'padding', 'color', 'textColor', 'glossy', 'externalLabel', 'label', 'labelPosition', 'labelClass', 'labelStyle', 'square', 'disable', 'tabindex'],
    emits: ['update:modelValue', 'show', 'before-show', 'hide', 'before-hide'],
  },
  QFabAction: {
    name: 'QFabAction',
    template: '<button class="q-fab__action"><slot /></button>',
    props: ['icon', 'anchor', 'to', 'replace', 'type', 'outline', 'push', 'flat', 'unelevated', 'padding', 'color', 'textColor', 'glossy', 'externalLabel', 'label', 'labelPosition', 'labelClass', 'labelStyle', 'square', 'disable', 'tabindex'],
    emits: ['click'],
  },
  QPageSticky: {
    name: 'QPageSticky',
    template: '<div class="q-page-sticky"><slot /></div>',
    props: ['position', 'offset', 'expand'],
  },
  QPullToRefresh: {
    name: 'QPullToRefresh',
    template: '<div class="q-pull-to-refresh"><slot /></div>',
    props: ['color', 'bgColor', 'icon', 'noMouse', 'disable', 'scrollTarget'],
    emits: ['refresh'],
  },
  QInfiniteScroll: {
    name: 'QInfiniteScroll',
    template: '<div class="q-infinite-scroll"><slot /></div>',
    props: ['offset', 'debounce', 'scrollTarget', 'initialIndex', 'disable', 'reverse'],
    emits: ['load'],
  },
  QVirtualScroll: {
    name: 'QVirtualScroll',
    template: '<div class="q-virtual-scroll"><slot /></div>',
    props: ['virtualScrollSliceSize', 'virtualScrollSliceRatioBefore', 'virtualScrollSliceRatioAfter', 'virtualScrollItemSize', 'virtualScrollStickySizeStart', 'virtualScrollStickySizeEnd', 'tableColspan', 'type', 'items', 'itemsFn', 'itemsSize', 'scrollTarget'],
    emits: ['virtual-scroll'],
  },
  RouterLink: {
    name: 'RouterLink',
    template: '<a :href="to" @click.prevent="$emit(\'click\', $event)"><slot /></a>',
    props: ['to', 'replace', 'activeClass', 'exactActiveClass', 'custom', 'ariaCurrentValue'],
    emits: ['click'],
  },
  RouterView: {
    name: 'RouterView',
    template: '<div class="router-view"><slot /></div>',
    props: ['name', 'route'],
  },
};

// ============================================
// Quasar Plugin Mocks
// ============================================

const mockNotify = vi.fn();
mockNotify.create = vi.fn();
mockNotify.setDefaults = vi.fn();
mockNotify.registerType = vi.fn();

const mockDialogResult = {
  onOk: vi.fn().mockReturnThis(),
  onCancel: vi.fn().mockReturnThis(),
  onDismiss: vi.fn().mockReturnThis(),
  hide: vi.fn(),
  update: vi.fn(),
};

const mockDialog = vi.fn().mockReturnValue(mockDialogResult);
mockDialog.create = vi.fn().mockReturnValue(mockDialogResult);

const mockLoading = {
  show: vi.fn(),
  hide: vi.fn(),
  isActive: false,
  setDefaults: vi.fn(),
};

const mockLocalStorage = {
  has: vi.fn().mockReturnValue(false),
  getLength: vi.fn().mockReturnValue(0),
  getItem: vi.fn().mockReturnValue(null),
  getIndex: vi.fn().mockReturnValue(null),
  getKey: vi.fn().mockReturnValue(null),
  getAll: vi.fn().mockReturnValue({}),
  getAllKeys: vi.fn().mockReturnValue([]),
  set: vi.fn(),
  remove: vi.fn(),
  clear: vi.fn(),
  isEmpty: vi.fn().mockReturnValue(true),
};

const mockSessionStorage = {
  has: vi.fn().mockReturnValue(false),
  getLength: vi.fn().mockReturnValue(0),
  getItem: vi.fn().mockReturnValue(null),
  getIndex: vi.fn().mockReturnValue(null),
  getKey: vi.fn().mockReturnValue(null),
  getAll: vi.fn().mockReturnValue({}),
  getAllKeys: vi.fn().mockReturnValue([]),
  set: vi.fn(),
  remove: vi.fn(),
  clear: vi.fn(),
  isEmpty: vi.fn().mockReturnValue(true),
};

const mockBottomSheet = vi.fn().mockReturnValue({
  onOk: vi.fn().mockReturnThis(),
  onCancel: vi.fn().mockReturnThis(),
  onDismiss: vi.fn().mockReturnThis(),
  hide: vi.fn(),
});

// Quasar $q object mock
const mockQuasar = {
  notify: mockNotify,
  dialog: mockDialog,
  loading: mockLoading,
  localStorage: mockLocalStorage,
  sessionStorage: mockSessionStorage,
  bottomSheet: mockBottomSheet,
  dark: {
    isActive: false,
    mode: false,
    set: vi.fn(),
    toggle: vi.fn(),
  },
  screen: {
    width: 1920,
    height: 1080,
    name: 'lg',
    sizes: { sm: 600, md: 1024, lg: 1440, xl: 1920 },
    lt: { sm: false, md: false, lg: false, xl: false },
    gt: { xs: true, sm: true, md: true, lg: true },
    xs: false,
    sm: false,
    md: false,
    lg: true,
    xl: false,
    setSizes: vi.fn(),
    setDebounce: vi.fn(),
  },
  platform: {
    is: {
      desktop: true,
      mobile: false,
      ios: false,
      android: false,
      chrome: true,
      firefox: false,
      safari: false,
      edge: false,
      ie: false,
      opera: false,
      mac: false,
      linux: false,
      win: true,
      cros: false,
      capacitor: false,
      cordova: false,
      electron: false,
      bex: false,
      nativeMobile: false,
      nativeMobileWrapper: false,
    },
    has: {
      touch: false,
      webStorage: true,
    },
    within: {
      iframe: false,
    },
  },
  lang: {
    isoName: 'en-US',
    nativeName: 'English',
    label: {
      clear: 'Clear',
      ok: 'OK',
      cancel: 'Cancel',
      close: 'Close',
      set: 'Set',
      select: 'Select',
      reset: 'Reset',
      remove: 'Remove',
      update: 'Update',
      create: 'Create',
      search: 'Search',
      filter: 'Filter',
      refresh: 'Refresh',
    },
    date: {},
    table: {},
    editor: {},
    tree: {},
  },
  iconSet: {
    name: 'material-icons',
  },
};

// ============================================
// Vue-i18n Mock
// ============================================

const mockT = vi.fn((key: string, ...args: unknown[]) => {
  // Return the key itself for easy testing
  // Can inspect what translation keys are being used
  if (args.length > 0 && typeof args[0] === 'object') {
    // Handle named interpolation
    let result = key;
    const params = args[0] as Record<string, unknown>;
    Object.entries(params).forEach(([k, v]) => {
      result = result.replace(`{${k}}`, String(v));
    });
    return result;
  }
  return key;
});

const mockTc = vi.fn((key: string, choice: number) => `${key}[${choice}]`);
const mockTe = vi.fn(() => true);
const mockTm = vi.fn((key: string) => key);
const mockRt = vi.fn((message: string) => message);
const mockD = vi.fn((date: Date) => date.toISOString());
const mockN = vi.fn((value: number) => String(value));

const mockI18n = {
  locale: ref('en'),
  fallbackLocale: ref('en'),
  messages: ref({}),
  t: mockT,
  tc: mockTc,
  te: mockTe,
  tm: mockTm,
  rt: mockRt,
  d: mockD,
  n: mockN,
  availableLocales: ['en', 'ru'],
  getLocaleMessage: vi.fn(() => ({})),
  setLocaleMessage: vi.fn(),
  mergeLocaleMessage: vi.fn(),
};

// ============================================
// Vue-Router Mock
// ============================================

const mockRoute = reactive({
  path: '/',
  name: 'home',
  params: {} as Record<string, string>,
  query: {} as Record<string, string>,
  hash: '',
  fullPath: '/',
  matched: [] as unknown[],
  meta: {} as Record<string, unknown>,
  redirectedFrom: undefined as unknown,
});

const mockRouter = {
  currentRoute: ref(mockRoute),
  push: vi.fn().mockResolvedValue(undefined),
  replace: vi.fn().mockResolvedValue(undefined),
  go: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  beforeEach: vi.fn().mockReturnValue(vi.fn()),
  afterEach: vi.fn().mockReturnValue(vi.fn()),
  onError: vi.fn().mockReturnValue(vi.fn()),
  isReady: vi.fn().mockResolvedValue(undefined),
  resolve: vi.fn((to: string | { name: string }) => ({
    href: typeof to === 'string' ? to : `/${to.name}`,
    route: mockRoute,
  })),
  addRoute: vi.fn(),
  removeRoute: vi.fn(),
  hasRoute: vi.fn().mockReturnValue(true),
  getRoutes: vi.fn().mockReturnValue([]),
  options: {},
  install: vi.fn(),
};

// Mock vue-router composables
vi.mock('vue-router', () => ({
  useRouter: () => mockRouter,
  useRoute: () => mockRoute,
  RouterLink: quasarComponentStubs.RouterLink,
  RouterView: quasarComponentStubs.RouterView,
  createRouter: vi.fn(() => mockRouter),
  createWebHistory: vi.fn(),
  createWebHashHistory: vi.fn(),
  createMemoryHistory: vi.fn(),
}));

// ============================================
// PouchDB Mock
// ============================================

interface MockPouchDBDoc {
  _id: string;
  _rev?: string;
  _deleted?: boolean;
  type?: string;
  [key: string]: unknown;
}

interface MockPouchDBOptions {
  selector?: Record<string, unknown>;
  sort?: Array<Record<string, 'asc' | 'desc'>>;
  limit?: number;
  skip?: number;
}

const createMockPouchDB = () => {
  const store = new Map<string, MockPouchDBDoc>();
  let revCounter = 1;

  return {
    get: vi.fn(async (id: string) => {
      const doc = store.get(id);
      if (!doc) {
        const error = new Error('missing') as Error & { status: number };
        error.status = 404;
        throw error;
      }
      return { ...doc };
    }),
    put: vi.fn(async (doc: MockPouchDBDoc) => {
      const rev = `${revCounter++}-mock`;
      store.set(doc._id, { ...doc, _rev: rev });
      return { ok: true, id: doc._id, rev };
    }),
    remove: vi.fn(async (docOrId: string | MockPouchDBDoc, rev?: string) => {
      const id = typeof docOrId === 'string' ? docOrId : docOrId._id;
      store.delete(id);
      return { ok: true, id, rev: rev || `${revCounter++}-mock` };
    }),
    bulkDocs: vi.fn(async (docs: MockPouchDBDoc[]) => {
      return docs.map((doc) => {
        const rev = `${revCounter++}-mock`;
        if (doc._deleted) {
          store.delete(doc._id);
        } else {
          store.set(doc._id, { ...doc, _rev: rev });
        }
        return { ok: true, id: doc._id, rev };
      });
    }),
    allDocs: vi.fn(async (options?: { include_docs?: boolean; keys?: string[] }) => {
      const rows = Array.from(store.entries())
        .filter(([id]) => !options?.keys || options.keys.includes(id))
        .map(([id, doc]) => ({
          id,
          key: id,
          value: { rev: doc._rev },
          doc: options?.include_docs ? doc : undefined,
        }));
      return { total_rows: rows.length, offset: 0, rows };
    }),
    find: vi.fn(async (options: MockPouchDBOptions) => {
      let docs = Array.from(store.values()).filter((doc) => !doc._deleted);

      // Basic selector filtering
      if (options.selector) {
        docs = docs.filter((doc) => {
          return Object.entries(options.selector || {}).every(([key, value]) => {
            if (key === '$and' || key === '$or') return true; // Skip complex operators
            if (typeof value === 'object' && value !== null) {
              // Handle operators like $eq, $ne, $in, $exists
              const ops = value as Record<string, unknown>;
              if ('$eq' in ops) return doc[key] === ops.$eq;
              if ('$ne' in ops) return doc[key] !== ops.$ne;
              if ('$in' in ops) return (ops.$in as unknown[]).includes(doc[key]);
              if ('$exists' in ops) return ops.$exists ? key in doc : !(key in doc);
              if ('$elemMatch' in ops) {
                const arr = doc[key];
                if (!Array.isArray(arr)) return false;
                const match = ops.$elemMatch as Record<string, unknown>;
                return arr.some((item) => item === match.$eq);
              }
              return true;
            }
            return doc[key] === value;
          });
        });
      }

      // Basic sorting
      if (options.sort) {
        docs.sort((a, b) => {
          for (const sortObj of options.sort || []) {
            const [field, order] = Object.entries(sortObj)[0];
            const aVal = String(a[field] || '');
            const bVal = String(b[field] || '');
            const cmp = aVal.localeCompare(bVal);
            if (cmp !== 0) return order === 'desc' ? -cmp : cmp;
          }
          return 0;
        });
      }

      // Pagination
      if (options.skip) docs = docs.slice(options.skip);
      if (options.limit) docs = docs.slice(0, options.limit);

      return { docs };
    }),
    createIndex: vi.fn(async () => ({ result: 'created' })),
    changes: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      cancel: vi.fn(),
      then: vi.fn().mockResolvedValue({ results: [], last_seq: 0 }),
    })),
    compact: vi.fn(async () => ({ ok: true })),
    destroy: vi.fn(async () => ({ ok: true })),
    close: vi.fn(async () => undefined),
    info: vi.fn(async () => ({
      db_name: 'test',
      doc_count: store.size,
      update_seq: revCounter,
    })),
    // Test helper to clear the store
    _clear: () => store.clear(),
    _store: store,
  };
};

const mockPouchDB = createMockPouchDB();

// Mock PouchDB service
vi.mock('@/services/pouchdb', () => ({
  getDatabase: vi.fn(() => mockPouchDB),
  find: vi.fn(mockPouchDB.find),
  findById: vi.fn(mockPouchDB.get),
  upsert: vi.fn(mockPouchDB.put),
  softDelete: vi.fn(async (id: string) => {
    const doc = await mockPouchDB.get(id);
    return mockPouchDB.put({ ...doc, _deleted: true });
  }),
  subscribeToChanges: vi.fn(() => vi.fn()),
  getWishlists: vi.fn(async () => []),
  getSharedWishlists: vi.fn(async () => []),
  getItems: vi.fn(async () => []),
  getItemCounts: vi.fn(async () => ({})),
  getMarks: vi.fn(async () => []),
  getMarksByUser: vi.fn(async () => []),
  getBookmarks: vi.fn(async () => []),
  subscribeToWishlists: vi.fn(() => vi.fn()),
  subscribeToSharedWishlists: vi.fn(() => vi.fn()),
  subscribeToItems: vi.fn(() => vi.fn()),
  subscribeToMarks: vi.fn(() => vi.fn()),
  subscribeToBookmarks: vi.fn(() => vi.fn()),
  startSync: vi.fn(),
  stopSync: vi.fn(),
  triggerSync: vi.fn(async () => undefined),
  getSyncStatus: vi.fn(() => 'idle'),
  isSyncing: vi.fn(() => false),
  onSyncComplete: vi.fn(() => vi.fn()),
  destroyDatabase: vi.fn(async () => undefined),
  clearDatabase: vi.fn(async () => undefined),
  createId: vi.fn((type: string) => `${type}:test-${Math.random().toString(36).slice(2, 10)}`),
  extractId: vi.fn((docId: string) => docId.split(':')[1] || docId),
}));

// ============================================
// Axios/API Mock
// ============================================

interface MockAxiosResponse<T = unknown> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
  config: Record<string, unknown>;
}

const createMockResponse = <T>(data: T, status = 200): MockAxiosResponse<T> => ({
  data,
  status,
  statusText: status === 200 ? 'OK' : 'Error',
  headers: {},
  config: {},
});

const mockApi = {
  get: vi.fn().mockResolvedValue(createMockResponse({})),
  post: vi.fn().mockResolvedValue(createMockResponse({})),
  put: vi.fn().mockResolvedValue(createMockResponse({})),
  patch: vi.fn().mockResolvedValue(createMockResponse({})),
  delete: vi.fn().mockResolvedValue(createMockResponse({})),
  request: vi.fn().mockResolvedValue(createMockResponse({})),
  defaults: {
    baseURL: 'http://localhost:8000',
    headers: {
      common: {},
    },
  },
  interceptors: {
    request: {
      use: vi.fn(),
      eject: vi.fn(),
      clear: vi.fn(),
    },
    response: {
      use: vi.fn(),
      eject: vi.fn(),
      clear: vi.fn(),
    },
  },
  create: vi.fn(() => mockApi),
};

vi.mock('@/boot/axios', () => ({
  api: mockApi,
  getApiBaseUrl: vi.fn(() => 'http://localhost:8000'),
}));

vi.mock('axios', () => ({
  default: mockApi,
  ...mockApi,
}));

// ============================================
// Global Test Configuration
// ============================================

// Configure Vue Test Utils
config.global.stubs = quasarComponentStubs;

config.global.mocks = {
  $q: mockQuasar,
  $t: mockT,
  $tc: mockTc,
  $te: mockTe,
  $tm: mockTm,
  $rt: mockRt,
  $d: mockD,
  $n: mockN,
  $i18n: mockI18n,
  $router: mockRouter,
  $route: mockRoute,
};

config.global.provide = {
  // Quasar uses provide/inject for some features
};

// ============================================
// Test Lifecycle Hooks
// ============================================

beforeEach(() => {
  // Clear all mock call history
  vi.clearAllMocks();

  // Reset route to default
  mockRoute.path = '/';
  mockRoute.name = 'home';
  mockRoute.params = {};
  mockRoute.query = {};
  mockRoute.hash = '';
  mockRoute.fullPath = '/';
  mockRoute.meta = {};

  // Clear PouchDB store
  mockPouchDB._clear();
});

afterEach(() => {
  // Additional cleanup if needed
});

// ============================================
// Exports for Test Files
// ============================================

export {
  mockQuasar,
  mockNotify,
  mockDialog,
  mockDialogResult,
  mockLoading,
  mockLocalStorage,
  mockSessionStorage,
  mockBottomSheet,
  mockT,
  mockI18n,
  mockRouter,
  mockRoute,
  mockPouchDB,
  mockApi,
  createMockResponse,
  quasarComponentStubs,
};
