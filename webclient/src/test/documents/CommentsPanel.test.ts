import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, ref } from "vue";
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
import type { VersionStateResponse } from "../../api/client";
import {
  MutationClientError,
  mutate,
} from "../../api/mutationClient";
import CommentsPanel from "../../components/documents/CommentsPanel.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { __setBootstrapWritesAllowedForTest } from "../../state/bootstrap";

const fetchWorkflowCommentsMock = vi.hoisted(() => vi.fn());
const fetchWorkflowCommentDetailMock = vi.hoisted(() => vi.fn());
const fetchDocumentVersionMock = vi.hoisted(() => vi.fn());
const mutateMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchWorkflowComments: fetchWorkflowCommentsMock,
    fetchWorkflowCommentDetail: fetchWorkflowCommentDetailMock,
    fetchDocumentVersion: fetchDocumentVersionMock,
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

function commentsDescriptor(enabled = true): ActionDescriptor {
  return {
    code: "comments",
    enabled,
    destructive: false,
    label_key: "documents.action.comments",
    requires_confirmation: false,
    requires_reason: false,
    severity: "info",
    signature_required: false,
    assignment_kind: null,
  } as ActionDescriptor;
}

function detail(
  overrides: {
    etag?: string;
    allowed_actions?: ActionDescriptor[];
  } = {},
): VersionStateResponse {
  return {
    etag: overrides.etag ?? "evt-42",
    allowed_actions: overrides.allowed_actions ?? [commentsDescriptor(true)],
    available_actions: ["comments"],
    state: {
      document_id: "DOC-1",
      version: 2,
      status: "DRAFT",
      workflow_profile_id: "default",
      assignments: { editors: [], reviewers: [], approvers: [] },
    },
  } as unknown as VersionStateResponse;
}

function listItem(commentId = "cmt-1") {
  return {
    comment_id: commentId,
    context: "PDF_REVIEW",
    document_id: "DOC-1",
    etag: "cmt-etag",
    page_number: 1,
    preview_text: "Kurztext",
    ref_no: "C-1",
    status: "ACTIVE",
    version: 2,
    updated_at: "2026-01-15T10:00:00Z",
    created_at: "2026-01-15T10:00:00Z",
    author_display: "Anna",
  };
}

function mountPanel(overrides: {
  detail?: VersionStateResponse;
  currentPage?: number;
  hasPdf?: boolean;
} = {}) {
  return mount(CommentsPanel, {
    props: {
      documentId: "DOC-1",
      version: 2,
      detail: overrides.detail ?? detail(),
      currentPage: overrides.currentPage ?? 1,
      hasPdf: overrides.hasPdf ?? true,
    },
    global: { plugins: [vuetify, i18n] },
  });
}

const CommentsPanelParentHarness = defineComponent({
  name: "CommentsPanelParentHarness",
  components: { CommentsPanel },
  setup() {
    const detailState = ref(detail({ etag: "evt-42" }));
    function onDetailUpdated(payload: VersionStateResponse) {
      detailState.value = payload;
    }
    return { detailState, onDetailUpdated };
  },
  template: `
    <CommentsPanel
      document-id="DOC-1"
      :version="2"
      :detail="detailState"
      :current-page="1"
      :has-pdf="true"
      @detail-updated="onDetailUpdated"
    />
  `,
});

function mountPanelWithParent() {
  return mount(CommentsPanelParentHarness, {
    global: { plugins: [vuetify, i18n] },
  });
}

