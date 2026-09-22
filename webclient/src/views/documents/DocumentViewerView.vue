<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import {
  ApiTransportError,
  fetchDocumentArtifacts,
  fetchDocumentVersion,
  type DocumentArtifactModel,
  type VersionStateResponse,
} from "../../api/client";
import { mutationErrorI18nKey } from "../../api/errors";
import { MutationClientError } from "../../api/mutationClient";
import ConflictDialog from "../../components/conflict/ConflictDialog.vue";
import CommentsPanel from "../../components/documents/CommentsPanel.vue";
import PdfViewer from "../../components/documents/PdfViewer.vue";
import { parseDetailRouteVersion } from "../../composables/useDocumentDetail";
import { useConflictRecovery } from "../../composables/useConflictRecovery";
import { INVALID_PREVIEW_MIME, usePdfPreview } from "../../composables/usePdfPreview";

defineOptions({
  name: "DocumentViewerView",
});

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const requestGeneration = { current: 0 };
const detail = shallowRef<VersionStateResponse | null>(null);
const artifacts = shallowRef<DocumentArtifactModel[]>([]);
const loading = ref(false);
const error = ref<ApiTransportError | Error | null>(null);
const artifactsError = ref<ApiTransportError | Error | null>(null);
const selectedArtifactId = ref<string | null>(null);
const currentPage = ref(1);
const commentsPanelRef = ref<InstanceType<typeof CommentsPanel> | null>(null);

const documentId = computed(() => String(route.params.docId ?? "").trim());
const versionParse = computed(() => parseDetailRouteVersion(route.query.version));
const version = computed(() => (versionParse.value.valid ? versionParse.value.version : null));
const versionError = computed(() =>
  versionParse.value.valid ? null : versionParse.value.reason,
);

const routeLoadable = computed(
  () => Boolean(documentId.value) && versionParse.value.valid,
);

const pdfArtifacts = computed(() =>
  artifacts.value.filter(
    (artifact) =>
      artifact.mime_type === "application/pdf" && artifact.is_current === true,
  ),
);

const queryArtifactId = computed(() => {
  const raw = route.query.artifact;
  if (typeof raw !== "string" || Array.isArray(raw)) {
    return null;
  }
  const trimmed = raw.trim();
  return trimmed || null;
});

const previewEnabled = computed(() =>
  (detail.value?.allowed_actions ?? []).some(
    (action) => action.code === "preview" && action.enabled,
  ),
);

const effectiveArtifactId = computed(() => {
  const fromSelection = selectedArtifactId.value;
  if (fromSelection && pdfArtifacts.value.some((a) => a.artifact_id === fromSelection)) {
    return fromSelection;
  }
  const fromQuery = queryArtifactId.value;
  if (fromQuery && pdfArtifacts.value.some((a) => a.artifact_id === fromQuery)) {
    return fromQuery;
  }
  if (pdfArtifacts.value.length === 1) {
    return pdfArtifacts.value[0].artifact_id;
  }
  return null;
});

const previewArtifactIdRef = computed(() =>
  previewEnabled.value ? effectiveArtifactId.value : null,
);

const canCreatePdfComment = computed(
  () => previewEnabled.value && Boolean(effectiveArtifactId.value),
);
const { previewUrl, loading: previewLoading, error: previewError, reload: reloadPreview } =
  usePdfPreview(previewArtifactIdRef);

function mapLoadError(cause: ApiTransportError | Error | null): string {
  if (!cause) {
    return t("documents.viewer.errors.connection");
  }
  if (cause instanceof Error && cause.message === INVALID_PREVIEW_MIME) {
    return t("documents.viewer.pdf.invalidMime");
  }
  if (cause instanceof MutationClientError) {
    return t(mutationErrorI18nKey(cause.kind));
  }
  if (cause instanceof ApiTransportError) {
    switch (cause.status) {
      case 401:
        return t("api.errors.unauthorized");
      case 403:
        return t("documents.viewer.errors.forbidden");
      case 404:
        return t("api.errors.notFound");
      default:
        return t("api.errors.transport");
    }
  }
  return t("documents.viewer.errors.connection");
}

