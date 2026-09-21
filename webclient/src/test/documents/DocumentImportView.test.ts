import { flushPromises, mount } from "@vue/test-utils";
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

import { ApiTransportError } from "../../api/client";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { routes } from "../../router/routes";
import DocumentImportView from "../../views/documents/DocumentImportView.vue";
import { __setBootstrapWritesAllowedForTest } from "../../state/bootstrap";

const mutateMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/mutationClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/mutationClient")>();
  return {
    ...actual,
    mutate: mutateMock,
  };
});

function createdResponse(docId = "DOC-NEW", version = 1, etag = "evt-create") {
  return {
    etag,
    allowed_actions: [],
    available_actions: [],
    state: {
      document_id: docId,
      version,
      title: "Neu",
      status: "PLANNED",
      doc_type: "OTHER",
      control_class: "CONTROLLED",
      workflow_profile_id: "default",
      approved_by: [],
      reviewed_by: [],
      assignments: { editors: [], reviewers: [], approvers: [] },
      edit_signature_done: false,
      extension_count: 0,
      workflow_active: false,
    },
  };
}

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

async function submitImportForm(wrapper: ReturnType<typeof mount>): Promise<void> {
  await wrapper.get("[data-testid=document-import-form]").trigger("submit");
}

async function mountImport() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  });
  await router.push("/documents/import");
  await router.isReady();

  const wrapper = mount(DocumentImportView, {
    global: {
      plugins: [router, vuetify, i18n],
    },
  });
  await flushPromises();
  return { wrapper, router };
}

async function fillImportForm(
  wrapper: ReturnType<typeof mount>,
  input: { documentId: string; version: string; file: File },
): Promise<void> {
  await wrapper.get("[data-testid=document-import-document-id]").find("input").setValue(input.documentId);
  await wrapper.get("[data-testid=document-import-version]").find("input").setValue(input.version);
  await flushPromises();
  const fileInput = wrapper.get("[data-testid=document-import-file]").element as HTMLInputElement;
  Object.defineProperty(fileInput, "files", { value: [input.file], configurable: true });
  await wrapper.get("[data-testid=document-import-file]").trigger("change");
  await flushPromises();
}

