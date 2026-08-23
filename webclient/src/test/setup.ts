import { vi } from "vitest";

vi.stubGlobal(
  "fetch",
  vi.fn(async () => ({
    ok: true,
    status: 204,
    text: async () => "",
    json: async () => ({}),
  })),
);

const storageProto = Storage.prototype as Storage & {
  setItem: (key: string, value: string) => void;
};

const forbiddenKeys = ["token", "session", "qmtool_session", "authorization"];

function guardStorage(kind: "localStorage" | "sessionStorage"): void {
  const original = storageProto.setItem.bind(window[kind]);
  storageProto.setItem = function guardedSetItem(key: string, value: string) {
    const normalized = key.toLowerCase();
    if (forbiddenKeys.some((marker) => normalized.includes(marker))) {
      throw new Error(`${kind} must not persist session credentials (${key})`);
    }
    if (typeof value === "string" && /Bearer\s+/i.test(value)) {
      throw new Error(`${kind} must not persist bearer tokens`);
    }
    return original(key, value);
  };
}

guardStorage("localStorage");
guardStorage("sessionStorage");
