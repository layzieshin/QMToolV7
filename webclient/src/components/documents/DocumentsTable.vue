<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { DocumentQueryItem } from "../../api/client";
import type { DocumentsOrder, DocumentsSortField } from "../../composables/useDocumentsQuerySync";

export type DocumentRowIdentity = {
  documentId: string;
  version: number;
};

const props = defineProps<{
  items: DocumentQueryItem[];
  sort: DocumentsSortField;
  order: DocumentsOrder;
  selectedRow?: DocumentRowIdentity | null;
  loading?: boolean;
}>();

const emit = defineEmits<{
  sort: [payload: { sort: DocumentsSortField; order: DocumentsOrder }];
  select: [row: DocumentRowIdentity];
}>();

const { t, te, locale } = useI18n();

const headers = computed(() => [
  { title: t("documents.pool.columnTitle"), key: "title", sortable: true, sortKey: "title" as const },
  { title: t("documents.pool.columnStatus"), key: "status", sortable: true, sortKey: "status" as const },
  { title: t("documents.pool.columnVersion"), key: "version", sortable: false },
  { title: t("documents.pool.columnUpdated"), key: "updated_at", sortable: true, sortKey: "updated_at" as const },
]);

function statusLabel(status: string): string {
  const key = `documents.status.${status}`;
  return te(key) ? t(key) : t("documents.status.unknown");
}

function formatUpdated(value: string | null | undefined): string {
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

function rowIdentity(item: DocumentQueryItem): DocumentRowIdentity {
  return { documentId: item.document_id, version: item.version };
}

function isSelected(item: DocumentQueryItem): boolean {
  return (
    props.selectedRow?.documentId === item.document_id &&
    props.selectedRow?.version === item.version
  );
}

function toggleSort(sortKey: DocumentsSortField): void {
  if (props.sort === sortKey) {
    emit("sort", { sort: sortKey, order: props.order === "asc" ? "desc" : "asc" });
    return;
  }
  emit("sort", { sort: sortKey, order: "desc" });
}

function ariaSort(sortKey: DocumentsSortField): "ascending" | "descending" | "none" {
  if (props.sort !== sortKey) {
    return "none";
  }
  return props.order === "asc" ? "ascending" : "descending";
}
</script>

<template>
  <div class="documents-table" data-testid="documents-table">
    <v-table density="comfortable" :aria-busy="loading ? 'true' : 'false'">
      <thead>
        <tr>
          <th
            v-for="header in headers"
            :key="header.key"
            scope="col"
            :aria-sort="header.sortable ? ariaSort(header.sortKey!) : undefined"
          >
            <button
              v-if="header.sortable"
              type="button"
              class="sort-button"
              :data-testid="`documents-sort-${header.sortKey}`"
              @click="toggleSort(header.sortKey!)"
            >
              {{ header.title }}
            </button>
            <span v-else>{{ header.title }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in items"
          :key="`${item.document_id}-${item.version}`"
          tabindex="0"
          role="row"
          :class="{ selected: isSelected(item) }"
          :aria-selected="isSelected(item) ? 'true' : 'false'"
          data-testid="documents-table-row"
          @click="emit('select', rowIdentity(item))"
          @keydown.enter.prevent="emit('select', rowIdentity(item))"
          @keydown.space.prevent="emit('select', rowIdentity(item))"
        >
          <td>{{ item.title }}</td>
          <td data-testid="documents-table-status">{{ statusLabel(item.status) }}</td>
          <td data-testid="documents-table-version">{{ item.version }}</td>
          <td>{{ formatUpdated(item.updated_at) }}</td>
        </tr>
      </tbody>
    </v-table>
  </div>
</template>

<style scoped>
.sort-button {
  background: none;
  border: none;
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-align: left;
}

tr.selected {
  background: rgba(25, 118, 210, 0.08);
}

tr {
  cursor: pointer;
}
</style>
