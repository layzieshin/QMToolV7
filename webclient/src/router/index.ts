import {
  createRouter,
  createWebHistory,
  type RouteLocationNormalized,
  type Router,
  type RouterHistory,
} from "vue-router";

import {
  RETURN_URL_QUERY,
  buildChangePasswordLocation,
  buildLoginLocation,
  readReturnUrlQuery,
  sanitizeReturnUrl,
} from "../composables/useReturnUrl";
import { refreshAuth, useAppShellState } from "../state/appShell";
import { routes } from "./routes";

let authBootstrapped = false;

function resolveReturnTarget(to: RouteLocationNormalized): string {
  const fromQuery = readReturnUrlQuery(to.query[RETURN_URL_QUERY]);
  if (fromQuery) {
    return sanitizeReturnUrl(fromQuery);
  }
  return sanitizeReturnUrl(to.fullPath);
}

export async function authNavigationGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: (value?: unknown) => void,
): Promise<void> {
  if (!authBootstrapped) {
    authBootstrapped = true;
    await refreshAuth();
  }

  const shell = useAppShellState();
  const authStatus = shell.auth.status;
  const returnTarget = resolveReturnTarget(to);

  if (authStatus === "password_change_required") {
    if (to.path !== "/change-password") {
      next(buildChangePasswordLocation(returnTarget));
      return;
    }
    next();
    return;
  }

  if (authStatus === "authenticated") {
    if (to.path === "/login" || to.path === "/change-password") {
      next(returnTarget === "/" ? { path: "/" } : returnTarget);
      return;
    }
    next();
    return;
  }

  if (to.meta.requiresAuth) {
    next(buildLoginLocation(to.fullPath));
    return;
  }

  if (to.path === "/change-password") {
    next(buildLoginLocation(returnTarget));
    return;
  }

  next();
}

export function createAppRouter(history: RouterHistory): Router {
  const router = createRouter({
    history,
    routes,
  });
  router.beforeEach(authNavigationGuard);
  return router;
}

const router = createAppRouter(createWebHistory());

export function __resetAuthBootstrapForTest(): void {
  authBootstrapped = false;
}

export default router;
