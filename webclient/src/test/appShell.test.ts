import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import AppShell from "../components/AppShell.vue";
import { i18n } from "../i18n";
import { __resetAppShellStateForTest } from "../state/appShell";

vi.mock("../api/client", () => ({
  probeHealth: vi.fn(async () => true),
  fetchMe: vi.fn(async () => ({
    user_id: "u1",
    session_id: "s1",
    request_id: "r1",
    organization_id: "org",
    username: "bob",
    global_roles: ["USER"],
    is_qmb: false,
    authenticated_at: "2026-01-01T00:00:00Z",
  })),
  loginBrowser: vi.fn(async () => undefined),
  logoutBrowser: vi.fn(async () => undefined),
  bootstrapCsrf: vi.fn(async () => undefined),
}));

describe("AppShell", () => {
  it("renders connection and auth state with german labels", async () => {
    __resetAppShellStateForTest();
    const wrapper = mount(AppShell, {
      slots: { default: "<p>content</p>" },
      global: {
        plugins: [i18n],
      },
    });
    await vi.waitFor(() => {
      expect(wrapper.get("[data-testid=connection-state]").text()).toBe("Verbunden");
    });
    expect(wrapper.get("[data-testid=auth-state]").text()).toContain("bob");
    expect(wrapper.get("main.app-shell__main").text()).toBeDefined();
    expect(wrapper.text()).toContain("content");
  });
});
