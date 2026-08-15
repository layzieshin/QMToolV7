"""Bootstrap path resolution without SettingsService (J02)."""

from __future__ import annotations

import os
from pathlib import Path

from qm_platform.runtime.paths import resolve_home_path
from qm_platform.sdk.module_contract import DatabaseContribution


# Env override pattern: QMTOOL_DB_<DATABASE_ID>_PATH (uppercase id).
_ENV_PREFIX = "QMTOOL_DB_"


def env_key_for_database(database_id: str) -> str:
    return f"{_ENV_PREFIX}{database_id.upper()}_PATH"


def resolve_database_relative_path(contribution: DatabaseContribution) -> str:
    """Return relative or absolute path string from Env or contribution default."""
    env_name = env_key_for_database(contribution.database_id)
    raw = os.environ.get(env_name)
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return contribution.default_path


def resolve_database_absolute_path(app_home: Path, contribution: DatabaseContribution) -> Path:
    return resolve_home_path(app_home, resolve_database_relative_path(contribution))


BOOTSTRAP_PATH_DEFAULTS: dict[tuple[str, str], str] = {
    ("container", "container_db_path"): "storage/container/container.db",
    ("container", "artifact_files_root"): "storage/container/artifacts",
    ("usermanagement", "users_db_path"): "storage/platform/users.db",
    ("documents", "documents_db_path"): "storage/documents/documents.db",
    ("documents", "artifacts_root"): "storage/documents/artifacts",
    ("documents", "profiles_file"): "modules/documents/workflow_profiles.json",
    ("registry", "registry_db_path"): "storage/documents/registry.db",
    ("signature", "templates_db_path"): "storage/signature/templates.db",
    ("signature", "assets_root"): "storage/signature/assets",
    ("signature", "master_key_path"): "storage/platform/signature_master.key",
    ("training", "training_db_path"): "storage/training/training.db",
    ("training", "quiz_blob_root"): "storage/training/quiz_blobs",
    ("training", "quiz_master_key_path"): "storage/platform/training_quiz_master.key",
    ("incident_management", "incident_db_path"): "storage/incident_management/incidents.db",
    ("incident_management", "artifacts_root"): "storage/incident_management/artifacts",
}


def bootstrap_path_env_key(module_id: str, setting_key: str) -> str:
    return f"QMTOOL_PATH_{module_id.upper()}_{setting_key.upper()}"


def resolve_bootstrap_relative_path(module_id: str, setting_key: str) -> str:
    env_name = bootstrap_path_env_key(module_id, setting_key)
    raw = os.environ.get(env_name)
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    try:
        return BOOTSTRAP_PATH_DEFAULTS[(module_id, setting_key)]
    except KeyError as exc:
        raise KeyError(f"unknown bootstrap path key: {module_id}.{setting_key}") from exc


def resolve_bootstrap_absolute_path(app_home: Path, module_id: str, setting_key: str) -> Path:
    return resolve_home_path(app_home, resolve_bootstrap_relative_path(module_id, setting_key))


PLATFORM_SETTINGS_DATABASE_ID = "platform_settings"
PLATFORM_SETTINGS_DEFAULT_PATH = "storage/platform/platform_settings.db"


def resolve_platform_settings_db_path(app_home: Path) -> Path:
    env_name = env_key_for_database(PLATFORM_SETTINGS_DATABASE_ID)
    raw = os.environ.get(env_name)
    if raw is not None and str(raw).strip():
        return resolve_home_path(app_home, str(raw).strip())
    return resolve_home_path(app_home, PLATFORM_SETTINGS_DEFAULT_PATH)
