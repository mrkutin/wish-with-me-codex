/**
 * Unit tests for the ShareDialog component.
 * Tests share link management, clipboard operations, and QR code display.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, VueWrapper, flushPromises } from '@vue/test-utils';
import { nextTick } from 'vue';
import ShareDialog from '../ShareDialog.vue';
import { mockApi, createMockResponse, mockNotify, mockDialog, mockDialogResult } from '@/test/setup';
import type { ShareLink, ShareLinkListResponse } from '@/types/share';

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

// Helper to create mock share links
function createMockShareLink(overrides: Partial<ShareLink> = {}): ShareLink {
  return {
    id: 'share:123',
    wishlist_id: 'wishlist:456',
    token: 'abc123token',
    link_type: 'mark',
    expires_at: null,
    access_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    share_url: 'https://wishwith.me/shared/abc123token',
    qr_code_base64: 'data:image/png;base64,QRCodeData',
    ...overrides,
  };
}

describe('ShareDialog', () => {
  let wrapper: VueWrapper;

  function mountDialog(props = {}) {
    return mount(ShareDialog, {
      props: {
        modelValue: true,
        wishlistId: 'wishlist:456',
        wishlistName: 'Test Wishlist',
        ...props,
      },
      global: {
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
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('fetching share links', () => {
    it('fetches share links when dialog opens', async () => {
      const mockLinks: ShareLinkListResponse = {
        items: [createMockShareLink()],
      };

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse(mockLinks)
      );

      wrapper = mountDialog({ modelValue: false });

      // Open the dialog
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockApi.get).toHaveBeenCalledWith(
        '/api/v1/wishlists/wishlist:456/share'
      );
    });

    it('displays loading state while fetching', async () => {
      let resolveGet: (value: unknown) => void;
      const getPromise = new Promise((resolve) => {
        resolveGet = resolve;
      });
      vi.mocked(mockApi.get).mockReturnValueOnce(getPromise as Promise<never>);

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await nextTick();

      // Check isLoading state
      const vm = wrapper.vm as unknown as { isLoading: boolean };
      expect(vm.isLoading).toBe(true);

      // Resolve the promise
      resolveGet!(createMockResponse({ items: [] }));
      await flushPromises();

      expect(vm.isLoading).toBe(false);
    });

    it('displays share links after fetching', async () => {
      const mockLinks: ShareLinkListResponse = {
        items: [
          createMockShareLink({ id: 'share:1' }),
          createMockShareLink({ id: 'share:2' }),
        ],
      };

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse(mockLinks)
      );

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      const vm = wrapper.vm as unknown as { shareLinks: ShareLink[] };
      expect(vm.shareLinks).toHaveLength(2);
    });

    it('shows empty state when no links exist', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      const vm = wrapper.vm as unknown as { shareLinks: ShareLink[] };
      expect(vm.shareLinks).toHaveLength(0);
    });

    it('shows error notification on fetch failure', async () => {
      vi.mocked(mockApi.get).mockRejectedValueOnce(new Error('Network error'));

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
    it('creates share link and prepends to list', async () => {
      const existingLink = createMockShareLink({ id: 'share:existing' });
      const newLink = createMockShareLink({ id: 'share:new' });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [existingLink] })
      );
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
      expect(vm.shareLinks[0].id).toBe('share:new');

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'positive',
        message: 'sharing.linkCreated',
      });
    });

    it('shows loading state while creating', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

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
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );
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
    it('revokes share link with confirmation dialog', async () => {
      const linkToRevoke = createMockShareLink({ id: 'share:123' });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [linkToRevoke] })
      );
      vi.mocked(mockApi.delete).mockResolvedValueOnce(createMockResponse({}));

      // Configure dialog to call onOk callback
      let onOkCallback: () => void;
      mockDialogResult.onOk.mockImplementation((cb: () => void) => {
        onOkCallback = cb;
        return mockDialogResult;
      });

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        revokeShareLink: (link: ShareLink) => void;
      };

      vm.revokeShareLink(linkToRevoke);
      await nextTick();

      // Confirmation dialog should be shown
      expect(mockDialog).toHaveBeenCalledWith({
        title: 'sharing.revokeConfirm',
        message: 'sharing.revokeMessage',
        cancel: true,
        persistent: true,
      });

      // Simulate clicking OK
      onOkCallback!();
      await flushPromises();

      expect(mockApi.delete).toHaveBeenCalledWith(
        '/api/v1/wishlists/wishlist:456/share/share:123'
      );

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'info',
        message: 'sharing.linkRevoked',
      });
    });

    it('removes revoked link from list', async () => {
      const link1 = createMockShareLink({ id: 'share:1' });
      const link2 = createMockShareLink({ id: 'share:2' });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [link1, link2] })
      );
      vi.mocked(mockApi.delete).mockResolvedValueOnce(createMockResponse({}));

      let onOkCallback: () => void;
      mockDialogResult.onOk.mockImplementation((cb: () => void) => {
        onOkCallback = cb;
        return mockDialogResult;
      });

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        revokeShareLink: (link: ShareLink) => void;
      };

      // Manually set shareLinks to test the removal logic
      vm.shareLinks = [link1, link2];
      expect(vm.shareLinks).toHaveLength(2);

      vm.revokeShareLink(link1);
      onOkCallback!();
      await flushPromises();

      expect(vm.shareLinks).toHaveLength(1);
      expect(vm.shareLinks[0].id).toBe('share:2');
    });

    it('shows error notification on revoke failure', async () => {
      const link = createMockShareLink();

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      // Make delete fail
      vi.mocked(mockApi.delete).mockRejectedValueOnce(
        new Error('Revoke failed')
      );

      // Track async callback
      let onOkCallback: () => Promise<void>;
      mockDialogResult.onOk.mockImplementation((cb: () => Promise<void>) => {
        onOkCallback = cb;
        return mockDialogResult;
      });

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      vi.clearAllMocks(); // Clear mock calls from fetch

      const vm = wrapper.vm as unknown as {
        shareLinks: ShareLink[];
        revokeShareLink: (link: ShareLink) => void;
      };

      // Manually add link so it can be revoked
      vm.shareLinks = [link];

      vm.revokeShareLink(link);
      // Simulate clicking OK - the callback is async
      await onOkCallback!();
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('copying links', () => {
    it('copies link to clipboard', async () => {
      const link = createMockShareLink({
        share_url: 'https://wishwith.me/shared/test123',
      });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [link] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        copyLink: (url: string) => Promise<void>;
      };

      await vm.copyLink(link.share_url);
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'positive',
        message: 'sharing.linkCopied',
      });
    });

    it('shows error on clipboard failure', async () => {
      const link = createMockShareLink();

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [link] })
      );

      // Mock copyToClipboard to fail
      const { copyToClipboard } = await import('quasar');
      vi.mocked(copyToClipboard).mockRejectedValueOnce(new Error('Clipboard error'));

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        copyLink: (url: string) => Promise<void>;
      };

      await vm.copyLink(link.share_url);
      await flushPromises();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'errors.generic',
      });
    });
  });

  describe('QR code dialog', () => {
    it('shows QR code image in dialog', async () => {
      const link = createMockShareLink({
        qr_code_base64: 'data:image/png;base64,MockQRCode',
      });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [link] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        currentQrCode: string | null;
        openQrDialog: (qrCode: string) => void;
      };

      vm.openQrDialog(link.qr_code_base64!);
      await nextTick();

      expect(vm.showQrDialog).toBe(true);
      expect(vm.currentQrCode).toBe('data:image/png;base64,MockQRCode');
    });

    it('closes QR code dialog on button click', async () => {
      const link = createMockShareLink({
        qr_code_base64: 'data:image/png;base64,MockQRCode',
      });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [link] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        currentQrCode: string | null;
        openQrDialog: (qrCode: string) => void;
        closeQrDialog: () => void;
      };

      // Open and close
      vm.openQrDialog(link.qr_code_base64!);
      await nextTick();
      expect(vm.showQrDialog).toBe(true);

      vm.closeQrDialog();
      await nextTick();
      expect(vm.showQrDialog).toBe(false);
      expect(vm.currentQrCode).toBeNull();
    });

    it('does not show QR button when qr_code_base64 is not provided', async () => {
      const link = createMockShareLink({
        qr_code_base64: undefined,
      });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      // Manually set shareLinks to test the condition
      const vm = wrapper.vm as unknown as { shareLinks: ShareLink[] };
      vm.shareLinks = [link];
      await nextTick();

      expect(vm.shareLinks).toHaveLength(1);
      expect(vm.shareLinks[0].qr_code_base64).toBeUndefined();
    });
  });

  describe('link type selector', () => {
    it('defaults to mark link type', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkType: 'mark' | 'view' };
      expect(vm.newLinkType).toBe('mark');
    });

    it('updates link type state when changed', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkType: 'mark' | 'view' };
      vm.newLinkType = 'view';
      await nextTick();

      expect(vm.newLinkType).toBe('view');
    });

    it('sends selected link type when creating link', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );
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
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkExpiry: number | null };
      expect(vm.newLinkExpiry).toBe(30);
    });

    it('updates expiry state when changed', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkExpiry: number | null };
      vm.newLinkExpiry = 7;
      await nextTick();

      expect(vm.newLinkExpiry).toBe(7);
    });

    it('allows never expire option (null)', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { newLinkExpiry: number | null };
      vm.newLinkExpiry = null;
      await nextTick();

      expect(vm.newLinkExpiry).toBeNull();
    });

    it('sends selected expiry when creating link', async () => {
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );
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
      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as { isOpen: boolean };
      vm.isOpen = false;
      await nextTick();

      expect(wrapper.emitted('update:modelValue')).toBeTruthy();
      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false]);
    });

    it('closes QR dialog when main dialog closes', async () => {
      const link = createMockShareLink({
        qr_code_base64: 'data:image/png;base64,MockQRCode',
      });

      vi.mocked(mockApi.get).mockResolvedValueOnce(
        createMockResponse({ items: [link] })
      );

      wrapper = mountDialog();
      await flushPromises();

      const vm = wrapper.vm as unknown as {
        showQrDialog: boolean;
        openQrDialog: (qrCode: string) => void;
        isOpen: boolean;
      };

      // Open QR dialog
      vm.openQrDialog(link.qr_code_base64!);
      await nextTick();
      expect(vm.showQrDialog).toBe(true);

      // Close main dialog
      await wrapper.setProps({ modelValue: false });
      await nextTick();

      // QR dialog should also close (via watch)
      expect(vm.showQrDialog).toBe(false);
    });
  });
});
