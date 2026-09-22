import { flushPromises, mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Real Vuetify pulls per-component CSS; stub those side effects locally for jsdom.
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

import App from "../App.vue";
import { i18n } from "../i18n";
import vuetify from "../plugins/vuetify";
import { routes } from "../router/routes";
import { __resetAppShellStateForTest } from "../state/appShell";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    probeHealth: vi.fn(async () => true),
    fetchMe: vi.fn(async () => ({
      user_id: "u1",
      session_id: "s1",
      request_id: "r1",
      organization_id: "org",
      username: "bob",
      global_roles: ["USER"],
      is_qmb: false,
      authenticated_at: "2026-01-01T00:00:00Z",
    })),
    loginBrowser: vi.fn(async () => undefined),
    logoutBrowser: vi.fn(async () => undefined),
    bootstrapCsrf: vi.fn(async () => undefined),
  };
});

function stubBrowserApis(): void {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  Object.defineProperty(window, "ResizeObserver", {
    writable: true,
    configurable: true,
    value: ResizeObserverStub,
  });
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("vuetify shell", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    stubBrowserApis();
    __resetAppShellStateForTest();
  });

  it("uses the real Vuetify application root with AppShell and routed content", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    });
    await router.push("/");
    await router.isReady();

    const wrapper = mount(App, {
      global: {
        plugins: [router, vuetify, i18n],
      },
      attachTo: document.body,
    });
    await flushPromises();

    await vi.waitFor(() => {
      const vApp = wrapper.find(".v-application");
      expect(vApp.exists()).toBe(true);
      expect(vApp.classes()).toContain("v-theme--light");
      expect(wrapper.find(".v-application__wrap").exists()).toBe(true);
      expect(wrapper.find("[data-testid=app-shell]").exists()).toBe(true);
      expect(wrapper.find("[data-testid=shell-placeholder]").exists()).toBe(true);
      expect(wrapper.get("[data-testid=connection-state]").text()).toBe("Verbunden");
    });

    expect(wrapper.findComponent({ name: "VApp" }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: "AppShell" }).exists()).toBe(true);
    expect(wrapper.text()).toContain("bob");
  });
});
