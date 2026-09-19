import { onUnmounted, ref, shallowRef, watch, type Ref } from "vue";

import {
  ApiTransportError,
  fetchArtifactPreviewBlob,
  pdfPreviewMimeType,
} from "../api/client";

export type PdfPreviewState = {
  previewUrl: Ref<string | null>;
  loading: Ref<boolean>;
  error: Ref<ApiTransportError | Error | null>;
  reload: () => Promise<void>;
};

export const INVALID_PREVIEW_MIME = "invalid_preview_mime";

export function normalizeBlobMimeType(type: string): string {
  const trimmed = type.trim().toLowerCase();
  if (!trimmed) {
    return "";
  }
  const parameterIndex = trimmed.indexOf(";");
  return parameterIndex === -1 ? trimmed : trimmed.slice(0, parameterIndex).trim();
}

export function isPdfBlobMimeType(type: string): boolean {
  return normalizeBlobMimeType(type) === pdfPreviewMimeType();
}

export function usePdfPreview(artifactId: Ref<string | null>): PdfPreviewState {
  const previewUrl = shallowRef<string | null>(null);
  const loading = ref(false);
  const error = ref<ApiTransportError | Error | null>(null);
  const requestGeneration = { current: 0 };
  let activeObjectUrl: string | null = null;

  function revokeObjectUrl(): void {
    if (activeObjectUrl) {
      URL.revokeObjectURL(activeObjectUrl);
      activeObjectUrl = null;
    }
    previewUrl.value = null;
  }

  async function loadPreview(generation: number, id: string): Promise<void> {
    loading.value = true;
    error.value = null;
    revokeObjectUrl();

    try {
      const blob = await fetchArtifactPreviewBlob(id);
      if (generation !== requestGeneration.current) {
        return;
      }

      if (!isPdfBlobMimeType(blob.type)) {
        error.value = new Error(INVALID_PREVIEW_MIME);
        return;
      }

      const objectUrl = URL.createObjectURL(blob);
      activeObjectUrl = objectUrl;
      previewUrl.value = objectUrl;
      error.value = null;
    } catch (cause) {
      if (generation !== requestGeneration.current) {
        return;
      }
      revokeObjectUrl();
      error.value = cause instanceof Error ? cause : new Error(String(cause));
    } finally {
      if (generation === requestGeneration.current) {
        loading.value = false;
      }
    }
  }

  async function reload(): Promise<void> {
    const id = artifactId.value?.trim() ?? "";
    if (!id) {
      requestGeneration.current += 1;
      revokeObjectUrl();
      loading.value = false;
      error.value = null;
      return;
    }
    const generation = ++requestGeneration.current;
    await loadPreview(generation, id);
  }

  watch(
    artifactId,
    (id) => {
      const trimmed = id?.trim() ?? "";
      if (!trimmed) {
        requestGeneration.current += 1;
        revokeObjectUrl();
        loading.value = false;
        error.value = null;
        return;
      }
      void reload();
    },
    { immediate: true },
  );

  onUnmounted(() => {
    requestGeneration.current += 1;
    revokeObjectUrl();
    loading.value = false;
  });

  return {
    previewUrl,
    loading,
    error,
    reload,
  };
}
