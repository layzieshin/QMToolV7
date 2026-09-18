<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useBootstrapState } from "../state/bootstrap";

const MODULE_ROUTE_NAMES: Record<string, string> = {
  documents: "documents",
};

const MODULE_LABEL_KEYS: Record<string, string> = {
  documents: "modules.documents.label",
};

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const bootstrap = useBootstrapState();

const items = computed(() =>
  bootstrap.modules
    .filter((module) => module.licensed && module.authorized)
    .map((module) => {
      const routeName = MODULE_ROUTE_NAMES[module.id];
      if (!routeName || !router.hasRoute(routeName)) {
        return null;
      }
      const labelKey = MODULE_LABEL_KEYS[module.id];
      if (!labelKey) {
        return null;
      }
      return {
        routeName,
        label: t(labelKey),
        active: route.name === routeName,
      };
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null),
);
</script>

<template>
  <nav
    v-if="items.length > 0"
    class="module-navigation"
    data-testid="module-navigation"
    :aria-label="t('modules.navigationLabel')"
  >
    <v-list density="compact" nav>
      <v-list-item
        v-for="item in items"
        :key="item.routeName"
        :to="{ name: item.routeName }"
        :active="item.active"
        :title="item.label"
        data-testid="module-navigation-item"
      />
    </v-list>
  </nav>
</template>

<style scoped>
.module-navigation {
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  min-width: 12rem;
  padding-right: 0.5rem;
}
</style>
