import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthState } from "../api/types";

const { retryConnectionMock, refreshAuthMock, shellState, authenticatedUser } =
  vi.hoisted(() => {
    const user = {
      user_id: "u1",
      session_id: "s1",
      request_id: "r1",
      organization_id: "org",
      username: "bob",
      global_roles: ["USER"],
      is_qmb: false,
      authenticated_at: "2026-01-01T00:00:00Z",
    };
    return {
      retryConnectionMock: vi.fn(async () => undefined),
      refreshAuthMock: vi.fn(async () => undefined),
      authenticatedUser: user,
      shellState: {
        connection: "online" as const,
        auth: {
          status: "authenticated" as const,
          user,
        } as AuthState,
        lastError: null,
        loading: false,
      },
    };
  });

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
vi.mock("../components/AppShell.vue", () => ({
  default: {
    name: "AppShell",
    template: '<div data-testid="app-shell-stub"><slot /></div>',
  },
}));

vi.mock("../state/appShell", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../state/appShell")>();
  return {
    ...actual,
    refreshAuth: refreshAuthMock,
    useAppShellState: () => shellState as ReturnType<typeof actual.useAppShellState>,
  };
});

vi.mock("../state/bootstrap", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../state/bootstrap")>();
  return {
    ...actual,
    retryConnection: retryConnectionMock,
  };
});

import ConnectionBanner from "../components/ConnectionBanner.vue";
import ModuleNavigation from "../components/ModuleNavigation.vue";
import { RETURN_URL_QUERY } from "../composables/useReturnUrl";
import { i18n } from "../i18n";
import AppLayout from "../layouts/AppLayout.vue";
import vuetify from "../plugins/vuetify";
import { routes } from "../router/routes";
import {
  __resetBootstrapStateForTest,
  __setBootstrapBannerForTest,
  __setBootstrapModulesForTest,
  useBootstrapState,
} from "../state/bootstrap";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

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

function mountWithPlugins(
  component: Parameters<typeof mount>[0],
  extra: { global?: Record<string, unknown> } = {},
) {
  stubBrowserApis();
  return mount(component, {
    global: {
      plugins: [vuetify, i18n],
      ...extra.global,
    },
    attachTo: document.body,
  });
}

describe("ConnectionBanner", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    __resetBootstrapStateForTest();
    retryConnectionMock.mockClear();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("is hidden when connection is healthy", async () => {
    __setBootstrapBannerForTest("hidden");
    const wrapper = mountWithPlugins(ConnectionBanner);
    await flushPromises();
    expect(wrapper.find("[data-testid=connection-banner]").exists()).toBe(false);
  });

  it("shows offline, reconnecting, maintenance, degraded and restored messages", async () => {
    const modes: Array<{
      mode: "offline" | "reconnecting" | "maintenance" | "degraded" | "restored";
      text: string;
    }> = [
      { mode: "offline", text: "Verbindung unterbrochen" },
      { mode: "reconnecting", text: "Wiederverbinden …" },
      { mode: "maintenance", text: "Wartungsmodus" },
      { mode: "degraded", text: "Eingeschränkter Betrieb" },
      { mode: "restored", text: "Verbindung wiederhergestellt" },
    ];

    for (const entry of modes) {
      __resetBootstrapStateForTest();
      __setBootstrapBannerForTest(entry.mode, entry.mode === "reconnecting");
      const wrapper = mountWithPlugins(ConnectionBanner);
      await flushPromises();
      expect(wrapper.find("[data-testid=connection-banner]").exists()).toBe(true);
      expect(wrapper.get("[data-testid=connection-banner-message]").text()).toContain(entry.text);
      wrapper.unmount();
    }
  });

  it("calls retry exactly once and exposes accessible alert role", async () => {
    __setBootstrapBannerForTest("offline");
    const wrapper = mountWithPlugins(ConnectionBanner);
    const retry = wrapper.get("[data-testid=connection-banner-retry]");
    await retry.trigger("click");
    expect(retryConnectionMock).toHaveBeenCalledTimes(1);
    expect(wrapper.get("[data-testid=connection-banner]").attributes("role")).toBe("alert");
  });

  it("shows retry on maintenance and degraded banners", async () => {
    for (const mode of ["maintenance", "degraded"] as const) {
      __resetBootstrapStateForTest();
      __setBootstrapBannerForTest(mode);
      const wrapper = mountWithPlugins(ConnectionBanner);
      await flushPromises();
      expect(wrapper.find("[data-testid=connection-banner-retry]").exists()).toBe(true);
      wrapper.unmount();
    }
  });

  it("does not show retry on restored banner", async () => {
    __setBootstrapBannerForTest("restored");
    const wrapper = mountWithPlugins(ConnectionBanner);
    await flushPromises();
    expect(wrapper.find("[data-testid=connection-banner-retry]").exists()).toBe(false);
  });

  it("calls retry exactly once from maintenance banner", async () => {
    __setBootstrapBannerForTest("maintenance");
    const wrapper = mountWithPlugins(ConnectionBanner);
    await wrapper.get("[data-testid=connection-banner-retry]").trigger("click");
    expect(retryConnectionMock).toHaveBeenCalledTimes(1);
  });
});

