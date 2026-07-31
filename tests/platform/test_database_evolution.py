from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from qm_platform.persistence import (
    DataValidationQuery,
    DatabaseEvolutionError,
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)


def _write_migration(root: Path, version: int, sql: str) -> MigrationStep:
    path = root / f"{version:04d}_step.sql"
    path.write_text(sql, encoding="utf-8")
    return MigrationStep(version=version, name=f"step_{version}", sql_path=path)


def _spec(root: Path, *, versions: int = 1) -> DatabaseSpec:
    steps = [
        _write_migration(
            root,
            1,
            "CREATE TABLE records (record_id TEXT PRIMARY KEY, value TEXT NOT NULL);",
        )
    ]
    if versions >= 2:
        steps.append(
            _write_migration(
                root,
                2,
                "ALTER TABLE records ADD COLUMN note TEXT;",
            )
        )
    return DatabaseSpec(
        database_id="test",
        path=root / "test.db",
        migrations=tuple(steps),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_database_migrates_to_target_and_second_run_is_idempotent(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)

    first = service.migrate((spec,))
    second = service.migrate((spec,))

    assert first["ok"] is True
    assert first["backup_id"] is not None
    assert second["backup_id"] is None
    assert service.status(spec).ok is True
    with sqlite3.connect(spec.path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute(
            "SELECT version, name FROM _qm_schema_migrations"
        ).fetchall() == [(1, "step_1")]


def test_exact_unversioned_v1_database_is_adopted_without_data_loss(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    with sqlite3.connect(spec.path) as conn:
        conn.executescript(spec.migrations[0].sql_path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO records (record_id, value) VALUES ('r1', 'kept')")
    before_count = spec.path.stat().st_size
    service = DatabaseEvolutionService(app_home=tmp_path)

    assert service.status(spec).state == "adoptable_v1"
    service.migrate((spec,))

    with sqlite3.connect(spec.path) as conn:
        assert conn.execute("SELECT value FROM records WHERE record_id='r1'").fetchone() == (
            "kept",
        )
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert spec.path.stat().st_size >= before_count


def test_unknown_unversioned_database_is_not_modified(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    with sqlite3.connect(spec.path) as conn:
        conn.execute("CREATE TABLE unexpected (id INTEGER PRIMARY KEY)")
    before = _sha256(spec.path)
    service = DatabaseEvolutionService(app_home=tmp_path)

    with pytest.raises(DatabaseEvolutionError, match="unknown_unversioned"):
        service.migrate((spec,))

    assert _sha256(spec.path) == before


def test_too_new_database_is_blocked(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    with sqlite3.connect(spec.path) as conn:
        conn.executescript(spec.migrations[0].sql_path.read_text(encoding="utf-8"))
        conn.execute("PRAGMA user_version = 2")
    service = DatabaseEvolutionService(app_home=tmp_path)

    assert service.status(spec).state == "too_new"
    with pytest.raises(DatabaseEvolutionError, match="too_new"):
        service.migrate((spec,))


def test_changed_applied_migration_checksum_is_blocked(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((spec,))
    spec.migrations[0].sql_path.write_text(
        "CREATE TABLE records (record_id TEXT PRIMARY KEY, changed TEXT);",
        encoding="utf-8",
    )

    assert service.status(spec).state == "history_mismatch"


def test_failed_upgrade_restores_previous_database(tmp_path: Path) -> None:
    v1 = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((v1,))
    with closing(sqlite3.connect(v1.path)) as conn:
        conn.execute("INSERT INTO records (record_id, value) VALUES ('r1', 'kept')")
        conn.commit()
    before = _sha256(v1.path)
    broken = DatabaseSpec(
        database_id="test",
        path=v1.path,
        migrations=(
            v1.migrations[0],
            _write_migration(tmp_path, 2, "ALTER TABLE missing ADD COLUMN value TEXT;"),
        ),
    )

    with pytest.raises(sqlite3.OperationalError):
        service.migrate((broken,))

    assert _sha256(v1.path) == before
    with sqlite3.connect(v1.path) as conn:
        assert conn.execute("SELECT value FROM records").fetchall() == [("kept",)]
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_restore_rejects_tampered_backup_and_preserves_current_database(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((spec,))
    backup = service.create_backup(specs=(spec,), reason="manual")
    with closing(sqlite3.connect(spec.path)) as conn:
        conn.execute("INSERT INTO records (record_id, value) VALUES ('r1', 'current')")
        conn.commit()
    current_hash = _sha256(spec.path)
    manifest = json.loads(
        (Path(backup.path) / "manifest.json").read_text(encoding="utf-8")
    )
    backup_file = Path(backup.path) / "databases" / manifest["databases"][0]["filename"]
    backup_file.write_bytes(backup_file.read_bytes() + b"tampered")

    with pytest.raises(DatabaseEvolutionError, match="checksum mismatch"):
        service.restore(backup.backup_id, specs=(spec,))

    assert _sha256(spec.path) == current_hash


def test_restore_rejects_backup_path_traversal(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((spec,))

    with pytest.raises(DatabaseEvolutionError, match="invalid backup id"):
        service.restore("../outside", specs=(spec,))


def test_migration_chain_must_be_contiguous(tmp_path: Path) -> None:
    step = _write_migration(tmp_path, 2, "CREATE TABLE records (id INTEGER);")
    spec = DatabaseSpec("test", tmp_path / "test.db", (step,))
    service = DatabaseEvolutionService(app_home=tmp_path)

    with pytest.raises(DatabaseEvolutionError, match="start at version 1"):
        service.status(spec)


def test_manual_schema_change_after_migration_is_blocked(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((spec,))
    with closing(sqlite3.connect(spec.path)) as conn:
        conn.execute("ALTER TABLE records ADD COLUMN rogue TEXT")
        conn.commit()

    status = service.status(spec)

    assert status.state == "history_mismatch"
    assert "fingerprint" in str(status.detail)


def test_module_data_validator_blocks_invalid_rows(tmp_path: Path) -> None:
    base = _spec(tmp_path)
    spec = DatabaseSpec(
        database_id=base.database_id,
        path=base.path,
        migrations=base.migrations,
        validation_queries=(
            DataValidationQuery(
                name="blank values",
                sql="SELECT COUNT(*) FROM records WHERE TRIM(value) = ''",
            ),
        ),
    )
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((spec,))
    with closing(sqlite3.connect(spec.path)) as conn:
        conn.execute("INSERT INTO records (record_id, value) VALUES ('r1', '')")
        conn.commit()

    assert service.status(spec).state == "data_invalid"
    with pytest.raises(DatabaseEvolutionError, match="data_invalid"):
        service.migrate((spec,))


def test_interrupted_migration_is_restored_and_requires_retry(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((spec,))
    with closing(sqlite3.connect(spec.path)) as conn:
        conn.execute("INSERT INTO records (record_id, value) VALUES ('r1', 'before')")
        conn.commit()
    backup = service.create_backup(specs=(spec,), reason="interrupted_test")
    with closing(sqlite3.connect(spec.path)) as conn:
        conn.execute("UPDATE records SET value = 'partial' WHERE record_id = 'r1'")
        conn.commit()
    journal = tmp_path / "storage" / "platform" / "database-migration-journal.json"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        json.dumps({"backup_id": backup.backup_id, "database_ids": ["test"]}),
        encoding="utf-8",
    )

    with pytest.raises(DatabaseEvolutionError, match="interrupted migration was restored"):
        service.migrate((spec,))

    with closing(sqlite3.connect(spec.path)) as conn:
        assert conn.execute("SELECT value FROM records").fetchone() == ("before",)
    assert not journal.exists()


def test_stepwise_upgrade_matches_fresh_target_and_preserves_data(
    tmp_path: Path,
) -> None:
    stepwise_root = tmp_path / "stepwise"
    stepwise_root.mkdir()
    v1 = _spec(stepwise_root)
    service = DatabaseEvolutionService(app_home=tmp_path)
    service.migrate((v1,))
    with closing(sqlite3.connect(v1.path)) as conn:
        conn.execute("INSERT INTO records (record_id, value) VALUES ('r1', 'kept')")
        conn.commit()
    v2 = DatabaseSpec(
        database_id="test",
        path=v1.path,
        migrations=(
            v1.migrations[0],
            _write_migration(
                stepwise_root,
                2,
                "ALTER TABLE records ADD COLUMN note TEXT;",
            ),
        ),
    )
    service.migrate((v2,))

    fresh_root = tmp_path / "fresh"
    fresh_root.mkdir()
    fresh_v2 = _spec(fresh_root, versions=2)
    fresh_v2 = DatabaseSpec(
        database_id="fresh",
        path=fresh_v2.path,
        migrations=fresh_v2.migrations,
    )
    service.migrate((fresh_v2,))

    with closing(sqlite3.connect(v2.path)) as stepwise_conn:
        stepwise_columns = stepwise_conn.execute(
            "PRAGMA table_info(records)"
        ).fetchall()
        assert stepwise_conn.execute("SELECT record_id, value FROM records").fetchall() == [
            ("r1", "kept")
        ]
    with closing(sqlite3.connect(fresh_v2.path)) as fresh_conn:
        fresh_columns = fresh_conn.execute("PRAGMA table_info(records)").fetchall()
    assert stepwise_columns == fresh_columns


def test_concurrent_migration_attempt_is_rejected(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    service = DatabaseEvolutionService(app_home=tmp_path)

    with service._migration_lock():
        with pytest.raises(
            DatabaseEvolutionError,
            match="another database migration is running",
        ):
            service.migrate((spec,))
