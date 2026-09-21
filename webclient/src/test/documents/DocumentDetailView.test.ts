import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
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

import type { ActionDescriptor } from "../../actions/actionTypes";
import { ApiTransportError, apiBasePrefix } from "../../api/client";
import { parseDetailRouteVersion } from "../../composables/useDocumentDetail";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { routes } from "../../router/routes";
import {
  __resetBootstrapStateForTest,
  __setBootstrapWritesAllowedForTest,
  __setBootstrapBannerForTest,
} from "../../state/bootstrap";
import DocumentDetailView from "../../views/documents/DocumentDetailView.vue";

const fetchDocumentVersionMock = vi.hoisted(() => vi.fn());
const fetchDocumentVersionHistoryMock = vi.hoisted(() => vi.fn());
const fetchUsersDirectoryMock = vi.hoisted(() => vi.fn());
const mutateMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchDocumentVersion: fetchDocumentVersionMock,
    fetchDocumentVersionHistory: fetchDocumentVersionHistoryMock,
    fetchUsersDirectory: fetchUsersDirectoryMock,
  };
});

vi.mock("../../api/mutationClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/mutationClient")>();
  return {
    ...actual,
    mutate: mutateMock,
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

function assignRolesDescriptor(enabled = true): ActionDescriptor {
  return {
    code: "assign_roles",
    enabled,
    destructive: false,
    label_key: "documents.action.assign_roles",
    requires_confirmation: false,
    requires_reason: false,
    severity: "normal",
    signature_required: false,
    assignment_kind: "workflow_roles",
  };
}

function versionState(
  overrides: {
    etag?: string;
    allowed_actions?: ActionDescriptor[];
    available_actions?: string[];
    state?: Record<string, unknown>;
  } = {},
) {
  return {
    etag: overrides.etag ?? "evt-1",
    allowed_actions: overrides.allowed_actions ?? [assignRolesDescriptor(true)],
    available_actions: overrides.available_actions ?? ["assign_roles"],
    state: {
      document_id: "DOC-1",
      version: 2,
      title: "Qualitätsleitbild",
      status: "DRAFT",
      doc_type: "SOP",
      control_class: "controlled",
      workflow_profile_id: "default",
      description: "Beschreibung",
      owner_user_id: "user-active",
      updated_at: "2026-01-15T10:00:00Z",
      approved_by: [],
      reviewed_by: [],
      assignments: {
        editors: ["user-active", "user-missing"],
        reviewers: [],
        approvers: [],
      },
      edit_signature_done: false,
      extension_count: 0,
      workflow_active: false,
      ...overrides.state,
    },
  };
}

const mountedWrappers: VueWrapper[] = [];

async function mountDetail(initialPath = "/documents/DOC-1?version=2") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  });
  await router.push(initialPath);
  await router.isReady();

  const wrapper = mount(DocumentDetailView, {
    global: {
      plugins: [router, vuetify, i18n],
    },
  });
  mountedWrappers.push(wrapper);
  await flushPromises();
  await router.isReady();
  return { wrapper, router };
}

describe("parseDetailRouteVersion", () => {
  it("accepts positive integers only", () => {
    expect(parseDetailRouteVersion("2")).toEqual({ valid: true, version: 2 });
    expect(parseDetailRouteVersion("0")).toEqual({ valid: false, reason: "invalid" });
    expect(parseDetailRouteVersion("")).toEqual({ valid: false, reason: "invalid" });
    expect(parseDetailRouteVersion(undefined)).toEqual({ valid: false, reason: "missing" });
  });
});

