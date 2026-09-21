<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import {
  ApiTransportError,
  fetchActiveSignatureAssetContent,
  fetchActiveSignatureAssetId,
  fetchArtifactPreviewBlob,
  fetchDocumentArtifacts,
  fetchDocumentVersion,
  fetchSignatureTemplateSuggestion,
  fetchSignatureTemplatesGlobal,
  fetchSignatureTemplatesUser,
  pdfPreviewMimeType,
  signatureImageMimeType,
  type DocumentArtifactModel,
  type EnsureSourcePdfResponse,
  type SignatureTemplateModel,
  type VersionStateResponse,
} from "../../api/client";
import { mutationErrorI18nKey } from "../../api/errors";
import {
  MutationClientError,
  MutationWritesBlockedError,
  mutate,
  type MutationBody,
} from "../../api/mutationClient";
import { useProductWriteAvailability } from "../../composables/useProductWriteAvailability";
import ConflictDialog from "../../components/conflict/ConflictDialog.vue";
import ReleasedArtifactPanel from "../../components/documents/ReleasedArtifactPanel.vue";
import ReauthDialog from "../../components/signature/ReauthDialog.vue";
import SignaturePlacementCanvas, {
  type CanonicalPlacement,
} from "../../components/signature/SignaturePlacementCanvas.vue";
import type { ActionDescriptor } from "../../actions/actionTypes";
import { parseDetailRouteVersion } from "../../composables/useDocumentDetail";
import { useConflictRecovery } from "../../composables/useConflictRecovery";
import { normalizeBlobMimeType } from "../../composables/usePdfPreview";

const SIGNATURE_ACTION_CODES = new Set(["complete_editing", "review_accept", "approval_accept"]);
const SIGNED_PDF_ARTIFACT_TYPE = "SIGNED_PDF";

const DEFAULT_PLACEMENT: CanonicalPlacement = {
  page_index: 0,
  x: 72,
  y: 72,
  target_width: 120,
};

type SignatureLayout = {
  show_signature: boolean;
  show_name: boolean;
  show_date: boolean;
  show_time: boolean;
  name_position: string;
  date_position: string;
};

const DEFAULT_LAYOUT: SignatureLayout = {
  show_signature: true,
  show_name: true,
  show_date: true,
  show_time: false,
  name_position: "above",
  date_position: "below",
};

type SignatureDraftSnapshot = {
  placement: CanonicalPlacement;
  layout: SignatureLayout;
  selectedTemplateId: string | null;
};

type OperationKind = "workspaceLoad" | "sign" | "templateSave" | "assetLoad" | "artifactRefresh";

type OperationToken = {
  workspaceGen: number;
  operationGen: number;
  kind: OperationKind;
};

defineOptions({
  name: "SignatureWorkspaceView",
});

const { t } = useI18n();
const { writesAllowed, blockedMessage } = useProductWriteAvailability();
const route = useRoute();
const router = useRouter();

const workspaceGeneration = { current: 0 };
const operationGeneration: Record<OperationKind, number> = {
  workspaceLoad: 0,
  sign: 0,
  templateSave: 0,
  assetLoad: 0,
  artifactRefresh: 0,
};

const detail = shallowRef<VersionStateResponse | null>(null);
const artifacts = shallowRef<DocumentArtifactModel[]>([]);
const sourceArtifactId = ref<string | null>(null);
const sourcePdfUrl = ref<string | null>(null);
const activeAssetId = ref<string | null>(null);
const signatureImageUrl = ref<string | null>(null);
const signatureAssetError = ref<string | null>(null);
const signatureAssetLoading = ref(false);
const loading = ref(false);
const loadError = ref<string | null>(null);
const workspaceReady = ref(false);
const signedSuccess = ref(false);
const artifactsUnknown = ref(false);
const artifactRefreshError = ref<string | null>(null);
const reauthOpen = ref(false);
const reauthLoading = ref(false);
const reauthError = ref<string | null>(null);
const pendingEnsureSourceRetry = ref(false);
const ensureSourceRetryUsed = ref(false);
const mutating = ref(false);
const alertMessage = ref<string | null>(null);
const conflictDraftSnapshot = ref<SignatureDraftSnapshot | null>(null);
const conflictReloadInProgress = ref(false);

const userTemplates = ref<SignatureTemplateModel[]>([]);
const globalTemplates = ref<SignatureTemplateModel[]>([]);
const suggestion = ref<SignatureTemplateModel | null>(null);
const selectedTemplateId = ref<string | null>(null);

