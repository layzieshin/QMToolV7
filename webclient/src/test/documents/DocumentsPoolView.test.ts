import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h, ref, type Ref } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  const { register } = require("node:module") as typeof import("node:module");
  const { mkdtempSync, writeFileSync } = require("node:fs") as typeof import("node:fs");
  const { tmpdir } = require("node:os") as typeof import("node:os");
  const { join } = require("node:path") as typeof import("node:path");
  const { pathToFileURL } = require("node:url") as typeof import("node:url");

  const loaderDir = mkdtempSync(join(tmpdir(), "vitest-css-stub-"));
  const loaderPath = join(loaderDir, "css-stub-loader.mjs");
  writeFileSync(
    loaderPath,
    `export async function load(url, context, nextLoad) {
  if (url.endsWith(".css")) {
    return { format: "module", shortCircuit: true, source: "export default {}\\n" };
  }
  return nextLoad(url, context);
}
`,
  );
  register(pathToFileURL(loaderPath), pathToFileURL(join(process.cwd(), "package.json")));
});

import { type DocumentQueryItem, type DocumentQueryPageResponse } from "../../api/client";
import { useDocumentsList } from "../../composables/useDocumentsList";
import type { DocumentsQueryState } from "../../composables/useDocumentsQuerySync";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { routes } from "../../router/routes";
import { __setBootstrapWritesAllowedForTest } from "../../state/bootstrap";
import DocumentsPoolView from "../../views/documents/DocumentsPoolView.vue";

const fetchDocumentsQueryMock = vi.hoisted(() => vi.fn());
const fetchDocumentsCapabilitiesMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchDocumentsQuery: fetchDocumentsQueryMock,
    fetchDocumentsCapabilities: fetchDocumentsCapabilitiesMock,
  };
});

function stubBrowserApis(): void {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }));
}

function page(items: DocumentQueryItem[], nextCursor: string | null = null): DocumentQueryPageResponse {
  return { items, limit: 50, next_cursor: nextCursor };
}

function item(overrides: Partial<DocumentQueryItem> = {}): DocumentQueryItem {
  return {
    allowed_actions: [],
    approved_by: [],
    assignments: {
      approvers: [],
      editors: [],
      reviewers: [],
    },
    control_class: "controlled",
    description: "Kurzbeschreibung",
    doc_type: "SOP",
    document_id: "DOC-1",
    edit_signature_done: false,
    extension_count: 0,
    reviewed_by: [],
    status: "APPROVED",
    title: "Qualitätsleitbild",
    updated_at: "2026-01-15T10:00:00Z",
    version: 2,
    workflow_active: false,
    workflow_profile_id: "default",
    ...overrides,
  };
}

