"""Slim Usermanagement wiring for the backend host (AP-028 M5).

Does not start Documents/Training/Registry/Incidents or run SQLite evolution.
Forces hardened seed_mode so the backend never auto-creates admin/admin.
"""
from __future__ import annotations

import os

from modules.usermanagement import api as um_api
from modules.usermanagement.api import ensure_postgres_schema_ready
from modules.usermanagement.module import create_usermanagement_module_contract

from .container import RuntimeContainer
from .lifecycle import LifecycleManager


class BackendUsermanagementBootstrapError(RuntimeError):
    """Raised when backend Usermanagement cannot start safely."""


def _force_hardened_usermanagement_settings(container: RuntimeContainer) -> None:
    settings = container.get_port("settings_service")
    cfg = dict(settings.get_module_settings("usermanagement"))
    cfg["seed_mode"] = "hardened"
    cfg["dev_mode"] = False
    settings.set_module_settings(
        "usermanagement",
        cfg,
        acknowledge_governance_change=True,
    )


def _ensure_users_or_bootstrap(container: RuntimeContainer) -> None:
    service = um_api.get_usermanagement_service(container)
    if service.list_users():
        return

    username = os.environ.get("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.environ.get("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or password == "":
        raise BackendUsermanagementBootstrapError(
            "backend has no users; set QMTOOL_BOOTSTRAP_ADMIN_USERNAME and "
            "QMTOOL_BOOTSTRAP_ADMIN_PASSWORD for one-time first-admin bootstrap "
            "(or provision a user before starting the backend)"
        )
    if username.lower() == "admin" and password == "admin":
        raise BackendUsermanagementBootstrapError(
            "refusing insecure bootstrap credentials admin/admin"
        )
    created = um_api.bootstrap_first_admin(container, username, password)
    if created is None and not service.list_users():
        raise BackendUsermanagementBootstrapError("first-admin bootstrap produced no users")


def wire_backend_usermanagement(container: RuntimeContainer) -> LifecycleManager:
    """Prepare, wire, and start only the Usermanagement module contract."""
    if not container.has_port("usermanagement_postgres_dsn"):
        raise RuntimeError("backend requires usermanagement_postgres_dsn")

    ensure_postgres_schema_ready(container)

    lifecycle = LifecycleManager(container)
    lifecycle.prepare(create_usermanagement_module_contract())
    _force_hardened_usermanagement_settings(container)
    lifecycle.wire("usermanagement")
    _ensure_users_or_bootstrap(container)
    lifecycle.start(strict=True)
    return lifecycle
