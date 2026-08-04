from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


MIGRATION_TABLE = "_qm_schema_migrations"
INTERNAL_TABLES = {MIGRATION_TABLE, "sqlite_sequence"}


class DatabaseEvolutionError(RuntimeError):
    """Raised when a database cannot be migrated without risking data."""


@dataclass(frozen=True)
class MigrationStep:
    version: int
    name: str
    sql_path: Path

    @property
    def checksum(self) -> str:
        normalized = self.sql_path.read_text(encoding="utf-8").encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()


@dataclass(frozen=True)
class DataValidationQuery:
    name: str
    sql: str


@dataclass(frozen=True)
class DatabaseSpec:
    database_id: str
    path: Path
    migrations: tuple[MigrationStep, ...]
    validation_queries: tuple[DataValidationQuery, ...] = ()

    @property
    def target_version(self) -> int:
        return self.migrations[-1].version if self.migrations else 0


@dataclass(frozen=True)
class DatabaseStatus:
    database_id: str
    path: str
    state: str
    current_version: int
    target_version: int
    pending_versions: tuple[int, ...]
    integrity: str
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.state == "current" and self.integrity == "ok"


@dataclass(frozen=True)
class DatabaseBackup:
    backup_id: str
    path: str
    created_at: str
    reason: str
    database_ids: tuple[str, ...]


