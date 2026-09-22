<script setup lang="ts">
import { useI18n } from "vue-i18n";

defineOptions({
  name: "ShellHomeView",
});

const { t } = useI18n();
</script>

<template>
  <section data-testid="shell-placeholder" class="dashboard-view">
    <h2>{{ t("dashboard.title") }}</h2>
    <p>{{ t("dashboard.hint") }}</p>
  </section>
</template>

<style scoped>
.dashboard-view h2 {
  margin-top: 0;
}
</style>
