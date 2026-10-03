<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { logout, refreshAuth, refreshConnection, useAppShellState } from "../state/appShell";

const { t } = useI18n();
const router = useRouter();
const shell = useAppShellState();
defineProps<{ documentWorkspace?: boolean }>();

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

async function onLogout(): Promise<void> {
  await logout();
  await router.replace("/login");
}
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--workspace': documentWorkspace }" data-testid="app-shell">
    <header class="app-shell__header">
      <strong>{{ t("app.title") }}</strong>
      <span data-testid="connection-state">{{ connectionLabel }}</span>
      <p data-testid="auth-state" class="app-shell__auth">{{ authLabel }}</p>
      <div v-if="shell.auth.status === 'authenticated'" data-testid="authenticated-panel">
        <v-btn variant="outlined" data-testid="shell-logout" @click="onLogout">
          {{ t("shell.logout") }}
        </v-btn>
      </div>
    </header>
    <section v-if="shell.lastError || shell.loading" class="app-shell__status" aria-live="polite">
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
  max-width: 1800px;
  width: 100%;
  padding: 1rem;
}
.app-shell__header {
  align-items: center;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}
.app-shell__status {
  margin: 0.5rem 0 1rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
}
.app-shell__status p { margin: 0; }
.app-shell__header { padding-bottom: .5rem; border-bottom: 1px solid rgba(0,0,0,.12); }
.app-shell__auth { margin: 0; font-size: .875rem; }
.app-shell--workspace { height: 100dvh; max-width: none; padding: .25rem .5rem; display: flex; flex-direction: column; gap: .25rem; }
.app-shell--workspace .app-shell__header { flex: 0 0 auto; padding: 0; gap: .5rem; }
.app-shell--workspace .app-shell__main { flex: 1; min-height: 0; display: flex; flex-direction: column; }
@media (max-width: 600px) { .app-shell__header { flex-wrap: wrap; } .app-shell--workspace .app-shell__auth { display: none; } }
</style>
