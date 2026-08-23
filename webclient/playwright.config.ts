import { defineConfig } from "@playwright/test";

const baseURL = process.env.WEB00_SMOKE_BASE_URL ?? "https://127.0.0.1:4443";
const evidenceDir = process.env.WEB00_SMOKE_EVIDENCE_DIR;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: evidenceDir
    ? [
        ["list"],
        ["json", { outputFile: `${evidenceDir}/browser-smoke-playwright.json` }],
      ]
    : [["list"]],
  use: {
    baseURL,
    ignoreHTTPSErrors: true,
    headless: true,
    trace: "off",
  },
});