class DatabaseEvolutionService:
    def __init__(self, *, app_home: Path, backup_root: Path | None = None) -> None:
        self._app_home = app_home.resolve()
        self._backup_root = (
            backup_root.resolve()
            if backup_root is not None
            else self._app_home / "storage" / "platform" / "backups" / "databases"
        )
        self._lock_path = self._app_home / "storage" / "platform" / "database-migration.lock"
        self._journal_path = self._app_home / "storage" / "platform" / "database-migration-journal.json"

    @property
    def has_interrupted_migration(self) -> bool:
        return self._journal_path.exists()

    def status(self, spec: DatabaseSpec) -> DatabaseStatus:
        self._validate_spec(spec)
        path = spec.path.resolve()
        if not path.exists() or path.stat().st_size == 0:
            return DatabaseStatus(
                database_id=spec.database_id,
                path=str(path),
                state="missing",
                current_version=0,
                target_version=spec.target_version,
                pending_versions=tuple(step.version for step in spec.migrations),
                integrity="not_run",
            )

        try:
            with self._connect_readonly(path) as conn:
                integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
                current = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if integrity != "ok":
                    return DatabaseStatus(
                        database_id=spec.database_id,
                        path=str(path),
                        state="corrupt",
                        current_version=current,
                        target_version=spec.target_version,
                        pending_versions=(),
                        integrity=integrity,
                        detail="SQLite integrity_check failed",
                    )
                if current > spec.target_version:
                    return DatabaseStatus(
                        database_id=spec.database_id,
                        path=str(path),
                        state="too_new",
                        current_version=current,
                        target_version=spec.target_version,
                        pending_versions=(),
                        integrity=integrity,
                        detail="database schema is newer than this application",
                    )
                if current == 0 and self._has_user_tables(conn):
                    if not self._matches_v1_fingerprint(conn, spec):
                        return DatabaseStatus(
                            database_id=spec.database_id,
                            path=str(path),
                            state="unknown_unversioned",
                            current_version=0,
                            target_version=spec.target_version,
                            pending_versions=(),
                            integrity=integrity,
                            detail="unversioned database does not match the V1 schema",
                        )
                    validation_error = self._data_validation_error(conn, spec)
                    if validation_error is not None:
                        return DatabaseStatus(
                            database_id=spec.database_id,
                            path=str(path),
                            state="data_invalid",
                            current_version=0,
                            target_version=spec.target_version,
                            pending_versions=(),
                            integrity=integrity,
                            detail=validation_error,
                        )
                    return DatabaseStatus(
                        database_id=spec.database_id,
                        path=str(path),
                        state="adoptable_v1",
                        current_version=0,
                        target_version=spec.target_version,
                        pending_versions=(1,),
                        integrity=integrity,
                    )
                history_error = self._history_error(conn, spec, current)
                if history_error is not None:
                    return DatabaseStatus(
                        database_id=spec.database_id,
                        path=str(path),
                        state="history_mismatch",
                        current_version=current,
                        target_version=spec.target_version,
                        pending_versions=(),
                        integrity=integrity,
                        detail=history_error,
                    )
                if current > 0 and not self._matches_version_fingerprint(
                    conn, spec, current
                ):
                    return DatabaseStatus(
                        database_id=spec.database_id,
                        path=str(path),
                        state="history_mismatch",
                        current_version=current,
                        target_version=spec.target_version,
                        pending_versions=(),
                        integrity=integrity,
                        detail="schema fingerprint does not match migration history",
                    )
                validation_error = self._data_validation_error(conn, spec)
                if validation_error is not None:
                    return DatabaseStatus(
                        database_id=spec.database_id,
                        path=str(path),
                        state="data_invalid",
                        current_version=current,
                        target_version=spec.target_version,
                        pending_versions=(),
                        integrity=integrity,
                        detail=validation_error,
                    )
                pending = tuple(
                    step.version for step in spec.migrations if step.version > current
                )
                return DatabaseStatus(
                    database_id=spec.database_id,
                    path=str(path),
                    state="current" if not pending else "pending",
                    current_version=current,
                    target_version=spec.target_version,
                    pending_versions=pending,
                    integrity=integrity,
                )
        except sqlite3.DatabaseError as exc:
            return DatabaseStatus(
                database_id=spec.database_id,
                path=str(path),
                state="corrupt",
                current_version=0,
                target_version=spec.target_version,
                pending_versions=(),
                integrity="failed",
                detail=str(exc),
            )

    def statuses(self, specs: tuple[DatabaseSpec, ...]) -> tuple[DatabaseStatus, ...]:
        return tuple(self.status(spec) for spec in specs)

    def migrate(
        self,
        specs: tuple[DatabaseSpec, ...],
        *,
        dry_run: bool = False,
        reason: str = "schema_migration",
    ) -> dict[str, object]:
        self._validate_specs(specs)
        if self.has_interrupted_migration:
            if dry_run:
                raise DatabaseEvolutionError(
                    "an interrupted database migration requires recovery"
                )
            with self._migration_lock():
                self._recover_interrupted_if_needed(specs)
        statuses = self.statuses(specs)
        blocked = [
            status
            for status in statuses
            if status.state
            in {
                "corrupt",
                "too_new",
                "unknown_unversioned",
                "history_mismatch",
                "data_invalid",
            }
        ]
        if blocked:
            details = "; ".join(
                f"{item.database_id}: {item.state} ({item.detail or 'no detail'})"
                for item in blocked
            )
            raise DatabaseEvolutionError(details)

        pending_specs = tuple(
            spec
            for spec, status in zip(specs, statuses, strict=True)
            if status.state != "current"
        )
        if dry_run or not pending_specs:
            return {
                "ok": True,
                "dry_run": dry_run,
                "backup_id": None,
                "databases": [asdict(status) for status in statuses],
            }

        with self._migration_lock():
            self._recover_interrupted_if_needed(specs)
            refreshed = self.statuses(specs)
            blocked_after_lock = [
                status
                for status in refreshed
                if status.state
                in {
                    "corrupt",
                    "too_new",
                    "unknown_unversioned",
                    "history_mismatch",
                    "data_invalid",
                }
            ]
            if blocked_after_lock:
                raise DatabaseEvolutionError("database state changed during migration preflight")
            pending_specs = tuple(
                spec
                for spec, status in zip(specs, refreshed, strict=True)
                if status.state != "current"
            )
            if not pending_specs:
                return {
                    "ok": True,
                    "dry_run": False,
                    "backup_id": None,
                    "databases": [asdict(status) for status in refreshed],
                }

            backup = self.create_backup(specs=specs, reason=reason)
            self._write_journal(backup=backup, specs=specs)
            try:
                for spec in pending_specs:
                    self._migrate_one(spec)
                final_statuses = self.statuses(specs)
                failed = [status for status in final_statuses if not status.ok]
                if failed:
                    raise DatabaseEvolutionError(
                        "post-migration verification failed: "
                        + "; ".join(f"{item.database_id}: {item.state}" for item in failed)
                    )
            except Exception:
                self._restore_backup(backup.backup_id, specs=specs)
                raise
            finally:
                self._journal_path.unlink(missing_ok=True)

        return {
            "ok": True,
            "dry_run": False,
            "backup_id": backup.backup_id,
            "databases": [asdict(status) for status in self.statuses(specs)],
        }

    def create_backup(
        self,
        *,
        specs: tuple[DatabaseSpec, ...],
        reason: str,
    ) -> DatabaseBackup:
        self._backup_root.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc)
        backup_id = f"{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        final_dir = self._backup_root / backup_id
        final_dir.mkdir()
        entries: list[dict[str, object]] = []
        try:
            databases_dir = final_dir / "databases"
            databases_dir.mkdir(parents=True, exist_ok=True)
            for spec in specs:
                source = spec.path.resolve()
                if not source.exists() or source.stat().st_size == 0:
                    entries.append(
                        {
                            "database_id": spec.database_id,
                            "source_path": str(source),
                            "present": False,
                        }
                    )
                    continue
                target = databases_dir / f"{spec.database_id}.db"
                self._sqlite_backup(source, target)
                integrity = self._integrity(target)
                if integrity != "ok":
                    raise DatabaseEvolutionError(
                        f"backup integrity failed for {spec.database_id}: {integrity}"
                    )
                entries.append(
                    {
                        "database_id": spec.database_id,
                        "source_path": str(source),
                        "present": True,
                        "filename": target.name,
                        "size_bytes": target.stat().st_size,
                        "sha256": self._sha256_file(target),
                        "user_version": self._user_version(target),
                    }
                )
            residual_entry = self._backup_residual_archive(final_dir)
            if residual_entry["present"] and not any(
                entry.get("database_id") == "platform_settings"
                and bool(entry.get("present"))
                for entry in entries
            ):
                raise DatabaseEvolutionError(
                    "residual archive backup requires platform_settings database"
                )
            manifest = {
                "backup_id": backup_id,
                "created_at": created_at.isoformat(),
                "reason": reason,
                "databases": entries,
                "residual_archive": residual_entry,
            }
            (final_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except Exception:
            shutil.rmtree(final_dir, ignore_errors=True)
            raise
        return DatabaseBackup(
            backup_id=backup_id,
            path=str(final_dir),
            created_at=created_at.isoformat(),
            reason=reason,
            database_ids=tuple(spec.database_id for spec in specs),
        )

    def list_backups(self) -> tuple[DatabaseBackup, ...]:
        if not self._backup_root.exists():
            return ()
        backups: list[DatabaseBackup] = []
        for manifest_path in sorted(self._backup_root.glob("*/manifest.json"), reverse=True):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                entries = payload.get("databases", [])
                backups.append(
                    DatabaseBackup(
                        backup_id=str(payload["backup_id"]),
                        path=str(manifest_path.parent),
                        created_at=str(payload["created_at"]),
                        reason=str(payload["reason"]),
                        database_ids=tuple(str(item["database_id"]) for item in entries),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return tuple(backups)

    def restore(self, backup_id: str, *, specs: tuple[DatabaseSpec, ...]) -> dict[str, object]:
        self._validate_specs(specs)
        with self._migration_lock():
            self._load_validated_backup(backup_id, specs=specs)
            safety = self.create_backup(specs=specs, reason=f"pre_restore:{backup_id}")
            try:
                self._restore_backup(backup_id, specs=specs)
            except Exception:
                self._restore_backup(safety.backup_id, specs=specs)
                raise
        return {
            "ok": True,
            "restored_backup_id": backup_id,
            "safety_backup_id": safety.backup_id,
        }

    def _migrate_one(self, spec: DatabaseSpec) -> None:
        path = spec.path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.exists() and path.stat().st_size > 0
        if existing:
            with self._connect_readonly(path) as read_conn:
                current = int(read_conn.execute("PRAGMA user_version").fetchone()[0])
                adopt_v1 = current == 0 and self._has_user_tables(read_conn)
        else:
            current = 0
            adopt_v1 = False

        if adopt_v1:
            step = spec.migrations[0]
            with closing(sqlite3.connect(path)) as conn:
                self._apply_metadata_transaction(conn, step)
            current = step.version

        for step in spec.migrations:
            if step.version <= current:
                continue
            sql = step.sql_path.read_text(encoding="utf-8")
            quoted_name = step.name.replace("'", "''")
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{sql}\n"
                f"{self._migration_table_sql()}\n"
                f"INSERT INTO {MIGRATION_TABLE} "
                "(version, name, checksum, applied_at) VALUES "
                f"({step.version}, '{quoted_name}', '{step.checksum}', "
                f"'{datetime.now(timezone.utc).isoformat()}');\n"
                f"PRAGMA user_version = {step.version};\n"
                "COMMIT;\n"
            )
            with closing(sqlite3.connect(path)) as conn:
                try:
                    conn.executescript(script)
                except Exception:
                    if conn.in_transaction:
                        conn.rollback()
                    raise
            current = step.version

    def _apply_metadata_transaction(
        self,
        conn: sqlite3.Connection,
        step: MigrationStep,
    ) -> None:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(self._migration_table_sql())
            conn.execute(
                f"""
                INSERT INTO {MIGRATION_TABLE} (version, name, checksum, applied_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    step.version,
                    step.name,
                    step.checksum,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.execute(f"PRAGMA user_version = {step.version}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _history_error(
        self,
        conn: sqlite3.Connection,
        spec: DatabaseSpec,
        current: int,
    ) -> str | None:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (MIGRATION_TABLE,),
        ).fetchone()
        if current == 0:
            return None
        if table_exists is None:
            return "versioned database has no migration history table"
        rows = conn.execute(
            f"SELECT version, name, checksum FROM {MIGRATION_TABLE} ORDER BY version"
        ).fetchall()
        expected_steps = [step for step in spec.migrations if step.version <= current]
        if len(rows) != len(expected_steps):
            return "migration history length does not match user_version"
        for row, step in zip(rows, expected_steps, strict=True):
            if (
                int(row[0]) != step.version
                or str(row[1]) != step.name
                or str(row[2]) != step.checksum
            ):
                return f"migration history mismatch at version {step.version}"
        return None

    def _matches_v1_fingerprint(
        self,
        conn: sqlite3.Connection,
        spec: DatabaseSpec,
    ) -> bool:
        if not spec.migrations or spec.migrations[0].version != 1:
            return False
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.row_factory = sqlite3.Row
            expected.executescript(spec.migrations[0].sql_path.read_text(encoding="utf-8"))
            return self._schema_fingerprint(conn) == self._schema_fingerprint(expected)

    def _matches_version_fingerprint(
        self,
        conn: sqlite3.Connection,
        spec: DatabaseSpec,
        version: int,
    ) -> bool:
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.row_factory = sqlite3.Row
            for step in spec.migrations:
                if step.version > version:
                    break
                expected.executescript(step.sql_path.read_text(encoding="utf-8"))
            return self._schema_fingerprint(conn) == self._schema_fingerprint(expected)

    @staticmethod
    def _data_validation_error(
        conn: sqlite3.Connection,
        spec: DatabaseSpec,
    ) -> str | None:
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            return f"foreign key validation failed ({len(foreign_key_errors)} row(s))"
        for query in spec.validation_queries:
            row = conn.execute(query.sql).fetchone()
            invalid_count = int(row[0]) if row is not None else 0
            if invalid_count:
                return f"{query.name} failed ({invalid_count} row(s))"
        return None

    @staticmethod
    def _schema_fingerprint(conn: sqlite3.Connection) -> tuple[object, ...]:
        tables = [
            str(row[0])
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != ?
                ORDER BY name
                """,
                (MIGRATION_TABLE,),
            ).fetchall()
        ]
        table_rows: list[object] = []
        for table in tables:
            columns = tuple(sorted(
                (
                    str(row[1]),
                    str(row[2]).upper(),
                    int(row[3]),
                    None if row[4] is None else str(row[4]),
                    int(row[5]),
                )
                for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            ))
            foreign_keys = tuple(
                sorted(
                    tuple(str(value) for value in row)
                    for row in conn.execute(
                        f'PRAGMA foreign_key_list("{table}")'
                    ).fetchall()
                )
            )
            indexes = []
            for index in conn.execute(f'PRAGMA index_list("{table}")').fetchall():
                index_name = str(index[1])
                indexes.append(
                    (
                        index_name,
                        int(index[2]),
                        str(index[3]),
                        int(index[4]),
                        tuple(
                            str(column[2])
                            for column in conn.execute(
                                f'PRAGMA index_info("{index_name}")'
                            ).fetchall()
                        ),
                    )
                )
            table_rows.append((table, columns, foreign_keys, tuple(sorted(indexes))))
        return tuple(table_rows)

    @staticmethod
    def _has_user_tables(conn: sqlite3.Connection) -> bool:
        return (
            conn.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != ?
                LIMIT 1
                """,
                (MIGRATION_TABLE,),
            ).fetchone()
            is not None
        )

    def _recover_interrupted_if_needed(self, specs: tuple[DatabaseSpec, ...]) -> None:
        if not self._journal_path.exists():
            return
        try:
            payload = json.loads(self._journal_path.read_text(encoding="utf-8"))
            backup_id = str(payload["backup_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DatabaseEvolutionError("invalid interrupted migration journal") from exc
        self._restore_backup(backup_id, specs=specs)
        self._journal_path.unlink(missing_ok=True)
        raise DatabaseEvolutionError(
            "an interrupted migration was restored; retry requires an explicit new run"
        )

    def _write_journal(
        self,
        *,
        backup: DatabaseBackup,
        specs: tuple[DatabaseSpec, ...],
    ) -> None:
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "backup_id": backup.backup_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "database_ids": [spec.database_id for spec in specs],
        }
        temp = self._journal_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        temp.replace(self._journal_path)

    def _load_validated_backup(
        self,
        backup_id: str,
        *,
        specs: tuple[DatabaseSpec, ...],
    ) -> tuple[Path, dict[str, object]]:
        if (
            not backup_id
            or backup_id in {".", ".."}
            or Path(backup_id).name != backup_id
        ):
            raise DatabaseEvolutionError("invalid backup id")
        backup_dir = (self._backup_root / backup_id).resolve()
        if backup_dir.parent != self._backup_root.resolve():
            raise DatabaseEvolutionError("invalid backup id")
        manifest_path = backup_dir / "manifest.json"
        if not manifest_path.exists():
            raise DatabaseEvolutionError(f"unknown backup: {backup_id}")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if str(payload.get("backup_id")) != backup_id:
            raise DatabaseEvolutionError("backup manifest id mismatch")
        configured = {
            spec.database_id: spec.path.resolve()
            for spec in specs
        }
        seen_ids: set[str] = set()
        backup_database_files: dict[str, Path | None] = {}
        databases = payload.get("databases")
        if not isinstance(databases, list):
            raise DatabaseEvolutionError("backup manifest databases must be a list")
        for entry in databases:
            if not isinstance(entry, dict):
                raise DatabaseEvolutionError("backup database entry must be an object")
            database_id = str(entry["database_id"])
            if database_id in seen_ids:
                raise DatabaseEvolutionError(
                    f"duplicate database in backup: {database_id}"
                )
            seen_ids.add(database_id)
            source_path = Path(str(entry["source_path"])).resolve()
            if configured.get(database_id) != source_path:
                raise DatabaseEvolutionError(
                    f"backup target mismatch for {database_id}"
                )
            if not bool(entry.get("present")):
                backup_database_files[database_id] = None
                continue
            backup_file = backup_dir / "databases" / str(entry["filename"])
            expected_hash = str(entry["sha256"])
            if not backup_file.is_file():
                raise DatabaseEvolutionError(
                    f"backup file missing for {entry['database_id']}"
                )
            if self._sha256_file(backup_file) != expected_hash:
                raise DatabaseEvolutionError(
                    f"backup checksum mismatch for {entry['database_id']}"
                )
            if self._integrity(backup_file) != "ok":
                raise DatabaseEvolutionError(
                    f"backup integrity failed for {entry['database_id']}"
                )
            backup_database_files[database_id] = backup_file
        expected_ids = set(configured)
        if seen_ids != expected_ids:
            missing = sorted(expected_ids - seen_ids)
            unexpected = sorted(seen_ids - expected_ids)
            raise DatabaseEvolutionError(
                "backup manifest database set mismatch"
                + (f"; missing={missing}" if missing else "")
                + (f"; unexpected={unexpected}" if unexpected else "")
            )
        from qm_platform.settings.residual_store import RESIDUAL_ARCHIVE_REL
        from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

        residual = payload.get("residual_archive")
        if not isinstance(residual, dict):
            raise DatabaseEvolutionError(
                "backup residual_archive metadata missing or invalid"
            )
        required_common = {
            "present",
            "relative_path",
            "cutover_status",
            "db_hash_anchor",
        }
        missing_common = sorted(required_common - set(residual))
        if missing_common:
            raise DatabaseEvolutionError(
                "backup residual_archive metadata incomplete: "
                + ", ".join(missing_common)
            )
        if type(residual["present"]) is not bool:
            raise DatabaseEvolutionError("backup residual present must be boolean")
        if residual["relative_path"] != RESIDUAL_ARCHIVE_REL:
            raise DatabaseEvolutionError("backup residual relative_path mismatch")
        if not residual["present"] and (
            residual["db_hash_anchor"] is not None
            or residual["cutover_status"] is not None
        ):
            raise DatabaseEvolutionError(
                "backup residual absent but cutover/hash metadata indicates completed cutover"
            )

        db_cutover_status: str | None = None
        db_hash_anchor: str | None = None
        settings_backup = backup_database_files.get("platform_settings")
        if settings_backup is not None:
            try:
                with self._connect_readonly(settings_backup) as conn:
                    rows = conn.execute(
                        """
                        SELECT integrity_key, integrity_value
                        FROM platform_settings_integrity
                        WHERE integrity_key IN (?, ?)
                        """,
                        (
                            SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
                            SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
                        ),
                    ).fetchall()
            except sqlite3.Error as exc:
                raise DatabaseEvolutionError(
                    "backup platform settings integrity metadata unavailable"
                ) from exc
            integrity = {str(key): str(value) for key, value in rows}
            db_cutover_status = integrity.get(
                SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS
            )
            db_hash_anchor = integrity.get(
                SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256
            )
        if residual["cutover_status"] != db_cutover_status:
            raise DatabaseEvolutionError(
                "backup residual cutover_status does not match platform settings database"
            )
        if residual["db_hash_anchor"] != db_hash_anchor:
            raise DatabaseEvolutionError(
                "backup residual db_hash_anchor does not match platform settings database"
            )

        if residual["present"]:
            required_present = {
                "filename",
                "hash_filename",
                "size_bytes",
                "sha256",
                "sidecar_sha256",
            }
            missing_present = sorted(required_present - set(residual))
            if missing_present:
                raise DatabaseEvolutionError(
                    "backup residual_archive metadata incomplete: "
                    + ", ".join(missing_present)
                )
            if settings_backup is None:
                raise DatabaseEvolutionError(
                    "backup residual archive requires platform_settings database"
                )
            if residual["filename"] != "settings.json":
                raise DatabaseEvolutionError("backup residual filename mismatch")
            if residual["hash_filename"] != "settings.json.sha256":
                raise DatabaseEvolutionError("backup residual sidecar filename mismatch")
            residual_file = backup_dir / "residual" / "settings.json"
            expected_hash = str(residual["sha256"] or "")
            if not residual_file.is_file():
                raise DatabaseEvolutionError("backup residual archive file missing")
            if self._sha256_file(residual_file) != expected_hash:
                raise DatabaseEvolutionError("backup residual archive checksum mismatch")
            if residual_file.stat().st_size != residual["size_bytes"]:
                raise DatabaseEvolutionError("backup residual archive size mismatch")
            sidecar = backup_dir / "residual" / "settings.json.sha256"
            if not sidecar.is_file():
                raise DatabaseEvolutionError("backup residual sidecar missing")
            expected_sidecar_hash = str(residual["sidecar_sha256"] or "")
            if self._sha256_file(sidecar) != expected_sidecar_hash:
                raise DatabaseEvolutionError("backup residual sidecar checksum mismatch")
            if sidecar.read_text(encoding="utf-8") != f"{expected_hash}  settings.json\n":
                raise DatabaseEvolutionError("backup residual sidecar content mismatch")
            if residual["cutover_status"] != "completed":
                raise DatabaseEvolutionError(
                    "backup residual present but cutover_status is not completed"
                )
            db_anchor = residual["db_hash_anchor"]
            if db_anchor is None or str(db_anchor).strip() == "":
                raise DatabaseEvolutionError(
                    "backup residual present but db_hash_anchor is missing"
                )
            if str(db_anchor) != expected_hash:
                raise DatabaseEvolutionError(
                    "backup residual db_hash_anchor does not match archive sha256"
                )
        return backup_dir, payload

    def _restore_backup(
        self,
        backup_id: str,
        *,
        specs: tuple[DatabaseSpec, ...],
    ) -> None:
        backup_dir, payload = self._load_validated_backup(
            backup_id,
            specs=specs,
        )
        for entry in payload.get("databases", []):
            source_path = Path(str(entry["source_path"])).resolve()
            if not bool(entry.get("present")):
                source_path.unlink(missing_ok=True)
                continue
            backup_file = backup_dir / "databases" / str(entry["filename"])
            source_path.parent.mkdir(parents=True, exist_ok=True)
            temp_target = source_path.with_name(f".{source_path.name}.restore-{uuid.uuid4().hex}")
            shutil.copy2(backup_file, temp_target)
            os.replace(temp_target, source_path)
        self._restore_residual_archive(backup_dir, payload)

    @contextmanager
    def _migration_lock(self) -> Iterator[None]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = None
        try:
            lock_file = self._lock_path.open("a+b")
            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
        except OSError as exc:
            if lock_file is not None:
                lock_file.close()
            raise DatabaseEvolutionError(
                "another database migration is running"
            ) from exc
        locked = False
        try:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                raise DatabaseEvolutionError("another database migration is running") from exc
            yield
        finally:
            try:
                if locked:
                    if os.name == "nt":
                        import msvcrt

                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                lock_file.close()

    def _backup_residual_archive(self, backup_dir: Path) -> dict[str, object]:
        from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
        from qm_platform.settings.residual_store import (
            RESIDUAL_ARCHIVE_REL,
            ResidualSettingsStore,
        )
        from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

        residual = ResidualSettingsStore.under_app_home(self._app_home)
        repo = SqliteSettingsRepository(resolve_platform_settings_db_path(self._app_home))
        cutover_status = repo.get_integrity(SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS)
        db_hash = repo.get_integrity(SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256)
        if not residual.exists():
            if cutover_status is not None or db_hash is not None:
                raise DatabaseEvolutionError(
                    "residual archive missing while platform settings integrity metadata exists"
                )
            return {
                "present": False,
                "relative_path": RESIDUAL_ARCHIVE_REL,
                "cutover_status": cutover_status,
                "db_hash_anchor": db_hash,
            }
        digest = residual.sha256()
        if cutover_status != "completed":
            raise DatabaseEvolutionError(
                "residual archive exists without completed cutover metadata"
            )
        if db_hash != digest:
            raise DatabaseEvolutionError(
                "residual archive does not match platform settings hash anchor"
            )
        if not residual.hash_path.is_file():
            raise DatabaseEvolutionError("residual archive sidecar missing")
        if residual.hash_path.read_text(encoding="utf-8") != f"{digest}  settings.json\n":
            raise DatabaseEvolutionError("residual archive sidecar content mismatch")
        residual_dir = backup_dir / "residual"
        residual_dir.mkdir(parents=True, exist_ok=True)
        target = residual_dir / "settings.json"
        shutil.copy2(residual.archive_path, target)
        hash_target = residual_dir / "settings.json.sha256"
        hash_target.write_text(
            f"{digest}  settings.json\n",
            encoding="utf-8",
            newline="\n",
        )
        return {
            "present": True,
            "relative_path": RESIDUAL_ARCHIVE_REL,
            "filename": "settings.json",
            "hash_filename": "settings.json.sha256",
            "size_bytes": target.stat().st_size,
            "sha256": digest,
            "sidecar_sha256": self._sha256_file(hash_target),
            "cutover_status": cutover_status,
            "db_hash_anchor": db_hash,
        }

    def _restore_residual_archive(
        self,
        backup_dir: Path,
        payload: dict[str, object],
    ) -> None:
        from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
        from qm_platform.settings.residual_store import ResidualSettingsStore
        from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

        residual_meta = payload.get("residual_archive")
        live = ResidualSettingsStore.under_app_home(self._app_home)
        if not isinstance(residual_meta, dict) or not bool(residual_meta.get("present")):
            live.archive_path.unlink(missing_ok=True)
            live.hash_path.unlink(missing_ok=True)
            return
        backup_file = backup_dir / "residual" / str(
            residual_meta.get("filename", "settings.json")
        )
        hash_name = str(residual_meta.get("hash_filename", "settings.json.sha256"))
        hash_file = backup_dir / "residual" / hash_name
        live.archive_path.parent.mkdir(parents=True, exist_ok=True)
        temp_archive = live.archive_path.with_name(
            f".{live.archive_path.name}.restore-{uuid.uuid4().hex}"
        )
        shutil.copy2(backup_file, temp_archive)
        os.replace(temp_archive, live.archive_path)
        if hash_file.is_file():
            temp_hash = live.hash_path.with_name(
                f".{live.hash_path.name}.restore-{uuid.uuid4().hex}"
            )
            shutil.copy2(hash_file, temp_hash)
            os.replace(temp_hash, live.hash_path)
        else:
            digest = self._sha256_file(live.archive_path)
            live.hash_path.write_text(
                f"{digest}  settings.json\n",
                encoding="utf-8",
                newline="\n",
            )
        repo = SqliteSettingsRepository(resolve_platform_settings_db_path(self._app_home))
        expected = repo.get_integrity(SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256)
        cutover_status = repo.get_integrity(
            SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS
        )
        if not expected or expected != residual_meta.get("db_hash_anchor"):
            raise DatabaseEvolutionError(
                "restored residual archive does not match DB hash anchor"
            )
        if cutover_status != "completed":
            raise DatabaseEvolutionError(
                "restored residual archive has no completed cutover marker"
            )
        anchored = ResidualSettingsStore.under_app_home(
            self._app_home, expected_sha256=expected
        )
        anchored.verify()

    @staticmethod
    def _validate_spec(spec: DatabaseSpec) -> None:
        versions = [step.version for step in spec.migrations]
        if not spec.database_id.strip():
            raise DatabaseEvolutionError("database_id is required")
        if not versions or versions[0] != 1:
            raise DatabaseEvolutionError(
                f"{spec.database_id}: migration chain must start at version 1"
            )
        if versions != list(range(1, len(versions) + 1)):
            raise DatabaseEvolutionError(
                f"{spec.database_id}: migration versions must be contiguous"
            )
        if len({step.name for step in spec.migrations}) != len(spec.migrations):
            raise DatabaseEvolutionError(f"{spec.database_id}: duplicate migration name")
        invalid_names = [
            step.sql_path.name
            for step in spec.migrations
            if not step.sql_path.name.startswith(f"{step.version:04d}_")
        ]
        if invalid_names:
            raise DatabaseEvolutionError(
                f"{spec.database_id}: invalid migration filenames: {', '.join(invalid_names)}"
            )
        missing = [str(step.sql_path) for step in spec.migrations if not step.sql_path.is_file()]
        if missing:
            raise DatabaseEvolutionError(
                f"{spec.database_id}: missing migration files: {', '.join(missing)}"
            )

    def _validate_specs(self, specs: tuple[DatabaseSpec, ...]) -> None:
        if len({spec.database_id for spec in specs}) != len(specs):
            raise DatabaseEvolutionError("duplicate database_id")
        paths = [str(spec.path.resolve()).casefold() for spec in specs]
        if len(set(paths)) != len(paths):
            raise DatabaseEvolutionError("multiple database specs resolve to the same path")
        for spec in specs:
            self._validate_spec(spec)

    @staticmethod
    def _migration_table_sql() -> str:
        return f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """

    @staticmethod
    @contextmanager
    def _connect_readonly(path: Path) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _sqlite_backup(source: Path, target: Path) -> None:
        with closing(sqlite3.connect(source, timeout=30.0)) as source_conn:
            checkpoint = source_conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
            if checkpoint is not None and int(checkpoint[0]) != 0:
                raise DatabaseEvolutionError(
                    f"database is busy and cannot be backed up: {source}"
                )
            source_conn.execute("BEGIN EXCLUSIVE")
            try:
                shutil.copy2(source, target)
            finally:
                source_conn.rollback()

    @staticmethod
    def _integrity(path: Path) -> str:
        with closing(
            sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        ) as conn:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])

    @staticmethod
    def _user_version(path: Path) -> int:
        with closing(
            sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        ) as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
