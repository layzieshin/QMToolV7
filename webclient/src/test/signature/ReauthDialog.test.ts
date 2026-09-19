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

import ReauthDialog from "../../components/signature/ReauthDialog.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";

function queryInput(): HTMLInputElement {
  const element = document.body.querySelector('[data-testid="reauth-password"] input');
  if (!element) {
    throw new Error("missing reauth password input");
  }
  return element as HTMLInputElement;
}

function clickTestId(testId: string): void {
  const element = document.body.querySelector(`[data-testid="${testId}"]`);
  if (!element) {
    throw new Error(`missing ${testId}`);
  }
  (element as HTMLElement).click();
}

function mountDialog(open = true) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const wrapper = mount(ReauthDialog, {
    props: { modelValue: open },
    attachTo: host,
    global: { plugins: [i18n, vuetify] },
  });
  return { wrapper, host };
}

describe("ReauthDialog", () => {
  beforeEach(() => {
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

  it("emits trimmed password on submit and clears it after close", async () => {
    const { wrapper } = mountDialog(true);
    await flushPromises();
    const input = queryInput();
    input.value = "  secret-pass  ";
    input.dispatchEvent(new Event("input"));
    await flushPromises();
    clickTestId("reauth-submit");
    await flushPromises();
    expect(wrapper.emitted("submit")).toEqual([["secret-pass"]]);

    await wrapper.setProps({ modelValue: false });
    await flushPromises();
    await wrapper.setProps({ modelValue: true });
    await flushPromises();
    expect(queryInput().value).toBe("");
  });

  it("does not emit empty or whitespace-only passwords", async () => {
    const { wrapper } = mountDialog(true);
    await flushPromises();
    const submit = document.body.querySelector('[data-testid="reauth-submit"]') as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    const input = queryInput();
    input.value = "   ";
    input.dispatchEvent(new Event("input"));
    await flushPromises();
    expect(submit.disabled).toBe(true);
    clickTestId("reauth-submit");
    await flushPromises();
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("clears password on cancel and backend error", async () => {
    const { wrapper } = mountDialog(true);
    await flushPromises();
    const input = queryInput();
    input.value = "secret-pass";
    input.dispatchEvent(new Event("input"));
    clickTestId("reauth-cancel");
    await flushPromises();
    expect(wrapper.emitted("cancel")).toHaveLength(1);
    await wrapper.setProps({ modelValue: true });
    await flushPromises();
    clickTestId("reauth-submit");
    await flushPromises();
    expect(wrapper.emitted("submit")).toBeUndefined();

    input.value = "secret-pass";
    input.dispatchEvent(new Event("input"));
    await flushPromises();
    await wrapper.setProps({ errorMessage: "Fehler" });
    await flushPromises();
    expect(queryInput().value).toBe("");
    clickTestId("reauth-submit");
    await flushPromises();
    expect(wrapper.emitted("submit")).toBeUndefined();
  });
});
