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

import type { PageViewport } from "pdfjs-dist";
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
const getDocumentMock = vi.hoisted(() => vi.fn());
const getPageMock = vi.hoisted(() => vi.fn());

vi.mock("pdfjs-dist/legacy/build/pdf.mjs", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: getDocumentMock,
}));

vi.mock("pdfjs-dist/legacy/build/pdf.worker.min.mjs?url", () => ({
  default: "mock-pdf-legacy-worker-url",
}));

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
let resizeObserverCallback: (() => void) | null = null;

const PAGE_WIDTH = 612;
const PAGE_HEIGHT = 792;

function createMockViewport(scale: number): PageViewport {
  return {
    width: PAGE_WIDTH * scale,
    height: PAGE_HEIGHT * scale,
    convertToPdfPoint: (x: number, y: number) => [x / scale, (PAGE_HEIGHT * scale - y) / scale],
    convertToViewportPoint: (x: number, y: number) => [x * scale, PAGE_HEIGHT * scale - y * scale],
  } as PageViewport;
}

type PdfDocMock = {
  numPages: number;
  getPage: typeof getPageMock;
};

type RenderTaskPlan = {
  deferred: ReturnType<typeof createDeferred<void>>;
  cancel: ReturnType<typeof vi.fn>;
};

type PagePlan = {
  pageDeferred: ReturnType<typeof createDeferred<void>>;
  renderTasks: RenderTaskPlan[];
  createRenderTask: () => RenderTaskPlan;
};

type DocumentPlan = {
  url: string;
  numPages: number;
  documentDeferred: ReturnType<typeof createDeferred<PdfDocMock>>;
  destroy: ReturnType<typeof vi.fn>;
  pagePlan: PagePlan;
  pdfDoc: PdfDocMock;
};

type PdfJsHarness = {
  viewportCalls: Array<{ scale: number; rotation: number }>;
  plans: Map<string, DocumentPlan>;
  defaultUrl: string;
  createPlan: (url: string, options?: { numPages?: number }) => DocumentPlan;
  resolveDocument: (url?: string) => void;
  resolvePage: (url?: string) => void;
  resolveRender: (url?: string, taskIndex?: number) => void;
  rejectRender: (url: string, error: Error, taskIndex?: number) => void;
  resolveAll: (url?: string) => void;
  latestRenderTask: (url?: string) => RenderTaskPlan | undefined;
  renderTaskAt: (url: string, taskIndex: number) => RenderTaskPlan | undefined;
};

let activePlanUrl: string | null = null;
let harness: PdfJsHarness;

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function createPagePlan(): PagePlan {
  const renderTasks: RenderTaskPlan[] = [];
  const pageDeferred = createDeferred<void>();
  return {
    pageDeferred,
    renderTasks,
    createRenderTask: () => {
      const deferred = createDeferred<void>();
      const task = {
        deferred,
        cancel: vi.fn(() => {
          deferred.reject(new Error("Rendering cancelled"));
        }),
      };
      renderTasks.push(task);
      return task;
    },
  };
}

function createDocumentPlan(url: string, numPages = 3): DocumentPlan {
  const pagePlan = createPagePlan();
  const pdfDoc: PdfDocMock = {
    numPages,
    getPage: getPageMock,
  };
  return {
    url,
    numPages,
    documentDeferred: createDeferred<PdfDocMock>(),
    destroy: vi.fn(),
    pagePlan,
    pdfDoc,
  };
}

function planForUrl(url?: string): DocumentPlan {
  const resolvedUrl = url ?? harness.defaultUrl;
  const plan = harness.plans.get(resolvedUrl);
  if (!plan) {
    throw new Error(`missing document plan for ${resolvedUrl}`);
  }
  return plan;
}

