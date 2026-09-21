import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PageViewport } from "pdfjs-dist";

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

import SignaturePlacementCanvas, {
  canonicalPlacementToViewportRect,
  clampPlacementToPage,
  DEFAULT_BLOCK_HEIGHT_RATIO,
  estimateBlockHeightPdf,
  placementFitsPage,
  pointerToSurfaceCoords,
  viewportDistanceToPdfWidth,
  viewportRectToCanonicalPlacement,
} from "../../components/signature/SignaturePlacementCanvas.vue";
import { ApiTransportError } from "../../api/client";
import SignatureWorkspaceView from "../../views/signature/SignatureWorkspaceView.vue";
import { MutationClientError, MutationWritesBlockedError } from "../../api/mutationClient";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { routes } from "../../router/routes";
import { __setBootstrapWritesAllowedForTest } from "../../state/bootstrap";

const fetchDocumentVersionMock = vi.hoisted(() => vi.fn());
const fetchDocumentArtifactsMock = vi.hoisted(() => vi.fn());
const fetchArtifactPreviewBlobMock = vi.hoisted(() => vi.fn());
const fetchActiveSignatureAssetIdMock = vi.hoisted(() => vi.fn());
const fetchActiveSignatureAssetContentMock = vi.hoisted(() => vi.fn());
const fetchSignatureTemplatesUserMock = vi.hoisted(() => vi.fn());
const fetchSignatureTemplatesGlobalMock = vi.hoisted(() => vi.fn());
const fetchSignatureTemplateSuggestionMock = vi.hoisted(() => vi.fn());
const mutateMock = vi.hoisted(() => vi.fn());
const getDocumentMock = vi.hoisted(() => vi.fn());
const destroyPdfTaskMock = vi.hoisted(() => vi.fn());
const getPageMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchDocumentVersion: fetchDocumentVersionMock,
    fetchDocumentArtifacts: fetchDocumentArtifactsMock,
    fetchArtifactPreviewBlob: fetchArtifactPreviewBlobMock,
    fetchActiveSignatureAssetId: fetchActiveSignatureAssetIdMock,
    fetchActiveSignatureAssetContent: fetchActiveSignatureAssetContentMock,
    fetchSignatureTemplatesUser: fetchSignatureTemplatesUserMock,
    fetchSignatureTemplatesGlobal: fetchSignatureTemplatesGlobalMock,
    fetchSignatureTemplateSuggestion: fetchSignatureTemplateSuggestionMock,
  };
});

vi.mock("../../api/mutationClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/mutationClient")>();
  return {
    ...actual,
    mutate: mutateMock,
  };
});

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: getDocumentMock,
}));

function createMockViewport(scale: number, skewY = 0): PageViewport {
  const pageHeight = 792;
  return {
    width: 612 * scale,
    height: pageHeight * scale,
    convertToPdfPoint: (x: number, y: number) => [
      (x + skewY) / scale,
      (pageHeight * scale - y) / scale,
    ],
    convertToViewportPoint: (x: number, y: number) => [
      (x - skewY) * scale,
      pageHeight * scale - y * scale,
    ],
  } as PageViewport;
}

function suggestedTemplate() {
  return {
    template_id: "tpl-suggested",
    name: "Suggested",
    scope: "user",
    document_type: "SOP",
    role_context: "editor",
    signature_asset_id: null,
    placement: { page_index: 0, x: 100, y: 100, target_width: 80 },
    layout: {
      show_signature: true,
      show_name: true,
      show_date: true,
      show_time: false,
      name_position: "above",
      date_position: "below",
    },
  };
}

function actionDescriptor(
  code: string,
  enabled = true,
  options: { signatureRequired?: boolean; assignmentKind?: string | null } = {},
) {
  return {
    code,
    enabled,
    destructive: false,
    label_key: `documents.action.${code}`,
    requires_confirmation: false,
    requires_reason: false,
    severity: "info" as const,
    disabled_reason: enabled ? null : "blocked",
    signature_required: options.signatureRequired ?? false,
    assignment_kind:
      options.assignmentKind !== undefined ? options.assignmentKind : null,
  };
}

function baseDetailForSignatureAction(
  actionCode: "complete_editing" | "review_accept" | "approval_accept",
  signatureAction: { signatureRequired: boolean; assignmentKind: string },
): { detail: ReturnType<typeof baseDetail>; workflowPath: string } {
  const statuses: Record<string, string> = {
    complete_editing: "IN_PROGRESS",
    review_accept: "IN_REVIEW",
    approval_accept: "IN_APPROVAL",
  };
  const workflowPaths: Record<string, string> = {
    complete_editing: "/workflow/editing-complete",
    review_accept: "/workflow/review/accept",
    approval_accept: "/workflow/approval/accept",
  };
  const detail = {
    ...baseDetail(),
    allowed_actions: [
      actionDescriptor(actionCode, true, signatureAction),
      actionDescriptor("preview"),
    ],
    available_actions: [actionCode, "preview"],
    state: {
      ...baseDetail().state,
      status: statuses[actionCode],
    },
  };
  return { detail: detail as ReturnType<typeof baseDetail>, workflowPath: workflowPaths[actionCode] };
}

function ensuredResponseFromDetail(detail: ReturnType<typeof baseDetail>) {
  return {
    etag: "evt-2",
    artifact_id: "artifact-source",
    allowed_actions: detail.allowed_actions,
    available_actions: detail.available_actions,
    state: detail.state,
  };
}

function signedPdfArtifact(
  artifactId: string,
  options?: { isCurrent?: boolean; createdAt?: string },
) {
  return {
    artifact_id: artifactId,
    artifact_type: "SIGNED_PDF",
    created_at: options?.createdAt ?? "2025-01-01T00:00:00Z",
    document_id: "DOC-1",
    is_current: options?.isCurrent ?? true,
    mime_type: "application/pdf",
    version: 1,
  };
}

function conflictDraftPreviewText(): string {
  const dialog = document.body.querySelector('[data-testid="conflict-dialog"]');
  const preview = dialog?.querySelector('[data-testid="signature-draft-preview"]');
  return preview?.textContent ?? "";
}

function baseDetail() {
  return {
    etag: "evt-1",
    allowed_actions: [
      {
        code: "complete_editing",
        enabled: true,
        destructive: false,
        label_key: "documents.action.complete_editing",
        requires_confirmation: false,
        requires_reason: false,
        severity: "info",
        disabled_reason: null,
        signature_required: true,
        assignment_kind: "editor",
      },
      {
        code: "preview",
        enabled: true,
        destructive: false,
        label_key: "documents.action.preview",
        requires_confirmation: false,
        requires_reason: false,
        severity: "info",
        disabled_reason: null,
        signature_required: false,
        assignment_kind: null,
      },
    ],
    available_actions: ["complete_editing", "preview"],
    state: {
      document_id: "DOC-1",
      version: 1,
      status: "IN_PROGRESS",
      doc_type: "SOP",
      workflow_profile_id: "signed_profile",
      workflow_profile: {
        profile_id: "signed_profile",
        signature_required_transitions: ["IN_PROGRESS->IN_REVIEW"],
        allows_content_changes: true,
        control_class: "CONTROLLED",
        four_eyes_required: false,
        label: "Signed",
        phases: [],
        release_evidence_mode: "WORKFLOW",
        requires_approvers: true,
        requires_editors: true,
        requires_reviewers: true,
      },
      assignments: { editors: [], reviewers: [], approvers: [] },
    },
  };
}

