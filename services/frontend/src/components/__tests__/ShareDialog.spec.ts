/**
 * Unit tests for the ShareDialog component.
 * Tests share link management, clipboard operations, and QR code display.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, VueWrapper, flushPromises } from '@vue/test-utils';
import { nextTick } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import ShareDialog from '../ShareDialog.vue';
import { mockApi, createMockResponse, mockNotify, mockDialog, mockDialogResult } from '@/test/setup';
import type { ShareLink } from '@/types/share';
import type { ShareDoc } from '@/services/pouchdb';

// Mock qrcode
vi.mock('qrcode', () => ({
  default: {
    toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,MockQRCode'),
  },
}));

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

// Mock quasar
vi.mock('quasar', async () => {
  const actual = await vi.importActual('quasar');
  return {
    ...actual,
    useQuasar: () => ({
      notify: mockNotify,
      dialog: mockDialog,
    }),
    copyToClipboard: vi.fn().mockResolvedValue(undefined),
  };
});

// Mock PouchDB service
const mockGetShares = vi.fn();
const mockSubscribeToShares = vi.fn();
const mockTriggerSync = vi.fn();
const mockExtractId = vi.fn((id: string) => id.split(':')[1] || id);

vi.mock('@/services/pouchdb', () => ({
  getShares: (...args: unknown[]) => mockGetShares(...args),
  subscribeToShares: (...args: unknown[]) => mockSubscribeToShares(...args),
  triggerSync: (...args: unknown[]) => mockTriggerSync(...args),
  extractId: (id: string) => mockExtractId(id),
}));

// Mock auth store
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    userId: 'user:test123',
  }),
}));

// Helper to create mock share links (API response format)
function createMockShareLink(overrides: Partial<ShareLink> = {}): ShareLink {
  return {
    id: '123',
    wishlist_id: 'wishlist:456',
    token: 'abc123token',
    link_type: 'mark',
    expires_at: null,
    access_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    share_url: 'https://wishwith.me/s/abc123token',
    ...overrides,
  };
}

// Helper to create mock share docs (PouchDB format)
function createMockShareDoc(overrides: Partial<ShareDoc> = {}): ShareDoc {
  return {
    _id: 'share:123',
    _rev: '1-abc',
    type: 'share',
    wishlist_id: 'wishlist:456',
    owner_id: 'user:test123',
    token: 'abc123token',
    link_type: 'mark',
    expires_at: null,
    access_count: 0,
    revoked: false,
    granted_users: [],
    access: ['user:test123'],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('ShareDialog', () => {
  let wrapper: VueWrapper;

  function mountDialog(props = {}) {
    // Set up Pinia for auth store
    const pinia = createPinia();
    setActivePinia(pinia);

    return mount(ShareDialog, {
      props: {
        modelValue: true,
        wishlistId: 'wishlist:456',
        wishlistName: 'Test Wishlist',
        ...props,
      },
      global: {
        plugins: [pinia],
        stubs: {
          QDialog: {
            name: 'QDialog',
            template: '<div class="q-dialog" v-if="modelValue"><slot /></div>',
            props: ['modelValue', 'persistent'],
            emits: ['update:modelValue'],
          },
          QOptionGroup: {
            name: 'QOptionGroup',
            template: '<div class="q-option-group"><slot /></div>',
            props: ['modelValue', 'options', 'type', 'inline', 'dense'],
            emits: ['update:modelValue'],
          },
        },
      },
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock implementations
    mockGetShares.mockResolvedValue([]);
    mockSubscribeToShares.mockReturnValue(() => {});
    mockTriggerSync.mockResolvedValue(undefined);
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('fetching share links', () => {
    it('fetches share links from PouchDB when dialog opens', async () => {
      const mockDocs = [createMockShareDoc()];
      mockGetShares.mockResolvedValueOnce(mockDocs);

      wrapper = mountDialog({ modelValue: false });

      // Open the dialog
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockGetShares).toHaveBeenCalledWith('wishlist:456', 'user:test123');
    });

    it('displays loading state while fetching', async () => {
      let resolveGet: (value: ShareDoc[]) => void;
      const getPromise = new Promise<ShareDoc[]>((resolve) => {
        resolveGet = resolve;
      });
      mockGetShares.mockReturnValueOnce(getPromise);

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await nextTick();

      // Check isLoading state
      const vm = wrapper.vm as unknown as { isLoading: boolean };
      expect(vm.isLoading).toBe(true);

      // Resolve the promise
      resolveGet!([]);
      await flushPromises();

      expect(vm.isLoading).toBe(false);
    });

    it('displays share links after fetching', async () => {
      const mockDocs = [
        createMockShareDoc({ _id: 'share:1' }),
        createMockShareDoc({ _id: 'share:2' }),
      ];
      mockGetShares.mockResolvedValueOnce(mockDocs);

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      const vm = wrapper.vm as unknown as { shareLinks: ShareLink[] };
      expect(vm.shareLinks).toHaveLength(2);
    });

    it('shows empty state when no links exist', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      const vm = wrapper.vm as unknown as { shareLinks: ShareLink[] };
      expect(vm.shareLinks).toHaveLength(0);
    });

    it('shows error notification on fetch failure', async () => {
      mockGetShares.mockRejectedValueOnce(new Error('PouchDB error'));

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('creating share links', () => {
    it('creates share link via API and triggers sync', async () => {
      const existingDoc = createMockShareDoc({ _id: 'share:existing' });
      const newLink = createMockShareLink({ id: 'new' });

      mockGetShares.mockResolvedValueOnce([existingDoc]);
      vi.mocked(mockApi.post).mockResolvedValueOnce(
        createMockResponse(newLink)
      );

      wrapper = mountDialog();
      await flushPromises();

      // Call createShareLink
      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        createShareLink: () => Promise<void>;
      };

      await vm.createShareLink();
      await flushPromises();

      expect(mockApi.post).toHaveBeenCalledWith(
        '/api/v1/wishlists/wishlist:456/share',
        expect.objectContaining({
          link_type: 'mark',
          expires_in_days: 30,
        })
      );

      // New link should be at the beginning
      expect(vm.shareLinks[0].id).toBe('new');

      // Should trigger sync to pull the new share into PouchDB
      expect(mockTriggerSync).toHaveBeenCalled();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'positive',
        message: 'sharing.linkCreated',
      });
    });

    it('shows loading state while creating', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      let resolvePost: (value: unknown) => void;
      const postPromise = new Promise((resolve) => {
        resolvePost = resolve;
      });
      vi.mocked(mockApi.post).mockReturnValueOnce(postPromise as Promise<never>);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        isCreating: boolean;
        createShareLink: () => Promise<void>;
      };

      const createPromise = vm.createShareLink();
      await nextTick();

      expect(vm.isCreating).toBe(true);

      resolvePost!(createMockResponse(createMockShareLink()));
      await createPromise;
      await flushPromises();

      expect(vm.isCreating).toBe(false);
    });

    it('shows error notification on create failure', async () => {
      mockGetShares.mockResolvedValueOnce([]);
      vi.mocked(mockApi.post).mockRejectedValueOnce(new Error('Create failed'));

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        createShareLink: () => Promise<void>;
      };

      await vm.createShareLink();
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('revoking share links', () => {
    it('shows confirmation dialog when revoking', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        revokeShareLink: (link: ShareLink) => void;
      };

      // Manually add a link to revoke
      const link = createMockShareLink({ id: '123' });
      vm.shareLinks = [link];

      vm.revokeShareLink(link);
      await nextTick();

      // Confirmation dialog should be shown
      expect(mockDialog).toHaveBeenCalledWith({
        title: 'sharing.revokeConfirm',
        message: 'sharing.revokeMessage',
        cancel: true,
        persistent: true,
      });
    });

    it('calls delete API and triggers sync on confirmation', async () => {
      mockGetShares.mockResolvedValueOnce([]);
      vi.mocked(mockApi.delete).mockResolvedValueOnce(createMockResponse({}));

      // Set up dialog to immediately call onOk callback
      let capturedCallback: () => void;
      mockDialogResult.onOk.mockImplementation((cb: () => void) => {
        capturedCallback = cb;
        return mockDialogResult;
      });

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        revokeShareLink: (link: ShareLink) => void;
      };

      // Manually add a link to revoke
      const link = createMockShareLink({ id: '123' });
      vm.shareLinks = [link];

      // Trigger revoke
      vm.revokeShareLink(link);
      await nextTick();

      // Execute the captured callback
      capturedCallback!();
      await flushPromises();

      expect(mockApi.delete).toHaveBeenCalledWith(
        '/api/v1/wishlists/wishlist:456/share/123'
      );
      expect(mockTriggerSync).toHaveBeenCalled();
    });

    it('removes revoked link from list', async () => {
      mockGetShares.mockResolvedValueOnce([]);
      vi.mocked(mockApi.delete).mockResolvedValueOnce(createMockResponse({}));

      let capturedCallback: () => void;
      mockDialogResult.onOk.mockImplementation((cb: () => void) => {
        capturedCallback = cb;
        return mockDialogResult;
      });

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        revokeShareLink: (link: ShareLink) => void;
      };

      // Manually set shareLinks to test the removal logic
      const link1 = createMockShareLink({ id: '1' });
      const link2 = createMockShareLink({ id: '2' });
      vm.shareLinks = [link1, link2];

      vm.revokeShareLink(link1);
      capturedCallback!();
      await flushPromises();

      expect(vm.shareLinks).toHaveLength(1);
      expect(vm.shareLinks[0].id).toBe('2');
    });

    it('shows error notification on revoke failure', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      let capturedCallback: () => void;
      mockDialogResult.onOk.mockImplementation((cb: () => void) => {
        capturedCallback = cb;
        return mockDialogResult;
      });

      wrapper = mountDialog();
      await flushPromises();

      // Set up delete to fail AFTER mounting
      vi.mocked(mockApi.delete).mockRejectedValueOnce(
        new Error('Revoke failed')
      );

      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        revokeShareLink: (link: ShareLink) => void;
      };

      const link = createMockShareLink();
      vm.shareLinks = [link];

      vm.revokeShareLink(link);
      capturedCallback!();
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('copying links', () => {
    it('copies link to clipboard', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        copyLink: (url: string) => Promise<void>;
      };

      await vm.copyLink('https://wishwith.me/s/test123');
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'positive',
        message: 'sharing.linkCopied',
      });
    });

    it('shows error on clipboard failure', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      // Mock copyToClipboard to fail
      const { copyToClipboard } = await import('quasar');
      vi.mocked(copyToClipboard).mockRejectedValueOnce(new Error('Clipboard error'));

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        copyLink: (url: string) => Promise<void>;
      };

      await vm.copyLink('https://wishwith.me/s/test123');
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('QR code dialog', () => {
    it('generates QR code client-side and shows in dialog', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        currentQrCode: string | null;
        openQrDialog: (shareUrl: string) => Promise<void>;
      };

      await vm.openQrDialog('https://wishwith.me/s/abc123token');
      await flushPromises();

      expect(vm.showQrDialog).toBe(true);
      expect(vm.currentQrCode).toBe('data:image/png;base64,MockQRCode');
    });

    it('closes QR code dialog on button click', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        currentQrCode: string | null;
        openQrDialog: (shareUrl: string) => Promise<void>;
        closeQrDialog: () => void;
      };

      // Open and close
      await vm.openQrDialog('https://wishwith.me/s/abc123token');
      await flushPromises();
      expect(vm.showQrDialog).toBe(true);

      vm.closeQrDialog();
      await nextTick();
      expect(vm.showQrDialog).toBe(false);
      expect(vm.currentQrCode).toBeNull();
    });

    it('shows error notification when QR generation fails', async () => {
      const QRCode = await import('qrcode');
      vi.mocked(QRCode.default.toDataURL).mockRejectedValueOnce(new Error('QR generation failed'));

      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        openQrDialog: (shareUrl: string) => Promise<void>;
      };

      await vm.openQrDialog('https://wishwith.me/s/abc123token');
      await flushPromises();

      expect(vm.showQrDialog).toBe(false);
      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('link type selector', () => {
    it('defaults to mark link type', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkType: 'mark' | 'view' };
      expect(vm.newLinkType).toBe('mark');
    });

    it('updates link type state when changed', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkType: 'mark' | 'view' };
      vm.newLinkType = 'view';
      await nextTick();

      expect(vm.newLinkType).toBe('view');
    });

    it('sends selected link type when creating link', async () => {
      mockGetShares.mockResolvedValueOnce([]);
      vi.mocked(mockApi.post).mockResolvedValueOnce(
        createMockResponse(createMockShareLink({ link_type: 'view' }))
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        newLinkType: 'mark' | 'view';
        createShareLink: () => Promise<void>;
      };

      vm.newLinkType = 'view';
      await nextTick();

      await vm.createShareLink();
      await flushPromises();

      expect(mockApi.post).toHaveBeenCalledWith(
        '/api/v1/wishlists/wishlist:456/share',
        expect.objectContaining({
          link_type: 'view',
        })
      );
    });
  });

  describe('expiry selector', () => {
    it('defaults to 30 days expiry', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkExpiry: number | null };
      expect(vm.newLinkExpiry).toBe(30);
    });

    it('updates expiry state when changed', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkExpiry: number | null };
      vm.newLinkExpiry = 7;
      await nextTick();

      expect(vm.newLinkExpiry).toBe(7);
    });

    it('allows never expire option (null)', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkExpiry: number | null };
      vm.newLinkExpiry = null;
      await nextTick();

      expect(vm.newLinkExpiry).toBeNull();
    });

    it('sends selected expiry when creating link', async () => {
      mockGetShares.mockResolvedValueOnce([]);
      vi.mocked(mockApi.post).mockResolvedValueOnce(
        createMockResponse(createMockShareLink())
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        newLinkExpiry: number | null;
        createShareLink: () => Promise<void>;
      };

      vm.newLinkExpiry = 90;
      await nextTick();

      await vm.createShareLink();
      await flushPromises();

      expect(mockApi.post).toHaveBeenCalledWith(
        '/api/v1/wishlists/wishlist:456/share',
        expect.objectContaining({
          expires_in_days: 90,
        })
      );
    });
  });

  describe('dialog close', () => {
    it('emits update:modelValue false when close button is clicked', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { isOpen: boolean };
      vm.isOpen = false;
      await nextTick();

      expect(wrapper.emitted('update:modelValue')).toBeTruthy();
      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false]);
    });

    it('closes QR dialog when main dialog closes', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        openQrDialog: (shareUrl: string) => Promise<void>;
        isOpen: boolean;
      };

      // Open QR dialog
      await vm.openQrDialog('https://wishwith.me/s/abc123token');
      await flushPromises();
      expect(vm.showQrDialog).toBe(true);

      // Close main dialog
      await wrapper.setProps({ modelValue: false });
      await nextTick();

      // QR dialog should also close (via watch)
      expect(vm.showQrDialog).toBe(false);
    });
  });

  describe('subscription management', () => {
    it('subscribes to share changes when dialog opens', async () => {
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockSubscribeToShares).toHaveBeenCalledWith(
        'wishlist:456',
        'user:test123',
        expect.any(Function)
      );
    });

    it('cleans up subscription when dialog closes', async () => {
      const mockUnsubscribe = vi.fn();
      mockSubscribeToShares.mockReturnValue(mockUnsubscribe);
      mockGetShares.mockResolvedValueOnce([]);

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      // Close dialog
      await wrapper.setProps({ modelValue: false });
      await flushPromises();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });
});
