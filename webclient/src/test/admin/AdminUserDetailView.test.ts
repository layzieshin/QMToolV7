import { flushPromises, mount } from "@vue/test-utils";
import { nextTick } from "vue";
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
import { MutationClientError } from "../../api/mutationClient";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";
import AdminUserDetailView from "../../views/admin/AdminUserDetailView.vue";

const fetchAdminUserMock = vi.hoisted(() => vi.fn());
const mutateMock = vi.hoisted(() => vi.fn());
const bootstrapState = vi.hoisted(() => ({ writesAllowed: true }));

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchAdminUser: fetchAdminUserMock,
  };
});

vi.mock("../../api/mutationClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/mutationClient")>();
  return {
    ...actual,
    mutate: mutateMock,
  };
});

vi.mock("../../state/bootstrap", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../state/bootstrap")>();
  return {
    ...actual,
    useBootstrapState: () => bootstrapState,
  };
});

const detailTestRoutes = [
  {
    path: "/admin/users/:username",
    name: "admin-user-detail",
    component: AdminUserDetailView,
  },
  {
    path: "/admin/users",
    name: "admin-users",
    component: { template: "<div data-testid='admin-users-stub' />" },
  },
];

function bobUser(overrides: Record<string, unknown> = {}) {
  return {
    user_id: "u-bob",
    username: "bob",
    role: "User",
    is_active: true,
    is_qmb: false,
    must_change_password: true,
    ...overrides,
  };
}

function stubBrowserApis(): void {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
}

const RouterHost = {
  template: "<router-view />",
};

async function mountDetail(username = "bob") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: detailTestRoutes,
  });
  await router.push(`/admin/users/${encodeURIComponent(username)}`);
  await router.isReady();

  const wrapper = mount(RouterHost, {
    global: {
      plugins: [router, vuetify, i18n],
    },
    attachTo: document.body,
  });
  await flushPromises();
  return { wrapper, router };
}

async function makeAccessDirty(wrapper: ReturnType<typeof mount>): Promise<void> {
  await wrapper.get('[data-testid="admin-user-edit-active"] label').trigger("click");
  await flushPromises();
}

