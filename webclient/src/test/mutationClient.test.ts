import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiBasePrefix } from "../api/client";
import type { MutationBody } from "../api/mutationClient";
import {
  MutationClientError,
  buildMutationClientError,
  extractErrorDetail,
  mutationErrorI18nKey,
  mutate,
} from "../api/mutationClient";

type FetchCall = {
  url: string;
  init?: RequestInit;
};

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function textResponse(
  status: number,
  body: string,
  headers: Record<string, string> = {},
): Response {
  return new Response(body, { status, headers });
}

function empty204Response(headers: Record<string, string> = {}): Response {
  return {
    status: 204,
    ok: true,
    headers: new Headers(headers),
    text: async () => "",
  } as Response;
}

function captureFetch(
  handler: (call: FetchCall) => Response | Promise<Response>,
): ReturnType<typeof vi.fn> {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    return handler({ url, init });
  });
}

describe("mutationClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    document.cookie = "qmtool_csrf=test-csrf-token";
    fetchMock = captureFetch(() => empty204Response());
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "qmtool_csrf=; Max-Age=0";
  });

  it("uses same-origin /api/v1 URL with credentials include and no Authorization", async () => {
    await mutate({ method: "POST", path: "/documents/versions/create", body: { json: { ok: true } } });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${apiBasePrefix()}/documents/versions/create`);
    expect(url.startsWith("http")).toBe(false);
    expect(init.credentials).toBe("include");
    const headers = new Headers(init.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("sends CSRF header from cookie on every mutation", async () => {
    await mutate({ method: "DELETE", path: "/documents/versions/DOC-1/1" });

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("test-csrf-token");
  });

  it("fails before fetch when qmtool_csrf cookie is missing", async () => {
    document.cookie = "qmtool_csrf=; Max-Age=0";

    await expect(
      mutate({ method: "POST", path: "/documents/versions/DOC-1/1/workflow/start" }),
    ).rejects.toMatchObject({
      name: "ApiTransportError",
      status: 403,
      message: "csrf cookie missing",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends JSON body with application/json content type", async () => {
    await mutate({
      method: "POST",
      path: "/documents/versions/create",
      body: { json: { document_id: "DOC-1", version: 1 } },
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ document_id: "DOC-1", version: 1 }));
  });

  it("sends raw body with supplied media type", async () => {
    const pdfBytes = new Uint8Array([0x25, 0x50, 0x44, 0x46]);
    await mutate({
      method: "POST",
      path: "/documents/versions/DOC-1/1/import-pdf",
      body: { raw: pdfBytes, contentType: "application/pdf" },
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/pdf");
    expect(init.body).toBe(pdfBytes);
  });

  it("rejects mixed body modes at runtime before fetch", async () => {
    const mixedBody = {
      json: { document_id: "DOC-1" },
      raw: new Uint8Array([0x25, 0x50]),
      contentType: "application/pdf",
    } as MutationBody;

    await expect(
      mutate({
        method: "POST",
        path: "/documents/versions/DOC-1/1/import-pdf",
        body: mixedBody,
      }),
    ).rejects.toMatchObject({
      name: "MutationValidationError",
      code: "invalid_body",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each(["", "   "] as const)(
    "rejects raw body with empty or whitespace content type before fetch (%j)",
    async (contentType) => {
      await expect(
        mutate({
          method: "POST",
          path: "/documents/versions/DOC-1/1/import-pdf",
          body: { raw: new Uint8Array([0x25, 0x50, 0x44, 0x46]), contentType },
        }),
      ).rejects.toMatchObject({
        name: "MutationValidationError",
        code: "invalid_body",
      });
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("does not force multipart content type for FormData", async () => {
    const form = new FormData();
    form.append("file", new Blob(["x"], { type: "text/plain" }), "x.txt");
    await mutate({
      method: "POST",
      path: "/documents/versions/DOC-1/1/import-docx",
      body: { form },
    });

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.has("Content-Type")).toBe(false);
    expect(fetchMock.mock.calls[0][1]?.body).toBe(form);
  });

  it("sets If-Match exactly when provided", async () => {
    await mutate({
      method: "PATCH",
      path: "/documents/versions/DOC-1/1",
      ifMatch: "evt-42",
      body: { json: { note: "x" } },
    });

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("If-Match")).toBe("evt-42");
  });

  it("omits If-Match when not provided", async () => {
    await mutate({ method: "POST", path: "/documents/versions/DOC-1/1/workflow/start" });

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.has("If-Match")).toBe(false);
  });

  it("rejects blank If-Match before fetch", async () => {
    await expect(
      mutate({
        method: "POST",
        path: "/documents/versions/DOC-1/1/workflow/start",
        ifMatch: "   ",
      }),
    ).rejects.toMatchObject({ name: "MutationValidationError", code: "invalid_if_match" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("parses 200 JSON responses", async () => {
    fetchMock = captureFetch(() => jsonResponse(200, { etag: "evt-1", version: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await mutate<{ etag: string; version: number }>({
      method: "POST",
      path: "/documents/versions/create",
      body: { json: { document_id: "DOC-1", version: 1 } },
    });

    expect(result).toEqual({ etag: "evt-1", version: 1 });
  });

  it("handles 204 empty responses without JSON parsing", async () => {
    const jsonParse = vi.spyOn(JSON, "parse");
    fetchMock = captureFetch(() => empty204Response());
    vi.stubGlobal("fetch", fetchMock);

    const result = await mutate({ method: "POST", path: "/documents/versions/DOC-1/1/workflow/start" });

    expect(result).toBeUndefined();
    expect(jsonParse).not.toHaveBeenCalled();
    jsonParse.mockRestore();
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"] as const)(
    "forwards %s method unchanged to fetch",
    async (method) => {
      await mutate({ method, path: "/documents/versions/DOC-1/1" });

      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe(method);
    },
  );

  it("rejects absolute and protocol-relative paths before fetch", async () => {
    await expect(
      mutate({ method: "POST", path: "https://evil.example/api/v1/x" }),
    ).rejects.toMatchObject({ code: "invalid_path" });
    await expect(mutate({ method: "POST", path: "//evil.example/x" })).rejects.toMatchObject({
      code: "invalid_path",
    });
    await expect(mutate({ method: "POST", path: "/api/v1/documents" })).rejects.toMatchObject({
      code: "invalid_path",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects dot-segment, encoded traversal and backslash escapes before fetch", async () => {
    const rejectedPaths = [
      "/../health",
      "/documents/../health",
      "/documents/%2e%2e/health",
      "/documents/%2E%2E/health",
      "/documents/..%2fhealth",
      "/documents\\health",
      "/documents/%5chealth",
      "/documents/%5Chealth",
    ];

    for (const path of rejectedPaths) {
      fetchMock.mockClear();
      await expect(mutate({ method: "POST", path })).rejects.toMatchObject({
        code: "invalid_path",
      });
      expect(fetchMock).not.toHaveBeenCalled();
    }
  });

  it("allows :// only in query values without rejecting the mutation path", async () => {
    await mutate({
      method: "POST",
      path: "/documents/search?redirect=https://example.com/app",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${apiBasePrefix()}/documents/search?redirect=https://example.com/app`,
    );
  });

  it("does not write request bodies or errors to web storage", async () => {
    fetchMock = captureFetch(() =>
      jsonResponse(409, {
        detail: {
          error: "document_conflict",
          message: "document state is newer",
          current_etag: "evt-9",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const setItem = vi.spyOn(Storage.prototype, "setItem");

    await expect(
      mutate({
        method: "POST",
        path: "/documents/versions/DOC-1/1/workflow/start",
        body: { json: { secret: "payload-value" } },
      }),
    ).rejects.toBeInstanceOf(MutationClientError);

    expect(
      setItem.mock.calls.some(([, value]) => String(value).includes("payload-value")),
    ).toBe(false);
    expect(
      setItem.mock.calls.some(([, value]) => String(value).includes("document_conflict")),
    ).toBe(false);
    setItem.mockRestore();
  });
});

describe("mutation error normalization", () => {
  it("classifies 401/403/404/409/428 with code, message and field_errors", () => {
    const cases = [
      {
        status: 401,
        kind: "unauthorized",
        detail: { error: "unauthorized", message: "not logged in" },
      },
      {
        status: 403,
        kind: "forbidden",
        detail: { error: "forbidden", message: "not allowed" },
      },
      {
        status: 404,
        kind: "not_found",
        detail: { error: "not_found", message: "missing" },
      },
      {
        status: 409,
        kind: "conflict",
        detail: {
          error: "document_conflict",
          message: "document state is newer",
          current_etag: "evt-42",
          field_errors: [{ code: "stale", field: "etag", message: "stale etag" }],
        },
      },
      {
        status: 428,
        kind: "precondition_required",
        detail: { error: "precondition_required", message: "If-Match required" },
      },
    ];

    for (const caseEntry of cases) {
      const error = buildMutationClientError(
        caseEntry.status,
        { detail: caseEntry.detail },
        "req-1",
      );
      expect(error.kind).toBe(caseEntry.kind);
      expect(error.status).toBe(caseEntry.status);
      expect(error.errorCode).toBe(caseEntry.detail.error);
      expect(error.message).toBe(caseEntry.detail.message);
      expect(error.requestId).toBe("req-1");
      if (caseEntry.status === 409) {
        expect(error.currentEtag).toBe("evt-42");
        expect(error.fieldErrors).toEqual(caseEntry.detail.field_errors);
      }
      expect(mutationErrorI18nKey(error.kind)).toMatch(/^api\.errors\./);
    }
  });

  it("treats detail arrays as absent detail without unsafe casts", () => {
    const detail = extractErrorDetail({ detail: [{}] });
    expect(detail).toBeNull();

    const error = buildMutationClientError(409, { detail: [{}] });
    expect(error.errorCode).toBeNull();
    expect(error.message).toBe("HTTP 409");
  });

  it("falls back for malformed and non-JSON error bodies", async () => {
    document.cookie = "qmtool_csrf=test-csrf-token";
    const fetchMock = captureFetch(() => textResponse(500, "not-json"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      mutate({ method: "POST", path: "/documents/versions/create", body: { json: { x: 1 } } }),
    ).rejects.toMatchObject({
      kind: "transport",
      status: 500,
      errorCode: null,
      message: "HTTP 500",
      body: null,
    });

    vi.unstubAllGlobals();
  });

  it("maps classified errors from live fetch responses", async () => {
    document.cookie = "qmtool_csrf=test-csrf-token";
    const fetchMock = captureFetch(() =>
      jsonResponse(
        428,
        { detail: { error: "precondition_required", message: "If-Match required" } },
        { "X-Request-ID": "trace-428" },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      mutate({ method: "POST", path: "/documents/versions/DOC-1/1/workflow/start" }),
    ).rejects.toMatchObject({
      kind: "precondition_required",
      status: 428,
      errorCode: "precondition_required",
      message: "If-Match required",
      requestId: "trace-428",
    });

    vi.unstubAllGlobals();
  });
});
