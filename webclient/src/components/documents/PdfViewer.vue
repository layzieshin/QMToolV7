<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

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

const iframeSrc = computed(() => {
  if (!props.previewUrl) {
    return null;
  }
  const hashParts: string[] = [`page=${currentPage.value}`];
  if (fitMode.value === "width") {
    hashParts.push("view=FitH");
  } else if (fitMode.value === "page") {
    hashParts.push("view=Fit");
  } else {
    hashParts.push(`zoom=${zoomPercent.value}`);
  }
  return `${props.previewUrl}#${hashParts.join("&")}`;
});

watch(currentPage, (page) => {
  emit("page-change", page);
});

function goToPreviousPage(): void {
  if (currentPage.value > MIN_PAGE) {
    currentPage.value -= 1;
    fitMode.value = "none";
  }
}

function goToNextPage(): void {
  currentPage.value += 1;
  fitMode.value = "none";
}

function onPageInput(event: Event): void {
  const raw = (event.target as HTMLInputElement).value.trim();
  const parsed = Number.parseInt(raw, 10);
  if (Number.isInteger(parsed) && parsed >= MIN_PAGE) {
    currentPage.value = parsed;
    fitMode.value = "none";
  }
}

function zoomIn(): void {
  fitMode.value = "none";
  zoomPercent.value = Math.min(MAX_ZOOM, zoomPercent.value + ZOOM_STEP);
}

function zoomOut(): void {
  fitMode.value = "none";
  zoomPercent.value = Math.max(MIN_ZOOM, zoomPercent.value - ZOOM_STEP);
}

function fitWidth(): void {
  fitMode.value = "width";
}

function fitPage(): void {
  fitMode.value = "page";
}

watch(
  () => props.previewUrl,
  () => {
    currentPage.value = MIN_PAGE;
    zoomPercent.value = DEFAULT_ZOOM;
    fitMode.value = "none";
  },
);
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
        @click="goToPreviousPage"
      >
        {{ t("documents.viewer.pdf.prevPage") }}
      </v-btn>
      <label class="pdf-viewer__page-label">
        <span class="sr-only">{{ t("documents.viewer.pdf.currentPage") }}</span>
        <input
          type="number"
          min="1"
          :value="currentPage"
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
        {{ zoomPercent }}%
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
    <div v-else-if="iframeSrc" class="pdf-viewer__frame-wrap">
      <iframe
        :key="iframeSrc"
        :src="iframeSrc"
        class="pdf-viewer__frame"
        data-testid="pdf-viewer-frame"
        :title="t('documents.viewer.pdf.frameTitle')"
      />
    </div>
    <p v-else data-testid="pdf-viewer-empty">
      {{ t("documents.viewer.pdf.empty") }}
    </p>
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

.pdf-viewer__frame-wrap {
  flex: 1;
  min-height: 20rem;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

.pdf-viewer__frame {
  width: 100%;
  height: 100%;
  min-height: 20rem;
  border: 0;
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
