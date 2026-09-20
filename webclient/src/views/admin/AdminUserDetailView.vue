<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
} from "vue-router";

import {
  ApiTransportError,
  encodeAdminUsernamePathSegment,
  fetchAdminUser,
  type UserAccessResponse,
} from "../../api/client";
import { mutationErrorI18nKey } from "../../api/errors";
import { MutationClientError, mutate } from "../../api/mutationClient";
import { useBootstrapState } from "../../state/bootstrap";

defineOptions({
  name: "AdminUserDetailView",
});

const ROLE_OPTIONS = ["User", "Admin", "QMB"] as const;

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const bootstrap = useBootstrapState();

const user = ref<UserAccessResponse | null>(null);
const loading = ref(true);
const errorKey = ref<string | null>(null);
const editMode = ref(false);
const savingAccess = ref(false);
const accessError = ref<string | null>(null);
const accessFieldErrors = ref<Record<string, string>>({});

const passwordValue = ref("");
const passwordSaving = ref(false);
const passwordError = ref<string | null>(null);
const passwordFieldErrors = ref<Record<string, string>>({});

const draftRole = ref<string>("User");
const draftIsActive = ref(true);
const draftIsQmb = ref(false);

const discardDialogOpen = ref(false);
let pendingNavigation: (() => void) | null = null;
let pendingRouteConfirmation: ((allow: boolean) => void) | null = null;

const loadGeneration = { current: 0 };
const accessOperationGeneration = { current: 0 };
let mounted = false;

const username = computed(() => String(route.params.username ?? ""));
const writesEnabled = computed(() => bootstrap.writesAllowed);

const isAccessDirty = computed(() => {
  if (!user.value || !editMode.value) {
    return false;
  }
  return (
    draftRole.value !== user.value.role ||
    draftIsActive.value !== user.value.is_active ||
    draftIsQmb.value !== user.value.is_qmb
  );
});

function mapLoadError(cause: unknown): string {
  if (cause instanceof ApiTransportError) {
    switch (cause.status) {
      case 401:
        return t("api.errors.unauthorized");
      case 403:
        return t("admin.users.errors.forbidden");
      case 404:
        return t("admin.users.errors.notFound");
      default:
        return t("admin.users.errors.detailLoad");
    }
  }
  return t("admin.users.errors.detailLoad");
}

function roleLabel(role: string): string {
  const key = `admin.users.roles.${role}` as const;
  if (t(key) !== key) {
    return t(key);
  }
  return t("admin.users.roles.unknown");
}

function applyUserToDraft(current: UserAccessResponse): void {
  draftRole.value = current.role;
  draftIsActive.value = current.is_active;
  draftIsQmb.value = current.is_qmb;
}

function isDetailLoadStillCurrent(
  generation: number,
  targetUsername: string,
): boolean {
  return (
    mounted &&
    generation === loadGeneration.current &&
    username.value === targetUsername
  );
}

function invalidateAccessOperations(): void {
  accessOperationGeneration.current += 1;
  savingAccess.value = false;
}

function isAccessOperationStillCurrent(
  operationId: number,
  targetUsername: string,
  loadGenerationAtStart: number,
): boolean {
  return (
    mounted &&
    operationId === accessOperationGeneration.current &&
    loadGenerationAtStart === loadGeneration.current &&
    username.value === targetUsername
  );
}

async function loadDetail(targetUsername: string): Promise<UserAccessResponse> {
  return fetchAdminUser(targetUsername);
}

async function reload(): Promise<void> {
  const targetUsername = username.value;
  const generation = ++loadGeneration.current;
  invalidateAccessOperations();
  loading.value = true;
  errorKey.value = null;
  editMode.value = false;
  accessError.value = null;
  accessFieldErrors.value = {};
  passwordError.value = null;
  passwordFieldErrors.value = {};
  passwordValue.value = "";
  discardDialogOpen.value = false;
  pendingNavigation = null;

  try {
    const detail = await loadDetail(targetUsername);
    if (!isDetailLoadStillCurrent(generation, targetUsername)) {
      return;
    }
    user.value = detail;
    applyUserToDraft(detail);
  } catch (cause) {
    if (!isDetailLoadStillCurrent(generation, targetUsername)) {
      return;
    }
    user.value = null;
    errorKey.value = mapLoadError(cause);
  } finally {
    if (isDetailLoadStillCurrent(generation, targetUsername)) {
      loading.value = false;
    }
  }
}

