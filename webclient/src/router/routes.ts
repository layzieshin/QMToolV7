import { defineComponent, h } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter, type RouteRecordRaw } from "vue-router";

import AppLayout from "../layouts/AppLayout.vue";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import LoginView from "../views/LoginView.vue";
import { logout, useAppShellState } from "../state/appShell";

const ShellHomeView = defineComponent({
  name: "ShellHomeView",
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const shell = useAppShellState();

    async function onLogout(): Promise<void> {
      await logout();
      await router.replace("/login");
    }

    return () => {
      const isAuthenticated = shell.auth.status === "authenticated";

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
        meta: { requiresAuth: true },
        component: ShellHomeView,
      },
      {
        path: "login",
        name: "login",
        component: LoginView,
      },
      {
        path: "change-password",
        name: "change-password",
        component: ChangePasswordView,
      },
    ],
  },
];
