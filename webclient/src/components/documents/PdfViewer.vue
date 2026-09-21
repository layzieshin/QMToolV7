<script setup lang="ts">
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf.mjs";
// @ts-expect-error Vite resolves the bundled pdf.js worker asset URL at build time.
import pdfjsWorker from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";
import { computed, nextTick, onUnmounted, ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

const MIN_PAGE = 1;
const MIN_ZOOM = 50;
const MAX_ZOOM = 300;
const ZOOM_STEP = 25;
const DEFAULT_ZOOM = 100;

const props = defineProps<{
  previewUrl: string | null;
  loading?: boolean;
  error?: boolean;
}>();

const emit = defineEmits<{
  "page-change": [page: number];
}>();

const { t } = useI18n();

const currentPage = ref(MIN_PAGE);
const zoomPercent = ref(DEFAULT_ZOOM);
const fitMode = ref<"none" | "width" | "page">("none");
const pageCount = ref(0);
const renderState = ref<"loading" | "ready" | "error">("loading");
const internalError = ref(false);
const appliedScalePercent = ref(DEFAULT_ZOOM);
const canvasRef = ref<HTMLCanvasElement | null>(null);
const stageRef = ref<HTMLDivElement | null>(null);
const renderGeneration = { current: 0 };
const activeRenderTask = shallowRef<RenderTask | null>(null);
const isMounted = ref(true);
let resizeObserver: ResizeObserver | null = null;
let lastObservedStageWidth = 0;
let lastObservedStageHeight = 0;
let pendingPageResetEmit = false;

type PdfCacheEntry = {
  url: string;
  loadingTask: PDFDocumentLoadingTask;
  documentPromise: Promise<PDFDocumentProxy>;
};

let pdfDocumentCache: PdfCacheEntry | null = null;

const showViewerSurface = computed(
  () => Boolean(props.previewUrl) && !props.loading && !props.error,
);

const hasCanvasGeometry = computed(() => {
  const canvas = canvasRef.value;
  return Boolean(canvas && canvas.width > 0 && canvas.height > 0);
});

const displayZoomPercent = computed(() => {
  if (renderState.value === "ready") {
    return appliedScalePercent.value;
  }
  return fitMode.value === "none" ? zoomPercent.value : appliedScalePercent.value;
});

const isPageNavigationDisabled = computed(
  () => !showViewerSurface.value || pageCount.value <= 0,
);
const isPreviousDisabled = computed(
  () => isPageNavigationDisabled.value || currentPage.value <= MIN_PAGE,
);
const isNextDisabled = computed(
  () => isPageNavigationDisabled.value || currentPage.value >= pageCount.value,
);
const pageInputMax = computed(() => (pageCount.value > 0 ? pageCount.value : undefined));

function releaseOwnedRenderTask(task: RenderTask | null): void {
  if (task && activeRenderTask.value === task) {
    activeRenderTask.value = null;
  }
}

function cancelActiveRender(): void {
  const task = activeRenderTask.value;
  if (!task) {
    return;
  }
  task.cancel();
  activeRenderTask.value = null;
}

function destroyLoadingTask(loadingTask: PDFDocumentLoadingTask): void {
  try {
    const destroyResult = loadingTask.destroy();
    if (
      destroyResult &&
      typeof (destroyResult as Promise<unknown>).catch === "function"
    ) {
      void (destroyResult as Promise<unknown>).catch(() => undefined);
    }
  } catch {
    // Bound synchronous destroy failures without disturbing active render ownership.
  }
}

function destroyPdfCache(): void {
  if (!pdfDocumentCache) {
    return;
  }
  const loadingTask = pdfDocumentCache.loadingTask;
  pdfDocumentCache = null;
  destroyLoadingTask(loadingTask);
}

function clearCanvas(): void {
  const canvas = canvasRef.value;
  if (!canvas) {
    return;
  }
  canvas.width = 0;
  canvas.height = 0;
  canvas.style.width = "0";
  canvas.style.height = "0";
  canvas.removeAttribute("data-rendered-page");
  canvas.removeAttribute("data-rendered-fit");
  canvas.removeAttribute("data-rendered-scale");
}

function enterLoadingState(clearCanvasGeometry: boolean): void {
  renderState.value = "loading";
  internalError.value = false;
  if (clearCanvasGeometry) {
    clearCanvas();
  }
}

function invalidateRender(clearCanvasGeometry = true): number {
  renderGeneration.current += 1;
  enterLoadingState(clearCanvasGeometry);
  cancelActiveRender();
  return renderGeneration.current;
}

function isRenderGenerationCurrent(generation: number): boolean {
  return isMounted.value && generation === renderGeneration.current;
}

function emitValidatedPageChange(page: number): void {
  if (
    !showViewerSurface.value ||
    pageCount.value <= 0 ||
    page < MIN_PAGE ||
    page > pageCount.value
  ) {
    return;
  }
  emit("page-change", page);
}

function emitPendingPageReset(): void {
  if (!pendingPageResetEmit) {
    return;
  }
  pendingPageResetEmit = false;
  emit("page-change", MIN_PAGE);
}

async function acquirePdfDocument(
  url: string,
  generation: number,
): Promise<PDFDocumentProxy | null> {
  if (!pdfDocumentCache || pdfDocumentCache.url !== url) {
    return null;
  }
  const document = await pdfDocumentCache.documentPromise;
  if (!isRenderGenerationCurrent(generation)) {
    return null;
  }
  return document;
}

function ensurePdfCache(url: string): void {
  if (pdfDocumentCache?.url === url) {
    return;
  }
  const loadingTask = pdfjsLib.getDocument({ url });
  pdfDocumentCache = {
    url,
    loadingTask,
    documentPromise: loadingTask.promise,
  };
}

function readStageMetrics(): { width: number; height: number } {
  const stage = stageRef.value;
  return {
    width: stage?.clientWidth ?? 0,
    height: stage?.clientHeight ?? 0,
  };
}

function computeScale(pageWidth: number, pageHeight: number): number {
  const { width: containerWidth, height: containerHeight } = readStageMetrics();
  if (fitMode.value === "width" && containerWidth > 0 && pageWidth > 0) {
    return containerWidth / pageWidth;
  }
  if (fitMode.value === "page" && pageWidth > 0 && pageHeight > 0) {
    if (containerWidth > 0 && containerHeight > 0) {
      return Math.min(containerWidth / pageWidth, containerHeight / pageHeight);
    }
    if (containerWidth > 0) {
      return containerWidth / pageWidth;
    }
  }
  return zoomPercent.value / 100;
}

function roundScalePercent(scale: number): number {
  return Math.round(scale * 100);
}

async function renderCurrentPage(generation: number): Promise<void> {
  const url = props.previewUrl?.trim();
  const canvas = canvasRef.value;
  if (!url || !canvas || props.loading || props.error || !isMounted.value) {
    return;
  }
  if (!isRenderGenerationCurrent(generation)) {
    return;
  }

  try {
    ensurePdfCache(url);
    const pdf = await acquirePdfDocument(url, generation);
    if (!pdf || !isRenderGenerationCurrent(generation)) {
      return;
    }

    pageCount.value = pdf.numPages;
    const boundedPage = Math.min(Math.max(currentPage.value, MIN_PAGE), pdf.numPages);
    if (boundedPage !== currentPage.value) {
      currentPage.value = boundedPage;
      emitValidatedPageChange(boundedPage);
    }

    const page = await pdf.getPage(boundedPage);
    if (!isRenderGenerationCurrent(generation)) {
      return;
    }

    const unscaled = page.getViewport({ scale: 1, rotation: 0 });
    const scale = computeScale(unscaled.width, unscaled.height);
    appliedScalePercent.value = roundScalePercent(scale);
    const viewport = page.getViewport({ scale, rotation: 0 });

    if (viewport.width <= 0 || viewport.height <= 0) {
      if (!isRenderGenerationCurrent(generation)) {
        return;
      }
      internalError.value = true;
      renderState.value = "error";
      return;
    }

    const context = canvas.getContext("2d");
    if (!context) {
      if (!isRenderGenerationCurrent(generation)) {
        return;
      }
      internalError.value = true;
      renderState.value = "error";
      return;
    }

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    const task = page.render({ canvasContext: context, viewport });
    activeRenderTask.value = task;
    try {
      await task.promise;
    } catch (cause) {
      releaseOwnedRenderTask(task);
      if (!isRenderGenerationCurrent(generation)) {
        return;
      }
      if (cause instanceof Error && cause.message.toLowerCase().includes("cancel")) {
        return;
      }
      internalError.value = true;
      renderState.value = "error";
      return;
    }

    releaseOwnedRenderTask(task);
    if (!isRenderGenerationCurrent(generation)) {
      return;
    }

    canvas.setAttribute("data-rendered-page", String(boundedPage));
    canvas.setAttribute("data-rendered-fit", fitMode.value);
    canvas.setAttribute("data-rendered-scale", String(appliedScalePercent.value));
    renderState.value = "ready";
  } catch (cause) {
    if (!isRenderGenerationCurrent(generation)) {
      return;
    }
    if (cause instanceof Error && cause.message.toLowerCase().includes("cancel")) {
      return;
    }
    internalError.value = true;
    renderState.value = "error";
  }
}

function scheduleRender(generation: number): void {
  void nextTick(async () => {
    await nextTick();
    if (!isMounted.value || generation !== renderGeneration.current) {
      return;
    }
    void renderCurrentPage(generation);
  });
}

function requestRender(): void {
  const generation = invalidateRender(false);
  scheduleRender(generation);
}

function goToPreviousPage(): void {
  if (isPageNavigationDisabled.value || currentPage.value <= MIN_PAGE) {
    return;
  }
  currentPage.value -= 1;
  fitMode.value = "none";
  emitValidatedPageChange(currentPage.value);
  requestRender();
}

function goToNextPage(): void {
  if (isPageNavigationDisabled.value || currentPage.value >= pageCount.value) {
    return;
  }
  currentPage.value += 1;
  fitMode.value = "none";
  emitValidatedPageChange(currentPage.value);
  requestRender();
}

function onPageInput(event: Event): void {
  if (isPageNavigationDisabled.value) {
    return;
  }
  const input = event.target as HTMLInputElement;
  const raw = input.value.trim();
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isInteger(parsed) || parsed < MIN_PAGE) {
    input.value = String(currentPage.value);
    return;
  }
  const clamped = Math.min(parsed, pageCount.value);
  if (clamped === currentPage.value) {
    input.value = String(clamped);
    return;
  }
  currentPage.value = clamped;
  fitMode.value = "none";
  input.value = String(clamped);
  emitValidatedPageChange(clamped);
  requestRender();
}

