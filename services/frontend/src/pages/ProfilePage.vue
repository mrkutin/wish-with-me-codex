<template>
  <q-page padding>
    <h1 class="text-h5 q-mb-md">{{ $t('profile.title') }}</h1>

    <q-card v-if="authStore.user">
      <q-card-section class="row items-center q-gutter-md">
        <q-avatar size="80px">
          <img v-if="!isPlaceholderAvatar(authStore.user.avatar_base64)" :src="authStore.user.avatar_base64" alt="Avatar" />
          <q-icon v-else name="person" size="48px" />
        </q-avatar>
        <div>
          <div class="text-h6">{{ authStore.user.name }}</div>
          <div class="text-body2 text-grey">{{ authStore.user.email }}</div>
        </div>
      </q-card-section>

      <q-separator />

      <q-card-section>
        <q-form @submit="updateProfile" class="q-gutter-md">
          <q-input
            v-model="profileForm.name"
            :label="$t('auth.name')"
            outlined
            :rules="[val => !!val || 'Name is required']"
          />

          <q-input
            v-model="profileForm.bio"
            :label="$t('profile.bio')"
            outlined
            type="textarea"
          />

          <q-input
            v-model="profileForm.public_url_slug"
            :label="$t('profile.publicUrl')"
            outlined
            prefix="wishwith.me/u/"
            :rules="[val => !val || /^[a-z0-9-]+$/.test(val) || 'Only lowercase letters, numbers, and hyphens']"
          />

          <q-btn
            type="submit"
            color="primary"
            :label="$t('common.save')"
            :loading="saving"
          />
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, watchEffect } from 'vue';
import { useQuasar } from 'quasar';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/boot/axios';
import { useI18n } from 'vue-i18n';

const $q = useQuasar();
const authStore = useAuthStore();
const { t } = useI18n();
const saving = ref(false);

const profileForm = reactive({
  name: '',
  bio: '',
  public_url_slug: '',
});

watchEffect(() => {
  if (authStore.user) {
    profileForm.name = authStore.user.name;
    profileForm.bio = authStore.user.bio || '';
    profileForm.public_url_slug = authStore.user.public_url_slug || '';
  }
});

async function updateProfile() {
  saving.value = true;
  try {
    await api.patch('/api/v1/users/me', {
      name: profileForm.name,
      bio: profileForm.bio || null,
      public_url_slug: profileForm.public_url_slug || null,
    });
    await authStore.fetchCurrentUser();
    $q.notify({
      type: 'positive',
      message: t('common.success'),
    });
  } catch {
    $q.notify({
      type: 'negative',
      message: t('errors.generic'),
    });
  } finally {
    saving.value = false;
  }
}

function isPlaceholderAvatar(avatar: string): boolean {
  // Check if avatar is the default placeholder SVG (contains "?" text element)
  return avatar.includes('PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiM2MzY2ZjEiLz48dGV4dCB4PSI1MCIgeT0iNTUiIGZvbnQtc2l6ZT0iNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+PzwvdGV4dD48L3N2Zz4=');
}
</script>
