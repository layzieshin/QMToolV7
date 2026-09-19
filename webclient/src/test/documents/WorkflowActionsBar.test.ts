import { flushPromises, mount } from "@vue/test-utils";
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
  mutationConflictCurrentEtag,
  mutationConflictCurrentState,
} from "../../api/mutationClient";
import WorkflowActionsBar from "../../components/documents/WorkflowActionsBar.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";

const mutateMock = vi.hoisted(() => vi.fn());

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

function action(overrides: Partial<ActionDescriptor> = {}): ActionDescriptor {
  return {
    code: "start",
    label_key: "documents.action.start",
    enabled: true,
    destructive: false,
    severity: "info" as const,
    requires_confirmation: false,
    requires_reason: false,
    disabled_reason: null,
    ...overrides,
  } as ActionDescriptor;
}

function detail(overrides: Partial<VersionStateResponse> = {}): VersionStateResponse {
  const baseActions: ActionDescriptor[] = [action()];
  return {
    etag: "evt-1",
    allowed_actions: baseActions,
    available_actions: ["start"],
    state: {
      document_id: "DOC-1",
      version: 1,
      status: "PLANNED",
      workflow_profile_id: "http_flow_profile",
      assignments: { editors: [], reviewers: [], approvers: [] },
    },
    ...overrides,
  } as VersionStateResponse;
}

function mountBar(detailValue: VersionStateResponse) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const wrapper = mount(WorkflowActionsBar, {
    props: {
      detail: detailValue,
      documentId: "DOC-1",
      version: 1,
    },
    attachTo: host,
    global: {
      plugins: [i18n, vuetify],
    },
  });
  return { wrapper, host };
}

