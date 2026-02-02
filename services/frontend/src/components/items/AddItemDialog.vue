<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="min-width: 400px; max-width: 500px">
      <q-card-section>
        <div class="text-h6">{{ $t('items.add') }}</div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-tabs
          v-model="tab"
          dense
          class="text-grey"
          active-color="primary"
          indicator-color="primary"
          align="justify"
        >
          <q-tab name="url" :label="$t('items.addFromUrl')" />
          <q-tab name="manual" :label="$t('items.addManually')" />
        </q-tabs>

        <q-separator class="q-my-md" />

        <q-tab-panels v-model="tab" animated>
          <!-- From URL Tab -->
          <q-tab-panel name="url">
            <q-input
              v-model="formData.source_url"
              :label="$t('items.url')"
              outlined
              type="url"
              :hint="$t('items.urlHint')"
              autofocus
              :rules="[
                (val) => !!val || $t('validation.required'),
                (val) => isValidUrl(val) || $t('validation.invalidUrl'),
              ]"
            >
              <template #prepend>
                <q-icon name="link" />
              </template>
            </q-input>

            <div class="text-caption text-grey-7 q-mt-md">
              {{ $t('items.urlDescription') }}
            </div>
          </q-tab-panel>

          <!-- Manual Tab -->
          <q-tab-panel name="manual">
            <q-input
              v-model="formData.title"
              :label="$t('items.itemTitle')"
              outlined
              autofocus
              :rules="[(val) => !!val || $t('validation.required')]"
            />

            <q-input
              v-model="formData.description"
              :label="$t('items.description')"
              outlined
              type="textarea"
              rows="3"
              class="q-mt-md"
            />

            <div class="row q-col-gutter-md q-mt-sm">
              <div class="col-8">
                <q-input
                  v-model.number="formData.price"
                  :label="$t('items.price')"
                  outlined
                  type="number"
                  step="0.01"
                  min="0"
                />
              </div>
              <div class="col-4">
                <q-input
                  v-model="formData.currency"
                  :label="$t('items.currency')"
                  outlined
                  maxlength="3"
                  placeholder="RUB"
                />
              </div>
            </div>

            <q-input
              v-model.number="formData.quantity"
              :label="$t('items.quantity')"
              outlined
              type="number"
              min="1"
              class="q-mt-md"
              :rules="[(val) => val >= 1 || $t('validation.minValue', { min: 1 })]"
            />

            <q-input
              v-model="formData.manual_url"
              :label="$t('items.sourceUrl')"
              outlined
              type="url"
              class="q-mt-md"
              :hint="$t('items.sourceUrlHint')"
              :rules="[
                (val) => !val || isValidUrl(val) || $t('validation.invalidUrl'),
              ]"
            >
              <template #prepend>
                <q-icon name="link" />
              </template>
            </q-input>

            <!-- Image upload -->
            <div class="q-mt-md">
              <div class="text-caption text-grey-7 q-mb-sm">{{ $t('items.image') }}</div>
              <div class="row items-start q-gutter-md">
                <q-file
                  v-model="imageFile"
                  :label="$t('items.uploadImage')"
                  outlined
                  accept="image/*"
                  max-file-size="5242880"
                  class="col"
                  @update:model-value="handleImageSelect"
                  @rejected="onImageRejected"
                >
                  <template #prepend>
                    <q-icon name="image" />
                  </template>
                </q-file>
                <div v-if="imagePreview" class="image-preview">
                  <q-img :src="imagePreview" :ratio="1" style="width: 80px; height: 80px; border-radius: 8px" />
                  <q-btn
                    round
                    dense
                    flat
                    icon="close"
                    size="sm"
                    class="remove-image-btn"
                    @click="removeImage"
                  />
                </div>
              </div>
            </div>
          </q-tab-panel>
        </q-tab-panels>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat :label="$t('common.cancel')" @click="closeDialog" />
        <q-btn
          color="primary"
          :label="$t('common.create')"
          @click="handleSubmit"
          :loading="loading"
          :disable="!isValid"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { ItemCreate } from '@/types/item';

const $q = useQuasar();
const { t } = useI18n();

interface Props {
  modelValue: boolean;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
});

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  submit: [data: ItemCreate];
}>();

const tab = ref<'url' | 'manual'>('url');
const imageFile = ref<File | null>(null);
const imagePreview = ref<string | null>(null);

const formData = reactive<ItemCreate & { source_url: string | null; manual_url: string | null }>({
  title: '',
  description: null,
  price: null,
  currency: 'RUB',
  quantity: 1,
  source_url: null,
  manual_url: null,
});

const isValid = computed(() => {
  if (tab.value === 'url') {
    return !!formData.source_url && isValidUrl(formData.source_url);
  } else {
    const urlValid = !formData.manual_url || isValidUrl(formData.manual_url);
    return !!formData.title && (formData.quantity ?? 1) >= 1 && urlValid;
  }
});

function isValidUrl(url: string | null): boolean {
  if (!url) return false;
  try {
    const urlObj = new URL(url);
    return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
  } catch {
    return false;
  }
}

async function handleImageSelect(file: File | null) {
  if (!file) {
    imagePreview.value = null;
    return;
  }

  // Convert to base64
  const reader = new FileReader();
  reader.onload = (e) => {
    imagePreview.value = e.target?.result as string;
  };
  reader.readAsDataURL(file);
}

function removeImage() {
  imageFile.value = null;
  imagePreview.value = null;
}

function onImageRejected() {
  $q.notify({
    type: 'negative',
    message: t('items.imageTooLarge'),
  });
}

function handleSubmit() {
  if (!isValid.value) return;

  const data: ItemCreate = {};

  if (tab.value === 'url') {
    // For URL-based items, only send the URL
    // The backend will automatically trigger resolution
    data.source_url = formData.source_url;
    // Use URL hostname as temporary title until resolved
    try {
      const urlObj = new URL(formData.source_url!);
      data.title = urlObj.hostname;
    } catch {
      data.title = formData.source_url!;
    }
  } else {
    // For manual items, send all filled fields
    data.title = formData.title;
    if (formData.description) data.description = formData.description;
    if (formData.price !== null) data.price = formData.price;
    if (formData.currency) data.currency = formData.currency;
    data.quantity = formData.quantity ?? 1;
    if (formData.manual_url) data.source_url = formData.manual_url;
    if (imagePreview.value) data.image_base64 = imagePreview.value;
    // Manual items should not be resolved even if they have a URL
    data.skip_resolution = true;
  }

  emit('submit', data);
}

function closeDialog() {
  emit('update:modelValue', false);
}

function resetForm() {
  formData.title = '';
  formData.description = null;
  formData.price = null;
  formData.currency = 'RUB';
  formData.quantity = 1;
  formData.source_url = null;
  formData.manual_url = null;
  imageFile.value = null;
  imagePreview.value = null;
  tab.value = 'url';
}

// Reset form when dialog closes
watch(() => props.modelValue, (newValue) => {
  if (!newValue) {
    setTimeout(resetForm, 300); // Delay to avoid flicker during close animation
  }
});
</script>

<style scoped>
.image-preview {
  position: relative;
}

.remove-image-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
</style>
