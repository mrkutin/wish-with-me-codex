<template>
  <div>
    <q-form @submit="handleLogin" class="q-gutter-md">
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
        :rules="[val => !!val || 'Password is required']"
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
        :label="$t('auth.login')"
        :loading="authStore.isLoading"
      />
    </q-form>

    <SocialLoginButtons class="q-mt-lg" />

    <div class="text-center q-mt-lg">
      <router-link :to="{ name: 'register' }" class="text-primary">
        {{ $t('auth.noAccount') }} {{ $t('auth.register') }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useI18n } from 'vue-i18n';
import SocialLoginButtons from '@/components/SocialLoginButtons.vue';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const { t } = useI18n();

const email = ref('');
const password = ref('');
const showPassword = ref(false);
const error = ref('');

function isValidRedirect(url: string): boolean {
  // Only allow relative paths starting with /
  if (!url || !url.startsWith('/')) {
    return false;
  }
  // Prevent protocol-relative URLs like //evil.com
  if (url.startsWith('//')) {
    return false;
  }
  return true;
}

async function handleLogin() {
  error.value = '';
  try {
    await authStore.login(email.value, password.value);
    const redirect = route.query.redirect as string;
    // Validate redirect to prevent open redirect vulnerability
    router.push(isValidRedirect(redirect) ? redirect : { name: 'wishlists' });
  } catch (err: unknown) {
    error.value = t('auth.invalidCredentials');
  }
}
</script>
