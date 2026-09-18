import { defineComponent, h } from "vue";
import type { RouteRecordRaw } from "vue-router";
import { useI18n } from "vue-i18n";

import AppLayout from "../layouts/AppLayout.vue";
import LoginView from "../views/LoginView.vue";
import { logout, useAppShellState } from "../state/appShell";

const ShellHomeView = defineComponent({
  name: "ShellHomeView",
  setup() {
    const { t } = useI18n();
    const shell = useAppShellState();

    async function onLogout(): Promise<void> {
      await logout();
    }

    return () => {
      const isAuthenticated =
        shell.auth.status === "authenticated" || shell.auth.status === "password_change_required";

      return h("section", { "data-testid": "shell-placeholder" }, [
        h("h2", t("shell.homeTitle")),
        h("p", isAuthenticated ? t("shell.homeAuthenticatedHint") : t("shell.homeHint")),
        isAuthenticated
          ? h("section", { "data-testid": "authenticated-panel" }, [
              h(
                "button",
                {
                  type: "button",
                  onClick: onLogout,
                },
                t("shell.logout"),
              ),
            ])
          : null,
      ]);
    };
  },
});

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    component: AppLayout,
    children: [
      {
        path: "",
        name: "home",
        component: ShellHomeView,
      },
      {
        path: "login",
        name: "login",
        component: LoginView,
      },
    ],
  },
];
