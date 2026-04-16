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
    seed_mode = str(user_settings.get("seed_mode", "legacy_defaults"))
    dev_mode = bool(user_settings.get("dev_mode", True))
    runtime_profile = os.environ.get("QMTOOL_RUNTIME_PROFILE", "").strip().lower()
    if runtime_profile in ("prod", "production") and seed_mode != "hardened":
        raise RuntimeError("production profile requires usermanagement.seed_mode='hardened'")
    if dev_mode and seed_mode == "legacy_defaults":
        repository.ensure_seed_users(
            [
                ("admin", "admin", "Admin"),
                ("qmb", "qmb", "QMB"),
                ("user", "user", "User"),
            ]
        )
    container.register_port(
        "usermanagement_service",
        UserManagementService(
            event_bus=container.get_port("event_bus"),
            session_file=app_home / "storage/platform/session/current_user.json",
            repository=repository,
        ),
    )

