/**
 * WEB00 AC14: real Chromium smoke against ephemeral HTTPS gateway + same-origin /api/v1.
 */
import { execSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import http from "node:http";
import https from "node:https";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEBCLIENT = path.resolve(__dirname, "..");
const ROOT = path.resolve(WEBCLIENT, "..");
const PYTHON = path.join(ROOT, ".venv", "Scripts", "python.exe");
const NPM = process.platform === "win32" ? "npm.cmd" : "npm";
const NPX = process.platform === "win32" ? "npx.cmd" : "npx";
const NODE = process.execPath;

const HOST = "127.0.0.1";
const EVIDENCE_DIR =
  process.env.WEB00_SMOKE_EVIDENCE_DIR ??
  path.join(ROOT, "build", "ap-029-web00", "r1-20260822T195500Z");

const children = [];
const insecureAgent = new https.Agent({ rejectUnauthorized: false });

function allocateEphemeralPort(host) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, host, () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : null;
      server.close((closeError) => {
        if (closeError) {
          reject(closeError);
          return;
        }
        if (!port) {
          reject(new Error(`failed to allocate ephemeral port on ${host}`));
          return;
        }
        resolve(port);
      });
    });
  });
}

function assertPortAvailable(host, port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", (error) => {
      reject(
        new Error(
          `port ${port} on ${host} is not available for WEB00 smoke (${error.code ?? error.message})`,
        ),
      );
    });
    server.listen(port, host, () => {
      server.close((closeError) => {
        if (closeError) {
          reject(closeError);
          return;
        }
        resolve(undefined);
      });
    });
  });
}

async function resolveSmokePort(host, envName) {
  const raw = process.env[envName]?.trim();
  if (raw) {
    const port = Number(raw);
    if (!Number.isInteger(port) || port <= 0 || port > 65535) {
      throw new Error(`${envName} must be a valid TCP port when set explicitly`);
    }
    await assertPortAvailable(host, port);
    return port;
  }
  return allocateEphemeralPort(host);
}

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      shell: false,
      ...options,
    });
    children.push(child);
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve(undefined);
      } else {
        reject(new Error(`${command} ${args.join(" ")} exited ${code}`));
      }
    });
  });
}

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    stdio: "inherit",
    shell: false,
    ...options,
  });
  children.push(child);
  return child;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHttpOk(url, attempts = 60, delayMs = 500) {
  let lastError = "unknown";
  for (let i = 0; i < attempts; i += 1) {
    try {
      await new Promise((resolve, reject) => {
        const lib = url.startsWith("https:") ? https : http;
        const options = url.startsWith("https:") ? { agent: insecureAgent } : {};
        const req = lib.get(url, options, (res) => {
          res.resume();
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 500) {
            resolve(undefined);
          } else {
            reject(new Error(`status ${res.statusCode}`));
          }
        });
        req.on("error", (error) => reject(error));
        req.setTimeout(5000, () => req.destroy(new Error("timeout")));
      });
      return;
    } catch (error) {
      lastError = String(error);
      await sleep(delayMs);
    }
  }
  throw new Error(`timeout waiting for ${url} (last: ${lastError})`);
}

function stopChildren() {
  for (const child of children) {
    if (child.killed || child.exitCode !== null) {
      continue;
    }
    if (process.platform === "win32" && child.pid) {
      try {
        // Terminate only processes started by this runner (npm/cmd/vite/python trees).
        execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: "ignore" });
      } catch {
        // already exited
      }
    } else {
      child.kill("SIGTERM");
    }
  }
}