async function refreshDetailOnly(): Promise<void> {
  if (!user.value) {
    return;
  }
  const targetUsername = username.value;
  const generation = loadGeneration.current;
  try {
    const detail = await loadDetail(targetUsername);
    if (!isDetailLoadStillCurrent(generation, targetUsername)) {
      return;
    }
    user.value = detail;
    applyUserToDraft(detail);
  } catch {
    if (!isDetailLoadStillCurrent(generation, targetUsername)) {
      return;
    }
  }
}

function mapMutationError(cause: unknown): string {
  if (cause instanceof MutationClientError) {
    if (cause.errorCode === "last_active_admin") {
      return t("admin.users.errors.lastActiveAdmin");
    }
    return t(mutationErrorI18nKey(cause.kind));
  }
  return t("admin.users.errors.save");
}

function applyFieldErrors(
  cause: unknown,
  target: { value: Record<string, string> },
): void {
  target.value = {};
  if (!(cause instanceof MutationClientError)) {
    return;
  }
  for (const item of cause.fieldErrors) {
    if (item.field) {
      target.value[item.field] = item.message;
    }
  }
}

function requestDiscard(onConfirm: () => void): void {
  if (!isAccessDirty.value) {
    onConfirm();
    return;
  }
  pendingNavigation = onConfirm;
  discardDialogOpen.value = true;
}

function keepEditing(): void {
  discardDialogOpen.value = false;
  pendingNavigation = null;
  pendingRouteConfirmation?.(false);
  pendingRouteConfirmation = null;
}

function discardChanges(): void {
  discardDialogOpen.value = false;
  if (user.value) {
    applyUserToDraft(user.value);
  }
  editMode.value = false;
  accessError.value = null;
  accessFieldErrors.value = {};
  const resume = pendingNavigation;
  const confirmRoute = pendingRouteConfirmation;
  pendingNavigation = null;
  pendingRouteConfirmation = null;
  if (confirmRoute) {
    confirmRoute(true);
    return;
  }
  resume?.();
}

function confirmDirtyNavigation(): boolean | Promise<boolean> {
  if (!isAccessDirty.value) {
    return true;
  }
  return new Promise<boolean>((resolve) => {
    pendingRouteConfirmation = resolve;
    discardDialogOpen.value = true;
  });
}

function enterEditMode(): void {
  if (!user.value || !writesEnabled.value) {
    return;
  }
  applyUserToDraft(user.value);
  accessError.value = null;
  accessFieldErrors.value = {};
  editMode.value = true;
}

function cancelEditMode(): void {
  requestDiscard(() => {
    if (user.value) {
      applyUserToDraft(user.value);
    }
    accessError.value = null;
    accessFieldErrors.value = {};
    editMode.value = false;
  });
}

async function saveAccess(): Promise<void> {
  if (!user.value || savingAccess.value || !writesEnabled.value) {
    return;
  }
  const targetUsername = user.value.username;
  const loadGenerationAtStart = loadGeneration.current;
  const operationId = ++accessOperationGeneration.current;
  savingAccess.value = true;
  accessError.value = null;
  accessFieldErrors.value = {};
  try {
    const updated = await mutate<UserAccessResponse>({
      method: "PATCH",
      path: `/users/${encodeAdminUsernamePathSegment(targetUsername)}/access`,
      body: {
        json: {
          role: draftRole.value,
          is_active: draftIsActive.value,
          is_qmb: draftIsQmb.value,
        },
      },
    });
    if (!isAccessOperationStillCurrent(operationId, targetUsername, loadGenerationAtStart)) {
      return;
    }
    if (updated) {
      user.value = updated;
      applyUserToDraft(updated);
    }
    editMode.value = false;
  } catch (cause) {
    if (!isAccessOperationStillCurrent(operationId, targetUsername, loadGenerationAtStart)) {
      return;
    }
    accessError.value = mapMutationError(cause);
    applyFieldErrors(cause, accessFieldErrors);
  } finally {
    if (isAccessOperationStillCurrent(operationId, targetUsername, loadGenerationAtStart)) {
      savingAccess.value = false;
    }
  }
}

