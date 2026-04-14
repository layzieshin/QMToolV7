from __future__ import annotations

import os
from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

from .service import UserManagementService
from .sqlite_repository import SQLiteUserRepository


USERMANAGEMENT_SETTINGS_CONTRIBUTION = SettingsContribution(
    module_id="usermanagement",
    schema_version=1,
    schema={
        "type": "object",
        "properties": {
            "users_db_path": {"type": "string"},
            "seed_mode": {"type": "string"},
            "dev_mode": {"type": "boolean"},
        },
        "required": ["users_db_path", "seed_mode", "dev_mode"],
        "additionalProperties": False,
    },
    defaults={
        "users_db_path": "storage/platform/users.db",
        "seed_mode": "legacy_defaults",
        "dev_mode": True,
    },
    scope="module_global",
    migrations=[],
)


def register_usermanagement_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    settings_service = container.get_port("settings_service")
    user_settings = settings_service.get_module_settings("usermanagement")
    users_db_path = Path(user_settings.get("users_db_path", "storage/platform/users.db"))
    if not users_db_path.is_absolute():
        users_db_path = app_home / users_db_path
    repository = SQLiteUserRepository(
        db_path=users_db_path,
        schema_path=Path(__file__).with_name("schema.sql"),
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


def start_usermanagement_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("usermanagement", "module started")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.usermanagement.module.started.v1", "usermanagement", {"status": "started"})
    )


def stop_usermanagement_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("usermanagement", "module stopped")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.usermanagement.module.stopped.v1", "usermanagement", {"status": "stopped"})
    )


def create_usermanagement_module_contract() -> ModuleContract:
    return ModuleContract(
        module_id="usermanagement",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=["logger", "audit_logger", "event_bus", "settings_service"],
        provided_ports=["usermanagement_service"],
        required_capabilities=[],
        provided_capabilities=["auth.authenticate", "auth.session.read"],
        settings_contribution=USERMANAGEMENT_SETTINGS_CONTRIBUTION,
        license_tag=None,
        register=register_usermanagement_ports,
        start=start_usermanagement_module,
        stop=stop_usermanagement_module,
    )