describe("CommentsPanel", () => {
  beforeEach(() => {
    __setBootstrapWritesAllowedForTest(true);
    stubBrowserApis();
    fetchWorkflowCommentsMock.mockReset();
    fetchWorkflowCommentDetailMock.mockReset();
    fetchDocumentVersionMock.mockReset();
    mutateMock.mockReset();
    fetchWorkflowCommentsMock.mockResolvedValue([listItem()]);
    fetchDocumentVersionMock.mockResolvedValue(detail({ etag: "evt-new" }));
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads comments list on mount", async () => {
    mountPanel();
    await flushPromises();
    expect(fetchWorkflowCommentsMock).toHaveBeenCalledWith("DOC-1", 2);
    expect(fetchWorkflowCommentsMock).toHaveBeenCalledTimes(1);
  });

  it("shows create form only when comments action enabled and PDF page present", async () => {
    const enabled = mountPanel();
    await flushPromises();
    expect(enabled.find("[data-testid=comments-create-form]").exists()).toBe(true);

    const disabled = mountPanel({ detail: detail({ allowed_actions: [commentsDescriptor(false)] }) });
    await flushPromises();
    expect(disabled.find("[data-testid=comments-create-form]").exists()).toBe(false);

    const noPdf = mountPanel({ hasPdf: false });
    await flushPromises();
    expect(noPdf.find("[data-testid=comments-create-form]").exists()).toBe(false);
  });

  it("submits trimmed comment with exact If-Match and PDF_REVIEW body", async () => {
    mutateMock.mockResolvedValue({});
    const wrapper = mountPanel();
    await flushPromises();

    const textarea = wrapper.get("[data-testid=comments-text-input]");
    await textarea.setValue("  Mein Kommentar  ");
    await wrapper.get("[data-testid=comments-create-form]").trigger("submit");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith({
      method: "POST",
      path: "/documents/versions/DOC-1/2/comments",
      ifMatch: "evt-42",
      body: {
        json: {
          context: "PDF_REVIEW",
          page_number: 1,
          comment_text: "Mein Kommentar",
        },
      },
    });
    expect(wrapper.find("[data-testid=comments-submit-success]").exists()).toBe(true);
    expect(fetchDocumentVersionMock).toHaveBeenCalled();
    expect(fetchWorkflowCommentsMock).toHaveBeenCalledTimes(1);
  });

  it("reloads comments exactly once when parent applies post-create etag", async () => {
    mutateMock.mockResolvedValue({});
    fetchDocumentVersionMock.mockResolvedValueOnce(detail({ etag: "evt-new" }));
    const wrapper = mountPanelWithParent();
    await flushPromises();
    expect(fetchWorkflowCommentsMock).toHaveBeenCalledTimes(1);

    await wrapper.get("[data-testid=comments-text-input]").setValue("Integrationskommentar");
    await wrapper.get("[data-testid=comments-create-form]").trigger("submit");
    await flushPromises();

    expect(fetchWorkflowCommentsMock).toHaveBeenCalledTimes(2);
    expect(wrapper.find("[data-testid=comments-submit-success]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=comments-submit-error]").exists()).toBe(false);
    const submitButton = wrapper.get("[data-testid=comments-submit]").element as HTMLButtonElement;
    expect(submitButton.disabled).toBe(false);
  });

  it("blocks double submit while mutation is in flight", async () => {
    let resolveMutate: (value: unknown) => void = () => undefined;
    mutateMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveMutate = resolve;
        }),
    );

    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.get("[data-testid=comments-text-input]").setValue("Eins");
    const form = wrapper.get("[data-testid=comments-create-form]");
    await form.trigger("submit");
    await form.trigger("submit");
    expect(mutateMock).toHaveBeenCalledTimes(1);
    resolveMutate({});
    await flushPromises();
  });

  it("emits conflict on 409 without success state", async () => {
    mutateMock.mockRejectedValue(
      new MutationClientError("conflict", "conflict", 409, { currentEtag: "evt-other" }),
    );
    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.get("[data-testid=comments-text-input]").setValue("Konflikt");
    await wrapper.get("[data-testid=comments-create-form]").trigger("submit");
    await flushPromises();

    const emitted = wrapper.emitted("conflict");
    expect(emitted).toBeTruthy();
    const [error, context] = emitted![0] as [MutationClientError, { reason?: string }];
    expect(error.kind).toBe("conflict");
    expect(context.reason).toBe("Konflikt");
    expect(wrapper.find("[data-testid=comments-submit-success]").exists()).toBe(false);
  });

  it("emits conflict on 428 without success state", async () => {
    mutateMock.mockRejectedValue(
      new MutationClientError("precondition", "precondition_required", 428),
    );
    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.get("[data-testid=comments-text-input]").setValue("Precondition");
    await wrapper.get("[data-testid=comments-create-form]").trigger("submit");
    await flushPromises();
    expect(wrapper.emitted("conflict")).toBeTruthy();
    expect(wrapper.find("[data-testid=comments-submit-success]").exists()).toBe(false);
  });

  it("lazy-loads comment detail and localizes source_kind without raw codes", async () => {
    fetchWorkflowCommentDetailMock.mockResolvedValue({
      comment_id: "cmt-1",
      context: "PDF_REVIEW",
      document_id: "DOC-1",
      full_text: "Volltext",
      ref_no: "C-1",
      source_kind: "PDF_APP",
      status: "ACTIVE",
      version: 2,
      page_number: 1,
    });

    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.get("[data-testid=comment-summary-cmt-1]").trigger("click");
    await flushPromises();

    const source = wrapper.get("[data-testid=comment-detail-source-kind]").text();
    expect(source).toBe("PDF-Kommentar");
    expect(source).not.toContain("PDF_APP");
    expect(wrapper.get("[data-testid=comment-detail-full-text]").text()).toBe("Volltext");
  });

  it.each([
    ["Anna", "Anna"],
    [null, "Unbekannter Autor"],
    ["", "Unbekannter Autor"],
    ["   ", "Unbekannter Autor"],
    ["550e8400-e29b-41d4-a716-446655440000", "Unbekannter Autor"],
    ["a1b2c3d4e5f6478990abcdef12345678", "Unbekannter Autor"],
  ])("localizes author_display %p without leaking technical ids", async (authorDisplay, expected) => {
    fetchWorkflowCommentsMock.mockResolvedValueOnce([
      { ...listItem(), author_display: authorDisplay },
    ]);
    const wrapper = mountPanel();
    await flushPromises();
    const author = wrapper.get(".comment-list__author").text();
    expect(author).toBe(expected);
    if (authorDisplay === "Anna") {
      expect(author).toContain("Anna");
    } else {
      expect(author).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/i);
      expect(author).not.toMatch(/^[0-9a-f]{32}$/i);
    }
  });

  it("does not show raw status codes in list", async () => {
    const wrapper = mountPanel();
    await flushPromises();
    const text = wrapper.get("[data-testid=comment-list-item]").text();
    expect(text).toContain("Aktiv");
    expect(text).not.toContain("ACTIVE");
  });

  it("localizes version and page metadata without hardcoded labels", async () => {
    const wrapper = mountPanel();
    await flushPromises();
    const meta = wrapper.get("[data-testid=comment-list-meta]").text();
    expect(meta).toContain("Version 2");
    expect(meta).toContain("Seite 1");
    expect(meta).not.toMatch(/\bv\d+\b/);
    expect(meta).not.toContain("S.");
  });

  it("keeps create success when post-create refresh fails", async () => {
    mutateMock.mockResolvedValue({});
    fetchDocumentVersionMock.mockRejectedValueOnce(new Error("refresh failed"));
    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.get("[data-testid=comments-text-input]").setValue("Erfolg");
    await wrapper.get("[data-testid=comments-create-form]").trigger("submit");
    await flushPromises();
    expect(wrapper.find("[data-testid=comments-submit-success]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=comments-submit-error]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=comments-submit-refresh-error]").exists()).toBe(true);
  });

  it("ignores stale comment detail response after CommentList unmount", async () => {
    let resolveSlow: (value: unknown) => void = () => undefined;
    fetchWorkflowCommentDetailMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveSlow = resolve;
        }),
    );

    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.get("[data-testid=comment-summary-cmt-1]").trigger("click");
    wrapper.unmount();
    resolveSlow({
      comment_id: "cmt-1",
      context: "PDF_REVIEW",
      document_id: "DOC-1",
      full_text: "Late detail",
      ref_no: "C-1",
      source_kind: "PDF_APP",
      status: "ACTIVE",
      version: 2,
      page_number: 1,
    });
    await flushPromises();
    expect(fetchWorkflowCommentDetailMock).toHaveBeenCalledTimes(1);
  });

  it("ignores stale comment list response after unmount", async () => {
    let resolveSlow: (value: unknown) => void = () => undefined;
    fetchWorkflowCommentsMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveSlow = resolve;
        }),
    );

    const wrapper = mountPanel();
    wrapper.unmount();
    resolveSlow([listItem("late")]);
    await flushPromises();
    expect(fetchWorkflowCommentsMock).toHaveBeenCalledTimes(1);
  });

  it("hides create form and blocks mutate when product writes are unavailable", async () => {
    __setBootstrapWritesAllowedForTest(false);
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find("[data-testid=comments-writes-blocked]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=comments-create-form]").exists()).toBe(false);
    expect(mutateMock).not.toHaveBeenCalled();
  });
});

describe("mutate export sanity", () => {
  it("re-exports mutate for comment create path", () => {
    expect(typeof mutate).toBe("function");
  });
});
