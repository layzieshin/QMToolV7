<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import type { ActionDescriptor } from "../../actions/actionTypes";
import type { UserDirectoryItem, VersionStateResponse } from "../../api/client";
import { MutationClientError, MutationWritesBlockedError, mutate } from "../../api/mutationClient";
import { mutationErrorI18nKey } from "../../api/errors";
import { useProductWriteAvailability } from "../../composables/useProductWriteAvailability";

const props = defineProps<{
  detail: VersionStateResponse | null;
  directory: UserDirectoryItem[];
  directoryLoading: boolean;
  directoryError: boolean;
  documentId: string;
  version: number | null;
}>();

const emit = defineEmits<{
  updated: [payload: VersionStateResponse];
}>();

const { t } = useI18n();
const { writesAllowed, blockedMessage } = useProductWriteAvailability();

const editors = ref<string[]>([]);
const reviewers = ref<string[]>([]);
const approvers = ref<string[]>([]);
const submitting = ref(false);
const alertMessage = ref<string | null>(null);
const alertLive = ref<"polite" | "assertive">("polite");

function isAssignRolesEnabled(actions: ActionDescriptor[] | undefined): boolean {
  return Boolean(
    actions?.some((action) => action.code === "assign_roles" && action.enabled),
  );
}

const canEdit = computed(() => {
  if (!props.detail || props.directoryLoading || props.directoryError || !writesAllowed.value) {
    return false;
  }
  return isAssignRolesEnabled(props.detail.allowed_actions);
});

const directoryById = computed(() => {
  const map = new Map<string, UserDirectoryItem>();
  for (const entry of props.directory) {
    map.set(entry.user_id, entry);
  }
  return map;
});

function displayName(userId: string): string {
  const entry = directoryById.value.get(userId);
  if (entry?.is_active) {
    return entry.username;
  }
  return t("documents.detail.assignments.unavailableUser");
}

function buildRoleOptions(selectedIds: string[]) {
  const options = props.directory
    .filter((entry) => entry.is_active)
    .map((entry) => ({
      title: entry.username,
      value: entry.user_id,
    }));
  for (const userId of selectedIds) {
    if (!options.some((option) => option.value === userId)) {
      options.push({
        title: displayName(userId),
        value: userId,
      });
    }
  }
  return options;
}

const editorOptions = computed(() => buildRoleOptions(editors.value));
const reviewerOptions = computed(() => buildRoleOptions(reviewers.value));
const approverOptions = computed(() => buildRoleOptions(approvers.value));

watch(
  () => props.detail?.state.assignments,
  (assignments) => {
    if (!assignments) {
      editors.value = [];
      reviewers.value = [];
      approvers.value = [];
      return;
    }
    editors.value = [...assignments.editors];
    reviewers.value = [...assignments.reviewers];
    approvers.value = [...assignments.approvers];
  },
  { immediate: true, deep: true },
);

function assignedLabels(ids: string[]): string[] {
  return ids.map((id) => displayName(id));
}

function mapSubmitError(error: unknown): string {
  if (error instanceof MutationWritesBlockedError) {
    return blockedMessage.value;
  }
  if (error instanceof MutationClientError) {
    if (error.kind === "conflict" || error.kind === "precondition_required") {
      return t("documents.detail.assignments.conflictDeferred");
    }
    return t(mutationErrorI18nKey(error.kind));
  }
  return t("documents.detail.errors.connection");
}

async function submitAssignments(): Promise<void> {
  if (!props.detail || !props.version || submitting.value || !canEdit.value || !writesAllowed.value) {
    return;
  }
  submitting.value = true;
  alertMessage.value = null;
  alertLive.value = "polite";

  try {
    const response = await mutate<VersionStateResponse>({
      method: "POST",
      path: `/documents/versions/${encodeURIComponent(props.documentId)}/${props.version}/workflow/assign-roles`,
      ifMatch: props.detail.etag,
      body: {
        json: {
          editors: editors.value,
          reviewers: reviewers.value,
          approvers: approvers.value,
        },
      },
    });
    if (response) {
      emit("updated", response);
      alertMessage.value = t("documents.detail.assignmentsSaveSuccess");
      alertLive.value = "polite";
    }
  } catch (error) {
    alertMessage.value = mapSubmitError(error);
    alertLive.value = "assertive";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="assignments-panel" data-testid="assignments-panel">
    <h3>{{ t("documents.detail.assignmentsTitle") }}</h3>

    <p
      v-if="directoryLoading"
      data-testid="assignments-directory-loading"
    >
      {{ t("documents.detail.directoryLoading") }}
    </p>

    <p
      v-else-if="directoryError"
      role="alert"
      aria-live="polite"
      data-testid="assignments-directory-error"
    >
      {{ t("documents.detail.directoryError") }}
    </p>

    <template v-if="detail">
      <p
        v-if="!writesAllowed && isAssignRolesEnabled(detail.allowed_actions)"
        role="status"
        data-testid="assignments-writes-blocked"
      >
        {{ blockedMessage }}
      </p>

      <dl v-if="!canEdit" data-testid="assignments-readonly">
        <dt>{{ t("documents.detail.assignmentsEditors") }}</dt>
        <dd data-testid="assignments-editors-readonly">
          {{ assignedLabels(editors).join(", ") || "—" }}
        </dd>
        <dt>{{ t("documents.detail.assignmentsReviewers") }}</dt>
        <dd data-testid="assignments-reviewers-readonly">
          {{ assignedLabels(reviewers).join(", ") || "—" }}
        </dd>
        <dt>{{ t("documents.detail.assignmentsApprovers") }}</dt>
        <dd data-testid="assignments-approvers-readonly">
          {{ assignedLabels(approvers).join(", ") || "—" }}
        </dd>
      </dl>

      <form v-else data-testid="assignments-form" @submit.prevent="submitAssignments">
        <v-select
          v-model="editors"
          :items="editorOptions"
          item-title="title"
          item-value="value"
          :label="t('documents.detail.assignmentsEditors')"
          multiple
          chips
          data-testid="assignments-editors"
        />
        <v-select
          v-model="reviewers"
          :items="reviewerOptions"
          item-title="title"
          item-value="value"
          :label="t('documents.detail.assignmentsReviewers')"
          multiple
          chips
          data-testid="assignments-reviewers"
        />
        <v-select
          v-model="approvers"
          :items="approverOptions"
          item-title="title"
          item-value="value"
          :label="t('documents.detail.assignmentsApprovers')"
          multiple
          chips
          data-testid="assignments-approvers"
        />
        <v-btn
          type="submit"
          color="primary"
          :loading="submitting"
          :disabled="submitting"
          data-testid="assignments-submit"
        >
          {{ t("documents.detail.assignmentsSave") }}
        </v-btn>
      </form>

      <p
        v-if="alertMessage"
        role="alert"
        :aria-live="alertLive"
        data-testid="assignments-alert"
      >
        {{ alertMessage }}
      </p>
    </template>
  </section>
</template>

<style scoped>
.assignments-panel {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  padding: 1rem;
}

.assignments-panel h3 {
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
