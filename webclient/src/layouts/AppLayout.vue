<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiTransportError } from "../api/client";
import AppShell from "../components/AppShell.vue";
import ConnectionBanner from "../components/ConnectionBanner.vue";
import ModuleNavigation from "../components/ModuleNavigation.vue";
import {
  buildChangePasswordLocation,
  buildLoginLocation,
} from "../composables/useReturnUrl";
import {
  clearBootstrapModules,
  loadBootstrap,
  startBootstrapLifecycle,
  stopBootstrapLifecycle,
} from "../state/bootstrap";
import { refreshAuth, useAppShellState } from "../state/appShell";

const router = useRouter();
const route = useRoute();
const documentWorkspace = computed(() => route.name === "document-viewer" || route.name === "document-signature");
const shell = useAppShellState();

const showModuleNavigation = computed(() => shell.auth.status === "authenticated");

onMounted(() => {
  startBootstrapLifecycle();
});

onUnmounted(() => {
  stopBootstrapLifecycle();
});

async function handleAuthenticatedBootstrap(): Promise<void> {
  try {
    await loadBootstrap();
  } catch (error) {
    if (!(error instanceof ApiTransportError && error.status === 401)) {
      return;
    }
    await refreshAuth();
    const auth = useAppShellState().auth;
    if (auth.status === "password_change_required") {
      await router.replace(buildChangePasswordLocation(router.currentRoute.value.fullPath));
      return;
    }
    if (auth.status === "anonymous") {
      await router.replace(buildLoginLocation(router.currentRoute.value.fullPath));
    }
  }
}

watch(
  () => shell.auth.status,
  async (status) => {
    if (status === "authenticated") {
      await handleAuthenticatedBootstrap();
      return;
    }
    clearBootstrapModules();
  },
  { immediate: true },
);
</script>

<template>
  <v-app>
    <AppShell :document-workspace="documentWorkspace">
      <ConnectionBanner />
      <div class="app-layout__body" :class="{ 'app-layout__body--workspace': documentWorkspace }">
        <aside v-if="showModuleNavigation && !documentWorkspace" class="app-layout__sidebar" aria-label="Navigation">
          <ModuleNavigation />
        </aside>
        <div class="app-layout__content">
          <router-view />
        </div>
      </div>
    </AppShell>
  </v-app>
</template>

<style scoped>
.app-layout__body {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}
.app-layout__sidebar {
  flex: 0 0 auto;
}
.app-layout__content {
  flex: 1;
  min-width: 0;
}
.app-layout__body--workspace { flex: 1; min-height: 0; }
.app-layout__body--workspace .app-layout__content { height: 100%; }

@media (max-width: 960px) {
  .app-layout__body {
    flex-direction: column;
    align-items: stretch;
  }

  .app-layout__content {
    width: 100%;
  }
}
</style>