function setupPdfJsMocks(options?: { slowLoad?: boolean }) {
  destroyPdfTaskMock.mockReset();
  getPageMock.mockReset();
  getDocumentMock.mockReset();

  const viewportCalls: Array<{ scale: number; rotation: number }> = [];
  getPageMock.mockImplementation(async () => ({
    getViewport: ({ scale, rotation }: { scale: number; rotation: number }) => {
      viewportCalls.push({ scale, rotation });
      return createMockViewport(scale);
    },
    render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
  }));

  const pdfDoc = {
    numPages: 2,
    getPage: getPageMock,
  };

  let resolveDoc: (value: typeof pdfDoc) => void = () => undefined;
  const documentPromise = options?.slowLoad
    ? new Promise<typeof pdfDoc>((resolve) => {
        resolveDoc = resolve;
      })
    : Promise.resolve(pdfDoc);

  getDocumentMock.mockReturnValue({
    promise: documentPromise,
    destroy: destroyPdfTaskMock,
  });

  return { viewportCalls, resolveDoc, pdfDoc };
}

async function mountWorkspace(
  routePath = "/documents/DOC-1/signature?version=1&action=complete_editing",
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  });
  await router.push(routePath);
  await router.isReady();
  const host = document.createElement("div");
  document.body.appendChild(host);
  const wrapper = mount(SignatureWorkspaceView, {
    attachTo: host,
    global: { plugins: [i18n, vuetify, router] },
  });
  await flushPromises();
  return { wrapper, router, host };
}

function queryReauthPassword(): HTMLInputElement {
  const element = document.body.querySelector('[data-testid="reauth-password"] input');
  if (!element) {
    throw new Error("missing reauth password input");
  }
  return element as HTMLInputElement;
}

describe("Signature placement coordinates", () => {
  it("round-trips viewport and canonical coordinates at two zoom levels", () => {
    for (const scale of [1, 1.5]) {
      const viewport = createMockViewport(scale);
      const placement = { page_index: 0, x: 72, y: 72, target_width: 120 };
      const rect = canonicalPlacementToViewportRect(viewport, placement);
      const back = viewportRectToCanonicalPlacement(
        viewport,
        rect.left,
        rect.top,
        rect.width,
        rect.height,
        0,
      );
      expect(back.x).toBeCloseTo(placement.x, 3);
      expect(back.y).toBeCloseTo(placement.y, 3);
      expect(back.target_width).toBeCloseTo(placement.target_width, 3);
      expect(back.page_index).toBe(0);
    }
  });

  it("derives pdf width from full viewport distance, not only the x delta", () => {
    const viewport = {
      convertToPdfPoint: (x: number, y: number) => [x * 0.5 + y * 0.2, y * 0.1 + x * 0.05],
    } as PageViewport;
    const width = viewportDistanceToPdfWidth(viewport, 100, 40);
    const start = viewport.convertToPdfPoint(0, 40);
    const end = viewport.convertToPdfPoint(100, 40);
    const xOnly = Math.abs(end[0] - start[0]);
    expect(width).toBeCloseTo(Math.hypot(end[0] - start[0], end[1] - start[1]), 5);
    expect(width).not.toBeCloseTo(xOnly, 5);
  });

  it("clamps the full rectangle inside page bounds", () => {
    const clamped = clampPlacementToPage(
      { page_index: 5, x: 9999, y: 9999, target_width: 5000 },
      612,
      792,
      2,
    );
    expect(clamped.page_index).toBe(1);
    expect(placementFitsPage(clamped, 612, 792)).toBe(true);
    expect(clamped.x + clamped.target_width).toBeLessThanOrEqual(612);
    const blockHeight = clamped.target_width * 0.3;
    expect(clamped.y + blockHeight).toBeLessThanOrEqual(792 + 0.001);
  });
});

function stubCanvasContext(): void {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    drawImage: vi.fn(),
  })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
}

function stubPointerCapture(): void {
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  if (typeof globalThis.PointerEvent === "undefined") {
    globalThis.PointerEvent = class PointerEvent extends MouseEvent {
      readonly pointerId: number;
      constructor(type: string, params: PointerEventInit = {}) {
        super(type, params);
        this.pointerId = params.pointerId ?? 0;
      }
    } as typeof PointerEvent;
  }
}

function dispatchPointer(
  element: Element,
  type: "pointerdown" | "pointermove" | "pointerup",
  clientX: number,
  clientY: number,
  pointerId = 1,
): void {
  element.dispatchEvent(
    new PointerEvent(type, {
      clientX,
      clientY,
      pointerId,
      bubbles: true,
      cancelable: true,
    }),
  );
}

