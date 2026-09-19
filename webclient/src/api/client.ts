import type { components } from "./openapi";
import type { ApiErrorResponse, LoginRequest, MeResponse } from "./types";

const API_PREFIX = "/api/v1";
const CSRF_COOKIE = "qmtool_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export type ConnectionResponse = components["schemas"]["ConnectionResponse"];
export type BootstrapResponse = components["schemas"]["BootstrapResponse"];
export type ModuleBootstrapItem = components["schemas"]["ModuleBootstrapItem"];
export type DocumentQueryItem = components["schemas"]["DocumentQueryItem"];
export type DocumentQueryPageResponse = components["schemas"]["DocumentQueryPageResponse"];

export type DocumentsQueryRequest = {
  q?: string;
  status?: string;
  sort: "updated_at" | "title" | "status";
  order: "asc" | "desc";
  cursor?: string;
};

export class ApiTransportError extends Error {
  readonly status: number;
  readonly body: ApiErrorResponse | null;

  constructor(message: string, status: number, body: ApiErrorResponse | null) {
    super(message);
    this.name = "ApiTransportError";
    this.status = status;
    this.body = body;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function parseApiErrorBody(text: string): ApiErrorResponse | null {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as ApiErrorResponse;
  } catch {
    return null;
  }
}

function parseErrorBody(text: string): ApiErrorResponse | null {
  return parseApiErrorBody(text);
}

async function apiFetch(
  path: string,
  init: RequestInit & { csrf?: boolean } = {},
): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  if (init.csrf) {
    const csrf = readCookie(CSRF_COOKIE);
    if (!csrf) {
      throw new ApiTransportError("csrf cookie missing", 403, null);
    }
    headers.set(CSRF_HEADER, csrf);
  }
  // Browser SPA never emits Authorization — cookie session only.
  headers.delete("Authorization");

  return fetch(`${API_PREFIX}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
}

async function expectJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) {
    throw new ApiTransportError(
      `HTTP ${response.status}`,
      response.status,
      parseErrorBody(text),
    );
  }
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

export async function bootstrapCsrf(): Promise<void> {
  const response = await apiFetch("/auth/csrf", { method: "GET" });
  if (response.status !== 204) {
    const text = await response.text();
    throw new ApiTransportError(
      `csrf bootstrap failed (${response.status})`,
      response.status,
      parseErrorBody(text),
    );
  }
}

export async function loginBrowser(credentials: LoginRequest): Promise<void> {
  await bootstrapCsrf();
  const response = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
    csrf: true,
  });
  if (response.status !== 204) {
    const text = await response.text();
    throw new ApiTransportError(
      `login failed (${response.status})`,
      response.status,
      parseErrorBody(text),
    );
  }
}

export async function fetchMe(): Promise<MeResponse> {
  const response = await apiFetch("/auth/me", { method: "GET" });
  return expectJson<MeResponse>(response);
}

export async function changePasswordBrowser(newPassword: string): Promise<void> {
  await bootstrapCsrf();
  const response = await apiFetch("/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_password: newPassword }),
    csrf: true,
  });
  if (response.status !== 204) {
    const text = await response.text();
    throw new ApiTransportError(
      `change-password failed (${response.status})`,
      response.status,
      parseErrorBody(text),
    );
  }
}

export async function logoutBrowser(): Promise<void> {
  const response = await apiFetch("/auth/logout", { method: "POST", csrf: true });
  if (response.status !== 204) {
    const text = await response.text();
    throw new ApiTransportError(
      `logout failed (${response.status})`,
      response.status,
      parseErrorBody(text),
    );
  }
}

export async function fetchConnection(): Promise<ConnectionResponse> {
  const response = await apiFetch("/session/connection", { method: "GET" });
  return expectJson<ConnectionResponse>(response);
}

export async function fetchBootstrap(): Promise<BootstrapResponse> {
  const response = await apiFetch("/session/bootstrap", { method: "GET" });
  return expectJson<BootstrapResponse>(response);
}

export async function fetchDocumentsQuery(
  params: DocumentsQueryRequest,
): Promise<DocumentQueryPageResponse> {
  const search = new URLSearchParams();
  if (params.q) {
    search.set("q", params.q);
  }
  if (params.status) {
    search.set("status", params.status);
  }
  search.set("sort", params.sort);
  search.set("order", params.order);
  if (params.cursor) {
    search.set("cursor", params.cursor);
  }
  const qs = search.toString();
  const response = await apiFetch(`/documents/query?${qs}`, { method: "GET" });
  return expectJson<DocumentQueryPageResponse>(response);
}

export async function probeHealth(): Promise<boolean> {
  try {
    await fetchConnection();
    return true;
  } catch {
    return false;
  }
}

export function apiBasePrefix(): string {
  return API_PREFIX;
}

/** CSRF-protected mutation transport; caller supplies a validated relative path. */
export async function mutationFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return apiFetch(path, { ...init, csrf: true });
}

/** Test hook: ensure fetch adapter never sets Authorization. */
export function __buildAuthHeadersForTest(csrf: boolean): Headers {
  const headers = new Headers();
  if (csrf) {
    const token = readCookie(CSRF_COOKIE);
    if (token) {
      headers.set(CSRF_HEADER, token);
    }
  }
  headers.delete("Authorization");
  return headers;
}
