import { reactive, readonly } from "vue";

import {
  ApiTransportError,
  fetchBootstrap,
  fetchConnection,
  type ConnectionResponse,
  type ModuleBootstrapItem,
} from "../api/client";

export type ConnectionBannerMode =
  | "hidden"
  | "offline"
  | "reconnecting"
  | "maintenance"
  | "degraded"
  | "restored";

export interface BootstrapState {
  connection: ConnectionResponse | null;
  online: boolean;
  writesAllowed: boolean;
  modules: ModuleBootstrapItem[];
  connectionLoading: boolean;
  bootstrapLoading: boolean;
  connectionError: string | null;
  bootstrapError: string | null;
  banner: ConnectionBannerMode;
  reconnecting: boolean;
}

const MIN_RETRY_MS = 5000;
const MAX_RETRY_MS = 30000;
const RESTORED_VISIBLE_MS = 3000;

const state = reactive<BootstrapState>({
  connection: null,
  online: false,
  writesAllowed: false,
  modules: [],
  connectionLoading: false,
  bootstrapLoading: false,
  connectionError: null,
  bootstrapError: null,
  banner: "hidden",
  reconnecting: false,
});

let lifecycleActive = false;
let lifecycleEpoch = 0;
let bootstrapGeneration = 0;
let latestBootstrapLoadId = 0;
let latestConnectionRequestId = 0;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let restoredTimer: ReturnType<typeof setTimeout> | null = null;
let retryDelayMs = MIN_RETRY_MS;
let wasOffline = false;

function clearRetryTimer(): void {
  if (retryTimer !== null) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
}

function clearRestoredTimer(): void {
  if (restoredTimer !== null) {
    clearTimeout(restoredTimer);
    restoredTimer = null;
  }
}

function invalidateConnectionRequests(): void {
  latestConnectionRequestId += 1;
  clearRestoredTimer();
}

function beginConnectionRequest(): number {
  invalidateConnectionRequests();
  return latestConnectionRequestId;
}

function isLatestConnectionRequest(requestId: number): boolean {
  return requestId === latestConnectionRequestId;
}

function isLifecycleEpochCurrent(boundEpoch: number): boolean {
  return lifecycleActive && boundEpoch === lifecycleEpoch;
}

function sortModules(modules: ModuleBootstrapItem[]): ModuleBootstrapItem[] {
  return [...modules].sort((left, right) => left.id.localeCompare(right.id));
}

function deriveWritesAllowed(connection: ConnectionResponse | null, online: boolean): boolean {
  if (!online || !connection) {
    return false;
  }
  if (connection.maintenance || connection.status === "degraded") {
    return false;
  }
  return connection.writes_allowed;
}

function deriveBannerMode(
  online: boolean,
  reconnecting: boolean,
  connection: ConnectionResponse | null,
  restoredVisible: boolean,
): ConnectionBannerMode {
  if (restoredVisible) {
    return "restored";
  }
  if (!online) {
    return reconnecting ? "reconnecting" : "offline";
  }
  if (!connection) {
    return "hidden";
  }
  if (connection.maintenance) {
    return "maintenance";
  }
  if (connection.status === "degraded" || !connection.writes_allowed) {
    return "degraded";
  }
  return "hidden";
}

function applyConnectionSuccess(
  connection: ConnectionResponse,
  requestId: number,
  boundEpoch?: number,
): void {
  if (!isLatestConnectionRequest(requestId)) {
    return;
  }
  if (boundEpoch !== undefined && !isLifecycleEpochCurrent(boundEpoch)) {
    return;
  }

  const recovering = wasOffline;
  state.connection = connection;
  state.online = true;
  state.connectionError = null;
  state.reconnecting = false;
  state.writesAllowed = deriveWritesAllowed(connection, true);
  wasOffline = false;

  if (recovering) {
    clearRestoredTimer();
    state.banner = "restored";
    const epochAtSchedule = boundEpoch ?? lifecycleEpoch;
    restoredTimer = setTimeout(() => {
      if (!isLatestConnectionRequest(requestId)) {
        return;
      }
      if (boundEpoch !== undefined && !isLifecycleEpochCurrent(epochAtSchedule)) {
        return;
      }
      state.banner = deriveBannerMode(true, false, connection, false);
    }, RESTORED_VISIBLE_MS);
    retryDelayMs = MIN_RETRY_MS;
    clearRetryTimer();
    return;
  }

  state.banner = deriveBannerMode(true, false, connection, false);
}

function applyConnectionFailure(requestId: number, boundEpoch?: number): void {
  if (!isLatestConnectionRequest(requestId)) {
    return;
  }
  if (boundEpoch !== undefined && !isLifecycleEpochCurrent(boundEpoch)) {
    return;
  }

  clearRestoredTimer();
  wasOffline = true;
  state.online = false;
  state.writesAllowed = false;
  state.connection = null;
  state.reconnecting = false;
  state.banner = deriveBannerMode(false, false, null, false);
  if (boundEpoch !== undefined) {
    scheduleReconnect(boundEpoch, requestId);
  }
}

