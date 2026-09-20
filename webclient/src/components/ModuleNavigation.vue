<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useBootstrapState } from "../state/bootstrap";

const ADMIN_USERS_CAPABILITY = "usermanagement.can_administer_users";

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

const moduleItems = computed(() =>
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

const showAdminUsers = computed(() => {
  const usermanagement = bootstrap.modules.find((module) => module.id === "usermanagement");
  if (!usermanagement?.licensed) {
    return false;
  }
  return (usermanagement.capabilities ?? []).includes(ADMIN_USERS_CAPABILITY);
});

const adminUsersActive = computed(
  () => route.name === "admin-users" || route.name === "admin-user-detail",
);

const showAnyNavigation = computed(
  () => moduleItems.value.length > 0 || showAdminUsers.value,
);
</script>

<template>
  <div
    v-if="showAnyNavigation"
    class="module-navigation-stack"
    data-testid="module-navigation-stack"
  >
    <nav
      v-if="moduleItems.length > 0"
      class="module-navigation"
      data-testid="module-navigation"
      :aria-label="t('modules.navigationLabel')"
    >
      <v-list density="compact" nav>
        <v-list-item
          v-for="item in moduleItems"
          :key="item.routeName"
          :to="{ name: item.routeName }"
          :active="item.active"
          :title="item.label"
          data-testid="module-navigation-item"
        />
      </v-list>
    </nav>

    <nav
      v-if="showAdminUsers"
      class="admin-navigation"
      data-testid="admin-navigation"
      :aria-label="t('admin.navigationLabel')"
    >
      <p class="admin-navigation__heading text-caption text-medium-emphasis">
        {{ t("admin.navigationLabel") }}
      </p>
      <v-list density="compact" nav>
        <v-list-item
          :to="{ name: 'admin-users' }"
          :active="adminUsersActive"
          :title="t('admin.users.label')"
          data-testid="admin-navigation-users"
        />
      </v-list>
    </nav>
  </div>
</template>

<style scoped>
.module-navigation-stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 12rem;
  padding-right: 0.5rem;
}

.module-navigation,
.admin-navigation {
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}

.admin-navigation__heading {
  margin: 0 0 0.25rem 0.75rem;
}
</style>
