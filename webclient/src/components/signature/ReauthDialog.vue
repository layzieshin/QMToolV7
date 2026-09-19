<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  modelValue: boolean;
  loading?: boolean;
  errorMessage?: string | null;
}>();

const emit = defineEmits<{
  "update:modelValue": [open: boolean];
  submit: [password: string];
  cancel: [];
}>();

const { t } = useI18n();
const password = ref("");

const canSubmit = computed(() => password.value.trim().length > 0);

function clearPassword(): void {
  password.value = "";
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      clearPassword();
    }
  },
);

watch(
  () => props.errorMessage,
  (message) => {
    if (message) {
      clearPassword();
    }
  },
);

watch(
  () => props.loading,
  (loading, wasLoading) => {
    if (wasLoading && !loading && !props.errorMessage) {
      clearPassword();
    }
  },
);

onUnmounted(() => {
  clearPassword();
});

function closeDialog(): void {
  clearPassword();
  emit("update:modelValue", false);
}

function onCancel(): void {
  closeDialog();
  emit("cancel");
}

function onSubmit(): void {
  const trimmed = password.value.trim();
  if (!trimmed || props.loading) {
    return;
  }
  emit("submit", trimmed);
  clearPassword();
}

function onEnter(): void {
  if (canSubmit.value) {
    onSubmit();
  }
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="440"
    persistent
    data-testid="reauth-dialog"
    @update:model-value="(open: boolean) => { if (!open) onCancel(); else emit('update:modelValue', open); }"
  >
    <v-card>
      <v-card-title>{{ t("signature.reauth.title") }}</v-card-title>
      <v-card-text>
        <p>{{ t("signature.reauth.hint") }}</p>
        <v-text-field
          v-model="password"
          type="password"
          autocomplete="off"
          :label="t('signature.reauth.password')"
          :disabled="loading"
          data-testid="reauth-password"
          @keyup.enter="onEnter"
        />
        <p
          v-if="errorMessage"
          role="alert"
          class="reauth-dialog__error"
          data-testid="reauth-error"
        >
          {{ errorMessage }}
        </p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="loading" data-testid="reauth-cancel" @click="onCancel">
          {{ t("conflict.cancel") }}
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="loading"
          :disabled="!canSubmit || loading"
          data-testid="reauth-submit"
          @click="onSubmit"
        >
          {{ t("signature.reauth.submit") }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.reauth-dialog__error {
  color: rgb(var(--v-theme-error));
  margin-top: 0.5rem;
}
</style>