function zoomIn(): void {
  fitMode.value = "none";
  zoomPercent.value = Math.min(MAX_ZOOM, zoomPercent.value + ZOOM_STEP);
  requestRender();
}

function zoomOut(): void {
  fitMode.value = "none";
  zoomPercent.value = Math.max(MIN_ZOOM, zoomPercent.value - ZOOM_STEP);
  requestRender();
}

function fitWidth(): void {
  fitMode.value = "width";
  requestRender();
}

function fitPage(): void {
  fitMode.value = "page";
  requestRender();
}

function handleStageResize(): void {
  if (fitMode.value === "none" || !showViewerSurface.value) {
    return;
  }
  const { width, height } = readStageMetrics();
  if (fitMode.value === "width") {
    if (width <= 0 || width === lastObservedStageWidth) {
      return;
    }
    lastObservedStageWidth = width;
    lastObservedStageHeight = height;
  } else {
    if (
      width <= 0 ||
      height <= 0 ||
      (width === lastObservedStageWidth && height === lastObservedStageHeight)
    ) {
      return;
    }
    lastObservedStageWidth = width;
    lastObservedStageHeight = height;
  }
  requestRender();
}

function resetObservedStageSize(): void {
  const { width, height } = readStageMetrics();
  lastObservedStageWidth = width;
  lastObservedStageHeight = height;
}

