import type { components } from "../api/openapi";

/** OpenAPI-owned action descriptor; no parallel client contract. */
export type ActionDescriptor = components["schemas"]["ActionDescriptorModel"];

export type ActionHandlerContext = {
  descriptor: ActionDescriptor;
  confirmed: boolean;
  reason?: string;
};

export type ActionHandler = (context: ActionHandlerContext) => Promise<unknown> | unknown;

export type ActionHandlerRegistry = ReadonlyMap<string, ActionHandler>;

export type DispatchActionInput = {
  descriptor: ActionDescriptor;
  handlers: ActionHandlerRegistry;
  confirmed?: boolean;
  reason?: string;
};

export type DispatchActionResult =
  | { status: "executed"; value: unknown }
  | { status: "disabled"; disabledReason: string | null }
  | { status: "unsupported" }
  | { status: "confirmation_required" }
  | { status: "reason_required" };

type TranslateFn = (key: string) => string;

export function createHandlerRegistry(
  handlers: Record<string, ActionHandler>,
): ActionHandlerRegistry {
  return new Map(Object.entries(handlers));
}

export function resolveActionLabel(
  descriptor: ActionDescriptor,
  t: TranslateFn,
  genericFallback: string,
): string {
  const key = descriptor.label_key?.trim();
  if (!key) {
    return genericFallback;
  }
  const translated = t(key);
  if (!translated || translated === key) {
    return genericFallback;
  }
  return translated;
}

export function resolveActionAccessibleTitle(
  descriptor: ActionDescriptor,
  t: TranslateFn,
  label: string,
  supported: boolean,
  productWritesAllowed = true,
  productWritesBlockedMessage?: string,
): string {
  if (!productWritesAllowed) {
    return productWritesBlockedMessage?.trim() || t("connection.degraded");
  }
  if (!descriptor.enabled) {
    return descriptor.disabled_reason?.trim() || t("actions.disabled");
  }
  if (!supported) {
    return t("actions.unsupported");
  }
  return label;
}

export function actionButtonColor(descriptor: ActionDescriptor): string {
  if (descriptor.destructive || descriptor.severity === "danger") {
    return "error";
  }
  if (descriptor.severity === "warning") {
    return "warning";
  }
  return "primary";
}

export function isActionInteractive(
  descriptor: ActionDescriptor,
  supported: boolean,
  productWritesAllowed = true,
): boolean {
  return productWritesAllowed && descriptor.enabled && supported;
}
