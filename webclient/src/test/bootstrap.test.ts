import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiBasePrefix, probeHealth } from "../api/client";
import type { BootstrapResponse, ConnectionResponse, ModuleBootstrapItem } from "../api/client";
import {
  __getBootstrapRetryDelayForTest,
  __getLifecycleEpochForTest,
  __isBootstrapLifecycleActiveForTest,
  __resetBootstrapStateForTest,
  clearBootstrapModules,
  loadBootstrap,
  refreshConnection,
  retryConnection,
  startBootstrapLifecycle,
  stopBootstrapLifecycle,
  useBootstrapState,
} from "../state/bootstrap";

type FetchCall = {
  url: string;
  init?: RequestInit;
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function captureFetch(
  handler: (call: FetchCall) => Response | Promise<Response>,
): ReturnType<typeof vi.fn> {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    return handler({ url, init });
  });
}

function connectionOk(overrides: Partial<ConnectionResponse> = {}): ConnectionResponse {
  return {
    contract_version: "1",
    maintenance: false,
    service: "qmtool-backend",
    status: "ok",
    writes_allowed: true,
    ...overrides,
  };
}

function moduleItem(overrides: Partial<ModuleBootstrapItem> = {}): ModuleBootstrapItem {
  return {
    id: "documents",
    licensed: true,
    authorized: true,
    capabilities: ["read"],
    ...overrides,
  };
}

function bootstrapResponse(modules: ModuleBootstrapItem[]): BootstrapResponse {
  return {
    contract_version: "1",
    modules,
  };
}

