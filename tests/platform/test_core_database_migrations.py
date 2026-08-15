from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from interfaces.cli.bootstrap import build_container
from qm_platform.runtime import bootstrap as runtime_bootstrap


REPOSITORY_FILES = (
    Path("modules/documents/sqlite_repository.py"),
    Path("modules/registry/sqlite_repository.py"),
    Path("modules/usermanagement/sqlite_repository.py"),
    Path("modules/signature/sqlite_repository.py"),
    Path("modules/training/training_tag_repository.py"),
    Path("modules/training/training_override_repository.py"),
    Path("modules/training/training_snapshot_repository.py"),
    Path("modules/training/training_quiz_repository.py"),
    Path("modules/training/training_comment_repository.py"),
    Path("modules/training/training_report_repository.py"),
    Path("modules/incident_management/sqlite_repository.py"),
    Path("modules/container/sqlite_repository.py"),
)


def _runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    container = build_container()
    lifecycle = runtime_bootstrap.prepare_core_modules(container)
    service, specs = runtime_bootstrap.configure_database_evolution(
        container,
        lifecycle,
    )
    return container, lifecycle, service, specs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_restore_targets(
    app_home: Path,
    specs,
) -> tuple[dict[str, str], bytes | None, bytes | None]:
    from qm_platform.settings.residual_store import ResidualSettingsStore

    residual = ResidualSettingsStore.under_app_home(app_home)
    return (
        {spec.database_id: _sha256(spec.path) for spec in specs},
        residual.archive_path.read_bytes() if residual.archive_path.is_file() else None,
        residual.hash_path.read_bytes() if residual.hash_path.is_file() else None,
    )


def test_all_seven_databases_build_from_empty_and_wire_after_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _container, lifecycle, service, specs = _runtime(tmp_path, monkeypatch)

    assert [spec.database_id for spec in specs] == [
        "documents",
        "incidents",
        "platform_settings",
        "registry",
        "signature",
        "training",
        "users",
    ]
    dry_run = service.migrate(specs, dry_run=True)
    assert dry_run["dry_run"] is True
    assert not any(spec.path.exists() for spec in specs)

    service.migrate(specs, reason="test_fresh_install")
    from qm_platform.settings.persistence_bootstrap import attach_settings_persistence

    attach_settings_persistence(_container)
    assert all(status.ok for status in service.statuses(specs))
    for spec in specs:
        with closing(sqlite3.connect(spec.path)) as conn:
            if spec.database_id == "users":
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
                assert conn.execute(
                    "SELECT version, name FROM _qm_schema_migrations ORDER BY version"
                ).fetchall() == [
                    (1, "initial"),
                    (2, "deactivated_at"),
                ]
            elif spec.database_id == "platform_settings":
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
                assert conn.execute(
                    "SELECT version, name FROM _qm_schema_migrations ORDER BY version"
                ).fetchall() == [
                    (1, "platform_settings"),
                    (2, "platform_settings_integrity"),
                ]
            elif spec.database_id == "documents":
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
                assert conn.execute(
                    "SELECT version, name FROM _qm_schema_migrations ORDER BY version"
                ).fetchall() == [
                    (1, "initial"),
                    (2, "workflow_profiles"),
                ]
            else:
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
                assert conn.execute(
                    "SELECT version, name FROM _qm_schema_migrations"
                ).fetchall() == [(1, "initial")]
    from qm_platform.persistence.database_evolution import (
        DATABASE_PREFLIGHT_STATUSES_PORT,
        DatabaseStatus,
    )
    from types import MappingProxyType

    docs_spec = next(spec for spec in specs if spec.database_id == "documents")
    _container.register_port(
        DATABASE_PREFLIGHT_STATUSES_PORT,
        MappingProxyType(
            {
                "documents": DatabaseStatus(
                    database_id="documents",
                    path=str(docs_spec.path),
                    state="missing",
                    current_version=0,
                    target_version=docs_spec.target_version,
                    pending_versions=tuple(step.version for step in docs_spec.migrations),
                    integrity="not_run",
                )
            }
        ),
    )
    lifecycle.wire_all()