async function main() {
  if (!existsSync(PYTHON)) {
    throw new Error(`Python venv not found: ${PYTHON}`);
  }
  await mkdir(EVIDENCE_DIR, { recursive: true });

  const backendPort = await resolveSmokePort(HOST, "WEB00_SMOKE_BACKEND_PORT");
  const previewPort = await resolveSmokePort(HOST, "WEB00_SMOKE_PREVIEW_PORT");
  const gatewayPort = await resolveSmokePort(HOST, "WEB00_SMOKE_GATEWAY_PORT");

  const backendUrl = `http://${HOST}:${backendPort}`;
  const previewUrl = `http://${HOST}:${previewPort}`;
  const gatewayUrl = `https://${HOST}:${gatewayPort}`;

  start(PYTHON, ["-m", "tests.backend.web00_browser_smoke_backend"], {
    cwd: ROOT,
    env: {
      ...process.env,
      WEB00_SMOKE_BACKEND_HOST: HOST,
      WEB00_SMOKE_BACKEND_PORT: String(backendPort),
    },
  });

  await waitForHttpOk(`${backendUrl}/health`);

  await run(NPM, ["run", "build"], {
    cwd: WEBCLIENT,
    env: { ...process.env, QMTOOL_BACKEND_URL: backendUrl },
  });

  start(
    NPM,
    ["run", "preview", "--", "--host", HOST, "--port", String(previewPort), "--strictPort"],
    {
      cwd: WEBCLIENT,
      env: { ...process.env, QMTOOL_BACKEND_URL: backendUrl },
    },
  );

  await waitForHttpOk(`${previewUrl}/`);

  start(NODE, ["scripts/https-smoke-gateway.mjs"], {
    cwd: WEBCLIENT,
    env: {
      ...process.env,
      WEB00_SMOKE_BACKEND_URL: backendUrl,
      WEB00_SMOKE_PREVIEW_URL: previewUrl,
      WEB00_SMOKE_GATEWAY_HOST: HOST,
      WEB00_SMOKE_GATEWAY_PORT: String(gatewayPort),
    },
  });

  await waitForHttpOk(`${gatewayUrl}/health`);

  await run(NPX, ["playwright", "test", "e2e/https-browser-smoke.spec.ts"], {
    cwd: WEBCLIENT,
    env: {
      ...process.env,
      WEB00_SMOKE_BASE_URL: gatewayUrl,
      WEB00_SMOKE_EVIDENCE_DIR: EVIDENCE_DIR,
    },
  });

  const result = {
    mode: "playwright-chromium-ephemeral-https-gateway",
    browser: "chromium-headless",
    gateway_url: gatewayUrl,
    preview_url: previewUrl,
    backend_url: backendUrl,
    ports: {
      backend: backendPort,
      preview: previewPort,
      gateway: gatewayPort,
    },
    port_allocation: "OS ephemeral (bind port 0); explicit env ports fail if occupied",
    tls: "self-signed (selfsigned npm, 1-day CN=127.0.0.1)",
    evidence_dir: EVIDENCE_DIR,
    proves: [
      "GET /api/v1/auth/csrf before login (204)",
      "POST /api/v1/auth/login 204 empty body (tokenless)",
      "GET /api/v1/auth/me authenticated as bob",
      "POST /api/v1/auth/logout 204 with X-CSRF-Token",
      "no session credential in localStorage/sessionStorage",
      "qmtool_session HttpOnly+Secure; not readable via document.cookie",
    ],
    exit_code: 0,
  };
  await writeFile(
    path.join(EVIDENCE_DIR, "browser-smoke-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  console.log(JSON.stringify(result, null, 2));
}

process.on("SIGINT", () => {
  stopChildren();
  process.exit(130);
});

main()
  .then(() => {
    stopChildren();
    process.exit(0);
  })
  .catch(async (error) => {
    const payload = {
      mode: "playwright-chromium-ephemeral-https-gateway",
      exit_code: 1,
      error: String(error),
    };
    try {
      await mkdir(EVIDENCE_DIR, { recursive: true });
      await writeFile(
        path.join(EVIDENCE_DIR, "browser-smoke-result.json"),
        `${JSON.stringify(payload, null, 2)}\n`,
        "utf8",
      );
    } catch {
      // best effort
    }
    console.error(error);
    stopChildren();
    process.exit(1);
  });
