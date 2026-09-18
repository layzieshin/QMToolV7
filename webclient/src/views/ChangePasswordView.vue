<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { readReturnUrlQuery, sanitizeReturnUrl } from "../composables/useReturnUrl";
import { ApiTransportError } from "../api/client";
import { changePassword, useAppShellState } from "../state/appShell";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const shell = useAppShellState();

const newPassword = ref("");
const formError = ref<string | null>(null);
const fieldError = ref<string | null>(null);

const showForm = computed(() => shell.auth.status === "password_change_required");

defineExpose({ newPassword });

function clearPasswordField(): void {
  newPassword.value = "";
}

async function onSubmit(): Promise<void> {
  formError.value = null;
  fieldError.value = null;
  try {
    await changePassword(newPassword.value);
    clearPasswordField();
    const target = sanitizeReturnUrl(readReturnUrlQuery(route.query.returnUrl));
    await router.replace(target);
  } catch (error) {
    clearPasswordField();
    if (error instanceof ApiTransportError) {
      const detail = error.body?.detail;
      const code = !Array.isArray(detail) ? detail?.error : undefined;
      if (code === "weak_password") {
        fieldError.value = t("changePassword.weakPassword");
        return;
      }
    }
    formError.value = error instanceof Error ? error.message : t("changePassword.failed");
  }
}
</script>

<template>
  <section v-if="showForm" data-testid="change-password-panel">
    <h2>{{ t("changePassword.title") }}</h2>
    <p>{{ t("changePassword.hint") }}</p>
    <form @submit.prevent="onSubmit">
      <v-text-field
        v-model="newPassword"
        :label="t('changePassword.newPassword')"
        type="password"
        autocomplete="new-password"
        name="new-password"
        :error-messages="fieldError ? [fieldError] : undefined"
      />
      <v-btn type="submit" color="primary">{{ t("changePassword.submit") }}</v-btn>
    </form>
    <v-alert
      v-if="formError"
      type="error"
      role="alert"
      data-testid="change-password-error"
      class="mt-4"
    >
      {{ formError }}
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
