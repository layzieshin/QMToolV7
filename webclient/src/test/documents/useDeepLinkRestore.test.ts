import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, ref } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  buildCanonicalDetailQuery,
  buildDetailQueryReplacement,
  detailQueryNeedsSanitization,
  parseDetailRouteSection,
  resolveSanitizedDetailQuery,
  useDeepLinkRestore,
  type DocumentDetailSection,
} from "../../composables/useDeepLinkRestore";
import { routes } from "../../router/routes";
import {
  __resetBootstrapStateForTest,
  __setBootstrapBannerForTest,
} from "../../state/bootstrap";

describe("useDeepLinkRestore helpers", () => {
  it("parses section with overview default", () => {
    expect(parseDetailRouteSection(undefined)).toBe("overview");
    expect(parseDetailRouteSection("history")).toBe("history");
    expect(parseDetailRouteSection("invalid")).toBe("overview");
    expect(parseDetailRouteSection(["history", "overview"])).toBe("overview");
  });

  it("builds canonical detail query without section for overview", () => {
    expect(buildCanonicalDetailQuery(2, "overview")).toEqual({ version: "2" });
    expect(buildCanonicalDetailQuery(2, "history")).toEqual({ version: "2", section: "history" });
  });

  it.each([
    ["missing version with secret", undefined, undefined, { token: "secret" }, {}],
    ["invalid version with unknown key", "abc", undefined, { foo: "bar", version: "abc" }, {}],
    ["multi-valued version", ["1", "2"], undefined, { version: ["1", "2"] }, {}],
    ["valid version strips secrets", "2", "history", { version: "2", section: "history", Password: "x" }, { version: "2", section: "history" }],
    ["valid version strips unknown keys", "3", undefined, { version: "3", audit: "1" }, { version: "3" }],
    ["invalid section falls back to overview query", "2", "audit", { version: "2", section: "audit" }, { version: "2" }],
    ["multi-valued section falls back to overview query", "2", ["history", "overview"], { version: "2", section: ["history", "overview"] }, { version: "2" }],
  ])("sanitizes %s", (_label, versionRaw, sectionRaw, currentQuery, expected) => {
    const target = resolveSanitizedDetailQuery(versionRaw, sectionRaw);
    expect(target).toEqual(expected);
    expect(detailQueryNeedsSanitization(currentQuery, target)).toBe(true);
  });

  it("builds router replacement that unsets removed query keys", () => {
    expect(
      buildDetailQueryReplacement(
        { version: "2", section: "audit", token: "secret" },
        { version: "2" },
      ),
    ).toEqual({ version: "2", section: undefined, token: undefined });
  });

  it("detects mixed-case secret keys and array-valued canonical keys", () => {
    expect(
      detailQueryNeedsSanitization(
        { version: ["2", "3"], TOKEN: "secret", Authorization: "bearer" },
        {},
      ),
    ).toBe(true);
    expect(
      detailQueryNeedsSanitization(
        { version: ["2"], section: "history" },
        { version: "2", section: "history" },
      ),
    ).toBe(true);
  });
});

describe("useDeepLinkRestore", () => {
  const mountedWrappers: ReturnType<typeof mount>[] = [];

  beforeEach(() => {
    __resetBootstrapStateForTest();
  });

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount();
    }
    __resetBootstrapStateForTest();
  });

  async function mountHarness(initialPath = "/documents/DOC-1?version=2") {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push(initialPath);
    await router.isReady();
    const restoreCalls = ref<number[]>([]);
    const wrapper = mount(
      defineComponent({
        setup() {
          useDeepLinkRestore((generation) => {
            restoreCalls.value.push(generation);
          });
          return () => null;
        },
      }),
      { global: { plugins: [router] } },
    );
    mountedWrappers.push(wrapper);
    await flushPromises();
    return { router, restoreCalls, wrapper };
  }

  it("normalizes secret and unknown query keys to canonical version/section", async () => {
    const { router } = await mountHarness("/documents/DOC-1?version=2&section=history&token=secret");
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ version: "2", section: "history" });
    expect(router.currentRoute.value.query.token).toBeUndefined();
  });

  it("strips invalid version and secret keys to empty query", async () => {
    const { router } = await mountHarness("/documents/DOC-1?version=abc&Password=secret&foo=bar");
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({});
  });

  it("removes invalid section query keys via router replace", async () => {
    const { router } = await mountHarness("/documents/DOC-1?version=2&section=audit");
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ version: "2" });
  });

  it("strips secret keys when version is missing", async () => {
    const { router } = await mountHarness("/documents/DOC-1?token=secret");
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({});
  });

  it("preserves version when switching to history section", async () => {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1?version=3");
    await router.isReady();
    const setSectionRef: { fn: (section: DocumentDetailSection) => Promise<void> } = {
      fn: async () => undefined,
    };
    const wrapper = mount(
      defineComponent({
        setup() {
          const { setSection } = useDeepLinkRestore(() => undefined);
          setSectionRef.fn = setSection;
          return () => null;
        },
      }),
      { global: { plugins: [router] } },
    );
    mountedWrappers.push(wrapper);
    await setSectionRef.fn("history");
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ version: "3", section: "history" });
  });

  it("triggers one restore callback on offline to restored transition", async () => {
    const { restoreCalls } = await mountHarness();
    __setBootstrapBannerForTest("offline");
    await flushPromises();
    __setBootstrapBannerForTest("restored");
    await flushPromises();
    expect(restoreCalls.value).toEqual([1]);
  });

  it("does not reload on restored without prior offline or reconnecting", async () => {
    const { restoreCalls } = await mountHarness();
    __setBootstrapBannerForTest("restored");
    await flushPromises();
    expect(restoreCalls.value).toEqual([]);
  });

  it("does not duplicate restore when banner remains restored", async () => {
    const { restoreCalls } = await mountHarness();
    __setBootstrapBannerForTest("offline");
    await flushPromises();
    __setBootstrapBannerForTest("restored");
    await flushPromises();
    expect(restoreCalls.value).toEqual([1]);
    __setBootstrapBannerForTest("restored");
    await flushPromises();
    expect(restoreCalls.value).toEqual([1]);
  });

  it("restores history section after browser back", async () => {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/documents/DOC-1?version=2&section=history");
    await router.isReady();
    const wrapper = mount(
      defineComponent({
        setup() {
          useDeepLinkRestore(() => undefined);
          return () => null;
        },
      }),
      { global: { plugins: [router] } },
    );
    mountedWrappers.push(wrapper);
    await router.push({ name: "documents" });
    await flushPromises();
    await router.back();
    await flushPromises();
    expect(router.currentRoute.value.query.section).toBe("history");
    expect(router.currentRoute.value.query.version).toBe("2");
  });
});