async function submitPasswordAction(): Promise<void> {
  if (!user.value || passwordSaving.value || !writesEnabled.value) {
    return;
  }
  passwordSaving.value = true;
  passwordError.value = null;
  passwordFieldErrors.value = {};
  try {
    await mutate({
      method: "POST",
      path: `/users/${encodeAdminUsernamePathSegment(user.value.username)}/password-actions`,
      body: {
        json: {
          new_password: passwordValue.value,
        },
      },
    });
    passwordValue.value = "";
    await refreshDetailOnly();
  } catch (cause) {
    passwordError.value = mapMutationError(cause);
    applyFieldErrors(cause, passwordFieldErrors);
    if (
      cause instanceof MutationClientError &&
      cause.fieldErrors.some((item) => item.field === "new_password")
    ) {
      passwordError.value = t("admin.users.password.weak");
    }
  } finally {
    passwordSaving.value = false;
  }
}

function backToList(): void {
  void router.push({ name: "admin-users" });
}

function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (!isAccessDirty.value) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
}

onBeforeRouteLeave(() => confirmDirtyNavigation());

onBeforeRouteUpdate((to) => {
  if (!isAccessDirty.value) {
    return true;
  }
  pendingNavigation = () => {
    void router.push(to);
  };
  discardDialogOpen.value = true;
  return false;
});

watch(
  () => route.params.username,
  (nextUsername, previousUsername) => {
    if (nextUsername !== previousUsername && !isAccessDirty.value) {
      void reload();
    }
  },
);

onMounted(() => {
  mounted = true;
  window.addEventListener("beforeunload", onBeforeUnload);
  void reload();
});

onUnmounted(() => {
  mounted = false;
  loadGeneration.current += 1;
  invalidateAccessOperations();
  passwordValue.value = "";
  window.removeEventListener("beforeunload", onBeforeUnload);
});
</script>

