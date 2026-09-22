import { expect, test } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import path from "node:path";

function requireEnv(name: string): string {
  const value = process.env[name]?.trim() ?? "";
  if (!value) {
    throw new Error(`${name} is required for the WEB01 conflict live spec`);
  }
  return value;
}

async function waitForFile(filePath: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await import("node:fs/promises").then((fs) => fs.access(filePath));
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw new Error(`timeout waiting for ${filePath}`);
}

test.describe("WEB01 conflict live proof", () => {
  test.beforeEach(() => {
    test.skip(
      process.env.QMTOOL_WEB01_JOINT !== "1",
      "WEB01 conflict spec runs only from the guarded Python harness",
    );
  });

  test("428 without If-Match and 409 stale workflow conflict recovery", async ({ page }) => {
    const documentId = requireEnv("QMTOOL_WEB01_DOCUMENT_ID");
    const version = Number(requireEnv("QMTOOL_WEB01_VERSION"));
    const profileId = requireEnv("QMTOOL_WEB01_PROFILE_ID");
    const username = requireEnv("QMTOOL_WEB01_USERNAME");
    const password = requireEnv("QMTOOL_WEB01_PASSWORD");
    const evidenceDir = requireEnv("QMTOOL_WEB01_EVIDENCE_DIR");

    await page.goto("/");
    await page.getByLabel("Benutzername").fill(username);
    await page.getByLabel("Passwort").fill(password);
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page.getByTestId("authenticated-panel")).toBeVisible();

    const missingIfMatch = await page.evaluate(
      async ({ docId, ver, profile }) => {
        const csrfMatch = document.cookie.match(/(?:^|; )qmtool_csrf=([^;]*)/);
        const csrf = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (csrf) {
          headers["X-CSRF-Token"] = csrf;
        }
        const response = await fetch(
          `/api/v1/documents/versions/${encodeURIComponent(docId)}/${ver}/workflow/start`,
          {
            method: "POST",
            headers,
            credentials: "include",
            body: JSON.stringify({ profile_id: profile }),
          },
        );
        const body = await response.json().catch(() => ({}));
        const detail = body?.detail ?? {};
        return { status: response.status, error: detail.error ?? null };
      },
      { docId: documentId, ver: version, profile: profileId },
    );

    expect(missingIfMatch.status, "missing If-Match must yield HTTP 428").toBe(428);
    expect(missingIfMatch.error, "428 contract error code").toBe("if_match_required");

    await expect(page.getByTestId("module-navigation")).toBeVisible();
    await page.getByTestId("module-navigation").getByRole("link", { name: "Dokumente" }).click();
    await expect(page.getByTestId("documents-pool-view")).toBeVisible();
    const targetRow = page
      .locator('[data-testid="documents-table-row"]')
      .filter({ hasText: documentId });
    await expect(targetRow).toBeVisible();
    await targetRow.click();
    await page.getByTestId("documents-pool-open-detail").click();
    await expect(page).toHaveURL(new RegExp(`/documents/${encodeURIComponent(documentId)}`));
    await expect(page.getByTestId("document-detail-view")).toBeVisible();
    await expect(page.getByTestId("workflow-actions-bar")).toBeVisible();

    const detailEtag = await page.evaluate(
      async ({ docId, ver }) => {
        const response = await fetch(
          `/api/v1/documents/versions/${encodeURIComponent(docId)}/${ver}`,
          { credentials: "include" },
        );
        const body = await response.json();
        return String(body.etag ?? "");
      },
      { docId: documentId, ver: version },
    );
    expect(detailEtag, "detail ETag required for stale-mutation handshake").not.toBe("");

    await writeFile(
      path.join(evidenceDir, "detail-ready.json"),
      JSON.stringify({ phase: "detail-ready", documentId, version, etag: detailEtag }, null, 2),
      "utf-8",
    );

    await waitForFile(path.join(evidenceDir, "stale-mutation-complete.json"), 60_000);

    const startButton = page.getByRole("button", { name: "Workflow starten" });
    await expect(startButton).toBeVisible();
    await startButton.click();

    await expect(page.getByTestId("conflict-dialog")).toBeVisible();
    await page.getByTestId("conflict-load-server").click();
    await expect(page.getByTestId("conflict-dialog")).toBeHidden();

    await expect(page.getByTestId("workflow-actions-bar")).toBeVisible();
    await expect(page.getByTestId("workflow-actions-alert")).toHaveCount(0);
    await expect(startButton).toBeVisible();
  });
});