async function mountPool(initialPath = "/documents") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  });
  await router.push(initialPath);
  await router.isReady();

  const wrapper = mount(DocumentsPoolView, {
    global: {
      plugins: [router, vuetify, i18n],
    },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("DocumentsPoolView", () => {
  beforeEach(() => {
    __setBootstrapWritesAllowedForTest(true);
    stubBrowserApis();
    fetchDocumentsQueryMock.mockReset();
    fetchDocumentsCapabilitiesMock.mockReset();
    fetchDocumentsQueryMock.mockResolvedValue(page([item()]));
    fetchDocumentsCapabilitiesMock.mockResolvedValue({ can_create_new_documents: false });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("registers /documents with requiresAuth in production routes", () => {
    const documentsRoute = routes[0]?.children?.find((route) => route.name === "documents");
    expect(documentsRoute?.path).toBe("documents");
    expect(documentsRoute?.meta?.requiresAuth).toBe(true);
  });

  it("calls typed client adapter with normalized query parameters", async () => {
    await mountPool("/documents?sort=title&order=asc&q=alpha&status=APPROVED");

    expect(fetchDocumentsQueryMock).toHaveBeenCalled();
    const params = fetchDocumentsQueryMock.mock.calls.at(-1)?.[0];
    expect(params).toEqual({
      sort: "title",
      order: "asc",
      q: "alpha",
      status: "APPROVED",
    });
    expect(params?.limit).toBeUndefined();
  });

  it("shows loading, unfiltered empty, filtered empty and error states distinctly", async () => {
    fetchDocumentsQueryMock.mockImplementationOnce(
      () => new Promise(() => {
        /* pending */
      }),
    );
    const loadingMount = await mountPool();
    expect(loadingMount.wrapper.find("[data-testid=documents-pool-loading]").exists()).toBe(true);

    fetchDocumentsQueryMock.mockResolvedValueOnce(page([]));
    const emptyMount = await mountPool();
    expect(emptyMount.wrapper.find("[data-testid=documents-pool-empty]").exists()).toBe(true);

    fetchDocumentsQueryMock.mockResolvedValueOnce(page([]));
    const filteredMount = await mountPool("/documents?sort=updated_at&order=desc&q=nope");
    expect(filteredMount.wrapper.find("[data-testid=documents-pool-empty-filtered]").exists()).toBe(
      true,
    );

    fetchDocumentsQueryMock.mockRejectedValueOnce(new Error("network"));
    const errorMount = await mountPool();
    expect(errorMount.wrapper.find("[data-testid=documents-pool-error]").exists()).toBe(true);
    expect(errorMount.wrapper.find("[data-testid=documents-table-row]").exists()).toBe(false);
  });

  it("shows empty state and next page when items are empty but next_cursor is present", async () => {
    fetchDocumentsQueryMock.mockResolvedValueOnce(page([], "cursor-2"));
    const { wrapper } = await mountPool();
    expect(wrapper.find("[data-testid=documents-pool-empty]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=documents-pool-next]").exists()).toBe(true);
    expect(wrapper.text()).toContain("Nächste Seite");
  });

  it("latest request wins and stale finally does not clear loading early", async () => {
    let resolveSlow: (value: DocumentQueryPageResponse) => void = () => undefined;
    const slow = new Promise<DocumentQueryPageResponse>((resolve) => {
      resolveSlow = resolve;
    });

    fetchDocumentsQueryMock
      .mockImplementationOnce(() => slow)
      .mockResolvedValueOnce(page([item({ title: "Fresh" })]));

    const { wrapper, router } = await mountPool("/documents?sort=updated_at&order=desc");
    expect(wrapper.find("[data-testid=documents-pool-loading]").exists()).toBe(true);

    await router.replace({
      name: "documents",
      query: { sort: "title", order: "asc" },
    });
    await flushPromises();

    resolveSlow(page([item({ title: "Stale" })]));
    await flushPromises();

    expect(wrapper.text()).toContain("Fresh");
    expect(wrapper.text()).not.toContain("Stale");
    expect(wrapper.find("[data-testid=documents-pool-loading]").exists()).toBe(false);
  });

  it("retains selection when filter change keeps the exact document version accessible", async () => {
    fetchDocumentsQueryMock
      .mockResolvedValueOnce(page([item({ document_id: "DOC-1", version: 2, title: "V2" })]))
      .mockResolvedValueOnce(page([item({ document_id: "DOC-1", version: 2, title: "Noch V2" })]));

    const { wrapper, router } = await mountPool();
    const rows = wrapper.findAll("[data-testid=documents-table-row]");
    await rows[0].trigger("click");
    expect(wrapper.find("[data-testid=documents-detail-version]").text()).toBe("2");

    await router.replace({
      name: "documents",
      query: { sort: "updated_at", order: "desc", q: "noch" },
    });
    await flushPromises();

    expect(wrapper.find("[data-testid=documents-detail-summary]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=documents-detail-version]").text()).toBe("2");
    expect(wrapper.text()).toContain("Noch V2");
  });

  it("clears selection when only another version of the same document remains", async () => {
    fetchDocumentsQueryMock
      .mockResolvedValueOnce(page([item({ document_id: "DOC-1", version: 2, title: "V2" })]))
      .mockResolvedValueOnce(page([item({ document_id: "DOC-1", version: 3, title: "V3" })]));

    const { wrapper, router } = await mountPool();
    await wrapper.find("[data-testid=documents-table-row]").trigger("click");
    expect(wrapper.find("[data-testid=documents-detail-version]").text()).toBe("2");

    await router.replace({
      name: "documents",
      query: { sort: "updated_at", order: "desc", q: "neu" },
    });
    await flushPromises();

    expect(wrapper.find("[data-testid=documents-detail-empty]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=documents-detail-summary]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=documents-table-row]").text()).toContain("V3");
  });

  it("clears selection when the selected document is no longer in the result set", async () => {
    fetchDocumentsQueryMock
      .mockResolvedValueOnce(page([item({ document_id: "DOC-1", version: 1 })]))
      .mockResolvedValueOnce(page([item({ document_id: "DOC-2", version: 1, title: "Anderes Dokument" })]));

    const { wrapper, router } = await mountPool();
    await wrapper.find("[data-testid=documents-table-row]").trigger("click");
    expect(wrapper.find("[data-testid=documents-detail-summary]").exists()).toBe(true);

    await router.replace({
      name: "documents",
      query: { sort: "updated_at", order: "desc", q: "anderes" },
    });
    await flushPromises();

    expect(wrapper.find("[data-testid=documents-detail-empty]").exists()).toBe(true);
  });

  it("uses push for next cursor page navigation", async () => {
    fetchDocumentsQueryMock.mockResolvedValueOnce(
      page([item({ document_id: "DOC-1" })], "cursor-2"),
    );

    const { wrapper, router } = await mountPool();
    await vi.waitFor(() => {
      expect(wrapper.find("[data-testid=documents-pool-next]").exists()).toBe(true);
    });

    const pushSpy = vi.spyOn(router, "push");
    await wrapper.get("[data-testid=documents-pool-next]").trigger("click");
    await flushPromises();
    expect(pushSpy).toHaveBeenCalledWith({
      name: "documents",
      query: {
        sort: "updated_at",
        order: "desc",
        cursor: "cursor-2",
      },
    });
  });

  it("shows import action only when server capability allows create", async () => {
    fetchDocumentsCapabilitiesMock.mockResolvedValueOnce({ can_create_new_documents: true });
    const allowed = await mountPool();
    expect(allowed.wrapper.find("[data-testid=documents-pool-import]").exists()).toBe(true);

    fetchDocumentsCapabilitiesMock.mockResolvedValueOnce({ can_create_new_documents: false });
    const denied = await mountPool();
    expect(denied.wrapper.find("[data-testid=documents-pool-import]").exists()).toBe(false);

    fetchDocumentsCapabilitiesMock.mockRejectedValueOnce(new Error("caps failed"));
    const failed = await mountPool();
    expect(failed.wrapper.find("[data-testid=documents-pool-import]").exists()).toBe(false);
  });

  it("disables import and blocks navigation when product writes are unavailable", async () => {
    fetchDocumentsCapabilitiesMock.mockResolvedValueOnce({ can_create_new_documents: true });
    __setBootstrapWritesAllowedForTest(false);
    const { wrapper, router } = await mountPool();
    const importButton = wrapper.get("[data-testid=documents-pool-import]");
    expect(importButton.attributes("disabled")).toBeDefined();
    const pushSpy = vi.spyOn(router, "push");
    await importButton.trigger("click");
    await flushPromises();
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("routes import action to document-import", async () => {
    fetchDocumentsCapabilitiesMock.mockResolvedValueOnce({ can_create_new_documents: true });
    const { wrapper, router } = await mountPool();
    const pushSpy = vi.spyOn(router, "push");
    await wrapper.get("[data-testid=documents-pool-import]").trigger("click");
    await flushPromises();
    expect(pushSpy).toHaveBeenCalledWith({ name: "document-import" });
  });

  it("navigates selected detail with docId param and version query", async () => {
    fetchDocumentsQueryMock.mockResolvedValueOnce(
      page([item({ document_id: "DOC/SLASH", version: 4, title: "Slash Doc" })]),
    );
    const { wrapper, router } = await mountPool();
    await wrapper.find("[data-testid=documents-table-row]").trigger("click");
    const pushSpy = vi.spyOn(router, "push");
    await wrapper.get("[data-testid=documents-pool-open-detail]").trigger("click");
    await flushPromises();
    expect(pushSpy).toHaveBeenCalledWith({
      name: "document-detail",
      params: { docId: "DOC/SLASH" },
      query: { version: "4" },
    });
  });

  it("does not apply late capabilities result after unmount", async () => {
    let resolveCaps: (value: { can_create_new_documents: boolean }) => void = () => undefined;
    const pending = new Promise<{ can_create_new_documents: boolean }>((resolve) => {
      resolveCaps = resolve;
    });
    fetchDocumentsCapabilitiesMock.mockImplementationOnce(() => pending);

    const { wrapper } = await mountPool();
    expect(wrapper.find("[data-testid=documents-pool-import]").exists()).toBe(false);
    wrapper.unmount();
    resolveCaps({ can_create_new_documents: true });
    await flushPromises();
    expect(fetchDocumentsCapabilitiesMock).toHaveBeenCalledTimes(1);
  });

  it("does not call global fetch directly for documents query", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    try {
      await mountPool();
      const queryCalls = fetchSpy.mock.calls.filter((call) =>
        String(call[0]).includes("/documents/query"),
      );
      expect(queryCalls).toHaveLength(0);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("useDocumentsList instance isolation", () => {
  beforeEach(() => {
    fetchDocumentsQueryMock.mockReset();
  });

  async function mountListProbe(query: Ref<DocumentsQueryState>) {
    const snapshot: {
      items: Ref<DocumentQueryItem[]> | null;
      nextCursor: Ref<string | null> | null;
      error: Ref<Error | null> | null;
      loading: Ref<boolean> | null;
    } = { items: null, nextCursor: null, error: null, loading: null };
    const Probe = defineComponent({
      setup() {
        const list = useDocumentsList(query);
        snapshot.items = list.items;
        snapshot.nextCursor = list.nextCursor;
        snapshot.error = list.error;
        snapshot.loading = list.loading;
        return () => h("div");
      },
    });
    const wrapper = mount(Probe);
    await flushPromises();
    return { wrapper, snapshot };
  }

  it("keeps concurrent pending instances independent when responses resolve out of order", async () => {
    let resolveA: (value: DocumentQueryPageResponse) => void = () => undefined;
    let resolveB: (value: DocumentQueryPageResponse) => void = () => undefined;
    const pendingA = new Promise<DocumentQueryPageResponse>((resolve) => {
      resolveA = resolve;
    });
    const pendingB = new Promise<DocumentQueryPageResponse>((resolve) => {
      resolveB = resolve;
    });

    fetchDocumentsQueryMock
      .mockImplementationOnce(() => pendingA)
      .mockImplementationOnce(() => pendingB);

    const queryA = ref<DocumentsQueryState>({ sort: "updated_at", order: "desc" });
    const queryB = ref<DocumentsQueryState>({ sort: "title", order: "asc" });

    const instanceA = await mountListProbe(queryA);
    const instanceB = await mountListProbe(queryB);
    expect(instanceA.snapshot.loading?.value).toBe(true);
    expect(instanceB.snapshot.loading?.value).toBe(true);

    resolveB(page([item({ document_id: "DOC-B", title: "B" })]));
    await flushPromises();
    expect(instanceB.snapshot.items?.value?.[0]?.document_id).toBe("DOC-B");
    expect(instanceA.snapshot.items?.value).toEqual([]);

    resolveA(page([item({ document_id: "DOC-A", title: "A" })]));
    await flushPromises();
    expect(instanceA.snapshot.items?.value?.[0]?.document_id).toBe("DOC-A");
    expect(instanceB.snapshot.items?.value?.[0]?.document_id).toBe("DOC-B");
    expect(instanceA.snapshot.loading?.value).toBe(false);
    expect(instanceB.snapshot.loading?.value).toBe(false);
  });

  it("keeps error state when the newest request fails and an older success resolves later", async () => {
    let resolveOld: (value: DocumentQueryPageResponse) => void = () => undefined;
    const oldPending = new Promise<DocumentQueryPageResponse>((resolve) => {
      resolveOld = resolve;
    });

    fetchDocumentsQueryMock
      .mockImplementationOnce(() => oldPending)
      .mockRejectedValueOnce(new Error("latest failed"));

    const query = ref<DocumentsQueryState>({ sort: "updated_at", order: "desc" });
    const { snapshot } = await mountListProbe(query);

    query.value = { sort: "title", order: "asc" };
    await flushPromises();

    expect(snapshot.error?.value).toBeTruthy();
    expect(snapshot.items?.value).toEqual([]);

    resolveOld(page([item({ title: "Stale success" })]));
    await flushPromises();

    expect(snapshot.items?.value).toEqual([]);
    expect(snapshot.error?.value).toBeTruthy();
    expect(snapshot.loading?.value).toBe(false);
  });

  it("ignores pending responses after unmount and clears loading", async () => {
    let resolvePending: (value: DocumentQueryPageResponse) => void = () => undefined;
    fetchDocumentsQueryMock.mockImplementationOnce(
      () =>
        new Promise<DocumentQueryPageResponse>((resolve) => {
          resolvePending = resolve;
        }),
    );

    const query = ref<DocumentsQueryState>({ sort: "updated_at", order: "desc" });
    const { wrapper, snapshot } = await mountListProbe(query);
    expect(snapshot.loading?.value).toBe(true);

    wrapper.unmount();
    expect(snapshot.loading?.value).toBe(false);

    resolvePending(page([item({ title: "After unmount" })]));
    await flushPromises();

    expect(snapshot.items?.value).toEqual([]);
    expect(snapshot.nextCursor?.value ?? null).toBeNull();
    expect(snapshot.error?.value).toBeNull();
    expect(snapshot.loading?.value).toBe(false);
  });
});
