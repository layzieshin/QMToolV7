from __future__ import annotations

import hashlib
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


def test_all_six_databases_build_from_empty_and_wire_after_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _container, lifecycle, service, specs = _runtime(tmp_path, monkeypatch)

    assert [spec.database_id for spec in specs] == [
        "documents",
        "incidents",
        "registry",
        "signature",
        "training",
        "users",
    ]
    dry_run = service.migrate(specs, dry_run=True)
    assert dry_run["dry_run"] is True
    assert not any(spec.path.exists() for spec in specs)

    service.migrate(specs, reason="test_fresh_install")

    assert all(status.ok for status in service.statuses(specs))
    for spec in specs:
        with closing(sqlite3.connect(spec.path)) as conn:
            if spec.database_id == "users":
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
                assert conn.execute(
                    "SELECT version, name FROM _qm_schema_migrations ORDER BY version"
                ).fetchall() == [(1, "initial"), (2, "deactivated_at")]
            else:
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
                assert conn.execute(
                    "SELECT version, name FROM _qm_schema_migrations"
                ).fetchall() == [(1, "initial")]
    lifecycle.wire_all()


def test_complete_six_database_backup_restore_is_byte_exact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _container, _lifecycle, service, specs = _runtime(tmp_path, monkeypatch)
    service.migrate(specs, reason="test_fresh_install")
    before = {spec.database_id: _sha256(spec.path) for spec in specs}
    backup = service.create_backup(specs=specs, reason="restore_drill")

    for spec in specs:
        with closing(sqlite3.connect(spec.path)) as conn:
            conn.execute("CREATE TABLE restore_drill_mutation (id INTEGER)")
            conn.commit()

    result = service.restore(backup.backup_id, specs=specs)

    assert result["ok"] is True
    assert {
        spec.database_id: _sha256(spec.path) for spec in specs
    } == before
    assert all(status.ok for status in service.statuses(specs))


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
    for contract in runtime_bootstrap.core_module_contracts():
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
