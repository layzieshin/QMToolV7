import type { RouteRecordRaw } from "vue-router";

import AppLayout from "../layouts/AppLayout.vue";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import DashboardView from "../views/DashboardView.vue";
import DocumentDetailView from "../views/documents/DocumentDetailView.vue";
import DocumentViewerView from "../views/documents/DocumentViewerView.vue";
import SignatureWorkspaceView from "../views/signature/SignatureWorkspaceView.vue";
import DocumentImportView from "../views/documents/DocumentImportView.vue";
import DocumentsPoolView from "../views/documents/DocumentsPoolView.vue";
import AdminUserDetailView from "../views/admin/AdminUserDetailView.vue";
import AdminUsersView from "../views/admin/AdminUsersView.vue";
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
        path: "documents/:docId/viewer",
        name: "document-viewer",
        meta: { requiresAuth: true },
        component: DocumentViewerView,
      },
      {
        path: "documents/:docId/signature",
        name: "document-signature",
        meta: { requiresAuth: true },
        component: SignatureWorkspaceView,
      },
      {
        path: "documents/:docId",
        name: "document-detail",
        meta: { requiresAuth: true },
        component: DocumentDetailView,
      },
      {
        path: "admin/users",
        name: "admin-users",
        meta: { requiresAuth: true },
        component: AdminUsersView,
      },
      {
        path: "admin/users/:username",
        name: "admin-user-detail",
        meta: { requiresAuth: true },
        component: AdminUserDetailView,
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
