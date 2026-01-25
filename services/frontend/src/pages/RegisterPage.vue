<template>
  <div>
    <q-form @submit="handleRegister" class="q-gutter-md">
      <q-input
        v-model="name"
        :label="$t('auth.name')"
        outlined
        :rules="[val => !!val || 'Name is required']"
      />

      <q-input
        v-model="email"
        :label="$t('auth.email')"
        type="email"
        outlined
        :rules="[val => !!val || 'Email is required', val => /.+@.+\..+/.test(val) || 'Invalid email']"
      />

      <q-input
        v-model="password"
        :label="$t('auth.password')"
        :type="showPassword ? 'text' : 'password'"
        outlined
        :rules="[val => !!val || 'Password is required', val => val.length >= 8 || $t('auth.passwordTooShort')]"
      >
        <template v-slot:append>
          <q-icon
            :name="showPassword ? 'visibility_off' : 'visibility'"
            class="cursor-pointer"
            @click="showPassword = !showPassword"
          />
        </template>
      </q-input>

      <div v-if="error" class="text-negative text-center">
        {{ error }}
      </div>

      <q-btn
        type="submit"
        color="primary"
        class="full-width"
        size="lg"
        :label="$t('auth.register')"
        :loading="authStore.isLoading"
      />
    </q-form>

    <SocialLoginButtons class="q-mt-lg" />

    <div class="text-center q-mt-lg">
      <router-link :to="{ name: 'login' }" class="text-primary">
        {{ $t('auth.hasAccount') }} {{ $t('auth.login') }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useI18n } from 'vue-i18n';
import { LocalStorage } from 'quasar';
import SocialLoginButtons from '@/components/SocialLoginButtons.vue';

const PENDING_SHARE_TOKEN_KEY = 'pending_share_token';

const authStore = useAuthStore();
const router = useRouter();
const { t, locale } = useI18n();

const name = ref('');
const email = ref('');
const password = ref('');
const showPassword = ref(false);
const error = ref('');

async function handleRegister() {
  error.value = '';
  try {
    await authStore.register({
      name: name.value,
      email: email.value,
      password: password.value,
      locale: locale.value,
    });

    // Check for pending share token and redirect accordingly
    const pendingShareToken = LocalStorage.getItem<string>(PENDING_SHARE_TOKEN_KEY);
    if (pendingShareToken) {
      LocalStorage.remove(PENDING_SHARE_TOKEN_KEY);
      router.push({ name: 'shared-wishlist', params: { token: pendingShareToken } });
    } else {
      router.push({ name: 'wishlists' });
    }
  } catch (err: unknown) {
    const axiosError = err as { response?: { status: number } };
    if (axiosError.response?.status === 409) {
      error.value = t('auth.emailTaken');
    } else {
      error.value = t('errors.generic');
    }
  }
}
</script>
