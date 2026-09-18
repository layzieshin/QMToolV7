import { beforeEach, describe, expect, it, vi } from "vitest";

import { __buildAuthHeadersForTest, apiBasePrefix } from "../api/client";
import { changePassword, login, logout, __resetAppShellStateForTest } from "../state/appShell";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    bootstrapCsrf: vi.fn(async () => undefined),
    probeHealth: vi.fn(async () => true),
    loginBrowser: vi.fn(actual.loginBrowser),
    changePasswordBrowser: vi.fn(actual.changePasswordBrowser),
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
    logoutBrowser: vi.fn(async () => undefined),
  };
});

describe("api client transport contract", () => {
  it("uses relative /api/v1 prefix only", () => {
    expect(apiBasePrefix()).toBe("/api/v1");
    expect(apiBasePrefix().startsWith("http")).toBe(false);
  });

  it("never emits Authorization header", () => {
    document.cookie = "qmtool_csrf=test-csrf-value";
    const headers = __buildAuthHeadersForTest(true);
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.get("X-CSRF-Token")).toBe("test-csrf-value");
  });
});

describe("web storage negativetest", () => {
  beforeEach(() => {
    __resetAppShellStateForTest();
  });

  it("fail-fast when session token is written to localStorage", () => {
    expect(() => localStorage.setItem("qmtool_session", "secret")).toThrow(
      /must not persist session credentials/i,
    );
  });

  it("fail-fast when bearer token is written to sessionStorage", () => {
    expect(() => sessionStorage.setItem("auth", "Bearer abc")).toThrow(
      /must not persist bearer tokens/i,
    );
  });

  it("does not persist login credentials through appShell login", async () => {
    const localSet = vi.spyOn(Storage.prototype, "setItem");
    const sessionSet = vi.spyOn(Storage.prototype, "setItem");

    await login("alice", "alice-secret");

    const writes = [...localSet.mock.calls, ...sessionSet.mock.calls].map(([key, value]) => ({
      key,
      value,
    }));
    expect(writes.some((entry) => /password|session|token|bearer/i.test(String(entry.key)))).toBe(
      false,
    );
    expect(
      writes.some((entry) => /password|bearer|secret/i.test(String(entry.value))),
    ).toBe(false);

    localSet.mockRestore();
    sessionSet.mockRestore();
  });

  it("does not persist new password through changePassword", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");

    await changePassword("new-password-value-123");

    expect(
      setItem.mock.calls.some(([, value]) => String(value).includes("new-password-value-123")),
    ).toBe(false);

    setItem.mockRestore();
  });

  it("does not persist credentials through logout", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    await logout();
    expect(
      setItem.mock.calls.some(([key]) => /session|token|password/i.test(String(key))),
    ).toBe(false);
    setItem.mockRestore();
  });
});

function empty204Response(): Response {
  return {
    status: 204,
    ok: false,
    text: async () => "",
  } as Response;
}

describe("204 transport bodies", () => {
  it("loginBrowser does not JSON-parse a 204 login response", async () => {
    const jsonParse = vi.spyOn(JSON, "parse");
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/csrf")) {
        return empty204Response();
      }
      if (url.endsWith("/auth/login")) {
        expect(init?.method).toBe("POST");
        return empty204Response();
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "qmtool_csrf=test-token";

    const { loginBrowser: realLoginBrowser } =
      await vi.importActual<typeof import("../api/client")>("../api/client");
    await realLoginBrowser({ username: "bob", password: "secret" });

    expect(jsonParse).not.toHaveBeenCalled();
    jsonParse.mockRestore();
    vi.unstubAllGlobals();
  });

  it("changePasswordBrowser does not JSON-parse a 204 response", async () => {
    const jsonParse = vi.spyOn(JSON, "parse");
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.endsWith("/auth/csrf")) {
        return empty204Response();
      }
      if (url.endsWith("/auth/change-password")) {
        return empty204Response();
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "qmtool_csrf=test-token";

    const { changePasswordBrowser: realChangePasswordBrowser } =
      await vi.importActual<typeof import("../api/client")>("../api/client");
    await realChangePasswordBrowser("new-password-123");

    expect(jsonParse).not.toHaveBeenCalled();
    jsonParse.mockRestore();
    vi.unstubAllGlobals();
  });
});
