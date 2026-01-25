<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { useQuasar, copyToClipboard } from 'quasar';
import { useI18n } from 'vue-i18n';
import { api } from '@/boot/axios';
import type { ShareLink, ShareLinkListResponse } from '@/types/share';

interface Props {
  modelValue: boolean;
  wishlistId: string;
  wishlistName: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const $q = useQuasar();
const { t } = useI18n();

const shareLinks = ref<ShareLink[]>([]);
const isLoading = ref(false);
const isCreating = ref(false);
const newLinkExpiry = ref<number | null>(30);
const showQrCode = ref<string | null>(null);

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

async function fetchShareLinks() {
  isLoading.value = true;
  try {
    const response = await api.get<ShareLinkListResponse>(
      `/api/v1/wishlists/${props.wishlistId}/share`
    );
    shareLinks.value = response.data.items;
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
  } finally {
    isLoading.value = false;
  }
}

async function createShareLink() {
  isCreating.value = true;
  try {
    const response = await api.post<ShareLink>(
      `/api/v1/wishlists/${props.wishlistId}/share`,
      {
        link_type: 'mark',
        expires_in_days: newLinkExpiry.value,
      }
    );
    shareLinks.value.unshift(response.data);
    $q.notify({
      type: 'positive',
      message: t('sharing.linkCreated'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
  } finally {
    isCreating.value = false;
  }
}

async function revokeShareLink(link: ShareLink) {
  $q.dialog({
    title: t('sharing.revokeConfirm'),
    message: t('sharing.revokeMessage'),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await api.delete(`/api/v1/wishlists/${props.wishlistId}/share/${link.id}`);
      shareLinks.value = shareLinks.value.filter(l => l.id !== link.id);
      $q.notify({
        type: 'info',
        message: t('sharing.linkRevoked'),
      });
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: t('errors.generic'),
      });
    }
  });
}

async function copyLink(url: string) {
  try {
    await copyToClipboard(url);
    $q.notify({
      type: 'positive',
      message: t('sharing.linkCopied'),
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return t('sharing.neverExpires');
  const date = new Date(dateStr);
  return date.toLocaleDateString();
}

watch(isOpen, (open) => {
  if (open) {
    fetchShareLinks();
  } else {
    showQrCode.value = null;
  }
});
</script>

<template>
  <q-dialog v-model="isOpen" persistent>
    <q-card style="min-width: 400px; max-width: 90vw;">
      <q-card-section class="row items-center">
        <div class="text-h6">{{ $t('sharing.shareWishlist') }}</div>
        <q-space />
        <q-btn flat round dense icon="close" @click="isOpen = false" />
      </q-card-section>

      <q-separator />

      <q-card-section>
        <!-- Create new link -->
        <div class="row items-center q-gutter-sm q-mb-lg">
          <q-select
            v-model="newLinkExpiry"
            :options="[
              { label: $t('sharing.expires7days'), value: 7 },
              { label: $t('sharing.expires30days'), value: 30 },
              { label: $t('sharing.expires90days'), value: 90 },
              { label: $t('sharing.neverExpires'), value: null },
            ]"
            emit-value
            map-options
            dense
            outlined
            style="min-width: 150px;"
          />
          <q-btn
            color="primary"
            :label="$t('sharing.createLink')"
            :loading="isCreating"
            @click="createShareLink"
          />
        </div>

        <!-- Loading state -->
        <div v-if="isLoading" class="flex flex-center q-pa-md">
          <q-spinner color="primary" size="30px" />
        </div>

        <!-- Links list -->
        <div v-else-if="shareLinks.length > 0">
          <q-list separator>
            <q-item v-for="link in shareLinks" :key="link.id">
              <q-item-section>
                <q-item-label class="text-caption text-grey">
                  {{ $t('sharing.createdAt', { date: formatDate(link.created_at) }) }}
                  <span v-if="link.expires_at">
                    &middot; {{ $t('sharing.expiresAt', { date: formatDate(link.expires_at) }) }}
                  </span>
                </q-item-label>
                <q-item-label class="text-body2">
                  <code class="bg-grey-2 q-pa-xs" style="word-break: break-all;">
                    {{ link.share_url }}
                  </code>
                </q-item-label>
                <q-item-label caption class="q-mt-xs">
                  {{ $t('sharing.accessCount', { count: link.access_count }) }}
                </q-item-label>
              </q-item-section>

              <q-item-section side>
                <div class="row q-gutter-xs">
                  <q-btn
                    flat
                    round
                    dense
                    icon="content_copy"
                    @click="copyLink(link.share_url)"
                  >
                    <q-tooltip>{{ $t('sharing.copyLink') }}</q-tooltip>
                  </q-btn>
                  <q-btn
                    v-if="link.qr_code_base64"
                    flat
                    round
                    dense
                    icon="qr_code"
                    @click="showQrCode = link.qr_code_base64"
                  >
                    <q-tooltip>{{ $t('sharing.showQr') }}</q-tooltip>
                  </q-btn>
                  <q-btn
                    flat
                    round
                    dense
                    icon="delete"
                    color="negative"
                    @click="revokeShareLink(link)"
                  >
                    <q-tooltip>{{ $t('sharing.revoke') }}</q-tooltip>
                  </q-btn>
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </div>

        <!-- Empty state -->
        <div v-else class="text-center text-grey-6 q-pa-lg">
          <q-icon name="link_off" size="48px" class="q-mb-md" />
          <p>{{ $t('sharing.noLinks') }}</p>
          <p class="text-caption">{{ $t('sharing.noLinksHint') }}</p>
        </div>
      </q-card-section>

      <!-- QR Code dialog -->
      <q-dialog v-model="showQrCode" v-if="showQrCode">
        <q-card class="q-pa-md text-center">
          <q-img :src="showQrCode" style="width: 250px; height: 250px;" />
          <q-card-actions align="center">
            <q-btn flat :label="$t('common.close')" @click="showQrCode = null" />
          </q-card-actions>
        </q-card>
      </q-dialog>
    </q-card>
  </q-dialog>
</template>
