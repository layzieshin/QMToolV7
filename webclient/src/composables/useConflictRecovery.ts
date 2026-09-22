import { ref, type Ref } from "vue";

import type { VersionStateResponse } from "../api/client";
import { MutationClientError } from "../api/mutationClient";

export type ConflictRecoveryContext = {
  actionCode?: string;
  /** Localized action label; never a raw action code. */
  actionLabel?: string;
  reason?: string;
};

export type UseConflictRecoveryOptions = {
  detail: Ref<VersionStateResponse | null>;
  reload: () => Promise<void>;
};

export type ConflictRecoveryState = {
  conflictVisible: Ref<boolean>;
  conflictLoading: Ref<boolean>;
  reloadFailed: Ref<boolean>;
  showingLocalInput: Ref<boolean>;
  preservedContext: Ref<ConflictRecoveryContext | null>;
  openConflict: (error: MutationClientError, context?: ConflictRecoveryContext) => void;
  loadServerState: () => Promise<void>;
  viewLocalInput: () => void;
  cancelConflict: () => void;
};

export function useConflictRecovery(options: UseConflictRecoveryOptions): ConflictRecoveryState {
  const conflictVisible = ref(false);
  const conflictLoading = ref(false);
  const reloadFailed = ref(false);
  const showingLocalInput = ref(false);
  const preservedContext = ref<ConflictRecoveryContext | null>(null);

  function closeConflict(): void {
    conflictVisible.value = false;
    showingLocalInput.value = false;
    reloadFailed.value = false;
  }

  function openConflict(error: MutationClientError, context?: ConflictRecoveryContext): void {
    if (error.kind !== "conflict" && error.kind !== "precondition_required") {
      return;
    }
    preservedContext.value = context ?? null;
    showingLocalInput.value = false;
    reloadFailed.value = false;
    conflictVisible.value = true;
  }

  async function loadServerState(): Promise<void> {
    if (conflictLoading.value) {
      return;
    }
    conflictLoading.value = true;
    reloadFailed.value = false;
    try {
      await options.reload();
      if (!options.detail.value?.state) {
        reloadFailed.value = true;
        return;
      }
      preservedContext.value = null;
      closeConflict();
    } finally {
      conflictLoading.value = false;
    }
  }

  function viewLocalInput(): void {
    showingLocalInput.value = true;
  }

  function cancelConflict(): void {
    preservedContext.value = null;
    closeConflict();
  }

  return {
    conflictVisible,
    conflictLoading,
    reloadFailed,
    showingLocalInput,
    preservedContext,
    openConflict,
    loadServerState,
    viewLocalInput,
    cancelConflict,
  };
}
