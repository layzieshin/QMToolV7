import { mount } from "@vue/test-utils";
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

import { artifactDownloadUrl, type DocumentArtifactModel, type VersionStateResponse } from "../../api/client";
import ReleasedArtifactPanel from "../../components/documents/ReleasedArtifactPanel.vue";
import { i18n } from "../../i18n";
import vuetify from "../../plugins/vuetify";

const fetchArtifactPreviewBlobMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    fetchArtifactPreviewBlob: fetchArtifactPreviewBlobMock,
  };
});

function artifact(type: string, id: string): DocumentArtifactModel {
  return {
    artifact_id: id,
    artifact_type: type,
    created_at: "2026-01-01T00:00:00Z",
    document_id: "DOC-1",
    is_current: true,
    mime_type: "application/pdf",
    original_filename: `${type}.pdf`,
    sha256: "abc",
    size_bytes: 100,
    source_type: "upload",
    version: 1,
  };
}

function actionDescriptor(code: string, enabled: boolean) {
  return {
    code,
    enabled,
    destructive: false,
    label_key: `documents.action.${code}`,
    requires_confirmation: false,
    requires_reason: false,
    severity: "info" as const,
    disabled_reason: enabled ? null : "blocked",
    signature_required: false,
    assignment_kind: null,
  };
}

function detailWithActions(
  previewEnabled: boolean,
  downloadEnabled = false,
): VersionStateResponse {
  const allowed = [actionDescriptor("preview", previewEnabled)];
  if (downloadEnabled) {
    allowed.push(actionDescriptor("download", true));
  }
  const available = allowed.filter((action) => action.enabled).map((action) => action.code);
  return {
    etag: "evt-1",
    allowed_actions: allowed,
    available_actions: available,
    state: {
      document_id: "DOC-1",
      version: 1,
      status: "APPROVED",
      workflow_profile_id: "profile",
      assignments: { editors: [], reviewers: [], approvers: [] },
    },
  } as unknown as VersionStateResponse;
}

function detailWithPreview(enabled: boolean): VersionStateResponse {
  return detailWithActions(enabled, false);
}

describe("ReleasedArtifactPanel", () => {
  beforeEach(() => {
    fetchArtifactPreviewBlobMock.mockReset();
    fetchArtifactPreviewBlobMock.mockResolvedValue(
      new Blob(["%PDF-1.4"], { type: "application/pdf" }),
    );
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
    vi.stubGlobal(
      "URL",
      Object.assign(globalThis.URL, {
        createObjectURL: vi.fn(() => "blob:released"),
        revokeObjectURL: vi.fn(),
      }),
    );
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it("shows signed success without claiming release when RELEASED_PDF is absent and artifacts are known", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithPreview(true),
        artifacts: [artifact("SIGNED_PDF", "signed-1")],
        signedSuccess: true,
        artifactsUnknown: false,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.get('[data-testid="signed-without-release"]').text()).toContain(
      "freigegebenes PDF liegt noch nicht vor",
    );
    expect(wrapper.find('[data-testid="released-artifact-entry"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="artifacts-unknown"]').exists()).toBe(false);
  });

  it("shows artifacts-unknown when the artifact list is unknown", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithPreview(true),
        artifacts: [],
        signedSuccess: true,
        artifactsUnknown: true,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.find('[data-testid="artifacts-unknown"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="signed-without-release"]').exists()).toBe(false);
  });

  it("shows retryable artifact refresh error when refresh failed", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithPreview(true),
        artifacts: [],
        signedSuccess: true,
        artifactsUnknown: true,
        artifactRefreshError: "Artefakte konnten nicht geladen werden.",
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.find('[data-testid="artifacts-unknown"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="artifact-refresh-error"]').text()).toContain(
      "Artefakte konnten nicht geladen werden",
    );
  });

  it("hides stale artifact rows while artifacts are unknown or refresh failed", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithPreview(true),
        artifacts: [artifact("RELEASED_PDF", "stale-released")],
        signedSuccess: true,
        artifactsUnknown: true,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.find('[data-testid="artifact-type-list"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="released-artifact-entry"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="signed-without-release"]').exists()).toBe(false);
  });

  it("previews only the current RELEASED_PDF artifact when preview is allowed", async () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithPreview(true),
        artifacts: [
          artifact("SOURCE_PDF", "source-1"),
          artifact("SIGNED_PDF", "signed-1"),
          artifact("RELEASED_PDF", "released-1"),
        ],
        signedSuccess: true,
        artifactsUnknown: false,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.get('[data-testid="released-artifact-entry"]').text()).toContain("Freigegebenes PDF");
    await vi.waitFor(() => {
      expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledTimes(1);
      expect(fetchArtifactPreviewBlobMock).toHaveBeenCalledWith("released-1");
    });
  });

  it("does not fetch preview when preview action is disabled", async () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithPreview(false),
        artifacts: [artifact("RELEASED_PDF", "released-1")],
        signedSuccess: true,
      },
      global: { plugins: [i18n, vuetify] },
    });
    await vi.waitFor(() => {
      expect(fetchArtifactPreviewBlobMock).not.toHaveBeenCalled();
    });
    expect(wrapper.find('[data-testid="released-preview-unavailable"]').exists()).toBe(true);
  });

  it("shows download only when RELEASED_PDF is authoritative and download action is enabled", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithActions(true, true),
        artifacts: [artifact("RELEASED_PDF", "released-1")],
        signedSuccess: true,
        artifactsUnknown: false,
      },
      global: { plugins: [i18n, vuetify] },
    });
    const link = wrapper.get('[data-testid="released-artifact-download"]');
    expect(link.text()).toContain("Herunterladen");
    expect(link.attributes("href")).toBe(artifactDownloadUrl("released-1"));
  });

  it("hides download when download action is disabled even with preview", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithActions(true, false),
        artifacts: [artifact("RELEASED_PDF", "released-1")],
        signedSuccess: true,
        artifactsUnknown: false,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.find('[data-testid="released-artifact-download"]').exists()).toBe(false);
  });

  it("hides download when artifacts are unknown or refresh failed", () => {
    const detail = detailWithActions(true, true);
    const unknownWrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail,
        artifacts: [artifact("RELEASED_PDF", "released-1")],
        signedSuccess: true,
        artifactsUnknown: true,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(unknownWrapper.find('[data-testid="released-artifact-download"]').exists()).toBe(false);

    const errorWrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail,
        artifacts: [artifact("RELEASED_PDF", "released-1")],
        signedSuccess: true,
        artifactsUnknown: true,
        artifactRefreshError: "Artefakte konnten nicht geladen werden.",
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(errorWrapper.find('[data-testid="released-artifact-download"]').exists()).toBe(false);
  });

  it("encodes artifact ids in download URLs", () => {
    const wrapper = mount(ReleasedArtifactPanel, {
      props: {
        detail: detailWithActions(true, true),
        artifacts: [artifact("RELEASED_PDF", "release/id+special")],
        signedSuccess: true,
        artifactsUnknown: false,
      },
      global: { plugins: [i18n, vuetify] },
    });
    expect(wrapper.get('[data-testid="released-artifact-download"]').attributes("href")).toBe(
      artifactDownloadUrl("release/id+special"),
    );
  });
});
