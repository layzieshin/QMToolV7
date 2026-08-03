"""Attach DB + residual settings persistence after platform_settings migration."""

from __future__ import annotations

from pathlib import Path

from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
from qm_platform.settings.settings_cutover import ensure_settings_residual_ready
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository


def attach_settings_persistence(container, *, app_home: Path | None = None) -> SettingsService:
    """Open DB-backed settings after the seven databases have been migrated."""
    home = Path(app_home) if app_home is not None else Path(container.get_port("app_home"))
    settings: SettingsService = container.get_port("settings_service")
    repository = SqliteSettingsRepository(resolve_platform_settings_db_path(home))
    settings.attach_persistence(repository, None, require_residual_if_present=False)

    def _pre_mutation_backup() -> str | None:
        if not container.has_port("database_evolution_service"):
            return None
        if not container.has_port("database_specs"):
            return None
        evolution = container.get_port("database_evolution_service")
        specs = container.get_port("database_specs")
        backup = evolution.create_backup(specs=specs, reason="pre_j02_settings_cutover")
        return backup.backup_id

    ensure_settings_residual_ready(
        home,
        settings,
        pre_mutation_backup=_pre_mutation_backup,
    )
    return settings


def refresh_backup_reminder_from_settings(container) -> None:
    """Update backup reminder threshold from technical settings after attach."""
    if not container.has_port("log_backup_service"):
        return
    from qm_platform.logging.backup_reminder import BackupReminderService

    settings: SettingsService = container.get_port("settings_service")
    backup_service = container.get_port("log_backup_service")
    threshold_days = int(
        settings.get_module_settings("documents").get("logs_backup_reminder_days", 30)
    )
    container.register_port(
        "backup_reminder_service",
        BackupReminderService(backup_service, threshold_days=threshold_days),
    )
