<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { DocumentVersionStateModel } from "../../api/client";

const props = defineProps<{
  state: DocumentVersionStateModel | null;
}>();

const { t, te } = useI18n();

const statusLabel = computed(() => {
  if (!props.state) {
    return "";
  }
  const key = `documents.status.${props.state.status}`;
  return te(key) ? t(key) : t("documents.status.unknown");
});
</script>

<template>
  <header class="document-header" data-testid="document-header">
    <h2 v-if="state" data-testid="document-header-title">{{ state.title }}</h2>
    <dl v-if="state" class="document-header-meta">
      <dt>{{ t("documents.detail.headerStatus") }}</dt>
      <dd data-testid="document-header-status">{{ statusLabel }}</dd>
      <dt>{{ t("documents.detail.headerVersion") }}</dt>
      <dd data-testid="document-header-version">{{ state.version }}</dd>
      <dt>{{ t("documents.detail.headerDocumentId") }}</dt>
      <dd data-testid="document-header-document-id">{{ state.document_id }}</dd>
    </dl>
  </header>
</template>

<style scoped>
.document-header h2 {
  margin-top: 0;
}

dl {
  margin: 0;
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.25rem 1rem;
}

dt {
  font-weight: 600;
}
</style>
