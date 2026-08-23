/** Thin re-exports from OpenAPI-generated types (`npm run generate:types`). */
import type { components } from "./openapi";

export type MeResponse = components["schemas"]["MeResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type ApiErrorDetail = components["schemas"]["ErrorDetail"];
export type ApiErrorResponse = components["schemas"]["ErrorResponse"];

/** SPA-local shell state (not part of the HTTP contract). */
export type ConnectionState = "unknown" | "online" | "offline";

export type AuthState =
  | { status: "anonymous" }
  | { status: "authenticated"; user: MeResponse }
  | { status: "password_change_required"; username: string };
