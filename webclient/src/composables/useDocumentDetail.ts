import { computed, onUnmounted, ref, shallowRef, watch, type ComputedRef, type Ref } from "vue";
import { useRoute, type LocationQueryValue } from "vue-router";

import {
  ApiTransportError,
  fetchDocumentVersion,
  fetchUsersDirectory,
  type UserDirectoryItem,
  type VersionStateResponse,
} from "../api/client";

export type DetailRouteVersionParse =
  | { valid: true; version: number }
  | { valid: false; reason: "missing" | "invalid" };

export function parseDetailRouteVersion(
  raw: LocationQueryValue | LocationQueryValue[] | null | undefined,
): DetailRouteVersionParse {
  if (raw === null || raw === undefined || Array.isArray(raw)) {
    return { valid: false, reason: "missing" };
  }
  const text = raw.trim();
  if (!/^\d+$/.test(text)) {
    return { valid: false, reason: "invalid" };
  }
  const version = Number.parseInt(text, 10);
  if (!Number.isInteger(version) || version < 1) {
    return { valid: false, reason: "invalid" };
  }
  return { valid: true, version };
}

function isRouteLoadable(documentId: string, versionParse: DetailRouteVersionParse): boolean {
  return Boolean(documentId) && versionParse.valid;
}

export type DocumentDetailState = {
  documentId: ComputedRef<string>;
  version: ComputedRef<number | null>;
  versionError: ComputedRef<"missing" | "invalid" | null>;
  detail: Ref<VersionStateResponse | null>;
  directory: Ref<UserDirectoryItem[]>;
  loading: Ref<boolean>;
  directoryLoading: Ref<boolean>;
  directoryError: Ref<boolean>;
  error: Ref<ApiTransportError | Error | null>;
  reload: () => Promise<void>;
};

export function useDocumentDetail(): DocumentDetailState {
  const route = useRoute();
  const requestGeneration = { current: 0 };
  const detail = shallowRef<VersionStateResponse | null>(null);
  const directory = shallowRef<UserDirectoryItem[]>([]);
  const loading = ref(false);
  const directoryLoading = ref(false);
  const directoryError = ref(false);
  const error = ref<ApiTransportError | Error | null>(null);

  const documentId = computed(() => String(route.params.docId ?? "").trim());
  const versionParse = computed(() => parseDetailRouteVersion(route.query.version));
  const version = computed(() =>
    versionParse.value.valid ? versionParse.value.version : null,
  );
  const versionError = computed(() =>
    versionParse.value.valid ? null : versionParse.value.reason,
  );

  function resetInvalidRouteState(): void {
    detail.value = null;
    directory.value = [];
    error.value = null;
    directoryError.value = false;
    loading.value = false;
    directoryLoading.value = false;
  }

  async function loadDetailForRoute(
    generation: number,
    docId: string,
    parsedVersion: number,
  ): Promise<void> {
    try {
      const response = await fetchDocumentVersion(docId, parsedVersion);
      if (generation !== requestGeneration.current) {
        return;
      }
      detail.value = response;
      error.value = null;
    } catch (cause) {
      if (generation !== requestGeneration.current) {
        return;
      }
      detail.value = null;
      error.value = cause instanceof Error ? cause : new Error(String(cause));
    } finally {
      if (generation === requestGeneration.current) {
        loading.value = false;
      }
    }
  }

  async function loadDirectoryForRoute(generation: number): Promise<void> {
    try {
      const response = await fetchUsersDirectory();
      if (generation !== requestGeneration.current) {
        return;
      }
      directory.value = response;
      directoryError.value = false;
    } catch {
      if (generation !== requestGeneration.current) {
        return;
      }
      directory.value = [];
      directoryError.value = true;
    } finally {
      if (generation === requestGeneration.current) {
        directoryLoading.value = false;
      }
    }
  }

  async function loadForRoute(): Promise<void> {
    const generation = ++requestGeneration.current;
    const docId = documentId.value;
    const parse = versionParse.value;

    if (!isRouteLoadable(docId, parse) || !parse.valid) {
      resetInvalidRouteState();
      return;
    }

    loading.value = true;
    directoryLoading.value = true;
    error.value = null;
    directoryError.value = false;
    detail.value = null;
    directory.value = [];

    const parsedVersion = parse.version;
    await Promise.all([
      loadDetailForRoute(generation, docId, parsedVersion),
      loadDirectoryForRoute(generation),
    ]);
  }

  async function reload(): Promise<void> {
    await loadForRoute();
  }

  watch(
    () => [documentId.value, route.query.version] as const,
    () => {
      void loadForRoute();
    },
    { immediate: true },
  );

  onUnmounted(() => {
    requestGeneration.current += 1;
    loading.value = false;
    directoryLoading.value = false;
  });

  return {
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
  };
}
