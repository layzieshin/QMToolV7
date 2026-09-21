<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { ApiTransportError, type CreateVersionBody, type VersionStateResponse } from "../../api/client";
import { MutationClientError, MutationWritesBlockedError, mutate } from "../../api/mutationClient";
import { mutationErrorI18nKey } from "../../api/errors";
import { useProductWriteAvailability } from "../../composables/useProductWriteAvailability";

defineOptions({
  name: "DocumentImportView",
});

const PDF_MIME = "application/pdf";
const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** OpenAPI CreateVersionBody requires these fields; values match schema @default. */
const CREATE_SCHEMA_DEFAULTS: Pick<CreateVersionBody, "doc_type" | "control_class"> = {
  doc_type: "OTHER",
  control_class: "CONTROLLED",
};

type UploadRetryRecord = {
  created: VersionStateResponse;
  file: File;
};

const { t } = useI18n();
const router = useRouter();
const { writesAllowed, blockedMessage } = useProductWriteAvailability();

const documentId = ref("");
const version = ref("1");
const title = ref("");
const submitting = ref(false);
const alertMessage = ref<string | null>(null);
const alertLive = ref<"polite" | "assertive">("polite");
const selectedFile = ref<File | null>(null);
const uploadRetry = ref<UploadRetryRecord | null>(null);

const awaitingUploadRetry = computed(() => uploadRetry.value !== null);

function resetAlert(): void {
  alertMessage.value = null;
  alertLive.value = "polite";
}

