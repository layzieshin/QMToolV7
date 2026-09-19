import {
  mutationFetch,
  parseApiErrorBody,
  type DocumentVersionStateModel,
} from "./client";
import { MutationValidationError, buildMutationClientError, extractErrorDetail } from "./errors";
import type { MutationClientError } from "./errors";

export type MutationMethod = "POST" | "PUT" | "PATCH" | "DELETE";

export type MutationJsonBody = {
  json: unknown;
};

export type MutationRawBody = {
  raw: BodyInit;
  contentType: string;
};

export type MutationFormBody = {
  form: FormData;
};

export type MutationBody = MutationJsonBody | MutationRawBody | MutationFormBody;

export interface MutationRequest {
  method: MutationMethod;
  /** Relative route under `/api/v1`, must start with `/` and exclude the prefix. */
  path: string;
  body?: MutationBody;
  /** Optional concurrency token; blank values are rejected before fetch. */
  ifMatch?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDocumentVersionStateModel(value: unknown): value is DocumentVersionStateModel {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.document_id === "string" &&
    typeof value.version === "number" &&
    typeof value.status === "string"
  );
}

/** Typed access to conflict payload `current_state` (bare version state, not `VersionStateResponse`). */
export function mutationConflictCurrentState(
  error: MutationClientError,
): DocumentVersionStateModel | null {
  const detail = extractErrorDetail(error.body);
  const currentState = detail?.current_state;
  if (!currentState || !isDocumentVersionStateModel(currentState)) {
    return null;
  }
  return currentState;
}

/** Typed access to conflict payload `current_etag` (falls back to `MutationClientError.currentEtag`). */
export function mutationConflictCurrentEtag(error: MutationClientError): string | null {
  const fromError = error.currentEtag?.trim();
  if (fromError) {
    return fromError;
  }
  const detail = extractErrorDetail(error.body);
  const etag = detail?.current_etag;
  return typeof etag === "string" && etag.trim() ? etag.trim() : null;
}

function splitPathAndQuery(path: string): { pathname: string; query: string | undefined } {
  const queryIndex = path.indexOf("?");
  if (queryIndex === -1) {
    return { pathname: path, query: undefined };
  }
  return {
    pathname: path.slice(0, queryIndex),
    query: path.slice(queryIndex + 1),
  };
}

function decodePathSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    throw new MutationValidationError("mutation path contains invalid encoding", "invalid_path");
  }
}

function assertNoTraversalOrBackslashEscapes(pathname: string): void {
  if (pathname.includes("\\") || /%5c/i.test(pathname)) {
    throw new MutationValidationError("mutation path must not contain backslashes", "invalid_path");
  }
  if (/%2e%2e/i.test(pathname)) {
    throw new MutationValidationError("mutation path must not contain encoded dot segments", "invalid_path");
  }
  if (/(^|\/)\.\.(\/|$)/.test(pathname) || /(^|\/)\.(\/|$)/.test(pathname)) {
    throw new MutationValidationError("mutation path must not contain dot segments", "invalid_path");
  }

  for (const segment of pathname.split("/")) {
    if (!segment) {
      continue;
    }
    const decoded = decodePathSegment(segment);
    if (decoded.includes("\\")) {
      throw new MutationValidationError("mutation path must not contain backslashes", "invalid_path");
    }
    for (const inner of decoded.split(/[/\\]/)) {
      if (inner === "." || inner === "..") {
        throw new MutationValidationError("mutation path must not contain dot segments", "invalid_path");
      }
    }
  }
}

export function validateMutationPath(path: string): void {
  const { pathname } = splitPathAndQuery(path);

  if (!pathname.startsWith("/")) {
    throw new MutationValidationError("mutation path must start with /", "invalid_path");
  }
  if (pathname.startsWith("//")) {
    throw new MutationValidationError("mutation path must not be protocol-relative", "invalid_path");
  }
  if (pathname.includes("://")) {
    throw new MutationValidationError("mutation path must not be absolute", "invalid_path");
  }
  if (pathname.startsWith("/api/v1")) {
    throw new MutationValidationError("mutation path must not include API prefix", "invalid_path");
  }
  assertNoTraversalOrBackslashEscapes(pathname);
}

export function resolveIfMatchHeader(value?: string): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    throw new MutationValidationError("If-Match must not be blank", "invalid_if_match");
  }
  return trimmed;
}

function assertExclusiveBody(body: MutationBody): void {
  const keys = ["json", "raw", "form"].filter((key) => key in body);
  if (keys.length !== 1) {
    throw new MutationValidationError("mutation body modes are mutually exclusive", "invalid_body");
  }
}

function buildMutationInit(body?: MutationBody, ifMatch?: string): RequestInit {
  const headers = new Headers();
  const resolvedIfMatch = resolveIfMatchHeader(ifMatch);
  if (resolvedIfMatch) {
    headers.set("If-Match", resolvedIfMatch);
  }

  if (!body) {
    return { headers };
  }

  assertExclusiveBody(body);

  if ("json" in body) {
    headers.set("Content-Type", "application/json");
    return {
      headers,
      body: JSON.stringify(body.json),
    };
  }

  if ("raw" in body) {
    const contentType = body.contentType.trim();
    if (!contentType) {
      throw new MutationValidationError("raw body requires a content type", "invalid_body");
    }
    headers.set("Content-Type", contentType);
    return {
      headers,
      body: body.raw,
    };
  }

  return {
    headers,
    body: body.form,
  };
}

async function parseMutationSuccess<T>(response: Response): Promise<T | undefined> {
  if (response.status === 204) {
    return undefined;
  }
  const text = await response.text();
  if (!text) {
    return undefined;
  }
  return JSON.parse(text) as T;
}

export async function mutate<TResponse = unknown>(
  request: MutationRequest,
): Promise<TResponse | undefined> {
  validateMutationPath(request.path);
  const init = buildMutationInit(request.body, request.ifMatch);

  const response = await mutationFetch(request.path, {
    method: request.method,
    ...init,
  });

  if (response.ok) {
    return parseMutationSuccess<TResponse>(response);
  }

  const text = await response.text();
  const body = parseApiErrorBody(text);
  const requestId = response.headers.get("X-Request-ID");
  throw buildMutationClientError(response.status, body, requestId);
}

export {
  MutationClientError,
  MutationValidationError,
  buildMutationClientError,
  classifyMutationStatus,
  extractErrorDetail,
  mutationErrorI18nKey,
} from "./errors";
export type { MutationErrorKind } from "./errors";