const placement = ref<CanonicalPlacement>({ ...DEFAULT_PLACEMENT });
const layout = ref<SignatureLayout>({ ...DEFAULT_LAYOUT });

const documentId = computed(() => String(route.params.docId ?? "").trim());
const versionParse = computed(() => parseDetailRouteVersion(route.query.version));

const actionCode = computed(() => {
  const raw = route.query.action;
  if (typeof raw !== "string" || Array.isArray(raw)) {
    return null;
  }
  const trimmed = raw.trim();
  return SIGNATURE_ACTION_CODES.has(trimmed) ? trimmed : null;
});

const workflowReason = computed(() => {
  const state = history.state as { workflowReason?: unknown } | null;
  const fromState = state?.workflowReason;
  if (typeof fromState === "string" && fromState.trim()) {
    return fromState.trim();
  }
  return null;
});

const routeValid = computed(
  () => Boolean(documentId.value) && versionParse.value.valid && Boolean(actionCode.value),
);

const templatePickerOptions = computed(() => {
  const byId = new Map<string, SignatureTemplateModel>();
  for (const row of userTemplates.value) {
    byId.set(row.template_id, row);
  }
  for (const row of globalTemplates.value) {
    byId.set(row.template_id, row);
  }
  const suggested = suggestion.value;
  if (suggested && !byId.has(suggested.template_id)) {
    byId.set(suggested.template_id, suggested);
  }
  return [...byId.values()];
});

const selectedTemplate = computed(() => {
  const selectedId = selectedTemplateId.value;
  if (!selectedId) {
    return null;
  }
  return templatePickerOptions.value.find((row) => row.template_id === selectedId) ?? null;
});

const selectedTemplateAssetId = computed(() => {
  const explicit = selectedTemplate.value?.signature_asset_id?.trim();
  return explicit || null;
});

const signatureAssetMismatch = computed(
  () =>
    Boolean(selectedTemplateAssetId.value) &&
    selectedTemplateAssetId.value !== activeAssetId.value,
);

const signaturePreviewUrl = computed(() => {
  if (!layout.value.show_signature || signatureAssetMismatch.value) {
    return null;
  }
  if (selectedTemplateAssetId.value) {
    return selectedTemplateAssetId.value === activeAssetId.value ? signatureImageUrl.value : null;
  }
  return signatureImageUrl.value;
});

const missingSignatureAsset = computed(
  () =>
    layout.value.show_signature &&
    !selectedTemplateAssetId.value &&
    !activeAssetId.value &&
    !signatureAssetLoading.value,
);

const {
  conflictVisible,
  conflictLoading,
  reloadFailed,
  showingLocalInput,
  preservedContext,
  openConflict,
  cancelConflict,
  viewLocalInput,
} = useConflictRecovery({
  detail,
  reload: reloadWorkspace,
});

let activeSourceObjectUrl: string | null = null;
let activeSignatureObjectUrl: string | null = null;

function beginOperation(kind: OperationKind): OperationToken {
  operationGeneration[kind] += 1;
  return {
    workspaceGen: workspaceGeneration.current,
    operationGen: operationGeneration[kind],
    kind,
  };
}

function isOperationActive(token: OperationToken): boolean {
  return (
    token.workspaceGen === workspaceGeneration.current &&
    token.operationGen === operationGeneration[token.kind]
  );
}

function resetBusyState(): void {
  mutating.value = false;
  reauthLoading.value = false;
  reauthOpen.value = false;
  reauthError.value = null;
  signatureAssetLoading.value = false;
  conflictReloadInProgress.value = false;
}

function invalidateWorkspaceOperations(): void {
  workspaceGeneration.current += 1;
  resetBusyState();
}

function clearConflictForRouteChange(): void {
  if (conflictVisible.value || conflictDraftSnapshot.value || showingLocalInput.value) {
    cancelConflict();
  }
  conflictDraftSnapshot.value = null;
}

function revokeSourceUrl(): void {
  if (activeSourceObjectUrl) {
    URL.revokeObjectURL(activeSourceObjectUrl);
    activeSourceObjectUrl = null;
  }
  sourcePdfUrl.value = null;
}

function revokeSignatureUrl(): void {
  if (activeSignatureObjectUrl) {
    URL.revokeObjectURL(activeSignatureObjectUrl);
    activeSignatureObjectUrl = null;
  }
  signatureImageUrl.value = null;
}

