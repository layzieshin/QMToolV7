import { flushPromises, mount } from "@vue/test-utils";
import { reactive } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardView from "../views/DashboardView.vue";
import { i18n } from "../i18n";
import { ApiTransportError, fetchDocumentHomeTasks } from "../api/client";
import { useBootstrapState } from "../state/bootstrap";
import { useAppShellState } from "../state/appShell";

vi.mock("../api/client", async (original) => ({ ...await original<typeof import("../api/client")>(), fetchDocumentHomeTasks: vi.fn() }));
vi.mock("../state/bootstrap", () => ({ useBootstrapState: vi.fn() }));
vi.mock("../state/appShell", () => ({ useAppShellState: vi.fn() }));

const request = vi.mocked(fetchDocumentHomeTasks);
const state = reactive({ modules: [{ id: "documents", licensed: true, authorized: true }] });
const shell = reactive({ auth: { status: "authenticated", user: { session_id: "synthetic-session" } } });

async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/", name: "home", component: DashboardView },
    { path: "/documents", name: "documents", component: { template: "<div/>" } },
    { path: "/documents/:docId", name: "document-detail", component: { template: "<div/>" } },
  ] });
  await router.push("/");
  return mount(DashboardView, { global: { plugins: [i18n, router], stubs: { VBtn: { template: '<button @click="$emit(\'click\')"><slot/></button>' } } } });
}
beforeEach(() => {
  request.mockReset().mockResolvedValue([]);
  state.modules[0].authorized = true;
  shell.auth.status = "authenticated";
  vi.mocked(useBootstrapState).mockReturnValue(state as unknown as ReturnType<typeof useBootstrapState>);
  vi.mocked(useAppShellState).mockReturnValue(shell as unknown as ReturnType<typeof useAppShellState>);
});
describe("Dashboard document tasks", () => {
  it("shows backend tasks and links to their precise document version", async () => {
    request.mockResolvedValue([{ document_id: "DOC/1", version: 2, title: "Synthetische SOP", status: "IN_REVIEW", workflow_active: true }]);
    const wrapper = await render(); await flushPromises();
    expect(wrapper.get('[data-testid="dashboard-task"]').attributes("href")).toBe("/documents/DOC%2F1?version=2");
    expect(wrapper.text()).toContain("Synthetische SOP");
    wrapper.unmount();
  });
  it("distinguishes loading and empty results", async () => {
    let resolve!: (rows: []) => void;
    request.mockReturnValue(new Promise(done => { resolve = done; }));
    const wrapper = await render();
    expect(wrapper.text()).toContain("werden geladen");
    expect(wrapper.find('[data-testid="dashboard-empty"]').exists()).toBe(false);
    resolve([]); await flushPromises();
    expect(wrapper.get('[data-testid="dashboard-empty"]').text()).toContain("Keine offenen");
    wrapper.unmount();
  });
  it("shows forbidden errors instead of claiming an empty inbox", async () => {
    request.mockRejectedValue(new ApiTransportError("forbidden", 403, null));
    const wrapper = await render(); await flushPromises();
    expect(wrapper.find('[data-testid="dashboard-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="dashboard-empty"]').exists()).toBe(false);
    wrapper.unmount();
  });
  it("does not request tasks for an unavailable module", async () => {
    state.modules[0].authorized = false;
    const wrapper = await render(); await flushPromises();
    expect(request).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="dashboard-documents"]').exists()).toBe(false);
    wrapper.unmount();
  });
  it("discards in-flight tasks when the authenticated session disappears", async () => {
    let resolve!: (rows: Awaited<ReturnType<typeof fetchDocumentHomeTasks>>) => void;
    request.mockReturnValue(new Promise(done => { resolve = done; }));
    const wrapper = await render();
    shell.auth.status = "anonymous"; await flushPromises();
    resolve([{ document_id: "private", version: 1, title: "Must not appear", status: "DRAFT", workflow_active: false }]);
    await flushPromises();
    expect(wrapper.text()).not.toContain("Must not appear");
    wrapper.unmount();
  });
});
