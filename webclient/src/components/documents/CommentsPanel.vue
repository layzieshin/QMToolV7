<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  ApiTransportError,
  fetchDocumentVersion,
  fetchWorkflowComments,
  type VersionStateResponse,
  type WorkflowCommentListItemModel,
} from "../../api/client";
import { mutationErrorI18nKey } from "../../api/errors";
import {
  MutationClientError,
  MutationWritesBlockedError,
  mutate,
} from "../../api/mutationClient";
import type { ConflictRecoveryContext } from "../../composables/useConflictRecovery";
import { useProductWriteAvailability } from "../../composables/useProductWriteAvailability";
import CommentList from "./CommentList.vue";

const props = defineProps<{
  documentId: string;
  version: number;
  detail: VersionStateResponse;
  currentPage: number;
  hasPdf: boolean;
}>();

const emit = defineEmits<{
  detailUpdated: [payload: VersionStateResponse];
  conflict: [error: MutationClientError, context: ConflictRecoveryContext];
}>();

const { t } = useI18n();
const { writesAllowed, blockedMessage } = useProductWriteAvailability();

const comments = ref<WorkflowCommentListItemModel[]>([]);
const commentsLoading = ref(false);
const commentsError = ref<ApiTransportError | Error | null>(null);
const submitMessage = ref<string | null>(null);
const submitError = ref<string | null>(null);
const submitRefreshError = ref<string | null>(null);
const commentText = ref("");
const submitting = ref(false);
const listGeneration = { current: 0 };
const submitGeneration = { current: 0 };

const commentsEnabled = computed(() =>
  (props.detail.allowed_actions ?? []).some(
    (action) => action.code === "comments" && action.enabled,
  ),
);

const commentsCreateEligible = computed(
  () => commentsEnabled.value && props.hasPdf && props.currentPage >= 1,
);

const showCreateForm = computed(
  () => commentsCreateEligible.value && writesAllowed.value,
);

const commentsWritesBlocked = computed(
  () => commentsCreateEligible.value && !writesAllowed.value,
);

watch(
  () => props.detail.etag,
  (etag, previousEtag) => {
    submitGeneration.current += 1;
    submitting.value = false;
    submitError.value = null;
    if (previousEtag !== undefined && etag !== previousEtag) {
      void loadComments();
    }
  },
);

async function loadComments(): Promise<void> {
  const generation = ++listGeneration.current;
  commentsLoading.value = true;
  commentsError.value = null;
  comments.value = [];

  try {
    const rows = await fetchWorkflowComments(props.documentId, props.version);
    if (generation !== listGeneration.current) {
      return;
    }
    comments.value = rows;
  } catch (cause) {
    if (generation !== listGeneration.current) {
      return;
    }
    comments.value = [];
    commentsError.value = cause instanceof Error ? cause : new Error(String(cause));
  } finally {
    if (generation === listGeneration.current) {
      commentsLoading.value = false;
    }
  }
}

function mapLoadError(cause: ApiTransportError | Error | null): string {
  if (!cause) {
    return t("documents.viewer.comments.loadError");
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
        return t("api.errors.transport");
    }
  }
  return t("documents.viewer.comments.loadError");
}

