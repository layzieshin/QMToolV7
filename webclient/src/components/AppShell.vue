<script setup lang="ts">
import { computed, onMounted } from "vue";

import { refreshAuth, refreshConnection, useAppShellState } from "../state/appShell";

const shell = useAppShellState();

const authLabel = computed(() => {
  switch (shell.auth.status) {
    case "authenticated":
      return `Angemeldet als ${shell.auth.user.username}`;
    case "password_change_required":
      return "Passwortänderung erforderlich";
    default:
      return "Nicht angemeldet";
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
      <strong>QMTool</strong>
      <span data-testid="connection-state">{{ shell.connection }}</span>
    </header>
    <section class="app-shell__status">
      <p data-testid="auth-state">{{ authLabel }}</p>
      <p v-if="shell.lastError" data-testid="transport-error">{{ shell.lastError }}</p>
      <p v-if="shell.loading" data-testid="loading-indicator">Laden…</p>
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
