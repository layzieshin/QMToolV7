import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

// Visual/component integration evidence only. All API traffic is synthetic;
// no ServiceHost, PostgreSQL, signing write or human acceptance is exercised.
function syntheticPdf(): Buffer {
  const stream = "BT /F1 22 Tf 50 775 Td (SYNTHETISCHE PRUEFANWEISUNG) Tj 0 -38 Td /F1 12 Tf (QMTool - UI-Pruefung ohne Produktivdaten) Tj 0 -45 Td (1. Dokument pruefen) Tj 0 -25 Td (2. Unterschrift und Angaben platzieren) Tj 0 -25 Td (3. Nach Sichtpruefung mit Passwort bestaetigen) Tj ET";
  const objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(pdf, "ascii");
}

test("approved UI package: synthetic desktop views, full signature preview and responsive shell", async ({ page, context, baseURL }) => {
  const output = resolve(process.env.UI_PILOT_SCREENSHOT_DIR ?? "../build/ui-pilot-synthetic");
  await mkdir(output, { recursive: true });
  await context.addCookies([{ name: "qmtool_csrf", value: "synthetic-csrf", url: baseURL! }]);
  const pngUrl = await page.evaluate(() => {
    const canvas = document.createElement("canvas"); canvas.width = 300; canvas.height = 90;
    const pen = canvas.getContext("2d")!; pen.strokeStyle = "#173d64"; pen.lineWidth = 3;
    pen.beginPath(); pen.moveTo(18, 64); pen.bezierCurveTo(88, -30, 18, 92, 124, 28); pen.bezierCurveTo(140, 72, 162, 7, 185, 56); pen.bezierCurveTo(214, 20, 237, 60, 278, 29); pen.stroke();
    return canvas.toDataURL("image/png");
  });
  const png = Buffer.from(pngUrl.split(",")[1], "base64");
  const actions = ["complete_editing", "preview"].map(code => ({ code, enabled: true, destructive: false, label_key: `documents.action.${code}`, requires_confirmation: false, requires_reason: false, severity: "info", signature_required: code === "complete_editing", assignment_kind: code === "complete_editing" ? "editor" : null }));
  const item = { document_id: "SYN-001", version: 1, title: "Prüfanweisung Wareneingang", description: "Synthetischer Datensatz für die UI-Sichtprüfung.", status: "IN_PROGRESS", doc_type: "SOP", control_class: "CONTROLLED", workflow_profile_id: "synthetic", workflow_active: true, assignments: { editors: ["synthetic-user"], reviewers: [], approvers: [] }, approved_by: [], reviewed_by: [], edit_signature_done: false, extension_count: 0, updated_at: "2026-10-02T08:00:00Z", allowed_actions: actions, available_actions: ["complete_editing", "preview"] };
  const detail = { etag: "synthetic-etag", allowed_actions: actions, available_actions: item.available_actions, state: item };
  const template = { template_id: "synthetic-template", name: "Standard · Name und Zeit", scope: "user", owner_user_id: "synthetic-user", signature_asset_id: "synthetic-asset", document_type: "SOP", role_context: "editor", created_at: "2026-10-02T08:00:00Z", placement: { page_index: 0, x: 72, y: 470, target_width: 145 }, layout: { show_signature: true, show_name: true, show_date: true, show_time: true, name_position: "above", date_position: "below", name_font_size: 12, date_font_size: 12, name_above: 6, name_below: 12, date_above: 18, date_below: 24, x_offset: 0, color_hex: "#173d64" } };
  const unexpected: string[] = [];
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let payload: unknown;
    if (path === "/auth/me") payload = { user_id: "synthetic-user", session_id: "synthetic-session", request_id: "synthetic-request", organization_id: "synthetic-org", username: "demo.signer", global_roles: ["USER"], is_qmb: false, authenticated_at: "2026-10-02T08:00:00Z" };
    else if (path === "/session/connection") payload = { contract_version: "1", maintenance: false, service: "qmtool-backend", status: "ok", writes_allowed: true };
    else if (path === "/session/bootstrap") payload = { contract_version: "1", modules: [{ id: "documents", licensed: true, authorized: true, capabilities: ["read"] }] };
    else if (path === "/documents/home/tasks") payload = [item, { ...item, document_id: "SYN-002", title: "Arbeitsanweisung Probenannahme", status: "IN_REVIEW", version: 3 }];
    else if (path === "/documents/query") payload = { items: [item, { ...item, document_id: "SYN-002", title: "Arbeitsanweisung Probenannahme", status: "IN_REVIEW", version: 3 }, { ...item, document_id: "SYN-003", title: "Qualitätsleitbild", status: "APPROVED", workflow_active: false }], limit: 50, next_cursor: null };
    else if (path === "/documents/capabilities") payload = { can_create_new_documents: true };
    else if (path === "/documents/versions/SYN-001/1") payload = detail;
    else if (path.endsWith("/workflow/ensure-source-pdf")) payload = { ...detail, artifact_id: "synthetic-pdf" };
    else if (path.endsWith("/artifacts") || path.endsWith("/history")) payload = [];
    else if (path === "/signature/assets/active/id") payload = { asset_id: "synthetic-asset" };
    else if (path === "/signature/assets/active/content") { await route.fulfill({ contentType: "image/png", body: png }); return; }
    else if (path === "/documents/artifacts/synthetic-pdf/preview") { await route.fulfill({ contentType: "application/pdf", body: syntheticPdf() }); return; }
    else if (path === "/signature/templates/user") payload = [template];
    else if (path === "/signature/templates/global") payload = [];
    else if (path === "/signature/templates/suggestion") payload = template;
    else { unexpected.push(`${route.request().method()} ${path}`); await route.abort(); return; }
    await route.fulfill({ json: payload });
  });
  const browserErrors: string[] = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.getByTestId("dashboard-task")).toHaveCount(2);
  const refresh = page.getByRole("button", { name: "Aktualisieren", exact: true });
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect(page.getByTestId("dashboard-task")).toHaveCount(2);
  await expect(refresh).toBeEnabled();
  // Vuetify animates disabled -> enabled opacity; capture the settled usable state.
  await expect.poll(() => refresh.evaluate(button => Number(getComputedStyle(button).opacity))).toBeGreaterThan(0.99);
  await page.screenshot({ path: `${output}/dashboard-1440.png`, fullPage: true });
  await page.getByTestId("dashboard-documents").click();
  await expect(page.getByTestId("documents-table-status")).toHaveCount(3);
  await page.getByTestId("documents-table-row").first().click();
  await expect(page.getByTestId("documents-pool-open-detail")).toBeEnabled();
  await page.screenshot({ path: `${output}/documents-1440.png`, fullPage: true });
  await page.goto("/documents/SYN-001/signature?version=1&action=complete_editing");
  await expect(page.getByTestId("signature-preview-name")).toHaveText("demo.signer");
  await expect(page.getByTestId("signature-preview-date")).toContainText(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/);
  await expect(page.getByTestId("signature-preview-image")).toBeVisible();
  await expect.poll(() => page.getByTestId("signature-pdf-canvas").evaluate(canvas => (canvas as HTMLCanvasElement).width)).toBeGreaterThan(500);
  const pdfRegion = await page.getByTestId("signature-workspace-canvas-region").boundingBox();
  const sidebar = await page.getByTestId("signature-workspace-sidebar").boundingBox();
  expect(pdfRegion!.width).toBeGreaterThan(sidebar!.width * 2);
  await page.screenshot({ path: `${output}/signature-1440.png`, fullPage: true });
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1280, height: 800 }, { width: 800, height: 900 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.getByTestId("signature-sign-button")).toBeVisible();
    await page.screenshot({ path: `${output}/signature-${viewport.width}.png`, fullPage: true });
  }
  expect(browserErrors).toEqual([]);
  expect(unexpected).toEqual([]);
});
