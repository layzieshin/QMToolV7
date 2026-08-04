from __future__ import annotations

import json
import os
from pathlib import Path
from getpass import getpass

from qm_platform.licensing.license_status import build_license_diagnostics
from qm_platform.persistence.path_resolver import (
    bootstrap_path_env_key,
    resolve_bootstrap_absolute_path,
    resolve_platform_settings_db_path,
)
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.paths import path_writable, resolve_home_path, runtime_home
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from qm_platform.settings.residual_store import RESIDUAL_ARCHIVE_REL
from qm_platform.settings.settings_service import SettingsService

from interfaces.cli.bootstrap import build_container
from modules.usermanagement.api import bootstrap_admin


def _prompt_if_missing(value: str | None, prompt: str, default: str | None = None) -> str:
    if value is not None and value.strip():
        return value.strip()
    hint = f" [{default}]" if default else ""
    entered = input(f"{prompt}{hint}: ").strip()
    if not entered and default:
        return default
    if not entered:
        raise ValueError(f"{prompt} is required")
    return entered


def _resolve_runtime_paths(app_home: Path) -> dict[str, str]:
    return {
        "users_db_path": "storage/platform/users.db",
        "documents_db_path": "storage/documents/documents.db",
        "artifacts_root": "storage/documents/artifacts",
        "registry_db_path": "storage/documents/registry.db",
        "logs_dir": "storage/platform/logs",
        "license_file": "license/license.json",
    }


def _set_bootstrap_path_env(module_id: str, setting_key: str, value: str) -> None:
    os.environ[bootstrap_path_env_key(module_id, setting_key)] = value


def _seed_admin_credentials(container, username: str, password: str) -> None:
    """Delegate to the public bootstrap use-case in usermanagement API."""
    bootstrap_admin(container, username, password)


def _all_user_passwords_hashed(usermanagement) -> bool:
    audit = getattr(usermanagement, "all_passwords_hashed", None)
    if callable(audit):
        return bool(audit())
    return False


