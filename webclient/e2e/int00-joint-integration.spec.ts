import { expect, test } from "@playwright/test";
import { writeFile, access } from "node:fs/promises";
import path from "node:path";

const FORBIDDEN_STORAGE_KEY = /token|session|qmtool_session|authorization|bearer/i;
const FORBIDDEN_STORAGE_VALUE = /Bearer\s+/i;

function requireEnv(name: string): string {
  const value = process.env[name]?.trim() ?? "";
  if (!value) {
    throw new Error(`${name} is required for the INT00 joint browser spec`);
  }
  return value;
}

async function waitForFile(filePath: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await access(filePath);
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw new Error(`timeout waiting for ${filePath}`);
}

function assertStorageClean(
  kind: string,
  entries: [string, string][],
  when: string,
): void {
  for (const [key, value] of entries) {
    expect(
      FORBIDDEN_STORAGE_KEY.test(key) || FORBIDDEN_STORAGE_VALUE.test(value),
      `${kind} must stay clean ${when} (${key})`,
    ).toBeFalsy();
  }
}

test("INT00 joint Chromium PostgreSQL HTTPS cookie restart", async ({ page, context }) => {
  test.skip(
    process.env.QMTOOL_INT00_JOINT !== "1",
    "INT00 joint spec runs only from the guarded Python harness",
  );

  const username = requireEnv("QMTOOL_INT00_USERNAME");
  const password = requireEnv("QMTOOL_INT00_PASSWORD");
  const evidenceDir = requireEnv("QMTOOL_INT00_EVIDENCE_DIR");
  const restartRequestPath = path.join(evidenceDir, "restart-request.json");
  const restartCompletePath = path.join(evidenceDir, "restart-complete.json");

  await page.goto("/");
  await expect(page.getByTestId("login-panel")).toBeVisible();

  const storageBefore = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));
  assertStorageClean("localStorage", storageBefore.local as [string, string][], "before login");
  assertStorageClean("sessionStorage", storageBefore.session as [string, string][], "before login");

  const connection = await page.evaluate(async () => {
    const response = await fetch("/api/v1/session/connection");
    return { status: response.status, body: await response.json() };
  });
  expect(connection.status, "unauthenticated connection").toBe(200);
  expect(connection.body.contract_version).toBe("1");

  const unauthBootstrap = await page.evaluate(async () => {
    const response = await fetch("/api/v1/session/bootstrap");
    return { status: response.status };
  });
  expect(unauthBootstrap.status, "unauthenticated bootstrap").toBe(401);

  const csrfResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/csrf") && response.request().method() === "GET",
  );
  const loginResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/login") && response.request().method() === "POST",
  );
  const meResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/me") &&
      response.request().method() === "GET" &&
      response.status() === 200,
  );

  await page.getByLabel("Benutzername").fill(username);
  await page.getByLabel("Passwort").fill(password);
  await page.getByRole("button", { name: "Anmelden" }).click();

  const csrf = await csrfResponse;
  const login = await loginResponse;
  const me = await meResponse;

  expect(csrf.status(), "CSRF bootstrap GET /api/v1/auth/csrf").toBe(204);
  expect(login.status(), "browser login must be 204").toBe(204);
  const loginBody = await login.body().catch(() => Buffer.alloc(0));
  expect(loginBody.byteLength, "login body must be tokenless").toBe(0);
  expect(login.request().headers()["x-csrf-token"], "login sends X-CSRF-Token").toBeTruthy();

  const mePayload = (await me.json()) as { username?: string };
  expect(mePayload.username, "authenticated me").toBe(username);
  await expect(page.getByTestId("authenticated-panel")).toBeVisible();

  const bootstrap = await page.evaluate(async () => {
    const response = await fetch("/api/v1/session/bootstrap");
    return { status: response.status, body: await response.json() };
  });
  expect(bootstrap.status, "authenticated bootstrap").toBe(200);
  expect(bootstrap.body.contract_version).toBe("1");
  const modules = (bootstrap.body.modules ?? []) as Array<{
    id: string;
    licensed: boolean;
    authorized: boolean;
  }>;
  const ids = modules.map((item) => item.id).sort();
  expect(ids, "active backend catalogue").toEqual(["documents", "usermanagement"]);
  for (const item of modules) {
    expect(item.licensed, `${item.id} licensed`).toBe(true);
    expect(item.authorized, `${item.id} authorized`).toBe(true);
  }
  expect(ids).not.toContain("training");
  expect(ids).not.toContain("incident_management");
  expect(ids).not.toContain("signature");

  const storageAfterLogin = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));
  assertStorageClean("localStorage", storageAfterLogin.local as [string, string][], "after login");
  assertStorageClean("sessionStorage", storageAfterLogin.session as [string, string][], "after login");

  const readableSessionInDocumentCookie = await page.evaluate(
    () => document.cookie.includes("qmtool_session="),
  );
  expect(readableSessionInDocumentCookie, "session cookie must be HttpOnly").toBe(false);

  const cookies = await context.cookies();
  const sessionCookie = cookies.find((item) => item.name === "qmtool_session");
  const csrfCookie = cookies.find((item) => item.name === "qmtool_csrf");
  expect(sessionCookie, "qmtool_session cookie set").toBeTruthy();
  expect(sessionCookie?.httpOnly, "session cookie HttpOnly").toBe(true);
  expect(sessionCookie?.secure, "session cookie Secure").toBe(true);
  expect(csrfCookie, "qmtool_csrf cookie set").toBeTruthy();
  expect(csrfCookie?.httpOnly, "csrf cookie readable to SPA").toBe(false);
  expect(csrfCookie?.secure, "csrf cookie Secure").toBe(true);

  await page.goto("about:blank");
  await writeFile(
    restartRequestPath,
    `${JSON.stringify({ phase: "ready-for-host-restart", username }, null, 2)}\n`,
    "utf8",
  );
  await waitForFile(restartCompletePath, 90_000);

  const meAfterRestart = await context.request.get("/api/v1/auth/me");
  expect(meAfterRestart.status(), "cookie session survives ServiceHost restart").toBe(200);
  const meAfterRestartBody = (await meAfterRestart.json()) as { username?: string };
  expect(meAfterRestartBody.username).toBe(username);

  const bootstrapAfterRestart = await context.request.get("/api/v1/session/bootstrap");
  expect(bootstrapAfterRestart.status(), "bootstrap survives ServiceHost restart").toBe(200);
  const bootstrapAfterRestartBody = (await bootstrapAfterRestart.json()) as {
    contract_version?: string;
  };
  expect(bootstrapAfterRestartBody.contract_version).toBe("1");

  await page.goto("/");
  await expect(page.getByTestId("authenticated-panel")).toBeVisible();

  const logoutResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/logout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Abmelden" }).click();
  const logout = await logoutResponse;
  expect(logout.status(), "CSRF-protected logout").toBe(204);
  expect(logout.request().headers()["x-csrf-token"], "logout sends X-CSRF-Token").toBeTruthy();

  await expect(page.getByTestId("login-panel")).toBeVisible();

  const meAfterLogout = await page.evaluate(async () => {
    const response = await fetch("/api/v1/auth/me");
    return { status: response.status };
  });
  expect(meAfterLogout.status, "logout invalidates session").toBe(401);

  const cookiesAfterLogout = await context.cookies();
  const sessionAfterLogout = cookiesAfterLogout.find((item) => item.name === "qmtool_session");
  expect(
    !sessionAfterLogout || !sessionAfterLogout.value,
    "session cookie cleared after logout",
  ).toBeTruthy();
});
