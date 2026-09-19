import type { RouteRecordRaw } from "vue-router";

import AppLayout from "../layouts/AppLayout.vue";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import DashboardView from "../views/DashboardView.vue";
import DocumentDetailView from "../views/documents/DocumentDetailView.vue";
import DocumentImportView from "../views/documents/DocumentImportView.vue";
import DocumentsPoolView from "../views/documents/DocumentsPoolView.vue";
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
        path: "documents",
        name: "documents",
        meta: { requiresAuth: true },
        component: DocumentsPoolView,
      },
      {
        path: "documents/import",
        name: "document-import",
        meta: { requiresAuth: true },
        component: DocumentImportView,
      },
      {
        path: "documents/:docId",
        name: "document-detail",
        meta: { requiresAuth: true },
        component: DocumentDetailView,
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