def cmd_init(args) -> int:
    if args.app_home:
        os.environ["QMTOOL_HOME"] = str(Path(args.app_home).resolve())
    app_home = runtime_home()
    defaults = _resolve_runtime_paths(app_home)
    non_interactive = bool(args.non_interactive)
    try:
        users_db_path = args.users_db_path or (
            defaults["users_db_path"] if non_interactive else _prompt_if_missing(None, "users_db_path", defaults["users_db_path"])
        )
        documents_db_path = args.documents_db_path or (
            defaults["documents_db_path"] if non_interactive else _prompt_if_missing(None, "documents_db_path", defaults["documents_db_path"])
        )
        artifacts_root = args.artifacts_root or (
            defaults["artifacts_root"] if non_interactive else _prompt_if_missing(None, "artifacts_root", defaults["artifacts_root"])
        )
        registry_db_path = args.registry_db_path or (
            defaults["registry_db_path"] if non_interactive else _prompt_if_missing(None, "registry_db_path", defaults["registry_db_path"])
        )
        admin_username = args.admin_username or "admin"
        admin_password = args.admin_password
        if not admin_password:
            if non_interactive:
                raise ValueError("--admin-password is required in --non-interactive mode")
            admin_password = getpass("admin_password: ").strip()
        if not admin_password:
            raise ValueError("admin_password is required")

        container = build_container()
        lifecycle = runtime_bootstrap.prepare_core_modules(container)
        _set_bootstrap_path_env("usermanagement", "users_db_path", users_db_path)
        _set_bootstrap_path_env("documents", "documents_db_path", documents_db_path)
        _set_bootstrap_path_env("documents", "artifacts_root", artifacts_root)
        _set_bootstrap_path_env("registry", "registry_db_path", registry_db_path)

        runtime_bootstrap.activate_core_modules(container, lifecycle)
        settings_service: SettingsService = container.get_port("settings_service")
        settings_service.set_module_settings(
            "usermanagement",
            {"seed_mode": "hardened", "dev_mode": False},
            actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
            acknowledge_governance_change=True,
            reason="cli_init",
        )
        lifecycle.start()
        _seed_admin_credentials(container, admin_username, admin_password)
        print(
            json.dumps(
                {
                    "status": "initialized",
                    "app_home": str(app_home),
                    "users_db_path": users_db_path,
                    "documents_db_path": documents_db_path,
                    "artifacts_root": artifacts_root,
                    "registry_db_path": registry_db_path,
                    "admin_username": admin_username,
                    "seed_mode": "hardened",
                },
                ensure_ascii=True,
            )
        )
        return 0
    except (ValueError, KeyError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7


def cmd_doctor(*, strict: bool = False) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.prepare_core_modules(container)
    database_service, database_specs = runtime_bootstrap.configure_database_evolution(
        container,
        lifecycle,
    )
    runtime_bootstrap.capture_database_preflight_statuses(
        container,
        database_service,
        database_specs,
    )
    from qm_platform.settings.persistence_bootstrap import attach_settings_persistence

    try:
        database_service.migrate(database_specs, reason="doctor")
        attach_settings_persistence(container)
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED: {exc}")
        return 8
    database_statuses = database_service.statuses(database_specs)
    databases_current = all(status.ok for status in database_statuses)
    if databases_current:
        lifecycle.wire_all()
        lifecycle.start(strict=False)
    app_home = container.get_port("app_home")
    settings_service: SettingsService = container.get_port("settings_service")
    usermanagement = (
        container.get_port("usermanagement_service")
        if container.has_port("usermanagement_service")
        else None
    )
    user_cfg = settings_service.get_module_settings("usermanagement")
    checks = {}
    checks["database:no_interrupted_migration"] = (
        not database_service.has_interrupted_migration
    )
    paths = {
        "users_db": resolve_bootstrap_absolute_path(app_home, "usermanagement", "users_db_path"),
        "documents_db": resolve_bootstrap_absolute_path(app_home, "documents", "documents_db_path"),
        "artifacts_root": resolve_bootstrap_absolute_path(app_home, "documents", "artifacts_root"),
        "registry_db": resolve_bootstrap_absolute_path(app_home, "registry", "registry_db_path"),
        "platform_settings_db": resolve_platform_settings_db_path(app_home),
        "settings_residual_archive": resolve_home_path(app_home, RESIDUAL_ARCHIVE_REL),
        "license_file": resolve_home_path(app_home, "license/license.json"),
    }
    for key, path in paths.items():
        if key == "settings_residual_archive":
            # Optional until legacy cutover; require only that storage/platform exists.
            platform_root = resolve_home_path(app_home, "storage/platform")
            checks[f"path:{key}:exists_or_parent"] = bool(
                path.exists() or path.parent.exists() or platform_root.exists()
            )
        else:
            checks[f"path:{key}:exists_or_parent"] = bool(path.exists() or path.parent.exists())
        checks[f"path:{key}:writable"] = path_writable(path)
    checks["license:readable"] = paths["license_file"].exists()
    license_service = container.get_port("license_service")
    checks.update(
        build_license_diagnostics(
            license_service,
            licensed_modules=runtime_bootstrap.core_licensed_modules(),
            known_tags=set(runtime_bootstrap.core_license_tags()),
        )
    )
    checks["settings:modules_registered"] = all(
        module_id in settings_service.registry.list_module_ids()
        for module_id in ("usermanagement", "documents", "registry", "signature", "training")
    )
    for status in database_statuses:
        checks[f"database:{status.database_id}:version_current"] = (
            status.current_version == status.target_version and status.state == "current"
        )
        checks[f"database:{status.database_id}:integrity"] = status.integrity == "ok"
        checks[f"database:{status.database_id}:no_pending_migrations"] = (
            not status.pending_versions
        )
    checks["database:all_current"] = databases_current
    checks["users:admin_exists"] = bool(
        usermanagement is not None
        and any(
            user.username == "admin" and user.role == "Admin"
            for user in usermanagement.list_users()
        )
    )
    runtime_profile = os.environ.get("QMTOOL_RUNTIME_PROFILE", "").strip().lower()
    if runtime_profile in ("prod", "production"):
        production_seed_valid = str(user_cfg.get("seed_mode", "")).strip() in (
            "hardened",
            "admin_only",
        )
        checks["security:production_seed_mode_valid"] = production_seed_valid
        if not production_seed_valid:
            checks["security:production_profile_error"] = (
                "production profile requires usermanagement.seed_mode="
                "'hardened' or 'admin_only'"
            )
    if strict:
        checks["security:seed_mode_hardened"] = str(user_cfg.get("seed_mode", "")).strip() == "hardened"
        checks["security:password_hashes_only"] = bool(
            usermanagement is not None and _all_user_passwords_hashed(usermanagement)
        )
    gate_results = [value for value in checks.values() if isinstance(value, bool)]
    ok = bool(gate_results) and all(gate_results)
    print(
        json.dumps(
            {
                "ok": ok,
                "strict_mode": strict,
                "app_home": str(app_home),
                "checks": checks,
            },
            ensure_ascii=True,
        )
    )
    return 0 if ok else 8

