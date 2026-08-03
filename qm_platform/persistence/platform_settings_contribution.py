"""Platform-owned database contribution for J02 settings DB (not a fachliches Modul)."""

from __future__ import annotations

from pathlib import Path

from qm_platform.sdk.module_contract import DatabaseContribution, DatabaseMigrationContribution

from .path_resolver import PLATFORM_SETTINGS_DATABASE_ID, PLATFORM_SETTINGS_DEFAULT_PATH

PLATFORM_SETTINGS_DATABASE_CONTRIBUTION = DatabaseContribution(
    database_id=PLATFORM_SETTINGS_DATABASE_ID,
    module_id="qm_platform",
    setting_key="",  # path is bootstrap-only; never resolved via SettingsService
    default_path=PLATFORM_SETTINGS_DEFAULT_PATH,
    migrations=(
        DatabaseMigrationContribution(
            version=1,
            name="platform_settings",
            sql_path=Path(__file__).parent / "migrations" / "0001_platform_settings.sql",
        ),
        DatabaseMigrationContribution(
            version=2,
            name="platform_settings_integrity",
            sql_path=Path(__file__).parent / "migrations" / "0002_platform_settings_integrity.sql",
        ),
    ),
    validation_queries=(),
)
