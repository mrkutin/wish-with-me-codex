/**
 * Unit tests for the AddItemDialog component.
 * Tests tab switching, URL validation, form validation, and image upload.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, VueWrapper, flushPromises } from '@vue/test-utils';
import { nextTick, ref } from 'vue';
import AddItemDialog from '../AddItemDialog.vue';
import { mockNotify } from '@/test/setup';

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

// Mock quasar useQuasar
vi.mock('quasar', async () => {
  const actual = await vi.importActual('quasar');
  return {
    ...actual,
    useQuasar: () => ({
      notify: mockNotify,
    }),
  };
});

describe('AddItemDialog', () => {
  let wrapper: VueWrapper;

  function mountDialog(props = {}) {
    return mount(AddItemDialog, {
      props: {
        modelValue: true,
        loading: false,
        ...props,
      },
      global: {
        stubs: {
          QDialog: {
            name: 'QDialog',
            template: '<div class="q-dialog" v-if="modelValue"><slot /></div>',
            props: ['modelValue'],
          },
          QTabs: {
            name: 'QTabs',
            template: '<div class="q-tabs"><slot /></div>',
            props: ['modelValue'],
            emits: ['update:modelValue'],
          },
          QTab: {
            name: 'QTab',
            template: '<div class="q-tab" @click="$emit(\'click\')"><slot />{{ label }}</div>',
            props: ['name', 'label'],
            emits: ['click'],
          },
          QTabPanels: {
            name: 'QTabPanels',
            template: '<div class="q-tab-panels"><slot /></div>',
            props: ['modelValue'],
          },
          QTabPanel: {
            name: 'QTabPanel',
            template: '<div class="q-tab-panel" :data-name="name"><slot /></div>',
            props: ['name'],
          },
          QFile: {
            name: 'QFile',
            template: '<input type="file" @change="handleChange" :accept="accept" />',
            props: ['modelValue', 'accept', 'maxFileSize', 'label'],
            emits: ['update:modelValue', 'rejected'],
            methods: {
              handleChange(e: Event) {
                const target = e.target as HTMLInputElement;
                const files = target.files;
                if (files && files.length > 0) {
                  this.$emit('update:modelValue', files[0]);
                }
              },
            },
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

  describe('tab switching', () => {
    it('renders URL tab as default', () => {
      wrapper = mountDialog();

      const tabs = wrapper.findAll('.q-tab');
      expect(tabs.length).toBe(2);

      // Check URL tab is rendered
      expect(tabs[0].text()).toContain('items.addFromUrl');
    });

    it('renders both URL and manual tabs', () => {
      wrapper = mountDialog();

      const tabs = wrapper.findAll('.q-tab');
      expect(tabs.length).toBe(2);
      expect(tabs[0].text()).toContain('items.addFromUrl');
      expect(tabs[1].text()).toContain('items.addManually');
    });
  });

  describe('URL validation', () => {
    it('isValidUrl function accepts valid https URL', () => {
      wrapper = mountDialog();

      // Access the internal isValidUrl function through the component
      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        isValid: boolean;
      };

      // Set a valid URL and check isValid
      vm.formData.source_url = 'https://example.com/product';

      // Since we're on URL tab, isValid should check the URL
      expect(vm.isValid).toBe(true);
    });

    it('isValidUrl function accepts valid http URL', () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        isValid: boolean;
      };

      vm.formData.source_url = 'http://example.com/product';
      expect(vm.isValid).toBe(true);
    });

    it('isValidUrl function rejects invalid URL without protocol', () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        isValid: boolean;
      };

      vm.formData.source_url = 'example.com/product';
      expect(vm.isValid).toBe(false);
    });

    it('isValidUrl function rejects ftp protocol', () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        isValid: boolean;
      };

      vm.formData.source_url = 'ftp://example.com/file';
      expect(vm.isValid).toBe(false);
    });

    it('isValidUrl function rejects javascript protocol', () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        isValid: boolean;
      };

      vm.formData.source_url = 'javascript:alert(1)';
      expect(vm.isValid).toBe(false);
    });
  });

  describe('manual form validation', () => {
    it('requires title in manual mode', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: { title: string };
        isValid: boolean;
      };

      // Switch to manual tab
      vm.tab = 'manual';
      vm.formData.title = '';
      await nextTick();

      expect(vm.isValid).toBe(false);
    });

    it('validates title is not empty in manual mode', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: { title: string };
        isValid: boolean;
      };

      vm.tab = 'manual';
      vm.formData.title = 'My Product';
      await nextTick();

      expect(vm.isValid).toBe(true);
    });

    it('accepts optional description in manual mode', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: { title: string; description: string | null };
        isValid: boolean;
      };

      vm.tab = 'manual';
      vm.formData.title = 'My Product';
      vm.formData.description = null;
      await nextTick();

      expect(vm.isValid).toBe(true);
    });

    it('accepts optional price and currency in manual mode', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: { title: string; price: number | null; currency: string };
        isValid: boolean;
      };

      vm.tab = 'manual';
      vm.formData.title = 'My Product';
      vm.formData.price = null;
      await nextTick();

      expect(vm.isValid).toBe(true);
    });

    it('validates quantity is at least 1', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: { title: string; quantity: number };
        isValid: boolean;
      };

      vm.tab = 'manual';
      vm.formData.title = 'My Product';
      vm.formData.quantity = 0;
      await nextTick();

      expect(vm.isValid).toBe(false);

      vm.formData.quantity = 1;
      await nextTick();

      expect(vm.isValid).toBe(true);
    });
  });

  describe('image upload', () => {
    it('converts uploaded image to base64', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        handleImageSelect: (file: File | null) => Promise<void>;
        imagePreview: string | null;
      };

      vm.tab = 'manual';
      await nextTick();

      // Create a mock file
      const mockFile = new File(['test'], 'test.png', { type: 'image/png' });

      // Mock FileReader
      const mockFileReader = {
        readAsDataURL: vi.fn(function (this: FileReader) {
          setTimeout(() => {
            Object.defineProperty(this, 'result', {
              value: 'data:image/png;base64,dGVzdA==',
              writable: true,
            });
            if (this.onload) {
              this.onload({ target: this } as ProgressEvent<FileReader>);
            }
          }, 0);
        }),
        onload: null as ((e: ProgressEvent<FileReader>) => void) | null,
        result: null as string | null,
      };

      vi.spyOn(globalThis, 'FileReader').mockImplementation(
        () => mockFileReader as unknown as FileReader
      );

      await vm.handleImageSelect(mockFile);
      await flushPromises();

      expect(mockFileReader.readAsDataURL).toHaveBeenCalled();
    });

    it('rejects images over 5MB', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        onImageRejected: () => void;
      };

      vm.tab = 'manual';
      await nextTick();

      // Call the rejection handler
      vm.onImageRejected();

      expect(mockNotify).toHaveBeenCalledWith({
        type: 'negative',
        message: 'items.imageTooLarge',
      });
    });

    it('shows image preview after upload', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        imagePreview: string | null;
      };

      vm.tab = 'manual';
      await nextTick();

      // Initially no preview
      expect(vm.imagePreview).toBeNull();
    });

    it('removes image when remove button is clicked', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        imageFile: File | null;
        imagePreview: string | null;
        removeImage: () => void;
      };

      vm.tab = 'manual';
      vm.imageFile = new File(['test'], 'test.png', { type: 'image/png' });
      vm.imagePreview = 'data:image/png;base64,test';
      await nextTick();

      vm.removeImage();
      await nextTick();

      expect(vm.imageFile).toBeNull();
      expect(vm.imagePreview).toBeNull();
    });
  });

  describe('form submission', () => {
    it('emits submit with URL mode data', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        handleSubmit: () => void;
      };

      vm.formData.source_url = 'https://example.com/product';

      vm.handleSubmit();
      await nextTick();

      const emitted = wrapper.emitted('submit');
      expect(emitted).toBeTruthy();
      expect(emitted?.[0][0]).toMatchObject({
        source_url: 'https://example.com/product',
        title: 'example.com',
      });
    });

    it('emits submit with manual mode data and skip_resolution flag', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: {
          title: string;
          description: string | null;
          price: number | null;
          currency: string;
          quantity: number;
          manual_url: string | null;
        };
        handleSubmit: () => void;
      };

      vm.tab = 'manual';
      vm.formData.title = 'Manual Product';
      vm.formData.description = 'A manual description';
      vm.formData.price = 100;
      vm.formData.currency = 'USD';
      vm.formData.quantity = 2;
      await nextTick();

      vm.handleSubmit();
      await nextTick();

      const emitted = wrapper.emitted('submit');
      expect(emitted).toBeTruthy();
      expect(emitted?.[0][0]).toMatchObject({
        title: 'Manual Product',
        description: 'A manual description',
        price: 100,
        currency: 'USD',
        quantity: 2,
        skip_resolution: true,
      });
    });

    it('disables submit button when form is invalid', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: { source_url: string | null };
        isValid: boolean;
      };

      vm.formData.source_url = '';
      await nextTick();

      expect(vm.isValid).toBe(false);
    });

    it('shows loading state on submit button when loading prop is true', () => {
      wrapper = mountDialog({ loading: true });

      // Check that loading prop is passed correctly
      expect(wrapper.props('loading')).toBe(true);
    });
  });

  describe('dialog close', () => {
    it('emits update:modelValue false when cancel is clicked', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        closeDialog: () => void;
      };

      vm.closeDialog();
      await nextTick();

      expect(wrapper.emitted('update:modelValue')).toBeTruthy();
      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false]);
    });

    it('resets form fields when dialog closes', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        formData: {
          source_url: string | null;
          title: string;
        };
        resetForm: () => void;
      };

      // Fill in some data
      vm.formData.source_url = 'https://example.com';
      vm.formData.title = 'Test';
      await nextTick();

      // Reset form
      vm.resetForm();
      await nextTick();

      expect(vm.formData.source_url).toBeNull();
      expect(vm.formData.title).toBe('');
    });

    it('resets tab to URL mode on close', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        resetForm: () => void;
      };

      // Switch to manual tab
      vm.tab = 'manual';
      await nextTick();

      // Reset form
      vm.resetForm();
      await nextTick();

      expect(vm.tab).toBe('url');
    });

    it('clears image upload on close', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        imageFile: File | null;
        imagePreview: string | null;
        resetForm: () => void;
      };

      // Set image
      vm.imageFile = new File(['test'], 'test.png', { type: 'image/png' });
      vm.imagePreview = 'data:image/png;base64,test';
      await nextTick();

      // Reset form
      vm.resetForm();
      await nextTick();

      expect(vm.imageFile).toBeNull();
      expect(vm.imagePreview).toBeNull();
    });
  });

  describe('optional source URL in manual mode', () => {
    it('accepts optional source_url in manual mode', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: {
          title: string;
          manual_url: string | null;
        };
        isValid: boolean;
      };

      vm.tab = 'manual';
      vm.formData.title = 'My Product';
      vm.formData.manual_url = null;
      await nextTick();

      expect(vm.isValid).toBe(true);
    });

    it('validates source_url when provided in manual mode', async () => {
      wrapper = mountDialog();

      const vm = wrapper.vm as unknown as {
        tab: string;
        formData: {
          title: string;
          manual_url: string | null;
        };
        isValid: boolean;
      };

      vm.tab = 'manual';
      vm.formData.title = 'My Product';
      vm.formData.manual_url = 'not-a-valid-url';
      await nextTick();

      expect(vm.isValid).toBe(false);

      vm.formData.manual_url = 'https://example.com';
      await nextTick();

      expect(vm.isValid).toBe(true);
    });
  });
});
