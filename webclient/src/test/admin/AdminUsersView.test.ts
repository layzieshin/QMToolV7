import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  const { register } = require("node:module") as typeof import("node:module");
  const { mkdtempSync, writeFileSync } = require("node:fs") as typeof import("node:fs");
  const { tmpdir } = require("node:os") as typeof import("node:os");
  const { join } = require("node:path") as typeof import("node:path");
  const { pathToFileURL } = require("node:url") as typeof import("node:url");

  const loaderDir = mkdtempSync(join(tmpdir(), "vitest-css-stub-"));
  const loaderPath = join(loaderDir, "css-stub-loader.mjs");
  writeFileSync(
    loaderPath,
    `export async function load(url, context, nextLoad) {
  if (url.endsWith(".css")) {
    return { format: "module", shortCircuit: true, source: "export default {}\\n" };
  }
  return nextLoad(url, context);
}
`,
  );
  register(pathToFileURL(loaderPath), pathToFileURL(join(process.cwd(), "package.json")));
});

import { ApiTransportError } from "../../api/client";
import ModuleNavigation from "../../components/ModuleNavigation.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import { routes } from "../../router/routes";
import {
  __resetBootstrapStateForTest,
  __setBootstrapModulesForTest,
} from "../../state/bootstrap";
import AdminUsersView from "../../views/admin/AdminUsersView.vue";

const fetchAdminUsersMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchAdminUsers: fetchAdminUsersMock,
  };
});

function sampleUsers() {
  return [
    {
      user_id: "u-admin",
      username: "admin",
      role: "Admin",
      is_active: true,
      is_qmb: true,
      must_change_password: false,
    },
    {
      user_id: "u-qmb",
      username: "qmb-user",
      role: "QMB",
      is_active: true,
      is_qmb: true,
      must_change_password: false,
    },
    {
      user_id: "u-inactive",
      username: "inactive-user",
      role: "User",
      is_active: false,
      is_qmb: false,
      must_change_password: true,
    },
  ];
}

function stubBrowserApis(): void {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
}

async function mountUsersView(path = "/admin/users") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  });
  await router.push(path);
  await router.isReady();

  const wrapper = mount(AdminUsersView, {
    global: {
      plugins: [router, vuetify, i18n],
    },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("AdminUsersView", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    fetchAdminUsersMock.mockReset();
    stubBrowserApis();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads active and inactive users via fetchAdminUsers adapter", async () => {
    fetchAdminUsersMock.mockResolvedValueOnce(sampleUsers());
    const { wrapper } = await mountUsersView();

    expect(fetchAdminUsersMock).toHaveBeenCalledTimes(1);
    expect(wrapper.find("[data-testid=admin-users-loading]").exists()).toBe(false);
    const rows = wrapper.findAll("[data-testid=admin-users-row]");
    expect(rows).toHaveLength(3);
    expect(wrapper.text()).toContain("inactive-user");
    expect(wrapper.text()).toContain("Änderung erforderlich");
    expect(wrapper.text()).toContain("Administrator");
    expect(wrapper.text()).toContain("QMB");
    expect(wrapper.text()).not.toMatch(/\bUser\b/);
    wrapper.unmount();
  });

  it("shows empty state when list is empty", async () => {
    fetchAdminUsersMock.mockResolvedValueOnce([]);
    const { wrapper } = await mountUsersView();

    expect(wrapper.get("[data-testid=admin-users-empty]").text()).toContain(
      "Keine Benutzerkonten vorhanden.",
    );
    wrapper.unmount();
  });

  it("shows forbidden state with home back path on 403", async () => {
    fetchAdminUsersMock.mockRejectedValueOnce(
      new ApiTransportError("forbidden", 403, {
        detail: { error: "forbidden", message: "forbidden" },
      }),
    );
    const { wrapper } = await mountUsersView();

    expect(wrapper.get("[data-testid=admin-users-error]").text()).toContain(
      "nicht berechtigt",
    );
    expect(wrapper.get("[data-testid=admin-users-back-home]").attributes("href")).toBe("/");
    wrapper.unmount();
  });

  it("shows load error on network failure", async () => {
    fetchAdminUsersMock.mockRejectedValueOnce(new Error("offline"));
    const { wrapper } = await mountUsersView();

    expect(wrapper.get("[data-testid=admin-users-error]").text()).toContain(
      "konnte nicht geladen werden",
    );
    wrapper.unmount();
  });

  it("renders semantic RouterLink href for detail navigation", async () => {
    fetchAdminUsersMock.mockResolvedValueOnce(sampleUsers());
    const { wrapper } = await mountUsersView();

    const link = wrapper.get("[data-testid=admin-users-row-link]");
    expect(link.attributes("href")).toBe("/admin/users/admin");
    wrapper.unmount();
  });
});

describe("ModuleNavigation admin capability", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    __resetBootstrapStateForTest();
  });

  it("shows admin users link only with usermanagement.can_administer_users", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        ...routes,
        {
          path: "/documents",
          name: "documents",
          component: { template: "<div />" },
        },
      ],
    });
    await router.push("/");
    await router.isReady();

    __setBootstrapModulesForTest([
      {
        id: "documents",
        licensed: true,
        authorized: true,
        capabilities: ["documents.read"],
      },
      {
        id: "usermanagement",
        licensed: true,
        authorized: true,
        capabilities: [
          "auth.authenticate",
          "auth.session.read",
          "usermanagement.can_administer_users",
        ],
      },
    ]);

    const wrapper = mount(ModuleNavigation, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();

    expect(wrapper.get("[data-testid=admin-navigation-users]").text()).toBe("Benutzer");
    wrapper.unmount();
  });

  it("hides admin users link without capability even when usermanagement is authorized", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", name: "home", component: { template: "<div />" } }],
    });

    __setBootstrapModulesForTest([
      {
        id: "usermanagement",
        licensed: true,
        authorized: true,
        capabilities: ["auth.authenticate", "auth.session.read"],
      },
    ]);

    const wrapper = mount(ModuleNavigation, {
      global: { plugins: [router, vuetify, i18n] },
    });
    await flushPromises();

    expect(wrapper.find("[data-testid=admin-navigation]").exists()).toBe(false);
    wrapper.unmount();
  });
});