describe("bootstrap state and session API", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    __resetBootstrapStateForTest();
    vi.useFakeTimers();
    fetchMock = captureFetch(({ url }) => {
      if (url.includes("/session/bootstrap")) {
        return jsonResponse(200, bootstrapResponse([moduleItem()]));
      }
      return jsonResponse(200, connectionOk());
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("uses versioned /api/v1 session URLs with credentials include and no Authorization", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return jsonResponse(200, connectionOk());
      }
      if (url.includes("/session/bootstrap")) {
        return jsonResponse(200, bootstrapResponse([moduleItem()]));
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    await refreshConnection();
    await loadBootstrap();

    expect(fetchMock).toHaveBeenCalled();
    const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
    const connectionCall = calls.find(([url]) => url.endsWith("/session/connection"));
    const bootstrapCall = calls.find(([url]) => url.endsWith("/session/bootstrap"));
    expect(connectionCall?.[0]).toBe(`${apiBasePrefix()}/session/connection`);
    expect(bootstrapCall?.[0]).toBe(`${apiBasePrefix()}/session/bootstrap`);
    expect(connectionCall?.[1]?.credentials).toBe("include");
    expect(bootstrapCall?.[1]?.credentials).toBe("include");
    const headers = new Headers(connectionCall?.[1]?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("stores typed connection values and fail-closes writes when offline", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    await refreshConnection();

    const state = useBootstrapState();
    expect(state.online).toBe(false);
    expect(state.writesAllowed).toBe(false);
    expect(state.connection).toBeNull();
    expect(state.banner).toBe("offline");
  });

  it("fail-closes writes on maintenance and degraded server state", async () => {
    fetchMock.mockImplementationOnce(async () =>
      jsonResponse(200, connectionOk({ maintenance: true, writes_allowed: false })),
    );
    await refreshConnection();
    expect(useBootstrapState().writesAllowed).toBe(false);
    expect(useBootstrapState().banner).toBe("maintenance");

    fetchMock.mockImplementationOnce(async () =>
      jsonResponse(200, connectionOk({ status: "degraded", writes_allowed: false })),
    );
    await refreshConnection();
    expect(useBootstrapState().writesAllowed).toBe(false);
    expect(useBootstrapState().banner).toBe("degraded");
  });

  it("sorts bootstrap modules stably and keeps only server data", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return jsonResponse(
          200,
          bootstrapResponse([
            moduleItem({ id: "zebra" }),
            moduleItem({ id: "alpha" }),
            moduleItem({ id: "mango", licensed: false }),
          ]),
        );
      }
      return jsonResponse(200, connectionOk());
    });

    await loadBootstrap();

    const state = useBootstrapState();
    expect(state.modules.map((entry) => entry.id)).toEqual(["alpha", "mango", "zebra"]);
    expect(state.modules[0]?.capabilities).toEqual(["read"]);
  });

  it("clears modules and rethrows bootstrap 401 for the auth owner", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return jsonResponse(401, { detail: { message: "unauthorized" } });
      }
      return jsonResponse(200, connectionOk());
    });

    await expect(loadBootstrap()).rejects.toMatchObject({
      name: "ApiTransportError",
      status: 401,
    });
    expect(useBootstrapState().modules).toEqual([]);
  });

  it("does not rethrow stale bootstrap 401 after clearBootstrapModules", async () => {
    let resolveBootstrap: ((value: Response) => void) | undefined;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return new Promise<Response>((resolve) => {
          resolveBootstrap = resolve;
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const loadPromise = loadBootstrap();
    clearBootstrapModules();
    resolveBootstrap?.(jsonResponse(401, { detail: { message: "unauthorized" } }));
    await expect(loadPromise).resolves.toBeUndefined();
    expect(useBootstrapState().modules).toEqual([]);
  });

  it("schedules bounded reconnect with backoff and stops on lifecycle stop", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    startBootstrapLifecycle();
    expect(__isBootstrapLifecycleActiveForTest()).toBe(true);
    await vi.waitFor(() => {
      expect(useBootstrapState().banner).toBe("offline");
    });
    expect(__getBootstrapRetryDelayForTest()).toBe(10000);

    const callsBeforeStop = fetchMock.mock.calls.length;
    stopBootstrapLifecycle();
    vi.advanceTimersByTime(30000);
    expect(fetchMock.mock.calls.length).toBe(callsBeforeStop);
  });

  it("supports explicit retry and reset hook", async () => {
    fetchMock
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(jsonResponse(200, connectionOk()));

    await refreshConnection();
    expect(useBootstrapState().banner).toBe("offline");

    await retryConnection();
    expect(useBootstrapState().online).toBe(true);
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2);

    __resetBootstrapStateForTest();
    expect(useBootstrapState().modules).toEqual([]);
    expect(useBootstrapState().banner).toBe("hidden");
  });

  it("does not persist bootstrap data in web storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    fetchMock.mockImplementation(async ({ url }) => {
      if (url.endsWith("/session/bootstrap")) {
        return jsonResponse(200, bootstrapResponse([moduleItem({ id: "secret-module" })]));
      }
      return jsonResponse(200, connectionOk());
    });

    await loadBootstrap();

    expect(
      setItem.mock.calls.some(([key, value]) =>
        /token|password|session|bearer|secret-module/i.test(`${key}:${value}`),
      ),
    ).toBe(false);
    setItem.mockRestore();
  });

  it("probeHealth is true for reachable 200 maintenance/degraded and false on transport failure", async () => {
    fetchMock.mockImplementationOnce(async () =>
      jsonResponse(200, connectionOk({ maintenance: true, writes_allowed: false })),
    );
    await expect(probeHealth()).resolves.toBe(true);

    fetchMock.mockImplementationOnce(async () =>
      jsonResponse(200, connectionOk({ status: "degraded", writes_allowed: false })),
    );
    await expect(probeHealth()).resolves.toBe(true);

    fetchMock.mockRejectedValueOnce(new Error("network down"));
    await expect(probeHealth()).resolves.toBe(false);
  });

  it("ignores deferred bootstrap response after clearBootstrapModules", async () => {
    let resolveBootstrap: ((value: Response) => void) | undefined;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return new Promise<Response>((resolve) => {
          resolveBootstrap = resolve;
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const loadPromise = loadBootstrap();
    clearBootstrapModules();
    resolveBootstrap?.(jsonResponse(200, bootstrapResponse([moduleItem({ id: "stale" })])));
    await loadPromise;

    expect(useBootstrapState().modules).toEqual([]);
  });

  it("applies only the newest bootstrap load when responses resolve out of order", async () => {
    const resolvers: Array<(value: Response) => void> = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return new Promise<Response>((resolve) => {
          resolvers.push(resolve);
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const firstLoad = loadBootstrap();
    const secondLoad = loadBootstrap();
    resolvers[1]?.(
      jsonResponse(200, bootstrapResponse([moduleItem({ id: "newest" })])),
    );
    await secondLoad;
    resolvers[0]?.(
      jsonResponse(200, bootstrapResponse([moduleItem({ id: "stale" })])),
    );
    await firstLoad;

    expect(useBootstrapState().modules.map((entry) => entry.id)).toEqual(["newest"]);
  });

  it("keeps newest connection failure when an older success resolves later", async () => {
    const pending: Array<{
      resolve: (value: Response) => void;
      reject: (error: Error) => void;
    }> = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return new Promise<Response>((resolve, reject) => {
          pending.push({ resolve, reject });
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const first = refreshConnection();
    const second = refreshConnection();
    pending[1]?.reject(new Error("offline"));
    await second;
    pending[0]?.resolve(jsonResponse(200, connectionOk()));
    await first;

    expect(useBootstrapState().online).toBe(false);
    expect(useBootstrapState().banner).toBe("offline");
  });

  it("applies only the newest successful connection response", async () => {
    const pending: Array<{ resolve: (value: Response) => void }> = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return new Promise<Response>((resolve) => {
          pending.push({ resolve });
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const first = refreshConnection();
    const second = refreshConnection();
    pending[0]?.resolve(jsonResponse(200, connectionOk({ maintenance: true })));
    await first;
    pending[1]?.resolve(jsonResponse(200, connectionOk()));
    await second;

    expect(useBootstrapState().online).toBe(true);
    expect(useBootstrapState().banner).toBe("hidden");
  });

  it("does not clear connectionLoading from a stale request finally block", async () => {
    const pending: Array<{ resolve: (value: Response) => void }> = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return new Promise<Response>((resolve) => {
          pending.push({ resolve });
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const first = refreshConnection();
    const second = refreshConnection();
    expect(useBootstrapState().connectionLoading).toBe(true);
    pending[0]?.resolve(jsonResponse(200, connectionOk()));
    await first;
    expect(useBootstrapState().connectionLoading).toBe(true);
    pending[1]?.resolve(jsonResponse(200, connectionOk()));
    await second;
    expect(useBootstrapState().connectionLoading).toBe(false);
  });

  it("clears restored banner when connection fails again before timer elapses", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    await refreshConnection();
    expect(useBootstrapState().banner).toBe("offline");

    fetchMock.mockResolvedValueOnce(jsonResponse(200, connectionOk()));
    await refreshConnection();
    expect(useBootstrapState().banner).toBe("restored");

    fetchMock.mockRejectedValueOnce(new Error("offline again"));
    await refreshConnection();
    expect(useBootstrapState().banner).toBe("offline");

    vi.advanceTimersByTime(3000);
    expect(useBootstrapState().banner).toBe("offline");
  });

  it("ignores deferred lifecycle connection after stopBootstrapLifecycle", async () => {
    let resolveConnection: ((value: Response) => void) | undefined;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return new Promise<Response>((resolve) => {
          resolveConnection = resolve;
        });
      }
      return jsonResponse(200, connectionOk());
    });

    startBootstrapLifecycle();
    expect(useBootstrapState().connectionLoading).toBe(true);
    stopBootstrapLifecycle();
    expect(useBootstrapState().connectionLoading).toBe(false);
    resolveConnection?.(jsonResponse(200, connectionOk()));
    await Promise.resolve();

    expect(useBootstrapState().online).toBe(false);
    expect(useBootstrapState().banner).toBe("hidden");
    expect(vi.getTimerCount()).toBe(0);

    vi.advanceTimersByTime(60000);
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/session/connection"))).toHaveLength(1);
  });

  it("does not fetch or invalidate the current request on stale lifecycle-bound refreshConnection", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return new Promise<Response>(() => undefined);
      }
      return jsonResponse(200, connectionOk());
    });

    startBootstrapLifecycle();
    const connectionCalls = () =>
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/session/connection")).length;
    expect(connectionCalls()).toBe(1);

    await refreshConnection({ lifecycleEpoch: __getLifecycleEpochForTest() - 1 });
    expect(connectionCalls()).toBe(1);
    expect(useBootstrapState().connectionLoading).toBe(true);
  });

  it("clears a scheduled retry when bootstrap lifecycle restarts", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    startBootstrapLifecycle();
    await vi.waitFor(() => {
      expect(useBootstrapState().banner).toBe("offline");
    });
    const callsAfterFailure = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/session/connection"),
    ).length;

    startBootstrapLifecycle();
    const callsAfterRestart = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/session/connection"),
    ).length;
    expect(callsAfterRestart).toBe(callsAfterFailure + 1);

    vi.advanceTimersByTime(60000);
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/session/connection")),
    ).toHaveLength(callsAfterRestart);
  });

  it("clears bootstrapLoading immediately when clearBootstrapModules invalidates a pending load", async () => {
    let resolveBootstrap: ((value: Response) => void) | undefined;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return new Promise<Response>((resolve) => {
          resolveBootstrap = resolve;
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const loadPromise = loadBootstrap();
    expect(useBootstrapState().bootstrapLoading).toBe(true);
    clearBootstrapModules();
    expect(useBootstrapState().bootstrapLoading).toBe(false);

    resolveBootstrap?.(jsonResponse(200, bootstrapResponse([moduleItem({ id: "stale" })])));
    await loadPromise;

    expect(useBootstrapState().modules).toEqual([]);
    expect(useBootstrapState().bootstrapLoading).toBe(false);
  });

  it("reset monotonically invalidates a stale unbound connection request", async () => {
    const pending: Array<{ resolve: (value: Response) => void }> = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/connection")) {
        return new Promise<Response>((resolve) => {
          pending.push({ resolve });
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const stale = refreshConnection();
    __resetBootstrapStateForTest();
    const fresh = refreshConnection();

    pending[0]?.resolve(
      jsonResponse(200, connectionOk({ maintenance: true, writes_allowed: false })),
    );
    await stale;
    expect(useBootstrapState().banner).not.toBe("maintenance");
    expect(useBootstrapState().online).toBe(false);

    pending[1]?.resolve(jsonResponse(200, connectionOk()));
    await fresh;
    expect(useBootstrapState().online).toBe(true);
    expect(useBootstrapState().banner).toBe("hidden");
  });

  it("reset monotonically invalidates a stale bootstrap load", async () => {
    const pending: Array<{ resolve: (value: Response) => void }> = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return new Promise<Response>((resolve) => {
          pending.push({ resolve });
        });
      }
      return jsonResponse(200, connectionOk());
    });

    const stale = loadBootstrap();
    __resetBootstrapStateForTest();
    const fresh = loadBootstrap();

    pending[0]?.resolve(jsonResponse(200, bootstrapResponse([moduleItem({ id: "stale" })])));
    await stale;
    expect(useBootstrapState().modules).toEqual([]);

    pending[1]?.resolve(jsonResponse(200, bootstrapResponse([moduleItem({ id: "fresh" })])));
    await fresh;
    expect(useBootstrapState().modules.map((entry) => entry.id)).toEqual(["fresh"]);
  });

  it("clearBootstrapModules empties module list", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/session/bootstrap")) {
        return jsonResponse(200, bootstrapResponse([moduleItem()]));
      }
      return jsonResponse(200, connectionOk());
    });
    await loadBootstrap();
    expect(useBootstrapState().modules.length).toBe(1);
    clearBootstrapModules();
    expect(useBootstrapState().modules).toEqual([]);
  });
});
