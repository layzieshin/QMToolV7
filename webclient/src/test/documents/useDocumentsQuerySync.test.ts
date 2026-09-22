import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiBasePrefix, fetchDocumentsQuery } from "../../api/client";
import {
  documentsQueryKey,
  documentsQueryToRouteQuery,
  isCanonicalRouteQuery,
  parseDocumentsQuery,
  type DocumentsQuerySync,
  useDocumentsQuerySync,
} from "../../composables/useDocumentsQuerySync";
import { routes } from "../../router/routes";

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes,
  });
}

async function withQuerySync(
  router: ReturnType<typeof createTestRouter>,
  run: (sync: DocumentsQuerySync) => Promise<void>,
): Promise<void> {
  let syncRef: DocumentsQuerySync | null = null;
  const Probe = defineComponent({
    name: "QuerySyncProbe",
    setup() {
      syncRef = useDocumentsQuerySync();
      return () => h("div", { "data-testid": "probe" });
    },
  });

  mount(Probe, { global: { plugins: [router] } });
  await flushPromises();
  if (!syncRef) {
    throw new Error("query sync not initialized");
  }
  await run(syncRef);
}

describe("useDocumentsQuerySync", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("normalizes defaults and treats duplicate query arrays as ambiguous", () => {
    expect(parseDocumentsQuery({})).toEqual({
      sort: "updated_at",
      order: "desc",
    });
    expect(parseDocumentsQuery({ sort: "bad", order: ["asc", "desc"] })).toEqual({
      sort: "updated_at",
      order: "desc",
    });
    expect(parseDocumentsQuery({ status: ["DRAFT", "APPROVED"], q: ["  alpha  ", ""] })).toEqual({
      sort: "updated_at",
      order: "desc",
    });
    expect(parseDocumentsQuery({ status: "NOT_A_STATUS" })).toEqual({
      sort: "updated_at",
      order: "desc",
    });
  });

  it("trims q and keeps opaque cursor in canonical route query", () => {
    const parsed = parseDocumentsQuery({
      q: "  report  ",
      cursor: "opaque%2Ftoken+1",
      sort: "title",
      order: "asc",
    });
    expect(parsed.q).toBe("report");
    expect(parsed.cursor).toBe("opaque%2Ftoken+1");

    expect(documentsQueryToRouteQuery(parsed)).toEqual({
      sort: "title",
      order: "asc",
      q: "report",
      cursor: "opaque%2Ftoken+1",
    });
  });

  it("uses stable query keys for semantically identical state", () => {
    const bare = parseDocumentsQuery({});
    const explicit = parseDocumentsQuery({ sort: "updated_at", order: "desc" });
    expect(documentsQueryKey(bare)).toBe(documentsQueryKey(explicit));
  });

  it("treats present-null optional keys as non-canonical", () => {
    expect(
      isCanonicalRouteQuery({
        sort: "updated_at",
        order: "desc",
        cursor: null,
      }),
    ).toBe(false);
    expect(
      isCanonicalRouteQuery({
        sort: "updated_at",
        order: "desc",
        q: null,
      }),
    ).toBe(false);
    expect(isCanonicalRouteQuery({ sort: "updated_at", order: "desc" })).toBe(true);
  });

  it("removes a present-null optional key with exactly one replace and stays stable", async () => {
    const router = createTestRouter();
    await router.push({
      name: "documents",
      query: {
        sort: "updated_at",
        order: "desc",
        cursor: null,
      },
    });
    await router.isReady();

    expect(isCanonicalRouteQuery(router.currentRoute.value.query)).toBe(false);

    const replaceSpy = vi.spyOn(router, "replace");
    const Probe = defineComponent({
      setup() {
        useDocumentsQuerySync();
        return () => h("div");
      },
    });
    mount(Probe, { global: { plugins: [router] } });
    await flushPromises();

    expect(replaceSpy).toHaveBeenCalledTimes(1);
    expect(router.currentRoute.value.query).toEqual({
      sort: "updated_at",
      order: "desc",
    });
    expect(router.currentRoute.value.query.cursor).toBeUndefined();
    expect(isCanonicalRouteQuery(router.currentRoute.value.query)).toBe(true);

    replaceSpy.mockClear();
    mount(Probe, { global: { plugins: [router] } });
    await flushPromises();
    expect(replaceSpy).not.toHaveBeenCalled();
  });

  it("removes empty optional query keys with exactly one replace and stays stable", async () => {
    const router = createTestRouter();
    await router.push({
      name: "documents",
      query: {
        q: "   ",
        status: "",
        cursor: null,
      },
    });
    await router.isReady();

    const replaceSpy = vi.spyOn(router, "replace");
    const Probe = defineComponent({
      setup() {
        useDocumentsQuerySync();
        return () => h("div");
      },
    });
    mount(Probe, { global: { plugins: [router] } });
    await flushPromises();

    expect(replaceSpy).toHaveBeenCalledTimes(1);
    expect(router.currentRoute.value.query).toEqual({
      sort: "updated_at",
      order: "desc",
    });
    expect(isCanonicalRouteQuery(router.currentRoute.value.query)).toBe(true);

    replaceSpy.mockClear();
    mount(Probe, { global: { plugins: [router] } });
    await flushPromises();
    expect(replaceSpy).not.toHaveBeenCalled();
  });

  it("canonicalizes invalid /documents URLs on mount with exactly one replace", async () => {
    const router = createTestRouter();
    await router.push({
      name: "documents",
      query: {
        sort: "bad",
        order: ["asc", "desc"],
        q: ["foo", "bar"],
        status: ["DRAFT", "APPROVED"],
        cursor: ["a", "b"],
        extra: "x",
      },
    });
    await router.isReady();

    expect(isCanonicalRouteQuery(router.currentRoute.value.query)).toBe(false);

    const replaceSpy = vi.spyOn(router, "replace");
    const Probe = defineComponent({
      setup() {
        useDocumentsQuerySync();
        return () => h("div");
      },
    });
    mount(Probe, { global: { plugins: [router] } });
    await flushPromises();

    expect(replaceSpy).toHaveBeenCalledTimes(1);
    expect(router.currentRoute.value.query).toEqual({
      sort: "updated_at",
      order: "desc",
    });
    expect(isCanonicalRouteQuery(router.currentRoute.value.query)).toBe(true);

    replaceSpy.mockClear();
    mount(Probe, { global: { plugins: [router] } });
    await flushPromises();
    expect(replaceSpy).not.toHaveBeenCalled();
  });

  it("applyFilters and applySort clear cursor via replace", async () => {
    const router = createTestRouter();
    await router.push({
      name: "documents",
      query: { sort: "title", order: "asc", cursor: "abc" },
    });
    await router.isReady();
    await flushPromises();

    const replaceSpy = vi.spyOn(router, "replace");
    const pushSpy = vi.spyOn(router, "push");

    await withQuerySync(router, async (sync) => {
      await sync.applyFilters({ q: "alpha", status: "DRAFT" });
      await flushPromises();
    });

    expect(replaceSpy).toHaveBeenCalled();
    expect(pushSpy).not.toHaveBeenCalled();
    expect(router.currentRoute.value.query).toEqual({
      sort: "title",
      order: "asc",
      q: "alpha",
      status: "DRAFT",
    });
    expect(router.currentRoute.value.query.cursor).toBeUndefined();

    await withQuerySync(router, async (sync) => {
      await sync.applySort({ sort: "status", order: "asc" });
      await flushPromises();
    });
    expect(router.currentRoute.value.query).toEqual({
      sort: "status",
      order: "asc",
      q: "alpha",
      status: "DRAFT",
    });
  });

  it("goNextPage uses push for opaque cursor navigation", async () => {
    const router = createTestRouter();
    await router.push({ name: "documents", query: { sort: "updated_at", order: "desc" } });
    await router.isReady();
    await flushPromises();

    const pushSpy = vi.spyOn(router, "push");

    await withQuerySync(router, async (sync) => {
      await sync.goNextPage("next-cursor-token");
      await flushPromises();
    });

    expect(pushSpy).toHaveBeenCalled();
    expect(router.currentRoute.value.query.cursor).toBe("next-cursor-token");
  });

  it("reload and browser back restore the same parsed query state", async () => {
    const router = createTestRouter();
    await router.push({
      name: "documents",
      query: { sort: "title", order: "asc", q: "beta", status: "APPROVED" },
    });
    await router.isReady();
    await flushPromises();

    await withQuerySync(router, async (sync) => {
      expect(sync.query.value).toEqual({
        sort: "title",
        order: "asc",
        q: "beta",
        status: "APPROVED",
      });
    });

    await router.push({ name: "documents", query: { sort: "updated_at", order: "desc" } });
    await flushPromises();
    await router.back();
    await flushPromises();

    expect(parseDocumentsQuery(router.currentRoute.value.query)).toEqual({
      sort: "title",
      order: "asc",
      q: "beta",
      status: "APPROVED",
    });
  });

  it("does not spam history when applying identical filters", async () => {
    const router = createTestRouter();
    await router.push({
      name: "documents",
      query: { sort: "updated_at", order: "desc", q: "same" },
    });
    await router.isReady();
    await flushPromises();

    const replaceSpy = vi.spyOn(router, "replace");

    await withQuerySync(router, async (sync) => {
      await sync.applyFilters({ q: "same" });
      await flushPromises();
    });

    expect(replaceSpy).not.toHaveBeenCalled();
  });
});

describe("fetchDocumentsQuery transport", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ items: [], limit: 50, next_cursor: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses /api/v1/documents/query with credentials include and no Authorization or limit", async () => {
    await fetchDocumentsQuery({
      sort: "title",
      order: "asc",
      q: "report",
      cursor: "opaque-token-1",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://localhost");
    expect(parsed.pathname).toBe(`${apiBasePrefix()}/documents/query`);
    expect(parsed.searchParams.get("sort")).toBe("title");
    expect(parsed.searchParams.get("order")).toBe("asc");
    expect(parsed.searchParams.get("q")).toBe("report");
    expect(parsed.searchParams.get("cursor")).toBe("opaque-token-1");
    expect(parsed.searchParams.has("limit")).toBe(false);
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).has("Authorization")).toBe(false);
  });
});