function resetInvalidRouteState(): void {
  detail.value = null;
  artifacts.value = [];
  error.value = null;
  artifactsError.value = null;
  loading.value = false;
  selectedArtifactId.value = null;
}

async function loadViewerData(generation: number): Promise<void> {
  if (!routeLoadable.value || !version.value) {
    resetInvalidRouteState();
    return;
  }

  loading.value = true;
  error.value = null;
  artifactsError.value = null;
  detail.value = null;
  artifacts.value = [];
  selectedArtifactId.value = null;

  const docId = documentId.value;
  const ver = version.value;

  try {
    const [detailResponse, artifactRows] = await Promise.all([
      fetchDocumentVersion(docId, ver),
      fetchDocumentArtifacts(docId, ver),
    ]);
    if (generation !== requestGeneration.current) {
      return;
    }
    detail.value = detailResponse;
    artifacts.value = artifactRows;
    error.value = null;
    artifactsError.value = null;

    const pdfs = artifactRows.filter(
      (artifact) =>
        artifact.mime_type === "application/pdf" && artifact.is_current === true,
    );
    const queryId = queryArtifactId.value;
    if (queryId && pdfs.some((a) => a.artifact_id === queryId)) {
      selectedArtifactId.value = queryId;
    } else if (pdfs.length === 1) {
      selectedArtifactId.value = pdfs[0].artifact_id;
    }
  } catch (cause) {
    if (generation !== requestGeneration.current) {
      return;
    }
    detail.value = null;
    artifacts.value = [];
    if (cause instanceof ApiTransportError && cause.status === 403) {
      error.value = cause;
    } else {
      error.value = cause instanceof Error ? cause : new Error(String(cause));
    }
  } finally {
    if (generation === requestGeneration.current) {
      loading.value = false;
    }
  }
}

async function reloadViewerState(): Promise<void> {
  const generation = ++requestGeneration.current;
  await loadViewerData(generation);
}

const {
  conflictVisible,
  conflictLoading,
  reloadFailed,
  showingLocalInput,
  preservedContext,
  openConflict,
  loadServerState,
  viewLocalInput,
  cancelConflict,
} = useConflictRecovery({
  detail,
  reload: reloadViewerState,
});

function onArtifactSelected(event: Event): void {
  const value = (event.target as HTMLSelectElement).value;
  selectedArtifactId.value = value || null;
}

function onPageChange(page: number): void {
  currentPage.value = page;
}

function onDetailUpdated(payload: VersionStateResponse): void {
  detail.value = payload;
}

function onCommentConflict(
  mutationError: MutationClientError,
  context: { actionLabel?: string; reason?: string },
): void {
  openConflict(mutationError, context);
}

async function onConflictLoadServerState(): Promise<void> {
  await loadServerState();
}

function backToDetail(): void {
  if (!version.value) {
    void router.push({ name: "documents" });
    return;
  }
  void router.push({
    name: "document-detail",
    params: { docId: documentId.value },
    query: { version: String(version.value) },
  });
}

watch(
  () => [documentId.value, route.query.version, route.query.artifact] as const,
  () => {
    const generation = ++requestGeneration.current;
    void loadViewerData(generation);
  },
  { immediate: true },
);

onUnmounted(() => {
  requestGeneration.current += 1;
  loading.value = false;
});
</script>