describe("DocumentDetailView", () => {
  beforeEach(() => {
    __resetBootstrapStateForTest();
    __setBootstrapWritesAllowedForTest(true);
    stubBrowserApis();
    fetchDocumentVersionMock.mockReset();
    fetchDocumentVersionHistoryMock.mockReset();
    fetchUsersDirectoryMock.mockReset();
    mutateMock.mockReset();
    fetchUsersDirectoryMock.mockResolvedValue([
      { user_id: "user-active", username: "Aktiver Benutzer", is_active: true, is_qmb: false, role: "editor" },
    ]);
    fetchDocumentVersionMock.mockResolvedValue(versionState());
    fetchDocumentVersionHistoryMock.mockResolvedValue([]);
  });

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount();
    }
    document.body.innerHTML = "";
    __resetBootstrapStateForTest();
    vi.clearAllMocks();
  });

  it("does not request detail or directory when version query is invalid", async () => {
    const { wrapper } = await mountDetail("/documents/DOC-1?version=abc");
    expect(fetchDocumentVersionMock).not.toHaveBeenCalled();
    expect(fetchUsersDirectoryMock).not.toHaveBeenCalled();
    expect(wrapper.find("[data-testid=document-detail-version-error]").exists()).toBe(true);
  });

  it("does not request detail or directory when document id is empty", async () => {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push({ name: "document-detail", params: { docId: "   " }, query: { version: "2" } });
    await router.isReady();
    const wrapper = mount(DocumentDetailView, { global: { plugins: [router, vuetify, i18n] } });
    mountedWrappers.push(wrapper);
    await flushPromises();
    await router.isReady();
    expect(fetchDocumentVersionMock).not.toHaveBeenCalled();
    expect(fetchUsersDirectoryMock).not.toHaveBeenCalled();
  });

  it("loads detail from typed GET path with document_id and version", async () => {
    await mountDetail("/documents/DOC-1?version=2");
    expect(fetchDocumentVersionMock).toHaveBeenCalledWith("DOC-1", 2);
    expect(fetchUsersDirectoryMock).toHaveBeenCalled();
  });

  it("uses exact GET transport path for version read", async () => {
    const fetchSpy = vi.fn(
      async () =>
        new Response(JSON.stringify(versionState()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    try {
      const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
      await actual.fetchDocumentVersion("DOC-1", 2);
      expect(fetchSpy).toHaveBeenCalled();
      const firstCall = fetchSpy.mock.calls[0] as unknown as [RequestInfo | URL, RequestInit?];
      const url = String(firstCall[0]);
      expect(url).toContain(`${apiBasePrefix()}/documents/versions/DOC-1/2`);
      const init = firstCall[1];
      expect(new Headers(init?.headers).has("Authorization")).toBe(false);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("latest route change wins and stale detail responses do not overwrite", async () => {
    let resolveSlow: (value: unknown) => void = () => undefined;
    const slow = new Promise((resolve) => {
      resolveSlow = resolve;
    });
    fetchDocumentVersionMock
      .mockImplementationOnce(() => slow)
      .mockResolvedValueOnce(versionState({ state: { title: "Fresh" } }));

    const { wrapper, router } = await mountDetail("/documents/DOC-1?version=1");
    await router.replace({ path: "/documents/DOC-1", query: { version: "2" } });
    await flushPromises();

    resolveSlow(versionState({ state: { title: "Stale" } }));
    await flushPromises();

    expect(wrapper.find("[data-testid=document-header-title]").text()).toBe("Fresh");
    expect(wrapper.text()).not.toContain("Stale");
  });

  it("latest route change wins and stale directory responses do not overwrite", async () => {
    let resolveSlow: (value: unknown) => void = () => undefined;
    const slow = new Promise((resolve) => {
      resolveSlow = resolve;
    });
    fetchUsersDirectoryMock
      .mockImplementationOnce(() => slow)
      .mockResolvedValueOnce([
        { user_id: "user-b", username: "Route B", is_active: true, is_qmb: false, role: "editor" },
      ]);
    fetchDocumentVersionMock.mockResolvedValue(
      versionState({
        state: {
          assignments: { editors: ["user-b"], reviewers: [], approvers: [] },
        },
      }),
    );

    const { wrapper, router } = await mountDetail("/documents/DOC-A?version=1");
    await router.replace({ path: "/documents/DOC-B", query: { version: "1" } });
    await flushPromises();

    resolveSlow([
      { user_id: "user-stale", username: "Stale User", is_active: true, is_qmb: false, role: "editor" },
    ]);
    await flushPromises();

    expect(wrapper.text()).toContain("Route B");
    expect(wrapper.text()).not.toContain("Stale User");
  });

  it("does not mutate refs after unmount when late detail or directory resolves", async () => {
    let resolveDetail: (value: unknown) => void = () => undefined;
    let resolveDirectory: (value: unknown) => void = () => undefined;
    const detailPending = new Promise((resolve) => {
      resolveDetail = resolve;
    });
    const directoryPending = new Promise((resolve) => {
      resolveDirectory = resolve;
    });
    fetchDocumentVersionMock.mockImplementationOnce(() => detailPending);
    fetchUsersDirectoryMock.mockImplementationOnce(() => directoryPending);

    const { wrapper } = await mountDetail();
    wrapper.unmount();
    resolveDetail(versionState({ state: { title: "Late Detail" } }));
    resolveDirectory([
      { user_id: "late", username: "Late", is_active: true, is_qmb: false, role: "editor" },
    ]);
    await flushPromises();
    expect(fetchDocumentVersionMock).toHaveBeenCalledTimes(1);
    expect(fetchUsersDirectoryMock).toHaveBeenCalledTimes(1);
  });

  it("reconstructs state after browser back with version query", async () => {
    const { router } = await mountDetail("/documents/DOC-1?version=2");
    await router.push({ name: "documents" });
    await flushPromises();
    fetchDocumentVersionMock.mockClear();
    fetchUsersDirectoryMock.mockClear();
    await router.back();
    await flushPromises();
    expect(fetchDocumentVersionMock).toHaveBeenCalledWith("DOC-1", 2);
    expect(fetchUsersDirectoryMock).toHaveBeenCalled();
  });

  it("uses allowed_actions enabled descriptor and ignores contradictory available_actions", async () => {
    fetchDocumentVersionMock.mockResolvedValueOnce(
      versionState({
        allowed_actions: [assignRolesDescriptor(false)],
        available_actions: ["assign_roles"],
      }),
    );
    const disabledMount = await mountDetail();
    expect(disabledMount.wrapper.find("[data-testid=assignments-readonly]").exists()).toBe(true);
    expect(disabledMount.wrapper.find("[data-testid=assignments-form]").exists()).toBe(false);

    fetchDocumentVersionMock.mockResolvedValueOnce(
      versionState({
        allowed_actions: [assignRolesDescriptor(true)],
        available_actions: [],
      }),
    );
    const enabledMount = await mountDetail();
    expect(enabledMount.wrapper.find("[data-testid=assignments-form]").exists()).toBe(true);
  });

  it("keeps assignments read-only when directory load fails but detail remains visible", async () => {
    fetchUsersDirectoryMock.mockRejectedValueOnce(new Error("directory down"));
    fetchDocumentVersionMock.mockResolvedValueOnce(versionState());
    const { wrapper } = await mountDetail();
    expect(wrapper.find("[data-testid=document-header-title]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=assignments-directory-error]").text()).toContain("Benutzerverzeichnis");
    expect(wrapper.find("[data-testid=assignments-readonly]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=assignments-form]").exists()).toBe(false);
    expect(wrapper.text()).toContain("Benutzer nicht verfügbar");
  });

  it("preserves unavailable assigned users in display labels", async () => {
    const { wrapper } = await mountDetail();
    expect(wrapper.text()).toContain("Benutzer nicht verfügbar");
    expect(wrapper.text()).not.toContain("user-missing");
  });

  it("submits complete assignment arrays with encoded path and exact If-Match", async () => {
    mutateMock.mockResolvedValueOnce(
      versionState({
        etag: "evt-2",
        state: {
          assignments: { editors: ["user-active"], reviewers: [], approvers: [] },
        },
      }),
    );
    const { wrapper } = await mountDetail("/documents/DOC%2F1?version=2");
    await wrapper.get("[data-testid=assignments-form]").trigger("submit");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith({
      method: "POST",
      path: "/documents/versions/DOC%2F1/2/workflow/assign-roles",
      ifMatch: "evt-1",
      body: {
        json: {
          editors: ["user-active", "user-missing"],
          reviewers: [],
          approvers: [],
        },
      },
    });
    expect(wrapper.find("[data-testid=assignments-alert]").text()).toContain("gespeichert");
  });

  it("guards assignment double submit while pending", async () => {
    let resolveMutate: (value: unknown) => void = () => undefined;
    const pending = new Promise((resolve) => {
      resolveMutate = resolve;
    });
    mutateMock.mockImplementationOnce(() => pending);

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=assignments-form]").trigger("submit");
    await wrapper.get("[data-testid=assignments-form]").trigger("submit");
    expect(mutateMock).toHaveBeenCalledTimes(1);

    resolveMutate(versionState({ etag: "evt-2" }));
    await flushPromises();
  });

  it("atomically replaces etag and allowed_actions after success", async () => {
    mutateMock.mockResolvedValueOnce(
      versionState({
        etag: "evt-readonly",
        allowed_actions: [],
        available_actions: ["assign_roles"],
      }),
    );
    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=assignments-form]").trigger("submit");
    await flushPromises();

    expect(wrapper.find("[data-testid=assignments-readonly]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=assignments-form]").exists()).toBe(false);

    mutateMock.mockClear();
    await wrapper.get("[data-testid=assignments-readonly]").trigger("click");
    await flushPromises();
    expect(mutateMock).not.toHaveBeenCalled();
  });

  it("preserves selections on conflict and shows deferred handling message", async () => {
    const { MutationClientError } = await import("../../api/mutationClient");
    mutateMock.mockRejectedValueOnce(new MutationClientError("conflict", "conflict", 409));
    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=assignments-form]").trigger("submit");
    await flushPromises();

    expect(wrapper.find("[data-testid=assignments-alert]").text()).toContain("späteren Schritt");
    expect(wrapper.find("[data-testid=assignments-editors]").exists()).toBe(true);
  });

  it("preserves selections on precondition required", async () => {
    const { MutationClientError } = await import("../../api/mutationClient");
    mutateMock.mockRejectedValueOnce(
      new MutationClientError("precondition", "precondition_required", 428),
    );
    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=assignments-form]").trigger("submit");
    await flushPromises();

    expect(wrapper.find("[data-testid=assignments-alert]").text()).toContain("späteren Schritt");
    expect(wrapper.find("[data-testid=assignments-editors]").exists()).toBe(true);
  });

  it("does not show raw status tokens in the header", async () => {
    fetchDocumentVersionMock.mockResolvedValueOnce(
      versionState({ state: { status: "CUSTOM_STATE" } }),
    );
    const { wrapper } = await mountDetail();
    expect(wrapper.find("[data-testid=document-header-status]").text()).toBe("Unbekannter Status");
    expect(wrapper.text()).not.toContain("CUSTOM_STATE");
  });

  it.each([
    [401, "angemeldet"],
    [403, "nicht erlaubt"],
    [404, "nicht gefunden"],
    [413, "zu groß"],
    [422, "ungültig"],
    [428, "späteren Schritt"],
    [501, "nicht verfügbar"],
    [503, "nicht erreichbar"],
  ])("maps detail load HTTP %i to localized message without raw server text", async (status, snippet) => {
    fetchDocumentVersionMock.mockRejectedValueOnce(new ApiTransportError("fail", status, null));
    const { wrapper } = await mountDetail();
    const alert = wrapper.find("[data-testid=document-detail-error]");
    expect(alert.exists()).toBe(true);
    expect(alert.text()).toContain(snippet);
    expect(alert.text()).not.toContain("fail");
  });

  it("uses exact GET transport path for version history without Authorization", async () => {
    const fetchSpy = vi.fn(
      async () =>
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    try {
      const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
      await actual.fetchDocumentVersionHistory("DOC-1", 2);
      expect(fetchSpy).toHaveBeenCalled();
      const firstCall = fetchSpy.mock.calls[0] as unknown as [RequestInfo | URL, RequestInit?];
      const url = String(firstCall[0]);
      expect(url).toContain(`${apiBasePrefix()}/documents/versions/DOC-1/2/history`);
      const init = firstCall[1];
      expect(new Headers(init?.headers).has("Authorization")).toBe(false);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("shows overview by default and switches to history tab with deep link", async () => {
    const { wrapper, router } = await mountDetail("/documents/DOC-1?version=2&section=history");
    await flushPromises();
    expect(wrapper.find("[data-testid=document-detail-tab-overview]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=document-detail-history-panel]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=assignments-form]").exists()).toBe(false);
    expect(fetchDocumentVersionHistoryMock).toHaveBeenCalledWith("DOC-1", 2);
    expect(router.currentRoute.value.query).toEqual({ version: "2", section: "history" });
  });

  it("falls back invalid section to overview in route query", async () => {
    const { wrapper, router } = await mountDetail("/documents/DOC-1?version=2&section=audit");
    await vi.waitUntil(
      () => router.currentRoute.value.query.section === undefined,
      { timeout: 2000 },
    );
    await flushPromises();
    expect(wrapper.find("[data-testid=document-detail-history-panel]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=assignments-form]").exists()).toBe(true);
    expect(router.currentRoute.value.query).toEqual({ version: "2" });
  });

  it("reloads detail and history exactly once per real connection recovery", async () => {
    const { wrapper, router } = await mountDetail("/documents/DOC-1?version=2&section=history");
    await flushPromises();
    fetchDocumentVersionMock.mockClear();
    fetchDocumentVersionHistoryMock.mockClear();
    const queryBefore = { ...router.currentRoute.value.query };
    __setBootstrapBannerForTest("offline");
    await flushPromises();
    __setBootstrapBannerForTest("restored");
    await flushPromises();
    expect(fetchDocumentVersionMock).toHaveBeenCalledTimes(1);
    expect(fetchDocumentVersionMock).toHaveBeenCalledWith("DOC-1", 2);
    expect(fetchDocumentVersionHistoryMock).toHaveBeenCalledTimes(1);
    expect(fetchDocumentVersionHistoryMock).toHaveBeenCalledWith("DOC-1", 2);
    expect(router.currentRoute.value.query).toEqual(queryBefore);
    expect(wrapper.find("[data-testid=document-detail-panel-history]").exists()).toBe(true);
  });

  it("does not reload detail or history when restored without prior offline or reconnecting", async () => {
    const { router } = await mountDetail("/documents/DOC-1?version=2&section=history");
    await flushPromises();
    await router.isReady();
    fetchDocumentVersionMock.mockClear();
    fetchDocumentVersionHistoryMock.mockClear();
    __setBootstrapBannerForTest("restored");
    await flushPromises();
    expect(fetchDocumentVersionMock).not.toHaveBeenCalled();
    expect(fetchDocumentVersionHistoryMock).not.toHaveBeenCalled();
  });

  it("exposes accessible tablist, tabs, and tabpanels with linked ids", async () => {
    const { wrapper } = await mountDetail("/documents/DOC-1?version=2");
    const tablist = wrapper.get("[data-testid=document-detail-tabs]");
    const overviewTab = wrapper.get("[data-testid=document-detail-tab-overview]");
    const historyTab = wrapper.get("[data-testid=document-detail-tab-history]");

    expect(tablist.attributes("role")).toBe("tablist");
    expect(tablist.attributes("aria-label")).toBe("Dokumentbereiche");

    expect(overviewTab.attributes("id")).toBe("document-detail-tab-overview");
    expect(historyTab.attributes("id")).toBe("document-detail-tab-history");
    expect(overviewTab.attributes("aria-controls")).toBe("document-detail-panel-overview");
    expect(historyTab.attributes("aria-controls")).toBe("document-detail-panel-history");

    expect(overviewTab.attributes("aria-selected")).toBe("true");
    expect(historyTab.attributes("aria-selected")).toBe("false");
    const overviewPanel = wrapper.get("#document-detail-panel-overview");
    expect(overviewPanel.attributes("role")).toBe("tabpanel");
    expect(overviewPanel.attributes("aria-labelledby")).toBe("document-detail-tab-overview");

    await historyTab.trigger("click");
    await flushPromises();
    await vi.waitUntil(() => wrapper.find("#document-detail-panel-history").exists());
    const historyTabActive = wrapper.get("[data-testid=document-detail-tab-history]");
    const overviewTabAfterHistory = wrapper.get("[data-testid=document-detail-tab-overview]");
    expect(historyTabActive.attributes("aria-selected")).toBe("true");
    expect(overviewTabAfterHistory.attributes("aria-selected")).toBe("false");
    const historyPanel = wrapper.get("#document-detail-panel-history");
    expect(historyPanel.attributes("role")).toBe("tabpanel");
    expect(historyPanel.attributes("aria-labelledby")).toBe("document-detail-tab-history");
    expect(historyTab.attributes("aria-controls")).toBe("document-detail-panel-history");

    await overviewTabAfterHistory.trigger("click");
    await flushPromises();
    await vi.waitUntil(() => wrapper.find("#document-detail-panel-overview").exists());
    const overviewTabActive = wrapper.get("[data-testid=document-detail-tab-overview]");
    const historyTabAfterOverview = wrapper.get("[data-testid=document-detail-tab-history]");
    expect(overviewTabActive.attributes("aria-selected")).toBe("true");
    expect(historyTabAfterOverview.attributes("aria-selected")).toBe("false");
    expect(wrapper.get("#document-detail-panel-overview").attributes("aria-labelledby")).toBe(
      "document-detail-tab-overview",
    );
  });

  it("does not flash history from previous document after route change", async () => {
    fetchDocumentVersionHistoryMock.mockImplementation(async (docId: string) => {
      if (docId === "DOC-1") {
        await new Promise((resolve) => setTimeout(resolve, 20));
        return [
          {
            occurred_at: "2026-01-15T10:30:00Z",
            event_type: "comment_added",
            actor_user_id: null,
            summary: "Stale history",
          },
        ];
      }
      return [
        {
          occurred_at: "2026-01-16T10:30:00Z",
          event_type: "comment_added",
          actor_user_id: null,
          summary: "Fresh history",
        },
      ];
    });
    const { wrapper, router } = await mountDetail("/documents/DOC-1?version=1&section=history");
    await wrapper.get("[data-testid=document-detail-tab-history]").trigger("click");
    await flushPromises();
    await router.replace({ path: "/documents/DOC-2", query: { version: "1", section: "history" } });
    fetchDocumentVersionMock.mockResolvedValueOnce(
      versionState({ state: { document_id: "DOC-2", version: 1, title: "Doc 2" } }),
    );
    await flushPromises();
    expect(wrapper.text()).not.toContain("Stale history");
    expect(wrapper.text()).toContain("Fresh history");
  });
});
