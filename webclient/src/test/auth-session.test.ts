import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
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

import App from "../App.vue";
import { ApiTransportError } from "../api/client";
import {
  RETURN_URL_QUERY,
  buildLoginLocation,
  sanitizeReturnUrl,
} from "../composables/useReturnUrl";
import { i18n } from "../i18n";
import vuetify from "../plugins/vuetify";
import { __resetAuthBootstrapForTest, createAppRouter } from "../router/index";
import {
  __resetAppShellStateForTest,
  login,
  logout,
  refreshAuth,
} from "../state/appShell";
import ChangePasswordView from "../views/ChangePasswordView.vue";

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

const passwordChangeRequiredError = new ApiTransportError("password change required", 409, {
  detail: { error: "password_change_required", message: "password change required" },
});

const { bootstrapCsrf, fetchMe, loginBrowser, changePasswordBrowser, logoutBrowser, probeHealth } =
  vi.hoisted(() => ({
    bootstrapCsrf: vi.fn(async () => undefined),
    fetchMe: vi.fn(),
    loginBrowser: vi.fn(async () => undefined),
    changePasswordBrowser: vi.fn(async () => undefined),
    logoutBrowser: vi.fn(async () => undefined),
    probeHealth: vi.fn(async () => true),
  }));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    bootstrapCsrf,
    fetchMe,
    loginBrowser,
    changePasswordBrowser,
    logoutBrowser,
    probeHealth,
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

describe("return URL sanitization", () => {
  it("accepts safe local deep links", () => {
    expect(sanitizeReturnUrl("/documents/42?status=open")).toBe("/documents/42?status=open");
    expect(sanitizeReturnUrl("/?view=docs")).toBe("/?view=docs");
  });

  it("rejects unsafe return URLs", () => {
    expect(sanitizeReturnUrl("//evil.example/path")).toBe("/");
    expect(sanitizeReturnUrl("https://evil.example/path")).toBe("/");
    expect(sanitizeReturnUrl("/login")).toBe("/");
    expect(sanitizeReturnUrl("/change-password")).toBe("/");
    expect(sanitizeReturnUrl("/docs?token=secret")).toBe("/");
    expect(sanitizeReturnUrl("%2Flogin")).toBe("/");
    expect(sanitizeReturnUrl("%2Fchange-password")).toBe("/");
    expect(sanitizeReturnUrl("/login?returnUrl=%2F")).toBe("/");
  });

  it("builds login redirect with sanitized returnUrl query", () => {
    expect(buildLoginLocation("/documents/42")).toEqual({
      path: "/login",
      query: { [RETURN_URL_QUERY]: "/documents/42" },
    });
    expect(buildLoginLocation("//evil")).toEqual({ path: "/login" });
    expect(buildLoginLocation("/login")).toEqual({ path: "/login" });
  });
});

