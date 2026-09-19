<script lang="ts">
import type { PageViewport } from "pdfjs-dist";

export type CanonicalPlacement = {
  page_index: number;
  x: number;
  y: number;
  target_width: number;
};

export const DEFAULT_BLOCK_HEIGHT_RATIO = 0.3;
export const MIN_TARGET_WIDTH_PDF = 10;

export function estimateBlockHeightPdf(targetWidth: number): number {
  return Math.max(6, targetWidth * DEFAULT_BLOCK_HEIGHT_RATIO);
}

export function viewportDistanceToPdfWidth(
  viewport: PageViewport,
  viewportWidth: number,
  anchorY: number,
): number {
  const start = viewport.convertToPdfPoint(0, anchorY);
  const end = viewport.convertToPdfPoint(viewportWidth, anchorY);
  return Math.hypot(end[0] - start[0], end[1] - start[1]);
}

export function viewportRectToCanonicalPlacement(
  viewport: PageViewport,
  left: number,
  top: number,
  width: number,
  height: number,
  pageIndex: number,
): CanonicalPlacement {
  const bottomLeft = viewport.convertToPdfPoint(left, top + height);
  const targetWidth = viewportDistanceToPdfWidth(viewport, width, top + height);
  return {
    page_index: pageIndex,
    x: bottomLeft[0],
    y: bottomLeft[1],
    target_width: targetWidth,
  };
}

export function canonicalPlacementToViewportRect(
  viewport: PageViewport,
  placement: CanonicalPlacement,
): { left: number; top: number; width: number; height: number } {
  const blockHeight = estimateBlockHeightPdf(placement.target_width);
  const topLeft = viewport.convertToViewportPoint(placement.x, placement.y + blockHeight);
  const bottomRight = viewport.convertToViewportPoint(
    placement.x + placement.target_width,
    placement.y,
  );
  const left = Math.min(topLeft[0], bottomRight[0]);
  const top = Math.min(topLeft[1], bottomRight[1]);
  const width = Math.abs(bottomRight[0] - topLeft[0]);
  const height = Math.abs(bottomRight[1] - topLeft[1]);
  return { left, top, width, height };
}

export function placementFitsPage(
  placement: CanonicalPlacement,
  pageWidth: number,
  pageHeight: number,
): boolean {
  const blockHeight = estimateBlockHeightPdf(placement.target_width);
  return (
    placement.x >= 0 &&
    placement.y >= 0 &&
    placement.x + placement.target_width <= pageWidth &&
    placement.y + blockHeight <= pageHeight
  );
}

export function pointerToSurfaceCoords(
  stage: Pick<HTMLElement, "getBoundingClientRect" | "scrollLeft" | "scrollTop">,
  event: Pick<PointerEvent, "clientX" | "clientY">,
): { x: number; y: number } {
  const rect = stage.getBoundingClientRect();
  return {
    x: event.clientX - rect.left + stage.scrollLeft,
    y: event.clientY - rect.top + stage.scrollTop,
  };
}

export function clampPlacementToPage(
  placement: CanonicalPlacement,
  pageWidth: number,
  pageHeight: number,
  pageCount = Number.POSITIVE_INFINITY,
): CanonicalPlacement {
  const maxPageIndex = Number.isFinite(pageCount) && pageCount > 0 ? pageCount - 1 : placement.page_index;
  const pageIndex = Math.min(Math.max(placement.page_index, 0), maxPageIndex);
  let targetWidth = Math.min(
    Math.max(placement.target_width, MIN_TARGET_WIDTH_PDF),
    pageWidth,
  );
  let blockHeight = estimateBlockHeightPdf(targetWidth);
  let x = Math.min(Math.max(placement.x, 0), Math.max(0, pageWidth - targetWidth));
  let y = Math.min(Math.max(placement.y, 0), Math.max(0, pageHeight - blockHeight));
  targetWidth = Math.min(targetWidth, Math.max(0, pageWidth - x));
  blockHeight = estimateBlockHeightPdf(targetWidth);
  y = Math.min(y, Math.max(0, pageHeight - blockHeight));
  return {
    page_index: pageIndex,
    x,
    y,
    target_width: targetWidth,
  };
}
</script>

<script setup lang="ts">
import * as pdfjsLib from "pdfjs-dist";
// @ts-expect-error Vite resolves the bundled pdf.js worker asset URL at build time.
import pdfjsWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

