import { mount, type VueWrapper } from "@vue/test-utils";
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

import type { VersionStateResponse } from "../../api/client";
import ConflictDialog from "../../components/conflict/ConflictDialog.vue";
import {
  useConflictRecovery,
  type ConflictRecoveryState,
} from "../../composables/useConflictRecovery";
import { MutationClientError } from "../../api/mutationClient";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";

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

function queryBody(testId: string): HTMLElement {
  const element = document.body.querySelector(`[data-testid="${testId}"]`);
  if (!element) {
    throw new Error(`missing element ${testId} in document.body`);
  }
  return element as HTMLElement;
}

function detailFixture(etag = "evt-1"): VersionStateResponse {
  return {
    etag,
    allowed_actions: [],
    available_actions: [],
    state: {
      document_id: "DOC-1",
      version: 1,
      status: "PLANNED",
      workflow_profile_id: "http_flow_profile",
      assignments: { editors: [], reviewers: [], approvers: [] },
    },
  } as unknown as VersionStateResponse;
}

function mountRecoveryHarness(
  reloadImpl: () => Promise<void>,
  initialDetail: VersionStateResponse | null = detailFixture(),
): { recovery: ConflictRecoveryState; detail: ReturnType<typeof ref<VersionStateResponse | null>> } {
  const holder: { recovery: ConflictRecoveryState | null } = { recovery: null };
  const detail = ref<VersionStateResponse | null>(initialDetail);
  mount(
    defineComponent({
      setup() {
        holder.recovery = useConflictRecovery({
          detail,
          reload: reloadImpl,
        });
        return () => null;
      },
    }),
  );
  if (!holder.recovery) {
    throw new Error("recovery harness failed to initialize");
  }
  return { recovery: holder.recovery, detail };
}

