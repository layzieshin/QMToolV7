import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const WEB01_K1_PDF_MARKER = "QMTool WEB01 K1";
const WEB01_K1_MAGENTA_MIN_PIXELS = 800;

function padPdfOffset(byteOffset: number): string {
  return String(byteOffset).padStart(10, "0");
}

function buildDeterministicWeb01K1Pdf(): Buffer {
  const contentStream =
    "1 0 1 rg\n" +
    "50 650 495 100 re f\n" +
    `BT /F1 18 Tf 72 760 Td (${WEB01_K1_PDF_MARKER}) Tj ET`;
  const contentLength = Buffer.byteLength(contentStream, "ascii");
  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] " +
      "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
    `4 0 obj\n<< /Length ${contentLength} >>\nstream\n${contentStream}\nendstream\nendobj\n`,
    "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
  ];

  const header = "%PDF-1.4\n";
  let body = "";
  const objectOffsets: number[] = [0];
  let position = Buffer.byteLength(header, "ascii");
  for (const objectBody of objects) {
    objectOffsets.push(position);
    body += objectBody;
    position += Buffer.byteLength(objectBody, "ascii");
  }

  const xrefOffset = position;
  const xrefLines = [
    "xref\n",
    "0 6\n",
    `${padPdfOffset(0)} 65535 f \n`,
    ...objectOffsets.slice(1).map((offset) => `${padPdfOffset(offset)} 00000 n \n`),
  ];
  const xref = xrefLines.join("");
  const trailer = `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(header + body + xref + trailer, "ascii");
}

const WEB01_K1_SYNTHETIC_PDF = buildDeterministicWeb01K1Pdf();

const ACTION_TIMEOUT = 30_000;
const NAVIGATION_TIMEOUT = 45_000;
const SCREENSHOT_TIMEOUT = 30_000;
const WORKFLOW_STEP_TIMEOUT = 60_000;
const HANDSHAKE_TIMEOUT = 120_000;
const VIEWER_TIMEOUT = 90_000;
const STEP_TIMEOUT = 120_000;
const RESTART_STEP_TIMEOUT = 180_000;
const CONFLICT_STEP_TIMEOUT = 150_000;
const MAINTENANCE_STEP_TIMEOUT = 120_000;

function configurePageTimeouts(page: Page): void {
  page.setDefaultTimeout(ACTION_TIMEOUT);
  page.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT);
}

function requireEnv(name: string): string {
  const value = process.env[name]?.trim() ?? "";
  if (!value) {
    throw new Error(`${name} is required for the WEB01 product slice spec`);
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

async function waitForGlobalLoadingHidden(page: Page): Promise<void> {
  await expect(page.getByTestId("loading-indicator")).toBeHidden({ timeout: ACTION_TIMEOUT });
}

async function waitForDashboardBootstrapReady(page: Page): Promise<void> {
  await waitForGlobalLoadingHidden(page);
  const moduleNavigation = page.getByTestId("module-navigation");
  await expect(moduleNavigation).toBeVisible({ timeout: ACTION_TIMEOUT });
  await expect(moduleNavigation.getByRole("link", { name: "Dokumente" })).toBeVisible({
    timeout: ACTION_TIMEOUT,
  });
}

async function countMagentaMarkerPixelsFromProductCanvas(canvas: Locator): Promise<number> {
  return canvas.evaluate((element) => {
    const node = element as HTMLCanvasElement;
    const context = node.getContext("2d");
    if (!context || node.width <= 0 || node.height <= 0) {
      return 0;
    }
    const { data, width, height } = context.getImageData(0, 0, node.width, node.height);
    let magentaPixels = 0;
    for (let y = 0; y < height; y += 2) {
      for (let x = 0; x < width; x += 2) {
        const index = (y * width + x) * 4;
        const red = data[index];
        const green = data[index + 1];
        const blue = data[index + 2];
        const alpha = data[index + 3];
        if (alpha > 180 && red > 180 && green < 100 && blue > 180) {
          magentaPixels += 1;
        }
      }
    }
    return magentaPixels;
  });
}

async function waitForPdfViewerRenderReady(page: Page): Promise<void> {
  const frame = page.getByTestId("pdf-viewer-frame");
  await expect(frame).toBeVisible({ timeout: VIEWER_TIMEOUT });

  const stage = page.getByTestId("pdf-viewer-stage");
  await expect(stage).toBeVisible({ timeout: VIEWER_TIMEOUT });
  await expect(stage).toHaveAttribute("data-render-state", "ready", { timeout: VIEWER_TIMEOUT });

  const canvas = page.getByTestId("pdf-viewer-canvas");
  await expect(canvas).toBeVisible({ timeout: VIEWER_TIMEOUT });
  await expect(canvas).toHaveAttribute("data-rendered-page", "1", { timeout: VIEWER_TIMEOUT });
  await expect(canvas).toHaveAttribute("data-rendered-fit", /.+/);
  await expect(canvas).toHaveAttribute("data-rendered-scale", /.+/);

  await expect
    .poll(
      async () => {
        const geometry = await canvas.evaluate((element) => {
          const node = element as HTMLCanvasElement;
          return {
            width: node.width,
            height: node.height,
          };
        });
        if (geometry.width <= 0 || geometry.height <= 0) {
          return 0;
        }
        return countMagentaMarkerPixelsFromProductCanvas(canvas);
      },
      {
        timeout: VIEWER_TIMEOUT,
        intervals: [500, 1000, 2000],
        message: `pdf viewer canvas wait timed out waiting for magenta marker pixels >= ${WEB01_K1_MAGENTA_MIN_PIXELS}`,
      },
    )
    .toBeGreaterThanOrEqual(WEB01_K1_MAGENTA_MIN_PIXELS);
}

async function waitForSignatureVisualReady(page: Page): Promise<void> {
  const canvasSection = page.getByTestId("signature-placement-canvas");
  const canvas = page.getByTestId("signature-pdf-canvas");
  const placementBlock = page.getByTestId("signature-placement-block");

  await expect(canvasSection).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
  await expect(canvas).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
  await expect(page.getByTestId("signature-page-label")).not.toContainText("?", {
    timeout: WORKFLOW_STEP_TIMEOUT,
  });

  const baselineGeometry = await canvas.evaluate((element) => {
    const node = element as HTMLCanvasElement;
    return {
      width: node.width,
      height: node.height,
      styleWidth: node.style.width,
      styleHeight: node.style.height,
    };
  });

  await canvasSection.getByRole("button", { name: "Breite anpassen" }).click({
    timeout: ACTION_TIMEOUT,
  });

  await expect
    .poll(
      async () =>
        canvas.evaluate((element, baseline) => {
          const node = element as HTMLCanvasElement;
          return (
            node.width !== baseline.width ||
            node.height !== baseline.height ||
            node.style.width !== baseline.styleWidth ||
            node.style.height !== baseline.styleHeight
          );
        }, baselineGeometry),
      { timeout: WORKFLOW_STEP_TIMEOUT, intervals: [200, 400, 800] },
    )
    .toBe(true);

  await expect(placementBlock).toBeInViewport({ timeout: WORKFLOW_STEP_TIMEOUT });

  await expect
    .poll(
      async () =>
        canvas.evaluate((element) => {
          const node = element as HTMLCanvasElement;
          const context = node.getContext("2d");
          if (!context || node.width === 0 || node.height === 0) {
            return false;
          }
          const { data, width, height } = context.getImageData(0, 0, node.width, node.height);
          for (let y = 0; y < height; y += 8) {
            for (let x = 0; x < width; x += 8) {
              const index = (y * width + x) * 4;
              const alpha = data[index + 3];
              const red = data[index];
              const green = data[index + 1];
              const blue = data[index + 2];
              if (alpha > 0 && (red < 235 || green < 235 || blue < 235)) {
                return true;
              }
            }
          }
          return false;
        }),
      { timeout: WORKFLOW_STEP_TIMEOUT, intervals: [200, 400, 800] },
    )
    .toBe(true);
}

async function capture(
  page: Page,
  visualDir: string,
  filename: string,
  viewport: { width: number; height: number },
): Promise<void> {
  await page.setViewportSize(viewport);
  await page.screenshot({
    path: path.join(visualDir, filename),
    fullPage: false,
    timeout: SCREENSHOT_TIMEOUT,
  });
}

async function login(page: Page, username: string, password: string): Promise<void> {
  await page.goto("/", { timeout: NAVIGATION_TIMEOUT });
  await page.getByLabel("Benutzername").fill(username, { timeout: ACTION_TIMEOUT });
  await page.getByLabel("Passwort").fill(password, { timeout: ACTION_TIMEOUT });
  await page.getByRole("button", { name: "Anmelden" }).click({ timeout: ACTION_TIMEOUT });
}

async function logout(page: Page): Promise<void> {
  const logoutResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/logout") && response.request().method() === "POST",
    { timeout: ACTION_TIMEOUT },
  );
  await page.getByRole("button", { name: "Abmelden" }).click({ timeout: ACTION_TIMEOUT });
  const logout = await logoutResponse;
  expect(logout.status()).toBe(204);
  await expect(page.getByTestId("login-panel")).toBeVisible({ timeout: ACTION_TIMEOUT });
}

async function ensureSpaShell(page: Page): Promise<void> {
  const hasShell =
    (await page.getByTestId("authenticated-panel").count()) > 0 ||
    (await page.getByTestId("login-panel").count()) > 0;
  if (!hasShell) {
    await page.goto("/", { timeout: NAVIGATION_TIMEOUT });
  }
  await expect(
    page.getByTestId("authenticated-panel").or(page.getByTestId("login-panel")),
  ).toBeVisible({ timeout: ACTION_TIMEOUT });
}

async function spaNavigate(page: Page, targetPath: string): Promise<void> {
  await ensureSpaShell(page);
  await page.evaluate(async (routePath) => {
    const root = document.querySelector("#app") as
      | (HTMLElement & {
          __vue_app__?: {
            config: {
              globalProperties: {
                $router: { push: (location: string) => Promise<unknown> };
              };
            };
          };
        })
      | null;
    const router = root?.__vue_app__?.config?.globalProperties?.$router;
    if (!router) {
      throw new Error("Vue router is not available on #app");
    }
    await router.push(routePath);
  }, targetPath);
}

async function withSlowDocumentsQuery(page: Page, action: () => Promise<void>): Promise<void> {
  const pattern = "**/api/v1/documents/query?**";
  let routeCompletion: Promise<void> | null = null;
  const handler = (route: Route): Promise<void> => {
    routeCompletion = (async () => {
      await new Promise((resolve) => setTimeout(resolve, 2_000));
      await route.continue();
    })();
    return routeCompletion;
  };
  await page.route(pattern, handler);
  try {
    await action();
  } finally {
    if (routeCompletion) {
      await routeCompletion;
    }
    await page.unroute(pattern, handler);
  }
}

async function completeSignatureAction(
  page: Page,
  documentId: string,
  version: number,
  actionCode: "complete_editing" | "review_accept" | "approval_accept",
  password: string,
): Promise<void> {
  const signaturePath = `/documents/${encodeURIComponent(documentId)}/signature?version=${version}&action=${actionCode}`;
  await spaNavigate(page, signaturePath);
  await expect(page.getByTestId("signature-workspace")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
  await expect(page.getByTestId("signature-sign-button")).toBeEnabled({ timeout: WORKFLOW_STEP_TIMEOUT });
  await page.getByTestId("signature-sign-button").click({ timeout: ACTION_TIMEOUT });
  await expect(page.getByTestId("reauth-dialog")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
  await page.getByTestId("reauth-password").locator("input").fill(password, { timeout: ACTION_TIMEOUT });
  await page.getByTestId("reauth-submit").click({ timeout: ACTION_TIMEOUT });
  await expect(page.getByTestId("signature-result-panel")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
}

async function resolveCurrentArtifactId(
  page: Page,
  documentId: string,
  version: number,
  artifactType: "SIGNED_PDF" | "RELEASED_PDF",
): Promise<string> {
  const artifactId = await page.evaluate(
    async ({ docId, ver, type }) => {
      const response = await fetch(
        `/api/v1/documents/versions/${encodeURIComponent(docId)}/${ver}/artifacts`,
        { credentials: "include" },
      );
      if (!response.ok) {
        throw new Error(`artifacts request failed with HTTP ${response.status}`);
      }
      const body = (await response.json()) as Array<{
        artifact_id?: string;
        artifact_type?: string;
        is_current?: boolean;
        created_at?: string;
      }>;
      const currentOfType = body.filter(
        (row) => row.artifact_type === type && row.is_current === true,
      );
      if (currentOfType.length === 0) {
        return null;
      }
      const sorted = [...currentOfType].sort((left, right) => {
        const rightTime = Date.parse(String(right.created_at ?? ""));
        const leftTime = Date.parse(String(left.created_at ?? ""));
        return rightTime - leftTime;
      });
      const newest = sorted[0];
      const id = String(newest.artifact_id ?? "").trim();
      return id || null;
    },
    { docId: documentId, ver: version, type: artifactType },
  );
  expect(
    artifactId,
    `requires a current ${artifactType} artifact; no fallback to other types`,
  ).not.toBeNull();
  return artifactId as string;
}

async function resolveCurrentSignedPdfArtifactId(
  page: Page,
  documentId: string,
  version: number,
): Promise<string> {
  return resolveCurrentArtifactId(page, documentId, version, "SIGNED_PDF");
}

async function resolveCurrentReleasedPdfArtifactId(
  page: Page,
  documentId: string,
  version: number,
): Promise<string> {
  return resolveCurrentArtifactId(page, documentId, version, "RELEASED_PDF");
}

test.describe("WEB01 product slice", () => {
  test.beforeEach(() => {
    test.skip(
      process.env.QMTOOL_WEB01_JOINT !== "1",
      "WEB01 product slice runs only from the guarded Python harness",
    );
  });

  test("PIS lifecycle and 16-state visual matrix", async ({ browser }) => {
    test.setTimeout(600_000);

    const evidenceDir = requireEnv("QMTOOL_WEB01_EVIDENCE_DIR");
    const visualDir = requireEnv("QMTOOL_WEB01_VISUAL_DIR");
    await mkdir(visualDir, { recursive: true });

    const adminUser = requireEnv("QMTOOL_WEB01_ADMIN_USER");
    const adminPass = requireEnv("QMTOOL_WEB01_ADMIN_PASS");
    const mustChangeUser = requireEnv("QMTOOL_WEB01_MUSTCHANGE_USER");
    const mustChangePass = requireEnv("QMTOOL_WEB01_MUSTCHANGE_PASS");
    const editorUser = requireEnv("QMTOOL_WEB01_EDITOR_USER");
    const editorPass = requireEnv("QMTOOL_WEB01_EDITOR_PASS");
    const reviewerUser = requireEnv("QMTOOL_WEB01_REVIEWER_USER");
    const reviewerPass = requireEnv("QMTOOL_WEB01_REVIEWER_PASS");
    const approverUser = requireEnv("QMTOOL_WEB01_APPROVER_USER");
    const approverPass = requireEnv("QMTOOL_WEB01_APPROVER_PASS");
    const pisDocumentId = requireEnv("QMTOOL_WEB01_PIS_DOCUMENT_ID");
    const conflictDocumentId = requireEnv("QMTOOL_WEB01_DOCUMENT_ID");
    const conflictVersion = Number(requireEnv("QMTOOL_WEB01_VERSION"));

    const desktop = { width: 1280, height: 800 };
    const stacked = { width: 390, height: 844 };

    await test.step(
      "anonymous login screenshots",
      async () => {
        const anonPage = await browser.newPage();
        configurePageTimeouts(anonPage);
        await anonPage.goto("/", { timeout: NAVIGATION_TIMEOUT });
        await expect(anonPage.getByTestId("login-panel")).toBeVisible({ timeout: ACTION_TIMEOUT });
        await capture(anonPage, visualDir, "login-desktop.png", desktop);
        await capture(anonPage, visualDir, "login-stacked.png", stacked);
        await anonPage.close();
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "must-change password flow",
      async () => {
        const mustChangePage = await browser.newPage();
        configurePageTimeouts(mustChangePage);
        await login(mustChangePage, mustChangeUser, mustChangePass);
        await expect(mustChangePage.getByTestId("change-password-panel")).toBeVisible({
          timeout: ACTION_TIMEOUT,
        });
        await capture(mustChangePage, visualDir, "change-password-desktop.png", desktop);
        await mustChangePage
          .getByLabel("Neues Passwort")
          .fill("web01-fixture-mustchange-rotated", { timeout: ACTION_TIMEOUT });
        await mustChangePage
          .getByRole("button", { name: "Passwort speichern" })
          .click({ timeout: ACTION_TIMEOUT });
        await expect(mustChangePage.getByTestId("authenticated-panel")).toBeVisible({
          timeout: ACTION_TIMEOUT,
        });
        await mustChangePage.close();
      },
      { timeout: STEP_TIMEOUT },
    );

    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    configurePageTimeouts(adminPage);

    await test.step(
      "dashboard and pool matrix screenshots",
      async () => {
      await login(adminPage, adminUser, adminPass);
      await expect(adminPage.getByTestId("authenticated-panel")).toBeVisible({ timeout: ACTION_TIMEOUT });
      await adminPage.goto("/", { timeout: NAVIGATION_TIMEOUT });
      await expect(adminPage.getByTestId("shell-logout")).toBeVisible({
        timeout: ACTION_TIMEOUT,
      });
      await waitForDashboardBootstrapReady(adminPage);
      await capture(adminPage, visualDir, "dashboard-desktop.png", desktop);

      await withSlowDocumentsQuery(adminPage, async () => {
        await adminPage.getByTestId("module-navigation").getByRole("link", { name: "Dokumente" }).click();
        await expect(adminPage.getByTestId("documents-pool-loading")).toBeVisible({ timeout: 15_000 });
        await capture(adminPage, visualDir, "loading-pool-desktop.png", desktop);
      });
      await expect(adminPage.getByTestId("documents-pool-view")).toBeVisible();

      await spaNavigate(adminPage, "/documents?cursor=not-valid");
      await expect(adminPage.getByTestId("documents-pool-error")).toBeVisible();
      await capture(adminPage, visualDir, "error-pool-desktop.png", desktop);

      await spaNavigate(adminPage, "/documents?q=ZZZ-WEB01-NO-MATCH");
      await expect(adminPage.getByTestId("documents-pool-empty-filtered")).toBeVisible();
      await capture(adminPage, visualDir, "empty-pool-desktop.png", desktop);
      },
      { timeout: STEP_TIMEOUT },
    );

    const editorContext = await browser.newContext();
    const editorPage = await editorContext.newPage();
    configurePageTimeouts(editorPage);

    await test.step(
      "editor import and PIS document handshake",
      async () => {
      await login(editorPage, editorUser, editorPass);
      await spaNavigate(editorPage, "/documents/import");
      await expect(editorPage.getByTestId("document-import-view")).toBeVisible();
      await editorPage.getByTestId("document-import-document-id").locator("input").fill(pisDocumentId);
      await editorPage.getByTestId("document-import-version").locator("input").fill("1");
      await editorPage.getByTestId("document-import-title").locator("input").fill("WEB01 K1 PIS");
      await editorPage.getByTestId("document-import-file").setInputFiles({
        name: "web01-k1.pdf",
        mimeType: "application/pdf",
        buffer: WEB01_K1_SYNTHETIC_PDF,
      });
      await editorPage.getByTestId("document-import-submit").click();
      await expect(editorPage.getByTestId("document-detail-view")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });

      const pisEtag = await editorPage.evaluate(
        async ({ docId }) => {
          const response = await fetch(`/api/v1/documents/versions/${encodeURIComponent(docId)}/1`, {
            credentials: "include",
          });
          const body = await response.json();
          return String(body.etag ?? "");
        },
        { docId: pisDocumentId },
      );
      expect(pisEtag).not.toBe("");
      await writeFile(
        path.join(evidenceDir, "pis-document-ready.json"),
        JSON.stringify(
          {
            phase: "pis-document-ready",
            documentId: pisDocumentId,
            version: 1,
            etag: pisEtag,
          },
          null,
          2,
        ),
        "utf-8",
      );
      await waitForFile(path.join(evidenceDir, "pis-roles-assigned.json"), HANDSHAKE_TIMEOUT);
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "pool split and stacked screenshots",
      async () => {
      await spaNavigate(editorPage, "/documents");
      const pisRow = editorPage
        .locator('[data-testid="documents-table-row"]')
        .filter({ hasText: "WEB01 K1 PIS" });
      await expect(pisRow).toBeVisible();
      await pisRow.click();
      await capture(editorPage, visualDir, "pool-split-desktop.png", desktop);
      await capture(editorPage, visualDir, "pool-stacked.png", stacked);
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "editor workflow start and editing signature",
      async () => {
      await spaNavigate(editorPage, `/documents/${encodeURIComponent(pisDocumentId)}?version=1`);
      await expect(editorPage.getByTestId("workflow-actions-bar")).toBeVisible();
      const expectedStartPath =
        `/api/v1/documents/versions/${encodeURIComponent(pisDocumentId)}/1/workflow/start`;
      const startResponse = editorPage.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === expectedStartPath &&
          response.request().method() === "POST",
        { timeout: WORKFLOW_STEP_TIMEOUT },
      );
      await editorPage.getByTestId("workflow-action-start").click({ timeout: ACTION_TIMEOUT });
      const start = await startResponse;
      expect(start.ok(), "workflow start must succeed with HTTP 2xx").toBe(true);
      await expect(editorPage.getByTestId("workflow-confirm-dialog")).toBeHidden({
        timeout: ACTION_TIMEOUT,
      });
      await expect(editorPage.getByTestId("workflow-action-complete_editing")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await completeSignatureAction(editorPage, pisDocumentId, 1, "complete_editing", editorPass);
      await spaNavigate(editorPage, `/documents/${encodeURIComponent(pisDocumentId)}?version=1`);
      await expect(editorPage.getByTestId("workflow-action-review_accept")).toBeHidden({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "reviewer review comment and signature",
      async () => {
      const reviewerContext = await browser.newContext();
      const reviewerPage = await reviewerContext.newPage();
      configurePageTimeouts(reviewerPage);
      await login(reviewerPage, reviewerUser, reviewerPass);
      await spaNavigate(
        reviewerPage,
        `/documents/${encodeURIComponent(pisDocumentId)}/viewer?version=1`,
      );
      await expect(reviewerPage.getByTestId("document-viewer-view")).toBeVisible({
        timeout: VIEWER_TIMEOUT,
      });
      const signedPdfArtifactId = await resolveCurrentSignedPdfArtifactId(
        reviewerPage,
        pisDocumentId,
        1,
      );
      const artifactSelect = reviewerPage.getByTestId("artifact-select");
      await expect(artifactSelect).toBeVisible({ timeout: VIEWER_TIMEOUT });
      await artifactSelect.selectOption(signedPdfArtifactId, { timeout: ACTION_TIMEOUT });
      await expect(artifactSelect).toHaveValue(signedPdfArtifactId);
      await expect(reviewerPage.getByTestId("comments-create-form")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await reviewerPage
        .getByTestId("comments-text-input")
        .fill("WEB01 K1 review comment", { timeout: ACTION_TIMEOUT });
      await reviewerPage.getByTestId("comments-submit").click({ timeout: ACTION_TIMEOUT });
      await expect(reviewerPage.getByTestId("comments-submit-success")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await completeSignatureAction(reviewerPage, pisDocumentId, 1, "review_accept", reviewerPass);
      await reviewerPage.close();
      await reviewerContext.close();
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "approver signature screenshot and approval release",
      async () => {
      const approverContext = await browser.newContext();
      const approverPage = await approverContext.newPage();
      configurePageTimeouts(approverPage);
      await login(approverPage, approverUser, approverPass);
      await spaNavigate(
        approverPage,
        `/documents/${encodeURIComponent(pisDocumentId)}/signature?version=1&action=approval_accept`,
      );
      await expect(approverPage.getByTestId("signature-workspace")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await expect(approverPage.getByTestId("signature-sign-button")).toBeEnabled({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await waitForSignatureVisualReady(approverPage);
      await capture(approverPage, visualDir, "signature-desktop.png", desktop);
      await approverPage.getByTestId("signature-sign-button").click({ timeout: ACTION_TIMEOUT });
      await expect(approverPage.getByTestId("reauth-dialog")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
      await approverPage
        .getByTestId("reauth-password")
        .locator("input")
        .fill(approverPass, { timeout: ACTION_TIMEOUT });
      await approverPage.getByTestId("reauth-submit").click({ timeout: ACTION_TIMEOUT });
      await expect(approverPage.getByTestId("signature-result-panel")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await resolveCurrentReleasedPdfArtifactId(approverPage, pisDocumentId, 1);
      await approverPage.close();
      await approverContext.close();
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "released PDF viewer screenshot",
      async () => {
      await spaNavigate(
        editorPage,
        `/documents/${encodeURIComponent(pisDocumentId)}/viewer?version=1`,
      );
      await expect(editorPage.getByTestId("document-viewer-view")).toBeVisible({ timeout: VIEWER_TIMEOUT });
      const releasedPdfArtifactId = await resolveCurrentReleasedPdfArtifactId(
        editorPage,
        pisDocumentId,
        1,
      );
      const releasedArtifactSelect = editorPage.getByTestId("artifact-select");
      await expect(releasedArtifactSelect).toBeVisible({ timeout: VIEWER_TIMEOUT });
      await releasedArtifactSelect.selectOption(releasedPdfArtifactId, { timeout: ACTION_TIMEOUT });
      await expect(releasedArtifactSelect).toHaveValue(releasedPdfArtifactId);
      await waitForPdfViewerRenderReady(editorPage);
      await capture(editorPage, visualDir, "viewer-desktop.png", desktop);
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "released read-only detail with history panel screenshot",
      async () => {
      await spaNavigate(
        editorPage,
        `/documents/${encodeURIComponent(pisDocumentId)}?version=1&section=history`,
      );
      await expect(editorPage.getByTestId("document-detail-history-panel")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await expect(editorPage.getByTestId("history-panel-list")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await expect(editorPage.getByTestId("workflow-action-start")).toBeHidden();
      await capture(editorPage, visualDir, "detail-desktop.png", desktop);
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "forbidden and admin users screenshots",
      async () => {
      const forbiddenPage = await browser.newPage();
      configurePageTimeouts(forbiddenPage);
      await login(forbiddenPage, editorUser, editorPass);
      await spaNavigate(forbiddenPage, "/admin/users");
      await expect(forbiddenPage.getByTestId("admin-users-error")).toBeVisible();
      await capture(forbiddenPage, visualDir, "forbidden-desktop.png", desktop);
      await forbiddenPage.close();

      await spaNavigate(adminPage, "/admin/users");
      await expect(adminPage.getByTestId("admin-users-table")).toBeVisible();
      await capture(adminPage, visualDir, "admin-users-desktop.png", desktop);
      await adminPage.getByTestId("admin-users-row-link").first().click();
      await expect(adminPage.getByTestId("admin-user-detail-view")).toBeVisible({
        timeout: ACTION_TIMEOUT,
      });
      },
      { timeout: STEP_TIMEOUT },
    );

    await test.step(
      "conflict 409 dialog screenshot",
      async () => {
      await spaNavigate(
        editorPage,
        `/documents/${encodeURIComponent(conflictDocumentId)}?version=${conflictVersion}`,
      );
      await expect(editorPage.getByTestId("workflow-actions-bar")).toBeVisible();
      const detailEtag = await editorPage.evaluate(
        async ({ docId, ver }) => {
          const response = await fetch(
            `/api/v1/documents/versions/${encodeURIComponent(docId)}/${ver}`,
            { credentials: "include" },
          );
          const body = await response.json();
          return String(body.etag ?? "");
        },
        { docId: conflictDocumentId, ver: conflictVersion },
      );
      expect(detailEtag).not.toBe("");
      await writeFile(
        path.join(evidenceDir, "detail-ready.json"),
        JSON.stringify(
          {
            phase: "detail-ready",
            documentId: conflictDocumentId,
            version: conflictVersion,
            etag: detailEtag,
          },
          null,
          2,
        ),
        "utf-8",
      );
      await waitForFile(path.join(evidenceDir, "stale-mutation-complete.json"), HANDSHAKE_TIMEOUT);
      await editorPage.getByTestId("workflow-action-start").click({ timeout: ACTION_TIMEOUT });
      await expect(editorPage.getByTestId("conflict-dialog")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
      await capture(editorPage, visualDir, "conflict-desktop.png", desktop);
      await editorPage.getByTestId("conflict-load-server").click({ timeout: ACTION_TIMEOUT });
      await expect(editorPage.getByTestId("conflict-dialog")).toBeHidden({ timeout: ACTION_TIMEOUT });
      },
      { timeout: CONFLICT_STEP_TIMEOUT },
    );

    await test.step(
      "maintenance degraded banner screenshot",
      async () => {
      await writeFile(
        path.join(evidenceDir, "maintenance-request.json"),
        JSON.stringify({ phase: "maintenance-request" }, null, 2),
        "utf-8",
      );
      await waitForFile(path.join(evidenceDir, "maintenance-complete.json"), HANDSHAKE_TIMEOUT);
      await adminPage.goto("/", { timeout: NAVIGATION_TIMEOUT });
      await expect(adminPage.getByTestId("connection-banner")).toBeVisible({ timeout: WORKFLOW_STEP_TIMEOUT });
      await expect(adminPage.getByTestId("connection-banner-message")).toContainText(
        "Wartungsmodus – Schreibzugriff gesperrt",
      );
      await waitForGlobalLoadingHidden(adminPage);
      await capture(adminPage, visualDir, "maintenance-banner-desktop.png", desktop);
      await writeFile(
        path.join(evidenceDir, "maintenance-exit-request.json"),
        JSON.stringify({ phase: "maintenance-exit-request" }, null, 2),
        "utf-8",
      );
      await waitForFile(path.join(evidenceDir, "maintenance-exit-complete.json"), HANDSHAKE_TIMEOUT);
      const connection = await adminPage.evaluate(async () => {
        const response = await fetch("/api/v1/session/connection", { credentials: "include" });
        if (!response.ok) {
          throw new Error(`session/connection failed with HTTP ${response.status}`);
        }
        return (await response.json()) as { maintenance?: boolean; writes_allowed?: boolean };
      });
      expect(connection.maintenance).toBe(false);
      expect(connection.writes_allowed).toBe(true);
      },
      { timeout: MAINTENANCE_STEP_TIMEOUT },
    );

    let savedUrl = "";
    await test.step(
      "restart deep-link session restore",
      async () => {
      const restorePath = `/documents/${encodeURIComponent(pisDocumentId)}?version=1&section=history`;
      await adminPage.goto(restorePath, { timeout: NAVIGATION_TIMEOUT });
      await expect(adminPage.getByTestId("document-detail-history-panel")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      savedUrl = adminPage.url();
      await writeFile(
        path.join(evidenceDir, "restart-request.json"),
        JSON.stringify(
          { phase: "ready-for-host-restart", username: adminUser, restoreUrl: savedUrl },
          null,
          2,
        ),
        "utf-8",
      );
      await waitForFile(path.join(evidenceDir, "restart-complete.json"), HANDSHAKE_TIMEOUT);
      const meAfterRestart = await adminContext.request.get("/api/v1/auth/me", {
        timeout: ACTION_TIMEOUT,
      });
      expect(meAfterRestart.status(), "cookie session survives ServiceHost restart").toBe(200);
      await adminPage.goto(savedUrl, { timeout: NAVIGATION_TIMEOUT });
      await expect(adminPage.getByTestId("document-detail-view")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      await expect(adminPage.getByTestId("document-detail-history-panel")).toBeVisible({
        timeout: WORKFLOW_STEP_TIMEOUT,
      });
      expect(adminPage.url(), "restart restore must reload the saved deep link").toBe(savedUrl);
      },
      { timeout: RESTART_STEP_TIMEOUT },
    );

    await test.step(
      "logout invalidates session",
      async () => {
      expect(adminPage.url(), "logout remains available on the restored deep link").toBe(savedUrl);
      await expect(adminPage.getByTestId("shell-logout")).toBeVisible({
        timeout: ACTION_TIMEOUT,
      });
      await logout(adminPage);
      const meAfterLogout = await adminPage.evaluate(async () => {
        const response = await fetch("/api/v1/auth/me");
        return response.status;
      });
      expect(meAfterLogout).toBe(401);
      },
      { timeout: STEP_TIMEOUT },
    );

    await adminContext.close();
    await editorContext.close();
  });
});
