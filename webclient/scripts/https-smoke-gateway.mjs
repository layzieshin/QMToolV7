/**
 * Ephemeral HTTPS same-origin front door for WEB00 browser smoke.
 * Terminates TLS with a self-signed cert and proxies:
 * - /api/v1, /health -> FastAPI backend (HTTP)
 * - all other paths -> Vite preview (HTTP)
 */
import http from "node:http";
import https from "node:https";
import httpProxy from "http-proxy";
import selfsigned from "selfsigned";

const backendTarget = process.env.WEB00_SMOKE_BACKEND_URL ?? "http://127.0.0.1:18765";
const previewTarget = process.env.WEB00_SMOKE_PREVIEW_URL ?? "http://127.0.0.1:4173";
const host = process.env.WEB00_SMOKE_GATEWAY_HOST ?? "127.0.0.1";
const port = Number(process.env.WEB00_SMOKE_GATEWAY_PORT ?? "4443");

const pems = selfsigned.generate([{ name: "commonName", value: "127.0.0.1" }], {
  days: 1,
  keySize: 2048,
  algorithm: "sha256",
});

const proxy = httpProxy.createProxyServer({
  changeOrigin: true,
  secure: false,
});

proxy.on("error", (_error, _req, res) => {
  if (res && "writeHead" in res && !res.headersSent) {
    res.writeHead(502, { "Content-Type": "text/plain" });
    res.end("gateway proxy error");
  }
});

function routeTarget(url) {
  return url.startsWith("/api/v1") || url.startsWith("/health")
    ? backendTarget
    : previewTarget;
}

const server = https.createServer({ key: pems.private, cert: pems.cert }, (req, res) => {
  proxy.web(req, res, { target: routeTarget(req.url ?? "/") });
});

server.on("upgrade", (req, socket, head) => {
  proxy.ws(req, socket, head, { target: previewTarget });
});

server.listen(port, host, () => {
  process.stdout.write(`WEB00 smoke gateway listening on https://${host}:${port}\n`);
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
