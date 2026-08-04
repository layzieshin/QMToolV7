"""Test helpers for DB-backed SettingsService (J02)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.documents.module import DOCUMENTS_SETTINGS_CONTRIBUTION
from modules.incident_management.module import INCIDENT_SETTINGS_CONTRIBUTION
from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.training.module import TRAINING_SETTINGS_CONTRIBUTION
from modules.usermanagement.module import USERMANAGEMENT_SETTINGS_CONTRIBUTION
from qm_platform.persistence.database_evolution import (
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)
from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
from qm_platform.persistence.platform_settings_contribution import (
    PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
)
from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
from qm_platform.settings.atomic_io import atomic_write_text
from qm_platform.settings.expected_keys import (
    build_complete_bucket_b_payloads,
    build_complete_bucket_c_payloads_from_defaults,
)
from qm_platform.settings.residual_store import (
    ResidualSettingsStore,
    write_residual_archive_bytes,
)
from qm_platform.settings.settings_cutover import (
    JOURNAL_STATUS_COMPLETED,
    JOURNAL_VERSION,
    cutover_journal_path,
)
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

_CORE_SETTINGS_CONTRIBUTIONS = (
    USERMANAGEMENT_SETTINGS_CONTRIBUTION,
    SIGNATURE_SETTINGS_CONTRIBUTION,
    TRAINING_SETTINGS_CONTRIBUTION,
    DOCUMENTS_SETTINGS_CONTRIBUTION,
    INCIDENT_SETTINGS_CONTRIBUTION,
)


def _core_registry() -> SettingsRegistry:
    registry = SettingsRegistry()
    for contribution in _CORE_SETTINGS_CONTRIBUTIONS:
        registry.register(contribution)
    return registry


def write_residual_policy_archive(
    app_home: Path,
    modules: dict[str, dict[str, Any]] | None = None,
    *,
    repository: SqliteSettingsRepository | None = None,
    seed_bucket_b: bool = False,
    merge_complete_defaults: bool = True,
) -> ResidualSettingsStore:
    """Write residual archive (defaults ⊕ overrides by default), sidecar, optional DB anchor."""
    if merge_complete_defaults:
        registry = _core_registry()
        complete = build_complete_bucket_c_payloads_from_defaults(registry)
        for module_id, blob in (modules or {}).items():
            complete.setdefault(module_id, {}).update(blob)
        payload = complete
        planned = sorted(build_complete_bucket_b_payloads(registry))
    else:
        registry = _core_registry()
        payload = dict(modules or {})
        planned = []
    raw = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
    _, digest = write_residual_archive_bytes(app_home, raw)
    if repository is not None:
        if seed_bucket_b:
            for module_id, values in build_complete_bucket_b_payloads(registry).items():
                contribution = registry.get(module_id)
                assert contribution is not None
                repository.replace_module_technical(
                    module_id,
                    values,
                    actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
                    schema_version=int(contribution.schema_version),
                    reason="test_residual_seed",
                )
        repository.set_integrity(
            SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
            digest,
            actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
        )
        repository.set_integrity(
            SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
            "completed",
            actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
        )
        journal = {
            "version": JOURNAL_VERSION,
            "status": JOURNAL_STATUS_COMPLETED,
            "cutover_id": "test-residual-seed",
            "source_path": None,
            "source_sha256": None,
            "planned_modules": planned,
            "imported_modules": planned,
            "archive_sha256": digest,
        }
        atomic_write_text(
            cutover_journal_path(app_home),
            json.dumps(journal, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        )
        return ResidualSettingsStore.under_app_home(app_home, expected_sha256=digest)
    return ResidualSettingsStore.under_app_home(app_home, expected_sha256=digest)


def build_settings_service_for_tests(
    root: Path,
    *,
    residual_policy: dict[str, dict[str, Any]] | None = None,
) -> SettingsService:
    """Create a SettingsService with migrated platform_settings SQLite under ``root``.

    When ``residual_policy`` is omitted, persistence is attached without a residual so
    ``attach_settings_persistence`` / ``ensure_settings_residual_ready`` can seed Bucket-C
    defaults after contributions are registered.
    """
    contrib = PLATFORM_SETTINGS_DATABASE_CONTRIBUTION
    db_path = resolve_platform_settings_db_path(root)
    evolution = DatabaseEvolutionService(app_home=root, backup_root=root / "settings-backups")
    evolution.migrate(
        (
            DatabaseSpec(
                database_id=contrib.database_id,
                path=db_path,
                migrations=tuple(
                    MigrationStep(
                        version=item.version,
                        name=item.name,
                        sql_path=item.sql_path,
                    )
                    for item in contrib.migrations
                ),
            ),
        ),
        reason="test_settings",
    )
    repository = SqliteSettingsRepository(db_path)
    service = SettingsService(SettingsRegistry())
    if residual_policy is not None:
        residual = write_residual_policy_archive(
            root,
            residual_policy,
            repository=repository,
            seed_bucket_b=True,
        )
        service.attach_persistence(repository, residual, cutover_completed=True)
    else:
        service.attach_persistence(repository, None, require_residual_if_present=False)
    return service
