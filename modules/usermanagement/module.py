from __future__ import annotations

import os
from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import (
    DatabaseContribution,
    DatabaseMigrationContribution,
    DatabaseValidationContribution,
    ModuleContract,
    SettingsContribution,
)

from .service import UserManagementService
from .password_policy import password_policy_from_mapping
from .postgres_session_repository import PostgresSessionRepository
from .postgres_user_repository import PostgresUserRepository
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
            "password_policy": {
                "type": "object",
                "properties": {
                    "min_length": {"type": "integer"},
                    "require_letter": {"type": "boolean"},
                    "require_digit": {"type": "boolean"},
                    "require_uppercase": {"type": "boolean"},
                    "require_special": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        "required": ["users_db_path", "seed_mode", "dev_mode"],
        "additionalProperties": False,
    },
    defaults={
        "users_db_path": "storage/platform/users.db",
        "seed_mode": "admin_only",
        "dev_mode": False,
        "password_policy": {
            "min_length": 10,
            "require_letter": False,
            "require_digit": False,
            "require_uppercase": False,
            "require_special": False,
        },
    },
    scope="module_global",
    migrations=[],
)

USERMANAGEMENT_DATABASE_CONTRIBUTION = DatabaseContribution(
    database_id="users",
    module_id="usermanagement",
    setting_key="users_db_path",
    default_path="storage/platform/users.db",
    migrations=(
        DatabaseMigrationContribution(
            version=1,
            name="initial",
            sql_path=Path(__file__).parent / "migrations" / "0001_initial.sql",
        ),
        DatabaseMigrationContribution(
            version=2,
            name="deactivated_at",
            sql_path=Path(__file__).parent / "migrations" / "0002_deactivated_at.sql",
        ),
    ),
    validation_queries=(
        DatabaseValidationContribution(
            name="users without stable identity",
            sql=(
                "SELECT COUNT(*) FROM users "
                "WHERE user_id IS NULL OR TRIM(user_id) = '' "
                "OR username IS NULL OR TRIM(username) = ''"
            ),
        ),
    ),
)


def register_usermanagement_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    settings_service = container.get_port("settings_service")
    user_settings = settings_service.get_module_settings("usermanagement")
    postgres_dsn = (
        container.get_port("usermanagement_postgres_dsn")
        if container.has_port("usermanagement_postgres_dsn")
        else None
    )
    if postgres_dsn:
        repository = PostgresUserRepository(str(postgres_dsn))
        session_repository = PostgresSessionRepository(str(postgres_dsn))
        session_file = None
    else:
        users_db_path = Path(user_settings.get("users_db_path", "storage/platform/users.db"))
        if not users_db_path.is_absolute():
            users_db_path = app_home / users_db_path
        repository = SQLiteUserRepository(
            db_path=users_db_path,
        )
        session_repository = None
        session_file = app_home / "storage/platform/session/current_user.json"
    seed_mode = str(user_settings.get("seed_mode", "admin_only"))
    dev_mode = bool(user_settings.get("dev_mode", False))
    runtime_profile = os.environ.get("QMTOOL_RUNTIME_PROFILE", "").strip().lower()
    if runtime_profile in ("prod", "production") and seed_mode != "hardened":
        raise RuntimeError(
            "production profile requires usermanagement.seed_mode='hardened' "
            "(legacy admin/admin seed is not allowed)"
        )
    if seed_mode == "hardened":
        pass
    elif seed_mode == "admin_only":
        # Legacy/dev desktop convenience only: repository seed bypasses the
        # password policy and creates admin/admin with must_change_password.
        # Backend composition forces hardened; production forbids this mode.
        repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=True)
    elif seed_mode == "legacy_defaults" and dev_mode:
        # Explicit legacy/dev seed; same policy bypass as admin_only.
        repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=True)
    password_policy = password_policy_from_mapping(user_settings.get("password_policy"))
    container.register_port(
        "usermanagement_service",
        UserManagementService(
            event_bus=container.get_port("event_bus"),
            session_file=session_file,
            repository=repository,
            session_repository=session_repository,
            password_policy=password_policy,
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
        database_contributions=(USERMANAGEMENT_DATABASE_CONTRIBUTION,),
    )

