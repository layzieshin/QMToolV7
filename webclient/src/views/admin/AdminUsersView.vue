<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { RouterLink } from "vue-router";

import {
  ApiTransportError,
  fetchAdminUsers,
  type UserAccessResponse,
} from "../../api/client";

defineOptions({
  name: "AdminUsersView",
});

const { t } = useI18n();

const users = ref<UserAccessResponse[]>([]);
const loading = ref(true);
const errorKey = ref<string | null>(null);
const forbidden = ref(false);
const loadGeneration = { current: 0 };
let mounted = false;

function mapLoadError(cause: unknown): string {
  if (cause instanceof ApiTransportError) {
    switch (cause.status) {
      case 401:
        return t("api.errors.unauthorized");
      case 403:
        forbidden.value = true;
        return t("admin.users.errors.forbidden");
      default:
        return t("admin.users.errors.load");
    }
  }
  return t("admin.users.errors.load");
}

function roleLabel(role: string): string {
  const key = `admin.users.roles.${role}` as const;
  if (t(key) !== key) {
    return t(key);
  }
  return t("admin.users.roles.unknown");
}

async function reload(): Promise<void> {
  const generation = ++loadGeneration.current;
  loading.value = true;
  errorKey.value = null;
  forbidden.value = false;
  try {
    const rows = await fetchAdminUsers();
    if (!mounted || generation !== loadGeneration.current) {
      return;
    }
    users.value = rows;
  } catch (cause) {
    if (!mounted || generation !== loadGeneration.current) {
      return;
    }
    users.value = [];
    errorKey.value = mapLoadError(cause);
  } finally {
    if (mounted && generation === loadGeneration.current) {
      loading.value = false;
    }
  }
}

const showEmpty = computed(() => !loading.value && !errorKey.value && users.value.length === 0);

onMounted(() => {
  mounted = true;
  void reload();
});

onUnmounted(() => {
  mounted = false;
  loadGeneration.current += 1;
});
</script>

<template>
  <section class="admin-users-view" data-testid="admin-users-view">
    <header class="admin-users-view__header">
      <h1 class="text-h5">{{ t("admin.users.title") }}</h1>
      <p class="text-body-2 text-medium-emphasis">{{ t("admin.users.listHint") }}</p>
    </header>

    <v-alert
      v-if="errorKey"
      type="error"
      variant="tonal"
      role="alert"
      data-testid="admin-users-error"
      class="mb-4"
    >
      {{ errorKey }}
      <template #append>
        <div class="admin-users-view__error-actions">
          <v-btn
            v-if="forbidden"
            variant="text"
            :to="{ name: 'home' }"
            data-testid="admin-users-back-home"
          >
            {{ t("admin.users.backToHome") }}
          </v-btn>
          <v-btn variant="text" data-testid="admin-users-retry" @click="reload">
            {{ t("admin.users.retry") }}
          </v-btn>
        </div>
      </template>
    </v-alert>

    <div v-if="loading" data-testid="admin-users-loading" role="status">
      <v-skeleton-loader type="table-heading, table-row@5" />
    </div>

    <v-alert
      v-else-if="showEmpty"
      type="info"
      variant="tonal"
      data-testid="admin-users-empty"
      role="status"
    >
      {{ t("admin.users.empty") }}
    </v-alert>

    <div v-else-if="!errorKey" class="admin-users-view__table-wrap">
      <v-table density="comfortable" data-testid="admin-users-table">
        <thead>
          <tr>
            <th scope="col">{{ t("admin.users.columns.username") }}</th>
            <th scope="col">{{ t("admin.users.columns.role") }}</th>
            <th scope="col">{{ t("admin.users.columns.active") }}</th>
            <th scope="col">{{ t("admin.users.columns.qmb") }}</th>
            <th scope="col">{{ t("admin.users.columns.password") }}</th>
          </tr>
        </thead>
        <tbody>
          <RouterLink
            v-for="user in users"
            :key="user.user_id"
            v-slot="{ href, navigate }"
            :to="{ name: 'admin-user-detail', params: { username: user.username } }"
            custom
          >
            <tr class="admin-users-view__row" data-testid="admin-users-row">
              <td>
                <a
                  :href="href"
                  class="admin-users-view__row-link"
                  data-testid="admin-users-row-link"
                  @click="navigate"
                >
                  {{ user.username }}
                </a>
              </td>
              <td>{{ roleLabel(user.role) }}</td>
              <td>
                <v-chip
                  size="small"
                  :color="user.is_active ? 'success' : 'default'"
                  variant="tonal"
                >
                  {{
                    user.is_active
                      ? t("admin.users.status.active")
                      : t("admin.users.status.inactive")
                  }}
                </v-chip>
              </td>
              <td>
                {{
                  user.is_qmb ? t("admin.users.status.yes") : t("admin.users.status.no")
                }}
              </td>
              <td>
                <v-chip
                  v-if="user.must_change_password"
                  size="small"
                  color="warning"
                  variant="tonal"
                >
                  {{ t("admin.users.status.mustChangePassword") }}
                </v-chip>
                <span v-else>{{ t("admin.users.status.no") }}</span>
              </td>
            </tr>
          </RouterLink>
        </tbody>
      </v-table>
    </div>
  </section>
</template>

<style scoped>
.admin-users-view__header {
  margin-bottom: 1rem;
}

.admin-users-view__table-wrap {
  overflow-x: auto;
}

.admin-users-view__row-link {
  color: inherit;
  text-decoration: none;
  font-weight: 500;
}

.admin-users-view__row-link:hover,
.admin-users-view__row-link:focus-visible {
  text-decoration: underline;
}

.admin-users-view__row:hover {
  background: rgba(0, 0, 0, 0.04);
}

.admin-users-view__error-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

@media (max-width: 960px) {
  .admin-users-view__header h1 {
    font-size: 1.25rem;
  }
}
</style>
