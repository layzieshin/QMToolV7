import { expect, test } from "@playwright/test";

const FORBIDDEN_STORAGE_KEY = /token|session|qmtool_session|authorization|bearer/i;
const FORBIDDEN_STORAGE_VALUE = /Bearer\s+/i;

test("WEB00 HTTPS browser cookie/CSRF smoke", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByTestId("login-panel")).toBeVisible();

  const storageBefore = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));
  for (const [kind, entries] of Object.entries(storageBefore)) {
    for (const [key, value] of entries as [string, string][]) {
      expect(
        FORBIDDEN_STORAGE_KEY.test(key) || FORBIDDEN_STORAGE_VALUE.test(value),
        `${kind} must stay clean before login (${key})`,
      ).toBeFalsy();
    }
  }

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

  await page.getByLabel("Benutzername").fill("bob");
  await page.getByLabel("Passwort").fill("bob-secret");
  await page.getByRole("button", { name: "Anmelden" }).click();

  const csrf = await csrfResponse;
  const login = await loginResponse;
  const me = await meResponse;

  expect(csrf.status(), "CSRF bootstrap GET /api/v1/auth/csrf").toBe(204);
  expect(login.status(), "browser login must be 204").toBe(204);
  const loginBody = await login.body().catch(() => Buffer.alloc(0));
  expect(loginBody.byteLength, "login body must be tokenless").toBe(0);

  const mePayload = (await me.json()) as { username?: string };
  expect(mePayload.username, "authenticated me").toBe("bob");

  await expect(page.getByTestId("authenticated-panel")).toBeVisible();
  await expect(page.getByTestId("auth-state")).toContainText("bob");

  const storageAfterLogin = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));
  for (const [kind, entries] of Object.entries(storageAfterLogin)) {
    for (const [key, value] of entries as [string, string][]) {
      expect(
        FORBIDDEN_STORAGE_KEY.test(key) || FORBIDDEN_STORAGE_VALUE.test(value),
        `${kind} must not persist session credentials (${key})`,
      ).toBeFalsy();
    }
  }

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

  const logoutResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/logout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Abmelden" }).click();
  const logout = await logoutResponse;
  expect(logout.status(), "CSRF-protected logout").toBe(204);
  expect(logout.request().headers()["x-csrf-token"], "logout sends X-CSRF-Token").toBeTruthy();

  await expect(page.getByTestId("login-panel")).toBeVisible();
});
