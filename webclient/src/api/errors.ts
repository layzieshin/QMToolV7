import type { ApiErrorDetail, ApiErrorResponse, ApiFieldError } from "./types";

export type MutationErrorKind =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "precondition_required"
  | "transport";

export class MutationValidationError extends Error {
  readonly code: "invalid_path" | "invalid_if_match" | "invalid_body";

  constructor(message: string, code: "invalid_path" | "invalid_if_match" | "invalid_body") {
    super(message);
    this.name = "MutationValidationError";
    this.code = code;
  }
}

export class MutationClientError extends Error {
  readonly kind: MutationErrorKind;
  readonly status: number;
  readonly errorCode: string | null;
  readonly fieldErrors: readonly ApiFieldError[];
  readonly requestId: string | null;
  readonly currentEtag: string | null;
  readonly body: ApiErrorResponse | null;

  constructor(
    message: string,
    kind: MutationErrorKind,
    status: number,
    options: {
      errorCode?: string | null;
      fieldErrors?: readonly ApiFieldError[];
      requestId?: string | null;
      currentEtag?: string | null;
      body?: ApiErrorResponse | null;
    } = {},
  ) {
    super(message);
    this.name = "MutationClientError";
    this.kind = kind;
    this.status = status;
    this.errorCode = options.errorCode ?? null;
    this.fieldErrors = options.fieldErrors ?? [];
    this.requestId = options.requestId ?? null;
    this.currentEtag = options.currentEtag ?? null;
    this.body = options.body ?? null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function extractErrorDetail(body: ApiErrorResponse | null): ApiErrorDetail | null {
  const detail = body?.detail;
  if (!detail) {
    return null;
  }
  if (Array.isArray(detail)) {
    return null;
  }
  if (!isRecord(detail)) {
    return null;
  }
  if (typeof detail.error !== "string" || typeof detail.message !== "string") {
    return null;
  }
  return detail as ApiErrorDetail;
}

export function classifyMutationStatus(status: number): MutationErrorKind {
  switch (status) {
    case 401:
      return "unauthorized";
    case 403:
      return "forbidden";
    case 404:
      return "not_found";
    case 409:
      return "conflict";
    case 428:
      return "precondition_required";
    default:
      return "transport";
  }
}

export function mutationErrorI18nKey(kind: MutationErrorKind): string {
  const keys: Record<MutationErrorKind, string> = {
    unauthorized: "api.errors.unauthorized",
    forbidden: "api.errors.forbidden",
    not_found: "api.errors.notFound",
    conflict: "api.errors.conflict",
    precondition_required: "api.errors.preconditionRequired",
    transport: "api.errors.transport",
  };
  return keys[kind];
}

export function buildMutationClientError(
  status: number,
  body: ApiErrorResponse | null,
  requestId: string | null = null,
): MutationClientError {
  const kind = classifyMutationStatus(status);
  const detail = extractErrorDetail(body);
  const message = detail?.message ?? `HTTP ${status}`;
  const fieldErrors = Array.isArray(detail?.field_errors) ? detail.field_errors : [];

  return new MutationClientError(message, kind, status, {
    errorCode: detail?.error ?? null,
    fieldErrors,
    requestId,
    currentEtag: detail?.current_etag ?? null,
    body,
  });
}