<template>
  <section class="admin-user-detail-view" data-testid="admin-user-detail-view">
    <header class="admin-user-detail-view__header">
      <v-btn
        variant="text"
        data-testid="admin-user-back"
        @click="backToList"
      >
        {{ t("admin.users.backToList") }}
      </v-btn>
      <h1 class="text-h5">{{ t("admin.users.detailTitle", { username }) }}</h1>
    </header>

    <v-alert
      v-if="!writesEnabled && user"
      type="warning"
      variant="tonal"
      role="status"
      class="mb-4"
      data-testid="admin-user-writes-disabled"
    >
      {{ t("admin.users.writesDisabled") }}
    </v-alert>

    <v-alert
      v-if="errorKey"
      type="error"
      variant="tonal"
      role="alert"
      data-testid="admin-user-error"
      class="mb-4"
    >
      {{ errorKey }}
      <template v-if="errorKey !== t('admin.users.errors.forbidden')" #append>
        <v-btn variant="text" data-testid="admin-user-retry" @click="reload">
          {{ t("admin.users.retry") }}
        </v-btn>
      </template>
    </v-alert>

    <div v-if="loading" data-testid="admin-user-loading" role="status">
      <v-skeleton-loader type="article" />
    </div>

    <template v-else-if="user">
      <v-card class="mb-4" data-testid="admin-user-read-card">
        <v-card-title>{{ t("admin.users.readModeTitle") }}</v-card-title>
        <v-card-text>
          <dl class="admin-user-detail-view__facts">
            <div>
              <dt>{{ t("admin.users.fields.username") }}</dt>
              <dd>{{ user.username }}</dd>
            </div>
            <div>
              <dt>{{ t("admin.users.fields.role") }}</dt>
              <dd data-testid="admin-user-role">{{ roleLabel(user.role) }}</dd>
            </div>
            <div>
              <dt>{{ t("admin.users.fields.active") }}</dt>
              <dd>
                {{
                  user.is_active
                    ? t("admin.users.status.active")
                    : t("admin.users.status.inactive")
                }}
              </dd>
            </div>
            <div>
              <dt>{{ t("admin.users.fields.qmb") }}</dt>
              <dd data-testid="admin-user-qmb-flag">
                {{ user.is_qmb ? t("admin.users.status.yes") : t("admin.users.status.no") }}
              </dd>
            </div>
            <div>
              <dt>{{ t("admin.users.fields.mustChangePassword") }}</dt>
              <dd data-testid="admin-user-must-change">
                {{
                  user.must_change_password
                    ? t("admin.users.status.yes")
                    : t("admin.users.status.no")
                }}
              </dd>
            </div>
          </dl>
          <v-btn
            v-if="!editMode"
            color="primary"
            class="mt-2"
            data-testid="admin-user-edit-start"
            :disabled="!writesEnabled"
            @click="enterEditMode"
          >
            {{ t("admin.users.edit.start") }}
          </v-btn>
        </v-card-text>
      </v-card>

      <v-card
        v-if="editMode"
        class="mb-4"
        data-testid="admin-user-edit-card"
      >
        <v-card-title>{{ t("admin.users.edit.title") }}</v-card-title>
        <v-card-text>
          <v-alert
            v-if="isAccessDirty"
            type="warning"
            variant="tonal"
            role="status"
            class="mb-3"
            data-testid="admin-user-dirty-hint"
          >
            {{ t("admin.users.edit.dirtyHint") }}
          </v-alert>
          <v-alert
            v-if="accessError"
            type="error"
            variant="tonal"
            role="alert"
            class="mb-3"
            data-testid="admin-user-access-error"
          >
            {{ accessError }}
          </v-alert>
          <v-form @submit.prevent="saveAccess">
            <v-select
              v-model="draftRole"
              :items="ROLE_OPTIONS.map((value) => ({ title: roleLabel(value), value }))"
              :label="t('admin.users.fields.role')"
              :error-messages="accessFieldErrors.role"
              data-testid="admin-user-edit-role"
            />
            <v-checkbox
              v-model="draftIsActive"
              :label="t('admin.users.fields.active')"
              :error-messages="accessFieldErrors.is_active"
              data-testid="admin-user-edit-active"
            />
            <v-checkbox
              v-model="draftIsQmb"
              :label="t('admin.users.fields.qmb')"
              :error-messages="accessFieldErrors.is_qmb"
              data-testid="admin-user-edit-qmb"
            />
            <div class="admin-user-detail-view__actions">
              <v-btn
                type="submit"
                color="primary"
                :loading="savingAccess"
                :disabled="!writesEnabled"
                data-testid="admin-user-edit-save"
              >
                {{ t("admin.users.edit.save") }}
              </v-btn>
              <v-btn
                variant="text"
                :disabled="savingAccess"
                data-testid="admin-user-edit-cancel"
                @click="cancelEditMode"
              >
                {{ t("admin.users.edit.cancel") }}
              </v-btn>
            </div>
          </v-form>
        </v-card-text>
      </v-card>

      <v-card data-testid="admin-user-password-card">
        <v-card-title>{{ t("admin.users.password.title") }}</v-card-title>
        <v-card-text>
          <p class="text-body-2 mb-3">{{ t("admin.users.password.hint") }}</p>
          <v-alert
            v-if="passwordError"
            type="error"
            variant="tonal"
            role="alert"
            class="mb-3"
            data-testid="admin-user-password-error"
          >
            {{ passwordError }}
          </v-alert>
          <v-form @submit.prevent="submitPasswordAction">
            <v-text-field
              v-model="passwordValue"
              type="password"
              autocomplete="new-password"
              :label="t('admin.users.password.newPassword')"
              :error-messages="passwordFieldErrors.new_password"
              data-testid="admin-user-password-input"
            />
            <v-btn
              type="submit"
              color="primary"
              :loading="passwordSaving"
              :disabled="!passwordValue || !writesEnabled"
              data-testid="admin-user-password-submit"
            >
              {{ t("admin.users.password.submit") }}
            </v-btn>
          </v-form>
        </v-card-text>
      </v-card>
    </template>

    <v-dialog
      v-model="discardDialogOpen"
      max-width="28rem"
      data-testid="admin-user-discard-dialog"
    >
      <v-card>
        <v-card-title>{{ t("admin.users.edit.discardTitle") }}</v-card-title>
        <v-card-text>{{ t("admin.users.edit.discardMessage") }}</v-card-text>
        <v-card-actions>
          <v-btn variant="text" data-testid="admin-user-discard-keep" @click="keepEditing">
            {{ t("admin.users.edit.keepEditing") }}
          </v-btn>
          <v-btn color="primary" data-testid="admin-user-discard-confirm" @click="discardChanges">
            {{ t("admin.users.edit.discard") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<style scoped>
.admin-user-detail-view__header {
  margin-bottom: 1rem;
}

.admin-user-detail-view__facts {
  display: grid;
  gap: 0.75rem;
}

.admin-user-detail-view__facts dt {
  font-weight: 600;
}

.admin-user-detail-view__facts dd {
  margin: 0;
}

.admin-user-detail-view__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

@media (max-width: 960px) {
  .admin-user-detail-view__header h1 {
    font-size: 1.25rem;
  }
}
</style>
