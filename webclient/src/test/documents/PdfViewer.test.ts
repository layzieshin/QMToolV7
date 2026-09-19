import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, ref, watch, type PropType } from "vue";
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
import { ApiTransportError, apiBasePrefix, pdfPreviewMimeType } from "../../api/client";
import PdfViewer from "../../components/documents/PdfViewer.vue";
import { usePdfPreview } from "../../composables/usePdfPreview";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { routes } from "../../router/routes";
import DocumentDetailView from "../../views/documents/DocumentDetailView.vue";
import DocumentViewerView from "../../views/documents/DocumentViewerView.vue";

const fetchDocumentVersionMock = vi.hoisted(() => vi.fn());
const fetchDocumentArtifactsMock = vi.hoisted(() => vi.fn());
const fetchArtifactPreviewBlobMock = vi.hoisted(() => vi.fn());
const fetchUsersDirectoryMock = vi.hoisted(() => vi.fn());
const fetchWorkflowCommentsMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchDocumentVersion: fetchDocumentVersionMock,
    fetchDocumentArtifacts: fetchDocumentArtifactsMock,
    fetchArtifactPreviewBlob: fetchArtifactPreviewBlobMock,
    fetchUsersDirectory: fetchUsersDirectoryMock,
    fetchWorkflowComments: fetchWorkflowCommentsMock,
  };
});

let urlRevokeMock = vi.fn();
let urlCreateMock = vi.fn((blob: Blob) => `blob:${blob.size}`);

