import { computed, onUnmounted, watch, type ComputedRef } from "vue";
import {
  isNavigationFailure,
  NavigationFailureType,
  useRoute,
  useRouter,
  type LocationQuery,
  type LocationQueryValue,
} from "vue-router";

import { parseDetailRouteVersion } from "./useDocumentDetail";
import { useBootstrapState } from "../state/bootstrap";

export type DocumentDetailSection = "overview" | "history";

const SECRET_QUERY_KEYS = new Set([
  "password",
  "token",
  "secret",
  "bearer",
  "csrf",
  "session",
  "authorization",
]);

export function parseDetailRouteSection(
  raw: LocationQueryValue | LocationQueryValue[] | null | undefined,
): DocumentDetailSection {
  if (raw === null || raw === undefined || Array.isArray(raw)) {
    return "overview";
  }
  const trimmed = raw.trim().toLowerCase();
  return trimmed === "history" ? "history" : "overview";
}

export function buildCanonicalDetailQuery(
  version: number,
  section: DocumentDetailSection,
): Record<string, string> {
  const query: Record<string, string> = {
    version: String(version),
  };
  if (section === "history") {
    query.section = "history";
  }
  return query;
}

export function isSecretDetailQueryKey(key: string): boolean {
  return SECRET_QUERY_KEYS.has(key.toLowerCase());
}

export function resolveSanitizedDetailQuery(
  versionRaw: LocationQueryValue | LocationQueryValue[] | null | undefined,
  sectionRaw: LocationQueryValue | LocationQueryValue[] | null | undefined,
): Record<string, string> {
  const versionParse = parseDetailRouteVersion(versionRaw);
  if (!versionParse.valid) {
    return {};
  }
  const section = parseDetailRouteSection(sectionRaw);
  return buildCanonicalDetailQuery(versionParse.version, section);
}

export function buildDetailQueryReplacement(
  query: LocationQuery,
  target: Record<string, string>,
): Record<string, string | undefined> {
  const replacement: Record<string, string | undefined> = { ...target };
  for (const key of Object.keys(query)) {
    if (!(key in target)) {
      replacement[key] = undefined;
    }
  }
  return replacement;
}

export function detailQueryNeedsSanitization(
  query: LocationQuery,
  target: Record<string, string>,
): boolean {
  const targetKeys = new Set(Object.keys(target));
  for (const [key, value] of Object.entries(query)) {
    if (isSecretDetailQueryKey(key)) {
      return true;
    }
    if (Array.isArray(value)) {
      return true;
    }
    if (!targetKeys.has(key)) {
      return true;
    }
    const text = typeof value === "string" ? value : null;
    if (text !== target[key]) {
      return true;
    }
  }
  for (const [key, expected] of Object.entries(target)) {
    const current = query[key];
    if (Array.isArray(current)) {
      return true;
    }
    const text = typeof current === "string" ? current : null;
    if (text !== expected) {
      return true;
    }
  }
  return false;
}

export type DeepLinkRestoreState = {
  section: ComputedRef<DocumentDetailSection>;
  setSection: (next: DocumentDetailSection) => Promise<void>;
};

export function useDeepLinkRestore(
  onRestore: (generation: number) => void | Promise<void>,
): DeepLinkRestoreState {
  const router = useRouter();
  useRoute();
  const bootstrap = useBootstrapState();
  const route = computed(() => router.currentRoute.value);
  const restoreEpoch = { current: 0 };
  let lastBanner = bootstrap.banner;

  const section = computed(() => parseDetailRouteSection(route.value.query.section));

  async function normalizeRouteQuery(): Promise<void> {
    const current = route.value;
    const target = resolveSanitizedDetailQuery(current.query.version, current.query.section);
    if (!detailQueryNeedsSanitization(current.query, target)) {
      return;
    }
    const result = await router.replace({
      path: current.path,
      query: buildDetailQueryReplacement(current.query, target),
    });
    if (isNavigationFailure(result, NavigationFailureType.duplicated)) {
      return;
    }
  }

  async function setSection(next: DocumentDetailSection): Promise<void> {
    const current = route.value;
    const versionParse = parseDetailRouteVersion(current.query.version);
    if (!versionParse.valid) {
      return;
    }
    const canonical = buildCanonicalDetailQuery(versionParse.version, next);
    const result = await router.replace({
      path: current.path,
      query: buildDetailQueryReplacement(current.query, canonical),
    });
    if (isNavigationFailure(result, NavigationFailureType.duplicated)) {
      return;
    }
  }

  function triggerRestore(): void {
    const generation = ++restoreEpoch.current;
    void Promise.resolve(onRestore(generation));
  }

  watch(
    () => bootstrap.banner,
    (banner) => {
      const previous = lastBanner;
      lastBanner = banner;
      if (
        banner === "restored" &&
        (previous === "offline" || previous === "reconnecting")
      ) {
        triggerRestore();
      }
    },
  );

  watch(
    () => route.value.fullPath,
    () => {
      void normalizeRouteQuery();
    },
    { immediate: true },
  );

  onUnmounted(() => {
    restoreEpoch.current += 1;
  });

  return {
    section,
    setSection,
  };
}