watch(
  () => [props.previewUrl, props.loading, props.error] as const,
  ([url, loading, error], previous) => {
    const previousUrl = previous?.[0] ?? null;
    if (url !== previousUrl) {
      const generation = invalidateRender(true);
      const previousPage = currentPage.value;
      if (previousPage !== MIN_PAGE) {
        pendingPageResetEmit = true;
      }
      currentPage.value = MIN_PAGE;
      zoomPercent.value = DEFAULT_ZOOM;
      fitMode.value = "none";
      pageCount.value = 0;
      destroyPdfCache();
      if (url && !loading && !error) {
        emitPendingPageReset();
        ensurePdfCache(url.trim());
        scheduleRender(generation);
      }
      return;
    }

    if (!url || loading || error) {
      invalidateRender(true);
      pageCount.value = 0;
      destroyPdfCache();
      return;
    }

    emitPendingPageReset();
    requestRender();
  },
  { immediate: true, flush: "sync" },
);

watch(stageRef, (stage) => {
  resizeObserver?.disconnect();
  resizeObserver = null;
  if (!stage || typeof ResizeObserver === "undefined") {
    return;
  }
  resetObservedStageSize();
  resizeObserver = new ResizeObserver(() => {
    handleStageResize();
  });
  resizeObserver.observe(stage);
});

