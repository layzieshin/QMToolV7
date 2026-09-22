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

const props = withDefaults(
  defineProps<{
    actions: ActionDescriptor[];
    supportedCodes: readonly string[];
    productWritesAllowed?: boolean;
    productWritesBlockedMessage?: string;
  }>(),
  {
    productWritesAllowed: true,
    productWritesBlockedMessage: undefined,
  },
);

const emit = defineEmits<{
  action: [descriptor: ActionDescriptor];
}>();

const { t } = useI18n();

const supportedSet = computed(() => new Set(props.supportedCodes));

const menuActions = computed(() => props.actions.filter((action) => action.destructive));

function isSupported(code: string): boolean {
  return supportedSet.value.has(code);
}

function itemLabel(descriptor: ActionDescriptor): string {
  return resolveActionLabel(descriptor, t, t("actions.genericLabel"));
}

function itemTitle(descriptor: ActionDescriptor): string {
  return resolveActionAccessibleTitle(
    descriptor,
    t,
    itemLabel(descriptor),
    isSupported(descriptor.code),
    props.productWritesAllowed,
    props.productWritesBlockedMessage,
  );
}

function itemColor(descriptor: ActionDescriptor): string | undefined {
  if (!descriptor.destructive && descriptor.severity !== "danger") {
    return undefined;
  }
  return actionButtonColor(descriptor);
}

function onSelect(descriptor: ActionDescriptor): void {
  if (!isActionInteractive(descriptor, isSupported(descriptor.code), props.productWritesAllowed)) {
    return;
  }
  emit("action", descriptor);
}
</script>

<template>
  <v-menu v-if="menuActions.length > 0">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        type="button"
        variant="text"
        icon="mdi-dots-vertical"
        :aria-label="t('actions.overflowMenu')"
      />
    </template>
    <v-list density="compact">
      <v-list-item
        v-for="action in menuActions"
        :key="action.code"
        :title="itemLabel(action)"
        :subtitle="action.enabled ? undefined : action.disabled_reason || t('actions.disabled')"
        :disabled="!isActionInteractive(action, isSupported(action.code), productWritesAllowed)"
        :aria-label="itemTitle(action)"
        :base-color="itemColor(action)"
        @click="onSelect(action)"
      />
    </v-list>
  </v-menu>
</template>