function resetWorkspaceState(): void {
  detail.value = null;
  artifacts.value = [];
  sourceArtifactId.value = null;
  revokeSourceUrl();
  activeAssetId.value = null;
  revokeSignatureUrl();
  signatureAssetError.value = null;
  signatureAssetLoading.value = false;
  loadError.value = null;
  workspaceReady.value = false;
  signedSuccess.value = false;
  artifactsUnknown.value = false;
  artifactRefreshError.value = null;
  alertMessage.value = null;
  userTemplates.value = [];
  globalTemplates.value = [];
  suggestion.value = null;
  selectedTemplateId.value = null;
  placement.value = { ...DEFAULT_PLACEMENT };
  layout.value = { ...DEFAULT_LAYOUT };
}

function snapshotDraft(): void {
  if (conflictReloadInProgress.value && conflictDraftSnapshot.value) {
    return;
  }
  conflictDraftSnapshot.value = {
    placement: { ...placement.value },
    layout: { ...layout.value },
    selectedTemplateId: selectedTemplateId.value,
  };
}

function restoreDraft(): void {
  const snapshot = conflictDraftSnapshot.value;
  if (!snapshot) {
    return;
  }
  placement.value = { ...snapshot.placement };
  layout.value = { ...snapshot.layout };
  selectedTemplateId.value = snapshot.selectedTemplateId;
}

function openConflictWithDraft(
  error: MutationClientError,
  context?: { actionCode?: string; actionLabel?: string; reason?: string },
): void {
  snapshotDraft();
  openConflict(error, context);
}

function onViewLocalDraft(): void {
  viewLocalInput();
  restoreDraft();
}

function mapLoadError(cause: unknown): string {
  if (cause instanceof MutationWritesBlockedError) {
    return blockedMessage.value;
  }
  if (cause instanceof ApiTransportError) {
    switch (cause.status) {
      case 401:
        return t("api.errors.unauthorized");
      case 403:
        return t("signature.workspace.errors.forbidden");
      case 404:
        return t("api.errors.notFound");
      default:
        return t("api.errors.transport");
    }
  }
  if (cause instanceof MutationClientError) {
    return t(mutationErrorI18nKey(cause.kind));
  }
  return t("signature.workspace.errors.connection");
}

function findActionDescriptor(
  state: VersionStateResponse,
  code: string,
): ActionDescriptor | undefined {
  return (state.allowed_actions ?? []).find((action) => action.code === code);
}

function isSignatureRequiredDescriptor(descriptor: ActionDescriptor | undefined): boolean {
  return Boolean(descriptor?.enabled && descriptor.signature_required);
}

function assignmentKindForAction(state: VersionStateResponse, code: string): string | null {
  return findActionDescriptor(state, code)?.assignment_kind ?? null;
}

function isActionEnabled(state: VersionStateResponse, code: string): boolean {
  return Boolean(findActionDescriptor(state, code)?.enabled);
}

function toAuthoritativeState(ensured: EnsureSourcePdfResponse): VersionStateResponse {
  return {
    etag: ensured.etag,
    allowed_actions: ensured.allowed_actions,
    available_actions: ensured.available_actions,
    state: ensured.state,
  };
}

function usesEnsureSourcePdf(action: string): boolean {
  return action === "complete_editing";
}

