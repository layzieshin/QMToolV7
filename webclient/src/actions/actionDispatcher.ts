import type { DispatchActionInput, DispatchActionResult } from "./actionTypes";

export async function dispatchAction(input: DispatchActionInput): Promise<DispatchActionResult> {
  const { descriptor, handlers, confirmed = false, reason } = input;

  if (!descriptor.enabled) {
    return {
      status: "disabled",
      disabledReason: descriptor.disabled_reason ?? null,
    };
  }

  const handler = handlers.get(descriptor.code);
  if (!handler) {
    return { status: "unsupported" };
  }

  if (descriptor.requires_confirmation && !confirmed) {
    return { status: "confirmation_required" };
  }

  const trimmedReason = reason?.trim();
  if (descriptor.requires_reason && !trimmedReason) {
    return { status: "reason_required" };
  }

  const value = await handler({
    descriptor,
    confirmed,
    reason,
  });
  return { status: "executed", value };
}

export type {
  ActionDescriptor,
  ActionHandler,
  ActionHandlerContext,
  ActionHandlerRegistry,
  DispatchActionInput,
  DispatchActionResult,
} from "./actionTypes";
export {
  actionButtonColor,
  createHandlerRegistry,
  isActionInteractive,
  resolveActionAccessibleTitle,
  resolveActionLabel,
} from "./actionTypes";
