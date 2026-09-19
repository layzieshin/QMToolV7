<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { DocumentQueryItem } from "../../api/client";

const props = defineProps<{
  item: DocumentQueryItem | null;
}>();

const { t, te, locale } = useI18n();

const statusLabel = computed(() => {
  if (!props.item) {
    return "";
  }
  const key = `documents.status.${props.item.status}`;
  return te(key) ? t(key) : t("documents.status.unknown");
});

const updatedLabel = computed(() => {
  if (!props.item?.updated_at) {
    return "—";
  }
  const date = new Date(props.item.updated_at);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
});
</script>

<template>
  <aside class="documents-detail-panel" data-testid="documents-detail-panel">
    <h3>{{ t("documents.pool.detailTitle") }}</h3>
    <p v-if="!item" data-testid="documents-detail-empty">
      {{ t("documents.pool.detailEmpty") }}
    </p>
    <dl v-else data-testid="documents-detail-summary">
      <dt>{{ t("documents.pool.columnTitle") }}</dt>
      <dd>{{ item.title }}</dd>
      <dt>{{ t("documents.pool.columnStatus") }}</dt>
      <dd data-testid="documents-detail-status">{{ statusLabel }}</dd>
      <dt>{{ t("documents.pool.columnVersion") }}</dt>
      <dd data-testid="documents-detail-version">{{ item.version }}</dd>
      <dt>{{ t("documents.pool.columnUpdated") }}</dt>
      <dd>{{ updatedLabel }}</dd>
      <template v-if="item.description">
        <dt>{{ t("documents.pool.detailDescription") }}</dt>
        <dd>{{ item.description }}</dd>
      </template>
    </dl>
  </aside>
</template>

<style scoped>
.documents-detail-panel {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  padding: 1rem;
}

.documents-detail-panel h3 {
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
