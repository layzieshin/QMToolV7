<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  ApiTransportError,
  fetchDocumentVersionHistory,
  type UserDirectoryItem,
  type VersionHistoryEvent,
} from "../../api/client";

const props = defineProps<{
  documentId: string;
  version: number;
  directory: UserDirectoryItem[];
}>();

const { t, locale } = useI18n();

const events = ref<VersionHistoryEvent[]>([]);
const loading = ref(false);
const error = ref<ApiTransportError | Error | null>(null);
const listGeneration = { current: 0 };

const directoryById = computed(() => {
  const map = new Map<string, UserDirectoryItem>();
  for (const row of props.directory) {
    map.set(row.user_id, row);
  }
  return map;
});

function formatOccurredAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function historyEventLabel(event: VersionHistoryEvent): string {
  const eventType = event.event_type?.trim().toLowerCase() ?? "";
  const summary = event.summary?.trim().toLowerCase() ?? "";

  if (eventType === "created" && summary === "created") {
    return t("documents.detail.history.events.created");
  }
  if (eventType === "status_changed" && summary === "review completed") {
    return t("documents.detail.history.events.reviewCompleted");
  }
  if (eventType === "status_changed" && summary === "approval completed") {
    return t("documents.detail.history.events.approvalCompleted");
  }
  if (eventType === "released" && summary === "released") {
    return t("documents.detail.history.events.released");
  }
  if (eventType === "archived" && summary === "archived") {
    return t("documents.detail.history.events.archived");
  }
  if (eventType === "signed" && summary === "signed") {
    return t("documents.detail.history.events.signed");
  }
  if (eventType === "comment_added") {
    return t("documents.detail.history.events.commentAdded");
  }
  return t("documents.detail.history.events.unknown");
}

function historyEventUserContent(event: VersionHistoryEvent): string | null {
  if (event.event_type?.trim().toLowerCase() !== "comment_added") {
    return null;
  }
  const preview = event.summary?.trim();
  return preview ? preview : null;
}

function actorDisplayName(event: VersionHistoryEvent): string | null {
  const actorId = event.actor_user_id?.trim();
  if (!actorId) {
    return null;
  }
  const match = directoryById.value.get(actorId);
  if (match?.username) {
    return match.username;
  }
  return t("documents.detail.history.actorUnknown");
}

function mapLoadError(cause: ApiTransportError | Error | null): string {
  if (!cause) {
    return t("documents.detail.history.error");
  }
  if (cause instanceof ApiTransportError) {
    switch (cause.status) {
      case 401:
        return t("api.errors.unauthorized");
      case 403:
        return t("api.errors.forbidden");
      case 404:
        return t("api.errors.notFound");
      default:
        return t("documents.detail.history.error");
    }
  }
  return t("documents.detail.history.error");
}

async function loadHistory(): Promise<void> {
  const generation = ++listGeneration.current;
  loading.value = true;
  error.value = null;
  events.value = [];

  try {
    const rows = await fetchDocumentVersionHistory(props.documentId, props.version);
    if (generation !== listGeneration.current) {
      return;
    }
    events.value = Array.isArray(rows) ? rows : [];
  } catch (cause) {
    if (generation !== listGeneration.current) {
      return;
    }
    events.value = [];
    error.value = cause instanceof Error ? cause : new Error(String(cause));
  } finally {
    if (generation === listGeneration.current) {
      loading.value = false;
    }
  }
}

watch(
  () => [props.documentId, props.version] as const,
  () => {
    void loadHistory();
  },
  { immediate: true },
);

onUnmounted(() => {
  listGeneration.current += 1;
});

defineExpose({ reload: loadHistory });
</script>

<template>
  <section class="history-panel" data-testid="history-panel">
    <h2>{{ t("documents.detail.history.title") }}</h2>
    <p v-if="loading" role="status" data-testid="history-panel-loading">
      {{ t("documents.detail.history.loading") }}
    </p>
    <div v-else-if="error" role="alert" data-testid="history-panel-error">
      <p>{{ mapLoadError(error) }}</p>
      <v-btn variant="outlined" data-testid="history-panel-retry" @click="loadHistory">
        {{ t("documents.pool.retry") }}
      </v-btn>
    </div>
    <p v-else-if="events.length === 0" data-testid="history-panel-empty">
      {{ t("documents.detail.history.empty") }}
    </p>
    <ul v-else class="history-panel__list" data-testid="history-panel-list">
      <li
        v-for="(event, index) in events"
        :key="`${event.occurred_at}-${index}`"
        class="history-panel__item"
        data-testid="history-panel-item"
      >
        <time
          :datetime="event.occurred_at"
          data-testid="history-panel-occurred-at"
        >
          {{ formatOccurredAt(event.occurred_at) }}
        </time>
        <p class="history-panel__label" data-testid="history-panel-event-label">
          {{ historyEventLabel(event) }}
        </p>
        <p
          v-if="historyEventUserContent(event)"
          class="history-panel__comment"
          data-testid="history-panel-comment-content"
        >
          {{ historyEventUserContent(event) }}
        </p>
        <p
          v-if="actorDisplayName(event)"
          class="history-panel__actor"
          data-testid="history-panel-actor"
        >
          {{ t("documents.detail.history.actorLabel", { name: actorDisplayName(event) }) }}
        </p>
        <p
          v-else
          class="history-panel__actor history-panel__actor--unavailable"
          data-testid="history-panel-actor-unavailable"
        >
          {{ t("documents.detail.history.actorUnavailable") }}
        </p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-panel__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-panel__item {
  padding: 0.75rem;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}

.history-panel__label {
  margin: 0.35rem 0 0;
  font-weight: 500;
}

.history-panel__comment {
  margin: 0.35rem 0 0;
}

.history-panel__actor {
  margin: 0.35rem 0 0;
  color: rgba(0, 0, 0, 0.7);
  font-size: 0.9rem;
}

.history-panel__actor--unavailable {
  font-style: italic;
}
</style>