const MIN_ZOOM = 50;
const MAX_ZOOM = 300;
const ZOOM_STEP = 25;
const DEFAULT_ZOOM = 100;

const props = defineProps<{
  pdfUrl: string | null;
  placement: CanonicalPlacement;
  signatureImageUrl?: string | null;
  loading?: boolean;
  error?: boolean;
}>();

const emit = defineEmits<{
  "update:placement": [placement: CanonicalPlacement];
  rendered: [];
}>();

const { t } = useI18n();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const stageRef = ref<HTMLDivElement | null>(null);
const surfaceRef = ref<HTMLDivElement | null>(null);
const renderGeneration = { current: 0 };
const activeRenderTask = shallowRef<pdfjsLib.RenderTask | null>(null);
const pageCount = ref(0);
const pageWidthPdf = ref(0);
const pageHeightPdf = ref(0);
const currentViewport = shallowRef<PageViewport | null>(null);
const surfaceWidthPx = ref(0);
const surfaceHeightPx = ref(0);
const zoomPercent = ref(DEFAULT_ZOOM);
const fitMode = ref<"none" | "width">("none");
const renderError = ref(false);
const dragging = ref(false);
const resizing = ref(false);
const dragOffset = ref({ x: 0, y: 0 });

type PdfCacheEntry = {
  url: string;
  loadingTask: pdfjsLib.PDFDocumentLoadingTask;
  documentPromise: Promise<pdfjsLib.PDFDocumentProxy>;
};

let pdfDocumentCache: PdfCacheEntry | null = null;

function cancelActiveRender(): void {
  activeRenderTask.value?.cancel();
  activeRenderTask.value = null;
}

function destroyPdfCache(): void {
  if (pdfDocumentCache) {
    void pdfDocumentCache.loadingTask.destroy();
    pdfDocumentCache = null;
  }
}

async function acquirePdfDocument(
  url: string,
  generation: number,
): Promise<pdfjsLib.PDFDocumentProxy | null> {
  if (pdfDocumentCache?.url !== url) {
    destroyPdfCache();
    const loadingTask = pdfjsLib.getDocument({ url });
    pdfDocumentCache = {
      url,
      loadingTask,
      documentPromise: loadingTask.promise,
    };
  }
  const document = await pdfDocumentCache.documentPromise;
  if (generation !== renderGeneration.current) {
    return null;
  }
  return document;
}

const overlayStyle = computed(() => {
  const viewport = currentViewport.value;
  if (!viewport) {
    return null;
  }
  const rect = canonicalPlacementToViewportRect(viewport, props.placement);
  return {
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
  };
});

const signatureBackgroundStyle = computed(() => {
  if (props.signatureImageUrl) {
    return {
      backgroundImage: `url(${props.signatureImageUrl})`,
      backgroundSize: "contain",
      backgroundRepeat: "no-repeat",
      backgroundPosition: "center",
    };
  }
  return undefined;
});

function emitPlacement(next: CanonicalPlacement): void {
  const clamped = clampPlacementToPage(
    next,
    pageWidthPdf.value,
    pageHeightPdf.value,
    pageCount.value,
  );
  emit("update:placement", clamped);
}

function syncPlacementToLoadedPage(): void {
  if (pageWidthPdf.value <= 0 || pageHeightPdf.value <= 0 || pageCount.value <= 0) {
    return;
  }
  const clamped = clampPlacementToPage(
    props.placement,
    pageWidthPdf.value,
    pageHeightPdf.value,
    pageCount.value,
  );
  if (
    clamped.page_index !== props.placement.page_index ||
    clamped.x !== props.placement.x ||
    clamped.y !== props.placement.y ||
    clamped.target_width !== props.placement.target_width
  ) {
    emit("update:placement", clamped);
  }
}