function stubBrowserApis(): void {
  urlRevokeMock = vi.fn();
  urlCreateMock = vi.fn((blob: Blob) => `blob:${blob.size}`);
  vi.stubGlobal("URL", {
    createObjectURL: urlCreateMock,
    revokeObjectURL: urlRevokeMock,
  });

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

function commentsDescriptor(enabled = true): ActionDescriptor {
  return {
    code: "comments",
    enabled,
    destructive: false,
    label_key: "documents.action.comments",
    requires_confirmation: false,
    requires_reason: false,
    severity: "info" as const,
  };
}

function previewDescriptor(enabled = true): ActionDescriptor {
  return {
    code: "preview",
    enabled,
    destructive: false,
    label_key: "documents.action.preview",
    requires_confirmation: false,
    requires_reason: false,
    severity: "info" as const,
  };
}

function versionState(
  overrides: {
    allowed_actions?: ActionDescriptor[];
    state?: Record<string, unknown>;
  } = {},
) {
  return {
    etag: "evt-1",
    allowed_actions: overrides.allowed_actions ?? [previewDescriptor(true)],
    available_actions: ["preview"],
    state: {
      document_id: "DOC-1",
      version: 2,
      title: "Qualitätsleitbild",
      status: "DRAFT",
      ...overrides.state,
    },
  };
}

function pdfArtifact(id = "art-pdf-1") {
  return {
    artifact_id: id,
    artifact_type: "source",
    created_at: "2026-01-15T10:00:00Z",
    document_id: "DOC-1",
    is_current: true,
    mime_type: "application/pdf",
    original_filename: "doc.pdf",
    sha256: "abc",
    size_bytes: 100,
    source_type: "upload",
    version: 2,
  };
}

function mountPdfViewer(previewUrl: string | null = "blob:1234") {
  return mount(PdfViewer, {
    props: {
      previewUrl,
      loading: false,
      error: false,
    },
    global: {
      plugins: [vuetify, i18n],
    },
  });
}

describe("PdfViewer", () => {
  beforeEach(() => {
    stubBrowserApis();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders iframe with blob URL fragments and never raw API paths", () => {
    const wrapper = mountPdfViewer("blob:preview-test");
    const frame = wrapper.get("[data-testid=pdf-viewer-frame]");
    const src = frame.attributes("src") ?? "";
    expect(src.startsWith("blob:preview-test#")).toBe(true);
    expect(src).toContain("page=1");
    expect(src).not.toContain("/api/v1");
    expect(src).not.toContain("/download");
  });

  it("updates page and zoom fragments via controls", async () => {
    const wrapper = mountPdfViewer("blob:zoom-test");
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    let src = wrapper.get("[data-testid=pdf-viewer-frame]").attributes("src") ?? "";
    expect(src).toContain("page=2");

    await wrapper.get("[data-testid=pdf-zoom-in]").trigger("click");
    src = wrapper.get("[data-testid=pdf-viewer-frame]").attributes("src") ?? "";
    expect(src).toContain("zoom=125");

    await wrapper.get("[data-testid=pdf-fit-width]").trigger("click");
    src = wrapper.get("[data-testid=pdf-viewer-frame]").attributes("src") ?? "";
    expect(src).toContain("view=FitH");

    await wrapper.get("[data-testid=pdf-fit-page]").trigger("click");
    src = wrapper.get("[data-testid=pdf-viewer-frame]").attributes("src") ?? "";
    expect(src).toContain("view=Fit");
  });

  it("emits page-change when navigating", async () => {
    const wrapper = mountPdfViewer();
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    expect(wrapper.emitted("page-change")?.[0]).toEqual([2]);
  });

  it("does not render iframe without preview URL", () => {
    const wrapper = mountPdfViewer(null);
    expect(wrapper.find("[data-testid=pdf-viewer-frame]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=pdf-viewer-empty]").exists()).toBe(true);
  });
});

const PdfPreviewHarness = defineComponent({
  name: "PdfPreviewHarness",
  props: {
    artifactId: {
      type: String as PropType<string | null>,
      default: null,
    },
  },
  setup(props) {
    const artifactRef = ref<string | null>(props.artifactId);
    watch(
      () => props.artifactId,
      (artifactId) => {
        artifactRef.value = artifactId;
      },
    );
    const state = usePdfPreview(artifactRef);
    return { artifactRef, ...state };
  },
  template: `
    <div data-testid="pdf-preview-harness">
      <span data-testid="preview-url">{{ previewUrl ?? "" }}</span>
      <span data-testid="preview-loading">{{ loading }}</span>
      <span data-testid="preview-error">{{ error ? "error" : "" }}</span>
    </div>
  `,
});

function mountPdfPreviewHarness(artifactId: string | null = "art-1") {
  return mount(PdfPreviewHarness, {
    props: { artifactId },
    global: { plugins: [vuetify, i18n] },
  });
}

describe("usePdfPreview", () => {
  beforeEach(() => {
    stubBrowserApis();
    fetchArtifactPreviewBlobMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads PDF blob, creates object URL, and revokes on unmount", async () => {
    fetchArtifactPreviewBlobMock.mockResolvedValue(
      new Blob(["%PDF"], { type: pdfPreviewMimeType() }),
    );

    const wrapper = mountPdfPreviewHarness("art-1");
    await flushPromises();
    expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("art-1");
    expect(wrapper.get("[data-testid=preview-url]").text()).toBe("blob:4");
    expect(urlCreateMock).toHaveBeenCalled();

    wrapper.unmount();
    await flushPromises();
    expect(urlRevokeMock).toHaveBeenCalled();
  });

  it("rejects empty and non-PDF MIME fail-closed without object URL", async () => {
    urlCreateMock.mockClear();
    fetchArtifactPreviewBlobMock.mockResolvedValueOnce(new Blob(["text"], { type: "" }));
    const emptyMime = mountPdfPreviewHarness("art-empty");
    await flushPromises();
    expect(emptyMime.get("[data-testid=preview-error]").text()).toBe("error");
    expect(emptyMime.get("[data-testid=preview-url]").text()).toBe("");
    expect(urlCreateMock).not.toHaveBeenCalled();

    fetchArtifactPreviewBlobMock.mockResolvedValueOnce(
      new Blob(["text"], { type: "text/plain" }),
    );
    const nonPdf = mountPdfPreviewHarness("art-bad");
    await flushPromises();
    expect(nonPdf.get("[data-testid=preview-error]").text()).toBe("error");
    expect(nonPdf.get("[data-testid=preview-url]").text()).toBe("");
  });

  it("accepts application/pdf with charset parameter", async () => {
    fetchArtifactPreviewBlobMock.mockResolvedValue(
      new Blob(["%PDF"], { type: "application/pdf; charset=binary" }),
    );
    const wrapper = mountPdfPreviewHarness("art-param");
    await flushPromises();
    expect(wrapper.get("[data-testid=preview-url]").text()).toBe("blob:4");
  });

  it("ignores stale responses after artifact change", async () => {
    let resolveSlow: (value: Blob) => void = () => undefined;
    const slow = new Promise<Blob>((resolve) => {
      resolveSlow = resolve;
    });
    fetchArtifactPreviewBlobMock
      .mockImplementationOnce(() => slow)
      .mockResolvedValueOnce(new Blob(["%PDF"], { type: pdfPreviewMimeType() }));

    const wrapper = mount(PdfPreviewHarness, {
      props: { artifactId: "art-slow" },
      global: { plugins: [vuetify, i18n] },
    });
    await wrapper.setProps({ artifactId: "art-fast" });
    await flushPromises();
    resolveSlow(new Blob(["STALE-LONGER-CONTENT"], { type: pdfPreviewMimeType() }));
    await flushPromises();
    expect(wrapper.get("[data-testid=preview-url]").text()).toBe("blob:4");
    expect(fetchArtifactPreviewBlobMock).toHaveBeenLastCalledWith("art-fast");
  });

  it("maps non-2xx preview to transport error", async () => {
    fetchArtifactPreviewBlobMock.mockRejectedValue(
      new ApiTransportError("HTTP 403", 403, null),
    );
    const wrapper = mountPdfPreviewHarness("art-denied");
    await flushPromises();
    expect(wrapper.get("[data-testid=preview-url]").text()).toBe("");
    expect(wrapper.get("[data-testid=preview-error]").text()).toBe("error");
  });
});

describe("DocumentViewerView routing", () => {
  beforeEach(() => {
    stubBrowserApis();
    fetchDocumentVersionMock.mockReset();
    fetchDocumentArtifactsMock.mockReset();
    fetchArtifactPreviewBlobMock.mockReset();
    fetchWorkflowCommentsMock.mockReset();
    fetchWorkflowCommentsMock.mockResolvedValue([]);
    fetchDocumentVersionMock.mockResolvedValue(versionState());
    fetchDocumentArtifactsMock.mockResolvedValue([pdfArtifact()]);
    fetchArtifactPreviewBlobMock.mockResolvedValue(
      new Blob(["%PDF"], { type: pdfPreviewMimeType() }),
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  async function mountViewer(path = "/documents/DOC-1/viewer?version=2") {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push(path);
    await router.isReady();
    const wrapper = mount(DocumentViewerView, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();
    return { wrapper, router };
  }

  it("does not call HTTP when route version is invalid", async () => {
    await mountViewer("/documents/DOC-1/viewer?version=abc");
    expect(fetchDocumentVersionMock).not.toHaveBeenCalled();
    expect(fetchDocumentArtifactsMock).not.toHaveBeenCalled();
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
  });

  it("does not load artifact query ID outside server list", async () => {
    fetchDocumentArtifactsMock.mockResolvedValue([
      pdfArtifact("art-listed"),
      pdfArtifact("art-second"),
    ]);
    await mountViewer("/documents/DOC-1/viewer?version=2&artifact=art-unknown");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
  });

  it("loads preview only for listed artifact query ID", async () => {
    fetchDocumentArtifactsMock.mockResolvedValue([pdfArtifact("art-listed")]);
    await mountViewer("/documents/DOC-1/viewer?version=2&artifact=art-listed");
    expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("art-listed");
  });

  it("does not fetch preview blob when preview action is absent on direct route", async () => {
    fetchDocumentVersionMock.mockResolvedValue(
      versionState({ allowed_actions: [commentsDescriptor(true)] }),
    );
    const { wrapper } = await mountViewer("/documents/DOC-1/viewer?version=2");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    expect(wrapper.find("[data-testid=pdf-viewer-frame]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=document-viewer-preview-unavailable]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=comments-create-form]").exists()).toBe(false);
  });

  it("does not fetch preview blob when preview action is disabled on direct route", async () => {
    fetchDocumentVersionMock.mockResolvedValue(
      versionState({
        allowed_actions: [commentsDescriptor(true), previewDescriptor(false)],
      }),
    );
    const { wrapper } = await mountViewer("/documents/DOC-1/viewer?version=2");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    expect(wrapper.find("[data-testid=pdf-viewer-frame]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=document-viewer-preview-unavailable]").text()).toContain(
      "nicht verfügbar",
    );
    expect(wrapper.find("[data-testid=comments-create-form]").exists()).toBe(false);
  });

  it("uses preview read path without download segment", async () => {
    const fetchSpy = vi.fn(
      async () =>
        new Response(new Blob(["%PDF"], { type: pdfPreviewMimeType() }), {
          status: 200,
          headers: { "Content-Type": pdfPreviewMimeType() },
        }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    try {
      const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
      await actual.fetchArtifactPreviewBlob("art-1");
      const firstCall = fetchSpy.mock.calls[0] as unknown as [RequestInfo | URL, RequestInit?];
      const url = String(firstCall[0]);
      expect(url).toContain(`${apiBasePrefix()}/documents/artifacts/art-1/preview`);
      expect(url).not.toContain("/download");
    } finally {
      vi.unstubAllGlobals();
      stubBrowserApis();
    }
  });
});

describe("DocumentDetailView preview link", () => {
  beforeEach(() => {
    stubBrowserApis();
    fetchDocumentVersionMock.mockReset();
    fetchUsersDirectoryMock.mockReset();
    fetchUsersDirectoryMock.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows viewer link only when preview action is enabled", async () => {
    fetchDocumentVersionMock.mockResolvedValueOnce(
      versionState({ allowed_actions: [previewDescriptor(true)] }),
    );
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1?version=2");
    await router.isReady();
    const enabled = mount(DocumentDetailView, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();
    expect(enabled.find("[data-testid=document-detail-viewer-link]").exists()).toBe(true);

    fetchDocumentVersionMock.mockResolvedValueOnce(
      versionState({ allowed_actions: [previewDescriptor(false)] }),
    );
    await router.push("/documents/DOC-1?version=2");
    const disabled = mount(DocumentDetailView, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();
    expect(disabled.find("[data-testid=document-detail-viewer-link]").exists()).toBe(false);
  });

  it("does not fetch preview blob from detail view", async () => {
    fetchDocumentVersionMock.mockResolvedValue(versionState());
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1?version=2");
    await router.isReady();
    mount(DocumentDetailView, { global: { plugins: [router, vuetify, i18n] } });
    await flushPromises();
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
  });
});
