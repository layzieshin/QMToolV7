<script setup lang="ts">
import { useI18n } from "vue-i18n";

const props = defineProps<{
  modelValue: boolean;
  loading?: boolean;
  reloadFailed?: boolean;
  showingLocalInput?: boolean;
  actionLabel?: string | null;
  preservedReason?: string | null;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  loadServerState: [];
  viewLocalInput: [];
  cancel: [];
}>();

const { t } = useI18n();

function close(): void {
  emit("update:modelValue", false);
  emit("cancel");
}

function onLoadServerState(): void {
  if (props.loading) {
    return;
  }
  emit("loadServerState");
}

function onViewLocalInput(): void {
  if (props.loading) {
    return;
  }
  emit("viewLocalInput");
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    persistent
    max-width="520"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card data-testid="conflict-dialog">
      <v-card-title>{{ t("conflict.title") }}</v-card-title>
      <v-card-text>
        <p>{{ t("conflict.message") }}</p>
        <p
          v-if="reloadFailed"
          role="alert"
          data-testid="conflict-reload-error"
        >
          {{ t("conflict.reloadError") }}
        </p>
        <section
          v-if="showingLocalInput"
          class="conflict-local-input"
          data-testid="conflict-local-input"
        >
          <h4>{{ t("conflict.localInputTitle") }}</h4>
          <p v-if="actionLabel" data-testid="conflict-local-action">
            <strong>{{ t("conflict.localInputAction") }}:</strong> {{ actionLabel }}
          </p>
          <p v-if="preservedReason" data-testid="conflict-local-reason">
            <strong>{{ t("conflict.localInputReason") }}:</strong> {{ preservedReason }}
          </p>
        </section>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          data-testid="conflict-cancel"
          :disabled="loading"
          @click="close"
        >
          {{ t("conflict.cancel") }}
        </v-btn>
        <v-btn
          variant="outlined"
          data-testid="conflict-view-local"
          :disabled="loading"
          @click="onViewLocalInput"
        >
          {{ t("conflict.viewLocalInput") }}
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          data-testid="conflict-load-server"
          :loading="loading"
          @click="onLoadServerState"
        >
          {{ t("conflict.loadServerState") }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.conflict-local-input {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.conflict-local-input h4 {
  margin: 0 0 0.5rem;
}
</style>
