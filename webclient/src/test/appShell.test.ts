import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AppShell from "../components/AppShell.vue";
import { i18n } from "../i18n";
import { __resetAppShellStateForTest } from "../state/appShell";

const { fetchMe, logoutBrowser } = vi.hoisted(() => ({
  fetchMe: vi.fn(),
  logoutBrowser: vi.fn(async () => undefined),
}));

const authenticatedUser = {
    user_id: "u1",
    session_id: "s1",
    request_id: "r1",
    organization_id: "org",
    username: "bob",
    global_roles: ["USER"],
    is_qmb: false,
    authenticated_at: "2026-01-01T00:00:00Z",
};

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    probeHealth: vi.fn(async () => true),
    fetchMe,
    loginBrowser: vi.fn(async () => undefined),
    logoutBrowser,
    bootstrapCsrf: vi.fn(async () => undefined),
  };
});

async function mountShell() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/login", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  await router.isReady();
  const wrapper = mount(AppShell, {
    slots: { default: "<p>content</p>" },
    global: {
      plugins: [i18n, router],
      components: {
        VBtn: { template: '<button v-bind="$attrs"><slot /></button>' },
      },
    },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("AppShell", () => {
  beforeEach(() => {
    __resetAppShellStateForTest();
    fetchMe.mockReset();
    logoutBrowser.mockClear();
  });

  it("renders connection and auth state with german labels", async () => {
    fetchMe.mockResolvedValue(authenticatedUser);
    const { wrapper } = await mountShell();
    await vi.waitFor(() => {
      expect(wrapper.get("[data-testid=connection-state]").text()).toBe("Verbunden");
    });
    expect(wrapper.get("[data-testid=auth-state]").text()).toContain("bob");
    expect(wrapper.get("main.app-shell__main").text()).toBeDefined();
    expect(wrapper.text()).toContain("content");
  });

  it("keeps logout in the persistent authenticated shell and routes fail-closed to login", async () => {
    fetchMe.mockResolvedValue(authenticatedUser);
    const { wrapper, router } = await mountShell();

    await vi.waitFor(() => {
      expect(wrapper.get("[data-testid=shell-logout]").text()).toBe("Abmelden");
    });
    await wrapper.get("[data-testid=shell-logout]").trigger("click");
    await flushPromises();

    expect(logoutBrowser).toHaveBeenCalledTimes(1);
    expect(router.currentRoute.value.path).toBe("/login");
    expect(wrapper.find("[data-testid=shell-logout]").exists()).toBe(false);
  });

  it("does not render logout for an anonymous shell", async () => {
    fetchMe.mockRejectedValue(new Error("offline"));
    const { wrapper } = await mountShell();

    expect(wrapper.find("[data-testid=authenticated-panel]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=shell-logout]").exists()).toBe(false);
  });
});