function parseArtifactCreatedAt(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function resolveSignedPdfArtifact(rows: DocumentArtifactModel[]): DocumentArtifactModel | null {
  const signed = rows.filter((row) => row.artifact_type === SIGNED_PDF_ARTIFACT_TYPE);
  if (!signed.length) {
    return null;
  }
  const current = signed.filter((row) => row.is_current);
  const pool = current.length > 0 ? current : signed;
  return [...pool].sort(
    (left, right) => parseArtifactCreatedAt(right.created_at) - parseArtifactCreatedAt(left.created_at),
  )[0] ?? null;
}

function workflowPath(code: string): string {
  const docId = encodeURIComponent(documentId.value);
  const ver = encodeURIComponent(String(versionParse.value.valid ? versionParse.value.version : ""));
  const base = `/documents/versions/${docId}/${ver}/workflow`;
  switch (code) {
    case "complete_editing":
      return `${base}/editing-complete`;
    case "review_accept":
      return `${base}/review/accept`;
    case "approval_accept":
      return `${base}/approval/accept`;
    default:
      throw new Error(`unsupported signature action: ${code}`);
  }
}

async function loadSourcePreview(artifactId: string, token: OperationToken): Promise<void> {
  revokeSourceUrl();
  const blob = await fetchArtifactPreviewBlob(artifactId);
  if (!isOperationActive(token)) {
    return;
  }
  if (normalizeBlobMimeType(blob.type) !== pdfPreviewMimeType()) {
    throw new Error("invalid preview mime");
  }
  const objectUrl = URL.createObjectURL(blob);
  activeSourceObjectUrl = objectUrl;
  sourcePdfUrl.value = objectUrl;
}

async function loadActiveSignatureAsset(token: OperationToken): Promise<void> {
  signatureAssetLoading.value = true;
  signatureAssetError.value = null;
  activeAssetId.value = null;
  revokeSignatureUrl();
  try {
    const assetId = await fetchActiveSignatureAssetId();
    if (!isOperationActive(token)) {
      return;
    }
    activeAssetId.value = assetId;
    if (!assetId) {
      return;
    }
    const blob = await fetchActiveSignatureAssetContent();
    if (!isOperationActive(token)) {
      return;
    }
    if (!blob) {
      activeAssetId.value = null;
      return;
    }
    if (normalizeBlobMimeType(blob.type) !== signatureImageMimeType()) {
      throw new Error("invalid signature mime");
    }
    const objectUrl = URL.createObjectURL(blob);
    activeSignatureObjectUrl = objectUrl;
    signatureImageUrl.value = objectUrl;
  } catch (cause) {
    if (!isOperationActive(token)) {
      return;
    }
    signatureAssetError.value = mapLoadError(cause);
    activeAssetId.value = null;
    revokeSignatureUrl();
  } finally {
    if (isOperationActive(token)) {
      signatureAssetLoading.value = false;
    }
  }
}

async function loadTemplates(state: VersionStateResponse, token: OperationToken): Promise<void> {
  const docType = state.state.doc_type;
  const code = actionCode.value;
  const role = code ? assignmentKindForAction(state, code) : null;
  if (!docType || !role) {
    return;
  }
  const [userList, globalList, suggested] = await Promise.all([
    fetchSignatureTemplatesUser(),
    fetchSignatureTemplatesGlobal(),
    fetchSignatureTemplateSuggestion(docType, role),
  ]);
  if (!isOperationActive(token)) {
    return;
  }
  userTemplates.value = userList;
  globalTemplates.value = globalList;
  suggestion.value = suggested;
  if (suggested) {
    applyTemplatePreview(suggested, true);
  }
}

function applyTemplatePreview(template: SignatureTemplateModel, select: boolean): void {
  placement.value = {
    page_index: template.placement.page_index,
    x: template.placement.x,
    y: template.placement.y,
    target_width: template.placement.target_width,
  };
  layout.value = {
    show_signature: template.layout.show_signature,
    show_name: template.layout.show_name,
    show_date: template.layout.show_date,
    show_time: template.layout.show_date ? template.layout.show_time : false,
    name_position: template.layout.name_position,
    date_position: template.layout.date_position,
  };
  if (select) {
    selectedTemplateId.value = template.template_id;
  }
}

async function ensureSourcePdf(state: VersionStateResponse): Promise<EnsureSourcePdfResponse> {
  const version = versionParse.value.valid ? versionParse.value.version : null;
  if (version === null) {
    throw new Error("missing version");
  }
  const response = await mutate<EnsureSourcePdfResponse>({
    method: "POST",
    path: `/documents/versions/${encodeURIComponent(documentId.value)}/${encodeURIComponent(String(version))}/workflow/ensure-source-pdf`,
    ifMatch: state.etag,
  });
  if (!response) {
    throw new Error("ensure-source-pdf returned empty response");
  }
  return response;
}

async function refreshArtifacts(token: OperationToken): Promise<void> {
  const version = versionParse.value.valid ? versionParse.value.version : null;
  if (version === null) {
    return;
  }
  const rows = await fetchDocumentArtifacts(documentId.value, version);
  if (!isOperationActive(token)) {
    return;
  }
  artifacts.value = rows;
  artifactsUnknown.value = false;
  artifactRefreshError.value = null;
}

async function reloadWorkspace(): Promise<void> {
  await initializeWorkspace();
}

async function initializeWorkspace(): Promise<void> {
  if (!routeValid.value || !versionParse.value.valid || !actionCode.value) {
    resetWorkspaceState();
    workspaceReady.value = false;
    loadError.value = t("signature.workspace.errors.invalidRoute");
    return;
  }

  const loadToken = beginOperation("workspaceLoad");
  resetWorkspaceState();
  loading.value = true;
  loadError.value = null;

  try {
    const version = versionParse.value.version;
    const initial = await fetchDocumentVersion(documentId.value, version);
    if (!isOperationActive(loadToken)) {
      return;
    }

    const initialDescriptor = findActionDescriptor(initial, actionCode.value);
    if (!isSignatureRequiredDescriptor(initialDescriptor)) {
      if (!initialDescriptor?.enabled) {
        loadError.value = t("signature.workspace.errors.actionDisabled");
        return;
      }
      loadError.value = t("signature.workspace.errors.signatureNotRequired");
      return;
    }

    const code = actionCode.value;
    if (!code) {
      loadError.value = t("signature.workspace.errors.invalidRoute");
      return;
    }

    let authoritative: VersionStateResponse;
    let previewArtifactId: string | null = null;

    if (usesEnsureSourcePdf(code)) {
      let ensured: EnsureSourcePdfResponse;
      try {
        ensured = await ensureSourcePdf(initial);
      } catch (cause) {
        if (!isOperationActive(loadToken)) {
          return;
        }
        if (cause instanceof MutationWritesBlockedError) {
          pendingEnsureSourceRetry.value = true;
          loadError.value = blockedMessage.value;
          return;
        }
        throw cause;
      }
      pendingEnsureSourceRetry.value = false;
      if (!isOperationActive(loadToken)) {
        return;
      }
      authoritative = toAuthoritativeState(ensured);
      const authoritativeDescriptor = findActionDescriptor(authoritative, code);
      if (!isSignatureRequiredDescriptor(authoritativeDescriptor)) {
        if (!authoritativeDescriptor?.enabled) {
          loadError.value = t("signature.workspace.errors.actionDisabled");
          return;
        }
        loadError.value = t("signature.workspace.errors.signatureNotRequired");
        return;
      }
      if (!isActionEnabled(authoritative, "preview")) {
        loadError.value = t("signature.workspace.errors.previewUnavailable");
        return;
      }
      previewArtifactId = ensured.artifact_id ?? null;
    } else {
      authoritative = initial;
      if (!isActionEnabled(authoritative, "preview")) {
        loadError.value = t("signature.workspace.errors.previewUnavailable");
        return;
      }
      const artifactRows = await fetchDocumentArtifacts(documentId.value, version);
      if (!isOperationActive(loadToken)) {
        return;
      }
      const signedArtifact = resolveSignedPdfArtifact(artifactRows);
      if (!signedArtifact) {
        loadError.value = t("signature.workspace.errors.noSourcePdf");
        return;
      }
      previewArtifactId = signedArtifact.artifact_id;
    }

    detail.value = authoritative;
    sourceArtifactId.value = previewArtifactId;
    if (!sourceArtifactId.value) {
      loadError.value = t("signature.workspace.errors.noSourcePdf");
      return;
    }

    const assetToken = beginOperation("assetLoad");
    await Promise.all([
      loadSourcePreview(sourceArtifactId.value, loadToken),
      loadActiveSignatureAsset(assetToken),
      loadTemplates(authoritative, loadToken),
    ]);

    if (!isOperationActive(loadToken)) {
      return;
    }

    const artifactToken = beginOperation("artifactRefresh");
    await refreshArtifacts(artifactToken);
    if (!isOperationActive(loadToken)) {
      return;
    }
    workspaceReady.value = true;
  } catch (cause) {
    if (!isOperationActive(loadToken)) {
      return;
    }
    if (
      cause instanceof MutationClientError &&
      (cause.kind === "conflict" || cause.kind === "precondition_required")
    ) {
      openConflictWithDraft(cause, {
        actionCode: actionCode.value ?? undefined,
        actionLabel: t("signature.workspace.title"),
      });
      return;
    }
    loadError.value = mapLoadError(cause);
  } finally {
    if (isOperationActive(loadToken)) {
      loading.value = false;
    }
  }
}

watch(
  () => [documentId.value, versionParse.value.valid, versionParse.value.valid ? versionParse.value.version : null, actionCode.value] as const,
  () => {
    pendingEnsureSourceRetry.value = false;
    ensureSourceRetryUsed.value = false;
    clearConflictForRouteChange();
    invalidateWorkspaceOperations();
    void initializeWorkspace();
  },
  { immediate: true },
);

watch(writesAllowed, (allowed, wasAllowed) => {
  if (
    allowed &&
    wasAllowed === false &&
    pendingEnsureSourceRetry.value &&
    !ensureSourceRetryUsed.value &&
    routeValid.value &&
    versionParse.value.valid &&
    actionCode.value
  ) {
    ensureSourceRetryUsed.value = true;
    pendingEnsureSourceRetry.value = false;
    void initializeWorkspace();
  }
});

watch(
  () => layout.value.show_date,
  (showDate) => {
    if (!showDate) {
      layout.value.show_time = false;
    }
  },
);

function effectiveLayoutPayload(): Record<string, unknown> {
  return {
    ...layout.value,
    show_time: layout.value.show_date ? layout.value.show_time : false,
  };
}

function openReauth(): void {
  if (missingSignatureAsset.value || mutating.value || !writesAllowed.value) {
    return;
  }
  reauthError.value = null;
  reauthOpen.value = true;
}

function onReauthCancel(): void {
  reauthOpen.value = false;
  reauthError.value = null;
}

async function savePersonalTemplate(): Promise<void> {
  const state = detail.value;
  const code = actionCode.value;
  const role = state && code ? assignmentKindForAction(state, code) : null;
  if (!state || !role || mutating.value || !writesAllowed.value) {
    return;
  }
  const token = beginOperation("templateSave");
  mutating.value = true;
  alertMessage.value = null;
  try {
    await mutate({
      method: "POST",
      path: "/signature/templates/user",
      body: {
        json: {
          name: t("signature.workspace.defaultTemplateName"),
          document_type: state.state.doc_type,
          role_context: role,
          scope: "user",
          placement: placement.value,
          layout: effectiveLayoutPayload(),
        },
      },
    });
    if (!isOperationActive(token)) {
      return;
    }
    userTemplates.value = await fetchSignatureTemplatesUser();
    if (!isOperationActive(token)) {
      return;
    }
    alertMessage.value = t("signature.workspace.templateSaved");
  } catch (cause) {
    if (!isOperationActive(token)) {
      return;
    }
    if (
      cause instanceof MutationClientError &&
      (cause.kind === "conflict" || cause.kind === "precondition_required")
    ) {
      openConflictWithDraft(cause, { actionLabel: t("signature.workspace.saveTemplate") });
      return;
    }
    alertMessage.value = mapLoadError(cause);
  } finally {
    if (isOperationActive(token)) {
      mutating.value = false;
    }
  }
}

async function submitSignature(password: string): Promise<void> {
  const trimmedPassword = password.trim();
  if (!trimmedPassword) {
    return;
  }
  const state = detail.value;
  const code = actionCode.value;
  if (
    !state ||
    !code ||
    reauthLoading.value ||
    mutating.value ||
    missingSignatureAsset.value ||
    !writesAllowed.value
  ) {
    return;
  }

  const token = beginOperation("sign");
  reauthLoading.value = true;
  reauthError.value = null;
  mutating.value = true;

  const body: MutationBody = {
    json: {
      sign_intent: {
        placement: placement.value,
        layout: effectiveLayoutPayload(),
        password: trimmedPassword,
        reason: workflowReason.value,
        template_id: selectedTemplateId.value,
      },
    },
  };

  try {
    const response = await mutate<VersionStateResponse>({
      method: "POST",
      path: workflowPath(code),
      ifMatch: state.etag,
      body,
    });
    if (!isOperationActive(token)) {
      return;
    }
    if (response) {
      detail.value = response;
      signedSuccess.value = true;
      artifactsUnknown.value = true;
      artifacts.value = [];
      artifactRefreshError.value = null;
      reauthOpen.value = false;
      reauthError.value = null;
      alertMessage.value = t("signature.workspace.success");
      const refreshToken = beginOperation("artifactRefresh");
      try {
        await refreshArtifacts(refreshToken);
      } catch (cause) {
        if (!isOperationActive(token)) {
          return;
        }
        artifactsUnknown.value = true;
        artifactRefreshError.value = mapLoadError(cause);
      }
    }
  } catch (cause) {
    if (!isOperationActive(token)) {
      return;
    }
    if (
      cause instanceof MutationClientError &&
      (cause.kind === "conflict" || cause.kind === "precondition_required")
    ) {
      reauthOpen.value = false;
      openConflictWithDraft(cause, {
        actionCode: code,
        actionLabel: t("signature.workspace.title"),
        reason: workflowReason.value ?? undefined,
      });
      return;
    }
    reauthError.value =
      cause instanceof MutationClientError && cause.kind === "forbidden"
        ? t("signature.reauth.invalidPassword")
        : mapLoadError(cause);
  } finally {
    if (isOperationActive(token)) {
      reauthLoading.value = false;
      mutating.value = false;
    }
  }
}

async function retryArtifactRefresh(): Promise<void> {
  const token = beginOperation("artifactRefresh");
  artifactRefreshError.value = null;
  artifactsUnknown.value = true;
  try {
    await refreshArtifacts(token);
  } catch (cause) {
    if (!isOperationActive(token)) {
      return;
    }
    artifactsUnknown.value = true;
    artifactRefreshError.value = mapLoadError(cause);
  }
}

async function onConflictLoadServerState(): Promise<void> {
  if (conflictReloadInProgress.value || conflictLoading.value) {
    return;
  }
  conflictReloadInProgress.value = true;
  reloadFailed.value = false;
  try {
    await initializeWorkspace();
    if (!workspaceReady.value || !detail.value?.state) {
      reloadFailed.value = true;
      return;
    }
    conflictDraftSnapshot.value = null;
    cancelConflict();
  } finally {
    conflictReloadInProgress.value = false;
  }
}

function goBack(): void {
  void router.push({
    name: "document-detail",
    params: { docId: documentId.value },
    query: {
      version: versionParse.value.valid ? String(versionParse.value.version) : "",
    },
  });
}

function templateScopeLabel(scope: string): string {
  return scope === "global"
    ? t("signature.workspace.scopeOrganization")
    : t("signature.workspace.scopePersonal");
}

function onTemplateSelected(id: string | null): void {
  selectedTemplateId.value = id;
  const match = templatePickerOptions.value.find((row) => row.template_id === id);
  if (match) {
    applyTemplatePreview(match, true);
  }
}

function retrySignatureAsset(): void {
  const token = beginOperation("assetLoad");
  void loadActiveSignatureAsset(token);
}

onUnmounted(() => {
  invalidateWorkspaceOperations();
  revokeSourceUrl();
  revokeSignatureUrl();
});
</script>

<template>
  <section class="signature-workspace" data-testid="signature-workspace">
    <header class="signature-workspace__header">
      <h2>{{ t("signature.workspace.title") }}</h2>
      <v-btn variant="text" data-testid="signature-back" @click="goBack">
        {{ t("signature.workspace.backToDetail") }}
      </v-btn>
    </header>

    <p v-if="loading" role="status">{{ t("signature.workspace.loading") }}</p>
    <p v-else-if="loadError" role="alert" data-testid="signature-load-error">{{ loadError }}</p>

    <div
      v-else-if="workspaceReady && !signedSuccess"
      class="signature-workspace__grid"
      data-testid="signature-workspace-grid"
    >
      <aside class="signature-workspace__sidebar" data-testid="signature-workspace-sidebar">
        <p v-if="alertMessage" role="status">{{ alertMessage }}</p>

        <p
          v-if="!writesAllowed"
          role="status"
          data-testid="signature-writes-blocked"
        >
          {{ blockedMessage }}
        </p>

        <div class="signature-workspace__layout-controls" data-testid="signature-layout-controls">
          <v-switch v-model="layout.show_signature" :label="t('signature.workspace.showSignature')" hide-details />
          <v-switch v-model="layout.show_name" :label="t('signature.workspace.showName')" hide-details />
          <v-switch v-model="layout.show_date" :label="t('signature.workspace.showDate')" hide-details />
          <v-switch
            v-model="layout.show_time"
            :label="t('signature.workspace.showTime')"
            :disabled="!layout.show_date"
            hide-details
          />
        </div>

        <div v-if="suggestion" class="signature-workspace__suggestion" data-testid="signature-suggestion">
          {{ t("signature.workspace.suggestionAvailable", { name: suggestion.name }) }}
        </div>

        <p
          v-if="signatureAssetError"
          role="alert"
          data-testid="signature-asset-error"
        >
          {{ signatureAssetError }}
          <v-btn
            size="small"
            variant="text"
            data-testid="signature-asset-retry"
            @click="retrySignatureAsset"
          >
            {{ t("signature.workspace.retryAsset") }}
          </v-btn>
        </p>

        <p
          v-if="signatureAssetMismatch"
          role="status"
          data-testid="signature-asset-mismatch"
        >
          {{ t("signature.workspace.templateAssetMismatch") }}
        </p>

        <p
          v-if="missingSignatureAsset"
          role="alert"
          data-testid="signature-missing-asset"
        >
          {{ t("signature.workspace.missingAsset") }}
        </p>

        <div class="signature-workspace__templates">
          <h3>{{ t("signature.workspace.templatesTitle") }}</h3>
          <v-select
            :model-value="selectedTemplateId"
            :items="templatePickerOptions"
            item-title="name"
            item-value="template_id"
            :label="t('signature.workspace.templatePicker')"
            clearable
            data-testid="signature-template-picker"
            @update:model-value="onTemplateSelected"
          >
            <template #item="{ props: itemProps, item }">
              <v-list-item v-bind="itemProps" :subtitle="templateScopeLabel(item.raw.scope)" />
            </template>
          </v-select>
          <v-btn
            variant="outlined"
            :disabled="mutating || !writesAllowed"
            data-testid="save-personal-template"
            @click="savePersonalTemplate"
          >
            {{ t("signature.workspace.saveTemplate") }}
          </v-btn>
        </div>

        <v-btn
          color="primary"
          :disabled="mutating || missingSignatureAsset || !writesAllowed"
          data-testid="signature-sign-button"
          @click="openReauth"
        >
          {{ t("signature.workspace.signAction") }}
        </v-btn>
      </aside>

      <div class="signature-workspace__canvas-region" data-testid="signature-workspace-canvas-region">
        <SignaturePlacementCanvas
          :pdf-url="sourcePdfUrl"
          :placement="placement"
          :signature-image-url="signaturePreviewUrl"
          :loading="loading"
          :error="Boolean(loadError)"
          @update:placement="(next) => { placement = next; }"
        />
      </div>
    </div>

    <ReleasedArtifactPanel
      v-if="signedSuccess"
      :detail="detail"
      :artifacts="artifacts"
      :signed-success="signedSuccess"
      :artifacts-unknown="artifactsUnknown"
      :artifact-refresh-error="artifactRefreshError"
      data-testid="signature-result-panel"
      @retry-artifacts="retryArtifactRefresh"
    />

    <ReauthDialog
      v-model="reauthOpen"
      :loading="reauthLoading"
      :error-message="reauthError"
      :product-writes-allowed="writesAllowed"
      @submit="submitSignature"
      @cancel="onReauthCancel"
    />

    <ConflictDialog
      v-if="conflictVisible"
      v-model="conflictVisible"
      :loading="conflictLoading || conflictReloadInProgress"
      :reload-failed="reloadFailed"
      :showing-local-input="showingLocalInput"
      :action-label="preservedContext?.actionLabel ?? null"
      :preserved-reason="preservedContext?.reason ?? null"
      @load-server-state="onConflictLoadServerState"
      @view-local-input="onViewLocalDraft"
      @cancel="cancelConflict"
    >
      <template v-if="conflictDraftSnapshot" #local-input-details>
        <div class="signature-workspace__draft-preview" data-testid="signature-draft-preview">
          <h4>{{ t("signature.workspace.draftPreviewTitle") }}</h4>
          <p>
            {{
              t("signature.workspace.draftPreviewPlacement", {
                page: conflictDraftSnapshot.placement.page_index + 1,
              })
            }}
          </p>
          <p v-if="conflictDraftSnapshot.selectedTemplateId">
            {{
              t("signature.workspace.draftPreviewTemplate", {
                id: conflictDraftSnapshot.selectedTemplateId,
              })
            }}
          </p>
          <p data-testid="signature-draft-layout">
            <template v-if="conflictDraftSnapshot.layout.show_signature">
              {{ t("signature.workspace.showSignature") }}
            </template>
            <template v-if="conflictDraftSnapshot.layout.show_name">
              · {{ t("signature.workspace.showName") }}
            </template>
            <template v-if="conflictDraftSnapshot.layout.show_date">
              · {{ t("signature.workspace.showDate") }}
            </template>
            <template v-if="conflictDraftSnapshot.layout.show_time">
              · {{ t("signature.workspace.showTime") }}
            </template>
          </p>
        </div>
      </template>
    </ConflictDialog>
  </section>
</template>

<style scoped>
.signature-workspace {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.signature-workspace__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.signature-workspace__grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

.signature-workspace__sidebar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.signature-workspace__canvas-region {
  min-width: 0;
}

.signature-workspace__layout-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
}

.signature-workspace__templates {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.signature-workspace__draft-preview {
  margin-top: 0.75rem;
}

.signature-workspace__draft-preview h4 {
  margin: 0 0 0.5rem;
}

@media (max-width: 960px) {
  .signature-workspace__grid {
    grid-template-columns: 1fr;
  }
}
</style>
