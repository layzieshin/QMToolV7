import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
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
import { ApiTransportError } from "../api/client";
import { i18n } from "../i18n";
import vuetify from "../plugins/vuetify";
import { __resetAuthBootstrapForTest, createAppRouter } from "../router/index";
import { routes } from "../router/routes";
import { __resetAppShellStateForTest } from "../state/appShell";

const meAuthenticated = {
  user_id: "u1",
  session_id: "s1",
  request_id: "r1",
  organization_id: "org",
  username: "bob",
  global_roles: ["USER"],
  is_qmb: false,
  authenticated_at: "2026-01-01T00:00:00Z",
};

const { fetchMe, probeHealth, loginBrowser, logoutBrowser, bootstrapCsrf } = vi.hoisted(() => ({
  fetchMe: vi.fn(),
  probeHealth: vi.fn(async () => true),
  loginBrowser: vi.fn(async () => undefined),
  logoutBrowser: vi.fn(async () => undefined),
  bootstrapCsrf: vi.fn(async () => undefined),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    probeHealth,
    fetchMe,
    loginBrowser,
    logoutBrowser,
    bootstrapCsrf,
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
  __resetAuthBootstrapForTest();
  const router = createAppRouter(createMemoryHistory());
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
    __resetAppShellStateForTest();
    __resetAuthBootstrapForTest();
    vi.clearAllMocks();
    fetchMe.mockReset();
    probeHealth.mockResolvedValue(true);
  });

  it("registers home and login routes in the production route table", () => {
    expect(routes[0]?.children?.some((route) => route.name === "home")).toBe(true);
    expect(routes[0]?.children?.some((route) => route.name === "login")).toBe(true);
    const home = routes[0]?.children?.find((route) => route.name === "home");
    expect(home?.meta?.requiresAuth).toBe(true);
  });

  it("renders LoginView through App, AppLayout, AppShell and VApp at /login under anonymous guard refresh", async () => {
    fetchMe.mockRejectedValue(new ApiTransportError("unauthorized", 401, null));
    const { wrapper, router } = await mountAppAt("/login");

    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe("/login");
      expect(wrapper.find(".v-application").exists()).toBe(true);
      expect(wrapper.find("[data-testid=app-shell]").exists()).toBe(true);
      expect(wrapper.find("[data-testid=login-panel]").exists()).toBe(true);
    });

    expect(wrapper.text()).toContain("Anmeldung");
    expect(wrapper.findComponent({ name: "LoginView" }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: "AppLayout" }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: "AppShell" }).exists()).toBe(true);
  });

  it("renders the shell home route through App at / under authenticated guard refresh", async () => {
    fetchMe.mockResolvedValue(meAuthenticated);
    const { wrapper, router } = await mountAppAt("/");

    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe("/");
      expect(wrapper.find(".v-application").exists()).toBe(true);
      expect(wrapper.find("[data-testid=app-shell]").exists()).toBe(true);
      expect(wrapper.find("[data-testid=shell-placeholder]").exists()).toBe(true);
    });

    expect(wrapper.text()).toContain("Start");
    expect(wrapper.findComponent({ name: "ShellHomeView" }).exists()).toBe(true);
  });
});
