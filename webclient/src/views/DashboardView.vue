<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { logout, useAppShellState } from "../state/appShell";

defineOptions({
  name: "ShellHomeView",
});

const { t } = useI18n();
const router = useRouter();
const shell = useAppShellState();

async function onLogout(): Promise<void> {
  await logout();
  await router.replace("/login");
}
</script>

<template>
  <section data-testid="shell-placeholder" class="dashboard-view">
    <h2>{{ t("dashboard.title") }}</h2>
    <p>{{ t("dashboard.hint") }}</p>
    <section v-if="shell.auth.status === 'authenticated'" data-testid="authenticated-panel">
      <v-btn variant="outlined" data-testid="dashboard-logout" @click="onLogout">
        {{ t("shell.logout") }}
      </v-btn>
    </section>
  </section>
</template>

<style scoped>
.dashboard-view h2 {
  margin-top: 0;
}
</style>
