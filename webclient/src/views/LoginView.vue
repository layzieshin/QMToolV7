<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import {
  buildChangePasswordLocation,
  readReturnUrlQuery,
  sanitizeReturnUrl,
} from "../composables/useReturnUrl";
import { login, useAppShellState } from "../state/appShell";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const shell = useAppShellState();

const username = ref("");
const password = ref("");
const loginError = ref<string | null>(null);

const showLoginForm = computed(() => shell.auth.status === "anonymous");

async function onLogin(): Promise<void> {
  loginError.value = null;
  try {
    await login(username.value, password.value);
    password.value = "";
    const returnTarget = sanitizeReturnUrl(readReturnUrlQuery(route.query.returnUrl));
    if (shell.auth.status === "authenticated") {
      await router.replace(returnTarget);
      return;
    }
    if (shell.auth.status === "password_change_required") {
      await router.replace(buildChangePasswordLocation(returnTarget));
    }
  } catch (error) {
    password.value = "";
    loginError.value = error instanceof Error ? error.message : t("login.failed");
  }
}
</script>

<template>
  <section v-if="showLoginForm" data-testid="login-panel">
    <h2>{{ t("login.title") }}</h2>
    <form @submit.prevent="onLogin">
      <v-text-field
        v-model="username"
        :label="t('login.username')"
        autocomplete="username"
        name="username"
      />
      <v-text-field
        v-model="password"
        :label="t('login.password')"
        type="password"
        autocomplete="current-password"
        name="password"
      />
      <v-btn type="submit" color="primary">{{ t("login.submit") }}</v-btn>
    </form>
    <v-alert
      v-if="loginError"
      type="error"
      role="alert"
      data-testid="login-error"
      class="mt-4"
    >
      {{ loginError }}
    </v-alert>
  </section>
</template>

<style scoped>
form {
  display: grid;
  gap: 0.75rem;
  max-width: 24rem;
}
</style>