async function renderCurrentPage(): Promise<void> {
  const url = props.pdfUrl?.trim();
  const canvas = canvasRef.value;
  if (!url || !canvas) {
    return;
  }
  const generation = ++renderGeneration.current;
  cancelActiveRender();
  renderError.value = false;

  try {
    const pdf = await acquirePdfDocument(url, generation);
    if (!pdf || generation !== renderGeneration.current) {
      return;
    }
    pageCount.value = pdf.numPages;
    const pageNumber = Math.min(Math.max(props.placement.page_index + 1, 1), pdf.numPages);
    const page = await pdf.getPage(pageNumber);
    if (generation !== renderGeneration.current) {
      return;
    }

    const unscaled = page.getViewport({ scale: 1, rotation: 0 });
    pageWidthPdf.value = unscaled.width;
    pageHeightPdf.value = unscaled.height;

    let scale = zoomPercent.value / 100;
    if (fitMode.value === "width" && stageRef.value) {
      const containerWidth = stageRef.value.clientWidth;
      if (containerWidth > 0) {
        scale = containerWidth / unscaled.width;
      }
    }
    const viewport = page.getViewport({ scale, rotation: 0 });
    currentViewport.value = viewport;
    surfaceWidthPx.value = viewport.width;
    surfaceHeightPx.value = viewport.height;

    const context = canvas.getContext("2d");
    if (!context) {
      renderError.value = true;
      return;
    }
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    const task = page.render({ canvasContext: context, viewport });
    activeRenderTask.value = task;
    await task.promise;
    if (generation !== renderGeneration.current) {
      return;
    }
    activeRenderTask.value = null;
    syncPlacementToLoadedPage();
    emit("rendered");
  } catch (cause) {
    if (generation !== renderGeneration.current) {
      return;
    }
    if (cause instanceof Error && cause.message.toLowerCase().includes("cancel")) {
      return;
    }
    renderError.value = true;
  }
}

function scheduleRender(): void {
  void nextTick(() => {
    void renderCurrentPage();
  });
}

function goToPage(pageIndex: number): void {
  const bounded = Math.min(Math.max(pageIndex, 0), Math.max(0, pageCount.value - 1));
  emitPlacement({ ...props.placement, page_index: bounded });
}

function onPreviousPage(): void {
  goToPage(props.placement.page_index - 1);
  fitMode.value = "none";
}

function onNextPage(): void {
  goToPage(props.placement.page_index + 1);
  fitMode.value = "none";
}

function onZoomIn(): void {
  fitMode.value = "none";
  zoomPercent.value = Math.min(zoomPercent.value + ZOOM_STEP, MAX_ZOOM);
}

function onZoomOut(): void {
  fitMode.value = "none";
  zoomPercent.value = Math.max(zoomPercent.value - ZOOM_STEP, MIN_ZOOM);
}

function onFitWidth(): void {
  fitMode.value = "width";
}

function pointerCoordsFromEvent(event: PointerEvent): { x: number; y: number } {
  const stage = stageRef.value;
  if (!stage) {
    return { x: 0, y: 0 };
  }
  return pointerToSurfaceCoords(stage, event);
}