function setupPdfJsMocks(options?: {
  numPages?: number;
  immediate?: boolean;
  defaultUrl?: string;
}): PdfJsHarness {
  getDocumentMock.mockReset();
  getPageMock.mockReset();
  activePlanUrl = null;

  const viewportCalls: Array<{ scale: number; rotation: number }> = [];
  const plans = new Map<string, DocumentPlan>();
  const defaultUrl = options?.defaultUrl ?? "blob:default";

  const createPlan = (url: string, planOptions?: { numPages?: number }) => {
    const plan = createDocumentPlan(url, planOptions?.numPages ?? options?.numPages ?? 3);
    plans.set(url, plan);
    return plan;
  };

  createPlan(defaultUrl);

  getDocumentMock.mockImplementation(({ url }: { url: string }) => {
    if (!plans.has(url)) {
      createPlan(url);
    }
    const plan = plans.get(url)!;
    activePlanUrl = url;
    return {
      promise: plan.documentDeferred.promise,
      destroy: plan.destroy,
    };
  });

  getPageMock.mockImplementation(async () => {
    const plan = activePlanUrl ? plans.get(activePlanUrl) : undefined;
    if (!plan) {
      throw new Error("pdf.js getPage called without active document plan");
    }
    await plan.pagePlan.pageDeferred.promise;
    return {
      getViewport: ({ scale, rotation }: { scale: number; rotation: number }) => {
        viewportCalls.push({ scale, rotation });
        return createMockViewport(scale);
      },
      render: () => {
        const task = plan.pagePlan.createRenderTask();
        return {
          promise: task.deferred.promise,
          cancel: task.cancel,
        };
      },
    };
  });

  const resolveDocument = (url = defaultUrl) => {
    const plan = planForUrl(url);
    plan.documentDeferred.resolve(plan.pdfDoc);
  };

  const resolvePage = (url = defaultUrl) => {
    planForUrl(url).pagePlan.pageDeferred.resolve();
  };

  const resolveRender = (url = defaultUrl, taskIndex = -1) => {
    const plan = planForUrl(url);
    const task =
      taskIndex >= 0 ? plan.pagePlan.renderTasks[taskIndex] : plan.pagePlan.renderTasks.at(-1);
    task?.deferred.resolve();
  };

  const rejectRender = (url: string, error: Error, taskIndex = -1) => {
    const plan = planForUrl(url);
    const task =
      taskIndex >= 0 ? plan.pagePlan.renderTasks[taskIndex] : plan.pagePlan.renderTasks.at(-1);
    task?.deferred.reject(error);
  };

  const resolveAll = (url = defaultUrl) => {
    resolveDocument(url);
    resolvePage(url);
    resolveRender(url);
  };

  const latestRenderTask = (url = defaultUrl) => planForUrl(url).pagePlan.renderTasks.at(-1);

  const renderTaskAt = (url: string, taskIndex: number) =>
    planForUrl(url).pagePlan.renderTasks[taskIndex];

  harness = {
    viewportCalls,
    plans,
    defaultUrl,
    createPlan,
    resolveDocument,
    resolvePage,
    resolveRender,
    rejectRender,
    resolveAll,
    latestRenderTask,
    renderTaskAt,
  };

  if (options?.immediate ?? true) {
    resolveAll(defaultUrl);
  }

  return harness;
}

function stubBrowserApis(): void {
  urlRevokeMock = vi.fn();
  urlCreateMock = vi.fn((blob: Blob) => `blob:${blob.size}`);
  vi.stubGlobal("URL", {
    createObjectURL: urlCreateMock,
    revokeObjectURL: urlRevokeMock,
  });

  class ResizeObserverStub {
    constructor(callback: ResizeObserverCallback) {
      resizeObserverCallback = () => callback([], this as ResizeObserver);
    }
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {
      resizeObserverCallback = null;
    }
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);

  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    drawImage: vi.fn(),
  })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
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
    signature_required: false,
    assignment_kind: null,
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
    signature_required: false,
    assignment_kind: null,
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

