<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ApiTransportError, fetchReleasedDocuments, type ReleasedDocumentItem } from "../../api/client";
import { useBootstrapState } from "../../state/bootstrap";
import { useAppShellState } from "../../state/appShell";

const { t } = useI18n();
const bootstrap = useBootstrapState();
const shell = useAppShellState();
const available = computed(() => shell.auth.status === "authenticated" && bootstrap.modules.some(module => module.id === "documents" && module.licensed && module.authorized));
const session = computed(() => shell.auth.status === "authenticated" ? shell.auth.user.session_id : null);
const items = ref<ReleasedDocumentItem[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
let generation = 0;
async function load(): Promise<void> {
  const token = ++generation;
  items.value = []; error.value = null; loading.value = false;
  if (!available.value) return;
  loading.value = true;
  try {
    const rows = await fetchReleasedDocuments();
    if (token === generation) items.value = rows;
  } catch (cause) {
    if (token === generation) error.value = t(cause instanceof ApiTransportError && cause.status === 403 ? "api.errors.forbidden" : cause instanceof ApiTransportError && cause.status === 401 ? "api.errors.unauthorized" : "api.errors.transport");
  } finally { if (token === generation) loading.value = false; }
}
watch(() => [available.value, session.value], () => { void load(); }, { immediate: true });
onUnmounted(() => { generation += 1; });
function date(value: string | null): string { return value ? new Date(value).toLocaleDateString("de-DE") : t("releasedDocuments.noDate"); }
// Presentation of the supplied date only, not a client authorization/validity policy.
function dateExceeded(value: string | null): boolean { return Boolean(value && Date.parse(value) < Date.now()); }
</script>
<template>
  <section data-testid="released-documents" class="released-documents">
    <header><h2>{{ t("releasedDocuments.title") }}</h2><v-btn size="small" variant="text" :disabled="loading || !available" @click="load">{{ t("dashboard.refresh") }}</v-btn></header>
    <p>{{ t("releasedDocuments.hint") }}</p>
    <p v-if="!available" role="status">{{ t("dashboard.unavailable") }}</p>
    <p v-else-if="loading" role="status">{{ t("dashboard.loading") }}</p>
    <p v-else-if="error" role="alert" data-testid="released-documents-error">{{ error }}</p>
    <p v-else-if="items.length === 0" role="status">{{ t("releasedDocuments.empty") }}</p>
    <v-table v-else density="compact">
      <thead><tr><th>{{ t("releasedDocuments.document") }}</th><th>{{ t("releasedDocuments.version") }}</th><th>{{ t("releasedDocuments.releasedAt") }}</th><th>{{ t("releasedDocuments.validUntil") }}</th><th>{{ t("releasedDocuments.action") }}</th></tr></thead>
      <tbody><tr v-for="item in items" :key="`${item.document_id}:${item.version}`" data-testid="released-document-row">
        <td>{{ item.title }}</td><td>{{ item.version }}</td><td>{{ date(item.released_at) }}</td>
        <td>{{ date(item.valid_until) }} <span v-if="dateExceeded(item.valid_until)" class="text-error" data-testid="released-date-exceeded"> · {{ t("releasedDocuments.dateExceeded") }}</span></td>
        <td><v-btn size="small" variant="text" :to="{ name: 'document-viewer', params: { docId: item.document_id }, query: { version: item.version, returnTo: 'released-documents' } }" data-testid="released-document-read">{{ t("releasedDocuments.read") }}</v-btn></td>
      </tr></tbody>
    </v-table>
  </section>
</template>
<style scoped>
.released-documents header { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.released-documents h2 { margin: 0; }
</style>
