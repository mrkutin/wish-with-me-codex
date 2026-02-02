/**
 * Unit tests for the SyncStatus component.
 * Tests icon display, color states, animations, and click behavior.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, VueWrapper } from '@vue/test-utils';
import { ref, computed } from 'vue';
import { nextTick } from 'vue';
import SyncStatus from '../SyncStatus.vue';

// Mock useSync composable
const mockStatus = ref<'idle' | 'syncing' | 'error' | 'offline'>('idle');
const mockPendingCount = ref(0);
const mockIsOnline = ref(true);
const mockTriggerSync = vi.fn();

vi.mock('@/composables/useSync', () => ({
  useSync: () => ({
    status: computed(() => {
      if (!mockIsOnline.value) return 'offline';
      return mockStatus.value;
    }),
    pendingCount: computed(() => mockPendingCount.value),
    triggerSync: mockTriggerSync,
    isOnline: computed(() => mockIsOnline.value),
  }),
}));

describe('SyncStatus', () => {
  let wrapper: VueWrapper;

  function mountComponent() {
    return mount(SyncStatus, {
      global: {
        stubs: {
          QBtn: {
            name: 'QBtn',
            template: `
              <button
                :class="$attrs.class"
                @click="$emit('click', $event)"
              >
                <span class="icon-name" :data-icon="$attrs.icon" :data-color="$attrs.color">{{ $attrs.icon }}</span>
                <slot />
              </button>
            `,
          },
          QBadge: {
            name: 'QBadge',
            template: '<span class="q-badge" :data-color="$attrs.color"><slot /></span>',
          },
          QTooltip: {
            name: 'QTooltip',
            template: '<span class="q-tooltip"><slot /></span>',
          },
        },
      },
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    mockStatus.value = 'idle';
    mockPendingCount.value = 0;
    mockIsOnline.value = true;
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('icon display', () => {
    it('shows cloud_off icon when offline', async () => {
      mockIsOnline.value = false;

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-icon')).toBe('cloud_off');
    });

    it('shows cloud_sync icon when syncing', async () => {
      mockStatus.value = 'syncing';

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-icon')).toBe('cloud_sync');
    });

    it('shows sync_problem icon when error', async () => {
      mockStatus.value = 'error';

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-icon')).toBe('sync_problem');
    });

    it('shows cloud_upload icon when idle with pending items', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 5;

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-icon')).toBe('cloud_upload');
    });

    it('shows cloud_done icon when idle with no pending items', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 0;

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-icon')).toBe('cloud_done');
    });
  });

  describe('icon color', () => {
    it('shows grey-6 color when offline', async () => {
      mockIsOnline.value = false;

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-color')).toBe('grey-6');
    });

    it('shows primary color when syncing', async () => {
      mockStatus.value = 'syncing';

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-color')).toBe('primary');
    });

    it('shows negative color when error', async () => {
      mockStatus.value = 'error';

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-color')).toBe('negative');
    });

    it('shows warning color when idle with pending items', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 3;

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-color')).toBe('warning');
    });

    it('shows positive color when idle with no pending items', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 0;

      wrapper = mountComponent();
      await nextTick();

      const iconSpan = wrapper.find('.icon-name');
      expect(iconSpan.attributes('data-color')).toBe('positive');
    });
  });

  describe('spinning animation', () => {
    it('applies sync-spinning class when syncing', async () => {
      mockStatus.value = 'syncing';

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      expect(button.classes()).toContain('sync-spinning');
    });

    it('does not apply sync-spinning class when not syncing', async () => {
      mockStatus.value = 'idle';

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      expect(button.classes()).not.toContain('sync-spinning');
    });

    it('does not apply sync-spinning class when offline', async () => {
      mockIsOnline.value = false;

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      expect(button.classes()).not.toContain('sync-spinning');
    });

    it('does not apply sync-spinning class when error', async () => {
      mockStatus.value = 'error';

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      expect(button.classes()).not.toContain('sync-spinning');
    });
  });

  describe('error badge', () => {
    it('shows error badge when status is error', async () => {
      mockStatus.value = 'error';

      wrapper = mountComponent();
      await nextTick();

      const badge = wrapper.find('.q-badge');
      expect(badge.exists()).toBe(true);
      expect(badge.attributes('data-color')).toBe('negative');
      expect(badge.text()).toBe('!');
    });

    it('does not show error badge when status is not error', async () => {
      mockStatus.value = 'idle';

      wrapper = mountComponent();
      await nextTick();

      const badges = wrapper.findAll('.q-badge');
      const errorBadge = badges.find(
        (badge) => badge.attributes('data-color') === 'negative'
      );
      expect(errorBadge).toBeUndefined();
    });
  });

  describe('pending count badge', () => {
    it('shows pending count badge when pendingCount > 0', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 5;

      wrapper = mountComponent();
      await nextTick();

      const badge = wrapper.find('.q-badge');
      expect(badge.exists()).toBe(true);
      expect(badge.attributes('data-color')).toBe('warning');
      expect(badge.text()).toBe('5');
    });

    it('does not show pending badge when pendingCount is 0', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 0;

      wrapper = mountComponent();
      await nextTick();

      const badges = wrapper.findAll('.q-badge');
      const warningBadge = badges.find(
        (badge) => badge.attributes('data-color') === 'warning'
      );
      expect(warningBadge).toBeUndefined();
    });

    it('shows 99+ when pendingCount exceeds 99', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 150;

      wrapper = mountComponent();
      await nextTick();

      const badge = wrapper.find('.q-badge');
      expect(badge.text()).toBe('99+');
    });

    it('shows exact count when pendingCount is 99', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 99;

      wrapper = mountComponent();
      await nextTick();

      const badge = wrapper.find('.q-badge');
      expect(badge.text()).toBe('99');
    });

    it('shows error badge instead of pending badge when error', async () => {
      mockStatus.value = 'error';
      mockPendingCount.value = 5;

      wrapper = mountComponent();
      await nextTick();

      const badge = wrapper.find('.q-badge');
      // Error badge takes precedence
      expect(badge.attributes('data-color')).toBe('negative');
      expect(badge.text()).toBe('!');
    });
  });

  describe('click behavior', () => {
    it('triggers sync when online and not syncing', async () => {
      mockIsOnline.value = true;
      mockStatus.value = 'idle';

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      await button.trigger('click');

      expect(mockTriggerSync).toHaveBeenCalled();
    });

    it('does not trigger sync when offline', async () => {
      mockIsOnline.value = false;

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      await button.trigger('click');

      expect(mockTriggerSync).not.toHaveBeenCalled();
    });

    it('does not trigger sync when already syncing', async () => {
      mockIsOnline.value = true;
      mockStatus.value = 'syncing';

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      await button.trigger('click');

      expect(mockTriggerSync).not.toHaveBeenCalled();
    });

    it('triggers sync when error status (to retry)', async () => {
      mockIsOnline.value = true;
      mockStatus.value = 'error';

      wrapper = mountComponent();
      await nextTick();

      const button = wrapper.find('button');
      await button.trigger('click');

      expect(mockTriggerSync).toHaveBeenCalled();
    });
  });

  describe('tooltip', () => {
    it('shows offline tooltip when offline', async () => {
      mockIsOnline.value = false;

      wrapper = mountComponent();
      await nextTick();

      const tooltip = wrapper.find('.q-tooltip');
      expect(tooltip.text()).toContain('offline.statusOffline');
    });

    it('shows syncing tooltip when syncing', async () => {
      mockStatus.value = 'syncing';

      wrapper = mountComponent();
      await nextTick();

      const tooltip = wrapper.find('.q-tooltip');
      expect(tooltip.text()).toContain('offline.statusSyncing');
    });

    it('shows error tooltip when error', async () => {
      mockStatus.value = 'error';

      wrapper = mountComponent();
      await nextTick();

      const tooltip = wrapper.find('.q-tooltip');
      expect(tooltip.text()).toContain('offline.statusError');
    });

    it('shows pending tooltip when idle with pending items', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 5;

      wrapper = mountComponent();
      await nextTick();

      const tooltip = wrapper.find('.q-tooltip');
      expect(tooltip.text()).toContain('offline.statusPending');
    });

    it('shows synced tooltip when idle with no pending items', async () => {
      mockStatus.value = 'idle';
      mockPendingCount.value = 0;

      wrapper = mountComponent();
      await nextTick();

      const tooltip = wrapper.find('.q-tooltip');
      expect(tooltip.text()).toContain('offline.statusSynced');
    });
  });
});