function setStageDimensions(
  wrapper: ReturnType<typeof mount>,
  options?: { stageWidth?: number; stageHeight?: number },
): void {
  const stage = wrapper.find("[data-testid=pdf-viewer-stage]");
  if (!stage.exists()) {
    return;
  }
  Object.defineProperty(stage.element, "clientWidth", {
    configurable: true,
    value: options?.stageWidth ?? 800,
  });
  Object.defineProperty(stage.element, "clientHeight", {
    configurable: true,
    value: options?.stageHeight ?? 600,
  });
}

function mountPdfViewer(
  previewUrl: string | null = "blob:1234",
  options?: {
    stageWidth?: number;
    stageHeight?: number;
    loading?: boolean;
    error?: boolean;
  },
) {
  const wrapper = mount(PdfViewer, {
    props: {
      previewUrl,
      loading: options?.loading ?? false,
      error: options?.error ?? false,
    },
    global: {
      plugins: [vuetify, i18n],
    },
    attachTo: document.body,
  });
  setStageDimensions(wrapper, options);
  return wrapper;
}

async function readyPdfViewer(
  wrapper: ReturnType<typeof mountPdfViewer>,
  mocks: PdfJsHarness,
  url?: string,
) {
  await flushPromises();
  mocks.resolveDocument(url);
  await flushPromises();
  mocks.resolvePage(url);
  await flushPromises();
  mocks.resolveRender(url);
  await flushPromises();
  await vi.waitFor(() => {
    expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
      "ready",
    );
  });
}