describe("ModuleNavigation", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    __resetBootstrapStateForTest();
  });

  it("shows only licensed, authorized modules with registered routes and german labels", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        ...routes,
        {
          path: "/documents",
          name: "documents",
          component: { template: "<div>Dokumente</div>" },
        },
      ],
    });
    await router.push("/");
    await router.isReady();

    __setBootstrapModulesForTest([
      { id: "documents", licensed: true, authorized: true, capabilities: ["read"] },
      { id: "documents", licensed: true, authorized: false, capabilities: ["read"] },
      { id: "usermanagement", licensed: true, authorized: true, capabilities: ["admin"] },
      { id: "unknown", licensed: true, authorized: true, capabilities: [] },
    ]);

    const wrapper = mountWithPlugins(ModuleNavigation, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();

    const items = wrapper.findAll("[data-testid=module-navigation-item]");
    expect(items).toHaveLength(1);
    expect(items[0]?.text()).toBe("Dokumente");
    expect(wrapper.text()).not.toContain("usermanagement");
    expect(wrapper.text()).not.toContain("unknown");
    expect(wrapper.get("[data-testid=module-navigation]").attributes("aria-label")).toBe(
      "Modulnavigation",
    );
  });

  it("hides documents when route is not registered yet", async () => {
    __setBootstrapModulesForTest([
      { id: "documents", licensed: true, authorized: true, capabilities: ["read"] },
    ]);

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", name: "home", component: { template: "<div />" } }],
    });

    const wrapper = mountWithPlugins(ModuleNavigation, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();

    expect(router.hasRoute("documents")).toBe(false);
    expect(wrapper.find("[data-testid=module-navigation]").exists()).toBe(false);
  });
});

describe("AppLayout bootstrap 401 handoff", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    document.body.innerHTML = "";
    __resetBootstrapStateForTest();
    refreshAuthMock.mockReset();
    shellState.auth = { status: "authenticated", user: authenticatedUser } as AuthState;
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return jsonResponse(401, { detail: { message: "unauthorized" } });
      }
      if (url.includes("/session/connection")) {
        return jsonResponse(200, {
          contract_version: "1",
          maintenance: false,
          service: "qmtool-backend",
          status: "ok",
          writes_allowed: true,
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("refreshes auth once and navigates to login with a safe return URL", async () => {
    refreshAuthMock.mockImplementation(async () => {
      shellState.auth = { status: "anonymous" } as AuthState;
    });

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        ...routes,
        {
          path: "/dashboard",
          name: "dashboard",
          component: { template: "<div />" },
        },
      ],
    });
    await router.push("/dashboard");
    await router.isReady();

    mount(AppLayout, {
      global: { plugins: [router, vuetify, i18n] },
      attachTo: document.body,
    });
    await flushPromises();
    await vi.waitFor(() => {
      expect(refreshAuthMock).toHaveBeenCalledTimes(1);
      expect(router.currentRoute.value.path).toBe("/login");
    });

    expect(useBootstrapState().modules).toEqual([]);
    expect(router.currentRoute.value.query[RETURN_URL_QUERY]).toBe("/dashboard");
  });

  it("navigates to change-password when refreshAuth reports password_change_required", async () => {
    refreshAuthMock.mockImplementation(async () => {
      shellState.auth = {
        status: "password_change_required",
        username: "bob",
      } as AuthState;
    });

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        ...routes,
        {
          path: "/reports",
          name: "reports",
          component: { template: "<div />" },
        },
      ],
    });
    await router.push("/reports");
    await router.isReady();

    mount(AppLayout, {
      global: { plugins: [router, vuetify, i18n] },
      attachTo: document.body,
    });
    await flushPromises();
    await vi.waitFor(() => {
      expect(refreshAuthMock).toHaveBeenCalledTimes(1);
      expect(router.currentRoute.value.path).toBe("/change-password");
    });

    expect(useBootstrapState().modules).toEqual([]);
    expect(router.currentRoute.value.query[RETURN_URL_QUERY]).toBe("/reports");
  });

  it("does not navigate when a stale bootstrap 401 resolves after clearBootstrapModules", async () => {
    let resolveBootstrap: ((value: Response) => void) | undefined;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return new Promise<Response>((resolve) => {
          resolveBootstrap = resolve;
        });
      }
      if (url.includes("/session/connection")) {
        return jsonResponse(200, {
          contract_version: "1",
          maintenance: false,
          service: "qmtool-backend",
          status: "ok",
          writes_allowed: true,
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    });
    await router.push("/");
    await router.isReady();

    const wrapper = mount(AppLayout, {
      global: { plugins: [router, vuetify, i18n] },
      attachTo: document.body,
    });
    await flushPromises();

    const { clearBootstrapModules } = await import("../state/bootstrap");
    clearBootstrapModules();
    resolveBootstrap?.(jsonResponse(401, { detail: { message: "unauthorized" } }));
    await flushPromises();

    expect(refreshAuthMock).not.toHaveBeenCalled();
    expect(router.currentRoute.value.path).toBe("/");
    wrapper.unmount();
  });
});
