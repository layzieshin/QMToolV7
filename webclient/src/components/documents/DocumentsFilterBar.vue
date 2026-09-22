<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  DOCUMENTS_STATUS_VALUES,
  type DocumentsStatusFilter,
} from "../../composables/useDocumentsQuerySync";

const props = defineProps<{
  q?: string;
  status?: DocumentsStatusFilter;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  apply: [payload: { q?: string; status?: DocumentsStatusFilter | "" }];
}>();

const { t } = useI18n();

const searchText = ref(props.q ?? "");
const statusValue = ref<DocumentsStatusFilter | "">(props.status ?? "");

watch(
  () => [props.q, props.status] as const,
  ([nextQ, nextStatus]) => {
    searchText.value = nextQ ?? "";
    statusValue.value = nextStatus ?? "";
  },
);

function onApply(): void {
  emit("apply", {
    q: searchText.value,
    status: statusValue.value,
  });
}
</script>

<template>
  <form
    class="documents-filter-bar"
    data-testid="documents-filter-bar"
    @submit.prevent="onApply"
  >
    <v-text-field
      v-model="searchText"
      :label="t('documents.pool.filterSearch')"
      density="compact"
      hide-details
      :disabled="disabled"
      data-testid="documents-filter-search"
    />
    <v-select
      v-model="statusValue"
      :items="[
        { title: t('documents.pool.filterStatusAll'), value: '' },
        ...DOCUMENTS_STATUS_VALUES.map((value) => ({
          title: t(`documents.status.${value}`),
          value,
        })),
      ]"
      :label="t('documents.pool.filterStatus')"
      density="compact"
      hide-details
      :disabled="disabled"
      data-testid="documents-filter-status"
    />
    <v-btn
      type="submit"
      variant="tonal"
      :disabled="disabled"
      data-testid="documents-filter-apply"
    >
      {{ t("documents.pool.filterApply") }}
    </v-btn>
  </form>
</template>

<style scoped>
.documents-filter-bar {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: 1fr;
  margin-bottom: 1rem;
}

@media (min-width: 960px) {
  .documents-filter-bar {
    grid-template-columns: 2fr 1fr auto;
    align-items: center;
  }
}
</style>