describe("WorkflowActionsBar", () => {
  beforeEach(() => {
    stubBrowserApis();
    mutateMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders enabled workflow actions from allowed_actions", () => {
    const { wrapper } = mountBar(detail());
    expect(wrapper.get('[data-testid="workflow-actions-bar"]').text()).toContain("Workflow starten");
  });

  it("does not render assign_roles from allowed_actions", () => {
    const { wrapper } = mountBar(
      detail({
        allowed_actions: [
          action(),
          action({
            code: "assign_roles",
            label_key: "documents.action.assign_roles",
            severity: "info" as const,
          }),
        ],
      } as Partial<VersionStateResponse>),
    );
    expect(wrapper.text()).not.toContain("Rollen zuweisen");
  });

  it("executes start with profile_id and If-Match", async () => {
    mutateMock.mockResolvedValueOnce(detail({ etag: "evt-2", state: { ...detail().state, status: "IN_PROGRESS" } }));
    const { wrapper } = mountBar(detail());
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(mutateMock).toHaveBeenCalledWith({
      method: "POST",
      path: "/documents/versions/DOC-1/1/workflow/start",
      ifMatch: "evt-1",
      body: { json: { profile_id: "http_flow_profile" } },
    });
    expect(wrapper.emitted("updated")).toHaveLength(1);
  });

  it("emits conflict on HTTP 409 without treating it as success", async () => {
    mutateMock.mockRejectedValueOnce(
      new MutationClientError("conflict", "conflict", 409, {
        errorCode: "document_conflict",
        currentEtag: "evt-new",
        body: { detail: { error: "document_conflict", message: "newer" } },
      }),
    );
    const { wrapper } = mountBar(detail());
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.emitted("updated")).toBeUndefined();
    expect(wrapper.emitted("conflict")).toHaveLength(1);
  });

  it("blocks a second mutation while the first is in flight", async () => {
    let resolveFirst: (value: VersionStateResponse) => void = () => undefined;
    mutateMock.mockImplementationOnce(
      () =>
        new Promise<VersionStateResponse>((resolve) => {
          resolveFirst = resolve;
        }),
    );
    const { wrapper } = mountBar(
      detail({
        allowed_actions: [
          action(),
          action({
            code: "complete_editing",
            label_key: "documents.action.complete_editing",
            severity: "info" as const,
          }),
        ],
      } as Partial<VersionStateResponse>),
    );
    const buttons = wrapper.findAll("button");
    await buttons[0].trigger("click");
    await buttons[1].trigger("click");
    expect(mutateMock).toHaveBeenCalledTimes(1);
    resolveFirst(detail({ etag: "evt-2" }));
    await flushPromises();
  });

  it("renders destructive abort in the overflow menu", () => {
    const { wrapper } = mountBar(
      detail({
        allowed_actions: [
          action({
            code: "abort",
            label_key: "documents.action.abort",
            destructive: true,
            requires_confirmation: true,
            severity: "danger" as const,
          }),
        ],
      } as Partial<VersionStateResponse>),
    );
    expect(wrapper.get('button[aria-label="Weitere Aktionen"]')).toBeTruthy();
  });

  it("emits conflict on HTTP 428 without treating it as success", async () => {
    mutateMock.mockRejectedValueOnce(
      new MutationClientError("precondition", "precondition_required", 428, {
        errorCode: "if_match_required",
        body: { detail: { error: "if_match_required", message: "If-Match required" } },
      }),
    );
    const { wrapper } = mountBar(detail());
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.emitted("updated")).toBeUndefined();
    expect(wrapper.emitted("conflict")).toHaveLength(1);
  });

  it("exposes typed conflict payload helpers for bare current_state and current_etag", () => {
    const statePayload = {
      document_id: "DOC-1",
      version: 1,
      status: "PLANNED",
      workflow_profile_id: "http_flow_profile",
      assignments: { editors: ["u1"], reviewers: [], approvers: [] },
    };
    const error = new MutationClientError("conflict", "conflict", 409, {
      errorCode: "document_conflict",
      currentEtag: "evt-server",
      body: {
        detail: {
          error: "document_conflict",
          message: "newer",
          current_etag: "evt-server",
          current_state: statePayload,
        },
      },
    });
    expect(mutationConflictCurrentState(error)).toEqual(statePayload);
    expect(mutationConflictCurrentEtag(error)).toBe("evt-server");
    expect(error.body?.detail).toMatchObject({ error: "document_conflict", message: "newer" });
  });

  async function submitReasonMutation(
    actionCode: "review_reject" | "approval_reject",
    labelKey: string,
    pathSuffix: string,
    reason: string,
  ): Promise<void> {
    mutateMock.mockResolvedValueOnce(detail({ etag: "evt-2" }));
    const { wrapper } = mountBar(
      detail({
        allowed_actions: [
          action({
            code: actionCode,
            label_key: labelKey,
            requires_reason: true,
            severity: "warning" as const,
          }),
        ],
      } as Partial<VersionStateResponse>),
    );
    await wrapper.get("button").trigger("click");
    await flushPromises();
    const textarea = document.body.querySelector("textarea");
    expect(textarea).toBeTruthy();
    textarea!.value = reason;
    textarea!.dispatchEvent(new Event("input"));
    await flushPromises();
    const submit = document.body.querySelector('[data-testid="workflow-reason-dialog"] button:last-child');
    expect(submit).toBeTruthy();
    await (submit as HTMLElement).click();
    await flushPromises();
    expect(mutateMock).toHaveBeenCalledWith({
      method: "POST",
      path: `/documents/versions/DOC-1/1/workflow/${pathSuffix}`,
      ifMatch: "evt-1",
      body: { json: { free_text: reason.trim() } },
    });
  }

  it("sends review_reject with free_text only", async () => {
    await submitReasonMutation(
      "review_reject",
      "documents.action.review_reject",
      "review/reject",
      "  Ablehnungsgrund  ",
    );
  });

  it("sends approval_reject with free_text only", async () => {
    await submitReasonMutation(
      "approval_reject",
      "documents.action.approval_reject",
      "approval/reject",
      "Freigabe verweigert",
    );
  });
});
