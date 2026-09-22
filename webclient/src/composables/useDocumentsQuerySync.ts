import { computed, onMounted, type ComputedRef, watch } from "vue";
import {
  type LocationQueryRaw,
  type LocationQueryValue,
  useRoute,
  useRouter,
} from "vue-router";

export const DOCUMENTS_DEFAULT_SORT = "updated_at" as const;
export const DOCUMENTS_DEFAULT_ORDER = "desc" as const;

export const DOCUMENTS_SORT_FIELDS = ["updated_at", "title", "status"] as const;
export type DocumentsSortField = (typeof DOCUMENTS_SORT_FIELDS)[number];

export const DOCUMENTS_ORDER_VALUES = ["asc", "desc"] as const;
export type DocumentsOrder = (typeof DOCUMENTS_ORDER_VALUES)[number];

export const DOCUMENTS_STATUS_VALUES = [
  "PLANNED",
  "DRAFT",
  "IN_PROGRESS",
  "IN_REVIEW",
  "IN_APPROVAL",
  "APPROVED",
  "ARCHIVED",
] as const;
export type DocumentsStatusFilter = (typeof DOCUMENTS_STATUS_VALUES)[number];

const CANONICAL_QUERY_KEYS = ["sort", "order", "q", "status", "cursor"] as const;

export type DocumentsQueryState = {
  q?: string;
  status?: DocumentsStatusFilter;
  sort: DocumentsSortField;
  order: DocumentsOrder;
  cursor?: string;
};

function isAmbiguousQueryValue(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): boolean {
  return Array.isArray(value);
}

function scalarQueryValue(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): string | undefined {
  if (value === null || value === undefined || Array.isArray(value)) {
    return undefined;
  }
  const text = String(value);
  return text === "" ? undefined : text;
}

function parseSort(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): DocumentsSortField {
  if (isAmbiguousQueryValue(value)) {
    return DOCUMENTS_DEFAULT_SORT;
  }
  const raw = scalarQueryValue(value);
  if (raw && (DOCUMENTS_SORT_FIELDS as readonly string[]).includes(raw)) {
    return raw as DocumentsSortField;
  }
  return DOCUMENTS_DEFAULT_SORT;
}

function parseOrder(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): DocumentsOrder {
  if (isAmbiguousQueryValue(value)) {
    return DOCUMENTS_DEFAULT_ORDER;
  }
  const raw = scalarQueryValue(value);
  if (raw === "asc" || raw === "desc") {
    return raw;
  }
  return DOCUMENTS_DEFAULT_ORDER;
}

function parseStatus(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): DocumentsStatusFilter | undefined {
  if (isAmbiguousQueryValue(value)) {
    return undefined;
  }
  const raw = scalarQueryValue(value);
  if (!raw) {
    return undefined;
  }
  if ((DOCUMENTS_STATUS_VALUES as readonly string[]).includes(raw)) {
    return raw as DocumentsStatusFilter;
  }
  return undefined;
}

function parseQ(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): string | undefined {
  if (isAmbiguousQueryValue(value)) {
    return undefined;
  }
  const raw = scalarQueryValue(value);
  if (!raw) {
    return undefined;
  }
  const trimmed = raw.trim();
  return trimmed === "" ? undefined : trimmed;
}

function parseCursor(
  value: LocationQueryValue | LocationQueryValue[] | undefined | null,
): string | undefined {
  if (isAmbiguousQueryValue(value)) {
    return undefined;
  }
  return scalarQueryValue(value);
}

export function parseDocumentsQuery(
  query: Record<string, LocationQueryValue | LocationQueryValue[]>,
): DocumentsQueryState {
  return {
    q: parseQ(query.q),
    status: parseStatus(query.status),
    sort: parseSort(query.sort),
    order: parseOrder(query.order),
    cursor: parseCursor(query.cursor),
  };
}

export function documentsQueryToRouteQuery(state: DocumentsQueryState): LocationQueryRaw {
  const result: LocationQueryRaw = {
    sort: state.sort,
    order: state.order,
  };
  if (state.q) {
    result.q = state.q;
  }
  if (state.status) {
    result.status = state.status;
  }
  if (state.cursor) {
    result.cursor = state.cursor;
  }
  return result;
}

export function documentsQueryKey(state: DocumentsQueryState): string {
  return [
    state.sort,
    state.order,
    state.q ?? "",
    state.status ?? "",
    state.cursor ?? "",
  ].join("\0");
}

export function documentsQueriesEqual(a: DocumentsQueryState, b: DocumentsQueryState): boolean {
  return documentsQueryKey(a) === documentsQueryKey(b);
}