function scheduleReconnect(boundEpoch: number, requestId: number): void {
  if (!isLatestConnectionRequest(requestId) || !isLifecycleEpochCurrent(boundEpoch)) {
    return;
  }
  clearRetryTimer();
  retryTimer = setTimeout(() => {
    void refreshConnection({ automatic: true, lifecycleEpoch: boundEpoch });
  }, retryDelayMs);
  retryDelayMs = Math.min(retryDelayMs * 2, MAX_RETRY_MS);
}

export function useBootstrapState() {
  return readonly(state);
}

export async function refreshConnection(
  options: { automatic?: boolean; lifecycleEpoch?: number } = {},
): Promise<void> {
  const boundEpoch = options.lifecycleEpoch;
  const isLifecycleBound = boundEpoch !== undefined;

  if (isLifecycleBound && !isLifecycleEpochCurrent(boundEpoch)) {
    return;
  }

  if (options.automatic && (!isLifecycleBound || !isLifecycleEpochCurrent(boundEpoch))) {
    return;
  }

  const requestId = beginConnectionRequest();

  if (options.automatic) {
    state.reconnecting = true;
    state.banner = "reconnecting";
  }

  state.connectionLoading = true;

  try {
    const connection = await fetchConnection();
    if (!isLatestConnectionRequest(requestId)) {
      return;
    }
    if (isLifecycleBound && !isLifecycleEpochCurrent(boundEpoch)) {
      return;
    }
    applyConnectionSuccess(connection, requestId, boundEpoch);
  } catch (error) {
    if (!isLatestConnectionRequest(requestId)) {
      return;
    }
    if (isLifecycleBound && !isLifecycleEpochCurrent(boundEpoch)) {
      return;
    }
    clearRestoredTimer();
    state.connectionError = error instanceof Error ? error.message : "connection failed";
    applyConnectionFailure(requestId, boundEpoch);
  } finally {
    if (isLatestConnectionRequest(requestId)) {
      state.connectionLoading = false;
    }
  }
}

export async function retryConnection(): Promise<void> {
  clearRetryTimer();
  retryDelayMs = MIN_RETRY_MS;
  state.reconnecting = true;
  state.banner = "reconnecting";
  await refreshConnection(lifecycleActive ? { lifecycleEpoch: lifecycleEpoch } : {});
}

export async function loadBootstrap(): Promise<void> {
  const generationAtStart = bootstrapGeneration;
  const loadId = ++latestBootstrapLoadId;

  state.bootstrapLoading = true;
  state.bootstrapError = null;
  try {
    const response = await fetchBootstrap();
    if (generationAtStart !== bootstrapGeneration || loadId !== latestBootstrapLoadId) {
      return;
    }
    state.modules = sortModules(response.modules);
  } catch (error) {
    if (generationAtStart !== bootstrapGeneration || loadId !== latestBootstrapLoadId) {
      return;
    }
    if (error instanceof ApiTransportError && error.status === 401) {
      state.modules = [];
      throw error;
    }
    state.modules = [];
    state.bootstrapError = error instanceof Error ? error.message : "bootstrap failed";
  } finally {
    if (loadId === latestBootstrapLoadId && generationAtStart === bootstrapGeneration) {
      state.bootstrapLoading = false;
    }
  }
}

export function clearBootstrapModules(): void {
  bootstrapGeneration += 1;
  latestBootstrapLoadId += 1;
  state.modules = [];
  state.bootstrapError = null;
  state.bootstrapLoading = false;
}

export function startBootstrapLifecycle(): void {
  clearRetryTimer();
  lifecycleActive = true;
  lifecycleEpoch += 1;
  const epoch = lifecycleEpoch;
  void refreshConnection({ lifecycleEpoch: epoch });
}

export function stopBootstrapLifecycle(): void {
  lifecycleActive = false;
  lifecycleEpoch += 1;
  invalidateConnectionRequests();
  clearRetryTimer();
  state.reconnecting = false;
  state.connectionLoading = false;
}

export function __resetBootstrapStateForTest(): void {
  lifecycleActive = false;
  lifecycleEpoch += 1;
  invalidateConnectionRequests();
  clearRetryTimer();
  bootstrapGeneration += 1;
  latestBootstrapLoadId += 1;
  state.connection = null;
  state.online = false;
  state.writesAllowed = false;
  state.modules = [];
  state.connectionLoading = false;
  state.bootstrapLoading = false;
  state.connectionError = null;
  state.bootstrapError = null;
  state.banner = "hidden";
  state.reconnecting = false;
  retryDelayMs = MIN_RETRY_MS;
  wasOffline = false;
}

export function __getBootstrapRetryDelayForTest(): number {
  return retryDelayMs;
}

export function __isBootstrapLifecycleActiveForTest(): boolean {
  return lifecycleActive;
}

export function __getLifecycleEpochForTest(): number {
  return lifecycleEpoch;
}

export function __setBootstrapBannerForTest(
  banner: ConnectionBannerMode,
  reconnecting = false,
): void {
  state.banner = banner;
  state.reconnecting = reconnecting;
}

export function __setBootstrapModulesForTest(modules: ModuleBootstrapItem[]): void {
  state.modules = modules;
}