<template>
  <section class="document-viewer-view" data-testid="document-viewer-view">
    <nav aria-label="breadcrumb">
      <v-btn variant="text" data-testid="document-viewer-back" @click="backToDetail">
        {{ t("documents.viewer.backToDetail") }}
      </v-btn>
    </nav>

    <p v-if="versionError" role="alert" data-testid="document-viewer-version-error">
      {{ versionError === "missing"
        ? t("documents.detail.invalidVersionMissing")
        : t("documents.detail.invalidVersion") }}
    </p>

    <p v-else-if="!routeLoadable" role="alert" data-testid="document-viewer-route-invalid">
      {{ t("documents.viewer.errors.invalidRoute") }}
    </p>

    <p v-else-if="loading" data-testid="document-viewer-loading">
      {{ t("documents.viewer.loading") }}
    </p>

    <div v-else-if="error" role="alert" data-testid="document-viewer-error">
      <p>{{ mapLoadError(error) }}</p>
      <v-btn variant="outlined" data-testid="document-viewer-retry" @click="reloadViewerState">
        {{ t("documents.pool.retry") }}
      </v-btn>
    </div>

    <template v-else-if="detail">
      <header class="document-viewer-view__header">
        <h1 data-testid="document-viewer-title">
          {{ detail.state.title || documentId }}
        </h1>
        <p class="document-viewer-view__meta" data-testid="document-viewer-meta">
          {{ t("documents.viewer.versionLabel", { version }) }}
        </p>
      </header>

      <div class="document-viewer-view__layout">
        <div class="document-viewer-view__pdf-column">
          <div
            v-if="!previewEnabled"
            role="status"
            data-testid="document-viewer-preview-unavailable"
          >
            {{ t("documents.viewer.previewUnavailable") }}
          </div>

          <div
            v-else-if="pdfArtifacts.length === 0"
            data-testid="document-viewer-no-pdf"
          >
            {{ t("documents.viewer.noPdfArtifacts") }}
          </div>

          <template v-else>
            <div
              v-if="pdfArtifacts.length > 1"
              class="document-viewer-view__artifact-select"
            >
              <label for="artifact-select">{{ t("documents.viewer.selectArtifact") }}</label>
              <select
                id="artifact-select"
                data-testid="artifact-select"
                :value="effectiveArtifactId ?? ''"
                @change="onArtifactSelected"
              >
                <option value="" disabled>
                  {{ t("documents.viewer.selectArtifactPlaceholder") }}
                </option>
                <option
                  v-for="artifact in pdfArtifacts"
                  :key="artifact.artifact_id"
                  :value="artifact.artifact_id"
                >
                  {{ artifact.original_filename }}
                </option>
              </select>
            </div>

            <p
              v-if="pdfArtifacts.length > 1 && !effectiveArtifactId"
              data-testid="document-viewer-select-prompt"
            >
              {{ t("documents.viewer.selectArtifactPrompt") }}
            </p>

            <PdfViewer
              :preview-url="previewUrl"
              :loading="previewLoading"
              :error="Boolean(previewError)"
              @page-change="onPageChange"
            />

            <div v-if="previewError" role="alert" data-testid="document-viewer-preview-error">
              <p>{{ mapLoadError(previewError) }}</p>
              <v-btn variant="outlined" size="small" data-testid="document-viewer-preview-retry" @click="reloadPreview">
                {{ t("documents.pool.retry") }}
              </v-btn>
            </div>
          </template>
        </div>

        <div class="document-viewer-view__comments-column">
          <CommentsPanel
            ref="commentsPanelRef"
            :document-id="documentId"
            :version="version ?? 1"
            :detail="detail"
            :current-page="currentPage"
            :has-pdf="canCreatePdfComment"
            @detail-updated="onDetailUpdated"
            @conflict="onCommentConflict"
          />
        </div>
      </div>
    </template>

    <ConflictDialog
      v-if="conflictVisible"
      v-model="conflictVisible"
      :loading="conflictLoading"
      :reload-failed="reloadFailed"
      :showing-local-input="showingLocalInput"
      :action-label="preservedContext?.actionLabel ?? null"
      :preserved-reason="preservedContext?.reason ?? null"
      @load-server-state="onConflictLoadServerState"
      @view-local-input="viewLocalInput"
      @cancel="cancelConflict"
    />
  </section>
</template>

<style scoped>
.document-viewer-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.document-viewer-view__header h1 {
  margin: 0;
}

.document-viewer-view__meta {
  margin: 0.25rem 0 0;
  color: rgba(0, 0, 0, 0.6);
}

.document-viewer-view__layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.5rem;
}

.document-viewer-view__artifact-select {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
}

@media (max-width: 960px) {
  .document-viewer-view__layout {
    grid-template-columns: 1fr;
  }
}
</style>
