import { flushPromises, mount } from "@vue/test-utils";
import { reactive } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReleasedDocumentsView from "../../views/documents/ReleasedDocumentsView.vue";
import { i18n } from "../../i18n";
import { ApiTransportError, fetchReleasedDocuments } from "../../api/client";
import { useBootstrapState } from "../../state/bootstrap";
import { useAppShellState } from "../../state/appShell";
vi.mock("../../api/client", async (original) => ({ ...await original<typeof import("../../api/client")>(), fetchReleasedDocuments: vi.fn() }));
vi.mock("../../state/bootstrap", () => ({ useBootstrapState: vi.fn() }));
vi.mock("../../state/appShell", () => ({ useAppShellState: vi.fn() }));
const request = vi.mocked(fetchReleasedDocuments);
const bootstrap = reactive({ modules: [{ id: "documents", licensed: true, authorized: true }] });
const shell = reactive({ auth: { status: "authenticated", user: { session_id: "synthetic" } } });
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/", component: ReleasedDocumentsView }, { path: "/documents/:docId/viewer", name: "document-viewer", component: { template: "<div/>" } }] });
  await router.push("/");
  return mount(ReleasedDocumentsView, { global: { plugins: [i18n, router], stubs: { VTable: { template: "<table><slot/></table>" }, VBtn: { template: "<button><slot/></button>" } } } });
}
beforeEach(() => {
  request.mockReset().mockResolvedValue([]);
  bootstrap.modules[0].authorized = true; shell.auth.status = "authenticated";
  vi.mocked(useBootstrapState).mockReturnValue(bootstrap as unknown as ReturnType<typeof useBootstrapState>);
  vi.mocked(useAppShellState).mockReturnValue(shell as unknown as ReturnType<typeof useAppShellState>);
});
describe("Released documents backend catalog", () => {
  it("renders precisely the backend catalog and clearly marks exceeded validity dates", async () => {
    request.mockResolvedValue([{ document_id: "R-1", version: 2, title: "Released synthetic", released_at: null, valid_until: "2020-01-01T00:00:00Z", owner_user_id: null }]);
    const wrapper = await render(); await flushPromises();
    expect(wrapper.findAll('[data-testid="released-document-row"]')).toHaveLength(1);
    expect(wrapper.get('[data-testid="released-date-exceeded"]').text()).toContain("überschritten");
    expect(wrapper.get('[data-testid="released-document-read"]').attributes("to")).toBeDefined();
    wrapper.unmount();
  });
  it("does not load the catalog when the module is unavailable", async () => {
    bootstrap.modules[0].authorized = false;
    const wrapper = await render(); await flushPromises();
    expect(request).not.toHaveBeenCalled(); wrapper.unmount();
  });
  it("distinguishes forbidden errors from an empty catalog", async () => {
    request.mockRejectedValue(new ApiTransportError("forbidden", 403, null));
    const wrapper = await render(); await flushPromises();
    expect(wrapper.find('[data-testid="released-documents-error"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain("Keine freigegebenen"); wrapper.unmount();
  });
  it("does not apply a late catalog response after logout", async () => {
    let resolve!: (rows: Awaited<ReturnType<typeof fetchReleasedDocuments>>) => void;
    request.mockReturnValue(new Promise(done => { resolve = done; }));
    const wrapper = await render(); shell.auth.status = "anonymous"; await flushPromises();
    resolve([{ document_id: "R-1", version: 1, title: "Must not appear", valid_until: null, released_at: null, owner_user_id: null }]);
    await flushPromises(); expect(wrapper.text()).not.toContain("Must not appear"); wrapper.unmount();
  });
});
