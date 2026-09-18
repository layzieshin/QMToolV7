import type { RouteRecordRaw } from "vue-router";

import AppLayout from "../layouts/AppLayout.vue";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import DashboardView from "../views/DashboardView.vue";
import LoginView from "../views/LoginView.vue";

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    component: AppLayout,
    children: [
      {
        path: "",
        name: "home",
        meta: { requiresAuth: true },
        component: DashboardView,
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
