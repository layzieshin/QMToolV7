<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { ActionDescriptor } from "../actions/actionTypes";
import {
  actionButtonColor,
  isActionInteractive,
  resolveActionAccessibleTitle,
  resolveActionLabel,
} from "../actions/actionTypes";

const props = defineProps<{
  descriptor: ActionDescriptor;
  supported: boolean;
}>();

const emit = defineEmits<{
  action: [descriptor: ActionDescriptor];
}>();

const { t } = useI18n();

const label = computed(() =>
  resolveActionLabel(props.descriptor, t, t("actions.genericLabel")),
);

const accessibleTitle = computed(() =>
  resolveActionAccessibleTitle(props.descriptor, t, label.value, props.supported),
);

const interactive = computed(() => isActionInteractive(props.descriptor, props.supported));

const color = computed(() => actionButtonColor(props.descriptor));

function onClick(): void {
  if (!interactive.value) {
    return;
  }
  emit("action", props.descriptor);
}
</script>

<template>
  <v-btn
    v-if="!descriptor.destructive"
    type="button"
    variant="flat"
    :color="color"
    :disabled="!interactive"
    :title="accessibleTitle"
    :aria-label="accessibleTitle"
    @click="onClick"
  >
    {{ label }}
  </v-btn>
</template>
