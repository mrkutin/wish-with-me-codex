/**
 * Unit tests for the ItemCard component.
 * Tests rendering of item data, status badges, events, and links.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, VueWrapper } from '@vue/test-utils';
import ItemCard from '../ItemCard.vue';
import type { Item } from '@/types/item';

// Helper to create a mock item
function createMockItem(overrides: Partial<Item> = {}): Item {
  return {
    id: 'item:123',
    wishlist_id: 'wishlist:456',
    title: 'Test Product',
    description: 'This is a test product description',
    price: 1500,
    currency: 'RUB',
    quantity: 1,
    source_url: 'https://example.com/product',
    image_url: null,
    image_base64: null,
    status: 'resolved',
    resolver_metadata: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

// Override QMenu stub to always show content for testing
const testStubs = {
  QMenu: {
    name: 'QMenu',
    template: '<div class="q-menu"><slot /></div>',
    props: ['modelValue'],
  },
};

describe('ItemCard', () => {
  let wrapper: VueWrapper;

  function mountComponent(item: Item) {
    return mount(ItemCard, {
      props: { item },
      global: {
        stubs: testStubs,
      },
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders title and description', () => {
      const item = createMockItem({
        title: 'My Awesome Product',
        description: 'A detailed description of the product',
      });

      wrapper = mountComponent(item);

      expect(wrapper.find('.item-title').text()).toBe('My Awesome Product');
      expect(wrapper.find('.item-description').text()).toBe(
        'A detailed description of the product'
      );
    });

    it('truncates long descriptions to 100 characters', () => {
      const longDescription =
        'This is a very long description that exceeds one hundred characters and should be truncated with ellipsis at the end';
      const item = createMockItem({ description: longDescription });

      wrapper = mountComponent(item);

      const descriptionText = wrapper.find('.item-description').text();
      expect(descriptionText.length).toBeLessThanOrEqual(103); // 100 chars + '...'
      expect(descriptionText).toContain('...');
    });

    it('does not render description element when description is null', () => {
      const item = createMockItem({ description: null });

      wrapper = mountComponent(item);

      expect(wrapper.find('.item-description').exists()).toBe(false);
    });

    it('renders image when image_base64 is provided', () => {
      const item = createMockItem({
        image_base64: 'data:image/png;base64,ABC123',
      });

      wrapper = mountComponent(item);

      const img = wrapper.find('.q-img');
      expect(img.exists()).toBe(true);
      expect(img.attributes('src')).toBe('data:image/png;base64,ABC123');
    });

    it('renders placeholder when no image is provided', () => {
      const item = createMockItem({
        image_base64: null,
        image_url: null,
      });

      wrapper = mountComponent(item);

      expect(wrapper.find('.item-image-placeholder').exists()).toBe(true);
      expect(wrapper.find('.q-img').exists()).toBe(false);
    });

    it('renders quantity', () => {
      const item = createMockItem({ quantity: 5 });

      wrapper = mountComponent(item);

      expect(wrapper.find('.item-quantity').text()).toContain('5');
    });
  });

  describe('formatPrice', () => {
    it('formats price with currency using Intl.NumberFormat', () => {
      const item = createMockItem({
        price: 1500,
        currency: 'RUB',
      });

      wrapper = mountComponent(item);

      const priceText = wrapper.find('.item-price').text();
      // The format depends on the locale, but should contain the number
      expect(priceText).toMatch(/1[,.\s]?500/);
    });

    it('formats price with USD currency', () => {
      const item = createMockItem({
        price: 99.99,
        currency: 'USD',
      });

      wrapper = mountComponent(item);

      const priceText = wrapper.find('.item-price').text();
      expect(priceText).toMatch(/99[.,]99|\$99[.,]99/);
    });

    it('uses USD as default currency when currency is null', () => {
      const item = createMockItem({
        price: 50,
        currency: null,
      });

      wrapper = mountComponent(item);

      const priceText = wrapper.find('.item-price').text();
      // Should format as USD
      expect(priceText).toMatch(/50|\$50/);
    });

    it('does not render price when price is null', () => {
      const item = createMockItem({
        price: null,
      });

      wrapper = mountComponent(item);

      expect(wrapper.find('.item-price').exists()).toBe(false);
    });
  });

  describe('status badges', () => {
    it('shows pending badge when status is pending', () => {
      const item = createMockItem({ status: 'pending' });

      wrapper = mountComponent(item);

      const badge = wrapper.find('.status-badge');
      expect(badge.exists()).toBe(true);
      expect(badge.text()).toContain('items.pending');
    });

    it('shows in_progress badge when status is in_progress', () => {
      const item = createMockItem({ status: 'in_progress' });

      wrapper = mountComponent(item);

      const badge = wrapper.find('.status-badge');
      expect(badge.exists()).toBe(true);
      expect(badge.text()).toContain('items.resolving');
    });

    it('shows resolved badge when status is resolved', () => {
      const item = createMockItem({ status: 'resolved' });

      wrapper = mountComponent(item);

      const badge = wrapper.find('.status-badge');
      expect(badge.exists()).toBe(true);
      expect(badge.text()).toContain('items.resolved');
    });

    it('shows error badge when status is error', () => {
      const item = createMockItem({ status: 'error' });

      wrapper = mountComponent(item);

      const badge = wrapper.find('.status-badge');
      expect(badge.exists()).toBe(true);
      expect(badge.text()).toContain('items.resolveFailed');
    });

    it('shows retry button only when status is error', () => {
      const itemError = createMockItem({ status: 'error' });
      const itemResolved = createMockItem({ status: 'resolved' });

      wrapper = mountComponent(itemError);
      expect(wrapper.find('.retry-btn').exists()).toBe(true);

      wrapper = mountComponent(itemResolved);
      expect(wrapper.find('.retry-btn').exists()).toBe(false);
    });
  });

  describe('events', () => {
    it('emits edit event when edit menu item is clicked', async () => {
      const item = createMockItem();

      wrapper = mountComponent(item);

      // Find the edit menu item and click it (menu is always visible in test)
      const menuItems = wrapper.findAll('.q-item');
      const editItem = menuItems.find((el) => el.text().includes('common.edit'));

      expect(editItem).toBeDefined();
      if (editItem) {
        await editItem.trigger('click');

        expect(wrapper.emitted('edit')).toBeTruthy();
        expect(wrapper.emitted('edit')?.[0]).toEqual([item]);
      }
    });

    it('emits delete event when delete menu item is clicked', async () => {
      const item = createMockItem();

      wrapper = mountComponent(item);

      // Find the delete menu item and click it
      const menuItems = wrapper.findAll('.q-item');
      const deleteItem = menuItems.find((el) =>
        el.text().includes('common.delete')
      );

      expect(deleteItem).toBeDefined();
      if (deleteItem) {
        await deleteItem.trigger('click');

        expect(wrapper.emitted('delete')).toBeTruthy();
        expect(wrapper.emitted('delete')?.[0]).toEqual([item]);
      }
    });

    it('emits retry event when retry button is clicked', async () => {
      const item = createMockItem({ status: 'error' });

      wrapper = mountComponent(item);

      const retryBtn = wrapper.find('.retry-btn');
      await retryBtn.trigger('click');

      expect(wrapper.emitted('retry')).toBeTruthy();
      expect(wrapper.emitted('retry')?.[0]).toEqual([item]);
    });
  });

  describe('source URL', () => {
    it('renders source_url as external link', () => {
      const item = createMockItem({
        source_url: 'https://example.com/product/123',
      });

      wrapper = mountComponent(item);

      const link = wrapper.find('.item-source-link');
      expect(link.exists()).toBe(true);
      expect(link.attributes('href')).toBe('https://example.com/product/123');
      expect(link.attributes('target')).toBe('_blank');
      expect(link.attributes('rel')).toBe('noopener noreferrer');
    });

    it('does not render source link when source_url is null', () => {
      const item = createMockItem({
        source_url: null,
      });

      wrapper = mountComponent(item);

      expect(wrapper.find('.item-source-link').exists()).toBe(false);
    });

    it('link has noopener noreferrer for security', () => {
      const item = createMockItem({
        source_url: 'https://example.com/product',
      });

      wrapper = mountComponent(item);

      const link = wrapper.find('.item-source-link');
      expect(link.attributes('rel')).toContain('noopener');
      expect(link.attributes('rel')).toContain('noreferrer');
    });
  });
});