async function submitComment(): Promise<void> {
  if (!showCreateForm.value || submitting.value || !writesAllowed.value) {
    return;
  }
  const trimmed = commentText.value.trim();
  if (!trimmed) {
    submitError.value = t("documents.viewer.comments.validationEmpty");
    return;
  }

  const generation = ++submitGeneration.current;
  submitting.value = true;
  submitMessage.value = null;
  submitError.value = null;
  submitRefreshError.value = null;

  const actionLabel = t("documents.viewer.comments.createAction");

  try {
    await mutate({
      method: "POST",
      path: `/documents/versions/${encodeURIComponent(props.documentId)}/${props.version}/comments`,
      ifMatch: props.detail.etag,
      body: {
        json: {
          context: "PDF_REVIEW",
          page_number: props.currentPage,
          comment_text: trimmed,
        },
      },
    });

    if (generation !== submitGeneration.current) {
      return;
    }

    submitMessage.value = t("documents.viewer.comments.createSuccess");
    commentText.value = "";
    try {
      await reloadAfterMutation();
    } catch {
      submitRefreshError.value = t("documents.viewer.comments.refreshAfterCreateError");
    }
  } catch (cause) {
    if (generation !== submitGeneration.current) {
      return;
    }
    if (cause instanceof MutationWritesBlockedError) {
      submitError.value = blockedMessage.value;
      return;
    }
    if (cause instanceof MutationClientError) {
      if (cause.kind === "conflict" || cause.kind === "precondition_required") {
        emit("conflict", cause, {
          actionLabel,
          reason: trimmed,
        });
        return;
      }
      submitError.value = t(mutationErrorI18nKey(cause.kind));
      return;
    }
    submitError.value = t("documents.viewer.comments.createError");
  } finally {
    if (generation === submitGeneration.current) {
      submitting.value = false;
    }
  }
}

async function reloadAfterMutation(): Promise<void> {
  const updated = await fetchDocumentVersion(props.documentId, props.version);
  emit("detailUpdated", updated);
}

watch(
  () => [props.documentId, props.version] as const,
  () => {
    void loadComments();
  },
  { immediate: true },
);

onUnmounted(() => {
  listGeneration.current += 1;
  submitGeneration.current += 1;
});

defineExpose({
  reloadComments: loadComments,
});
</script>

<template>
  <section class="comments-panel" data-testid="comments-panel">
    <h2>{{ t("documents.viewer.comments.title") }}</h2>

    <p v-if="commentsLoading" data-testid="comments-panel-loading">
      {{ t("documents.viewer.comments.loading") }}
    </p>

    <div v-else-if="commentsError" role="alert" data-testid="comments-panel-error">
      <p>{{ mapLoadError(commentsError) }}</p>
      <v-btn variant="outlined" size="small" data-testid="comments-panel-retry" @click="loadComments">
        {{ t("documents.pool.retry") }}
      </v-btn>
    </div>

    <CommentList v-else :items="comments" />

    <p
      v-if="commentsWritesBlocked"
      role="status"
      data-testid="comments-writes-blocked"
    >
      {{ blockedMessage }}
    </p>

    <form
      v-if="showCreateForm"
      class="comments-panel__form"
      data-testid="comments-create-form"
      @submit.prevent="submitComment"
    >
      <label for="comment-text-input">{{ t("documents.viewer.comments.newLabel") }}</label>
      <textarea
        id="comment-text-input"
        v-model="commentText"
        rows="3"
        data-testid="comments-text-input"
        :disabled="submitting"
        :aria-label="t('documents.viewer.comments.newLabel')"
      />
      <p class="comments-panel__page-hint" data-testid="comments-page-hint">
        {{ t("documents.viewer.comments.pageHint", { page: currentPage }) }}
      </p>
      <v-btn
        type="submit"
        color="primary"
        data-testid="comments-submit"
        :disabled="submitting"
        :loading="submitting"
      >
        {{ t("documents.viewer.comments.submit") }}
      </v-btn>
      <p v-if="submitMessage" role="status" data-testid="comments-submit-success">
        {{ submitMessage }}
      </p>
      <p v-if="submitRefreshError" role="alert" data-testid="comments-submit-refresh-error">
        {{ submitRefreshError }}
      </p>
      <p v-if="submitError" role="alert" data-testid="comments-submit-error">
        {{ submitError }}
      </p>
    </form>
  </section>
</template>

<style scoped>
.comments-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.comments-panel__form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 1rem;
}

.comments-panel__form textarea {
  width: 100%;
  min-height: 4rem;
}

.comments-panel__page-hint {
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.6);
}
</style>