function mapError(error: unknown): string {
  if (error instanceof MutationWritesBlockedError) {
    return blockedMessage.value;
  }
  if (error instanceof MutationClientError) {
    if (error.fieldErrors.length > 0) {
      return t("documents.detail.errors.validation");
    }
    switch (error.status) {
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
        return t(mutationErrorI18nKey(error.kind));
    }
  }
  if (error instanceof ApiTransportError) {
    switch (error.status) {
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

function parseVersionInput(): number | null {
  const text = version.value.trim();
  if (!/^\d+$/.test(text)) {
    return null;
  }
  const parsed = Number.parseInt(text, 10);
  return Number.isInteger(parsed) && parsed >= 1 ? parsed : null;
}

function resolveImportTarget(file: File): { path: string; contentType: string } | null {
  const lower = file.name.toLowerCase();
  const mime = file.type;
  const isPdfExt = lower.endsWith(".pdf");
  const isDocxExt = lower.endsWith(".docx");

  if (isPdfExt) {
    if (mime && mime !== PDF_MIME) {
      return null;
    }
    return { path: "import-pdf", contentType: PDF_MIME };
  }
  if (isDocxExt) {
    if (mime && mime !== DOCX_MIME) {
      return null;
    }
    return { path: "import-docx", contentType: DOCX_MIME };
  }
  if (mime === PDF_MIME || mime === DOCX_MIME) {
    return null;
  }
  return null;
}

async function createVersion(parsedVersion: number): Promise<VersionStateResponse> {
  const trimmedId = documentId.value.trim();
  const response = await mutate<VersionStateResponse>({
    method: "POST",
    path: "/documents/versions/create",
    body: {
      json: {
        document_id: trimmedId,
        version: parsedVersion,
        title: title.value.trim(),
        ...CREATE_SCHEMA_DEFAULTS,
      },
    },
  });
  if (!response) {
    throw new Error("create returned empty response");
  }
  return response;
}

async function uploadFile(
  created: VersionStateResponse,
  file: File,
): Promise<VersionStateResponse> {
  const target = resolveImportTarget(file);
  if (!target) {
    throw new MutationClientError("unsupported format", "transport", 400);
  }
  const response = await mutate<VersionStateResponse>({
    method: "POST",
    path: `/documents/versions/${encodeURIComponent(created.state.document_id)}/${created.state.version}/${target.path}`,
    ifMatch: created.etag,
    body: {
      raw: file,
      contentType: target.contentType,
    },
  });
  if (!response) {
    throw new Error("import returned empty response");
  }
  return response;
}

function onFileChange(event: Event): void {
  if (awaitingUploadRetry.value) {
    return;
  }
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  resetAlert();
}

async function submitImport(): Promise<void> {
  if (submitting.value || !writesAllowed.value) {
    return;
  }
  resetAlert();

  if (uploadRetry.value) {
    submitting.value = true;
    try {
      const imported = await uploadFile(uploadRetry.value.created, uploadRetry.value.file);
      uploadRetry.value = null;
      await router.push({
        name: "document-detail",
        params: { docId: imported.state.document_id },
        query: { version: String(imported.state.version) },
      });
    } catch (error) {
      alertMessage.value = mapError(error);
      alertLive.value = "assertive";
    } finally {
      submitting.value = false;
    }
    return;
  }

  const parsedVersion = parseVersionInput();
  if (!documentId.value.trim() || parsedVersion === null) {
    alertMessage.value = t("documents.import.validation");
    alertLive.value = "assertive";
    return;
  }
  if (!selectedFile.value) {
    alertMessage.value = t("documents.import.fileRequired");
    alertLive.value = "assertive";
    return;
  }
  if (!resolveImportTarget(selectedFile.value)) {
    alertMessage.value = t("documents.import.unsupportedFormat");
    alertLive.value = "assertive";
    return;
  }

  const fileForUpload = selectedFile.value;
  submitting.value = true;
  try {
    const created = await createVersion(parsedVersion);
    uploadRetry.value = { created, file: fileForUpload };
    const imported = await uploadFile(created, fileForUpload);
    uploadRetry.value = null;
    await router.push({
      name: "document-detail",
      params: { docId: imported.state.document_id },
      query: { version: String(imported.state.version) },
    });
  } catch (error) {
    alertMessage.value = mapError(error);
    alertLive.value = "assertive";
  } finally {
    submitting.value = false;
  }
}

function backToPool(): void {
  void router.push({ name: "documents" });
}
</script>

<template>
  <section class="document-import-view" data-testid="document-import-view">
    <nav aria-label="breadcrumb">
      <v-btn variant="text" data-testid="document-import-back" @click="backToPool">
        {{ t("documents.detail.backToPool") }}
      </v-btn>
    </nav>

    <h2>{{ t("documents.import.title") }}</h2>
    <p>{{ awaitingUploadRetry ? t("documents.import.retryHint") : t("documents.import.hint") }}</p>

    <p
      v-if="!writesAllowed"
      role="status"
      data-testid="document-import-writes-blocked"
    >
      {{ blockedMessage }}
    </p>

    <form data-testid="document-import-form" @submit.prevent="submitImport">
      <v-text-field
        v-model="documentId"
        :label="t('documents.import.documentId')"
        data-testid="document-import-document-id"
        :disabled="awaitingUploadRetry || !writesAllowed"
        required
      />
      <v-text-field
        v-model="version"
        :label="t('documents.import.version')"
        inputmode="numeric"
        data-testid="document-import-version"
        :disabled="awaitingUploadRetry || !writesAllowed"
        required
      />
      <v-text-field
        v-model="title"
        :label="t('documents.import.titleField')"
        data-testid="document-import-title"
        :disabled="awaitingUploadRetry || !writesAllowed"
      />
      <label for="document-import-file">{{ t("documents.import.file") }}</label>
      <input
        id="document-import-file"
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        data-testid="document-import-file"
        :disabled="awaitingUploadRetry || !writesAllowed"
        @change="onFileChange"
      />
      <v-btn
        type="submit"
        color="primary"
        class="submit-btn"
        :loading="submitting"
        :disabled="submitting || !writesAllowed"
        data-testid="document-import-submit"
      >
        {{ awaitingUploadRetry ? t("documents.import.retryUpload") : t("documents.import.submit") }}
      </v-btn>
    </form>

    <p
      v-if="alertMessage"
      role="alert"
      :aria-live="alertLive"
      data-testid="document-import-alert"
    >
      {{ alertMessage }}
    </p>
  </section>
</template>

<style scoped>
.document-import-view h2 {
  margin-top: 0;
}

form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 32rem;
}

.submit-btn {
  align-self: flex-start;
}
</style>