def test_complete_seven_database_backup_restore_is_byte_exact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    from qm_platform.settings.residual_store import ResidualSettingsStore
    from qm_platform.settings.testing import write_residual_policy_archive

    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 11}}},
    )
    from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
    from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository
    from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR

    residual = ResidualSettingsStore.under_app_home(tmp_path)
    residual_before = residual.sha256()
    repo = SqliteSettingsRepository(resolve_platform_settings_db_path(tmp_path))
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        residual_before,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "completed",
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    residual = ResidualSettingsStore.under_app_home(
        tmp_path, expected_sha256=residual_before
    )
    before = {spec.database_id: _sha256(spec.path) for spec in specs}
    backup = service.create_backup(specs=specs, reason="restore_drill")
    manifest = json.loads((Path(backup.path) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["residual_archive"]["present"] is True
    assert manifest["residual_archive"]["sha256"] == residual_before

    for spec in specs:
        with closing(sqlite3.connect(spec.path)) as conn:
            conn.execute("CREATE TABLE restore_drill_mutation (id INTEGER)")
            conn.commit()
    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 12}}},
    )
    changed_digest = ResidualSettingsStore.under_app_home(tmp_path).sha256()
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        changed_digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )

    result = service.restore(backup.backup_id, specs=specs)

    assert result["ok"] is True
    assert {
        spec.database_id: _sha256(spec.path) for spec in specs
    } == before
    assert residual.sha256() == residual_before
    assert all(status.ok for status in service.statuses(specs))


def test_restore_rejects_tampered_residual_archive_in_backup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError
    from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
    from qm_platform.settings.residual_store import ResidualSettingsStore
    from qm_platform.settings.testing import write_residual_policy_archive
    from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
    from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 11}}},
    )
    residual = ResidualSettingsStore.under_app_home(tmp_path)
    digest = residual.sha256()
    repo = SqliteSettingsRepository(resolve_platform_settings_db_path(tmp_path))
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "completed",
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    backup = service.create_backup(specs=specs, reason="residual_tamper")
    residual_file = Path(backup.path) / "residual" / "settings.json"
    residual_file.write_text('{"tampered": true}', encoding="utf-8")
    before = _snapshot_restore_targets(tmp_path, specs)
    with pytest.raises(DatabaseEvolutionError, match="residual archive checksum"):
        service.restore(backup.backup_id, specs=specs)
    assert _snapshot_restore_targets(tmp_path, specs) == before


def test_restore_rejects_missing_residual_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError
    from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
    from qm_platform.settings.residual_store import ResidualSettingsStore
    from qm_platform.settings.testing import write_residual_policy_archive
    from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
    from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 11}}},
    )
    residual = ResidualSettingsStore.under_app_home(tmp_path)
    digest = residual.sha256()
    repo = SqliteSettingsRepository(resolve_platform_settings_db_path(tmp_path))
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "completed",
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    backup = service.create_backup(specs=specs, reason="missing_sidecar")
    (Path(backup.path) / "residual" / "settings.json.sha256").unlink()
    before = _snapshot_restore_targets(tmp_path, specs)
    with pytest.raises(DatabaseEvolutionError, match="sidecar missing"):
        service.restore(backup.backup_id, specs=specs)
    assert _snapshot_restore_targets(tmp_path, specs) == before


def test_restore_rejects_tampered_residual_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError
    from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
    from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
    from qm_platform.settings.residual_store import ResidualSettingsStore
    from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository
    from qm_platform.settings.testing import write_residual_policy_archive

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 11}}},
    )
    residual = ResidualSettingsStore.under_app_home(tmp_path)
    digest = residual.sha256()
    repo = SqliteSettingsRepository(resolve_platform_settings_db_path(tmp_path))
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "completed",
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    backup = service.create_backup(specs=specs, reason="tampered_sidecar")
    sidecar = Path(backup.path) / "residual" / "settings.json.sha256"
    sidecar.write_text("0" * 64 + "  settings.json\n", encoding="utf-8")
    before = _snapshot_restore_targets(tmp_path, specs)
    with pytest.raises(DatabaseEvolutionError, match="sidecar checksum"):
        service.restore(backup.backup_id, specs=specs)
    assert _snapshot_restore_targets(tmp_path, specs) == before


