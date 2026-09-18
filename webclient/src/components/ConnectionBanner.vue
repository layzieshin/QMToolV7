<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import { retryConnection, useBootstrapState } from "../state/bootstrap";

const { t } = useI18n();
const bootstrap = useBootstrapState();

const visible = computed(() => bootstrap.banner !== "hidden");

const messageKey = computed(() => {
  switch (bootstrap.banner) {
    case "offline":
      return "connection.offline";
    case "reconnecting":
      return "connection.reconnecting";
    case "maintenance":
      return "connection.maintenance";
    case "degraded":
      return "connection.degraded";
    case "restored":
      return "connection.restored";
    default:
      return "connection.offline";
  }
});

const alertRole = computed(() => (bootstrap.banner === "restored" ? "status" : "alert"));

const showRetry = computed(
  () => bootstrap.banner === "offline" || bootstrap.banner === "reconnecting",
);

async function onRetry(): Promise<void> {
  await retryConnection();
}
</script>

<template>
  <v-alert
    v-if="visible"
    :type="bootstrap.banner === 'restored' ? 'success' : 'warning'"
    variant="tonal"
    density="compact"
    class="connection-banner"
    data-testid="connection-banner"
    :role="alertRole"
  >
    <div class="connection-banner__row">
      <span data-testid="connection-banner-message">{{ t(messageKey) }}</span>
      <v-btn
        v-if="showRetry"
        variant="text"
        size="small"
        data-testid="connection-banner-retry"
        :disabled="bootstrap.reconnecting"
        @click="onRetry"
      >
        {{ t("connection.retry") }}
      </v-btn>
    </div>
  </v-alert>
</template>

<style scoped>
.connection-banner {
  margin-bottom: 0.75rem;
}
.connection-banner__row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: space-between;
  width: 100%;
}
</style>