describe("DocumentImportView", () => {
  beforeEach(() => {
    __setBootstrapWritesAllowedForTest(true);
    stubBrowserApis();
    mutateMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("rejects unsupported file extensions before mutate", async () => {
    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, {
      documentId: "DOC-1",
      version: "1",
      file: new File(["x"], "image.png", { type: "image/png" }),
    });
    await submitImportForm(wrapper);
    await flushPromises();
    expect(mutateMock).not.toHaveBeenCalled();
    expect(wrapper.find("[data-testid=document-import-alert]").text()).toContain("PDF");
  });

  it("rejects contradictory pdf extension with docx MIME before mutate", async () => {
    const docxMime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, {
      documentId: "DOC-1",
      version: "1",
      file: new File(["x"], "report.pdf", { type: docxMime }),
    });
    await submitImportForm(wrapper);
    await flushPromises();
    expect(mutateMock).not.toHaveBeenCalled();
    expect(wrapper.find("[data-testid=document-import-alert]").text()).toContain("PDF");
  });

  it("creates once and retries upload with frozen file even after form edits", async () => {
    const pdf = new File(["%PDF-1.4"], "doc.pdf", { type: "application/pdf" });
    mutateMock
      .mockResolvedValueOnce(createdResponse("DOC-NEW", 1, "evt-create"))
      .mockRejectedValueOnce(new Error("upload failed"));

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-NEW", version: "1", file: pdf });
    await submitImportForm(wrapper);
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledTimes(2);
    expect(mutateMock.mock.calls[0]?.[0]?.path).toBe("/documents/versions/create");
    expect(mutateMock.mock.calls[0]?.[0]?.body).toEqual({
      json: {
        document_id: "DOC-NEW",
        version: 1,
        title: "",
        doc_type: "OTHER",
        control_class: "CONTROLLED",
      },
    });
    expect(mutateMock.mock.calls[1]?.[0]?.path).toBe("/documents/versions/DOC-NEW/1/import-pdf");
    expect(mutateMock.mock.calls[1]?.[0]?.body).toEqual({ raw: pdf, contentType: "application/pdf" });
    expect(wrapper.get("[data-testid=document-import-submit]").text()).toContain("Upload erneut");

    await wrapper.get("[data-testid=document-import-document-id]").find("input").setValue("DOC-OTHER");
    await wrapper.get("[data-testid=document-import-version]").find("input").setValue("9");
    await flushPromises();

    mutateMock.mockClear();
    mutateMock.mockResolvedValueOnce(createdResponse("DOC-NEW", 1, "evt-imported"));
    await submitImportForm(wrapper);
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledTimes(1);
    expect(mutateMock.mock.calls[0]?.[0]?.path).toBe("/documents/versions/DOC-NEW/1/import-pdf");
    expect(mutateMock.mock.calls[0]?.[0]?.ifMatch).toBe("evt-create");
    expect(mutateMock.mock.calls[0]?.[0]?.body).toEqual({ raw: pdf, contentType: "application/pdf" });
  });

  it("disables metadata controls after create succeeds and upload is pending", async () => {
    const pdf = new File(["%PDF"], "doc.pdf", { type: "application/pdf" });
    mutateMock
      .mockResolvedValueOnce(createdResponse())
      .mockRejectedValueOnce(new Error("upload failed"));

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-NEW", version: "1", file: pdf });
    await submitImportForm(wrapper);
    await flushPromises();

    expect(wrapper.get("[data-testid=document-import-document-id]").find("input").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid=document-import-version]").find("input").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid=document-import-file]").attributes("disabled")).toBeDefined();
  });

  it("uploads PDF with raw body and application/pdf content type", async () => {
    const pdf = new File(["%PDF-1.4"], "doc.pdf", { type: "application/pdf" });
    mutateMock
      .mockResolvedValueOnce(createdResponse())
      .mockResolvedValueOnce(createdResponse("DOC-NEW", 1, "evt-imported"));

    const { wrapper, router } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-NEW", version: "1", file: pdf });
    await submitImportForm(wrapper);
    await flushPromises();

    const uploadCall = mutateMock.mock.calls[1]?.[0];
    expect(uploadCall?.body).toEqual({ raw: pdf, contentType: "application/pdf" });
    expect(router.currentRoute.value.name).toBe("document-detail");
    expect(router.currentRoute.value.params.docId).toBe("DOC-NEW");
    expect(router.currentRoute.value.query.version).toBe("1");
  });

  it("uploads DOCX with the docx MIME type", async () => {
    const docxMime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    const docx = new File(["PK"], "doc.docx", { type: docxMime });
    mutateMock
      .mockResolvedValueOnce(createdResponse("DOC-DOCX", 1))
      .mockResolvedValueOnce(createdResponse("DOC-DOCX", 1, "evt-docx"));

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-DOCX", version: "1", file: docx });
    await submitImportForm(wrapper);
    await flushPromises();
    expect(mutateMock.mock.calls[1]?.[0]?.body).toEqual({ raw: docx, contentType: docxMime });
  });

  it("accepts docx extension with empty MIME", async () => {
    const docxMime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    const docx = new File(["PK"], "plain.docx", { type: "" });
    mutateMock
      .mockResolvedValueOnce(createdResponse("DOC-EMPTY", 1))
      .mockResolvedValueOnce(createdResponse("DOC-EMPTY", 1, "evt-empty"));

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-EMPTY", version: "1", file: docx });
    await submitImportForm(wrapper);
    await flushPromises();
    expect(mutateMock.mock.calls[1]?.[0]?.body?.contentType).toBe(docxMime);
  });

  it("encodes document id path segment on import upload", async () => {
    const pdf = new File(["%PDF"], "doc.pdf", { type: "application/pdf" });
    mutateMock
      .mockResolvedValueOnce(createdResponse("DOC/SLASH", 1, "evt-slash"))
      .mockResolvedValueOnce(createdResponse("DOC/SLASH", 1, "evt-done"));

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC/SLASH", version: "1", file: pdf });
    await submitImportForm(wrapper);
    await flushPromises();

    expect(mutateMock.mock.calls[1]?.[0]?.path).toBe(
      "/documents/versions/DOC%2FSLASH/1/import-pdf",
    );
  });

  it("guards against double submit while pending", async () => {
    let resolveCreate: (value: unknown) => void = () => undefined;
    const pending = new Promise((resolve) => {
      resolveCreate = resolve;
    });
    mutateMock.mockImplementationOnce(() => pending);

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, {
      documentId: "DOC-NEW",
      version: "1",
      file: new File(["%PDF"], "doc.pdf", { type: "application/pdf" }),
    });

    await submitImportForm(wrapper);
    await submitImportForm(wrapper);
    expect(mutateMock).toHaveBeenCalledTimes(1);

    resolveCreate(createdResponse());
    await flushPromises();
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
  ])("maps import HTTP %i to localized message without raw server text", async (status, snippet) => {
    const pdf = new File(["%PDF"], "doc.pdf", { type: "application/pdf" });
    mutateMock
      .mockResolvedValueOnce(createdResponse())
      .mockRejectedValueOnce(new ApiTransportError("fail", status, null));

    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-NEW", version: "1", file: pdf });
    await submitImportForm(wrapper);
    await flushPromises();

    const alert = wrapper.find("[data-testid=document-import-alert]");
    expect(alert.exists()).toBe(true);
    expect(alert.text()).toContain(snippet);
    expect(alert.text()).not.toContain("fail");
    expect(wrapper.get("[data-testid=document-import-submit]").text()).toContain("Upload erneut");
  });

  it("disables import submit and blocks mutate when product writes are unavailable", async () => {
    __setBootstrapWritesAllowedForTest(false);
    const pdf = new File(["%PDF"], "doc.pdf", { type: "application/pdf" });
    const { wrapper } = await mountImport();
    await fillImportForm(wrapper, { documentId: "DOC-NEW", version: "1", file: pdf });
    await submitImportForm(wrapper);
    await flushPromises();
    expect(wrapper.find("[data-testid=document-import-writes-blocked]").exists()).toBe(true);
    expect(wrapper.get("[data-testid=document-import-submit]").attributes("disabled")).toBeDefined();
    expect(mutateMock).not.toHaveBeenCalled();
  });
});
