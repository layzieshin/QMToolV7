import { flushPromises, mount } from "@vue/test-utils";
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

import { ApiTransportError, type VersionHistoryEvent } from "../../api/client";
import HistoryPanel from "../../components/documents/HistoryPanel.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";

const fetchDocumentVersionHistoryMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchDocumentVersionHistory: fetchDocumentVersionHistoryMock,
  };
});

function directory() {
  return [{ user_id: "user-active", username: "Aktiver Benutzer", is_active: true, is_qmb: false, role: "editor" }];
}

function backendEvent(
  event_type: string,
  summary: string,
  overrides: Partial<VersionHistoryEvent> = {},
): VersionHistoryEvent {
  return {
    occurred_at: "2026-01-15T10:30:00Z",
    event_type,
    actor_user_id: "user-active",
    summary,
    ...overrides,
  };
}

describe("HistoryPanel", () => {
  const mountedWrappers: ReturnType<typeof mount>[] = [];

  function mountPanel(props: Record<string, unknown> = {}) {
    const wrapper = mount(HistoryPanel, {
      props: { documentId: "DOC-1", version: 2, directory: directory(), ...props },
      global: { plugins: [i18n, vuetify] },
    });
    mountedWrappers.push(wrapper);
    return wrapper;
  }

  beforeEach(() => {
    fetchDocumentVersionHistoryMock.mockReset();
    vi.stubGlobal(
      "matchMedia",
      (query: string) =>
        ({
          matches: false,
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
          addListener: () => undefined,
          removeListener: () => undefined,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    );
  });

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount();
    }
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it.each([
    ["created", "created", "Dokument angelegt"],
    ["status_changed", "review completed", "Prüfung abgeschlossen"],
    ["status_changed", "approval completed", "Freigabe abgeschlossen"],
    ["released", "released", "Version freigegeben"],
    ["archived", "archived", "Version archiviert"],
    ["signed", "signed", "Bearbeitung signiert"],
  ])("maps backend %s/%s to localized label", async (eventType, summary, label) => {
    fetchDocumentVersionHistoryMock.mockResolvedValueOnce([
      backendEvent(eventType, summary),
    ]);
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find('[data-testid="history-panel-event-label"]').text()).toBe(label);
    expect(wrapper.text()).not.toContain(eventType);
    expect(wrapper.text()).not.toContain(summary);
  });

  it("shows comment_added label and user preview content without raw codes", async () => {
    fetchDocumentVersionHistoryMock.mockResolvedValueOnce([
      backendEvent("comment_added", "Bitte Abschnitt 3 prüfen", { actor_user_id: null }),
    ]);
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find('[data-testid="history-panel-event-label"]').text()).toBe("Kommentar hinzugefügt");
    expect(wrapper.find('[data-testid="history-panel-comment-content"]').text()).toBe(
      "Bitte Abschnitt 3 prüfen",
    );
    expect(wrapper.text()).not.toContain("comment_added");
  });

  it("uses neutral fallback for unknown event combinations", async () => {
    fetchDocumentVersionHistoryMock.mockResolvedValueOnce([
      backendEvent("workflow_reset", "technical payload"),
    ]);
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find('[data-testid="history-panel-event-label"]').text()).toBe("Verlaufsereignis");
    expect(wrapper.text()).not.toContain("workflow_reset");
    expect(wrapper.text()).not.toContain("technical payload");
  });

  it("renders directory actor, unknown actor, and unavailable actor without claiming system", async () => {
    fetchDocumentVersionHistoryMock.mockResolvedValueOnce([
      backendEvent("created", "created"),
      backendEvent("signed", "signed", { actor_user_id: "user-missing" }),
      backendEvent("comment_added", "Hinweis", { actor_user_id: null }),
    ]);
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find('[data-testid="history-panel-actor"]').text()).toContain("Aktiver Benutzer");
    expect(wrapper.findAll('[data-testid="history-panel-actor"]').length).toBeGreaterThanOrEqual(2);
    const unavailable = wrapper.findAll('[data-testid="history-panel-actor-unavailable"]');
    expect(unavailable).toHaveLength(1);
    expect(unavailable[0]?.text()).toContain("Akteur nicht verfügbar");
    expect(wrapper.text()).not.toContain("System");
    expect(wrapper.find('[data-testid="history-panel-occurred-at"]').attributes("datetime")).toBe(
      "2026-01-15T10:30:00Z",
    );
  });

  it("shows empty state when history returns no events", async () => {
    fetchDocumentVersionHistoryMock.mockResolvedValueOnce([]);
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find('[data-testid="history-panel-empty"]').exists()).toBe(true);
  });

  it("shows localized error and retries load", async () => {
    fetchDocumentVersionHistoryMock.mockRejectedValueOnce(new ApiTransportError("HTTP 403", 403, null));
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.find('[data-testid="history-panel-error"]').text()).toContain("nicht erlaubt");
    fetchDocumentVersionHistoryMock.mockResolvedValueOnce([
      backendEvent("created", "created"),
    ]);
    await wrapper.get('[data-testid="history-panel-retry"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Dokument angelegt");
  });

  it("exposes loading state with role=status", async () => {
    fetchDocumentVersionHistoryMock.mockImplementationOnce(
      () => new Promise(() => undefined),
    );
    const wrapper = mountPanel();
    const loading = wrapper.find('[data-testid="history-panel-loading"]');
    expect(loading.exists()).toBe(true);
    expect(loading.attributes("role")).toBe("status");
  });

  it("ignores stale history responses after document change", async () => {
    let resolveSlow: (value: unknown) => void = () => undefined;
    fetchDocumentVersionHistoryMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSlow = resolve;
          }),
      )
      .mockResolvedValueOnce([
        backendEvent("comment_added", "Fresh doc", { actor_user_id: null }),
      ]);
    const wrapper = mountPanel({ documentId: "DOC-1", version: 1 });
    await wrapper.setProps({ documentId: "DOC-2", version: 1 });
    await flushPromises();
    expect(wrapper.text()).toContain("Fresh doc");
    resolveSlow([backendEvent("comment_added", "Stale doc", { actor_user_id: null })]);
    await flushPromises();
    expect(wrapper.text()).toContain("Fresh doc");
    expect(wrapper.text()).not.toContain("Stale doc");
  });
});
