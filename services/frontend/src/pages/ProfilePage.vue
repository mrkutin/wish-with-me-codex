<template>
  <q-page class="profile-page">
    <div class="page-container">
      <h1 class="page-title">{{ $t('profile.title') }}</h1>

      <div v-if="authStore.user" class="profile-card">
        <!-- Profile Header -->
        <div class="profile-header">
          <q-avatar size="80px" class="profile-avatar">
            <img v-if="!isPlaceholderAvatar(authStore.user.avatar_base64)" :src="authStore.user.avatar_base64" alt="Avatar" />
            <q-icon v-else name="person" size="48px" />
          </q-avatar>
          <div class="profile-info">
            <div class="profile-name">{{ authStore.user.name }}</div>
            <div class="profile-email">{{ authStore.user.email }}</div>
          </div>
        </div>

        <div class="divider"></div>

        <!-- Profile Form -->
        <q-form @submit="updateProfile" class="profile-form">
          <div class="form-fields">
            <q-input
              v-model="profileForm.name"
              :label="$t('auth.name')"
              outlined
              :rules="[val => !!val || $t('validation.required')]"
              class="form-field"
            />

            <q-input
              v-model="profileForm.bio"
              :label="$t('profile.bio')"
              outlined
              type="textarea"
              autogrow
              class="form-field"
            />

            <q-input
              v-model="profileForm.public_url_slug"
              :label="$t('profile.publicUrl')"
              outlined
              prefix="wishwith.me/u/"
              :rules="[val => !val || /^[a-z0-9-]+$/.test(val) || $t('validation.invalidHandle')]"
              class="form-field"
            />

            <q-input
              v-model="profileForm.birthday"
              :label="$t('profile.birthday')"
              outlined
              type="date"
              class="form-field"
            />
          </div>

          <q-btn
            type="submit"
            color="primary"
            class="submit-btn"
            size="lg"
            :label="$t('common.save')"
            :loading="saving"
            unelevated
            no-caps
          />
        </q-form>
      </div>
    </div>
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
  birthday: '',
});

watchEffect(() => {
  if (authStore.user) {
    profileForm.name = authStore.user.name;
    profileForm.bio = authStore.user.bio || '';
    profileForm.public_url_slug = authStore.user.public_url_slug || '';
    profileForm.birthday = authStore.user.birthday || '';
  }
});

async function updateProfile() {
  saving.value = true;
  try {
    await api.patch('/api/v1/users/me', {
      name: profileForm.name,
      bio: profileForm.bio || null,
      public_url_slug: profileForm.public_url_slug || null,
      birthday: profileForm.birthday || null,
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
  return avatar.includes('PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiM2MzY2ZjEiLz48dGV4dCB4PSI1MCIgeT0iNTUiIGZvbnQtc2l6ZT0iNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+PzwvdGV4dD48L3N2Zz4=');
}
</script>

<style scoped lang="sass">
.profile-page
  min-height: 100%
  padding: var(--space-4)
  background: var(--bg-primary)

  @media (min-width: 600px)
    padding: var(--space-6)

.page-container
  max-width: 600px
  margin: 0 auto

  @media (min-width: 1024px)
    max-width: 680px

  @media (min-width: 1440px)
    max-width: 720px

.page-title
  font-size: var(--text-h3)
  font-weight: 700
  color: var(--text-primary)
  margin: 0 0 var(--space-6) 0
  letter-spacing: -0.02em

  @media (min-width: 600px)
    font-size: var(--text-h2)

.profile-card
  background: var(--bg-primary)
  border-radius: var(--radius-xl)
  box-shadow: var(--shadow-lg)
  border: 1px solid var(--border-subtle)
  overflow: hidden

.profile-header
  display: flex
  align-items: center
  gap: var(--space-4)
  padding: var(--space-6)

  @media (min-width: 600px)
    padding: var(--space-8)

.profile-avatar
  background: var(--primary-light)
  color: var(--primary)
  flex-shrink: 0

.profile-info
  min-width: 0

.profile-name
  font-size: var(--text-h4)
  font-weight: 600
  color: var(--text-primary)
  margin-bottom: var(--space-1)

.profile-email
  font-size: var(--text-body)
  color: var(--text-secondary)

.divider
  height: 1px
  background: var(--border-default)

.profile-form
  padding: var(--space-6)
  display: flex
  flex-direction: column
  gap: var(--space-4)

  @media (min-width: 600px)
    padding: var(--space-8)

.form-fields
  display: flex
  flex-direction: column
  gap: var(--space-4)

.form-field
  margin-bottom: 0

.submit-btn
  width: 100%
  margin-top: var(--space-2)
  font-size: 16px

  @media (min-width: 600px)
    width: auto
    align-self: flex-start

// Dark mode
.body--dark .profile-card
  background: var(--bg-secondary)
  border-color: var(--border-default)
</style>
