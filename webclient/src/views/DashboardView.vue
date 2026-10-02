<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ApiTransportError, fetchDocumentHomeTasks, type DocumentTaskItem } from "../api/client";
import { useBootstrapState } from "../state/bootstrap";
import { useAppShellState } from "../state/appShell";

defineOptions({
  name: "ShellHomeView",
});

const { t, te } = useI18n();
const bootstrap = useBootstrapState();
const shell = useAppShellState();
const documentsAvailable = computed(() => bootstrap.modules.some(module => module.id === "documents" && module.licensed && module.authorized));
const actor = computed(() => shell.auth.status === "authenticated" ? shell.auth.user.session_id : null);
const tasks = ref<DocumentTaskItem[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
let generation = 0;

async function loadTasks(): Promise<void> {
  const token = ++generation;
  tasks.value = [];
  error.value = null;
  loading.value = false;
  if (!documentsAvailable.value || !actor.value) return;
  loading.value = true;
  try {
    const rows = await fetchDocumentHomeTasks();
    if (token === generation) tasks.value = rows;
  } catch (cause) {
    if (token !== generation) return;
    const key = cause instanceof ApiTransportError && cause.status === 403 ? "api.errors.forbidden"
      : cause instanceof ApiTransportError && cause.status === 401 ? "api.errors.unauthorized" : "api.errors.transport";
    error.value = t(key);
  } finally {
    if (token === generation) loading.value = false;
  }
}
watch(() => [documentsAvailable.value, actor.value], () => { void loadTasks(); }, { immediate: true });
onUnmounted(() => { generation += 1; });
function statusLabel(status: string): string {
  const key = `documents.status.${status}`;
  return te(key) ? t(key) : t("documents.status.unknown");
}
</script>

<template>
  <section data-testid="dashboard" class="dashboard-view">
    <h2>{{ t("dashboard.title") }}</h2>
    <p>{{ t("dashboard.hint") }}</p>
    <template v-if="documentsAvailable">
      <v-btn color="primary" variant="flat" :to="{ name: 'documents' }" data-testid="dashboard-documents">{{ t("dashboard.openDocuments") }}</v-btn>
      <section class="dashboard-view__tasks" :aria-label="t('dashboard.tasksTitle')">
        <header><h3>{{ t("dashboard.tasksTitle") }}</h3><v-btn size="small" variant="text" :disabled="loading" @click="loadTasks">{{ t("dashboard.refresh") }}</v-btn></header>
        <p v-if="loading" role="status">{{ t("dashboard.loading") }}</p>
        <p v-else-if="error" role="alert" data-testid="dashboard-error">{{ error }}</p>
        <p v-else-if="tasks.length === 0" role="status" data-testid="dashboard-empty">{{ t("dashboard.empty") }}</p>
        <ul v-else class="dashboard-view__list">
          <li v-for="task in tasks" :key="`${task.document_id}:${task.version}`">
            <router-link :to="{ name: 'document-detail', params: { docId: task.document_id }, query: { version: task.version } }" data-testid="dashboard-task">{{ task.title }}</router-link>
            <span>{{ statusLabel(task.status) }} · {{ t("dashboard.version", { version: task.version }) }}</span>
          </li>
        </ul>
      </section>
    </template>
    <p v-else role="status">{{ t("dashboard.unavailable") }}</p>
  </section>
</template>

<style scoped>
.dashboard-view h2 {
  margin-top: 0;
}
.dashboard-view__tasks { margin-top: 1.5rem; padding: 1rem; background: white; border: 1px solid rgba(0,0,0,.12); border-radius: 6px; }
.dashboard-view__tasks header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.dashboard-view__tasks h3 { margin: 0; }
.dashboard-view__list { list-style: none; padding: 0; margin-bottom: 0; }
.dashboard-view__list li { display: flex; justify-content: space-between; flex-wrap: wrap; gap: .5rem; padding: .85rem 0; border-top: 1px solid rgba(0,0,0,.08); }
.dashboard-view__list span { color: #555; font-size: .875rem; }
.dashboard-view__list a { color: rgb(var(--v-theme-primary)); text-decoration: none; font-weight: 500; }
.dashboard-view__list a:hover { text-decoration: underline; }
</style>
