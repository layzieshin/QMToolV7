import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

import type { ActionDescriptor } from "../actions/actionTypes";
import ActionButton from "../components/ActionButton.vue";
import ActionOverflowMenu from "../components/ActionOverflowMenu.vue";
import { i18n } from "../i18n";
import vuetify from "../plugins/vuetify";

function descriptor(overrides: Partial<ActionDescriptor> = {}): ActionDescriptor {
  return {
    code: "start",
    label_key: "documents.action.start",
    enabled: true,
    destructive: false,
    severity: "info",
    requires_confirmation: false,
    requires_reason: false,
    disabled_reason: null,
    signature_required: false,
    assignment_kind: null,
    ...overrides,
  };
}

function mountActionButton(props: { descriptor: ActionDescriptor; supported: boolean }) {
  return mount(ActionButton, {
    props,
    global: {
      plugins: [vuetify, i18n],
    },
  });
}

function mountOverflowMenu(
  props: {
    actions: ActionDescriptor[];
    supportedCodes: readonly string[];
    productWritesAllowed?: boolean;
    productWritesBlockedMessage?: string;
  },
) {
  return mount(ActionOverflowMenu, {
    props,
    global: {
      plugins: [vuetify, i18n],
    },
  });
}

function buttonElement(wrapper: ReturnType<typeof mount>): HTMLButtonElement {
  const button = wrapper.find("button");
  expect(button.exists()).toBe(true);
  return button.element as HTMLButtonElement;
}

describe("ActionButton", () => {
  beforeEach(() => {
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
  });

  it("renders translated label from label_key", () => {
    const wrapper = mountActionButton({
      descriptor: descriptor(),
      supported: true,
    });

    expect(wrapper.text()).toContain("Workflow starten");
    expect(wrapper.text()).not.toContain("documents.action.start");
    expect(wrapper.text()).not.toMatch(/\bstart\b/);
  });

  it("uses generic fallback for unknown label keys without showing raw code or key", () => {
    const wrapper = mountActionButton({
      descriptor: descriptor({
        code: "mystery_action",
        label_key: "documents.action.unknown_future_action",
      }),
      supported: true,
    });

    expect(wrapper.text()).toBe("Aktion");
    expect(wrapper.text()).not.toContain("mystery_action");
    expect(wrapper.text()).not.toContain("unknown_future_action");
  });

  it("exposes disabled_reason as accessible title and blocks emit", async () => {
    const wrapper = mountActionButton({
      descriptor: descriptor({
        enabled: false,
        disabled_reason: "document is not visible to the current actor",
      }),
      supported: true,
    });

    const button = buttonElement(wrapper);
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("title")).toBe("document is not visible to the current actor");
    expect(button.getAttribute("aria-label")).toBe("document is not visible to the current actor");

    await button.click();
    expect(wrapper.emitted("action")).toBeUndefined();
  });

  it("does not emit for unsupported enabled actions", async () => {
    const wrapper = mountActionButton({
      descriptor: descriptor(),
      supported: false,
    });

    const button = buttonElement(wrapper);
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("title")).toBe("Aktion wird hier nicht unterstützt");

    await button.click();
    expect(wrapper.emitted("action")).toBeUndefined();
  });

  it("emits exactly once for enabled supported actions", async () => {
    const wrapper = mountActionButton({
      descriptor: descriptor({ severity: "warning" }),
      supported: true,
    });

    const button = buttonElement(wrapper);
    expect(button.disabled).toBe(false);
    await button.click();
    await flushPromises();

    const emitted = wrapper.emitted("action");
    expect(emitted).toHaveLength(1);
    expect(emitted?.[0]?.[0]).toEqual(descriptor({ severity: "warning" }));
  });

  it("applies severity styling from descriptor metadata", () => {
    const wrapper = mountActionButton({
      descriptor: descriptor({ severity: "warning" }),
      supported: true,
    });

    expect(buttonElement(wrapper).className).toMatch(/text-warning|bg-warning/);
  });

  it("does not render destructive actions as primary buttons", () => {
    const wrapper = mountActionButton({
      descriptor: descriptor({ code: "abort", destructive: true, severity: "danger" }),
      supported: true,
    });

    expect(wrapper.find("button").exists()).toBe(false);
  });

  it("does not write to web storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const wrapper = mountActionButton({
      descriptor: descriptor(),
      supported: true,
    });

    await buttonElement(wrapper).click();
    expect(setItem).not.toHaveBeenCalled();
    setItem.mockRestore();
  });
});

describe("ActionOverflowMenu", () => {
  beforeEach(() => {
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
  });

  it("renders destructive actions and respects disabled state", async () => {
    const wrapper = mountOverflowMenu({
      actions: [
        descriptor({ code: "start", destructive: false }),
        descriptor({
          code: "abort",
          label_key: "documents.action.abort",
          destructive: true,
          severity: "danger",
          enabled: false,
          disabled_reason: "not allowed for observer",
        }),
        descriptor({
          code: "archive",
          label_key: "documents.action.archive",
          destructive: true,
          severity: "danger",
          requires_confirmation: true,
        }),
      ],
      supportedCodes: ["abort", "archive"],
    });

    await buttonElement(wrapper).click();
    await flushPromises();

    const items = document.body.querySelectorAll(".v-list-item");
    expect(items.length).toBe(2);
    expect(document.body.textContent).toContain("Workflow abbrechen");
    expect(document.body.textContent).toContain("Archivieren");

    const disabledItem = Array.from(items).find((item) =>
      item.textContent?.includes("Workflow abbrechen"),
    ) as HTMLElement;
    expect(disabledItem.className).toMatch(/v-list-item--disabled/);

    const enabledItem = Array.from(items).find((item) =>
      item.textContent?.includes("Archivieren"),
    ) as HTMLElement;
    await enabledItem.click();
    await flushPromises();

    const emitted = wrapper.emitted("action");
    expect(emitted).toHaveLength(1);
    expect(emitted?.[0]?.[0]).toMatchObject({ code: "archive", destructive: true });
  });

  it("disables destructive overflow actions when product writes are blocked", async () => {
    const wrapper = mountOverflowMenu({
      actions: [
        descriptor({
          code: "archive",
          label_key: "documents.action.archive",
          destructive: true,
          severity: "danger",
        }),
      ],
      supportedCodes: ["archive"],
      productWritesAllowed: false,
      productWritesBlockedMessage: "Writes blocked",
    });

    await buttonElement(wrapper).click();
    await flushPromises();

    const item = document.body.querySelector(".v-list-item") as HTMLElement;
    expect(item.className).toMatch(/v-list-item--disabled/);
    await item.click();
    await flushPromises();
    expect(wrapper.emitted("action")).toBeUndefined();
  });

  it("does not emit for disabled or unsupported destructive actions", async () => {
    const wrapper = mountOverflowMenu({
      actions: [
        descriptor({
          code: "abort",
          label_key: "documents.action.abort",
          destructive: true,
          severity: "danger",
          enabled: false,
          disabled_reason: "blocked",
        }),
        descriptor({
          code: "archive",
          label_key: "documents.action.archive",
          destructive: true,
          severity: "danger",
        }),
      ],
      supportedCodes: ["abort"],
    });

    await buttonElement(wrapper).click();
    await flushPromises();

    const archiveItem = Array.from(document.body.querySelectorAll(".v-list-item")).find((item) =>
      item.textContent?.includes("Archivieren"),
    ) as HTMLElement;
    expect(archiveItem).toBeTruthy();
    await archiveItem.click();
    expect(wrapper.emitted("action")).toBeUndefined();
  });
});