describe("auth session flows", () => {
  beforeEach(() => {
    __resetAppShellStateForTest();
    __resetAuthBootstrapForTest();
    vi.clearAllMocks();
    fetchMe.mockReset();
    loginBrowser.mockReset();
    loginBrowser.mockResolvedValue(undefined);
    changePasswordBrowser.mockReset();
    changePasswordBrowser.mockResolvedValue(undefined);
    logoutBrowser.mockReset();
    logoutBrowser.mockResolvedValue(undefined);
  });

  it("login calls /auth/me after 204 login without JSON parsing login body", async () => {
    const jsonParse = vi.spyOn(JSON, "parse");
    fetchMe.mockResolvedValueOnce(meAuthenticated);

    await login("bob", "bob-secret");

    expect(loginBrowser).toHaveBeenCalledWith({ username: "bob", password: "bob-secret" });
    expect(fetchMe).toHaveBeenCalledTimes(1);
    expect(jsonParse).not.toHaveBeenCalled();
    jsonParse.mockRestore();
  });

  it("maps 409 password_change_required and preserves attempted username", async () => {
    fetchMe.mockRejectedValueOnce(passwordChangeRequiredError);

    await login("admin", "admin");

    const shell = (await import("../state/appShell")).useAppShellState();
    expect(shell.auth.status).toBe("password_change_required");
    if (shell.auth.status === "password_change_required") {
      expect(shell.auth.username).toBe("admin");
    }
  });

  it("forces password_change_required navigation to /change-password from /", async () => {
    fetchMe.mockRejectedValueOnce(passwordChangeRequiredError);
    await login("admin", "admin");
    __resetAuthBootstrapForTest();
    fetchMe.mockRejectedValueOnce(passwordChangeRequiredError);

    const testRouter = createAppRouter(createMemoryHistory());
    await testRouter.push("/");
    await testRouter.isReady();
    expect(testRouter.currentRoute.value.path).toBe("/change-password");
    expect(testRouter.currentRoute.value.query[RETURN_URL_QUERY]).toBeUndefined();
  });

  it("successful password change uses CSRF transport, refreshes me and clears password field", async () => {
    fetchMe
      .mockRejectedValueOnce(passwordChangeRequiredError)
      .mockRejectedValueOnce(passwordChangeRequiredError)
      .mockResolvedValueOnce(meAuthenticated);

    await login("admin", "admin");
    __resetAuthBootstrapForTest();

    stubBrowserApis();
    const testRouter = createAppRouter(createMemoryHistory());
    await testRouter.push("/change-password");
    await testRouter.isReady();
    const wrapper = mount(ChangePasswordView, {
      global: { plugins: [vuetify, i18n, testRouter] },
    });
    await flushPromises();

    const input = wrapper.get('input[name="new-password"]');
    await input.setValue("admin-new-password-1");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(changePasswordBrowser).toHaveBeenCalledWith("admin-new-password-1");
    expect(fetchMe).toHaveBeenCalledTimes(3);
    await vi.waitFor(() => {
      expect((wrapper.vm as { newPassword: string }).newPassword).toBe("");
    });
    const shell = (await import("../state/appShell")).useAppShellState();
    expect(shell.auth.status).toBe("authenticated");
    expect(testRouter.currentRoute.value.path).toBe("/");
  });

  it("keeps weak password errors on the form", async () => {
    fetchMe
      .mockRejectedValueOnce(passwordChangeRequiredError)
      .mockRejectedValueOnce(passwordChangeRequiredError);
    await login("admin", "admin");
    __resetAuthBootstrapForTest();

    changePasswordBrowser.mockRejectedValueOnce(
      new ApiTransportError("weak password", 400, {
        detail: {
          error: "weak_password",
          message: "weak password",
          field_errors: [{ code: "too_short", field: "password", message: "too short" }],
        },
      }),
    );

    stubBrowserApis();
    const testRouter = createAppRouter(createMemoryHistory());
    await testRouter.push("/change-password");
    await testRouter.isReady();
    const wrapper = mount(ChangePasswordView, {
      global: { plugins: [vuetify, i18n, testRouter] },
    });
    await flushPromises();

    await wrapper.get('input[name="new-password"]').setValue("short");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.find("[data-testid=change-password-panel]").exists()).toBe(true);
    expect(wrapper.text()).toContain("Das Passwort ist zu schwach.");
    expect((wrapper.vm as { newPassword: string }).newPassword).toBe("");
  });

  it("logout and 401 refresh remain fail-closed anonymous", async () => {
    fetchMe.mockResolvedValueOnce(meAuthenticated);
    await login("bob", "bob-secret");

    await logout();
    let shell = (await import("../state/appShell")).useAppShellState();
    expect(shell.auth.status).toBe("anonymous");

    fetchMe.mockRejectedValueOnce(new ApiTransportError("unauthorized", 401, null));
    await refreshAuth();
    shell = (await import("../state/appShell")).useAppShellState();
    expect(shell.auth.status).toBe("anonymous");
  });

  it("shell logout routes to /login fail-closed", async () => {
    fetchMe.mockResolvedValue(meAuthenticated);
    stubBrowserApis();
    const testRouter = createAppRouter(createMemoryHistory());
    await testRouter.push("/");
    await testRouter.isReady();

    const wrapper = mount(App, {
      global: { plugins: [testRouter, vuetify, i18n] },
      attachTo: document.body,
    });
    await flushPromises();

    await wrapper.get("[data-testid=authenticated-panel] button").trigger("click");
    await flushPromises();

    expect(testRouter.currentRoute.value.path).toBe("/login");
    const shell = (await import("../state/appShell")).useAppShellState();
    expect(shell.auth.status).toBe("anonymous");
  });

  it("production router redirects anonymous / to /login", async () => {
    fetchMe.mockRejectedValueOnce(new ApiTransportError("unauthorized", 401, null));

    const testRouter = createAppRouter(createMemoryHistory());
    await testRouter.push("/");
    await testRouter.isReady();

    expect(testRouter.currentRoute.value.path).toBe("/login");
    expect(testRouter.currentRoute.value.query[RETURN_URL_QUERY]).toBeUndefined();
  });

  it("production router preserves safe local returnUrl when anonymous / has query", async () => {
    fetchMe.mockRejectedValueOnce(new ApiTransportError("unauthorized", 401, null));

    const testRouter = createAppRouter(createMemoryHistory());
    await testRouter.push("/?view=docs");
    await testRouter.isReady();

    expect(testRouter.currentRoute.value.path).toBe("/login");
    expect(testRouter.currentRoute.value.query[RETURN_URL_QUERY]).toBe("/?view=docs");
  });
});