async function clickDiscardButton(testId: string): Promise<void> {
  const button = document.body.querySelector(`[data-testid=${testId}]`) as HTMLElement | null;
  expect(button).not.toBeNull();
  button!.click();
  await flushPromises();
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("AdminUserDetailView", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    fetchAdminUserMock.mockReset();
    mutateMock.mockReset();
    bootstrapState.writesAllowed = true;
    stubBrowserApis();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders read mode with must_change_password and localized role", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    const { wrapper } = await mountDetail();

    expect(fetchAdminUserMock).toHaveBeenCalledWith("bob");
    expect(wrapper.get("[data-testid=admin-user-must-change]").text()).toContain("Ja");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Benutzer");
    wrapper.unmount();
  });

  it("shows localized QMB role and preserves is_qmb in edit save", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(
      bobUser({ role: "QMB", is_qmb: true, must_change_password: false }),
    );
    mutateMock.mockResolvedValueOnce(
      bobUser({ role: "QMB", is_qmb: true, must_change_password: false, is_active: false }),
    );

    const { wrapper } = await mountDetail();
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("QMB");

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith({
      method: "PATCH",
      path: "/users/bob/access",
      body: {
        json: {
          role: "QMB",
          is_active: true,
          is_qmb: true,
        },
      },
    });
    wrapper.unmount();
  });

  it("shows not-found state on 404", async () => {
    fetchAdminUserMock.mockRejectedValueOnce(
      new ApiTransportError("not found", 404, {
        detail: { error: "user_not_found", message: "user not found" },
      }),
    );
    const { wrapper } = await mountDetail("missing");

    expect(wrapper.get("[data-testid=admin-user-error]").text()).toContain("nicht gefunden");
    wrapper.unmount();
  });

  it("shows forbidden state on 403 without role interpretation", async () => {
    fetchAdminUserMock.mockRejectedValueOnce(
      new ApiTransportError("forbidden", 403, {
        detail: { error: "forbidden", message: "forbidden" },
      }),
    );
    const { wrapper } = await mountDetail();

    expect(wrapper.get("[data-testid=admin-user-error]").text()).toContain("nicht berechtigt");
    wrapper.unmount();
  });

  it("URL-encodes username with slash question mark and unicode on read and mutation", async () => {
    const encodedUsername = "a/b?ü";
    fetchAdminUserMock.mockResolvedValueOnce(
      bobUser({ username: encodedUsername, user_id: "u-encoded" }),
    );
    mutateMock.mockResolvedValueOnce(
      bobUser({ username: encodedUsername, user_id: "u-encoded", is_active: false }),
    );

    const { wrapper } = await mountDetail(encodedUsername);
    expect(fetchAdminUserMock).toHaveBeenCalledWith(encodedUsername);

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith({
      method: "PATCH",
      path: `/users/${encodeURIComponent(encodedUsername)}/access`,
      body: {
        json: {
          role: "User",
          is_active: true,
          is_qmb: false,
        },
      },
    });
    wrapper.unmount();
  });

  it("maps last_active_admin to dedicated German message", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    mutateMock.mockRejectedValueOnce(
      new MutationClientError("conflict", "conflict", 409, {
        errorCode: "last_active_admin",
        body: {
          detail: { error: "last_active_admin", message: "cannot remove the last active admin" },
        },
      }),
    );

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.get("[data-testid=admin-user-access-error]").text()).toContain(
      "letzte aktive Administrator",
    );
    wrapper.unmount();
  });

  it("shows access field errors field-near", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    mutateMock.mockRejectedValueOnce(
      new MutationClientError("invalid", "transport", 400, {
        fieldErrors: [
          { field: "role", message: "Rolle ungültig", code: "invalid_role" },
          { field: "is_active", message: "Aktiv ungültig", code: "invalid_active" },
          { field: "is_qmb", message: "QMB ungültig", code: "invalid_qmb" },
        ],
        body: {
          detail: {
            error: "invalid_user_update",
            message: "invalid",
            field_errors: [
              { field: "role", message: "Rolle ungültig", code: "invalid_role" },
              { field: "is_active", message: "Aktiv ungültig", code: "invalid_active" },
              { field: "is_qmb", message: "QMB ungültig", code: "invalid_qmb" },
            ],
          },
        },
      }),
    );

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.get("[data-testid=admin-user-edit-role]").text()).toContain("Rolle ungültig");
    expect(wrapper.get("[data-testid=admin-user-edit-active]").text()).toContain("Aktiv ungültig");
    expect(wrapper.get("[data-testid=admin-user-edit-qmb]").text()).toContain("QMB ungültig");
    wrapper.unmount();
  });

  it("disables writes when writesAllowed is false", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    bootstrapState.writesAllowed = false;

    const { wrapper } = await mountDetail();
    expect(wrapper.get("[data-testid=admin-user-edit-start]").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid=admin-user-password-submit]").attributes("disabled")).toBeDefined();
    expect(wrapper.find("[data-testid=admin-user-writes-disabled]").exists()).toBe(true);
    wrapper.unmount();
  });

  it("allows writes when writesAllowed is true", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    bootstrapState.writesAllowed = true;

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    expect(wrapper.get("[data-testid=admin-user-edit-save]").attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });

  it("shows dirty hint and discard dialog on cancel with unsaved changes", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    const { wrapper } = await mountDetail();

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await makeAccessDirty(wrapper);


    expect(wrapper.find("[data-testid=admin-user-dirty-hint]").exists()).toBe(true);

    await wrapper.get("[data-testid=admin-user-edit-cancel]").trigger("click");
    await flushPromises();
    expect(document.body.querySelector("[data-testid=admin-user-discard-dialog]")).not.toBeNull();

    await clickDiscardButton("admin-user-discard-keep");
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(true);
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(true);

    await wrapper.get("[data-testid=admin-user-edit-cancel]").trigger("click");
    await flushPromises();
    await clickDiscardButton("admin-user-discard-confirm");
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("clears dirty state after successful access save without discard dialog", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    mutateMock.mockResolvedValueOnce(bobUser({ is_active: false }));

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await makeAccessDirty(wrapper);
    await wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=admin-user-dirty-hint]").exists()).toBe(false);
    expect(document.body.querySelector("[data-testid=admin-user-discard-dialog]")).toBeNull();
    wrapper.unmount();
  });

  it("cancels edit immediately when not dirty", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    const { wrapper } = await mountDetail();

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid=admin-user-edit-cancel]").trigger("click");
    await flushPromises();

    expect(wrapper.find("[data-testid=admin-user-discard-dialog]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("blocks route leave and route update while dirty, then allows after discard", async () => {
    fetchAdminUserMock
      .mockResolvedValueOnce(bobUser())
      .mockResolvedValueOnce(bobUser({ username: "carol", user_id: "u-carol" }));
    const { wrapper, router } = await mountDetail("bob");

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await makeAccessDirty(wrapper);

    const leaveNavigation = router.push({ name: "admin-users" });
    await flushPromises();
    await nextTick();
    expect(router.currentRoute.value.params.username).toBe("bob");
    expect(document.body.querySelector('[data-testid="admin-user-discard-dialog"]')).not.toBeNull();

    await clickDiscardButton("admin-user-discard-confirm");
    await leaveNavigation;
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("admin-users");

    await router.push("/admin/users/bob");
    await flushPromises();
    fetchAdminUserMock.mockResolvedValueOnce(bobUser({ username: "carol", user_id: "u-carol" }));

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await makeAccessDirty(wrapper);

    void router.push("/admin/users/carol");
    await flushPromises();
    await nextTick();
    expect(router.currentRoute.value.params.username).toBe("bob");
    expect(fetchAdminUserMock).toHaveBeenCalledTimes(2);

    await wrapper.get("[data-testid=admin-user-edit-cancel]").trigger("click");
    await flushPromises();
    await clickDiscardButton("admin-user-discard-confirm");

    await router.push("/admin/users/carol");
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(fetchAdminUserMock).toHaveBeenCalledTimes(3);
    wrapper.unmount();
  });

  it("registers beforeunload while dirty and removes listener on unmount", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");

    const { wrapper } = await mountDetail();
    const beforeUnloadHandler = addSpy.mock.calls.find((call) => call[0] === "beforeunload")?.[1] as
      | ((event: BeforeUnloadEvent) => void)
      | undefined;
    expect(beforeUnloadHandler).toBeTypeOf("function");

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await makeAccessDirty(wrapper);

    const event = new Event("beforeunload") as BeforeUnloadEvent;
    beforeUnloadHandler?.(event);
    expect(event.returnValue === "" || event.returnValue === true).toBe(true);

    wrapper.unmount();
    expect(removeSpy).toHaveBeenCalledWith("beforeunload", beforeUnloadHandler);
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("clears password field and reloads detail exactly once after successful password action", async () => {
    fetchAdminUserMock
      .mockResolvedValueOnce(bobUser())
      .mockResolvedValueOnce(bobUser({ must_change_password: false }));
    mutateMock.mockResolvedValueOnce(undefined);

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=admin-user-password-input]").find("input").setValue("new-password-12");
    await wrapper.get("[data-testid=admin-user-password-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledWith({
      method: "POST",
      path: "/users/bob/password-actions",
      body: { json: { new_password: "new-password-12" } },
    });
    expect(fetchAdminUserMock).toHaveBeenCalledTimes(2);
    expect(wrapper.get("[data-testid=admin-user-password-input]").find("input").element.value).toBe("");
    wrapper.unmount();
  });

  it("ignores stale detail response after route changes to another user", async () => {
    const bobDeferred = deferred<ReturnType<typeof bobUser>>();
    const carolUser = bobUser({
      username: "carol",
      user_id: "u-carol",
      role: "Admin",
      must_change_password: false,
    });
    let bobFetchCount = 0;

    fetchAdminUserMock.mockImplementation((name: string) => {
      if (name === "bob") {
        bobFetchCount += 1;
        if (bobFetchCount === 1) {
          return bobDeferred.promise;
        }
        return Promise.resolve(bobUser());
      }
      if (name === "carol") {
        return Promise.resolve(carolUser);
      }
      return Promise.reject(new Error(`unexpected user ${name}`));
    });

    const router = createRouter({
      history: createMemoryHistory(),
      routes: detailTestRoutes,
    });
    await router.push("/admin/users/bob");
    await router.isReady();

    const wrapper = mount(RouterHost, {
      global: { plugins: [router, vuetify, i18n] },
      attachTo: document.body,
    });
    await nextTick();
    expect(bobFetchCount).toBe(1);

    await router.push("/admin/users/carol");
    await router.isReady();
    await flushPromises();
    await nextTick();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Administrator");

    bobDeferred.resolve(bobUser());
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Administrator");
    expect(wrapper.text()).not.toContain("u-bob");
    wrapper.unmount();
  });

  it("ignores stale password refresh when route changes before detail fetch completes", async () => {
    const refreshDeferred = deferred<ReturnType<typeof bobUser>>();
    const carolUser = bobUser({
      username: "carol",
      user_id: "u-carol",
      role: "Admin",
      must_change_password: false,
    });
    let bobFetchCount = 0;

    fetchAdminUserMock.mockImplementation((name: string) => {
      if (name === "bob") {
        bobFetchCount += 1;
        if (bobFetchCount === 1) {
          return Promise.resolve(bobUser());
        }
        if (bobFetchCount === 2) {
          return refreshDeferred.promise;
        }
        return Promise.resolve(bobUser());
      }
      if (name === "carol") {
        return Promise.resolve(carolUser);
      }
      return Promise.reject(new Error(`unexpected user ${name}`));
    });
    mutateMock.mockResolvedValueOnce(undefined);

    const { wrapper, router } = await mountDetail("bob");

    await wrapper.get("[data-testid=admin-user-password-input]").find("input").setValue("new-password-12");
    void wrapper.get("[data-testid=admin-user-password-card] form").trigger("submit.prevent");
    await flushPromises();

    await router.push("/admin/users/carol");
    await router.isReady();
    await flushPromises();
    await nextTick();

    refreshDeferred.resolve(bobUser({ must_change_password: false }));
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Administrator");
    expect(wrapper.text()).not.toContain("u-bob");
    wrapper.unmount();
  });

  it("ignores stale access save success after dirty discard navigates to another user", async () => {
    const patchDeferred = deferred<ReturnType<typeof bobUser>>();
    const carolUser = bobUser({
      username: "carol",
      user_id: "u-carol",
      role: "Admin",
      must_change_password: false,
    });

    fetchAdminUserMock
      .mockResolvedValueOnce(bobUser())
      .mockResolvedValueOnce(carolUser);
    mutateMock.mockImplementationOnce(() => patchDeferred.promise);

    const { wrapper, router } = await mountDetail("bob");
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    await makeAccessDirty(wrapper);

    void wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    const leaveNavigation = router.push({ name: "admin-users" });
    await flushPromises();
    await nextTick();
    expect(document.body.querySelector("[data-testid=admin-user-discard-dialog]")).not.toBeNull();

    await clickDiscardButton("admin-user-discard-confirm");
    await leaveNavigation;
    await flushPromises();

    await router.push("/admin/users/carol");
    await router.isReady();
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Administrator");

    patchDeferred.resolve(bobUser({ role: "Admin", is_active: false }));
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Administrator");
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=admin-user-access-error]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("ignores stale access save error after route changes to another user", async () => {
    const patchDeferred = deferred<never>();
    const carolUser = bobUser({
      username: "carol",
      user_id: "u-carol",
      role: "Admin",
      must_change_password: false,
    });

    fetchAdminUserMock.mockResolvedValueOnce(bobUser()).mockResolvedValueOnce(carolUser);
    mutateMock.mockImplementationOnce(() => patchDeferred.promise);

    const { wrapper, router } = await mountDetail("bob");
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();

    void wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    await router.push("/admin/users/carol");
    await router.isReady();
    await flushPromises();

    patchDeferred.reject(
      new MutationClientError("invalid", "transport", 400, {
        fieldErrors: [{ field: "role", message: "Rolle ungültig", code: "invalid_role" }],
        body: {
          detail: {
            error: "invalid_user_update",
            message: "invalid",
            field_errors: [{ field: "role", message: "Rolle ungültig", code: "invalid_role" }],
          },
        },
      }),
    );
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("Administrator");
    expect(wrapper.find("[data-testid=admin-user-access-error]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("does not let stale access save finally affect a newer access operation", async () => {
    const bobPatchDeferred = deferred<ReturnType<typeof bobUser>>();
    const carolPatchDeferred = deferred<ReturnType<typeof bobUser>>();
    const carolUser = bobUser({
      username: "carol",
      user_id: "u-carol",
      role: "QMB",
      is_qmb: true,
      must_change_password: false,
    });

    fetchAdminUserMock.mockResolvedValueOnce(bobUser()).mockResolvedValueOnce(carolUser);
    mutateMock
      .mockImplementationOnce(() => bobPatchDeferred.promise)
      .mockImplementationOnce(() => carolPatchDeferred.promise);

    const { wrapper, router } = await mountDetail("bob");
    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();

    void wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    await router.push("/admin/users/carol");
    await router.isReady();
    await flushPromises();

    await wrapper.get("[data-testid=admin-user-edit-start]").trigger("click");
    await flushPromises();
    void wrapper.get("[data-testid=admin-user-edit-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(mutateMock).toHaveBeenCalledTimes(2);
    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("QMB");
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(true);
    expect(wrapper.get("[data-testid=admin-user-edit-save]").classes()).toContain("v-btn--loading");
    expect(wrapper.get("[data-testid=admin-user-edit-cancel]").attributes("disabled")).toBeDefined();

    bobPatchDeferred.resolve(bobUser({ role: "Admin", is_active: false }));
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("QMB");
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(true);
    expect(wrapper.get("[data-testid=admin-user-edit-save]").classes()).toContain("v-btn--loading");
    expect(wrapper.get("[data-testid=admin-user-edit-cancel]").attributes("disabled")).toBeDefined();

    carolPatchDeferred.resolve(carolUser);
    await flushPromises();

    expect(router.currentRoute.value.params.username).toBe("carol");
    expect(wrapper.get("[data-testid=admin-user-role]").text()).toBe("QMB");
    expect(wrapper.find("[data-testid=admin-user-edit-card]").exists()).toBe(false);
    expect(wrapper.find("[data-testid=admin-user-edit-start]").exists()).toBe(true);
    wrapper.unmount();
  });

  it("maps new_password field errors on password action", async () => {
    fetchAdminUserMock.mockResolvedValueOnce(bobUser());
    mutateMock.mockRejectedValueOnce(
      new MutationClientError("weak", "transport", 400, {
        fieldErrors: [{ field: "new_password", message: "too short", code: "too_short" }],
        body: {
          detail: {
            error: "weak_password",
            message: "password does not meet policy",
            field_errors: [{ field: "new_password", message: "too short", code: "too_short" }],
          },
        },
      }),
    );

    const { wrapper } = await mountDetail();
    await wrapper.get("[data-testid=admin-user-password-input]").find("input").setValue("short");
    await wrapper.get("[data-testid=admin-user-password-card] form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.get("[data-testid=admin-user-password-error]").text()).toContain("Richtlinien");
    wrapper.unmount();
  });
});

describe("fetchAdminUser adapter encoding", () => {
  beforeEach(() => {
    stubBrowserApis();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests encoded username with credentials include via real client adapter", async () => {
    const encodedUsername = "a/b?ü";
    const payload = bobUser({ username: encodedUsername, user_id: "u-encoded" });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(payload),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { fetchAdminUser } = await vi.importActual<typeof import("../../api/client")>(
      "../../api/client",
    );
    const result = await fetchAdminUser(encodedUsername);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/users/a%2Fb%3F%C3%BC",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
      }),
    );
    expect(result.username).toBe(encodedUsername);
  });
});
