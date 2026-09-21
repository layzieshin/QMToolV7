<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  ApiTransportError,
  fetchWorkflowCommentDetail,
  type WorkflowCommentDetailModel,
  type WorkflowCommentListItemModel,
} from "../../api/client";

const props = defineProps<{
  items: WorkflowCommentListItemModel[];
}>();

const { t, locale } = useI18n();

const expandedId = ref<string | null>(null);
const detailLoading = ref(false);
const detailError = ref(false);
const detailById = ref<Record<string, WorkflowCommentDetailModel>>({});
const detailGeneration = { current: 0 };

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return t("documents.viewer.comments.unknownTime");
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return t("documents.viewer.comments.unknownTime");
  }
  try {
    return new Intl.DateTimeFormat(locale.value, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  } catch {
    try {
      return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
    } catch {
      return t("documents.viewer.comments.unknownTime");
    }
  }
}

function formatVersionMeta(version: number): string {
  return t("documents.viewer.comments.metaVersion", { version });
}

function formatPageMeta(page: number): string {
  return t("documents.viewer.comments.metaPage", { page });
}

function localizeStatus(status: string): string {
  const key = `documents.viewer.comments.status.${status}`;
  const translated = t(key);
  return translated === key ? t("documents.viewer.comments.status.unknown") : translated;
}

const UUID_WITH_DASHES =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const HEX_32_ID = /^[0-9a-f]{32}$/i;

function formatAuthorDisplay(authorDisplay: string | null | undefined): string {
  if (authorDisplay === null || authorDisplay === undefined) {
    return t("documents.viewer.comments.unknownAuthor");
  }
  const trimmed = authorDisplay.trim();
  if (!trimmed || UUID_WITH_DASHES.test(trimmed) || HEX_32_ID.test(trimmed)) {
    return t("documents.viewer.comments.unknownAuthor");
  }
  return trimmed;
}

function localizeSourceKind(sourceKind: string | null | undefined): string {
  if (!sourceKind) {
    return t("documents.viewer.comments.sourceKind.unknown");
  }
  const key = `documents.viewer.comments.sourceKind.${sourceKind}`;
  const translated = t(key);
  if (translated !== key) {
    return translated;
  }
  return t("documents.viewer.comments.sourceKind.unknown");
}

const sortedItems = computed(() =>
  [...props.items].sort((a, b) => {
    const aTime = a.updated_at ?? a.created_at ?? "";
    const bTime = b.updated_at ?? b.created_at ?? "";
    return bTime.localeCompare(aTime);
  }),
);

async function loadDetail(commentId: string): Promise<void> {
  if (detailById.value[commentId]) {
    return;
  }
  const generation = ++detailGeneration.current;
  detailLoading.value = true;
  detailError.value = false;
  try {
    const detail = await fetchWorkflowCommentDetail(commentId);
    if (generation !== detailGeneration.current) {
      return;
    }
    detailById.value = { ...detailById.value, [commentId]: detail };
  } catch (cause) {
    if (generation !== detailGeneration.current) {
      return;
    }
    if (cause instanceof ApiTransportError) {
      detailError.value = true;
    } else {
      detailError.value = true;
    }
  } finally {
    if (generation === detailGeneration.current) {
      detailLoading.value = false;
    }
  }
}

function toggleExpanded(commentId: string): void {
  if (expandedId.value === commentId) {
    expandedId.value = null;
    return;
  }
  expandedId.value = commentId;
  void loadDetail(commentId);
}

function retryDetail(): void {
  if (!expandedId.value) {
    return;
  }
  const id = expandedId.value;
  const next = { ...detailById.value };
  delete next[id];
  detailById.value = next;
  void loadDetail(id);
}

watch(
  () => props.items,
  () => {
    detailGeneration.current += 1;
    expandedId.value = null;
    detailById.value = {};
    detailLoading.value = false;
    detailError.value = false;
  },
);

onUnmounted(() => {
  detailGeneration.current += 1;
  detailLoading.value = false;
  detailError.value = false;
});
</script>

<template>
  <ul class="comment-list" data-testid="comment-list">
    <li
      v-for="item in sortedItems"
      :key="item.comment_id"
      class="comment-list__item"
      data-testid="comment-list-item"
    >
      <button
        type="button"
        class="comment-list__summary"
        :data-testid="`comment-summary-${item.comment_id}`"
        :aria-expanded="expandedId === item.comment_id"
        @click="toggleExpanded(item.comment_id)"
      >
        <span class="comment-list__author">
          {{ formatAuthorDisplay(item.author_display) }}
        </span>
        <span class="comment-list__meta" data-testid="comment-list-meta">
          {{ formatTimestamp(item.created_at ?? item.updated_at) }}
          · {{ formatVersionMeta(item.version) }}
          <template v-if="item.page_number !== null && item.page_number !== undefined">
            · {{ formatPageMeta(item.page_number) }}
          </template>
          · {{ localizeStatus(item.status) }}
        </span>
        <span class="comment-list__preview">{{ item.preview_text }}</span>
      </button>

      <div
        v-if="expandedId === item.comment_id"
        class="comment-list__detail"
        :data-testid="`comment-detail-panel-${item.comment_id}`"
      >
        <p v-if="detailLoading" data-testid="comment-detail-loading">
          {{ t("documents.viewer.comments.detailLoading") }}
        </p>
        <div v-else-if="detailError" role="alert" data-testid="comment-detail-error">
          <p>{{ t("documents.viewer.comments.detailError") }}</p>
          <v-btn variant="outlined" size="small" data-testid="comment-detail-retry" @click="retryDetail">
            {{ t("documents.pool.retry") }}
          </v-btn>
        </div>
        <template v-else-if="detailById[item.comment_id]">
          <p class="comment-list__source-kind" data-testid="comment-detail-source-kind">
            {{ localizeSourceKind(detailById[item.comment_id].source_kind) }}
          </p>
          <p class="comment-list__full-text" data-testid="comment-detail-full-text">
            {{ detailById[item.comment_id].full_text }}
          </p>
        </template>
      </div>
    </li>
    <li v-if="sortedItems.length === 0" data-testid="comment-list-empty">
      {{ t("documents.viewer.comments.empty") }}
    </li>
  </ul>
</template>

<style scoped>
.comment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.comment-list__item {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}

.comment-list__summary {
  width: 100%;
  text-align: left;
  padding: 0.75rem;
  background: transparent;
  border: 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.comment-list__author {
  font-weight: 600;
}

.comment-list__meta {
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.6);
}

.comment-list__preview {
  white-space: pre-wrap;
}

.comment-list__detail {
  padding: 0 0.75rem 0.75rem;
}

.comment-list__source-kind {
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.6);
}

.comment-list__full-text {
  white-space: pre-wrap;
}
</style>
