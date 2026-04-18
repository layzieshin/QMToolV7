"""Port wiring for the usermanagement module (SRP split B5)."""
from __future__ import annotations

import os
from pathlib import Path

from .service import UserManagementService
from .sqlite_repository import SQLiteUserRepository


def register_usermanagement_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    settings_service = container.get_port("settings_service")
    user_settings = settings_service.get_module_settings("usermanagement")
    users_db_path = Path(user_settings.get("users_db_path", "storage/platform/users.db"))
    if not users_db_path.is_absolute():
        users_db_path = app_home / users_db_path
    repository = SQLiteUserRepository(
        db_path=users_db_path,
        schema_path=Path(__file__).parent / "schema.sql",
    )
    seed_mode = str(user_settings.get("seed_mode", "admin_only"))
    dev_mode = bool(user_settings.get("dev_mode", False))
    runtime_profile = os.environ.get("QMTOOL_RUNTIME_PROFILE", "").strip().lower()
    if runtime_profile in ("prod", "production") and seed_mode not in ("hardened", "admin_only"):
        raise RuntimeError("production profile requires usermanagement.seed_mode='hardened' or 'admin_only'")
    if seed_mode == "hardened":
        pass
    elif seed_mode == "admin_only":
        repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=True)
    elif seed_mode == "legacy_defaults" and dev_mode:
        repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=True)
    container.register_port(
        "usermanagement_service",
        UserManagementService(
            event_bus=container.get_port("event_bus"),
            session_file=app_home / "storage/platform/session/current_user.json",
            repository=repository,
        ),
    )

