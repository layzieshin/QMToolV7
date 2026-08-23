import { describe, expect, it } from "vitest";

import { __buildAuthHeadersForTest, apiBasePrefix } from "../api/client";

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
});
