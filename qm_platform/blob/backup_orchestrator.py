"""PostgreSQL + blob backup and restore orchestrator (OPS00-C)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from qm_platform.blob.contract import (
    BACKUP_SET_SEALED,
    BackupSetWrite,
    PlatformBlobWriteError,
)
from qm_platform.blob.filesystem_store import BlobInventoryEntry, FilesystemBlobStore
from qm_platform.blob.postgres_repository import PlatformBlobRepository
from qm_platform.persistence.postgres_schema import schema_fingerprint
from qm_platform.runtime.operation_lock import OperationLock, OperationLockError
from qm_platform.runtime.paths import resolve_home_path, runtime_home

MANIFEST_FILENAME = "manifest.json"
CHECKSUMS_FILENAME = "checksums.json"
DUMP_FILENAME = "database.dump"
BLOBS_DIRNAME = "blobs"
RESTORE_DB_PREFIX = "qmtool_ops00_restore_"
FORBIDDEN_RESTORE_DATABASES = frozenset({"qmtool_j04_destructive_test", "qmtool_test"})
FORBIDDEN_LAB_HOST = "192.168.0.4"
_SECRET_PATTERN = re.compile(r"(password|pwd)=([^\s\"']+)", re.IGNORECASE)


class BackupOrchestratorError(RuntimeError):
    """Raised when backup or restore cannot proceed safely."""


@dataclass(frozen=True)
class BackupResult:
    backup_id: str
    backup_path: str
    app_release_fingerprint: str
    schema_migration_fingerprint: str
    blob_count: int
    dump_checksum_sha256: str


@dataclass(frozen=True)
class RestoreResult:
    backup_id: str
    target_database: str
    restored_blob_count: int
    verified_artifact_count: int


def host_running_marker_path(app_home: Path | None = None) -> Path:
    home = app_home if app_home is not None else runtime_home()
    return resolve_home_path(home, "storage/platform/host-running.pid")


def is_host_running_marker_present(app_home: Path | None = None) -> bool:
    return host_running_marker_path(app_home).is_file()


def write_host_running_marker(app_home: Path | None = None) -> None:
    path = host_running_marker_path(app_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="ascii")


def remove_host_running_marker(app_home: Path | None = None) -> None:
    host_running_marker_path(app_home).unlink(missing_ok=True)


def backups_root(app_home: Path | None = None) -> Path:
    home = app_home if app_home is not None else runtime_home()
    return resolve_home_path(home, "backups")


def release_identity_path(app_home: Path | None = None) -> Path:
    home = app_home if app_home is not None else runtime_home()
    return resolve_home_path(home, "release/identity")


def compute_app_release_fingerprint(app_home: Path | None = None) -> str:
    path = release_identity_path(app_home)
    if not path.is_file():
        raise BackupOrchestratorError("app release identity file is missing")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_pg_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for version in ("18", "16"):
        candidate = Path(rf"C:\Program Files\PostgreSQL\{version}\bin") / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    raise BackupOrchestratorError(f"{name} not found on PATH")


def _subprocess_env_from_dsn(dsn: str) -> dict[str, str]:
    env = dict(os.environ)
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    password = info.get("password")
    if password is not None and str(password) != "":
        env["PGPASSWORD"] = str(password)
    return env


def _pg_dump_args(dsn: str, *, output_path: Path) -> list[str]:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    cmd = [
        _find_pg_tool("pg_dump"),
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(output_path),
    ]
    host = info.get("host")
    port = info.get("port")
    user = info.get("user")
    database = info.get("dbname") or info.get("database")
    if host:
        cmd.extend(["-h", str(host)])
    if port:
        cmd.extend(["-p", str(port)])
    if user:
        cmd.extend(["-U", str(user)])
    if not database:
        raise BackupOrchestratorError("source database name is missing from DSN")
    cmd.extend(["-d", str(database)])
    return cmd


def _pg_restore_args(dsn: str, *, dump_path: Path) -> list[str]:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    cmd = [
        _find_pg_tool("pg_restore"),
        "--no-owner",
        "--no-acl",
    ]
    host = info.get("host")
    port = info.get("port")
    user = info.get("user")
    database = info.get("dbname") or info.get("database")
    if host:
        cmd.extend(["-h", str(host)])
    if port:
        cmd.extend(["-p", str(port)])
    if user:
        cmd.extend(["-U", str(user)])
    if not database:
        raise BackupOrchestratorError("target database name is missing from DSN")
    cmd.extend(["-d", str(database), str(dump_path)])
    return cmd


def _conninfo_host_database(dsn: str) -> tuple[str, str]:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    host = str(info.get("host") or "127.0.0.1").strip().lower()
    if host == "localhost":
        host = "127.0.0.1"
    database = str(info.get("dbname") or info.get("database") or "").strip()
    return host, database


def _validate_restore_target_database(database_name: str, *, admin_dsn: str) -> None:
    name = str(database_name).strip()
    if name in FORBIDDEN_RESTORE_DATABASES:
        raise BackupOrchestratorError("restore target database name is forbidden")
    if not name.startswith(RESTORE_DB_PREFIX):
        raise BackupOrchestratorError(
            f"restore target database must start with {RESTORE_DB_PREFIX!r}"
        )
    host, source_db = _conninfo_host_database(admin_dsn)
    if host == FORBIDDEN_LAB_HOST or source_db == "qmtool_test":
        raise BackupOrchestratorError("lab PostgreSQL endpoint is forbidden for restore drill")
    if name == source_db:
        raise BackupOrchestratorError("restore target must not overwrite the source database")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_text_for_secrets(text: str) -> None:
    if _SECRET_PATTERN.search(text):
        raise BackupOrchestratorError("secret material must not be written to evidence")


def _safe_json_dumps(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2)
    _scan_text_for_secrets(encoded)
    return encoded


def _acquire_operation_lock(app_home: Path) -> OperationLock:
    lock = OperationLock(app_home=app_home)
    try:
        lock.acquire()
    except OperationLockError as exc:
        raise BackupOrchestratorError(
            "backup refused while exclusive operation lock is held"
        ) from exc
    return lock


def _bind_operation_lock(
    app_home: Path,
    held_operation_lock: OperationLock | None,
) -> tuple[OperationLock, bool]:
    """Return ``(lock, owns_lock)``. C releases only when ``owns_lock`` is True."""
    if held_operation_lock is None:
        return _acquire_operation_lock(app_home), True
    if type(held_operation_lock) is not OperationLock:
        raise BackupOrchestratorError(
            "held operation lock is invalid for this backup or restore"
        )
    try:
        held_operation_lock.validate_held_for(app_home)
    except OperationLockError as exc:
        raise BackupOrchestratorError(
            "held operation lock is invalid for this backup or restore"
        ) from exc
    return held_operation_lock, False


def _load_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise BackupOrchestratorError("backup manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupOrchestratorError("backup manifest is invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise BackupOrchestratorError("backup manifest must be a JSON object")
    return manifest


def _verify_manifest_files(backup_dir: Path, manifest: dict[str, Any]) -> dict[str, str]:
    dump_info = manifest.get("dump")
    if not isinstance(dump_info, dict):
        raise BackupOrchestratorError("backup manifest dump section is missing")
    dump_name = str(dump_info.get("filename") or DUMP_FILENAME)
    dump_path = backup_dir / dump_name
    if not dump_path.is_file():
        raise BackupOrchestratorError("backup dump file is missing")
    expected_dump_checksum = str(dump_info.get("checksum_sha256") or "")
    if len(expected_dump_checksum) != 64:
        raise BackupOrchestratorError("backup dump checksum is missing from manifest")
    actual_dump_checksum = _sha256_file(dump_path)
    if actual_dump_checksum != expected_dump_checksum.lower():
        raise BackupOrchestratorError("backup dump checksum mismatch")

    checksums_path = backup_dir / CHECKSUMS_FILENAME
    if not checksums_path.is_file():
        raise BackupOrchestratorError("backup checksums file is missing")
    try:
        checksums_doc = json.loads(checksums_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupOrchestratorError("backup checksums file is invalid JSON") from exc
    if not isinstance(checksums_doc, dict):
        raise BackupOrchestratorError("backup checksums file must be a JSON object")

    dump_checksum_entry = str(checksums_doc.get(dump_name) or "")
    if dump_checksum_entry.lower() != actual_dump_checksum.lower():
        raise BackupOrchestratorError(
            f"backup checksums file mismatch for dump {dump_name!r}"
        )

    blobs = manifest.get("blobs")
    if not isinstance(blobs, list):
        raise BackupOrchestratorError("backup manifest blobs section is missing")

    blobs_root = backup_dir / BLOBS_DIRNAME
    verified: dict[str, str] = {"dump": actual_dump_checksum}
    for item in blobs:
        if not isinstance(item, dict):
            raise BackupOrchestratorError("backup manifest blob entry is invalid")
        storage_key = str(item.get("storage_key") or "")
        expected_checksum = str(item.get("checksum_sha256") or "").lower()
        size_bytes = int(item.get("size_bytes") or 0)
        if not storage_key or len(expected_checksum) != 64 or size_bytes <= 0:
            raise BackupOrchestratorError("backup manifest blob entry is incomplete")
        blob_path = blobs_root / Path(storage_key.replace("/", os.sep))
        if not blob_path.is_file():
            raise BackupOrchestratorError(f"backup blob file is missing for key {storage_key!r}")
        actual_size = blob_path.stat().st_size
        if actual_size != size_bytes:
            raise BackupOrchestratorError(
                f"backup blob size mismatch for key {storage_key!r}"
            )
        actual_checksum = _sha256_file(blob_path)
        if actual_checksum != expected_checksum:
            raise BackupOrchestratorError(
                f"backup blob checksum mismatch for key {storage_key!r}"
            )
        file_checksum = str(checksums_doc.get(storage_key) or "")
        if file_checksum.lower() != expected_checksum:
            raise BackupOrchestratorError(
                f"backup checksums file mismatch for key {storage_key!r}"
            )
        verified[storage_key] = actual_checksum
    return verified


def create_backup(
    *,
    source_dsn: str,
    metadata_dsn: str,
    app_home: Path | None = None,
    blob_store: FilesystemBlobStore | None = None,
    backup_id: str | None = None,
    label: str | None = None,
    held_operation_lock: OperationLock | None = None,
) -> BackupResult:
    """Seal a whole-database dump and blob-tree backup set."""
    home = app_home if app_home is not None else runtime_home()
    resolved_backup_id = backup_id or str(uuid.uuid4())
    backup_dir = backups_root(home) / resolved_backup_id
    lock, owns_lock = _bind_operation_lock(home, held_operation_lock)
    try:
        if is_host_running_marker_present(home):
            raise BackupOrchestratorError(
                "backup refused while backend host running marker is present"
            )
        if backup_dir.exists():
            raise BackupOrchestratorError("backup destination already exists")

        app_fp = compute_app_release_fingerprint(home)
        store = blob_store or FilesystemBlobStore(
            resolve_home_path(home, "storage/platform/blobs")
        )

        with psycopg.connect(source_dsn) as conn:
            schema_fp = schema_fingerprint(conn)

        backup_dir.mkdir(parents=True, exist_ok=False)
        blobs_target = backup_dir / BLOBS_DIRNAME
        dump_path = backup_dir / DUMP_FILENAME

        pg_dump = _pg_dump_args(source_dsn, output_path=dump_path)
        dump_result = subprocess.run(
            pg_dump,
            env=_subprocess_env_from_dsn(source_dsn),
            capture_output=True,
            text=True,
            check=False,
        )
        if dump_result.returncode != 0:
            raise BackupOrchestratorError("pg_dump failed")

        inventory = store.inventory()
        blobs_target.mkdir(parents=True, exist_ok=True)
        blob_entries: list[dict[str, Any]] = []
        checksums_doc: dict[str, str] = {}
        for entry in inventory:
            source_path = store.resolve_path(entry.storage_key)
            target_path = blobs_target / Path(entry.storage_key.replace("/", os.sep))
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            blob_entries.append(
                {
                    "storage_key": entry.storage_key,
                    "checksum_sha256": entry.checksum_sha256,
                    "size_bytes": entry.size_bytes,
                }
            )
            checksums_doc[entry.storage_key] = entry.checksum_sha256

        dump_checksum = _sha256_file(dump_path)
        checksums_doc[DUMP_FILENAME] = dump_checksum
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        manifest = {
            "backup_id": resolved_backup_id,
            "created_at": created_at,
            "app_release_fingerprint": app_fp,
            "schema_migration_fingerprint": schema_fp,
            "dump": {
                "filename": DUMP_FILENAME,
                "checksum_sha256": dump_checksum,
            },
            "blobs": blob_entries,
        }
        (backup_dir / MANIFEST_FILENAME).write_text(
            _safe_json_dumps(manifest),
            encoding="utf-8",
        )
        (backup_dir / CHECKSUMS_FILENAME).write_text(
            _safe_json_dumps(checksums_doc),
            encoding="utf-8",
        )

        with psycopg.connect(metadata_dsn) as meta_conn:
            meta_conn.execute("SET ROLE qmtool_runtime")
            PlatformBlobRepository.insert_backup_set_on_connection(
                meta_conn,
                BackupSetWrite(
                    backup_set_id=resolved_backup_id,
                    label=label or f"ops00-backup-{resolved_backup_id[:8]}",
                    status=BACKUP_SET_SEALED,
                    created_at=datetime.fromisoformat(created_at),
                ),
            )
            meta_conn.commit()

        return BackupResult(
            backup_id=resolved_backup_id,
            backup_path=str(backup_dir),
            app_release_fingerprint=app_fp,
            schema_migration_fingerprint=schema_fp,
            blob_count=len(blob_entries),
            dump_checksum_sha256=dump_checksum,
        )
    except Exception:
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    finally:
        if owns_lock:
            lock.release()


def restore_backup_set(
    *,
    backup_dir: Path,
    target_admin_dsn: str,
    target_database: str,
    destination_blob_root: Path,
    app_home: Path | None = None,
    held_operation_lock: OperationLock | None = None,
) -> RestoreResult:
    """Restore a sealed backup set into an isolated target database and blob root."""
    home = app_home if app_home is not None else runtime_home()
    lock, owns_lock = _bind_operation_lock(home, held_operation_lock)
    try:
        _validate_restore_target_database(target_database, admin_dsn=target_admin_dsn)

        backup_path = Path(backup_dir)
        if not backup_path.is_dir():
            raise BackupOrchestratorError("backup set directory is missing")

        manifest = _load_manifest(backup_path)
        _verify_manifest_files(backup_path, manifest)

        backup_id = str(manifest.get("backup_id") or backup_path.name)
        blobs = manifest.get("blobs")
        if not isinstance(blobs, list):
            raise BackupOrchestratorError("backup manifest blobs section is missing")

        dump_info = manifest["dump"]
        dump_path = backup_path / str(dump_info.get("filename") or DUMP_FILENAME)
        blobs_source = backup_path / BLOBS_DIRNAME
        admin_info = psycopg.conninfo.conninfo_to_dict(target_admin_dsn)
        admin_info["dbname"] = "postgres"
        bootstrap_dsn = psycopg.conninfo.make_conninfo(**admin_info)

        with psycopg.connect(bootstrap_dsn, autocommit=True) as admin:
            admin.execute(
                psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    psycopg.sql.Identifier(target_database)
                )
            )
            admin.execute(
                psycopg.sql.SQL("CREATE DATABASE {}").format(
                    psycopg.sql.Identifier(target_database)
                )
            )

        target_info = dict(admin_info)
        target_info["dbname"] = target_database
        restore_dsn = psycopg.conninfo.make_conninfo(**target_info)

        pg_restore = _pg_restore_args(restore_dsn, dump_path=dump_path)
        restore_result = subprocess.run(
            pg_restore,
            env=_subprocess_env_from_dsn(restore_dsn),
            capture_output=True,
            text=True,
            check=False,
        )
        if restore_result.returncode != 0:
            raise BackupOrchestratorError("pg_restore failed")

        destination_blob_root.mkdir(parents=True, exist_ok=True)
        if blobs_source.is_dir():
            for item in blobs_source.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(blobs_source).as_posix()
                    target = destination_blob_root / Path(rel.replace("/", os.sep))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

        store = FilesystemBlobStore(destination_blob_root)
        fs_inventory = {entry.storage_key: entry for entry in store.inventory()}

        with psycopg.connect(restore_dsn) as conn:
            pg_rows = PlatformBlobRepository.list_artifacts_on_connection(conn)

        if len(pg_rows) != len(fs_inventory):
            raise BackupOrchestratorError(
                "restored blob artifact count does not match filesystem inventory"
            )

        for row in pg_rows:
            key = str(row["storage_key"])
            fs_entry = fs_inventory.get(key)
            if fs_entry is None:
                raise BackupOrchestratorError(
                    f"restored filesystem inventory missing key {key!r}"
                )
            if str(row["checksum_sha256"]).lower() != fs_entry.checksum_sha256:
                raise BackupOrchestratorError(
                    f"restored checksum mismatch for key {key!r}"
                )
            if int(row["size_bytes"]) != fs_entry.size_bytes:
                raise BackupOrchestratorError(
                    f"restored size mismatch for key {key!r}"
                )

        return RestoreResult(
            backup_id=backup_id,
            target_database=target_database,
            restored_blob_count=len(fs_inventory),
            verified_artifact_count=len(pg_rows),
        )
    finally:
        if owns_lock:
            lock.release()
