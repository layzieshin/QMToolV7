import { describe, expect, it, vi } from "vitest";

import { createHandlerRegistry, dispatchAction } from "../actions/actionDispatcher";
import type { ActionDescriptor, ActionHandlerRegistry } from "../actions/actionTypes";

function descriptor(overrides: Partial<ActionDescriptor> = {}): ActionDescriptor {
  return {
    code: "start",
    label_key: "documents.action.start",
    enabled: true,
    destructive: false,
    severity: "info",
    requires_confirmation: false,
    requires_reason: false,
    disabled_reason: null,
    signature_required: false,
    assignment_kind: null,
    ...overrides,
  };
}

describe("actionDispatcher", () => {
  it("executes a registered enabled handler exactly once", async () => {
    const handler = vi.fn(async () => "ok");
    const handlers = createHandlerRegistry({ start: handler });
    const inputDescriptor = descriptor();

    const result = await dispatchAction({
      descriptor: inputDescriptor,
      handlers,
    });

    expect(result).toEqual({ status: "executed", value: "ok" });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith({
      descriptor: inputDescriptor,
      confirmed: false,
      reason: undefined,
    });
  });

  it("never executes a disabled descriptor and preserves disabled_reason", async () => {
    const handler = vi.fn();
    const handlers = createHandlerRegistry({ start: handler });
    const inputDescriptor = descriptor({
      enabled: false,
      disabled_reason: "document is not visible to the current actor",
    });

    const result = await dispatchAction({
      descriptor: inputDescriptor,
      handlers,
    });

    expect(result).toEqual({
      status: "disabled",
      disabledReason: "document is not visible to the current actor",
    });
    expect(handler).not.toHaveBeenCalled();
  });

  it("returns unsupported for enabled descriptors without a registered handler", async () => {
    const handlers = createHandlerRegistry({});
    const result = await dispatchAction({
      descriptor: descriptor({ code: "archive" }),
      handlers,
    });

    expect(result).toEqual({ status: "unsupported" });
  });

  it("returns unsupported before confirmation or reason gates for unknown enabled codes", async () => {
    const handler = vi.fn();
    const handlers = createHandlerRegistry({});

    const result = await dispatchAction({
      descriptor: descriptor({
        code: "archive",
        requires_confirmation: true,
        requires_reason: true,
      }),
      handlers,
      confirmed: false,
      reason: "",
    });

    expect(result).toEqual({ status: "unsupported" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("requires explicit confirmation before execution", async () => {
    const handler = vi.fn();
    const handlers = createHandlerRegistry({ archive: handler });

    const withoutConfirmation = await dispatchAction({
      descriptor: descriptor({ code: "archive", requires_confirmation: true }),
      handlers,
    });
    expect(withoutConfirmation).toEqual({ status: "confirmation_required" });
    expect(handler).not.toHaveBeenCalled();

    const withConfirmation = await dispatchAction({
      descriptor: descriptor({ code: "archive", requires_confirmation: true }),
      handlers,
      confirmed: true,
    });
    expect(withConfirmation.status).toBe("executed");
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("requires a trimmed non-empty reason without interpreting it", async () => {
    const handler = vi.fn(async (context) => context.reason);
    const handlers = createHandlerRegistry({ review_reject: handler });
    const inputDescriptor = descriptor({
      code: "review_reject",
      requires_reason: true,
    });

    expect(
      await dispatchAction({
        descriptor: inputDescriptor,
        handlers,
      }),
    ).toEqual({ status: "reason_required" });

    expect(
      await dispatchAction({
        descriptor: inputDescriptor,
        handlers,
        reason: "   ",
      }),
    ).toEqual({ status: "reason_required" });

    const result = await dispatchAction({
      descriptor: inputDescriptor,
      handlers,
      reason: "  policy mismatch  ",
    });
    expect(result).toEqual({ status: "executed", value: "  policy mismatch  " });
    expect(handler).toHaveBeenCalledWith({
      descriptor: inputDescriptor,
      confirmed: false,
      reason: "  policy mismatch  ",
    });
  });

  it("preserves destructive metadata on the descriptor passed to handlers", async () => {
    const handler = vi.fn(async (context) => context.descriptor);
    const handlers = createHandlerRegistry({ abort: handler });
    const inputDescriptor = descriptor({
      code: "abort",
      destructive: true,
      severity: "danger",
      requires_confirmation: true,
    });

    const result = await dispatchAction({
      descriptor: inputDescriptor,
      handlers,
      confirmed: true,
    });

    expect(result.status).toBe("executed");
    expect(handler.mock.calls[0][0].descriptor).toEqual(inputDescriptor);
    expect(handler.mock.calls[0][0].descriptor.destructive).toBe(true);
    expect(handler.mock.calls[0][0].descriptor.severity).toBe("danger");
  });

  it("propagates handler rejections", async () => {
    const handlers = createHandlerRegistry({
      start: async () => {
        throw new Error("handler failed");
      },
    });

    await expect(
      dispatchAction({
        descriptor: descriptor(),
        handlers,
      }),
    ).rejects.toThrow("handler failed");
  });

  it("does not mutate handler registry or descriptor input", async () => {
    const handlersObject = { start: vi.fn(async () => undefined) };
    const handlers: ActionHandlerRegistry = createHandlerRegistry(handlersObject);
    const allowedActions: ActionDescriptor[] = [descriptor()];
    const snapshot = JSON.stringify(allowedActions);
    const registrySnapshot = JSON.stringify([...handlers.entries()]);

    await dispatchAction({
      descriptor: allowedActions[0],
      handlers,
      confirmed: true,
    });

    expect(JSON.stringify(allowedActions)).toBe(snapshot);
    expect(JSON.stringify([...handlers.entries()])).toBe(registrySnapshot);
    expect(Object.keys(handlersObject)).toEqual(["start"]);
  });

  it("does not inspect roles or derive permissions from action codes", async () => {
    const handler = vi.fn();
    const handlers = createHandlerRegistry({ approval_accept: handler });
    const inputDescriptor = descriptor({
      code: "approval_accept",
      label_key: "documents.action.approval_accept",
    });

    await dispatchAction({
      descriptor: inputDescriptor,
      handlers,
    });

    expect(handler).toHaveBeenCalledTimes(1);
    expect((handler.mock.calls[0][0] as { role?: string }).role).toBeUndefined();
  });
});
