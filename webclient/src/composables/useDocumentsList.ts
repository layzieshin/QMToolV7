import { onUnmounted, ref, shallowRef, watch, type Ref } from "vue";

import {
  ApiTransportError,
  fetchDocumentsQuery,
  type DocumentQueryItem,
} from "../api/client";
import { documentsQueryKey, type DocumentsQueryState } from "./useDocumentsQuerySync";

export type DocumentsListState = {
  items: Ref<DocumentQueryItem[]>;
  nextCursor: Ref<string | null>;
  loading: Ref<boolean>;
  error: Ref<ApiTransportError | Error | null>;
  reload: () => Promise<void>;
};

export function useDocumentsList(query: Ref<DocumentsQueryState>): DocumentsListState {
  const requestGeneration = { current: 0 };
  const items = shallowRef<DocumentQueryItem[]>([]);
  const nextCursor = ref<string | null>(null);
  const loading = ref(false);
  const error = ref<ApiTransportError | Error | null>(null);

  async function load(state: DocumentsQueryState): Promise<void> {
    const generation = ++requestGeneration.current;
    loading.value = true;
    error.value = null;
    items.value = [];
    nextCursor.value = null;

    try {
      const page = await fetchDocumentsQuery(state);
      if (generation !== requestGeneration.current) {
        return;
      }
      items.value = page.items;
      nextCursor.value = page.next_cursor ?? null;
      error.value = null;
    } catch (cause) {
      if (generation !== requestGeneration.current) {
        return;
      }
      items.value = [];
      nextCursor.value = null;
      error.value = cause instanceof Error ? cause : new Error(String(cause));
    } finally {
      if (generation === requestGeneration.current) {
        loading.value = false;
      }
    }
  }

  async function reload(): Promise<void> {
    await load(query.value);
  }

  watch(
    () => documentsQueryKey(query.value),
    () => {
      void load(query.value);
    },
    { immediate: true },
  );

  onUnmounted(() => {
    requestGeneration.current += 1;
    loading.value = false;
  });

  return { items, nextCursor, loading, error, reload };
}
