<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";

import { refreshAuth, refreshConnection, useAppShellState } from "../state/appShell";

const { t } = useI18n();
const shell = useAppShellState();

const connectionLabel = computed(() => {
  switch (shell.connection) {
    case "online":
      return t("shell.connection.online");
    case "offline":
      return t("shell.connection.offline");
    default:
      return t("shell.connection.unknown");
  }
});

const authLabel = computed(() => {
  switch (shell.auth.status) {
    case "authenticated":
      return t("shell.auth.authenticated", { username: shell.auth.user.username });
    case "password_change_required":
      return t("shell.auth.passwordChangeRequired");
    default:
      return t("shell.auth.anonymous");
  }
});

onMounted(async () => {
  await refreshConnection();
  await refreshAuth();
});
</script>

<template>
  <div class="app-shell" data-testid="app-shell">
    <header class="app-shell__header">
      <strong>{{ t("app.title") }}</strong>
      <span data-testid="connection-state">{{ connectionLabel }}</span>
    </header>
    <section class="app-shell__status" aria-live="polite">
      <p data-testid="auth-state">{{ authLabel }}</p>
      <p v-if="shell.lastError" data-testid="transport-error" role="alert">{{ shell.lastError }}</p>
      <p v-if="shell.loading" data-testid="loading-indicator">{{ t("shell.loading") }}</p>
    </section>
    <main class="app-shell__main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  font-family: system-ui, sans-serif;
  margin: 0 auto;
  max-width: 960px;
  padding: 1rem;
}
.app-shell__header {
  align-items: center;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}
.app-shell__status {
  margin: 1rem 0;
}
</style>