def test_restore_rejects_absent_residual_with_completed_cutover_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    backup = service.create_backup(specs=specs, reason="pre_cutover")
    manifest_path = Path(backup.path) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["residual_archive"] = {
        "present": False,
        "relative_path": "storage/platform/settings_residual_archive/settings.json",
        "cutover_status": "completed",
        "db_hash_anchor": "deadbeef",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
    before = _snapshot_restore_targets(tmp_path, specs)
    with pytest.raises(DatabaseEvolutionError, match="cutover/hash metadata"):
        service.restore(backup.backup_id, specs=specs)
    assert _snapshot_restore_targets(tmp_path, specs) == before


def test_restore_rejects_residual_db_hash_anchor_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError
    from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
    from qm_platform.settings.residual_store import ResidualSettingsStore
    from qm_platform.settings.testing import write_residual_policy_archive
    from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
    from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 11}}},
    )
    residual = ResidualSettingsStore.under_app_home(tmp_path)
    digest = residual.sha256()
    repo = SqliteSettingsRepository(resolve_platform_settings_db_path(tmp_path))
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    repo.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "completed",
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    backup = service.create_backup(specs=specs, reason="anchor_mismatch")
    manifest_path = Path(backup.path) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["residual_archive"]["db_hash_anchor"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
    before = _snapshot_restore_targets(tmp_path, specs)
    with pytest.raises(DatabaseEvolutionError, match="db_hash_anchor"):
        service.restore(backup.backup_id, specs=specs)
    assert _snapshot_restore_targets(tmp_path, specs) == before


def test_restore_rejects_manifest_missing_expected_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    backup = service.create_backup(specs=specs, reason="missing_db")
    manifest_path = Path(backup.path) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["databases"] = [
        entry for entry in manifest["databases"] if entry["database_id"] != "training"
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
    before = _snapshot_restore_targets(tmp_path, specs)
    with pytest.raises(DatabaseEvolutionError, match="database set mismatch"):
        service.restore(backup.backup_id, specs=specs)
    assert _snapshot_restore_targets(tmp_path, specs) == before


def test_restore_rejects_missing_malformed_or_incomplete_residual_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest
    from qm_platform.persistence import DatabaseEvolutionError

    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    backup = service.create_backup(specs=specs, reason="invalid_residual_metadata")
    manifest_path = Path(backup.path) / "manifest.json"
    valid_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = _snapshot_restore_targets(tmp_path, specs)

    invalid_values = (
        None,
        [],
        {"present": False},
        {
            "present": True,
            "relative_path": "storage/platform/settings_residual_archive/settings.json",
            "cutover_status": None,
            "db_hash_anchor": None,
        },
    )
    for value in invalid_values:
        manifest = dict(valid_manifest)
        if value is None:
            manifest.pop("residual_archive", None)
        else:
            manifest["residual_archive"] = value
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=True),
            encoding="utf-8",
        )
        with pytest.raises(DatabaseEvolutionError, match="residual_archive"):
            service.restore(backup.backup_id, specs=specs)
        assert _snapshot_restore_targets(tmp_path, specs) == before


def test_pre_cutover_backup_restores_without_residual(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    before = {spec.database_id: _sha256(spec.path) for spec in specs}
    backup = service.create_backup(specs=specs, reason="pre_cutover")
    manifest = json.loads((Path(backup.path) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["residual_archive"]["present"] is False
    for spec in specs:
        with closing(sqlite3.connect(spec.path)) as conn:
            conn.execute("CREATE TABLE restore_drill_mutation (id INTEGER)")
            conn.commit()
    result = service.restore(backup.backup_id, specs=specs)
    assert result["ok"] is True
    assert {spec.database_id: _sha256(spec.path) for spec in specs} == before


def test_repository_sources_contain_no_schema_mutation_logic() -> None:
    forbidden = ("ALTER TABLE", "executescript(", "_ensure_schema")
    findings = []
    for path in REPOSITORY_FILES:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                findings.append(f"{path}:{token}")

    assert findings == []


def test_module_migration_chains_are_contiguous_and_immutable_named() -> None:
    for contract in runtime_bootstrap.all_module_contracts():
        for contribution in contract.database_contributions:
            versions = [
                migration.version for migration in contribution.migrations
            ]
            assert versions == list(range(1, len(versions) + 1))
            for migration in contribution.migrations:
                assert migration.sql_path.name.startswith(
                    f"{migration.version:04d}_"
                )
                assert migration.sql_path.is_file()
