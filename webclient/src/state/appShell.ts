import { reactive, readonly } from "vue";

import {
  ApiTransportError,
  changePasswordBrowser,
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

function isPasswordChangeRequired(error: unknown): boolean {
  if (!(error instanceof ApiTransportError) || error.status !== 409) {
    return false;
  }
  const detail = error.body?.detail;
  const code = !Array.isArray(detail) ? detail?.error : undefined;
  return code === "password_change_required";
}

export function useAppShellState() {
  return readonly(state);
}

export async function refreshConnection(): Promise<void> {
  state.connection = (await probeHealth()) ? "online" : "offline";
}

async function refreshAuthState(preserveAuthenticatedOnTransientError: boolean): Promise<boolean> {
  state.loading = true;
  state.lastError = null;
  try {
    await refreshConnection();
    const user: MeResponse = await fetchMe();
    state.auth = { status: "authenticated", user };
    return true;
  } catch (error) {
    if (isPasswordChangeRequired(error)) {
      const preservedUsername =
        state.auth.status === "password_change_required" ? state.auth.username : "";
      state.auth = { status: "password_change_required", username: preservedUsername };
      return true;
    }
    if (error instanceof ApiTransportError && error.status === 401) {
      state.auth = { status: "anonymous" };
      return true;
    }
    if (!(preserveAuthenticatedOnTransientError && state.auth.status === "authenticated")) {
      state.auth = { status: "anonymous" };
    }
    state.lastError = errorMessage(error);
    return false;
  } finally {
    state.loading = false;
  }
}

export async function refreshAuth(): Promise<void> {
  await refreshAuthState(false);
}

export async function revalidateAuth(): Promise<boolean> {
  return refreshAuthState(true);
}

export async function login(username: string, password: string): Promise<void> {
  state.loading = true;
  state.lastError = null;
  try {
    await loginBrowser({ username, password });
    try {
      const user: MeResponse = await fetchMe();
      state.auth = { status: "authenticated", user };
    } catch (error) {
      if (isPasswordChangeRequired(error)) {
        state.auth = { status: "password_change_required", username };
        return;
      }
      throw error;
    }
  } catch (error) {
    state.auth = { status: "anonymous" };
    state.lastError = errorMessage(error);
    throw error;
  } finally {
    state.loading = false;
  }
}

export async function changePassword(newPassword: string): Promise<void> {
  state.loading = true;
  state.lastError = null;
  try {
    await changePasswordBrowser(newPassword);
    await refreshAuth();
  } catch (error) {
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
