import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

import type { DocumentQueryItem } from "../../api/client";
import DocumentsDetailPanel from "../../components/documents/DocumentsDetailPanel.vue";
import DocumentsTable from "../../components/documents/DocumentsTable.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";

function item(overrides: Partial<DocumentQueryItem> = {}): DocumentQueryItem {
  return {
    allowed_actions: [],
    approved_by: [],
    assignments: {
      approvers: [],
      editors: [],
      reviewers: [],
    },
    control_class: "controlled",
    description: null,
    doc_type: "SOP",
    document_id: "DOC-1",
    edit_signature_done: false,
    extension_count: 0,
    reviewed_by: [],
    status: "APPROVED",
    title: "Qualitätsleitbild",
    updated_at: "2026-01-15T10:00:00Z",
    version: 2,
    workflow_active: false,
    workflow_profile_id: "default",
    ...overrides,
  };
}

function mountTable(props: {
  items: DocumentQueryItem[];
  sort?: "updated_at" | "title" | "status";
  order?: "asc" | "desc";
  selectedRow?: { documentId: string; version: number } | null;
}) {
  return mount(DocumentsTable, {
    props: {
      items: props.items,
      sort: props.sort ?? "updated_at",
      order: props.order ?? "desc",
      selectedRow: props.selectedRow ?? null,
    },
    global: {
      plugins: [vuetify, i18n],
    },
  });
}

describe("DocumentsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders core columns with German status labels and no dominant technical id", () => {
    const wrapper = mountTable({ items: [item()] });

    expect(wrapper.text()).toContain("Titel");
    expect(wrapper.text()).toContain("Status");
    expect(wrapper.text()).toContain("Version");
    expect(wrapper.text()).toContain("Geändert");
    expect(wrapper.text()).toContain("Qualitätsleitbild");
    expect(wrapper.find("[data-testid=documents-table-status]").text()).toBe("Freigegeben");
    expect(wrapper.text()).not.toContain("DOC-1");
    expect(wrapper.text()).not.toContain("start");
    expect(wrapper.text()).not.toContain("assign_roles");
  });

  it("uses a generic German fallback for unknown status codes", () => {
    const wrapper = mountTable({ items: [item({ status: "CUSTOM_STATE" })] });
    expect(wrapper.find("[data-testid=documents-table-status]").text()).toBe("Unbekannter Status");
    expect(wrapper.text()).not.toContain("CUSTOM_STATE");
  });

  it("selects only the exact document_id and version row", async () => {
    const wrapper = mountTable({
      items: [
        item({ document_id: "DOC-1", version: 1, title: "Version 1" }),
        item({ document_id: "DOC-1", version: 2, title: "Version 2" }),
      ],
      selectedRow: { documentId: "DOC-1", version: 2 },
    });

    const rows = wrapper.findAll("[data-testid=documents-table-row]");
    expect(rows[0].attributes("aria-selected")).toBe("false");
    expect(rows[1].attributes("aria-selected")).toBe("true");

    await rows[0].trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([{ documentId: "DOC-1", version: 1 }]);
  });

  it("emits sort only for allowed server fields", async () => {
    const wrapper = mountTable({ items: [item()], sort: "updated_at", order: "desc" });

    await wrapper.get("[data-testid=documents-sort-title]").trigger("click");
    expect(wrapper.emitted("sort")?.[0]).toEqual([{ sort: "title", order: "desc" }]);

    await wrapper.setProps({ sort: "title", order: "desc" });
    await wrapper.get("[data-testid=documents-sort-title]").trigger("click");
    expect(wrapper.emitted("sort")?.[1]).toEqual([{ sort: "title", order: "asc" }]);
  });

  it("marks selected row for accessibility and emits select on click", async () => {
    const wrapper = mountTable({
      items: [
        item({ document_id: "DOC-1", version: 1 }),
        item({ document_id: "DOC-2", version: 1, title: "Zweites Dokument" }),
      ],
      selectedRow: { documentId: "DOC-2", version: 1 },
    });

    const rows = wrapper.findAll("[data-testid=documents-table-row]");
    expect(rows[1].attributes("aria-selected")).toBe("true");

    await rows[0].trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([{ documentId: "DOC-1", version: 1 }]);
  });

  it("supports keyboard row selection with Enter and Space", async () => {
    const wrapper = mountTable({
      items: [
        item({ document_id: "DOC-1", version: 1 }),
        item({ document_id: "DOC-2", version: 1, title: "Zweites Dokument" }),
      ],
    });

    const rows = wrapper.findAll("[data-testid=documents-table-row]");
    await rows[1].trigger("keydown.enter");
    expect(wrapper.emitted("select")?.[0]).toEqual([{ documentId: "DOC-2", version: 1 }]);

    await rows[0].trigger("keydown.space");
    expect(wrapper.emitted("select")?.[1]).toEqual([{ documentId: "DOC-1", version: 1 }]);
  });
});

describe("DocumentsDetailPanel", () => {
  it("uses the same unknown-status fallback as the table without raw codes", () => {
    const wrapper = mount(DocumentsDetailPanel, {
      props: {
        item: item({ status: "CUSTOM_STATE", title: "Detailtitel" }),
      },
      global: {
        plugins: [vuetify, i18n],
      },
    });

    expect(wrapper.find("[data-testid=documents-detail-status]").text()).toBe("Unbekannter Status");
    expect(wrapper.text()).not.toContain("CUSTOM_STATE");
  });
});