function surfaceToClient(
  stageRect: { left: number; top: number },
  scrollLeft: number,
  scrollTop: number,
  surfaceX: number,
  surfaceY: number,
): { clientX: number; clientY: number } {
  return {
    clientX: surfaceX + stageRect.left - scrollLeft,
    clientY: surfaceY + stageRect.top - scrollTop,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("SignaturePlacementCanvas", () => {
  beforeEach(() => {
    stubCanvasContext();
    stubPointerCapture();
    vi.stubGlobal(
      "matchMedia",
      (query: string) =>
        ({
          matches: false,
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
          addListener: () => undefined,
          removeListener: () => undefined,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    );
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it("renders after mount when canvasRef is available", async () => {
    const { viewportCalls } = setupPdfJsMocks();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const rendered = vi.fn();
    mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: {
        pdfUrl: "blob:pdf-1",
        placement: { page_index: 0, x: 72, y: 72, target_width: 120 },
      },
      global: { plugins: [i18n, vuetify] },
      attrs: { onRendered: rendered },
    });
    await flushPromises();
    await vi.waitFor(() => {
      expect(getDocumentMock).toHaveBeenCalledTimes(1);
    });
    const canvas = host.querySelector('[data-testid="signature-pdf-canvas"]') as HTMLCanvasElement;
    expect(canvas.width).toBeGreaterThan(0);
    expect(canvas.style.width).toBe(`${canvas.width}px`);
    expect(viewportCalls.some((call) => call.rotation === 0)).toBe(true);
    host.remove();
  });

  it("accounts for stage scroll offsets when converting pointer coordinates", () => {
    const stage = {
      getBoundingClientRect: () => ({ left: 10, top: 20, right: 0, bottom: 0, width: 0, height: 0, x: 10, y: 20, toJSON: () => ({}) }),
      scrollLeft: 40,
      scrollTop: 15,
    };
    const coords = pointerToSurfaceCoords(stage, { clientX: 50, clientY: 35 });
    expect(coords).toEqual({ x: 80, y: 30 });
  });

  it("destroys the pdf loading task on unmount", async () => {
    setupPdfJsMocks();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const wrapper = mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: {
        pdfUrl: "blob:pdf-1",
        placement: { page_index: 0, x: 72, y: 72, target_width: 120 },
      },
      global: { plugins: [i18n, vuetify] },
    });
    await flushPromises();
    wrapper.unmount();
    expect(destroyPdfTaskMock).toHaveBeenCalled();
    host.remove();
  });

  it("ignores stale pdf render completion after url replacement", async () => {
    destroyPdfTaskMock.mockReset();
    getPageMock.mockReset();
    getDocumentMock.mockReset();
    const slowDoc = { numPages: 2, getPage: getPageMock };
    let resolveSlow: (value: typeof slowDoc) => void = () => undefined;
    const slowPromise = new Promise<typeof slowDoc>((resolve) => {
      resolveSlow = resolve;
    });
    getDocumentMock.mockImplementationOnce(() => ({
      promise: slowPromise,
      destroy: destroyPdfTaskMock,
    }));
    getDocumentMock.mockImplementation(() => ({
      promise: Promise.resolve(slowDoc),
      destroy: destroyPdfTaskMock,
    }));
    getPageMock.mockImplementation(async () => ({
      getViewport: ({ scale }: { scale: number; rotation: number }) => createMockViewport(scale),
      render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
    }));

    const host = document.createElement("div");
    document.body.appendChild(host);
    const wrapper = mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: {
        pdfUrl: "blob:pdf-slow",
        placement: { page_index: 0, x: 72, y: 72, target_width: 120 },
      },
      global: { plugins: [i18n, vuetify] },
    });
    await wrapper.setProps({ pdfUrl: "blob:pdf-fast" });
    await flushPromises();
    resolveSlow(slowDoc);
    await flushPromises();
    expect(getPageMock).toHaveBeenCalledTimes(1);
    host.remove();
  });

  it("keeps canonical placement when zoom changes", async () => {
    setupPdfJsMocks();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const placement = { page_index: 0, x: 72, y: 72, target_width: 120 };
    const wrapper = mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: { pdfUrl: "blob:pdf-1", placement },
      global: { plugins: [i18n, vuetify] },
    });
    await flushPromises();
    const beforeCount = (wrapper.emitted("update:placement") ?? []).length;
    const zoomIn = wrapper.findAll("button").find((btn) => btn.text().includes("Vergrößern"));
    await zoomIn!.trigger("click");
    await flushPromises();
    const afterCount = (wrapper.emitted("update:placement") ?? []).length;
    expect(afterCount).toBe(beforeCount);
    host.remove();
  });

  it("reuses one pdf document for zoom changes and destroys on url replacement", async () => {
    setupPdfJsMocks();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const wrapper = mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: {
        pdfUrl: "blob:pdf-1",
        placement: { page_index: 0, x: 72, y: 72, target_width: 120 },
      },
      global: { plugins: [i18n, vuetify] },
    });
    await flushPromises();
    await vi.waitFor(() => expect(getDocumentMock).toHaveBeenCalledTimes(1));

    await wrapper.get('[data-testid="signature-zoom-label"]');
    const zoomIn = wrapper.findAll("button").find((btn) => btn.text().includes("Vergrößern"));
    expect(zoomIn).toBeTruthy();
    await zoomIn!.trigger("click");
    await flushPromises();
    expect(getDocumentMock).toHaveBeenCalledTimes(1);

    await wrapper.setProps({ pdfUrl: "blob:pdf-2" });
    await flushPromises();
    expect(destroyPdfTaskMock).toHaveBeenCalled();
    expect(getDocumentMock).toHaveBeenCalledTimes(2);
    host.remove();
  });

  it("emits scrolled canonical placement when dragging the mounted placement block", async () => {
    setupPdfJsMocks();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const placement = { page_index: 0, x: 72, y: 72, target_width: 120 };
    const wrapper = mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: { pdfUrl: "blob:pdf-1", placement },
      global: { plugins: [i18n, vuetify] },
    });
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="signature-placement-block"]').exists()).toBe(true);
    });

    const stage = wrapper.get('[data-testid="signature-canvas-stage"]').element as HTMLDivElement;
    const stageRect = { left: 10, top: 20, right: 0, bottom: 0, width: 0, height: 0, x: 10, y: 20, toJSON: () => ({}) };
    vi.spyOn(stage, "getBoundingClientRect").mockReturnValue(stageRect as DOMRect);
    stage.scrollLeft = 40;
    stage.scrollTop = 15;

    const viewport = createMockViewport(1);
    const blockRect = canonicalPlacementToViewportRect(viewport, placement);
    const down = surfaceToClient(stageRect, stage.scrollLeft, stage.scrollTop, blockRect.left + 4, blockRect.top + 4);
    const move = surfaceToClient(
      stageRect,
      stage.scrollLeft,
      stage.scrollTop,
      blockRect.left + 54,
      blockRect.top + 4,
    );
    const block = wrapper.get('[data-testid="signature-placement-block"]').element;
    dispatchPointer(block, "pointerdown", down.clientX, down.clientY);
    dispatchPointer(block, "pointermove", move.clientX, move.clientY);
    dispatchPointer(block, "pointerup", move.clientX, move.clientY);
    await flushPromises();

    const emissions = wrapper.emitted("update:placement") ?? [];
    expect(emissions.length).toBeGreaterThan(0);
    const updated = emissions[emissions.length - 1]![0] as typeof placement;
    expect(updated.x).toBeGreaterThan(placement.x);
    expect(placementFitsPage(updated, 612, 792)).toBe(true);
    host.remove();
  });

  it("emits resized canonical placement when dragging the mounted resize handle", async () => {
    setupPdfJsMocks();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const placement = { page_index: 0, x: 72, y: 72, target_width: 120 };
    const wrapper = mount(SignaturePlacementCanvas, {
      attachTo: host,
      props: { pdfUrl: "blob:pdf-1", placement },
      global: { plugins: [i18n, vuetify] },
    });
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="signature-resize-handle"]').exists()).toBe(true);
    });

    const stage = wrapper.get('[data-testid="signature-canvas-stage"]').element as HTMLDivElement;
    const stageRect = { left: 10, top: 20, right: 0, bottom: 0, width: 0, height: 0, x: 10, y: 20, toJSON: () => ({}) };
    vi.spyOn(stage, "getBoundingClientRect").mockReturnValue(stageRect as DOMRect);
    stage.scrollLeft = 25;
    stage.scrollTop = 10;

    const viewport = createMockViewport(1);
    const blockRect = canonicalPlacementToViewportRect(viewport, placement);
    const handle = wrapper.get('[data-testid="signature-resize-handle"]').element;
    const down = surfaceToClient(
      stageRect,
      stage.scrollLeft,
      stage.scrollTop,
      blockRect.left + blockRect.width - 2,
      blockRect.top + blockRect.height - 2,
    );
    const move = surfaceToClient(
      stageRect,
      stage.scrollLeft,
      stage.scrollTop,
      blockRect.left + blockRect.width + 48,
      blockRect.top + blockRect.height - 2,
    );
    dispatchPointer(handle, "pointerdown", down.clientX, down.clientY);
    dispatchPointer(handle, "pointermove", move.clientX, move.clientY);
    dispatchPointer(handle, "pointerup", move.clientX, move.clientY);
    await flushPromises();

    const emissions = wrapper.emitted("update:placement") ?? [];
    expect(emissions.length).toBeGreaterThan(0);
    const updated = emissions[emissions.length - 1]![0] as typeof placement;
    expect(updated.target_width).toBeGreaterThan(placement.target_width);
    const blockHeight = estimateBlockHeightPdf(updated.target_width);
    expect(blockHeight / updated.target_width).toBeCloseTo(DEFAULT_BLOCK_HEIGHT_RATIO, 5);
    expect(placementFitsPage(updated, 612, 792)).toBe(true);
    host.remove();
  });

});

