<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { ApiTransportError, type VersionStateResponse } from "../../api/client";
import { mutationErrorI18nKey } from "../../api/errors";
import { MutationClientError } from "../../api/mutationClient";
import AssignmentsPanel from "../../components/documents/AssignmentsPanel.vue";
import DocumentHeader from "../../components/documents/DocumentHeader.vue";
import DocumentMetadataPanel from "../../components/documents/DocumentMetadataPanel.vue";
import { useDocumentDetail } from "../../composables/useDocumentDetail";

defineOptions({
  name: "DocumentDetailView",
});

const { t } = useI18n();
const router = useRouter();
const {
  documentId,
  version,
  versionError,
  detail,
  directory,
  loading,
  directoryLoading,
  directoryError,
  error,
  reload,
} = useDocumentDetail();

const state = computed(() => detail.value?.state ?? null);

function mapLoadError(cause: ApiTransportError | Error | null): string {
  if (!cause) {
    return t("documents.detail.errors.connection");
  }
  if (cause instanceof MutationClientError) {
    return t(mutationErrorI18nKey(cause.kind));
  }
  if (cause instanceof ApiTransportError) {
    switch (cause.status) {
      case 401:
        return t("api.errors.unauthorized");
      case 403:
        return t("api.errors.forbidden");
      case 404:
        return t("api.errors.notFound");
      case 409:
        return t("documents.detail.errors.conflictDeferred");
      case 413:
        return t("documents.detail.errors.payloadTooLarge");
      case 422:
        return t("documents.detail.errors.validation");
      case 428:
        return t("documents.detail.errors.preconditionDeferred");
      case 501:
        return t("documents.detail.errors.notImplemented");
      case 503:
        return t("documents.detail.errors.serviceUnavailable");
      default:
        return t("api.errors.transport");
    }
  }
  return t("documents.detail.errors.connection");
}

function backToPool(): void {
  void router.push({ name: "documents" });
}

function onAssignmentsUpdated(payload: VersionStateResponse): void {
  detail.value = payload;
}
</script>

<template>
  <section class="document-detail-view" data-testid="document-detail-view">
    <nav aria-label="breadcrumb">
      <v-btn variant="text" data-testid="document-detail-back" @click="backToPool">
        {{ t("documents.detail.backToPool") }}
      </v-btn>
    </nav>

    <p v-if="versionError" role="alert" data-testid="document-detail-version-error">
      {{ versionError === "missing"
        ? t("documents.detail.invalidVersionMissing")
        : t("documents.detail.invalidVersion") }}
    </p>

    <p v-else-if="loading" data-testid="document-detail-loading">
      {{ t("documents.detail.loading") }}
    </p>

    <div v-else-if="error" role="alert" data-testid="document-detail-error">
      <p>{{ mapLoadError(error) }}</p>
      <v-btn variant="outlined" data-testid="document-detail-retry" @click="reload">
        {{ t("documents.pool.retry") }}
      </v-btn>
    </div>

    <template v-else-if="detail && state">
      <DocumentHeader :state="state" />
      <DocumentMetadataPanel :state="state" :directory="directory" />
      <AssignmentsPanel
        :detail="detail"
        :directory="directory"
        :directory-loading="directoryLoading"
        :directory-error="directoryError"
        :document-id="documentId"
        :version="version"
        @updated="onAssignmentsUpdated"
      />
    </template>
  </section>
</template>

<style scoped>
.document-detail-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