onUnmounted(() => {
  isMounted.value = false;
  invalidateRender(true);
  destroyPdfCache();
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <section class="pdf-viewer" data-testid="pdf-viewer">
    <div
      class="pdf-viewer__toolbar"
      role="toolbar"
      :aria-label="t('documents.viewer.pdf.toolbar')"
    >
      <v-btn
        variant="outlined"
        size="small"
        data-testid="pdf-prev-page"
        :aria-label="t('documents.viewer.pdf.prevPage')"
        :disabled="isPreviousDisabled"
        @click="goToPreviousPage"
      >
        {{ t("documents.viewer.pdf.prevPage") }}
      </v-btn>
      <label class="pdf-viewer__page-label">
        <span class="sr-only">{{ t("documents.viewer.pdf.currentPage") }}</span>
        <input
          type="number"
          min="1"
          :max="pageInputMax"
          :value="currentPage"
          :disabled="isPageNavigationDisabled"
          data-testid="pdf-page-input"
          :aria-label="t('documents.viewer.pdf.currentPage')"
          @change="onPageInput"
        />
      </label>
      <v-btn
        variant="outlined"
        size="small"
        data-testid="pdf-next-page"
        :aria-label="t('documents.viewer.pdf.nextPage')"
        :disabled="isNextDisabled"
        @click="goToNextPage"
      >
        {{ t("documents.viewer.pdf.nextPage") }}
      </v-btn>
      <v-btn
        variant="outlined"
        size="small"
        data-testid="pdf-zoom-out"
        :aria-label="t('documents.viewer.pdf.zoomOut')"
        @click="zoomOut"
      >
        {{ t("documents.viewer.pdf.zoomOut") }}
      </v-btn>
      <span data-testid="pdf-zoom-level" aria-live="polite">
        {{ displayZoomPercent }}%
      </span>
      <v-btn
        variant="outlined"
        size="small"
        data-testid="pdf-zoom-in"
        :aria-label="t('documents.viewer.pdf.zoomIn')"
        @click="zoomIn"
      >
        {{ t("documents.viewer.pdf.zoomIn") }}
      </v-btn>
      <v-btn
        variant="outlined"
        size="small"
        data-testid="pdf-fit-width"
        :aria-label="t('documents.viewer.pdf.fitWidth')"
        @click="fitWidth"
      >
        {{ t("documents.viewer.pdf.fitWidth") }}
      </v-btn>
      <v-btn
        variant="outlined"
        size="small"
        data-testid="pdf-fit-page"
        :aria-label="t('documents.viewer.pdf.fitPage')"
        @click="fitPage"
      >
        {{ t("documents.viewer.pdf.fitPage") }}
      </v-btn>
    </div>

    <p v-if="loading" data-testid="pdf-viewer-loading">
      {{ t("documents.viewer.pdf.loading") }}
    </p>
    <p v-else-if="error" role="alert" data-testid="pdf-viewer-error">
      {{ t("documents.viewer.pdf.loadError") }}
    </p>
    <p v-else-if="!previewUrl" data-testid="pdf-viewer-empty">
      {{ t("documents.viewer.pdf.empty") }}
    </p>
    <div v-else class="pdf-viewer__frame" data-testid="pdf-viewer-frame">
      <div
        ref="stageRef"
        class="pdf-viewer__stage"
        data-testid="pdf-viewer-stage"
        :data-render-state="renderState"
      >
        <p v-if="internalError" role="alert" data-testid="pdf-viewer-error">
          {{ t("documents.viewer.pdf.loadError") }}
        </p>
        <canvas
          v-show="!internalError"
          ref="canvasRef"
          class="pdf-viewer__canvas"
          :class="{ 'pdf-viewer__canvas--hidden': renderState !== 'ready' && !hasCanvasGeometry }"
          data-testid="pdf-viewer-canvas"
          :title="t('documents.viewer.pdf.frameTitle')"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.pdf-viewer {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 24rem;
}

.pdf-viewer__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.pdf-viewer__page-label input {
  width: 4rem;
}

.pdf-viewer__frame {
  flex: 1 1 auto;
  min-height: clamp(20rem, 55vh, 40rem);
  height: clamp(20rem, 55vh, 40rem);
  border: 1px solid rgba(0, 0, 0, 0.12);
  overflow: hidden;
}

.pdf-viewer__stage {
  width: 100%;
  height: 100%;
  overflow: auto;
  scrollbar-gutter: stable;
}

.pdf-viewer__canvas {
  display: block;
  margin-left: auto;
  margin-right: auto;
}

.pdf-viewer__canvas--hidden {
  visibility: hidden;
  pointer-events: none;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