describe("SignatureWorkspaceView", () => {
  beforeEach(() => {
    __setBootstrapWritesAllowedForTest(true);
    stubCanvasContext();
    stubPointerCapture();
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {
          return undefined;
        }
        unobserve() {
          return undefined;
        }
        disconnect() {
          return undefined;
        }
      },
    );
    fetchDocumentVersionMock.mockReset();
    fetchDocumentArtifactsMock.mockReset();
    fetchArtifactPreviewBlobMock.mockReset();
    fetchActiveSignatureAssetIdMock.mockReset();
    fetchActiveSignatureAssetContentMock.mockReset();
    fetchSignatureTemplatesUserMock.mockReset();
    fetchSignatureTemplatesGlobalMock.mockReset();
    fetchSignatureTemplateSuggestionMock.mockReset();
    mutateMock.mockReset();
    setupPdfJsMocks();

    fetchDocumentVersionMock.mockResolvedValue(baseDetail());
    mutateMock.mockResolvedValue({
      etag: "evt-2",
      artifact_id: "artifact-source",
      allowed_actions: baseDetail().allowed_actions,
      available_actions: baseDetail().available_actions,
      state: baseDetail().state,
    });
    fetchArtifactPreviewBlobMock.mockResolvedValue(
      new Blob(["%PDF-1.4"], { type: "application/pdf" }),
    );
    fetchActiveSignatureAssetIdMock.mockResolvedValue("asset-active");
    fetchActiveSignatureAssetContentMock.mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" }),
    );
    fetchSignatureTemplatesUserMock.mockResolvedValue([]);
    fetchSignatureTemplatesGlobalMock.mockResolvedValue([]);
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(null);
    fetchDocumentArtifactsMock.mockResolvedValue([]);

    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:source"),
      revokeObjectURL: vi.fn(),
    });
    vi.stubGlobal(
      "matchMedia",
      (query: string) =>
        ({
          matches: false,
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
          addListener: () => undefined,
          removeListener: () => undefined,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    );
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it("uses responsive desktop grid layout regions", async () => {
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="signature-workspace-sidebar"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="signature-workspace-canvas-region"]').exists()).toBe(true);
    host.remove();
  });

  it("rejects malformed version query values such as 1abc", async () => {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1/signature?version=1abc&action=complete_editing");
    await router.isReady();
    const host = document.createElement("div");
    document.body.appendChild(host);
    mount(SignatureWorkspaceView, {
      attachTo: host,
      global: { plugins: [i18n, vuetify, router] },
    });
    await flushPromises();
    expect(document.body.querySelector('[data-testid="signature-load-error"]')?.textContent).toContain(
      "ungültig",
    );
    host.remove();
  });

  it("retries ensure-source init exactly once when writes become available again", async () => {
    __setBootstrapWritesAllowedForTest(false);
    mutateMock.mockRejectedValueOnce(new MutationWritesBlockedError("writes blocked"));
    const { host } = await mountWorkspace();
    expect(document.body.querySelector('[data-testid="signature-load-error"]')).toBeTruthy();
    expect(mutateMock).toHaveBeenCalledTimes(1);

    mutateMock.mockResolvedValueOnce({
      etag: "evt-2",
      artifact_id: "artifact-source",
      allowed_actions: baseDetail().allowed_actions,
      available_actions: baseDetail().available_actions,
      state: baseDetail().state,
    });
    __setBootstrapWritesAllowedForTest(true);
    await flushPromises();
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledTimes(2);
    expect(document.body.querySelector('[data-testid="signature-placement-canvas"]')).toBeTruthy();
    host.remove();
  });

  it("does not retry ensure-source when the initial load fails for other reasons", async () => {
    mutateMock.mockRejectedValueOnce(new Error("network down"));
    const { host } = await mountWorkspace();
    expect(document.body.querySelector('[data-testid="signature-load-error"]')).toBeTruthy();
    __setBootstrapWritesAllowedForTest(false);
    __setBootstrapWritesAllowedForTest(true);
    await flushPromises();
    expect(mutateMock).toHaveBeenCalledTimes(1);
    host.remove();
  });

  it("loads workspace through ensure-source-pdf and preview read owner", async () => {
    const { wrapper, host } = await mountWorkspace();
    expect(mutateMock).toHaveBeenCalledWith({
      method: "POST",
      path: "/documents/versions/DOC-1/1/workflow/ensure-source-pdf",
      ifMatch: "evt-1",
    });
    expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("artifact-source");
    expect(wrapper.find('[data-testid="signature-placement-canvas"]').exists()).toBe(true);
    host.remove();
  });

  it("uses assignment_kind from ensure-source-pdf response for suggestion and template save, not the initial descriptor value", async () => {
    const initialKind = "initial_stub_role";
    const authoritativeKind = "authoritative_server_role_q7";
    const initial = {
      ...baseDetail(),
      allowed_actions: [
        actionDescriptor("complete_editing", true, {
          signatureRequired: true,
          assignmentKind: initialKind,
        }),
        actionDescriptor("preview"),
      ],
    };
    fetchDocumentVersionMock.mockResolvedValueOnce(initial);
    mutateMock.mockResolvedValueOnce({
      etag: "evt-2",
      artifact_id: "artifact-source",
      allowed_actions: [
        actionDescriptor("complete_editing", true, {
          signatureRequired: true,
          assignmentKind: authoritativeKind,
        }),
        actionDescriptor("preview"),
      ],
      available_actions: initial.available_actions,
      state: initial.state,
    });
    const suggestedForAuthoritative = {
      ...suggestedTemplate(),
      template_id: "tpl-authoritative",
      name: "Authoritative Suggestion",
      role_context: authoritativeKind,
    };
    fetchSignatureTemplateSuggestionMock.mockImplementation(async (_docType, roleContext) => {
      if (roleContext === authoritativeKind) {
        return suggestedForAuthoritative;
      }
      return null;
    });

    const { wrapper, host } = await mountWorkspace();
    expect(fetchSignatureTemplateSuggestionMock).toHaveBeenCalledWith("SOP", authoritativeKind);
    expect(fetchSignatureTemplateSuggestionMock).not.toHaveBeenCalledWith("SOP", initialKind);
    expect(wrapper.get('[data-testid="signature-suggestion"]').text()).toContain("Authoritative Suggestion");

    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path === "/signature/templates/user") {
        return baseDetail();
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="save-personal-template"]').trigger("click");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/signature/templates/user",
        body: expect.objectContaining({
          json: expect.objectContaining({
            role_context: authoritativeKind,
          }),
        }),
      }),
    );
    const templateSaveCalls = mutateMock.mock.calls.filter(
      (call) => (call[0] as { path?: string }).path === "/signature/templates/user",
    );
    for (const call of templateSaveCalls) {
      const body = (call[0] as { body?: { json?: { role_context?: string } } }).body;
      expect(body?.json?.role_context).not.toBe(initialKind);
    }
    host.remove();
  });

  it("allows core signature workspace when assignment_kind is null but skips template suggestion reads and role-scoped template save", async () => {
    const initial = {
      ...baseDetail(),
      allowed_actions: [
        actionDescriptor("complete_editing", true, {
          signatureRequired: true,
          assignmentKind: null,
        }),
        actionDescriptor("preview"),
      ],
    };
    fetchDocumentVersionMock.mockResolvedValueOnce(initial);
    mutateMock.mockResolvedValueOnce({
      etag: "evt-2",
      artifact_id: "artifact-source",
      allowed_actions: [
        actionDescriptor("complete_editing", true, {
          signatureRequired: true,
          assignmentKind: null,
        }),
        actionDescriptor("preview"),
      ],
      available_actions: initial.available_actions,
      state: initial.state,
    });

    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="signature-placement-canvas"]').exists()).toBe(true);
    expect(fetchSignatureTemplateSuggestionMock).not.toHaveBeenCalled();
    expect(fetchSignatureTemplatesUserMock).not.toHaveBeenCalled();
    expect(fetchSignatureTemplatesGlobalMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="signature-suggestion"]').exists()).toBe(false);

    const templateSaveCallsBefore = mutateMock.mock.calls.filter(
      (call) => (call[0] as { path?: string }).path === "/signature/templates/user",
    ).length;
    await wrapper.get('[data-testid="save-personal-template"]').trigger("click");
    await flushPromises();
    const templateSaveCallsAfter = mutateMock.mock.calls.filter(
      (call) => (call[0] as { path?: string }).path === "/signature/templates/user",
    ).length;
    expect(templateSaveCallsAfter).toBe(templateSaveCallsBefore);
    host.remove();
  });

  it("forces show_time off when show_date is disabled", async () => {
    const { wrapper, host } = await mountWorkspace();
    const dateSwitch = wrapper
      .findAllComponents({ name: "VSwitch" })
      .find((row) => row.props("label") === "Datum anzeigen");
    expect(dateSwitch).toBeTruthy();
    await dateSwitch!.setValue(false);
    await flushPromises();
    const timeSwitch = wrapper
      .findAllComponents({ name: "VSwitch" })
      .find((row) => row.props("label") === "Uhrzeit anzeigen");
    expect(timeSwitch?.props("disabled")).toBe(true);
    host.remove();
  });

  it("preselects suggested template and sends template_id in final sign_intent", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(suggestedTemplate());
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.get('[data-testid="signature-suggestion"]').text()).toContain("Suggested");
    const picker = wrapper.getComponent({ name: "VSelect" });
    expect(picker.props("modelValue")).toBe("tpl-suggested");

    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        return {
          etag: "evt-signed",
          allowed_actions: baseDetail().allowed_actions,
          available_actions: baseDetail().available_actions,
          state: { ...baseDetail().state, status: "IN_REVIEW" },
        };
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    fetchDocumentArtifactsMock.mockResolvedValueOnce([]);

    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "POST",
        path: "/documents/versions/DOC-1/1/workflow/editing-complete",
        body: expect.objectContaining({
          json: expect.objectContaining({
            sign_intent: expect.objectContaining({
              template_id: "tpl-suggested",
            }),
          }),
        }),
      }),
    );
    host.remove();
  });

  it("shows asset mismatch placeholder when template asset differs from active asset", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue({
      ...suggestedTemplate(),
      signature_asset_id: "asset-other",
    });
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-asset-mismatch"]').exists()).toBe(true);
    host.remove();
  });

  it("shows mismatch when explicit template asset exists but active asset is null", async () => {
    fetchActiveSignatureAssetIdMock.mockResolvedValueOnce(null);
    fetchSignatureTemplateSuggestionMock.mockResolvedValue({
      ...suggestedTemplate(),
      signature_asset_id: "asset-explicit",
    });
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-asset-mismatch"]').exists()).toBe(true);
    const signButton = wrapper.get('[data-testid="signature-sign-button"]').element as HTMLButtonElement;
    expect(signButton.disabled).toBe(false);
    host.remove();
  });

  it("surfaces active asset id endpoint errors instead of treating 404 as no asset", async () => {
    fetchActiveSignatureAssetIdMock.mockRejectedValueOnce(new ApiTransportError("HTTP 404", 404, null));
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-asset-error"]').exists()).toBe(true);
    host.remove();
  });

  it("surfaces signature asset transport errors with retry", async () => {
    fetchActiveSignatureAssetContentMock.mockRejectedValueOnce(
      Object.assign(new Error("HTTP 503"), { status: 503 }),
    );
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-asset-error"]').exists()).toBe(true);
    fetchActiveSignatureAssetContentMock.mockResolvedValueOnce(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" }),
    );
    await wrapper.get('[data-testid="signature-asset-retry"]').trigger("click");
    await flushPromises();
    expect(fetchActiveSignatureAssetIdMock).toHaveBeenCalledTimes(2);
    host.remove();
  });

  it("blocks signing when show_signature is enabled but no active asset exists", async () => {
    fetchActiveSignatureAssetIdMock.mockResolvedValueOnce(null);
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-missing-asset"]').exists()).toBe(true);
    const signButton = wrapper.get('[data-testid="signature-sign-button"]').element as HTMLButtonElement;
    expect(signButton.disabled).toBe(true);
    host.remove();
  });

  it("preserves draft placement on conflict and restores it via view-local", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(suggestedTemplate());
    const { wrapper, host } = await mountWorkspace();
    const canvas = wrapper.findComponent(SignaturePlacementCanvas);
    await canvas.vm.$emit("update:placement", {
      page_index: 1,
      x: 200,
      y: 220,
      target_width: 90,
    });
    await flushPromises();

    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        throw new MutationClientError("conflict", "conflict", 409);
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();

    expect(document.body.querySelector('[data-testid="conflict-view-local"]')).toBeTruthy();
    (document.body.querySelector('[data-testid="conflict-view-local"]') as HTMLElement).click();
    await flushPromises();
    expect(conflictDraftPreviewText()).toContain("Seite 2");
    expect(conflictDraftPreviewText()).toContain("tpl-suggested");
    expect(document.body.querySelector('[data-testid="conflict-dialog"]')).toBeTruthy();
    host.remove();
  });

  it("shows signature draft inside the conflict dialog for 428 precondition conflicts", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(suggestedTemplate());
    const { wrapper, host } = await mountWorkspace();
    const canvas = wrapper.findComponent(SignaturePlacementCanvas);
    await canvas.vm.$emit("update:placement", {
      page_index: 1,
      x: 200,
      y: 220,
      target_width: 90,
    });
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        throw new MutationClientError("precondition", "precondition_required", 428);
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();
    (document.body.querySelector('[data-testid="conflict-view-local"]') as HTMLElement).click();
    await flushPromises();
    expect(conflictDraftPreviewText()).toContain("Seite 2");
    expect(
      document.body.querySelector(
        '[data-testid="conflict-dialog"] [data-testid="signature-draft-layout"]',
      ),
    ).toBeTruthy();
    host.remove();
  });

  it("clears prior suggestion state when navigating to a workspace without suggestion", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValueOnce(suggestedTemplate());
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1/signature?version=1&action=complete_editing");
    await router.isReady();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const wrapper = mount(SignatureWorkspaceView, {
      attachTo: host,
      global: { plugins: [i18n, vuetify, router] },
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="signature-suggestion"]').exists()).toBe(true);

    fetchSignatureTemplateSuggestionMock.mockResolvedValueOnce(null);
    await router.push("/documents/DOC-2/signature?version=1&action=complete_editing");
    fetchDocumentVersionMock.mockResolvedValueOnce({
      ...baseDetail(),
      state: { ...baseDetail().state, document_id: "DOC-2" },
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="signature-suggestion"]').exists()).toBe(false);
    host.remove();
  });

  it("keeps sign success when artifact refresh fails and exposes retry", async () => {
    const { wrapper, host } = await mountWorkspace();
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        return {
          etag: "evt-signed",
          allowed_actions: baseDetail().allowed_actions,
          available_actions: baseDetail().available_actions,
          state: { ...baseDetail().state, status: "IN_REVIEW" },
        };
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    fetchDocumentArtifactsMock.mockRejectedValueOnce(new Error("refresh failed"));

    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();

    expect(wrapper.find('[data-testid="signature-result-panel"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="artifact-type-list"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="artifact-refresh-error"]').exists()).toBe(true);
    fetchDocumentArtifactsMock.mockResolvedValueOnce([]);
    await wrapper.get('[data-testid="artifact-refresh-retry"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="artifact-refresh-error"]').exists()).toBe(false);
    host.remove();
  });

  it("does not apply late sign mutation after route change", async () => {
    const { wrapper, router, host } = await mountWorkspace();
    mutateMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              etag: "evt-late",
              allowed_actions: baseDetail().allowed_actions,
              available_actions: baseDetail().available_actions,
              state: baseDetail().state,
            });
          }, 50);
        }),
    );
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await router.push("/documents/DOC-2/signature?version=1&action=complete_editing");
    await new Promise((resolve) => setTimeout(resolve, 80));
    await flushPromises();
    expect(wrapper.find('[data-testid="signature-result-panel"]').exists()).toBe(false);
    host.remove();
  });

  it("keeps conflict draft when server reload fails and clears it only after success", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(suggestedTemplate());
    const { wrapper, host } = await mountWorkspace();
    const canvas = wrapper.findComponent(SignaturePlacementCanvas);
    await canvas.vm.$emit("update:placement", {
      page_index: 1,
      x: 200,
      y: 220,
      target_width: 90,
    });
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        throw new MutationClientError("conflict", "conflict", 409);
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();

    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/ensure-source-pdf")) {
        return {
          etag: "evt-2",
          artifact_id: "artifact-source",
          allowed_actions: baseDetail().allowed_actions,
          available_actions: baseDetail().available_actions,
          state: baseDetail().state,
        };
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });

    fetchDocumentVersionMock.mockRejectedValueOnce(new Error("reload failed"));
    (document.body.querySelector('[data-testid="conflict-load-server"]') as HTMLElement).click();
    await flushPromises();
    expect(conflictDraftPreviewText()).toBe("");
    (document.body.querySelector('[data-testid="conflict-view-local"]') as HTMLElement).click();
    await flushPromises();
    expect(conflictDraftPreviewText()).toContain("Seite 2");

    fetchDocumentVersionMock.mockResolvedValueOnce(baseDetail());
    (document.body.querySelector('[data-testid="conflict-load-server"]') as HTMLElement).click();
    await flushPromises();
    await vi.waitFor(() => {
      expect(document.body.querySelector('[data-testid="conflict-view-local"]')).toBeFalsy();
    });
    host.remove();
  });

  it("preserves original conflict draft when reload hits another 409", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(suggestedTemplate());
    const { wrapper, host } = await mountWorkspace();
    const canvas = wrapper.findComponent(SignaturePlacementCanvas);
    await canvas.vm.$emit("update:placement", {
      page_index: 1,
      x: 200,
      y: 220,
      target_width: 90,
    });
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        throw new MutationClientError("conflict", "conflict", 409);
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();

    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/ensure-source-pdf")) {
        throw new MutationClientError("conflict", "conflict", 409);
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    (document.body.querySelector('[data-testid="conflict-load-server"]') as HTMLElement).click();
    await flushPromises();
    (document.body.querySelector('[data-testid="conflict-view-local"]') as HTMLElement).click();
    await flushPromises();
    expect(conflictDraftPreviewText()).toContain("Seite 2");
    expect(conflictDraftPreviewText()).toContain("tpl-suggested");
    host.remove();
  });

  it("clears conflict UI and draft when route changes during an open conflict", async () => {
    fetchSignatureTemplateSuggestionMock.mockResolvedValue(suggestedTemplate());
    const { wrapper, router, host } = await mountWorkspace();
    const canvas = wrapper.findComponent(SignaturePlacementCanvas);
    await canvas.vm.$emit("update:placement", {
      page_index: 1,
      x: 200,
      y: 220,
      target_width: 90,
    });
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        throw new MutationClientError("conflict", "conflict", 409);
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();
    (document.body.querySelector('[data-testid="conflict-view-local"]') as HTMLElement).click();
    await flushPromises();
    expect(document.body.querySelector('[data-testid="conflict-dialog"]')).toBeTruthy();
    expect(conflictDraftPreviewText()).toContain("Seite 2");

    fetchSignatureTemplateSuggestionMock.mockResolvedValueOnce({
      ...suggestedTemplate(),
      template_id: "tpl-doc2",
      name: "Doc2 Suggested",
      placement: { page_index: 0, x: 110, y: 120, target_width: 85 },
    });
    fetchDocumentVersionMock.mockResolvedValueOnce({
      ...baseDetail(),
      state: { ...baseDetail().state, document_id: "DOC-2" },
    });
    mutateMock.mockResolvedValue({
      etag: "evt-doc2",
      artifact_id: "artifact-doc2",
      allowed_actions: baseDetail().allowed_actions,
      available_actions: baseDetail().available_actions,
      state: { ...baseDetail().state, document_id: "DOC-2" },
    });
    await router.push("/documents/DOC-2/signature?version=1&action=complete_editing");
    await flushPromises();

    expect(document.body.querySelector('[data-testid="conflict-dialog"]')).toBeFalsy();
    expect(conflictDraftPreviewText()).toBe("");
    const passwordInput = document.body.querySelector(
      '[data-testid="reauth-password"] input',
    ) as HTMLInputElement | null;
    expect(passwordInput?.value ?? "").toBe("");
    expect(wrapper.get('[data-testid="signature-suggestion"]').text()).toContain("Doc2 Suggested");
    const picker = wrapper.getComponent({ name: "VSelect" });
    expect(picker.props("modelValue")).toBe("tpl-doc2");
    host.remove();
  });

  it("does not apply late template save after route change", async () => {
    const { wrapper, router, host } = await mountWorkspace();
    const pending = deferred<ReturnType<typeof baseDetail>>();
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path === "/signature/templates/user") {
        return pending.promise;
      }
      if (args.path?.includes("/workflow/ensure-source-pdf")) {
        return {
          etag: "evt-2",
          artifact_id: "artifact-source",
          allowed_actions: baseDetail().allowed_actions,
          available_actions: baseDetail().available_actions,
          state: baseDetail().state,
        };
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    await wrapper.get('[data-testid="save-personal-template"]').trigger("click");
    await router.push("/documents/DOC-2/signature?version=1&action=complete_editing");
    fetchDocumentVersionMock.mockResolvedValueOnce({
      ...baseDetail(),
      state: { ...baseDetail().state, document_id: "DOC-2" },
    });
    pending.resolve(baseDetail());
    await new Promise((resolve) => setTimeout(resolve, 60));
    await flushPromises();
    expect(wrapper.text()).not.toContain("Vorlage gespeichert");
    const signButton = wrapper.get('[data-testid="signature-sign-button"]').element as HTMLButtonElement;
    expect(signButton.disabled).toBe(false);
    host.remove();
  });

  it("does not apply late asset retry after route change", async () => {
    fetchActiveSignatureAssetContentMock.mockRejectedValueOnce(
      Object.assign(new Error("HTTP 503"), { status: 503 }),
    );
    const { wrapper, router, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-asset-error"]').exists()).toBe(true);
    const pending = deferred<string | null>();
    fetchActiveSignatureAssetIdMock.mockImplementationOnce(() => pending.promise);
    await wrapper.get('[data-testid="signature-asset-retry"]').trigger("click");
    await router.push("/documents/DOC-2/signature?version=1&action=complete_editing");
    fetchDocumentVersionMock.mockResolvedValueOnce({
      ...baseDetail(),
      state: { ...baseDetail().state, document_id: "DOC-2" },
    });
    pending.resolve("asset-late");
    fetchActiveSignatureAssetContentMock.mockResolvedValueOnce(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" }),
    );
    await new Promise((resolve) => setTimeout(resolve, 60));
    await flushPromises();
    expect(wrapper.find('[data-testid="signature-asset-error"]').exists()).toBe(false);
    host.remove();
  });

  it("does not apply late artifact retry after route change", async () => {
    const { wrapper, router, host } = await mountWorkspace();
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes("/workflow/editing-complete")) {
        return {
          etag: "evt-signed",
          allowed_actions: baseDetail().allowed_actions,
          available_actions: baseDetail().available_actions,
          state: { ...baseDetail().state, status: "IN_REVIEW" },
        };
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    fetchDocumentArtifactsMock.mockRejectedValueOnce(new Error("refresh failed"));
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(wrapper.find('[data-testid="artifact-refresh-error"]').exists()).toBe(true);

    const pending = deferred<[]>();
    fetchDocumentArtifactsMock.mockImplementationOnce(() => pending.promise);
    await wrapper.get('[data-testid="artifact-refresh-retry"]').trigger("click");
    await router.push("/documents/DOC-2/signature?version=1&action=complete_editing");
    fetchDocumentVersionMock.mockResolvedValueOnce({
      ...baseDetail(),
      state: { ...baseDetail().state, document_id: "DOC-2" },
    });
    pending.resolve([]);
    await new Promise((resolve) => setTimeout(resolve, 60));
    await flushPromises();
    expect(wrapper.find('[data-testid="signature-result-panel"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="artifact-refresh-error"]').exists()).toBe(false);
    host.remove();
  });

  it.each([
    ["complete_editing", "/workflow/editing-complete", { signatureRequired: true, assignmentKind: "editor" }],
    ["review_accept", "/workflow/review/accept", { signatureRequired: true, assignmentKind: "reviewer" }],
    ["approval_accept", "/workflow/approval/accept", { signatureRequired: true, assignmentKind: "approver" }],
  ] as const)(
    "loads signature workspace for %s with correct workflow path",
    async (actionCode, workflowPath, signatureAction) => {
    const { detail } = baseDetailForSignatureAction(actionCode, signatureAction);
    fetchDocumentVersionMock.mockResolvedValueOnce(detail);
    if (actionCode === "complete_editing") {
      mutateMock.mockResolvedValueOnce(ensuredResponseFromDetail(detail));
    } else {
      fetchDocumentArtifactsMock.mockResolvedValueOnce([signedPdfArtifact("artifact-signed")]);
    }
    const { wrapper, host } = await mountWorkspace(
      `/documents/DOC-1/signature?version=1&action=${actionCode}`,
    );
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(true);
    if (actionCode === "complete_editing") {
      expect(mutateMock).toHaveBeenCalledWith({
        method: "POST",
        path: "/documents/versions/DOC-1/1/workflow/ensure-source-pdf",
        ifMatch: detail.etag,
      });
      expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("artifact-source");
    } else {
      expect(mutateMock).not.toHaveBeenCalledWith(
        expect.objectContaining({
          path: "/documents/versions/DOC-1/1/workflow/ensure-source-pdf",
        }),
      );
      expect(fetchDocumentArtifactsMock).toHaveBeenCalledWith("DOC-1", 1);
      expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("artifact-signed");
    }
    mutateMock.mockImplementation(async (args: { path?: string }) => {
      if (args.path?.includes(workflowPath)) {
        return {
          etag: "evt-signed",
          allowed_actions: detail.allowed_actions,
          available_actions: detail.available_actions,
          state: { ...detail.state, status: "IN_REVIEW" },
        };
      }
      throw new Error(`unexpected mutate path: ${args.path}`);
    });
    fetchDocumentArtifactsMock.mockResolvedValueOnce([]);
    await wrapper.get('[data-testid="signature-sign-button"]').trigger("click");
    await flushPromises();
    const password = queryReauthPassword();
    password.value = "secret";
    password.dispatchEvent(new Event("input"));
    await flushPromises();
    (document.body.querySelector('[data-testid="reauth-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        path: `/documents/versions/DOC-1/1${workflowPath}`,
      }),
    );
    host.remove();
  },
  );

  it("review_accept does not POST ensure-source-pdf and uses current SIGNED_PDF", async () => {
    const { detail } = baseDetailForSignatureAction("review_accept", {
      signatureRequired: true,
      assignmentKind: "reviewer",
    });
    fetchDocumentVersionMock.mockResolvedValueOnce(detail);
    fetchDocumentArtifactsMock.mockResolvedValueOnce([
      signedPdfArtifact("signed-current", { isCurrent: true, createdAt: "2025-01-02T00:00:00Z" }),
      signedPdfArtifact("signed-older", { isCurrent: false, createdAt: "2025-01-03T00:00:00Z" }),
    ]);
    const { wrapper, host } = await mountWorkspace(
      "/documents/DOC-1/signature?version=1&action=review_accept",
    );
    expect(mutateMock).not.toHaveBeenCalled();
    expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("signed-current");
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(true);
    host.remove();
  });

  it("approval_accept selects newest current SIGNED_PDF among equivalent candidates", async () => {
    const { detail } = baseDetailForSignatureAction("approval_accept", {
      signatureRequired: true,
      assignmentKind: "approver",
    });
    fetchDocumentVersionMock.mockResolvedValueOnce(detail);
    fetchDocumentArtifactsMock.mockResolvedValueOnce([
      signedPdfArtifact("signed-older-current", { isCurrent: true, createdAt: "2025-01-01T00:00:00Z" }),
      signedPdfArtifact("signed-newer-current", { isCurrent: true, createdAt: "2025-01-03T00:00:00Z" }),
    ]);
    const { wrapper, host } = await mountWorkspace(
      "/documents/DOC-1/signature?version=1&action=approval_accept",
    );
    expect(mutateMock).not.toHaveBeenCalled();
    expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("signed-newer-current");
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(true);
    host.remove();
  });

  it("review_accept falls back to newest SIGNED_PDF when none is current", async () => {
    const { detail } = baseDetailForSignatureAction("review_accept", {
      signatureRequired: true,
      assignmentKind: "reviewer",
    });
    fetchDocumentVersionMock.mockResolvedValueOnce(detail);
    fetchDocumentArtifactsMock.mockResolvedValueOnce([
      signedPdfArtifact("signed-older", { isCurrent: false, createdAt: "2025-01-01T00:00:00Z" }),
      signedPdfArtifact("signed-newer", { isCurrent: false, createdAt: "2025-01-04T00:00:00Z" }),
    ]);
    const { wrapper, host } = await mountWorkspace(
      "/documents/DOC-1/signature?version=1&action=review_accept",
    );
    expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("signed-newer");
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(true);
    host.remove();
  });

  it("fails closed for review_accept when no SIGNED_PDF artifact exists", async () => {
    const { detail } = baseDetailForSignatureAction("review_accept", {
      signatureRequired: true,
      assignmentKind: "reviewer",
    });
    fetchDocumentVersionMock.mockResolvedValueOnce(detail);
    fetchDocumentArtifactsMock.mockResolvedValueOnce([
      {
        artifact_id: "artifact-source",
        artifact_type: "SOURCE_PDF",
        created_at: "2025-01-01T00:00:00Z",
        document_id: "DOC-1",
        is_current: true,
        mime_type: "application/pdf",
        version: 1,
      },
    ]);
    const { wrapper, host } = await mountWorkspace(
      "/documents/DOC-1/signature?version=1&action=review_accept",
    );
    expect(mutateMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="signature-load-error"]').text()).toContain("Quell-PDF");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(false);
    host.remove();
  });

  it("fails closed for review_accept when preview is disabled", async () => {
    const { detail } = baseDetailForSignatureAction("review_accept", {
      signatureRequired: true,
      assignmentKind: "reviewer",
    });
    fetchDocumentVersionMock.mockResolvedValueOnce({
      ...detail,
      allowed_actions: [
        actionDescriptor("review_accept", true, {
          signatureRequired: true,
          assignmentKind: "reviewer",
        }),
        actionDescriptor("preview", false),
      ],
    });
    fetchDocumentArtifactsMock.mockResolvedValueOnce([signedPdfArtifact("artifact-signed")]);
    const { wrapper, host } = await mountWorkspace(
      "/documents/DOC-1/signature?version=1&action=review_accept",
    );
    expect(wrapper.find('[data-testid="signature-load-error"]').text()).toContain("Vorschau");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(false);
    host.remove();
  });

  it("rejects a signature route when the action descriptor does not require a signature", async () => {
    const detail = {
      ...baseDetail(),
      allowed_actions: [
        actionDescriptor("complete_editing", true, { signatureRequired: false, assignmentKind: "editor" }),
        actionDescriptor("preview"),
      ],
      state: {
        ...baseDetail().state,
        workflow_profile: {
          ...baseDetail().state.workflow_profile,
          signature_required_transitions: ["IN_PROGRESS->IN_REVIEW"],
        },
      },
    };
    fetchDocumentVersionMock.mockResolvedValueOnce(detail);
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1/signature?version=1&action=complete_editing");
    await router.isReady();
    const host = document.createElement("div");
    document.body.appendChild(host);
    mount(SignatureWorkspaceView, {
      attachTo: host,
      global: { plugins: [i18n, vuetify, router] },
    });
    await flushPromises();
    expect(document.body.querySelector('[data-testid="signature-load-error"]')?.textContent).toContain(
      "keine Signatur",
    );
    expect(mutateMock).not.toHaveBeenCalled();
    host.remove();
  });

  it("fails closed when ensure-source-pdf disables the signature action", async () => {
    const initial = baseDetail();
    fetchDocumentVersionMock.mockResolvedValueOnce(initial);
    mutateMock.mockResolvedValueOnce({
      ...ensuredResponseFromDetail(initial),
      allowed_actions: [
        actionDescriptor("complete_editing", false, {
          signatureRequired: true,
          assignmentKind: "editor",
        }),
        actionDescriptor("preview"),
      ],
    });
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-load-error"]').text()).toContain("nicht verfügbar");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(false);
    host.remove();
  });

  it("fails closed when ensure-source-pdf no longer requires a signature", async () => {
    const initial = baseDetail();
    fetchDocumentVersionMock.mockResolvedValueOnce(initial);
    mutateMock.mockResolvedValueOnce({
      ...ensuredResponseFromDetail(initial),
      allowed_actions: [
        actionDescriptor("complete_editing", true, { signatureRequired: false, assignmentKind: "editor" }),
        actionDescriptor("preview"),
      ],
    });
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-load-error"]').text()).toContain("keine Signatur");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    host.remove();
  });

  it("does not fetch preview or mark workspace ready when ensure-source-pdf disables preview", async () => {
    const initial = baseDetail();
    fetchDocumentVersionMock.mockResolvedValueOnce(initial);
    mutateMock.mockResolvedValueOnce({
      ...ensuredResponseFromDetail(initial),
      allowed_actions: [
        actionDescriptor("complete_editing", true, {
          signatureRequired: true,
          assignmentKind: "editor",
        }),
        actionDescriptor("preview", false),
      ],
    });
    const { wrapper, host } = await mountWorkspace();
    expect(wrapper.find('[data-testid="signature-load-error"]').text()).toContain("Vorschau");
    expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="signature-workspace-grid"]').exists()).toBe(false);
    host.remove();
  });

  it("ignores stale workspace initialization after route change", async () => {
    let resolveVersion: (value: ReturnType<typeof baseDetail>) => void = () => undefined;
    fetchDocumentVersionMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveVersion = resolve;
        }),
    );
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1/signature?version=1&action=complete_editing");
    await router.isReady();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const wrapper = mount(SignatureWorkspaceView, {
      attachTo: host,
      global: { plugins: [i18n, vuetify, router] },
    });
    await router.push("/documents/DOC-1/signature?version=2&action=complete_editing");
    resolveVersion(baseDetail());
    await flushPromises();
    expect(wrapper.find('[data-testid="signature-load-error"]').exists()).toBe(false);
    host.remove();
  });
});
