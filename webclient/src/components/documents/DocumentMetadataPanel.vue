<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { DocumentVersionStateModel, UserDirectoryItem } from "../../api/client";

const props = defineProps<{
  state: DocumentVersionStateModel | null;
  directory: UserDirectoryItem[];
}>();

const { t, locale } = useI18n();

const directoryById = computed(() => {
  const map = new Map<string, UserDirectoryItem>();
  for (const entry of props.directory) {
    map.set(entry.user_id, entry);
  }
  return map;
});

function ownerLabel(userId: string | null | undefined): string {
  if (!userId) {
    return "—";
  }
  const entry = directoryById.value.get(userId);
  if (entry?.is_active) {
    return entry.username;
  }
  return t("documents.detail.assignments.unavailableUser");
}

function localizeDocType(docType: string | null | undefined): string {
  const trimmed = docType?.trim();
  if (!trimmed) {
    return t("documents.detail.docType.unknown");
  }
  const key = `documents.detail.docType.${trimmed}`;
  const translated = t(key);
  return translated === key ? t("documents.detail.docType.unknown") : translated;
}

function localizeControlClass(controlClass: string | null | undefined): string {
  const trimmed = controlClass?.trim();
  if (!trimmed) {
    return t("documents.detail.controlClass.unknown");
  }
  const key = `documents.detail.controlClass.${trimmed}`;
  const translated = t(key);
  return translated === key ? t("documents.detail.controlClass.unknown") : translated;
}

function workflowProfileLabel(): string {
  const label = props.state?.workflow_profile?.label?.trim();
  if (!label) {
    return t("documents.detail.workflowProfile.unavailable");
  }
  return label;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
</script>

<template>
  <section class="document-metadata-panel" data-testid="document-metadata-panel">
    <h3>{{ t("documents.detail.metadataTitle") }}</h3>
    <p v-if="!state" data-testid="document-metadata-empty">
      {{ t("documents.detail.metadataEmpty") }}
    </p>
    <dl v-else data-testid="document-metadata-summary">
      <dt>{{ t("documents.detail.metadataDocType") }}</dt>
      <dd data-testid="document-metadata-doc-type">{{ localizeDocType(state.doc_type) }}</dd>
      <dt>{{ t("documents.detail.metadataControlClass") }}</dt>
      <dd data-testid="document-metadata-control-class">{{ localizeControlClass(state.control_class) }}</dd>
      <dt>{{ t("documents.detail.metadataWorkflowProfile") }}</dt>
      <dd data-testid="document-metadata-workflow-profile">{{ workflowProfileLabel() }}</dd>
      <dt>{{ t("documents.detail.metadataOwner") }}</dt>
      <dd data-testid="document-metadata-owner">{{ ownerLabel(state.owner_user_id) }}</dd>
      <dt>{{ t("documents.detail.metadataUpdated") }}</dt>
      <dd>{{ formatDate(state.updated_at) }}</dd>
      <template v-if="state.description">
        <dt>{{ t("documents.pool.detailDescription") }}</dt>
        <dd data-testid="document-metadata-description">{{ state.description }}</dd>
      </template>
    </dl>
  </section>
</template>

<style scoped>
.document-metadata-panel {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  padding: 1rem;
}

.document-metadata-panel h3 {
  margin-top: 0;
}

dl {
  margin: 0;
}

dt {
  font-weight: 600;
  margin-top: 0.75rem;
}

dd {
  margin: 0.25rem 0 0;
}
</style>
