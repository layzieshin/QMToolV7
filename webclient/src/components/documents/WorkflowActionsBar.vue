<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { createHandlerRegistry, dispatchAction } from "../../actions/actionDispatcher";
import { resolveActionLabel, type ActionDescriptor } from "../../actions/actionTypes";
import type { VersionStateResponse } from "../../api/client";
import { mutationErrorI18nKey } from "../../api/errors";
import {
  MutationClientError,
  MutationWritesBlockedError,
  mutate,
  type MutationBody,
} from "../../api/mutationClient";
import type { ConflictRecoveryContext } from "../../composables/useConflictRecovery";
import { useProductWriteAvailability } from "../../composables/useProductWriteAvailability";
import ActionButton from "../ActionButton.vue";
import ActionOverflowMenu from "../ActionOverflowMenu.vue";

const WORKFLOW_BAR_CODES = new Set([
  "start",
  "complete_editing",
  "review_accept",
  "review_reject",
  "approval_accept",
  "approval_reject",
  "abort",
]);

const SUPPORTED_HANDLER_CODES = new Set(WORKFLOW_BAR_CODES);

const props = defineProps<{
  detail: VersionStateResponse;
  documentId: string;
  version: number;
}>();

const emit = defineEmits<{
  updated: [payload: VersionStateResponse];
  conflict: [error: MutationClientError, context: ConflictRecoveryContext];
}>();

const { t } = useI18n();
const router = useRouter();
const { writesAllowed, blockedMessage } = useProductWriteAvailability();

const mutating = ref(false);
const alertMessage = ref<string | null>(null);
const alertLive = ref<"polite" | "assertive">("polite");
const confirmOpen = ref(false);
const reasonOpen = ref(false);
const pendingDescriptor = ref<ActionDescriptor | null>(null);
const pendingReason = ref("");
const mutationGeneration = { current: 0 };

const supportedCodes = computed(() => Array.from(SUPPORTED_HANDLER_CODES));

const workflowActions = computed(() =>
  (props.detail.allowed_actions ?? []).filter((action) => WORKFLOW_BAR_CODES.has(action.code)),
);

const primaryActions = computed(() =>
  workflowActions.value.filter((action) => !action.destructive),
);

const overflowActions = computed(() =>
  workflowActions.value.filter((action) => action.destructive),
);

watch(
  () => props.detail.etag,
  () => {
    mutationGeneration.current += 1;
    mutating.value = false;
    confirmOpen.value = false;
    reasonOpen.value = false;
    pendingDescriptor.value = null;
    pendingReason.value = "";
  },
);

function workflowPath(code: string): string {
  const base = `/documents/versions/${encodeURIComponent(props.documentId)}/${props.version}/workflow`;
  switch (code) {
    case "start":
      return `${base}/start`;
    case "complete_editing":
      return `${base}/editing-complete`;
    case "review_accept":
      return `${base}/review/accept`;
    case "review_reject":
      return `${base}/review/reject`;
    case "approval_accept":
      return `${base}/approval/accept`;
    case "approval_reject":
      return `${base}/approval/reject`;
    case "abort":
      return `${base}/abort`;
    default:
      throw new Error(`unsupported workflow code: ${code}`);
  }
}

function buildMutationBody(code: string, reason?: string): MutationBody | undefined {
  if (code === "start") {
    const profileId = props.detail.state.workflow_profile_id;
    if (!profileId) {
      return undefined;
    }
    return { json: { profile_id: profileId } };
  }
  if (code === "review_reject" || code === "approval_reject") {
    const trimmed = reason?.trim() ?? "";
    return { json: { free_text: trimmed } };
  }
  return undefined;
}

function requiresSignatureWorkspace(descriptor: ActionDescriptor): boolean {
  return descriptor.enabled && descriptor.signature_required;
}

function routeToSignatureWorkspace(descriptor: ActionDescriptor, reason?: string): void {
  const query: Record<string, string> = {
    version: String(props.version),
    action: descriptor.code,
  };
  void router.push({
    name: "document-signature",
    params: { docId: props.documentId },
    query,
    state: reason?.trim() ? { workflowReason: reason.trim() } : {},
  });
}

function mapMutationError(error: unknown): string {
  if (error instanceof MutationWritesBlockedError) {
    return blockedMessage.value;
  }
  if (error instanceof MutationClientError) {
    return t(mutationErrorI18nKey(error.kind));
  }
  return t("documents.detail.errors.connection");
}

async function executeWorkflowMutation(
  descriptor: ActionDescriptor,
  reason?: string,
): Promise<void> {
  if (mutating.value || !writesAllowed.value) {
    return;
  }
  const generation = ++mutationGeneration.current;
  mutating.value = true;
  alertMessage.value = null;
  alertLive.value = "polite";

  const body = buildMutationBody(descriptor.code, reason);
  if (descriptor.code === "start" && !body) {
    mutating.value = false;
    alertMessage.value = t("documents.workflow.errors.missingProfile");
    alertLive.value = "assertive";
    return;
  }

  try {
    const response = await mutate<VersionStateResponse>({
      method: "POST",
      path: workflowPath(descriptor.code),
      ifMatch: props.detail.etag,
      body,
    });
    if (generation !== mutationGeneration.current) {
      return;
    }
    if (response) {
      emit("updated", response);
      alertMessage.value = t("documents.workflow.success");
      alertLive.value = "polite";
    }
  } catch (error) {
    if (generation !== mutationGeneration.current) {
      return;
    }
    if (
      error instanceof MutationClientError &&
      (error.kind === "conflict" || error.kind === "precondition_required")
    ) {
      emit("conflict", error, {
        actionCode: descriptor.code,
        actionLabel: resolveActionLabel(descriptor, t, t("actions.genericLabel")),
        reason,
      });
      return;
    }
    alertMessage.value = mapMutationError(error);
    alertLive.value = "assertive";
  } finally {
    if (generation === mutationGeneration.current) {
      mutating.value = false;
    }
  }
}

