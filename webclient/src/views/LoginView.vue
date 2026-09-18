<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import { login, useAppShellState } from "../state/appShell";

const { t } = useI18n();
const shell = useAppShellState();

const username = ref("");
const password = ref("");
const loginError = ref<string | null>(null);

const showLoginForm = computed(() => shell.auth.status === "anonymous");

async function onLogin(): Promise<void> {
  loginError.value = null;
  try {
    await login(username.value, password.value);
  } catch (error) {
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