describe("ConflictDialog", () => {
  let wrapper: VueWrapper | null = null;
  let host: HTMLElement | null = null;

  function mountDialog(
    modelValue = true,
    loading = false,
    extraProps: Record<string, unknown> = {},
    slots: Record<string, string> = {},
  ): VueWrapper {
    host = document.createElement("div");
    document.body.appendChild(host);
    return mount(ConflictDialog, {
      props: {
        modelValue,
        loading,
        reloadFailed: false,
        showingLocalInput: false,
        actionLabel: null,
        preservedReason: null,
        ...extraProps,
      },
      slots,
      attachTo: host,
      global: {
        plugins: [i18n, vuetify],
      },
    });
  }

  beforeEach(() => {
    stubBrowserApis();
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    host?.remove();
    host = null;
    vi.unstubAllGlobals();
  });

  it("renders localized conflict copy", () => {
    wrapper = mountDialog();
    expect(queryBody("conflict-dialog").textContent).toContain("Konflikt erkannt");
    expect(document.body.textContent).toContain("Aktuellen Stand laden");
    expect(document.body.textContent).toContain("Meine Eingabe ansehen");
  });

  it("uses responsive right-aligned wrap layout and keeps all conflict actions", () => {
    wrapper = mountDialog();
    const actions = queryBody("conflict-dialog-actions");
    expect(actions.classList.contains("conflict-dialog-actions")).toBe(true);
    expect(queryBody("conflict-cancel").textContent).toContain("Abbrechen");
    expect(queryBody("conflict-view-local").textContent).toContain("Meine Eingabe ansehen");
    expect(queryBody("conflict-load-server").textContent).toContain("Aktuellen Stand laden");
  });

  it("emits loadServerState when primary action is clicked", async () => {
    wrapper = mountDialog();
    await queryBody("conflict-load-server").click();
    expect(wrapper.emitted("loadServerState")).toHaveLength(1);
  });

  it("emits viewLocalInput without closing when view-local is clicked", async () => {
    wrapper = mountDialog();
    await queryBody("conflict-view-local").click();
    expect(wrapper.emitted("viewLocalInput")).toHaveLength(1);
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("shows preserved local input inside the dialog without closing", async () => {
    wrapper = mountDialog(true, false, {
      showingLocalInput: true,
      actionLabel: "Review ablehnen",
      preservedReason: "Bitte nacharbeiten",
    });
    expect(queryBody("conflict-local-input").textContent).toContain("Review ablehnen");
    expect(queryBody("conflict-local-reason").textContent).toContain("Bitte nacharbeiten");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("shows localized reload error without closing the dialog", () => {
    wrapper = mountDialog(true, false, { reloadFailed: true });
    expect(queryBody("conflict-reload-error").textContent).toContain(
      "Der aktuelle Stand konnte nicht geladen werden.",
    );
    expect(queryBody("conflict-dialog")).toBeTruthy();
  });

  it("emits cancel when dialog cancel is clicked", async () => {
    wrapper = mountDialog();
    await queryBody("conflict-cancel").click();
    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("disables actions while loading", () => {
    wrapper = mountDialog(true, true);
    expect(queryBody("conflict-view-local").hasAttribute("disabled")).toBe(true);
    expect(queryBody("conflict-cancel").hasAttribute("disabled")).toBe(true);
  });

  it("does not render local-input-details slot when local input is hidden", () => {
    wrapper = mountDialog(true, false, { showingLocalInput: false }, {
      "local-input-details": '<p data-testid="slot-content">Details</p>',
    });
    expect(document.body.querySelector('[data-testid="slot-content"]')).toBeFalsy();
  });

  it("renders local-input-details slot inside the dialog when local input is shown", () => {
    wrapper = mountDialog(true, false, { showingLocalInput: true }, {
      "local-input-details": '<p data-testid="slot-content">Details</p>',
    });
    expect(queryBody("slot-content").textContent).toContain("Details");
    expect(queryBody("conflict-local-input").contains(queryBody("slot-content"))).toBe(true);
  });
});

describe("useConflictRecovery", () => {
  it("closes and clears context only after a successful reload with valid detail", async () => {
    const reload = vi.fn(async () => undefined);
    const { recovery, detail } = mountRecoveryHarness(reload);
    const error = new MutationClientError("conflict", "conflict", 409);

    recovery.openConflict(error, {
      actionLabel: "Workflow starten",
      reason: "Testgrund",
    });
    expect(recovery.conflictVisible.value).toBe(true);
    expect(recovery.preservedContext.value?.actionLabel).toBe("Workflow starten");

    await recovery.loadServerState();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(recovery.conflictVisible.value).toBe(false);
    expect(recovery.preservedContext.value).toBeNull();
    expect(recovery.reloadFailed.value).toBe(false);

    detail.value = null;
    recovery.openConflict(error, { actionLabel: "Workflow starten" });
    await recovery.loadServerState();
    expect(recovery.conflictVisible.value).toBe(true);
    expect(recovery.preservedContext.value?.actionLabel).toBe("Workflow starten");
    expect(recovery.reloadFailed.value).toBe(true);
  });

  it("keeps dialog open and exposes local input without resubmitting", async () => {
    const reload = vi.fn(async () => undefined);
    const { recovery } = mountRecoveryHarness(reload);
    recovery.openConflict(new MutationClientError("conflict", "conflict", 409), {
      actionLabel: "Workflow starten",
      reason: "Konfliktgrund",
    });

    recovery.viewLocalInput();
    expect(recovery.showingLocalInput.value).toBe(true);
    expect(recovery.conflictVisible.value).toBe(true);
    expect(reload).not.toHaveBeenCalled();
  });

  it("discards preserved context on cancel", () => {
    const reload = vi.fn(async () => undefined);
    const { recovery } = mountRecoveryHarness(reload);
    recovery.openConflict(new MutationClientError("conflict", "conflict", 409), {
      actionLabel: "Workflow starten",
    });
    recovery.cancelConflict();
    expect(recovery.conflictVisible.value).toBe(false);
    expect(recovery.preservedContext.value).toBeNull();
  });
});
