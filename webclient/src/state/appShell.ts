import { reactive, readonly } from "vue";

import {
  ApiTransportError,
  fetchMe,
  loginBrowser,
  logoutBrowser,
  probeHealth,
} from "../api/client";
import type { AuthState, ConnectionState, MeResponse } from "../api/types";

export interface AppShellState {
  connection: ConnectionState;
  auth: AuthState;
  lastError: string | null;
  loading: boolean;
}

const state = reactive<AppShellState>({
  connection: "unknown",
  auth: { status: "anonymous" },
  lastError: null,
  loading: false,
});

function errorMessage(error: unknown): string {
  if (error instanceof ApiTransportError) {
    const detail = error.body?.detail;
    if (detail && !Array.isArray(detail) && detail.message) {
      return detail.message;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "unexpected error";
}

export function useAppShellState() {
  return readonly(state);
}

export async function refreshConnection(): Promise<void> {
  state.connection = (await probeHealth()) ? "online" : "offline";
}

export async function refreshAuth(): Promise<void> {
  state.loading = true;
  state.lastError = null;
  try {
    await refreshConnection();
    const user: MeResponse = await fetchMe();
    state.auth = { status: "authenticated", user };
  } catch (error) {
    if (error instanceof ApiTransportError && error.status === 409) {
      const detail = error.body?.detail;
      const code = !Array.isArray(detail) ? detail?.error : undefined;
      if (code === "password_change_required") {
        state.auth = { status: "password_change_required", username: "" };
        return;
      }
    }
    if (error instanceof ApiTransportError && error.status === 401) {
      state.auth = { status: "anonymous" };
      return;
    }
    state.auth = { status: "anonymous" };
    state.lastError = errorMessage(error);
  } finally {
    state.loading = false;
  }
}

export async function login(username: string, password: string): Promise<void> {
  state.loading = true;
  state.lastError = null;
  try {
    await loginBrowser({ username, password });
    await refreshAuth();
  } catch (error) {
    state.auth = { status: "anonymous" };
    state.lastError = errorMessage(error);
    throw error;
  } finally {
    state.loading = false;
  }
}

export async function logout(): Promise<void> {
  state.loading = true;
  state.lastError = null;
  try {
    await logoutBrowser();
  } catch (error) {
    state.lastError = errorMessage(error);
  } finally {
    state.auth = { status: "anonymous" };
    state.loading = false;
  }
}

export function __resetAppShellStateForTest(): void {
  state.connection = "unknown";
  state.auth = { status: "anonymous" };
  state.lastError = null;
  state.loading = false;
}
