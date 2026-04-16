from __future__ import annotations

import json
import os
from pathlib import Path
from getpass import getpass

from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.paths import path_writable, resolve_home_path, runtime_home
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
        lifecycle = runtime_bootstrap.register_core_modules(container)
        lifecycle.start()
        settings_service: SettingsService = container.get_port("settings_service")
        user_cfg = settings_service.get_module_settings("usermanagement")
        user_cfg["users_db_path"] = users_db_path
        user_cfg["seed_mode"] = "hardened"
        settings_service.set_module_settings("usermanagement", user_cfg, acknowledge_governance_change=True)

        docs_cfg = settings_service.get_module_settings("documents")
        docs_cfg["documents_db_path"] = documents_db_path
        docs_cfg["artifacts_root"] = artifacts_root
        settings_service.set_module_settings("documents", docs_cfg, acknowledge_governance_change=True)

        reg_cfg = settings_service.get_module_settings("registry")
        reg_cfg["registry_db_path"] = registry_db_path
        settings_service.set_module_settings("registry", reg_cfg, acknowledge_governance_change=True)

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
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    app_home = container.get_port("app_home")
    settings_service: SettingsService = container.get_port("settings_service")
    usermanagement = container.get_port("usermanagement_service")
    user_cfg = settings_service.get_module_settings("usermanagement")
    docs_cfg = settings_service.get_module_settings("documents")
    reg_cfg = settings_service.get_module_settings("registry")
    checks = {}
    paths = {
        "users_db": resolve_home_path(app_home, user_cfg.get("users_db_path", "storage/platform/users.db")),
        "documents_db": resolve_home_path(app_home, docs_cfg.get("documents_db_path", "storage/documents/documents.db")),
        "artifacts_root": resolve_home_path(app_home, docs_cfg.get("artifacts_root", "storage/documents/artifacts")),
        "registry_db": resolve_home_path(app_home, reg_cfg.get("registry_db_path", "storage/documents/registry.db")),
        "settings_file": resolve_home_path(app_home, "storage/platform/settings.json"),
        "license_file": resolve_home_path(app_home, "license/license.json"),
    }
    for key, path in paths.items():
        checks[f"path:{key}:exists_or_parent"] = bool(path.exists() or path.parent.exists())
        checks[f"path:{key}:writable"] = path_writable(path)
    checks["license:readable"] = paths["license_file"].exists()
    checks["settings:modules_registered"] = all(
        module_id in settings_service.registry.list_module_ids()
        for module_id in ("usermanagement", "documents", "registry", "signature", "training")
    )
    checks["users:admin_exists"] = any(u.username == "admin" and u.role == "Admin" for u in usermanagement.list_users())
    if strict:
        checks["security:seed_mode_hardened"] = str(user_cfg.get("seed_mode", "")).strip() == "hardened"
        checks["security:password_hashes_only"] = _all_user_passwords_hashed(usermanagement)
    ok = all(checks.values())
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

