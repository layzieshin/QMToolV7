import type { LocationQueryValue } from "vue-router";

export const RETURN_URL_QUERY = "returnUrl";

const AUTH_LOOP_PATHS = new Set(["/login", "/change-password"]);

const SECRET_QUERY_PATTERN =
  /(?:^|[?&])(?:password|token|secret|bearer|csrf|session|authorization)=/i;

function normalizePath(path: string): string {
  if (path.length > 1 && path.endsWith("/")) {
    return path.slice(0, -1);
  }
  return path;
}

export function sanitizeReturnUrl(raw: string | null | undefined): string {
  if (!raw || typeof raw !== "string") {
    return "/";
  }

  const trimmed = raw.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return "/";
  }
  if (trimmed.includes("://")) {
    return "/";
  }
  if (SECRET_QUERY_PATTERN.test(trimmed)) {
    return "/";
  }

  const pathOnly = normalizePath(trimmed.split("?")[0]?.split("#")[0] ?? "/");
  if (AUTH_LOOP_PATHS.has(pathOnly)) {
    return "/";
  }

  return trimmed;
}

export function readReturnUrlQuery(
  value: LocationQueryValue | LocationQueryValue[] | undefined,
): string | null {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : null;
  }
  return typeof value === "string" ? value : null;
}

export function buildLoginLocation(returnTarget: string): {
  path: string;
  query?: Record<string, string>;
} {
  const sanitized = sanitizeReturnUrl(returnTarget);
  if (sanitized === "/") {
    return { path: "/login" };
  }
  return {
    path: "/login",
    query: { [RETURN_URL_QUERY]: sanitized },
  };
}

export function buildChangePasswordLocation(returnTarget?: string | null): {
  path: string;
  query?: Record<string, string>;
} {
  const sanitized = sanitizeReturnUrl(returnTarget ?? "/");
  if (sanitized === "/") {
    return { path: "/change-password" };
  }
  return {
    path: "/change-password",
    query: { [RETURN_URL_QUERY]: sanitized },
  };
}
