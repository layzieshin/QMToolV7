<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import { artifactDownloadUrl, type DocumentArtifactModel, type VersionStateResponse } from "../../api/client";
import PdfViewer from "./PdfViewer.vue";
import { usePdfPreview } from "../../composables/usePdfPreview";

const RELEASED_TYPE = "RELEASED_PDF";
const SIGNED_TYPE = "SIGNED_PDF";
const SOURCE_TYPE = "SOURCE_PDF";

const props = defineProps<{
  detail: VersionStateResponse | null;
  artifacts: DocumentArtifactModel[];
  signedSuccess?: boolean;
  artifactsUnknown?: boolean;
  artifactRefreshError?: string | null;
}>();

const emit = defineEmits<{
  retryArtifacts: [];
}>();

const { t } = useI18n();
const currentPage = ref(1);

const artifactsAuthoritative = computed(
  () => !props.artifactsUnknown && !props.artifactRefreshError,
);

const previewEnabled = computed(() =>
  (props.detail?.allowed_actions ?? []).some(
    (action) => action.code === "preview" && action.enabled,
  ),
);

const downloadEnabled = computed(() =>
  (props.detail?.allowed_actions ?? []).some(
    (action) => action.code === "download" && action.enabled,
  ),
);

const authoritativeArtifacts = computed(() =>
  artifactsAuthoritative.value ? props.artifacts : [],
);

const releasedArtifact = computed(() =>
  authoritativeArtifacts.value.find(
    (artifact) => artifact.artifact_type === RELEASED_TYPE && artifact.is_current,
  ) ?? null,
);

const showDownload = computed(
  () =>
    artifactsAuthoritative.value &&
    Boolean(releasedArtifact.value) &&
    downloadEnabled.value,
);

const downloadHref = computed(() => {
  const artifact = releasedArtifact.value;
  return artifact ? artifactDownloadUrl(artifact.artifact_id) : null;
});

const signedArtifact = computed(() =>
  authoritativeArtifacts.value.find(
    (artifact) => artifact.artifact_type === SIGNED_TYPE && artifact.is_current,
  ) ?? null,
);

const sourceArtifact = computed(() =>
  authoritativeArtifacts.value.find(
    (artifact) => artifact.artifact_type === SOURCE_TYPE && artifact.is_current,
  ) ?? null,
);

const previewArtifactId = computed(() => {
  if (!artifactsAuthoritative.value || !previewEnabled.value || !releasedArtifact.value) {
    return null;
  }
  return releasedArtifact.value.artifact_id;
});

const { previewUrl, loading, error } = usePdfPreview(previewArtifactId);

function artifactLabel(type: string): string {
  switch (type) {
    case RELEASED_TYPE:
      return t("signature.released.typeReleased");
    case SIGNED_TYPE:
      return t("signature.released.typeSigned");
    case SOURCE_TYPE:
      return t("signature.released.typeSource");
    default:
      return type;
  }
}
</script>

<template>
  <section class="released-artifact-panel" data-testid="released-artifact-panel">
    <h3>{{ t("signature.released.title") }}</h3>

    <p v-if="signedSuccess" role="status" data-testid="signed-success-message">
      {{ t("signature.workspace.success") }}
    </p>

    <p
      v-if="artifactRefreshError"
      role="alert"
      data-testid="artifact-refresh-error"
    >
      {{ artifactRefreshError }}
      <v-btn
        size="small"
        variant="text"
        data-testid="artifact-refresh-retry"
        @click="emit('retryArtifacts')"
      >
        {{ t("signature.released.retryArtifacts") }}
      </v-btn>
    </p>

    <p
      v-else-if="signedSuccess && artifactsUnknown"
      role="status"
      data-testid="artifacts-unknown"
    >
      {{ t("signature.released.artifactsUnknown") }}
    </p>

    <p
      v-else-if="signedSuccess && artifactsAuthoritative && !releasedArtifact"
      role="status"
      data-testid="signed-without-release"
    >
      {{ t("signature.released.signedWithoutRelease") }}
    </p>

    <ul
      v-if="artifactsAuthoritative"
      class="released-artifact-panel__list"
      data-testid="artifact-type-list"
    >
      <li v-if="sourceArtifact">
        {{ artifactLabel(SOURCE_TYPE) }} — v{{ sourceArtifact.version }}
      </li>
      <li v-if="signedArtifact">
        {{ artifactLabel(SIGNED_TYPE) }} — v{{ signedArtifact.version }}
      </li>
      <li v-if="releasedArtifact" data-testid="released-artifact-entry">
        {{ artifactLabel(RELEASED_TYPE) }} — v{{ releasedArtifact.version }}
        <span class="released-artifact-panel__immutable">{{ t("signature.released.immutable") }}</span>
        <a
          v-if="showDownload && downloadHref"
          :href="downloadHref"
          class="released-artifact-panel__download"
          data-testid="released-artifact-download"
        >
          {{ t("documents.action.download") }}
        </a>
      </li>
    </ul>

    <p
      v-if="artifactsAuthoritative && releasedArtifact && !previewEnabled"
      role="status"
      data-testid="released-preview-unavailable"
    >
      {{ t("signature.released.previewUnavailable") }}
    </p>

    <div
      v-if="artifactsAuthoritative && releasedArtifact && previewEnabled"
      class="released-artifact-panel__preview"
      data-testid="released-artifact-preview"
    >
      <PdfViewer
        :preview-url="previewUrl"
        :loading="loading"
        :error="Boolean(error)"
        @page-change="(page: number) => { currentPage = page; }"
      />
    </div>
  </section>
</template>

<style scoped>
.released-artifact-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.released-artifact-panel__list {
  margin: 0;
  padding-left: 1.25rem;
}

.released-artifact-panel__immutable {
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.6);
}

.released-artifact-panel__download {
  margin-left: 0.5rem;
}
</style>