describe("PdfViewer", () => {
  beforeEach(() => {
    stubBrowserApis();
    setupPdfJsMocks({ defaultUrl: "blob:1234" });
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    resizeObserverCallback = null;
  });

  it("renders frame, stage, and canvas via previewUrl without fetch or ObjectURL side effects", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const mocks = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:preview-test" });
    const wrapper = mountPdfViewer("blob:preview-test");
    await readyPdfViewer(wrapper, mocks, "blob:preview-test");
    expect(getDocumentMock).toHaveBeenCalledWith({ url: "blob:preview-test" });
    expect(wrapper.find("[data-testid=pdf-viewer-frame]").exists()).toBe(true);
    expect(wrapper.find("iframe").exists()).toBe(false);
    const canvas = wrapper.get("[data-testid=pdf-viewer-canvas]").element as HTMLCanvasElement;
    expect(canvas.getAttribute("data-rendered-page")).toBe("1");
    expect(canvas.width).toBeGreaterThan(0);
    expect(canvas.height).toBeGreaterThan(0);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(urlCreateMock).not.toHaveBeenCalled();
    expect(urlRevokeMock).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("becomes ready only after document, page, and render promises resolve", async () => {
    const mocks = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:ready-test" });
    const wrapper = mountPdfViewer("blob:ready-test");
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
      "loading",
    );
    mocks.resolveDocument("blob:ready-test");
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
      "loading",
    );
    mocks.resolvePage("blob:ready-test");
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
      "loading",
    );
    mocks.resolveRender("blob:ready-test");
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
        "ready",
      );
    });
    const canvas = wrapper.get("[data-testid=pdf-viewer-canvas]").element as HTMLCanvasElement;
    expect(canvas.getAttribute("data-rendered-fit")).toBe("none");
    expect(canvas.getAttribute("data-rendered-scale")).toBe("100");
    wrapper.unmount();
  });

  it("keeps next/input disabled and emits nothing before pageCount is known", async () => {
    const mocks = setupPdfJsMocks({
      numPages: 2,
      immediate: false,
      defaultUrl: "blob:pending-page",
    });
    const wrapper = mountPdfViewer("blob:pending-page");
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-next-page]").attributes("disabled")).toBeDefined();
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).disabled).toBe(
      true,
    );
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    expect(wrapper.emitted("page-change")).toBeUndefined();
    await readyPdfViewer(wrapper, mocks, "blob:pending-page");
    wrapper.unmount();
  });

  it("clamps page navigation, disables boundaries, and emits validated page-change", async () => {
    const mocks = setupPdfJsMocks({ numPages: 2, defaultUrl: "blob:page-test" });
    const wrapper = mountPdfViewer("blob:page-test");
    await readyPdfViewer(wrapper, mocks, "blob:page-test");

    expect(wrapper.get("[data-testid=pdf-prev-page]").attributes("disabled")).toBeDefined();
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:page-test");
    await flushPromises();
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).value).toBe(
      "2",
    );
    expect(wrapper.emitted("page-change")?.at(-1)).toEqual([2]);
    expect(wrapper.get("[data-testid=pdf-next-page]").attributes("disabled")).toBeDefined();

    const input = wrapper.get("[data-testid=pdf-page-input]");
    expect((input.element as HTMLInputElement).max).toBe("2");
    await input.setValue("9");
    await flushPromises();
    mocks.resolveAll("blob:page-test");
    await flushPromises();
    expect((input.element as HTMLInputElement).value).toBe("2");
    wrapper.unmount();
  });

  it("applies zoom and fit modes through pdf.js viewport scale against stable stage size", async () => {
    const mocks = setupPdfJsMocks({ defaultUrl: "blob:zoom-test" });
    const wrapper = mountPdfViewer("blob:zoom-test", { stageWidth: 612, stageHeight: 792 });
    await readyPdfViewer(wrapper, mocks, "blob:zoom-test");

    await wrapper.get("[data-testid=pdf-zoom-in]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:zoom-test");
    await flushPromises();
    expect(mocks.viewportCalls.at(-1)?.scale).toBeCloseTo(1.25, 5);
    expect(wrapper.get("[data-testid=pdf-zoom-level]").text()).toContain("125");
    const zoomedCanvas = wrapper.get("[data-testid=pdf-viewer-canvas]").element as HTMLCanvasElement;
    expect(zoomedCanvas.width).toBeGreaterThan(PAGE_WIDTH);

    await wrapper.get("[data-testid=pdf-fit-width]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:zoom-test");
    await flushPromises();
    expect(mocks.viewportCalls.at(-1)?.scale).toBeCloseTo(1, 5);

    await wrapper.get("[data-testid=pdf-fit-page]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:zoom-test");
    await flushPromises();
    const fitPageScale = mocks.viewportCalls.at(-1)?.scale ?? 0;
    expect(fitPageScale).toBeCloseTo(Math.min(612 / PAGE_WIDTH, 792 / PAGE_HEIGHT), 5);
    expect(
      wrapper.get("[data-testid=pdf-viewer-canvas]").element.getAttribute("data-rendered-fit"),
    ).toBe("page");
    wrapper.unmount();
  });

  it("computes distinct fit-width and fit-page scales for non-square stage ratios", async () => {
    const mocks = setupPdfJsMocks({ defaultUrl: "blob:aspect-test" });
    const wrapper = mountPdfViewer("blob:aspect-test", { stageWidth: 480, stageHeight: 500 });
    await readyPdfViewer(wrapper, mocks, "blob:aspect-test");

    await wrapper.get("[data-testid=pdf-fit-width]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:aspect-test");
    await flushPromises();
    const fitWidthScale = mocks.viewportCalls.at(-1)?.scale ?? 0;
    expect(fitWidthScale).toBeCloseTo(480 / PAGE_WIDTH, 5);

    await wrapper.get("[data-testid=pdf-fit-page]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:aspect-test");
    await flushPromises();
    const fitPageScale = mocks.viewportCalls.at(-1)?.scale ?? 0;
    expect(fitPageScale).toBeCloseTo(Math.min(480 / PAGE_WIDTH, 500 / PAGE_HEIGHT), 5);
    expect(fitPageScale).toBeLessThan(fitWidthScale);
    wrapper.unmount();
  });

  it("does not compress canvas width and keeps a stable frame height contract", async () => {
    const mocks = setupPdfJsMocks({ defaultUrl: "blob:css-test" });
    const wrapper = mountPdfViewer("blob:css-test", { stageWidth: 400, stageHeight: 300 });
    await readyPdfViewer(wrapper, mocks, "blob:css-test");
    const canvas = wrapper.get("[data-testid=pdf-viewer-canvas]").element as HTMLCanvasElement;
    const frame = wrapper.get("[data-testid=pdf-viewer-frame]").element as HTMLElement;
    expect(canvas.width).toBe(PAGE_WIDTH);
    expect(getComputedStyle(canvas).maxWidth).not.toBe("100%");
    expect(frame.className).toContain("pdf-viewer__frame");

    await wrapper.get("[data-testid=pdf-fit-width]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:css-test");
    await flushPromises();
    expect(canvas.width).toBe(400);
    wrapper.unmount();
  });

  it("re-renders on resize only for active fit modes and only when dimensions change", async () => {
    const mocks = setupPdfJsMocks({ defaultUrl: "blob:resize-test" });
    const wrapper = mountPdfViewer("blob:resize-test", { stageWidth: 400, stageHeight: 300 });
    await readyPdfViewer(wrapper, mocks, "blob:resize-test");
    const callsBeforeResize = getPageMock.mock.calls.length;

    resizeObserverCallback?.();
    await flushPromises();
    expect(getPageMock.mock.calls.length).toBe(callsBeforeResize);

    await wrapper.get("[data-testid=pdf-fit-width]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:resize-test");
    await flushPromises();
    const callsAfterFit = getPageMock.mock.calls.length;
    const widthBeforePendingResize = (
      wrapper.get("[data-testid=pdf-viewer-canvas]").element as HTMLCanvasElement
    ).width;

    setStageDimensions(wrapper, { stageWidth: 400, stageHeight: 300 });
    resizeObserverCallback?.();
    await flushPromises();
    expect(getPageMock.mock.calls.length).toBe(callsAfterFit);

    setStageDimensions(wrapper, { stageWidth: 500, stageHeight: 300 });
    resizeObserverCallback?.();
    const canvasDuringPendingResize = wrapper.get(
      "[data-testid=pdf-viewer-canvas]",
    ).element as HTMLCanvasElement;
    expect(canvasDuringPendingResize.width).toBe(widthBeforePendingResize);
    await flushPromises();
    mocks.resolveAll("blob:resize-test");
    await flushPromises();
    expect(getPageMock.mock.calls.length).toBeGreaterThan(callsAfterFit);
    expect(mocks.viewportCalls.at(-1)?.scale).toBeCloseTo(500 / PAGE_WIDTH, 5);
    expect(canvasDuringPendingResize.width).toBe(500);

    await wrapper.get("[data-testid=pdf-fit-page]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:resize-test");
    await flushPromises();
    const callsAfterPageFit = getPageMock.mock.calls.length;
    setStageDimensions(wrapper, { stageWidth: 500, stageHeight: 400 });
    resizeObserverCallback?.();
    await flushPromises();
    mocks.resolveAll("blob:resize-test");
    await flushPromises();
    expect(getPageMock.mock.calls.length).toBeGreaterThan(callsAfterPageFit);
    expect(mocks.viewportCalls.at(-1)?.scale).toBeCloseTo(
      Math.min(500 / PAGE_WIDTH, 400 / PAGE_HEIGHT),
      5,
    );
    wrapper.unmount();
  });

  it("invalidates stale document/page/render completions across URL and external state changes", async () => {
    const slow = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:slow" });
    const wrapper = mountPdfViewer("blob:slow");
    await flushPromises();
    slow.createPlan("blob:fast");
    await wrapper.setProps({ previewUrl: "blob:fast" });
    await flushPromises();
    slow.resolveAll("blob:slow");
    await flushPromises();
    expect(getDocumentMock).toHaveBeenLastCalledWith({ url: "blob:fast" });
    expect(slow.plans.get("blob:slow")?.destroy).toHaveBeenCalled();
    expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).not.toBe(
      "error",
    );

    const pendingPage = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:page-pending" });
    await wrapper.setProps({ previewUrl: "blob:page-pending" });
    await flushPromises();
    pendingPage.resolveDocument("blob:page-pending");
    await flushPromises();
    await wrapper.setProps({ loading: true });
    await flushPromises();
    pendingPage.resolvePage("blob:page-pending");
    pendingPage.resolveRender("blob:page-pending");
    await flushPromises();
    expect(wrapper.find("[data-testid=pdf-viewer-stage]").exists()).toBe(false);

    await wrapper.setProps({ loading: false, previewUrl: "blob:page-pending" });
    await flushPromises();
    await readyPdfViewer(wrapper, pendingPage, "blob:page-pending");
    wrapper.unmount();
  });

  it("destroys cache on URL change before stale document resolves", async () => {
    const slow = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:slow" });
    const wrapper = mountPdfViewer("blob:slow");
    await flushPromises();
    slow.createPlan("blob:fast");
    await wrapper.setProps({ previewUrl: "blob:fast" });
    await flushPromises();
    slow.resolveAll("blob:slow");
    await flushPromises();
    expect(getDocumentMock).toHaveBeenNthCalledWith(1, { url: "blob:slow" });
    expect(getDocumentMock).toHaveBeenNthCalledWith(2, { url: "blob:fast" });
    expect(slow.plans.get("blob:slow")?.destroy).toHaveBeenCalled();
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).value).toBe(
      "1",
    );
    wrapper.unmount();
  });

  it("keeps active render B cancellable after stale render A completes", async () => {
    const mocks = setupPdfJsMocks({ numPages: 2, immediate: false, defaultUrl: "blob:overlap" });
    const wrapper = mountPdfViewer("blob:overlap");
    await flushPromises();
    mocks.resolveDocument("blob:overlap");
    mocks.resolvePage("blob:overlap");
    await flushPromises();
    const taskA = mocks.renderTaskAt("blob:overlap", 0);
    expect(taskA).toBeDefined();

    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    await flushPromises();
    const taskB = mocks.renderTaskAt("blob:overlap", 1);
    expect(taskB).toBeDefined();
    expect(taskA?.cancel).toHaveBeenCalled();

    taskA?.deferred.resolve();
    await flushPromises();
    expect(taskB?.cancel).not.toHaveBeenCalled();

    wrapper.unmount();
    expect(taskB?.cancel).toHaveBeenCalled();
  });

  it("ignores stale render A rejection while render B stays active until invalidation", async () => {
    const mocks = setupPdfJsMocks({ numPages: 2, immediate: false, defaultUrl: "blob:reject-overlap" });
    const wrapper = mountPdfViewer("blob:reject-overlap");
    await flushPromises();
    mocks.resolveDocument("blob:reject-overlap");
    mocks.resolvePage("blob:reject-overlap");
    await flushPromises();
    const taskA = mocks.renderTaskAt("blob:reject-overlap", 0);
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    await flushPromises();
    const taskB = mocks.renderTaskAt("blob:reject-overlap", 1);

    taskA?.deferred.reject(new Error("stale render failed"));
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
      "loading",
    );

    await wrapper.setProps({ previewUrl: null });
    await flushPromises();
    expect(taskB?.cancel).toHaveBeenCalled();
    wrapper.unmount();
  });

  it("cancels the active render task directly on unmount", async () => {
    const rejectionHandler = vi.fn();
    const originalUnhandled = process.listeners("unhandledRejection");
    process.removeAllListeners("unhandledRejection");
    process.on("unhandledRejection", rejectionHandler);

    const mocks = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:unmount-cancel" });
    const wrapper = mountPdfViewer("blob:unmount-cancel");
    await flushPromises();
    mocks.resolveDocument("blob:unmount-cancel");
    mocks.resolvePage("blob:unmount-cancel");
    await flushPromises();
    const activeTask = mocks.latestRenderTask("blob:unmount-cancel");
    expect(activeTask).toBeDefined();
    wrapper.unmount();
    await flushPromises();
    expect(activeTask?.cancel).toHaveBeenCalled();
    expect(mocks.plans.get("blob:unmount-cancel")?.destroy).toHaveBeenCalled();
    expect(rejectionHandler).not.toHaveBeenCalled();

    process.removeAllListeners("unhandledRejection");
    for (const listener of originalUnhandled) {
      process.on("unhandledRejection", listener as NodeJS.UnhandledRejectionListener);
    }
  });

  it("consumes rejected destroy promises without unhandled rejection", async () => {
    const rejectionHandler = vi.fn();
    const originalUnhandled = process.listeners("unhandledRejection");
    process.removeAllListeners("unhandledRejection");
    process.on("unhandledRejection", rejectionHandler);

    const mocks = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:destroy-reject" });
    const sourcePlan = mocks.plans.get("blob:destroy-reject")!;
    const otherPlan = mocks.createPlan("blob:other");
    const wrapper = mountPdfViewer("blob:destroy-reject");
    await flushPromises();

    sourcePlan.destroy.mockImplementationOnce(() => Promise.reject(new Error("destroy failed")));
    await wrapper.setProps({ previewUrl: "blob:other" });
    await flushPromises();
    await flushPromises();
    expect(sourcePlan.destroy).toHaveBeenCalled();
    expect(rejectionHandler).not.toHaveBeenCalled();

    otherPlan.destroy.mockImplementationOnce(() => {
      throw new Error("sync destroy failed");
    });
    await wrapper.setProps({ previewUrl: null });
    await flushPromises();
    expect(otherPlan.destroy).toHaveBeenCalled();
    expect(rejectionHandler).not.toHaveBeenCalled();

    process.removeAllListeners("unhandledRejection");
    for (const listener of originalUnhandled) {
      process.on("unhandledRejection", listener as NodeJS.UnhandledRejectionListener);
    }
    wrapper.unmount();
  });

  it("surfaces render failures and ignores cancelled stale completions", async () => {
    const mocks = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:render-error" });
    const wrapper = mountPdfViewer("blob:render-error");
    await flushPromises();
    mocks.resolveDocument("blob:render-error");
    mocks.resolvePage("blob:render-error");
    await flushPromises();
    mocks.rejectRender("blob:render-error", new Error("render failed"));
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.get("[data-testid=pdf-viewer-stage]").attributes("data-render-state")).toBe(
        "error",
      );
    });
    wrapper.unmount();

    const stale = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:cancelled" });
    const staleWrapper = mountPdfViewer("blob:cancelled");
    await flushPromises();
    stale.resolveDocument("blob:cancelled");
    stale.resolvePage("blob:cancelled");
    await flushPromises();
    stale.createPlan("blob:next");
    await staleWrapper.setProps({ previewUrl: "blob:next" });
    await flushPromises();
    stale.resolveAll("blob:cancelled");
    await flushPromises();
    await readyPdfViewer(staleWrapper, stale, "blob:next");
    expect(staleWrapper.findAll("[data-testid=pdf-viewer-error]").length).toBe(0);
    staleWrapper.unmount();
  });

  it("invalidates synchronously when previewUrl becomes null", async () => {
    const mocks = setupPdfJsMocks({ immediate: false, defaultUrl: "blob:null-test" });
    const wrapper = mountPdfViewer("blob:null-test");
    await flushPromises();
    await wrapper.setProps({ previewUrl: null });
    await flushPromises();
    mocks.resolveAll("blob:null-test");
    await flushPromises();
    expect(wrapper.find("[data-testid=pdf-viewer-empty]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=pdf-viewer-stage]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("shows external loading, error, and empty states without frame", () => {
    const loading = mount(PdfViewer, {
      props: { previewUrl: "blob:loading", loading: true, error: false },
      global: { plugins: [vuetify, i18n] },
    });
    expect(loading.find("[data-testid=pdf-viewer-loading]").exists()).toBe(true);
    expect(loading.find("[data-testid=pdf-viewer-frame]").exists()).toBe(false);
    loading.unmount();

    const error = mount(PdfViewer, {
      props: { previewUrl: "blob:error", loading: false, error: true },
      global: { plugins: [vuetify, i18n] },
    });
    expect(error.find("[data-testid=pdf-viewer-error]").exists()).toBe(true);
    expect(error.find("[data-testid=pdf-viewer-frame]").exists()).toBe(false);
    error.unmount();

    const empty = mountPdfViewer(null);
    expect(empty.find("[data-testid=pdf-viewer-empty]").exists()).toBe(true);
    expect(empty.find("[data-testid=pdf-viewer-frame]").exists()).toBe(false);
    empty.unmount();
  });

  it("emits exactly one page reset after old URL to null/loading to new URL cycle", async () => {
    const mocks = setupPdfJsMocks({ numPages: 3, defaultUrl: "blob:cycle-old" });
    mocks.createPlan("blob:cycle-new");
    const wrapper = mountPdfViewer("blob:cycle-old");
    await readyPdfViewer(wrapper, mocks, "blob:cycle-old");

    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    await flushPromises();
    mocks.resolveAll("blob:cycle-old");
    await flushPromises();
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).value).toBe(
      "2",
    );
    const emitsAfterNavigation = wrapper.emitted("page-change")?.length ?? 0;

    await wrapper.setProps({ previewUrl: null, loading: true });
    await flushPromises();
    expect(wrapper.emitted("page-change")?.length ?? 0).toBe(emitsAfterNavigation);
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).value).toBe(
      "1",
    );

    await wrapper.setProps({ previewUrl: "blob:cycle-new", loading: false });
    await flushPromises();
    mocks.resolveAll("blob:cycle-new");
    await flushPromises();
    expect(wrapper.emitted("page-change")?.length ?? 0).toBe(emitsAfterNavigation + 1);
    expect(wrapper.emitted("page-change")?.at(-1)).toEqual([1]);
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).value).toBe(
      "1",
    );

    await wrapper.setProps({ loading: true });
    await flushPromises();
    const emitsBeforeBlockedControls = wrapper.emitted("page-change")?.length ?? 0;
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    await wrapper.get("[data-testid=pdf-page-input]").setValue("2");
    expect(wrapper.emitted("page-change")?.length ?? 0).toBe(emitsBeforeBlockedControls);
    wrapper.unmount();
  });

  it("blocks navigation and page-change emits while external loading or error is active", async () => {
    const mocks = setupPdfJsMocks({ numPages: 3, defaultUrl: "blob:external-lock" });
    const wrapper = mountPdfViewer("blob:external-lock");
    await readyPdfViewer(wrapper, mocks, "blob:external-lock");

    await wrapper.setProps({ loading: true });
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-next-page]").attributes("disabled")).toBeDefined();
    expect((wrapper.get("[data-testid=pdf-page-input]").element as HTMLInputElement).disabled).toBe(
      true,
    );
    const emitsBefore = wrapper.emitted("page-change")?.length ?? 0;
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    await wrapper.get("[data-testid=pdf-page-input]").setValue("2");
    expect(wrapper.emitted("page-change")?.length ?? 0).toBe(emitsBefore);

    await wrapper.setProps({ loading: false, error: true });
    await flushPromises();
    expect(wrapper.get("[data-testid=pdf-next-page]").attributes("disabled")).toBeDefined();
    await wrapper.get("[data-testid=pdf-next-page]").trigger("click");
    expect(wrapper.emitted("page-change")?.length ?? 0).toBe(emitsBefore);
    wrapper.unmount();
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
    setupPdfJsMocks({ defaultUrl: "blob:viewer-route" });
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
    expect(wrapper.find("[data-testid=pdf-viewer-canvas]").exists()).toBe(false);
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
    expect(wrapper.find("[data-testid=pdf-viewer-canvas]").exists()).toBe(false);
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
