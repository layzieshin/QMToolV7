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
    fetchMe: vi.fn(async () => {
      throw new actual.ApiTransportError("unauthorized", 401, null);
    }),
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

async function mountAppAt(path: string) {
  stubBrowserApis();
  __resetAppShellStateForTest();
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  });
  await router.push(path);
  await router.isReady();

  const wrapper = mount(App, {
    global: {
      plugins: [router, vuetify, i18n],
    },
    attachTo: document.body,
  });
  await flushPromises();
  return { wrapper, router };
}

describe("router mount", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("registers home and login routes in the production route table", () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    });
    expect(router.getRoutes().some((route) => route.name === "home")).toBe(true);
    expect(router.getRoutes().some((route) => route.name === "login")).toBe(true);
  });

  it("renders LoginView through App, AppLayout, AppShell and VApp at /login", async () => {
    const { wrapper } = await mountAppAt("/login");

    await vi.waitFor(() => {
      expect(wrapper.find(".v-application").exists()).toBe(true);
      expect(wrapper.find("[data-testid=app-shell]").exists()).toBe(true);
      expect(wrapper.find("[data-testid=login-panel]").exists()).toBe(true);
    });

    expect(wrapper.text()).toContain("Anmeldung");
    expect(wrapper.findComponent({ name: "LoginView" }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: "AppLayout" }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: "AppShell" }).exists()).toBe(true);
  });

  it("renders the shell home route through App at /", async () => {
    const { wrapper } = await mountAppAt("/");

    await vi.waitFor(() => {
      expect(wrapper.find(".v-application").exists()).toBe(true);
      expect(wrapper.find("[data-testid=app-shell]").exists()).toBe(true);
      expect(wrapper.find("[data-testid=shell-placeholder]").exists()).toBe(true);
    });

    expect(wrapper.text()).toContain("Start");
    expect(wrapper.findComponent({ name: "ShellHomeView" }).exists()).toBe(true);
  });
});
