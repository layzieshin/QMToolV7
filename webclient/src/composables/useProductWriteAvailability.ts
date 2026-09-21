import { computed } from "vue";
import { useI18n } from "vue-i18n";

import {
  type BootstrapState,
  type ConnectionBannerMode,
  useBootstrapState,
} from "../state/bootstrap";

type TranslateFn = (key: string) => string;

export function resolveProductWritesBlockedMessage(
  state: Pick<BootstrapState, "banner" | "online">,
  t: TranslateFn,
): string {
  switch (state.banner) {
    case "offline":
      return t("connection.offline");
    case "reconnecting":
      return t("connection.reconnecting");
    case "maintenance":
      return t("connection.maintenance");
    case "degraded":
      return t("connection.degraded");
    default:
      if (!state.online) {
        return t("connection.offline");
      }
      return t("connection.degraded");
  }
}

export function productWritesBlockedMessageForBanner(
  banner: ConnectionBannerMode,
  online: boolean,
  t: TranslateFn,
): string {
  return resolveProductWritesBlockedMessage({ banner, online }, t);
}

export function useProductWriteAvailability() {
  const bootstrap = useBootstrapState();
  const { t } = useI18n();

  const writesAllowed = computed(() => bootstrap.writesAllowed);
  const blockedMessage = computed(() =>
    resolveProductWritesBlockedMessage(bootstrap, t),
  );

  return {
    writesAllowed,
    blockedMessage,
  };
}