function onBlockPointerDown(event: PointerEvent): void {
  if (!currentViewport.value) {
    return;
  }
  const target = event.target as HTMLElement;
  resizing.value = target.dataset.resizeHandle === "true";
  dragging.value = !resizing.value;
  const rect = canonicalPlacementToViewportRect(currentViewport.value, props.placement);
  const pointer = pointerCoordsFromEvent(event);
  dragOffset.value = {
    x: pointer.x - rect.left,
    y: pointer.y - rect.top,
  };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function onBlockPointerMove(event: PointerEvent): void {
  const viewport = currentViewport.value;
  if (!viewport || (!dragging.value && !resizing.value)) {
    return;
  }
  const pointer = pointerCoordsFromEvent(event);
  const currentRect = canonicalPlacementToViewportRect(viewport, props.placement);
  const aspectRatio = currentRect.height / Math.max(currentRect.width, 1);

  if (resizing.value) {
    const newWidth = Math.max(20, pointer.x - currentRect.left);
    const newHeight = newWidth * aspectRatio;
    const placement = viewportRectToCanonicalPlacement(
      viewport,
      currentRect.left,
      currentRect.top,
      newWidth,
      newHeight,
      props.placement.page_index,
    );
    emitPlacement(placement);
    return;
  }

  if (dragging.value) {
    const left = pointer.x - dragOffset.value.x;
    const top = pointer.y - dragOffset.value.y;
    const placement = viewportRectToCanonicalPlacement(
      viewport,
      left,
      top,
      currentRect.width,
      currentRect.height,
      props.placement.page_index,
    );
    emitPlacement(placement);
  }
}

function onBlockPointerUp(event: PointerEvent): void {
  dragging.value = false;
  resizing.value = false;
  (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
}

watch(
  () => [props.pdfUrl, props.placement.page_index, zoomPercent.value, fitMode.value] as const,
  () => {
    scheduleRender();
  },
);

watch(
  () => props.pdfUrl,
  (url, previous) => {
    if (url?.trim() !== previous?.trim()) {
      destroyPdfCache();
    }
  },
);

onMounted(() => {
  scheduleRender();
});

onUnmounted(() => {
  renderGeneration.current += 1;
  cancelActiveRender();
  destroyPdfCache();
});

defineExpose({
  destroyPdfCache,
  renderCurrentPage,
  pointerCoordsFromEvent,
  getZoomPercent: () => zoomPercent.value,
  setZoomPercent: (value: number) => {
    zoomPercent.value = value;
  },
});
</script>

<template>
  <section class="signature-placement-canvas" data-testid="signature-placement-canvas">
    <div class="signature-placement-canvas__toolbar" role="toolbar" :aria-label="t('signature.canvas.toolbar')">
      <v-btn size="small" variant="text" :disabled="placement.page_index <= 0" @click="onPreviousPage">
        {{ t("signature.canvas.prevPage") }}
      </v-btn>
      <span data-testid="signature-page-label">
        {{ t("signature.canvas.pageLabel", { page: placement.page_index + 1, total: pageCount || "?" }) }}
      </span>
      <v-btn
        size="small"
        variant="text"
        :disabled="pageCount === 0 || placement.page_index >= pageCount - 1"
        @click="onNextPage"
      >
        {{ t("signature.canvas.nextPage") }}
      </v-btn>
      <v-btn size="small" variant="text" @click="onZoomOut">{{ t("signature.canvas.zoomOut") }}</v-btn>
      <span data-testid="signature-zoom-label">{{ zoomPercent }}%</span>
      <v-btn size="small" variant="text" @click="onZoomIn">{{ t("signature.canvas.zoomIn") }}</v-btn>
      <v-btn size="small" variant="text" @click="onFitWidth">{{ t("signature.canvas.fitWidth") }}</v-btn>
    </div>

    <p v-if="loading" role="status">{{ t("signature.canvas.loading") }}</p>
    <p v-else-if="error || renderError" role="alert">{{ t("signature.canvas.loadError") }}</p>
    <p v-else-if="!pdfUrl" role="status">{{ t("signature.canvas.empty") }}</p>

    <div v-else ref="stageRef" class="signature-placement-canvas__stage" data-testid="signature-canvas-stage">
      <div
        ref="surfaceRef"
        class="signature-placement-canvas__surface"
        :style="{ width: `${surfaceWidthPx}px`, height: `${surfaceHeightPx}px` }"
      >
        <canvas ref="canvasRef" class="signature-placement-canvas__pdf" data-testid="signature-pdf-canvas" />
        <div class="signature-placement-canvas__overlay">
          <div
            v-if="overlayStyle"
            class="signature-placement-canvas__block"
            :style="[overlayStyle, signatureBackgroundStyle]"
            data-testid="signature-placement-block"
            @pointerdown="onBlockPointerDown"
            @pointermove="onBlockPointerMove"
            @pointerup="onBlockPointerUp"
            @pointercancel="onBlockPointerUp"
          >
            <span v-if="!signatureImageUrl" class="signature-placement-canvas__placeholder">
              {{ t("signature.canvas.placeholder") }}
            </span>
            <span
              class="signature-placement-canvas__resize-handle"
              data-resize-handle="true"
              data-testid="signature-resize-handle"
            />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.signature-placement-canvas {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.signature-placement-canvas__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.signature-placement-canvas__stage {
  position: relative;
  max-width: 100%;
  overflow: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

.signature-placement-canvas__surface {
  position: relative;
}

.signature-placement-canvas__pdf {
  display: block;
}

.signature-placement-canvas__overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.signature-placement-canvas__block {
  position: absolute;
  border: 2px dashed rgba(25, 118, 210, 0.9);
  background-color: rgba(25, 118, 210, 0.08);
  pointer-events: auto;
  cursor: move;
  display: flex;
  align-items: center;
  justify-content: center;
}

.signature-placement-canvas__placeholder {
  font-size: 0.75rem;
  color: rgba(0, 0, 0, 0.6);
  text-align: center;
  padding: 0.25rem;
}

.signature-placement-canvas__resize-handle {
  position: absolute;
  right: -4px;
  bottom: -4px;
  width: 12px;
  height: 12px;
  background: rgb(25, 118, 210);
  cursor: se-resize;
  pointer-events: auto;
}
</style>
