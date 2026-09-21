<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { fetchDocumentsCapabilities } from "../../api/client";

import DocumentsDetailPanel from "../../components/documents/DocumentsDetailPanel.vue";
import DocumentsFilterBar from "../../components/documents/DocumentsFilterBar.vue";
import DocumentsTable, {
  type DocumentRowIdentity,
} from "../../components/documents/DocumentsTable.vue";
import { useProductWriteAvailability } from "../../composables/useProductWriteAvailability";
import { useDocumentsList } from "../../composables/useDocumentsList";
import {
  type DocumentsOrder,
  type DocumentsSortField,
  type DocumentsStatusFilter,
  useDocumentsQuerySync,
} from "../../composables/useDocumentsQuerySync";

defineOptions({
  name: "DocumentsPoolView",
});

const { t } = useI18n();
const router = useRouter();
const { writesAllowed, blockedMessage } = useProductWriteAvailability();
const { query, applyFilters, applySort, goNextPage } = useDocumentsQuerySync();
const { items, nextCursor, loading, error, reload } = useDocumentsList(query);

const selectedRow = ref<DocumentRowIdentity | null>(null);
const canCreate = ref(false);
const capabilitiesGeneration = { current: 0 };
let capabilitiesMounted = false;

onMounted(() => {
  capabilitiesMounted = true;
  const generation = ++capabilitiesGeneration.current;
  void fetchDocumentsCapabilities()
    .then((caps) => {
      if (!capabilitiesMounted || generation !== capabilitiesGeneration.current) {
        return;
      }
      canCreate.value = Boolean(caps.can_create_new_documents);
    })
    .catch(() => {
      if (!capabilitiesMounted || generation !== capabilitiesGeneration.current) {
        return;
      }
      canCreate.value = false;
    });
});

onUnmounted(() => {
  capabilitiesMounted = false;
  capabilitiesGeneration.current += 1;
});

const selectedItem = computed(() =>
  items.value.find(
    (entry) =>
      entry.document_id === selectedRow.value?.documentId &&
      entry.version === selectedRow.value?.version,
  ) ?? null,
);

const isFiltered = computed(() => Boolean(query.value.q || query.value.status));

const showUnfilteredEmpty = computed(
  () => !loading.value && !error.value && items.value.length === 0 && !isFiltered.value,
);

const showFilteredEmpty = computed(
  () => !loading.value && !error.value && items.value.length === 0 && isFiltered.value,
);

const importAllowed = computed(() => canCreate.value && writesAllowed.value);

watch(
  () => ({
    items: items.value,
    loading: loading.value,
    error: error.value,
  }),
  ({ items: currentItems, loading: isLoading, error: currentError }) => {
    if (isLoading || !selectedRow.value) {
      return;
    }
    if (currentError) {
      selectedRow.value = null;
      return;
    }
    const stillPresent = currentItems.some(
      (entry) =>
        entry.document_id === selectedRow.value?.documentId &&
        entry.version === selectedRow.value?.version,
    );
    if (!stillPresent) {
      selectedRow.value = null;
    }
  },
  { deep: true },
);

function onSelect(row: DocumentRowIdentity): void {
  selectedRow.value = row;
}

function openImport(): void {
  if (!importAllowed.value) {
    return;
  }
  void router.push({ name: "document-import" });
}

function openSelectedDetail(): void {
  if (!selectedRow.value) {
    return;
  }
  void router.push({
    name: "document-detail",
    params: { docId: selectedRow.value.documentId },
    query: { version: String(selectedRow.value.version) },
  });
}

async function onApplyFilters(payload: {
  q?: string;
  status?: DocumentsStatusFilter | "";
}): Promise<void> {
  await applyFilters(payload);
}

async function onSort(payload: {
  sort: DocumentsSortField;
  order: DocumentsOrder;
}): Promise<void> {
  await applySort(payload);
}

async function onNextPage(): Promise<void> {
  if (!nextCursor.value) {
    return;
  }
  await goNextPage(nextCursor.value);
}
</script>

<template>
  <section class="documents-pool-view" data-testid="documents-pool-view">
    <div class="documents-pool-header">
      <h2>{{ t("documents.pool.title") }}</h2>
      <div class="documents-pool-actions">
        <v-btn
          v-if="canCreate"
          color="primary"
          data-testid="documents-pool-import"
          :disabled="!writesAllowed"
          :title="writesAllowed ? undefined : blockedMessage"
          @click="openImport"
        >
          {{ t("documents.pool.importAction") }}
        </v-btn>
        <v-btn
          v-if="selectedRow"
          variant="tonal"
          data-testid="documents-pool-open-detail"
          @click="openSelectedDetail"
        >
          {{ t("documents.pool.openDetail") }}
        </v-btn>
      </div>
    </div>

    <DocumentsFilterBar
      :q="query.q"
      :status="query.status"
      :disabled="loading"
      @apply="onApplyFilters"
    />

    <p v-if="loading" data-testid="documents-pool-loading">
      {{ t("documents.pool.loading") }}
    </p>

    <div v-else-if="error" data-testid="documents-pool-error">
      <p>{{ t("documents.pool.error") }}</p>
      <v-btn variant="outlined" data-testid="documents-pool-retry" @click="reload">
        {{ t("documents.pool.retry") }}
      </v-btn>
    </div>

    <template v-else>
      <p v-if="items.length === 0 && showUnfilteredEmpty" data-testid="documents-pool-empty">
        {{ t("documents.pool.empty") }}
      </p>

      <p
        v-else-if="items.length === 0 && showFilteredEmpty"
        data-testid="documents-pool-empty-filtered"
      >
        {{ t("documents.pool.emptyFiltered") }}
      </p>

      <div v-if="items.length > 0 || nextCursor" class="documents-pool-layout">
        <div class="documents-pool-table">
          <DocumentsTable
            v-if="items.length > 0"
            :items="items"
            :sort="query.sort"
            :order="query.order"
            :selected-row="selectedRow"
            :loading="loading"
            @sort="onSort"
            @select="onSelect"
          />
          <v-btn
            v-if="nextCursor"
            class="documents-pool-next"
            variant="tonal"
            data-testid="documents-pool-next"
            @click="onNextPage"
          >
            {{ t("documents.pool.nextPage") }}
          </v-btn>
        </div>
        <DocumentsDetailPanel :item="selectedItem" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.documents-pool-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.documents-pool-header h2 {
  margin: 0;
}

.documents-pool-actions {
  display: flex;
  gap: 0.5rem;
}

.documents-pool-layout {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.documents-pool-table {
  flex: 2;
  min-width: 0;
}

.documents-pool-next {
  margin-top: 0.75rem;
}

@media (min-width: 960px) {
  .documents-pool-layout {
    flex-direction: row;
    align-items: flex-start;
  }

  .documents-pool-layout > :last-child {
    flex: 1;
    min-width: 16rem;
  }
}
</style>
