<script setup lang="ts">
import { ref } from "vue";

import AppShell from "./components/AppShell.vue";
import { login, logout, useAppShellState } from "./state/appShell";

const shell = useAppShellState();
const username = ref("");
const password = ref("");
const loginError = ref<string | null>(null);

async function onLogin(): Promise<void> {
  loginError.value = null;
  try {
    await login(username.value, password.value);
  } catch (error) {
    loginError.value = error instanceof Error ? error.message : "Login fehlgeschlagen";
  }
}

async function onLogout(): Promise<void> {
  await logout();
}
</script>

<template>
  <AppShell>
    <section v-if="shell.auth.status === 'anonymous'" data-testid="login-panel">
      <h2>Anmeldung</h2>
      <form @submit.prevent="onLogin">
        <label>
          Benutzername
          <input v-model="username" autocomplete="username" />
        </label>
        <label>
          Passwort
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>
        <button type="submit">Anmelden</button>
      </form>
      <p v-if="loginError" data-testid="login-error">{{ loginError }}</p>
    </section>
    <section v-else data-testid="authenticated-panel">
      <button type="button" @click="onLogout">Abmelden</button>
    </section>
  </AppShell>
</template>

<style scoped>
form {
  display: grid;
  gap: 0.75rem;
  max-width: 24rem;
}
label {
  display: grid;
  gap: 0.25rem;
}
</style>