function routeQueryEntryEquals(
  raw: LocationQueryValue | LocationQueryValue[] | null | undefined,
  expected: unknown,
): boolean {
  if (expected === undefined) {
    return raw === undefined;
  }
  if (raw === null || raw === undefined || Array.isArray(raw)) {
    return false;
  }
  return String(raw) === String(expected);
}

export function isCanonicalRouteQuery(
  query: Record<string, LocationQueryValue | LocationQueryValue[]>,
): boolean {
  for (const key of Object.keys(query)) {
    if (!(CANONICAL_QUERY_KEYS as readonly string[]).includes(key)) {
      return false;
    }
  }
  if (!routeQueryEntryEquals(query.sort, undefined) && isAmbiguousQueryValue(query.sort)) {
    return false;
  }
  if (!routeQueryEntryEquals(query.order, undefined) && isAmbiguousQueryValue(query.order)) {
    return false;
  }
  for (const key of ["q", "status", "cursor"] as const) {
    if (query[key] === null || isAmbiguousQueryValue(query[key])) {
      return false;
    }
  }

  const canonical = documentsQueryToRouteQuery(parseDocumentsQuery(query));
  for (const [key, value] of Object.entries(canonical)) {
    if (!routeQueryEntryEquals(query[key], value)) {
      return false;
    }
  }
  for (const key of CANONICAL_QUERY_KEYS) {
    if (key in canonical) {
      continue;
    }
    const raw = query[key];
    if (raw === undefined) {
      continue;
    }
    if (raw === null) {
      return false;
    }
    if (Array.isArray(raw)) {
      return false;
    }
    if (raw === "") {
      return false;
    }
    if (key === "q" && String(raw).trim() === "") {
      return false;
    }
    return false;
  }
  return routeQueryEntryEquals(query.sort, canonical.sort) && routeQueryEntryEquals(query.order, canonical.order);
}

export type DocumentsQuerySync = {
  query: ComputedRef<DocumentsQueryState>;
  applyFilters: (input: { q?: string; status?: DocumentsStatusFilter | "" }) => Promise<void>;
  applySort: (input: { sort: DocumentsSortField; order: DocumentsOrder }) => Promise<void>;
  goNextPage: (nextCursor: string) => Promise<void>;
};

export function useDocumentsQuerySync(): DocumentsQuerySync {
  const router = useRouter();
  const route = useRoute();
  let canonicalizing = false;

  const query = computed(() => parseDocumentsQuery(route.query));

  async function ensureCanonicalRouteQuery(): Promise<void> {
    if (canonicalizing || route.name !== "documents") {
      return;
    }
    if (isCanonicalRouteQuery(route.query)) {
      return;
    }
    canonicalizing = true;
    const nextQuery = documentsQueryToRouteQuery(parseDocumentsQuery(route.query));
    try {
      await router.replace({ name: "documents", query: nextQuery });
    } finally {
      canonicalizing = false;
    }
  }

  onMounted(() => {
    void ensureCanonicalRouteQuery();
  });

  watch(
    () => route.query,
    () => {
      void ensureCanonicalRouteQuery();
    },
    { deep: true },
  );

  async function navigate(
    next: DocumentsQueryState,
    method: "replace" | "push",
  ): Promise<void> {
    const routeQuery = documentsQueryToRouteQuery(next);
    const location = { name: route.name ?? "documents", query: routeQuery };
    if (method === "replace") {
      await router.replace(location);
    } else {
      await router.push(location);
    }
  }

  async function applyFilters(input: {
    q?: string;
    status?: DocumentsStatusFilter | "";
  }): Promise<void> {
    const trimmedQ = input.q?.trim();
    const next: DocumentsQueryState = {
      sort: query.value.sort,
      order: query.value.order,
      q: trimmedQ && trimmedQ !== "" ? trimmedQ : undefined,
      status: input.status ? input.status : undefined,
    };
    if (documentsQueriesEqual(next, query.value)) {
      return;
    }
    await navigate(next, "replace");
  }

  async function applySort(input: {
    sort: DocumentsSortField;
    order: DocumentsOrder;
  }): Promise<void> {
    const next: DocumentsQueryState = {
      q: query.value.q,
      status: query.value.status,
      sort: input.sort,
      order: input.order,
    };
    if (documentsQueriesEqual(next, query.value)) {
      return;
    }
    await navigate(next, "replace");
  }

  async function goNextPage(nextCursor: string): Promise<void> {
    const next: DocumentsQueryState = {
      ...query.value,
      cursor: nextCursor,
    };
    await navigate(next, "push");
  }

  return { query, applyFilters, applySort, goNextPage };
}