function handleWorkflowAction(ctx: {
  descriptor: ActionDescriptor;
  reason?: string;
}): Promise<void> | void {
  if (requiresSignatureWorkspace(ctx.descriptor)) {
    routeToSignatureWorkspace(ctx.descriptor, ctx.reason);
    return;
  }
  return executeWorkflowMutation(ctx.descriptor, ctx.reason);
}

const handlers = createHandlerRegistry({
  start: (ctx) => executeWorkflowMutation(ctx.descriptor, ctx.reason),
  complete_editing: (ctx) => handleWorkflowAction(ctx),
  review_accept: (ctx) => handleWorkflowAction(ctx),
  review_reject: (ctx) => executeWorkflowMutation(ctx.descriptor, ctx.reason),
  approval_accept: (ctx) => handleWorkflowAction(ctx),
  approval_reject: (ctx) => executeWorkflowMutation(ctx.descriptor, ctx.reason),
  abort: (ctx) => executeWorkflowMutation(ctx.descriptor, ctx.reason),
});

async function runDispatch(
  descriptor: ActionDescriptor,
  options: { confirmed?: boolean; reason?: string } = {},
): Promise<void> {
  if (mutating.value || !writesAllowed.value) {
    return;
  }
  const result = await dispatchAction({
    descriptor,
    handlers,
    confirmed: options.confirmed ?? false,
    reason: options.reason,
  });

  if (result.status === "confirmation_required") {
    pendingDescriptor.value = descriptor;
    confirmOpen.value = true;
    return;
  }
  if (result.status === "reason_required") {
    pendingDescriptor.value = descriptor;
    pendingReason.value = "";
    reasonOpen.value = true;
    return;
  }
  if (result.status === "disabled" || result.status === "unsupported") {
    return;
  }
}

function onAction(descriptor: ActionDescriptor): void {
  void runDispatch(descriptor);
}

function onConfirm(): void {
  if (!writesAllowed.value) {
    return;
  }
  const descriptor = pendingDescriptor.value;
  confirmOpen.value = false;
  if (!descriptor) {
    return;
  }
  void runDispatch(descriptor, { confirmed: true, reason: pendingReason.value });
}

function onCancelConfirm(): void {
  confirmOpen.value = false;
  pendingDescriptor.value = null;
}

function onSubmitReason(): void {
  if (!writesAllowed.value) {
    return;
  }
  const descriptor = pendingDescriptor.value;
  if (!descriptor) {
    return;
  }
  const reason = pendingReason.value;
  reasonOpen.value = false;
  pendingDescriptor.value = null;
  void runDispatch(descriptor, { confirmed: true, reason });
}

function onCancelReason(): void {
  reasonOpen.value = false;
  pendingDescriptor.value = null;
  pendingReason.value = "";
}
</script>

<template>
  <section class="workflow-actions-bar" data-testid="workflow-actions-bar">
    <h3>{{ t("documents.workflow.title") }}</h3>

    <p
      v-if="!writesAllowed"
      role="status"
      data-testid="workflow-writes-blocked"
    >
      {{ blockedMessage }}
    </p>

    <p
      v-if="alertMessage"
      :role="alertLive === 'assertive' ? 'alert' : 'status'"
      :aria-live="alertLive"
      data-testid="workflow-actions-alert"
    >
      {{ alertMessage }}
    </p>

    <div class="workflow-actions-bar__controls">
      <ActionButton
        v-for="action in primaryActions"
        :key="action.code"
        :descriptor="action"
        :supported="supportedCodes.includes(action.code)"
        :product-writes-allowed="writesAllowed"
        :product-writes-blocked-message="blockedMessage"
        :data-testid="`workflow-action-${action.code}`"
        @action="onAction"
      />
      <ActionOverflowMenu
        :actions="overflowActions"
        :supported-codes="supportedCodes"
        :product-writes-allowed="writesAllowed"
        :product-writes-blocked-message="blockedMessage"
        @action="onAction"
      />
    </div>

    <v-dialog v-model="confirmOpen" max-width="480" data-testid="workflow-confirm-dialog">
      <v-card>
        <v-card-title>{{ t("documents.workflow.confirmTitle") }}</v-card-title>
        <v-card-text>{{ t("documents.workflow.confirmMessage") }}</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="onCancelConfirm">{{ t("conflict.cancel") }}</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!writesAllowed" @click="onConfirm">
            {{ t("documents.workflow.confirmProceed") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="reasonOpen" max-width="520" data-testid="workflow-reason-dialog">
      <v-card>
        <v-card-title>{{ t("documents.workflow.reasonTitle") }}</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="pendingReason"
            :label="t('documents.workflow.reasonLabel')"
            rows="3"
            auto-grow
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="onCancelReason">{{ t("conflict.cancel") }}</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!writesAllowed" @click="onSubmitReason">
            {{ t("documents.workflow.reasonSubmit") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<style scoped>
.workflow-actions-bar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.workflow-actions-bar__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
</style>
